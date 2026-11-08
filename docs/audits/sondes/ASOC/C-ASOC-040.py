# flake8: noqa  (sonde d'audit de parcours PF2 « Socle », rejouable par scripts/sonde.py — METHODE §C.4)
"""K40 — l'échéancier d'un devis ENVOYÉ sans échéancier propre est lu EN DIRECT jusqu'à l'acceptation :
`apps/ventes/utils/echeancier.py::tranches_normalisees` (Devis.echeancier vide ⇒ `payment_terms_for` vivant),
`::figer_echeancier` appelé seulement à l'acceptation (`domain/cycle_vie.py`, AMET2) ; l'envoi
(`domain/envoi.py::geler_document_engage`) ne fige pas l'échéancier.
Chemin : profil société 30/60/10 résidentiel ; devis brouillon (panneaux + onduleur) ; `mark_devis_sent` ;
GET /proposal (vraie route, PDF réel, texte extrait par fitz) → « Acompte à la commande : 30 % » ;
l'admin passe le réglage à 40/50/10 ; POST /devis/<id>/accepter/ (vraie route, porte interne) ;
relire `Devis.echeancier` figé et le brouillon d'acompte AMET4 créé dans la transaction."""
SONDE = {"constat": "C-ASOC-040", "sha": "c514bd8ba",
         "attendu": "repro si PDF envoyé = acompte 30 % et, après changement du réglage, l'acceptation fige 40 % "
                    "et le brouillon d'acompte vaut 40 % du TTC (attendu sain : 30 %, ce que le client a reçu)",
         "modeles": ["ventes.Devis", "ventes.LigneDevis", "ventes.Facture", "ventes.LigneFacture",
                     "parametres.CompanyProfile", "crm.Client", "stock.Produit"]}


def sonde(ctx):
    import re
    from decimal import Decimal
    import fitz
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.parametres.models import CompanyProfile
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, Facture, LigneDevis
    from apps.ventes.domain.envoi import mark_devis_sent
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ASOC 040', slug='sonde-asoc-040')
    u = get_user_model().objects.create_user(username='sonde-asoc-040', password='x', role_legacy='admin', company=co)
    prof = CompanyProfile.get(company=co)
    prof.payment_terms = {'residentiel': {'acompte': 30, 'materiel': 60, 'solde': 10}}
    prof.save()
    cl = Client.objects.create(company=co, nom='Bennani', prenom='K40', email='asoc040@example.invalid',
                               telephone='+212600000040')
    d = Devis.objects.create(company=co, client=cl, reference='DEV-SONDE-ASOC040', statut=Devis.Statut.BROUILLON,
                             taux_tva=Decimal('20'), mode_installation='residentiel', created_by=u)
    for i, (nom, qte, pu) in enumerate((('Panneau Canadien Solar 710W', '8', '1200'),
                                        ('Onduleur réseau Huawei 5kW Monophasé', '1', '9000'))):
        p = Produit.objects.create(company=co, nom=nom, sku=f'ASOC040-{i}', prix_vente=Decimal(pu),
                                   prix_achat=Decimal('1'), quantite_stock=50)
        LigneDevis.objects.create(devis=d, produit=p, designation=nom, quantite=Decimal(qte),
                                  prix_unitaire=Decimal(pu), remise=Decimal('0'), ordre=i)
    mark_devis_sent(devis=d, user=u)
    d.refresh_from_db()
    api = APIClient()
    api.force_authenticate(u)
    obs = {'statut_apres_envoi': d.statut, 'echeancier_apres_envoi': d.echeancier}

    def acompte_pdf():
        r = api.get(f'/api/django/ventes/devis/{d.pk}/proposal/', **H)
        if r.status_code != 200 or not r.get('Content-Type', '').startswith('application/pdf'):
            return r.status_code, None
        raw = b''.join(r.streaming_content) if getattr(r, 'streaming', False) else r.content
        with fitz.open(stream=raw, filetype='pdf') as doc:
            t = re.sub(r'\s+', ' ', ' '.join(pg.get_text() for pg in doc))
        m = re.search(r'Acompte à la commande\s*:\s*(\d+)\s*%', t)
        return r.status_code, (m.group(1) if m else t[:0])
    obs['pdf_envoye'] = acompte_pdf()
    # l'admin change le réglage APRÈS l'envoi
    prof = CompanyProfile.get(company=co)
    prof.payment_terms = {'residentiel': {'acompte': 40, 'materiel': 50, 'solde': 10}}
    prof.save()
    obs['pdf_apres_reglage_avant_acceptation'] = acompte_pdf()
    r = api.post(f'/api/django/ventes/devis/{d.pk}/accepter/', {'nom': 'K40 Bennani'}, format='json', **H)
    d.refresh_from_db()
    obs['accepter_http'] = [r.status_code, None if r.status_code < 400 else str(getattr(r, 'data', ''))[:200]]
    obs['statut'] = d.statut
    obs['echeancier_fige'] = [(e.get('type'), e.get('pct_or_montant')) for e in (d.echeancier or [])]
    ttc = d.total_ttc if hasattr(d, 'total_ttc') else None
    obs['devis_ttc'] = str(ttc)
    acs = list(Facture.objects.filter(devis=d).values_list('reference', 'statut', 'type_facture'
                                                           if hasattr(Facture, 'type_facture') else 'statut'))
    obs['factures'] = acs
    f = Facture.objects.filter(devis=d).order_by('pk').first()
    if f is not None:
        f.refresh_from_db()
        obs['acompte_ttc'] = str(getattr(f, 'total_ttc', None) or getattr(f, 'montant_ttc', None))
        try:
            obs['acompte_pct_du_ttc'] = round(float(Decimal(obs['acompte_ttc']) * 100 / Decimal(str(ttc))), 2)
        except Exception as exc:  # noqa
            obs['acompte_pct_du_ttc'] = f'err {exc!r}'[:80]
    print(obs)
    pdf_30 = obs['pdf_envoye'][0] == 200 and obs['pdf_envoye'][1] == '30'
    fige_40 = bool(obs['echeancier_fige']) and float(obs['echeancier_fige'][0][1]) == 40.0
    obs['repro'] = bool(pdf_30 and obs['accepter_http'][0] == 200 and fige_40)
    return obs
