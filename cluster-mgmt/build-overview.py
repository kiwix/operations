#!/usr/bin/env python3

""" Quick and dirty script to generate an overview of k8s cluster resources assignations

    Computes **assigned** resources for running and planned (cronjobs) pods to get
    an overview of how much available resources are left on each node.

    Usage:
        pip install jinja2 humanfriendly
        ./resusage.py [keep]

        # keep saves and/or restores fetched data to a local dump.json file

        Generates several HTML files:
        - overview.html         List of resources per namespace
        - overview-all.html     List of resources per services (and namespace)
        - node-{nodename}.html  Total and per-services resources for this node
"""

import json
import logging
import pathlib
import subprocess
import sys
from pprint import pprint
from typing import Dict, List

import humanfriendly
from jinja2 import Environment, select_autoescape

HERE = pathlib.Path(__file__).parent
OUTPUT = HERE / "k8s-overview"
ONEMIB = 1024 ** 2
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("rsc")

tmpl_header = """
<!DOCTYPE html>
<html>
    <head>
        <meta charset="utf-8">
        <meta http-equiv="X-UA-Compatible" content="IE=edge">
        <title>k8s overview</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-1BmE4kWBq78iYhFldvKuhfTAU6auU8tT94WrHftjDbrCEXSU1oBoqyl2QvZ6jIW3" crossorigin="anonymous">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.8.1/font/bootstrap-icons.css">
        <style type="text/css">
            .namespace th, .namespace td { font-weight: bold; }
            .service th { padding-left: 2rem; font-weight: normal; }
            a[name] { text-decoration: none; color: unset; }
            a { text-decoration: none; color: unset; }
        </style>
    </head>
    <body>
        <header class="p-3 bg-dark text-white">
        <div class="container">
          <div class="d-flex flex-wrap align-items-center justify-content-center justify-content-lg-start">
            <ul class="nav col-12 col-lg-auto me-lg-auto mb-2 justify-content-center mb-md-0">
              <li><a href="/" class="nav-link px-2 text-white">⎈  k8s</a></li>
              <li><a href="index.html" class="nav-link px-2 {% if where == "overview" %}text-secondary{% else %}text-white{% endif %}">Namespaces</a></li>
              <li class="me-4"><a href="all.html" class="nav-link px-2 {% if where == "detailed" %}text-secondary{% else %}text-white{% endif %}">Services</a></li>
              {% for nodename, node in nodes.items() %}
              <li class="me-4">
                <a href="node-{{ nodename }}.html" class="nav-link px-2 {% if where == "node-" + nodename %}text-secondary{% else %}text-white{% endif %} me-2">
                <i class="bi bi-server"></i> {{ nodename }}<br />
                 <span class="badge pill bg-info">
                    <small>
                    <i class="bi bi-cpu"></i> {{ node.cpu|human_cpu }}
                    <i class="bi bi-memory"></i> {{ node.memory|human_mem }}
                    </small>
                  </span>
                </a>
              </li>
              {% endfor %}
            </ul>
          </div>
        </div>
      </header>
      <div class="container">
"""

tmpl_footer = """
        </div>
    </body>
</html>
"""

node_template = """
<p class="text-center alert mt-2">
    <span class="alert alert-{{ node.total_cpu|percent_color_from(node.cpu) }}">
        <i class="bi bi-cpu"></i> {{ node.total_cpu|percent_from(node.cpu) }} – {{ node.total_cpu|human_cpu }}/{{ node.cpu|human_cpu }}</span>
    <code>{{ nodename }}</code>
    <span class="alert alert-{{ node.total_memory|percent_color_from(node.memory) }}">
        <i class="bi bi-memory"></i> {{ node.total_memory|percent_from(node.memory) }} – {{ node.total_memory|human_mem }}/{{ node.memory|human_mem }}</span>
</p>
<table class="table table-striped">
    <thead>
        <tr><th>NS/Service</th><th>CPU</th><th>MEM</th><th>Time</th></tr>
    </thead>
    <tbody>
        {% for nsname, ns in node.namespaces.items() %}
        {% if ns.services|length %}
        <tr class="namespace">
            <th><a name="ns-{{ nsname }}" href="#ns-{{ nsname }}">{{ nsname }}</a></th>
            <td>{{ ns.total_cpu|human_cpu }}</td>
            <td>{{ ns.total_memory|human_mem }}</td>
            <td>allways</td>
        </tr>
        {% for service in ns.services %}
        <tr class="service {{nsname }}">
            <th><a name="svc-{{ service.name }}"
                   href="#svc-{{ service.name }}">{{ service.name }}</a></th>
            <td>{{ service.cpu|human_cpu }}</td>
            <td>{{ service.memory|human_mem }}</td>
            <td>{{ service.timeframe }}</td>
        </tr>
        {% endfor %}
        {% endif %}
        {% endfor %}
    </tbody>
</table>
"""

