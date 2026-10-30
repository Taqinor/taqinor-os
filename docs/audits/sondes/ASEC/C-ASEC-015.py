SONDE = {"constat": "C-ASEC-015", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : Admin RH et Technicien responsable -> 403 sur PATCH RIB/ICE du profil "
                    "société (valeurs relues inchangées, société B aussi) ; rôle sans crm_export -> export clients "
                    "xlsx 403 ; rôle sans users_gerer -> 403 droit_manquant sur POST/PATCH/DELETE /users/ ; "
                    "Directeur -> 200 sur RIB/ICE ; rôle avec crm_export -> 200 ; rôle avec users_gerer -> 200"}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.roles.models import Role
    from apps.roles import permissions_registre as reg
    from apps.parametres.models_company import CompanyProfile
    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    a = Company.objects.create(nom='Sonde ASEC015 A', slug='sonde-asec015-a')
    b = Company.objects.create(nom='Sonde ASEC015 B', slug='sonde-asec015-b')
    RIB, ICE = '011780000012345678901234', '000000000000042'
    profils = {}
    for co in (a, b):
        p = CompanyProfile.get(company=co)
        p.rib, p.ice = RIB, ICE
        p.save()
        profils[co.slug] = p

    def role(nom, perms, co=a, systeme=True):
        return Role.objects.create(company=co, nom=nom, permissions=list(perms), est_systeme=systeme)

    def user(nom, r, co=a):
        return User.objects.create_user(username=f'sonde-asec015-{nom}', password='x', company=co, role=r)

    def api_de(u):
        api = APIClient()
        api.force_authenticate(u)
        return api

    def rib_ice():
        out = []
        for p in profils.values():
            p.refresh_from_db()
            out.append([p.rib, p.ice])
        return out

    avant = rib_ice()
    obs, refus_ok = {}, True
    u_rh = user('rh', role('Admin RH', reg.ADMIN_RH_PERMISSIONS))
    u_tr = user('tr', role('Technicien responsable', reg.TECHNICIEN_RESP_PERMISSIONS))
    u_dir = user('dir', role('Directeur', reg.DIRECTEUR_PERMISSIONS), a)
    gestes = []
    for nom, u in (('Admin RH', u_rh), ('Technicien responsable', u_tr)):
        r = api_de(u).patch('/api/django/parametres/update/', {'rib': '999', 'ice': '000000000000001'},
                            format='json', **H)
        gestes.append([nom, r.status_code, str(getattr(r, 'data', ''))[:60]])
        refus_ok &= r.status_code == 403
    inchange = rib_ice() == avant
    obs['profil_refus'] = {'gestes': gestes, 'rib_ice_inchanges_A_et_B': inchange}
    refus_ok &= inchange
    r = api_de(u_dir).patch('/api/django/parametres/update/', {'rib': '011780000099999999999999'},
                            format='json', **H)
    profils['sonde-asec015-a'].refresh_from_db()
    dir_ok = r.status_code == 200 and profils['sonde-asec015-a'].rib == '011780000099999999999999'
    profils['sonde-asec015-b'].refresh_from_db()
    dir_ok &= profils['sonde-asec015-b'].rib == RIB
    obs['directeur_profil'] = {'patch': r.status_code, 'rib_A_modifie': profils['sonde-asec015-a'].rib != RIB,
                               'rib_B_inchange': profils['sonde-asec015-b'].rib == RIB}

    # export clients xlsx : rôle personnalisé SANS puis AVEC crm_export
    base = ['crm_voir', 'crm_creer', 'crm_modifier']
    u_sans = user('sansexp', role('Perso sans export', base, systeme=False))
    u_avec = user('avecexp', role('Perso avec export', base + ['crm_export'], systeme=False))
    r_sans = api_de(u_sans).post('/api/django/crm/clients/export-xlsx/', {}, format='json', **H)
    r_avec = api_de(u_avec).post('/api/django/crm/clients/export-xlsx/', {}, format='json', **H)
    obs['export_clients_xlsx'] = {'sans_crm_export': r_sans.status_code, 'avec_crm_export': r_avec.status_code}
    exp_ok = r_sans.status_code == 403 and r_avec.status_code == 200

    # users_gerer : rôle sans / avec
    cible = User.objects.create_user(username='sonde-asec015-cible', password='x', email='c@sonde.invalid',
                                     company=a, role=role('Vendeur', ['crm_voir'], systeme=False))
    u_ng = user('nogerer', role('Chef sans comptes', ['users_voir', 'crm_voir', 'crm_creer'], systeme=False))
    u_g = user('gerer', role('Chef avec comptes', ['users_voir', 'users_gerer', 'crm_voir', 'crm_creer'],
                             systeme=False))
    api = api_de(u_ng)
    rp = api.post('/api/django/users/', {'username': 'sonde-asec015-new', 'password': 'Nouveau-mdp-456!'},
                  format='json', **H)
    rpa = api.patch(f'/api/django/users/{cible.id}/', {'email': 'p@sonde.invalid'}, format='json', **H)
    rd = api.delete(f'/api/django/users/{cible.id}/', **H)
    rg = api.get('/api/django/users/', **H)
    cible = User.objects.get(pk=cible.pk)
    ug_refus = all(x.status_code == 403 and x.data.get('code') == 'droit_manquant' for x in (rp, rpa, rd)) \
        and not User.objects.filter(username='sonde-asec015-new').exists() \
        and cible.email == 'c@sonde.invalid' and cible.is_active
    rl = api_de(u_g).patch(f'/api/django/users/{cible.id}/', {'poste': 'Vendeur'}, format='json', **H)
    obs['users_gerer'] = {'sans_code_post_patch_delete': [rp.status_code, rpa.status_code, rd.status_code],
                          'lecture_sans_code': rg.status_code, 'cible_inchangee': ug_refus,
                          'avec_code_patch': rl.status_code}
    ug_ok = ug_refus and rg.status_code == 200 and rl.status_code == 200
    obs['repro'] = bool(refus_ok and dir_ok and exp_ok and ug_ok)
    return obs
