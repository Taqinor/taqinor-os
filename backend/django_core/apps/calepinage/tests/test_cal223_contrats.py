"""CAL223 — TESTS DE CONTRAT sur TOUTES les sorties du module.

POURQUOI CE FICHIER EXISTE À CÔTÉ DE ``scripts/check_api_shapes.py``
---------------------------------------------------------------------
La garde de dépôt fait beaucoup, mais elle s'ABSTIENT par construction : « un
doute ne rougit JAMAIS ». Une vue dont la forme n'est pas certaine
statiquement sort du contrat, et son échantillon n'est alors comparé à RIEN.
C'est exactement la porte par laquelle un échantillon dérive en silence.

Ce fichier ferme cette porte, avec trois contrôles qui ne demandent NI base de
données NI réseau :

1. **INVENTAIRE** — tout échantillon du dossier est complet (``endpoint``,
   ``pourquoi``, ``exemple``) et déclaré dans CE fichier : un échantillon neuf
   ne peut pas entrer sans qu'on décide s'il est comparable. C'est le contrôle
   qui empêche la liste de pourrir.
2. **CHEMIN DÉCLARÉ** — le chemin de chaque échantillon du module existe
   vraiment dans ``urls.py`` ou dans une ``@action`` (``url_path=``) des vues.
   Renommer une route côté serveur sans toucher l'échantillon échoue ICI, en
   nommant le chemin. Contrôle TEXTUEL et non ``resolve()`` : charger la
   configuration d'URL complète tire WeasyPrint, absent des postes Windows —
   un test qui ne peut pas tourner chez le développeur ne garde rien.
3. **CLÉS SERVIES** — pour chaque échantillon dont le producteur est
   appelable SANS base, on compare les clés RÉELLEMENT servies à celles de
   l'échantillon, et on ÉCHOUE EN NOMMANT la clé divergente.

Les échantillons dont le producteur exige la base (comparatif de variantes,
moteur, pompage…) sont listés dans ``SANS_PRODUCTEUR_PUR`` avec leur raison :
ils restent couverts par les contrôles 1 et 2 ici, et par
``check_api_shapes.py`` + leurs tests dédiés côté CI.
"""
from __future__ import annotations

import json
import pathlib
import unittest

from apps.calepinage.selectors import (
    SECTIONS_LECTURE_SEULE,
    SECTIONS_PARAMETRES,
    parametres_de_societe,
)
from apps.calepinage.services import site
from apps.calepinage.services.equipements import equipements_du_calepinage
from apps.calepinage.services.lestage import masse_et_lestage
from apps.calepinage.services.modules_stock import (
    modules_disponibles_du_calepinage,
)
from apps.calepinage.services.raccordement import bloc_raccordement
from apps.calepinage.services.reglementaire import composer_dossiers

RACINE = pathlib.Path(__file__).resolve().parent.parent
ECHANTILLONS = RACINE / 'contract_samples'
VUES = RACINE / 'views'

#: Les échantillons du module qui ONT un producteur appelable sans base.
#: ``nom de fichier -> (clé de l'exemple, producteur)``.
#: Le producteur rend le dictionnaire RÉELLEMENT servi.
AVEC_PRODUCTEUR_PUR = ('calepinage_equipements.json',
                       'dossiers_reglementaires.json',
                       'parametres_calepinage.json',
                       'site_imagerie.json',
                       # CALX17 — masse posée + feuille de lestage : producteur
                       # PUR (aucune base) sur un calepinage nu.
                       'calepinage_masse_lestage.json',
                       # CALX244 — le point de raccordement : producteur PUR
                       # (``services/raccordement.py::bloc_raccordement``),
                       # servi par ``views/raccordement.py``.
                       'calepinage_raccordement.json',
                       # CALX109 — le catalogue de modules de la société :
                       # producteur PUR (``services/modules_stock.py``), la
                       # vue ne fait que lui passer le QuerySet du stock.
                       'calepinage_modules_disponibles.json')

