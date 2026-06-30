"""GED34 — Classification automatique (IA gated + heuristique locale).

Couvre :
  * l'heuristique locale (mots-clés) classe sans clé (facture/cin/contrat…) ;
  * le provider IA est NO-OP sans clé (fallback heuristique) ;
  * `classer_document` pose `custom_data['categorie']` de façon ADDITIVE
    (jamais d'écrasement d'une catégorie déjà posée) ;
  * un document non reconnu n'est jamais catégorisé arbitrairement ('') ;
  * isolation société (custom_data posé côté serveur).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from authentication.models import Company
from apps.ged import services
from apps.ged.models import Cabinet, Document, Folder

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class HeuristiqueTests(TestCase):
    def test_classe_facture(self):
        self.assertEqual(
            services.classer_heuristique('Facture EDF Total TTC 100'),
            'facture')

    def test_classe_cin(self):
        self.assertEqual(
            services.classer_heuristique('Carte nationale de M. X'), 'cin')

    def test_classe_contrat(self):
        self.assertEqual(
            services.classer_heuristique('Contrat de maintenance'), 'contrat')

    def test_inconnu_renvoie_vide(self):
        self.assertEqual(services.classer_heuristique('blabla random'), '')
        self.assertEqual(services.classer_heuristique(''), '')


class ClasserDocumentTests(TestCase):
    def setUp(self):
        self.co = make_company('ged34', 'Ged34')
        self.cab = Cabinet.objects.create(company=self.co, nom='Docs')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=self.cab, nom='Entrants')

    def _doc(self, nom):
        return Document.objects.create(
            company=self.co, folder=self.folder, nom=nom)

    @override_settings(GED_CLASSIFICATION_ENABLED=False)
    def test_ia_noop_fallback_heuristique(self):
        self.assertFalse(services.classification_enabled())
        doc = self._doc('Facture fournisseur')
        cat = services.classer_document(doc)
        self.assertEqual(cat, 'facture')
        doc.refresh_from_db()
        self.assertEqual(doc.custom_data.get('categorie'), 'facture')

    @override_settings(GED_CLASSIFICATION_ENABLED=True)
    def test_ia_active_sans_provider_reste_noop(self):
        # Flag activé mais aucun provider concret → classer_ia no-op, fallback.
        doc = self._doc('Contrat cadre')
        cat = services.classer_document(doc)
        self.assertEqual(cat, 'contrat')

    @override_settings(GED_CLASSIFICATION_ENABLED=False)
    def test_fusion_additive_sans_ecrasement(self):
        doc = self._doc('Facture')
        doc.custom_data = {'categorie': 'manuel'}
        doc.save(update_fields=['custom_data'])
        services.classer_document(doc)
        doc.refresh_from_db()
        self.assertEqual(doc.custom_data.get('categorie'), 'manuel')

    @override_settings(GED_CLASSIFICATION_ENABLED=False)
    def test_inconnu_ne_categorise_pas(self):
        doc = self._doc('xyz random sans mot-clé')
        cat = services.classer_document(doc)
        self.assertEqual(cat, '')
        doc.refresh_from_db()
        self.assertIsNone((doc.custom_data or {}).get('categorie'))
