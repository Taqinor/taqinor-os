"""Tests QJR6 — scripts/check_override_registry.py.

Pur stdlib (unittest), sans Django et sans base — comme le checker. Lancer :
    python -m unittest scripts.tests.test_check_override_registry -v
"""
import functools
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_override_registry as cor  # noqa: E402


@functools.lru_cache(maxsize=1)
def _real_sites():
    """Scan reel de l'arbre, calcule UNE fois pour toute la suite."""
    return tuple(cor.scan(cor.load_registry_paths()))


#: Sous-ensemble representatif du contrat QJR1 (les tests qui doivent prouver
#: que la liste vient bien du contrat lisent le VRAI fichier, voir plus bas).
PATHS = [
    "taille.nb_panneaux", "taille.kwc", "scenario", "recommended_option",
    "profil.occupation", "profil.equipements.<clef>", "tarif.distributeur",
    "mode_installation",
]

REL = "backend/django_core/apps/ventes/services.py"


def _sites(src, rel=REL, paths=None, scan_lignes=True):
    return cor.collect_sites_in_source(src, rel, paths or PATHS,
                                       scan_lignes=scan_lignes)


def _targets(src, **kw):
    return [(s.family, s.target) for s in _sites(src, **kw)]


def _keys(src, **kw):
    return [s.key for s in _sites(src, **kw)]


# ---------------------------------------------------------------- famille A

PLAT = '''
def poser(etude_params):
    etude_params['scenario'] = 'Avec batterie'
'''

IMBRIQUE = '''
def poser(etude_params):
    etude_params['taille']['nb_panneaux'] = 14
'''

SOUS_ARBRE = '''
def poser(etude_params):
    etude_params['taille'] = {'nb_panneaux': 14}
'''

PLUS_PROFOND = '''
def poser(etude_params):
    etude_params['profil']['equipements']['piscine']['puissance_kw'] = 1.5
'''

VIA_ATTRIBUT = '''
def poser(devis):
    devis.etude_params['scenario'] = 'Sans batterie'
'''

HORS_REGISTRE = '''
def poser(etude_params):
    etude_params['production_annuelle'] = 10800
    etude_params['toiture'] = {}
    etude_params['etude_horaire'] = {}
'''

CLE_DYNAMIQUE = '''
def poser(etude_params, clef):
    etude_params[clef] = 1
'''

DYNAMIQUE_SOUS_PREFIXE_CONNU = '''
def poser(etude_params, clef):
    etude_params['taille'][clef] = 1
'''

UPDATE_DICT = '''
def poser(etude_params):
    etude_params.update({'scenario': 'Avec batterie', 'toiture': {}})
'''

UPDATE_KWARG = '''
def poser(etude_params):
    etude_params.update(scenario='Avec batterie')
'''

SETDEFAULT = '''
def poser(etude_params):
    etude_params.setdefault('tarif', {})
'''

POP = '''
def poser(etude_params):
    etude_params.pop('scenario', None)
'''

AUTRE_DICT = '''
def poser(contexte):
    contexte['scenario'] = 'Avec batterie'
    contexte.update({'scenario': 'x'})
'''

LECTURE_SEULE = '''
def lire(etude_params):
    valeur = etude_params['scenario']
    return valeur
'''


class TestFamilleEtudeParams(unittest.TestCase):
    def test_ecriture_a_plat_signalee(self):
        self.assertEqual(_targets(PLAT), [("etude_params", "scenario")])

    def test_ecriture_imbriquee_signalee(self):
        self.assertEqual(_targets(IMBRIQUE),
                         [("etude_params", "taille.nb_panneaux")])

    def test_ecriture_du_sous_arbre_signalee(self):
        # `etude_params['taille'] = {...}` ecrit `taille.nb_panneaux` aussi.
        self.assertEqual(_targets(SOUS_ARBRE), [("etude_params", "taille")])

    def test_ecriture_plus_profonde_signalee(self):
        self.assertEqual(
            _targets(PLUS_PROFOND),
            [("etude_params", "profil.equipements.piscine.puissance_kw")])

    def test_base_attribut_signalee(self):
        self.assertEqual(_targets(VIA_ATTRIBUT), [("etude_params", "scenario")])

    def test_chemin_hors_registre_ignore(self):
        self.assertEqual(_targets(HORS_REGISTRE), [])

    def test_cle_dynamique_signalee(self):
        self.assertEqual(_targets(CLE_DYNAMIQUE),
                         [("etude_params", cor.DYNAMIC_TARGET)])

    def test_cle_dynamique_sous_prefixe_du_registre_signalee(self):
        self.assertEqual(_targets(DYNAMIQUE_SOUS_PREFIXE_CONNU),
                         [("etude_params", "taille")])

    def test_update_dict_signale_la_seule_cle_du_registre(self):
        self.assertEqual(_targets(UPDATE_DICT), [("etude_params", "scenario")])

    def test_update_kwarg_signale(self):
        self.assertEqual(_targets(UPDATE_KWARG), [("etude_params", "scenario")])

    def test_setdefault_sur_prefixe_du_registre_signale(self):
        self.assertEqual(_targets(SETDEFAULT), [("etude_params", "tarif")])

    def test_pop_signale(self):
        self.assertEqual(_targets(POP), [("etude_params", "scenario")])

    def test_autre_dictionnaire_ignore(self):
        self.assertEqual(_targets(AUTRE_DICT), [])

    def test_lecture_seule_ignoree(self):
        self.assertEqual(_targets(LECTURE_SEULE), [])


