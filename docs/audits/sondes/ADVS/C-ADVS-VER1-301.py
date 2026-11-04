# flake8: noqa  (sonde de verification VER1, rejouable par scripts/sonde.py)
"""VER1-301 (ADVS19) — apres le correctif : « Marquer accepté » interne (POST /ventes/devis/<id>/accepter/ {nom:'Commercial'}) :
consent_esign / consentement_explicite faux, mail client sans « signature électronique » ni « 43-20 » (FR et EN) ; et la phrase
reste servie quand la signature porte un vrai consentement (lien, portail). repro=True = l'ecart existe encore. Societe neuve, transaction annulee."""
SONDE = {"constat": "C-ADVS-024", "sha": "06ced8b1a",
         "attendu": "acceptation interne : consent_esign faux, mail sans « signature électronique » ni 43-20 ; phrase gardee si consent_esign vrai",
         "modeles": ["ventes.Devis", "ventes.ShareLink", "ventes.DevisSignature"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.core import mail
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, DevisSignature, LigneDevis, ShareLink
    from apps.ventes.domain import pdf_signe
    if not hasattr(mail, 'outbox'):
        mail.outbox = []
    U = get_user_model()
    c = Company.objects.create(nom='Sonde VER1 301', slug='sonde-ver1-301')
    u = U.objects.create_user(username='sonde-ver1-301', password='x', role_legacy='admin', company=c,
                              email='vendeur-ver1-301@example.invalid')
    cl = Client.objects.create(company=c, nom='Papier', prenom='Fatima', email='client-ver1-301@example.invalid')
    pan = Produit.objects.create(company=c, nom='Panneau Canadien Solar 710W', sku='VER1301-P',
                                 prix_vente=Decimal('1166.67'), tva=Decimal('20'), quantite_stock=100)
    ond = Produit.objects.create(company=c, nom='Onduleur réseau Huawei 10kW Monophasé', sku='VER1301-O',
                                 prix_vente=Decimal('14000'), tva=Decimal('20'), quantite_stock=100)
    d = Devis.objects.create(company=c, reference='DEV-VER1301-01', client=cl, statut='envoye',
                             taux_tva=Decimal('20'), created_by=u)
    LigneDevis.objects.create(devis=d, produit=pan, designation=pan.nom, quantite=Decimal('12'),
                              prix_unitaire=pan.prix_vente, remise=Decimal('0'), ordre=0)
    LigneDevis.objects.create(devis=d, produit=ond, designation=ond.nom, quantite=Decimal('1'),
                              prix_unitaire=ond.prix_vente, remise=Decimal('0'), ordre=1)
    link = ShareLink.objects.create(company=c, devis=d)
    api = APIClient()
    api.force_authenticate(u)
    obs = {}
    try:
        with transaction.atomic():
            r = api.post(f'/api/django/ventes/devis/{d.id}/accepter/', {'nom': 'Commercial'}, format='json',
                         HTTP_HOST='localhost')
        obs['accepter_interne'] = r.status_code
    except Exception as e:
        obs['accepter_interne'] = repr(e)[:200]
    d.refresh_from_db()
    sig = DevisSignature.objects.filter(devis=d).first()
    obs['statut'] = d.statut
    if sig is None:
        return {'repro': False, 'observe': obs}
    obs['signature'] = {'consent_esign': sig.consent_esign, 'consentement_explicite': sig.consentement_explicite,
                        'ip': sig.ip_address, 'nom': sig.signataire_nom}
    n0 = len(mail.outbox)
    with mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf'):
        try:
            with transaction.atomic():
                obs['rendu_differe'] = pdf_signe.rendre_pdf_signe(d.pk, user_id=u.pk, envoyer_confirmation=True,
                                                                  jeton='sonde-301')
        except Exception as e:
            obs['rendu_differe'] = repr(e)[:200]
    mails = mail.outbox[n0:]
    obs['mails'] = [{'a': m.to, 'sujet': (m.subject or '')[:80]} for m in mails]
    client_mail = next((m for m in mails if 'client-ver1-301@example.invalid' in (m.to or [])), None)
    if client_mail is not None:
        corps = client_mail.body or ''
        obs['corps_client'] = {'signature_electronique': 'signature électronique' in corps, 'loi_43_20': '43-20' in corps,
                               'extrait': corps[corps.find('signature'):corps.find('signature') + 260] if 'signature' in corps else corps[:200]}
    from apps.ventes.domain.confirmation_acceptation import corps_confirmation
    en_interne = corps_confirmation(d, sig, langue='en')
    fr_interne = corps_confirmation(d, sig, langue='fr')
    obs['interne_FR_43_20'] = '43-20' in fr_interne or 'signature électronique' in fr_interne
    obs['interne_EN_43_20'] = '43-20' in en_interne or 'electronic signature' in en_interne
    sig.consent_esign = True  # en memoire seulement (lien / portail) : la phrase doit rester
    obs['consent_vrai_FR_phrase'] = '43-20' in corps_confirmation(d, sig, langue='fr')
    obs['consent_vrai_EN_phrase'] = '43-20' in corps_confirmation(d, sig, langue='en')
    cc = obs.get('corps_client') or {}
    ecart = bool(obs['signature']['consent_esign'] or obs['signature']['consentement_explicite']
                 or cc.get('signature_electronique') or cc.get('loi_43_20') or obs['interne_FR_43_20']
                 or obs['interne_EN_43_20'] or not obs['consent_vrai_FR_phrase'] or not obs['consent_vrai_EN_phrase'])
    if client_mail is None:
        ecart = True
        obs['mail_client'] = 'ABSENT'
    return {'repro': ecart, 'observe': obs}
