# -*- coding: utf-8 -*-
"""CALX215 — les deux natures de dépassement, enfin NOMMÉES.

Avant : la distinction « plage interdite » / « plage bloquante » existait dans
le calcul (Isc cumulé hors fiche = bloquant, Imp cumulé = alerte, incident
DEV-202608-0016) mais ne ressortait que par la LISTE où le message atterrissait.
Le consommateur recevait des PHRASES, sans code, sans nature, sans borne.

Ce module arme quatre garanties :

1. les listes historiques ``bloquants``/``alertes`` DÉRIVENT des objets — mot
   pour mot, dans le même ordre : aucun aval ne bouge ;
2. chaque code n'apparaît QU'UNE FOIS dans le source du moteur — deux contrôles
   ne peuvent pas se répondre sous la même identité ;
3. ``non_verifiable`` n'est JAMAIS rendu comme un ``ok`` ;
4. seul un BLOQUANT arrête un enregistrement ; une alerte passée outre laisse
   une trace relisible (auteur, date, motif).

Un test lit toujours un verdict par son CODE, jamais par sa position dans une
liste. ``SimpleTestCase`` : aucune base de données.
"""

import datetime
import re
from pathlib import Path

from django.test import SimpleTestCase

from core.electrique.chaines import concevoir_chaines
from core.electrique.types import (
    NATURES_CONNUES,
    STATUT_ALERTE,
    STATUT_BLOQUANT,
    STATUT_NON_VERIFIABLE,
    STATUTS_ALERTANTS,
    STATUTS_CONNUS,
    EntreeElectrique,
    GroupePan,
    SpecModule,
    SpecOnduleur,
    enregistrement_possible,
    libelles,
    passer_outre,
)

SOURCE_CHAINES = (Path(__file__).resolve().parents[3]
                  / 'core' / 'electrique' / 'chaines.py')

#: Les codes que le moteur de chaînes sait prononcer. La liste est ÉCRITE ici
#: (et non dérivée du source) pour qu'un code supprimé par accident fasse
#: rougir au lieu de disparaître en silence.
CODES_ATTENDUS = (
    'CH_FENETRE_VIDE',
    'CH_BORNES_NON_VERIFIABLES',
    'CH_LONGUEUR_IMPOSEE_INVALIDE',
    'CH_LONGUEUR_IMPOSEE_SUR_FENETRE_VIDE',
    'CH_LONGUEUR_IMPOSEE_HORS_PLAGE',
    'CH_AUCUN_MODULE',
    'CH_PANS_PARTAGENT_UNE_ENTREE',
    'CH_PARTITION_NON_EGALE',
    'CH_MODULES_EN_RESERVE',
    'CH_VOC_FROID_AU_DESSUS_V_MAX',
    'CH_VMP_FROID_AU_DESSUS_MPPT',
    'CH_VMP_CHAUD_SOUS_MPPT',
    'CH_VMP_CHAUD_SOUS_DEMARRAGE',
    'CH_ISC_CUMULE_HORS_SPECIFICATION',
    'CH_IMP_CUMULE_ECRETAGE',
    'CH_ISC_CUMULE_SUR_BORNE_DE_REPLI',
)


def _module(vmp=34.0, voc=41.0, pmax=550.0, coeff_voc=-0.27, coeff_pmax=-0.35,
            isc=13.8, imp=13.0):
    return SpecModule(vmp_v=vmp, voc_v=voc, isc_a=isc, imp_a=imp, pmax_wc=pmax,
                      temp_coeff_voc_pct_c=coeff_voc,
                      temp_coeff_pmax_pct_c=coeff_pmax)


def _onduleur(n_mppt=2, mppt_min=120.0, mppt_max=850.0, v_max=1000.0,
              i_max=26.0, ac_kw=10.0, v_demarrage=90.0, isc_max=None):
    return SpecOnduleur(n_mppt=n_mppt, mppt_v_min=mppt_min,
                        mppt_v_max=mppt_max, v_max_abs=v_max,
                        i_max_mppt_a=i_max, ac_kw=ac_kw,
                        v_demarrage_v=v_demarrage, isc_max_mppt_a=isc_max)


