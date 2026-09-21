"""CALX405 — proposer un châssis incliné sous un seuil de pente saisi.

CE QUI EST PROUVÉ ICI
----------------------
* ``services/gabarits.py`` valide ``chassis_sous_pente_deg`` et
  ``chassis_inclinaison_deg`` comme n'importe quel autre réglage de gabarit
  (angle borné, champ fautif NOMMÉ) — et refuse une inclinaison saisie sans
  son seuil, en nommant la clé manquante ;
* ``services/traduction.py`` (CAL78) PUBLIE la proposition de châssis
  incliné pour un pan relevé strictement sous le seuil, avec une raison qui
  nomme les DEUX angles — jamais appliquée d'office (le document et la
  politique restent ceux d'aujourd'hui) ;
* un pan relevé AU-DESSUS (ou à égalité) du seuil garde sa pose au fil du
  toit inchangée : aucune proposition ;
* un gabarit MUET sur les deux clés (ou complètement absent) rend une
  traduction octet pour octet identique à celle d'avant CALX405 (D12).

Aucune base de données : ``SimpleTestCase``.

Run :
    python manage.py test apps.calepinage.tests.test_calx405_chassis_sous_pente -v2
"""
import dataclasses
import math

from django.test import SimpleTestCase

from apps.calepinage.services.gabarits import (
    normaliser_section_gabarits_disposition,
)
from apps.calepinage.services.parametres import ReglageInvalide
from apps.calepinage.services.traduction import entree_depuis_layout


def _rectangle(lon0, lat0, largeur_m, hauteur_m):
    """Un rectangle en ``[[lng, lat], …]`` autour de ``(lon0, lat0)`` —
    même conversion mètres → degrés que ``test_traduction_layout.py``."""
    dlon = largeur_m / (111320.0 * math.cos(math.radians(lat0))) / 2.0
    dlat = hauteur_m / 110540.0 / 2.0
    return [[lon0 - dlon, lat0 - dlat], [lon0 + dlon, lat0 - dlat],
            [lon0 + dlon, lat0 + dlat], [lon0 - dlon, lat0 + dlat]]


def _sans_projection(traduction):
    """La ``Traduction``, sans son ``projection`` (une fermeture ``_VersRepere``
    — deux appels équivalents en rendent deux objets distincts, jamais
    ``==`` entre eux ; hors sujet CALX405, exclue de la comparaison)."""
    return dataclasses.replace(traduction, projection=None)


def _document(pitch_deg):
    """Un document D'OR à un seul pan, relevé à ``pitch_deg`` — Casablanca."""
    return {
        'version': 2,
        'pin': {'lat': 33.5, 'lng': -7.6},
        'panelWatt': 720,
        'panelLengthM': 2.278,
        'panelWidthM': 1.134,
        'activeAreaId': 'z1',
        'zones': [
            {
                'id': 'z1',
                'pitchDeg': pitch_deg,
                'vertices': _rectangle(-7.6, 33.5, 14.0, 10.0),
            },
        ],
    }


