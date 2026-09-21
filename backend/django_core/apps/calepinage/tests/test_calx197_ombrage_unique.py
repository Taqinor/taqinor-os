"""CALX197 — un seul calcul d'ombrage pour un même toit.

Deux moteurs réduisaient la même toiture à deux pertes d'ombrage : la moyenne
pondérée production d'``apps/ventes/etude.py`` (PV70, matrice 12×24) et la
cascade heure par heure du calepinage (CALX147/148/157). Depuis CALX197, quand
le devis porte un calepinage SIMULÉ, l'étude ne calcule plus : elle LIT les
quatre étapes d'ombrage de la cascade et PUBLIE la provenance retenue sous
``origine_ombrage``.

Tous les tests sont des ``SimpleTestCase`` : les sélecteurs de lecture
cross-app sont remplacés par des doublures, aucune base n'est touchée. Les
chemins qui exigent l'ORM (``run_bankable_study`` de bout en bout, qui lit les
réglages de tarification de la société) restent couverts par les tests ventes
existants (PV69/PV70/PV72), non rejouables sur un hôte sans base.
"""
import ast
import pathlib
import types
from unittest import mock

from django.test import SimpleTestCase

from apps.ventes.etude import (
    ETAPES_OMBRAGE_CASCADE,
    ORIGINE_OMBRAGE_CALEPINAGE,
    ORIGINE_OMBRAGE_ETUDE,
    _ombrage_du_calepinage,
    _perte_ombrage_cascade,
    _weighted_shading_loss_pct,
    _zone_production_weights,
    _zone_shading,
)

#: Énergie retirée par l'étape fictive des fixtures (kWh sur 10 000).
ENERGIE_RETIREE_KWH = 1000.0

#: Le module dont CALX197 verrouille la frontière d'import.
SOURCE_ETUDE = (pathlib.Path(__file__).resolve().parents[3]
                / 'apps' / 'ventes' / 'etude.py')

EMPREINTE = 'ab' * 32


def _etape(nom, perte_pct, *, motif=''):
    """Une ligne de cascade à la forme du contrat CALX141 (six clés + rang)."""
    appliquee = not motif
    return {
        'rang': 1,
        'etape': nom,
        'libelle': nom,
        'kwh_avant': 10000.0,
        'kwh_apres': 9000.0 if appliquee else None,
        'perte_kwh': ENERGIE_RETIREE_KWH if appliquee else None,
        'perte_pct': perte_pct,
        'gain': False,
        'source': 'pvgis' if appliquee else None,
        'entree': 'horizon' if appliquee else None,
        'reference': 'PVGIS-SARAH3' if appliquee else None,
        'motif_omission': motif,
    }


def _cascade(etapes, *, hash_entree=EMPREINTE):
    return {
        'etapes': list(etapes),
        'ordre': [e['etape'] for e in etapes],
        'total_pct': None,
        'postes_non_sources': [],
        'hash_entree': hash_entree,
    }


def _resultat(cascade, *, hash_simulation=EMPREINTE):
    return {
        'simulation': {'hash_entree': hash_simulation,
                       'calcule_le': '2026-09-21T10:00:00Z'},
        'cascade': cascade,
    }


def _devis(roof_layout=None):
    return types.SimpleNamespace(pk=7, company=object(),
                                 roof_layout=roof_layout or {})


def _matrice_soir():
    """12×24 : soirée (18 h → 23 h) totalement masquée, le reste plein soleil."""
    ligne = [1.0] * 24
    for heure in range(18, 24):
        ligne[heure] = 0.0
    return [list(ligne) for _ in range(12)]


