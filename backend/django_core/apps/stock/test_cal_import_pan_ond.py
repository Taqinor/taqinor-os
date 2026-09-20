"""CAL117 — import OPTIONNEL d'une fiche constructeur .PAN / .OND.

ROUGE avant CAL117 : ``grep -rniI "\\.pan|\\.ond|import_fiche" apps/stock``
ne rendait que des faux positifs (``self.panneau``) — toute fiche se
saisissait à la main, aucun parseur n'existait. VERT : un parseur PUR
(stdlib seule, hors Django) qui propose un mapping vers ``FicheTechnique``,
n'écrase JAMAIS un champ déjà saisi, liste les clés non reconnues, et
n'écrit qu'après confirmation explicite (``confirmer=true``) via l'action
``importer-datasheet``.

Run :
    docker compose exec django_core python manage.py test \
        apps.stock.tests.test_import_pan_ond -v 2
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.stock.importers.fiche_pan_ond import (
    FichierIllisible,
    champs_a_ecrire,
    parse_pan_ond_bytes,
    parse_pan_ond_text,
    propose_mapping,
)
from apps.stock.models import FicheTechnique, Produit
from authentication.models import Company, CustomUser

# ── Fixtures COMMITÉES — un .PAN et un .OND synthétiques (format PVsyst
# clé=valeur, sections/en-têtes réels) exercés par le parseur pur. ──
FICHIER_PAN = """
PVObject_=pvModule
  Comment=www.pvsyst.com - synthetic CAL117 fixture, jamais un vrai produit
  Flags=$00381027

  PVObject_Commercial=
    Manufacturer=CAL117 Fixture
    Model=GEN-550
  End of PVObject_Commercial

  PNom=550.000
  Voc=49.500
  Isc=13.900
  Vmpp=41.400
  Impp=13.290
  Weight=27.500
  Width=1.134
  Height=2.278
  NCelS=144
  muISC=7.500
  muVocSpec=-123.500

  Remarks, Count=1
    Str_1=Synthetic fixture for CAL117 tests
  End of Remarks
End of PVObject_=pvModule
""".strip()

FICHIER_OND = """
PVObject_=pvInverter
  PVObject_Commercial=
    Manufacturer=CAL117 Fixture
    Model=OND-6000
  End of PVObject_Commercial

  Pnom=6000.000
  NbMPPT=2
  VMppMin=120.000
  VMPPMax=550.000
  VAbsMax=600.000
  IMaxMPP=13.500
