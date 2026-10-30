SONDE = {"constat": "C-ASEC-022", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : POST anonyme /api/django/auth/register-company/ (corps complet, valide) "
                    "avec "
                    "TENANT_SIGNUP_ENABLED à sa valeur réelle de réglage (attendue False, défaut '0') -> 404, aucune "
                    "Company ni aucun utilisateur créés (comptes relus avant / après dans la sonde)"}


def sonde(ctx):
    import uuid
    from unittest import mock
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from authentication.throttles import RegisterRateThrottle
    User = get_user_model()
    s = uuid.uuid4().hex[:6]
    drapeau = getattr(settings, 'TENANT_SIGNUP_ENABLED', '<absent>')
    # Deux sociétés existantes (contexte multi-locataire du rejeu) : rien ne doit s'y ajouter non plus
    for tag in ('a', 'b'):
        Company.objects.create(nom=f'Sonde ASEC022 {tag}', slug=f'sonde-asec022-{s}-{tag}')

    def comptes():
        return Company.objects.count(), User.objects.count()

    corps = {'company_nom': f'Sonde ASEC022 {s} SARL', 'username': f'sonde-asec022-{s}-boss',
             'password': 'Mot-de-passe-solide-22', 'email': f'boss-{s}@sonde.invalid'}
    avant = comptes()
    with mock.patch.object(RegisterRateThrottle, 'allow_request', return_value=True):
        r = APIClient(raise_request_exception=False).post('/api/django/auth/register-company/', corps, format='json',
                                                          HTTP_HOST='localhost', REMOTE_ADDR='203.0.113.22')
    apres = comptes()
    out = {'TENANT_SIGNUP_ENABLED': drapeau, 'throttle': 'RegisterRateThrottle (scope register, 3/h par IP) '
                                                         'neutralisé par mock',
           'status': r.status_code, 'comptes_avant': list(avant), 'comptes_apres': list(apres),
           'societe_creee': Company.objects.filter(nom=corps['company_nom']).exists(),
           'utilisateur_cree': User.objects.filter(username=corps['username']).exists(),
           'jeton_rendu': 'access_token' in r.cookies}
    out['repro'] = bool(drapeau is False and r.status_code == 404 and avant == apres and not out['societe_creee']
                        and not out['utilisateur_cree'] and not out['jeton_rendu'])
    return out