overview_template = """
<p class="text-center alert mt-2">
    <span class="alert alert-info"><i class="bi bi-cpu"></i> {{ total_cpu|human_cpu }}</span>
    <code>cluster</code>
    <span class="alert alert-info"><i class="bi bi-memory"></i> {{ total_memory|human_mem }}</span>
</p>
<table class="table table-striped">
    <thead>
        <tr>
            <th>NS/Service</th>
            <th>CPU</th>
            <th>MEM</th>
            {% if detailed %}<th>Time</th>{% endif %}
            <th>Nodes</th>
        </tr>
    </thead>
    <tbody>
        {% for nsname, ns in namespaces.items() %}
        <tr class="namespace">
            <th><a name="ns-{{ nsname }}" href="#ns-{{ nsname }}">{{ nsname }}</a></th>
            <td>{{ ns.total_cpu|human_cpu }}</td>
            <td>{{ ns.total_memory|human_mem }}</td>
            {% if detailed %}<td>allways</td>{% endif %}
            <td>{% for node in ns.nodes %}
                <a href="node-{{ node }}.html">{{ node }}</a> {% endfor %}
            </td>
        </tr>
        {% if detailed %}
        {% for service in ns.services %}
        <tr class="service {{nsname }}">
            <th><a name="svc-{{ service.name }}"
                   href="#svc-{{ service.name }}">{{ service.name }}</a></th>
            <td>{{ service.cpu|human_cpu }}</td>
            <td>{{ service.memory|human_mem }}</td>
            <td>{{ service.timeframe }}</td>
            <td>{% for node in service.nodes %}
                <a href="node-{{ node }}.html">{{ node }}</a> {% endfor %}
            </td>
        </tr>
        {% endfor %}
        {% endif %}
        {% endfor %}
    </tbody>
</table>
"""

jinja_env = Environment(autoescape=select_autoescape())


def human_cpu(value):
    value = value / 1000.0
    return int(value) if value.is_integer() else value


def human_mem(value):
    return humanfriendly.format_size(value * ONEMIB, binary=True)


def percent_from(part, total):
    return format(part / total, ".1%")


def percent_color_from(part, total):
    value = part / total
    color = "success"
    if value >= 0.5:
        color = "info"
    if value >= 0.8:
        color = "warning"
    if value >= 0.9:
        color = "danger"
    return color


jinja_env.filters["human_cpu"] = human_cpu
jinja_env.filters["human_mem"] = human_mem
jinja_env.filters["percent_from"] = percent_from
jinja_env.filters["percent_color_from"] = percent_color_from


def kube(args: List, json_req=None):
    kargs = ["kubectl"] + args
    if json_req:
        kargs += ["-o", f"jsonpath-as-json={json_req}"]
    k = subprocess.run(kargs, text=True, capture_output=True, check=True)
    if json_req:
        return json.loads(k.stdout.strip())
    return k.stdout.strip()


