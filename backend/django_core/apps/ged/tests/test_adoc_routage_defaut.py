"""ADOC75 — routages documentaires par défaut pour les documents client."""
import importlib

from django.apps import apps as django_apps
from django.test import TestCase

from apps.ged import services
from apps.ged.models import Cabinet, RoutageDocumentaire
from authentication.models import Company

SOURCES = {'ventes_facture', 'ventes_avoir', 'ventes_note_debit',
           'ventes_remise'}


class RoutageDefautTests(TestCase):
    def test_nouvelle_societe_route_ses_factures(self):
        co = Company.objects.create(nom='Adoc75 A', slug='adoc75-a')
        routages = RoutageDocumentaire.objects.filter(company=co)
        self.assertEqual({r.source for r in routages}, SOURCES)
        self.assertTrue(all(r.actif and r.seme_par_defaut for r in routages))
        facture = routages.get(source='ventes_facture')
        self.assertEqual(facture.dossier_cible, 'Ventes/Factures/{{ annee }}')
        self.assertEqual(
            routages.get(source='ventes_avoir').dossier_cible,
            'Ventes/Avoirs/{{ annee }}')
        self.assertEqual(facture.cabinet_cible.company_id, co.pk)

    def test_reglage_existant_preserve(self):
        co = Company.objects.create(nom='Adoc75 B', slug='adoc75-b')
        RoutageDocumentaire.objects.filter(
            company=co, source='ventes_facture').update(
            dossier_cible='Perso', actif=False, seme_par_defaut=False)
        self.assertEqual(services.semer_routages_defaut(co), 0)
        r = RoutageDocumentaire.objects.get(
            company=co, source='ventes_facture')
        self.assertEqual((r.dossier_cible, r.actif), ('Perso', False))

    def test_semis_complete_les_sources_absentes_seulement(self):
        co = Company.objects.create(nom='Adoc75 C', slug='adoc75-c')
        RoutageDocumentaire.objects.filter(
            company=co, source__in=['ventes_avoir', 'ventes_remise']).delete()
        self.assertEqual(services.semer_routages_defaut(co), 2)
        self.assertEqual(
            RoutageDocumentaire.objects.filter(company=co).count(), 4)

    def test_migration_inverse_ne_touche_pas_les_reglages(self):
        mig = importlib.import_module(
            'apps.ged.migrations.0056_adoc75_routages_defaut')
        co = Company.objects.create(nom='Adoc75 D', slug='adoc75-d')
        cab = Cabinet.objects.create(company=co, nom='Mien')
        RoutageDocumentaire.objects.create(
            company=co, source='ventes_devis', cabinet_cible=cab,
            dossier_cible='Devis')
        mig.retirer(django_apps, None)
        restants = RoutageDocumentaire.objects.filter(company=co)
        self.assertEqual([r.source for r in restants], ['ventes_devis'])
        # Rejouer la migration de données recrée les 4 défauts sans doublon.
        mig.semer(django_apps, None)
        mig.semer(django_apps, None)
        self.assertEqual(
            RoutageDocumentaire.objects.filter(
                company=co, source__in=SOURCES).count(), 4)
