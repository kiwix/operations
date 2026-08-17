# Zammad helpdesk solution

Zammad is deployed using [zammad-helm](https://github.com/zammad/zammad-helm/tree/main/zammad) chart.

## First-time

```sh
helm repo add zammad https://zammad.github.io/zammad-helm
```

## Update

```sh
helm repo update zammad
helm upgrade --install -n zammad -f values.yaml zammad zammad/zammad
```

## Important

- We don't use any secret (sentitive parts are not exposed)
- We use `nodeSelector`s in `values.yaml` to assign all components to `services` node
- We use `existingClaim`s in `values.yaml` to use our own PV+PVC for storage
- We don't use minio and store everything in the DB


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