#: Les autres, avec la RAISON — aucun n'est oublié, chacun est un choix.
SANS_PRODUCTEUR_PUR = {
    'calepinage_detail.json':
        'sérialiseur DRF sur une instance en base (test dédié CAL1)',
    'calepinage_design_context.json':
        'contexte lu sur le devis et la société en base (CAL231)',
    'calepinage_horizon.json':
        'profil PVGIS lu sur le calepinage en base (CAL92/93)',
    'calepinage_pompage.json':
        'dimensionnement qui lit le catalogue produits en base (CAL155-159)',
    'calepinage_resultat.json':
        'résultat du moteur électrique, lu sur le calepinage en base (CAL244)',
    'calepinage_sorties.json':
        "inventaire qui interroge la géométrie et les documents du "
        "calepinage en base (CAL175)",
    'lead_layout_public.json':
        "endpoint d'une AUTRE app (apps.crm) — hors périmètre de ce module",
    'moteur_calculer.json':
        'appel du moteur pur, couvert par ses propres tests (CAL22)',
    'pose.json': 'appel du moteur de pose, tests dédiés (CAL78)',
    'variantes_comparer.json':
        'comparatif qui lit les variantes en base (CAL21)',
    'zones.json':
        'entrée du moteur (pas une réponse serveur) — couvert par CAL22',
    # CALX4 / CALX5 — le document écrit par la simulation dans
    # ``Calepinage.resultat``. Son producteur EXISTE désormais
    # (``services/simulation.py``), mais il lit le devis, le stock et les
    # réglages en base : la forme est affirmée sans base par
    # apps/calepinage/tests/test_calx5_simulation.py.
    'calepinage_simulation.json':
        'document écrit par services/simulation.py (CALX5) : son producteur '
        'lit le document, les fiches produit et les réglages société en base',
    # CALX45
    'calepinage_du_devis.json':
        "endpoint d'une AUTRE app (apps.ventes, DevisSerializer) — couvert "
        'par apps/ventes/tests/test_calx46_calepinage_du_devis.py',
    # CALX25
    'calepinage_releve.json':
        'enveloppe (`releve_en_ligne`) lue sur un `ReleveTerrain` SAUVÉ en '
        'base (photos, auteur) — la géométrie PURE (`resoudre_chaines`) est '
        'affirmée sans base par tests/test_calx25_releve_contrat.py',

    # CALX39
    'calepinage_import_plan.json':
        "réponse d'une porte MULTIPART : son producteur exige un plan "
        'déposé (DXF/PDF réel) et un calepinage résolu — affirmé par '
        'apps/calepinage/tests/test_calx39_import_plan.py, qui appelle la '
        "porte sur un DXF fabriqué par ezdxf",

    # CALX35
    'calepinage_dupliquer.json':
        'la réponse décrit la COPIE enregistrée (identifiant, référence '
        'dérivée, variantes comptées) : son producteur exige la base — '
        'couvert par apps/calepinage/tests/test_calx35_dupliquer.py',

    # CALX141
    'calepinage_pertes_cascade.json':
        "détail du bloc `resultat['cascade']` servi par GET resultat/ "
        '(CALX70) : son producteur est services/chaine_pertes.py '
        '(CALX147), pas encore écrit — la forme est affirmée sans base par '
        'apps/calepinage/tests/test_calx141_contrat_cascade.py',

    # CALX143
    'calepinage_meteo.json':
        "détail du bloc `resultat['meteo']` servi par GET resultat/ "
        '(CALX70) : la provenance est aujourd’hui éparse (pvgis_serie, '
        'horizon, production) et son assembleur arrive avec CALX150 — la '
        'forme est affirmée sans base, depuis une réponse PVGIS rejouée, par '
        'apps/calepinage/tests/test_calx143_contrat_meteo.py',

    # CALX144
    'calepinage_incertitude.json':
        "détail du bloc `resultat['incertitude']` servi par GET resultat/ "
        '(CALX70) : son producteur est services/incertitude.py (CALX185, '
        'CALX186), pas encore écrit — la forme et les deux règles dures '
        '(aucun σ sans source, aucun P50 recopié en P90) sont affirmées sans '
        'base par '
        'apps/calepinage/tests/test_calx144_contrat_incertitude.py',

    # CALX142
    'calepinage_serie_horaire.json':
        "détail du bloc `resultat['serie_horaire']` PERSISTÉ : il n'est pas "
        'recopié par GET resultat/ (D-CALX 14, volume) et son seul lecteur '
        "est l'export CSV, qui rend un FICHIER — aucune forme JSON servie à "
        'comparer ; la série est écrite par CALX150 et la forme est affirmée '
        "sans base, par l'exporteur lui-même, dans "
        'apps/calepinage/tests/test_calx142_contrat_serie.py',

    # CALX201
    'electrique_equipements.json':
        "FRAGMENT du document `roof_layout` v2 (clé racine OPTIONNELLE "
        '`electrical.equipements[]`), pas une réponse serveur : la route '
        'GET layout/ rend `{roof_layout, layout_hash, schema_version}` et '
        "l'écrivain du fragment est l'atelier 3D (CALX219/CALX220) — la "
        'forme est affirmée sans base, contre le schéma et contre la porte '
        "d'import réelle, par "
        'apps/calepinage/tests/test_calx201_contrat_equipements.py',

    # CALX202
    'electrique_cheminements.json':
        'FRAGMENT du document `roof_layout` v2 (clé racine OPTIONNELLE '
        '`electrical.cheminements[]`), pas une réponse serveur : le tracé '
        "est écrit par l'atelier 3D (CALX223) et relu par "
        'services/troncons.py (CALX224) — la forme, les deux refus et la '
        'résolution des références sont affirmées sans base par '
        'apps/calepinage/tests/test_calx202_contrat_cheminements.py',

    # CALX203
    'calepinage_troncons.json':
        'métré et chute TRONÇON PAR TRONÇON : la route arrive avec la vague '
        'ÉLECTRIQUE PRO et son producteur est services/troncons.py '
        '(CALX224-226), pas encore écrit — la forme, les omissions nommées '
        'et la cohérence avec electrique_cheminements.json sont affirmées '
        'sans base par '
        'apps/calepinage/tests/test_calx203_contrat_troncons.py',

    # CALX204
    'calepinage_sld.json':
        "schéma unifilaire ÉDITABLE : GET est servi (views/schema.py) mais "
        'son producteur traverse la conception électrique et la porte '
        'cross-app apps.ventes.selectors.schema_unifilaire_svg, donc la '
        'base ; les deux clés neuves (`blocs`, `edition`) et la règle dure '
        "« `edition` n'est pas une seconde source de vérité du dessin » "
        'sont affirmées sans base par '
        'apps/calepinage/tests/test_calx204_contrat_sld.py',


    # CALX106
    'calepinage_empreinte_osm.json':
        "endpoint d'une AUTRE app (apps.crm, GET leads/<id>/roof-footprint/) "
        '— hors périmètre de ce module ; son producteur '
        '(apps/crm/roof_detect.py::_parse_geometry) est PUR et la forme est '
        'affirmée sans base, depuis des réponses Overpass FIXÉES, par '
        'apps/crm/tests/test_calx106_empreinte_osm.py, et le document lui-'
        'même par '
        'apps/calepinage/tests/test_calx106_contrat_empreinte_osm.py',

    # CALX62
    'calepinage_meteo_fichier.json':
        'réponse de la porte MULTIPART qui dépose une série météo de la '
        'société : son producteur crée une ligne records.Attachment et écrit '
        "dans le magasin d'objets, donc il exige la base — le bloc `meteo` et "
        'le résumé de série sont affirmés sans base, depuis un petit fichier '
        'synthétique, par '
        'apps/calepinage/tests/test_calx62_meteo_fichier.py',
}