def conv_resources(spec):
    def get_cpu(cpu: str = None):
        # non-set requests marked as 0
        if not cpu:
            cpu = "0m"
        # convert if not in millicpu
        if not cpu.endswith("m"):
            cpu = f"{float(cpu) * 1000}m"
        return int(float(cpu[:-1]))

    def get_memory(memory: str = None):
        if not memory:
            memory = "0Mi"
        if memory.endswith("i"):
            memory += "B"
        return int(humanfriendly.parse_size(memory) / ONEMIB)

    qos = "BestEffort"
    all_has_cpu = has_cpu = True
    all_has_memory = has_memory = True
    has_identical_cpu = has_identical_memory = True
    cpu = memory = 0
    for container in spec.get("initContainers", []) + spec.get("containers", []):
        requests_cpu = get_cpu(container["resources"].get("requests", {}).get("cpu"))
        requests_memory = get_memory(
            container["resources"].get("requests", {}).get("memory")
        )
        limit_cpu = get_cpu(container["resources"].get("limits", {}).get("cpu"))
        limit_memory = get_memory(
            container["resources"].get("limits", {}).get("memory")
        )

        # whether one had configured rsc
        has_cpu = has_cpu and (requests_cpu or limit_cpu)
        has_memory = has_memory and (requests_memory or limit_memory)

        # wether all have configured rsc
        all_has_cpu = all_has_cpu and requests_cpu and limit_cpu
        all_has_memory = all_has_memory and requests_memory and limit_memory

        # whether all have identical resources
        has_identical_cpu = (
            has_identical_cpu and all_has_cpu and (requests_cpu == limit_cpu)
        )
        has_identical_memory = (
            has_identical_memory
            and all_has_memory
            and (requests_memory == limit_memory)
        )

        cpu = max([cpu, requests_cpu, limit_cpu])
        memory = max([memory, requests_memory, limit_memory])

    if all_has_cpu and all_has_memory:
        qos = "Guaranteed"
    elif has_cpu or has_memory:
        qos = "Burstable"

    return cpu, memory, qos


class Global:
    fpath: str = OUTPUT / "dump.json"

    # retrieved data from kubectl
    context: str = None
    # resources in millicpu and MiB
    nodes: Dict[str, Dict] = {
        "storage": {"cpu": 8000, "memory": 96519},
        "system": {"cpu": 3000, "memory": 3930},
        "services": {"cpu": 8000, "memory": 32065},
        "stats": {"cpu": 8000, "memory": 32065},
    }
    namespaces: List = []
    pods: List[Dict[str, Dict]] = []

    # aggregated data built later-on
    ns_agg: Dict[str, Dict] = {}
    nodes_agg: Dict[str, Dict] = {}

    @classmethod
    def to_dict(cls) -> Dict[str, Dict]:
        return {
            "context": cls.context,
            "nodes": cls.nodes,
            "namespaces": cls.namespaces,
            "pods": cls.pods,
        }

    @classmethod
    def add_pod(cls, name, namespace, kind, timeframe, spec, nodes):
        cpu, memory, qos = conv_resources(spec)
        cls.pods.append(
            {
                "name": name,
                "namespace": namespace,
                "kind": kind,
                "timeframe": timeframe,
                "cpu": cpu,
                "memory": memory,
                "qos": qos,
                "nodes": nodes,
            }
        )

    @classmethod
    def get_namespaces(cls):
        cls.namespaces = kube(["get", "namespaces"], "{.items[*].metadata.name}")

    @classmethod
    def get_daemonsets(cls):
        for ds in kube(["get", "daemonsets", "-A"], "{.items[*]}"):
            cls.add_pod(
                name=ds["metadata"]["name"],
                kind="DaemonSet",
                timeframe="always",
                namespace=ds["metadata"]["namespace"],
                spec=ds["spec"]["template"]["spec"],
                nodes=list(cls.nodes.keys()),
            )

    @classmethod
    def get_deployments(cls):
        for depl in kube(["get", "deployments", "-A"], "{.items[*]}"):
            spec = depl["spec"]["template"]["spec"]
            cls.add_pod(
                name=depl["metadata"]["name"],
                kind="Deployment",
                timeframe="always",
                namespace=depl["metadata"]["namespace"],
                spec=spec,
                nodes=[
                    spec.get("nodeSelector", {}).get("k8s.kiwix.org/role", "system")
                ],
            )

    @classmethod
    def get_cronjobs(cls):
        for cj in kube(["get", "cronjobs", "-A"], "{.items[*]}"):
            spec = cj["spec"]["jobTemplate"]["spec"]["template"]["spec"]
            cls.add_pod(
                name=cj["metadata"]["name"],
                kind="Cronjob",
                timeframe=cj["spec"]["schedule"],
                namespace=cj["metadata"]["namespace"],
                spec=spec,
                nodes=[spec.get("nodeSelector", {}).get("k8s.kiwix.org/role")],
            )

    @classmethod
    def load(cls):
        with open(cls.fpath, "rb") as fh:
            dump = json.load(fh)
        Global.context = dump.get("context")
        Global.namespaces = dump.get("namespaces", [])
        Global.pods = dump.get("pods", [])

    @classmethod
    def save(cls):
        with open(cls.fpath, "w") as fh:
            dump = json.dump(cls.to_dict(), fh, indent=4)

    @classmethod
    def build_aggregation(cls):
        cls.total_cpu = 0
        cls.total_memory = 0
        cls.ns_agg = {
            ns: {"total_cpu": 0, "total_memory": 0, "services": [], "nodes": set()}
            for ns in cls.namespaces
        }
        cls.nodes_agg = {
            nodename: {
                "total_cpu": 0,
                "total_memory": 0,
                "cpu": node["cpu"],
                "memory": node["memory"],
                "namespaces": {
                    ns: {"total_cpu": 0, "total_memory": 0, "services": []}
                    for ns in cls.namespaces
                },
            }
            for nodename, node in Global.nodes.items()
        }
        for pod in cls.pods:
            ns = pod["namespace"]
            ns_target = cls.ns_agg[ns]
            for node in pod["nodes"]:
                ns_target["total_cpu"] += pod["cpu"]
                ns_target["total_memory"] += pod["memory"]
                ns_target["services"].append(pod)
                ns_target["nodes"].add(node)

                node_target = cls.nodes_agg[node]
                node_target["total_cpu"] += pod["cpu"]
                node_target["total_memory"] += pod["memory"]

                nsnode_target = node_target["namespaces"][ns]
                nsnode_target["total_cpu"] += pod["cpu"]
                nsnode_target["total_memory"] += pod["memory"]
                nsnode_target["services"].append(pod)

                cls.total_cpu += pod["cpu"]
                cls.total_memory += pod["memory"]


