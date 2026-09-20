# -*- coding: utf-8 -*-
"""CAL232 — le schéma v2 de ``roof_layout`` ne casse AUCUN consommateur ventes.

POURQUOI CE TEST EXISTE
-----------------------
La seule définition du document ``roof_layout`` est ``serializeLayout`` côté
site (``apps/web/src/scripts/roofPro11/prefill.ts``). Le backend ne le valide
NULLE PART : l'AO le stocke « non validé » et ``Devis.roof_layout`` est le blob
POST conservé tel quel. SEPT tâches du groupe CAL vont l'étendre depuis des
lanes file-disjointes (arêtes typées CAL57, identifiant de bâtiment CAL59,
hauteur d'obstacle CAL66, objets d'environnement CAL67, zones CAL68,
provenance CAL72, accès solaire CAL248) — et PACT10 dit que deux lanes sans
fichier partagé inventent deux formes.

``apps/calepinage/contract_samples/roof_layout_v2.schema.json`` est ce fichier
partagé. Ce test est sa contre-épreuve, et il pose DEUX obligations :

1. **Un document v1 reste valide.** Le schéma décrit ce qui EXISTE ; il ne
   referme pas un document que personne ne validait hier. Les documents v1
   utilisés ici sont recopiés de fixtures RÉELLES du dépôt (citées en
   commentaire), champs internes compris (``_pans_geometry``,
   ``prix_achat_total``) — ce sont eux qui arrivent en base.
2. **Un document v2 passe les trois consommateurs sans changer un chiffre.**
   Les trois sont exercés directement, sans base de données :
   ``_panneaux_du_layout`` (drapeau de péremption du calepinage),
   ``_zone_villa_depuis_pan`` (adaptateur vers le moteur villa) et
   ``_safe_roof_layout`` (assainissement de la section publique ``#roof3d``).

``jsonschema`` N'EST PAS UNE NOUVELLE DÉPENDANCE : c'est une dépendance dure de
``drf-spectacular==0.28.0`` (``requirements.txt``), déjà installée partout
où ce test tourne.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_roof_layout_v2 -v 2
"""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase
from jsonschema import Draft202012Validator

from apps.ventes.domain.geometrie import _zone_villa_depuis_pan
from apps.ventes.public_views import _safe_roof_layout
from apps.ventes.quote_engine.builder import _panneaux_du_layout

# ``…/backend/django_core/apps/ventes/tests/`` -> ``…/apps/calepinage/…``
SCHEMA_PATH = (Path(__file__).resolve().parents[2] / 'calepinage'
               / 'contract_samples' / 'roof_layout_v2.schema.json')

#: Les sept extensions nommées par le schéma, par l'endroit où elles vivent.
#: Les retirer d'un document v2 doit rendre EXACTEMENT le document v1 dont il
#: est l'extension — c'est la définition opérationnelle de « additif ».
EXTENSIONS_RACINE = ('environment', 'exclusionZones')      # CAL67, CAL68
EXTENSIONS_ZONE = ('buildingId', 'edges')                  # CAL59, CAL57
EXTENSIONS_OBSTACLE = ('heightM', 'provenance')            # CAL66, CAL72
EXTENSIONS_GEOMETRIE = ('solarAccess',)                    # CAL248


def charger_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))


def sans_extensions(document):
    """Le même document, privé de TOUTES les extensions v2 du groupe CAL."""
    base = copy.deepcopy(document)
    for cle in EXTENSIONS_RACINE:
        base.pop(cle, None)
    for zone in base.get('zones', []):
        for cle in EXTENSIONS_ZONE:
            zone.pop(cle, None)
        for obstacle in zone.get('obstacles', []):
            for cle in EXTENSIONS_OBSTACLE:
                obstacle.pop(cle, None)
        geometrie = zone.get('geometry')
        if isinstance(geometrie, dict):
            for cle in EXTENSIONS_GEOMETRIE:
                geometrie.pop(cle, None)
    return base


