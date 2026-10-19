# Enterprise Copilot — RAG Project Structure (Scalable)

Architecture RAG hybride : indexation offline, requête online, rerank, génération grounded, eval et observabilité.

## Structure

```
.
├── README.md
├── requirements.txt
├── .env
├── .gitignore
├── config.yaml
├── Dockerfile
├── docker-compose.yaml
├── main.py
├── data/
│   ├── raw/          # documents sources
│   ├── parsed/       # fichiers parsés / index BM25
│   └── eval/         # golden set
├── src/
│   ├── schemas/      # Document, Chunk, QueryResult
│   ├── ingestion/    # loaders + parsers
│   ├── chunking/
│   ├── embeddings/
│   ├── vector_db/
│   ├── lexical/      # BM25
│   ├── retrieval/    # hybrid + RRF
│   ├── rerank/
│   ├── query/
│   ├── cache/
│   ├── prompts/
│   ├── llm/
│   ├── generation/
│   ├── eval/
│   ├── observability/
│   ├── security/     # ACL
│   ├── api/          # FastAPI routes
│   ├── pipelines/    # index + query
│   └── utils/
├── jobs/
│   ├── index_corpus.py
│   └── eval_nightly.py
├── tests/
│   └── test_retrieval.py
└── logs/
    └── app.log
```

## Quick start

```bash
pip install -r requirements.txt
# ou: uv sync

# Indexer le corpus
python jobs/index_corpus.py

# Lancer l'API
python main.py
```

## Kubernetes

```bash
# Local Minikube
kubectl apply -k k8s/overlays/minikube

# Azure / Argo CD uses k8s/overlays/azure
```

See [docs/AZURE_DEPLOY.md](docs/AZURE_DEPLOY.md) for Terraform + GitHub Actions + Argo CD on Azure AKS.

## Principes

- Config / secrets / prompts / data séparés du code
- Pipeline d'indexation (offline) ≠ pipeline de requête (online)
- Hybrid search (vector + lexical) → rerank → génération avec citations
- Eval, traces et ACL comme citoyens de première classe
