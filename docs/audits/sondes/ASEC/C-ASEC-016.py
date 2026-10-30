SONDE = {"constat": "C-ASEC-016", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : après POST /auth/2fa/setup/ + /auth/2fa/enable/ puis /auth/change-password/ "
                    "par l'utilisateur lui-même, AuditLog.changes de son compte trace totp_secret et password avec "
                    "old/new = *** (le changement reste tracé, jamais la valeur : ni le secret ni un hash de mot de "
                    "passe dans le journal) ; GET /api/django/audit/objets/authentication.customuser/<id>/as-of/ -> "
                    "200 avec totp_secret et password = *** et aucun secret dans la réponse"}


def sonde(ctx):
    import json
    import pyotp
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType
    from rest_framework.test import APIClient
    from apps.audit.models import AuditLog
    from authentication.models import Company
    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    ANCIEN, NOUVEAU = 'Ancien-mdp-016!', 'Brise-Marine-Oasis-74'

    a = Company.objects.create(nom='Sonde ASEC016 a', slug='sonde-asec016-a')
    b = Company.objects.create(nom='Sonde ASEC016 b', slug='sonde-asec016-b')
    u = User.objects.create_user(username='sonde-asec016-u', password=ANCIEN, email='u@sonde.invalid', company=a)
    su = User.objects.create_superuser(username='sonde-asec016-su', password='x', email='su@sonde.invalid')
    su.company = a
    su.save()
    su_b = User.objects.create_superuser(username='sonde-asec016-sub', password='x', email='sub@sonde.invalid')
    su_b.company = b
    su_b.save()
    ct = ContentType.objects.get_for_model(User)
    pk_max = AuditLog.objects.order_by('-pk').values_list('pk', flat=True).first() or 0

    api = APIClient()
    api.force_authenticate(u)
    setup = api.post('/api/django/auth/2fa/setup/', {}, format='json', **H)
    secret = setup.data.get('secret') if setup.status_code == 200 else None
    enable = api.post('/api/django/auth/2fa/enable/', {'code': pyotp.TOTP(secret).now() if secret else '000000'},
                      format='json', **H)
    hash_avant = User.objects.get(pk=u.pk).password
    chg = api.post('/api/django/auth/change-password/', {'current_password': ANCIEN, 'new_password': NOUVEAU},
                   format='json', **H)
    relu = User.objects.get(pk=u.pk)
    out = {'gestes': {'setup': setup.status_code, 'enable': enable.status_code, 'change_password': chg.status_code,
                      'change_password_detail': (chg.data or {}).get('detail') if chg.status_code != 200 else None,
                      'totp_enabled_relu': relu.totp_enabled, 'nouveau_mdp_relu': relu.check_password(NOUVEAU)}}

    lignes = list(AuditLog.objects.filter(content_type=ct, object_id=str(u.pk), pk__gt=pk_max).order_by('pk'))
    changes = [c for ligne in lignes for c in (ligne.changes or []) if isinstance(c, dict)]
    secrets = {c['field']: (c.get('old'), c.get('new')) for c in changes
               if c.get('field') in ('totp_secret', 'password', 'totp_recovery_codes')}
    brut = json.dumps([ligne.changes for ligne in lignes], default=str)
    fuites = [x for x in (secret, hash_avant, relu.password, NOUVEAU, ANCIEN) if x and x in brut]
    out['audit'] = {'lignes': len(lignes), 'champs_secrets': secrets, 'nb_fuites_en_clair': len(fuites),
                    'champs_traces': sorted({c.get('field') for c in changes})}
    journal_ok = (secrets.get('totp_secret') == ('***', '***') and secrets.get('password') == ('***', '***')
                  and not fuites)  # totp_recovery_codes : observé, non gaté (hors texte ASEC8)

    api_su = APIClient()
    api_su.force_authenticate(su)
    url = f'/api/django/audit/objets/authentication.customuser/{u.pk}/as-of/'
    asof = api_su.get(url, **H)
    champs = asof.data.get('fields', {}) if asof.status_code == 200 and isinstance(asof.data, dict) else {}
    texte = json.dumps(asof.data, default=str) if asof.status_code == 200 else ''
    fuites_asof = [x for x in (secret, relu.password, hash_avant) if x and x in texte]
    out['as_of'] = {'status': asof.status_code, 'totp_secret': champs.get('totp_secret', '<absent>'),
                    'password': champs.get('password', '<absent>'), 'nb_fuites': len(fuites_asof)}
    asof_ok = (asof.status_code == 200 and not fuites_asof
               and all(champs.get(f, '***') == '***' for f in ('totp_secret', 'password'))
               and ('totp_secret' in champs or 'password' in champs))
    # Observation (non gatée) : un superuser rattaché à B relit l'objet de A
    asof_b = APIClient()
    asof_b.force_authenticate(su_b)
    rb = asof_b.get(url, **H)
    out['as_of_par_societe_b'] = [rb.status_code, sorted((rb.data or {}).get('fields', {}))[:5]
                                  if rb.status_code == 200 and isinstance(rb.data, dict) else None]
    gestes_ok = setup.status_code == 200 and enable.status_code == 200 and chg.status_code == 200 and relu.totp_enabled
    out['verdicts'] = {'gestes_legitimes': gestes_ok, 'journal_caviarde': journal_ok, 'as_of_caviarde': asof_ok}
    out['repro'] = bool(gestes_ok and journal_ok and asof_ok)
    return out
