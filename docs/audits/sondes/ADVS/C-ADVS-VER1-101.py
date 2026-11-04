# flake8: noqa  (sonde de contre-visite VER1, rejouable par scripts/sonde.py)
"""C-ADVS-VER1-101 — ADVS1/ADVS2/ADVS7 (D-ADVS-1) : un devis résidentiel ENVOYÉ puis les réglages société changés
(productible 1 200, redevance 120, barème de tranches édité, tarif ONEE) : la PAGE PUBLIQUE `public/proposal/<t>/data/`
(pas seulement build_quote_data / `/proposal`) garde-t-elle ses chiffres client ? Le gel couvre `build_quote_data`
(`etude_chiffrage`), mais `public/payload_horaire.py::conso_publique_du_devis` relit `_reglages_tarifaires(company)`
VIFS (tranches + redevance) pour convertir les factures en kWh. Contre-épreuve : build_quote_data (le /proposal)
reste identique. Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-011", "sha": "06ced8b1a",
         "attendu": "page publique d'un envoyé : chiffres client identiques avant/après changement des réglages société",
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
    from apps.parametres.models import CompanyProfile
    from apps.parametres.models_tariff import TariffSettings
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, ShareLink
    from apps.ventes.quote_engine.builder import build_quote_data
    U = get_user_model()
    c = Company.objects.create(nom='Sonde VER1 101', slug='sonde-ver1-101')
    u = U.objects.create_user(username='sonde-ver1-101', password='x', role_legacy='responsable', company=c)
    lead = Lead.objects.create(company=c, nom='Public', prenom='Vif', telephone='+212600101101', ville='Casablanca',
                               email='sonde-ver1-101@example.invalid', type_installation='residentiel',
                               facture_hiver=Decimal('1500'))
    cl = Client.objects.create(company=c, nom='Public', prenom='Vif', email='sonde-ver1-101@example.invalid')
    pan = Produit.objects.create(company=c, nom='Panneau Canadien Solar 710W', sku='VER1101-P',
                                 prix_vente=Decimal('1166.67'), tva=Decimal('20'), quantite_stock=100)
    ond = Produit.objects.create(company=c, nom='Onduleur réseau Huawei 5kW Monophasé', sku='VER1101-O',
                                 prix_vente=Decimal('9000'), tva=Decimal('20'), quantite_stock=100)
    api, pub = APIClient(), APIClient()
    api.force_authenticate(u)
    obs = {}

    def appel(client, meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(client, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            txt = (r.content if hasattr(r, 'content') else b''.join(r.streaming_content)).decode('utf-8', 'replace')
            try:
                return r.status_code, json.loads(txt)
            except Exception:
                return r.status_code, {}
        except Exception as e:
            return 599, {'err': repr(e)[:200]}

    s, _ = appel(api, 'post', '/api/django/ventes/devis/atomic/', {
        'client': cl.id, 'lead': lead.id, 'taux_tva': '20.00',
        'lignes': [{'produit': pan.id, 'designation': pan.nom, 'quantite': '8', 'prix_unitaire': '1166.67', 'taux_tva': '20'},
                   {'produit': ond.id, 'designation': ond.nom, 'quantite': '1', 'prix_unitaire': '9000.00', 'taux_tva': '20'}]})
    obs['atomic'] = s
    dv = Devis.objects.filter(company=c).first()
    if dv is None:
        return {'repro': False, 'observe': obs}
    with mock.patch('apps.ventes.public_views._notify_open'):
        s, _ = appel(api, 'post', f'/api/django/ventes/devis/{dv.id}/share-link/', {'envoi': True})
    dv = Devis.objects.get(pk=dv.pk)
    obs['envoi'] = [s, dv.statut]
    link = ShareLink.objects.filter(devis=dv, revoque_le__isnull=True).order_by('-id').first()
    if link is None:
        return {'repro': False, 'observe': obs}
    from apps.ventes.domain.reglages_figes_lecture import reglages_figes
    obs['instantane_a_l_envoi'] = bool(reglages_figes(dv))

    def aplatir(d, pref='', out=None, prof=0):
        out = {} if out is None else out
        if isinstance(d, dict) and prof < 6:
            for k, v in d.items():
                aplatir(v, f'{pref}{k}.', out, prof + 1)
        elif isinstance(d, list) and prof < 6:
            for i, v in enumerate(d[:40]):
                aplatir(v, f'{pref}{i}.', out, prof + 1)
        elif isinstance(d, (int, float, Decimal)) and not isinstance(d, bool):
            out[pref[:-1]] = float(d)
        elif isinstance(d, str) and any(ch.isdigit() for ch in d) and len(d) < 60:
            out[pref[:-1]] = d
        return out

    s1, p1 = appel(pub, 'get', f'/api/django/public/proposal/{link.token}/data/')
    d1 = aplatir(p1)
    with transaction.atomic():
        q1 = aplatir(build_quote_data(Devis.objects.get(pk=dv.pk)))

    ts, _ = TariffSettings.objects.get_or_create(company=c)
    ts.redevance_compteur_mad_mois = Decimal('120.00')
    ts.residential_tiers = [{'max_kwh': 100, 'prix_kwh_ttc': '1.50'}, {'max_kwh': 200, 'prix_kwh_ttc': '1.90'},
                            {'max_kwh': None, 'prix_kwh_ttc': '2.80'}]
    ts.save()
    prof = CompanyProfile.get(c)
    prof.productible_kwh_kwc = 1200
    prof.save()
    s2, p2 = appel(pub, 'get', f'/api/django/public/proposal/{link.token}/data/')
    d2 = aplatir(p2)
    with transaction.atomic():
        q2 = aplatir(build_quote_data(Devis.objects.get(pk=dv.pk)))
    obs['public_status'] = [s1, s2]
    diff_pub = {k: [d1.get(k), d2.get(k)] for k in sorted(set(d1) | set(d2)) if d1.get(k) != d2.get(k)}
    diff_q = {k: [q1.get(k), q2.get(k)] for k in sorted(set(q1) | set(q2)) if q1.get(k) != q2.get(k)}
    obs['proposal_data_cles_changees'] = len(diff_q)
    obs['public_cles_changees'] = len(diff_pub)
    obs['public_diff_extrait'] = dict(list(diff_pub.items())[:25])
    obs['proposal_diff_extrait'] = dict(list(diff_q.items())[:10])
    obs['statut_final'] = Devis.objects.get(pk=dv.pk).statut
    return {'repro': bool(diff_pub) and s1 == 200 and s2 == 200 and obs['statut_final'] == 'envoye', 'observe': obs}
