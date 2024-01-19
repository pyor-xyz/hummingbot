
## Create AWS EC2 Instance
* [Instance] (https://docs.aws.amazon.com/efs/latest/ug/gs-step-one-create-ec2-resources.html)

## Setup Git SSH and clone the Repo
Make sure you have the access to repo (https://github.com/pyor-xyz/hummingbot)
* [setup] (https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent)

## Setup ovpn
Note: Make sure you transfer the ovpn file from local to remote instance using scp.
```scp -i ~/.ssh/<path_to_pem>.pem <path_to_ovpn_file>.ovpn user@Public IPv4 DNS:~/.```
* [setup] (https://openvpn.net/cloud-docs/owner/connectors/connector-user-guides/openvpn-3-client-for-linux.html)

## setup conda
* [setup] (https://docs.conda.io/projects/miniconda/en/latest/)

## setup hummingBot
* [setup] (https://hummingbot.org/installation/source/)