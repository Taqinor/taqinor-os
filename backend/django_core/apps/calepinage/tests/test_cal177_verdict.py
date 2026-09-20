"""CAL177 — le verdict imprimé est ÉGAL à celui de l'API des variantes.

Le moteur ne rend pas un simple verdict : il rend un RÉGIME DE PREUVE (méthode,
exactitude, optimalité, borne supérieure, marges mesurées). Jusqu'ici, seul le
studio AO le consommait — aucune pièce imprimable ne le portait. Un compte de
modules SANS son régime n'est pas opposable.

La garantie vérifiée ici est une ÉGALITÉ : pour le MÊME résultat, le verdict
recopié par la note et celui que publie ``selectors._ligne_comparaison`` (la
source de l'API ``comparer``) disent la même chose, clé par clé. Un écart entre
l'écran et la pièce remise, c'est l'incident du 27/07/2026 sous un autre nom.

Essais PURS : les deux données d'essai sont les ÉCHANTILLONS DE CONTRAT
committés (``variantes_comparer.json``, ``pose.json``), jamais un dictionnaire
réécrit à la main.

Run :
    python manage.py test apps.calepinage.tests.test_cal177_verdict -v2
"""
import copy
import json
import pathlib
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.calepinage import selectors
from apps.calepinage.services.note_calcul import (
    CLES_MARGES, construire_note_calcul, html_de_note_calcul,
    verdict_de_preuve,
)

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]


def echantillon(nom):
    return json.loads((RACINE_APP / 'contract_samples' / f'{nom}.json')
                      .read_text(encoding='utf-8'))


#: La MESURE d'une variante telle que le comparateur la lit : c'est la forme
#: PLATE que l'API `comparer` republie.
LIGNE_VARIANTE = echantillon('variantes_comparer')['exemple']['lignes'][0]

#: Le résultat BRUT du moteur : le régime y vit sous `preuve`.
RESULTAT_MOTEUR = echantillon('pose')['exemple']


def mesures_de_variante():
    """Un ``resultat`` de variante, reconstruit depuis la ligne publiée.

    On ne réécrit rien : on reprend les clés que la ligne du contrat porte,
    puisque ce sont EXACTEMENT celles que ``_ligne_comparaison`` a lues dans
    le ``resultat`` de la variante.
    """
    ligne = copy.deepcopy(LIGNE_VARIANTE)
    return {cle: ligne[cle] for cle in (
        'total_modules', 'kwc', 'total_optimal', 'optimal', 'methode',
        'orientation', 'marge_troncon_min', 'marge_bande_min', 'marges',
        'production', 'version_moteur', 'entree_hash')}


class EgaliteAvecLApiVariantesTest(SimpleTestCase):
    def setUp(self):
        self.resultat = mesures_de_variante()
        self.variante = SimpleNamespace(pk=11, nom='Variante retenue',
                                        retenue=True, resultat=self.resultat)
        self.ligne = selectors._ligne_comparaison(self.variante, {}, 1)
        self.verdict = verdict_de_preuve(self.resultat)

    def test_le_regime_imprime_est_celui_de_l_api(self):
        for cle in ('methode', 'optimal', 'total_optimal'):
            self.assertEqual(self.verdict['regime'][cle], self.ligne[cle],
                             'divergence sur « %s »' % cle)

    def test_les_marges_imprimees_sont_celles_de_l_api(self):
        self.assertEqual(self.verdict['marge_troncon_min'],
                         self.ligne['marge_troncon_min'])
        self.assertEqual(self.verdict['marge_bande_min'],
                         self.ligne['marge_bande_min'])
        for cle in CLES_MARGES:
            self.assertEqual(self.verdict['marges'][cle],
                             (self.ligne['marges'] or {}).get(cle),
                             'divergence sur la marge « %s »' % cle)

    def test_une_marge_non_mesuree_reste_nulle_jamais_zero(self):
        # La 2e ligne du contrat porte `marge_bande_min` mesurée ; la 1re, non.
        resultat = mesures_de_variante()
        resultat['marge_bande_min'] = None
        resultat['marges'] = dict(resultat['marges'], bande_min_cm=None)
        verdict = verdict_de_preuve(resultat)
        self.assertIsNone(verdict['marge_bande_min'])
        self.assertIsNone(verdict['marges']['bande_min_cm'])


class RegimeDuMoteurBrutTest(SimpleTestCase):
    """Le même régime, écrit sous ``preuve`` par le moteur publié."""

    def test_le_regime_est_lu_sous_preuve(self):
        verdict = verdict_de_preuve(RESULTAT_MOTEUR)
        preuve = RESULTAT_MOTEUR['preuve']
        for cle in ('methode', 'methode_exacte', 'optimal', 'total_retenu',
                    'total_optimal', 'borne_superieure', 'pas_cm'):
            self.assertEqual(verdict['regime'][cle], preuve[cle])
        self.assertEqual(verdict['controles'], preuve['controles'])
        self.assertEqual(verdict['marges']['troncon_min_cm'],
                         RESULTAT_MOTEUR['marges']['troncon_min_cm'])

    def test_les_motifs_de_non_engageabilite_remontent_tels_quels(self):
        resultat = copy.deepcopy(RESULTAT_MOTEUR)
        resultat['engageable'] = False
        resultat['motifs_non_engageable'] = ['Obstacle OBS-1 non coté']
        verdict = verdict_de_preuve(resultat)
        self.assertFalse(verdict['engageable'])
        self.assertEqual(verdict['motifs_non_engageable'],
                         ['Obstacle OBS-1 non coté'])

    def test_un_resultat_sans_regime_ne_fabrique_aucune_valeur(self):
        verdict = verdict_de_preuve({})
        self.assertTrue(all(valeur is None
                            for valeur in verdict['regime'].values()))
        self.assertTrue(all(valeur is None
                            for valeur in verdict['marges'].values()))


class SectionImprimeeTest(SimpleTestCase):
    def test_la_note_porte_la_section_verdict_de_preuve(self):
        resultat = copy.deepcopy(
            echantillon('calepinage_resultat')['exemple'])
        # Le régime PLAT s'ajoute à l'agrégat ; on n'ÉCRASE pas `production`,
        # qui porte la source d'irradiance sans laquelle la note refuse.
        for cle, valeur in mesures_de_variante().items():
            if cle not in ('production', 'kwc', 'version_moteur'):
                resultat[cle] = valeur
        note = construire_note_calcul(resultat, site={})
        html = html_de_note_calcul(note)
        self.assertIn('Verdict de preuve', html)
        self.assertIn('programmation_dynamique', html)
        self.assertIn('Optimum prouvé', html)

    def test_une_grandeur_non_mesuree_s_affiche_non_mesure(self):
        note = construire_note_calcul(
            dict(copy.deepcopy(echantillon('calepinage_resultat')['exemple']),
                 marges={'troncon_min_cm': None, 'bande_min_cm': None,
                         'rangee_critique': None, 'obstacle_critique': None}),
            site={})
        html = html_de_note_calcul(note)
        # « 0 cm » signifierait « au ras » — ce n'est pas « non mesuré ».
        for libelle in ('Marge minimale de tronçon (cm)',
                        'Marge minimale de bande (cm)'):
            self.assertIn('<th>%s</th><td>non mesuré</td>' % libelle, html)
