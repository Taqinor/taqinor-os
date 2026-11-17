"""TCH11 — `est_confidentielle` (héritage 4 voies) et `nom_pour` : chaque ligne × colonne du tableau de
« La confidentialité » (reference/regles.md). Sans base : `SimpleTestCase` refuse toute requête, ce qui
prouve aussi qu'aucun appel ne relit la base (objets non enregistrés, liens déjà en mémoire).
"""
from django.test import SimpleTestCase

from apps.taches.confidentialite import est_confidentielle, nom_pour
from apps.taches.models.projets import Projet
from apps.taches.models.rythme import ReglagesRythme
from apps.taches.models.taches import Tache

TITRE = 'Appeler le notaire'
NOM = 'Maison de Fès'
LONG = 'x' * 90


def _projet(confidentiel=False, nom=NOM, pk=1):
    return Projet(pk=pk, nom=nom, confidentiel=confidentiel)


def _tache(titre=TITRE, confidentiel=False, projet=None, parent=None, pk=10):
    return Tache(pk=pk, titre=titre, confidentiel=confidentiel, projet=projet, parent=parent)


def _reglages(allume):
    return ReglagesRythme(titres_notifications=allume, titres_calendrier=allume, titres_tuile=allume)


class HeritageTests(SimpleTestCase):
    def test_tache_ordinaire(self):
        self.assertFalse(est_confidentielle(_tache(projet=_projet())))

    def test_quatre_voies(self):
        secret, ouvert = _projet(confidentiel=True, pk=2), _projet(pk=3)
        cas = {
            'drapeau propre': _tache(confidentiel=True),
            'projet': _tache(projet=secret),
            'parent': _tache(parent=_tache(confidentiel=True, pk=11), projet=ouvert),
            'projet du parent': _tache(parent=_tache(projet=secret, pk=12)),
        }
        for voie, tache in cas.items():
            with self.subTest(voie=voie):
                self.assertTrue(est_confidentielle(tache))

    def test_parent_ordinaire_dans_un_projet_ordinaire(self):
        parent = _tache(projet=_projet(pk=4), pk=13)
        self.assertFalse(est_confidentielle(_tache(parent=parent, projet=_projet(pk=4))))

    def test_projet_par_son_seul_drapeau(self):
        self.assertTrue(est_confidentielle(_projet(confidentiel=True)))
        self.assertFalse(est_confidentielle(_projet()))


class TableauNomPourTests(SimpleTestCase):
    """Colonnes : tâche ordinaire, tâche confidentielle, projet confidentiel (+ projet ordinaire)."""

    def setUp(self):
        self.ordinaire = _tache(projet=_projet(pk=5))
        self.confidentielle = _tache(confidentiel=True)
        self.sous_tache_secrete = _tache(parent=_tache(projet=_projet(confidentiel=True, pk=6), pk=14))
        self.projet_secret = _projet(confidentiel=True)
        self.projet = _projet()

    def _ligne(self, usage, reglages, attendu):
        objets = (self.ordinaire, self.confidentielle, self.sous_tache_secrete, self.projet_secret, self.projet)
        self.assertEqual([nom_pour(o, usage, reglages) for o in objets], attendu)

    def test_ecran(self):
        self._ligne('ecran', None, [TITRE, TITRE, TITRE, NOM, NOM])

    def test_assistant(self):
        conf = 'Tâche confidentielle'
        self._ligne('assistant', _reglages(True), [TITRE, conf, conf, 'Projet confidentiel', NOM])

    def test_flux(self):
        conf = 'Tâche confidentielle'
        self._ligne('flux', _reglages(True), [TITRE, conf, conf, None, None])
        self._ligne('flux', _reglages(False), ['Tâche', conf, conf, None, None])

    def test_tuile(self):
        conf = 'Tâche confidentielle'
        self._ligne('tuile', _reglages(True), [TITRE, conf, conf, None, None])
        self._ligne('tuile', _reglages(False), ['Tâche', conf, conf, None, None])

    def test_notification(self):
        self._ligne('notification', _reglages(False), [None, None, None, None, None])
        self._ligne('notification', _reglages(True), [TITRE, None, None, None, NOM])

    def test_siri(self):
        self._ligne('siri', None, [TITRE, 'une tâche', 'une tâche', 'un projet', NOM])
        self.assertEqual(nom_pour(_tache(titre=LONG), 'siri'), 'x' * 60)

    def test_sans_reglages_les_defauts_du_modele(self):
        self.assertEqual(nom_pour(self.ordinaire, 'flux'), TITRE)
        self.assertEqual(nom_pour(self.ordinaire, 'tuile'), TITRE)
        self.assertIsNone(nom_pour(self.ordinaire, 'notification'))

    def test_usage_et_objet_inconnus_refuses(self):
        with self.assertRaises(ValueError):
            nom_pour(self.ordinaire, 'journal')
        with self.assertRaises(TypeError):
            nom_pour(ReglagesRythme(), 'ecran')
