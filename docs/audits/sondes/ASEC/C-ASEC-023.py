SONDE = {"constat": "C-ASEC-023", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : mauvais mot de passe sur /api/django/token/ pour un compte verrouillé, un "
                    "compte SSO obligatoire, un compte normal et un nom inconnu -> quatre 401 au corps identique "
                    "(hors request_id), sans sso_required ni compte_verrouille ; bon mot de passe du compte verrouillé "
                    "-> même 401 ; GET /api/django/identity/login-banner/?username=<compte de B> sur l'hôte plateforme "
                    "-> ne rend PAS la bannière de B ; légitime : hôte rattaché à B -> bannière de B ; bon mot de "
                    "passe SSO -> 403 sso_required"}


def sonde(ctx):
    import uuid
    from datetime import timedelta
    from unittest import mock
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.test import override_settings
    from django.utils import timezone
    from rest_framework.test import APIClient
    from apps.identity.models import IdentityProvider
    from apps.parametres.models_company import CompanyProfile
    from authentication.models import Company
    from authentication.throttles import LoginRateThrottle
    from core.models import TenantTheme
    User = get_user_model()
    BON = 'Bon-mdp-123!'
    s = uuid.uuid4().hex[:6]
    n = [0]

    def ip():
        n[0] += 1
        return f'192.0.2.{n[0] % 250 + 1}'

    def login(username, password):
        return APIClient().post('/api/django/token/', {'username': username, 'password': password}, format='json',
                                HTTP_HOST='localhost', REMOTE_ADDR=ip())

    def corps(r):
        c = dict(r.data) if isinstance(getattr(r, 'data', None), dict) else {'brut': str(r.content[:200])}
        if isinstance(c.get('error'), dict):
            c['error'] = {k: v for k, v in c['error'].items() if k != 'request_id'}
        return c

    a = Company.objects.create(nom='Sonde ASEC023 a', slug=f'sonde-asec023-{s}-a')
    b = Company.objects.create(nom='Sonde ASEC023 b', slug=f'sonde-asec023-{s}-b')
    IdentityProvider.objects.create(company=b, protocol='saml', nom='Okta sonde', actif=True, enforce_sso=True)
    normal = User.objects.create_user(username=f'sonde-asec023-{s}-normal', password=BON, company=a)
    verrou = User.objects.create_user(username=f'sonde-asec023-{s}-verrou', password=BON, company=a)
    verrou.locked_until = timezone.now() + timedelta(minutes=15)
    verrou.save(update_fields=['locked_until'])
    sso = User.objects.create_user(username=f'sonde-asec023-{s}-sso', password=BON, company=b)
    out = {'throttle': 'LoginRateThrottle neutralisé par mock ; REMOTE_ADDR varié par requête'}
    with mock.patch.object(LoginRateThrottle, 'allow_request', return_value=True):
        cas = {'verrouille': verrou.username, 'sso_obligatoire': sso.username, 'normal': normal.username,
               'inconnu': f'sonde-asec023-{s}-inconnu'}
        reps = {k: login(u, 'faux-mot-de-passe') for k, u in cas.items()}
        ref = corps(reps['inconnu'])
        out['mauvais_mdp_4_cas'] = {k: [r.status_code, corps(r) == ref] for k, r in reps.items()}
        out['corps_reference'] = ref
        quatre_ok = all(r.status_code == 401 and corps(r) == ref and 'sso_required' not in str(r.data)
                        and 'compte_verrouille' not in str(r.data) for r in reps.values())
        bon_verrou = login(verrou.username, BON)
        bon_sso = login(sso.username, BON)
        out['bon_mdp'] = {'verrouille': [bon_verrou.status_code, corps(bon_verrou) == ref,
                                         'access_token' in bon_verrou.cookies],
                          'sso': [bon_sso.status_code, (bon_sso.data or {}).get('code')
                                  if isinstance(bon_sso.data, dict) else None, 'access_token' in bon_sso.cookies]}
        bon_ok = (bon_verrou.status_code == 401 and corps(bon_verrou) == ref
                  and 'access_token' not in bon_verrou.cookies
                  and bon_sso.status_code == 403 and 'access_token' not in bon_sso.cookies)
    # Bannière : B a sa mention ; un anonyme sur l'hôte plateforme passe le username d'un compte de B
    BANNIERE_B = f'Mention confidentielle sonde {s}'
    CompanyProfile.objects.update_or_create(company=b, defaults={'login_banner_text': BANNIERE_B})
    URL = '/api/django/identity/login-banner/'
    r = APIClient().get(URL, {'username': sso.username}, HTTP_HOST='localhost')
    texte = r.data.get('login_banner_text') if r.status_code == 200 and isinstance(r.data, dict) else None
    hote_b = f'sonde-asec023-{s}.example'
    TenantTheme.objects.create(company=b, domaine=hote_b)
    with override_settings(ALLOWED_HOSTS=list(settings.ALLOWED_HOSTS) + [hote_b]):
        rl = APIClient().get(URL, {'username': 'inconnu'}, HTTP_HOST=hote_b)
    texte_l = rl.data.get('login_banner_text') if rl.status_code == 200 and isinstance(rl.data, dict) else None
    out['banniere'] = {'hote_plateforme_username_b': [r.status_code, texte == BANNIERE_B, texte],
                       'legitime_hote_b': [rl.status_code, texte_l == BANNIERE_B]}
    ban_ok = r.status_code == 200 and BANNIERE_B not in str(r.data) and rl.status_code == 200 and texte_l == BANNIERE_B
    out['verdicts'] = {'quatre_reponses_identiques': quatre_ok, 'bon_mdp': bon_ok, 'banniere': ban_ok}
    out['repro'] = bool(quatre_ok and bon_ok and ban_ok)
    return out
