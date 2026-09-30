"""Garde « le guide du suivi commercial est à jour » (SimpleTestCase, sans base).

Le guide PDF « Le suivi commercial : étapes, réponses et suites » est GÉNÉRÉ
depuis la table du parcours (``frontend/src/features/crm/relances/
parcours_suivi.json``) par ``scripts/generer_guide_suivi.py`` ; le PDF est
ensuite publié dans la GED (Documentation -> Guides) par
``publier_documents_meryem`` à chaque déploiement. Cette garde empêche qu'une
table modifiée laisse un guide périmé dans le dépôt — donc en production :

  * le SHA-256 de la table (texte normalisé LF, comme le générateur) est celui
    que porte le HTML committé (``<meta name="table-sha256">``) ;
  * le HTML committé est exactement celui que le générateur produit
    AUJOURD'HUI (couvre aussi les délais lus dans ``models_relance.py`` et le
    code du générateur lui-même) ;
  * le PDF existe, commence par ``%PDF`` et pèse plus de 20 Ko ;
  * le manifeste de publication déclare les deux guides dans
    Documentation/Guides, et l'entrée du guide de la visite porte EXACTEMENT le
    nom du document déjà présent en production (elle lui ajoute une version,
    jamais un doublon) ;
  * le PDF du guide de la visite de ``docs/meryem/`` est le même fichier, octet
    pour octet, que la fixture lue par ``seed_guide_visite``.

Ces tests lisent des fichiers du dépôt (docs/, frontend/, scripts/) : ils
supposent un dépôt complet (CI, poste de développement) et se mettent en
« skip » dans une image qui n'embarque que ``backend/django_core``.
"""
import hashlib
import importlib.util
import json
import re
import unittest
from pathlib import Path

from django.test import SimpleTestCase

from apps.ged import services
from apps.ged.management.commands import publier_documents_meryem as cmd

# …/backend/django_core/apps/ged/<ce fichier> -> racine du dépôt = parents[4]
RACINE = Path(__file__).resolve().parents[4]
TABLE = (RACINE / 'frontend' / 'src' / 'features' / 'crm' / 'relances'
         / 'parcours_suivi.json')
DOCS = RACINE / 'docs' / 'meryem'
HTML = DOCS / 'source' / 'suivi_commercial_etapes_et_reponses.html'
PDF = DOCS / 'Suivi_commercial_etapes_et_reponses.pdf'
MANIFESTE = DOCS / cmd.MANIFEST_NOM
PDF_VISITE_DOCS = DOCS / 'Guide_visite_suivi_commercial.pdf'
PDF_VISITE_FIXTURE = (Path(services.__file__).resolve().parent / 'fixtures'
                      / 'guide_visite_suivi_commercial.pdf')
GENERATEUR = RACINE / 'scripts' / 'generer_guide_suivi.py'

FICHIER_SUIVI = 'Suivi_commercial_etapes_et_reponses.pdf'
FICHIER_VISITE = 'Guide_visite_suivi_commercial.pdf'

CONSIGNE = ('La table du parcours a changé : relancez '
            '`python scripts/generer_guide_suivi.py` et committez le HTML et '
            'le PDF.')

DEPOT_COMPLET = (RACINE / 'docs').is_dir() and (RACINE / 'frontend').is_dir()


def _sha256_table():
    """Empreinte de la table lue en texte NORMALISÉ (``\\r\\n`` -> ``\\n``) :
    identique sur un poste Windows (fins de ligne CRLF) et sur Linux (LF)."""
    texte = TABLE.read_bytes().decode('utf-8').replace('\r\n', '\n')
    return hashlib.sha256(texte.encode('utf-8')).hexdigest()


def _manifeste():
    return json.loads(MANIFESTE.read_text(encoding='utf-8'))


@unittest.skipUnless(
    DEPOT_COMPLET, 'dépôt incomplet : docs/ et frontend/ sont absents.')
