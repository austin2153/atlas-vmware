#!/usr/bin/env python3
"""
Creates a VM by cloning a template in vCenter via pyVmomi (SOAP API).

Usage:
  vcenter_create_vm.py <hostname> <username> <password> <json_spec>

json_spec fields:
  vm_name        - Name for the new VM
  datacenter     - Datacenter name
  cluster        - Cluster name
  datastore      - Datastore name
  template_moid  - MOID of the source template
  folder         - VM folder path (e.g. "vm" for root VM folder)
  cpu            - Number of vCPUs
  memory_mb      - Memory in MB

community.vmware.vmware_guest silently no-ops for VM creation on vcsim.
This script calls CloneVM_Task() directly via pyVmomi.
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


def find_datacenter(content, name):
    view = content.viewManager.CreateContainerView(
        content.rootFolder, [vim.Datacenter], True)
    dc = next((d for d in view.view if d.name == name), None)
    view.Destroy()
    return dc


def find_cluster(content, dc, name):
    view = content.viewManager.CreateContainerView(
        dc, [vim.ClusterComputeResource], True)
    cluster = next((c for c in view.view if c.name == name), None)
    view.Destroy()
    return cluster


def find_datastore(content, dc, name):
    view = content.viewManager.CreateContainerView(
        dc, [vim.Datastore], True)
    ds = next((d for d in view.view if d.name == name), None)
    view.Destroy()
    return ds


def find_folder(dc, folder_name):
    """Find a VM folder by name under the datacenter's vmFolder."""
    def _walk(folder):
        if folder.name == folder_name:
            return folder
        for child in getattr(folder, 'childEntity', []):
            if isinstance(child, vim.Folder):
                result = _walk(child)
                if result:
                    return result
        return None
    return _walk(dc.vmFolder)


def get_template_by_moid(content, moid):
    view = content.viewManager.CreateContainerView(
        content.rootFolder, [vim.VirtualMachine], True)
    template = next((vm for vm in view.view if vm._moId == moid), None)
    view.Destroy()
    return template


def create_vm(hostname, username, password, spec):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    si = SmartConnect(host=hostname, user=username, pwd=password, sslContext=ctx)
    try:
        content = si.RetrieveContent()

        dc = find_datacenter(content, spec['datacenter'])
        if not dc:
            return {"error": f"Datacenter '{spec['datacenter']}' not found"}

        cluster = find_cluster(content, dc, spec['cluster'])
        if not cluster:
            return {"error": f"Cluster '{spec['cluster']}' not found"}

        datastore = find_datastore(content, dc, spec['datastore'])
        if not datastore:
            return {"error": f"Datastore '{spec['datastore']}' not found"}

        template = get_template_by_moid(content, spec['template_moid'])
        if not template:
            return {"error": f"Template with MOID '{spec['template_moid']}' not found"}

        folder = find_folder(dc, spec.get('folder', 'vm')) or dc.vmFolder

        relocate_spec = vim.vm.RelocateSpec(
            pool=cluster.resourcePool,
            datastore=datastore,
        )

        config_spec = vim.vm.ConfigSpec(
            numCPUs=int(spec.get('cpu', 2)),
            memoryMB=int(spec.get('memory_mb', 4096)),
        )

        clone_spec = vim.vm.CloneSpec(
            location=relocate_spec,
            config=config_spec,
            powerOn=False,
            template=False,
        )

        task = template.CloneVM_Task(
            folder=folder,
            name=spec['vm_name'],
            spec=clone_spec,
        )
        vm = wait_for_task(task)

        return {
            "error": "",
            "vm": {
                "name": vm.name,
                "moid": vm._moId,
                "guest_id": vm.config.guestId if vm.config else None,
                "cpu": vm.config.hardware.numCPU if vm.config else None,
                "memory_mb": vm.config.hardware.memoryMB if vm.config else None,
                "datastore": datastore.name,
                "cluster": cluster.name,
                "hostname": hostname,
                "datacenter": spec['datacenter'],
            }
        }
    finally:
        Disconnect(si)


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(json.dumps({"error": "Usage: vcenter_create_vm.py <hostname> <username> <password> <json_spec>"}))
        sys.exit(1)

    _, hostname, username, password, json_spec = sys.argv
    try:
        spec = json.loads(json_spec)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON spec: {e}"}))
        sys.exit(1)

    result = create_vm(hostname, username, password, spec)
    print(json.dumps(result))
