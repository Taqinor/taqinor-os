"""CALX106 — le contrat de l'empreinte OSM, côté consommateur.

POURQUOI CE FICHIER EST DANS `apps/calepinage`
----------------------------------------------
Le producteur est `apps/crm/roof_detect.py` (affirmé par
`apps/crm/tests/test_calx106_empreinte_osm.py`, sur des réponses Overpass
FIXÉES). Le CONSOMMATEUR est l'atelier 3D du calepinage : la moitié atelier
(CALX132) lira ce document pour remplir `buildings[]` du document
`roof_layout` v2. Ce fichier garde le pont entre les deux, et RIEN d'autre —
il ne fait aucun appel réseau, ne touche aucune base, n'importe aucun modèle.

Ce qu'il affirme :

1. **L'échantillon est un contrat COMPLET** (PACT10) : `endpoint`, `pourquoi`,
   `exemple` — et ses trois états (bâtiment renseigné, bâtiment sans tag,
   aucun bâtiment) portent exactement les mêmes clés.
2. **Zéro chiffre inventé** (D-CALX 7) : dans l'état « sans tag », chaque
   valeur vaut `null` et son motif la NOMME ; aucune valeur n'est reconstruite
   depuis une autre.
3. **Le pont vers CALX84 tient** : ce que l'échantillon publie se traduit dans
   `$defs/building` du schéma v2 SANS invention — une hauteur OSM y entre avec
   sa `source`, une hauteur absente n'y entre pas. Le document traduit est
   validé contre le schéma RÉEL et passe la porte d'import RÉELLE.

Run :
    python manage.py test apps.calepinage.tests.test_calx106_contrat_empreinte_osm
"""
from __future__ import annotations

import copy
import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services.io_layout import valider_document

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')
DOCUMENT = json.loads((ECHANTILLONS / 'calepinage_empreinte_osm.json')
                      .read_text(encoding='utf-8'))
SCHEMA = json.loads((ECHANTILLONS / 'roof_layout_v2.schema.json')
                    .read_text(encoding='utf-8'))

#: Les trois états servis par la porte, sous leur nom dans l'échantillon.
ETATS = ('exemple', 'exemple_batiment_sans_tag', 'exemple_vide')

#: Les clés du bloc `batiment`, dans l'ordre où le serveur les sert.
CLES_BATIMENT = ('osm_way_id', 'levels', 'roof_levels', 'height_m', 'source',
                 'provenance', 'non_renseignes')

#: Le tag OSM derrière chaque valeur publiée — la provenance attendue est
#: exactement ``osm:<tag>``.
TAG_ATTENDU = {'levels': 'building:levels',
               'roof_levels': 'roof:levels',
               'height_m': 'height'}

#: CALX132 (moitié atelier) : la traduction attendue vers `$defs/building`.
#: Les niveaux restent des niveaux, la hauteur reste une hauteur.
TRADUCTION_CALX84 = {'height_m': 'hauteurM', 'levels': 'etages'}


def traduire(bloc):
    """Ce que l'atelier écrira dans `buildings[]` — sans rien inventer.

    Une valeur absente n'entre PAS dans le document (elle y vaudrait `null`,
    ce qui est déjà l'état par défaut) ; une valeur présente y entre AVEC sa
    provenance, faute de quoi le contrat CALX84 la refuse.
    """
    batiment = {'id': f"osm-{bloc['osm_way_id']}"}
    for cle_osm, cle_document in TRADUCTION_CALX84.items():
        if bloc[cle_osm] is not None:
            batiment[cle_document] = bloc[cle_osm]
    if bloc['source'] is not None:
        batiment['source'] = bloc['source']
    return batiment


class ContratCompletTest(SimpleTestCase):
    """L'échantillon porte ce que PACT10 exige, et ses états concordent."""

    def test_l_entete_du_contrat_est_complete(self):
        for cle in ('endpoint', 'pourquoi', 'exemple'):
            self.assertIn(cle, DOCUMENT)
        self.assertTrue(DOCUMENT['endpoint'].startswith('GET /api/django/crm/'))

    def test_les_trois_etats_sont_servis(self):
        for etat in ETATS:
            self.assertIn(etat, DOCUMENT, f"état « {etat} » absent")

    def test_chaque_etat_sert_les_memes_cles_racine(self):
        racine = {'polygon', 'source', 'batiment'}
        for etat in ETATS:
            manquantes = racine - set(DOCUMENT[etat])
            self.assertEqual(manquantes, set(),
                             f"{etat} : clé(s) {sorted(manquantes)} absente(s)")

    def test_chaque_etat_sert_les_memes_cles_de_batiment(self):
        for etat in ETATS:
            self.assertEqual(sorted(DOCUMENT[etat]['batiment']),
                             sorted(CLES_BATIMENT), etat)

    def test_la_cle_polygon_et_le_message_restent_inchanges(self):
        """CALX106 est ADDITIF : rien de ce qui existait ne bouge."""
        self.assertEqual(DOCUMENT['exemple']['source'], 'osm')
        self.assertEqual(DOCUMENT['exemple_vide']['polygon'], [])
        self.assertIn('message', DOCUMENT['exemple_vide'])
        self.assertNotIn('message', DOCUMENT['exemple'])

    def test_le_contour_reste_une_liste_de_points_lat_lng(self):
        for sommet in DOCUMENT['exemple']['polygon']:
            self.assertEqual(sorted(sommet), ['lat', 'lng'])


