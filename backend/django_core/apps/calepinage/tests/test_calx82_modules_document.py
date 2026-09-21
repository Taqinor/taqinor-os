"""CALX82 — le contrat `modules[]` + `zones[].geometry.moduleId` du v2.

CE QUE CE FICHIER GARDE
-----------------------
Aujourd'hui l'atelier ne connaît qu'UN module physique, codé en dur
(`apps/web/src/lib/roofPro2.ts` : `PANEL2_LONG_M` / `PANEL2_SHORT_M` /
`PANEL2_THICK_M` / `PANEL2_WATT`), et seule sa puissance voyage dans le
document (`panelWatt`). CALX82 ouvre la porte à DEUX modèles sur deux pans —
c'est un contrat, pas un sélecteur : le sélecteur arrive avec les lanes MOD.
Quatre promesses sont affirmées ici :

1. **Les deux clés sont ADDITIVES.** Un document v2 sans `modules` reste
   valide, l'`exemple` du schéma n'a pas bougé, et le même document avec le
   catalogue reste valide lui aussi.
2. **Aucune caractéristique n'est déduite.** Toute valeur d'un modèle est
   SAISIE ou lue d'une fiche, `null` quand la fiche ne la porte pas — jamais
   une dimension standard supposée, jamais un poids déduit d'une surface.
   `source` est OBLIGATOIRE : sans elle, rien ne dit ce qui est engageable.
3. **Un `moduleId` inconnu du catalogue est REFUSÉ**, en nommant le chemin du
   champ. Ce renvoi interne n'est pas exprimable en JSON Schema : il est donc
   prononcé par la porte d'import RÉELLE
   (``services/io_layout.py::valider_document``), et les écrans en héritent.
4. **Aucun prix, aucune marge** n'habite une entrée de catalogue.

`EXEMPLE_MODULES` ci-dessous est le document que les lanes 3D (`apps/web`)
liront TEL QUEL : DEUX modèles, DEUX pans qui n'ont pas le même `moduleId`,
et un modèle dont la fiche ne porte pas tout. Ses nombres sont des valeurs
d'EXEMPLE, plausibles et déclarées comme telles.

Run :
    python manage.py test apps.calepinage.tests.test_calx82_modules_document
"""
from __future__ import annotations

import copy
import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services.io_layout import (
    ImportLayoutRefuse, valider_document,
)

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')
SCHEMA = json.loads((ECHANTILLONS / 'roof_layout_v2.schema.json')
                    .read_text(encoding='utf-8'))

#: Deux modèles d'EXEMPLE. Le premier est lu d'une fiche produit et porte
#: tout ; le second est saisi à la main et laisse `null` ce que personne n'a
#: mesuré — c'est l'état qui fait OMETTRE un calcul en nommant le champ
#: manquant, jamais retomber sur le module d'aujourd'hui.
EXEMPLE_MODULES = [
    {
        'id': 'mod-a',
        'produitId': 4112,
        'libelle': 'Module monocristallin 580 Wc (exemple)',
        'longueurMm': 2278,
        'largeurMm': 1134,
        'epaisseurMm': 35,
        'poidsKg': 27.5,
        'pmaxWc': 580,
        'source': 'fiche produit',
    },
    {
        'id': 'mod-b',
        'produitId': None,
        'libelle': 'Module saisi à la main (exemple)',
        'longueurMm': 1722,
        'largeurMm': 1134,
        'epaisseurMm': None,
        'poidsKg': None,
        'pmaxWc': 440,
        'source': 'saisie atelier',
    },
]

#: Les mots qui n'ont RIEN à faire dans une entrée de catalogue : le document
#: dit ce qu'est un module, jamais ce qu'il coûte (règle fondateur — aucun
#: prix d'achat ni marge dans une sortie client).
INTERDITS = ('prix', 'marge', 'cout', 'achat', 'remise', 'tva')


def document_un_seul_pan():
    """L'exemple du schéma + le catalogue, SANS toucher à ses pans.

    C'est la forme qui sert à prouver l'additivité : retirer les deux clés
    rend le document de départ, octet pour octet.
    """
    document = copy.deepcopy(SCHEMA['exemple'])
    document['modules'] = copy.deepcopy(EXEMPLE_MODULES)
    document['zones'][0]['geometry']['moduleId'] = 'mod-a'
    return document


def document_avec_modules():
    """Le document que les lanes 3D liront : DEUX pans, DEUX modèles.

    L'`exemple` du schéma ne porte qu'UN pan ; le second est ajouté ICI (il
    n'entre pas dans le schéma) parce que « deux modèles » ne se démontre
    qu'avec deux pans qui n'en posent pas le même.
    """
    document = document_un_seul_pan()
    second = copy.deepcopy(document['zones'][0])
    second['id'] = f"{second.get('id', 'pan')}-bis"
    second['label'] = 'Pan Ouest (exemple)'
    second['geometry']['moduleId'] = 'mod-b'
    document['zones'].append(second)
    return document


def validateur():
    """Le validateur 2020-12 — `jsonschema` importé en FONCTION-LOCALE."""
    from jsonschema import Draft202012Validator

    return Draft202012Validator(SCHEMA)


def erreurs(document):
    return [(list(erreur.absolute_path), erreur.message)
            for erreur in validateur().iter_errors(document)]


