# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K07 — plan d'approbation multi-étapes : `_decider_etape_approbation_achat` ne lit jamais
`EtapeApprobationAchat.niveau_approbation` et n'exige pas d'approbateurs distincts. Règle « > 50 000 :
Direction, 3 approbateurs » ; DA 80 000 soumise par l'Admin (vraie route) ; UN SEUL compte au rôle système
« Responsable » auquel l'admin a coché `approuver_demande_achat` dans la grille (pas Direction) appelle
`approuver-etape` trois fois. Attendu sain : refus au palier (Direction) et/ou 3 personnes distinctes."""
SONDE = {"constat": "C-AAPV-102", "sha": "c6bd9b5d52",
         "attendu": "repro si 3 × 200, DA approuvee, 3 étapes au même approbateur (niveau direction)",
         "modeles": ["installations.DemandeAchat", "installations.EtapeApprobationAchat",
                     "installations.RegleApprobationAchat", "roles.Role", "authentication.Company"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from authentication.role_tiers import tier_for_role_fields
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from apps.installations.models import DemandeAchat, DemandeAchatLigne, RegleApprobationAchat
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    R = dict(CANONICAL_SYSTEM_ROLES)
    co = Company.objects.create(nom='Sonde AAPV 102', slug='sonde-aapv-102')

    def compte(nom, extra=()):
        perms = list(R[nom]) + list(extra)
        role, _ = Role.objects.get_or_create(company=co, nom=nom,
                                             defaults={'permissions': perms, 'est_systeme': True})
        u = U.objects.create_user(username='s102-' + nom.lower().replace(' ', '-'), password='x', company=co,
                                  role=role, role_legacy=tier_for_role_fields(nom, True, perms))
        c = APIClient()
        c.force_authenticate(u)
        return u, c

    adm, ca = compte('Administrateur')
    resp, cr = compte('Responsable', extra=['approuver_demande_achat'])
    regle = RegleApprobationAchat.objects.create(
        company=co, libelle='> 50 000 : Direction, 3 approbateurs', montant_min=Decimal('50000'),
        niveau_approbation=RegleApprobationAchat.NiveauApprobation.DIRECTION, nombre_approbateurs=3, actif=True)
    d = DemandeAchat.objects.create(company=co, reference='DA-S102', objet='Batteries', created_by=adm)
    DemandeAchatLigne.objects.create(demande=d, designation='Batterie 10 kWh', quantite=Decimal('4'),
                                     prix_estime=Decimal('20000'))
    base = '/api/django/installations/demandes-achat/'
    s = ca.post(f'{base}{d.id}/soumettre/', {}, format='json', **H)
    codes = [cr.post(f'{base}{d.id}/approuver-etape/', {}, format='json', **H).status_code for _ in range(3)]
    d.refresh_from_db()
    etapes = list(d.etapes_approbation.order_by('niveau').values('niveau', 'niveau_approbation', 'statut',
                                                                  'approbateur_id'))
    obs = {'montant_estime': str(d.montant_estime), 'soumettre_http': s.status_code,
           'resp_is_admin_role': resp.is_admin_role, 'resp_role_legacy': resp.role_legacy,
           'approuver_etape_http': codes, 'statut': d.statut, 'etapes': etapes,
           'approbateurs_distincts': len({e['approbateur_id'] for e in etapes}),
           'approbateur_est_resp': all(e['approbateur_id'] == resp.id for e in etapes)}
    print(obs)
    temoin_ok = s.status_code == 200 and len(etapes) == 3 and all(e['niveau_approbation'] == 'direction' for e in etapes)
    defaut = codes == [200, 200, 200] and d.statut == 'approuvee' and obs['approbateurs_distincts'] == 1 \
        and not resp.is_admin_role
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