def _entree(nb_modules=24, module=None, onduleur=None, groupes=None, **kw):
    return EntreeElectrique(
        module=module or _module(),
        onduleur=onduleur or _onduleur(),
        groupes=(groupes if groupes is not None
                 else (GroupePan('Sud', nb_modules, 180.0, 15.0),)),
        **kw)


def _codes(resultat):
    return tuple(verdict.code for verdict in resultat.verdicts)


def _par_code(resultat, code):
    """LE verdict de ce code — lecture par identité, jamais par position."""
    for verdict in resultat.verdicts:
        if verdict.code == code:
            return verdict
    return None


#: Les configurations de référence, chacune choisie pour DÉCLENCHER un
#: contrôle précis. Elles servent à la fois aux tests d'équivalence et à la
#: couverture des codes.
def _cas():
    return {
        'nominal': _entree(24),
        'voc_froid_hors_borne': _entree(
            5, module=_module(vmp=40.0, voc=49.0, coeff_voc=-0.30),
            onduleur=_onduleur(n_mppt=1, mppt_min=10.0, mppt_max=45.0,
                               v_max=50.0, ac_kw=4.0, v_demarrage=10.0)),
        # Incident DEV-202608-0016 : l'Isc d'UNE chaîne sort déjà de la borne
        # matérielle publiée — hors spécification, donc BLOQUANT.
        'isc_hors_specification': _entree(
            50, module=_module(isc=18.59, imp=17.59, pmax=710.0),
            onduleur=_onduleur(n_mppt=1, i_max=17.0, isc_max=17.0)),
        # Deux chaînes de CS7N-710 sur une entrée Deye SG05LP3 : l'Imp cumulé
        # écrête en permanence, l'Isc cumulé reste sous la borne publiée.
        'ecretage_imp': _entree(
            20, module=_module(isc=18.59, imp=17.59, pmax=710.0),
            onduleur=_onduleur(n_mppt=1, i_max=26.0, isc_max=39.0),
            longueur_chaine_forcee=10),
        # Fiche MUETTE sur l'Isc : le repli prudent alerte, il ne bloque pas.
        'repli_isc': _entree(
            20, module=_module(isc=18.59, imp=9.0, pmax=710.0),
            onduleur=_onduleur(n_mppt=1, i_max=26.0),
            longueur_chaine_forcee=10),
        'fiche_muette': _entree(
            12, module=_module(voc=0.0, vmp=0.0),
            onduleur=_onduleur(mppt_max=0.0, v_max=0.0)),
        'fenetre_vide': _entree(
            10, onduleur=_onduleur(n_mppt=1, mppt_min=200.0, mppt_max=100.0,
                                   v_max=60.0, v_demarrage=200.0)),
        'longueur_imposee_sur_fenetre_vide': _entree(
            10, onduleur=_onduleur(n_mppt=1, mppt_min=200.0, mppt_max=100.0,
                                   v_max=60.0, v_demarrage=200.0),
            longueur_chaine_forcee=8),
        'vmp_froid_au_dessus_mppt': _entree(
            22, onduleur=_onduleur(n_mppt=1, mppt_min=300.0, mppt_max=100.0,
                                   v_max=1000.0, v_demarrage=300.0)),
        'longueur_imposee_hors_plage': _entree(24, longueur_chaine_forcee=23),
        'longueur_imposee_invalide': _entree(24, longueur_chaine_forcee=0),
        'aucun_module': _entree(groupes=()),
        'pans_partages': _entree(
            groupes=(GroupePan('Sud', 8, 180.0, 15.0),
                     GroupePan('Est', 8, 90.0, 15.0),
                     GroupePan('Ouest', 8, 270.0, 15.0)),
            onduleur=_onduleur(n_mppt=1)),
        'partition_non_egale': _entree(23),
        'reste_en_reserve': _entree(23, longueur_chaine_forcee=11),
    }


