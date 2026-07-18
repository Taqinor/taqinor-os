"""ADSDEEP46 — Tests du parseur de convention de nommage créative (PUR, aucun
LLM), barre Motion (benchmark concurrent §2).

Prouve : découpage POSITIONNEL d'un nom réel selon une convention configurable
(``DATE_FORMAT_HOOK_ANGLE``), tags hook/angle/format toujours des chaînes
(jamais ``None``), un nom mal formé/tronqué ne casse rien (tags partiels), et
le retro-tag company-scopé (``AdMirror`` via ``name``, ``CreativeAsset`` via
``file_key``) est idempotent.
"""
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import naming
from apps.adsengine.models import AdMirror, CreativeAsset


class ParseConventionTests(SimpleTestCase):
    def test_splits_into_lowercase_fields(self):
        self.assertEqual(
            naming.parse_convention('DATE_FORMAT_HOOK_ANGLE'),
            ['date', 'format', 'hook', 'angle'])

    def test_empty_or_none_convention_gives_empty_list(self):
        self.assertEqual(naming.parse_convention(''), [])
        self.assertEqual(naming.parse_convention(None), [])


class ParseNameTests(SimpleTestCase):
    def test_parses_real_account_name(self):
        parsed = naming.parse_name(
            '26_UGC_PAIN_ROI', convention='DATE_FORMAT_HOOK_ANGLE')
        self.assertEqual(parsed, {
            'date': '26', 'format': 'UGC', 'hook': 'PAIN', 'angle': 'ROI'})

    def test_different_delimiter(self):
        parsed = naming.parse_name(
            '26-UGC-PAIN-ROI', convention='DATE_FORMAT_HOOK_ANGLE',
            delimiter='-')
        self.assertEqual(parsed['hook'], 'PAIN')

    def test_shorter_name_leaves_trailing_fields_absent(self):
        # Nom tronqué : seulement date+format, pas de hook/angle.
        parsed = naming.parse_name(
            '26_UGC', convention='DATE_FORMAT_HOOK_ANGLE')
        self.assertEqual(parsed, {'date': '26', 'format': 'UGC'})
        self.assertNotIn('hook', parsed)
        self.assertNotIn('angle', parsed)

    def test_empty_or_none_name_gives_empty_dict(self):
        self.assertEqual(naming.parse_name(''), {})
        self.assertEqual(naming.parse_name(None), {})

    def test_no_convention_gives_empty_dict(self):
        self.assertEqual(
            naming.parse_name('26_UGC_PAIN_ROI', convention=''), {})


class TagsFromNameTests(SimpleTestCase):
    def test_full_name_produces_all_three_tags(self):
        tags = naming.tags_from_name(
            '26_UGC_PAIN_ROI', convention='DATE_FORMAT_HOOK_ANGLE')
        self.assertEqual(tags, {
            'hook_tag': 'PAIN', 'angle_tag': 'ROI', 'format_tag': 'UGC'})

    def test_missing_segments_give_empty_strings_never_none(self):
        tags = naming.tags_from_name(
            '26_UGC', convention='DATE_FORMAT_HOOK_ANGLE')
        self.assertEqual(tags['hook_tag'], '')
        self.assertEqual(tags['angle_tag'], '')
        self.assertIsNotNone(tags['hook_tag'])

    def test_malformed_name_never_raises(self):
        # Ni séparateur, ni longueur attendue : jamais une exception.
        tags = naming.tags_from_name('un-nom-au-hasard-sans-convention')
        self.assertIsInstance(tags, dict)
        self.assertIn('hook_tag', tags)


class BasenameWithoutExtensionTests(SimpleTestCase):
    def test_strips_path_and_extension(self):
        self.assertEqual(
            naming._basename_without_extension(
                'societe/2026_UGC_PAIN_ROI.mp4'),
            '2026_UGC_PAIN_ROI')

    def test_empty_path_gives_empty_string(self):
        self.assertEqual(naming._basename_without_extension(''), '')
        self.assertEqual(naming._basename_without_extension(None), '')

    def test_windows_style_path(self):
        self.assertEqual(
            naming._basename_without_extension(
                'societe\\dossier\\26_UGC_PAIN_ROI.mov'),
            '26_UGC_PAIN_ROI')


class RetagCompanyAdsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Tag Co', slug='tag-co')

    def test_retags_ads_from_name(self):
        AdMirror.objects.create(
            company=self.company, meta_id='a1', name='26_UGC_PAIN_ROI')
        AdMirror.objects.create(
            company=self.company, meta_id='a2', name='27_Statique_PRIX_URGENCE')
        updated = naming.retag_company_ads(self.company)
        self.assertEqual(updated, 2)
        ad1 = AdMirror.objects.get(meta_id='a1')
        self.assertEqual(ad1.hook_tag, 'PAIN')
        self.assertEqual(ad1.angle_tag, 'ROI')
        self.assertEqual(ad1.format_tag, 'UGC')

    def test_idempotent_second_pass_updates_nothing(self):
        AdMirror.objects.create(
            company=self.company, meta_id='a1', name='26_UGC_PAIN_ROI')
        naming.retag_company_ads(self.company)
        second_pass = naming.retag_company_ads(self.company)
        self.assertEqual(second_pass, 0)

    def test_scoped_to_company(self):
        other = Company.objects.create(nom='Other', slug='other-tag')
        AdMirror.objects.create(
            company=other, meta_id='o1', name='26_UGC_PAIN_ROI')
        AdMirror.objects.create(
            company=self.company, meta_id='a1', name='26_UGC_PAIN_ROI')
        updated = naming.retag_company_ads(self.company)
        self.assertEqual(updated, 1)
        self.assertEqual(
            AdMirror.objects.get(meta_id='o1').hook_tag, '')

    def test_unparseable_name_leaves_tags_empty(self):
        AdMirror.objects.create(
            company=self.company, meta_id='a3', name='')
        updated = naming.retag_company_ads(self.company)
        self.assertEqual(updated, 0)


class RetagCompanyCreativeAssetsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Asset Co', slug='asset-co')

    def test_retags_from_file_key_basename(self):
        CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.REEL,
            file_key='asset-co/2026_UGC_PAIN_ROI.mp4')
        updated = naming.retag_company_creative_assets(self.company)
        self.assertEqual(updated, 1)
        asset = CreativeAsset.objects.first()
        self.assertEqual(asset.hook_tag, 'PAIN')
        self.assertEqual(asset.angle_tag, 'ROI')
        self.assertEqual(asset.format_tag, 'UGC')

    def test_empty_file_key_never_raises(self):
        CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC,
            file_key='')
        updated = naming.retag_company_creative_assets(self.company)
        self.assertEqual(updated, 0)
