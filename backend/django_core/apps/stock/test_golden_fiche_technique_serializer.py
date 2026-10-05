"""SPL112 — golden du sérialiseur ``FicheTechniqueSerializer``.

Capture seule : lecture (``.data``), validation (erreurs exactes), écriture
create/update sans pièce jointe et noms de champs exposés, tels qu'ils sont
AUJOURD'HUI dans ``stock/serializers.py``. SPL115 déplacera la classe vers
``serializers_fiche_technique.py`` (aucun ré-export) ; ce test résout le
symbole aux DEUX endroits (``_resolve``) et reste vert sans régénérer le JSON.
L'assertion ``__module__ == 'apps.stock.serializers_fiche_technique'`` est
ajoutée (et prouvée rouge) par SPL115. Le schéma drf-spectacular est vérifié
par ``python scripts/check_openapi_schema.py``, pas recopié ici.

Appelants relevés pour SPL115 (cinq fichiers, six sites, tous du même app) :
stock/views/fiche_technique.py:7,26,108 ; test_aud835_fiche_technique_minio.py
:22 ; test_cal_fiche_thermique.py:20 ; test_dc.py:189,310 ;
test_agr101_fiche_pompage.py:61.

Sections de ``golden/fiche_technique_serializer.json`` :
  * ``ast``         — empreinte AST de la classe (outil SPL110) ;
  * ``lecture``     — ``.data`` de 5 fiches (id/produit/dates masqués) ;
  * ``validation``  — erreurs exactes de 4 payloads invalides ;
  * ``ecriture``    — create puis update sans pièce jointe ;
  * ``champs``      — noms de champs exposés (garde AGR101).

Capture (UNE fois, sur le code actuel, jamais après le déplacement) :
    GOLDEN_CAPTURE=1 docker compose exec django_core python manage.py test \
        apps.stock.test_golden_fiche_technique_serializer
Hors capture, une section absente du JSON fait ÉCHOUER le test.

Run :
    docker compose exec django_core python manage.py test \
        apps.stock.test_golden_fiche_technique_serializer -v 2
"""
import importlib
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase

from apps.stock.golden.ast_fingerprint import fingerprint, verifier_section
from apps.stock.models import FicheTechnique, Produit
from authentication.models import Company

GOLDEN = 'fiche_technique_serializer'


def _resolve():
    """La classe, où qu'elle vive : le futur module (SPL115) puis l'actuel.
    Aucun ré-export n'existera dans ``serializers`` après SPL115."""
    try:
        module = importlib.import_module(
            'apps.stock.serializers_fiche_technique')
    except ImportError:
        module = importlib.import_module('apps.stock.serializers')
    return module.FicheTechniqueSerializer


def _masquer(donnees, ids):
    """Retire ce qui varie d'un run à l'autre : ids, dates ; ``produit``
    devient le sku."""
    sortie = dict(donnees)
    sortie['id'] = '<id>'
    sortie['produit'] = ids.get(donnees['produit'], donnees['produit'])
    for cle in ('date_creation', 'date_mise_a_jour'):
        sortie[cle] = '<date>' if donnees.get(cle) else donnees.get(cle)
    return sortie


def _erreurs(serializer):
    return {cle: [str(e) for e in valeurs]
            for cle, valeurs in serializer.errors.items()}


class GoldenFicheTechniqueSerializerTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.co = Company.objects.get_or_create(
            slug='spl112-golden-co', defaults={'nom': 'SPL112 Golden'})[0]
        cls.autre_co = Company.objects.get_or_create(
            slug='spl112-golden-autre', defaults={'nom': 'SPL112 Autre'})[0]
        cls.produits = {}
        for sku in ('S-MOD', 'S-OND', 'S-BAT', 'S-OPT', 'S-LEG', 'S-MINIO',
                    'S-NEW', 'S-UPD'):
            cls.produits[sku] = Produit.objects.create(
                company=cls.co, nom='Produit %s' % sku, sku=sku,
                marque='MarqueSPL112', garantie='10 ans',
                prix_achat=Decimal('100'), prix_vente=Decimal('150'),
                quantite_stock=1)
        cls.produit_autre = Produit.objects.create(
            company=cls.autre_co, nom='Produit autre société',
            sku='S-AUTRE', prix_achat=Decimal('100'),
            prix_vente=Decimal('150'), quantite_stock=1)
        cls.ids = {p.pk: sku for sku, p in cls.produits.items()}
        cls.ids[cls.produit_autre.pk] = 'S-AUTRE'

        def fiche(sku, **champs):
            return FicheTechnique.objects.create(
                company=cls.co, produit=cls.produits[sku], **champs)

        cls.fiches = {
            'module': fiche(
                'S-MOD', type_fiche='module', pmax_wc=Decimal('550'),
                voc_v=Decimal('49.5'), longueur_mm=2278, largeur_mm=1134,
                bifacial=True, noct_c=Decimal('43.0'),
                uc_w_m2k=Decimal('29.0'),
                temp_coeff_pmax_pct_c=Decimal('-0.300'),
                rendement_par_irradiance=[
                    {'w_m2': 200, 'rendement_relatif_pct': 97.0},
                    {'w_m2': 1000, 'rendement_relatif_pct': 100.0}]),
            'onduleur': fiche(
                'S-OND', type_fiche='onduleur', ond_n_mppt=2,
                ond_ac_kw=Decimal('10'), ond_phases=3,
                ond_courbe_rendement=[
                    {'charge_pct': 10, 'rendement_pct': 90},
                    {'charge_pct': 100, 'rendement_pct': 97}]),
            'batterie': fiche(
                'S-BAT', type_fiche='batterie',
                bat_kwh_nominal=Decimal('10.24'), bat_chimie='LFP',
                bat_dod_pct=Decimal('90')),
            'optimiseur': fiche(
                'S-OPT', type_fiche='optimiseur',
                opt_pmax_out_w=Decimal('700'),
                opt_modules_max_par_chaine=20),
            # Fiche historique : ``pdf`` (FileField legacy) sans clé MinIO.
            'legacy': fiche(
                'S-LEG', type_fiche='module',
                pdf='stock/fiches_techniques/2026/01/legacy.pdf'),
            # AUD835 : clé MinIO + métadonnées.
            'minio': fiche(
                'S-MINIO', type_fiche='module',
                pdf_key='spl112-golden-co/fiches/minio.pdf',
                pdf_filename='minio.pdf', pdf_size=1234,
                pdf_mime='application/pdf'),
        }

    def _contexte(self):
        request = SimpleNamespace(user=SimpleNamespace(company=self.co))
        return {'request': request}

    def _serializer(self, *args, **kwargs):
        kwargs.setdefault('context', self._contexte())
        return _resolve()(*args, **kwargs)

    def test_spl115_serializer_vit_dans_serializers_fiche_technique(self):
        """SPL115 — la classe a déménagé dans ``serializers_fiche_technique``
        et l'ancien module ne la porte plus (même app : aucun ré-export)."""
        import apps.stock.serializers as ancien
        self.assertEqual(_resolve().__module__,
                         'apps.stock.serializers_fiche_technique')
        self.assertFalse(hasattr(ancien, 'FicheTechniqueSerializer'))

    def test_empreinte_ast(self):
        verifier_section(self, GOLDEN, 'ast',
                         {'FicheTechniqueSerializer': fingerprint(_resolve())})

    def test_champs_exposes(self):
        """Noms de champs exposés, dans l'ordre (garde AGR101 : un champ de
        fiche ajouté au modèle sans l'être ici serait ignoré en silence)."""
        champs = list(self._serializer().fields)
        self.assertIn('pompe_i_nominal_a', champs)
        self.assertIn('pdf_url', champs)
        verifier_section(self, GOLDEN, 'champs', champs)

    def test_lecture_de_cinq_fiches(self):
        """``.data`` de 5 fiches (+ AUD835) ; l'URL présignée est celle du
        stockage, simulé à sa FRONTIÈRE (jamais le sérialiseur)."""
        sortie = {}
        with mock.patch('apps.records.storage.presign_attachment',
                        side_effect=lambda key: (
                            'https://minio.test/%s' % key if key else None)):
            for nom, fiche in self.fiches.items():
                data = self._serializer(
                    FicheTechnique.objects.select_related('produit').get(
                        pk=fiche.pk)).data
                sortie[nom] = _masquer(
                    {k: (str(v) if isinstance(v, Decimal) else v)
                     for k, v in data.items()}, self.ids)
        self.assertIsNone(sortie['legacy']['pdf_url'])
        self.assertEqual(sortie['minio']['pdf_url'],
                         'https://minio.test/spl112-golden-co/fiches/'
                         'minio.pdf')
        verifier_section(self, GOLDEN, 'lecture', sortie)

    def test_erreurs_de_validation(self):
        produit = self.produits['S-NEW'].pk
        payloads = {
            'courbe_index_fautif': {
                'produit': produit, 'type_fiche': 'module',
                'rendement_par_irradiance': [
                    {'w_m2': 800, 'rendement_relatif_pct': 99},
                    {'w_m2': 200, 'rendement_relatif_pct': 95}]},
            'valeurs_negatives': {
                'produit': produit, 'type_fiche': 'module',
                'longueur_mm': -1, 'opt_modules_max_par_chaine': 0},
            'produit_manquant': {'type_fiche': 'module'},
            'produit_autre_societe': {
                'produit': self.produit_autre.pk, 'type_fiche': 'module'},
        }
        courant = {}
        for nom, payload in payloads.items():
            serializer = self._serializer(data=payload)
            self.assertFalse(serializer.is_valid(), nom)
            courant[nom] = _erreurs(serializer)
        self.assertIn('produit', courant['produit_manquant'])
        self.assertEqual(courant['produit_autre_societe']['produit'],
                         ['Produit hors de votre entreprise.'])
        verifier_section(self, GOLDEN, 'validation', courant)

    def test_ecriture_create_puis_update_sans_fichier(self):
        """Create (société forcée par la vue : ``save(company=…)``) puis
        update partiel, sans pièce jointe : aucune clé MinIO n'apparaît."""
        def _fige(serializer):
            return _masquer(
                {k: (str(v) if isinstance(v, Decimal) else v)
                 for k, v in serializer.data.items()}, self.ids)

        creation = self._serializer(data={
            'produit': self.produits['S-NEW'].pk, 'type_fiche': 'module',
            'pmax_wc': '550.00', 'voc_v': '49.50', 'bifacial': True})
        self.assertTrue(creation.is_valid(), creation.errors)
        fiche = creation.save(company=self.co)
        fiche.refresh_from_db()
        self.assertEqual(fiche.company_id, self.co.pk)
        self.assertEqual(fiche.pdf_key, '')
        self.assertEqual(fiche.pdf_size, 0)
        apres_create = _fige(creation)

        maj = self._serializer(
            fiche, data={'pmax_wc': '560.00', 'noct_c': '44.5'},
            partial=True)
        self.assertTrue(maj.is_valid(), maj.errors)
        fiche = maj.save()
        fiche.refresh_from_db()
        self.assertEqual(fiche.pdf_key, '')
        verifier_section(self, GOLDEN, 'ecriture', {
            'apres_create': apres_create, 'apres_update': _fige(maj)})