#: Contrats posés AVANT leur route (PACT10 : le contrat d'abord, seul, sur
#: `main`) — le contrôle 2 les ignore tant que la tâche nommée n'a pas livré
#: la porte ; retirer l'entrée dans la même tâche que la route.
#: CALX5 a livré ``POST simuler/`` : ``calepinage_simulation.json`` en est
#: SORTI, et le contrôle 2 vérifie désormais sa route comme celle des autres.
POSES_AVANT_LEUR_ROUTE = {
    # CALX203 — `GET calepinages/<pk>/troncons/` : la vue arrive avec la
    # vague ÉLECTRIQUE PRO, le producteur est services/troncons.py (CALX224).
    'calepinage_troncons.json': 'CALX203 — route posée par la vague '
                                'ÉLECTRIQUE PRO (services/troncons.py, '
                                'CALX224-226)',
}

#: Les chemins qui ne sont PAS servis par ce module (aucun url_path à y
#: chercher) : ils appartiennent à une autre app.
HORS_MODULE = ('/api/django/crm/', '/api/django/ventes/')


def _echantillons():
    return sorted(chemin for chemin in ECHANTILLONS.glob('*.json')
                  if not chemin.name.endswith('.schema.json'))


def _charger(nom):
    return json.loads((ECHANTILLONS / nom).read_text(encoding='utf-8'))


