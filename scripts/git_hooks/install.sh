#!/bin/bash

# allow git user to restart service:
# sudo visudo
# git ALL=NOPASSWD: /bin/systemctl restart telydl.service

DEST="/opt/telydl/.git/hooks/post-receive"
cp post-receive.sh $DEST
chmod +x $DEST