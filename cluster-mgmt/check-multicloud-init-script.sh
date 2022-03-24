#!/bin/bash

# Checks whether the in-repo copy of the Scaleway script and its online version differs.
# A different online version means that Scaleway now recommends a different setup
# and our own script (-kiwix) should be adapted

echo -n "comparing scripts…"
remote_url=https://scwcontainermulticloud.s3.fr-par.scw.cloud/multicloud-init.sh
remote_digest=$(curl -s -L $remote_url | md5sum)

repo_digest=$(cat multicloud-init.sh.orig | md5sum)


if [ "$remote_digest" != "$repo_digest" ] ; then
    printf "\033[0;31m changed\033[0m\n"
    echo "Please download $remote_url and analyze"
    exit 1
fi

printf "\033[0;32m matches\033[0m\n"
