# SRV-M QoS

> [!WARNING]
> This is installed and ran on `SRV-M` host

Documentation on [SRV-M-QoS Wiki](https://github.com/kiwix/operations/wiki/SRV%E2%80%90M-QoS)

## Deployment

```sh
curl -O /usr/local/bin/setup-qos.sh https://github.com/kiwix/operations/blob/main/SRV-M/QoS/setup-qos.sh
curl -O /usr/local/bin/flush-qos.sh https://github.com/kiwix/operations/blob/main/SRV-M/QoS/flush-qos.sh
chmod +x /usr/local/bin/{setup,flush}-qos.sh
curl -O /etc/systemd/system/master-qos.service https://github.com/kiwix/operations/blob/main/SRV-M/QoS/master-qos.service
systemctl daemon-reload
systemctl enable --now master-qos.service
```
