#!/usr/bin/env python3
"""
Finds VM templates in a vCenter folder via pyVmomi (SOAP API).

Usage:
  vcenter_template_facts.py <hostname> <username> <password> <datacenter> <folder>

Outputs JSON list of template facts to stdout.
community.vmware.vmware_vm_info does not work reliably with vcsim,
so this script queries the SOAP API directly.
"""

import json
import ssl
import sys

from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim


def find_folder(datacenter, folder_name):
    """Walk the VM folder tree to find a named folder."""
    def _walk(folder):
        if folder.name == folder_name:
            return folder
        for child in getattr(folder, 'childEntity', []):
            if isinstance(child, vim.Folder):
                result = _walk(child)
                if result:
                    return result
        return None
    return _walk(datacenter.vmFolder)


def get_template_facts(hostname, username, password, datacenter_name, folder_name):
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
            return {"error": f"Datacenter '{datacenter_name}' not found", "templates": []}

        search_root = dc.vmFolder
        if folder_name:
            found = find_folder(dc, folder_name)
            if found is None:
                return {"error": f"Folder '{folder_name}' not found in datacenter '{datacenter_name}'", "templates": []}
            search_root = found

        view = content.viewManager.CreateContainerView(search_root, [vim.VirtualMachine], True)
        templates = []
        for vm in view.view:
            if vm.config and vm.config.template:
                templates.append({
                    "name": vm.name,
                    "guest_id": vm.config.guestId if vm.config else None,
                    "folder": vm.parent.name if vm.parent else None,
                    "moid": vm._moId,
                })
        view.Destroy()
        return {"error": "", "templates": templates}
    finally:
        Disconnect(si)


if __name__ == "__main__":
    if len(sys.argv) not in (5, 6):
        print(json.dumps({
            "error": "Usage: vcenter_template_facts.py <hostname> <username> <password> <datacenter> [folder]",
            "templates": []
        }))
        sys.exit(1)

    _, hostname, username, password, datacenter = sys.argv[:5]
    folder = sys.argv[5] if len(sys.argv) == 6 else ""
    result = get_template_facts(hostname, username, password, datacenter, folder)
    print(json.dumps(result))
