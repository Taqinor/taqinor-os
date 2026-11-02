# flake8: noqa  (sonde de vérification C-L3-3 + C-L4-2, une cause racine, rejouable par scripts/sonde.py)
"""C-L3-3 / C-L4-2 — ré-acceptation après dés-acceptation : signature « A » au lien (exemplaire signé posé à la main,
le rendu différé ne tourne pas en transaction annulée) → `annuler_acceptation` → correction d'une ligne (API, envoyé)
→ nouvelle lecture (empreinte neuve) → signature « B » au lien (200). Relevé : nombre de `DevisSignature`, nom, sceau,
vérificateur, reçu, état du rendu différé et octets servis par `/proposal/<t>/pdf/` (download_pdf bouchonné pour
nommer la clé servie). Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-021", "sha": "1dfa7986c",
         "attendu": "ré-acceptation : preuve B neuve qui concorde, exemplaire neuf (défaut : preuve A gardée, sceau faux, PDF A servi)",
         "modeles": ["ventes.Devis", "ventes.ShareLink", "ventes.DevisSignature", "ventes.LigneDevis"]}


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
    from apps.ventes.models import Devis, DevisSignature, LigneDevis, ShareLink
    from apps.ventes.domain.cycle_vie import annuler_acceptation
    from apps.ventes.domain.identite_entreprise import verifier_empreinte_signature
    from apps.ventes.domain import pdf_signe
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 021', slug='sonde-advs-021')
    u = U.objects.create_user(username='sonde-advs-021', password='x', role_legacy='admin', company=c)
    cl = Client.objects.create(company=c, nom='Reaccept', prenom='Ahmed', email='sonde-advs-021@example.invalid')
    pan = Produit.objects.create(company=c, nom='Panneau Canadien Solar 710W', sku='ADVS021-P',
                                 prix_vente=Decimal('1166.67'), tva=Decimal('20'), quantite_stock=100)
    ond = Produit.objects.create(company=c, nom='Onduleur réseau Huawei 10kW Monophasé', sku='ADVS021-O',
                                 prix_vente=Decimal('14000'), tva=Decimal('20'), quantite_stock=100)
    d = Devis.objects.create(company=c, reference='DEV-ADVS021-01', client=cl, statut='envoye',
                             taux_tva=Decimal('20'), created_by=u)
    l1 = LigneDevis.objects.create(devis=d, produit=pan, designation=pan.nom, quantite=Decimal('12'),
                                   prix_unitaire=pan.prix_vente, remise=Decimal('0'), ordre=0)
    LigneDevis.objects.create(devis=d, produit=ond, designation=ond.nom, quantite=Decimal('1'),
                              prix_unitaire=ond.prix_vente, remise=Decimal('0'), ordre=1)
    link = ShareLink.objects.create(company=c, devis=d)
    pub, api = APIClient(), APIClient()
    api.force_authenticate(u)
    obs = {}

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

    with mock.patch('apps.ventes.public_views._notify_open'):
        s, lu, _ = appel(pub, 'get', f'/api/django/public/proposal/{link.token}/data/')
        obs['lecture1'] = s
        s, r1, _ = appel(pub, 'post', f'/api/django/public/proposal/{link.token}/accept/',
                         {'nom': 'Ahmed A', 'consent_esign': True, 'empreinte_contenu': lu.get('empreinte_contenu')})
        obs['signature1'] = [s, r1.get('detail'), r1.get('code')]
        d.refresh_from_db()
        sig1 = DevisSignature.objects.filter(devis=d).first()
        if sig1 is None:
            obs['statut1'] = d.statut
            return {'repro': False, 'observe': obs}
        DevisSignature.objects.filter(pk=sig1.pk).update(signed_pdf_key='devis/sonde/DEV-ADVS021-01__signe.pdf')
        sig1.refresh_from_db()
        a = {'pk': sig1.pk, 'nom': sig1.signataire_nom, 'hash': sig1.content_hash[:12],
             'signed_at': sig1.signed_at.isoformat(), 'ttc': str(d.total_ttc)}
        obs['A'] = a
        try:
            with transaction.atomic():
                annuler_acceptation(devis=d, user=u, motif='sonde')
        except Exception as e:
            obs['annulation_err'] = repr(e)[:200]
        d.refresh_from_db()
        obs['statut_apres_annulation'] = d.statut
        s, rp, _ = appel(api, 'patch', f'/api/django/ventes/devis-lignes/{l1.id}/',
                         {'prix_unitaire': str(l1.prix_unitaire + Decimal('1000'))})
        obs['correction_ligne'] = [s, rp.get('detail') if isinstance(rp, dict) else None]
        d.refresh_from_db()
        obs['ttc_corrige'] = str(d.total_ttc)
        s, lu2, _ = appel(pub, 'get', f'/api/django/public/proposal/{link.token}/data/')
        obs['lecture2'] = [s, lu2.get('empreinte_contenu') != lu.get('empreinte_contenu')]
        s, r2, _ = appel(pub, 'post', f'/api/django/public/proposal/{link.token}/accept/',
                         {'nom': 'Ahmed B', 'consent_esign': True, 'empreinte_contenu': lu2.get('empreinte_contenu')})
        obs['signature2'] = [s, r2.get('detail'), r2.get('code'), (r2.get('recu') or {}).get('signe_le')]
        d.refresh_from_db()
        obs['statut_final'] = [d.statut, d.accepte_par_nom]
        sigs = list(DevisSignature.objects.filter(devis=d))
        sig = sigs[0] if sigs else None
        obs['signatures'] = len(sigs)
        if sig is not None:
            obs['signature_en_vigueur'] = {'pk_identique': sig.pk == a['pk'], 'nom': sig.signataire_nom,
                                           'hash_identique': sig.content_hash[:12] == a['hash'],
                                           'signed_at_identique': sig.signed_at.isoformat() == a['signed_at'],
                                           'cle_pdf': sig.signed_pdf_key}
            v = verifier_empreinte_signature(Devis.objects.select_related('client').get(pk=d.pk))
            obs['verif'] = [v.get('intacte'), (v.get('message') or '')[:60]]
            obs['rendu_differe'] = pdf_signe._rendre_si_scelle(d, sig)
        servis = []

        def faux_download(cle):
            servis.append(cle)
            return b'%PDF-1.4 sonde ' + cle.encode()
        with mock.patch('apps.ventes.public_views.download_pdf', side_effect=faux_download):
            s, _, brut = appel(pub, 'get', f'/api/django/public/proposal/{link.token}/pdf/')
        obs['pdf_public'] = [s, servis[:2]]
    repro = bool(obs.get('statut_final', [''])[0] == 'accepte' and obs.get('signatures') == 1
                 and (obs.get('signature_en_vigueur') or {}).get('nom') == 'Ahmed A')
    return {'repro': repro, 'observe': obs}
