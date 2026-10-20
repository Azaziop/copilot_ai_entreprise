#!/usr/bin/env bash
# Wait for ingress-nginx controller EXTERNAL-IP and print it.
set -euo pipefail
NS="${INGRESS_NAMESPACE:-ingress-nginx}"
SVC="${INGRESS_SERVICE:-ingress-nginx-controller}"
TIMEOUT="${INGRESS_WAIT_TIMEOUT:-300}"
elapsed=0
while [ "$elapsed" -lt "$TIMEOUT" ]; do
  IP=$(kubectl -n "$NS" get svc "$SVC" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
  if [ -n "${IP:-}" ]; then
    echo "$IP"
    exit 0
  fi
  HOST=$(kubectl -n "$NS" get svc "$SVC" -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || true)
  if [ -n "${HOST:-}" ]; then
    echo "$HOST"
    exit 0
  fi
  sleep 10
  elapsed=$((elapsed + 10))
done
echo "Timed out waiting for Ingress EXTERNAL-IP" >&2
exit 1
