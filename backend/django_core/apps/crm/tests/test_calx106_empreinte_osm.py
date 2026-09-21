"""CALX106 — ce que la voie OSM DIT du bâtiment, et rien de plus.

CE QUE CE FICHIER GARDE
-----------------------
La requête Overpass demande déjà ``out geom`` : chaque réponse porte les
``tags`` de la voie (``height``, ``building:levels``, ``roof:levels``) et
``_parse_geometry`` les JETAIT. Pendant ce temps l'atelier 3D extrudait
toujours son hypothèse 6 m. CALX106 retient ces tags — et SEULEMENT ce que le
serveur peut réellement lire.

Trois promesses sont affirmées ici :

1. **Rien n'est converti.** Les niveaux restent des niveaux, la hauteur reste
   une hauteur : aucun « étage de 3 m » n'est supposé, ni dans un sens ni dans
   l'autre. Une voie qui ne porte QUE ``building:levels`` ne gagne aucune
   hauteur, et réciproquement.
2. **Zéro chiffre inventé** (D-CALX 7). Tag absent, vide, ou écrit dans une
   forme illisible (pieds, intervalle, liste, texte) ⇒ ``null`` ET un motif
   FRANÇAIS qui nomme le tag. Jamais un défaut, jamais 0.
3. **Toute valeur publiée porte sa provenance** : ``provenance[<clé>]`` vaut
   ``osm:<tag>``, ``source`` vaut ``openstreetmap`` dès qu'une valeur est
   publiée (``null`` sinon), et ``osm_way_id`` identifie la voie lue.

Le dernier bloc compare l'échantillon COMMITTÉ
(``apps/calepinage/contract_samples/calepinage_empreinte_osm.json``) à ce que
le parseur produit VRAIMENT : un contrat qui dérive du code échoue ici.

AUCUN RÉSEAU : les réponses Overpass sont FIXÉES dans ce fichier.

Run :
    python manage.py test apps.crm.tests.test_calx106_empreinte_osm
"""
from __future__ import annotations

import json
import pathlib

from django.test import SimpleTestCase

from apps.crm.roof_detect import (
    MOTIF_AUCUN_BATIMENT, SOURCE_OSM, _parse_geometry, batiment_non_renseigne,
)

#: L'échantillon partagé vit dans le module consommateur (calepinage) : il est
#: LU ici par son chemin, jamais importé — aucune frontière inter-apps n'est
#: franchie.
ECHANTILLON = (pathlib.Path(__file__).resolve().parents[2]
               / 'calepinage' / 'contract_samples'
               / 'calepinage_empreinte_osm.json')

#: Quatre sommets fermés — le minimum pour que le parseur retienne la voie.
_GEOMETRIE = [
    {"lat": 33.5731, "lon": -7.5898},
    {"lat": 33.5732, "lon": -7.5897},
    {"lat": 33.5733, "lon": -7.5898},
    {"lat": 33.5731, "lon": -7.5898},
]


def reponse(tags=None, osm_id=123456, geometrie=None):
    """UNE réponse Overpass FIXÉE, avec les tags demandés."""
    voie = {
        "type": "way",
        "id": osm_id,
        "geometry": list(_GEOMETRIE if geometrie is None else geometrie),
    }
    if tags is not None:
        voie["tags"] = tags
    return {"elements": [voie]}


def batiment(tags=None, **kwargs):
    return _parse_geometry(reponse(tags, **kwargs))["batiment"]


class FormeServieTest(SimpleTestCase):
    """La réponse a TOUJOURS les mêmes clés, quoi qu'OSM dise."""

    CLES = ('osm_way_id', 'levels', 'roof_levels', 'height_m', 'source',
            'provenance', 'non_renseignes')

    def test_la_geometrie_reste_servie_a_l_identique(self):
        """CALX106 est ADDITIF : le contour ne bouge pas d'un sommet."""
        empreinte = _parse_geometry(reponse({"height": "7.5"}))
        self.assertEqual(empreinte['polygon'], [
            {"lat": 33.5731, "lng": -7.5898},
            {"lat": 33.5732, "lng": -7.5897},
            {"lat": 33.5733, "lng": -7.5898},
            {"lat": 33.5731, "lng": -7.5898},
        ])

    def test_les_memes_cles_dans_les_trois_etats(self):
        etats = (
            batiment({"height": "7.5", "building:levels": "2"}),
            batiment({}),
            _parse_geometry({"elements": []})['batiment'],
        )
        for bloc in etats:
            self.assertEqual(sorted(bloc), sorted(self.CLES))

    def test_l_identifiant_de_la_voie_est_publie(self):
        self.assertEqual(batiment({"height": "7.5"}, osm_id=987)['osm_way_id'],
                         987)

    def test_une_voie_trop_courte_ne_donne_aucun_batiment(self):
        """Moins de 3 sommets : ce n'est pas un bâtiment, rien n'est lu."""
        bloc = batiment({"height": "7.5"},
                        geometrie=_GEOMETRIE[:2])
        self.assertIsNone(bloc['osm_way_id'])
        self.assertIsNone(bloc['height_m'])
        self.assertEqual(bloc['non_renseignes']['height_m'],
                         MOTIF_AUCUN_BATIMENT)