# ── Documents v1 RÉELS, recopiés de fixtures du dépôt ────────────────────────

def layout_v1_qj26():
    """``apps/ventes/tests/test_qj26_roof_layout_proposal.sample_layout()``.

    Porte volontairement les champs INTERNES que l'assainissement public doit
    retirer (``prix_achat``, ``marge``, ``prix_vente``, ``prix_achat_total``) :
    un schéma qui les refuserait rendrait invalide un document réellement
    présent en base.
    """
    return {
        'version': 1,
        'scenario': 'reseau',
        'result': {'panels': 16, 'kwc': 8.8, 'annualKwh': 14000,
                   'savings': 11000},
        'zones': [{
            'id': 'z1', 'label': 'Pan Sud',
            'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
            'obstacles': [], 'roofType': 'pitched', 'pitchDeg': 30,
            'facingAzimuthDeg': 0, 'neededPanels': 12,
        }],
        '_pans_geometry': [{
            'label': 'Pan Sud', 'orientation': 'Sud', 'azimut_deg': 0,
            'inclinaison_deg': 30, 'nb_panneaux': 12, 'kwc': 6.6,
            'roof_type': 'pitched',
            'prix_achat': 9999, 'marge': 0.3, 'prix_vente': 1400,
        }],
        'prix_achat_total': 123456,
    }


def layout_v1_pv14():
    """``apps/ventes/tests/test_pv14_geometry_par_pan._zone_v1()`` complet."""
    return {
        'version': 1,
        'pin': {'lat': 33.5, 'lng': -7.6},
        'outline': [],
        'billKwh': None,
        'activeAreaId': 'z1',
        'zones': [{
            'id': 'z1', 'label': 'Pan z1',
            'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
            'obstacles': [], 'roofType': 'pitched', 'pitchDeg': 15.0,
            'facingAzimuthDeg': 0.0, 'facingManual': False,
            'neededPanels': 12, 'neededAuto': True,
            'geometry': {
                'azimuthDeg': 180.0, 'tiltDeg': 15.0, 'family': 'south',
                'flush': True, 'kwc': 6.6, 'count': 12,
                'origin': [-7.6, 33.5],
                'panels': [{'cx': i * 1.2, 'cy': 0.0} for i in range(12)],
            },
        }],
    }


def layout_v1_minimal():
    """``apps/ventes/tests/test_auto_pipeline`` : une zone, aucun en-tête."""
    return {'zones': [{
        'label': 'Toit', 'roofType': 'flat', 'pitchDeg': 15,
        'facingAzimuthDeg': 180,
        'result': {'count': 12, 'kwc': 8.52, 'areaM2': 30.0},
    }]}


def layout_sans_zones():
    """``apps/ventes/tests/test_pv74_simulation_async`` : aucune zone."""
    return {'version': 2, '_pans_geometry': [{'label': 'P',
                                              'nb_panneaux': 3}]}


