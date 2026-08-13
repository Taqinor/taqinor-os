"""Tests de scripts/check_choices_declares.py (PACT159 — vocabulaire declare).

Stdlib pur (unittest), aucune base de donnees, aucun Django. Lancer :
    python -m unittest scripts.tests.test_check_choices_declares -v

Chaque test correspond a une mesure de l'audit PACT159 : la detection par
ressemblance produisait 72 % de faux positifs (13 sur 18) et ratait le cas
fondateur ; la resolution par nom SIMPLE produisait 6 faux candidats. Les
tests ci-dessous verrouillent les deux enseignements : opt-in strict, et
resolution par nom QUALIFIE a partir du modele porteur.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_choices_declares as ccd  # noqa: E402


MODELE = """
from django.db import models


class Statut(models.TextChoices):
    # PIEGE MESURE : un `Statut` de NIVEAU MODULE, aux valeurs differentes.
    OUVERT = 'ouvert', 'Ouvert'
    FERME = 'ferme', 'Ferme'


GRAVITES = [('faible', 'Faible'), ('moyenne', 'Moyenne'), ('haute', 'Haute')]


class DossierEmploye(models.Model):
    class Statut(models.TextChoices):
        EMBAUCHE = 'embauche', 'Embauche'
        ACTIF = 'actif', 'Actif'
        SORTI = 'sorti', 'Sorti'

    class MotifSortie(models.TextChoices):
        DEMISSION = 'demission', 'Demission'
        LICENCIEMENT = 'licenciement', 'Licenciement'
        AUTRE = 'autre', 'Autre'

    statut = models.CharField(max_length=10, choices=Statut.choices)
    motif_sortie = models.CharField(
        max_length=20, choices=MotifSortie.choices, blank=True, default='')
    gravite = models.CharField(max_length=10, choices=GRAVITES)
    libre = models.CharField(max_length=10)
    dynamique = models.CharField(max_length=10, choices=charger_choix())
"""

CONSTANTES = "GRAVITES = ['mineure', 'majeure', 'critique']\n"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        apps = self.base / "apps"
        (apps / "rh").mkdir(parents=True)
        (apps / "rh" / "models.py").write_text(MODELE, encoding="utf-8")
        (apps / "ao" / "fabrique").mkdir(parents=True)
        (apps / "ao" / "fabrique" / "approvisionnement.py").write_text(
            CONSTANTES, encoding="utf-8")
        self.front = self.base / "frontend" / "src"
        self.front.mkdir(parents=True)
        ancien = ccd.APPS_ROOT
        ccd.APPS_ROOT = apps
        self.addCleanup(lambda: setattr(ccd, "APPS_ROOT", ancien))

    def ecrire(self, source: str, nom: str = "Ecran.jsx"):
        chemin = self.front / nom
        chemin.write_text(source, encoding="utf-8")
        return chemin

    def analyser(self):
        return ccd.analyser(self.front)


class ControleNegatifTests(Base):
    """LE controle exige par PACT159 : une valeur inventee doit rougir."""

    def test_valeur_inventee_dans_une_liste_marquee(self):
        self.ecrire("""
// source-choix: rh.DossierEmploye.motif_sortie
const MOTIFS = [
  { value: 'demission', label: 'Demission' },
  { value: 'deces', label: 'Deces' },
]
""")
        constats, verifiees = self.analyser()
        self.assertEqual(verifiees, 1)
        self.assertEqual(len(constats), 1)
        _, _, cible, motif = constats[0]
        self.assertEqual(cible, "rh.DossierEmploye.motif_sortie")
        self.assertIn("'deces'", motif)
        # Le message doit NOMMER le modele et le champ fautifs (regle du depot).
        self.assertIn("rh.DossierEmploye.motif_sortie", motif)
        self.assertIn("demission", motif)

    def test_liste_alignee_est_verte(self):
        self.ecrire("""
// source-choix: rh.DossierEmploye.motif_sortie
const MOTIFS = [
  { value: 'demission', label: 'Demission' },
  { value: 'autre', label: 'Autre' },
]
""")
        constats, verifiees = self.analyser()
        self.assertEqual((constats, verifiees), ([], 1))

    def test_le_serveur_peut_connaitre_plus_de_valeurs_que_l_ecran(self):
        # Sens DELIBERE : un formulaire n'offre pas forcement tout le
        # vocabulaire. Seul « le front invente » est un defaut.
        self.ecrire("""
// source-choix: rh.DossierEmploye.statut
const STATUTS = [{ value: 'actif', label: 'Actif' }]
""")
        self.assertEqual(self.analyser()[0], [])


class OptInTests(Base):
    """Une liste SANS marqueur n'est JAMAIS un rouge — par construction."""

    def test_liste_non_marquee_meme_completement_fausse(self):
        self.ecrire("""
// Motifs alignes sur DossierEmploye.MotifSortie (promesse en PROSE)
const MOTIFS = [
  { value: 'inexistant', label: 'Inexistant' },
  { value: 'invente', label: 'Invente' },
]
""")
        self.assertEqual(self.analyser(), ([], 0))

    def test_fichier_sans_marqueur_n_est_meme_pas_lu(self):
        self.ecrire("const X = [{ value: 'nimporte-quoi' }]\n")
        self.assertEqual(self.analyser(), ([], 0))


