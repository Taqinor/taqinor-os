# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K08 — `sod_stricte` (« le créateur ne peut pas approuver sa propre demande ») n'est appliquée que par
`_decider_etape_approbation_achat` (plan d'étapes). Société `AchatsParametres.sod_stricte=True`, aucune règle
d'approbation : l'Administrateur crée sa DA, la soumet (vraie route) et l'approuve lui-même par
`demandes-achat/<id>/approuver/` puis, sur une 2e DA, par la boîte `reporting/approbations-en-attente/decider/`.
Témoin : sous une règle 1 étape, le même créateur sur `approuver-etape` = 409 « Séparation des tâches »."""
SONDE = {"constat": "C-AAPV-103", "sha": "c6bd9b5d52",
         "attendu": "repro si témoin approuver-etape 409 SoD ET approuver/ + boîte = 200 approuvee par le créateur",
         "modeles": ["installations.DemandeAchat", "installations.EtapeApprobationAchat",
                     "installations.RegleApprobationAchat", "stock.AchatsParametres", "roles.Role",
                     "authentication.Company"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from authentication.role_tiers import tier_for_role_fields
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from apps.installations.models import DemandeAchat, DemandeAchatLigne, RegleApprobationAchat
    from apps.stock.models import AchatsParametres
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    R = dict(CANONICAL_SYSTEM_ROLES)
    co = Company.objects.create(nom='Sonde AAPV 103', slug='sonde-aapv-103')
    perms = list(R['Administrateur'])
    role, _ = Role.objects.get_or_create(company=co, nom='Administrateur',
                                         defaults={'permissions': perms, 'est_systeme': True})
    adm = U.objects.create_user(username='s103-admin', password='x', company=co, role=role,
                                role_legacy=tier_for_role_fields('Administrateur', True, perms))
    ca = APIClient()
    ca.force_authenticate(adm)
    p = AchatsParametres.for_company(co)
    p.sod_stricte = True
    p.save()
    base = '/api/django/installations/demandes-achat/'

    def da(ref):
        d = DemandeAchat.objects.create(company=co, reference=ref, objet='Rails', created_by=adm)
        DemandeAchatLigne.objects.create(demande=d, designation='Rail alu', quantite=Decimal('10'),
                                         prix_estime=Decimal('300'))
        return d

    obs = {'sod_stricte': AchatsParametres.for_company(co).sod_stricte}
    d1 = da('DA-S103-1')
    s1 = ca.post(f'{base}{d1.id}/soumettre/', {}, format='json', **H)
    a1 = ca.post(f'{base}{d1.id}/approuver/', {}, format='json', **H)
    d1.refresh_from_db()
    d2 = da('DA-S103-2')
    s2 = ca.post(f'{base}{d2.id}/soumettre/', {}, format='json', **H)
    b2 = ca.post('/api/django/reporting/approbations-en-attente/decider/',
                 {'source': 'installations', 'id': d2.id, 'decision': 'approuver'}, format='json', **H)
    d2.refresh_from_db()
    obs['sans_regle'] = {'soumettre': [s1.status_code, s2.status_code],
                         'etapes': [d1.etapes_approbation.count(), d2.etapes_approbation.count()],
                         'approuver_http': a1.status_code, 'statut_1': d1.statut,
                         'approuvee_par_createur_1': d1.approuvee_par_id == d1.created_by_id == adm.id,
                         'boite_http': b2.status_code, 'statut_2': d2.statut,
                         'approuvee_par_createur_2': d2.approuvee_par_id == d2.created_by_id == adm.id}
    # témoin : règle 1 étape → approuver-etape par le créateur
    RegleApprobationAchat.objects.create(company=co, libelle='1 approbateur', montant_min=Decimal('0'),
                                         nombre_approbateurs=1, actif=True)
    d3 = da('DA-S103-3')
    s3 = ca.post(f'{base}{d3.id}/soumettre/', {}, format='json', **H)
    e3 = ca.post(f'{base}{d3.id}/approuver-etape/', {}, format='json', **H)
    d3.refresh_from_db()
    obs['temoin_plan'] = {'soumettre': s3.status_code, 'etapes': d3.etapes_approbation.count(),
                          'approuver_etape_http': e3.status_code,
                          'detail': str(getattr(e3, 'data', ''))[:120], 'statut': d3.statut}
    print(obs)
    temoin_ok = e3.status_code == 409 and d3.statut == 'soumise'
    defaut = (a1.status_code == 200 and d1.statut == 'approuvee' and b2.status_code == 200 and d2.statut == 'approuvee')
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
