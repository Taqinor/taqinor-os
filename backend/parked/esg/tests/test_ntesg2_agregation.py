"""NTESG2 — Sélecteur d'agrégation cross-app en lecture
``agreger_indicateurs_periode``.

Critère d'acceptation : appeler le sélecteur sur une société SANS AUCUNE
donnée renvoie une structure vide avec tous les indicateurs
``disponible=False``, SANS exception. Couvre aussi la dégradation gracieuse
par source et le chemin « avec vraies données » pour qhse/flotte/rh.
"""
from datetime import date

from django.test import TestCase

from testkit.factories import CompanyFactory

from apps.esg.selectors import agreger_indicateurs_periode


class AgregationEmptyCompanyTests(TestCase):
    def test_no_company_returns_all_unavailable_without_exception(self):
        data = agreger_indicateurs_periode(None, date(2026, 1, 1), date(2026, 3, 31))
        for cle, source in data['sources'].items():
            self.assertFalse(
                source['disponible'], f'source {cle} devrait être False')
            self.assertIn('raison', source)

    def test_empty_company_returns_all_unavailable_without_exception(self):
        company = CompanyFactory()
        data = agreger_indicateurs_periode(
            company, date(2026, 1, 1), date(2026, 3, 31))
        self.assertEqual(data['periode']['annee'], 2026)
        for cle, source in data['sources'].items():
            self.assertFalse(
                source['disponible'], f'source {cle} devrait être False')
            self.assertIn('raison', source)

    def test_bilan_carbone_always_documented_unavailable(self):
        """Aucun sélecteur qhse.selectors n'existe pour BilanCarbone au
        moment de ce lane (NTESG2) — source documentée, jamais un import de
        modèle pour contourner la frontière cross-app."""
        company = CompanyFactory()
        data = agreger_indicateurs_periode(
            company, date(2026, 1, 1), date(2026, 3, 31))
        bilan = data['sources']['bilan_carbone']
        self.assertFalse(bilan['disponible'])
        self.assertIn('sélecteur', bilan['raison'])


class AgregationRealDataTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()

    def test_indicateurs_esg_available_with_real_data(self):
        from apps.qhse.models import IndicateurESG

        IndicateurESG.objects.create(
            company=self.company, code='E1', libelle='Énergie',
            pilier=IndicateurESG.Pilier.ENVIRONNEMENT, valeur=42, annee=2026)
        data = agreger_indicateurs_periode(
            self.company, date(2026, 1, 1), date(2026, 12, 31))
        indic = data['sources']['indicateurs_esg']
        self.assertTrue(indic['disponible'])
        self.assertEqual(indic['total'], 1)

    def test_carburant_flotte_available_with_real_data(self):
        from apps.flotte.models import PleinCarburant, Vehicule

        vehicule = Vehicule.objects.create(
            company=self.company, immatriculation='1234-A-12',
            energie=Vehicule.Energie.DIESEL)
        PleinCarburant.objects.create(
            company=self.company, vehicule=vehicule,
            date_plein=date(2026, 2, 1), kilometrage=1000,
            quantite=50, unite=PleinCarburant.Unite.LITRE)
        data = agreger_indicateurs_periode(
            self.company, date(2026, 1, 1), date(2026, 12, 31))
        carburant = data['sources']['carburant_flotte']
        self.assertTrue(carburant['disponible'])
        self.assertEqual(carburant['gasoil_litres'], 50.0)

    def test_social_hse_available_with_real_accident(self):
        from apps.rh.models import AccidentTravail, DossierEmploye

        employe = DossierEmploye.objects.create(
            company=self.company, matricule='M1', nom='Alami', prenom='Ali',
            statut=DossierEmploye.Statut.ACTIF)
        AccidentTravail.objects.create(
            company=self.company, employe=employe, reference='AT-TEST-0001',
            date_accident=date(2026, 2, 15),
            gravite=AccidentTravail.Gravite.LEGER)
        data = agreger_indicateurs_periode(
            self.company, date(2026, 1, 1), date(2026, 12, 31))
        social = data['sources']['social_hse']
        self.assertTrue(social['disponible'])
        self.assertEqual(social['accidents_total'], 1)

    def test_effectifs_available_with_active_employee(self):
        from apps.rh.models import DossierEmploye

        DossierEmploye.objects.create(
            company=self.company, matricule='M2', nom='Bennani',
            prenom='Sara', statut=DossierEmploye.Statut.ACTIF)
        data = agreger_indicateurs_periode(
            self.company, date(2026, 1, 1), date(2026, 12, 31))
        effectifs = data['sources']['effectifs']
        self.assertTrue(effectifs['disponible'])
        self.assertEqual(effectifs['effectif_actif'], 1)

    def test_source_degrades_gracefully_on_exception(self):
        """Une source qui lève une exception (signature changée, app
        cassée…) dégrade en disponible=False plutôt que de faire échouer
        toute l'agrégation."""
        import apps.esg.selectors as esg_selectors

        original = esg_selectors._source_effectifs

        def _boom(company):
            raise RuntimeError('boom')

        esg_selectors._source_effectifs = _boom
        try:
            data = agreger_indicateurs_periode(
                self.company, date(2026, 1, 1), date(2026, 12, 31))
        finally:
            esg_selectors._source_effectifs = original
        # L'agrégation entière n'a jamais planté malgré la source cassée.
        self.assertIn('sources', data)
