"""CALX258 — familles élargies à ``pompage`` + courbes SEGMENTÉES par type
de jour, sur ``ProfilTypeConsommation`` (CAL149).

Ce qui est tenu ici (partie PURE, sans base — même patron que le fichier
sœur ``test_conso_profils_types.py``) :

* la forme plate ``{saison: [24]}`` continue de se lire EXACTEMENT comme
  avant CALX258 (D12 : une société qui n'édite rien relit ce qu'elle
  relisait avant) ;
* la forme SEGMENTÉE ``{saison: {jour_type: [24]}}`` rend DEUX courbes
  distinctes pour deux types de jour d'une même saison ;
* un ``jour_type`` inconnu est refusé EN LE NOMMANT ;
* la famille ``pompage`` est acceptée, avec la même règle « provenance
  obligatoire » que les autres familles.
"""
from __future__ import annotations

import unittest

from django.core.exceptions import ValidationError

from apps.calepinage.models import ProfilTypeConsommation
from apps.calepinage.services.profils_types import _courbes_normalisees

#: Deux journées BIEN distinctes : impossible de les confondre par erreur.
JOURNEE_OUVRE = [1.0] * 6 + [4.0] * 12 + [1.0] * 6
JOURNEE_WEEKEND = [2.0] * 24
#: Une journée de repli, forme quelconque mais non nulle (comme le fichier
#: sœur ``test_conso_profils_types.py``).
JOURNEE = [1.0] * 6 + [2.0] * 6 + [3.0] * 6 + [4.0] * 6


def profil(**kwargs):
    donnees = {
        'cle': 'residentiel-casa', 'libelle': 'Résidentiel Casablanca',
        'famille': 'residentiel', 'courbe': {'annuel': JOURNEE},
        'provenance': 'Relevé de 12 factures ONEE, client anonymisé, 2025.',
    }
    donnees.update(kwargs)
    return ProfilTypeConsommation(**donnees)


def valider(objet):
    # ``company`` et ``saisi_par`` sont posés côté serveur : on valide la
    # SAISIE, pas le rattachement (même patron que CAL149).
    objet.full_clean(exclude=['company', 'saisi_par'])


class FormePlateInchangeeTest(unittest.TestCase):
    """« Une société qui n'édite rien se comporte exactement comme
    aujourd'hui » — la forme plate n'a PAS bougé avec CALX258."""

    def test_un_profil_a_forme_plate_reste_accepte(self):
        valider(profil())

    def test_la_lecture_normalisee_d_un_profil_plat_est_inchangee(self):
        courbes = _courbes_normalisees({'annuel': JOURNEE})
        total = sum(JOURNEE)
        self.assertEqual(courbes['annuel'],
                         [valeur / total for valeur in JOURNEE])

    def test_une_courbe_plate_mal_formee_reste_refusee_comme_avant(self):
        with self.assertRaises(ValidationError) as refus:
            valider(profil(courbe={'hiver': [1.0] * 23}))
        self.assertIn('24', refus.exception.message_dict['courbe'][0])

    def test_une_journee_plate_entierement_nulle_reste_refusee(self):
        with self.assertRaises(ValidationError) as refus:
            valider(profil(courbe={'ete': [0.0] * 24}))
        self.assertIn('nulle', refus.exception.message_dict['courbe'][0])


class CourbeSegmenteeTest(unittest.TestCase):
    """CALX258 — ``{saison: {jour_type: [24]}}``, en plus de la forme plate."""

    def test_deux_types_de_jour_sont_acceptes(self):
        valider(profil(courbe={
            'ete': {'ouvre': JOURNEE_OUVRE, 'weekend': JOURNEE_WEEKEND},
        }))

    def test_deux_types_de_jour_rendent_deux_courbes_distinctes(self):
        courbes = _courbes_normalisees({
            'ete': {'ouvre': JOURNEE_OUVRE, 'weekend': JOURNEE_WEEKEND},
        })
        self.assertIn('ouvre', courbes['ete'])
        self.assertIn('weekend', courbes['ete'])
        self.assertNotEqual(courbes['ete']['ouvre'],
                            courbes['ete']['weekend'])
        self.assertAlmostEqual(sum(courbes['ete']['ouvre']), 1.0, places=9)
        self.assertAlmostEqual(sum(courbes['ete']['weekend']), 1.0, places=9)

    def test_un_jour_type_inconnu_est_refuse_en_le_nommant(self):
        with self.assertRaises(ValidationError) as refus:
            valider(profil(courbe={
                'ete': {'ouvre': JOURNEE_OUVRE,
                        'mardi-gras': JOURNEE_WEEKEND},
            }))
        self.assertIn('mardi-gras',
                      refus.exception.message_dict['courbe'][0])

    def test_une_courbe_segmentee_vide_est_refusee(self):
        with self.assertRaises(ValidationError) as refus:
            valider(profil(courbe={'ete': {}}))
        self.assertIn('type de jour',
                      refus.exception.message_dict['courbe'][0])

    def test_un_type_de_jour_mal_forme_est_refuse_comme_la_forme_plate(self):
        with self.assertRaises(ValidationError) as refus:
            valider(profil(courbe={'ete': {'ouvre': [1.0] * 10}}))
        self.assertIn('24', refus.exception.message_dict['courbe'][0])

    def test_une_journee_de_type_de_jour_entierement_nulle_est_refusee(self):
        courbe = {'ete': {'ouvre': [0.0] * 24, 'weekend': JOURNEE_WEEKEND}}
        with self.assertRaises(ValidationError) as refus:
            valider(profil(courbe=courbe))
        self.assertIn('nulle', refus.exception.message_dict['courbe'][0])

    def test_une_seule_saison_segmentee_ne_touche_pas_les_autres(self):
        """Une saison plate et une saison segmentée peuvent coexister."""
        courbes = _courbes_normalisees({
            'annuel': JOURNEE,
            'ete': {'ouvre': JOURNEE_OUVRE, 'weekend': JOURNEE_WEEKEND},
        })
        self.assertIsInstance(courbes['annuel'], list)
        self.assertIsInstance(courbes['ete'], dict)


class FamillePompageTest(unittest.TestCase):
    """CALX258 — la famille neuve, avec la même règle « provenance »."""

    def test_la_famille_pompage_est_admise(self):
        codes = [code for code, _ in ProfilTypeConsommation.Famille.choices]
        self.assertIn('pompage', codes)

    def test_un_profil_pompage_avec_provenance_est_accepte(self):
        valider(profil(
            famille='pompage',
            provenance='Compteur du forage, relevé horaire, 2025.'))

    def test_un_profil_pompage_sans_provenance_est_refuse_en_le_nommant(self):
        with self.assertRaises(ValidationError) as refus:
            valider(profil(famille='pompage', provenance=''))
        self.assertIn('provenance', refus.exception.message_dict)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
