# flake8: noqa  (sonde de vérification PA1, rejouable par scripts/sonde.py)
"""H-10 + H-14.
H-10 : `bilan_hebdo_relances()` appelé DEUX fois (redistribution acks_late, double beat) → combien de notifications
       CRM_BILAN_HEBDO pour la direction d'une société NEUVE ?
H-14 : formulaire de contact ÉTEINT (CONTACT_FORM_ENABLED=False) : 6 POST anonymes de la même IP → 404 ×6 ou
       404 ×5 puis 429 ? Le throttle est servi par un cache LocMem posé le temps de la sonde (aucune clé laissée
       dans le cache partagé). Transaction annulée."""
SONDE = {"constat": "C-ACVI-149+153", "sha": "352ae5455",
         "attendu": "H-10 : 1 bilan par société et par semaine même si le beat repasse ; "
                    "H-14 : formulaire éteint → 404 à chaque appel, aucun mail",
         "modeles": ["notifications.Notification", "authentication.CustomUser"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from django.core import mail
    from django.core.cache.backends.locmem import LocMemCache
    from django.db import transaction
    from django.test import Client, override_settings
    from django.urls import reverse
    from authentication.models import Company
    from apps.notifications.models import Notification
    from apps.notifications.types_evenements import EventType
    from apps.roles.models import Role
    from apps.roles.permissions_registre import ADMIN_PERMISSIONS
    from apps.crm.management.commands.bilan_hebdo_relances import bilan_hebdo_relances
    from apps.contact import views as cv
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ACVI 149', slug='sonde-acvi-149')
    role = Role.objects.create(company=c, nom='Administrateur', permissions=ADMIN_PERMISSIONS, est_systeme=True)
    u = U.objects.create_user(username='sonde-acvi-149', password='x', company=c, role=role, role_legacy='admin')
    obs = {'societe_active': c.actif}

    def nb():
        return Notification.objects.filter(company=c, recipient=u, event_type=EventType.CRM_BILAN_HEBDO).count()

    n0 = nb()
    r1 = bilan_hebdo_relances()
    n1 = nb()
    r2 = bilan_hebdo_relances()
    n2 = nb()
    obs['H10'] = {'notifs_apres_1er': n1 - n0, 'notifs_apres_2e': n2 - n0, 'retours': [r1, r2]}

    ancien = cv.ContactThrottle.cache
    cv.ContactThrottle.cache = LocMemCache('sonde-acvi-149', {})
    codes = []
    mails0 = len(getattr(mail, 'outbox', []))
    try:
        with override_settings(CONTACT_FORM_ENABLED=False):
            cli = Client(raise_request_exception=False)
            url = reverse('contact')
            for i in range(6):
                with transaction.atomic():
                    rr = cli.post(url, data={'nom': 'X', 'email': 'x@example.invalid', 'message': 'test'},
                                  content_type='application/json', HTTP_HOST='localhost',
                                  REMOTE_ADDR='203.0.113.149')
                codes.append(rr.status_code)
    finally:
        cv.ContactThrottle.cache = ancien
    obs['H14'] = {'url': reverse('contact'), 'codes': codes,
                  'mails': len(getattr(mail, 'outbox', [])) - mails0}
    repro = {'H10': (n2 - n0) > 1, 'H14': 429 in codes}
    obs['repro_par_constat'] = repro
    return {'repro': any(repro.values()), 'observe': obs}
