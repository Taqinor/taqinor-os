"""AUD611 — le palier d'approbation voit la remise EFFECTIVE, pas la seule
remise globale.

La logique NTCPQ7 ne résolvait le palier que sur ``Devis.remise_globale``. Un
devis pouvait donc porter 0 % de remise globale et des remises de LIGNE
cumulées bien au-delà du seuil : il partait au client sans passer par la
moindre étape d'approbation. La remise de ligne et la remise globale sont le
MÊME geste commercial vu de deux endroits.

Run :
    python manage.py test apps.cpq.tests.test_aud611_remise_effective -v2
"""
from decimal import Decimal

from django.test import TestCase

from apps.cpq import services
from apps.cpq.models import RegleApprobationRemise
from testkit.factories import CompanyFactory, DevisFactory, LigneDevisFactory


class BasePalier(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        # Palier : remise 20-100 % → 2 approbateurs niveau direction.
        RegleApprobationRemise.objects.create(
            company=self.company, libelle='Remise forte',
            remise_min_pct=Decimal('20'), remise_max_pct=Decimal('100'),
            niveau_approbation=(
                RegleApprobationRemise.NiveauApprobation.DIRECTION),
            nombre_approbateurs=2)

    def _devis(self, *, remise_globale='0', remises_de_ligne=()):
        devis = DevisFactory(company=self.company,
                             remise_globale=Decimal(remise_globale))
        for remise in remises_de_ligne:
            LigneDevisFactory(devis=devis, quantite=Decimal('1'),
                              prix_unitaire=Decimal('1000.00'),
                              remise=Decimal(remise))
        return devis


class TestRemiseDeLigneDeclencheLApprobation(BasePalier):
    def test_zero_global_mais_remises_de_ligne_profondes(self):
        """LE cas du constat : 0 % global, 30 % sur chaque ligne."""
        devis = self._devis(remise_globale='0',
                            remises_de_ligne=('30', '30'))
        etapes = services.lancer_approbation_devis(devis)
        self.assertEqual(
            len(etapes), 2,
            "Un devis à 30 % de remise de ligne n'entre dans AUCUNE étape "
            "d'approbation.")

    def test_la_profondeur_vaut_bien_30(self):
        devis = self._devis(remise_globale='0',
                            remises_de_ligne=('30', '30'))
        self.assertEqual(services.profondeur_remise_effective(devis),
                         Decimal('30.00'))

    def test_remises_de_ligne_inegales_ponderees_par_le_montant(self):
        """Deux lignes de même prix, 40 % et 0 % → 20 % effectifs."""
        devis = self._devis(remise_globale='0',
                            remises_de_ligne=('40', '0'))
        self.assertEqual(services.profondeur_remise_effective(devis),
                         Decimal('20.00'))

    def test_le_cumul_ligne_plus_global_se_compose(self):
        """10 % de ligne PUIS 10 % global = 19 %, jamais 20 %."""
        devis = self._devis(remise_globale='10', remises_de_ligne=('10',))
        self.assertEqual(services.profondeur_remise_effective(devis),
                         Decimal('19.00'))


class TestComportementHistoriquePreserve(BasePalier):
    def test_sans_remise_de_ligne_la_profondeur_est_la_remise_globale(self):
        devis = self._devis(remise_globale='25', remises_de_ligne=('0',))
        self.assertEqual(services.profondeur_remise_effective(devis),
                         Decimal('25.00'))
        self.assertEqual(len(services.lancer_approbation_devis(devis)), 2)

    def test_un_devis_sans_ligne_retombe_sur_la_remise_globale(self):
        devis = DevisFactory(company=self.company,
                             remise_globale=Decimal('25'))
        self.assertEqual(services.profondeur_remise_effective(devis),
                         Decimal('25'))

    def test_une_remise_faible_ne_declenche_toujours_rien(self):
        devis = self._devis(remise_globale='0', remises_de_ligne=('8',))
        self.assertEqual(services.lancer_approbation_devis(devis), [])

    def test_la_profondeur_ne_descend_jamais_sous_la_remise_globale(self):
        """Garde-fou : une donnée de ligne aberrante n'affaiblit aucun palier."""
        devis = self._devis(remise_globale='25', remises_de_ligne=('-10',))
        self.assertGreaterEqual(
            services.profondeur_remise_effective(devis), Decimal('25'))


class TestSurchargeDeLaRemiseEntrante(BasePalier):
    """Le garde d'envoi juge la valeur ENTRANTE, pas celle encore en base."""

    def test_la_remise_globale_passee_prime_sur_celle_de_l_instance(self):
        devis = self._devis(remise_globale='0', remises_de_ligne=('10',))
        self.assertEqual(
            services.profondeur_remise_effective(devis,
                                                 remise_globale=Decimal('10')),
            Decimal('19.00'))
