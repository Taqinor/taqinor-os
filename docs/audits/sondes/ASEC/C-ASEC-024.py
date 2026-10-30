SONDE = {"constat": "C-ASEC-024", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : 40 POST anonymes de la bannière de connexion depuis la même IP -> "
                    "premier 200, puis 429 ; au plus 1 AuditLog SECURITY_ALERT agrégée pour la rafale ; une autre "
                    "société (B) ne reçoit aucune alerte ; les 12 vues publiques « sécurité » sont vues par le "
                    "scanner et throttlées (exemptions = sondes de santé seulement)"}


def sonde(ctx):
    import random
    from django.apps import apps as django_apps
    from django.test import override_settings
    from rest_framework.test import APIClient
    from authentication.models import Company
    from core import public_endpoint_scan
    from core.models import TenantTheme
    AuditLog = django_apps.get_model('audit', 'AuditLog')
    CompanyProfile = django_apps.get_model('parametres', 'CompanyProfile')
    hote = 'sonde-asec024-banner.example'
    a = Company.objects.create(nom='Sonde ASEC024 a', slug='sonde-asec024-a')
    b = Company.objects.create(nom='Sonde ASEC024 b', slug='sonde-asec024-b')
    TenantTheme.objects.create(company=a, domaine=hote)
    CompanyProfile.objects.update_or_create(company=a, defaults={'login_banner_text': 'Accès restreint.'})
    # IP unique par exécution : le throttle et l'agrégat vivent dans le cache partagé (non annulé).
    ip = '198.51.100.%d' % random.randint(2, 250)
    alertes = AuditLog.objects.filter(action=AuditLog.Action.SECURITY_ALERT)
    par_soc = 'company' in {f.name for f in AuditLog._meta.get_fields()}

    def compte(co=None):
        return (alertes.filter(company=co) if (co is not None and par_soc) else alertes).count()

    avant, avant_a, avant_b = compte(), compte(a), compte(b)
    api = APIClient(HTTP_HOST=hote, REMOTE_ADDR=ip)
    with override_settings(ALLOWED_HOSTS=[hote, 'testserver', 'localhost']):
        codes = [api.post('/api/django/identity/login-banner/', {'username': 'x'}, format='json').status_code
                 for _ in range(40)]
    apres, apres_a, apres_b = compte(), compte(a), compte(b)
    vues = {
        'identity/views.py::LoginBannerView', 'identity/scim.py::ScimUsersView',
        'identity/scim.py::ScimUserDetailView', 'identity/scim.py::ScimGroupsView',
        'identity/scim.py::ScimGroupDetailView', 'authentication/views.py::CookieTokenRefreshView',
        'core/dashboard_partage.py::dashboard_public', 'core/degraded_mode.py::degraded_mode_status_view',
        'core/export_registry.py::telecharger_export_reversibilite', 'core/trust_center.py::trust_center_public',
        'core/views.py::trust_center_export_pdf', 'core/views.py::metrics_view'}
    par_id = {e['id']: e for e in public_endpoint_scan.public_endpoints()}
    invisibles = sorted(vues - set(par_id))
    non_throttlees = sorted(v for v in vues & set(par_id) if not par_id[v]['throttled'])
    sans_throttle = sorted(i for i, e in par_id.items() if not e['throttled'])
    out = {'ip': ip, 'codes_premier': codes[0], 'nb_200': codes.count(200), 'nb_429': codes.count(429),
           'premier_429_a': codes.index(429) + 1 if 429 in codes else None,
           'alertes_ajoutees_total': apres - avant, 'alertes_a': apres_a - avant_a, 'alertes_b': apres_b - avant_b,
           'alerte_par_societe': par_soc,
           'scanner': {'vues_securite_invisibles': invisibles, 'vues_securite_non_throttlees': non_throttlees,
                       'publiques_sans_throttle': sans_throttle}}
    ajout = (apres_a - avant_a) if par_soc else (apres - avant)
    out['repro'] = bool(codes[0] == 200 and 429 in codes and ajout <= 1 and (apres_b - avant_b) == 0
                        and not invisibles and not non_throttlees)
    return out
