#!/usr/bin/env python3
"""
Deletes a VM from vCenter via pyVmomi.

Usage:
  vcenter_vm_delete.py <hostname> <username> <password> <vm_name> <datacenter>

Powers off the VM if running before destroying it.
"""

import json
import ssl
import sys

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


def delete_vm(hostname, username, password, vm_name, datacenter_name):
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

        view = content.viewManager.CreateContainerView(dc, [vim.VirtualMachine], True)
        vm = next(
            (v for v in view.view if v.name == vm_name and v.config and not v.config.template),
            None
        )
        view.Destroy()

        if not vm:
            return {"error": "", "result": "VM not found — nothing to delete", "vm": vm_name}

        try:
            powered_on = vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn
        except AttributeError:
            powered_on = False

        if powered_on:
            wait_for_task(vm.PowerOffVM_Task())

        wait_for_task(vm.Destroy_Task())
        return {"error": "", "result": "VM deleted", "vm": vm_name}
    finally:
        Disconnect(si)


if __name__ == "__main__":
    if len(sys.argv) != 6:
        print(json.dumps({"error": "Usage: vcenter_vm_delete.py <hostname> <username> <password> <vm_name> <datacenter>"}))
        sys.exit(1)

    _, hostname, username, password, vm_name, datacenter = sys.argv
    result = delete_vm(hostname, username, password, vm_name, datacenter)
    print(json.dumps(result))