class CleAdditiveTest(SimpleTestCase):
    """`modules` et `moduleId` sont OPTIONNELLES."""

    def test_le_schema_reste_bien_forme(self):
        from jsonschema import Draft202012Validator

        Draft202012Validator.check_schema(SCHEMA)

    def test_l_exemple_du_schema_ne_porte_pas_le_catalogue(self):
        """La preuve que le document historique n'a pas été réécrit."""
        self.assertNotIn('modules', SCHEMA['exemple'])
        for zone in SCHEMA['exemple'].get('zones', []):
            self.assertNotIn('moduleId', zone.get('geometry', {}))

    def test_un_document_sans_catalogue_reste_valide(self):
        self.assertEqual(erreurs(SCHEMA['exemple']), [])
        self.assertEqual(erreurs({}), [])

    def test_un_document_avec_catalogue_est_valide(self):
        self.assertEqual(erreurs(document_avec_modules()), [])

    def test_un_catalogue_vide_est_valide(self):
        document = copy.deepcopy(SCHEMA['exemple'])
        document['modules'] = []
        self.assertEqual(erreurs(document), [])

    def test_le_catalogue_seul_est_valide(self):
        self.assertEqual(erreurs(document_un_seul_pan()), [])

    def test_retirer_les_cles_rend_le_document_de_depart(self):
        """Définition opérationnelle d'« additif » : rien d'autre ne change."""
        document = document_un_seul_pan()
        document.pop('modules')
        document['zones'][0]['geometry'].pop('moduleId')
        self.assertEqual(document, SCHEMA['exemple'])


class DeuxModelesSurDeuxPansTest(SimpleTestCase):
    """Le document d'exemple prouve ce que CALX82 ouvre."""

    def setUp(self):
        self.document = document_avec_modules()

    def test_deux_modeles_sont_declares(self):
        identifiants = [modele['id'] for modele in self.document['modules']]
        self.assertEqual(len(identifiants), 2)
        self.assertEqual(sorted(identifiants), sorted(set(identifiants)))

    def test_deux_pans_ne_posent_pas_le_meme_modele(self):
        poses = [zone['geometry']['moduleId']
                 for zone in self.document['zones']
                 if 'moduleId' in zone.get('geometry', {})]
        self.assertEqual(len(poses), 2)
        self.assertEqual(len(set(poses)), 2,
                         'Sans deux modèles DIFFÉRENTS, le contrat ne '
                         'prouverait pas ce que CALX82 ouvre.')

    def test_une_fiche_absente_n_est_pas_comblee(self):
        sans_fiche = [modele for modele in self.document['modules']
                      if modele['produitId'] is None]
        self.assertTrue(sans_fiche)
        self.assertIn(None, [modele.get('poidsKg')
                             for modele in self.document['modules']],
                      "L'exemple doit montrer une valeur NON RENSEIGNÉE "
                      '(null) : « non mesuré » n’est pas « zéro ».')


class AucuneValeurInventeeTest(SimpleTestCase):
    """Le schéma décrit une FORME ; il ne livre aucune dimension."""

    def setUp(self):
        self.modele = SCHEMA['$defs']['moduleDocument']

    def test_la_provenance_est_obligatoire(self):
        self.assertEqual(sorted(self.modele['required']),
                         ['id', 'libelle', 'source'])

    def test_aucune_dimension_par_defaut(self):
        for nom, sous_schema in self.modele['properties'].items():
            for interdit in ('default', 'const', 'enum', 'examples'):
                self.assertNotIn(
                    interdit, sous_schema,
                    f'`{nom}` porte « {interdit} » : le schéma livrerait une '
                    f'caractéristique que personne n’a relevée.')

    def test_chaque_dimension_accepte_null(self):
        for nom in ('longueurMm', 'largeurMm', 'epaisseurMm', 'poidsKg',
                    'pmaxWc', 'produitId'):
            self.assertIn('null', self.modele['properties'][nom]['type'],
                          f'`{nom}` doit pouvoir valoir `null` : une fiche '
                          f'qui ne porte pas la valeur ne doit pas forcer '
                          f'une invention.')

    def test_aucun_prix_ni_marge_dans_le_catalogue(self):
        champs = set(self.modele['properties'])
        self.assertEqual(
            champs,
            {'id', 'produitId', 'libelle', 'longueurMm', 'largeurMm',
             'epaisseurMm', 'poidsKg', 'pmaxWc', 'source'})
        for champ in champs:
            for interdit in INTERDITS:
                self.assertNotIn(interdit, champ.lower())


class RefusNommeLeChampTest(SimpleTestCase):
    """C'est la porte d'import RÉELLE qui refuse, et elle nomme le champ."""

    def _refus(self, document):
        with self.assertRaises(ImportLayoutRefuse) as capture:
            valider_document(document)
        return capture.exception

    def test_le_document_de_l_exemple_passe_la_porte(self):
        valider_document(document_avec_modules())

    def test_un_module_inconnu_du_catalogue_nomme_le_champ(self):
        document = document_avec_modules()
        document['zones'][0]['geometry']['moduleId'] = 'mod-fantome'
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'zones.0.geometry.moduleId')
        self.assertIn('mod-fantome', str(refus))
        self.assertIn('modules', str(refus))

    def test_un_module_designe_sans_aucun_catalogue_est_refuse(self):
        document = document_avec_modules()
        document.pop('modules')
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'zones.0.geometry.moduleId')

    def test_un_modele_sans_provenance_nomme_la_cle_source(self):
        document = document_avec_modules()
        del document['modules'][0]['source']
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'modules.0')
        self.assertIn('source', str(refus))

    def test_un_modele_sans_libelle_est_refuse(self):
        document = document_avec_modules()
        del document['modules'][1]['libelle']
        self.assertIn('libelle', str(self._refus(document)))

    def test_une_dimension_negative_nomme_le_champ(self):
        document = document_avec_modules()
        document['modules'][0]['longueurMm'] = -1
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'modules.0.longueurMm')

    def test_un_document_sans_module_pose_passe_la_porte(self):
        """Le cas d'aujourd'hui : aucun catalogue, aucun `moduleId`."""
        valider_document(copy.deepcopy(SCHEMA['exemple']))
