# flake8: noqa  (sonde HÔTE d'audit PF9 « doubles clics, gestes rejoués, courses », groupe ACNC — sans Django, sans base, sans Docker)
"""C-ACNC-018 — l'assistant : `confirm_proposal` lit le jeton, exécute, PUIS le détruit (usage unique non atomique, aucune clé transmise à Django).
On extrait par ast les VRAIES fonctions de `backend/fastapi_ia/app/services/action_tools.py`, sur un faux Redis (get/set/delete/getdel) ; l'appel Django
est un bouchon qui crée un paiement (sauf clé d'idempotence déjà vue) et, PENDANT cet appel, une 2e confirmation du MÊME jeton arrive."""
SONDE = {"constat": "C-ACNC-018", "sha": "3acfee471",
         "attendu": "la 2e confirmation passe pendant que la 1re s'exécute : 2 paiements créés par Django pour un seul jeton"}
import ast, hashlib, hmac, json, os, pathlib, secrets, sys, time, types, typing, __future__
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
CHEMIN = "backend/fastapi_ia/app/services/action_tools.py"


def sonde(ctx=None):
    arbre = ast.parse((RACINE / CHEMIN).read_text(encoding="utf-8"))
    store, paiements, cles, etat = {}, [], set(), {"imbrique": False, "seconde": None}
    class FauxRedis:
        def set(s, k, v, ex=None, nx=False, **kw):
            if nx and k in store: return None
            store[k] = v; return True
        def get(s, k): return store.get(k)
        def delete(s, k): return int(store.pop(k, None) is not None)
        def getdel(s, k): return store.pop(k, None)
        def pipeline(s, *a, **k): raise RuntimeError("non simulé")
    def execute(c, action, inputs, *a, **k):  # = l'appel HTTP à Django enregistrer-paiement
        cle = k.get("idempotency_key") or k.get("cle_idempotence") or inputs.get("idempotency_key") or (a[0] if a and isinstance(a[0], str) else None)
        if not (cle and cle in cles):
            paiements.append(dict(inputs)); cle and cles.add(cle)
        if not etat["imbrique"]:  # 2e confirmation du même jeton PENDANT l'exécution de la 1re (double clic, 2e onglet)
            etat["imbrique"] = True; etat["seconde"] = g["confirm_proposal"](contexte, jeton)
        return {"ok": True, "data": {"id": len(paiements)}}
    g = {"__name__": "action_tools", "json": json, "hmac": hmac, "hashlib": hashlib, "secrets": secrets, "time": time, "os": os, "Optional": typing.Optional,
         "Any": typing.Any, "ActionContext": object, "ACTION_PROPOSAL_SECRET": "s", "ACTION_PROPOSAL_TTL": 300, "PREUVE_VERSION": 1,
         "logger": types.SimpleNamespace(warning=lambda *a, **k: None, info=lambda *a, **k: None, error=lambda *a, **k: None),
         "_proposal_redis": lambda: FauxRedis(), "ActionValidationError": ValueError, "validate_inputs": lambda schema, inputs: dict(inputs),
         "_execute_catalogue_action": execute, "_log_confirmed_action": lambda *a, **k: None, "__builtins__": __builtins__}
    for n in arbre.body:  # toutes les fonctions du module, décorateurs ôtés ; celles qui dépendent de bibliothèques absentes sont ignorées
        if isinstance(n, ast.FunctionDef) and n.name not in ("_execute_catalogue_action", "_log_confirmed_action", "_proposal_redis", "validate_inputs", "_catalogue_by_key"):
            n.decorator_list = []
            try: exec(compile(ast.Module([n], []), CHEMIN, "exec", flags=__future__.annotations.compiler_flag), g)
            except Exception: pass
    action = {"key": "ventes.facture.enregistrer_paiement", "risk": "irreversible", "inputs": {}}
    g["_catalogue_by_key"] = lambda c: {action["key"]: action}
    contexte = types.SimpleNamespace(company_id=1, user_id=5)
    jeton = g["_stash_proposal"](contexte, action, {"id": 42, "montant": "5000"}, "Enregistrer 5 000 MAD")
    premiere = g["confirm_proposal"](contexte, jeton)
    if not premiere.get("ok") and not paiements: raise RuntimeError("sonde mal montée : " + str(premiere))
    return {"repro": len(paiements) == 2, "observe": {
        "methode": "rejeu (vraies confirm_proposal / _load_proposal / _discard_proposal / _stash_proposal extraites par ast, faux Redis, Django bouchonné)",
        "scenario": "2e confirmation du même jeton arrivée PENDANT l'exécution de la 1re",
        "reponse_1re": {"ok": premiere.get("ok")}, "reponse_2e": {"ok": (etat["seconde"] or {}).get("ok")},
        "paiements_crees_par_django": len(paiements), "jeton_encore_present": bool(store),
        "latent": "assistant allumé mais 0 action exécutée en prod ; même défaut pour ventes.devis.generer_facture ; délai Django 20 s non rejoué ici"}}
