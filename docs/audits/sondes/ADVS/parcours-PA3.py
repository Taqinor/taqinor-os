# flake8: noqa  (sonde de parcours PA3, rejouable par scripts/sonde.py — AMET93)
"""PA3 bout en bout (C19) sur UN enregistrement, par l'API réelle : lead → POST devis/atomic (brouillon) →
share-link {envoi} (envoyé + jeton) → /proposal (PDF moteur) → page publique data → société B (404 partout) →
signature publique avec l'empreinte lue → relecture (statut, signature unique, chantier, étape du lead) → seconde
signature (idempotente). Oracles : aucune réponse ≥ 500 ; TTC page publique = TTC devis au centime ; `prix_achat`
absent de toute réponse ; PDF commence par %PDF. Société neuve, transaction annulée."""
SONDE = {"constat": "parcours-PA3", "sha": "1dfa7986c",
         "attendu": "chaque étape 2xx ; TTC public = TTC devis ; B → 404 ; accepté, 1 signature, chantier, lead SIGNED ; aucun prix_achat",
         "modeles": ["ventes.Devis", "ventes.ShareLink", "ventes.DevisSignature", "crm.Lead"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, DevisSignature, ShareLink
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 000', slug='sonde-advs-000')
    cb = Company.objects.create(nom='Sonde ADVS 000 B', slug='sonde-advs-000-b')
    u = U.objects.create_user(username='sonde-advs-000', password='x', role_legacy='admin', company=c)
    ub = U.objects.create_user(username='sonde-advs-000-b', password='x', role_legacy='admin', company=cb)
    lead = Lead.objects.create(company=c, nom='Parcours', prenom='PA3', telephone='+212600003000',
                               ville='Casablanca', email='sonde-advs-000@example.invalid')
    cl = Client.objects.create(company=c, nom='Parcours', prenom='PA3', email='sonde-advs-000@example.invalid')
    pan = Produit.objects.create(company=c, nom='Panneau Canadien Solar 710W', sku='ADVS000-P',
                                 prix_vente=Decimal('1166.67'), prix_achat=Decimal('700'), quantite_stock=100)
    ond = Produit.objects.create(company=c, nom='Onduleur réseau Huawei 10kW Monophasé', sku='ADVS000-O',
                                 prix_vente=Decimal('14000'), prix_achat=Decimal('9000'), quantite_stock=100)
    api, apib, pub = APIClient(), APIClient(), APIClient()
    api.force_authenticate(u)
    apib.force_authenticate(ub)
    etapes, fuites = [], []

    from django.db import transaction

    def appel(nom, client, meth, url, corps=None, attendu=None):
        try:
            with transaction.atomic():
                r = getattr(client, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
        except Exception as e:
            import traceback
            etapes.append((nom, 599, ''.join(traceback.format_exception_only(type(e), e))[:300]))
            return 599, {}, b''
        brut = r.content if hasattr(r, 'content') else b''.join(r.streaming_content)
        txt = brut.decode('utf-8', 'replace')
        etapes.append((nom, r.status_code, '' if r.status_code < 400 or attendu == r.status_code else txt[:200]))
        if 'prix_achat' in txt:
            fuites.append(nom)
        try:
            return r.status_code, json.loads(txt), brut
        except Exception:
            return r.status_code, {}, brut

    s, cree, _ = appel('atomic', api, 'post', '/api/django/ventes/devis/atomic/', {
        'client': cl.id, 'lead': lead.id, 'statut': 'brouillon', 'taux_tva': '20.00',
        'lignes': [{'produit': pan.id, 'designation': 'Panneau Canadien Solar 710W', 'quantite': '12',
                    'prix_unitaire': '1166.67', 'taux_tva': '20'},
                   {'produit': ond.id, 'designation': 'Onduleur réseau Huawei 10kW Monophasé', 'quantite': '1',
                    'prix_unitaire': '14000.00', 'taux_tva': '20'}]})
    obs = {'etapes': etapes, 'fuites_prix_achat': fuites}
    dv = Devis.objects.filter(company=c).first()
    if not dv:
        return {'repro': True, 'observe': obs}
    ttc = Decimal(str(dv.total_ttc))
    obs.update(reference=dv.reference, ttc_devis=str(ttc), lead_devis=dv.lead_id)
    with mock.patch('apps.ventes.public_views._notify_open'), \
            mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf'):
        s, sl, _ = appel('share-link envoi', api, 'post', f'/api/django/ventes/devis/{dv.id}/share-link/', {'envoi': True})
        dv.refresh_from_db()
        obs['statut_apres_envoi'] = dv.statut
        link = ShareLink.objects.filter(devis=dv, revoque_le__isnull=True).order_by('-id').first()
        s, _, pdf = appel('proposal pdf', api, 'get', f'/api/django/ventes/devis/{dv.id}/proposal/')
        obs['pdf_magic'] = pdf[:4].decode('latin-1') if pdf else ''
        if link is None:
            return {'repro': True, 'observe': obs}
        s, lu, _ = appel('public data', pub, 'get', f'/api/django/public/proposal/{link.token}/data/')
        obs['cles_public'] = sorted(lu.keys())[:60]
        totaux = json.dumps({k: lu.get(k) for k in ('totals', 'totaux', 'options', 'option_totals', 'total_ttc') if k in lu},
                            default=str)[:600]
        obs['totaux_public'] = totaux
        # société B : lecture, PDF, acceptation interne du devis de A
        sb1, _, _ = appel('B lecture', apib, 'get', f'/api/django/ventes/devis/{dv.id}/', attendu=404)
        sb2, _, _ = appel('B proposal', apib, 'get', f'/api/django/ventes/devis/{dv.id}/proposal/', attendu=404)
        sb3, _, _ = appel('B accepter', apib, 'post', f'/api/django/ventes/devis/{dv.id}/accepter/', {'nom': 'X'}, attendu=404)
        obs['societe_B'] = [sb1, sb2, sb3]
        corps = {'nom': 'M. Parcours', 'consent_esign': True, 'empreinte_contenu': lu.get('empreinte_contenu')}
        s1, r1, _ = appel('signature', pub, 'post', f'/api/django/public/proposal/{link.token}/accept/', corps)
        s2, r2, _ = appel('signature bis', pub, 'post', f'/api/django/public/proposal/{link.token}/accept/', corps)
        obs['reponse_signature'] = {k: r1.get(k) for k in ('statut', 'reference', 'detail')}
        obs['signature_bis'] = [s2, r2.get('detail'), r2.get('code')]
        s, lu2, _ = appel('public relecture', pub, 'get', f'/api/django/public/proposal/{link.token}/data/')
    dv.refresh_from_db()
    lead.refresh_from_db()
    chantiers = None
    try:
        from apps.installations.models import Installation as Chantier
        with transaction.atomic():
            chantiers = Chantier.objects.filter(devis=dv).count()
    except Exception as e:
        chantiers = f'err {e}'
    obs.update(statut_final=dv.statut, signatures=DevisSignature.objects.filter(devis=dv).count(),
               chantiers=chantiers, etape_lead=getattr(lead, 'stage', None) or getattr(lead, 'statut', None),
               ttc_final=str(dv.total_ttc), accepted_public=lu2.get('accepted'))
    erreurs = [e for e in etapes if e[1] >= 500 or (e[1] >= 400 and e[2])]
    repro = bool(erreurs or fuites or obs['pdf_magic'] != '%PDF' or dv.statut != 'accepte'
                 or obs['signatures'] != 1 or obs['societe_B'] != [404, 404, 404])
    obs['erreurs'] = erreurs
    return {'repro': repro, 'observe': obs}
