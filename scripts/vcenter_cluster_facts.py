#!/usr/bin/env python3
"""
Gathers cluster resource stats from vCenter via pyVmomi (SOAP API).

Usage:
  vcenter_cluster_facts.py <hostname> <username> <password> <datacenter>

Outputs JSON list of cluster facts to stdout.
community.vmware.vmware_cluster_info does not work reliably with vcsim,
so this script queries the SOAP API directly.
"""

import json
import ssl
import sys

from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim


def get_cluster_facts(hostname, username, password, datacenter_name):
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
            return {"error": f"Datacenter '{datacenter_name}' not found", "clusters": []}

        view = content.viewManager.CreateContainerView(
            dc, [vim.ClusterComputeResource], True)
        clusters = []
        for cluster in view.view:
            hosts = cluster.host or []
            total_cpu_mhz = sum(
                (h.hardware.cpuInfo.hz * h.hardware.cpuInfo.numCpuCores) / 1e6
                for h in hosts if h.hardware and h.hardware.cpuInfo
            )
            used_cpu_mhz = sum(
                h.summary.quickStats.overallCpuUsage or 0
                for h in hosts if h.summary and h.summary.quickStats
            )
            total_mem_mb = sum(
                h.hardware.memorySize / (1024 ** 2)
                for h in hosts if h.hardware
            )
            used_mem_mb = sum(
                h.summary.quickStats.overallMemoryUsage or 0
                for h in hosts if h.summary and h.summary.quickStats
            )
            cpu_ratio = used_cpu_mhz / total_cpu_mhz if total_cpu_mhz > 0 else 0.0
            mem_ratio = used_mem_mb / total_mem_mb if total_mem_mb > 0 else 0.0

            clusters.append({
                "name": cluster.name,
                "host_count": len(hosts),
                "total_cpu_ghz": round(total_cpu_mhz / 1000, 2),
                "used_cpu_ghz": round(used_cpu_mhz / 1000, 2),
                "free_cpu_ghz": round((total_cpu_mhz - used_cpu_mhz) / 1000, 2),
                "cpu_utilization_ratio": round(cpu_ratio, 4),
                "total_mem_gb": round(total_mem_mb / 1024, 2),
                "used_mem_gb": round(used_mem_mb / 1024, 2),
                "free_mem_gb": round((total_mem_mb - used_mem_mb) / 1024, 2),
                "mem_utilization_ratio": round(mem_ratio, 4),
            })
        view.Destroy()
        return {"error": "", "clusters": clusters}
    finally:
        Disconnect(si)


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(json.dumps({"error": "Usage: vcenter_cluster_facts.py <hostname> <username> <password> <datacenter>", "clusters": []}))
        sys.exit(1)

    _, hostname, username, password, datacenter = sys.argv
    result = get_cluster_facts(hostname, username, password, datacenter)
    print(json.dumps(result))
