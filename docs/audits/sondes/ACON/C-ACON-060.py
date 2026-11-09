# flake8: noqa  (sonde d'audit de parcours PA2 « Conception », rejouable par scripts/sonde.py — METHODE §C.4)
"""T1 — « Dupliquer » un calepinage vers un AUTRE lead (cible {lead}, ACAL187, vraie route POST dupliquer) :
la copie emporte-t-elle la CONSOMMATION du client source (courbe 24 h, appareils, saisons), son repère GPS
(pin de la maison de A) et le fond de plan (underlay.attachmentId rattaché à C1) — sans la translation ni la
purge que le MODÈLE applique (D-ACAL-15, `modeles.creer_depuis_modele::preparer`) ?
Témoin : le même C1 marqué modèle, `creer_depuis_modele` vers un lead C (autre repère) ⇒ `consumption` absent,
pin translaté. Lecteurs mesurés : `simulation._declaration_consommation` → `courbe_charge._courbe_de_base`
(source « layout » prioritaire), `repere.etat_derive` sur le repère du lead cible, `plan_importe._piece_du_calepinage`.
Transaction annulée, aucune pile MinIO touchée (Attachment = ligne seule)."""
SONDE = {"constat": "C-ACON-060", "sha": "819fe0f8c",
         "attendu": "repro si la copie vers le lead B porte consumption/pin/underlay de A, que la courbe de base "
                    "simulée de B est celle de A (origine layout) et que le témoin modèle purge + translate",
         "modeles": ["calepinage.Calepinage", "crm.Lead", "records.Attachment"]}