End of PVObject_=pvInverter
""".strip()


class ParsePanOndPurTests(TestCase):
    """Le parseur est pur (aucun import Django) — ces tests l'exercent
    directement, sans base de données."""

    def test_pan_type_et_mapping(self):
        proposition = propose_mapping(FICHIER_PAN)
        self.assertEqual(proposition.type_fiche, 'module')
        self.assertEqual(proposition.mapping['pmax_wc'], Decimal('550.000'))
        self.assertEqual(proposition.mapping['voc_v'], Decimal('49.500'))
        self.assertEqual(
            proposition.mapping['largeur_mm'], Decimal('1134.000'))
        self.assertEqual(
            proposition.mapping['longueur_mm'], Decimal('2278.000'))

    def test_pan_cles_non_reconnues_listees(self):
        proposition = propose_mapping(FICHIER_PAN)
        # Les coefficients de température PVsyst (mV/°C) ne sont PAS
        # convertis automatiquement (unité incompatible sans hypothèse
        # supplémentaire) — ils doivent être listés, jamais ignorés en
        # silence.
        self.assertIn('muISC', proposition.non_reconnus)
        self.assertIn('muVocSpec', proposition.non_reconnus)
        self.assertIn('Manufacturer', proposition.non_reconnus)
        self.assertNotIn('PVObject_', proposition.non_reconnus)

    def test_ond_type_et_mapping(self):
        proposition = propose_mapping(FICHIER_OND)
        self.assertEqual(proposition.type_fiche, 'onduleur')
        self.assertEqual(proposition.mapping['ond_ac_kw'], Decimal('6.000'))
        self.assertEqual(proposition.mapping['ond_n_mppt'], 2)
        self.assertEqual(
            proposition.mapping['ond_mppt_v_min'], Decimal('120.000'))

    def test_fichier_illisible_type_indetermine(self):
        with self.assertRaises(FichierIllisible) as ctx:
            propose_mapping('rien ici ne ressemble à du PVsyst')
        self.assertEqual(ctx.exception.champ, 'file')

    def test_parse_pan_ond_bytes_utf8_et_latin1(self):
        proposition = parse_pan_ond_bytes(FICHIER_PAN.encode('utf-8'))
        self.assertEqual(proposition.type_fiche, 'module')
        proposition_latin1 = parse_pan_ond_bytes(
            FICHIER_PAN.encode('latin-1'))
        self.assertEqual(proposition_latin1.type_fiche, 'module')

    def test_parse_pan_ond_bytes_encodage_illisible(self):
        with self.assertRaises(FichierIllisible):
            parse_pan_ond_bytes(b'\xff\xfe\x00\x01garbage')

    def test_parse_pan_ond_text_ignore_lignes_sans_egal(self):
        raw = parse_pan_ond_text('sans egal ici\nPNom=100.0\n')
        self.assertEqual(raw['PNom'], '100.0')
        self.assertNotIn('sans egal ici', raw)


class ChampsAEcrireTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='cal117-stock-co', defaults={'nom': 'CAL117 Stock'})[0]
        self.produit = Produit.objects.create(
            company=self.co, nom='Module CAL117', sku='CAL117-MOD',
            prix_achat=Decimal('600'), prix_vente=Decimal('900'),
            quantite_stock=1)

    def test_aucun_ecrasement_silencieux(self):
        """Un champ déjà saisi n'est JAMAIS dans ``a_ecrire`` — il part en
        ``deja_saisis``, jamais remplacé."""
        fiche = FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='module',
            pmax_wc=Decimal('500.00'))
        proposition = propose_mapping(FICHIER_PAN)
        a_ecrire, deja_saisis = champs_a_ecrire(fiche, proposition.mapping)
        self.assertNotIn('pmax_wc', a_ecrire)
        self.assertIn('pmax_wc', deja_saisis)
        self.assertIn('voc_v', a_ecrire)

    def test_fiche_vide_tout_ecrivable(self):
        fiche = FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='module')
        proposition = propose_mapping(FICHIER_PAN)
        a_ecrire, deja_saisis = champs_a_ecrire(fiche, proposition.mapping)
        self.assertEqual(deja_saisis, [])
        self.assertEqual(a_ecrire['pmax_wc'], Decimal('550.000'))


class ImporterDatasheetEndpointTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='cal117-api-co', defaults={'nom': 'CAL117 API'})[0]
        self.autre_co = Company.objects.get_or_create(
            slug='cal117-autre-co', defaults={'nom': 'CAL117 Autre'})[0]
        self.user = CustomUser.objects.create_user(
            username='cal117-user', password='x', company=self.co,
            is_superuser=True, is_staff=True)
        self.produit = Produit.objects.create(
            company=self.co, nom='Module API CAL117', sku='CAL117-API-MOD',
            prix_achat=Decimal('600'), prix_vente=Decimal('900'),
            quantite_stock=1)
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.user)

    def _upload(self, texte, nom='fixture.pan'):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile(
            nom, texte.encode('utf-8'), content_type='text/plain')

    def test_apercu_ne_cree_aucune_fiche(self):
        resp = self.client_api.post(
            '/api/django/stock/fiches-techniques/importer-datasheet/',
            {'produit': self.produit.pk, 'file': self._upload(FICHIER_PAN)},
            format='multipart')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(resp.data['confirme'])
        self.assertEqual(resp.data['type_fiche'], 'module')
        self.assertFalse(
            FicheTechnique.objects.filter(produit=self.produit).exists())

    def test_confirmer_ecrit_et_cree_la_fiche(self):
        resp = self.client_api.post(
            '/api/django/stock/fiches-techniques/importer-datasheet/',
            {'produit': self.produit.pk, 'file': self._upload(FICHIER_PAN),
             'confirmer': 'true'},
            format='multipart')
        self.assertEqual(resp.status_code, 200, resp.content)
        fiche = FicheTechnique.objects.get(produit=self.produit)
        self.assertEqual(fiche.pmax_wc, Decimal('550.000'))
        self.assertEqual(fiche.type_fiche, 'module')

    def test_champ_deja_saisi_jamais_ecrase_par_confirmer(self):
        FicheTechnique.objects.create(
            company=self.co, produit=self.produit, type_fiche='module',
            pmax_wc=Decimal('1.00'))
        resp = self.client_api.post(
            '/api/django/stock/fiches-techniques/importer-datasheet/',
            {'produit': self.produit.pk, 'file': self._upload(FICHIER_PAN),
             'confirmer': 'true'},
            format='multipart')
        self.assertEqual(resp.status_code, 200, resp.content)
        fiche = FicheTechnique.objects.get(produit=self.produit)
        self.assertEqual(fiche.pmax_wc, Decimal('1.00'))
        self.assertIn('pmax_wc', resp.data['deja_saisis'])

    def test_fichier_illisible_erreur_sous_le_champ_file(self):
        resp = self.client_api.post(
            '/api/django/stock/fiches-techniques/importer-datasheet/',
            {'produit': self.produit.pk,
             'file': self._upload('rien de PVsyst ici')},
            format='multipart')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['champ'], 'file')

    def test_produit_hors_societe_introuvable(self):
        autre_produit = Produit.objects.create(
            company=self.autre_co, nom='Hors société', sku='CAL117-HORS',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'),
            quantite_stock=0)
        resp = self.client_api.post(
            '/api/django/stock/fiches-techniques/importer-datasheet/',
            {'produit': autre_produit.pk, 'file': self._upload(FICHIER_PAN)},
            format='multipart')
        self.assertEqual(resp.status_code, 404)
