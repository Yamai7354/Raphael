#!/usr/bin/env bash
# Source this file to configure kubectl/helm for the raphael-swarm cluster
# Usage:  source infrastructure/env.sh

INFRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export KUBECONFIG="$INFRA_DIR/kubeconfig.yaml"
export TMPDIR="$INFRA_DIR/tmp"
export HELM_CONFIG_HOME="$INFRA_DIR/helm-config"
export HELM_CACHE_HOME="$INFRA_DIR/helm-cache"
export HELM_DATA_HOME="$INFRA_DIR/helm-data"
export PATH="$INFRA_DIR/bin:$PATH"

echo "✓ Cluster: raphael-swarm"
echo "✓ KUBECONFIG: $KUBECONFIG"
echo "✓ Registry:  localhost:5111"
