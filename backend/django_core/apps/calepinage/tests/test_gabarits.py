"""CAL82 — gabarits de disposition : enregistrés, réappliqués, sans géométrie.

Ce qui est prouvé ici :

* **appliquer un gabarit sur une zone vierge reproduit EXACTEMENT les réglages
  source** — l'aller-retour zone → gabarit → zone est vérifié clé par clé ;
* **un gabarit ne transporte JAMAIS une géométrie de toit** : une clé de
  géométrie (contour, obstacles, panneaux posés…) est REFUSÉE en la nommant,
  et appliquer un gabarit ne touche ni le contour ni les obstacles de la zone
  qui le reçoit ;
* l'axe des rangées n'est PAS un réglage de gabarit (il est dérivé du kit —
  un gabarit qui l'imposerait pourrait décrire une pose inconstructible) ;
* la section refuse ce qu'elle ne sait pas ranger, en nommant le champ ;
* le gabarit publié par le contrat CAL45 traverse la validation tel quel ;
* ÉQUIVALENCE : une société sans gabarit garde une section vide.

Aucune base de données : ``SimpleTestCase``.

Run :
    python manage.py test apps.calepinage.tests.test_gabarits -v2
"""
import io
import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services.gabarits import (
    CLES_DE_ZONE, SECTION, appliquer_gabarit, gabarit_depuis_zone,
    normaliser_section_gabarits_disposition, reglages_admis,
)
from apps.calepinage.services.parametres import ReglageInvalide

#: Une zone RÉGLÉE : ses règles de pose, et sa géométrie (qui ne doit jamais
#: entrer dans un gabarit).
ZONE_SOURCE = {
    'id': 'z1',
    'roofType': 'pitched',
    'pitchDeg': 15.0,
    'facingAzimuthDeg': 180.0,
    'facingManual': True,
    'neededAuto': False,
    'vertices': [[-7.6, 33.5], [-7.5999, 33.5], [-7.5999, 33.5001]],
    'obstacles': [{'id': 'obs-1', 'centerLng': -7.6, 'centerLat': 33.5,
                   'lengthM': 1.0, 'widthM': 1.0}],
}

#: Les réglages qui ne vivent pas dans le document (ils alimentent CAL78).
REGLAGES_MOTEUR = {
    'orientation': 'portrait',
    'famille': 'south',
    'rives': {'laterale_m': 0.35, 'extremite_m': 0.35},
    'allee_m': 0.60,
    'priorite': 2,
}


class UnGabaritReproduitExactementSesReglages(SimpleTestCase):

    def setUp(self):
        self.gabarit = gabarit_depuis_zone(
            ZONE_SOURCE, reglages=REGLAGES_MOTEUR, libelle='Pan sud type')

    def test_les_reglages_de_zone_sont_repris_a_l_identique(self):
        vierge, _regles = appliquer_gabarit(self.gabarit, {'id': 'z9'})
        for cle in CLES_DE_ZONE:
            self.assertEqual(vierge[cle], ZONE_SOURCE[cle], cle)

    def test_les_reglages_moteur_sont_repris_a_l_identique(self):
        _vierge, regles = appliquer_gabarit(self.gabarit, {'id': 'z9'})
        self.assertEqual(regles, REGLAGES_MOTEUR)

    def test_l_aller_retour_est_stable(self):
        """Ré-enregistrer la zone réglée doit redonner le MÊME gabarit."""
        vierge, regles = appliquer_gabarit(self.gabarit, {'id': 'z9'})
        self.assertEqual(
            gabarit_depuis_zone(vierge, reglages=regles,
                                libelle='Pan sud type'),
            self.gabarit)

    def test_une_zone_neuve_ne_porte_que_les_reglages(self):
        vierge, _regles = appliquer_gabarit(self.gabarit)
        self.assertEqual(set(vierge), set(CLES_DE_ZONE))

    def test_un_gabarit_partiel_n_efface_rien(self):
        partiel = {'pitchDeg': 22.0}
        zone, _regles = appliquer_gabarit(partiel, dict(ZONE_SOURCE))
        self.assertEqual(zone['pitchDeg'], 22.0)
        self.assertEqual(zone['roofType'], ZONE_SOURCE['roofType'])
        self.assertEqual(zone['facingAzimuthDeg'],
                         ZONE_SOURCE['facingAzimuthDeg'])

    def test_un_reglage_absent_de_la_zone_reste_absent_du_gabarit(self):
        """Aucun défaut inventé : ce qui n'a pas été réglé ne s'impose pas."""
        gabarit = gabarit_depuis_zone({'id': 'z2', 'roofType': 'flat'})
        self.assertEqual(set(gabarit), {'roofType'})


