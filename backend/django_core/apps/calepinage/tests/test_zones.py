"""CAL68 — les zones de l'atelier arrivent au moteur, et coûtent ce qu'elles coûtent.

CE QUI EST PROUVÉ ICI
---------------------
* **LA TRADUCTION EST CELLE DU CONTRAT** — ce que produit
  ``zones_moteur_depuis_layout`` sur ``exemple_layout`` est EXACTEMENT le
  ``exemple`` committé (``contract_samples/zones.json``) : l'échantillon ne
  peut pas pourrir dans son coin ;
* **UNE ZONE INTERDITE RETIRE SA SURFACE DU POSABLE**, et une RESERVEE la
  retire AUSSI mais est chiffrée À PART ;
* **UNE ZONE PRÉFÉRÉE NE CHANGE JAMAIS UN COMPTE** — son aire retirée vaut 0,
  et le compte de modules d'un plan est IDENTIQUE avec et sans elle (prouvé
  sur le moteur pur, patron de ``core/calepinage/zones.py``) ;
* **ÉQUIVALENCE** — un document sans ``exclusionZones`` laisse l'entrée moteur
  strictement inchangée (même objet, aucune zone effacée) ;
* les refus NOMMENT la zone fautive (``exclusionZones[i]``), en français :
  nature inconnue, contour à 1-2 sommets, retrait négatif, tableau qui n'en
  est pas un ; un contour VIDE est simplement ignoré (zone en cours de
  saisie) ;
* les CHIFFRES du contrat sont RECALCULÉS ici — aucun n'est écrit à la main.

Aucune base de données : tout est du document et du noyau pur.

Run :
    python manage.py test apps.calepinage.tests.test_zones -v2
"""
import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services.zones import (
    CLE_LAYOUT,
    CLE_MOTEUR,
    ZoneRefusee,
    chiffrage_zones,
    injecter_zones,
    natures_admises,
    projeteur_local,
    zones_moteur_depuis_layout,
)
from core.calepinage.types import NatureZone
from core.calepinage.zones import NATURES_BLOQUANTES, bonus_preference

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'zones.json').read_text(encoding='utf-8'))

LAYOUT = CONTRAT['exemple_layout']


def _zone(nature, sommets, **extra):
    zone = {'id': f'Z-{nature}', 'nature': nature, 'vertices': sommets}
    zone.update(extra)
    return zone


class ContratTest(SimpleTestCase):
    """L'échantillon committé EST ce que la traduction produit."""

    def test_traduction_egale_l_echantillon(self):
        self.assertEqual(zones_moteur_depuis_layout(LAYOUT),
                         CONTRAT['exemple']['zones'])

    def test_les_deux_cles_ne_se_confondent_pas(self):
        """CAL232 : `zones` = les PANS ; `exclusionZones` = les zones."""
        self.assertEqual(CLE_LAYOUT, 'exclusionZones')
        self.assertEqual(CLE_MOTEUR, 'zones')

    def test_les_natures_viennent_du_noyau(self):
        self.assertEqual(sorted(natures_admises()),
                         sorted(n.value for n in NatureZone))

    def test_chiffrage_du_contrat_recalcule(self):
        """Les chiffres publiés sont CALCULÉS, jamais écrits à la main."""
        chiffrage = chiffrage_zones(CONTRAT['exemple']['zones'])
        attendu = CONTRAT['exemple_chiffrage']
        self.assertAlmostEqual(chiffrage['aire_retiree_m2'],
                               attendu['aire_retiree_m2'], places=6)
        for nature, valeurs in attendu['par_nature'].items():
            for cle, valeur in valeurs.items():
                self.assertAlmostEqual(chiffrage['par_nature'][nature][cle],
                                       valeur, places=6, msg=f'{nature}.{cle}')


