import json
import math
from yaml import load, dump

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

with open("disk-bytes-dashboard.yml", "r") as fh:
    data = load(fh, Loader=Loader)

dashboard = {}

panels = []

panel_id = 1
instance_id = 1
consumed_y = 0
for instance_key, instance_data in data.items():
    panels.append(
        {
            "collapsed": False,
            "gridPos": {"h": 1, "w": 24, "x": 0, "y": consumed_y},
            "id": panel_id,
            "panels": [],
            "title": instance_data.get("label"),
            "type": "row",
        }
    )
    panel_id += 1
    consumed_y += 1
    disk_id = 1
    for disk_key, disk_data in instance_data.get("disks").items():
        panels.append(
            {
                "datasource": {"type": "prometheus", "uid": "grafanacloud-prom"},
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "custom": {
                            "axisBorderShow": False,
                            "axisCenteredZero": False,
                            "axisColorMode": "text",
                            "axisLabel": "",
                            "axisPlacement": "auto",
                            "barAlignment": 0,
                            "barWidthFactor": 0.6,
                            "drawStyle": "line",
                            "fillOpacity": 0,
                            "gradientMode": "none",
                            "hideFrom": {
                                "legend": False,
                                "tooltip": False,
                                "viz": False,
                            },
                            "insertNulls": False,
                            "lineInterpolation": "linear",
                            "lineWidth": 1,
                            "pointSize": 5,
                            "scaleDistribution": {"type": "linear"},
                            "showPoints": "auto",
                            "spanNulls": False,
                            "stacking": {"group": "A", "mode": "none"},
                            "thresholdsStyle": {"mode": "off"},
                        },
                        "mappings": [],
                        "min": 0,
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green"},
                                {"color": "red", "value": 80},
                            ],
                        },
                        "unit": "decbytes",
                    },
                    "overrides": [],
                },
                "gridPos": {
                    "h": 8,
                    "w": 8,
                    "x": (disk_id - 1) % 2 * 12,
                    "y": consumed_y + 8 * math.floor((disk_id - 1) / 2),
                },
                "id": panel_id,
                "options": {
                    "legend": {
                        "calcs": [],
                        "displayMode": "list",
                        "placement": "bottom",
                        "showLegend": True,
                    },
                    "tooltip": {"hideZeros": False, "mode": "single", "sort": "none"},
                },
                "pluginVersion": "12.1.0-88106",
                "targets": [
                    {
                        "datasource": {
                            "type": "prometheus",
                            "uid": "grafanacloud-prom",
                        },
                        "editorMode": "code",
                        "expr": f'node_filesystem_size_bytes{{device="{disk_data.get("device")}", instance="{instance_data.get("instance")}"}}',
                        "legendFormat": "Filesystem size",
                        "range": True,
                        "refId": "A",
                    },
                    {
                        "datasource": {
                            "type": "prometheus",
                            "uid": "grafanacloud-prom",
                        },
                        "editorMode": "code",
                        "expr": f'node_filesystem_size_bytes{{device="{disk_data.get("device")}", instance="{instance_data.get("instance")}"}} - node_filesystem_free_bytes{{device="{disk_data.get("device")}", instance="{instance_data.get("instance")}"}}',
                        "hide": False,
                        "instant": False,
                        "legendFormat": "Used bytes",
                        "range": True,
                        "refId": "B",
                    },
                ],
                "title": f'{disk_data.get("device")} (supposedly mounted on {disk_data.get("mounted")})',
                "type": "timeseries",
            }
        )
        panel_id += 1
        panels.append(
            {
                "datasource": {"type": "prometheus", "uid": "grafanacloud-prom"},
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "thresholds"},
                        "mappings": [],
                        "thresholds": {
                            "mode": "percentage",
                            "steps": [
                                {"color": "green"},
                                {"color": "red", "value": 80},
                            ],
                        },
                        "unit": "percentunit",
                    },
                    "overrides": [],
                },
                "gridPos": {
                    "h": 8,
                    "w": 4,
                    "x": (disk_id - 1) % 2 * 12 + 8,
                    "y": consumed_y + 8 * math.floor((disk_id - 1) / 2),
                },
                "id": panel_id,
                "options": {
                    "minVizHeight": 75,
                    "minVizWidth": 75,
                    "orientation": "auto",
                    "reduceOptions": {
                        "calcs": ["lastNotNull"],
                        "fields": "",
                        "values": False,
                    },
                    "showThresholdLabels": False,
                    "showThresholdMarkers": True,
                    "sizing": "auto",
                },
                "pluginVersion": "12.1.0-88106",
                "targets": [
                    {
                        "datasource": {
                            "type": "prometheus",
                            "uid": "grafanacloud-prom",
                        },
                        "editorMode": "code",
                        "expr": f'(node_filesystem_size_bytes{{device="{disk_data.get("device")}", instance="{instance_data.get("instance")}"}} - node_filesystem_free_bytes{{device="{disk_data.get("device")}", instance="{instance_data.get("instance")}"}}) / node_filesystem_size_bytes{{device="{disk_data.get("device")}", instance="{instance_data.get("instance")}"}}',
                        "legendFormat": "__auto",
                        "range": True,
                        "refId": "A",
                    }
                ],
                "title": f'{disk_data.get("device")} usage',
                "type": "gauge",
            }
        )
        panel_id += 1
        disk_id += 1

    instance_id += 1
    consumed_y += 8 * (
        1 + math.floor((len(instance_data.get("disks").items()) - 1) / 2)
    )

dashboard = {
    "annotations": {
        "list": [
            {
                "builtIn": 1,
                "datasource": {"type": "grafana", "uid": "-- Grafana --"},
                "enable": True,
                "hide": True,
                "iconColor": "rgba(0, 211, 255, 1)",
                "name": "Annotations & Alerts",
                "type": "dashboard",
            }
        ]
    },
    "editable": True,
    "fiscalYearStartMonth": 0,
    "graphTooltip": 0,
    "id": 42,
    "links": [],
    "panels": panels,
    "preload": False,
    "schemaVersion": 41,
    "tags": [],
    "templating": {"list": []},
    "time": {"from": "now-7d", "to": "now"},
    "timepicker": {},
    "timezone": "browser",
    "title": "Disk bytes usage",
    "uid": "8ee7e349-af68-4aac-8eba-23c561cedbc0",
}

with open("disk-bytes-dashboard.json", "w") as fh:
    json.dump(dashboard, fh, indent=2)

print(
    "File generated at disk-bytes-dashboard.json, create a dashboard "
    "(or update existing one in its settings) with this content"
)
