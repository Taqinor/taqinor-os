# -*- coding: utf-8 -*-
"""CALX213 — les deux bornes d'onduleur publiées mais jamais lues.

``s_max_kva`` et ``dc_max_kwc`` sont publiés par la fiche et listés comme
champs de complétude (``apps/calepinage/services/equipements.py:73-74``), mais
aucun appelant hors tests ne les lisait : un champ DC au-dessus du plafond
d'entrée constructeur passait sans un mot.

Ce module arme les quatre cas demandés — borne publiée FRANCHIE, borne publiée
RESPECTÉE, borne ABSENTE, fiche muette sur les DEUX — plus les trois paliers
du ratio DC/AC devenus des réglages société (CALX145) : valeur absente ⇒ les
constantes d'aujourd'hui s'appliquent à l'identique ET sont publiées « convention
atelier, non sourcée » ; seuil BAS non saisi ⇒ aucun contrôle bas.

``SimpleTestCase`` : aucune base de données.
"""

from django.test import SimpleTestCase

from core.electrique.onduleurs import (
    BORNE_USUELLE_DC_AC,
    CLE_BORNE_USUELLE_DC_AC,
    CLE_SEUIL_ALERTE_DC_AC,
    CLE_SEUIL_BAS_DC_AC,
    SEUIL_ALERTE_DC_AC,
    SOURCE_CONVENTION_ATELIER,
    bornes_dc_ac,
    dimensionner_onduleurs,
)
from core.electrique.types import (
    EntreeElectrique,
    GroupePan,
    SpecModule,
    SpecOnduleur,
)

MODULE = SpecModule(vmp_v=34.0, voc_v=41.0, isc_a=13.8, imp_a=13.0,
                    pmax_wc=550.0, temp_coeff_voc_pct_c=-0.27,
                    temp_coeff_pmax_pct_c=-0.35)


def _onduleur(ac_kw=10.0, s_max_kva=None, dc_max_kwc=None,
              designation='Deye SUN-10K-SG05LP3'):
    return SpecOnduleur(n_mppt=2, mppt_v_min=120.0, mppt_v_max=850.0,
                        v_max_abs=1000.0, i_max_mppt_a=26.0, ac_kw=ac_kw,
                        v_demarrage_v=90.0, designation=designation,
                        s_max_kva=s_max_kva, dc_max_kwc=dc_max_kwc)


def _entree(nb_modules, onduleur=None, **kw):
    return EntreeElectrique(module=MODULE, onduleur=onduleur or _onduleur(),
                            groupes=(GroupePan('Sud', nb_modules, 180.0, 15.0),),
                            **kw)


class LaBorneDcMaxKwcBloque(SimpleTestCase):
    """Puissance crête raccordée > ``dc_max_kwc`` = hors spécification."""

    def test_borne_publiee_franchie_est_bloquante_et_se_nomme(self):
        # 30 × 550 Wc = 16,5 kWc sur un appareil dont la fiche plafonne à 13.
        evaluation = dimensionner_onduleurs(
            _entree(30, onduleur=_onduleur(dc_max_kwc=13.0)))
        self.assertTrue(evaluation.bloquants)
        message = evaluation.bloquants[0]
        self.assertIn('HORS SPÉCIFICATION', message)
        self.assertIn('16,50 kWc', message)          # la valeur calculée
        self.assertIn('13,00 kWc', message)          # la valeur de fiche
        self.assertIn('Deye SUN-10K-SG05LP3', message)
        self.assertIn('ajouter un onduleur', message)   # l'action corrective

    def test_borne_publiee_respectee_ne_dit_rien(self):
        evaluation = dimensionner_onduleurs(
            _entree(20, onduleur=_onduleur(dc_max_kwc=13.0)))   # 11 kWc
        self.assertEqual(evaluation.bloquants, ())

    def test_borne_absente_ne_controle_rien(self):
        """Aucun repli : sans ``dc_max_kwc``, l'appareil n'est pas jugé."""
        evaluation = dimensionner_onduleurs(
            _entree(60, onduleur=_onduleur(dc_max_kwc=None)))   # 33 kWc
        self.assertEqual(evaluation.bloquants, ())

    def test_le_plafond_est_lu_PAR_ONDULEUR(self):
        """Deux onduleurs partagent le champ : chacun reste sous sa borne."""
        evaluation = dimensionner_onduleurs(
            _entree(40, onduleur=_onduleur(dc_max_kwc=13.0),
                    plafond_kwc_par_onduleur=12.0))            # 22 kWc / 2
        self.assertEqual(evaluation.nombre, 2)
        self.assertEqual(evaluation.bloquants, ())


class LaBorneSMaxKvaAlerte(SimpleTestCase):
    """Puissance apparente < puissance active nominale = bridage, pas casse."""

    def test_borne_publiee_franchie_est_une_alerte_nommee(self):
        evaluation = dimensionner_onduleurs(
            _entree(20, onduleur=_onduleur(ac_kw=10.0, s_max_kva=9.9)))
        bridage = [a for a in evaluation.alertes if 'BRIDÉ' in a]
        self.assertEqual(len(bridage), 1)
        self.assertIn('9,90 kVA', bridage[0])
        self.assertIn('10,00 kW', bridage[0])
        self.assertIn('cos φ = 1', bridage[0])
        self.assertEqual(evaluation.bloquants, ())

    def test_borne_publiee_respectee_ne_dit_rien(self):
        evaluation = dimensionner_onduleurs(
            _entree(20, onduleur=_onduleur(ac_kw=10.0, s_max_kva=10.0)))
        self.assertEqual([a for a in evaluation.alertes if 'BRIDÉ' in a], [])

    def test_borne_absente_ne_controle_rien(self):
        evaluation = dimensionner_onduleurs(
            _entree(20, onduleur=_onduleur(ac_kw=10.0, s_max_kva=None)))
        self.assertEqual([a for a in evaluation.alertes if 'BRIDÉ' in a], [])