class TestPerteOmbrageCascade(SimpleTestCase):
    """La composition des quatre étapes d'ombrage de la cascade."""

    def test_les_etapes_sont_celles_de_la_chaine_et_dans_son_ordre(self):
        # Un seul endroit du dépôt déclare l'ordre de la chaîne : les quatre
        # noms lus par l'étude en sortent, ils ne sont pas retapés à côté.
        from apps.calepinage.services.chaine_pertes import ORDRE_ETAPES

        self.assertEqual(
            list(ETAPES_OMBRAGE_CASCADE),
            [nom for nom in ORDRE_ETAPES if nom in ETAPES_OMBRAGE_CASCADE])

    def test_composition_sequentielle_jamais_une_somme(self):
        # 5 % puis 10 % qui s'appliquent l'un après l'autre : 14,5 %, pas 15 %.
        cascade = _cascade([_etape('horizon', 5.0),
                            _etape('ombrage_proche', 10.0)])
        self.assertEqual(_perte_ombrage_cascade(cascade), 14.5)

    def test_les_postes_hors_ombrage_ne_comptent_pas(self):
        cascade = _cascade([_etape('horizon', 5.0),
                            _etape('thermique', 8.0),
                            _etape('onduleur', 2.0)])
        self.assertEqual(_perte_ombrage_cascade(cascade), 5.0)

    def test_une_etape_omise_est_ignoree_jamais_zero_pourcent(self):
        cascade = _cascade([
            _etape('horizon', 5.0),
            _etape('ombrage_proche', None,
                   motif="Aucune matrice d'ombrage saisie : étape OMISE."),
        ])
        self.assertEqual(_perte_ombrage_cascade(cascade), 5.0)

    def test_aucune_etape_mesuree_rend_none(self):
        cascade = _cascade([
            _etape('horizon', None, motif="Aucun profil d'horizon saisi."),
            _etape('inter_rangees', None, motif='Aucune rangée posée.'),
        ])
        self.assertIsNone(_perte_ombrage_cascade(cascade))

    def test_cascade_vide_ou_illisible_rend_none(self):
        self.assertIsNone(_perte_ombrage_cascade(_cascade([])))
        self.assertIsNone(_perte_ombrage_cascade({}))
        self.assertIsNone(_perte_ombrage_cascade(None))
        self.assertIsNone(_perte_ombrage_cascade({'etapes': 'des étapes'}))

    def test_les_quatre_etapes_se_composent(self):
        cascade = _cascade([_etape(nom, 10.0)
                            for nom in ETAPES_OMBRAGE_CASCADE])
        # 1 − 0,9^4 = 34,39 %
        self.assertEqual(_perte_ombrage_cascade(cascade), 34.39)


class TestOmbrageDuCalepinage(SimpleTestCase):
    """La lecture cross-app : trois conditions, sinon le chemin d'hier."""

    def _patch(self, *, retenu, calepinage):
        return (
            mock.patch('apps.calepinage.selectors.calepinage_retenu_pour_devis',
                       return_value=retenu),
            mock.patch('apps.calepinage.selectors.calepinage_du_devis',
                       return_value=calepinage),
        )

    def _lire(self, *, retenu, resultat):
        calepinage = types.SimpleNamespace(resultat=resultat)
        p_retenu, p_cal = self._patch(retenu=retenu, calepinage=calepinage)
        with p_retenu as m_retenu, p_cal as m_cal:
            valeur = _ombrage_du_calepinage(_devis())
        return valeur, m_retenu, m_cal

    def test_calepinage_simule_rend_la_perte_de_la_cascade(self):
        valeur, m_retenu, _ = self._lire(
            retenu={'id': 3, 'kwc': 10.0, 'nb_modules': 20,
                    'planche_url': '/calepinage/3'},
            resultat=_resultat(_cascade([_etape('horizon', 5.0),
                                         _etape('ombrage_proche', 10.0)])))
        self.assertEqual(valeur, 14.5)
        m_retenu.assert_called_once()

    def test_aucune_variante_retenue_rend_none(self):
        valeur, _, m_cal = self._lire(retenu=None, resultat=_resultat(
            _cascade([_etape('horizon', 5.0)])))
        self.assertIsNone(valeur)
        # La lecture s'arrête au premier sélecteur : rien n'est ouvert ensuite.
        m_cal.assert_not_called()

    def test_calepinage_pose_mais_jamais_simule_rend_none(self):
        valeur, _, _ = self._lire(
            retenu={'id': 3, 'kwc': None, 'nb_modules': None,
                    'planche_url': '/calepinage/3'},
            resultat=_resultat(_cascade([_etape('horizon', 5.0)]),
                               hash_simulation=''))
        self.assertIsNone(valeur)

    def test_cascade_calculee_sur_un_autre_document_rend_none(self):
        valeur, _, _ = self._lire(
            retenu={'id': 3, 'kwc': 10.0, 'nb_modules': 20,
                    'planche_url': '/calepinage/3'},
            resultat=_resultat(_cascade([_etape('horizon', 5.0)],
                                        hash_entree='cd' * 32)))
        self.assertIsNone(valeur)

    def test_resultat_sans_cascade_rend_none(self):
        valeur, _, _ = self._lire(
            retenu={'id': 3, 'kwc': 10.0, 'nb_modules': 20,
                    'planche_url': '/calepinage/3'},
            resultat={'simulation': {'hash_entree': EMPREINTE}})
        self.assertIsNone(valeur)

    def test_devis_sans_societe_ne_lit_rien(self):
        with mock.patch(
                'apps.calepinage.selectors.calepinage_retenu_pour_devis') as m:
            self.assertIsNone(_ombrage_du_calepinage(
                types.SimpleNamespace(pk=7, company=None)))
            m.assert_not_called()

    def test_une_lecture_impossible_ne_leve_jamais(self):
        with mock.patch(
                'apps.calepinage.selectors.calepinage_retenu_pour_devis',
                side_effect=RuntimeError('base indisponible')):
            with self.assertLogs('apps.ventes.etude', level='WARNING') as logs:
                self.assertIsNone(_ombrage_du_calepinage(_devis()))
        self.assertIn('CALX197', logs.output[0])


