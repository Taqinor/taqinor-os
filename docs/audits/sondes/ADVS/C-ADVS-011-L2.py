# flake8: noqa  (sonde seconde lentille, rejouable par scripts/sonde.py — AMET93)
"""C-ADVS-011 — LENTILLE 2 (reproduction indépendante). Autre levier que le productible : le BARÈME
résidentiel réglé par la société (``TariffSettings.residential_tiers``, Paramètres → Tarification & ROI)
+ la redevance compteur. Autre chemin : la page publique (``/public/proposal/<jeton>/data/`` → ``quote``)
ET ``build_quote_data`` (données du PDF ``/proposal``). Devis résidentiel ONEE à conso déclarée, ENVOYÉ par
l'API (share-link envoi), lu une fois, puis la société change son barème ; relecture : les économies /
retour imprimés pour ce devis déjà envoyé changent-ils ? Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-011", "sha": "1dfa7986c",
         "attendu": "devis envoyé : eco_s_ann / roi_s / facture_sans_solaire identiques avant et après le changement de barème société",
         "modeles": ["ventes.Devis", "ventes.ShareLink", "parametres.TariffSettings"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, ShareLink
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 011 L2', slug='sonde-advs-011-l2')
    u = U.objects.create_user(username='sonde-advs-011-l2', password='x', role_legacy='admin', company=c)
    lead = Lead.objects.create(company=c, nom='Barème', prenom='L2', telephone='+212600011200',
                               ville='Marrakech', email='sonde-advs-011-l2@example.invalid')
    cl = Client.objects.create(company=c, nom='Barème', prenom='L2', email='sonde-advs-011-l2@example.invalid')
    pan = Produit.objects.create(company=c, nom='Panneau JA Solar 550W', sku='ADVS011L2-P',
                                 prix_vente=Decimal('1100'), prix_achat=Decimal('650'), quantite_stock=100)
    ond = Produit.objects.create(company=c, nom='Onduleur réseau Huawei 5kW Monophasé', sku='ADVS011L2-O',
                                 prix_vente=Decimal('9000'), prix_achat=Decimal('6000'), quantite_stock=100)
    api, pub = APIClient(), APIClient()
    api.force_authenticate(u)
    etapes = []

    def appel(nom, client, meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(client, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
        except Exception as e:
            etapes.append((nom, 599, repr(e)[:300]))
            return 599, {}
        brut = r.content if hasattr(r, 'content') else b''.join(r.streaming_content)
        etapes.append((nom, r.status_code, '' if r.status_code < 400 else brut[:200].decode('utf-8', 'replace')))
        try:
            return r.status_code, json.loads(brut.decode('utf-8'))
        except Exception:
            return r.status_code, {}

    etude = {'conso_annuelle': 7200, 'distributeur': 'onee'}
    appel('atomic', api, 'post', '/api/django/ventes/devis/atomic/', {
        'client': cl.id, 'lead': lead.id, 'statut': 'brouillon', 'taux_tva': '20.00',
        'mode_installation': 'residentiel', 'etude_params': etude,
        'lignes': [{'produit': pan.id, 'designation': 'Panneau JA Solar 550W', 'quantite': '10',
                    'prix_unitaire': '1100', 'taux_tva': '20'},
                   {'produit': ond.id, 'designation': 'Onduleur réseau Huawei 5kW Monophasé', 'quantite': '1',
                    'prix_unitaire': '9000', 'taux_tva': '20'}]})
    dv = Devis.objects.filter(company=c).first()
    obs = {'etapes': etapes}
    if dv is None:
        return {'repro': False, 'observe': obs}
    ep = dict(dv.etude_params or {})
    if not ep.get('conso_annuelle'):
        ep.update(etude)
        Devis.objects.filter(pk=dv.pk).update(etude_params=ep)
    from apps.ventes.quote_engine.builder import build_quote_data
    CLES = ('prod_kwh', 'eco_s_ann', 'eco_a_ann', 'roi_s', 'roi_a', 'facture_sans_solaire',
            'facture_avec_solaire_s', 'savings_model')

    def extrait(d):
        return {k: (d or {}).get(k) for k in CLES}

    with mock.patch('apps.ventes.public_views._notify_open'):
        appel('share-link envoi', api, 'post', f'/api/django/ventes/devis/{dv.id}/share-link/', {'envoi': True})
        dv.refresh_from_db()
        obs['statut'] = dv.statut
        obs['regles_calcul'] = getattr(dv, 'regles_calcul', None)
        link = ShareLink.objects.filter(devis=dv, revoque_le__isnull=True).order_by('-id').first()
        avant_pdf = extrait(build_quote_data(Devis.objects.get(pk=dv.pk)))
        avant_pub = {}
        if link is not None:
            _, lu = appel('public data avant', pub, 'get', f'/api/django/public/proposal/{link.token}/data/')
            avant_pub = extrait(lu.get('quote'))
            obs['empreinte_avant'] = lu.get('empreinte_contenu')
        # La société change son barème APRÈS l'envoi (geste d'écran Paramètres → Tarification & ROI).
        from apps.parametres.models_tariff import TariffSettings, DEFAULT_RESIDENTIAL_TIERS
        ts = TariffSettings.get(company=c)
        ts.residential_tiers = [{'max_kwh': t['max_kwh'],
                                 'prix_kwh_ttc': str((Decimal(t['prix_kwh_ttc']) * Decimal('1.5')).quantize(Decimal('0.000001')))}
                                for t in DEFAULT_RESIDENTIAL_TIERS]
        ts.redevance_compteur_mad_mois = Decimal('60.00')
        ts.save()
        apres_pdf = extrait(build_quote_data(Devis.objects.get(pk=dv.pk)))
        apres_pub = {}
        if link is not None:
            _, lu2 = appel('public data après', pub, 'get', f'/api/django/public/proposal/{link.token}/data/')
            apres_pub = extrait(lu2.get('quote'))
            obs['empreinte_apres'] = lu2.get('empreinte_contenu')
    diff_pdf = {k: [avant_pdf[k], apres_pdf[k]] for k in CLES if avant_pdf[k] != apres_pdf[k]}
    diff_pub = {k: [avant_pub.get(k), apres_pub.get(k)] for k in CLES if avant_pub.get(k) != apres_pub.get(k)}
    obs.update(avant_pdf=avant_pdf, diff_pdf=diff_pdf, diff_public=diff_pub,
               empreinte_inchangee=obs.get('empreinte_avant') == obs.get('empreinte_apres'))
    repro = dv.statut == 'envoye' and bool(diff_pdf or diff_pub)
    return {'repro': repro, 'observe': obs}
