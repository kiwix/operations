The resources in this namespace come from the `grafana-k8s-monitoring` helm chart from `grafana`.

These resources are deployed via Helm.


# Requirements

You need to have proper kubeconfig ready on your machine, with admin privileges on the cluster.

You need Helm 3 client installed on your machine.

You need to have grafana Helm repo configured:
```
helm repo add grafana https://grafana.github.io/helm-charts
```

You need a copy of the secret values (file named `grafana.values.secret.yaml`).

# Installation / upgrade

First update helm repo:
```
helm repo update
```

Then install the helm chart with custom values are stored in this repo:
```
  helm upgrade --install grafana-k8s-monitoring grafana/k8s-monitoring \
    --namespace "grafana" --create-namespace --values grafana.values.yaml \
    --values grafana.values.secret.yaml
```

Remark:
Do not mind about `policy/v1beta1 PodSecurityPolicy is deprecated in v1.21+, unavailable in v1.25+` warnings, 
they are indeed gracefully handled depending on the cluster capabilities.

To upgrade (e.g. kube-state-metrics version):
```
helm upgrade grafana-k8s-monitoring grafana/k8s-monitoring \
    --namespace "grafana" --values grafana.values.yaml \
    --values grafana.values.secret.yaml
```

If you face issues while upgrading due to deprecated API version in objects, you might benefit from using the
mapkubeapis plugin.

First, install the plugin:
```
helm plugin install https://github.com/helm/helm-mapkubeapis
```

Then, update release with mapkubeapis (will delete obsoleted objects and map old api to new ones):
```
helm mapkubeapis grafana-k8s-monitoring --namespace "grafana"
```