class TestZoneShadingUneSeuleVerite(SimpleTestCase):
    """Ce que la zone publie selon qui a mesuré l'ombrage."""

    def setUp(self):
        self.parts = [1.0 / 12.0] * 12
        self.matrice = _matrice_soir()

    def test_sans_calepinage_le_chemin_pv70_est_intact(self):
        devis = _devis({'shading12x24': self.matrice})
        perte, matrice = _zone_shading(devis, {'label': 'Pan Sud'}, 0,
                                       self.parts)
        attendu = _weighted_shading_loss_pct(
            self.matrice, _zone_production_weights(self.parts))
        self.assertEqual(perte, attendu)
        self.assertEqual(matrice, self.matrice)

    def test_avec_calepinage_la_matrice_n_est_meme_pas_ouverte(self):
        devis = _devis({'shading12x24': self.matrice})
        perte, matrice = _zone_shading(devis, {'label': 'Pan Sud'}, 0,
                                       self.parts, ombrage_calepinage=14.5)
        self.assertEqual(perte, 14.5)
        self.assertIsNone(matrice)
        # Le chiffre publié n'est PAS celui que la matrice aurait produit :
        # c'est bien le moteur du calepinage qui a parlé, et lui seul.
        self.assertNotEqual(perte, _weighted_shading_loss_pct(
            self.matrice, _zone_production_weights(self.parts)))

    def test_un_ombrage_nul_mesure_par_la_cascade_reste_zero(self):
        # 0 % venant de la cascade est une MESURE, pas une absence : il ne
        # doit pas rouvrir le chemin de l'étude (``None`` seul le fait).
        devis = _devis({'shading12x24': self.matrice})
        perte, matrice = _zone_shading(devis, {'label': 'Pan Sud'}, 0,
                                       self.parts, ombrage_calepinage=0.0)
        self.assertEqual(perte, 0.0)
        self.assertIsNone(matrice)

    def test_les_deux_origines_sont_les_seules_publiables(self):
        self.assertEqual(
            (ORIGINE_OMBRAGE_ETUDE, ORIGINE_OMBRAGE_CALEPINAGE),
            ('etude', 'calepinage'))


class TestFrontiereSansCycle(SimpleTestCase):
    """`apps.ventes` lit par les SÉLECTEURS — ni modèles, ni services."""

    def setUp(self):
        self.source = SOURCE_ETUDE.read_text(encoding='utf-8')
        self.arbre = ast.parse(self.source)

    def _imports_calepinage(self):
        for noeud in ast.walk(self.arbre):
            if isinstance(noeud, ast.ImportFrom) and noeud.module:
                if noeud.module.startswith('apps.calepinage'):
                    yield noeud.module
            elif isinstance(noeud, ast.Import):
                for alias in noeud.names:
                    if alias.name.startswith('apps.calepinage'):
                        yield alias.name

    def test_seuls_les_selecteurs_sont_importes(self):
        modules = sorted(set(self._imports_calepinage()))
        self.assertEqual(modules, ['apps.calepinage.selectors'])

    def test_aucun_import_calepinage_au_chargement_du_module(self):
        # Import FONCTION-LOCAL obligatoire : un import en tête de fichier
        # rouvrirait le cycle de chargement que la frontière existe pour
        # empêcher.
        for noeud in self.arbre.body:
            if isinstance(noeud, ast.ImportFrom) and noeud.module:
                self.assertFalse(
                    noeud.module.startswith('apps.calepinage'),
                    'apps/ventes/etude.py importe le calepinage au chargement')
            elif isinstance(noeud, ast.Import):
                for alias in noeud.names:
                    self.assertFalse(
                        alias.name.startswith('apps.calepinage'),
                        'apps/ventes/etude.py importe le calepinage au '
                        'chargement')
