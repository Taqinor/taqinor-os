# flake8: noqa  (seconde lentille C-ADVS-003, reproduction indépendante — rejouable par scripts/sonde.py)
"""Garde « kWh déclaré contre factures » (décision fondateur 30/09/2026, ERR-QAC-KWH-SAISI-INCOHERENT-FACTURES) :
présente sur POST /atomic, absente sur les chemins calepinage ? Fixture : lead à 60 kWh/mois déclarés contre des
factures 2 800 MAD (hiver) / 3 400 MAD (été, ete_differente) — contradiction ×≈30. Témoin : /atomic avec ce lead
(refus attendu). Chemins jugés : (1) POST calepinage/calepinages/<id>/generer-devis/ (« Générer le devis » du
module calepinage) ; (2) POST ventes/devis/from-layout/ ; (3) devis automatique /auto/ (contrôle : il a SA garde).
Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-003", "sha": "1dfa7986c",
         "attendu": "les trois chemins refusent comme /atomic (code kwh_incoherent_factures), aucun devis créé",
         "modeles": ["ventes.Devis", "ventes.LigneDevis", "calepinage.Calepinage"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Devis
    from apps.calepinage.models import Calepinage
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 003 L2', slug='sonde-advs-003-l2')
    u = U.objects.create_user(username='sonde-advs-003-l2', password='x', role_legacy='admin', company=c)

    def mk(nom, sku, prix):
        return Produit.objects.create(company=c, nom=nom, sku=f'ADVS003L2-{sku}', prix_vente=Decimal(prix),
                                      prix_achat=Decimal('1'), quantite_stock=100)
    pan = mk('Panneau Jinko 550W', 'P', 1100)
    ond = mk('Onduleur réseau Huawei 5kW Monophasé', 'O', 14000)
    mk('Onduleur hybride Deye 5kW Monophasé', 'H', 17000)
    mk('Batterie Dyness 5 kWh', 'B', 17000)

    def lead(suffixe):
        return Lead.objects.create(company=c, nom='Contradiction', prenom=suffixe, telephone='+212600003' + suffixe,
                                   ville='Marrakech', email=f'sonde-advs-003-l2-{suffixe}@example.invalid',
                                   conso_mensuelle_kwh=Decimal('60'), facture_hiver=Decimal('2800'),
                                   ete_differente=True, facture_ete=Decimal('3400'))
    layout = {'areas': [{'vertices': [[0, 0], [12, 0], [12, 7], [0, 7]], 'obstacles': [], 'roofType': 'flat',
                         'pitch': 10, 'azimuth': 170}],
              'scenario': 'reseau', 'result': {'panels': 10, 'kwc': 5.5, 'annualKwh': 9100, 'savings': 7800},
              'renderPlan': {'cells': 10}}
    api = APIClient()
    api.force_authenticate(u)
    etapes = []

    def appel(nom, url, corps):
        try:
            with transaction.atomic():
                r = api.post(url, corps, format='json', HTTP_HOST='localhost')
        except Exception as e:
            etapes.append((nom, 599, repr(e)[:300]))
            return 599, {}
        txt = r.content.decode('utf-8', 'replace')
        etapes.append((nom, r.status_code, txt[:220]))
        try:
            return r.status_code, json.loads(txt)
        except Exception:
            return r.status_code, {}

    from apps.ventes.etude_horaire import controle_kwh_declare_du_lead
    l0, l1, l2, l3 = lead('10'), lead('11'), lead('12'), lead('13')
    obs = {'controle_lead': {k: str(v) for k, v in (controle_kwh_declare_du_lead(l0, c) or {}).items()}}
    # Témoin : /atomic
    s0, r0 = appel('atomic (témoin)', '/api/django/ventes/devis/atomic/', {
        'lead': l0.id, 'statut': 'brouillon', 'taux_tva': '20.00',
        'lignes': [{'produit': pan.id, 'designation': pan.nom, 'quantite': '10', 'prix_unitaire': '1100', 'taux_tva': '10'},
                   {'produit': ond.id, 'designation': ond.nom, 'quantite': '1', 'prix_unitaire': '14000', 'taux_tva': '20'}]})
    # (1) module calepinage
    cal = Calepinage.objects.create(company=c, lead_id=l1.id, roof_layout=layout, titre='Sonde 003 L2')
    s1, r1 = appel('calepinage generer-devis', f'/api/django/calepinage/calepinages/{cal.id}/generer-devis/', {})
    # (2) from-layout
    s2, r2 = appel('from-layout', '/api/django/ventes/devis/from-layout/', {'layout': layout, 'lead': l2.id})
    # (3) devis automatique (contrôle)
    s3, r3 = appel('auto (contrôle)', '/api/django/ventes/devis/auto/', {'lead': l3.id})

    def devis_du(ld):
        out = []
        for d in Devis.objects.filter(company=c, lead_id=ld.id):
            ep = d.etude_params or {}
            out.append({'ref': d.reference, 'statut': d.statut, 'ttc': str(d.total_ttc), 'lignes': d.lignes.count(),
                        'production_annuelle': ep.get('production_annuelle'),
                        'economies_annuelles': ep.get('economies_annuelles'),
                        'cles_etude': sorted(ep.keys())[:40],
                        'conso': json.dumps({k: v for k, v in ep.items() if 'conso' in k.lower()}, default=str)[:400],
                        'horaire': json.dumps({k: v for k, v in (ep.get('etude_horaire') or ep.get('bloc_horaire') or {}).items()
                                               if any(m in k for m in ('conso', 'source', 'economie', 'facture'))},
                                              default=str)[:500]})
        return out
    obs.update(etapes=etapes, devis_atomic=devis_du(l0), devis_calepinage=devis_du(l1),
               devis_from_layout=devis_du(l2), devis_auto=devis_du(l3))
    refuse_atomic = s0 >= 400 and 'incoh' in json.dumps(r0, ensure_ascii=False)
    passe = [n for n, s, dv in (('calepinage', s1, obs['devis_calepinage']), ('from-layout', s2, obs['devis_from_layout']))
             if s in (200, 201) and dv]
    obs['refuse_atomic'] = refuse_atomic
    obs['chemins_sans_garde'] = passe
    return {'repro': bool(refuse_atomic and passe), 'observe': obs}
