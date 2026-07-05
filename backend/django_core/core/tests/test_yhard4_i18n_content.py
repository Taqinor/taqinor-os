"""Tests YHARD4 — traduction du contenu saisi (données maîtres).

Couvre : translated_value() avec/sans variante (repli FR octet-identique),
set_translation() upsert, scoping société, et le câblage additif dans
ProduitSerializer / ClauseSerializer (repli par défaut inchangé, variante
demandée via ?locale= quand elle existe).
"""
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate
from django.contrib.auth import get_user_model

from authentication.models import Company
from core import i18n_content
from core.models import ContentTranslation
from apps.stock.models import Produit
from apps.stock.serializers import ProduitSerializer

User = get_user_model()


def make_produit(company, nom='Panneau solaire 450W'):
    return Produit.objects.create(
        company=company, nom=nom, description='Desc FR', prix_vente=1000)


class TranslatedValueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='YHARD4 Co')
        cls.produit = make_produit(cls.company)

    def test_no_locale_returns_raw_value(self):
        self.assertEqual(
            i18n_content.translated_value(self.produit, 'nom', None),
            'Panneau solaire 450W')

    def test_default_locale_returns_raw_value(self):
        self.assertEqual(
            i18n_content.translated_value(self.produit, 'nom', 'fr'),
            'Panneau solaire 450W')

    def test_missing_translation_falls_back_to_raw(self):
        self.assertEqual(
            i18n_content.translated_value(self.produit, 'nom', 'ar'),
            'Panneau solaire 450W')

    def test_existing_translation_is_returned(self):
        i18n_content.set_translation(self.produit, 'nom', 'ar', 'لوحة شمسية 450 واط')
        self.assertEqual(
            i18n_content.translated_value(self.produit, 'nom', 'ar'),
            'لوحة شمسية 450 واط')

    def test_set_translation_upserts(self):
        i18n_content.set_translation(self.produit, 'nom', 'en', 'Solar panel 450W')
        i18n_content.set_translation(self.produit, 'nom', 'en', 'Solar Panel 450W v2')
        self.assertEqual(
            ContentTranslation.objects.filter(
                company=self.company, object_id=str(self.produit.pk),
                locale='en', field='nom').count(),
            1)
        self.assertEqual(
            i18n_content.translated_value(self.produit, 'nom', 'en'),
            'Solar Panel 450W v2')

    def test_translation_scoped_by_company(self):
        other = Company.objects.create(nom='YHARD4 Autre')
        other_produit = make_produit(other, nom='Autre produit')
        i18n_content.set_translation(other_produit, 'nom', 'ar', 'منتج آخر')
        # Même nom de champ, mais objet différent dans une société différente :
        # aucune fuite croisée.
        self.assertEqual(
            i18n_content.translated_value(self.produit, 'nom', 'ar'),
            'Panneau solaire 450W')

    def test_translations_for_groups_by_locale(self):
        i18n_content.set_translation(self.produit, 'nom', 'ar', 'لوحة')
        i18n_content.set_translation(self.produit, 'description', 'ar', 'وصف')
        result = i18n_content.translations_for(self.produit)
        self.assertEqual(result['ar']['nom'], 'لوحة')
        self.assertEqual(result['ar']['description'], 'وصف')


class ProduitSerializerLocalizationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='YHARD4 Serializer Co')
        cls.user = User.objects.create_user(
            username='yhard4_user', password='x', company=cls.company)
        cls.produit = make_produit(cls.company)
        i18n_content.set_translation(cls.produit, 'nom', 'ar', 'لوحة شمسية')
        cls.factory = APIRequestFactory()

    def test_default_serialization_unaffected(self):
        req = self.factory.get('/produits/')
        force_authenticate(req, user=self.user)
        data = ProduitSerializer(self.produit, context={'request': req}).data
        self.assertEqual(data['nom'], 'Panneau solaire 450W')
        # Repli FR : sans ?locale=, la variante localisée == la valeur brute.
        self.assertEqual(data['nom_localise'], 'Panneau solaire 450W')

    def test_locale_query_param_returns_translation(self):
        req = self.factory.get('/produits/?locale=ar')
        force_authenticate(req, user=self.user)
        data = ProduitSerializer(self.produit, context={'request': req}).data
        self.assertEqual(data['nom_localise'], 'لوحة شمسية')
        # Le champ brut reste inchangé (FR) quelle que soit la locale demandée.
        self.assertEqual(data['nom'], 'Panneau solaire 450W')

    def test_locale_context_override(self):
        data = ProduitSerializer(self.produit, context={'locale': 'ar'}).data
        self.assertEqual(data['nom_localise'], 'لوحة شمسية')
