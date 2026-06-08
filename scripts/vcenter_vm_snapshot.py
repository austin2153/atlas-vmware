#!/usr/bin/env python3
"""
Manages VM snapshots in vCenter via pyVmomi.

Usage:
  vcenter_vm_snapshot.py <hostname> <username> <password> <vm_name> <datacenter> <action> [snapshot_name]

action: create | list | delete_all
"""

import json
import ssl
import sys
from datetime import datetime

from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim


def wait_for_task(task):
    while task.info.state not in (
        vim.TaskInfo.State.success,
        vim.TaskInfo.State.error,
    ):
        pass
    if task.info.state == vim.TaskInfo.State.error:
        raise Exception(f"Task failed: {task.info.error.msg}")
    return task.info.result


def find_vm(content, dc, vm_name):
    view = content.viewManager.CreateContainerView(dc, [vim.VirtualMachine], True)
    vm = next(
        (v for v in view.view if v.name == vm_name and v.config and not v.config.template),
        None
    )
    view.Destroy()
    return vm


def list_snapshots(snapshot_tree, snapshots=None):
    if snapshots is None:
        snapshots = []
    for snap in snapshot_tree:
        snapshots.append({
            "name": snap.name,
            "description": snap.description,
            "created": str(snap.createTime),
            "state": snap.state,
        })
        if snap.childSnapshotList:
            list_snapshots(snap.childSnapshotList, snapshots)
    return snapshots


def manage_snapshot(hostname, username, password, vm_name, datacenter_name, action, snapshot_name=None):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    si = SmartConnect(host=hostname, user=username, pwd=password, sslContext=ctx)
    try:
        content = si.RetrieveContent()

        dc = next(
            (d for d in content.viewManager.CreateContainerView(
                content.rootFolder, [vim.Datacenter], True).view
             if d.name == datacenter_name),
            None
        )
        if not dc:
            return {"error": f"Datacenter '{datacenter_name}' not found"}

        vm = find_vm(content, dc, vm_name)
        if not vm:
            return {"error": f"VM '{vm_name}' not found"}

        if action == "create":
            name = snapshot_name or f"snapshot-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            wait_for_task(vm.CreateSnapshot_Task(
                name=name,
                description="",
                memory=False,
                quiesce=False,
            ))
            return {"error": "", "result": f"snapshot '{name}' created", "vm": vm_name}

        elif action == "list":
            if not vm.snapshot:
                return {"error": "", "snapshots": [], "vm": vm_name}
            snapshots = list_snapshots(vm.snapshot.rootSnapshotList)
            return {"error": "", "snapshots": snapshots, "vm": vm_name}

        elif action == "delete_all":
            if not vm.snapshot:
                return {"error": "", "result": "no snapshots to delete", "vm": vm_name}
            wait_for_task(vm.RemoveAllSnapshots_Task())
            return {"error": "", "result": "all snapshots deleted", "vm": vm_name}

        else:
            return {"error": f"Unknown action '{action}'. Use: create, list, delete_all"}
    finally:
        Disconnect(si)


if __name__ == "__main__":
    if len(sys.argv) not in (7, 8):
        print(json.dumps({"error": "Usage: vcenter_vm_snapshot.py <hostname> <username> <password> <vm_name> <datacenter> <action> [snapshot_name]"}))
        sys.exit(1)

    _, hostname, username, password, vm_name, datacenter, action = sys.argv[:7]
    snapshot_name = sys.argv[7] if len(sys.argv) == 8 else None
    result = manage_snapshot(hostname, username, password, vm_name, datacenter, action, snapshot_name)
    print(json.dumps(result))
