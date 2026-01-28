#!/bin/sh -xe

# Add HTB root qdisc with default to 1:40 for unclassified traffic
tc qdisc add dev eno1 root handle 1: htb default 40

# Add HTB root (1:1) with 1Gbps total bandwidth
tc class add dev eno1 parent 1: classid 1:1 htb rate 1gbit ceil 1gbit

# intentionally not using prio0 so it's avail for hot additions

# 1:10 - core traffic
tc class add dev eno1 parent 1:1 classid 1:10 htb rate 5mbit ceil 1gbit prio 1
# 1:20 - mirroring
tc class add dev eno1 parent 1:1 classid 1:20 htb rate 660mbit ceil 1gbit prio 2
# 1:30 - downloads
tc class add dev eno1 parent 1:1 classid 1:30 htb rate 320mbit ceil 1gbit prio 3
#   1:31 - HTTP downloads
tc class add dev eno1 parent 1:30 classid 1:31 htb rate 240mbit ceil 1gbit prio 3
#   1:32 - FTP downloads
tc class add dev eno1 parent 1:30 classid 1:32 htb rate 80mbit ceil 1gbit prio 4
# 1:40 - fallback. intentionally limited so new/unexpected usage can be identified
tc class add dev eno1 parent 1:1 classid 1:40 htb rate 10mbit ceil 10mbit prio 5

#
# Add SFQ discipline to each leaf so users within each que dont cannibalise the queue
#
tc qdisc add dev eno1 parent 1:10 handle 100: sfq perturb 10
tc qdisc add dev eno1 parent 1:20 handle 200: sfq perturb 10
tc qdisc add dev eno1 parent 1:31 handle 301: sfq perturb 10
tc qdisc add dev eno1 parent 1:32 handle 302: sfq perturb 10
tc qdisc add dev eno1 parent 1:40 handle 400: sfq perturb 10

#
# Assign traffic to queues
#
# intentionally not using prio0 so it's avail for hot additions
#
# send all packets marked 10 in firewall to go to 1:10
tc filter add dev eno1 protocol ip parent 1: handle 10 fw classid 1:10
# 1:10 - core traffic (reg box)
tc filter add dev eno1 protocol ip parent 1: prio 1 u32 match ip dst 196.200.90.182 flowid 1:10
# 1:10 - core traffic (kilo network)
tc filter add dev eno1 protocol ip parent 1: prio 1 u32 match ip dst 10.4.0.0/16 flowid 1:10
# 1:10 - core traffic (k8s network)
tc filter add dev eno1 protocol ip parent 1: prio 1 u32 match ip dst 100.64.0.0/16 flowid 1:10
# 1:10 - core traffic (SSH, port 22)
iptables -t mangle -A POSTROUTING -o eno1 -p tcp --dport 22 -j MARK --set-mark 10
iptables -t mangle -A POSTROUTING -o eno1 -p tcp --dport 22 -j RETURN
# 1:10 - core traffic (ICMP) so ping is replied fast (we use it only to test online-ness)
tc filter add dev eno1 protocol ip parent 1: prio 3 flower ip_proto icmp flowid 1:10
tc filter add dev eno1 protocol ipv6 parent 1: flower ip_proto icmpv6 flowid 1:10

# 1:20 - mirroring (rsync)
# send all packets marked 20 in firewall to go to 1:20
tc filter add dev eno1 protocol ip parent 1: handle 20 fw classid 1:20
# mark traffic to port 873 (rsyncd) as 20
iptables -t mangle -A POSTROUTING -o eno1 -p tcp --dport 873 -j MARK --set-mark 20
iptables -t mangle -A POSTROUTING -o eno1 -p tcp --dport 873 -j RETURN

# 1:30 - downloads
#   1:31 - HTTP
# send all packets marked 31 in firewall to go to 1:31
tc filter add dev eno1 protocol ip parent 1: handle 31 fw classid 1:31
# mark traffic to port 80 (HTTP) and 443 (HTTPS) as 31
iptables -A POSTROUTING -t mangle -o eno1 -p tcp -m multiport --sports 80,443 -j MARK --set-xmark 31
iptables -A POSTROUTING -t mangle -o eno1 -p tcp -m multiport --sports 80,443 -j RETURN

#   1:32 - FTP
# send all packets marked 31 in firewall to go to 1:31
tc filter add dev eno1 protocol ip parent 1: handle 32 fw classid 1:32
# mark traffic to port 21 (active) and ports 2000-2050 (passive) as 32
iptables -A POSTROUTING -t mangle -o eno1 -p tcp -m multiport --sports 21,2000:2050 -j MARK --set-xmark 32
iptables -A POSTROUTING -t mangle -o eno1 -p tcp -m multiport --sports 21,2000:2050 -j RETURN

# 1:40 - fallback, no need to filter/assign
