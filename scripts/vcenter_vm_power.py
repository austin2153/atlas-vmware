#!/usr/bin/env python3
"""
Controls VM power state in vCenter via pyVmomi.

Usage:
  vcenter_vm_power.py <hostname> <username> <password> <vm_name> <datacenter> <action>

action: on | off | reset
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


def power_vm(hostname, username, password, vm_name, datacenter_name, action):
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
            return {"error": f"VM '{vm_name}' not found"}

        try:
            power_state = vm.runtime.powerState
        except AttributeError:
            power_state = None

        if action == "on":
            if power_state == vim.VirtualMachinePowerState.poweredOn:
                return {"error": "", "result": "already powered on", "vm": vm_name}
            wait_for_task(vm.PowerOnVM_Task())
        elif action == "off":
            if power_state == vim.VirtualMachinePowerState.poweredOff:
                return {"error": "", "result": "already powered off", "vm": vm_name}
            wait_for_task(vm.PowerOffVM_Task())
        elif action == "reset":
            wait_for_task(vm.ResetVM_Task())
        else:
            return {"error": f"Unknown action '{action}'. Use: on, off, reset"}

        return {"error": "", "result": f"power {action} completed", "vm": vm_name}
    finally:
        Disconnect(si)


if __name__ == "__main__":
    if len(sys.argv) != 7:
        print(json.dumps({"error": "Usage: vcenter_vm_power.py <hostname> <username> <password> <vm_name> <datacenter> <action>"}))
        sys.exit(1)

    _, hostname, username, password, vm_name, datacenter, action = sys.argv
    result = power_vm(hostname, username, password, vm_name, datacenter, action)
    print(json.dumps(result))