class SchemaRoofLayoutV2Test(SimpleTestCase):
    """Le schéma est bien formé, et il n'invalide rien de ce qui existe."""

    def setUp(self):
        self.schema = charger_schema()
        self.validateur = Draft202012Validator(self.schema)

    def _erreurs(self, document):
        return [(list(e.absolute_path), e.message)
                for e in self.validateur.iter_errors(document)]

    def test_le_schema_est_un_schema_json_bien_forme(self):
        Draft202012Validator.check_schema(self.schema)

    def test_le_schema_porte_le_format_des_echantillons_de_contrat(self):
        """`check_api_shapes.py` n'accepte que `endpoint` + `exemple` ici."""
        self.assertTrue(self.schema['endpoint'].startswith('GET /api/django/'))
        self.assertIsInstance(self.schema['exemple'], dict)
        self.assertIn('pourquoi', self.schema)

    def test_l_exemple_du_schema_est_lui_meme_conforme(self):
        """Un exemple EXÉCUTABLE, jamais une annotation morte."""
        self.assertEqual(self._erreurs(self.schema['exemple']), [])

    def test_les_documents_v1_reels_restent_valides(self):
        for nom, fabrique in (('qj26', layout_v1_qj26),
                              ('pv14', layout_v1_pv14),
                              ('minimal', layout_v1_minimal),
                              ('sans_zones', layout_sans_zones)):
            with self.subTest(document=nom):
                self.assertEqual(self._erreurs(fabrique()), [])

    def test_un_document_vide_reste_valide(self):
        """Aucune clé n'est requise : les consommateurs sont tous tolérants.

        `_panneaux_du_layout` rend `0` sur un document absent ou mal formé,
        `_zone_villa_depuis_pan` rend `None` sur un pan sans contour. Un schéma
        qui refuserait serait plus strict que chacun d'eux — il créerait un
        mode de panne qui n'existe pas aujourd'hui.
        """
        self.assertEqual(self._erreurs({}), [])

    def test_chaque_extension_est_optionnelle(self):
        """Le v2 privé de ses sept extensions reste valide (additivité)."""
        base = sans_extensions(self.schema['exemple'])
        self.assertEqual(self._erreurs(base), [])

    def test_les_sept_extensions_sont_bien_dans_l_exemple(self):
        """Sinon `test_chaque_extension_est_optionnelle` ne prouverait rien."""
        exemple = self.schema['exemple']
        zone = exemple['zones'][0]
        obstacle = zone['obstacles'][0]
        for cle in EXTENSIONS_RACINE:
            self.assertIn(cle, exemple)
        for cle in EXTENSIONS_ZONE:
            self.assertIn(cle, zone)
        for cle in EXTENSIONS_OBSTACLE:
            self.assertIn(cle, obstacle)
        for cle in EXTENSIONS_GEOMETRIE:
            self.assertIn(cle, zone['geometry'])

    def test_une_valeur_hors_enumeration_est_refusee(self):
        """Le schéma est permissif sur les CLÉS, pas sur les NATURES."""
        document = copy.deepcopy(self.schema['exemple'])
        document['zones'][0]['edges'][0]['type'] = 'pignon_invente'
        self.assertNotEqual(self._erreurs(document), [])

    def test_les_deux_graphies_de_provenance_sont_acceptees(self):
        """`core.calepinage` dit RELEVE, `apps.ao` dit MESURE — mêmes états."""
        for graphie in ('RELEVE', 'MESURE', 'PLAN', 'DEVINE', 'ECARTE'):
            with self.subTest(provenance=graphie):
                document = copy.deepcopy(self.schema['exemple'])
                document['zones'][0]['obstacles'][0]['provenance'] = graphie
                self.assertEqual(self._erreurs(document), [])


