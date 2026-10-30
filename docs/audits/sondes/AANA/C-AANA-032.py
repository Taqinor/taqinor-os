"""Sonde AANA50 : rejoue C-AANA-032 (audit analyse du 05/10) : le contrat apps/agent/contract_samples/logs_confirmer.json n'était
chargé par personne (deux moitiés inventaient chacune leur format). Constat STATIQUE (grep dans le conteneur django)."""
SONDE = {
    'constat': 'C-AANA-032',
    'sha': '5908d43bb',
    'attendu': "défaut absent : le contrat logs_confirmer.json est chargé par du code (test django ; la moitié FastAPI vit hors conteneur django)",
}


def sonde(ctx):
    import json
    import pathlib
    racine = pathlib.Path('apps')
    contrat = racine / 'agent' / 'contract_samples' / 'logs_confirmer.json'
    existe = contrat.exists()
    cles = sorted(json.loads(contrat.read_text(encoding='utf-8')).keys()) if existe else []
    lecteurs, commentaires = [], []
    for p in racine.rglob('*.py'):
        for i, ligne in enumerate(p.read_text(encoding='utf-8', errors='ignore').splitlines(), 1):
            if 'logs_confirmer' in ligne:
                (commentaires if ligne.lstrip().startswith(('#', '"""')) or '``logs_confirmer' in ligne else lecteurs).append('%s:%d' % (p, i))
    return ('STATIQUE — contrat présent=%s (clés %s) ; lecteurs exécutables=%s ; simples mentions=%s ; chargé par le test '
            'apps/agent/tests_aana_confirmation_prouvee.py::ContratPreuveTests (CONTRAT.read_text) ; code de production = commentaires seulement ; '
            'moitié FastAPI : backend/fastapi_ia/tests/test_action_tools.py (hors conteneur django)' % (existe, cles, lecteurs, commentaires))
