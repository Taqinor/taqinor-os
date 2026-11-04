# flake8: noqa  (sonde de contre-visite « vérifie ADOC » 04/11, rejouable par scripts/sonde.py)
"""ADOC69 (jumeau) : `documents/views.py::_get_chantier_or_404` borne les documents de chantier par
`CHANTIER_OWNER_FIELDS` (technicien_responsable, created_by). Depuis ERR-CHT-TECH-CHANTIER-404 (29/10),
`InstallationViewSet.get_queryset` ouvre AUSSI la fiche (retrieve) au technicien d'une intervention du
chantier. Le technicien assigné voit donc la fiche (200) mais reçoit 404 sur PV / BL / dossier de remise :
la règle « les documents suivent la portée de la fiche » d'ADOC69 a divergé. Chaîne API réelle,
transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ADOC-VER4-020", "sha": "c38868a62",
         "attendu": "technicien d'une intervention (portée équipe, ni responsable ni créateur) : GET fiche chantier 200 ; GET pv-reception / bon-livraison / dossier-remise 404 (divergence) ; attendu sain : même verdict que la fiche",
         "modeles": ["authentication.Company", "installations.Installation", "installations.Intervention"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.installations.models import Installation, Intervention
    from apps.roles.models import Role
    from apps.roles.permissions_registre import SCOPE_TEAM
    User = get_user_model()
    co = Company.objects.create(nom='Sonde ADOC VER4-020', slug='sonde-adoc-ver4-020')
    chef = User.objects.create_user(username='sonde-adoc-v4-020-chef', password='x', company=co,
                                    role_legacy='responsable')
    role = Role.objects.create(company=co, nom='Technicien sonde v4-020',
                               permissions=['installation_voir', 'intervention_gerer', SCOPE_TEAM])
    resp_tech = User.objects.create_user(username='sonde-adoc-v4-020-a', password='x', company=co,
                                         role_legacy='normal', role=role)
    assigne = User.objects.create_user(username='sonde-adoc-v4-020-b', password='x', company=co,
                                       role_legacy='normal', role=role)
    inst = Installation.objects.create(company=co, reference='CH-SONDE-ADOC-V4-020',
                                       technicien_responsable=resp_tech, created_by=chef,
                                       statut=Installation.Statut.INSTALLE)
    Intervention.objects.create(company=co, installation=inst, type_intervention='pose',
                                technicien=assigne, created_by=chef)
    api = APIClient()
    api.force_authenticate(assigne)
    codes = {'fiche': api.get(f'/api/django/installations/chantiers/{inst.pk}/', HTTP_HOST='localhost').status_code}
    for route in ('pv-reception', 'bon-livraison', 'dossier-remise'):
        codes[route] = api.get(f'/api/django/documents/chantiers/{inst.pk}/{route}/',
                               HTTP_HOST='localhost').status_code
    # Témoin : le technicien responsable obtient ses documents.
    api_r = APIClient()
    api_r.force_authenticate(resp_tech)
    codes['temoin_responsable_pv'] = api_r.get(f'/api/django/documents/chantiers/{inst.pk}/pv-reception/',
                                               HTTP_HOST='localhost').status_code
    print(f'codes={codes}')
    repro = codes['fiche'] == 200 and all(codes[r] == 404 for r in ('pv-reception', 'bon-livraison', 'dossier-remise'))
    return {'repro': repro, 'codes': codes}
