SONDE = {"constat": "C-ASEC-027", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : jeton iCal signé il y a 400 jours -> 404 (récent -> 200) ; après "
                    "« régénérer le lien », l'ancien jeton -> 404 neutre (même corps qu'un jeton inexistant), le "
                    "nouveau -> 200 VCALENDAR ; la régénération de A ne touche pas le jeton de B (toujours 200)"}


def sonde(ctx):
    import random
    import time
    from unittest import mock
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.reporting.calendar import make_ics_token
    from apps.reporting.models import JetonCalendrier
    User = get_user_model()
    FLUX = '/api/django/reporting/calendar.ics?token='
    ABO = '/api/django/reporting/calendar/subscription/'
    base = random.randint(2, 200)
    n = [0]

    def flux(jeton):
        n[0] += 1
        return APIClient().get(FLUX + jeton, HTTP_HOST='localhost', REMOTE_ADDR=f'10.45.{base}.{n[0]}')

    def utilisateur(tag):
        co = Company.objects.create(nom=f'Sonde ASEC027 {tag}', slug=f'sonde-asec027-{tag}')
        u = User.objects.create_user(username=f'sonde-asec027-{tag}', password='x', role_legacy='responsable',
                                     company=co, email=f'asec027{tag}@sonde.invalid')
        s = APIClient(HTTP_HOST='localhost', REMOTE_ADDR=f'10.46.{base}.{1 if tag == "a" else 2}')
        s.force_authenticate(u)
        return co, u, s

    a, ua, sa = utilisateur('a')
    b, ub, sb = utilisateur('b')
    with mock.patch('django.core.signing.time.time', return_value=time.time() - 400 * 86400):
        vieux = make_ics_token(ua)
    recent = make_ics_token(ua)
    gestes = {'vieux_400j': flux(vieux).status_code, 'recent': flux(recent).status_code}
    abo_a = sa.get(ABO)
    ancien = abo_a.data.get('token') if isinstance(abo_a.data, dict) else None
    jeton_b = sb.get(ABO).data.get('token')
    gestes['ancien_avant_regeneration'] = flux(ancien).status_code
    regen = sa.post(ABO)
    nouveau = regen.data.get('token') if isinstance(regen.data, dict) else None
    r_ancien = flux(ancien)
    r_faux = flux('pas-un-jeton-sonde-asec027')
    r_nouveau = flux(nouveau)
    gestes.update({
        'regenerer': regen.status_code, 'nouveau_different': bool(nouveau) and nouveau != ancien,
        'ancien_apres_regeneration': r_ancien.status_code, 'faux': r_faux.status_code,
        'ancien_neutre_comme_faux': r_ancien.content == r_faux.content,
        'nouveau': r_nouveau.status_code, 'nouveau_vcalendar': b'BEGIN:VCALENDAR' in r_nouveau.content,
        'recent_avant_regeneration_apres': flux(recent).status_code,
        'jeton_b_apres_regeneration_a': flux(jeton_b).status_code})
    persistance = {'version_a': JetonCalendrier.objects.filter(user=ua).values_list('version', flat=True).first(),
                   'version_b': JetonCalendrier.objects.filter(user=ub).values_list('version', flat=True).first()}
    out = {'gestes': gestes, 'persistance': persistance}
    out['repro'] = bool(gestes['vieux_400j'] == 404 and gestes['recent'] == 200
                        and gestes['ancien_avant_regeneration'] == 200 and regen.status_code == 200
                        and gestes['nouveau_different'] and r_ancien.status_code == 404
                        and gestes['ancien_neutre_comme_faux'] and r_nouveau.status_code == 200
                        and gestes['nouveau_vcalendar'] and gestes['recent_avant_regeneration_apres'] == 404
                        and gestes['jeton_b_apres_regeneration_a'] == 200 and persistance['version_a'] == 1
                        and not persistance['version_b'])
    return out
