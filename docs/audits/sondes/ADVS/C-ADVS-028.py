# flake8: noqa  (sonde de vérification C-L3-5, rejouable par scripts/sonde.py)
"""C-L3-5 — devis BROUILLON (jamais envoyé) avec un jeton client (`ShareLink.for_devis`, comme le bouton de copie
de lien ou le `proposition_path` d'une gamme sœur brouillon) : `/public/proposal/<t>/data/` et `/pdf/` répondent 404
(ADEV11) ; `/public/document/<t>/` sert-il le PDF chiffré (et compte-t-il une ouverture) ? Jumeau : `/public/suivi/<t>/`.
Rendu réel. Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-028", "sha": "1dfa7986c",
         "attendu": "brouillon au jeton client : 404 sur document/ comme sur proposal/ (défaut : document/ = 200 PDF, vue comptée)",
         "modeles": ["ventes.Devis", "ventes.ShareLink"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis, ShareLink
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 028', slug='sonde-advs-028')
    u = U.objects.create_user(username='sonde-advs-028', password='x', role_legacy='admin', company=c)
    cl = Client.objects.create(company=c, nom='Brouillon', prenom='Jamais', email='sonde-advs-028@example.invalid')
    pan = Produit.objects.create(company=c, nom='Panneau Canadien Solar 710W', sku='ADVS028-P',
                                 prix_vente=Decimal('1166.67'), tva=Decimal('20'), quantite_stock=100)
    ond = Produit.objects.create(company=c, nom='Onduleur réseau Huawei 10kW Monophasé', sku='ADVS028-O',
                                 prix_vente=Decimal('14000'), tva=Decimal('20'), quantite_stock=100)
    d = Devis.objects.create(company=c, reference='DEV-ADVS028-01', client=cl, statut='brouillon',
                             taux_tva=Decimal('20'), created_by=u)
    LigneDevis.objects.create(devis=d, produit=pan, designation=pan.nom, quantite=Decimal('12'),
                              prix_unitaire=pan.prix_vente, remise=Decimal('0'), ordre=0)
    LigneDevis.objects.create(devis=d, produit=ond, designation=ond.nom, quantite=Decimal('1'),
                              prix_unitaire=ond.prix_vente, remise=Decimal('0'), ordre=1)
    link = ShareLink.for_devis(d)
    pub = APIClient()
    obs = {'statut': d.statut, 'ttc': str(d.total_ttc)}
    notes = []
    with mock.patch('apps.ventes.public_views._notify_open', side_effect=lambda *a, **k: notes.append(1)):
        for nom, url in (('data', f'/api/django/public/proposal/{link.token}/data/'),
                         ('pdf', f'/api/django/public/proposal/{link.token}/pdf/'),
                         ('document', f'/api/django/public/document/{link.token}/'),
                         ('suivi', f'/api/django/public/suivi/{link.token}/')):
            try:
                with transaction.atomic():
                    r = pub.get(url, HTTP_HOST='localhost')
                brut = r.content if hasattr(r, 'content') else b''.join(r.streaming_content)
                o = [r.status_code, r.get('Content-Type', '')[:20], brut[:4].decode('latin-1')]
                if nom == 'suivi' and r.status_code == 200:
                    try:
                        j = json.loads(brut.decode() or '{}')
                        o.append(sorted(j.keys())[:20])
                    except Exception:
                        pass
                obs[nom] = o
            except Exception as e:
                obs[nom] = repr(e)[:160]
    link.refresh_from_db()
    obs['view_count'] = link.view_count
    obs['notify_open_appels'] = len(notes)
    doc = obs.get('document')
    repro = bool(isinstance(doc, list) and doc[0] == 200 and doc[2] == '%PDF'
                 and isinstance(obs.get('data'), list) and obs['data'][0] == 404)
    return {'repro': repro, 'observe': obs}
