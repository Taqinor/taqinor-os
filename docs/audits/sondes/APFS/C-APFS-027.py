# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K66 — boîte d'approbations `GET reporting/approbations-en-attente/?source=installations` (IsAnyRole) sert
`montant` = `DemandeAchat.montant_estime` (Σ quantité × prix d'achat estimé) à tout rôle, alors que la fiche de la
demande (`installations/demandes-achat/<id>/`, `_retirer_estimations_achat`, ACHT16 / D-ASTK-2) retire
`montant_estime`/`total_estime` sans `prix_achat_voir`. Technicien, Technicien responsable, Commercial, Admin RH vs
Directeur (témoin). Rôles système semés comme `init_roles`, connexion /api/django/token/. DA de B absente."""
SONDE = {"constat": "C-APFS-027", "sha": "c9e72d5b2",
         "attendu": "repro si un rôle sans prix_achat_voir reçoit montant = 7500.00 dans la boîte alors que la fiche DA "
                    "ne lui sert pas montant_estime ; Directeur : montant présent ; DA de B absente",
         "modeles": ["authentication.CustomUser", "roles.Role", "installations.DemandeAchat",
                     "installations.DemandeAchatLigne"]}


def sonde(ctx):
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from authentication.throttles import LoginRateThrottle
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES, SYSTEM_ROLE_PERIMETRES
    from apps.installations.models_demande_achat import DemandeAchat, DemandeAchatLigne
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()

    def societe(tag):
        co = Company.objects.create(nom=f'Sonde APFS027 {tag}', slug=f'sonde-apfs027-{tag.lower()}')
        for nom, perms in CANONICAL_SYSTEM_ROLES:
            r, _ = Role.objects.get_or_create(company=co, nom=nom,
                                              defaults={'permissions': list(perms), 'est_systeme': True})
            r.permissions, r.est_systeme, r.perimetre = list(perms), True, SYSTEM_ROLE_PERIMETRES.get(nom)
            r.save()
        return co

    def compte(co, nom_role, username):
        r = Role.objects.get(company=co, nom=nom_role)
        u = U.objects.create_user(username=username, password='Sonde-APFS027-x9', company=co, role=r,
                                  role_legacy=U.tier_for_role(r) or 'normal')
        a = APIClient()
        with mock.patch.object(LoginRateThrottle, 'allow_request', return_value=True):
            rr = a.post('/api/django/token/', {'username': username, 'password': 'Sonde-APFS027-x9'}, format='json', **H)
        assert rr.status_code == 200, (username, rr.status_code)
        return u, a

    A, B = societe('A'), societe('B')
    das = {}
    for co, tag in ((A, 'A'), (B, 'B')):
        da = DemandeAchat.objects.create(company=co, reference=f'DA-APFS027-{tag}', objet='Panneaux', statut='soumise')
        DemandeAchatLigne.objects.create(demande=da, designation='Panneau 550 W', quantite=Decimal('10'),
                                         prix_estime=Decimal('750'))
        das[tag] = da
    out = {}
    for nom, role in (('tech', 'Technicien'), ('tech_resp', 'Technicien responsable'), ('commercial', 'Commercial'),
                      ('rh', 'Admin RH'), ('directeur', 'Directeur')):
        u, a = compte(A, role, f'apfs027-{nom}')
        r = a.get(f"/api/django/installations/demandes-achat/{das['A'].id}/", **H)
        fiche = r.json() if r.status_code == 200 else {}
        o = {'prix_achat_voir': bool(u.can_view_buy_prices),
             'fiche_da': [r.status_code, 'montant_estime' in fiche and fiche.get('montant_estime') is not None]}
        r = a.get('/api/django/reporting/approbations-en-attente/?source=installations', **H)
        d = r.json() if r.status_code == 200 else {}
        items = d.get('items', d.get('results', d)) if isinstance(d, dict) else d
        items = items if isinstance(items, list) else []
        it = next((x for x in items if x.get('source') == 'installations' and x.get('id') == das['A'].id), None)
        o['boite'] = [r.status_code, it is not None, (it or {}).get('montant'),
                      any(x.get('id') == das['B'].id and x.get('source') == 'installations' for x in items)]
        r = a.get('/api/django/reporting/approbations-en-attente/?source=installations&trier=montant', **H)
        o['tri_montant'] = r.status_code
        out[nom] = o
    ecarts = [n for n in ('tech', 'tech_resp', 'commercial', 'rh')
              if not out[n]['prix_achat_voir'] and out[n]['boite'][1] and out[n]['boite'][2] not in (None, '')]
    out['ecarts'] = ecarts
    out['temoin_directeur'] = out['directeur']['boite'][2]
    out['fuite_B'] = any(o['boite'][3] for o in out.values() if isinstance(o, dict) and 'boite' in o)
    return {'repro': bool(ecarts), 'observe': out}
