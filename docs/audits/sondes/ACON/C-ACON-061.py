# flake8: noqa  (sonde d'audit de parcours PA2 « Conception », rejouable par scripts/sonde.py — METHODE §C.4)
"""T2 — Archiver (vraie route POST archiver) un calepinage SIMULÉ avec ombrage lié à un devis BROUILLON le
DÉTACHE (`services/archivage.py::archiver`, devis=None) : la perte d'ombrage servie au devis tombe à None et le
moteur horaire du devis (ce qu'un enregistrement / envoi rangerait) remonte, sans rien côté devis
(`build_quote_data(D)['layout_stale']`, chatter du devis). Puis : (a) restauration immédiate ⇒ l'ombrage revient
(seconde variation) ; (b) archivage, ouverture 3D du devis (`creation.adopter_ou_creer_pour_devis`) puis
restauration ⇒ 409 (RestaurationEnConflit) et D porte une conception neuve sans simulation.
Même montage que C-ACON-020 (météo rejouée `_ClientParOrientation`, fiches module/onduleur injectées). Aucun
`rafraichir_etudes_du_devis` (cf. C-ACON-020-L2). Transaction annulée."""
SONDE = {"constat": "C-ACON-061", "sha": "819fe0f8c",
         "attendu": "repro si archiver = 200 sur le calepinage d'un brouillon simulé, perte d'ombrage du devis > 0 puis None, "
                    "production horaire du devis qui monte, layout_stale faux, aucune ligne au chatter du devis",
         "modeles": ["ventes.Devis", "calepinage.Calepinage", "records.Activity"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.records.models import Activity
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    from apps.calepinage.models import Calepinage
    from apps.calepinage.services.liens import lier_devis
    from apps.calepinage.services.simulation import simuler_calepinage
    from apps.calepinage.services.creation import adopter_ou_creer_pour_devis
    from apps.calepinage.selectors import calepinage_du_devis
    from apps.calepinage.tests.test_acal_multi_pans import _ClientParOrientation, _layout, _zone
    from apps.calepinage.tests.test_calx5_simulation import MATERIEL, REGLAGES
    from apps.ventes.horaire.ombrage import perte_ombrage_du_devis
    from apps.ventes.etude_horaire import etude_horaire_pour_devis
    from apps.ventes.quote_engine.builder import build_quote_data
    import copy

    H = {'HTTP_HOST': 'localhost'}
    patch_mat = mock.patch('apps.calepinage.services.electrique.resoudre_materiel', return_value=MATERIEL)
    patch_mat.start()
    obs = {}
    try:
        co = Company.objects.create(nom='Sonde ACON 061', slug='sonde-acon-061')
        u = get_user_model().objects.create_user(username='sonde_acon_061', password='x',
                                                 role_legacy='admin', company=co)
        api = APIClient()
        api.force_authenticate(u)
        sim0 = copy.deepcopy(REGLAGES['simulation'])
        for _v in sim0.values():
            _v['source'] = 'societe'
        r = api.put('/api/django/calepinage/parametres/', {'simulation': sim0}, format='json', **H)
        if r.status_code != 200:
            return 'PUT reglages refuse : %s %s' % (r.status_code, r.content[:300])
        cl = Client.objects.create(company=co, nom='Client T2')
        lead_kw = dict(company=co, nom='Lead T2', facture_hiver=Decimal('900'))
        if any(f.name == 'ville' for f in Lead._meta.fields):
            lead_kw['ville'] = 'Casablanca'
        lead = Lead.objects.create(**lead_kw)
        d = Devis.objects.create(company=co, reference='DEV-T2-01', client=cl, lead=lead,
                                 taux_tva=Decimal('20'), statut='brouillon', created_by=u,
                                 mode_installation='residentiel',
                                 etude_params={'factures_mensuelles_reelles': [900] * 12,
                                               'distributeur': 'onee', 'ville': 'casablanca'})
        for i, (nom, qte, pu) in enumerate((('Panneau Canadien Solar 710W', '8', '1166.67'),
                                            ('Onduleur réseau Huawei 5kW Monophasé', '1', '9000.00'))):
            p = Produit.objects.create(company=co, nom=nom, sku=f't2-{i}', prix_vente=Decimal(pu), quantite_stock=50)
            LigneDevis.objects.create(devis=d, produit=p, designation=nom, quantite=Decimal(qte),
                                      prix_unitaire=Decimal(pu), remise=Decimal('0'), ordre=i)
        layout = _layout(_zone(1, 16, 90.0), _zone(2, 8, 270.0))
        for zone in layout['zones']:
            zone['geometry']['solarAccess'] = {
                'values': [0.9] * zone['geometry']['count'],
                'method': {'horizon': False, 'rangees': False, 'resolution': 'annuelle',
                           'description': 'Accès solaire annuel'},
                'assumptions': {'periode': 'annee'}, 'computedAt': '2026-10-01T10:00:00Z'}
        c = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='T2', roof_layout=layout)
        lier_devis(c, d.pk)
        simuler_calepinage(c, client=_ClientParOrientation(), materiel=MATERIEL, enregistrer=True)
        ct_devis = ContentType.objects.get_for_model(Devis)

        def mesurer():
            from django.db import transaction as _tx
            with _tx.atomic():
                m = _mesurer()
                _tx.set_rollback(True)
            m['perte_apres_rollback_mesure'] = perte_ombrage_du_devis(Devis.objects.get(pk=d.pk))
            return m

        def _mesurer():
            from django.db import transaction as _tx
            dd = Devis.objects.get(pk=d.pk)
            perte = perte_ombrage_du_devis(dd)
            bloc = etude_horaire_pour_devis(dd, kwc=5.68)
            lie = calepinage_du_devis(dd.pk, co)
            perte_apres_horaire = perte_ombrage_du_devis(Devis.objects.get(pk=d.pk))
            # build_quote_data dans un savepoint annulé : ses écritures éventuelles ne faussent pas la suite
            with _tx.atomic():
                try:
                    stale = build_quote_data(Devis.objects.get(pk=d.pk)).get('layout_stale')
                except Exception as exc:  # noqa
                    stale = f'err {exc!r}'[:100]
                perte_apres_build = perte_ombrage_du_devis(Devis.objects.get(pk=d.pk))
                _tx.set_rollback(True)
            return {'statut_devis': dd.statut,
                    'perte_ombrage_pct': perte,
                    'perte_apres_horaire': perte_apres_horaire,
                    'perte_apres_build_quote_data_savepoint': perte_apres_build,
                    'perte_apres_rollback': perte_ombrage_du_devis(Devis.objects.get(pk=d.pk)),
                    'horaire_production_kwh': ((bloc or {}).get('annuel') or {}).get('production_kwh'),
                    'calepinage_du_devis': getattr(lie, 'pk', None),
                    'layout_stale': stale,
                    'chatter_devis': Activity.objects.filter(content_type=ct_devis, object_id=dd.pk).count()}

        m0 = mesurer()
        det = api.get(f'/api/django/calepinage/calepinages/{c.pk}/', **H)
        obs['detail_peut_supprimer'] = (det.data.get('permissions') or {}).get('peut_supprimer') if det.status_code == 200 else det.status_code
        ra = api.post(f'/api/django/calepinage/calepinages/{c.pk}/archiver/', {}, format='json', **H)
        obs['archiver_http'] = ra.status_code
        c.refresh_from_db()
        obs['apres_archivage_devis_id_du_calepinage'] = c.devis_id
        m1 = mesurer()
        # (a) restauration immédiate
        rr = api.post(f'/api/django/calepinage/calepinages/{c.pk}/restaurer-corbeille/', {}, format='json', **H)
        obs['restaurer_immediat_http'] = rr.status_code
        m2 = mesurer()
        # (b) re-archivage, ouverture 3D du devis, restauration
        ra2 = api.post(f'/api/django/calepinage/calepinages/{c.pk}/archiver/', {}, format='json', **H)
        obs['archiver_2_http'] = ra2.status_code
        neuf, origine = adopter_ou_creer_pour_devis(d.pk, co, user=u)
        obs['ouverture_3d_origine'] = origine
        obs['ouverture_3d_calepinage'] = neuf.pk
        obs['ouverture_3d_a_simulation'] = bool((neuf.resultat or {}).get('simulation'))
        rr2 = api.post(f'/api/django/calepinage/calepinages/{c.pk}/restaurer-corbeille/', {}, format='json', **H)
        obs['restaurer_apres_3d_http'] = rr2.status_code
        obs['restaurer_apres_3d_corps'] = str(rr2.content[:240])
        m3 = mesurer()
        c.refresh_from_db()
        obs['C_reste_archive'] = c.archive_le is not None
        obs['m0_lie_simule'] = m0
        obs['m1_apres_archivage'] = m1
        obs['m2_apres_restauration'] = m2
        obs['m3_apres_3d_et_restauration'] = m3
        p0, p1 = m0['perte_ombrage_pct'], m1['perte_ombrage_pct']
        h0, h1 = m0['horaire_production_kwh'], m1['horaire_production_kwh']
        obs['ecart_production_pct'] = (round((h1 - h0) / h0 * 100, 2) if h0 and h1 else None)
        obs['repro'] = bool(ra.status_code == 200 and p0 and p0 > 0 and p1 is None and h0 and h1 and h1 > h0
                            and m1['layout_stale'] is False
                            and m1['chatter_devis'] == m0['chatter_devis'])
    finally:
        patch_mat.stop()
    print(json.dumps(obs, default=str, ensure_ascii=False)[:5000])
    return obs
