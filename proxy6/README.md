# IPv6 Proxy

> [!WARNING]
> This is installed and ran on `proxy6` host

Documentation on [IPv6-Proxy Wiki](https://github.com/kiwix/operations/wiki/IPv6-Proxy)

## Deployment

```sh
# check https://github.com/heiher/hev-socks5-server/releases for new release first
curl -o /usr/local/bin/hev-socks5-server https://github.com/heiher/hev-socks5-server/releases/download/2.11.2/hev-socks5-server-linux-x86_64
chmod +x /usr/local/bin/hev-socks5-server

mkdir -p /etc/proxy
curl -o /etc/proxy/auth.txt https://github.com/kiwix/operations/blob/main/proxy6/auth.txt
# update auth file with credentials (clear text)

curl -o /etc/systemd/system/proxy-v6.service https://github.com/kiwix/operations/blob/main/proxy6/proxy-v6.service
curl -o /etc/systemd/system/proxy-dual.service https://github.com/kiwix/operations/blob/main/proxy6/proxy-dual.service
systemctl daemon-reload
systemctl enable --now proxy-v6.service
systemctl enable --now proxy-dual.service
```
