#!/bin/bash
# Build + deploy ToolPilot to https://www.161808.xyz/
set -euo pipefail
export PATH="$HOME/workspace/bin:$PATH"
cd "$HOME/workspace/sites/161808.xyz"
hugo --minify
rsync -avz --delete --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r \
  -e /home/hatch/workspace/bin/srv-ssh \
  public/ root@186.241.112.25:/var/www/161808/
echo "OK -> https://www.161808.xyz/"