class NonRegressionConsommateursVentesTest(SimpleTestCase):
    """Les TROIS consommateurs ventes ne changent aucun chiffre en v2."""

    def setUp(self):
        self.v2 = charger_schema()['exemple']
        self.v1 = sans_extensions(self.v2)

    # ── 1. builder._panneaux_du_layout (drapeau de péremption) ──────────────
    def test_panneaux_du_layout_identique(self):
        self.assertEqual(_panneaux_du_layout(self.v2),
                         _panneaux_du_layout(self.v1))

    def test_panneaux_du_layout_lit_bien_le_result(self):
        """Le compte vient de `result.panels` — pas d'accident d'égalité."""
        self.assertEqual(_panneaux_du_layout(self.v2),
                         self.v2['result']['panels'])

    # ── 2. domain.geometrie._zone_villa_depuis_pan (moteur villa) ───────────
    def test_zone_villa_depuis_pan_identique(self):
        self.assertEqual(_zone_villa_depuis_pan(self.v2['zones'][0]),
                         _zone_villa_depuis_pan(self.v1['zones'][0]))

    def test_zone_villa_depuis_pan_ignore_les_extensions(self):
        """L'adaptateur ne lit que des clés NOMMÉES : rien de neuf n'entre."""
        zone = _zone_villa_depuis_pan(self.v2['zones'][0])
        self.assertEqual(set(zone), {'id', 'polygon', 'flat', 'tilt',
                                     'azimuth', 'obstacles'})
        self.assertEqual(set(zone['obstacles'][0]),
                         {'id', 'center', 'widthM', 'heightM'})
        # `heightM` de l'adaptateur villa est l'étendue NORD-SUD (`lengthM` du
        # document), PAS la hauteur d'obstacle de CAL66 : deux clés homonymes
        # aux sens opposés. La preuve que CAL66 n'a rien écrasé.
        self.assertEqual(zone['obstacles'][0]['heightM'],
                         self.v2['zones'][0]['obstacles'][0]['lengthM'])

    # ── 3. public_views._safe_roof_layout (section publique `#roof3d`) ──────
    def _public(self, layout):
        return _safe_roof_layout(SimpleNamespace(roof_layout=layout))

    def test_roof3d_public_ne_publie_aucune_extension_structurante(self):
        """Ni les objets d'environnement, ni les zones, ni les arêtes, ni
        l'accès solaire, ni l'identifiant de bâtiment n'atteignent le client :
        la whitelist `_ZONE_KEYS` / `_safe_zone_geometry` les écarte."""
        public = self._public(self.v2)
        self.assertNotIn('environment', public)
        self.assertNotIn('exclusionZones', public)
        zone = public['zones'][0]
        self.assertNotIn('edges', zone)
        self.assertNotIn('buildingId', zone)
        self.assertNotIn('solarAccess', zone['geometry'])

    def test_roof3d_public_ne_change_aucun_chiffre(self):
        """Les totaux, la géométrie de pose et le contour sont identiques."""
        v1, v2 = self._public(self.v1), self._public(self.v2)
        self.assertEqual(v1['result'], v2['result'])
        self.assertEqual(v1.get('scenario'), v2.get('scenario'))
        self.assertEqual(v1['zones'][0]['geometry'],
                         v2['zones'][0]['geometry'])
        for cle in ('id', 'label', 'vertices', 'roofType', 'pitchDeg',
                    'facingAzimuthDeg', 'neededPanels'):
            self.assertEqual(v1['zones'][0].get(cle), v2['zones'][0].get(cle))

    def test_roof3d_public_recopie_les_obstacles_verbatim(self):
        """CONSTAT MESURÉ, à lire par la lane CAL72.

        `_safe_roof_layout` recopie `zones[].obstacles` EN BLOC (`_ZONE_KEYS`
        prend la clé telle quelle) là où `geometry` est recopiée champ par
        champ. Conséquence : `heightM` (CAL66) et `provenance` (CAL72)
        descendent jusqu'à la page CLIENT. Aucun CHIFFRE de l'offre n'en est
        changé et aucun prix ne fuit — mais publier « provenance: DEVINE »
        revient à dire au client qu'on a deviné sa cheminée. Ce test FIXE le
        comportement d'aujourd'hui pour qu'un durcissement soit une décision,
        pas un accident ; c'est à CAL72 de trancher s'il faut whitelister les
        sous-clés d'obstacle.
        """
        obstacle_public = self._public(self.v2)['zones'][0]['obstacles'][0]
        obstacle_source = self.v2['zones'][0]['obstacles'][0]
        self.assertEqual(obstacle_public, obstacle_source)
        self.assertIn('provenance', obstacle_public)
        self.assertIn('heightM', obstacle_public)

    def test_roof3d_public_ne_fuit_aucun_champ_interne(self):
        """Non-régression QJ26 : le v1 réel porte des prix ; rien ne sort."""
        public = self._public(layout_v1_qj26())
        texte = json.dumps(public, ensure_ascii=False)
        for interdit in ('prix_achat', 'marge', 'prix_vente', 'savings'):
            self.assertNotIn(interdit, texte)
