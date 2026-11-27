"""CALX257 — le calepinage PUBLIE les kWh que le barème société calcule.

Ce qui est prouvé ici :

* avec le réglage de la société, chaque mois porte ``kwh`` (la facture réelle
  SRM n° 643769639 : 496,03 MAD d'énergie + 39,94 MAD de charges fixes ⇒
  359 kWh) et l'avertissement « conversion non faite » disparaît ;
* SANS société : aucun réglage n'est lu (le lecteur n'est jamais appelé),
  ``kwh`` reste ``None`` et le motif NOMME le réglage manquant ;
* la classe est SAISIE : inconnue ⇒ ``ProfilInvalide.champ == 'classe'`` ;
* GARDE DE SOURCE — ``services/consommation.py`` ne porte aucune arithmétique
  de montant : il ne nomme aucun interne du barème, la fonction qui publie
  les kWh ne calcule rien, aucune opération n'y mélange un montant et une
  énergie, et la conversion vient de ``apps.parametres.tariff``.
  (``interpoler_factures``, CAL147, reste la seule forme en MAD du module :
  elle relie deux montants SAISIS — aucun barème, aucune énergie.)

Aucune base : ``TariffSettings`` NON enregistré (``SimpleTestCase``).
"""
from __future__ import annotations

import ast
import pathlib
import re
import unittest
from decimal import Decimal

from django.test import SimpleTestCase

from apps.calepinage.services import consommation
from apps.calepinage.services.consommation import (
    AVIS_KWH_NON_CONVERTIS, ProfilInvalide, _profil_mensuel, _publier_kwh,
)
from apps.parametres.models_tariff import TariffSettings


def lecteur(reglages, appels=None):
    def lire(company):
        if appels is not None:
            appels.append(company)
        return reglages
    return lire


class KwhPubliesTest(SimpleTestCase):

    def setUp(self):
        self.reglages = TariffSettings(
            redevance_compteur_mad_mois=Decimal('39.94'))

    def test_la_facture_reelle_publie_359_kwh_par_mois(self):
        profil = _profil_mensuel(facture_hiver=Decimal('535.97'))
        _publier_kwh(profil, 'SOCIETE', classe='residentiel',
                     lire_reglages=lecteur(self.reglages))
        for ligne in profil['mois']:
            self.assertAlmostEqual(ligne['kwh'], 359.0, delta=1.0)
            self.assertEqual(ligne['kwh_motif'], '')
        self.assertNotIn(AVIS_KWH_NON_CONVERTIS, profil['avertissements'])
        self.assertEqual(profil['conversion_kwh']['classe'], 'residentiel')
        self.assertEqual(profil['conversion_kwh']['motifs'], [])

    def test_un_mois_vide_reste_vide_avec_son_motif(self):
        profil = _profil_mensuel(facture_hiver=None, saisies={3: 535.97})
        _publier_kwh(profil, 'SOCIETE', classe='residentiel',
                     lire_reglages=lecteur(self.reglages))
        par_mois = {ligne['mois']: ligne for ligne in profil['mois']}
        self.assertAlmostEqual(par_mois[3]['kwh'], 359.0, delta=1.0)
        self.assertIsNone(par_mois[1]['kwh'])
        self.assertTrue(par_mois[1]['kwh_motif'])

    def test_sans_societe_kwh_none_et_le_motif_nomme_le_reglage(self):
        appels = []
        profil = _profil_mensuel(facture_hiver=Decimal('535.97'))
        _publier_kwh(profil, None, classe='residentiel',
                     lire_reglages=lecteur(self.reglages, appels))
        self.assertEqual(appels, [])          # jamais un réglage de repli
        for ligne in profil['mois']:
            self.assertIsNone(ligne['kwh'])
            self.assertIn('Tarification & ROI', ligne['kwh_motif'])
        motifs = profil['conversion_kwh']['motifs']
        self.assertEqual(len(motifs), 1)
        self.assertIn('Tarification & ROI', motifs[0])
        self.assertIn(motifs[0], profil['avertissements'])

    def test_classe_inconnue_refusee_en_la_nommant(self):
        profil = _profil_mensuel(facture_hiver=600)
        with self.assertRaises(ProfilInvalide) as capture:
            _publier_kwh(profil, 'SOCIETE', classe='commercial',
                         lire_reglages=lecteur(self.reglages))
        self.assertEqual(capture.exception.champ, 'classe')


