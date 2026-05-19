# Linux Setup

Ansible setup for Ubuntu/Linux servers.

## Files

- `playbook.yml`: committed server setup tasks

## Usage

SSH into the Linux server and run the playbook there:

```sh
ssh s
cd ~/dotfiles
apt update
apt install -y ansible
ansible-playbook -i 'localhost,' -c local linux/playbook.yml
```

The trailing comma in `localhost,` tells Ansible that this is an inline host list, not a file path.
