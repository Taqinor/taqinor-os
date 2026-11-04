# flake8: noqa  (sonde d'audit, contre-visite ATOT du 04/11, rejouable par scripts/sonde.py — AMET93)
"""ATOT43/ATOT45 : `domain/facturation_vente.py::crediter_ecart_de_vente` répartit l'écart sous le créditable
TTC de chaque facture, mais ventile chaque avoir au prorata des paniers de l'ÉCART, jamais borné par la base
par taux de la facture visée. Vente multi-taux (40 000 HT @10 % + 60 000 HT @20 %) facturée en 5 tranches
de 20 % émises (chacune 8 000 @10 % + 12 000 @20 %), révision V2 où la ligne à 10 % passe à 30 000 HT,
avoir d'écart confirmé : un seul avoir de 11 000 TTC (10 000 HT @10 %) sur UNE tranche dont la base à 10 %
n'est que de 8 000. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ATOT-VER4-010", "sha": "64c9c7317",
         "attendu": "avoir d'écart de 11 000 TTC : base 10 % de l'avoir (10 000) > base 10 % de la facture créditée (8 000) ; attendu sain : base créditée par taux ≤ base de la facture à ce taux (répartie sur deux tranches)",
         "modeles": ["authentication.Company", "ventes.Devis", "facturation.Facture", "facturation.Avoir", "crm.Lead"]}


def sonde(ctx):
    from django.utils.timezone import localdate
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.facturation.models import Avoir, Facture
    from apps.ventes.domain.cycle_vie import accept_devis
    from apps.ventes.domain.revision import rattacher_aval_financier_revision, reviser_devis
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes.tests._quote_engine_common import make_devis
    from apps.ventes.utils.echeancier import creer_facture_tranche
    from apps.ventes.utils.references import create_with_reference

    co = Company.objects.create(nom='Sonde ATOT-VER4-010', slug='sonde-atot-ver4-010')
    u = get_user_model().objects.create_user(username='sonde-atot-ver4-010', password='x',
                                             role_legacy='responsable', company=co)
    cl = Client.objects.create(company=co, nom='Client', prenom='VER4', email='atot-ver4-010@example.invalid')
    A10, A20 = 'Équipement à 10', 'Installation à 20'
    v1 = make_devis(co, u, cl, [(A10, '1', '40000', '10'), (A20, '1', '60000', '20')],
                    reference='DEV-SONDE-ATOT4-010')
    lead = Lead.objects.create(company=co, nom='Lead sonde ATOT4-010')
    Devis.objects.filter(pk=v1.pk).update(statut=Devis.Statut.ENVOYE, lead=lead,
                                          echeancier=[{'pct_or_montant': 20}] * 5)

    def accepter(d):
        return accept_devis(devis=Devis.objects.get(pk=d.pk), user=u, nom='Client VER4',
                            date_acceptation=localdate(), option='sans_batterie')

    with mock.patch('apps.ventes.domain.cycle_vie._send_acceptance_emails'), \
            mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf'):
        v1 = accepter(v1)
        n = 0
        while n < 10:
            try:
                creer_facture_tranche(Devis.objects.get(pk=v1.pk), u, co, create_with_reference)
            except ValueError:
                break
            n += 1
        factures = list(Facture.objects.filter(company=co).exclude(statut=Facture.Statut.ANNULEE).order_by('pk'))
        tranches = [(f.reference, f.statut, str(f.total_ttc),
                     [(str(b['taux']), str(b['base_ht']), str(b['montant'])) for b in f.tva_par_taux])
                    for f in factures]
        v2 = reviser_devis(Devis.objects.get(pk=v1.pk), user=u)
        LigneDevis.objects.filter(devis=v2, designation=A10).update(prix_unitaire=Decimal('30000'))
        Devis.objects.filter(pk=v2.pk).update(statut=Devis.Statut.ENVOYE)
        v2 = accepter(v2)
        r = rattacher_aval_financier_revision(Devis.objects.get(pk=v2.pk), user=u, confirmer_avoir=True)
    avoirs = []
    depassements = []
    for a in Avoir.objects.filter(company=co).order_by('pk'):
        f = Facture.objects.get(pk=a.facture_id)
        base_f = {Decimal(str(b['taux'])): Decimal(str(b['base_ht'])) for b in f.tva_par_taux}
        paniers = [(Decimal(str(b['taux'])), Decimal(str(b['base_ht'])), Decimal(str(b['montant'])))
                   for b in a.tva_par_taux]
        for t, base, _m in paniers:
            if base > base_f.get(t, Decimal('0')) + Decimal('0.01'):
                depassements.append({'avoir': a.reference, 'facture': f.reference, 'taux': str(t),
                                     'base_avoir': str(base), 'base_facture': str(base_f.get(t, 0))})
        avoirs.append({'ref': a.reference, 'facture': f.reference, 'ttc': str(a.total_ttc),
                       'paniers': [(str(t), str(b), str(m)) for t, b, m in paniers],
                       'facture_paniers': [(str(t), str(b)) for t, b in base_f.items()],
                       'facture_du': str(f.montant_du), 'facture_statut': f.statut})
    obs = {'nb_tranches': len(factures), 'tranches': tranches, 'avoirs': avoirs,
           'depassements': depassements, 'avoir_a_confirmer': str((r or {}).get('avoir_a_confirmer'))}
    print(obs)
    return {'repro': bool(depassements), **obs}
