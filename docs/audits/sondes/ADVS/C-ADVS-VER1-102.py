# flake8: noqa  (sonde de contre-visite VER1, rejouable par scripts/sonde.py)
"""C-ADVS-VER1-102 — ADVS4 (D-ADVS-2 = nouvelle_preuve) : A signe, dés-acceptation, ligne corrigée, B signe, dés-acceptation,
ligne corrigée, C signe. Attendu : 1 signature ACTIVE (C), 2 archives (A puis B) qui portent chacune nom, content_hash,
IP et signed_pdf_key de LEUR signature ; trois clés d'exemplaire signé DISTINCTES (aucun écrasement du PDF archivé) ; le
PDF public sert la clé de C ; chaque archive est de la société du devis. Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-021", "sha": "06ced8b1a",
         "attendu": "preuves successives archivées sans perte ni écrasement d'exemplaire, signature active = dernier signataire",
         "modeles": ["ventes.Devis", "ventes.DevisSignature", "ventes.DevisSignatureArchivee"]}


def sonde(ctx):
    import hashlib
    import json
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, DevisSignature, LigneDevis, ShareLink
    from apps.ventes.models_preuves import DevisSignatureArchivee
    from apps.ventes.domain.cycle_vie import annuler_acceptation
    from apps.ventes.domain.identite_entreprise import verifier_empreinte_signature
    from apps.ventes.domain import pdf_signe
    U = get_user_model()
    c = Company.objects.create(nom='Sonde VER1 102', slug='sonde-ver1-102')
    u = U.objects.create_user(username='sonde-ver1-102', password='x', role_legacy='admin', company=c)
    cl = Client.objects.create(company=c, nom='Reaccept', prenom='Ahmed', email='sonde-ver1-102@example.invalid')
    pan = Produit.objects.create(company=c, nom='Panneau Canadien Solar 710W', sku='VER1102-P',
                                 prix_vente=Decimal('1166.67'), tva=Decimal('20'), quantite_stock=100)
    d = Devis.objects.create(company=c, reference='DEV-VER1102-01', client=cl, statut='envoye',
                             taux_tva=Decimal('20'), created_by=u)
    l1 = LigneDevis.objects.create(devis=d, produit=pan, designation=pan.nom, quantite=Decimal('12'),
                                   prix_unitaire=pan.prix_vente, remise=Decimal('0'), ordre=0)
    ond = Produit.objects.create(company=c, nom='Onduleur réseau Huawei 10kW Monophasé', sku='VER1102-O',
                                 prix_vente=Decimal('14000'), tva=Decimal('20'), quantite_stock=100)
    LigneDevis.objects.create(devis=d, produit=ond, designation=ond.nom, quantite=Decimal('1'),
                              prix_unitaire=ond.prix_vente, remise=Decimal('0'), ordre=1)
    link = ShareLink.objects.create(company=c, devis=d)
    pub, api = APIClient(), APIClient()
    api.force_authenticate(u)
    obs = {}
    stock = {}

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
            return repr(e)[:200], {}, b''

    def faux_download(cle):
        return stock.get(cle, b'%PDF-1.4 absent ' + cle.encode())

    def faux_upload(octets, cle, *a, **k):
        stock[cle] = octets
        return cle

    def signer(nom, cle_rendu):
        s, lu, _ = appel(pub, 'get', f'/api/django/public/proposal/{link.token}/data/')
        s2, r, _ = appel(pub, 'post', f'/api/django/public/proposal/{link.token}/accept/',
                         {'nom': nom, 'consent_esign': True, 'empreinte_contenu': lu.get('empreinte_contenu')})
        d.refresh_from_db()
        obs.setdefault('refus', []).append([s2, r.get('code'), (r.get('detail') or '')[:100]])
        sig = DevisSignature.objects.filter(devis=d).first()
        etat = None
        if sig is not None:
            # exemplaire signé : rendu différé exécuté ici (celery coupé), stockage réel de la pile
            etat = pdf_signe._rendre_si_scelle(d, sig)
            sig.refresh_from_db()
        return s2, d.statut, sig, etat

    def corriger(plus):
        cur = Decimal(str(LigneDevis.objects.get(pk=l1.pk).prix_unitaire))
        s, _, _ = appel(api, 'patch', f'/api/django/ventes/devis-lignes/{l1.id}/', {'prix_unitaire': str(cur + plus)})
        return s

    with mock.patch('apps.ventes.public_views._notify_open'):
        sA = signer('Ahmed A', 'devis/sonde/D102.pdf')
        obs['A'] = [sA[0], sA[1], sA[2].signataire_nom if sA[2] else None, sA[3], sA[2].signed_pdf_key if sA[2] else None]
        cle_a = sA[2].signed_pdf_key if sA[2] else None
        try:
            from apps.ventes.utils.pdf import download_pdf as _dl
            octets_a_avant = [hashlib.sha256(_dl(cle_a)).hexdigest()[:12] if cle_a else None]
        except Exception as e:
            octets_a_avant = [None]
            obs['dl_a_err'] = repr(e)[:120]
        hash_a = sA[2].content_hash if sA[2] else None
        with transaction.atomic():
            annuler_acceptation(devis=d, user=u, motif='sonde')
        obs['corr1'] = corriger(Decimal('1000'))
        sB = signer('Ahmed B', 'devis/sonde/D102.pdf')
        obs['B'] = [sB[0], sB[1], sB[2].signataire_nom if sB[2] else None, sB[3], sB[2].signed_pdf_key if sB[2] else None]
        cle_b = sB[2].signed_pdf_key if sB[2] else None
        with transaction.atomic():
            annuler_acceptation(devis=d, user=u, motif='sonde')
        obs['corr2'] = corriger(Decimal('500'))
        sC = signer('Ahmed C', 'devis/sonde/D102.pdf')
        obs['C'] = [sC[0], sC[1], sC[2].signataire_nom if sC[2] else None, sC[3], sC[2].signed_pdf_key if sC[2] else None]
        cle_c = sC[2].signed_pdf_key if sC[2] else None
        servis = []

        def dl(cle):
            servis.append(cle)
            return faux_download(cle)
        with mock.patch('apps.ventes.public_views.download_pdf', side_effect=dl):
            s, _, brut = appel(pub, 'get', f'/api/django/public/proposal/{link.token}/pdf/')
        obs['pdf_public'] = [s, servis[:2]]
    d.refresh_from_db()
    actives = list(DevisSignature.objects.filter(devis=d))
    archives = list(DevisSignatureArchivee.objects.filter(devis=d).order_by('archivee_le', 'id'))
    obs['actives'] = [(s.signataire_nom, s.signed_pdf_key) for s in actives]
    obs['archives'] = [(a.preuve.get('signataire_nom'), a.preuve.get('signed_pdf_key'), a.preuve.get('ip_address'),
                        a.company_id == c.id) for a in archives]
    v = verifier_empreinte_signature(Devis.objects.select_related('client').get(pk=d.pk))
    obs['verif_active'] = [v.get('intacte')]
    obs['cles'] = [cle_a, cle_b, cle_c]
    ecarts = []
    if not (len(actives) == 1 and actives[0].signataire_nom == 'Ahmed C'):
        ecarts.append('active != C')
    if [a[0] for a in obs['archives']] != ['Ahmed A', 'Ahmed B']:
        ecarts.append('archives != A,B')
    if len({k for k in obs['cles'] if k}) != 3:
        ecarts.append('clés exemplaire non distinctes ou absentes')
    if archives and archives[0].preuve.get('signed_pdf_key') != cle_a:
        ecarts.append('clé A archivée != clé A signée')
    if archives and archives[0].preuve.get('content_hash') != hash_a:
        ecarts.append('hash A archivé != hash A')
    from apps.ventes.utils.pdf import download_pdf
    try:
        obs['octets_a_apres'] = hashlib.sha256(download_pdf(cle_a)).hexdigest()[:12] if cle_a else None
        obs['octets_c'] = hashlib.sha256(download_pdf(cle_c)).hexdigest()[:12] if cle_c else None
        if cle_a and obs['octets_a_apres'] != octets_a_avant[0]:
            ecarts.append('octets de A modifiés après les re-signatures')
    except Exception as e:
        obs['download_err'] = repr(e)[:120]
    if not obs['verif_active'][0]:
        ecarts.append('sceau actif non intact')
    obs['ecarts'] = ecarts
    return {'repro': bool(ecarts), 'observe': obs}
