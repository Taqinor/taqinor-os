# -*- coding: utf-8 -*-
"""CALX248 — UN VERDICT PUBLIABLE UNIQUE, ENTRÉE PAR ENTRÉE SOURCÉE.

LE CONSTAT
----------
``garde_publication`` ne regardait que DEUX choses — les bloquants d'onduleur
et la garde de terre — alors que le résultat portait déjà des omissions de
norme, de câble et de protection. Un dossier dont TOUTES les sections sont
OMISES faute de norme passait donc la garde.

PARITÉ CITÉE
------------
Aurora vend un rapport de validation comme livrable NOMMÉ
(https://aurorasolar.com/design-mode/) ; PV*SOL bloque la simulation sur ses
violations les plus graves
(https://help.valentin-software.com/pvsol/en/pages/inverters/
configuration-check/).

CE QUE CES TESTS ARMENT
-----------------------
Les CINQ sources de refus, une par une (conception, raccordement,
équilibrage, terre, tronçons) — plus un cas ENTIÈREMENT omis mais motivé qui
reste publiable, et la non-régression de la garde existante.

Tests PURS : le calepinage d'essai est un objet nu (ni ``pk``, ni société),
le matériel est résolu par une doublure du sélecteur du stock.
"""
from __future__ import annotations

import unittest
from unittest import mock

from apps.calepinage.services import electrique
from apps.calepinage.services.parametres_cles import SECTION_ELECTRIQUE_SOCIETE, registre
from apps.calepinage.services.electrique import (
    PublicationBloquee, STATUT_MOTIF_OMIS, STATUT_MOTIF_SANS_SOURCE,
    garde_publication, verdict_publiable,
)
from core.electrique.types import (
    NATURE_FONCTIONNELLE, NATURE_MATERIELLE, STATUT_ALERTE, STATUT_BLOQUANT,
    STATUT_NON_VERIFIABLE, STATUT_OK, VerdictElectrique,
)

