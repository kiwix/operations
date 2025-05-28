# disk-bytes-dashboard

This tooling is used to create the dashboard at https://kiwixorg.grafana.net/d/8ee7e349-af68-4aac-8eba-23c561cedbc0/disk-bytes-usage

Data (instances and disks) are defined in `disk-bytes-dashboard.yml`.

You then run `disk-bytes-dashboard.py` and it will create a `disk-bytes-dashboard.json` file.

You can then update dashboard definition with this JSON content. Go to the dashboard settings, JSON model, and update code. Or create a new dashboard if you wish.

Adding a new instance (node/server) or disk is simply a matter of updating `disk-bytes-dashboard.yml`, running Python tool again and using JSON to update dashboard.

Pre-requisite is obviously that this instance is already sending metrics corresponding to disk usage to Prometheus. Doc about this for "standalone" (understand non-k8s) nodes is at https://github.com/kiwix/operations/wiki/Monitor-any-server-basic-data-(disk,-cpu,-...).

Python code generating the JSON is probably not pixel-perfect at all, it is simply based on a manual export of a manually created dashboard in May 2025 and some coding to make loops. In particular, there is nothing handy to adapt it to new Grafana schema versions.