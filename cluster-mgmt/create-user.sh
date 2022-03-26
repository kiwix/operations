#!/usr/bin/env bash

set -e

USERNAME=$1
NAMESPACE=$2
GROUPNAME=$3
CLUSTERURL=https://api.scw.k8s.kiwix.org:6443
NAMESPACE="${NAMESPACE:=default}"
GROUPNAME="${GROUPNAME:=users}"  # users | gh-bots
### CONFIG-END


if [ -z "$USERNAME" ] ; then
  printf "Missing username.\nUsage: $0 USERNAME [NAMESPACE, [GROUPNAME]]"
  exit 1
fi

read -r -n 1 -p "Ready for User creation with username=${USERNAME}, namespace=${NAMESPACE}, groupname=${GROUPNAME}. OK ? ^C if not. "

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
CA_CERT="${SCRIPT_DIR}/users/ca.crt"

if [ ! -f $CA_CERT ] ; then
  echo "Retrieving CA certificate first"
  kubectl get configmap kube-root-ca.crt -o json |jq -r '.data."ca.crt"' > $CA_CERT
fi

echo "Creating certificate for User ${USERNAME} with Group ${GROUPNAME}"
CERTIFICATE_NAME="user-${USERNAME}"
CONFIGNAME="${SCRIPT_DIR}/users/${USERNAME}_kiwix-prod.config"
CSR_FILE="${SCRIPT_DIR}/users/${USERNAME}.csr"
KEY_FILE="${SCRIPT_DIR}/users/${USERNAME}.key"
CRT_FILE="${SCRIPT_DIR}/users/${USERNAME}.crt"

openssl genrsa -out ${KEY_FILE} 4096

openssl req -new -key $KEY_FILE -out $CSR_FILE -subj "/CN=$USERNAME/O=$GROUPNAME"

cat <<EOF | kubectl create -f -
apiVersion: certificates.k8s.io/v1
kind: CertificateSigningRequest
metadata:
  name: $CERTIFICATE_NAME
spec:
  groups:
  - system:authenticated
  request: $(cat $CSR_FILE | base64 | tr -d '\n')
  signerName: kubernetes.io/kube-apiserver-client
  # one year expiration
  expirationSeconds: 31536000
  usages:
  - client auth
EOF

kubectl certificate approve $CERTIFICATE_NAME

kubectl get csr $CERTIFICATE_NAME -o jsonpath='{.status.certificate}' | base64 -d > $CRT_FILE

echo "Generate kubeconfig for ${USERNAME}_kiwix-prod on namespace ${NAMESPACE}"
kubectl config --kubeconfig $CONFIGNAME set-credentials "${USERNAME}_kiwix-prod" --client-key=$KEY_FILE --client-certificate=$CRT_FILE --embed-certs=true
kubectl config --kubeconfig $CONFIGNAME set-cluster kiwix-prod --embed-certs --certificate-authority=$CA_CERT --server=$CLUSTERURL
kubectl config --kubeconfig $CONFIGNAME set-context "${USERNAME}@kiwix-prod" --cluster=kiwix-prod --user="${USERNAME}_kiwix-prod" --namespace=$NAMESPACE
kubectl config --kubeconfig $CONFIGNAME use-context "${USERNAME}@kiwix-prod"
