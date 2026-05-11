import json
import math
from typing import Any
from yaml import load

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

with open("disk-bytes-dashboard.yml", "r") as fh:
    data = load(fh, Loader=Loader)

dashboard: dict[str, Any] = {}

elements: dict[str, Any] = {}
rows: list[dict[str, Any]] = []

panel_id = 1
for instance_key, instance_data in data.items():
    panel_id += 1
    disk_id = 1
    row_items: list[dict[str, Any]] = []
    for disk_key, disk_data in instance_data.get("disks").items():
        elements[f"panel-{panel_id}"] = {
            "kind": "Panel",
            "spec": {
                "data": {
                    "kind": "QueryGroup",
                    "spec": {
                        "queries": [
                            {
                                "kind": "PanelQuery",
                                "spec": {
                                    "hidden": False,
                                    "query": {
                                        "datasource": {"name": "grafanacloud-prom"},
                                        "group": "prometheus",
                                        "kind": "DataQuery",
                                        "spec": {
                                            "editorMode": "code",
                                            "expr": f'sum(node_filesystem_size_bytes{{device="{disk_data.get("device")}", instance="{instance_data.get("instance")}"}})',
                                            "legendFormat": "Filesystem size",
                                            "range": True,
                                        },
                                        "version": "v0",
                                    },
                                    "refId": "A",
                                },
                            },
                            {
                                "kind": "PanelQuery",
                                "spec": {
                                    "hidden": False,
                                    "query": {
                                        "datasource": {"name": "grafanacloud-prom"},
                                        "group": "prometheus",
                                        "kind": "DataQuery",
                                        "spec": {
                                            "editorMode": "code",
                                            "expr": f'sum(node_filesystem_size_bytes{{device="{disk_data.get("device")}", instance="{instance_data.get("instance")}"}} - node_filesystem_free_bytes{{device="{disk_data.get("device")}", instance="{instance_data.get("instance")}"}})',
                                            "instant": False,
                                            "legendFormat": "Used bytes",
                                            "range": True,
                                        },
                                        "version": "v0",
                                    },
                                    "refId": "B",
                                },
                            },
                        ],
                        "queryOptions": {},
                        "transformations": [],
                    },
                },
                "description": "",
                "id": panel_id,
                "links": [],
                "title": f'{disk_data.get("device")} (supposedly mounted on {disk_data.get("mounted")})',
                "vizConfig": {
                    "group": "timeseries",
                    "kind": "VizConfig",
                    "spec": {
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
                                    "showValues": False,
                                    "spanNulls": False,
                                    "stacking": {"group": "A", "mode": "none"},
                                    "thresholdsStyle": {"mode": "off"},
                                },
                                "min": 0,
                                "thresholds": {
                                    "mode": "absolute",
                                    "steps": [
                                        {"color": "green", "value": 0},
                                        {"color": "red", "value": 80},
                                    ],
                                },
                                "unit": "decbytes",
                            },
                            "overrides": [],
                        },
                        "options": {
                            "annotations": {"clustering": -1, "multiLane": False},
                            "legend": {
                                "calcs": [],
                                "displayMode": "list",
                                "placement": "bottom",
                                "showLegend": True,
                            },
                            "tooltip": {
                                "hideZeros": False,
                                "mode": "single",
                                "sort": "none",
                            },
                        },
                    },
                    "version": "13.1.0-25365784498",
                },
            },
        }
        row_items.append(
            {
                "kind": "GridLayoutItem",
                "spec": {
                    "element": {
                        "kind": "ElementReference",
                        "name": f"panel-{panel_id}",
                    },
                    "height": 8,
                    "width": 8,
                    "x": (disk_id - 1) % 2 * 12,
                    "y": 8 * math.floor((disk_id - 1) / 2),
                },
            }
        )
        panel_id += 1
        elements[f"panel-{panel_id}"] = {
            "kind": "Panel",
            "spec": {
                "data": {
                    "kind": "QueryGroup",
                    "spec": {
                        "queries": [
                            {
                                "kind": "PanelQuery",
                                "spec": {
                                    "hidden": False,
                                    "query": {
                                        "datasource": {"name": "grafanacloud-prom"},
                                        "group": "prometheus",
                                        "kind": "DataQuery",
                                        "spec": {
                                            "editorMode": "code",
                                            "expr": f'sum((node_filesystem_size_bytes{{device="{disk_data.get("device")}", instance="{instance_data.get("instance")}"}} - node_filesystem_free_bytes{{device="{disk_data.get("device")}", instance="{instance_data.get("instance")}"}}) / node_filesystem_size_bytes{{device="{disk_data.get("device")}", instance="{instance_data.get("instance")}"}})',
                                            "legendFormat": "__auto",
                                            "range": True,
                                        },
                                        "version": "v0",
                                    },
                                    "refId": "A",
                                },
                            }
                        ],
                        "queryOptions": {},
                        "transformations": [],
                    },
                },
                "description": "",
                "id": panel_id,
                "links": [],
                "title": f'{disk_data.get("device")} usage',
                "vizConfig": {
                    "group": "gauge",
                    "kind": "VizConfig",
                    "spec": {
                        "fieldConfig": {
                            "defaults": {
                                "color": {"mode": "thresholds"},
                                "thresholds": {
                                    "mode": "percentage",
                                    "steps": [
                                        {"color": "green", "value": 0},
                                        {"color": "red", "value": 80},
                                    ],
                                },
                                "unit": "percentunit",
                            },
                            "overrides": [],
                        },
                        "options": {
                            "barShape": "flat",
                            "barWidthFactor": 0.5,
                            "effects": {
                                "barGlow": False,
                                "centerGlow": False,
                                "gradient": False,
                            },
                            "endpointMarker": "point",
                            "minVizHeight": 75,
                            "minVizWidth": 75,
                            "orientation": "auto",
                            "reduceOptions": {
                                "calcs": ["lastNotNull"],
                                "fields": "",
                                "values": False,
                            },
                            "segmentCount": 1,
                            "segmentSpacing": 0.3,
                            "shape": "gauge",
                            "showThresholdLabels": False,
                            "showThresholdMarkers": True,
                            "sizing": "auto",
                            "sparkline": False,
                            "textMode": "auto",
                        },
                    },
                    "version": "13.1.0-25365784498",
                },
            },
        }
        row_items.append(
            {
                "kind": "GridLayoutItem",
                "spec": {
                    "element": {
                        "kind": "ElementReference",
                        "name": f"panel-{panel_id}",
                    },
                    "height": 8,
                    "width": 4,
                    "x": (disk_id - 1) % 2 * 12 + 8,
                    "y": 8 * math.floor((disk_id - 1) / 2),
                },
            }
        )
        panel_id += 1
        disk_id += 1

    rows.append(
        {
            "kind": "RowsLayoutRow",
            "spec": {
                "collapse": False,
                "layout": {
                    "kind": "GridLayout",
                    "spec": {"items": row_items},
                },
                "title": instance_data.get("label"),
            },
        }
    )

