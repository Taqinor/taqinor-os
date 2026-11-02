# flake8: noqa  (sonde de vérification C-L1-5, rejouable par scripts/sonde.py)
"""C-L1-5 — `electrical_design`, `electrical_design_hash`, `pdf_render_meta` écrivables bruts par PATCH
/ventes/devis/<id>/ (absents de DevisWriteSerializer.read_only_fields). Rejeu : brouillon créé par atomic/,
PATCH d'une conception forgée (protection « QF-SONDE 999 A ») + d'un pdf_render_meta forgé ; relecture en base ;
envoi share-link {envoi} puis page publique data : le repère forgé y est-il servi au client ?
Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-005", "sha": "1dfa7986c",
         "attendu": "PATCH electrical_design / pdf_render_meta ignorés (lecture seule) ; rien de forgé sur la page publique",
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
    from apps.ventes.models import Devis, ShareLink
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 005', slug='sonde-advs-005')
    u = U.objects.create_user(username='sonde-advs-005', password='x', role_legacy='responsable', company=c)
    cl = Client.objects.create(company=c, nom='Forge', prenom='SLD', email='sonde-advs-005@example.invalid')
    pan = Produit.objects.create(company=c, nom='Panneau Canadien Solar 710W', sku='ADVS005-P',
                                 prix_vente=Decimal('1166.67'), tva=Decimal('20'), quantite_stock=100)
    ond = Produit.objects.create(company=c, nom='Onduleur réseau Huawei 10kW Monophasé', sku='ADVS005-O',
                                 prix_vente=Decimal('14000'), tva=Decimal('20'), quantite_stock=100)
    api, pub = APIClient(), APIClient()
    api.force_authenticate(u)
    obs = {}

    def appel(client, meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(client, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            txt = r.content.decode('utf-8', 'replace')
            try:
                return r.status_code, json.loads(txt), txt
            except Exception:
                return r.status_code, {}, txt
        except Exception as e:
            return 599, {'_exc': repr(e)[:300]}, ''

    s, _, _ = appel(api, 'post', '/api/django/ventes/devis/atomic/', {
        'client': cl.id, 'taux_tva': '20.00',
        'lignes': [{'produit': pan.id, 'designation': pan.nom, 'quantite': '12', 'prix_unitaire': '1166.67', 'taux_tva': '20'},
                   {'produit': ond.id, 'designation': ond.nom, 'quantite': '1', 'prix_unitaire': '14000.00', 'taux_tva': '20'}]})
    dv = Devis.objects.filter(company=c).first()
    obs['atomic'] = s
    if dv is None:
        return {'repro': False, 'observe': obs}
    obs['design_avant'] = bool(dv.electrical_design)
    forge = {'chaines': [{'pan': 'Pan forgé', 'mppt': 9, 'nb_modules': 99}],
             'protections': [{'repere': 'QF-SONDE', 'designation': 'Disjoncteur forgé', 'calibre': '999 A',
                              'quantite': 1, 'cote': 'ac'}],
             'cables': [{'liaison': 'Liaison forgée', 'section_mm2': 1, 'longueur_m': 1}]}
    s, r, _ = appel(api, 'patch', f'/api/django/ventes/devis/{dv.id}/',
                    {'electrical_design': forge, 'electrical_design_hash': 'forge-sonde',
                     'pdf_render_meta': {'options': {'pdf_mode': 'onepage'}, 'cle': 'forge'}})
    obs['patch'] = [s, str(r)[:200] if s >= 400 else '']
    dv.refresh_from_db()
    obs['base_apres_patch'] = {
        'electrical_design_forge': (dv.electrical_design or {}).get('protections', [{}])[0].get('repere')
        if isinstance(dv.electrical_design, dict) and dv.electrical_design.get('protections') else None,
        'electrical_design_hash': dv.electrical_design_hash,
        'pdf_render_meta': dv.pdf_render_meta}
    with mock.patch('apps.ventes.public_views._notify_open'):
        s, _, _ = appel(api, 'post', f'/api/django/ventes/devis/{dv.id}/share-link/', {'envoi': True})
        obs['envoi'] = s
        dv.refresh_from_db()
        obs['statut'] = dv.statut
        obs['design_apres_envoi'] = (dv.electrical_design or {}).get('protections', [{}])[0].get('repere') \
            if isinstance(dv.electrical_design, dict) and dv.electrical_design.get('protections') else None
        link = ShareLink.objects.filter(devis=dv, revoque_le__isnull=True).order_by('-id').first()
        if link is not None:
            s, lu, txt = appel(pub, 'get', f'/api/django/public/proposal/{link.token}/data/')
            obs['public_data'] = s
            obs['public_porte_forge'] = 'QF-SONDE' in txt
            obs['public_999A'] = '999 A' in txt
    repro = obs['base_apres_patch']['electrical_design_forge'] == 'QF-SONDE'
    return {'repro': repro, 'observe': obs}
