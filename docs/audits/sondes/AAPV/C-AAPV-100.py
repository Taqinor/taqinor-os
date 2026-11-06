# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K05 — la boîte d'approbations (`POST reporting/approbations-en-attente/decider/`, source `installations`)
décide une demande d'achat sur `is_responsable` brut : un Technicien ou un Commercial (rôles système, bâtis
comme `init_roles`) l'approuve ou la refuse sans `approuver_demande_achat`. Témoin : la route de la DA
`POST installations/demandes-achat/<id>/approuver/` (PeutApprouverDemandeAchat) répond 403 aux mêmes comptes."""
SONDE = {"constat": "C-AAPV-100", "sha": "c6bd9b5d52",
         "attendu": "repro si témoin approuver/ = 403 ET boîte decider = 200 avec DA approuvee/refusee par le technicien / commercial",
         "modeles": ["installations.DemandeAchat", "installations.EtapeApprobationAchat", "roles.Role",
                     "authentication.Company"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from authentication.role_tiers import tier_for_role_fields
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from apps.installations.models import DemandeAchat, DemandeAchatLigne
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    R = dict(CANONICAL_SYSTEM_ROLES)
    co = Company.objects.create(nom='Sonde AAPV 100', slug='sonde-aapv-100')

    def compte(nom):
        perms = list(R[nom])
        role, _ = Role.objects.get_or_create(company=co, nom=nom,
                                             defaults={'permissions': perms, 'est_systeme': True})
        u = U.objects.create_user(username='s100-' + nom.lower().replace(' ', '-'), password='x', company=co,
                                  role=role, role_legacy=tier_for_role_fields(nom, True, perms))
        c = APIClient()
        c.force_authenticate(u)
        return u, c

    adm, _ = compte('Administrateur')
    tech, ct = compte('Technicien')
    com, cc = compte('Commercial')

    def da(ref):
        d = DemandeAchat.objects.create(company=co, reference=ref, objet='Câbles chantier',
                                        statut=DemandeAchat.Statut.SOUMISE, created_by=adm)
        DemandeAchatLigne.objects.create(demande=d, designation='Câble 6 mm²', quantite=Decimal('100'),
                                         prix_estime=Decimal('12'))
        return d

    obs = {'perms': {'tech_a_approuver_demande_achat': 'approuver_demande_achat' in R['Technicien'],
                     'com_a_approuver_demande_achat': 'approuver_demande_achat' in R['Commercial'],
                     'tech_is_responsable': tech.is_responsable, 'com_is_responsable': com.is_responsable}}
    boite = '/api/django/reporting/approbations-en-attente/decider/'
    # Technicien — témoin route DA puis boîte
    d1 = da('DA-S100-1')
    t1 = ct.post(f'/api/django/installations/demandes-achat/{d1.id}/approuver/', {}, format='json', **H)
    b1 = ct.post(boite, {'source': 'installations', 'id': d1.id, 'decision': 'approuver'}, format='json', **H)
    d1.refresh_from_db()
    obs['technicien'] = {'temoin_approuver_http': t1.status_code, 'boite_http': b1.status_code,
                         'boite_detail': str(getattr(b1, 'data', ''))[:120], 'statut': d1.statut,
                         'approuvee_par_est_tech': d1.approuvee_par_id == tech.id}
    # Commercial — témoin route DA puis boîte (approbation) ; refus d'une seconde DA
    d2 = da('DA-S100-2')
    t2 = cc.post(f'/api/django/installations/demandes-achat/{d2.id}/approuver/', {}, format='json', **H)
    b2 = cc.post(boite, {'source': 'installations', 'id': d2.id, 'decision': 'approuver'}, format='json', **H)
    d2.refresh_from_db()
    d3 = da('DA-S100-3')
    b3 = cc.post(boite, {'source': 'installations', 'id': d3.id, 'decision': 'refuser', 'motif': 'pas utile'},
                 format='json', **H)
    d3.refresh_from_db()
    obs['commercial'] = {'temoin_approuver_http': t2.status_code, 'boite_http': b2.status_code,
                         'statut': d2.statut, 'approuvee_par_est_com': d2.approuvee_par_id == com.id,
                         'refus_boite_http': b3.status_code, 'statut_refus': d3.statut}
    print(obs)
    temoin_ok = t1.status_code == 403 and t2.status_code == 403
    defaut = (b1.status_code == 200 and obs['technicien']['statut'] == 'approuvee'
              and b2.status_code == 200 and obs['commercial']['statut'] == 'approuvee')
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
