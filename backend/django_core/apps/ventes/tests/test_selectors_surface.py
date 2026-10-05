# -*- coding: utf-8 -*-
"""SPL131 — golden de la surface publique de ``apps.ventes.selectors``
capturé AVANT sa découpe par propriétaire (piste SPL143-SPL147, déplacements
purs derrière une FAÇADE ré-exportante).

* ``PAR_PROPRIETAIRE`` — les noms que chaque déplacement sort de
  ``selectors.py`` (facturation, calepinage, cadence, publicité, portail,
  stock) ; tant que leur propriétaire n'est pas dans ``PLACE``, chacun existe
  sur ``apps.ventes.selectors`` et y est DÉFINI.
* ``RESTENT`` — le noyau d'argent qui ne bouge pas (``.importlinter`` nomme
  ``apps.ventes.selectors`` dans ses arêtes ignorées).
* ``fixtures/golden_selectors_corps.json`` — sha256 de ``ast.dump`` de chaque
  symbole à déplacer, retrouvé PAR NOM dans ``selectors*.py`` (fonction,
  classe ou affectation de niveau module) : un corps modifié pendant un
  déplacement rougit, un symbole défini deux fois (jumeau) aussi.
* ``PLACE`` (vide ici) — rempli par chaque déplacement : ``propriétaire →
  module attendu``. Alors : pour un nom ré-exporté,
  ``getattr(selectors, n) is getattr(module, n)`` (la façade est un IMPORT,
  jamais ``nom = _mod.nom`` : ``check_api_shapes._find_function`` ne suit que
  les ``FunctionDef`` et les imports) ; pour un nom NON ré-exporté (``PRIVES``,
  0 référence hors ``selectors.py``), ABSENCE sur ``selectors`` — aucun jumeau.

Le golden ne se régénère JAMAIS pour faire passer un déplacement : un golden
rouge est un bug du déplacement (NE PAS FAIRE du plan transverse).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_selectors_surface"
"""
import ast
import hashlib
import importlib
import json
from pathlib import Path

from django.test import SimpleTestCase

VENTES = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / 'fixtures' / \
    'golden_selectors_corps.json'

#: Texte des tâches SPL143-SPL147 (se repérer par NOM de symbole).
PAR_PROPRIETAIRE = {
    # SPL143 → selectors_facturation.py (29 fonctions + _SCORE_BANDS)
    'facturation': [
        'compter_factures', 'factures_echues', 'get_facture_scoped',
        'releve_client_portail', 'releve_client_pdf_bytes',
        'paiements_des_factures', 'paiements_totaux_par_mode',
        '_SCORE_BANDS', '_score_to_letter', '_retard_reel_jours',
        'comportement_paiement', 'date_encaissement_prevue',
        'references_factures', 'references_avoirs',
        'encours_clients_par_tiers', 'encours_ouvert_par_tiers',
        'reste_du_factures_brouillon', 'ca_devis_factures_par_clients',
        'acompte_paye_pour_devis', 'etat_recouvrement_client',
        'analyse_facturation', 'devis_a_facturer', 'tranche_facturee',
        'jours_impaye_facture', 'montants_factures_par_devis',
        'carnet_commande_par_mois', 'factures_via_bon_commande',
        'factures_du_devis', 'devis_deja_facture', 'kpis_factures',
    ],
    # SPL144 → selectors_calepinage.py (11 + 2 constantes)
    'calepinage': [
        'conception_pour_lead', 'calepinage_du_devis',
        'schema_unifilaire_svg', 'lignes_produits_calepinage',
        'peremption_layout_devis', 'devis_brouillon_pour_layout',
        'STATUT_RECALCULABLE', 'comparaison_calepinage_devis',
        '_config_carte', 'SECTIONS_ATELIER_3D', '_reglages_atelier',
        'devis_concevables', 'contexte_conception_devis',
    ],
    # SPL145 → selectors_cadence.py (9 + DECLENCHEUR_PEREMPTION_JOURS)
    'cadence': [
        'devis_action_requise', '_ligne_action_requise',
        '_brouillon_relance_engagement', 'DECLENCHEUR_PEREMPTION_JOURS',
        'dates_declencheurs', 'marquer_declencheur',
        '_date_declencheur_heritee', 'declencheurs_actifs',
        'engagement_proposition_du_lead',
        'annotations_engagement_proposition',
    ],
    # SPL146 → selectors_publicite.py (9)
    'publicite': [
        'devis_value_for_lead', '_client_contact', '_devis_contact',
        'devis_view_tracking_segments', 'expired_devis_contacts',
        'signed_clients_cross_sell_segments',
        'devis_accepted_totals_by_lead',
        'signature_velocity_by_month_and_mode', 'faits_temoignage_devis',
    ],
    # SPL147 → selectors_portail.py (8)
    'portail': [
        'devis_envoyes_du_client', 'devis_du_client_portail',
        '_date_correction_apres_envoi', 'devis_du_client_portail_obj',
        'factures_du_client_portail', 'facture_du_client_portail',
        'facture_est_payable_portail', 'resume_portail_client',
    ],
    # SPL147 → selectors_stock.py (6)
    'stock': [
        'frequence_co_achat', 'compatibilites_du_produit',
        'verdict_panneau_onduleur', 'verdict_batterie_onduleur',
        'classer_produit_nom', 'devis_utilisant_produit',
    ],
}