#: Les internes du barème : le module qui PUBLIE ne doit en nommer aucun.
INTERNES_BAREME = frozenset({
    'Decimal', 'effective_kwh_price', 'effective_tiers',
    'force_motrice_prix_kwh_ttc', 'monthly_bill',
    'monthly_bill_force_motrice', 'monthly_bill_residentiel', 'prix_kwh_ttc',
    'redevance_compteur_mad_mois', 'residential_tiers',
    'selective_threshold_kwh', 'tolerance_kwh',
})

TERME_MONTANT = re.compile(r'mad|facture|montant|prix|tarif|ttc')
TERME_ENERGIE = re.compile(r'kwh')

ARITHMETIQUE = (ast.BinOp, ast.AugAssign)

INSTRUCTIONS_SIMPLES = (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Return,
                        ast.Expr)


def _arbre():
    source = pathlib.Path(consommation.__file__).read_text(encoding='utf-8')
    return ast.parse(source)


def _noms_de_code(noeud):
    """Les identifiants du CODE (jamais la prose des docstrings)."""
    for sous in ast.walk(noeud):
        if isinstance(sous, ast.Name):
            yield sous.id
        elif isinstance(sous, ast.Attribute):
            yield sous.attr
        elif isinstance(sous, ast.alias):
            yield sous.name
        elif isinstance(sous, ast.keyword) and sous.arg:
            yield sous.arg


def _termes(noeud):
    termes = set(_noms_de_code(noeud))
    for sous in ast.walk(noeud):
        if isinstance(sous, ast.Constant) and isinstance(sous.value, str):
            termes.add(sous.value)
    return {terme.lower() for terme in termes}


class GardeDeSourceTest(unittest.TestCase):

    def test_le_module_ne_nomme_aucun_interne_du_bareme(self):
        nommes = set(_noms_de_code(_arbre())) & INTERNES_BAREME
        self.assertEqual(nommes, set())

    def test_la_fonction_qui_publie_ne_calcule_rien(self):
        fonctions = {noeud.name: noeud for noeud in ast.walk(_arbre())
                     if isinstance(noeud, ast.FunctionDef)}
        for nom in ('_publier_kwh', '_lire_reglages_tarif'):
            calculs = [sous for sous in ast.walk(fonctions[nom])
                       if isinstance(sous, ARITHMETIQUE)
                       or (isinstance(sous, ast.UnaryOp)
                           and isinstance(sous.op, ast.USub))]
            self.assertEqual(calculs, [], nom)

    def test_aucune_operation_ne_melange_montant_et_energie(self):
        # À l'échelle de l'INSTRUCTION (cible comprise) : ``kwh = facture / p``
        # mélange les deux termes même si l'opération seule n'en voit qu'un.
        fautives = []
        for noeud in ast.walk(_arbre()):
            if isinstance(noeud, (ast.If, ast.While)):
                noeud = noeud.test
            elif not isinstance(noeud, INSTRUCTIONS_SIMPLES):
                continue
            if not any(isinstance(sous, ARITHMETIQUE)
                       for sous in ast.walk(noeud)):
                continue
            termes = _termes(noeud)
            if (any(TERME_MONTANT.search(t) for t in termes)
                    and any(TERME_ENERGIE.search(t) for t in termes)):
                fautives.append(noeud.lineno)
        self.assertEqual(fautives, [])

    def test_la_conversion_vient_du_bareme_societe(self):
        importes = {
            (noeud.module, alias.name)
            for noeud in ast.walk(_arbre())
            if isinstance(noeud, ast.ImportFrom)
            for alias in noeud.names
        }
        self.assertIn(('apps.parametres.tariff', 'kwh_depuis_facture'),
                      importes)


