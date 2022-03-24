#!/usr/bin/env bash

# Create a *superuser* for the cluster.
# Permissions are similar to the default admin of the cluster that scaleway provides
# credentials for.
# Difference is that this one will be properly identified and easier to revoke.
# Requires the scaleway-provided config to be at $ADMIN_CONF_PATH path (see below).

set -e

USERNAME=$1
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
ADMIN_CONF_PATH=~/.kube/scw-admin_kiwix-prod.config

if [ ! -f $ADMIN_CONF_PATH ] ; then
  echo "Expects cluster admin config at ${ADMIN_CONF_PATH}"
  exit 1
fi
KUBECONFIG=${ADMIN_CONF_PATH}

echo "Create User ${USERNAME}…"
KUBECONFIG=$KUBECONFIG $SCRIPT_DIR/create-user.sh $USERNAME

echo "Add cluster-admin ClusterRole to User $USERNAME (using cluster-admins binding)"
echo "> failure to add probably means it exists and must be updated manually (append user to subjects)"

cat <<EOF | kubectl create -f -
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
