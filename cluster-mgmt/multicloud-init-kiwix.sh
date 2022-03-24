#!/bin/bash

# uncomment to debug
#set -x


if [ "$(lsb_release -i |grep Debian)" ] ; then
 distro="debian"
 AVAIL_VERSIONS="11"
else
 distro="ubuntu"
 AVAIL_VERSIONS="20.04"
fi


prettydate() {
  date '+%Y-%m-%d %H:%M:%S'
}

get_latest_release() {
  curl --silent "https://api.github.com/repos/$1/releases/latest" | # Get latest release from GitHub api
    grep '"tag_name":' |                                            # Get tag line
    sed -E 's/.*"([^"]+)".*/\1/' |                                  # Pluck JSON value
    sed -E 's/^v(.+)/\1/'                                           # remove leadind "v"
}

log() {
 script_name=${1}
 log_mess=${2}
 ret_code=${3}

 nocolor='\033[0m'
 if [[ ${ret_code} -eq 0 ]]; then
   color='\033[0;32m'
   text='OK'
 else
   color='\033[0;31m'
   text='FAILED'
 fi

 printf "[$(prettydate)] %s: %s (%s) ${color}[${text}]${nocolor}\n" \
         "${script_name}" \
         "${log_mess}" \
         ${ret_code}
}

function usage {
  echo "$0 usage: -t scw_token -p pool_id -r region [-a tag1,[tag2]]"
  exit 0
}

# checking version
function version_check {
  version=$(lsb_release -r |sed -E 's/.+\:\s+([0-9\.\-]+)$/\1/')
  version_check=$(echo "${AVAIL_VERSIONS}" | grep "${version}")
  if [[ -z ${version_check} ]]; then
    log "version check" "version ${version} unsupported" 255
    exit 255
  else
    log "version check" "version is ok"
  fi
}

# this function install containerd
function apt_prerequisites {
  apt -qq update > /dev/null 2>&1
  apt -qq -y install \
    curl \
    jq \
    apt-transport-https \
    ca-certificates \
    software-properties-common > /dev/null 2>&1

  if [ "${distro}" = "debian" ] ; then
    apt -qq -y install gnupg gnupg-utils gnupg-l10n libseccomp2 iptables
  fi

  log "apt prerequisites" "installing apt dependencies" ${?}
}

function install_containerd {
 # containerd config
 tee /etc/modules-load.d/containerd.conf &> /dev/null <<EOF
overlay
br_netfilter
EOF

  # loading modules for containerd
  modprobe overlay
  modprobe br_netfilter

  # setup required sysctl params, these persist across reboots.
  tee /etc/sysctl.d/99-kubernetes-cri.conf &> /dev/null << EOF
net.bridge.bridge-nf-call-iptables  = 1
net.ipv4.ip_forward                 = 1
net.bridge.bridge-nf-call-ip6tables = 1
EOF

  # apply sysctl params without reboot
  sysctl --system > /dev/null 2>&1

  # retrieve latest release version
  containerd_version=$(get_latest_release containerd/containerd)
  curl -s -O -L "https://github.com/containerd/containerd/releases/download/v${containerd_version}/cri-containerd-cni-${containerd_version}-linux-amd64.tar.gz"
  curl -s -O -L "https://github.com/containerd/containerd/releases/download/v${containerd_version}/cri-containerd-cni-${containerd_version}-linux-amd64.tar.gz.sha256sum"
  sha256sum --check "cri-containerd-cni-${containerd_version}-linux-amd64.tar.gz.sha256sum"
  tar --no-overwrite-dir -C / -xzf "cri-containerd-cni-${containerd_version}-linux-amd64.tar.gz"
  retval=$?

  systemctl daemon-reload
  mkdir -p /etc/containerd

  containerd config default > /etc/containerd/config.toml

  systemctl restart containerd > /dev/null 2>&1

  log "containerd" "installing containerd (v${containerd_version})" ${retval}
}

