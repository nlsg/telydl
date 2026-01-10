#!/bin/bash

DEST="/opt/telydl/.git/hooks/post-merge"
cp post_merge.sh $DEST

chmod +x $DEST