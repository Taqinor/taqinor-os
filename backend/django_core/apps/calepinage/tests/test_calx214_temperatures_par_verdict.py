# -*- coding: utf-8 -*-
"""CALX214 — LA TEMPÉRATURE QUI A SERVI, PUBLIÉE CONTRÔLE PAR CONTRÔLE.

LE DÉFAUT CORRIGÉ
-----------------
``fenetre_admissible`` recevait bien ``temp_froid_c``/``temp_chaud_c``, mais
chaque verdict de tension ne citait sa température que dans une PHRASE :
aucun champ ne disait QUELLE borne avait été évaluée à QUELLE température, et
``TemperaturesSite.source`` (``services/electrique.py``) n'était rattachée à
AUCUN verdict individuel — elle vivait en tête du résultat, loin du contrôle
qu'elle justifie.

PARITÉ CITÉE, JAMAIS RECOPIÉE
-----------------------------
PV*SOL publie explicitement ses trois températures de contrôle — MPP à 70 °C
et 15 °C, Voc à −10 °C
(https://help.valentin-software.com/pvsol/en/pages/inverters/configuration-check/).
La PRATIQUE est reprise (publier la température de chaque contrôle), les
VALEURS ne deviennent aucun défaut ici : celles qui sortent sont celles du
site, avec leur provenance.

Tests PURS : le noyau et le service électrique se calculent sans base.
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.chaines import concevoir_par_pan
from apps.calepinage.services.electrique import (
    MENTION_NON_SOURCEE, SOURCE_SAISIE, TemperaturesSite,
    verdicts_electriques,
)
from core.electrique.chaines import (
    _verdicts_tension, concevoir_chaines, fenetre_admissible,
)
from core.electrique.types import (
    Chaine, EntreeElectrique, GroupePan, SpecModule, SpecOnduleur,
)

#: Un couple module/onduleur RÉEL du dépôt (fiche CS7N-710 / Deye SG05LP3,
#: déjà employé par l'incident DEV-202608-0016) — aucun chiffre inventé ici.
MODULE = SpecModule(vmp_v=41.4, voc_v=49.3, isc_a=18.59, imp_a=17.59,
                    pmax_wc=710.0, designation='CS7N-710')
ONDULEUR = SpecOnduleur(n_mppt=2, mppt_v_min=120.0, mppt_v_max=500.0,
                        v_max_abs=600.0, i_max_mppt_a=26.0, ac_kw=5.0,
                        phases=1, v_demarrage_v=90.0,
                        designation='Deye SG05LP3')

#: Les QUATRE bornes de tension de ``_verdicts_tension`` — chacune doit
#: porter SA température. C'est la liste FERMÉE du contrôle.
CODES_TENSION = (
    'CH_VOC_FROID_AU_DESSUS_V_MAX',
    'CH_VMP_FROID_AU_DESSUS_MPPT',
    'CH_VMP_CHAUD_SOUS_MPPT',
    'CH_VMP_CHAUD_SOUS_DEMARRAGE',
)

FROID, CHAUD = -5.0, 70.0


def _entree(nb_modules=20, *, source=None, mention='', froid=FROID,
            chaud=CHAUD, onduleur=ONDULEUR):
    return EntreeElectrique(
        module=MODULE, onduleur=onduleur,
        groupes=(GroupePan(label='Sud', nb_modules=nb_modules,
                           azimut_deg=180.0, inclinaison_deg=15.0),),
        phases=1, temp_froid_c=froid, temp_chaud_c=chaud,
        temp_source=source, temp_mention=mention)


def _chaine(repere, nb_modules, *, voc, vmp_froid, vmp_chaud):
    """Une chaîne aux tensions IMPOSÉES — c'est le contrôle qu'on teste."""
    return Chaine(repere=repere, pan='Sud', nb_modules=nb_modules, mppt=1,
                  voc_froid_v=voc, vmp_froid_v=vmp_froid,
                  vmp_chaud_v=vmp_chaud, vmp_stc_v=MODULE.vmp_v * nb_modules,
                  isc_a=MODULE.isc_a, imp_a=MODULE.imp_a,
                  puissance_kwc=nb_modules * MODULE.pmax_wc / 1000.0)


def _par_code(verdicts):
    return {verdict.code: verdict for verdict in verdicts}


class QuatreBornesTest(unittest.TestCase):
    """Les quatre bornes portent leur température ET sa source."""

    def _verdicts_des_quatre_bornes(self, source=SOURCE_SAISIE, mention=''):
        """Les quatre contrôles de tension prononcés en UN appel.

        ``concevoir_chaines`` choisit toujours une longueur DANS la fenêtre :
        les deux bornes HAUTES n'y sont donc jamais franchies. Le contrôle
        lui-même est appelé directement, sur une chaîne trop LONGUE et une
        chaîne trop COURTE — la physique interdit d'être les deux à la fois.
        """
        fenetre = fenetre_admissible(MODULE, ONDULEUR, FROID, CHAUD,
                                     temp_source=source, temp_mention=mention)
        verdicts = []
        _verdicts_tension((_chaine('CH1', 14, voc=700.0, vmp_froid=600.0,
                                   vmp_chaud=520.0),
                           _chaine('CH2', 1, voc=53.3, vmp_froid=44.8,
                                   vmp_chaud=36.4)),
                          ONDULEUR, fenetre, [], verdicts)
        return _par_code(verdicts)

    def test_les_quatre_bornes_portent_leur_temperature(self):
        trouves = self._verdicts_des_quatre_bornes()
        manquants = [code for code in CODES_TENSION if code not in trouves]
        self.assertEqual(manquants, [],
                         "ces bornes ne se sont pas prononcées : %s"
                         % manquants)
        attendu = {
            'CH_VOC_FROID_AU_DESSUS_V_MAX': FROID,
            'CH_VMP_FROID_AU_DESSUS_MPPT': FROID,
            'CH_VMP_CHAUD_SOUS_MPPT': CHAUD,
            'CH_VMP_CHAUD_SOUS_DEMARRAGE': CHAUD,
        }
        for code, temperature in attendu.items():
            with self.subTest(code=code):
                self.assertEqual(trouves[code].temperature_c, temperature)
                self.assertEqual(trouves[code].temperature_source,
                                 SOURCE_SAISIE)

    def test_sans_source_chaque_verdict_porte_la_mention(self):
        trouves = self._verdicts_des_quatre_bornes(
            source=None, mention=MENTION_NON_SOURCEE)
        for code in CODES_TENSION:
            with self.subTest(code=code):
                self.assertIsNone(trouves[code].temperature_source)
                self.assertEqual(trouves[code].temperature_mention,
                                 MENTION_NON_SOURCEE)

    def test_la_mention_n_est_pas_seulement_en_tete(self):
        # Le défaut corrigé : la mention existait en tête du résultat
        # (``resultat['temperatures']``) et nulle part sur les contrôles.
        trouves = self._verdicts_des_quatre_bornes(
            source=None, mention=MENTION_NON_SOURCEE)
        portees = [verdict.temperature_mention
                   for verdict in trouves.values()]
        self.assertEqual(len(portees), len(CODES_TENSION))
        self.assertTrue(all(texte == MENTION_NON_SOURCEE
                            for texte in portees))

    def test_aucune_temperature_en_phrase_sans_champ(self):
        # Tout verdict qui ÉCRIT un « °C » dans sa phrase porte aussi sa
        # température dans un champ : c'est la règle « zéro chiffre nu ».
        for nb_modules in (2, 20, 40):
            resultat = concevoir_chaines(
                _entree(nb_modules, source=SOURCE_SAISIE))
            for verdict in resultat.verdicts:
                if '°C' not in verdict.libelle:
                    continue
                with self.subTest(code=verdict.code):
                    self.assertIsNotNone(
                        verdict.temperature_c,
                        "« %s » écrit une température dans sa phrase sans la "
                        "publier dans un champ" % verdict.code)

    def test_une_fenetre_vide_porte_sa_temperature_et_sa_source(self):
        # Onduleur dont la tension maximale absolue est trop basse pour un
        # seul module à froid : la fenêtre est vide, et son verdict cite les
        # deux températures dans sa phrase.
        etroit = SpecOnduleur(n_mppt=1, mppt_v_min=400.0, mppt_v_max=500.0,
                              v_max_abs=60.0, i_max_mppt_a=26.0, ac_kw=5.0,
                              phases=1, v_demarrage_v=350.0)
        resultat = concevoir_chaines(_entree(6, source=SOURCE_SAISIE,
                                             onduleur=etroit))
        vide = _par_code(resultat.verdicts).get('CH_FENETRE_VIDE')
        self.assertIsNotNone(vide, 'la fenêtre devait être déclarée vide')
        self.assertEqual(vide.temperature_c, FROID)
        self.assertEqual(vide.temperature_source, SOURCE_SAISIE)


class FenetreTransporteLaProvenanceTest(unittest.TestCase):
    """La fenêtre porte la provenance, et ne calcule rien de plus avec."""

    def test_la_provenance_n_est_pas_inventee_quand_elle_manque(self):
        fenetre = fenetre_admissible(MODULE, ONDULEUR, FROID, CHAUD)
        self.assertIsNone(fenetre.temp_source)
        self.assertEqual(fenetre.temp_mention, '')

    def test_la_provenance_ne_change_aucune_borne(self):
        nue = fenetre_admissible(MODULE, ONDULEUR, FROID, CHAUD)
        sourcee = fenetre_admissible(MODULE, ONDULEUR, FROID, CHAUD,
                                     temp_source=SOURCE_SAISIE,
                                     temp_mention='')
        for champ in ('longueur_min', 'longueur_max', 'max_par_voc',
                      'max_par_mppt', 'min_par_mppt', 'min_par_demarrage',
                      'trop_etroite', 'motif'):
            with self.subTest(champ=champ):
                self.assertEqual(getattr(nue, champ), getattr(sourcee, champ))

    def test_un_verdict_de_courant_ne_cite_aucune_temperature(self):
        # Deux chaînes sur UNE entrée : l'Isc cumulé se prononce. Un courant
        # ne se contrôle à aucune température — les trois champs restent
        # neutres plutôt que de citer un chiffre qui n'a servi à rien.
        mono = SpecOnduleur(n_mppt=1, mppt_v_min=120.0, mppt_v_max=900.0,
                            v_max_abs=1100.0, i_max_mppt_a=26.0, ac_kw=5.0,
                            phases=1, isc_max_mppt_a=17.0)
        resultat = concevoir_chaines(_entree(12, source=SOURCE_SAISIE,
                                             onduleur=mono))
        courant = [verdict for verdict in resultat.verdicts
                   if verdict.code.startswith('CH_ISC')
                   or verdict.code.startswith('CH_IMP')]
        self.assertTrue(courant, 'aucun verdict de courant ne s est prononcé')
        for verdict in courant:
            with self.subTest(code=verdict.code):
                self.assertIsNone(verdict.temperature_c)


class VerdictsServisTest(unittest.TestCase):
    """Les verdicts du contrat CAL244 portent les mêmes trois clés."""

    def _conception(self, temperatures):
        return concevoir_par_pan(
            {'zones': [{'label': 'Sud', 'azimuth': 180.0, 'tilt': 15.0,
                        'geometry': {'count': 20}}]},
            module_specs={'vmp_v': MODULE.vmp_v, 'voc_v': MODULE.voc_v,
                          'isc_a': MODULE.isc_a, 'imp_a': MODULE.imp_a,
                          'pmax_wc': MODULE.pmax_wc},
            onduleur_specs={'n_mppt': 2, 'mppt_v_min': 120.0,
                            'mppt_v_max': 500.0, 'v_max_abs': 600.0,
                            'i_max_mppt_a': 26.0, 'ac_kw': 5.0, 'phases': 1},
            temperatures=temperatures)

    def test_les_trois_cles_sont_toujours_presentes(self):
        conception = self._conception(TemperaturesSite(
            froid_c=FROID, chaud_c=CHAUD, source=SOURCE_SAISIE))
        verdicts = verdicts_electriques(conception)
        self.assertTrue(verdicts)
        for verdict in verdicts:
            with self.subTest(code=verdict['code']):
                for cle in ('temperature_c', 'temperature_source',
                            'temperature_mention'):
                    self.assertIn(cle, verdict)

    def test_les_verdicts_de_tension_citent_leur_temperature_et_sa_source(self):
        conception = self._conception(TemperaturesSite(
            froid_c=FROID, chaud_c=CHAUD, source=SOURCE_SAISIE))
        par_code = {v['code']: v for v in verdicts_electriques(conception)}
        attendu = {'voc_cold_under_vmax': FROID,
                   'vmp_cold_under_mppt_max': FROID,
                   'vmp_hot_over_mppt_min': CHAUD}
        for code, temperature in attendu.items():
            with self.subTest(code=code):
                self.assertEqual(par_code[code]['temperature_c'], temperature)
                self.assertEqual(par_code[code]['temperature_source'],
                                 SOURCE_SAISIE)
                self.assertEqual(par_code[code]['temperature_mention'], '')

    def test_sans_source_le_verdict_servi_porte_la_mention(self):
        conception = self._conception(TemperaturesSite(
            froid_c=FROID, chaud_c=CHAUD, source=None,
            mention=MENTION_NON_SOURCEE))
        par_code = {v['code']: v for v in verdicts_electriques(conception)}
        for code in ('voc_cold_under_vmax', 'vmp_cold_under_mppt_max',
                     'vmp_hot_over_mppt_min'):
            with self.subTest(code=code):
                self.assertIsNone(par_code[code]['temperature_source'])
                self.assertEqual(par_code[code]['temperature_mention'],
                                 MENTION_NON_SOURCEE)

    def test_le_verdict_de_courant_reste_neutre(self):
        conception = self._conception(TemperaturesSite(
            froid_c=FROID, chaud_c=CHAUD, source=SOURCE_SAISIE))
        par_code = {v['code']: v for v in verdicts_electriques(conception)}
        self.assertIsNone(par_code['courant_par_entree_mppt']['temperature_c'])
        self.assertIsNone(par_code['ratio_dc_ac']['temperature_c'])


if __name__ == '__main__':      # pragma: no cover
    unittest.main()