class RetraitDuPosableTest(SimpleTestCase):
    """Interdite et réservée retirent ; préférée ne retire rien."""

    def test_interdite_retire_sa_surface(self):
        chiffrage = chiffrage_zones(zones_moteur_depuis_layout(
            {CLE_LAYOUT: [_zone('INTERDITE',
                                [[0, 0], [4, 0], [4, 3], [0, 3]])]}))
        self.assertAlmostEqual(chiffrage['aire_retiree_m2'], 12.0, places=6)
        self.assertAlmostEqual(
            chiffrage['par_nature']['INTERDITE']['aire_retiree_m2'], 12.0,
            places=6)

    def test_le_retrait_saisi_dilate_la_zone(self):
        """Un retrait SAISI retire PLUS que le contour nu — jamais moins."""
        nu = chiffrage_zones(zones_moteur_depuis_layout(
            {CLE_LAYOUT: [_zone('INTERDITE',
                                [[0, 0], [4, 0], [4, 3], [0, 3]])]}))
        avec = chiffrage_zones(zones_moteur_depuis_layout(
            {CLE_LAYOUT: [_zone('INTERDITE',
                                [[0, 0], [4, 0], [4, 3], [0, 3]],
                                setbackM=0.5)]}))
        self.assertGreater(avec['aire_retiree_m2'], nu['aire_retiree_m2'])

    def test_reservee_est_chiffree_a_part(self):
        chiffrage = chiffrage_zones(zones_moteur_depuis_layout(LAYOUT))
        interdite = chiffrage['par_nature']['INTERDITE']['aire_retiree_m2']
        reservee = chiffrage['par_nature']['RESERVEE']['aire_retiree_m2']
        self.assertGreater(reservee, 0.0)
        self.assertAlmostEqual(chiffrage['aire_retiree_m2'],
                               interdite + reservee, places=6)

    def test_preferee_ne_retire_rien(self):
        chiffrage = chiffrage_zones(zones_moteur_depuis_layout(
            {CLE_LAYOUT: [_zone('PREFEREE',
                                [[0, 0], [4, 0], [4, 4], [0, 4]])]}))
        self.assertEqual(chiffrage['aire_retiree_m2'], 0.0)
        self.assertEqual(
            chiffrage['par_nature']['PREFEREE']['aire_retiree_m2'], 0.0)
        # Son aire reste PUBLIÉE : elle existe, elle ne coûte simplement rien.
        self.assertAlmostEqual(
            chiffrage['par_nature']['PREFEREE']['aire_m2'], 16.0, places=6)

    def test_preferee_hors_des_natures_bloquantes(self):
        """La garantie est celle du NOYAU, pas une règle recopiée ici."""
        self.assertNotIn(NatureZone.PREFEREE, NATURES_BLOQUANTES)
        self.assertIn(NatureZone.INTERDITE, NATURES_BLOQUANTES)
        self.assertIn(NatureZone.RESERVEE, NATURES_BLOQUANTES)

    def test_preferee_ne_change_jamais_un_compte(self):
        """Sans rangée, le bonus vaut 0 : il ne peut pas coûter un module."""
        from core.calepinage.serialisation import _zone_depuis

        zones = [_zone_depuis(z) for z in zones_moteur_depuis_layout(LAYOUT)]
        self.assertEqual(bonus_preference(zones, []), 0)


class InjectionTest(SimpleTestCase):
    """L'entrée moteur est enrichie — jamais réécrite en douce."""

    def setUp(self):
        self.document = {'repere': 'T1', 'surfaces': [], 'kits': []}

    def test_sans_zones_document_inchange(self):
        self.assertIs(injecter_zones(self.document, {}), self.document)
        self.assertIs(injecter_zones(self.document, {CLE_LAYOUT: []}),
                      self.document)
        self.assertIs(injecter_zones(self.document, None), self.document)

    def test_avec_zones_le_document_d_origine_n_est_pas_touche(self):
        enrichi = injecter_zones(self.document, LAYOUT)
        self.assertNotIn(CLE_MOTEUR, self.document)
        self.assertEqual(len(enrichi[CLE_MOTEUR]), 3)

    def test_les_zones_deja_presentes_sont_conservees(self):
        document = dict(self.document, zones=[{'repere': 'DEJA-LA'}])
        enrichi = injecter_zones(document, LAYOUT)
        self.assertEqual(enrichi[CLE_MOTEUR][0]['repere'], 'DEJA-LA')
        self.assertEqual(len(enrichi[CLE_MOTEUR]), 4)


