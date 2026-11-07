# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K09 — `RegleApprobationAchatViewSet.get_permissions` : écriture = `IsResponsableOrAdmin`, franchi par
`installation_gerer` du Technicien. Un Technicien (rôle système) PATCHe la règle « > 20 000 : 2 approbateurs,
sans dérogation » (`autorise_depassement_budget: true`, `nombre_approbateurs: 1`, puis `actif: false`) et en
crée une nouvelle ; effet : la DA suivante de 60 000 soumise ne reçoit AUCUNE étape. Témoin : le jumeau
`SeuilApprobationBCFViewSet` (écriture `IsAdminRole`) refuse le même Technicien (403)."""
SONDE = {"constat": "C-AAPV-104", "sha": "c6bd9b5d52",
         "attendu": "repro si PATCH/POST règle = 200/201 par le technicien, règle désactivée, DA 60 000 sans étape ; témoin seuil BCF 403",
         "modeles": ["installations.DemandeAchat", "installations.EtapeApprobationAchat",
                     "installations.RegleApprobationAchat", "installations.SeuilApprobationBCF", "roles.Role",
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
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    R = dict(CANONICAL_SYSTEM_ROLES)
    co = Company.objects.create(nom='Sonde AAPV 104', slug='sonde-aapv-104')

    def compte(nom):
        perms = list(R[nom])
        role, _ = Role.objects.get_or_create(company=co, nom=nom,
                                             defaults={'permissions': perms, 'est_systeme': True})
        u = U.objects.create_user(username='s104-' + nom.lower().replace(' ', '-'), password='x', company=co,
                                  role=role, role_legacy=tier_for_role_fields(nom, True, perms))
        c = APIClient()
        c.force_authenticate(u)
        return u, c

    adm, ca = compte('Administrateur')
    tech, ct = compte('Technicien')
    com, cc = compte('Commercial')
    regle = RegleApprobationAchat.objects.create(company=co, libelle='> 20 000 : 2 approbateurs',
                                                 montant_min=Decimal('20000'), nombre_approbateurs=2,
                                                 autorise_depassement_budget=False, actif=True)
    url = f'/api/django/installations/regles-approbation-achat/{regle.id}/'
    p1 = ct.patch(url, {'autorise_depassement_budget': True, 'nombre_approbateurs': 1}, format='json', **H)
    regle.refresh_from_db()
    apres_p1 = {'autorise_depassement_budget': regle.autorise_depassement_budget,
                'nombre_approbateurs': regle.nombre_approbateurs}
    p2 = ct.patch(url, {'actif': False}, format='json', **H)
    regle.refresh_from_db()
    cr = ct.post('/api/django/installations/regles-approbation-achat/',
                 {'libelle': 'règle du technicien', 'montant_min': '999999999', 'nombre_approbateurs': 1},
                 format='json', **H)
    pc = cc.patch(url, {'actif': True}, format='json', **H)
    # témoin jumeau : seuil d'approbation BCF (écriture IsAdminRole)
    ts = ct.post('/api/django/installations/seuils-approbation-bcf/', {'seuil_responsable': '50000'}, format='json', **H)
    # effet : DA de 60 000 soumise par l'admin
    d = DemandeAchat.objects.create(company=co, reference='DA-S104', objet='Structures', created_by=adm)
    DemandeAchatLigne.objects.create(demande=d, designation='Structure', quantite=Decimal('6'),
                                     prix_estime=Decimal('10000'))
    s = ca.post(f'/api/django/installations/demandes-achat/{d.id}/soumettre/', {}, format='json', **H)
    d.refresh_from_db()
    obs = {'tech_patch_derogation_http': p1.status_code, 'apres_patch_1': apres_p1,
           'tech_patch_actif_http': p2.status_code, 'regle_actif': regle.actif,
           'tech_create_regle_http': cr.status_code, 'commercial_patch_http': pc.status_code,
           'temoin_seuil_bcf_tech_http': ts.status_code,
           'da_soumettre_http': s.status_code, 'da_statut': d.statut, 'da_etapes': d.etapes_approbation.count(),
           'da_montant': str(d.montant_estime)}
    print(obs)
    temoin_ok = ts.status_code == 403
    defaut = p1.status_code == 200 and p2.status_code == 200 and regle.actif is False and obs['da_etapes'] == 0
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