class UnGabaritNeTransportePasDeGeometrie(SimpleTestCase):

    def test_la_geometrie_de_la_zone_source_n_entre_pas_dans_le_gabarit(self):
        gabarit = gabarit_depuis_zone(ZONE_SOURCE, reglages=REGLAGES_MOTEUR)
        self.assertNotIn('vertices', gabarit)
        self.assertNotIn('obstacles', gabarit)
        self.assertNotIn('id', gabarit)

    def test_une_geometrie_glissee_dans_un_gabarit_est_refusee(self):
        for cle in ('vertices', 'obstacles', 'geometry', 'outline', 'pin'):
            with self.assertRaises(ReglageInvalide) as refus:
                normaliser_section_gabarits_disposition(
                    {'g1': {'roofType': 'flat', cle: [[0, 0]]}})
            self.assertEqual(refus.exception.champ, f'{SECTION}.g1.{cle}')
            self.assertIn('géométrie', str(refus.exception))

    def test_appliquer_un_gabarit_ne_touche_pas_le_contour(self):
        gabarit = gabarit_depuis_zone(ZONE_SOURCE, reglages=REGLAGES_MOTEUR)
        autre = {'id': 'z9',
                 'vertices': [[0, 0], [1, 0], [1, 1]],
                 'obstacles': [{'id': 'x'}]}
        regle, _regles = appliquer_gabarit(gabarit, autre)
        self.assertEqual(regle['vertices'], autre['vertices'])
        self.assertEqual(regle['obstacles'], autre['obstacles'])

    def test_la_zone_source_n_est_pas_mutee(self):
        avant = json.dumps(ZONE_SOURCE, sort_keys=True)
        gabarit = gabarit_depuis_zone(ZONE_SOURCE, reglages=REGLAGES_MOTEUR)
        appliquer_gabarit(gabarit, ZONE_SOURCE)
        self.assertEqual(json.dumps(ZONE_SOURCE, sort_keys=True), avant)


class LAxeDesRangeesNEstPasUnReglage(SimpleTestCase):
    """Il est DÉRIVÉ du kit — un gabarit ne peut pas imposer l'inconstructible."""

    def test_axe_rangee_n_est_pas_un_reglage_admis(self):
        self.assertNotIn('axe_rangee', reglages_admis())

    def test_un_gabarit_qui_l_impose_est_refuse(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_gabarits_disposition(
                {'g1': {'axe_rangee': 'NORD_SUD'}})
        self.assertEqual(refus.exception.champ, f'{SECTION}.g1.axe_rangee')


class LaSectionRefuseCeQuElleNeSaitPasRanger(SimpleTestCase):

    def test_la_section_vide_reste_vide(self):
        self.assertEqual(normaliser_section_gabarits_disposition({}), {})
        self.assertEqual(normaliser_section_gabarits_disposition(None), {})

    def test_une_section_qui_n_est_pas_un_objet_est_refusee(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_gabarits_disposition(['g1'])
        self.assertEqual(refus.exception.champ, SECTION)

    def test_une_orientation_inconnue_est_refusee(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_gabarits_disposition(
                {'g1': {'orientation': 'diagonale'}})
        self.assertEqual(refus.exception.champ, f'{SECTION}.g1.orientation')

    def test_un_type_de_toiture_inconnu_est_refuse(self):
        with self.assertRaises(ReglageInvalide):
            normaliser_section_gabarits_disposition(
                {'g1': {'roofType': 'arrondie'}})

    def test_une_rive_inconnue_est_refusee(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_gabarits_disposition(
                {'g1': {'rives': {'diagonale_m': 0.3}}})
        self.assertEqual(refus.exception.champ,
                         f'{SECTION}.g1.rives.diagonale_m')

    def test_une_rive_negative_est_refusee(self):
        with self.assertRaises(ReglageInvalide):
            normaliser_section_gabarits_disposition(
                {'g1': {'rives': {'laterale_m': -0.1}}})

    def test_un_azimut_hors_cap_est_refuse(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_gabarits_disposition(
                {'g1': {'facingAzimuthDeg': 400}})
        self.assertIn('0 et 360', str(refus.exception))

    def test_une_pente_de_90_degres_est_refusee(self):
        with self.assertRaises(ReglageInvalide):
            normaliser_section_gabarits_disposition({'g1': {'pitchDeg': 90}})

    def test_un_compte_de_rangees_nul_est_refuse(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_gabarits_disposition({'g1': {'rangees': 0}})
        self.assertEqual(refus.exception.champ, f'{SECTION}.g1.rangees')

    def test_un_oui_non_qui_n_en_est_pas_un_est_refuse(self):
        with self.assertRaises(ReglageInvalide):
            normaliser_section_gabarits_disposition(
                {'g1': {'facingManual': 'oui'}})


class LeGabaritPublieParLeContratTraverse(SimpleTestCase):
    """PACT10 : l'échantillon publié ne peut pas être refusé par son serveur."""

    def test_l_exemple_du_contrat_est_valide(self):
        chemin = (pathlib.Path(__file__).resolve().parents[1]
                  / 'contract_samples' / 'parametres_calepinage.json')
        with io.open(chemin, encoding='utf-8') as fichier:
            contrat = json.load(fichier)
        publiee = contrat['exemple'][SECTION]
        self.assertTrue(publiee, 'le contrat ne décrit plus la section')
        self.assertEqual(normaliser_section_gabarits_disposition(publiee),
                         publiee)


class LaSectionEstBranchee(SimpleTestCase):

    def test_le_normaliseur_est_enregistre(self):
        from apps.calepinage.services.parametres import _normaliseurs

        self.assertIn(SECTION, _normaliseurs())

    def test_la_section_est_une_section_admise(self):
        from apps.calepinage.selectors import SECTIONS_PARAMETRES

        self.assertIn(SECTION, SECTIONS_PARAMETRES)
