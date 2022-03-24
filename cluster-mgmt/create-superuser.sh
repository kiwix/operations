#!/bin/bash

set -e

# Create a *superuser* for the cluster.
# Permissions are similar to the default admin of the cluster that scaleway provides
# credentials for.
# Difference is that this one will be properly identified and easier to revoke.
# Requires the scaleway-provided config to be at $adminconfpath path (see below).

USERNAME=$1
CLUSTERURL=https://api.scw.k8s.kiwix.org:6443
NAMESPACE=default
GROUPNAME=cluster-admin
### CONFIG-END


if [ -z "$USERNAME" ] ; then
  printf "Missing username.\nUsage: $0 USERNAME"
  exit 1
fi

adminconfpath=~/.kube/scw-admin_kiwix-prod.config

if [ ! -f $adminconfpath ] ; then
  echo "Expects cluster admin config at ${adminconfpath}"
  exit 1
fi

function kube {
  kubectl --kubeconfig $adminconfpath "$@"
}

CA_CERT="users/ca.crt"

if [ ! -f $CA_CERT ] ; then
  echo "Retrieving CA certificate first"
  kube get configmap kube-root-ca.crt -o json |jq -r '.data."ca.crt"' > $CA_CERT
fi

echo "Creating certificate for User $USERNAME"
CERTIFICATE_NAME="user-${USERNAME}"
CONFIGNAME="users/${USERNAME}_kiwix-prod.config"
CSR_FILE="users/${USERNAME}.csr"
KEY_FILE="users/${USERNAME}.key"
CRT_FILE="users/${USERNAME}.crt"

openssl genrsa -out ${KEY_FILE} 4096

openssl req -new -key $KEY_FILE -out $CSR_FILE -subj "/CN=$USERNAME/O=$GROUPNAME"

cat <<EOF | kube create -f -
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

kube certificate approve $CERTIFICATE_NAME

kube get csr $CERTIFICATE_NAME -o jsonpath='{.status.certificate}' | base64 -d > $CRT_FILE

echo "Generate kubeconfig for $USERNAME"
kubectl config --kubeconfig $CONFIGNAME set-credentials "${USERNAME}_kiwix-prod" --client-key=$KEY_FILE --client-certificate=$CRT_FILE --embed-certs=true
kubectl config --kubeconfig $CONFIGNAME set-cluster kiwix-prod --embed-certs --certificate-authority=$CA_CERT --server=$CLUSTERURL
kubectl config --kubeconfig $CONFIGNAME set-context "${USERNAME}@kiwix-prod" --cluster=kiwix-prod --user="${USERNAME}_kiwix-prod" --namespace=$NAMESPACE
kubectl config --kubeconfig $CONFIGNAME use-context "${USERNAME}@kiwix-prod"

echo "Add cluster-admin ClusterRole to User $USERNAME (using cluster-admins binding)"
echo "> failure to add probably means it exists and must be updated manually (append user to subjects)"

cat <<EOF | kube create -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  annotations:
    rbac.authorization.kubernetes.io/autoupdate: "true"
  labels:
    kubernetes.io/bootstrapping: rbac-defaults
  name: cluster-admins
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: cluster-admin
subjects:
- apiGroup: rbac.authorization.k8s.io
  kind: User
  name: $USERNAME
EOF
