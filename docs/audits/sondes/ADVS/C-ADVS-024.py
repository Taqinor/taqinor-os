# flake8: noqa  (sonde de vérification C-L4-3, frère C-L4-4, rejouable par scripts/sonde.py)
"""C-L4-3 — « Marquer accepté » interne (POST /ventes/devis/<id>/accepter/ {nom:'Commercial'}, devis papier) :
la `DevisSignature` créée porte-t-elle consent_esign/consentement_explicite à vrai, et la confirmation envoyée au
client (rendu différé `rendre_pdf_signe(envoyer_confirmation=True)`, mail en mémoire, `_store_signed_pdf` bouchonné)
affirme-t-elle une « signature électronique … loi 43-20 » ? Frère C-L4-4 : le client signe ENSUITE au lien → 200 et
sa signature est jetée ? Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-024", "sha": "1dfa7986c",
         "attendu": "acceptation interne : consent_esign faux, mail sans « signature électronique » (défaut : vrai + loi 43-20)",
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
    c = Company.objects.create(nom='Sonde ADVS 024', slug='sonde-advs-024')
    u = U.objects.create_user(username='sonde-advs-024', password='x', role_legacy='admin', company=c,
                              email='vendeur-advs-024@example.invalid')
    cl = Client.objects.create(company=c, nom='Papier', prenom='Fatima', email='client-advs-024@example.invalid')
    pan = Produit.objects.create(company=c, nom='Panneau Canadien Solar 710W', sku='ADVS024-P',
                                 prix_vente=Decimal('1166.67'), tva=Decimal('20'), quantite_stock=100)
    ond = Produit.objects.create(company=c, nom='Onduleur réseau Huawei 10kW Monophasé', sku='ADVS024-O',
                                 prix_vente=Decimal('14000'), tva=Decimal('20'), quantite_stock=100)
    d = Devis.objects.create(company=c, reference='DEV-ADVS024-01', client=cl, statut='envoye',
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
                                                                  jeton='sonde-024')
        except Exception as e:
            obs['rendu_differe'] = repr(e)[:200]
    mails = mail.outbox[n0:]
    obs['mails'] = [{'a': m.to, 'sujet': (m.subject or '')[:80]} for m in mails]
    client_mail = next((m for m in mails if 'client-advs-024@example.invalid' in (m.to or [])), None)
    if client_mail is not None:
        corps = client_mail.body or ''
        obs['corps_client'] = {'signature_electronique': 'signature électronique' in corps, 'loi_43_20': '43-20' in corps,
                               'extrait': corps[corps.find('signature'):corps.find('signature') + 260] if 'signature' in corps else corps[:200]}
    # Frère C-L4-4 : le client signe au lien après l'acceptation interne
    try:
        with mock.patch('apps.ventes.public_views._notify_open'):
            with transaction.atomic():
                r2 = APIClient().post(f'/api/django/public/proposal/{link.token}/accept/',
                                      {'nom': 'Fatima Papier', 'consent_esign': True}, format='json',
                                      HTTP_HOST='localhost')
        j = json.loads(r2.content.decode() or '{}')
        obs['C_L4_4_signature_client_au_lien'] = [r2.status_code, j.get('detail'), j.get('code')]
    except Exception as e:
        obs['C_L4_4_signature_client_au_lien'] = repr(e)[:200]
    obs['C_L4_4_apres'] = {'signatures': DevisSignature.objects.filter(devis=d).count(),
                           'nom': DevisSignature.objects.filter(devis=d).values_list('signataire_nom', flat=True).first()}
    cc = obs.get('corps_client') or {}
    repro = bool(obs['signature']['consent_esign'] and cc.get('signature_electronique'))
    return {'repro': repro, 'observe': obs}
