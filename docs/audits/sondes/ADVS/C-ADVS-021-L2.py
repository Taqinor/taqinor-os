# flake8: noqa  (sonde seconde lentille, rejouable par scripts/sonde.py — AMET93)
"""C-ADVS-021 — LENTILLE 2 (reproduction indépendante). Autre porte de DÉSACCEPTATION : le lead sort de
« Signé » par ``PATCH /crm/leads/<id>/ {stage: FOLLOW_UP}`` (décision fondateur 08/10, porte
``desaccepter_devis_du_lead``) au lieu d'un appel direct à ``annuler_acceptation``. Puis CORRECTION SUR PLACE
de l'envoyé (``PATCH /ventes/devis-lignes/<id>/`` prix unitaire, D-QJR5-1), puis ré-acceptation au jeton par
un AUTRE signataire. Le rendu de l'exemplaire signé de la 1ʳᵉ acceptation est ÉMULÉ (la file Celery
on_commit ne tourne pas dans une transaction annulée) : ``signed_pdf_key`` posée sur la signature comme le
ferait ``_store_signed_pdf`` ; ``public_views.download_pdf`` bouchonné pour dire QUELLE clé est servie.
Observé : nombre de signatures, signataire, sceau, clé servie par ``/public/proposal/<jeton>/pdf/``.
Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-021", "sha": "1dfa7986c",
         "attendu": "ré-acceptation après désacceptation + correction : preuve de la 2e signature, exemplaire du contenu re-signé (pas celui de la 1re)",
         "modeles": ["ventes.Devis", "ventes.DevisSignature", "ventes.ShareLink", "crm.Lead"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm import stages
    from apps.crm.models import Client, Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, DevisSignature, ShareLink
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 021 L2', slug='sonde-advs-021-l2')
    u = U.objects.create_user(username='sonde-advs-021-l2', password='x', role_legacy='admin', company=c)
    lead = Lead.objects.create(company=c, nom='Tazi', prenom='Omar', telephone='+212600021200',
                               ville='Rabat', email='sonde-advs-021-l2@example.invalid')
    cl = Client.objects.create(company=c, nom='Tazi', prenom='Omar', email='sonde-advs-021-l2@example.invalid')
    pan = Produit.objects.create(company=c, nom='Panneau Trina 600W', sku='ADVS021L2-P',
                                 prix_vente=Decimal('1300'), prix_achat=Decimal('800'), quantite_stock=100)
    ond = Produit.objects.create(company=c, nom='Onduleur réseau Huawei 6kW Monophasé', sku='ADVS021L2-O',
                                 prix_vente=Decimal('11000'), prix_achat=Decimal('7000'), quantite_stock=100)
    api, pub = APIClient(), APIClient()
    api.force_authenticate(u)
    etapes = []

    def appel(nom, client, meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(client, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
        except Exception as e:
            etapes.append((nom, 599, repr(e)[:300]))
            return 599, {}, b''
        brut = r.content if hasattr(r, 'content') else b''.join(r.streaming_content)
        etapes.append((nom, r.status_code, '' if r.status_code < 400 else brut[:300].decode('utf-8', 'replace')))
        try:
            return r.status_code, json.loads(brut.decode('utf-8')), brut
        except Exception:
            return r.status_code, {}, brut

    appel('atomic', api, 'post', '/api/django/ventes/devis/atomic/', {
        'client': cl.id, 'lead': lead.id, 'statut': 'brouillon', 'taux_tva': '20.00',
        'lignes': [{'produit': pan.id, 'designation': 'Panneau Trina 600W', 'quantite': '10',
                    'prix_unitaire': '1300', 'taux_tva': '20'},
                   {'produit': ond.id, 'designation': 'Onduleur réseau Huawei 6kW Monophasé', 'quantite': '1',
                    'prix_unitaire': '11000', 'taux_tva': '20'}]})
    dv = Devis.objects.filter(company=c).first()
    obs = {'etapes': etapes}
    if dv is None:
        return {'repro': False, 'observe': obs}
    servies = []

    def faux_download(cle):
        servies.append(cle)
        return b'%PDF-EXEMPLAIRE:' + cle.encode()

    with mock.patch('apps.ventes.public_views._notify_open'), \
            mock.patch('apps.ventes.public_views.download_pdf', side_effect=faux_download):
        appel('share-link envoi', api, 'post', f'/api/django/ventes/devis/{dv.id}/share-link/', {'envoi': True})
        link = ShareLink.objects.filter(devis=dv, revoque_le__isnull=True).order_by('-id').first()
        if link is None:
            return {'repro': False, 'observe': obs}
        _, lu, _ = appel('data 1', pub, 'get', f'/api/django/public/proposal/{link.token}/data/')
        appel('signature 1', pub, 'post', f'/api/django/public/proposal/{link.token}/accept/',
              {'nom': 'Omar Tazi', 'consent_esign': True, 'empreinte_contenu': lu.get('empreinte_contenu')})
        dv.refresh_from_db()
        lead.refresh_from_db()
        sig1 = DevisSignature.objects.filter(devis=dv).first()
        obs['apres_signature_1'] = {'statut': dv.statut, 'ttc': str(dv.total_ttc), 'stage_lead': lead.stage,
                                    'signataire': getattr(sig1, 'signataire_nom', None)}
        if sig1 is None:
            return {'repro': False, 'observe': obs}
        # Émulation du rendu post-commit de l'exemplaire signé n°1 (clé figée, comme _store_signed_pdf).
        CLE1 = f'devis/{c.id}/{dv.reference}__signe.pdf'
        DevisSignature.objects.filter(pk=sig1.pk).update(signed_pdf_key=CLE1)
        hash1 = sig1.content_hash
        # Désacceptation par la porte CRM : le lead sort de « Signé ».
        appel('PATCH lead stage -> FOLLOW_UP', api, 'patch', f'/api/django/crm/leads/{lead.id}/', {'stage': stages.FOLLOW_UP, 'confirme_recul': True})
        dv.refresh_from_db()
        obs['apres_desacceptation'] = {'statut': dv.statut, 'signatures': DevisSignature.objects.filter(devis=dv).count()}
        # Correction sur place de l'envoyé (D-QJR5-1) : le prix de l'onduleur.
        lg = dv.lignes.filter(designation__icontains='Onduleur').first()
        appel('PATCH ligne prix', api, 'patch', f'/api/django/ventes/devis-lignes/{lg.id}/', {'prix_unitaire': '9500'})
        dv.refresh_from_db()
        obs['ttc_corrige'] = str(dv.total_ttc)
        link = ShareLink.objects.filter(devis=dv, revoque_le__isnull=True).order_by('-id').first() or link
        _, lu2, _ = appel('data 2', pub, 'get', f'/api/django/public/proposal/{link.token}/data/')
        obs['empreinte_change'] = lu.get('empreinte_contenu') != lu2.get('empreinte_contenu')
        appel('signature 2', pub, 'post', f'/api/django/public/proposal/{link.token}/accept/',
              {'nom': 'Leila Tazi', 'consent_esign': True, 'empreinte_contenu': lu2.get('empreinte_contenu')})
        dv.refresh_from_db()
        sigs = list(DevisSignature.objects.filter(devis=dv).values('signataire_nom', 'signed_pdf_key', 'content_hash'))
        from apps.ventes.domain.identite_entreprise import verifier_empreinte_signature
        from apps.ventes.domain import pdf_signe
        sceau = verifier_empreinte_signature(Devis.objects.get(pk=dv.pk))
        s_pdf, _, octets = appel('PDF public après ré-acceptation', pub, 'get', f'/api/django/public/proposal/{link.token}/pdf/')
        etat = pdf_signe.etat_pdf_signe(DevisSignature.objects.filter(devis=dv).first())
    obs.update(statut_final=dv.statut, accepte_par_nom=dv.accepte_par_nom, signatures=sigs,
               hash_inchange=bool(sigs) and sigs[0]['content_hash'] == hash1, sceau=sceau,
               pdf_public={'http': s_pdf, 'debut': octets[:80].decode('latin-1') if octets else ''},
               cles_servies=servies, etat_exemplaire=etat)
    desaccepte = obs['apres_desacceptation']['statut'] == 'envoye'
    corrige = obs['ttc_corrige'] != obs['apres_signature_1']['ttc']
    obs.update(desaccepte=desaccepte, corrige=corrige)
    repro = bool(desaccepte and corrige and dv.statut == 'accepte' and len(sigs) == 1 and sigs[0]['signataire_nom'] == 'Omar Tazi'
                 and CLE1 in servies)
    return {'repro': repro, 'observe': obs}
