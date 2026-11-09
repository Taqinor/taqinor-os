# flake8: noqa  (seconde lentille PF2 « Socle » sur C-ASOC-040, rejouable par scripts/sonde.py — METHODE §B.5)
"""K40 — seconde lentille : le parcours RÉEL des deux côtés, gestes et corps exacts des écrans.
Vendeur : le générateur n'envoie PAS d'échéancier tant qu'on ne touche pas la carte (`DevisGenerator.jsx`
`echeancierAEnvoyer = useRef(false)`, `etatDevis.js` l. 435) ; envoi par « Envoyer par e-mail »
(`ventesApi.envoyerEmailDevis` -> POST /devis/<id>/envoyer-email/) : la PIÈCE JOINTE est lue dans mail.outbox.
Admin : l'écran Paramètres -> Devis enregistre la LISTE de jalons (`DevisSection.jsx::setJalons`, `jalonsDuMode`)
par PATCH /parametres/update/ (`parametresApi.updateProfile`).
Client : la page publique (`apps/web/src/lib/proposition.ts`) lit GET /ventes/proposal/<jeton>/ (acompte affiché +
`empreinte_contenu`) puis signe par POST /ventes/proposal/<jeton>/accept/ en RENVOYANT l'empreinte lue (ADEV51 :
« ce que le client signe = ce qu'il a lu »). L'empreinte (`modifiabilite._CHAMPS_ENTETE_VISIBLES`) compare le champ
`Devis.echeancier` STOCKÉ (vide), jamais les jalons société lus en direct."""
SONDE = {"constat": "C-ASOC-040", "sha": "c514bd8ba",
         "attendu": "repro si pièce jointe e-mail = 30 %, page client lue = 30 %, réglage écran 40/50/10 accepté, "
                    "empreinte inchangée, signature client avec l'empreinte LUE = 200 (aucun 409 empreinte_perimee), "
                    "acompte annoncé au client et brouillon d'acompte = 40 %",
         "modeles": ["ventes.Devis", "ventes.LigneDevis", "ventes.Facture", "ventes.ShareLink", "ventes.EmailLog",
                     "parametres.CompanyProfile", "crm.Client", "stock.Produit"]}


