# flake8: noqa  (sonde d'audit de parcours PF2 « Socle », rejouable par scripts/sonde.py — METHODE §C.4)
"""K42 — un devis ENVOYÉ puis ACCEPTÉ est ré-imprimé par `/proposal` avec l'identité vendeur VIVANTE.
`apps/ventes/views/devis_pdf.py::DevisPdfActionsMixin.proposal` (rendu à chaque appel) →
`quote_engine/conditions_commerciales.py` (`company_identity(devis.company)` vivant) ; seuls les textes
`DocumentTemplates` sont gelés à l'envoi (`_doc_texts_envoyes`). Jumeau figé : facture (APAR61).
Chemin : profil société (raison sociale / ICE / RIB / adresse v1) ; devis envoyé par `mark_devis_sent` (gel réel
de l'envoi), accepté par la vraie route POST /accepter/ ; GET /proposal (moteur RÉEL, pas de mock, texte fitz) ;
l'admin change raison sociale, ICE, RIB, adresse ; GET /proposal à nouveau."""
SONDE = {"constat": "C-ASOC-042", "sha": "c514bd8ba",
         "attendu": "repro si le second rendu /proposal du devis accepté porte les NOUVELLES valeurs (ICE/RIB/raison "
                    "sociale) et plus les anciennes (attendu sain : identité du jour de l'envoi)",
         "modeles": ["ventes.Devis", "ventes.LigneDevis", "ventes.Facture", "parametres.CompanyProfile",
                     "crm.Client", "stock.Produit"]}


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
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes.domain.envoi import mark_devis_sent
    H = {'HTTP_HOST': 'localhost'}
    V1 = {'nom': 'SOLAIRE ANCIEN SARL', 'ice': '001122334000055', 'rib': '011780000012345678901234',
          'adresse': '12 Rue Ancienne, Casablanca'}
    V2 = {'nom': 'SOLAIRE NOUVEAU SA', 'ice': '009988776000011', 'rib': '230810000098765432109876',
          'adresse': '99 Boulevard Nouveau, Rabat'}
    co = Company.objects.create(nom='Sonde ASOC 042', slug='sonde-asoc-042')
    u = get_user_model().objects.create_user(username='sonde-asoc-042', password='x', role_legacy='admin', company=co)
    prof = CompanyProfile.get(company=co)
    for k, v in V1.items():
        setattr(prof, k, v)
    prof.save()
    cl = Client.objects.create(company=co, nom='Tazi', prenom='K42', email='asoc042@example.invalid',
                               telephone='+212600000042')
    d = Devis.objects.create(company=co, client=cl, reference='DEV-SONDE-ASOC042', statut=Devis.Statut.BROUILLON,
                             taux_tva=Decimal('20'), mode_installation='residentiel', created_by=u)
    for i, (nom, qte, pu) in enumerate((('Panneau Canadien Solar 710W', '8', '1200'),
                                        ('Onduleur réseau Huawei 5kW Monophasé', '1', '9000'))):
        p = Produit.objects.create(company=co, nom=nom, sku=f'ASOC042-{i}', prix_vente=Decimal(pu),
                                   prix_achat=Decimal('1'), quantite_stock=50)
        LigneDevis.objects.create(devis=d, produit=p, designation=nom, quantite=Decimal(qte),
                                  prix_unitaire=Decimal(pu), remise=Decimal('0'), ordre=i)
    mark_devis_sent(devis=d, user=u)
    api = APIClient()
    api.force_authenticate(u)
    r = api.post(f'/api/django/ventes/devis/{d.pk}/accepter/', {'nom': 'K42 Tazi'}, format='json', **H)
    d.refresh_from_db()
    obs = {'accepter_http': r.status_code, 'statut': d.statut}

    def rendu():
        rr = api.get(f'/api/django/ventes/devis/{d.pk}/proposal/', **H)
        if rr.status_code != 200:
            return rr.status_code, ''
        raw = b''.join(rr.streaming_content) if getattr(rr, 'streaming', False) else rr.content
        with fitz.open(stream=raw, filetype='pdf') as doc:
            t = re.sub(r'\s+', ' ', ' '.join(pg.get_text() for pg in doc))
        return rr.status_code, t

    def presence(t, V):
        compact = re.sub(r'\s', '', t)
        return {k: (re.sub(r'\s', '', v) in compact) for k, v in V.items()}
    s1, t1 = rendu()
    obs['rendu1'] = {'http': s1, 'V1': presence(t1, V1), 'V2': presence(t1, V2)}
    prof = CompanyProfile.get(company=co)
    for k, v in V2.items():
        setattr(prof, k, v)
    prof.save()
    s2, t2 = rendu()
    obs['rendu2'] = {'http': s2, 'V1': presence(t2, V1), 'V2': presence(t2, V2)}
    print(obs)
    r1, r2 = obs['rendu1'], obs['rendu2']
    temoin = s1 == 200 and r1['V1']['ice'] and r1['V1']['nom']
    obs['temoin_ok'] = bool(temoin)
    obs['repro'] = bool(temoin and obs['statut'] == 'accepte' and s2 == 200 and r2['V2']['ice']
                        and not r2['V1']['ice'])
    return obs
