"""NTCPQ49 — KPI « Taux d'utilisation des offres groupées » et « Taux de
conversion configurateur » (hub KPI fédéré ARC40, widget existant)."""
from django.test import TestCase
from django.utils import timezone

from apps.cpq import platform, selectors, services
from apps.cpq.models import (
    LigneOffreGroupee, OffreGroupee, SessionConfigurateur,
)
from apps.ventes.models import Devis
from testkit.factories import CompanyFactory, DevisFactory, ProduitFactory, UserFactory


class TestTauxUtilisationOffresGroupees(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company)
        self.produit = ProduitFactory(company=self.company)

    def _devis_envoye(self):
        devis = DevisFactory(company=self.company)
        devis.statut = Devis.Statut.ENVOYE
        devis.date_envoi = timezone.now()
        devis.save(update_fields=['statut', 'date_envoi'])
        return devis

    def test_zero_sans_devis_envoye(self):
        self.assertEqual(
            selectors.taux_utilisation_offres_groupees(self.company), 0.0)

    def test_taux_avec_un_bundle_sur_deux(self):
        offre = OffreGroupee.objects.create(
            company=self.company, nom='Pack Solaire')
        LigneOffreGroupee.objects.create(
            offre=offre, produit=self.produit, quantite=1)
        devis_avec_bundle = self._devis_envoye()
        services.appliquer_offre_groupee(
            offre=offre, devis=devis_avec_bundle, user=self.user)
        self._devis_envoye()  # devis envoyé SANS bundle
        taux = selectors.taux_utilisation_offres_groupees(self.company)
        self.assertEqual(taux, 50.0)

    def test_devis_brouillon_non_envoye_exclu(self):
        offre = OffreGroupee.objects.create(company=self.company, nom='X')
        LigneOffreGroupee.objects.create(
            offre=offre, produit=self.produit, quantite=1)
        devis_brouillon = DevisFactory(company=self.company)  # jamais envoyé
        services.appliquer_offre_groupee(
            offre=offre, devis=devis_brouillon, user=self.user)
        # Aucun devis ENVOYÉ dans la société → dénominateur nul → 0.0.
        self.assertEqual(
            selectors.taux_utilisation_offres_groupees(self.company), 0.0)


class TestTauxConversionConfigurateur(TestCase):
    def setUp(self):
        self.company = CompanyFactory()

    def test_zero_sans_session(self):
        self.assertEqual(
            selectors.taux_conversion_configurateur(self.company), 0.0)

    def test_conversion_une_session_sur_deux(self):
        devis_envoye = DevisFactory(company=self.company)
        devis_envoye.statut = Devis.Statut.ENVOYE
        devis_envoye.date_envoi = timezone.now()
        devis_envoye.save(update_fields=['statut', 'date_envoi'])
        SessionConfigurateur.objects.create(
            company=self.company, devis=devis_envoye)
        # Session sans devis du tout (jamais générée) — ne convertit pas.
        SessionConfigurateur.objects.create(company=self.company)
        taux = selectors.taux_conversion_configurateur(self.company)
        self.assertEqual(taux, 50.0)

    def test_devis_brouillon_non_envoye_jamais_compte_converti(self):
        devis_brouillon = DevisFactory(company=self.company)  # jamais envoyé
        SessionConfigurateur.objects.create(
            company=self.company, devis=devis_brouillon)
        # Une session existe (dénominateur=1) mais son devis n'est pas
        # envoyé → 0 % (jamais compté converti au brouillon).
        self.assertEqual(
            selectors.taux_conversion_configurateur(self.company), 0.0)


class TestKpiTauxBundleConfigurateurProvider(TestCase):
    def setUp(self):
        self.company = CompanyFactory()

    def test_aucune_tuile_sans_donnees(self):
        self.assertEqual(
            selectors.kpi_taux_bundle_configurateur(self.company), [])

    def test_declare_dans_le_manifeste_plateforme(self):
        self.assertIn(
            'apps.cpq.selectors.kpi_taux_bundle_configurateur',
            platform.PLATFORM['kpi_providers'])