# ---------------------------------------------------------------- famille B

LIGNE_QUANTITE = '''
def resync(ligne):
    ligne.quantite = 12
    ligne.save(update_fields=['quantite'])
'''

LIGNE_PRIX = '''
def substituer(ligne, produit):
    ligne.prix_unitaire = produit.prix_vente
    ligne.save()
'''

LIGNE_QS_UPDATE = '''
def resync(devis):
    devis.lignes.filter(designation='X').update(quantite=8)
'''

LIGNE_AUTRE_CHAMP = '''
def toucher(ligne):
    ligne.designation = 'X'
    ligne.remise = 0
    ligne.save()
'''

LIGNE_CREATION = '''
def creer(devis):
    LigneDevis.objects.create(devis=devis, quantite=3, prix_unitaire=10)
'''


class TestFamilleLigne(unittest.TestCase):
    def test_quantite_signalee(self):
        self.assertEqual(_targets(LIGNE_QUANTITE),
                         [("ligne", "ligne.quantite")])

    def test_prix_unitaire_signale(self):
        self.assertEqual(_targets(LIGNE_PRIX),
                         [("ligne", "ligne.prix_unitaire")])

    def test_update_de_queryset_signale(self):
        self.assertEqual(_targets(LIGNE_QS_UPDATE),
                         [("ligne", "update(quantite=...)")])

    def test_autre_champ_ignore(self):
        self.assertEqual(_targets(LIGNE_AUTRE_CHAMP), [])

    def test_creation_ignoree(self):
        # Creer une ligne n'est pas surcharger une ligne existante.
        self.assertEqual(_targets(LIGNE_CREATION), [])

    def test_hors_ventes_la_famille_ligne_nest_pas_scannee(self):
        # `.quantite` de stock/installations est un AUTRE modele.
        self.assertEqual(_targets(LIGNE_QUANTITE, scan_lignes=False), [])


# ------------------------------------------------------- surface & modules


class TestSurfaceScannee(unittest.TestCase):
    def test_les_modules_sanctionnes_sont_exemptes(self):
        for rel in cor.SANCTIONED:
            self.assertTrue(cor._skip(rel), rel)

    def test_migrations_et_tests_exclus(self):
        self.assertTrue(cor._skip(
            "backend/django_core/apps/ventes/migrations/0001_initial.py"))
        self.assertTrue(cor._skip(
            "backend/django_core/apps/ventes/tests/test_x.py"))
        self.assertTrue(cor._skip(
            "backend/django_core/apps/ventes/tests_qj9_attribution_capi.py"))
        self.assertFalse(cor._skip(
            "backend/django_core/apps/ventes/services.py"))

    def test_la_famille_ligne_est_scannee_sur_ventes_seulement(self):
        flags = {rel: lignes for rel, lignes in
                 ((cor._rel(p), f) for p, f in cor.iter_scanned_files())}
        self.assertTrue(
            flags["backend/django_core/apps/ventes/services.py"])
        stock = "backend/django_core/apps/stock/services.py"
        if stock in flags:
            self.assertFalse(flags[stock])

    def test_le_scan_reel_nest_pas_vide(self):
        # Un glob casse rendrait la garde silencieusement inoffensive.
        self.assertGreater(len(_real_sites()), 0)


# ------------------------------------------------------------------- cles


DEUX_SITES_IDENTIQUES = '''
def resync(ligne, autre):
    ligne.quantite = 1
    ligne.quantite = 2
'''

AVEC_PREAMBULE = ("\n" * 50) + PLAT