class LesListesHistoriquesDerivedDesObjets(SimpleTestCase):
    """L'égalité ANCIEN ↔ NOUVEAU, sur toutes les configurations de référence."""

    def test_bloquants_et_alertes_sont_exactement_les_libelles_des_objets(self):
        for nom, entree in _cas().items():
            with self.subTest(cas=nom):
                resultat = concevoir_chaines(entree)
                self.assertEqual(
                    resultat.bloquants,
                    tuple(v.libelle for v in resultat.verdicts
                          if v.statut == STATUT_BLOQUANT))
                self.assertEqual(
                    resultat.alertes,
                    tuple(v.libelle for v in resultat.verdicts
                          if v.statut in STATUTS_ALERTANTS))

    def test_aucun_message_n_echappe_aux_objets(self):
        """Toute phrase publiée vient d'un verdict — pas une de plus, pas une
        de moins."""
        for nom, entree in _cas().items():
            with self.subTest(cas=nom):
                resultat = concevoir_chaines(entree)
                self.assertEqual(
                    len(resultat.verdicts),
                    len(resultat.bloquants) + len(resultat.alertes))

    def test_le_helper_libelles_rend_le_meme_decoupage(self):
        resultat = concevoir_chaines(_cas()['isc_hors_specification'])
        self.assertEqual(libelles(resultat.verdicts, (STATUT_BLOQUANT,)),
                         resultat.bloquants)
        self.assertEqual(libelles(resultat.verdicts, STATUTS_ALERTANTS),
                         resultat.alertes)


class ChaqueVerdictPorteSonIdentite(SimpleTestCase):
    def test_code_nature_statut_source_sont_toujours_renseignes(self):
        for nom, entree in _cas().items():
            with self.subTest(cas=nom):
                for verdict in concevoir_chaines(entree).verdicts:
                    self.assertIn(verdict.code, CODES_ATTENDUS)
                    self.assertIn(verdict.nature, NATURES_CONNUES)
                    self.assertIn(verdict.statut, STATUTS_CONNUS)
                    self.assertTrue(verdict.libelle.strip())
                    self.assertTrue(verdict.source.strip(),
                                    'verdict %s sans source' % verdict.code)

    def test_chaque_code_apparait_une_seule_fois_dans_le_source(self):
        source = SOURCE_CHAINES.read_text(encoding='utf-8')
        for code in CODES_ATTENDUS:
            with self.subTest(code=code):
                occurrences = len(re.findall(r'\b%s\b' % re.escape(code),
                                             source))
                self.assertEqual(
                    occurrences, 1,
                    '%s apparaît %d fois dans chaines.py — un code désigne UN '
                    'contrôle' % (code, occurrences))

    def test_les_configurations_de_reference_couvrent_tous_les_codes(self):
        vus = set()
        for entree in _cas().values():
            vus.update(_codes(concevoir_chaines(entree)))
        self.assertEqual(sorted(vus), sorted(CODES_ATTENDUS))

    def test_la_nature_materielle_designe_la_specification_constructeur(self):
        """Isc cumulé hors fiche = MATÉRIEL ; écrêtage sur l'Imp =
        FONCTIONNEL."""
        isc = _par_code(concevoir_chaines(_cas()['isc_hors_specification']),
                        'CH_ISC_CUMULE_HORS_SPECIFICATION')
        self.assertIsNotNone(isc)
        self.assertEqual(isc.nature, 'materielle')
        self.assertEqual(isc.statut, STATUT_BLOQUANT)
        self.assertGreater(isc.valeur, isc.borne)

        imp = _par_code(concevoir_chaines(_cas()['ecretage_imp']),
                        'CH_IMP_CUMULE_ECRETAGE')
        self.assertIsNotNone(imp)
        self.assertEqual(imp.nature, 'fonctionnelle')
        self.assertEqual(imp.statut, STATUT_ALERTE)
        self.assertGreater(imp.valeur, imp.borne)


