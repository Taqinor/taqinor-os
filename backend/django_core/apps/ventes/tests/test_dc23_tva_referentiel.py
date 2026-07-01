"""DC23 — UN référentiel TVA + UN selector `tva_buckets` unique.

La ventilation TVA par taux était copiée à l'identique dans Devis/Facture/Avoir
et reconsommée par DGI/FEC. Tout délègue désormais au selector unique
`apps.ventes.selectors.tva_buckets`. Ces tests vérifient :
  - mono-taux = formule d'origine (HT × taux, aucun arrondi par panier) ;
  - taux mixtes 10/20 = un panier par taux réconcilié au centime ;
  - facture/avoir de tranche (montant figé) = panier figé ;
  - Devis/Facture/Avoir renvoient la MÊME ventilation pour les mêmes lignes.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_dc23_tva_referentiel -v 2
"""
from decimal import Decimal

from django.test import TestCase

from apps.ventes.selectors import tva_buckets, TAUX_TVA_REFERENTIEL


class _Ligne:
    """Ligne factice exposant l'interface attendue par tva_buckets."""

    def __init__(self, total_ht, taux):
        self.total_ht = Decimal(str(total_ht))
        self.taux_tva_effectif = Decimal(str(taux))


class TestTvaBuckets(TestCase):
    def test_referentiel_exposes_canonical_rates(self):
        self.assertEqual(TAUX_TVA_REFERENTIEL['standard'], 20)
        self.assertEqual(TAUX_TVA_REFERENTIEL['panneaux'], 10)
        self.assertEqual(TAUX_TVA_REFERENTIEL['exonere'], 0)

    def test_mono_taux_uses_original_formula(self):
        # 3 lignes au même taux 20 % : un seul panier, HT × taux sans arrondi.
        lignes = [_Ligne(1000, 20), _Ligne(500, 20), _Ligne(250, 20)]
        out = tva_buckets(lignes, fallback_taux=20)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['taux'], Decimal('20'))
        self.assertEqual(out[0]['base_ht'], Decimal('1750'))
        self.assertEqual(out[0]['montant'], Decimal('350'))

    def test_no_lignes_falls_back_to_document_rate(self):
        out = tva_buckets([], fallback_taux=10)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['taux'], Decimal('10'))
        self.assertEqual(out[0]['base_ht'], Decimal('0'))
        self.assertEqual(out[0]['montant'], Decimal('0'))

    def test_mixed_rates_one_bucket_per_rate_cents_reconciled(self):
        # 10/20 : un panier par taux, chacun arrondi au centime.
        lignes = [_Ligne('1000.00', 10), _Ligne('500.00', 20),
                  _Ligne('333.33', 10)]
        out = tva_buckets(lignes, fallback_taux=20)
        self.assertEqual(len(out), 2)
        by_rate = {b['taux']: b for b in out}
        self.assertEqual(by_rate[Decimal('10')]['base_ht'], Decimal('1333.33'))
        self.assertEqual(by_rate[Decimal('10')]['montant'], Decimal('133.33'))
        self.assertEqual(by_rate[Decimal('20')]['base_ht'], Decimal('500.00'))
        self.assertEqual(by_rate[Decimal('20')]['montant'], Decimal('100.00'))
        # somme des montants = total TVA
        total = sum(b['montant'] for b in out)
        self.assertEqual(total, Decimal('233.33'))

    def test_frozen_returns_single_fixed_bucket(self):
        out = tva_buckets(
            [_Ligne('1000', 20)], fallback_taux=20,
            frozen=(Decimal('20'), Decimal('5000'), Decimal('1000')))
        self.assertEqual(out, [{'taux': Decimal('20'),
                                'base_ht': Decimal('5000'),
                                'montant': Decimal('1000')}])


class TestModelsShareOneImplementation(TestCase):
    """Devis, Facture et Avoir renvoient la même ventilation pour les mêmes
    lignes — preuve qu'ils consomment le selector unique."""

    def setUp(self):
        from authentication.models import Company
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from apps.ventes.models import (
            Devis, LigneDevis, Facture, LigneFacture, Avoir, LigneAvoir)
        self.company = Company.objects.get_or_create(
            slug='dc23-co', defaults={'nom': 'DC23 Co'})[0]
        self.client_obj = Client.objects.create(
            company=self.company, nom='C', prenom='D',
            telephone='+212600000099')
        self.pv = Produit.objects.create(
            company=self.company, nom='Panneau', sku='DC23PV',
            prix_vente=Decimal('1000'), quantite_stock=100)
        self.ond = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='DC23OND',
            prix_vente=Decimal('5000'), quantite_stock=10)

        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-DC23', client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=self.devis, produit=self.pv, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('10'))
        LigneDevis.objects.create(
            devis=self.devis, produit=self.ond, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20'))

        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-DC23', client=self.client_obj,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.pv, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('10'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.ond, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20'))

        self.avoir = Avoir.objects.create(
            company=self.company, reference='AVO-DC23', facture=self.facture,
            client=self.client_obj, statut=Avoir.Statut.EMISE,
            taux_tva=Decimal('20'))
        LigneAvoir.objects.create(
            avoir=self.avoir, produit=self.pv, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('10'))
        LigneAvoir.objects.create(
            avoir=self.avoir, produit=self.ond, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20'))

    def _norm(self, buckets):
        return sorted((b['taux'], b['base_ht'], b['montant']) for b in buckets)

    def test_all_three_models_agree(self):
        d = self._norm(self.devis.tva_par_taux)
        f = self._norm(self.facture.tva_par_taux)
        a = self._norm(self.avoir.tva_par_taux)
        self.assertEqual(d, f)
        self.assertEqual(f, a)
        # 10 % sur 10000 = 1000 ; 20 % sur 5000 = 1000 → 2000 TVA totale.
        self.assertEqual(sum(b['montant'] for b in self.facture.tva_par_taux),
                         Decimal('2000.00'))