class RienNEstConvertiTest(SimpleTestCase):
    """Les niveaux restent des niveaux, la hauteur reste une hauteur."""

    def test_les_trois_tags_sont_lus_tels_quels(self):
        bloc = batiment({"height": "7.5",
                         "building:levels": "2",
                         "roof:levels": "1"})
        self.assertEqual(bloc['height_m'], 7.5)
        self.assertEqual(bloc['levels'], 2)
        self.assertEqual(bloc['roof_levels'], 1)

    def test_des_niveaux_seuls_ne_fabriquent_aucune_hauteur(self):
        """Le piège exact : 2 étages × 3 m = 6 m serait une INVENTION."""
        bloc = batiment({"building:levels": "2"})
        self.assertEqual(bloc['levels'], 2)
        self.assertIsNone(bloc['height_m'])
        self.assertIn('height', bloc['non_renseignes']['height_m'])

    def test_une_hauteur_seule_ne_fabrique_aucun_niveau(self):
        bloc = batiment({"height": "7.5"})
        self.assertEqual(bloc['height_m'], 7.5)
        self.assertIsNone(bloc['levels'])
        self.assertIsNone(bloc['roof_levels'])

    def test_une_hauteur_en_metres_annotee_est_lue(self):
        for brut in ("12 m", "12m", "12", "7,5"):
            with self.subTest(brut=brut):
                self.assertIsNotNone(batiment({"height": brut})['height_m'])

    def test_aucun_autre_tag_n_est_regarde(self):
        """Un tag voisin ne comble JAMAIS un tag manquant."""
        bloc = batiment({"building:height": "9", "levels": "4",
                         "building:min_level": "1"})
        self.assertIsNone(bloc['height_m'])
        self.assertIsNone(bloc['levels'])
        self.assertIsNone(bloc['source'])


class ZeroChiffreInventeTest(SimpleTestCase):
    """Absent ⇒ absent, et le motif le DIT (D-CALX 7)."""

    def test_un_batiment_sans_aucun_tag_rend_tout_null(self):
        bloc = batiment({})
        self.assertIsNone(bloc['levels'])
        self.assertIsNone(bloc['height_m'])
        self.assertIsNone(bloc['roof_levels'])
        self.assertIsNone(bloc['source'])
        self.assertEqual(bloc['provenance'], {})

    def test_une_voie_sans_cle_tags_rend_tout_null(self):
        bloc = batiment(None)
        self.assertIsNone(bloc['levels'])
        self.assertIsNone(bloc['height_m'])

    def test_chaque_valeur_absente_nomme_son_tag(self):
        bloc = batiment({})
        self.assertIn('building:levels', bloc['non_renseignes']['levels'])
        self.assertIn('roof:levels', bloc['non_renseignes']['roof_levels'])
        self.assertIn('height', bloc['non_renseignes']['height_m'])

    def test_une_ecriture_illisible_est_refusee_en_la_citant(self):
        """Pieds, intervalle, liste, texte : rien n'est deviné."""
        for tag, brut in (("height", "25'"),
                          ("height", "10-12"),
                          ("height", "environ 8"),
                          ("building:levels", "3;4"),
                          ("building:levels", "2.5"),
                          ("building:levels", "R+2")):
            with self.subTest(tag=tag, brut=brut):
                cle = 'height_m' if tag == 'height' else 'levels'
                bloc = batiment({tag: brut})
                self.assertIsNone(bloc[cle])
                self.assertIn(brut, bloc['non_renseignes'][cle],
                              "Le motif doit CITER la valeur illisible.")
                self.assertIsNone(bloc['source'])

    def test_une_hauteur_nulle_n_est_pas_une_hauteur(self):
        bloc = batiment({"height": "0"})
        self.assertIsNone(bloc['height_m'])
        self.assertIn('height_m', bloc['non_renseignes'])

    def test_un_tag_vide_vaut_absent(self):
        bloc = batiment({"height": "   "})
        self.assertIsNone(bloc['height_m'])
        self.assertIn('height', bloc['non_renseignes']['height_m'])

    def test_zero_niveau_reste_une_valeur_lue(self):
        """`building:levels=0` est SAISI dans OSM : on le publie tel quel."""
        bloc = batiment({"building:levels": "0"})
        self.assertEqual(bloc['levels'], 0)
        self.assertEqual(bloc['provenance']['levels'], 'osm:building:levels')

    def test_aucun_batiment_trouve_nomme_le_motif(self):
        bloc = _parse_geometry({"elements": []})['batiment']
        self.assertEqual(set(bloc['non_renseignes'].values()),
                         {MOTIF_AUCUN_BATIMENT})
        self.assertIsNone(bloc['source'])


