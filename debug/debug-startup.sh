#!/bin/bash

mkdir -p /root/.ssh

# reg
echo "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC4UTXOYXrKA6dR7KizO2AvqqHKQGJE\
      /FZF2oKTiofWEYDf+UWylksH4WjFmVczDUHN653Ve/QOIyRfI6IUuVa2hJ+l02xFV7rd\
      l7L5zSZwKiSJr+SefouzWIFwS3VS3gbLOqk864a1NkUR97yKYjxsZiT9fISf771HqEKh\
      sXOzZDOFbxt5u+YAaAJIJlU0EMKkDRBBtAVxmLFHme0uSpZ8DlYMFARGe1s0I++1eby0\
      NVtzP3TarouvkPN1cFmS7UhQCsHzcmDMcNyrtHGBnlgjihd4m2bppmY75xTTR/PQTKDW\
      qwklyYZhiDCKjZYzxWTk493SwKfZfaT9FOU0r4FT" > /root/.ssh/authorized_keys

/etc/init.d/ssh start
