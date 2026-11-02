# flake8: noqa  (sonde de vérification C-L2-5, rejouable par scripts/sonde.py)
"""C-L2-5 — le format mémorisé (pdf_render_meta['options']) n'est suivi ni par les PDF publics (_opts_pdf_public)
ni par l'exemplaire signé (_store_signed_pdf : clean_pdf_options({}) = « full », persist=True).
(A) devis sans onduleur rendu en une page (seul format possible) → envoi → PDF public ? → acceptation publique →
rendre_pdf_signe → exemplaire signé ? (B) devis avec onduleur rendu en une page → acceptation → rendre_pdf_signe →
format mémorisé après. Société neuve, transaction annulée (le stockage objet reçoit des PDF de rendu)."""
SONDE = {"constat": "C-ADVS-012", "sha": "1dfa7986c",
         "attendu": "(A) PDF public 200 et exemplaire signé posé ; (B) pdf_mode mémorisé reste onepage",
         "modeles": ["ventes.Devis", "ventes.ShareLink", "ventes.DevisSignature"]}


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
    from apps.ventes.models import Devis, DevisSignature, ShareLink
    from apps.ventes.quote_engine import clean_pdf_options, generate_premium_devis_pdf
    from apps.ventes.domain.pdf_signe import rendre_pdf_signe
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 012', slug='sonde-advs-012')
    u = U.objects.create_user(username='sonde-advs-012', password='x', role_legacy='responsable', company=c)
    pan = Produit.objects.create(company=c, nom='Panneau Canadien Solar 710W', sku='ADVS012-P',
                                 prix_vente=Decimal('1166.67'), tva=Decimal('20'), quantite_stock=100)
    st = Produit.objects.create(company=c, nom='Structure aluminium toiture', sku='ADVS012-S',
                                prix_vente=Decimal('300'), tva=Decimal('20'), quantite_stock=100)
    ond = Produit.objects.create(company=c, nom='Onduleur réseau Huawei 10kW Monophasé', sku='ADVS012-O',
                                 prix_vente=Decimal('14000'), tva=Decimal('20'), quantite_stock=100)
    api, pub = APIClient(), APIClient()
    api.force_authenticate(u)

    def appel(client, meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(client, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            brut = r.content if hasattr(r, 'content') else b''.join(r.streaming_content)
            try:
                j = json.loads(brut.decode('utf-8', 'replace'))
            except Exception:
                j = {}
            return r.status_code, j, brut
        except Exception as e:
            return 599, {'_exc': repr(e)[:200]}, b''

    def cas(nom, lignes):
        o = {}
        cl = Client.objects.create(company=c, nom='Format', prenom=nom, email=f'sonde-advs-012-{nom}@example.invalid')
        s, _, _ = appel(api, 'post', '/api/django/ventes/devis/atomic/', {'client': cl.id, 'taux_tva': '20.00', 'lignes': lignes})
        dv = Devis.objects.filter(company=c, client=cl).first()
        o['creation'] = s
        if dv is None:
            return o
        try:
            with transaction.atomic():
                generate_premium_devis_pdf(dv.id, clean_pdf_options({'pdf_mode': 'onepage'}), persist=True)
        except Exception as e:
            o['rendu_onepage_err'] = repr(e)[:160]
        dv.refresh_from_db()
        o['pdf_mode_memorise_avant'] = ((dv.pdf_render_meta or {}).get('options') or {}).get('pdf_mode')
        with mock.patch('apps.ventes.public_views._notify_open'):
            s, _, _ = appel(api, 'post', f'/api/django/ventes/devis/{dv.id}/share-link/', {'envoi': True})
            o['envoi'] = s
            link = ShareLink.objects.filter(devis=dv, revoque_le__isnull=True).order_by('-id').first()
            if link is None:
                return o
            for chemin in (f'/api/django/ventes/proposal/{link.token}/pdf/', f'/api/django/public/proposal/{link.token}/pdf/'):
                s, j, b = appel(pub, 'get', chemin)
                o.setdefault('pdf_public', []).append([chemin.split('/api/django/')[1].split('/')[0], s,
                                                       b[:4].decode('latin-1') if s == 200 else str(j.get('detail'))[:80]])
            s, lu, _ = appel(pub, 'get', f'/api/django/public/proposal/{link.token}/data/')
            o['data_public'] = s
            corps = {'nom': f'M. {nom}', 'consent_esign': True, 'empreinte_contenu': lu.get('empreinte_contenu')}
            s, r, _ = appel(pub, 'post', f'/api/django/public/proposal/{link.token}/accept/', corps)
            o['acceptation'] = [s, r.get('detail') if s >= 400 else r.get('statut')]
        dv.refresh_from_db()
        o['statut'] = dv.statut
        try:
            with transaction.atomic():
                o['rendre_pdf_signe'] = rendre_pdf_signe(dv.id)
        except Exception as e:
            o['rendre_pdf_signe'] = repr(e)[:160]
        sig = DevisSignature.objects.filter(devis=dv).first()
        o['signed_pdf_key_pose'] = bool(sig and sig.signed_pdf_key)
        dv.refresh_from_db()
        o['pdf_mode_memorise_apres'] = ((dv.pdf_render_meta or {}).get('options') or {}).get('pdf_mode')
        return o

    obs = {}
    obs['A_sans_onduleur'] = cas('A', [
        {'produit': pan.id, 'designation': pan.nom, 'quantite': '8', 'prix_unitaire': '1166.67', 'taux_tva': '20'},
        {'produit': st.id, 'designation': st.nom, 'quantite': '1', 'prix_unitaire': '300.00', 'taux_tva': '20'}])
    obs['B_avec_onduleur_onepage'] = cas('B', [
        {'produit': pan.id, 'designation': pan.nom, 'quantite': '12', 'prix_unitaire': '1166.67', 'taux_tva': '20'},
        {'produit': ond.id, 'designation': ond.nom, 'quantite': '1', 'prix_unitaire': '14000.00', 'taux_tva': '20'}])
    a, b = obs['A_sans_onduleur'], obs['B_avec_onduleur_onepage']
    a_def = any(p[1] == 404 for p in a.get('pdf_public', [])) or (a.get('statut') == 'accepte' and not a.get('signed_pdf_key_pose'))
    b_def = b.get('pdf_mode_memorise_avant') == 'onepage' and b.get('pdf_mode_memorise_apres') not in (None, 'onepage')
    obs['defaut_A'] = a_def
    obs['defaut_B'] = b_def
    return {'repro': bool(a_def or b_def), 'observe': obs}