class ProvenanceTest(SimpleTestCase):
    """Toute valeur publiée arrive avec d'où elle vient."""

    def test_chaque_valeur_publiee_a_son_tag_source(self):
        bloc = batiment({"height": "7.5",
                         "building:levels": "2",
                         "roof:levels": "1"})
        self.assertEqual(bloc['provenance'], {
            'height_m': 'osm:height',
            'levels': 'osm:building:levels',
            'roof_levels': 'osm:roof:levels',
        })

    def test_la_source_accompagne_toute_valeur_publiee(self):
        self.assertEqual(batiment({"height": "7.5"})['source'], SOURCE_OSM)
        self.assertEqual(batiment({"building:levels": "2"})['source'],
                         SOURCE_OSM)

    def test_aucune_valeur_publiee_aucune_source(self):
        self.assertIsNone(batiment({})['source'])

    def test_une_valeur_non_publiee_n_a_pas_de_provenance(self):
        bloc = batiment({"building:levels": "2"})
        self.assertNotIn('height_m', bloc['provenance'])
        self.assertIn('levels', bloc['provenance'])

    def test_provenance_et_non_renseignes_sont_exclusifs(self):
        bloc = batiment({"height": "7.5", "building:levels": "3;4"})
        self.assertEqual(set(bloc['provenance']) & set(bloc['non_renseignes']),
                         set())

    def test_le_bloc_non_renseigne_est_muet_et_nomme_son_motif(self):
        bloc = batiment_non_renseigne('motif de test')
        self.assertIsNone(bloc['source'])
        self.assertEqual(bloc['provenance'], {})
        self.assertEqual(set(bloc['non_renseignes'].values()),
                         {'motif de test'})


class EchantillonCommitteTest(SimpleTestCase):
    """L'échantillon partagé dit ce que le serveur fait VRAIMENT."""

    def setUp(self):
        self.document = json.loads(ECHANTILLON.read_text(encoding='utf-8'))

    def test_l_exemple_est_ce_que_le_parseur_produit(self):
        attendu = self.document['exemple']['batiment']
        obtenu = batiment({"height": "7.5",
                           "building:levels": "2",
                           "roof:levels": "1"},
                          osm_id=attendu['osm_way_id'])
        self.assertEqual(obtenu, attendu)

    def test_l_exemple_sans_tag_est_ce_que_le_parseur_produit(self):
        attendu = self.document['exemple_batiment_sans_tag']['batiment']
        obtenu = batiment({}, osm_id=attendu['osm_way_id'])
        self.assertEqual(obtenu, attendu)

    def test_l_exemple_vide_est_ce_que_le_parseur_produit(self):
        attendu = self.document['exemple_vide']
        obtenu = _parse_geometry({"elements": []})
        self.assertEqual(obtenu['polygon'], attendu['polygon'])
        self.assertEqual(obtenu['batiment'], attendu['batiment'])

    def test_le_contour_de_l_exemple_est_celui_du_parseur(self):
        attendu = self.document['exemple']['polygon']
        self.assertEqual(_parse_geometry(reponse({}))['polygon'], attendu)