class SupposeTest(SimpleTestCase):
    """ACAL980 — « Ce qui est supposé » : un repli caché par entrée, sa valeur
    LUE des constantes du moteur, jamais recopiée."""

    DOSSIER = 'dossier'
    FICHE = 'fiche'

    def _liste(self, origine, societe, manquantes=()):
        from apps.calepinage.services.suppositions import (
            liste_des_suppositions)

        # ACAL2014 — la valeur dite est la longueur RETENUE (ici celle d'un dossier d'appel d'offres).
        from core.calepinage.electrique import MODULES_PAR_CHAINE

        return liste_des_suppositions({'origine': origine, 'longueur': MODULES_PAR_CHAINE}, societe,
                                      self.DOSSIER, manquantes)

    @staticmethod
    def _manquantes_sans_onduleur():
        """``Conception.manquantes`` RÉELLES de l'état d'``exemple_vide`` : 12
        modules posés (fiche module complète), AUCUN onduleur désigné — d'où
        ``electrique.onduleurs = []`` et ``chainage = null`` dans l'échantillon."""
        from apps.calepinage.services.chaines import concevoir_par_pan
        from apps.calepinage.services.electrique import temperatures_site

        conception = concevoir_par_pan(
            {'version': 2, 'zones': [{'id': 'z1', 'label': 'PAN-A', 'geometry': {
                'count': 12, 'azimuthDeg': 180.0, 'tiltDeg': 15.0}}]},
            module_specs={'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4,
                          'imp_a': 17.1, 'pmax_wc': 720.0},
            onduleur_specs={}, temperatures=temperatures_site(saisie={
                'temperature_min_c': -5.0, 'temperature_max_c': 70.0}))
        assert conception.manquantes and all(
            m.startswith('onduleur : ') for m in conception.manquantes), \
            conception.manquantes
        return conception.manquantes

    def test_fiche_incomplete_et_sans_allee_nomme_les_deux_replis(self):
        from core.calepinage.electrique import MODULES_PAR_CHAINE
        from core.calepinage.types import Parametres

        suppose = self._liste(self.DOSSIER, {})
        self.assertEqual([s['code'] for s in suppose],
                         ['longueur_chaine_dossier', 'allee_par_defaut'])
        self.assertEqual(suppose[0]['valeur'], MODULES_PAR_CHAINE)
        self.assertIn('%d modules par chaîne' % MODULES_PAR_CHAINE,
                      suppose[0]['libelle'])
        self.assertEqual(suppose[1]['valeur'], Parametres.__dataclass_fields__[
            'allee_m'].default)
        self.assertIn('0,60 m', suppose[1]['libelle'])
        # ACAL1630 (revue) — chaque repli dit OÙ le renseigner (lu par ``lienManque`` côté écran).
        self.assertEqual(suppose[0]['cible'], {'onglet': 'fiches'})
        self.assertEqual(suppose[1]['cible'], {'onglet': 'reglages', 'champ': 'allees'})
        for repli in suppose:
            self.assertEqual(sorted(repli),
                             ['champ', 'code', 'libelle', 'valeur'])

    def test_acal1648_la_ligne_nomme_ce_qui_manque_en_mots_de_metier(self):
        from apps.calepinage.services.suppositions import liste_des_suppositions

        reglee = {'degagements': {'allee_technique_m': 0.8}}
        dossier = {'origine': self.DOSSIER, 'longueur': 16}
        sans_onduleur = liste_des_suppositions(dossier, reglee, self.DOSSIER, ('onduleur : fiche absente',))
        self.assertEqual(
            sans_onduleur[0]['libelle'],
            "Choisissez l'onduleur pour vérifier la longueur des chaînes (16 modules par défaut, à confirmer)")
        sans_module = liste_des_suppositions(dossier, reglee, self.DOSSIER, ('module : voc_v',))
        self.assertTrue(sans_module[0]['libelle'].startswith('Complétez la fiche du module pour vérifier'))
        self.assertNotIn('repli', sans_onduleur[0]['libelle'])

    def test_fiche_complete_et_allee_reglee_liste_vide(self):
        societe = {'degagements': {'allee_technique_m': 0.8}}
        self.assertEqual(self._liste(self.FICHE, societe), [])

    def test_une_allee_reglee_retire_son_repli_seulement(self):
        societe = {'degagements': {'allee_technique_m': 0.8}}
        self.assertEqual(
            [s['code'] for s in self._liste(self.DOSSIER, societe)],
            ['longueur_chaine_dossier'])
        self.assertEqual(
            [s['code'] for s in self._liste(self.FICHE, {})],
            ['allee_par_defaut'])

    def test_la_forme_est_celle_du_contrat_partage(self):
        import json

        chemin = (pathlib.Path(__file__).resolve().parent.parent
                  / 'contract_samples' / 'calepinage_resultat.json')
        exemple = json.loads(chemin.read_text(encoding='utf-8'))
        vide = exemple['exemple_vide']['suppose']
        # ``exemple_vide`` = posé, non chaîné, SANS onduleur désigné : le
        # serveur reçoit les ``manquantes`` de cette conception (ACAL1648).
        self.assertEqual(vide, self._liste(self.DOSSIER, {},
                                           self._manquantes_sans_onduleur()))
        self.assertEqual(exemple['exemple']['suppose'],
                         self._liste(self.FICHE, {}))
