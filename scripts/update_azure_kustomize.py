#!/usr/bin/env python3
"""Rewrite k8s/overlays/azure/kustomization.yaml image refs for GitOps."""

from __future__ import annotations

import argparse
from pathlib import Path


TEMPLATE = """apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: enterprise-copilot

resources:
  - ../../base

images:
  - name: copilot-backend
    newName: {acr}/copilot-backend
    newTag: {tag}
  - name: copilot-frontend
    newName: {acr}/copilot-frontend
    newTag: {tag}

patches:
  - path: patch-services-lb.yaml
  - path: patch-pull-policy.yaml
  - path: patch-configmap.yaml
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--acr", required=True, help="ACR login server")
    parser.add_argument("--tag", required=True, help="Image tag")
    parser.add_argument(
        "--file",
        default="k8s/overlays/azure/kustomization.yaml",
        help="Target kustomization path",
    )
    args = parser.parse_args()
    path = Path(args.file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TEMPLATE.format(acr=args.acr.rstrip("/"), tag=args.tag), encoding="utf-8")
    print(f"Updated {path} -> {args.acr} @ {args.tag}")


if __name__ == "__main__":
    main()