class ZeroChiffreInventeTest(SimpleTestCase):
    """Absent ⇒ absent, et le motif le nomme (D-CALX 7)."""

    def test_un_batiment_sans_tag_rend_tout_null(self):
        bloc = DOCUMENT['exemple_batiment_sans_tag']['batiment']
        for cle in ('levels', 'roof_levels', 'height_m', 'source'):
            self.assertIsNone(bloc[cle], cle)
        self.assertEqual(bloc['provenance'], {})

    def test_chaque_valeur_absente_porte_son_motif(self):
        for etat in ('exemple_batiment_sans_tag', 'exemple_vide'):
            bloc = DOCUMENT[etat]['batiment']
            for cle in ('levels', 'roof_levels', 'height_m'):
                self.assertIn(cle, bloc['non_renseignes'], f'{etat}/{cle}')
                self.assertTrue(bloc['non_renseignes'][cle].strip(),
                                f'{etat}/{cle} : motif vide')

    def test_aucune_valeur_publiee_sans_provenance(self):
        for etat in ETATS:
            bloc = DOCUMENT[etat]['batiment']
            for cle, tag in TAG_ATTENDU.items():
                if bloc[cle] is None:
                    continue
                self.assertEqual(bloc['provenance'].get(cle), f'osm:{tag}',
                                 f'{etat}/{cle} : provenance absente ou fausse')
                self.assertEqual(bloc['source'], 'openstreetmap', etat)

    def test_une_valeur_publiee_n_est_jamais_dite_non_renseignee(self):
        for etat in ETATS:
            bloc = DOCUMENT[etat]['batiment']
            for cle in ('levels', 'roof_levels', 'height_m'):
                if bloc[cle] is not None:
                    self.assertNotIn(cle, bloc['non_renseignes'],
                                     f'{etat}/{cle}')

    def test_les_niveaux_ne_fabriquent_aucune_hauteur(self):
        """`etages × 3 m` serait une invention : la preuve est dans l'exemple.

        L'exemple porte 2 niveaux et 7.5 m — deux valeurs LUES, sans rapport
        arithmétique : aucune n'a été calculée depuis l'autre.
        """
        bloc = DOCUMENT['exemple']['batiment']
        self.assertEqual(bloc['levels'], 2)
        self.assertEqual(bloc['height_m'], 7.5)
        self.assertNotEqual(bloc['height_m'], bloc['levels'] * 3)


class PontVersLeDocumentV2Test(SimpleTestCase):
    """Ce qu'OSM dit entre dans `buildings[]` sans rien inventer (CALX84)."""

    def _valider(self, batiments):
        document = copy.deepcopy(SCHEMA['exemple'])
        document['buildings'] = batiments
        valider_document(document)
        return document

    def test_une_hauteur_osm_entre_avec_sa_provenance(self):
        batiment = traduire(DOCUMENT['exemple']['batiment'])
        self.assertEqual(batiment['hauteurM'], 7.5)
        self.assertEqual(batiment['etages'], 2)
        self.assertEqual(batiment['source'], 'openstreetmap')
        self._valider([batiment])

    def test_un_batiment_sans_tag_n_ecrit_aucune_hauteur(self):
        batiment = traduire(DOCUMENT['exemple_batiment_sans_tag']['batiment'])
        self.assertNotIn('hauteurM', batiment)
        self.assertNotIn('etages', batiment)
        self.assertNotIn('source', batiment)
        self._valider([batiment])

    def test_les_deux_etats_cohabitent_dans_un_meme_document(self):
        self._valider([traduire(DOCUMENT['exemple']['batiment']),
                       traduire(DOCUMENT['exemple_batiment_sans_tag']
                                ['batiment'])])

    def test_le_schema_decrit_bien_les_champs_traduits(self):
        proprietes = SCHEMA['$defs']['building']['properties']
        for cle_document in TRADUCTION_CALX84.values():
            self.assertIn(cle_document, proprietes)
        self.assertIn('source', proprietes)

    def test_une_hauteur_sans_provenance_serait_refusee(self):
        """La garde de CALX84, vue depuis CALX106 : `source` est la clé."""
        from apps.calepinage.services.io_layout import ImportLayoutRefuse

        batiment = traduire(DOCUMENT['exemple']['batiment'])
        del batiment['source']
        with self.assertRaises(ImportLayoutRefuse) as capture:
            self._valider([batiment])
        self.assertIn('source', str(capture.exception))
