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
| `provision_vm.yml` | Full end-to-end VM provisioning — config load, placement, VM clone |
| `vm_day2.yml` | Day 2 operations on an existing VM (power, snapshot, delete) |
| `validate_config_loading.yml` | Validates request vars resolve to the correct datacenter/profile/network config |
| `validate_vm_placement.yml` | Runs the placement pipeline without provisioning — useful for dry runs |
| `setup_vcsim.yml` | Seeds vcsim test fixtures (run once after redeploy) |
| `get_info.yml` | Queries datacenter info from all 4 vcsim instances |

## VM provisioning pipeline

`provision_vm.yml` runs the full pipeline from request inputs to a provisioned VM:

1. **load_request_config** — resolves `fts_*` request vars to datacenter, profile, and network config from Git
2. **select_vcenter** — discovers vSphere datacenters via SOAP API, validates at least one is reachable
3. **select_cluster** — picks the cluster with lowest CPU utilization, filtered by profile thresholds
4. **select_datastore** — picks the datastore with most free space, filtered by `disk_cutoff` GB threshold
5. **select_network** — matches a network from resolved config by compartment tag and `provisioning.state:enabled`
6. **select_template** — finds the requested OS template by name in the configured Templates folder
7. **check_vm_exists** — checks if a VM with the target name already exists; skips provisioning if so
8. **create VM** — clones the template onto the selected cluster/datastore via `CloneVM_Task`

Each placement step produces a `selected_*` fact consumed by subsequent steps.

### Request inputs

| Variable | Description | Example |
|---|---|---|
| `fts_config_profile` | Provisioning profile name | `homelab` |
| `fts_location` | Location tag | `location:atlas.vcenter-01` |
| `fts_environment` | Environment tag | `environment:atlas.dev` |
| `fts_compartment` | Compartment tag | `compartment:atlas.general` |
| `fts_os_type` | OS type key from profile | `rhel9` |
| `fts_cpu` | vCPU count | `2` |
| `fts_mem` | Memory in GB | `4` |
| `fts_purpose` | Free-text description of the VM's purpose | `AWX test run` |
| `fts_useremail` | Requestor email address | `user@example.com` |

For local testing these come from `playbooks/vars/sample_vm_request.yml`. In AWX they are passed as extra vars via a job template survey.

### VM naming

VMs are named `{site_code}-{os_type}-{timestamp}` at provision time, e.g. `atlas01-rhel9-20260608024058`. The site code comes from the matched datacenter config. Names are unique by timestamp and used as the identifier for day 2 operations.

### vcsim compatibility

vcsim implements the vSphere SOAP API but not all features. A few `community.vmware` modules crash against vcsim due to missing attributes (DRS config, VM summary fields). Where this happens, tasks use small pyVmomi scripts in `scripts/` instead:

| Script | Used by | Why |
|---|---|---|
| `vcenter_cluster_facts.py` | `select_cluster` | `vmware_cluster_info` crashes on missing DRS config |
| `vcenter_template_facts.py` | `select_template` | `vmware_vm_info` crashes on missing summary attribute |
| `vcenter_vm_exists.py` | `check_vm_exists` | direct pyVmomi lookup by name |
| `vcenter_create_vm.py` | `provision_vm.yml` | `vmware_guest` silently no-ops for VM creation on vcsim |
| `vcenter_vm_power.py` | `vm_day2.yml` | power on/off/reset via `PowerOnVM_Task`, `PowerOffVM_Task`, `ResetVM_Task` |
| `vcenter_vm_snapshot.py` | `vm_day2.yml` | create, list, and delete snapshots |
| `vcenter_vm_delete.py` | `vm_day2.yml` | power off then destroy via `Destroy_Task` |
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

| Job Template | Playbook | Survey inputs |
|---|---|---|
| Provision VM | `provision_vm.yml` | `fts_*` request variables |
| VM Day 2 Operations | `vm_day2.yml` | `vm_name`, `vm_action`, `vcenter_hostname`, `datacenter` |

The `vm_action` survey field accepts: `power_on`, `power_off`, `reset`, `snapshot`, `snapshots`, `delete_snapshots`, `delete`.

### AWX inventory requirement

The `localhost` host in the AWX inventory must have `ansible_connection: local` set. Without it, AWX attempts SSH for every task instead of running locally.