class TestClesDIdentite(unittest.TestCase):
    def test_cle_contient_chemin_qualname_famille_cible(self):
        self.assertEqual(
            _keys(PLAT), [f"{REL}::poser::etude_params::scenario"])

    def test_deux_sites_identiques_departages(self):
        self.assertEqual(
            _keys(DEUX_SITES_IDENTIQUES),
            [f"{REL}::resync::ligne::ligne.quantite#1",
             f"{REL}::resync::ligne::ligne.quantite#2"])

    def test_insertion_en_amont_ne_change_pas_la_cle(self):
        self.assertEqual(_keys(PLAT), _keys(AVEC_PREAMBULE))

    def test_renommer_la_fonction_change_la_cle(self):
        renomme = PLAT.replace("def poser", "def poser_v2")
        self.assertNotEqual(_keys(PLAT), _keys(renomme))

    def test_qualname_au_niveau_module(self):
        src = "etude_params['scenario'] = 'x'\n"
        self.assertEqual(
            _keys(src),
            [f"{REL}::{cor.MODULE_QUALNAME}::etude_params::scenario"])

    def test_qualname_de_methode(self):
        src = '''
class Vue:
    def poser(self, etude_params):
        etude_params['scenario'] = 'x'
'''
        self.assertEqual(_keys(src),
                         [f"{REL}::Vue.poser::etude_params::scenario"])


# ----------------------------------------------------------------- contrat


class TestChemninsDuContrat(unittest.TestCase):
    def test_les_chemins_viennent_du_contrat_qjr1(self):
        chemins = cor.load_registry_paths()
        self.assertIn("scenario", chemins)
        self.assertIn("taille.nb_panneaux", chemins)
        self.assertIn("profil.equipements.<clef>", chemins)

    def test_aucun_chemin_recopie_en_dur_dans_le_script(self):
        source = (ROOT / "scripts"
                  / "check_override_registry.py").read_text(encoding="utf-8")
        code = source.split('"""', 2)[-1]  # hors docstring de module
        for chemin in ("taille.nb_panneaux", "tarif.distributeur",
                       "mode_installation", "pompe_alim"):
            self.assertNotIn(f"'{chemin}'", code)
            self.assertNotIn(f'"{chemin}"', code)

    def test_joker_du_contrat(self):
        self.assertTrue(cor.path_touches_registry(
            "profil.equipements.piscine", ["profil.equipements.<clef>"]))
        self.assertTrue(cor.path_touches_registry(
            "profil.equipements", ["profil.equipements.<clef>"]))
        self.assertFalse(cor.path_touches_registry(
            "profil.autre", ["profil.equipements.<clef>"]))

    def test_chemin_vide_ne_touche_rien(self):
        self.assertFalse(cor.path_touches_registry("", PATHS))


# --------------------------------------------------------------- allowlist


class TestBaseDeReference(unittest.TestCase):
    def setUp(self):
        self.sites = _sites(PLAT)

    def test_site_absent_de_la_base_est_un_offender(self):
        offenders, orphans = cor.evaluate(self.sites, set())
        self.assertEqual([s.key for s in offenders],
                         [f"{REL}::poser::etude_params::scenario"])
        self.assertEqual(orphans, [])

    def test_site_present_est_accepte(self):
        offenders, orphans = cor.evaluate(
            self.sites, {f"{REL}::poser::etude_params::scenario"})
        self.assertEqual(offenders, [])
        self.assertEqual(orphans, [])

    def test_entree_orpheline_signalee(self):
        offenders, orphans = cor.evaluate(
            self.sites, {f"{REL}::poser::etude_params::scenario",
                         f"{REL}::disparue::ligne::ligne.quantite"})
        self.assertEqual(offenders, [])
        self.assertEqual(orphans, [f"{REL}::disparue::ligne::ligne.quantite"])

    def test_lecture_de_la_base_cle_et_raison(self):
        rendu = cor.render_allowlist(self.sites, {})
        path = Path(self.__class__.__name__ + ".tmp")
        try:
            path.write_text(rendu, encoding="utf-8")
            entries = cor.load_allowlist(path)
        finally:
            if path.exists():
                path.unlink()
        self.assertEqual(list(entries),
                         [f"{REL}::poser::etude_params::scenario"])
        self.assertEqual(entries[f"{REL}::poser::etude_params::scenario"],
                         cor.NEW_SITE_REASON)

    def test_les_raisons_existantes_sont_conservees(self):
        key = f"{REL}::poser::etude_params::scenario"
        rendu = cor.render_allowlist(self.sites, {key: "relu le 29/08"})
        self.assertIn(f"{key} {cor.SEPARATOR} relu le 29/08", rendu)

    def test_la_base_du_depot_couvre_l_arbre_courant(self):
        offenders, _orphans = cor.evaluate(list(_real_sites()),
                                           cor.load_allowlist())
        self.assertEqual([s.key for s in offenders], [])


if __name__ == "__main__":
    unittest.main()
