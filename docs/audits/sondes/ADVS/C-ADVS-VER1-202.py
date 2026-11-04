# flake8: noqa  (sonde de vérification ADVS8, contre-visite fraîche, rejouable par scripts/sonde.py)
"""ADVS8 contre-visite — C&I envoyé, client « Karim Exemple » sans ICE, signature AU LIEN PUBLIC avec raison sociale
et ICE ; puis le Client est renommé ET son e-mail changé (le sceau v3 relisait nom|email vivants). Attendu : signature
posée, identité scellée stockée (`client_scelle()` non vide), `verifier_empreinte_signature` intacte en version 4
après le renommage, exemplaire signé rendu (`pret`, `_store_signed_pdf` appelé). `repro: true` = un de ces points
manque. Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-020", "sha": "06ced8b1a",
         "attendu": "sceau intact v4 après renommage nom+email du Client, identité scellée stockée, exemplaire signé rendu",
         "modeles": ["ventes.Devis", "ventes.ShareLink", "ventes.DevisSignature", "crm.Client"]}


def sonde(ctx):
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, DevisSignature, LigneDevis, ShareLink
    from apps.ventes.domain.identite_entreprise import verifier_empreinte_signature
    from apps.ventes.domain.modifiabilite import empreinte_contenu_signable
    from apps.ventes.domain import pdf_signe
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS VER1 202', slug='sonde-advs-ver1-202')
    u = U.objects.create_user(username='sonde-advs-ver1-202', password='x', role_legacy='admin', company=c)
    prods = [Produit.objects.create(company=c, nom=n, sku=f'ADVSV1202-{i}', prix_vente=Decimal(p), tva=Decimal('20'),
                                    quantite_stock=100)
             for i, (n, p) in enumerate((('Panneau Canadien Solar 710W', '1166.67'),
                                         ('Onduleur réseau Huawei 30kW Triphasé', '42000'),
                                         ('Structure aluminium toiture', '300')))]
    cl = Client.objects.create(company=c, nom='Karim Exemple', type_client=Client.TypeClient.ENTREPRISE,
                               raison_sociale_a_confirmer=True, contact_nom='Karim Exemple',
                               email='sonde-advs-ver1-202@example.invalid')
    d = Devis.objects.create(company=c, reference='DEV-ADVSV1202-0001', client=cl, statut='envoye',
                             taux_tva=Decimal('20'), created_by=u, mode_installation='commercial')
    for i, (p, q) in enumerate(zip(prods, ('40', '1', '40'))):
        LigneDevis.objects.create(devis=d, produit=p, designation=p.nom, quantite=Decimal(q),
                                  prix_unitaire=p.prix_vente, remise=Decimal('0'), ordre=i)
    link = ShareLink.objects.create(company=c, devis=d)
    obs = {}
    emp = empreinte_contenu_signable(Devis.objects.get(pk=d.pk), link=link)
    corps = {'nom': 'Karim Exemple', 'consent_esign': True, 'empreinte_contenu': emp,
             'entreprise': {'raison_sociale': 'Boulangerie Exemple SARL', 'signataire_qualite': 'Gérant',
                            'ice': '001234567000089', 'signataire_nom': 'Karim Exemple',
                            'signataire_email': 'karim-v1@example.invalid', 'pouvoir_engager': True}}
    with mock.patch('apps.ventes.public_views._notify_open'):
        with transaction.atomic():
            r = APIClient().post(f'/api/django/public/proposal/{link.token}/accept/', corps, format='json',
                                 HTTP_HOST='localhost')
    obs['http'] = r.status_code
    d2 = Devis.objects.get(pk=d.pk)
    obs['statut'] = d2.statut
    sig = DevisSignature.objects.filter(devis=d2).first()
    if sig is None:
        return {'repro': True, 'observe': dict(obs, signature=False)}
    obs['client_scelle'] = sig.client_scelle()
    obs['client_scelle_vide'] = not sig.client_scelle()
    obs['avant_renommage'] = verifier_empreinte_signature(d2).get('intacte')
    Client.objects.filter(pk=cl.pk).update(nom='BEX', email='nouvelle-adresse@example.invalid')
    d3 = Devis.objects.select_related('client').get(pk=d.pk)
    v = verifier_empreinte_signature(d3)
    obs['apres_renommage'] = [v.get('intacte'), v.get('version')]
    appels = []

    def _stocker(*, devis):
        appels.append(1)
        DevisSignature.objects.filter(devis=devis).update(signed_pdf_key='cle__signe.pdf')
    with mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf', side_effect=_stocker):
        obs['etat_exemplaire'] = pdf_signe.rendre_pdf_signe(d.pk)
    obs['store_appele'] = len(appels)
    ok = (obs['statut'] == 'accepte' and obs['avant_renommage'] is True and obs['apres_renommage'] == [True, 4]
          and not obs['client_scelle_vide'] and obs['etat_exemplaire'] == pdf_signe.PRET and obs['store_appele'] == 1)
    return {'repro': not ok, 'observe': obs}
