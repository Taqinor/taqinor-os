# flake8: noqa  (sonde de vérification C-L2-4, rejouable par scripts/sonde.py)
"""C-L2-4 — un devis ENVOYÉ re-rendu relit les réglages tarifaires VIFS de la société. Rejeu : lead résidentiel
avec factures, devis par POST atomic/, envoi share-link {envoi:true}, d1 = build_quote_data (le rendu de /proposal,
du PDF public, de la pièce jointe) ; puis Paramètres : TariffSettings.redevance_compteur_mad_mois et
CompanyProfile.productible_kwh_kwc changés ; d2 = build_quote_data du MÊME devis envoyé. On liste les chiffres
client qui ont bougé. Contre-épreuve : /proposal rend toujours (200, %PDF). Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-011", "sha": "1dfa7986c",
         "attendu": "chiffres du devis envoyé inchangés après changement des réglages société (défaut : économies/production/facture changent)",
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
    from apps.ventes.models import Devis
    from apps.ventes.quote_engine.builder import build_quote_data
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 011', slug='sonde-advs-011')
    u = U.objects.create_user(username='sonde-advs-011', password='x', role_legacy='responsable', company=c)
    lead = Lead.objects.create(company=c, nom='Tarif', prenom='Vif', telephone='+212600011011', ville='Casablanca',
                               email='sonde-advs-011@example.invalid', type_installation='residentiel',
                               facture_hiver=Decimal('1500'))
    cl = Client.objects.create(company=c, nom='Tarif', prenom='Vif', email='sonde-advs-011@example.invalid')
    pan = Produit.objects.create(company=c, nom='Panneau Canadien Solar 710W', sku='ADVS011-P',
                                 prix_vente=Decimal('1166.67'), tva=Decimal('20'), quantite_stock=100)
    ond = Produit.objects.create(company=c, nom='Onduleur réseau Huawei 5kW Monophasé', sku='ADVS011-O',
                                 prix_vente=Decimal('9000'), tva=Decimal('20'), quantite_stock=100)
    api = APIClient()
    api.force_authenticate(u)
    obs = {}

    def appel(meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(api, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            brut = r.content if hasattr(r, 'content') else b''.join(r.streaming_content)
            return r.status_code, brut
        except Exception as e:
            return 599, repr(e)[:200].encode()

    s, b = appel('post', '/api/django/ventes/devis/atomic/', {
        'client': cl.id, 'lead': lead.id, 'taux_tva': '20.00',
        'lignes': [{'produit': pan.id, 'designation': pan.nom, 'quantite': '8', 'prix_unitaire': '1166.67', 'taux_tva': '20'},
                   {'produit': ond.id, 'designation': ond.nom, 'quantite': '1', 'prix_unitaire': '9000.00', 'taux_tva': '20'}]})
    obs['atomic'] = [s, b[:160].decode('utf-8', 'replace') if s >= 400 else '']
    dv = Devis.objects.filter(company=c).first()
    if dv is None:
        return {'repro': False, 'observe': obs}
    with mock.patch('apps.ventes.public_views._notify_open'):
        s, _ = appel('post', f'/api/django/ventes/devis/{dv.id}/share-link/', {'envoi': True})
    dv.refresh_from_db()
    obs['envoi'] = [s, dv.statut]

    def aplatir(d, pref='', prof=0, out=None):
        out = {} if out is None else out
        if isinstance(d, dict) and prof < 3:
            for k, v in d.items():
                aplatir(v, f'{pref}{k}.', prof + 1, out)
        elif isinstance(d, (int, float, Decimal)) and not isinstance(d, bool):
            out[pref[:-1]] = float(d)
        elif isinstance(d, str) and any(ch.isdigit() for ch in d) and len(d) < 40:
            out[pref[:-1]] = d
        return out

    with transaction.atomic():
        d1 = aplatir(build_quote_data(Devis.objects.get(pk=dv.pk)))
    ts, _ = TariffSettings.objects.get_or_create(company=c)
    obs['redevance_avant'] = str(ts.redevance_compteur_mad_mois)
    ts.redevance_compteur_mad_mois = Decimal('95.00')
    ts.save()
    prof = CompanyProfile.get(c)
    obs['productible_avant'] = str(prof.productible_kwh_kwc)
    prof.productible_kwh_kwc = 1200
    prof.save()
    with transaction.atomic():
        d2 = aplatir(build_quote_data(Devis.objects.get(pk=dv.pk)))
    mots = ('econom', 'saving', 'product', 'roi', 'payback', 'retour', 'facture', 'bill', 'gain', 'kwh', 'annee', 'an_1')
    diff = {k: [d1.get(k), d2.get(k)] for k in sorted(set(d1) | set(d2))
            if d1.get(k) != d2.get(k) and any(m in k.lower() for m in mots)}
    obs['statut_au_rendu'] = Devis.objects.get(pk=dv.pk).statut
    obs['nb_chiffres_client_changes'] = len(diff)
    obs['changes'] = dict(list(diff.items())[:30])
    s, pdf = appel('get', f'/api/django/ventes/devis/{dv.id}/proposal/')
    obs['proposal_apres'] = [s, pdf[:4].decode('latin-1')]
    return {'repro': bool(diff) and obs['statut_au_rendu'] == 'envoye', 'observe': obs}