def fetch_data():
    Global.context = kube(["config", "current-context"])
    logger.info(f"Fetching resources usage for {Global.context}")

    Global.get_namespaces()
    logger.info(f"> {len(Global.namespaces)} namespaces")

    Global.get_daemonsets()
    Global.get_deployments()
    Global.get_cronjobs()


def gen_node(nodename: str):
    fpath = OUTPUT / f"node-{nodename}.html"
    with open(fpath, "w") as fh:
        fh.write(
            jinja_env.from_string(tmpl_header + node_template + tmpl_footer).render(
                {
                    "nodename": nodename,
                    "node": Global.nodes_agg[nodename],
                    "node_usage": {"cpu": 7320, "memory": 12636},
                    "namespaces": Global.ns_agg,
                    "nodes": Global.nodes,
                    "total_cpu": Global.total_cpu,
                    "total_memory": Global.total_memory,
                    "where": f"node-{nodename}",
                }
            )
        )


def gen_nodes():
    for node in Global.nodes.keys():
        gen_node(node)


def gen_overview():
    fpath = OUTPUT / f"index.html"
    with open(fpath, "w") as fh:
        fh.write(
            jinja_env.from_string(tmpl_header + overview_template + tmpl_footer).render(
                {
                    "namespaces": Global.ns_agg,
                    "detailed": False,
                    "nodes": Global.nodes,
                    "total_cpu": Global.total_cpu,
                    "total_memory": Global.total_memory,
                    "where": "overview",
                }
            )
        )
    fpath = OUTPUT / f"all.html"
    with open(fpath, "w") as fh:
        fh.write(
            jinja_env.from_string(tmpl_header + overview_template + tmpl_footer).render(
                {
                    "namespaces": Global.ns_agg,
                    "detailed": True,
                    "nodes": Global.nodes,
                    "total_cpu": Global.total_cpu,
                    "total_memory": Global.total_memory,
                    "where": "detailed",
                }
            )
        )


def main(keep: bool = False):
    OUTPUT.mkdir(exist_ok=True)
    if keep and Global.fpath.exists():
        logger.info(f"Reloading resources from {Global.fpath}...")
        Global.load()
        logger.info(f"> {len(Global.namespaces)} namespaces")
        logger.info(f"> {len(Global.pods)} pods")
    else:
        fetch_data()

    Global.build_aggregation()

    gen_overview()
    gen_nodes()

    if keep:
        Global.save()


if __name__ == "__main__":
    main(*sys.argv[1:])