def sonde(ctx):
    import copy
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.records.models import Attachment
    from apps.calepinage.models import Calepinage
    from apps.calepinage.selectors import contexte_geographique
    from apps.calepinage.services.repere import etat_derive, repere_du_lead
    from apps.calepinage.services.simulation import _declaration_consommation
    from apps.calepinage.services.courbe_charge import _courbe_de_base
    from apps.calepinage.services.modeles import marquer_modele, creer_depuis_modele
    from apps.calepinage.views.plan_importe import _piece_du_calepinage
    from apps.ventes.services import layout_hash

    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ACON 060', slug='sonde-acon-060')
    u = get_user_model().objects.create_user(username='sonde_acon_060', password='x',
                                             role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    # Lead A Casablanca, lead B Marrakech (facture 2×), lead C Rabat (témoin modèle)
    la = Lead.objects.create(company=co, nom='A', prenom='Casa', gps_lat=Decimal('33.570000'),
                             gps_lng=Decimal('-7.600000'), facture_hiver=Decimal('600'))
    lb = Lead.objects.create(company=co, nom='B', prenom='Marrakech', gps_lat=Decimal('31.630000'),
                             gps_lng=Decimal('-8.000000'), facture_hiver=Decimal('1200'))
    lc = Lead.objects.create(company=co, nom='C', prenom='Rabat', gps_lat=Decimal('34.020000'),
                             gps_lng=Decimal('-6.840000'), facture_hiver=Decimal('900'))
    courbe_a = [0.4] * 6 + [0.9] * 3 + [0.6] * 8 + [1.4] * 4 + [0.8] * 3   # 18,0 kWh/j
    appareils_a = [{'type': 'clim', 'label': 'Clim salon de A', 'watt': 1500, 'startHour': 13, 'endHour': 17,
                    'source': 'saisi'},
                   {'type': 'pool', 'label': 'Pompe piscine de A', 'watt': 900, 'startHour': 9, 'endHour': 15,
                    'source': 'saisi'},
                   {'type': 'fridge', 'label': 'Frigo de A', 'watt': 150, 'startHour': 0, 'endHour': 24,
                    'source': 'table_atelier'}]
    L = {'scenario': 'reseau', 'panelWatt': 550, 'pinSource': 'lead',
         'pin': {'lat': 33.57, 'lng': -7.60},
         'outline': [[33.5701, -7.6001], [33.5701, -7.5999], [33.5699, -7.5999], [33.5699, -7.6001]],
         'zones': [{'id': 1, 'vertices': [[-7.6001, 33.5701], [-7.5999, 33.5701], [-7.5999, 33.5699],
                                          [-7.6001, 33.5699]],
                    'azimuthDeg': 180, 'tiltDeg': 25, 'count': 10}],
         'consumption': {'methode': 'appareils', 'courbe24': courbe_a, 'appareils': appareils_a,
                         'saisons': {'ete': 1.3, 'hiver': 0.9}, 'source': 'atelier'},
         'billKwh': 540,
         'result': {'panels': 10, 'kwc': 5.5, 'annualKwh': 9100},
         'underlay': {'attachmentId': None, 'calage': {'ancre': [[-7.6001, 33.5701], [-7.5999, 33.5699]],
                                                       'pointsImage': [[0, 0], [800, 600]]}}}
    c1 = Calepinage.objects.create(company=co, lead_id=la.pk, titre='Maison A', roof_layout=L,
                                   layout_hash=layout_hash(L))
    att = Attachment.objects.create(company=co, content_type=ContentType.objects.get_for_model(Calepinage),
                                    object_id=c1.pk, file_key=f'sonde/acon060/{c1.pk}.png',
                                    filename='plan_A.png', size=10, mime='image/png')
    L['underlay']['attachmentId'] = att.pk
    Calepinage.objects.filter(pk=c1.pk).update(roof_layout=L, layout_hash=layout_hash(L))
    c1.refresh_from_db()

    obs = {}
    # (1) vraie route : Dupliquer → cible lead B
    r = api.post(f'/api/django/calepinage/calepinages/{c1.pk}/dupliquer/', {'lead': lb.pk}, format='json', **H)
    obs['dupliquer_http'] = r.status_code
    if r.status_code != 201:
        return {'repro': False, 'dupliquer_http': r.status_code, 'corps': str(r.content[:400])}
    c2 = Calepinage.objects.get(pk=r.data['calepinage'])
    d2 = c2.roof_layout or {}
    obs['copie_lead'] = c2.lead_id == lb.pk
    obs['copie_consumption_identique_A'] = d2.get('consumption') == L['consumption']
    obs['copie_appareils_labels'] = [a.get('label') for a in ((d2.get('consumption') or {}).get('appareils') or [])]
    obs['copie_billKwh'] = d2.get('billKwh')
    obs['copie_pin'] = d2.get('pin')
    obs['copie_result_kwc'] = (d2.get('result') or {}).get('kwc')
    obs['copie_underlay_attachmentId'] = (d2.get('underlay') or {}).get('attachmentId')
    rep_b = repere_du_lead(contexte_geographique(c2))
    der = etat_derive(d2, rep_b)
    obs['repere_lead_B'] = rep_b
    obs['ecart_m_pin_copie_vs_lead_B'] = der.get('ecart_m')
    obs['derive_etat'] = (der.get('derive') or {}).get('etat')
    obs['fond_retrouve_sur_copie'] = _piece_du_calepinage(c2, att.pk) is not None
    obs['fond_retrouve_sur_source'] = _piece_du_calepinage(c1, att.pk) is not None
    # lecteur simulation : déclaration + courbe de base (source prioritaire « layout »)
    decl = _declaration_consommation(d2)
    points = [{'annee': 2025, 'mois': 1 + (h // 744) % 12, 'jour': 1, 'heure': h % 24} for h in range(24 * 30)]
    courbe, origine = _courbe_de_base(points, decl, [])
    obs['simulation_B_origine_courbe'] = origine
    obs['simulation_B_kwh_jour_1'] = round(sum(courbe[:24]), 3) if courbe else None
    obs['courbe_A_kwh_jour'] = round(sum(courbe_a), 3)
    # GET layout (vraie route) — ce que l'atelier de B réhydrate
    g = api.get(f'/api/django/calepinage/calepinages/{c2.pk}/layout/', **H)
    gd = g.data if g.status_code == 200 else {}
    doc_servi = gd.get('roof_layout') if isinstance(gd, dict) and 'roof_layout' in gd else gd
    obs['get_layout_http'] = g.status_code
    obs['get_layout_sert_appareils_A'] = 'Clim salon de A' in str(doc_servi)
    # (2) témoin : C1 marqué modèle → creer_depuis_modele vers lead C
    marquer_modele(c1, user=u)
    c1.refresh_from_db()
    c3 = creer_depuis_modele(c1, user=u, lead_id=lc.pk)
    d3 = c3.roof_layout or {}
    obs['temoin_modele_consumption_absent'] = 'consumption' not in d3
    obs['temoin_modele_pin'] = d3.get('pin')
    obs['temoin_modele_billKwh'] = d3.get('billKwh')
    obs['temoin_modele_result_kwc'] = (d3.get('result') or {}).get('kwc')
    obs['temoin_modele_underlay_attachmentId'] = (d3.get('underlay') or {}).get('attachmentId')
    print(obs)
    pin_c = d3.get('pin') or {}
    temoin_ok = obs['temoin_modele_consumption_absent'] and abs(float(pin_c.get('lat', 0)) - 34.02) < 1e-6
    defaut = (obs['copie_lead'] and obs['copie_consumption_identique_A'] and obs['copie_pin'] == L['pin']
              and obs['simulation_B_origine_courbe'] == 'layout'
              and obs['derive_etat'] not in (None, 'aucune'))
    obs['temoin_ok'] = bool(temoin_ok)
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
