SONDE = {"constat": "C-ASEC-001", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : Commercial responsable, Technicien responsable et Admin RH -> 403 sur "
                    "le Directeur protégé (email, is_active, role, must_change_password, avatar) et sur un rôle "
                    "plus large auto-attribué ; cible d'un autre locataire -> 403/404 ; Directeur relu inchangé ; "
                    "Directeur sur un Commercial -> 200"}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from django.core.files.uploadedfile import SimpleUploadedFile
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.roles.models import Role
    from apps.roles import permissions_registre as reg
    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}

    def societe(tag):
        co = Company.objects.create(nom=f'Sonde ASEC001 {tag}', slug=f'sonde-asec001-{tag}')
        roles = {nom: Role.objects.create(company=co, nom=nom, permissions=list(p), est_systeme=True)
                 for nom, p in (('Directeur', reg.DIRECTEUR_PERMISSIONS),
                                ('Commercial responsable', reg.COMMERCIAL_RESP_PERMISSIONS),
                                ('Technicien responsable', reg.TECHNICIEN_RESP_PERMISSIONS),
                                ('Admin RH', reg.ADMIN_RH_PERMISSIONS), ('Commercial', reg.COMMERCIAL_PERMISSIONS))}
        return co, roles

    def user(co, nom, role, **kw):
        return User.objects.create_user(username=f'sonde-asec001-{nom}', password='Ancien-mdp-123',
                                        email=f'{nom}@sonde.invalid', company=co, role=role, **kw)

    def code(r):
        return r.data.get('code') if isinstance(getattr(r, 'data', None), dict) else None

    a, ra = societe('a')
    b, rb = societe('b')
    directeur = user(a, 'dir', ra['Directeur'], is_protected=True)
    com = user(a, 'com', ra['Commercial'])
    responsables = [user(a, 'cresp', ra['Commercial responsable']), user(a, 'tresp', ra['Technicien responsable']),
                    user(a, 'rh', ra['Admin RH'])]
    dir_b = user(b, 'dirb', rb['Directeur'], is_protected=True)

    def etat(u):
        u = User.objects.get(pk=u.pk)
        return (u.check_password('Ancien-mdp-123'), u.is_active, u.email, u.role_id, u.avatar_key,
                u.must_change_password)

    avant, avant_b = etat(directeur), etat(dir_b)
    gestes, refus_ok, roles_ok, autre_ok = [], True, True, True
    for acteur in responsables:
        nom = acteur.username.replace('sonde-asec001-', '')
        api = APIClient()
        api.force_authenticate(acteur)
        for corps in ({'email': 'pirate@sonde.invalid'}, {'is_active': False}, {'role': ra['Commercial'].id},
                      {'must_change_password': True}):
            r = api.patch(f'/api/django/users/{directeur.id}/', corps, format='json', **H)
            gestes.append([nom, list(corps)[0], r.status_code, code(r)])
            refus_ok &= r.status_code == 403
        r = api.post(f'/api/django/users/{directeur.id}/avatar/',
                     {'file': SimpleUploadedFile('a.png', b'\x89PNG\r\n\x1a\n' + b'\x00' * 40, 'image/png')},
                     format='multipart', **H)
        gestes.append([nom, 'avatar', r.status_code, code(r)])
        refus_ok &= r.status_code == 403
        # rôle STRICTEMENT plus large que le sien : union des trois paliers « responsable »
        union = set(reg.COMMERCIAL_RESP_PERMISSIONS) | set(reg.TECHNICIEN_RESP_PERMISSIONS) | set(
            reg.ADMIN_RH_PERMISSIONS) | set(acteur.role.permissions)
        ajoutes = sorted(union - set(acteur.role.permissions))
        large = Role.objects.create(company=a, nom=f'Perso large {acteur.id}', permissions=sorted(union))
        role_avant = acteur.role_id
        r = api.patch(f'/api/django/users/{acteur.id}/', {'role': large.id}, format='json', **H)
        acteur.refresh_from_db()
        gestes.append([nom, 'role_plus_large', r.status_code, code(r), len(ajoutes)])
        roles_ok &= r.status_code in (400, 403) and acteur.role_id == role_avant
        r = api.patch(f'/api/django/users/{dir_b.id}/', {'email': 'x@sonde.invalid'}, format='json', **H)
        gestes.append([nom, 'autre_societe', r.status_code])
        autre_ok &= r.status_code in (403, 404)
    api = APIClient()
    api.force_authenticate(directeur)
    leg = api.patch(f'/api/django/users/{com.id}/', {'poste': 'Vendeur'}, format='json', **H)
    out = {'gestes': gestes, 'directeur_inchange': etat(directeur) == avant,
           'directeur_b_inchange': etat(dir_b) == avant_b, 'legitime_directeur_sur_commercial': leg.status_code}
    out['repro'] = bool(refus_ok and roles_ok and autre_ok and out['directeur_inchange']
                        and out['directeur_b_inchange'] and leg.status_code == 200)
    return out
