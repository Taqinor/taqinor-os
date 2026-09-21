"""NTJUR48 — KPI juridiques exposés à ``reporting``.

Critère d'acceptation : « le KPI ``juridique_taux_gain`` apparaît dans le
picker de KPI de ``reporting`` et se calcule correctement sur un jeu de test
avec dossiers gagnés/perdus/en cours mélangés ».
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.juridique import selectors
from apps.juridique.models import DossierJuridique
from apps.reporting.kpi_alertes import _KPI_COMPUTERS, kpis_disponibles
from apps.reporting.models import KpiAlerte

from ._base import make_admin, make_company, make_responsable


class KpiJuridiquesTests(TestCase):
    def setUp(self):
        self.company = make_company('jur-k48-co', 'Juridique K48')
        self.admin = make_admin(self.company, 'jur-k48-admin')
        self.responsable = make_responsable(self.company, 'jur-k48-resp')

    def _dossier(self, reference, statut, montant='0', confidentiel=False):
        return DossierJuridique.objects.create(
            company=self.company, reference=reference, titre=f'D {reference}',
            date_ouverture=date(2026, 1, 1), statut=statut,
            montant_en_jeu=Decimal(montant),
            confidentialite=(
                DossierJuridique.NiveauConfidentialite.CONFIDENTIEL
                if confidentiel
                else DossierJuridique.NiveauConfidentialite.INTERNE))

    def test_les_quatre_cles_sont_au_catalogue_et_calculables(self):
        for cle in ('juridique_dossiers_ouverts',
                    'juridique_montant_en_jeu_total',
                    'juridique_taux_gain',
                    'juridique_delai_moyen_resolution'):
            self.assertIn(cle, KpiAlerte.Kpi.values)
            self.assertIn(cle, _KPI_COMPUTERS)
        # …et le picker de reporting les propose.
        self.assertIn('juridique_taux_gain', kpis_disponibles(self.company))

    def test_taux_de_gain_sur_un_jeu_melange(self):
        self._dossier('JUR-2026-0001', DossierJuridique.Statut.CLOS_GAGNE)
        self._dossier('JUR-2026-0002', DossierJuridique.Statut.CLOS_GAGNE)
        self._dossier('JUR-2026-0003', DossierJuridique.Statut.CLOS_PERDU)
        self._dossier('JUR-2026-0004', DossierJuridique.Statut.CLOS_TRANSACTION)
        # Un dossier ENCORE OUVERT ne pèse jamais sur le taux de gain.
        self._dossier('JUR-2026-0005', DossierJuridique.Statut.INSTRUCTION)
        kpis = selectors.kpis_juridiques(self.company, user=self.admin)
        self.assertEqual(kpis['juridique_taux_gain'], 50.0)
        self.assertEqual(kpis['juridique_dossiers_ouverts'], 1)

    def test_taux_de_gain_indefini_sans_dossier_clos(self):
        """Aucun dossier clos : ``None``, jamais un 0 % qui mentirait."""
        self._dossier('JUR-2026-0006', DossierJuridique.Statut.OUVERT)
        kpis = selectors.kpis_juridiques(self.company, user=self.admin)
        self.assertIsNone(kpis['juridique_taux_gain'])
        self.assertIsNone(kpis['juridique_delai_moyen_resolution'])

    def test_montant_en_jeu_ne_compte_que_les_dossiers_ouverts(self):
        self._dossier('JUR-2026-0007', DossierJuridique.Statut.OUVERT,
                      montant='100000')
        self._dossier('JUR-2026-0008', DossierJuridique.Statut.CLOS_PERDU,
                      montant='900000')
        kpis = selectors.kpis_juridiques(self.company, user=self.admin)
        self.assertEqual(kpis['juridique_montant_en_jeu_total'],
                         Decimal('100000.00'))

    def test_les_kpi_excluent_les_confidentiels_pour_un_role_non_autorise(self):
        self._dossier('JUR-2026-0009', DossierJuridique.Statut.OUVERT,
                      montant='10000')
        self._dossier('JUR-2026-0010', DossierJuridique.Statut.OUVERT,
                      montant='500000', confidentiel=True)
        vu = selectors.kpis_juridiques(self.company, user=self.responsable)
        self.assertEqual(vu['juridique_dossiers_ouverts'], 1)
        self.assertEqual(vu['juridique_montant_en_jeu_total'],
                         Decimal('10000.00'))
        complet = selectors.kpis_juridiques(self.company, user=self.admin)
        self.assertEqual(complet['juridique_dossiers_ouverts'], 2)
        self.assertEqual(complet['juridique_montant_en_jeu_total'],
                         Decimal('510000.00'))

    def test_le_computer_reporting_rend_un_decimal_ou_none(self):
        self._dossier('JUR-2026-0011', DossierJuridique.Statut.CLOS_GAGNE)
        computer = _KPI_COMPUTERS[KpiAlerte.Kpi.JURIDIQUE_TAUX_GAIN]
        self.assertEqual(computer(self.company, self.admin), Decimal('100.0'))
        vide = _KPI_COMPUTERS[
            KpiAlerte.Kpi.JURIDIQUE_DELAI_MOYEN_RESOLUTION]
        self.assertIsNotNone(vide(self.company, self.admin))
