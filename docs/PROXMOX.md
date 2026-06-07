# Proxmox Access

This document describes how Claude connects to the Proxmox VE server for reviewing and managing the homelab hypervisor.

## Credentials File

The Proxmox API token is stored locally at `~/.proxmox-credentials` (not committed to git) as a single value in the format `user@realm!tokenid=secret`:

```
<user@realm!tokenid=secret>
```

Restrict permissions so only your user can read it:

```bash
chmod 600 ~/.proxmox-credentials
```

## Nodes

| Node | Hostname | IP |
|---|---|---|
| Primary | proxmox.atlas.local | 192.168.0.100 |
| Secondary | proxmox-cgrater.atlas.local | 192.168.0.102 |

## Connecting

Claude reads the API token from `~/.proxmox-credentials` and authenticates against the Proxmox REST API.

### Example — list nodes

```bash
PROXMOX_TOKEN=$(cat ~/.proxmox-credentials)
curl -sk "https://proxmox.atlas.local:8006/api2/json/nodes" \
  -H "Authorization: PVEAPIToken=$PROXMOX_TOKEN" | python3 -m json.tool
```

### Example — list VMs on a node

```bash
PROXMOX_TOKEN=$(cat ~/.proxmox-credentials)
curl -sk "https://proxmox.atlas.local:8006/api2/json/nodes/proxmox/qemu" \
  -H "Authorization: PVEAPIToken=$PROXMOX_TOKEN" | python3 -m json.tool
```

## Notes

- TLS verification is disabled (`-sk`) due to the self-signed certificate
- Always source credentials from `~/.proxmox-credentials` — never hardcode or echo secrets in the terminal
