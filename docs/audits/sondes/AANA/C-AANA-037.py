"""Sonde AANA50 (acceptation live du groupe AANA), rejouable par scripts/sonde.py (AMET93) :
transaction annulée, mail en mémoire, Celery coupé, HTTP bloqué. Jamais contre la prod.
Rejoue C-AANA-037 (audit analyse du 05/10, §6) : le lien de confirmation de la page de statut était relatif.
"""
SONDE = {
    'constat': 'C-AANA-037',
    'sha': '5908d43bb',
    'attendu': "défaut absent : l'e-mail de confirmation d'abonnement à la page de statut porte un lien ABSOLU (http(s)://…/confirmer/<jeton>/)",
}


def sonde(ctx):
    from django.core import mail
    from rest_framework.test import APIClient
    from apps.statuspage.models import StatusSubscriber
    email = 'sonde-aana-037@example.invalid'
    avant = len(getattr(mail, 'outbox', []))
    r = APIClient().post('/api/django/statuspage/public/abonner/', {'email': email}, HTTP_HOST='localhost')
    ab = StatusSubscriber.objects.filter(email=email).first()
    fin = '/api/django/statuspage/public/confirmer/%s/' % (ab.token_desabonnement if ab else '?')
    boite = getattr(mail, 'outbox', [])
    corps = boite[-1].body if len(boite) > avant else ''
    lien = next((m for m in corps.split() if m.endswith(fin)), None)
    absolu = bool(lien and lien.startswith(('http://', 'https://')))
    print('abonner=%s mails=%s lien=%s' % (r.status_code, len(boite) - avant, lien))
    return {'repro': absolu, 'statut': r.status_code, 'lien': lien}