class NomQualifieTests(Base):
    """Le piege mesure : `Statut` imbrique contre `Statut` de niveau module."""

    def test_le_nom_simple_designe_la_classe_imbriquee(self):
        # `choices=Statut.choices` dans DossierEmploye = DossierEmploye.Statut
        # ('embauche'/'actif'/'sorti'), PAS le Statut du module
        # ('ouvert'/'ferme'). Resolu par nom simple, ce test serait vert a tort
        # sur 'ouvert' et rouge a tort sur 'actif'.
        valeurs, _ = ccd.valeurs_serveur("rh.DossierEmploye.statut")
        self.assertEqual(valeurs, {"embauche", "actif", "sorti"})

    def test_le_statut_de_niveau_module_n_est_pas_pris(self):
        self.ecrire("""
// source-choix: rh.DossierEmploye.statut
const S = [{ value: 'ouvert', label: 'Ouvert' }]
""")
        constats, _ = self.analyser()
        self.assertEqual(len(constats), 1)
        self.assertIn("'ouvert'", constats[0][3])

    def test_reference_explicitement_qualifiee(self):
        valeurs, _ = ccd.valeurs_serveur("rh.DossierEmploye.motif_sortie")
        self.assertEqual(valeurs, {"demission", "licenciement", "autre"})

    def test_constante_de_module_du_meme_fichier(self):
        valeurs, _ = ccd.valeurs_serveur("rh.DossierEmploye.gravite")
        self.assertEqual(valeurs, {"faible", "moyenne", "haute"})


class VocabulaireHorsTextChoicesTests(Base):
    """Le second format du marqueur : un chemin de constante de module."""

    def test_chemin_de_constante(self):
        valeurs, description = ccd.valeurs_serveur(
            "ao.fabrique.approvisionnement.GRAVITES")
        self.assertEqual(valeurs, {"mineure", "majeure", "critique"})
        self.assertIn("3 valeurs", description)

    def test_valeur_inventee_contre_une_constante(self):
        self.ecrire("""
// source-choix: ao.fabrique.approvisionnement.GRAVITES
const G = ['mineure', 'catastrophique']
""")
        constats, _ = self.analyser()
        self.assertEqual(len(constats), 1)
        self.assertIn("'catastrophique'", constats[0][3])


class MarqueurFautifTests(Base):
    """Un marqueur est une PROMESSE : s'il ne designe rien, il rougit."""

    def _motif(self, source):
        self.ecrire(source)
        constats, _ = self.analyser()
        self.assertEqual(len(constats), 1, constats)
        return constats[0][3]

    def test_champ_inexistant(self):
        motif = self._motif("// source-choix: rh.DossierEmploye.fantome\n"
                            "const X = [{ value: 'a' }]\n")
        self.assertIn("fantome", motif)
        self.assertIn("DossierEmploye", motif)

    def test_modele_inexistant(self):
        motif = self._motif("// source-choix: rh.Fantome.statut\n"
                            "const X = [{ value: 'a' }]\n")
        self.assertIn("Fantome", motif)

    def test_application_inexistante(self):
        motif = self._motif("// source-choix: fantome.Modele.champ\n"
                            "const X = [{ value: 'a' }]\n")
        self.assertIn("fantome", motif)

    def test_champ_sans_choices(self):
        motif = self._motif("// source-choix: rh.DossierEmploye.libre\n"
                            "const X = [{ value: 'a' }]\n")
        self.assertIn("aucun `choices`", motif)

    def test_choices_non_resoluble_statiquement(self):
        # Anti-faux-positif : une source non figee ne peut pas etre PROMISE.
        motif = self._motif("// source-choix: rh.DossierEmploye.dynamique\n"
                            "const X = [{ value: 'a' }]\n")
        self.assertIn("resolubles", motif)

    def test_marqueur_sans_liste(self):
        motif = self._motif("// source-choix: rh.DossierEmploye.statut\n"
                            "const X = { actif: 1 }\n")
        self.assertIn("aucune liste", motif)

    def test_liste_d_objets_sans_cle_value(self):
        motif = self._motif("// source-choix: rh.DossierEmploye.statut\n"
                            "const X = [{ cle: 'actif', libelle: 'Actif' }]\n")
        self.assertIn("value:", motif)


class LectureDuSourceTests(Base):
    """Les commentaires ne sont pas du code : ils ne fournissent aucune valeur."""

    def test_valeur_en_commentaire_ignoree(self):
        self.ecrire("""
// source-choix: rh.DossierEmploye.motif_sortie
const MOTIFS = [
  { value: 'demission', label: 'Demission' },
  // { value: 'deces', label: 'Deces' },
]
""")
        self.assertEqual(self.analyser()[0], [])


class DepotReelTests(unittest.TestCase):
    """Le vrai depot : la garde est VERTE et n'est pas vide de sens."""

    def test_le_depot_est_vert_et_porte_au_moins_un_marqueur(self):
        constats, verifiees = ccd.analyser()
        self.assertEqual(constats, [], "la garde de vocabulaire rougit")
        self.assertGreaterEqual(
            verifiees, 1,
            "aucune liste a source declaree : la garde ne verifierait rien")


if __name__ == "__main__":
    unittest.main()
