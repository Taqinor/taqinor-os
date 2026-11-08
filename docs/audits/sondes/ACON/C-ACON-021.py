# flake8: noqa  (sonde d'audit PA2 « Conception », rejouable par scripts/sonde.py — METHODE §C.4)
"""K21 — devis D (8 panneaux, instantané = conception H1 de C, 8 modules peu ombrés) ; dans l'atelier on
ajoute un pan de 8 modules très ombrés (enregistrer_layout = service de PUT layout) et on simule (vraie
chaîne, météo rejouée) SANS resynchroniser D. Question : la perte d'ombrage servie au devis est-elle
celle de la conception H2 (16 modules) qu'il ne chiffre pas, alors que le prédicat de divergence
(ACAL46, celui qui retire la planche du PDF) dit « divergé » ? Lecture client : proposition publique
(vraie route) `dimensionnement_options.sans.production_annuelle_kwh`. Transaction annulée."""
SONDE = {"constat": "C-ACON-021", "sha": "33cba7f5d",
         "attendu": "repro si conception divergente (planche retiree) ET perte_ombrage_du_devis = perte de H2 (!= H1) appliquee a la production client",
         "modeles": ["ventes.Devis", "calepinage.Calepinage"]}


def sonde(ctx):
    import copy
    import json
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis, ShareLink
    from apps.calepinage.models import Calepinage
    from apps.calepinage.selectors import ombrage_servi
    from apps.calepinage.services.liens import lier_devis
    from apps.calepinage.services.layout import enregistrer_layout
    from apps.calepinage.services.simulation import simuler_calepinage
    from apps.calepinage.tests.test_acal_multi_pans import _ClientParOrientation, _layout, _zone
    from apps.calepinage.tests.test_calx5_simulation import MATERIEL, REGLAGES
    from apps.ventes.horaire.ombrage import perte_ombrage_du_devis
    from apps.ventes.etude_horaire import etude_horaire_pour_devis
    from apps.ventes.domain.geometrie import layout_hash
    from apps.ventes.quote_engine.artefacts_rendu import _conception_divergente_du_devis

    H = {'HTTP_HOST': 'localhost'}
    patch_mat = mock.patch('apps.calepinage.services.electrique.resoudre_materiel', return_value=MATERIEL)
    patch_mat.start()
    obs = {}
    try:
        co = Company.objects.create(nom='Sonde ACON 021', slug='sonde-acon-021')
        u = get_user_model().objects.create_user(username='sonde_acon_021', password='x',
                                                 role_legacy='admin', company=co)
        api = APIClient()
        api.force_authenticate(u)
        sim0 = copy.deepcopy(REGLAGES['simulation'])
        for _v in sim0.values():
            _v['source'] = 'societe'
        obs['put_reglages'] = api.put('/api/django/calepinage/parametres/', {'simulation': sim0},
                                      format='json', **H).status_code
        cl = Client.objects.create(company=co, nom='Client K21')
        lead_kw = dict(company=co, nom='Lead K21', facture_hiver=Decimal('900'))
        if any(f.name == 'ville' for f in Lead._meta.fields):
            lead_kw['ville'] = 'Casablanca'
        lead = Lead.objects.create(**lead_kw)
        d = Devis.objects.create(company=co, reference='DEV-K21-01', client=cl, lead=lead,
                                 taux_tva=Decimal('20'), statut='brouillon', created_by=u,
                                 mode_installation='residentiel',
                                 etude_params={'factures_mensuelles_reelles': [900] * 12,
                                               'distributeur': 'onee', 'ville': 'casablanca'})
        for i, (nom, qte, pu) in enumerate((('Panneau Canadien Solar 710W', '8', '1166.67'),
                                            ('Onduleur réseau Huawei 5kW Monophasé', '1', '9000.00'))):
            p = Produit.objects.create(company=co, nom=nom, sku=f'k21-{i}', prix_vente=Decimal(pu),
                                       quantite_stock=50)
            LigneDevis.objects.create(devis=d, produit=p, designation=nom, quantite=Decimal(qte),
                                      prix_unitaire=Decimal(pu), remise=Decimal('0'), ordre=i)

        def acces(zone, v):
            zone['geometry']['solarAccess'] = {
                'values': [v] * zone['geometry']['count'],
                'method': {'horizon': False, 'rangees': False, 'resolution': 'annuelle',
                           'description': 'Accès solaire annuel'},
                'assumptions': {'periode': 'annee'}, 'computedAt': '2026-10-01T10:00:00Z'}
            return zone

        h1 = _layout(acces(_zone(1, 8, 180.0), 0.96))
        c = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='K21', roof_layout=copy.deepcopy(h1))
        lier_devis(c, d.pk)
        simuler_calepinage(c, client=_ClientParOrientation(), materiel=MATERIEL, enregistrer=True)
        c.refresh_from_db()
        # instantané du devis = conception H1 (ce que generer/resynchroniser posent)
        Devis.objects.filter(pk=d.pk).update(roof_layout=copy.deepcopy(c.roof_layout),
                                             layout_hash=layout_hash(c.roof_layout))
        d = Devis.objects.get(pk=d.pk)
        link = ShareLink.objects.create(company=co, devis=d)

        def lecture(tag):
            dd = Devis.objects.get(pk=d.pk)
            cc = Calepinage.objects.get(pk=c.pk)
            servi = ombrage_servi(dd.pk, co) or {}
            with mock.patch('apps.ventes.public_views._notify_open'):
                rp = APIClient().get(f'/api/django/public/proposal/{link.token}/data/', **H)
            j = rp.json() if rp.status_code == 200 else {}
            return {'devis_layout_hash': (dd.layout_hash or '')[:10],
                    'calepinage_layout_hash': (cc.layout_hash or layout_hash(cc.roof_layout) or '')[:10],
                    'modules_calepinage': sum(z['geometry']['count'] for z in cc.roof_layout['zones']),
                    'conception_divergente_ACAL46': _conception_divergente_du_devis(dd),
                    'ombrage_servi_perime': servi.get('perime'), 'ombrage_servi_global': servi.get('global'),
                    'perte_ombrage_du_devis': perte_ombrage_du_devis(dd),
                    'horaire_devis_production_kwh_5_68kwc': ((etude_horaire_pour_devis(dd, kwc=5.68) or {}).get('annuel') or {}).get('production_kwh'),
                    'public_http': rp.status_code,
                    'public_layout_stale': j.get('layout_stale'),
                    'public_production_annuelle_sans': ((j.get('dimensionnement_options') or {}).get('sans') or {}).get('production_annuelle_kwh'),
                    'public_kwc_sans': ((j.get('dimensionnement_options') or {}).get('sans') or {}).get('puissance_kwc')}

        obs['h1'] = lecture('h1')
        # atelier : + 8 modules sous un arbre, sans resynchroniser le devis
        h2 = copy.deepcopy(c.roof_layout)
        h2['zones'].append(acces(_zone(2, 8, 180.0), 0.55))
        enregistrer_layout(c, h2, user=u, libelle='ajout pan ombré')
        c.refresh_from_db()
        simuler_calepinage(c, client=_ClientParOrientation(), materiel=MATERIEL, enregistrer=True)
        obs['h2'] = lecture('h2')
        a, b = obs['h1'], obs['h2']
        obs['repro'] = bool(b['conception_divergente_ACAL46'] and b['ombrage_servi_perime'] is False
                            and a['perte_ombrage_du_devis'] is not None and b['perte_ombrage_du_devis'] is not None
                            and b['perte_ombrage_du_devis'] > a['perte_ombrage_du_devis'] + 1)
    finally:
        patch_mat.stop()
    print(json.dumps(obs, default=str, ensure_ascii=False))
    return {'repro': obs.get('repro', False)}
