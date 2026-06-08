# atlas-vmware

Ansible playbooks for VMware automation, targeting vcsim instances running in the `atlas-talos` homelab Kubernetes cluster.

## Prerequisites

- Python 3.12+
- Git
- Vault password file at `~/.vault_password` (see [Vault setup](#vault-setup))

## First-time setup

```bash
./setup.sh
source .venv/bin/activate
```

This will:
1. Create a Python virtual environment at `.venv/`
2. Install `ansible-core`, `ansible-lint`, pyVmomi, and other pip dependencies
3. Install required Ansible collections (`community.vmware`, `vmware.vmware_rest`)

## vcsim setup

vcsim instances run in the `vcsim` namespace of the `atlas-talos` cluster. After a fresh deployment, seed them with test fixtures (Templates folder + OS templates):

```bash
ansible-playbook playbooks/setup_vcsim.yml --vault-password-file ~/.vault_password
```

This is idempotent — safe to re-run. Required before running `validate_vm_placement.yml`.

## Running playbooks locally

```bash
ansible-playbook playbooks/<playbook>.yml --vault-password-file ~/.vault_password
```

`ansible.cfg` automatically uses `inventories/vcsim` as the inventory.

### Key playbooks

| Playbook | What it does |
|---|---|
| `validate_config_loading.yml` | Validates request vars resolve to the correct datacenter/profile/network config |
| `validate_vm_placement.yml` | Full placement pipeline: vCenter → cluster → datastore → network → template |
| `setup_vcsim.yml` | Seeds vcsim test fixtures (run once after redeploy) |
| `get_info.yml` | Queries datacenter info from all 4 vcsim instances |

## VM placement pipeline

`validate_vm_placement.yml` exercises the full placement decision chain:

1. **select_vcenter** — discovers vSphere datacenters via SOAP API, validates at least one is reachable
2. **select_cluster** — picks the cluster with lowest CPU utilization, filtered by profile thresholds
3. **select_datastore** — picks the datastore with most free space, filtered by `disk_cutoff` GB threshold
4. **select_network** — matches a network from `resolved_config` by compartment tag and `provisioning.state:enabled`
5. **select_template** — finds the requested OS template by name in the configured Templates folder

Each step produces a `selected_*` fact consumed by the next step.

### vcsim compatibility

vcsim implements the vSphere SOAP API but not all features. A few `community.vmware` modules crash against vcsim due to missing attributes (DRS config, VM summary fields). Where this happens, placement tasks use small pyVmomi scripts in `scripts/` instead:

| Script | Used by | Why |
|---|---|---|
| `vcenter_cluster_facts.py` | `select_cluster` | `vmware_cluster_info` crashes on missing DRS config |
| `vcenter_template_facts.py` | `select_template` | `vmware_vm_info` crashes on missing summary attribute |
| `vcsim_create_templates.py` | `setup_vcsim.yml` | `vmware_guest` silently no-ops for template creation |

pyVmomi is VMware's official Python SDK for the vSphere SOAP API — the same underlying library that `community.vmware` modules use internally.

## Vault setup

Credentials are stored in `vars/credentials.yml` using field-level Ansible Vault encryption. Only the secret values are encrypted — the file is safe to commit.

The vault password lives at `~/.vault_password` (never committed):

```bash
echo 'yourvaultpassword' > ~/.vault_password
chmod 600 ~/.vault_password
```

To encrypt a new value:

```bash
ansible-vault encrypt_string 'yourvalue' --name 'fieldname'
```

Paste the output block into `vars/credentials.yml`.

## Project structure

```
config/              # Target environment configuration
  datacenter/        # Per-vCenter datacenter configs (tags, credential ref, network refs)
  networks/          # Network definitions (CIDR, function, tags)
  profiles/          # Provisioning profiles (OS templates, resource thresholds)
  vcenters.yml       # vCenter instance list
docs/                # Project documentation
inventories/         # Ansible inventory (localhost + group vars)
playbooks/           # Ansible playbooks
  tasks/             # Reusable task files (imported by playbooks)
    vm-placement/    # Placement decision chain tasks
scripts/             # pyVmomi helper scripts (used where community.vmware modules break on vcsim)
vars/                # Vault-encrypted credential registry
requirements.txt     # Python dependencies
requirements.yml     # Ansible collection dependencies
setup.sh             # First-time environment setup
```

## AWX

Playbooks are run via AWX at `awx.atlas.local`. AWX pulls from this repo as a Project. The vault password is stored as a **Vault** credential in AWX and attached to each job template.
