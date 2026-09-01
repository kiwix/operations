#!/usr/bin/env bash
set -euo pipefail

AFFINITY_PATCH='
{
  "spec": {
    "template": {
      "spec": {
        "nodeSelector": null,
        "affinity": {
          "nodeAffinity": {
            "requiredDuringSchedulingIgnoredDuringExecution": {
              "nodeSelectorTerms": [
                {
                  "matchExpressions": [
                    {
                      "key": "k8s.kiwix.org/core-services",
                      "operator": "In",
                      "values": ["primary", "secondary"]
                    }
                  ]
                }
              ]
            },
            "preferredDuringSchedulingIgnoredDuringExecution": [
              {
                "weight": 1,
                "preference": {
                  "matchExpressions": [
                    {
                      "key": "k8s.kiwix.org/core-services",
                      "operator": "In",
                      "values": ["primary"]
                    }
                  ]
                }
              },
              {
                "weight": 2,
                "preference": {
                  "matchExpressions": [
                    {
                      "key": "k8s.kiwix.org/core-services",
                      "operator": "In",
                      "values": ["secondary"]
                    }
                  ]
                }
              }
            ]
          }
        }
      }
    }
  }
}'

# deployment:namespace pairs
declare -A DEPLOYMENTS=(
  [cert-manager]="cert-manager"
  [cert-manager-webhook]="cert-manager"
  [cert-manager-cainjector]="cert-manager"
  [coredns]="kube-system"
  [metrics-server]="kube-system"
)

for dep in "${!DEPLOYMENTS[@]}"; do
  ns="${DEPLOYMENTS[$dep]}"
  echo "Patching deployment/$dep in namespace $ns..."
  kubectl patch deployment "$dep" -n "$ns" --type=merge -p="$AFFINITY_PATCH"
done