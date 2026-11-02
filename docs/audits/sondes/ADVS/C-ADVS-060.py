# flake8: noqa  (sonde d'audit, rejouable par scripts/sonde.py — AMET93)
"""C-ADVS-060 — PA3-03/04 (C1) : la FICHE PRODUIT (garantie, garantie_mois, description, marque) est relue
VIVANTE sur `stock.Produit` à chaque rendu d'un devis ENVOYÉ (`quote_engine/lignes_classement.py` l. 284-293
→ `build_quote_data`, données du PDF `/proposal` ET du PDF public re-rendu à chaque GET, `persist=False`, ET
de la charge publique `quote.*_items[].garantie(_mois)`). Rien n'est figé à l'envoi (`geler_document_engage`
fige marge, CGV, barème — pas la fiche) et l'empreinte signable (`modifiabilite._CHAMPS_LIGNE_VISIBLES`) ne
couvre pas la garantie : le client qui a reçu « Garantie 25 ans » relit « 10 ans » après une retouche du
catalogue, et SIGNE sans 409 `empreinte_perimee`. Jumeau de C-ADVS-011 (réglages société vivants) sur une
autre ancre (catalogue stock). `_octets_pdf_signe` (QJR670) protège l'ACCEPTÉ « d'une évolution d'une fiche
produit » — l'envoyé, non. Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-060", "sha": "1dfa7986c",
         "attendu": "garantie imprimée/servie après l'envoi = celle de l'envoi (ou 409 empreinte_perimee à la signature)",
         "modeles": ["ventes.Devis", "ventes.ShareLink", "ventes.DevisSignature", "stock.Produit"]}


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
    from apps.ventes.models import Devis, DevisSignature, ShareLink
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 060', slug='sonde-advs-060')
    u = U.objects.create_user(username='sonde-advs-060', password='x', role_legacy='admin', company=c)
    lead = Lead.objects.create(company=c, nom='Fiche', prenom='Vivante', telephone='+212600006000',
                               ville='Casablanca', email='sonde-advs-060@example.invalid')
    cl = Client.objects.create(company=c, nom='Fiche', prenom='Vivante', email='sonde-advs-060@example.invalid')
    G1, G2 = 'Garantie produit 25 ans', 'Garantie produit 10 ans'
    D1, D2 = 'Module bifacial 710 Wc, verre-verre', 'Module monofacial 710 Wc'
    pan = Produit.objects.create(company=c, nom='Panneau Canadien Solar 710W', sku='ADVS060-P',
                                 prix_vente=Decimal('1166.67'), prix_achat=Decimal('700'), quantite_stock=100,
                                 marque='Canadian Solar', description=D1, garantie=G1, garantie_mois=300)
    ond = Produit.objects.create(company=c, nom='Onduleur réseau Huawei 10kW Monophasé', sku='ADVS060-O',
                                 prix_vente=Decimal('14000'), prix_achat=Decimal('9000'), quantite_stock=100,
                                 marque='Huawei', garantie='Garantie 10 ans', garantie_mois=120)
    api, pub = APIClient(), APIClient()
    api.force_authenticate(u)
    etapes = []

    def appel(nom, client, meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(client, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
        except Exception as e:
            import traceback
            etapes.append((nom, 599, ''.join(traceback.format_exception_only(type(e), e))[:300]))
            return 599, {}
        txt = (r.content if hasattr(r, 'content') else b''.join(r.streaming_content)).decode('utf-8', 'replace')
        etapes.append((nom, r.status_code, '' if r.status_code < 400 else txt[:200]))
        try:
            return r.status_code, json.loads(txt)
        except Exception:
            return r.status_code, {}

    def fiche_pdf(dv):
        """Ce que le moteur imprime pour le panneau : (garantie, garantie_mois, description, marque)."""
        from apps.ventes.quote_engine.builder import build_quote_data
        data = build_quote_data(dv, {'pdf_mode': 'full'})
        for it in _items(data):
            if 'panneau' in (it.get('designation') or '').lower():
                return (it.get('garantie'), it.get('garantie_mois'), it.get('description'), it.get('marque'))
        return ('?', '?', '?', '?')

    def _items(bloc):
        out = []
        if not isinstance(bloc, dict):
            return out
        for k, v in bloc.items():
            if isinstance(v, list) and v and isinstance(v[0], dict) and 'designation' in v[0]:
                out.extend(v)
        return out

    def fiche_public(lu):
        quote = lu.get('quote') or {}
        for it in _items(quote) + _items(lu):
            if 'panneau' in (it.get('designation') or '').lower():
                return (it.get('garantie'), it.get('garantie_mois'), it.get('description'), it.get('marque'))
        return ('?', '?', '?', '?')

    s, cree = appel('atomic', api, 'post', '/api/django/ventes/devis/atomic/', {
        'client': cl.id, 'lead': lead.id, 'statut': 'brouillon', 'taux_tva': '20.00',
        'lignes': [{'produit': pan.id, 'designation': 'Panneau Canadien Solar 710W', 'quantite': '12',
                    'prix_unitaire': '1166.67', 'taux_tva': '20'},
                   {'produit': ond.id, 'designation': 'Onduleur réseau Huawei 10kW Monophasé', 'quantite': '1',
                    'prix_unitaire': '14000.00', 'taux_tva': '20'}]})
    obs = {'etapes': etapes}
    dv = Devis.objects.filter(company=c).first()
    if not dv:
        return {'repro': False, 'observe': obs}
    with mock.patch('apps.ventes.public_views._notify_open'), \
            mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf'):
        appel('share-link envoi', api, 'post', f'/api/django/ventes/devis/{dv.id}/share-link/', {'envoi': True})
        dv.refresh_from_db()
        obs['statut_apres_envoi'] = dv.statut
        link = ShareLink.objects.filter(devis=dv, revoque_le__isnull=True).order_by('-id').first()
        if link is None:
            return {'repro': False, 'observe': obs}
        # 1. ce que le client a REÇU (PDF moteur + page publique) à l'envoi
        obs['pdf_envoi'] = fiche_pdf(dv)
        s, lu1 = appel('public data (envoi)', pub, 'get', f'/api/django/public/proposal/{link.token}/data/')
        obs['public_envoi'] = fiche_public(lu1)
        empreinte_envoi = lu1.get('empreinte_contenu')
        # 2. le catalogue est retouché APRÈS l'envoi (geste stock ordinaire, aucun geste sur le devis)
        Produit.objects.filter(pk=pan.pk).update(garantie=G2, garantie_mois=120, description=D2, marque='Canadian Solar (v2)')
        dv = Devis.objects.get(pk=dv.pk)
        obs['pdf_apres'] = fiche_pdf(dv)
        s, lu2 = appel('public data (après retouche)', pub, 'get', f'/api/django/public/proposal/{link.token}/data/')
        obs['public_apres'] = fiche_public(lu2)
        obs['empreinte_envoi'] = (empreinte_envoi or '')[:12]
        obs['empreinte_apres'] = (lu2.get('empreinte_contenu') or '')[:12]
        obs['statut_devis'] = Devis.objects.get(pk=dv.pk).statut
        # 3. le client signe avec l'empreinte LUE À L'ENVOI (page gardée ouverte)
        s_sig, r_sig = appel('signature (empreinte de l\'envoi)', pub, 'post',
                             f'/api/django/public/proposal/{link.token}/accept/',
                             {'nom': 'M. Fiche', 'consent_esign': True, 'empreinte_contenu': empreinte_envoi})
        obs['signature'] = [s_sig, r_sig.get('code'), (r_sig.get('detail') or '')[:80]]
    dv.refresh_from_db()
    obs['statut_final'] = dv.statut
    obs['signatures'] = DevisSignature.objects.filter(devis=dv).count()
    erreurs = [e for e in etapes if e[1] >= 500]
    obs['erreurs'] = erreurs
    pdf_change = obs['pdf_envoi'] != obs['pdf_apres'] and obs['pdf_apres'][0] == G2
    public_change = obs['public_envoi'] != obs['public_apres']
    empreinte_inchangee = bool(empreinte_envoi) and obs['empreinte_envoi'] == obs['empreinte_apres']
    repro = (not erreurs and obs['statut_apres_envoi'] == 'envoye' and pdf_change
             and empreinte_inchangee and s_sig == 200 and dv.statut == 'accepte')
    obs['lecture'] = ('envoyé : la fiche imprimée/servie suit le catalogue courant (%s → %s), empreinte inchangée, '
                      'signature %s' % (obs['pdf_envoi'][0], obs['pdf_apres'][0], s_sig))
    obs['public_change'] = public_change
    return {'repro': repro, 'observe': obs}
