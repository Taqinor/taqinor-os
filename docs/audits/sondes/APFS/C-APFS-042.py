# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K68 — loi 09-08 : `core/dsr-requests/` (`IsAdminOrResponsableTier` SEUL) + `…/<id>/traiter/` laissent tout le
palier « responsable » exporter TOUTES les PII d'une personne (`kind=acces`, résultat stocké et servi) et l'EFFACER
(`kind=effacement` : client et leads anonymisés, irréversible) sans aucun code CRM ni `client_pii_voir`.
Par rôle système (JWT réel) dans A : accès sur le sujet commun, puis effacement d'un sujet propre au rôle.
Société B : un client et un lead au MÊME e-mail ne bougent jamais."""
SONDE = {"constat": "C-APFS-042", "sha": "57d3fd371d",
         "attendu": "repro si Admin RH et Technicien responsable (sans code CRM ni client_pii_voir) obtiennent 201 + "
                    "200 traiter, le téléphone du client dans `resultat` (accès) et leur sujet anonymisé "
                    "(effacement) ; Commercial 403 ; sujet de B intact",
         "modeles": ["core.DataSubjectRequest", "crm.Client", "crm.Lead", "roles.Role", "authentication.Company"]}


def sonde(ctx):
    import json
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import AccessToken
    from authentication.models import Company
    from authentication.role_tiers import tier_for_role_fields
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from apps.crm.models import Client, Lead
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    R = dict(CANONICAL_SYSTEM_ROLES)
    coA = Company.objects.create(nom='Sonde APFS 042 A', slug='sonde-apfs-042-a')
    coB = Company.objects.create(nom='Sonde APFS 042 B', slug='sonde-apfs-042-b')

    def compte(co, nom, suffixe):
        perms = list(R[nom])
        role, _ = Role.objects.get_or_create(company=co, nom=nom,
                                             defaults={'permissions': perms, 'est_systeme': True})
        u = U.objects.create_user(username=f's042{suffixe}-' + nom.lower().replace(' ', '-'), password='x',
                                  company=co, role=role, role_legacy=tier_for_role_fields(nom, True, perms))
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(AccessToken.for_user(u)))
        return u, c

    def sujet(co, tag, tel):
        email = f'sujet-{tag}@example.invalid'
        cl = Client.objects.create(company=co, nom='Bennani', prenom=f'Sujet {tag}', email=email, telephone=tel)
        le = Lead.objects.create(company=co, nom=f'Bennani {tag}', email=email, telephone=tel)
        return email, cl, le

    noms = ['Directeur', 'Admin RH', 'Technicien responsable', 'Admin Ventes', 'Commercial']
    comptes = {n: compte(coA, n, 'a') for n in noms}
    email_commun, clA, leA = sujet(coA, 'commun', '0612345601')
    _, clB, leB = sujet(coB, 'commun', '0612345601')
    obs = {'roles': {}}
    for i, nom in enumerate(noms):
        u, c = comptes[nom]
        p = set(R[nom])
        r = {'menu_tier': u.menu_tier, 'client_pii_voir': 'client_pii_voir' in p,
             'codes_crm': sorted(x for x in p if x.startswith('crm_'))[:3]}
        a = c.post('/api/django/core/dsr-requests/', {'subject_identifier': email_commun, 'kind': 'acces'},
                   format='json', **H)
        r['acces_creer_http'] = a.status_code
        if a.status_code == 201:
            t = c.post(f"/api/django/core/dsr-requests/{a.data['id']}/traiter/", {}, format='json', **H)
            r['acces_traiter_http'] = t.status_code
            brut = json.dumps((t.data or {}).get('resultat'), default=str) if t.status_code == 200 else ''
            r['acces_resultat_contient_tel'] = '0612345601' in brut
            r['acces_resultat_extrait'] = brut[:160]
        email_x, clx, lex = sujet(coA, f'r{i}', f'06123456{10 + i}')
        e = c.post('/api/django/core/dsr-requests/', {'subject_identifier': email_x, 'kind': 'effacement'},
                   format='json', **H)
        r['effacement_creer_http'] = e.status_code
        if e.status_code == 201:
            t = c.post(f"/api/django/core/dsr-requests/{e.data['id']}/traiter/", {}, format='json', **H)
            r['effacement_traiter_http'] = t.status_code
            r['effacement_detail'] = None if t.status_code == 200 else str(getattr(t, 'data', ''))[:120]
        clx.refresh_from_db()
        lex = Lead.all_objects.get(pk=lex.pk)
        r['sujet_efface'] = {'client_email': clx.email, 'client_tel': clx.telephone,
                             'client_anonymise': getattr(clx, 'is_anonymized', None), 'lead_nom': lex.nom,
                             'lead_tel': lex.telephone}
        obs['roles'][nom] = r
    clB.refresh_from_db()
    leB = Lead.all_objects.get(pk=leB.pk)
    obs['B_intact'] = (clB.email == email_commun and clB.telephone == '0612345601'
                       and leB.telephone == '0612345601' and leB.nom == 'Bennani commun')
    print(obs)
    ro = obs['roles']

    def efface(nom):
        x = ro[nom]
        return (x['effacement_creer_http'] == 201 and x.get('effacement_traiter_http') == 200
                and not x['sujet_efface']['client_tel'] and not x['sujet_efface']['lead_tel'])

    def exporte(nom):
        x = ro[nom]
        return x['acces_creer_http'] == 201 and x.get('acces_traiter_http') == 200 and x.get('acces_resultat_contient_tel')
    temoin_ok = (ro['Commercial']['acces_creer_http'] == 403 and ro['Commercial']['effacement_creer_http'] == 403
                 and efface('Directeur') and obs['B_intact'])
    obs['temoin_ok'] = temoin_ok
    obs['effacent'] = [n for n in noms if efface(n)]
    obs['exportent'] = [n for n in noms if exporte(n)]
    obs['repro'] = bool(temoin_ok and efface('Admin RH') and efface('Technicien responsable')
                        and exporte('Admin RH') and exporte('Technicien responsable'))
    return obs
