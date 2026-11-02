SONDE = {"constat": "C-ACAL-VER2-41", "sha": "56d5b623a",
         "attendu": "ACAL32 : lead raccordement='aucun', catalogue seede seul (aucun kit autonome tarife). "
                    "from-layout repond 409 (pas le 422 du texte ni de contract_samples/devis_from_layout.json) "
                    "et son corps {hors_reseau: msg} ne porte NI 'detail' NI 'errors' : le lecteur ecran "
                    "httpMessage (frontend/src/features/calepinage/atelier/contexteAtelier.js) affiche alors "
                    "'Composition invalide - verifiez le catalogue produits' au lieu du refus nomme. "
                    "Le module generer-devis, lui, rend 422."}


def sonde(ctx):
    from io import StringIO
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import AccessToken
    from apps.calepinage.models import Calepinage
    from apps.crm.models import Lead
    from apps.roles.models import Role
    from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
    from apps.ventes.domain.geometrie import layout_hash
    from authentication.models import Company
    User = get_user_model()
    co = Company.objects.create(nom='SONDE ACAL VER2-41', slug='sonde-acal-ver2-41')
    call_command('seed_catalogue', company_slug=co.slug, stdout=StringIO())
    role = Role.objects.create(company=co, nom='Directeur', permissions=list(DIRECTEUR_PERMISSIONS))
    u = User.objects.create_user(username='sonde_acal_ver2_41', password='x', company=co,
                                 role=role, role_legacy='responsable')
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(u))
    layout = {'scenario': 'reseau', 'panelWatt': 710,
              'result': {'panels': 10, 'kwc': 7.1, 'annualKwh': 12000, 'savings': 10000}}
    lead1 = Lead.objects.create(company=co, nom='Sonde', prenom='Isole1',
                                email='ver2-41-a@example.test', raccordement='aucun')
    lead2 = Lead.objects.create(company=co, nom='Sonde', prenom='Isole2',
                                email='ver2-41-b@example.test', raccordement='aucun')
    r_fl = api.post('/api/django/ventes/devis/from-layout/', {'layout': dict(layout), 'lead': lead1.pk},
                    format='json')
    cal = Calepinage.objects.create(company=co, lead_id=lead2.pk, titre='Sonde', roof_layout=dict(layout),
                                    layout_hash=layout_hash(layout))
    r_mod = api.post('/api/django/calepinage/calepinages/%s/generer-devis/' % cal.pk, {}, format='json')
    corps_fl = getattr(r_fl, 'data', None)
    corps_mod = getattr(r_mod, 'data', None)
    print('from-layout', r_fl.status_code, corps_fl)
    print('module', r_mod.status_code, corps_mod)
    sans_detail = isinstance(corps_fl, dict) and 'hors_reseau' in corps_fl \
        and not corps_fl.get('detail') and not corps_fl.get('errors')
    return {'repro': r_fl.status_code != 422 or sans_detail,
            'from_layout': [r_fl.status_code, corps_fl], 'module': [r_mod.status_code, corps_mod],
            'statuts_divergent': r_fl.status_code != r_mod.status_code,
            'ecran_lit_generique': sans_detail}
