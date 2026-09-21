"""NTSCM36 — Purge planifiée des anciennes prévisions.

Critère d'acceptation : une prévision de 30 mois non liée à un cycle est
supprimée, une prévision de 30 mois liée à un cycle clos est conservée."""
from django.test import TestCase
from django.utils import timezone

from apps.scm.models import CyclePlanificationSOP, LigneDemandeSOP, PrevisionDemande
from apps.scm.tasks import purger_donnees_scm_anciennes
from apps.stock.models import Produit

from .helpers import make_company


class PurgerDonneesScmAnciennesTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-purge', 'Supply Purge')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 450Wc', prix_vente=1500,
            quantite_stock=100)

    def _periode(self, offset_mois):
        today = timezone.localdate()
        idx = today.year * 12 + (today.month - 1) - offset_mois
        y, m0 = divmod(idx, 12)
        return f'{y:04d}-{m0 + 1:02d}'

    def test_prevision_ancienne_non_liee_est_supprimee(self):
        periode_30 = self._periode(30)
        PrevisionDemande.objects.create(
            company=self.company, produit=self.produit, segment='',
            periode=periode_30, quantite_prevue=10)

        resultat = purger_donnees_scm_anciennes()
        ligne = next(r for r in resultat if r['company_id'] == self.company.id)
        self.assertEqual(ligne['nb_supprimees'], 1)
        self.assertFalse(
            PrevisionDemande.objects.filter(
                company=self.company, periode=periode_30).exists())

    def test_prevision_ancienne_liee_a_un_cycle_clos_est_conservee(self):
        periode_30 = self._periode(30)
        PrevisionDemande.objects.create(
            company=self.company, produit=self.produit, segment='',
            periode=periode_30, quantite_prevue=10)
        cycle = CyclePlanificationSOP.objects.create(
            company=self.company, periode=periode_30,
            statut=CyclePlanificationSOP.Statut.CLOS)
        LigneDemandeSOP.objects.create(
            company=self.company, cycle=cycle, produit=self.produit,
            quantite_prevision_systeme=10)

        resultat = purger_donnees_scm_anciennes()
        ligne = next(r for r in resultat if r['company_id'] == self.company.id)
        self.assertEqual(ligne['nb_supprimees'], 0)
        self.assertTrue(
            PrevisionDemande.objects.filter(
                company=self.company, periode=periode_30).exists())

    def test_prevision_recente_est_conservee(self):
        periode_recente = self._periode(1)
        PrevisionDemande.objects.create(
            company=self.company, produit=self.produit, segment='',
            periode=periode_recente, quantite_prevue=10)

        resultat = purger_donnees_scm_anciennes()
        ligne = next(r for r in resultat if r['company_id'] == self.company.id)
        self.assertEqual(ligne['nb_supprimees'], 0)
