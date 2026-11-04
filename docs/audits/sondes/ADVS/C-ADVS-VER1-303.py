# flake8: noqa  (sonde de verification VER1, rejouable par scripts/sonde.py)
"""VER1-303 (ADVS21) — portail : POST /portail/mes-devis/<id>/accepter/ d'un devis industriel avec un ICE différent de celui
du client → 409 ice_divergent (message qui nomme les deux ICE), 0 signature, devis envoyé, client inchangé ; même ICE (forme
normalisée) → 200 ; client sans ICE → 200 (ICE déclaré stocké, client non écrasé) ; devis commercial aussi. repro=True = écart.
Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-031", "sha": "06ced8b1a",
         "attendu": "ICE B sur client ICE A : 409 ice_divergent, rien signé (défaut : 200, ice_declare = B)",
         "modeles": ["ventes.Devis", "ventes.DevisSignature", "crm.Client"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from unittest import mock
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company, CustomUser
    from apps.crm.models import Client
    from apps.portail.tests import corps_acceptation
    from apps.portail.tests.test_ntprt10_mes_devis import make_portal_user
    from apps.ventes.models import Devis, DevisSignature
    c = Company.objects.create(nom='Sonde VER1 303', slug='sonde-ver1-303')
    ca = Client.objects.create(company=c, nom='Hotel Alpha', prenom='V303A', email='v303a@example.invalid',
                               ice='111111111111111')
    csans = Client.objects.create(company=c, nom='Sans ICE', prenom='V303B', email='v303b@example.invalid')
    ua = make_portal_user(c, 'sonde-ver1-303-a', CustomUser.PORTEE_PORTAIL_CLIENT, ca.id)
    ub = make_portal_user(c, 'sonde-ver1-303-b', CustomUser.PORTEE_PORTAIL_CLIENT, csans.id)
    n = [0]

    def devis(client, mode='industriel'):
        n[0] += 1
        return Devis.objects.create(company=c, reference=f'DEV-V303-{n[0]:02d}', client=client,
                                    statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'), mode_installation=mode)

    def post(d, user, ice, mode_ent=None):
        api = APIClient()
        api.force_authenticate(user=user)
        corps = corps_acceptation(d, accepte_conditions=True, nom='Karim Exemple', consent_esign=True,
                                  entreprise={'raison_sociale': 'Hotel Exemple SARL',
                                              'signataire_qualite': 'Directeur general', 'ice': ice})
        try:
            with transaction.atomic(), mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf'):
                r = api.post(f'/api/django/portail/mes-devis/{d.id}/accepter/', corps, format='json',
                             HTTP_HOST='localhost')
            try:
                body = json.loads(r.content.decode('utf-8', 'replace') or '{}')
            except Exception:
                body = {'_brut': r.content[:200].decode('utf-8', 'replace')}
            return r.status_code, body
        except Exception as e:
            return 599, {'_exc': repr(e)[:300]}
    obs = {}
    # 1. ICE B sur client ICE A (industriel et commercial)
    for mode in ('industriel', 'commercial'):
        d = devis(ca, mode)
        s, b = post(d, ua, '222222222222222')
        d.refresh_from_db(); ca.refresh_from_db()
        obs[f'divergent_{mode}'] = {'status': s, 'code': b.get('code'), 'detail_nomme_les_2': (
            '222222222222222' in str(b.get('detail')) and '111111111111111' in str(b.get('detail'))),
            'statut': d.statut, 'signatures': DevisSignature.objects.filter(devis=d).count(), 'client_ice': ca.ice}
    # 2. même ICE, forme normalisée
    d = devis(ca)
    Client.objects.filter(pk=ca.pk).update(ice='111-111-111-111-111')
    s, b = post(d, ua, '111111111111111')
    obs['meme_ice_normalise'] = {'status': s, 'detail': str(b.get('detail'))[:80]}
    # 3. client sans ICE
    d = devis(csans)
    s, b = post(d, ub, '333333333333333')
    csans.refresh_from_db()
    obs['client_sans_ice'] = {'status': s, 'client_ice_apres': csans.ice,
                              'ice_declare': DevisSignature.objects.filter(devis=d).values_list('ice_declare', flat=True).first()}
    ecart = False
    for mode in ('industriel', 'commercial'):
        o = obs[f'divergent_{mode}']
        if not (o['status'] == 409 and o['code'] == 'ice_divergent' and o['detail_nomme_les_2']
                and o['statut'] == 'envoye' and o['signatures'] == 0 and o['client_ice'] == '111111111111111'):
            ecart = True
    if obs['meme_ice_normalise']['status'] != 200 or obs['client_sans_ice']['status'] != 200:
        ecart = True
    return {'repro': ecart, 'observe': obs}
