"""CALX145/69 — le registre des réglages, enfin SERVI par ``GET parametres/``.

POURQUOI CE FICHIER EXISTE
---------------------------
CALX145 (lane G2) a déclaré les DEUX registres (``services/parametres_cles.py``
— labels français, unités, références doctrinales des clés admises de
« simulation » et « electrique_societe »). CALX69 (lane J1) a construit
l'écran de saisie, mais a constaté que ``GET /api/django/calepinage/
parametres/`` ne servait QUE les valeurs saisies (deux dicts bruts) — jamais
le registre lui-même : l'écran redéclarait donc les deux tables à la main
(``ReglagesSimulation.jsx::REGISTRE_SIMULATION`` /
``REGISTRE_ELECTRIQUE_SOCIETE``), une SECONDE source de vérité, exactement ce
que ``scripts/check_api_shapes.py`` existe pour repérer.

Ce follow-up publie le registre sous une clé DÉRIVÉE ``registre`` — même
mécanique que ``kits`` (CAL246) : jamais une section (``PUT`` la refuse comme
toute clé inconnue), résolue à la lecture, sans aucune valeur ni défaut
(``selectors.registre_des_reglages``).

CE QUE CE FICHIER PROTÈGE (tout en ``SimpleTestCase`` — aucune base)
-----------------------------------------------------------------------
1. **ÉGALITÉ CLÉ PAR CLÉ** avec ``parametres_cles.registre(...)`` : le
   sélecteur ne réinvente rien, il transpose la déclaration APPEND-ONLY telle
   quelle.
2. **L'ORDRE DU REGISTRE** est préservé (jamais réordonné, D-CALX 13).
3. **LECTURE SEULE** : ``registre`` n'est ni une section admise du modèle, ni
   acceptée en écriture — refusée en la nommant comme toute clé inconnue.
4. **LE CONTRAT COMMITTÉ** (``contract_samples/parametres_calepinage.json``)
   porte EXACTEMENT ce que le sélecteur produit, dans ``exemple`` ET
   ``exemple_vide`` (le registre ne dépend d'aucune saisie de société).

Run :
    python manage.py test apps.calepinage.tests.test_calx69_registre_servi -v2
"""
import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.models import ParametresCalepinage
from apps.calepinage.selectors import (
    SECTIONS_LECTURE_SEULE,
    SECTIONS_PARAMETRES,
    registre_des_reglages,
)
from apps.calepinage.services.parametres_cles import (
    CLES_ELECTRIQUE_SOCIETE,
    CLES_SIMULATION,
    SECTION_ELECTRIQUE_SOCIETE,
    SECTION_SIMULATION,
    registre,
)

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'parametres_calepinage.json').read_text(encoding='utf-8'))


def _cles(declarations):
    return tuple(declaration[0] for declaration in declarations)


class RegistreServiTest(SimpleTestCase):
    """``registre_des_reglages()`` == ``parametres_cles.registre(...)``,
    clé par clé — c'est la garde qui empêche l'écran de redéclarer."""

    def test_les_deux_sections_sont_publiees(self):
        servi = registre_des_reglages()
        self.assertEqual(sorted(servi),
                         [SECTION_ELECTRIQUE_SOCIETE, SECTION_SIMULATION])

    def test_chaque_ligne_egale_le_registre_declare_cle_par_cle(self):
        servi = registre_des_reglages()
        for section in (SECTION_SIMULATION, SECTION_ELECTRIQUE_SOCIETE):
            with self.subTest(section=section):
                attendu = registre(section)
                obtenu = {
                    ligne['cle']: (ligne['libelle'], ligne['unite'],
                                   ligne['reference'])
                    for ligne in servi[section]
                }
                self.assertEqual(sorted(obtenu), sorted(attendu))
                for cle, valeurs in attendu.items():
                    with self.subTest(cle=cle):
                        self.assertEqual(obtenu[cle], valeurs)

    def test_ordre_du_registre_preserve(self):
        servi = registre_des_reglages()
        self.assertEqual(
            tuple(ligne['cle'] for ligne in servi[SECTION_SIMULATION]),
            _cles(CLES_SIMULATION))
        self.assertEqual(
            tuple(ligne['cle'] for ligne in servi[SECTION_ELECTRIQUE_SOCIETE]),
            _cles(CLES_ELECTRIQUE_SOCIETE))

    def test_chaque_ligne_porte_exactement_les_quatre_champs(self):
        servi = registre_des_reglages()
        for section, lignes in servi.items():
            with self.subTest(section=section):
                for ligne in lignes:
                    self.assertEqual(
                        sorted(ligne),
                        ['cle', 'libelle', 'reference', 'unite'])

    def test_ne_depend_d_aucune_societe(self):
        """Lecture PURE : deux appels rendent le même document."""
        self.assertEqual(registre_des_reglages(), registre_des_reglages())


class RegistreLectureSeuleTest(SimpleTestCase):
    """``registre`` suit exactement la mécanique de ``kits`` (CAL246)."""

    def test_registre_est_declare_lecture_seule(self):
        self.assertIn('registre', SECTIONS_LECTURE_SEULE)

    def test_registre_n_est_pas_une_section_admise(self):
        self.assertNotIn('registre', SECTIONS_PARAMETRES)
        self.assertNotIn('registre', ParametresCalepinage.SECTIONS)

    def test_registre_est_refuse_en_ecriture_comme_toute_cle_inconnue(self):
        self.assertEqual(
            ParametresCalepinage.sections_inconnues({'registre': {}}),
            ['registre'])


class ContratRegistreTest(SimpleTestCase):
    """PACT10 : le contrat committé porte EXACTEMENT ce que sert le serveur,
    dans les deux états publiés — le registre ne dépend d'aucune saisie."""

    def test_les_deux_etats_portent_la_cle_registre(self):
        for etat in ('exemple', 'exemple_vide'):
            with self.subTest(etat=etat):
                self.assertIn('registre', CONTRAT[etat])

    def test_le_contrat_egale_ce_que_sert_le_selecteur(self):
        attendu = registre_des_reglages()
        for etat in ('exemple', 'exemple_vide'):
            with self.subTest(etat=etat):
                self.assertEqual(CONTRAT[etat]['registre'], attendu)

    def test_les_deux_etats_du_contrat_portent_le_meme_registre(self):
        """Le registre ne dépend d'aucune valeur saisie : un état « vide »
        et un état « rempli » servent le MÊME registre."""
        self.assertEqual(CONTRAT['exemple']['registre'],
                         CONTRAT['exemple_vide']['registre'])
