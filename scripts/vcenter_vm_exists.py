#!/usr/bin/env python3
"""
Checks if a VM with a given name exists in vCenter via pyVmomi.

Usage:
  vcenter_vm_exists.py <hostname> <username> <password> <vm_name> <datacenter>

Outputs JSON with exists flag and VM details if found.
"""

import json
import ssl
import sys

from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim


def vm_exists(hostname, username, password, vm_name, datacenter_name):
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
        if dc is None:
            return {"error": f"Datacenter '{datacenter_name}' not found", "exists": False}

        view = content.viewManager.CreateContainerView(
            dc, [vim.VirtualMachine], True)
        vm = next(
            (v for v in view.view
             if v.name == vm_name and v.config and not v.config.template),
            None
        )
        view.Destroy()

        if vm:
            return {
                "error": "",
                "exists": True,
                "vm": {
                    "name": vm.name,
                    "moid": vm._moId,
                    "guest_id": vm.config.guestId if vm.config else None,
                }
            }
        return {"error": "", "exists": False}
    finally:
        Disconnect(si)


if __name__ == "__main__":
    if len(sys.argv) != 6:
        print(json.dumps({"error": "Usage: vcenter_vm_exists.py <hostname> <username> <password> <vm_name> <datacenter>", "exists": False}))
        sys.exit(1)

    _, hostname, username, password, vm_name, datacenter = sys.argv
    result = vm_exists(hostname, username, password, vm_name, datacenter)
    print(json.dumps(result))
