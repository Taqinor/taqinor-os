# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K22 — oracle d'existence inter-sociétés : des validateurs `validate_<champ>` écrits à la main répondent
DIFFÉREMMENT à un id d'une autre société et à un id absent (statut et/ou corps), alors que la règle ACAL298 /
`IdInconnu404Mixin` veut une réponse identique. Trois sites, un compte Administrateur de A (rôle système) :
(1) PATCH ventes/devis/<id A>/ {tiers_payeur} ; (2) POST sav/categories-equipement/ {responsable} ;
(3) PATCH uxviews/parametres/ {roles_autorises_definir_defaut}. Témoin : `client` (dans same_company_fields)."""
SONDE = {"constat": "C-APFS-062", "sha": "c9e72d5b20",
         "attendu": "repro si sur au moins un site (statut, corps) diffère entre id de B et id absent, alors que le "
                    "témoin `client` répond à l'identique",
         "modeles": ["ventes.Devis", "crm.Client", "sav.CategorieEquipement", "roles.Role", "authentication.Company"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import AccessToken
    from authentication.models import Company
    from authentication.role_tiers import tier_for_role_fields
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from apps.crm.models import Client
    from apps.ventes.models import Devis
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    R = dict(CANONICAL_SYSTEM_ROLES)
    coA = Company.objects.create(nom='Sonde APFS 062 A', slug='sonde-apfs-062-a')
    coB = Company.objects.create(nom='Sonde APFS 062 B', slug='sonde-apfs-062-b')

    def compte(co, nom, suffixe):
        perms = list(R[nom])
        role, _ = Role.objects.get_or_create(company=co, nom=nom,
                                             defaults={'permissions': perms, 'est_systeme': True})
        return U.objects.create_user(username='apfs062-' + suffixe, password='x', company=co, role=role,
                                     role_legacy=tier_for_role_fields(nom, True, perms))

    admA = compte(coA, 'Administrateur', 'adm-a')
    admB = compte(coB, 'Administrateur', 'adm-b')
    roleB = Role.objects.get(company=coB, nom='Administrateur')
    c = APIClient()
    c.cookies['access_token'] = str(AccessToken.for_user(admA))
    clA = Client.objects.create(company=coA, nom='Client', prenom='A062', email='a062@example.invalid')
    clB = Client.objects.create(company=coB, nom='Client', prenom='B062', email='b062@example.invalid')
    dv = Devis.objects.create(company=coA, reference='DEV-APFS-062', client=clA, statut=Devis.Statut.BROUILLON)
    ABSENT = 2147480000

    def rep(r):
        try:
            corps = r.json()
        except Exception:  # noqa
            corps = str(r.content)[:200]
        return {'http': r.status_code, 'corps': corps}

    import re

    def norme(x):
        # l'écho de l'id et le request_id diffèrent par construction : on compare statut + gabarit du corps
        corps = x['corps']
        if isinstance(corps, dict):
            corps = {k: v for k, v in corps.items() if k != 'error'}
        return (x['http'], re.sub(r'\d+', 'N', str(corps)))

    def paire(appel):
        b, a = rep(appel('B')), rep(appel('ABSENT'))
        return {'id_B': b, 'id_absent': a, 'identiques': norme(b) == norme(a)}

    obs = {}
    obs['temoin_client_devis'] = paire(lambda k: c.patch(
        f'/api/django/ventes/devis/{dv.id}/', {'client': clB.id if k == 'B' else ABSENT}, format='json', **H))
    obs['site1_devis_tiers_payeur'] = paire(lambda k: c.patch(
        f'/api/django/ventes/devis/{dv.id}/', {'tiers_payeur': clB.id if k == 'B' else ABSENT}, format='json', **H))
    obs['site2_sav_categorie_responsable'] = paire(lambda k: c.post(
        '/api/django/sav/categories-equipement/', {'nom': 'Cat 062 ' + k, 'responsable': admB.id if k == 'B' else ABSENT},
        format='json', **H))
    obs['site3_ux_roles_autorises'] = paire(lambda k: c.patch(
        '/api/django/uxviews/parametres/', {'roles_autorises_definir_defaut': [roleB.id if k == 'B' else ABSENT]},
        format='json', **H))
    print(obs)
    sites = [obs[k]['identiques'] for k in obs if k.startswith('site')]
    obs['sites_differents'] = [k for k in obs if k.startswith('site') and not obs[k]['identiques']]
    obs['repro'] = bool(obs['temoin_client_devis']['identiques'] and not all(sites))
    return obs
