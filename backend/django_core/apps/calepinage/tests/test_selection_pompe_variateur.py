"""CAL158 — pompe + variateur assortis, PARITÉ avec l'écran devis, et la
garde absolue « jamais de m³/jour sans courbe ».

Ce qui est prouvé ici :

* TEST DE PARITÉ — le même jeu de cas que
  ``frontend/src/features/ventes/solar.js`` (``selectPompeByCurve`` /
  ``selectVariateurVeichi``) rend la MÊME pompe et le MÊME variateur côté
  Python : la plus petite pompe dont la courbe tient le débit à la HMT, le
  plus petit variateur VEICHI dont kW ≥ kW pompe, tension assortie ;
* GARDE ABSOLUE — une pompe SANS ``courbe_pompe`` n'est JAMAIS candidate,
  même si elle correspond par ailleurs (kW, tension) : la carte volume est
  ABSENTE pour elle, jamais un débit à zéro ;
* un produit SANS PRIX n'est JAMAIS auto-sélectionné, même s'il est
  techniquement le meilleur candidat — ``sans_prix`` le liste plutôt ;
* une tension incompatible (mono demandé, pompe 380 V seule dispo) écarte
  la candidate et signale ``ecart_phase`` ;
* un variateur insuffisant (aucun VEICHI n'atteint le kW requis) rend
  ``insuffisant: True`` plutôt que le plus gros disponible sous-dimensionné.

Fonctions PURES : ce test n'a besoin d'AUCUNE base de données.

Run :
    python manage.py test apps.calepinage.tests.test_selection_pompe_variateur -v2
"""
import unittest

from apps.calepinage.services.pompage import (
    selection_pompe, selection_variateur,
)

#: Courbe DÉCROISSANTE : plus le débit monte, plus la HMT délivrable baisse
#: (patron constructeur réel, MÊME forme que ``frontend/…/solar.js
#: debitAtHmt`` documente).
COURBE_PETITE = {'debits_m3h': [0, 3, 6, 9], 'hmt_m': [90, 75, 55, 30]}
COURBE_GRANDE = {'debits_m3h': [0, 8, 16, 24], 'hmt_m': [110, 95, 70, 45]}


def _pompes_catalogue():
    return [
        {'id': 1, 'nom': 'Pompe immergée 2.2 kW', 'pompe_kw': 2.2,
         'tension_v': 380, 'prix_vente': 8000, 'courbe_pompe': COURBE_PETITE},
        {'id': 2, 'nom': 'Pompe immergée 4 kW', 'pompe_kw': 4.0,
         'tension_v': 380, 'prix_vente': 15000, 'courbe_pompe': COURBE_GRANDE},
        # Même gabarit que la #1 mais SANS courbe constructeur — jamais
        # candidate (garde absolue CAL158).
        {'id': 3, 'nom': 'Pompe immergée 2.2 kW (sans courbe)',
         'pompe_kw': 2.2, 'tension_v': 380, 'prix_vente': 7500,
         'courbe_pompe': None},
        # Techniquement la meilleure (0,5 kW) mais SANS PRIX — jamais
        # auto-sélectionnée.
        {'id': 4, 'nom': 'Pompe immergée 0.5 kW', 'pompe_kw': 0.5,
         'tension_v': 380, 'prix_vente': 0, 'courbe_pompe': COURBE_PETITE},
        # Même gabarit mais en 220 V mono — candidate seulement si mono
        # demandé.
        {'id': 5, 'nom': 'Pompe immergée 2.2 kW mono', 'pompe_kw': 2.2,
         'tension_v': 220, 'prix_vente': 8200, 'courbe_pompe': COURBE_PETITE},
    ]


def _variateurs_catalogue():
    return [
        {'id': 10, 'nom': 'Variateur VEICHI 3 kW', 'pompe_kw': 3.0,
         'tension_v': 380, 'prix_vente': 3200},
        {'id': 11, 'nom': 'Variateur VEICHI 5.5 kW', 'pompe_kw': 5.5,
         'tension_v': 380, 'prix_vente': 4800},
        {'id': 12, 'nom': 'Afficheur SI22', 'pompe_kw': 0, 'tension_v': 380,
         'prix_vente': 350},
        {'id': 13, 'nom': 'Variateur VEICHI 3 kW mono', 'pompe_kw': 3.0,
         'tension_v': 220, 'prix_vente': 3100},
    ]