MODULE = {
    'vmp_v': 41.4, 'voc_v': 49.3, 'isc_a': 18.59, 'imp_a': 17.59,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
ONDULEUR = {
    'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'ac_kw': 10.0, 'phases': 3,
}
MATERIEL = {
    'module': MODULE, 'onduleur': ONDULEUR, 'optimiseur': None,
    'designations': {'module': 'Module d essai',
                     'onduleur': 'Onduleur d essai', 'optimiseur': ''},
    'absents': (),
}
#: Le matériel de l'incident DEV-202608-0016 : la fiche PUBLIE un courant de
#: court-circuit admissible (17 A) plus bas que l'Isc d'UNE chaîne (18,59 A)
#: — configuration HORS SPÉCIFICATION, donc bloquante.
ONDULEUR_HORS_SPEC = dict(
    MATERIEL, onduleur=dict(ONDULEUR, isc_max_mppt_a=17.0))

LAYOUT = {
    'version': 2,
    'pin': {'lat': 33.5731, 'lng': -7.5898},
    'zones': [
        {'id': 'a', 'label': 'PAN-A',
         'geometry': {'count': 12, 'azimuthDeg': 180.0, 'tiltDeg': 15.0}},
    ],
}


class _Calepinage:
    """Un pivot NU : aucune société, aucun ``pk``, donc aucune base."""

    pk = None
    company = None

    def __init__(self, resultat=None, layout=None):
        self.roof_layout = LAYOUT if layout is None else layout
        self.resultat = resultat


def _avec_materiel(materiel=None):
    """Le matériel résolu SANS catalogue — la doublure du sélecteur."""
    return mock.patch.object(electrique, 'resoudre_materiel',
                             return_value=materiel or MATERIEL)


def _verdict(calepinage=None, **patches):
    with _avec_materiel(patches.pop('materiel', None)):
        with mock.patch.multiple(electrique, **patches) if patches \
                else _rien():
            return verdict_publiable(calepinage or _Calepinage())


class _rien:
    """Un gestionnaire de contexte neutre — évite un ``if`` dans le test."""

    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


def _codes(rapport):
    return {motif['code'] for motif in rapport['motifs']}


def _par_code(rapport, code):
    return next(motif for motif in rapport['motifs']
                if motif['code'] == code)


class FormeDuRapportTest(unittest.TestCase):
    """Deux clés, et quatre champs par motif — jamais plus."""

    def test_les_deux_cles_sont_toujours_presentes(self):
        rapport = _verdict()
        # ACAL934 y a ajouté ``etat`` et ``points`` (titre/phrase : ACAL612, à la vue).
        self.assertEqual(sorted(rapport), ['etat', 'motifs', 'points', 'publiable'])
        self.assertIsInstance(rapport['publiable'], bool)

    def test_chaque_motif_porte_les_quatre_champs(self):
        for motif in _verdict()['motifs']:
            self.assertEqual(sorted(motif),
                             ['code', 'libelle', 'source', 'statut'])


class CinqSourcesDeRefusTest(unittest.TestCase):
    """Les cinq sources de refus, une par une."""

    def test_1_un_bloquant_de_conception_refuse(self):
        # Incident DEV-202608-0016 : l'Isc cumulé dépasse le courant de
        # court-circuit admissible PUBLIÉ par la fiche — une seule chaîne
        # sort déjà de la borne. La conception prononce un BLOQUANT
        # (CALX215) et il refuse la publication.
        rapport = _verdict(materiel=ONDULEUR_HORS_SPEC)
        self.assertFalse(rapport['publiable'])
        self.assertTrue(any(motif['statut'] == STATUT_BLOQUANT
                            for motif in rapport['motifs']),
                        rapport['motifs'])

    def test_2_le_raccordement_entre_dans_le_rapport(self):
        # Les trois contrôles de CALX242 sont TOUJOURS prononcés (omis et
        # motivés tant que rien n'est saisi) : ils entrent donc au rapport.
        rapport = _verdict(_Calepinage(resultat={'entree_electrique': {}}))
        self.assertLessEqual(
            {'puissance_souscrite', 'regime_phases', 'tension_nominale'},
            _codes(rapport), sorted(_codes(rapport)))

    def test_2bis_un_cos_phi_sans_source_est_un_motif_sans_source(self):
        from apps.calepinage.services.raccordement import RaccordementInvalide

        with mock.patch(
                'apps.calepinage.services.raccordement.verdicts_raccordement',
                side_effect=RaccordementInvalide(
                    'source_cos_phi : un cos φ imposé sans source est refusé',
                    champ='source_cos_phi')):
            motifs = electrique._motifs_du_raccordement(None, {}, {})
        self.assertEqual([motif['statut'] for motif in motifs],
                         [STATUT_MOTIF_SANS_SOURCE])
        self.assertEqual(motifs[0]['code'], 'RACCORDEMENT_REFUSE')

    def test_3_l_equilibrage_omis_ne_refuse_pas(self):
        # CALX243 sans seuil réglé rend un verdict NON VÉRIFIABLE motivé :
        # c'est une omission ASSUMÉE, elle ne refuse pas la publication.
        motifs = electrique._motifs_du_raccordement(
            _conception(), {'phases': 3}, {})
        desequilibre = [motif for motif in motifs
                        if motif['code'] == 'desequilibre_phases']
        self.assertTrue(desequilibre)
        self.assertEqual(desequilibre[0]['statut'], STATUT_NON_VERIFIABLE)

    def test_4_la_terre_non_justifiee_refuse(self):
        motifs = electrique._motifs_de_la_terre({
            'justification_requise': True, 'justification_fournie': False,
            'omissions': []})
        self.assertEqual([motif['statut'] for motif in motifs],
                         [STATUT_BLOQUANT])
        self.assertEqual(motifs[0]['code'], 'TERRE_JUSTIFICATION_MANQUANTE')
        self.assertIn('NF C 15-100', motifs[0]['source'])

    def test_4bis_la_terre_omise_ne_refuse_pas(self):
        motifs = electrique._motifs_de_la_terre({
            'justification_requise': False, 'justification_fournie': False,
            'omissions': ['aucune norme électrique sélectionnée']})
        self.assertEqual([motif['statut'] for motif in motifs],
                         [STATUT_MOTIF_OMIS])

    def test_5_un_cumul_de_chute_bloquant_refuse(self):
        motifs = electrique._motifs_des_troncons({
            'omissions': [],
            'verdicts': [{'code': 'chute_cumulee_dc', 'conforme': False,
                          'bloquant': True,
                          'libelle': 'Chute de tension cumulée DC',
                          'detail': 'chute cumulée de 4,20 % au-dessus du '
                                    'maximum de 3,0 %',
                          'source': 'norme'}]})
        self.assertEqual([motif['statut'] for motif in motifs],
                         [STATUT_BLOQUANT])

    def test_5bis_un_troncon_non_calculable_ne_refuse_pas(self):
        motifs = electrique._motifs_des_troncons({
            'omissions': [{'troncon': 'ch5', 'champ': 'section_mm2',
                           'motif': "aucune norme n'est choisie"}],
            'verdicts': []})
        self.assertEqual([motif['statut'] for motif in motifs],
                         [STATUT_MOTIF_OMIS])
        self.assertIn('ch5', motifs[0]['libelle'])
        # R3-19 : le champ s'écrit par son intitulé, jamais sa clé technique.
        self.assertIn('section du câble', motifs[0]['libelle'])
        self.assertNotIn('section_mm2', motifs[0]['libelle'])
        vide = electrique._motifs_des_troncons({'omissions': [{
            'troncon': None, 'champ': 'electrical.cheminements',
            'motif': "aucun cheminement n'est tracé"}], 'verdicts': []})
        self.assertNotIn('electrical.', vide[0]['libelle'])
        self.assertNotIn('« — »', vide[0]['libelle'])


class OmisMaisMotiveResteePubliableTest(unittest.TestCase):
    """Le cas du plan : TOUT omis, mais chaque omission est motivée."""

    def test_sans_norme_le_dossier_reste_publiable(self):
        rapport = _verdict()
        norme = _par_code(rapport, 'NORME_NON_APPLICABLE')
        self.assertEqual(norme['statut'], STATUT_MOTIF_OMIS)
        self.assertTrue(norme['libelle'])
        self.assertTrue(rapport['publiable'],
                        [motif for motif in rapport['motifs']
                         if motif['statut'] in (STATUT_BLOQUANT,
                                                STATUT_MOTIF_SANS_SOURCE)])

    def test_aucun_motif_n_est_muet(self):
        for motif in _verdict()['motifs']:
            self.assertTrue(motif['libelle'].strip(), motif)


class AucunCheminDeCodeAffichéTest(unittest.TestCase):
    """ACAL879 — un texte affiché ne montre ni ``::``, ni ``[]``, ni ``.py``."""

    ECHANTILLONS = ('calepinage_resultat', 'calepinage_publication_electrique',
                    'calepinage_raccordement')
    CLES_AFFICHEES = ('source', 'motif', 'libelle')
    MOTIFS_DE_CODE = ('::', '[]', '.py')

    def _textes_affiches(self, noeud):
        if isinstance(noeud, dict):
            for cle, valeur in noeud.items():
                if cle in self.CLES_AFFICHEES and isinstance(valeur, str):
                    yield valeur
                yield from self._textes_affiches(valeur)
        elif isinstance(noeud, list):
            for element in noeud:
                yield from self._textes_affiches(element)

    def _fautifs(self, textes):
        return [t for t in textes
                if any(m in t for m in self.MOTIFS_DE_CODE)]

    def test_les_echantillons_servis_n_affichent_aucun_chemin(self):
        import json
        from pathlib import Path

        dossier = Path(electrique.__file__).resolve().parents[1] \
            / 'contract_samples'
        for nom in self.ECHANTILLONS:
            donnees = json.loads(
                (dossier / f'{nom}.json').read_text(encoding='utf-8'))
            self.assertEqual(self._fautifs(self._textes_affiches(donnees)),
                             [], nom)

    def test_le_motif_de_norme_n_affiche_aucun_chemin(self):
        motif = _par_code(_verdict(), 'NORME_NON_APPLICABLE')
        self.assertEqual(self._fautifs([motif['source'], motif['libelle']]),
                         [])
        self.assertEqual(motif['source'],
                         'norme électrique choisie pour le pays')

    def test_le_motif_de_troncon_n_affiche_aucun_chemin(self):
        from apps.calepinage.services import troncons

        texte = troncons._motif_norme_absente({'motif': 'aucune norme'})
        self.assertEqual(self._fautifs([texte]), [])


class ProvenanceTest(unittest.TestCase):
    """Un statut CONCLUSIF sans source devient ``sans_source``."""

    def test_une_valeur_qui_juge_sans_source_refuse(self):
        motif = electrique._motif_du_verdict(VerdictElectrique(
            code='CH_TEST', nature=NATURE_MATERIELLE, statut=STATUT_ALERTE,
            libelle='une alerte sans provenance', borne=1.0, valeur=2.0,
            source=''))
        self.assertEqual(motif['statut'], STATUT_MOTIF_SANS_SOURCE)

    def test_une_abstention_sans_source_ne_refuse_pas(self):
        motif = electrique._motif_du_verdict(VerdictElectrique(
            code='CH_TEST', nature=NATURE_FONCTIONNELLE,
            statut=STATUT_NON_VERIFIABLE,
            libelle='le seuil n est pas réglé', valeur=12.0, source=''))
        self.assertEqual(motif['statut'], STATUT_NON_VERIFIABLE)

    def test_un_verdict_conclusif_sourcé_garde_son_statut(self):
        motif = electrique._motif_du_verdict(VerdictElectrique(
            code='CH_TEST', nature=NATURE_MATERIELLE, statut=STATUT_ALERTE,
            libelle='une alerte sourcée', borne=1.0, valeur=2.0,
            source='fiche constructeur onduleur'))
        self.assertEqual(motif['statut'], STATUT_ALERTE)

    def test_un_verdict_ok_n_est_pas_un_motif(self):
        class _Resultat:
            verdicts = (VerdictElectrique(
                code='CH_OK', nature=NATURE_MATERIELLE, statut=STATUT_OK,
                libelle='tout va bien', source='fiche'),)

        class _Conception:
            resultat = _Resultat()

        self.assertEqual(electrique._motifs_de_la_conception(_Conception()),
                         [])


class NonRegressionDeLaGardeTest(unittest.TestCase):
    """ACAL170 — la garde LIT ce rapport : bloquant refusé, indéterminé
    passé (D-ACAL-9)."""

    def test_la_garde_laisse_passer_ce_qu_elle_laissait_passer(self):
        calepinage = _Calepinage()
        with _avec_materiel():
            garde = garde_publication(calepinage)
        self.assertNotEqual(garde['verdict'], 'bloquant')
        self.assertEqual(garde['bloquants'], [])
        self.assertIsNone(garde['derogation'])

    def test_la_garde_refuse_toujours_un_bloquant_d_onduleur(self):
        with _avec_materiel(ONDULEUR_HORS_SPEC):
            with self.assertRaises(PublicationBloquee):
                garde_publication(_Calepinage())

    def test_une_fiche_incomplete_est_indeterminee_sans_bloquer(self):
        vide = {'module': {}, 'onduleur': {}, 'optimiseur': None,
                'designations': {'module': '', 'onduleur': '',
                                 'optimiseur': ''},
                'absents': ('module PV non désigné',)}
        with _avec_materiel(vide):
            garde = garde_publication(_Calepinage())
        self.assertEqual(garde['verdict'], 'indetermine')
        self.assertIn('module PV non désigné', garde['manquantes'])

    def test_les_bloquants_de_la_garde_sont_ceux_du_rapport(self):
        # ACAL170 — la lecture des bloquants vit UNE fois : les codes
        # refusés par la garde sont les motifs ``bloquant`` du rapport.
        with _avec_materiel(ONDULEUR_HORS_SPEC):
            rapport = verdict_publiable(_Calepinage())
            with self.assertRaises(PublicationBloquee) as refus:
                garde_publication(_Calepinage())
        attendus = [motif['code'] for motif in rapport['motifs']
                    if motif['statut'] == STATUT_BLOQUANT]
        self.assertTrue(attendus)
        self.assertEqual([b['code'] for b in refus.exception.bloquants],
                         attendus)


def _conception():
    from apps.calepinage.services.chaines import concevoir_par_pan
    from apps.calepinage.services.electrique import temperatures_site

    return concevoir_par_pan(
        LAYOUT, module_specs=MODULE, onduleur_specs=ONDULEUR,
        temperatures=temperatures_site(
            saisie={'temperature_min_c': -5.0, 'temperature_max_c': 70.0}),
        module_designation='Module d essai',
        onduleur_designation='Onduleur d essai')


class SynthesePublicationTest(unittest.TestCase):
    """ACAL612 — ``titre`` / ``phrase`` composés de ``etat`` et ``points``."""

    @staticmethod
    def _publication(etat, points, statut, n_motifs):
        motifs = [{'code': 'X', 'statut': statut, 'source': 's',
                   'libelle': 'motif %d' % i} for i in range(n_motifs)]
        return {'publiable': etat != 'bloquant', 'motifs': motifs,
                'etat': etat, 'points': points}

    def _synthese(self, *args):
        from apps.calepinage.services.synthese_publication import (
            synthese_de_publication,
        )
        return synthese_de_publication(self._publication(*args))

    def test_a_completer_dit_le_nombre_de_points(self):
        # Le mutant ``len(motifs)`` (3 ici) au lieu de ``points`` échoue.
        servie = self._synthese('a_completer', 11, STATUT_NON_VERIFIABLE, 3)
        self.assertEqual(servie['titre'], 'À compléter : 11 points')
        self.assertEqual(
            servie['phrase'], 'Aucun motif bloquant ; 11 points restent à '
                              'compléter : motif 0 ; motif 1…')

    def test_acal1937_le_titre_dit_le_compte_du_rail(self):
        """Le rail dit 3 points à régler : le Verdict dit 3, pas les 11 motifs."""
        from unittest import mock
        from apps.calepinage.services.synthese_publication import (
            synthese_de_publication,
        )
        from apps.calepinage.views import electrique as vue
        publication = self._publication('a_completer', 11, STATUT_NON_VERIFIABLE, 3)
        lu = {'nombre_a_regler': 2, 'nombre_bloquants': 1}
        with mock.patch('apps.calepinage.services.pret_a_envoyer.agreger', return_value=lu):
            rail = vue._points_du_rail(object(), publication)
        self.assertEqual(rail, 3)
        servie = synthese_de_publication(publication, rail)
        self.assertEqual(servie['titre'], 'À compléter : 3 points')
        self.assertIn('3 points restent', servie['phrase'])
        # Un seul nombre : la clé `points` servie est celle du rail, pas celle des motifs.
        self.assertEqual(servie['points'], 3)
        # Sans compte du rail, le compte des motifs reste servi tel quel.
        self.assertEqual(synthese_de_publication(publication)['titre'],
                         'À compléter : 11 points')
        # Dossier non « à compléter » : rien à compter.
        pret = self._publication('pret', 0, STATUT_OK, 0)
        self.assertIsNone(vue._points_du_rail(object(), pret))

    def test_singulier(self):
        servie = self._synthese('a_completer', 1, STATUT_MOTIF_OMIS, 1)
        self.assertEqual(servie['titre'], 'À compléter : 1 point')

    def test_bloquant_et_pret(self):
        self.assertEqual(
            self._synthese('bloquant', 2, STATUT_BLOQUANT, 2)['titre'],
            'Bloquant : 2')
        self.assertEqual(self._synthese('pret', 0, STATUT_OK, 0)['titre'],
                         'Prêt')

    def test_publication_nulle_et_cles_d_origine_intactes(self):
        from apps.calepinage.services.synthese_publication import (
            synthese_de_publication,
        )
        self.assertIsNone(synthese_de_publication(None))
        avant = self._publication('a_completer', 11, STATUT_NON_VERIFIABLE, 3)
        servie = synthese_de_publication(avant)
        for cle in ('publiable', 'motifs', 'etat', 'points'):
            self.assertEqual(servie[cle], avant[cle])

    def test_un_dossier_sans_materiel_ni_norme_reste_publiable(self):
        from apps.calepinage.services.synthese_publication import (
            synthese_de_publication,
        )
        absent = dict(MATERIEL, module=None, onduleur=None,
                      absents=('module', 'onduleur'))
        servie = synthese_de_publication(_verdict(materiel=absent))
        self.assertTrue(servie['publiable'])
        self.assertEqual(servie['etat'], 'a_completer')
        self.assertIn('%d point' % servie['points'], servie['titre'])


class DeclassementThermiqueTest(unittest.TestCase):
    """ACAL664 — Pnom à la T2m maximale du TMY, d'après la fiche."""

    REDUITE = dict(MATERIEL, onduleur=dict(
        ONDULEUR, pnom_reduite_debut_c=45.0, pnom_pente_pct_c=2.0))

    @staticmethod
    def _tmy(maxi):
        return lambda lat, lon: {'temperature_min_c': -2.0, 'temperature_max_c': maxi}

    def _motif(self, materiel, fournisseur):
        with mock.patch.object(electrique, '_FOURNISSEUR', fournisseur):
            return _par_code(_verdict(materiel=materiel), 'DECLASSEMENT_THERMIQUE')

    def test_cinquante_degres_rendent_quatre_vingt_dix_pour_cent(self):
        # Le mutant « pente dès 0 °C » rendrait 0 kW, pas 9,0 kW.
        motif = self._motif(self.REDUITE, self._tmy(50.0))
        self.assertEqual(motif['statut'], STATUT_OK)
        self.assertEqual(motif['libelle'], "Puissance AC à 50 °C : 9,0 kW "
                         "(90 % de la nominale, d'après la fiche)")
        self.assertEqual(motif['source'], "fiche technique de l'onduleur")

    def test_sous_le_debut_pleine_puissance(self):
        self.assertIn('(100 %', self._motif(self.REDUITE, self._tmy(40.0))['libelle'])

    def test_fiche_muette_non_verifiable(self):
        motif = self._motif(MATERIEL, self._tmy(50.0))
        self.assertEqual(motif['statut'], STATUT_NON_VERIFIABLE)
        self.assertIn('déclassement thermique non modélisé', motif['libelle'])

    def test_air_non_connu_sans_tmy(self):
        motif = self._motif(self.REDUITE, None)
        self.assertEqual(motif['libelle'], "température d'air non connue")

    def test_la_fonction_du_noyau(self):
        from core.electrique.onduleurs import puissance_a_temperature

        self.assertAlmostEqual(puissance_a_temperature(10.0, 45.0, 2.0, 50.0), 9.0)
        self.assertIsNone(puissance_a_temperature(10.0, None, 2.0, 50.0))


def _pan(cle, azimut, acces):
    return {'id': cle, 'label': 'PAN-%s' % cle.upper(),
            'geometry': {'count': len(acces), 'azimuthDeg': azimut, 'tiltDeg': 15.0,
                         'solarAccess': {'values': acces}}}


#: Trois orientations ; le pan Sud a un module à 0,60 pour cinq à 0,95 (écart 0,35).
LAYOUT_TROIS_ORIENTATIONS = dict(LAYOUT, zones=[
    _pan('a', 180.0, [0.95] * 5 + [0.60]), _pan('b', 90.0, [0.9] * 6),
    _pan('c', 270.0, [0.9] * 6)])
#: Des seuils d'ESSAI (valeur + source), jamais une valeur proposée.
SEUILS_SAISIS = {'seuil_orientations_micro': {'valeur': 3, 'source': 'societe'},
                 'seuil_ecart_acces_optimiseur': {'valeur': 0.2, 'source': 'societe'}}


class ArchitectureOnduleurTest(unittest.TestCase):
    """ACAL671 — onduleur de chaîne, micro-onduleurs ou optimiseurs, seuils société."""

    def _motif(self, layout, reglages):
        rapport = _verdict(_Calepinage(layout=layout),
                           _reglages_electrique_societe=lambda *a, **k: reglages)
        self.assertNotEqual(_par_code(rapport, 'ARCHITECTURE_ONDULEUR')['statut'], STATUT_BLOQUANT)
        return _par_code(rapport, 'ARCHITECTURE_ONDULEUR')

    def test_trois_orientations_et_trente_cinq_pour_cent(self):
        motif = self._motif(LAYOUT_TROIS_ORIENTATIONS, SEUILS_SAISIS)
        self.assertEqual(motif['statut'], STATUT_OK)
        self.assertEqual(motif['libelle'], "3 orientations et un écart d'accès solaire de 35 % "
                         'dans une chaîne : micro-onduleurs ou optimiseurs à étudier')
        self.assertEqual(motif['source'], 'societe')

    def test_seuils_vides_aucun_verdict(self):
        # Mutant « verdict rendu sans seuils » : statut ok ⇒ échec.
        motif = self._motif(LAYOUT_TROIS_ORIENTATIONS, {})
        self.assertEqual(motif['statut'], STATUT_NON_VERIFIABLE)
        self.assertEqual(motif['libelle'], 'réglages non saisis : ' + ' ; '.join(
            registre(SECTION_ELECTRIQUE_SOCIETE)[cle][0]
            for cle in ('seuil_orientations_micro', 'seuil_ecart_acces_optimiseur')))

    def test_seuil_sans_source_reste_non_saisi(self):
        reglages = dict(SEUILS_SAISIS, seuil_orientations_micro={'valeur': 3, 'source': ''})
        self.assertEqual(self._motif(LAYOUT_TROIS_ORIENTATIONS, reglages)['libelle'],
                         'réglages non saisis : ' + registre(SECTION_ELECTRIQUE_SOCIETE)['seuil_orientations_micro'][0])

    def test_acces_solaire_non_mesure(self):
        motif = self._motif(LAYOUT, SEUILS_SAISIS)
        self.assertEqual((motif['statut'], motif['libelle']),
                         (STATUT_NON_VERIFIABLE, 'accès solaire non mesuré'))

    def test_sous_les_seuils_onduleur_de_chaine(self):
        reglages = {'seuil_orientations_micro': {'valeur': 4, 'source': 'societe'},
                    'seuil_ecart_acces_optimiseur': {'valeur': 0.5, 'source': 'societe'}}
        self.assertTrue(self._motif(LAYOUT_TROIS_ORIENTATIONS, reglages)['libelle']
                        .endswith(': onduleur de chaîne'))

    def test_deux_types_au_registre(self):
        from apps.calepinage.services.parametres_cles import (
            SECTION_ELECTRIQUE_SOCIETE, TYPES_CLES, registre,
        )

        types = TYPES_CLES[SECTION_ELECTRIQUE_SOCIETE]
        self.assertEqual(types['seuil_orientations_micro'], {'type': 'entier', 'minimum': 1})
        self.assertEqual(types['seuil_ecart_acces_optimiseur'],
                         {'type': 'nombre', 'minimum': 0, 'maximum': 1})
        self.assertIn('seuil_orientations_micro', registre(SECTION_ELECTRIQUE_SOCIETE))


class CodesDesMotifsOntUnIntituleTest(unittest.TestCase):
    """R3-09 — l'écran « Verdict électrique » traduit chaque code de motif en
    intitulé de métier (table JSON lue par l'écran). Un code que le serveur
    prononce sans entrée dans cette table fait rougir ici, pas à l'écran."""

    #: Les seuls codes écrits en littéral dans les services (ni constante, ni
    #: sortie d'une fonction pure testable sans base) : à tenir à la main.
    LITTERAUX = ('RACCORDEMENT_REFUSE', 'CHUTE_CUMULEE')

    @staticmethod
    def _table():
        import json
        from pathlib import Path

        fichier = (Path(__file__).resolve().parents[5] / 'frontend' / 'src'
                   / 'features' / 'calepinage' / 'electrique'
                   / 'libellesCodesVerdict.json')
        return json.loads(fichier.read_text(encoding='utf-8'))

    @staticmethod
    def _codes_prononces():
        from apps.calepinage.services import (
            architecture_onduleur, declassement_onduleur, raccordement,
            troncons,
        )
        from apps.calepinage.tests.test_calx215_natures_verdicts import (
            CODES_ATTENDUS,
        )

        codes = set(CODES_ATTENDUS)
        codes.update((
            electrique.CODE_FICHE_INCOMPLETE, electrique.CODE_AFFECTATION,
            electrique.CODE_POLYSTRING, electrique.CODE_MICRO_ONDULEURS,
            electrique.CODE_REGIME_NON_PRECISE,
            architecture_onduleur.CODE_ARCHITECTURE_ONDULEUR,
            declassement_onduleur.CODE_DECLASSEMENT_THERMIQUE,
            raccordement.CODE_ELEVATION, raccordement.CODE_PUISSANCE_SOUSCRITE,
            raccordement.CODE_REGIME_PHASES, raccordement.CODE_TENSION_NOMINALE,
            raccordement.CODE_DESEQUILIBRE,
            raccordement.CODE_LIMITATION_INJECTION))
        codes.update(troncons.CODE_VERDICT.values())
        # Les sorties de fonctions pures : le code vient du serveur, pas d'ici.
        codes.update(m['code'] for m in electrique._motifs_de_la_norme({}))
        codes.update(m['code'] for m in electrique._motifs_des_troncons(
            {'omissions': [{}]}))
        codes.update(m['code'] for m in electrique._motifs_de_la_terre(
            {'omissions': ['x'], 'justification_requise': True}))
        return codes

    def test_chaque_code_prononce_a_un_intitule(self):
        table = self._table()
        manquants = sorted(
            (self._codes_prononces() | set(self.LITTERAUX)) - set(table))
        self.assertEqual(
            manquants, [], 'codes prononcés par le serveur sans intitulé dans '
            'libellesCodesVerdict.json : %s' % manquants)

    def test_les_codes_de_fonctions_pures_sont_bien_vus(self):
        codes = self._codes_prononces()
        for attendu in ('NORME_NON_APPLICABLE', 'TRONCON_NON_CALCULABLE',
                        'TERRE_OMISE', 'TERRE_JUSTIFICATION_MANQUANTE'):
            self.assertIn(attendu, codes)

    def test_aucun_intitule_n_est_le_code_ni_vide(self):
        for code, intitule in self._table().items():
            self.assertNotEqual(intitule.strip(), code, code)
            self.assertIn(' ', intitule.strip(), code)


if __name__ == '__main__':      # pragma: no cover
    unittest.main()
