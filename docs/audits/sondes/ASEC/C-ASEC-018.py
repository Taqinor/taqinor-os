SONDE = {"constat": "C-ASEC-018", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : formulaire de connexion de l'admin Django (reverse('admin:login'), chemin "
                    "DJANGO_ADMIN_URL) : superuser totp_enabled SANS code -> 200 formulaire en erreur, aucune session "
                    "(index -> 302), failed_login_count +1 ; code faux -> idem ; is_staff non superuser -> refusé "
                    "(formulaire en erreur, index fermé même après force_login) ; légitime : bon code -> 302, index "
                    "200, une UserSession de plus, compteur remis à 0"}


def sonde(ctx):
    import os
    import uuid
    import pyotp
    from django.contrib.auth import get_user_model
    from django.test import Client
    from django.urls import reverse
    from apps.parametres.models import CompanyProfile
    from authentication.models import Company, UserSession
    User = get_user_model()
    MDP = 'Admin-mdp-123!'
    s = uuid.uuid4().hex[:6]
    H = {'HTTP_HOST': 'localhost'}

    a = Company.objects.create(nom='Sonde ASEC018 a', slug=f'sonde-asec018-{s}-a')
    b = Company.objects.create(nom='Sonde ASEC018 b', slug=f'sonde-asec018-{s}-b')
    CompanyProfile.objects.update_or_create(company=a, defaults={'lockout_max_attempts': 3})
    secret = pyotp.random_base32()
    su = User.objects.create_superuser(username=f'sonde-asec018-{s}-su', password=MDP, email='su@sonde.invalid')
    su.company = a
    su.totp_secret = secret
    su.totp_enabled = True
    su.save()
    staff = User.objects.create_user(username=f'sonde-asec018-{s}-staff', password=MDP, company=b, is_staff=True)
    url, index = reverse('admin:login'), reverse('admin:index')

    def tenter(username, **extra):
        client = Client(**H)
        corps = {'username': username, 'password': MDP, 'next': index}
        corps.update(extra)
        r = client.post(url, corps, **H)
        html = r.content.decode('utf-8', 'replace') if r.status_code == 200 else ''
        return client, r, ('errornote' in html or 'errorlist' in html)

    def relu(u):
        return User.objects.get(pk=u.pk)

    out = {'admin_login_url': url, 'DJANGO_ADMIN_URL_env': os.environ.get('DJANGO_ADMIN_URL', '<défaut>')}
    sessions_avant = UserSession.objects.filter(user=su).count()
    c1, r1, err1 = tenter(su.username)
    idx1 = c1.get(index, **H).status_code
    cpt1 = relu(su).failed_login_count
    c2, r2, err2 = tenter(su.username, otp='000000')
    idx2 = c2.get(index, **H).status_code
    cpt2 = relu(su).failed_login_count
    out['superuser_2fa'] = {'sans_code': [r1.status_code, err1, idx1, cpt1], 'code_faux': [r2.status_code, err2, idx2,
                                                                                           cpt2],
                            'sessions_creees': UserSession.objects.filter(user=su).count() - sessions_avant}
    su_ok = (r1.status_code == 200 and err1 and idx1 == 302 and cpt1 == 1 and r2.status_code == 200 and err2
             and idx2 == 302 and cpt2 == 2 and out['superuser_2fa']['sessions_creees'] == 0)
    c3, r3, err3 = tenter(staff.username)
    idx3 = c3.get(index, **H).status_code
    c3.force_login(staff)
    idx3_force = c3.get(index, **H).status_code
    out['staff_non_superuser'] = [r3.status_code, err3, idx3, idx3_force]
    staff_ok = r3.status_code == 200 and err3 and idx3 == 302 and idx3_force != 200
    c4, r4, _ = tenter(su.username, otp=pyotp.TOTP(secret).now())
    idx4 = c4.get(index, **H).status_code
    out['legitime_bon_code'] = {'status': r4.status_code, 'index': idx4,
                                'sessions_creees': UserSession.objects.filter(user=su).count() - sessions_avant,
                                'compteur': relu(su).failed_login_count}
    leg_ok = r4.status_code == 302 and idx4 == 200 and out['legitime_bon_code']['sessions_creees'] == 1 \
        and relu(su).failed_login_count == 0
    out['verdicts'] = {'superuser_sans_code_ou_faux': su_ok, 'staff_refuse': staff_ok, 'legitime': leg_ok}
    out['repro'] = bool(su_ok and staff_ok and leg_ok)
    return out