def _sources_de_routes():
    textes = [(RACINE / 'urls.py').read_text(encoding='utf-8')]
    textes += [chemin.read_text(encoding='utf-8')
               for chemin in sorted(VUES.glob('*.py'))]
    return '\n'.join(textes)


class Faux:
    """Un calepinage NU : aucun devis, aucun document — donc aucune base."""

    pk = 1
    devis_id = None
    roof_layout = None
    resultat = None
    company = None
    layout_hash = ''
    titre = 'Calepinage 1'

    def __str__(self):
        return self.titre


class InventaireDesEchantillonsTest(unittest.TestCase):
    """Aucun échantillon ne peut entrer sans être décidé."""

    def test_chaque_echantillon_est_complet(self):
        for chemin in _echantillons():
            donnees = _charger(chemin.name)
            for cle in ('endpoint', 'pourquoi', 'exemple'):
                self.assertIn(cle, donnees,
                              f"{chemin.name} : clé « {cle} » absente.")
            self.assertTrue(donnees['endpoint'].strip(), chemin.name)

    def test_chaque_echantillon_est_declare_ici(self):
        connus = set(AVEC_PRODUCTEUR_PUR) | set(SANS_PRODUCTEUR_PUR)
        trouves = {chemin.name for chemin in _echantillons()}
        self.assertEqual(
            sorted(trouves - connus), [],
            "Échantillon non déclaré dans test_cal223_contrats.py : ajoutez-le "
            "à AVEC_PRODUCTEUR_PUR (comparé) ou à SANS_PRODUCTEUR_PUR (avec "
            "sa raison) — un échantillon non décidé dérive en silence.")
        self.assertEqual(sorted(connus - trouves), [],
                         "Échantillon déclaré mais absent du dossier.")


class CheminDeclareTest(unittest.TestCase):
    """Renommer une route sans toucher l'échantillon échoue ICI."""

    def test_chaque_chemin_du_module_existe_dans_les_sources(self):
        sources = _sources_de_routes()
        for chemin in _echantillons():
            donnees = _charger(chemin.name)
            _verbe, _, route = donnees['endpoint'].partition(' ')
            if route.startswith(HORS_MODULE):
                continue
            if chemin.name in POSES_AVANT_LEUR_ROUTE:
                continue
            segment = route.rstrip('/').rsplit('/', 1)[-1]
            if segment.startswith('<'):        # ``calepinages/<int:pk>/``
                continue
            self.assertTrue(
                f"url_path='{segment}'" in sources
                or f"'{segment}/'" in sources
                or f"{segment}/'" in sources,
                f"{chemin.name} : le chemin « {route} » n'est déclaré nulle "
                f"part dans urls.py ni dans une @action du module "
                f"(segment cherché : « {segment} »).")