class GuideSuiviAJourTests(SimpleTestCase):

    def test_le_html_committe_correspond_a_la_table(self):
        html = HTML.read_text(encoding='utf-8')
        trouve = re.search(
            r'<meta name="table-sha256" content="([0-9a-f]{64})"', html)
        self.assertIsNotNone(
            trouve, 'Le HTML du guide ne porte pas sa balise table-sha256. '
            + CONSIGNE)
        self.assertEqual(trouve.group(1), _sha256_table(), CONSIGNE)

    def test_le_html_committe_est_celui_que_le_generateur_produit(self):
        # Le générateur est un script (bibliothèque standard seulement) : on le
        # charge par son chemin, sans l'exécuter en tant que programme.
        spec = importlib.util.spec_from_file_location(
            'generer_guide_suivi_sous_test', GENERATEUR)
        generateur = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generateur)
        attendu = generateur.produire_html(RACINE)[0]
        committe = HTML.read_text(encoding='utf-8').replace('\r\n', '\n')
        self.assertTrue(
            committe == attendu,
            'Le guide du suivi commercial n\'est plus celui que le '
            'générateur produit (table, délais des gabarits de relance ou '
            'générateur modifiés). ' + CONSIGNE)

    def test_le_pdf_du_guide_est_present_et_valide(self):
        self.assertTrue(
            PDF.is_file(), f'{PDF.name} est absent de docs/meryem/. '
            + CONSIGNE)
        donnees = PDF.read_bytes()
        self.assertTrue(
            donnees.startswith(b'%PDF'),
            f'{PDF.name} n\'est pas un PDF. ' + CONSIGNE)
        self.assertGreater(
            len(donnees), 20 * 1024,
            f'{PDF.name} est anormalement petit ({len(donnees)} octets). '
            + CONSIGNE)

    def test_le_manifeste_declare_les_deux_guides_dans_documentation_guides(self):
        entrees = {e.get('fichier'): e for e in _manifeste()}
        suivi = entrees.get(FICHIER_SUIVI)
        visite = entrees.get(FICHIER_VISITE)
        self.assertIsNotNone(suivi, f'{FICHIER_SUIVI} manque au manifeste.')
        self.assertIsNotNone(visite, f'{FICHIER_VISITE} manque au manifeste.')
        for entree in (suivi, visite):
            self.assertEqual(entree.get('cabinet'), services.GUIDE_VISITE_CABINET)
            self.assertEqual(entree.get('dossier'), services.GUIDE_VISITE_DOSSIER)
            self.assertTrue(entree.get('titre'))
            self.assertTrue(entree.get('version'))
            self.assertTrue(entree.get('description'))
            self.assertTrue((DOCS / entree['fichier']).is_file())
        # Le guide de la visite est déjà en production sous ce nom : la
        # publication doit lui ajouter une version, pas créer un doublon.
        self.assertEqual(visite['titre'], services.GUIDE_VISITE_NOM)
        # La version du guide du suivi est celle de la table du parcours.
        table = json.loads(TABLE.read_text(encoding='utf-8'))
        self.assertEqual(suivi['version'], str(table['version']), CONSIGNE)

    def test_toutes_les_entrees_du_manifeste_ont_une_destination_valide(self):
        for entree in _manifeste():
            with self.subTest(fichier=entree.get('fichier')):
                cmd._destination(entree)  # ValueError si un seul des deux champs
                self.assertTrue((DOCS / entree['fichier']).is_file())
                self.assertTrue(entree.get('titre'))

    def test_le_pdf_de_la_visite_est_identique_a_la_fixture(self):
        self.assertTrue(PDF_VISITE_DOCS.is_file(), f'{PDF_VISITE_DOCS} est absent.')
        self.assertTrue(PDF_VISITE_FIXTURE.is_file(), f'{PDF_VISITE_FIXTURE} est absent.')
        self.assertTrue(
            PDF_VISITE_DOCS.read_bytes() == PDF_VISITE_FIXTURE.read_bytes(),
            'Le PDF du guide de la visite de docs/meryem/ et la fixture de '
            'apps/ged/fixtures/ ne sont plus le même fichier : réimprimez-les '
            'ensemble avec `python scripts/generer_guide_suivi.py --visite`.')
