SONDE = {"constat": "C-ASEC-012", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : webhook WhatsApp SAV (AllowAny) -> POST non signé 401, signature fausse "
                    "401, secret absent 503, numéro destinataire inconnu 200 neutre — aucun ticket ni activité créé ; "
                    "réponse identique expéditeur connu/inconnu ; message signé et rattaché -> ticket dans LA "
                    "société du numéro (B), rien chez A"}


def sonde(ctx):
    import hashlib
    import hmac
    import json
    import uuid
    from django.test import override_settings
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.sav.models import Ticket, TicketActivity
    H = {'HTTP_HOST': 'localhost'}
    URL = '/api/django/sav/webhooks/whatsapp-inbound/'
    SECRET = 'secret-sonde-asec012'
    a = Company.objects.create(nom='Sonde ASEC012 a', slug='sonde-asec012-a')
    b = Company.objects.create(nom='Sonde ASEC012 b', slug='sonde-asec012-b')
    client_b = Client.objects.create(company=b, nom='Client', prenom='B', telephone='0600112299')
    num_a, num_b = f'SONDE012-A-{a.pk}', f'SONDE012-B-{b.pk}'
    numeros = {num_a: a.pk, num_b: b.pk}

    def payload(dest, tel='212600112299'):
        return {'entry': [{'changes': [{'value': {
            'metadata': {'phone_number_id': dest},
            'messages': [{'id': f'wamid.sonde012.{uuid.uuid4().hex}', 'from': tel,
                          'text': {'body': 'Panne onduleur'}}]}}]}]}

    def signer(corps, secret=SECRET):
        return 'sha256=' + hmac.new(secret.encode(), corps, hashlib.sha256).hexdigest()

    def post(pl, signature='auto', secret=SECRET):
        corps = json.dumps(pl).encode()
        extra = dict(H)
        if signature == 'auto':
            extra['HTTP_X_HUB_SIGNATURE_256'] = signer(corps)
        elif signature == 'fausse':
            extra['HTTP_X_HUB_SIGNATURE_256'] = signer(corps, 'autre-secret')
        with override_settings(WHATSAPP_BUSINESS_API_KEY='cle-sonde-asec012', SAV_WHATSAPP_APP_SECRET=secret,
                               SAV_WHATSAPP_NUMEROS=numeros):
            return APIClient().post(URL, data=corps, content_type='application/json', **extra)

    def compteurs():
        return (Ticket.objects.filter(company__in=[a, b]).count(),
                TicketActivity.objects.filter(ticket__company__in=[a, b]).count())

    avant = compteurs()
    gestes = {}
    r = post(payload(num_b), signature=None)
    gestes['non_signe'] = r.status_code
    r = post(payload(num_b), signature='fausse')
    gestes['signature_fausse'] = r.status_code
    r = post(payload(num_b), secret='')
    gestes['sans_secret'] = r.status_code
    r = post(payload('SONDE012-INCONNU'))
    gestes['numero_inconnu'] = r.status_code
    apres_refus = compteurs()
    connu = post(payload(num_b))
    inconnu = post(payload(num_b, tel='212699999998'))
    gestes['connu_vs_inconnu'] = [connu.status_code, inconnu.status_code, connu.content == inconnu.content]
    tickets_b = Ticket.objects.filter(company=b)
    out = {'gestes': gestes, 'compteurs_avant': avant, 'compteurs_apres_refus': apres_refus,
           'inchange_apres_refus': apres_refus == avant,
           'legitime': {'tickets_b': tickets_b.count(),
                        'ticket_client_b': tickets_b.filter(client=client_b).exists(),
                        'tickets_a': Ticket.objects.filter(company=a).count()}}
    out['repro'] = bool(gestes['non_signe'] == 401 and gestes['signature_fausse'] == 401
                        and gestes['sans_secret'] == 503 and gestes['numero_inconnu'] == 200
                        and out['inchange_apres_refus'] and connu.status_code == 200
                        and gestes['connu_vs_inconnu'][2] and out['legitime']['ticket_client_b']
                        and out['legitime']['tickets_a'] == 0)
    return out