class ClesServiesTest(unittest.TestCase):
    """La comparaison qui ÉCHOUE EN NOMMANT la clé divergente."""

    def _comparer(self, nom, servi, cle_exemple='exemple'):
        attendu = set(_charger(nom)[cle_exemple])
        obtenu = set(servi)
        self.assertEqual(
            sorted(attendu - obtenu), [],
            f"{nom} : le serveur ne sert PAS la ou les clés "
            f"{sorted(attendu - obtenu)} que l'échantillon promet.")
        self.assertEqual(
            sorted(obtenu - attendu), [],
            f"{nom} : le serveur sert la ou les clés "
            f"{sorted(obtenu - attendu)} que l'échantillon ignore.")

    def test_equipements(self):
        self._comparer('calepinage_equipements.json',
                       equipements_du_calepinage(Faux()))
        self._comparer('calepinage_equipements.json',
                       equipements_du_calepinage(Faux()), 'exemple_vide')

    def test_dossiers_reglementaires(self):
        servi = composer_dossiers(calepinage_id=1, pays='ma', entrees=[],
                                  infos={})
        self._comparer('dossiers_reglementaires.json', servi)
        self._comparer('dossiers_reglementaires.json', servi, 'exemple_vide')

    def test_parametres_de_societe(self):
        # ``kits`` est une clé DÉRIVÉE (CAL246), publiée par la vue et jamais
        # stockée : le sélecteur ne la rend pas, le contrat la porte.
        servi = dict(parametres_de_societe(None))
        for lecture_seule in SECTIONS_LECTURE_SEULE:
            servi[lecture_seule] = []
        self._comparer('parametres_calepinage.json', servi)
        self._comparer('parametres_calepinage.json', servi, 'exemple_vide')
        self.assertEqual(sorted(parametres_de_societe(None)),
                         sorted(SECTIONS_PARAMETRES))

    def test_raccordement(self):
        # CALX244 — ``bloc_raccordement`` est PUR : une conception absente,
        # aucun tronçon, aucun réglage, et les trois blocs sortent quand
        # même (les cinq verdicts omis en nommant ce qui manque).
        servi = bloc_raccordement(None, {}, [], {})
        self._comparer('calepinage_raccordement.json', servi)
        self._comparer('calepinage_raccordement.json', servi, 'exemple_vide')

    def test_masse_lestage(self):
        # CALX17 — ``masse_et_lestage`` sur un calepinage NU ne touche
        # aucune base : ni devis, ni document, ni produit désigné.
        servi = masse_et_lestage(Faux())
        self._comparer('calepinage_masse_lestage.json', servi)
        self._comparer('calepinage_masse_lestage.json', servi,
                       'exemple_vide')

    def test_modules_disponibles(self):
        # CALX109 — le service est PUR : la vue lui passe le QuerySet des
        # produits MODULE de la société, il n'en requête aucun lui-même.
        servi = modules_disponibles_du_calepinage(Faux(), [])
        self._comparer('calepinage_modules_disponibles.json', servi)
        self._comparer('calepinage_modules_disponibles.json', servi,
                       'exemple_vide')

    def test_site_imagerie(self):
        # Cet échantillon décrit la SECTION « imagerie » (CAL46) à l'intérieur
        # de la réponse des réglages : ses sections sont donc un SOUS-ENSEMBLE
        # des sections servies, et ses ``cles`` sont celles du service.
        donnees = _charger('site_imagerie.json')
        for etat in ('exemple', 'exemple_vide',
                     'exemple_section_declaree_sans_valeur'):
            absentes = set(donnees[etat]) - set(SECTIONS_PARAMETRES)
            self.assertEqual(
                sorted(absentes), [],
                f"site_imagerie.json ({etat}) : section(s) {sorted(absentes)} "
                "que le serveur ne sert pas.")
        self.assertEqual(list(donnees['cles']), list(site.CLES))
        self.assertEqual(sorted(site.section_vide()), sorted(donnees['cles']))
        self.assertEqual(
            sorted(donnees['exemple_section_declaree_sans_valeur']
                   ['imagerie']),
            sorted(site.CLES))
