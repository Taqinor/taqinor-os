# Environnement du service d'IA (backend/fastapi_ia) — Python 3.11, dépendances de requirements.txt + pytest.
# La CI joue : (depuis backend/fastapi_ia) python -m unittest -v tests.test_action_tools tests.test_prompt_copilote …
# `python -m pytest tests/<fichier>.py -q` marche aussi ici.
export PATH=/opt/venv-ia/bin:$(echo "$PATH" | sed 's#/opt/venv-erp/bin:##g')
export DJANGO_SECRET_KEY=cloud-dev-only-secret-key-not-used-in-production
export DB_NAME=${DB_NAME:-erp_db}
export DB_USER=erp_user
export DB_PASSWORD=erp_password
export DB_HOST=localhost
export DB_PORT=5432
export REDIS_HOST=localhost
export REDIS_PORT=6379
export PYTHONTZPATH=""
export PYTHONIOENCODING=utf-8