#: Noms déplacés mais NON ré-exportés par la façade (0 référence hors
#: ``selectors.py``, grep des tâches) : après déplacement ils sont ABSENTS
#: de ``apps.ventes.selectors``.
PRIVES = {
    '_SCORE_BANDS', '_score_to_letter', '_retard_reel_jours',
    '_config_carte', '_reglages_atelier', 'STATUT_RECALCULABLE',
    'SECTIONS_ATELIER_3D',
    '_ligne_action_requise', '_brouillon_relance_engagement',
    '_date_declencheur_heritee',
    '_client_contact', '_devis_contact',
    '_date_correction_apres_envoi',
}

#: Le noyau d'argent qui RESTE sur ``apps.ventes.selectors``.
RESTENT = [
    'TAUX_TVA_REFERENTIEL', 'ligne_compte_dans_totaux', 'tva_buckets',
    '_absorber_arrondi', '_canonical_totaux', 'multi_villa_totaux',
    'totaux_multi_proprietes', 'nombre_proprietes', 'puissance_kwc_projet',
]

#: propriétaire → module attendu ; rempli par chaque déplacement (ex.
#: SPL143 : ``PLACE['facturation'] = 'apps.ventes.selectors_facturation'``).
PLACE = {}


def _fichiers_selectors():
    return [VENTES / 'selectors.py'] + sorted(VENTES.glob('selectors_*.py'))


def _definitions():
    """{nom: [(fichier, noeud)]} des définitions de niveau module de
    ``selectors*.py`` (fonction, classe, affectation à un seul nom)."""
    trouves = {}
    for chemin in _fichiers_selectors():
        arbre = ast.parse(chemin.read_text(encoding='utf-8'))
        for noeud in arbre.body:
            noms = []
            if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef)):
                noms = [noeud.name]
            elif isinstance(noeud, ast.Assign):
                noms = [c.id for c in noeud.targets
                        if isinstance(c, ast.Name)]
            elif isinstance(noeud, ast.AnnAssign) and isinstance(
                    noeud.target, ast.Name):
                noms = [noeud.target.id]
            for nom in noms:
                trouves.setdefault(nom, []).append((chemin.name, noeud))
    return trouves


def _empreinte(noeud):
    return hashlib.sha256(ast.dump(noeud).encode('utf-8')).hexdigest()


def capturer_corps():
    trouves = _definitions()
    corps = {}
    for noms in PAR_PROPRIETAIRE.values():
        for nom in noms:
            (_fichier, noeud), = trouves[nom]
            corps[nom] = _empreinte(noeud)
    return dict(sorted(corps.items()))


def _golden():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


class SurfaceSelectorsVentes(SimpleTestCase):

    def test_comptes_par_proprietaire(self):
        comptes = {p: len(n) for p, n in PAR_PROPRIETAIRE.items()}
        self.assertEqual(comptes, {
            'facturation': 30, 'calepinage': 13, 'cadence': 10,
            'publicite': 9, 'portail': 8, 'stock': 6})
        tous = [n for noms in PAR_PROPRIETAIRE.values() for n in noms]
        self.assertEqual(len(tous), len(set(tous)))
        self.assertLessEqual(PRIVES, set(tous))

    def test_noms_en_place_sur_la_facade(self):
        from apps.ventes import selectors
        definis = _definitions()
        for proprietaire, noms in PAR_PROPRIETAIRE.items():
            module_attendu = PLACE.get(proprietaire)
            for nom in noms:
                with self.subTest(proprietaire=proprietaire, nom=nom):
                    if module_attendu is None:
                        self.assertTrue(hasattr(selectors, nom))
                        self.assertEqual(
                            [f for f, _n in definis.get(nom, [])],
                            ['selectors.py'])
                        continue
                    module = importlib.import_module(module_attendu)
                    self.assertTrue(hasattr(module, nom))
                    self.assertEqual(
                        [f for f, _n in definis.get(nom, [])],
                        [module_attendu.rsplit('.', 1)[1] + '.py'],
                        'aucun jumeau : %s défini UNE fois, dans %s'
                        % (nom, module_attendu))
                    if nom in PRIVES:
                        self.assertFalse(
                            hasattr(selectors, nom),
                            '%s est privé : pas de ré-export' % nom)
                    else:
                        self.assertIs(getattr(selectors, nom),
                                      getattr(module, nom))

    def test_le_noyau_d_argent_reste(self):
        from apps.ventes import selectors
        arbre = ast.parse((VENTES / 'selectors.py').read_text(
            encoding='utf-8'))
        locaux = set()
        for noeud in arbre.body:
            if isinstance(noeud, (ast.FunctionDef, ast.ClassDef)):
                locaux.add(noeud.name)
            elif isinstance(noeud, ast.Assign):
                locaux |= {c.id for c in noeud.targets
                           if isinstance(c, ast.Name)}
            elif isinstance(noeud, ast.ImportFrom) and noeud.level == 1 \
                    and not (noeud.module or '').startswith('selectors_'):
                locaux |= {a.asname or a.name for a in noeud.names}
        for nom in RESTENT:
            with self.subTest(nom=nom):
                self.assertTrue(hasattr(selectors, nom))
                self.assertIn(nom, locaux)

    def test_corps_couvrent_les_noms(self):
        corps = _golden()['corps']
        tous = {n for noms in PAR_PROPRIETAIRE.values() for n in noms}
        self.assertEqual(set(corps), tous)
        self.assertEqual(len(corps), 76)

    def test_empreintes_des_corps_identiques(self):
        definis = _definitions()
        for nom, empreinte in _golden()['corps'].items():
            with self.subTest(nom=nom):
                occurrences = definis.get(nom, [])
                self.assertEqual(len(occurrences), 1,
                                 '%s : %d définition(s) dans selectors*.py'
                                 % (nom, len(occurrences)))
                self.assertEqual(_empreinte(occurrences[0][1]), empreinte)
