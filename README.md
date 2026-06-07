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
2. Install `ansible-core`, `ansible-lint`, and other pip dependencies
3. Install required Ansible collections (`community.vmware`, `vmware.vmware_rest`)

## Running playbooks locally

```bash
ansible-playbook playbooks/<playbook>.yml
```

`ansible.cfg` automatically uses `inventories/vcsim` as the inventory and `~/.vault_password` for vault decryption — no extra flags needed.

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
config/          # Target environment configuration (hostnames, credential references)
docs/            # Project documentation
inventories/     # Ansible inventory (localhost + group vars)
playbooks/       # Ansible playbooks
vars/            # Vault-encrypted credential registry
requirements.txt # Python dependencies
requirements.yml # Ansible collection dependencies
setup.sh         # First-time environment setup
```

## AWX

Playbooks are run via AWX at `awx.atlas.local`. AWX pulls from this repo as a Project. The vault password is stored as a **Vault** credential in AWX and attached to each job template.