class NonVerifiableNEstJamaisUnOk(SimpleTestCase):
    def test_une_borne_absente_rend_non_verifiable_et_pas_ok(self):
        resultat = concevoir_chaines(_cas()['fiche_muette'])
        verdict = _par_code(resultat, 'CH_BORNES_NON_VERIFIABLES')
        self.assertIsNotNone(verdict)
        self.assertEqual(verdict.statut, STATUT_NON_VERIFIABLE)
        self.assertFalse(verdict.est_ok)
        self.assertFalse(verdict.est_bloquant)
        # Aucune borne substituée : la valeur comparée n'existe pas.
        self.assertIsNone(verdict.borne)
        self.assertIsNone(verdict.valeur)

    def test_une_borne_non_verifiable_reste_dans_les_alertes(self):
        """Non-régression : l'aval qui lit ``alertes`` la voit comme avant."""
        resultat = concevoir_chaines(_cas()['fiche_muette'])
        verdict = _par_code(resultat, 'CH_BORNES_NON_VERIFIABLES')
        self.assertIn(verdict.libelle, resultat.alertes)
        self.assertNotIn(verdict.libelle, resultat.bloquants)


class SeulUnBloquantArreteUneConception(SimpleTestCase):
    def test_une_alerte_laisse_enregistrer(self):
        resultat = concevoir_chaines(_cas()['ecretage_imp'])
        self.assertTrue(resultat.alertes)
        possible, codes = enregistrement_possible(resultat.verdicts)
        self.assertTrue(possible)
        self.assertEqual(codes, ())

    def test_un_bloquant_arrete_et_se_nomme(self):
        resultat = concevoir_chaines(_cas()['isc_hors_specification'])
        possible, codes = enregistrement_possible(resultat.verdicts)
        self.assertFalse(possible)
        self.assertIn('CH_ISC_CUMULE_HORS_SPECIFICATION', codes)


class UneAlertePasseeOutreResteRelisible(SimpleTestCase):
    HORODATAGE = datetime.datetime(2026, 9, 21, 10, 30,
                                   tzinfo=datetime.timezone.utc)

    def _alerte(self):
        return _par_code(concevoir_chaines(_cas()['ecretage_imp']),
                         'CH_IMP_CUMULE_ECRETAGE')

    def test_la_trace_porte_auteur_date_et_motif(self):
        trace = passer_outre(self._alerte(), auteur='Meryem',
                             horodatage=self.HORODATAGE,
                             motif='client informé, onduleur déjà en stock')
        self.assertEqual(trace.code, 'CH_IMP_CUMULE_ECRETAGE')
        self.assertEqual(trace.auteur, 'Meryem')
        self.assertEqual(trace.horodatage, self.HORODATAGE)
        self.assertIn('Meryem', trace.texte)
        self.assertIn('2026-09-21', trace.texte)
        self.assertIn('onduleur déjà en stock', trace.texte)

    def test_un_bloquant_ne_se_passe_pas_outre(self):
        bloquant = _par_code(
            concevoir_chaines(_cas()['isc_hors_specification']),
            'CH_ISC_CUMULE_HORS_SPECIFICATION')
        with self.assertRaises(ValueError) as capture:
            passer_outre(bloquant, auteur='Meryem',
                         horodatage=self.HORODATAGE, motif='on assume')
        self.assertIn('CH_ISC_CUMULE_HORS_SPECIFICATION',
                      str(capture.exception))

    def test_le_champ_manquant_est_nomme(self):
        for champs, attendu in (
                ({'auteur': '  ', 'motif': 'ok'}, 'auteur'),
                ({'auteur': 'Meryem', 'motif': ''}, 'motif')):
            with self.subTest(attendu=attendu):
                with self.assertRaises(ValueError) as capture:
                    passer_outre(self._alerte(),
                                 horodatage=self.HORODATAGE, **champs)
                self.assertIn(attendu, str(capture.exception))

    def test_un_horodatage_sans_fuseau_est_refuse(self):
        with self.assertRaises(ValueError) as capture:
            passer_outre(self._alerte(), auteur='Meryem',
                         horodatage=datetime.datetime(2026, 9, 21, 10, 30,
                                                      tzinfo=None),
                         motif='on assume')
        self.assertIn('horodatage', str(capture.exception))
