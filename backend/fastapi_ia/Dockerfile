# backend/fastapi_ia/Dockerfile
FROM python:3.11.11-slim-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/
# ── torch en version PROCESSEUR, jamais CUDA (03/08/2026) ──────────────────
# Mesuré DANS l'image en production : `site-packages` pesait 5,6 Go, dont
# `nvidia` 2,7 Go et `triton` 691 Mo — soit 3,4 Go de bibliothèques GPU sur un
# serveur Hetzner qui n'a AUCUNE carte graphique (`nvidia-smi` absent). Elles
# arrivaient en dépendance transitive de `sentence-transformers`, dont l'index
# PyPI par défaut sert les roues CUDA.
#
# `sentence-transformers` EST bel et bien utilisé — ne pas le retirer :
# `app/services/sql_agent_service.py::_get_embeddings` charge
# `HuggingFaceEmbeddings(all-MiniLM-L6-v2)` avec `device: "cpu"`, préchauffé au
# démarrage par `app/main.py`. C'est bien la variante CPU qu'il lui faut, et
# c'est exactement ce que cette ligne installe — même fonctionnalité, ~3,4 Go
# de moins à construire, à exporter et à décompresser À CHAQUE DÉPLOIEMENT.
#
# L'index CPU est consulté EN PREMIER (torch et ses satellites y sont), puis
# PyPI pour tout le reste : `--extra-index-url` garde donc l'installation
# complète, il ne fait que changer la roue de torch.
RUN pip install --no-cache-dir \
      --index-url https://download.pytorch.org/whl/cpu \
      --extra-index-url https://pypi.org/simple \
      -r requirements.txt

COPY . /app/

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
