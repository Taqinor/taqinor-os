"""QA-COHERENCE — sécurité : comptes de démonstration à mot de passe PUBLIÉ.

Incident du 30/09/2026 (premier passage de l'auditeur sur la prod) :
``demo_admin`` (rôle administrateur) et ``demo_resp``, créés par
``seed_demo`` le 10/06, étaient ACTIFS en production dans la société réelle,
alors que leur mot de passe est écrit en clair dans le dépôt PUBLIC
(``seed_demo.py``, ``frontend/e2e/helpers.js``). Désactivés le 30/09 sur
accord du fondateur ; cette règle le signale chaque nuit s'il se reproduit.

ASEC25 (C-ASEC-021, aggravé par C-ASEC-029 : la prod a tourné en DEBUG) :
la règle tourne QUEL QUE SOIT ``settings.DEBUG`` — l'ancien retour anticipé
sous DEBUG la rendait muette précisément là où elle devait parler. Le critère
est la société, jamais DEBUG ni le slug (même critère que la garde des
commandes démo, ASEC16) :
- société ``est_demo=True`` : tout compte ACTIF est un compte de démonstration
  (créé par une commande de seed, mot de passe publié) → violation ;
- société réelle : seuls les comptes de seed connus (``COMPTES_SEED``) actifs
  lèvent la violation (incident du 30/09) ; ses vrais comptes, jamais.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model

from .registre import GRAVITE_CRITIQUE, PORTEE_SOCIETE, regle

# Comptes créés avec un mot de passe LITTÉRAL par une commande du dépôt :
# seed_demo (demo_admin, demo_resp, demo_portail), seed_demo_company
# (demo_admin_full, demo_resp_full), qa_import_anonymise (anon_admin). Toute
# nouvelle commande de seed qui crée un compte à mot de passe connu l'ajoute ici.
COMPTES_SEED = ('demo_admin', 'demo_resp', 'demo_portail', 'demo_admin_full',
                'demo_resp_full', 'anon_admin')


@regle('SEC_COMPTE_DEMO_ACTIF',
       "Compte de démonstration (mot de passe publié dans le dépôt) actif "
       "en production",
       gravite=GRAVITE_CRITIQUE, portee=PORTEE_SOCIETE)
def compte_demo_actif(r, company, ctx):
    comptes = get_user_model().objects.filter(company=company, is_active=True)
    if not getattr(company, 'est_demo', False):
        comptes = comptes.filter(username__in=COMPTES_SEED)
    comptes = comptes.order_by('username')
    return [r.violation(
        None, f"Le compte « {u.username} » est actif alors que son mot de "
              "passe est publié dans le dépôt (commande de seed).",
        object_type='utilisateur', object_id=u.pk, reference=u.username,
        company_id=company.pk,
        valeurs={'username': u.username,
                 'derniere_connexion': (u.last_login.date().isoformat()
                                        if u.last_login else None)},
        attendu='compte désactivé')
        for u in comptes]