function scaleway_multicloud {
  kubelet_dir=/var/lib/kubelet
  kubeproxy_dir=/var/lib/kube-proxy
  scw_api=https://api.scaleway.com
  scw_token=$1
  tag=$2
  pool_id=$3
  region=$4

  curl -fsSL -k -d {} -H "X-Auth-Token: ${scw_token}" \
    -X POST \
    ${scw_api}/k8s-private/v1beta2/regions/${region}/pools/${pool_id}/node > /tmp/call

  if [[ ${?} -ne 0 ]]; then
    log "scaleway api call" "Error calling scw api" 255
    cat /tmp/call
    exit 255
  fi

  # cluster version
  cluster_version=$(cat /tmp/call | jq -r ".cluster_version")

  # kube node token
  node_token=$(cat /tmp/call | jq -r ".kube_token")

  # cluster url
  cluster_url=$(cat /tmp/call | jq -r ".cluster_url")

  # node name
  NODE_NAME=$(cat /tmp/call | jq -r ".name")

  # kube-proxy dir
  if [[ ! -d ${kubeproxy_dir} ]]; then
    mkdir -p ${kubeproxy_dir}
  fi

  # kubelet configuration
  if [[ ! -d ${kubelet_dir} ]]; then
    mkdir ${kubelet_dir}
  fi
  cat /tmp/call | jq -r ".kubelet_config" | base64 --decode > ${kubelet_dir}/kubelet.conf

  # ca
  if [[ ! -d ${kubelet_dir}/pki ]]; then
    mkdir -p ${kubelet_dir}/pki
  fi
  cat /tmp/call | jq -r ".cluster_ca" | base64 --decode > ${kubelet_dir}/pki/ca.crt

  # kubelet env
  node_name=$(cat /tmp/call | jq -r ".name")
  echo "NODE_NAME=${NODE_NAME}" > ${kubelet_dir}/kubelet.env

  # kilo label
  echo -n "NODELABELS=k8s.scw.cloud/disable-lifecycle=true" >> ${kubelet_dir}/kubelet.env

  node_public_ip=$(curl -s ifconfig.me/ip)
  log "multicloud node" "getting public ip" $?
  echo -n ",k8s.scw.cloud/node-public-ip=${node_public_ip}" >> ${kubelet_dir}/kubelet.env
  echo -n ",topology.kubernetes.io/region=${NODE_NAME}" >> ${kubelet_dir}/kubelet.env

  if [[ "${tag}" == "null" ]]; then
    echo "" >> ${kubelet_dir}/kubelet.env
  else
    echo ",${tag}" >> ${kubelet_dir}/kubelet.env
  fi

  # install kubelet and kubectl
  install_kube ${cluster_version}

  # kubelet configuration
  kubectl config set-cluster "kubernetes" \
    --certificate-authority=/var/lib/kubelet/pki/ca.crt \
    --embed-certs=true --server="${cluster_url}" \
    --kubeconfig=/var/lib/kubelet/kubeconfig > /dev/null 2>&1

  kubectl config set-credentials system:node:"${NODE_NAME}" \
    --token="node:${NODE_NAME}:${node_token}" \
    --kubeconfig=/var/lib/kubelet/kubeconfig > /dev/null 2>&1

  kubectl config set-context default \
    --cluster="kubernetes" \
    --user=system:node:"${NODE_NAME}" \
    --kubeconfig=/var/lib/kubelet/kubeconfig > /dev/null 2>&1

  kubectl config use-context default \
    --kubeconfig=/var/lib/kubelet/kubeconfig > /dev/null 2>&1

  # kube-proxy configuration
  kubectl config set-cluster "kubernetes" \
    --certificate-authority=/var/lib/kubelet/pki/ca.crt \
    --embed-certs=true --server="${cluster_url}" \
    --kubeconfig=/var/lib/kube-proxy/kubeconfig > /dev/null 2>&1

  kubectl config set-credentials default \
    --token="proxy:${NODE_NAME}:${node_token}" \
    --kubeconfig=/var/lib/kube-proxy/kubeconfig > /dev/null 2>&1

  kubectl config set-context default \
    --cluster="kubernetes" \
    --user=default \
    --kubeconfig=/var/lib/kube-proxy/kubeconfig > /dev/null 2>&1

  kubectl config use-context default \
    --kubeconfig=/var/lib/kube-proxy/kubeconfig > /dev/null 2>&1

  systemctl enable systemd-resolved > /dev/null 2>&1
  systemctl start systemd-resolved > /dev/null 2>&1
  systemctl start kubelet.service > /dev/null 2>&1

  log "multicloud node" "configuring this a node as a kubernetes node" $?
}

