# flake8: noqa  (sonde d'audit, rejouable par scripts/sonde.py — AMET93)
"""C-ADVS-061 — PA3-02 porte WhatsApp (C1) : `utils/whatsapp.py::build_single_devis_whatsapp` met dans le message
le lien BRUT de l'API `/api/django/public/document/<token>/` (`public_document_url`), pas la page `/proposition/`.
Ce flux porte les MÊMES gardes que la page (`public_document` : code d'accès `otp_lecture` → 403 JSON
`otp_required` ; case « PDF téléchargeable » décochée → 404 muet) mais AUCUNE interface : un client dont le
commercial a posé un code d'accès (dialogue « Envoyer au client ») ou décoché le PDF reçoit par WhatsApp un lien
qui répond `{"detail":"otp_required"}` ou 404, sans page, sans saisie de code, sans bouton « signer ». La porte
e-mail (page) et la porte WhatsApp (PDF brut) servent le même jeton (`ShareLink.for_devis`) avec deux postures.
Société neuve, transaction annulée ; aucun envoi réel (wa.me est une URL rendue au vendeur)."""
SONDE = {"constat": "C-ADVS-061", "sha": "1dfa7986c",
         "attendu": "le lien WhatsApp s'ouvre (page avec saisie du code ou PDF) quel que soit le réglage du lien",
         "modeles": ["ventes.Devis", "ventes.ShareLink"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from urllib.parse import urlparse
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, ShareLink
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 061', slug='sonde-advs-061')
    u = U.objects.create_user(username='sonde-advs-061', password='x', role_legacy='admin', company=c)
    lead = Lead.objects.create(company=c, nom='Wa', prenom='Lien', telephone='+212600006100',
                               ville='Casablanca', email='sonde-advs-061@example.invalid')
    cl = Client.objects.create(company=c, nom='Wa', prenom='Lien', telephone='+212600006100',
                               email='sonde-advs-061@example.invalid')
    pan = Produit.objects.create(company=c, nom='Panneau Canadien Solar 710W', sku='ADVS061-P',
                                 prix_vente=Decimal('1166.67'), prix_achat=Decimal('700'), quantite_stock=100)
    ond = Produit.objects.create(company=c, nom='Onduleur réseau Huawei 10kW Monophasé', sku='ADVS061-O',
                                 prix_vente=Decimal('14000'), prix_achat=Decimal('9000'), quantite_stock=100)
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
            return 599, {}, ''
        txt = (r.content if hasattr(r, 'content') else b''.join(r.streaming_content)).decode('utf-8', 'replace')
        etapes.append((nom, r.status_code, '' if r.status_code < 400 else txt[:160]))
        try:
            return r.status_code, json.loads(txt), txt
        except Exception:
            return r.status_code, {}, txt

    appel('atomic', api, 'post', '/api/django/ventes/devis/atomic/', {
        'client': cl.id, 'lead': lead.id, 'statut': 'brouillon', 'taux_tva': '20.00',
        'lignes': [{'produit': pan.id, 'designation': 'Panneau Canadien Solar 710W', 'quantite': '12',
                    'prix_unitaire': '1166.67', 'taux_tva': '20'},
                   {'produit': ond.id, 'designation': 'Onduleur réseau Huawei 10kW Monophasé', 'quantite': '1',
                    'prix_unitaire': '14000.00', 'taux_tva': '20'}]})
    obs = {'etapes': etapes}
    dv = Devis.objects.filter(company=c).first()
    if not dv:
        return {'repro': False, 'observe': obs}
    with mock.patch('apps.ventes.public_views._notify_open'):
        # A. le commercial envoie avec un CODE D'ACCÈS (dialogue « Envoyer au client », L-NIV/QJR132)
        s, _, _ = appel('share-link envoi + otp_lecture', api, 'post',
                        f'/api/django/ventes/devis/{dv.id}/share-link/', {'envoi': True, 'otp_lecture': True})
        link = ShareLink.objects.filter(devis=dv, revoque_le__isnull=True).order_by('-id').first()
        obs['lien'] = {'otp_lecture': getattr(link, 'otp_lecture', None), 'niveau': getattr(link, 'niveau', None)}
        # B. puis « Envoyer » par WhatsApp (porte QG8) — même jeton (ShareLink.for_devis)
        s_wa, r_wa, _ = appel('whatsapp', api, 'post', f'/api/django/ventes/devis/{dv.id}/whatsapp/', {})
        url = r_wa.get('url') or ''
        chemin = urlparse(url).path
        obs['whatsapp'] = {'statut': s_wa, 'url_path': chemin, 'meme_jeton': bool(link and link.token in url),
                           'wa_url': (r_wa.get('wa_url') or '')[:60], 'message_a_le_lien': url in (r_wa.get('message') or ''),
                           'proposition_dans_message': '/proposition/' in (r_wa.get('message') or '')}
        # C. le CLIENT clique le lien reçu (aucun en-tête de preuve : il sort de WhatsApp)
        s_doc, r_doc, txt_doc = appel('client GET lien WhatsApp (otp)', pub, 'get', chemin or '/__absent__/')
        obs['clic_client_otp'] = [s_doc, (r_doc.get('detail') if isinstance(r_doc, dict) else None),
                                  txt_doc[:4] == '%PDF']
        # D. le commercial retire le code mais décoche « PDF téléchargeable » (L-SECT) — WhatsApp à nouveau
        appel('share-link sections pdf=False', api, 'post', f'/api/django/ventes/devis/{dv.id}/share-link/',
              {'otp_lecture': False, 'sections': {'pdf': False}})
        s_wa2, r_wa2, _ = appel('whatsapp bis', api, 'post', f'/api/django/ventes/devis/{dv.id}/whatsapp/', {})
        chemin2 = urlparse(r_wa2.get('url') or '').path
        s_doc2, r_doc2, txt_doc2 = appel('client GET lien WhatsApp (pdf décoché)', pub, 'get', chemin2 or '/__absent__/')
        obs['clic_client_pdf_decoche'] = [s_doc2, txt_doc2[:4] == '%PDF']
        # E. contre-épreuve : la PAGE de ce jeton, elle, répond (403 otp → la page affiche la saisie du code ;
        #    ici sans otp → 200) : c'est la porte que le lien WhatsApp aurait dû viser
        s_page, lu, _ = appel('page /data/ du même jeton', pub, 'get', f'/api/django/public/proposal/{link.token}/data/')
        obs['page_meme_jeton'] = [s_page, bool(lu.get('empreinte_contenu'))]
    dv.refresh_from_db()
    obs['statut_devis'] = dv.statut
    erreurs = [e for e in etapes if e[1] >= 500]
    obs['erreurs'] = erreurs
    repro = (not erreurs and s_wa == 200 and chemin.startswith('/api/django/public/document/')
             and s_doc == 403 and obs['clic_client_otp'][1] == 'otp_required'
             and s_doc2 == 404 and s_page == 200)
    obs['lecture'] = ('WhatsApp → %s : client 403 %s avec code d\'accès ; 404 avec « PDF téléchargeable » décoché ; '
                      'la page du même jeton répond %s' % (chemin, obs['clic_client_otp'][1], s_page))
    return {'repro': repro, 'observe': obs}