class LeGabaritValideLesDeuxReglages(SimpleTestCase):
    """``services/gabarits.py`` : validation, bornes, et croisement des clés."""

    def test_les_deux_cles_sont_admises_et_conservees(self):
        section = normaliser_section_gabarits_disposition({
            'terrasse': {'chassis_sous_pente_deg': 10,
                         'chassis_inclinaison_deg': 12},
        })
        self.assertEqual(section['terrasse']['chassis_sous_pente_deg'], 10.0)
        self.assertEqual(section['terrasse']['chassis_inclinaison_deg'], 12.0)

    def test_seuil_hors_bornes_est_refuse_en_nommant_le_champ(self):
        with self.assertRaises(ReglageInvalide) as ctx:
            normaliser_section_gabarits_disposition({
                'terrasse': {'chassis_sous_pente_deg': 95},
            })
        self.assertIn('chassis_sous_pente_deg', ctx.exception.champ)

    def test_inclinaison_hors_bornes_est_refusee_en_nommant_le_champ(self):
        with self.assertRaises(ReglageInvalide) as ctx:
            normaliser_section_gabarits_disposition({
                'terrasse': {'chassis_sous_pente_deg': 10,
                             'chassis_inclinaison_deg': 90},
            })
        self.assertIn('chassis_inclinaison_deg', ctx.exception.champ)

    def test_inclinaison_sans_seuil_est_refusee_en_nommant_la_cle_manquante(self):
        with self.assertRaises(ReglageInvalide) as ctx:
            normaliser_section_gabarits_disposition({
                'terrasse': {'chassis_inclinaison_deg': 12},
            })
        self.assertIn('chassis_sous_pente_deg', ctx.exception.champ)

    def test_gabarit_sans_les_deux_cles_reste_admis(self):
        """ÉQUIVALENCE : un gabarit d'aujourd'hui, sans rien de CALX405."""
        section = normaliser_section_gabarits_disposition({
            'defaut': {'orientation': 'portrait', 'famille': 'south'},
        })
        self.assertNotIn('chassis_sous_pente_deg', section['defaut'])
        self.assertNotIn('chassis_inclinaison_deg', section['defaut'])


class LeTraducteurProposeLeChassisIncline(SimpleTestCase):
    """``services/traduction.py`` (CAL78) : la proposition, jamais appliquée."""

    def test_gabarit_sans_les_deux_cles_est_octet_pour_octet_identique(self):
        baseline = entree_depuis_layout(_document(3.0))
        sans_gabarit = entree_depuis_layout(_document(3.0), regles_gabarit={})
        muet_sur_chassis = entree_depuis_layout(
            _document(3.0),
            regles_gabarit={'orientation': 'portrait', 'famille': 'south'})
        self.assertEqual(_sans_projection(baseline), _sans_projection(sans_gabarit))
        self.assertEqual(_sans_projection(baseline), _sans_projection(muet_sur_chassis))
        self.assertEqual(baseline.propositions_chassis, ())

    def test_pente_sous_le_seuil_propose_le_chassis_avec_les_deux_angles(self):
        traduction = entree_depuis_layout(
            _document(3.0),
            regles_gabarit={'chassis_sous_pente_deg': 10.0,
                            'chassis_inclinaison_deg': 12.0})
        self.assertEqual(len(traduction.propositions_chassis), 1)
        repere_pan, proposition = traduction.propositions_chassis[0]
        self.assertEqual(repere_pan, 'z1')
        self.assertEqual(proposition['inclinaison_deg'], 12.0)
        self.assertIn('3.0', proposition['raison'])
        self.assertIn('10.0', proposition['raison'])

    def test_pente_au_dessus_du_seuil_laisse_la_pose_au_fil_du_toit(self):
        avec_gabarit = entree_depuis_layout(
            _document(25.0),
            regles_gabarit={'chassis_sous_pente_deg': 10.0,
                            'chassis_inclinaison_deg': 12.0})
        sans_gabarit = entree_depuis_layout(_document(25.0))
        self.assertEqual(avec_gabarit.propositions_chassis, ())
        # « pose au fil du toit inchangée » : le document rendu ne bouge pas.
        self.assertEqual(avec_gabarit.document, sans_gabarit.document)
        self.assertEqual(avec_gabarit.politiques, sans_gabarit.politiques)

    def test_seuil_saisi_sans_inclinaison_ne_propose_rien(self):
        """D7 — rien de chiffrable à proposer : jamais une inclinaison
        inventée."""
        traduction = entree_depuis_layout(
            _document(3.0), regles_gabarit={'chassis_sous_pente_deg': 10.0})
        self.assertEqual(traduction.propositions_chassis, ())

    def test_seuil_non_saisi_ne_propose_rien_meme_pente_tres_faible(self):
        traduction = entree_depuis_layout(
            _document(0.5),
            regles_gabarit={'chassis_inclinaison_deg': 12.0})
        self.assertEqual(traduction.propositions_chassis, ())
