# atlas-vmware

Ansible playbooks for VMware automation, targeting vcsim instances running in the `atlas-talos` homelab Kubernetes cluster.

## Project Context

This repo is part of the `atlas-` homelab project family. Infrastructure is managed in [`atlas-talos`](https://github.com/austin2153/atlas-talos) — refer to that repo for cluster setup, networking, and platform details.

## vcsim Targets

4 VMware vCenter simulator instances are available for testing playbooks:

| Instance | URL | IP |
|---|---|---|
| vcenter-01 | https://vcenter-01.atlas.local | 192.168.20.52 |
| vcenter-02 | https://vcenter-02.atlas.local | 192.168.20.53 |
| vcenter-03 | https://vcenter-03.atlas.local | 192.168.20.54 |
| vcenter-04 | https://vcenter-04.atlas.local | 192.168.20.55 |

- **Default credentials**: `administrator@vsphere.local` / `password`
- **Port**: 443 (HTTPS)
- **DNS**: Resolved via Pi-hole on the local network (`atlas.local` domain)
- These are simulated environments — safe to test destructive operations against

## Ansible Collections

Use the following collections for VMware automation:

- [`community.vmware`](https://docs.ansible.com/ansible/latest/collections/community/vmware/) — broad VMware module coverage
- [`vmware.vmware_rest`](https://docs.ansible.com/ansible/latest/collections/vmware/vmware_rest/) — REST API-based modules (recommended for vSphere 7+)

## AWX Integration

Playbooks in this repo are intended to be run via AWX (`awx.atlas.local`). AWX pulls from this repo as a Project and uses stored credentials for vCenter access.

## Notes

- vcsim instances run in the `vcsim` namespace of the atlas-talos cluster
- Manifests are in `platform/vcsim/` in the `atlas-talos` repo
- All `atlas.local` DNS entries are managed in Pi-hole