class SelectionPompeVariateurTest(unittest.TestCase):
    # ── Parité — jeu de cas committé ────────────────────────────────────
    def test_parite_petit_debit_retient_la_plus_petite_pompe(self):
        pompes = _pompes_catalogue()
        resultat = selection_pompe(
            pompes, hmt=55, debit_souhaite_m3h=5, type_pompe='immerge',
            alim='tri')
        self.assertEqual(resultat['pompe']['id'], 1)
        self.assertEqual(resultat['kw'], 2.2)
        self.assertEqual(resultat['sans_prix'], [])

        variateur = selection_variateur(
            _variateurs_catalogue(), resultat['kw'], 'tri')
        self.assertEqual(variateur['variateur']['id'], 10)
        self.assertFalse(variateur['insuffisant'])

    def test_parite_gros_debit_retient_la_grande_pompe(self):
        pompes = _pompes_catalogue()
        resultat = selection_pompe(
            pompes, hmt=70, debit_souhaite_m3h=14, type_pompe='immerge',
            alim='tri')
        self.assertEqual(resultat['pompe']['id'], 2)
        self.assertEqual(resultat['kw'], 4.0)

        variateur = selection_variateur(
            _variateurs_catalogue(), resultat['kw'], 'tri')
        self.assertEqual(variateur['variateur']['id'], 11)

    # ── Garde absolue : jamais de m³/jour sans courbe ───────────────────
    def test_pompe_sans_courbe_jamais_candidate(self):
        # Seule la pompe #3 (sans courbe, moins chère) « conviendrait » par
        # gabarit — elle ne doit JAMAIS ressortir.
        pompes = [p for p in _pompes_catalogue() if p['id'] in (1, 3)]
        resultat = selection_pompe(
            pompes, hmt=55, debit_souhaite_m3h=5, type_pompe='immerge',
            alim='tri')
        self.assertEqual(resultat['pompe']['id'], 1)

    def test_aucune_pompe_avec_courbe_aucune_selection(self):
        pompes = [p for p in _pompes_catalogue() if p['id'] == 3]
        resultat = selection_pompe(
            pompes, hmt=55, debit_souhaite_m3h=5, type_pompe='immerge',
            alim='tri')
        self.assertIsNone(resultat['pompe'])
        self.assertIsNone(resultat['debit_hmt_m3h'])

    # ── Jamais un produit sans prix ─────────────────────────────────────
    def test_pompe_sans_prix_jamais_auto_selectionnee(self):
        pompes = [p for p in _pompes_catalogue() if p['id'] in (1, 4)]
        resultat = selection_pompe(
            pompes, hmt=55, debit_souhaite_m3h=2, type_pompe='immerge',
            alim='tri')
        # La #4 (0.5 kW, sans prix) serait techniquement meilleure : elle
        # est écartée, la #1 (avec prix) est retenue à sa place.
        self.assertEqual(resultat['pompe']['id'], 1)

    def test_seulement_des_pompes_sans_prix_aucune_selection(self):
        pompes = [p for p in _pompes_catalogue() if p['id'] == 4]
        resultat = selection_pompe(
            pompes, hmt=55, debit_souhaite_m3h=2, type_pompe='immerge',
            alim='tri')
        self.assertIsNone(resultat['pompe'])
        self.assertIn('Pompe immergée 0.5 kW', resultat['sans_prix'])

    # ── Tension / phase ──────────────────────────────────────────────────
    def test_tension_incompatible_ecartee_avec_signalement(self):
        # Seule la pompe mono (220 V) convient par gabarit ; demande TRI.
        pompes = [p for p in _pompes_catalogue() if p['id'] == 5]
        resultat = selection_pompe(
            pompes, hmt=55, debit_souhaite_m3h=2, type_pompe='immerge',
            alim='tri')
        self.assertIsNone(resultat['pompe'])
        self.assertTrue(resultat['ecart_phase'])

    def test_tension_compatible_demandee_retenue(self):
        pompes = [p for p in _pompes_catalogue() if p['id'] == 5]
        resultat = selection_pompe(
            pompes, hmt=55, debit_souhaite_m3h=2, type_pompe='immerge',
            alim='mono')
        self.assertEqual(resultat['pompe']['id'], 5)

    # ── Variateur insuffisant : jamais le plus gros sous-dimensionné ────
    def test_variateur_insuffisant_jamais_le_plus_gros_disponible(self):
        variateurs = [v for v in _variateurs_catalogue() if v['id'] == 10]
        resultat = selection_variateur(variateurs, kw=4.5, alim='tri')
        self.assertIsNone(resultat['variateur'])
        self.assertTrue(resultat['insuffisant'])

    def test_afficheur_jamais_candidat_variateur(self):
        variateurs = [v for v in _variateurs_catalogue() if v['id'] == 12]
        resultat = selection_variateur(variateurs, kw=0.1, alim='tri')
        self.assertIsNone(resultat['variateur'])