def sonde(ctx):
    import re
    from decimal import Decimal
    import fitz
    from django.contrib.auth import get_user_model
    from django.core import mail
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.parametres.models import CompanyProfile
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, Facture, LigneDevis, ShareLink
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ASOC 040 L2', slug='sonde-asoc-040-l2')
    u = get_user_model().objects.create_user(username='sonde-asoc-040-l2', password='x', role_legacy='admin',
                                             company=co, email='vendeur040l2@example.invalid')
    prof = CompanyProfile.get(company=co)
    prof.payment_terms = {'residentiel': [{'jalon': 'acompte', 'pct': 30}, {'jalon': 'materiel', 'pct': 60},
                                          {'jalon': 'solde', 'pct': 10}]}
    prof.save()
    cl = Client.objects.create(company=co, nom='Bennani', prenom='K40L2', email='asoc040l2@example.invalid',
                               telephone='+212600000041')
    d = Devis.objects.create(company=co, client=cl, reference='DEV-SONDE-ASOC040L2', statut=Devis.Statut.BROUILLON,
                             taux_tva=Decimal('20'), mode_installation='residentiel', created_by=u)
    for i, (nom, qte, pu) in enumerate((('Panneau Canadien Solar 710W', '8', '1200'),
                                        ('Onduleur réseau Huawei 5kW Monophasé', '1', '9000'))):
        p = Produit.objects.create(company=co, nom=nom, sku=f'ASOC040L2-{i}', prix_vente=Decimal(pu),
                                   prix_achat=Decimal('1'), quantite_stock=50)
        LigneDevis.objects.create(devis=d, produit=p, designation=nom, quantite=Decimal(qte),
                                  prix_unitaire=Decimal(pu), remise=Decimal('0'), ordre=i)

    def pct_pdf(raw):
        with fitz.open(stream=raw, filetype='pdf') as doc:
            t = re.sub(r'\s+', ' ', ' '.join(pg.get_text() for pg in doc))
        m = re.search(r'Acompte à la commande\s*:\s*(\d+)\s*%', t)
        return m.group(1) if m else None

    vendeur = APIClient()
    vendeur.force_authenticate(u)
    client = APIClient()
    obs = {'echeancier_brouillon': d.echeancier}
    mail.outbox = []
    r = vendeur.post(f'/api/django/ventes/devis/{d.pk}/envoyer-email/', {}, format='json', **H)
    d.refresh_from_db()
    pj = [a for m in mail.outbox for a in m.attachments if str(a[0]).endswith('.pdf')]
    obs['envoi'] = {'http': r.status_code, 'statut': d.statut, 'echeancier': d.echeancier,
                    'emails': len(mail.outbox), 'piece_jointe_acompte_pct': pct_pdf(pj[0][1]) if pj else None}
    link = ShareLink.objects.filter(devis=d).order_by('-pk').first()
    tok = link.token if link else ''

    def lire():
        rr = client.get(f'/api/django/ventes/proposal/{tok}/', **H)
        data = rr.data if hasattr(rr, 'data') and isinstance(rr.data, dict) else {}
        ac = data.get('acompte') or {}
        return rr.status_code, ac.get('pourcentage'), ac.get('ttc'), data.get('empreinte_contenu')
    s1, pct1, ttc1, emp1 = lire()
    obs['client_lit'] = {'http': s1, 'acompte_pct': pct1, 'acompte_ttc': ttc1, 'empreinte': bool(emp1)}
    # l'admin modifie l'échéancier société par l'écran Paramètres -> Devis (liste de jalons)
    r = vendeur.patch('/api/django/parametres/update/', {'payment_terms': {'residentiel': [
        {'jalon': 'acompte', 'pct': '40'}, {'jalon': 'materiel', 'pct': '50'}, {'jalon': 'solde', 'pct': '10'}]}},
        format='json', **H)
    obs['reglage_ecran'] = [r.status_code, None if r.status_code < 400 else str(getattr(r, 'data', ''))[:200]]
    s2, pct2, ttc2, emp2 = lire()
    obs['client_relit'] = {'http': s2, 'acompte_pct': pct2, 'acompte_ttc': ttc2, 'empreinte_identique': emp1 == emp2}
    # le client signe avec l'empreinte qu'il a LUE avant le changement
    r = client.post(f'/api/django/ventes/proposal/{tok}/accept/',
                    {'nom': 'K40 Bennani', 'consent_esign': True, 'empreinte_contenu': emp1}, format='json', **H)
    body = r.data if isinstance(getattr(r, 'data', None), dict) else {}
    d.refresh_from_db()
    paiement = body.get('paiement') or {}
    obs['signature'] = {'http': r.status_code, 'code': body.get('code'), 'statut': d.statut,
                        'acompte_annonce_ttc': paiement.get('acompte_ttc')}
    obs['echeancier_fige'] = [(e.get('type'), e.get('pct_or_montant')) for e in (d.echeancier or [])]
    from apps.ventes.utils.options import option_totaux
    ttc = option_totaux(d)['ttc']
    obs['devis_ttc'] = str(ttc)
    f = Facture.objects.filter(devis=d).order_by('pk').first()
    if f is not None:
        obs['acompte_brouillon'] = {'reference': f.reference, 'statut': f.statut, 'ttc': str(f.total_ttc),
                                    'pct_du_ttc': round(float(Decimal(str(f.total_ttc)) * 100 / Decimal(str(ttc))), 2)}
    print(obs)
    try:
        annonce_pct = round(float(Decimal(str(paiement.get('acompte_ttc'))) * 100 / Decimal(str(ttc))), 2)
    except Exception:  # noqa
        annonce_pct = None
    obs['acompte_annonce_pct'] = annonce_pct
    obs['repro'] = bool(obs['envoi']['piece_jointe_acompte_pct'] == '30' and str(pct1).startswith('30')
                        and obs['client_relit']['empreinte_identique'] and r.status_code == 200
                        and obs['echeancier_fige'] and float(obs['echeancier_fige'][0][1]) == 40.0)
    return obs
