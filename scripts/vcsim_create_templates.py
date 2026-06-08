#!/usr/bin/env python3
"""
Creates template VMs in a vcsim instance via pyVmomi.

vcsim does not support vmware_guest for creating VMs. This script uses
the SOAP API directly to create minimal VMs and mark them as templates.

Usage:
  vcsim_create_templates.py <hostname> <username> <password>

Creates: rhel9-template, ubuntu22-template, win2022-template in Templates folder.
"""

import json
import ssl
import sys

from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim, vmodl


def wait_for_task(task):
    while task.info.state not in (
        vim.TaskInfo.State.success,
        vim.TaskInfo.State.error,
    ):
        pass
    if task.info.state == vim.TaskInfo.State.error:
        raise Exception(f"Task failed: {task.info.error.msg}")
    return task.info.result


def get_or_create_folder(datacenter, folder_name):
    vm_folder = datacenter.vmFolder
    for child in vm_folder.childEntity:
        if isinstance(child, vim.Folder) and child.name == folder_name:
            return child
    return vm_folder.CreateFolder(folder_name)


def find_resource_pool(cluster):
    return cluster.resourcePool


def create_template(si, datacenter, cluster, folder, name, guest_id):
    content = si.RetrieveContent()

    config = vim.vm.ConfigSpec(
        name=name,
        guestId=guest_id,
        memoryMB=512,
        numCPUs=1,
        files=vim.vm.FileInfo(vmPathName=f"[{datacenter.datastore[0].name}]"),
    )

    task = folder.CreateVM_Task(
        config=config,
        pool=cluster.resourcePool,
    )
    vm = wait_for_task(task)
    vm.MarkAsTemplate()
    return vm.name


def main():
    if len(sys.argv) != 4:
        print(json.dumps({"error": "Usage: vcsim_create_templates.py <hostname> <username> <password>"}))
        sys.exit(1)

    _, hostname, username, password = sys.argv

    templates = [
        {"name": "rhel9-template", "guest_id": "rhel9_64Guest"},
        {"name": "ubuntu22-template", "guest_id": "ubuntu64Guest"},
        {"name": "win2022-template", "guest_id": "windows2019srvNext_64Guest"},
    ]

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    si = SmartConnect(host=hostname, user=username, pwd=password, sslContext=ctx)
    try:
        content = si.RetrieveContent()
        dc = content.viewManager.CreateContainerView(
            content.rootFolder, [vim.Datacenter], True).view[0]

        cluster = content.viewManager.CreateContainerView(
            dc, [vim.ClusterComputeResource], True).view[0]

        folder = get_or_create_folder(dc, "Templates")

        existing = {vm.name for vm in content.viewManager.CreateContainerView(
            content.rootFolder, [vim.VirtualMachine], True).view
            if vm.config and vm.config.template}

        results = []
        for tmpl in templates:
            if tmpl["name"] in existing:
                results.append({"name": tmpl["name"], "status": "already exists"})
                continue
            try:
                create_template(si, dc, cluster, folder, tmpl["name"], tmpl["guest_id"])
                results.append({"name": tmpl["name"], "status": "created"})
            except Exception as e:
                results.append({"name": tmpl["name"], "status": f"failed: {e}"})

        print(json.dumps({"hostname": hostname, "results": results}))
    finally:
        Disconnect(si)


if __name__ == "__main__":
    main()
