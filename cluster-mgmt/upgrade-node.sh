#!/bin/bash

# Upgrades the kubernetes version of a node.
# Expects the cluster and nodepool to already be at the new version

set -e

kubernetes_version=${1}

if [ -z "${kubernetes_version}" ] ; then
  echo "Usage: $0 CLUSTER_VERSION."
  echo ""
  echo "You can retrieve it with curl -H \"X-Auth-Token: \$SCW_SECRET_KEY\" https://api.scaleway.com/k8s/v1/regions/fr-par/clusters/\$CLUSTER_ID |jq '.version'"
  exit 1
fi

echo "Your are about to shutdown kubelet for upgrade. You should have cordon'd the node."
read -p "Continue (y/n)?" confirm
if [ "$confirm" != "y" ]; then
  exit
fi

# this function install kubelet and kubectl
function download_kube {
  kubernetes_version=${1}
  echo "Downloading kubelet and kubectl v${kubernetes_version}"

  dir_bin="/usr/local/bin"

  if [[ -d ${dir_bin} ]]; then
    mkdir -p /usr/local/bin
  fi

  # get kubelet and kubectl
  curl -L "https://storage.googleapis.com/kubernetes-release/release/v${kubernetes_version}/bin/linux/amd64/kubectl" -o /usr/local/bin/kubectl-new
  curl -L "https://storage.googleapis.com/kubernetes-release/release/v${kubernetes_version}/bin/linux/amd64/kubelet" -o /usr/local/bin/kubelet-new
  chmod +x /usr/local/bin/kubelet-new /usr/local/bin/kubectl-new
}

echo "Downloading kubelet and kubectl v${kubernetes_version}"
download_kube ${kubernetes_version}

echo "Stopping kubelet"
systemctl stop kubelet.service

echo "Swaping binaries"
mv /usr/local/bin/kubectl /usr/local/bin/kubectl-old
mv /usr/local/bin/kubelet /usr/local/bin/kubelet-old
mv /usr/local/bin/kubectl-new /usr/local/bin/kubectl
mv /usr/local/bin/kubelet-new /usr/local/bin/kubelet
echo "Staring kubelet"
systemctl start kubelet.service
systemctl status --no-pager kubelet.service
echo "Upgraded: $(/usr/local/bin/kubelet --version)"
echo "You can now uncordon the node."