# this function install kubelet and kubectl
function install_kube {
  kubernetes_version=${1}
  dir_bin="/usr/local/bin"

  if [[ -d ${dir_bin} ]]; then
    mkdir -p /usr/local/bin
  fi

  # get kubelet and kubectl
  curl -L "https://storage.googleapis.com/kubernetes-release/release/v${kubernetes_version}/bin/linux/amd64/kubectl" \
    -o /usr/local/bin/kubectl > /dev/null 2>&1
  curl -L "https://storage.googleapis.com/kubernetes-release/release/v${kubernetes_version}/bin/linux/amd64/kubelet" \
    -o /usr/local/bin/kubelet > /dev/null 2>&1

  chmod +x /usr/local/bin/kubelet \
       /usr/local/bin/kubectl

  # write kubelet service

  tee /usr/lib/systemd/system/kubelet.service &> /dev/null <<EOF
[Unit]
Description=Kubernetes Kubelet
Documentation=https://github.com/kubernetes/kubernetes
After=containerd.service
Requires=containerd.service

[Service]
EnvironmentFile=/var/lib/kubelet/kubelet.env
ExecStart=/usr/local/bin/kubelet \\
  --image-pull-progress-deadline=2m \\
  --kubeconfig=/var/lib/kubelet/kubeconfig \\
  --network-plugin=cni \\
  --cert-dir=/var/lib/kubelet/pki \\
  --experimental-allocatable-ignore-eviction \\
  --node-labels=\${NODELABELS} \\
  --pod-infra-container-image=gcr.io/google-containers/pause:3.2 \\
  --hostname-override=\${NODE_NAME} \\
  --config=/var/lib/kubelet/kubelet.conf \\
  --container-runtime-endpoint=unix:///var/run/containerd/containerd.sock \
  --container-runtime=remote \
  --cloud-provider=external \
  --v=2
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

  swapoff -a
  systemctl daemon-reload
  log "kubernetes prerequisites" "installing and configuring kubelet" $?
}

# function check kubelet runing
function check_kubelet_running {
  KUBELET_BIN="kubelet"
  kubelet_process=$(ps -ef | grep -i kubelet)
  if [[ -z "${kubelet_process}" ]]; then
    log "kubelet running" "kubelet is already running on this host" 255
    exit 255
  fi
}

if [[ "$#" -eq 0 ]]; then
  usage
fi

echo "$0 for ${distro}"

while getopts a:r:p:t:h flag
do
    case "${flag}" in
      t) token=${OPTARG};;
      # override kilo location
      a) tag=${OPTARG};;
      p) pool_id=${OPTARG};;
      r) region=${OPTARG};;
      h) usage;;
      *) usage;;
      :) usage;;
      \?) usage ;;
    esac
done

if [[ $EUID -ne 0 ]]; then
  echo "script must be run as root"
  usage
fi

if [[ -z "${tag}" ]]; then
 tag="null"
fi

if [ -z "${token}" ] || [ -z "${pool_id}" ] || \
   [ -z "${region}" ]; then
        echo "Missing mandatory arg"
        usage
fi

# checking if pool_id is a valid uuid
if ! [[ ${pool_id} =~ ^\{?[A-F0-9a-f]{8}-[A-F0-9a-f]{4}-[A-F0-9a-f]{4}-[A-F0-9a-f]{4}-[A-F0-9a-f]{12}\}?$ ]]; then
    echo "${pool_id} is not a valid uuid"
    usage
fi

# checking if scaleway token is an uuid
if ! [[ ${token} =~ ^\{?[A-F0-9a-f]{8}-[A-F0-9a-f]{4}-[A-F0-9a-f]{4}-[A-F0-9a-f]{4}-[A-F0-9a-f]{12}\}?$ ]]; then
    echo "${token} is not a valid uuid"
    usage
fi

version_check
check_kubelet_running
apt_prerequisites
install_containerd
scaleway_multicloud ${token} ${tag} ${pool_id} ${region}
