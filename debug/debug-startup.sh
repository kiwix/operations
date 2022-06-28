#!/bin/bash

mkdir -p /root/.ssh

# reg
echo "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC4UTXOYXrKA6dR7KizO2AvqqHKQGJE/\
FZF2oKTiofWEYDf+UWylksH4WjFmVczDUHN653Ve/QOIyRfI6IUuVa2hJ+l02xFV7rdl7L5zSZw\
KiSJr+SefouzWIFwS3VS3gbLOqk864a1NkUR97yKYjxsZiT9fISf771HqEKhsXOzZDOFbxt5u+Y\
AaAJIJlU0EMKkDRBBtAVxmLFHme0uSpZ8DlYMFARGe1s0I++1eby0NVtzP3TarouvkPN1cFmS7U\
hQCsHzcmDMcNyrtHGBnlgjihd4m2bppmY75xTTR/PQTKDWqwklyYZhiDCKjZYzxWTk493SwKfZf\
aT9FOU0r4FT" >> /root/.ssh/authorized_keys

/etc/init.d/ssh start