class UneFicheMuetteSurLesDeuxNeProduitAucunVerdict(SimpleTestCase):
    def test_aucun_bloquant_aucune_alerte_de_borne(self):
        evaluation = dimensionner_onduleurs(
            _entree(20, onduleur=_onduleur(s_max_kva=None, dc_max_kwc=None)))
        self.assertEqual(evaluation.bloquants, ())
        for alerte in evaluation.alertes:
            self.assertNotIn('BRIDÉ', alerte)
            self.assertNotIn('HORS SPÉCIFICATION', alerte)


class LesTroisPaliersDuRatioSontDesReglages(SimpleTestCase):
    def test_sans_saisie_les_constantes_s_appliquent_et_se_declarent(self):
        bornes = bornes_dc_ac(None)
        self.assertEqual(bornes.borne_usuelle.valeur, BORNE_USUELLE_DC_AC)
        self.assertEqual(bornes.seuil_alerte.valeur, SEUIL_ALERTE_DC_AC)
        self.assertEqual(bornes.borne_usuelle.source, SOURCE_CONVENTION_ATELIER)
        self.assertEqual(bornes.seuil_alerte.source, SOURCE_CONVENTION_ATELIER)
        # Le seuil BAS n'a pas de constante : non saisi, il ne contrôle rien.
        self.assertIsNone(bornes.seuil_bas.valeur)
        self.assertFalse(bornes.seuil_bas.controlee)

    def test_une_saisie_remplace_la_constante_avec_sa_source(self):
        bornes = bornes_dc_ac({
            CLE_BORNE_USUELLE_DC_AC: {'valeur': 1.20,
                                      'source': 'norme_interne'},
            CLE_SEUIL_ALERTE_DC_AC: {'valeur': 1.33,
                                     'source': 'norme_interne'},
        })
        self.assertEqual(bornes.borne_usuelle.valeur, 1.20)
        self.assertEqual(bornes.borne_usuelle.source, 'norme_interne')
        self.assertEqual(bornes.seuil_alerte.valeur, 1.33)

    def test_une_valeur_sans_source_est_traitee_comme_non_saisie(self):
        bornes = bornes_dc_ac({CLE_BORNE_USUELLE_DC_AC: {'valeur': 1.20}})
        self.assertEqual(bornes.borne_usuelle.valeur, BORNE_USUELLE_DC_AC)
        self.assertEqual(bornes.borne_usuelle.source, SOURCE_CONVENTION_ATELIER)

    def test_la_borne_saisie_pilote_vraiment_l_alerte(self):
        entree = _entree(24)                       # 13,2 kWc / 10 kW = 1,32
        sans = dimensionner_onduleurs(entree)
        self.assertEqual([a for a in sans.alertes if 'DC/AC' in a], [])
        avec = dimensionner_onduleurs(entree, reglages={
            CLE_BORNE_USUELLE_DC_AC: {'valeur': 1.20,
                                      'source': 'norme_interne'}})
        haute = [a for a in avec.alertes if 'borne usuelle' in a]
        self.assertEqual(len(haute), 1)
        self.assertIn('1,20', haute[0])

    def test_le_seuil_bas_saisi_publie_onduleur_sous_utilise(self):
        entree = _entree(10, onduleur=_onduleur(ac_kw=10.0))   # 5,5 / 10 = 0,55
        evaluation = dimensionner_onduleurs(entree, reglages={
            CLE_SEUIL_BAS_DC_AC: {'valeur': 0.75,
                                  'source': 'reference_externe'}})
        bas = [a for a in evaluation.alertes if 'sous-utilisé' in a]
        self.assertEqual(len(bas), 1)
        self.assertIn('0,55', bas[0])
        self.assertIn('0,75', bas[0])
        self.assertIn('reference_externe', bas[0])
        self.assertEqual(evaluation.ratio_dc_ac.borne_min, 0.75)

    def test_sans_seuil_bas_aucun_controle_bas(self):
        entree = _entree(10, onduleur=_onduleur(ac_kw=10.0))
        evaluation = dimensionner_onduleurs(entree)
        self.assertEqual([a for a in evaluation.alertes
                          if 'sous-utilisé' in a], [])
        self.assertIsNone(evaluation.ratio_dc_ac.borne_min)

    def test_les_bornes_employees_sont_publiees_par_l_evaluation(self):
        evaluation = dimensionner_onduleurs(_entree(24))
        self.assertIsNotNone(evaluation.bornes)
        self.assertEqual(evaluation.bornes.borne_usuelle.cle,
                         CLE_BORNE_USUELLE_DC_AC)
        self.assertEqual(evaluation.bornes.seuil_bas.cle, CLE_SEUIL_BAS_DC_AC)
