# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K03 — `GET parametres/gabarits-document/<code>/rendre/?cible_id=<client>` (IsAnyRole) construit le contexte
de la fiche client (téléphone, email, adresse, ICE) via `crm.selectors.get_company_client`, borné société seul :
Commercial terrain et Admin RH (403 sur crm/clients/<id>/ = témoin écran) reçoivent le PDF. Le rendu WeasyPrint
est remplacé par un double qui renvoie le CONTEXTE reçu (la garde testée est celle de la vue). Rôles système
semés comme `init_roles`, connexion par /api/django/token/. Client de B → 404 attendu (contre-épreuve)."""
SONDE = {"constat": "C-APFS-021", "sha": "c9e72d5b2",
         "attendu": "repro si Commercial terrain / Admin RH (écran client 403) obtiennent 200 et un contexte "
                    "contenant téléphone + ICE du client de A ; client de B → 404",
         "modeles": ["authentication.CustomUser", "roles.Role", "crm.Client", "parametres.GabaritDocumentCustom"]}


def sonde(ctx):
    import json
    from unittest import mock
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from authentication.throttles import LoginRateThrottle
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES, SYSTEM_ROLE_PERIMETRES
    from apps.crm.models import Client
    from apps.parametres.models import GabaritDocumentCustom
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()

    def societe(tag):
        co = Company.objects.create(nom=f'Sonde APFS021 {tag}', slug=f'sonde-apfs021-{tag.lower()}')
        for nom, perms in CANONICAL_SYSTEM_ROLES:
            r, _ = Role.objects.get_or_create(company=co, nom=nom,
                                              defaults={'permissions': list(perms), 'est_systeme': True})
            r.permissions, r.est_systeme, r.perimetre = list(perms), True, SYSTEM_ROLE_PERIMETRES.get(nom)
            r.save()
        return co

    def compte(co, nom_role, username):
        r = Role.objects.get(company=co, nom=nom_role)
        U.objects.create_user(username=username, password='Sonde-APFS021-x9', company=co, role=r,
                              role_legacy=U.tier_for_role(r) or 'normal')
        a = APIClient()
        with mock.patch.object(LoginRateThrottle, 'allow_request', return_value=True):
            rr = a.post('/api/django/token/', {'username': username, 'password': 'Sonde-APFS021-x9'}, format='json', **H)
        assert rr.status_code == 200, (username, rr.status_code)
        return a

    A, B = societe('A'), societe('B')
    clA = Client.objects.create(company=A, nom='ClientA021', email='a021@sonde.invalid', telephone='0661021021',
                                adresse='12 rue Sonde', ice='001021021000021')
    clB = Client.objects.create(company=B, nom='ClientB021', email='b021@sonde.invalid', telephone='0661021999')
    GabaritDocumentCustom.objects.create(company=A, code='fiche-client-021', nom='Fiche client', cible='client',
                                         corps='<p>{{ nom }} {{ telephone }} {{ ice }}</p>', actif=True)

    def faux_rendu(gabarit, contexte):
        return json.dumps(contexte, default=str).encode('utf-8')

    out = {}
    for nom in ('Commercial terrain', 'Admin RH', 'Technicien', 'Commercial', 'Directeur'):
        a = compte(A, nom, 'apfs021-' + nom.lower().replace(' ', '-'))
        o = {'ecran_client': a.get(f'/api/django/crm/clients/{clA.id}/', **H).status_code}
        with mock.patch('apps.parametres.views_gabarits.rendre_pdf', side_effect=faux_rendu):
            r = a.get(f'/api/django/parametres/gabarits-document/fiche-client-021/rendre/?cible_id={clA.id}', **H)
            corps = r.content.decode('utf-8', 'replace')
            o['rendre_A'] = [r.status_code, '0661021021' in corps, '001021021000021' in corps, '12 rue Sonde' in corps]
            r = a.get(f'/api/django/parametres/gabarits-document/fiche-client-021/rendre/?cible_id={clB.id}', **H)
            o['rendre_B'] = r.status_code
        out[nom] = o
    ecarts = [n for n in ('Commercial terrain', 'Admin RH', 'Technicien')
              if out[n]['ecran_client'] in (403, 404) and out[n]['rendre_A'][0] == 200 and out[n]['rendre_A'][1]]
    out['ecarts'] = ecarts
    out['B_toujours_404'] = all(o['rendre_B'] == 404 for o in out.values() if isinstance(o, dict) and 'rendre_B' in o)
    return {'repro': bool(ecarts), 'observe': out}