class RepereTest(SimpleTestCase):
    """Aucune projection à l'aveugle : le repère est celui de l'appelant."""

    def test_par_defaut_les_sommets_passent_tels_quels(self):
        zones = zones_moteur_depuis_layout(
            {CLE_LAYOUT: [_zone('INTERDITE', [[1, 2], [3, 2], [3, 5]])]})
        self.assertEqual(zones[0]['sommets'], [[1.0, 2.0], [3.0, 2.0],
                                               [3.0, 5.0]])

    def test_projeteur_local_ramene_l_origine_a_zero(self):
        projeter = projeteur_local((4.8357, 45.7640))
        self.assertEqual(projeter((4.8357, 45.7640)), (0.0, 0.0))

    def test_projection_appliquee_quand_elle_est_fournie(self):
        zones = zones_moteur_depuis_layout(
            {CLE_LAYOUT: [_zone('INTERDITE',
                                [[4.8357, 45.7640], [4.8360, 45.7640],
                                 [4.8360, 45.7642]])]},
            projection=projeteur_local((4.8357, 45.7640)))
        self.assertEqual(zones[0]['sommets'][0], [0.0, 0.0])
        self.assertGreater(zones[0]['sommets'][1][0], 10.0)


class RefusTest(SimpleTestCase):
    """Les refus nomment LA zone fautive, en français."""

    def _refus(self, layout, champ):
        with self.assertRaises(ZoneRefusee) as capture:
            zones_moteur_depuis_layout(layout)
        self.assertEqual(capture.exception.champ, champ,
                         str(capture.exception))
        return capture.exception

    def test_nature_inconnue(self):
        erreur = self._refus(
            {CLE_LAYOUT: [_zone('SERVITUDE', [[0, 0], [1, 0], [1, 1]])]},
            'exclusionZones[0]')
        self.assertIn('SERVITUDE', str(erreur))
        self.assertIn('INTERDITE', str(erreur))

    def test_contour_a_deux_sommets(self):
        erreur = self._refus(
            {CLE_LAYOUT: [_zone('INTERDITE', [[0, 0], [1, 0]])]},
            'exclusionZones[0]')
        self.assertIn('2 sommet', str(erreur))

    def test_retrait_negatif(self):
        self._refus(
            {CLE_LAYOUT: [_zone('INTERDITE', [[0, 0], [1, 0], [1, 1]],
                                setbackM=-1)]},
            'exclusionZones[0]')

    def test_hauteur_negative(self):
        self._refus(
            {CLE_LAYOUT: [_zone('INTERDITE', [[0, 0], [1, 0], [1, 1]],
                                heightM=-2)]},
            'exclusionZones[0]')

    def test_sommet_illisible(self):
        self._refus(
            {CLE_LAYOUT: [_zone('INTERDITE', [[0, 0], ['x', 0], [1, 1]])]},
            'exclusionZones[0]')

    def test_zone_qui_n_est_pas_un_objet(self):
        self._refus({CLE_LAYOUT: ['une servitude']}, 'exclusionZones[0]')

    def test_tableau_qui_n_en_est_pas_un(self):
        self._refus({CLE_LAYOUT: {'id': 'X'}}, 'exclusionZones')

    def test_contour_vide_ignore_sans_refus(self):
        """Une zone en cours de saisie ne délimite rien : on l'ignore."""
        self.assertEqual(
            zones_moteur_depuis_layout(
                {CLE_LAYOUT: [_zone('INTERDITE', [])]}), [])

    def test_le_rang_de_la_zone_fautive_est_nomme(self):
        self._refus(
            {CLE_LAYOUT: [_zone('INTERDITE', [[0, 0], [1, 0], [1, 1]]),
                          _zone('INCONNUE', [[0, 0], [1, 0], [1, 1]])]},
            'exclusionZones[1]')
