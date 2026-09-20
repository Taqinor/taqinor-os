"""CAL170 — UNE seule longueur de chaîne, et on sait d'où elle vient.

Deux noyaux disent la longueur de chaîne : ``core.calepinage.electrique``
(``MODULES_PAR_CHAINE = 16``, la longueur RETENUE AU DOSSIER) et
``core.electrique.chaines`` (la longueur CALCULÉE sur les fiches). Les deux
ont interdiction de s'importer : l'arbitrage vit dans l'app, et c'est lui
qu'on teste ici.

* la longueur calculée l'emporte dès que la fiche permet de la calculer ;
* sinon, et seulement sinon, le repli est la longueur de dossier — annoncé
  comme tel, jamais présenté comme un calcul ;
* un écart au-delà de la tolérance est JOURNALISÉ (discipline PVG2) et son
  historique est conservé ;
* le plafond kWc par onduleur reboucle vers le calepinage en NOMBRE DE
  MODULES (cas FRDISI).

Run :
    python manage.py test apps.calepinage.tests.test_elec_reconciliation_noyaux -v2
"""
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services.chaines import concevoir_par_pan
from apps.calepinage.services.electrique import (
    ORIGINE_LONGUEUR_DOSSIER, ORIGINE_LONGUEUR_FICHE,
    journaliser_ecart_longueur, longueur_chaine_retenue, plafond_modules,
    temperatures_site,
)
from core.calepinage.electrique import MODULES_PAR_CHAINE

MODULE = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
ONDULEUR = {
    'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'isc_max_mppt_a': 45.0,
    'ac_kw': 10.0, 'phases': 3,
}
RACINE = pathlib.Path(__file__).resolve().parents[3]


class _Calepinage:
    pk = 11

    def __init__(self):
        self.resultat = {}
        self.enregistrements = 0

    def save(self, **_kwargs):
        self.enregistrements += 1


def _conception(modules, module_specs=None, onduleur_specs=None):
    layout = {'version': 2, 'zones': [
        {'label': 'PAN-A', 'geometry': {'count': modules, 'azimuthDeg': 180.0,
                                        'tiltDeg': 15.0}}]}
    return concevoir_par_pan(
        layout, module_specs=module_specs or MODULE,
        onduleur_specs=onduleur_specs or ONDULEUR,
        temperatures=temperatures_site(
            saisie={'temperature_min_c': -5.0, 'temperature_max_c': 70.0}))


class ArbitrageTest(SimpleTestCase):
    """La fiche l'emporte ; le dossier n'est qu'un repli assumé."""

    def test_la_longueur_calculee_l_emporte_et_le_dit(self):
        reconciliation = longueur_chaine_retenue(_conception(24))

        self.assertEqual(reconciliation['origine'], ORIGINE_LONGUEUR_FICHE)
        self.assertEqual(reconciliation['longueur_dossier'],
                         MODULES_PAR_CHAINE)
        self.assertIsNotNone(reconciliation['longueur'])
        self.assertIn('CALCULÉE', reconciliation['detail'])

    def test_fiche_muette_replie_sur_la_longueur_de_dossier(self):
        incomplet = {cle: valeur for cle, valeur in MODULE.items()
                     if cle != 'voc_v'}

        reconciliation = longueur_chaine_retenue(
            _conception(24, module_specs=incomplet))

        self.assertEqual(reconciliation['origine'], ORIGINE_LONGUEUR_DOSSIER)
        self.assertEqual(reconciliation['longueur'], MODULES_PAR_CHAINE)
        self.assertIn('repli assumé', reconciliation['detail'])
        self.assertIsNone(reconciliation['ecart'])

    def test_l_ecart_au_dossier_est_calcule(self):
        reconciliation = longueur_chaine_retenue(_conception(24))

        self.assertEqual(reconciliation['ecart'],
                         reconciliation['par_pan']['PAN-A']
                         - MODULES_PAR_CHAINE)


class JournalTest(SimpleTestCase):
    """Un grand écart est JOURNALISÉ, jamais remplacé en silence (PVG2)."""

    def test_un_ecart_dans_la_tolerance_ne_journalise_rien(self):
        calepinage = _Calepinage()
        dans_tolerance = {'hors_tolerance': False, 'longueur': 15,
                          'longueur_dossier': 16, 'ecart': -1}

        self.assertIsNone(journaliser_ecart_longueur(calepinage,
                                                     dans_tolerance))
        self.assertEqual(calepinage.resultat, {})

    def test_un_ecart_hors_tolerance_part_en_warning_et_reste_en_historique(
            self):
        calepinage = _Calepinage()
        hors = {'hors_tolerance': True, 'longueur': 6,
                'longueur_dossier': 16, 'ecart': -10,
                'par_pan': {'PAN-A': 6}}

        with self.assertLogs(
                'apps.calepinage.services.electrique', level='WARNING') as log:
            journal = journaliser_ecart_longueur(calepinage, hors)

        self.assertEqual(len(journal), 1)
        self.assertEqual(journal[0]['ecart'], -10)
        self.assertIn('CAL170', '\n'.join(log.output))

        # L'historique s'ACCUMULE : la relecture du dossier doit voir la
        # succession des écarts, pas seulement le dernier.
        journaliser_ecart_longueur(calepinage, hors)
        self.assertEqual(
            len(calepinage.resultat['journal_longueur_chaine']), 2)


class RebouclagePlafondTest(SimpleTestCase):
    """Le plafond kWc par onduleur redevient un NOMBRE DE MODULES."""

    def test_le_plafond_est_traduit_en_modules(self):
        # 60 kWc plafond, modules de 710 Wc → 84 modules.
        self.assertEqual(plafond_modules(60.0, 710.0), 84)

    def test_sans_plafond_rien_n_est_suppose(self):
        self.assertIsNone(plafond_modules(None, 710.0))
        self.assertIsNone(plafond_modules(60.0, None))


class NoyauxSansLienTest(SimpleTestCase):
    """Les deux noyaux restent sans lien d'import (contrat import-linter)."""

    def test_aucun_des_deux_noyaux_n_importe_l_autre(self):
        # Analyse AST : on cherche des IMPORTS, pas des mentions en
        # commentaire (``core/electrique/types.py`` cite légitimement
        # ``core.calepinage.types`` dans sa docstring).
        self._verifier((RACINE / 'core' / 'calepinage' / 'electrique.py'),
                       'core.electrique')
        for fichier in (RACINE / 'core' / 'electrique').glob('*.py'):
            self._verifier(fichier, 'core.calepinage')

    def _verifier(self, fichier, interdit):
        import ast

        arbre = ast.parse(fichier.read_text(encoding='utf-8'))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                noms = [alias.name for alias in noeud.names]
            elif isinstance(noeud, ast.ImportFrom):
                noms = [noeud.module or '']
            else:
                continue
            for nom in noms:
                self.assertFalse(
                    nom == interdit or nom.startswith(interdit + '.'),
                    '%s importe %s — les deux noyaux doivent rester sans '
                    'lien (CAL170)' % (fichier.name, nom))