dashboard = {
    "annotations": [
        {
            "kind": "AnnotationQuery",
            "spec": {
                "builtIn": True,
                "enable": True,
                "hide": True,
                "iconColor": "rgba(0, 211, 255, 1)",
                "name": "Annotations & Alerts",
                "query": {
                    "datasource": {"name": "-- Grafana --"},
                    "group": "grafana",
                    "kind": "DataQuery",
                    "spec": {},
                    "version": "v0",
                },
            },
        }
    ],
    "cursorSync": "Off",
    "editable": True,
    "elements": elements,
    "layout": {"kind": "RowsLayout", "spec": {"rows": rows}},
    "links": [],
    "liveNow": False,
    "preload": False,
    "tags": [],
    "timeSettings": {
        "autoRefresh": "",
        "autoRefreshIntervals": [
            "5s",
            "10s",
            "30s",
            "1m",
            "5m",
            "15m",
            "30m",
            "1h",
            "2h",
            "1d",
        ],
        "fiscalYearStartMonth": 0,
        "from": "now-7d",
        "hideTimepicker": False,
        "timezone": "browser",
        "to": "now",
    },
    "title": "Disk bytes usage",
    "variables": [],
}

with open("disk-bytes-dashboard.json", "w") as fh:
    json.dump(dashboard, fh, indent=2)

print(
    "File generated at disk-bytes-dashboard.json, create a dashboard "
    "(or update existing one in its settings) with this content"
)
