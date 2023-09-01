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

