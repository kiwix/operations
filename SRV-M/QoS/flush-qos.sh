#!/bin/sh -xe

# Clear existing QoS rules on eno1
tc qdisc del dev eno1 root 2>/dev/null || true
# there used to be a an fq_codel one, probably set by some part of the kube
# tc qdisc show dev eno1
#  qdisc mq 0: root
#  qdisc fq_codel 0: parent :1 limit 10240p flows 1024 quantum 1514 target 5ms interval 100ms memory_limit 32Mb ecn drop_batch 64

### /!\ clear out the POSTROUTING chain in mangle
# ATM there is no other use of this table so its safe
iptables -t mangle -F POSTROUTING
