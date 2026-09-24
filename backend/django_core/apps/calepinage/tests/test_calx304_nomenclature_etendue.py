"""CALX304 — la section « Nomenclature » du rapport, SANS PRIX, et
l'extension de ``export_tableur.table_nomenclature`` aux lignes de
structure/câbles/protections/terre.

Ce qui est prouvé ici, PUREMENT (aucune base — ``export_tableur.py`` et
``services/rapport/nomenclature.py`` n'importent Django nulle part au
niveau du module) :

* un résultat SANS câble calculé (``resultat['nomenclature']`` sans
  catégorie « Câblage ») n'ajoute AUCUNE ligne câble ;
* une protection retenue « décision société »
  (``services/protections.py::MENTION_SOCIETE``) est imprimée avec cette
  mention EXACTE ;
* une ligne dont le stock publie une référence l'imprime ; une ligne dont
  la quantité n'est PAS un nombre calculé est OMISE, jamais mise à 0 ;
* ``verifier_absence_de_prix`` PASSE sur la table étendue (aucun mot
  d'argent introduit par l'extension) — et REFUSE toujours un mot d'argent
  glissé dans une désignation, EN LE NOMMANT ;
* les TROIS colonnes historiques (``Désignation``/``Quantité``/``Unité``)
  et les assertions de ``test_cal179_export_tableur.py`` (rejouées ici sur
  la MÊME fixture, ``contract_samples/calepinage_resultat.json``) restent
  vraies — la ligne module reste ``lignes[0]``, inchangée ;
* la section ``nomenclature`` du rapport réutilise CETTE table (aucune
  seconde lecture, aucun recalcul).

Run :
    cd backend/django_core
    python -m pytest \
        apps/calepinage/tests/test_calx304_nomenclature_etendue.py -q
"""
import copy
import json
import pathlib
import unittest
from html import escape

from apps.calepinage.services.export_tableur import (
    ExportRefuse, table_nomenclature, verifier_absence_de_prix,
)
from apps.calepinage.services.rapport.nomenclature import (
    html_de_section, html_de_table,
)

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
RESULTAT_CONTRAT = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_resultat.json')
    .read_text(encoding='utf-8'))['exemple']

RESULTAT_BASE = {
    'pose': {'total_modules': 12, 'kwc': 8.64, 'puissance_module_wc': 720},
    'electrique': {'onduleurs': [{'reference': 'ONDULEUR-ESSAI-1',
                                  'nombre': 1}]},
}

MOTIF = "motif de test — section nomenclature"


def contexte(resultat, langue='fr'):
    return {'resultat': resultat, 'langue': langue,
            'section': {'code': 'nomenclature', 'motif_si_absent': MOTIF}}


def _designations(lignes):
    return [ligne[0] for ligne in lignes]


# ── L'extension de la table — structure/câbles/protections/terre ───────────

class TableNomenclatureEtendueTest(unittest.TestCase):
    def test_sans_cables_calcules_aucune_ligne_cable(self):
        resultat = dict(RESULTAT_BASE, nomenclature=[{
            'categorie': 'Structure',
            'designation': 'Rail de fixation aluminium',
            'quantite': 24.0, 'unite': 'u', 'spec': 'rail anodisé',
            'produit_id': None, 'reference': None}])
        _entetes, lignes = table_nomenclature(resultat)
        designations = _designations(lignes)
        self.assertTrue(any('Rail de fixation' in d for d in designations))
        self.assertFalse(any('Câble' in d for d in designations))

    def test_une_protection_decision_societe_porte_la_mention(self):
        from apps.calepinage.services.protections import MENTION_SOCIETE

        spec = MENTION_SOCIETE + ' — sécurité renforcée demandée client'
        resultat = dict(RESULTAT_BASE, nomenclature=[{
            'categorie': 'Protection DC',
            'designation': 'Parafoudre DC additionnel',
            'quantite': 1, 'unite': 'u', 'spec': spec,
            'produit_id': None, 'reference': None}])
        _entetes, lignes = table_nomenclature(resultat)
        designations = _designations(lignes)
        self.assertTrue(any(MENTION_SOCIETE in d for d in designations))

    def test_reference_produit_imprimee_quand_le_stock_en_publie_une(self):
        resultat = dict(RESULTAT_BASE, nomenclature=[{
            'categorie': 'Protection AC',
            'designation': 'QAC1 — Disjoncteur AC',
            'quantite': 1, 'unite': 'u', 'spec': '32 A / 400 V',
            'produit_id': 77, 'reference': 'DISJ-C32'}])
        _entetes, lignes = table_nomenclature(resultat)
        self.assertTrue(any('DISJ-C32' in d for d in _designations(lignes)))

    def test_sans_reference_publiee_aucune_reference_fabriquee(self):
        resultat = dict(RESULTAT_BASE, nomenclature=[{
            'categorie': 'Câblage DC',
            'designation': 'Câble solaire DC 6 mm²',
            'quantite': 120.0, 'unite': 'm', 'spec': 'chute 0,42 %',
            'produit_id': None, 'reference': None}])
        _entetes, lignes = table_nomenclature(resultat)
        self.assertNotIn('réf.', _designations(lignes)[-1])

    def test_ligne_sans_quantite_calculee_omise_jamais_zero(self):
        resultat = dict(RESULTAT_BASE, nomenclature=[{
            'categorie': 'Mise à la terre',
            'designation': 'Câble de terre cuivre nu',
            'quantite': None, 'unite': 'm', 'spec': '', 'produit_id': None,
            'reference': None}])
        _entetes, lignes = table_nomenclature(resultat)
        self.assertFalse(any('terre' in d.lower()
                             for d in _designations(lignes)))
        for ligne in lignes:
            self.assertNotEqual(ligne[1], 0)

    def test_verifier_absence_de_prix_passe_sur_la_table_etendue(self):
        resultat = dict(RESULTAT_BASE, nomenclature=[
            {'categorie': 'Câblage DC',
             'designation': 'Câble solaire DC 6 mm²', 'quantite': 120.0,
             'unite': 'm', 'spec': 'chute de tension 0,42 %',
             'produit_id': None, 'reference': None},
            {'categorie': 'Protection AC',
             'designation': 'QAC1 — Disjoncteur AC', 'quantite': 1,
             'unite': 'u', 'spec': '32 A / 400 V ; NF C 15-100 §433.1',
             'produit_id': 77, 'reference': 'DISJ-C32'},
        ])
        entetes, lignes = table_nomenclature(resultat)
        verifier_absence_de_prix(entetes, lignes)  # ne lève pas

    def test_verifier_absence_de_prix_refuse_toujours_un_mot_d_argent(self):
        resultat = dict(RESULTAT_BASE, nomenclature=[{
            'categorie': 'Structure', 'designation': 'Rail — 120 MAD',
            'quantite': 1, 'unite': 'u', 'spec': '', 'produit_id': None,
            'reference': None}])
        entetes, lignes = table_nomenclature(resultat)
        with self.assertRaises(ExportRefuse) as capture:
            verifier_absence_de_prix(entetes, lignes)
        self.assertIn('mad', str(capture.exception).lower())

    def test_entetes_restent_les_trois_colonnes_historiques(self):
        entetes, _lignes = table_nomenclature(RESULTAT_BASE)
        self.assertEqual(entetes, ['Désignation', 'Quantité', 'Unité'])

    def test_sans_cle_nomenclature_comportement_historique_inchange(self):
        entetes, lignes = table_nomenclature(RESULTAT_BASE)
        self.assertEqual(entetes, ['Désignation', 'Quantité', 'Unité'])
        self.assertEqual(len(lignes), 2)  # module + un onduleur


# ── Rejoue les assertions CAL179 sur la MÊME fixture ────────────────────────

class Cal179RestentVertesTest(unittest.TestCase):
    """``test_cal179_export_tableur.py`` n'est PAS modifié — ces essais
    rejouent SES assertions sur la fixture du contrat pour prouver que
    l'extension ne les casse pas."""

    def test_la_nomenclature_porte_toujours_designation_et_quantite(self):
        entetes, lignes = table_nomenclature(RESULTAT_CONTRAT)
        self.assertEqual(entetes, ['Désignation', 'Quantité', 'Unité'])
        self.assertEqual(lignes[0][1], RESULTAT_CONTRAT['pose']
                         ['total_modules'])
        self.assertIn('720', lignes[0][0])

    def test_sans_resultat_les_tables_restent_lisibles(self):
        entetes, lignes = table_nomenclature(None)
        self.assertTrue(entetes)
        self.assertIsInstance(lignes, list)

    def test_le_bordereau_electrique_du_contrat_s_ajoute_apres(self):
        # Le contrat calepinage_resultat.json PORTE déjà deux lignes de
        # bordereau (Câblage DC, Protection AC) — CALX246. Elles doivent
        # apparaître, APRÈS le module et l'onduleur, jamais à leur place.
        entetes, lignes = table_nomenclature(RESULTAT_CONTRAT)
        designations = _designations(lignes)
        self.assertIn('720', designations[0])
        self.assertTrue(any('ONDULEUR-ESSAI-1' in d for d in designations))
        self.assertTrue(any('120,0' in str(ligne[1]) or ligne[1] == 120.0
                            for ligne in lignes
                            if 'Câble solaire' in ligne[0]))
        self.assertTrue(any('DISJ-C32' in d for d in designations))

    def test_aucune_colonne_ni_cellule_de_prix(self):
        entetes, lignes = table_nomenclature(RESULTAT_CONTRAT)
        for entete in entetes:
            self.assertNotIn('prix', str(entete).lower())
            self.assertNotIn('achat', str(entete).lower())
        for ligne in lignes:
            for cellule in ligne:
                self.assertNotIn('prix_achat', str(cellule).lower())


# ── La section du rapport : MÊME table, aucun recalcul ─────────────────────

class HtmlDeSectionTest(unittest.TestCase):
    def test_meme_contenu_que_export_tableur_table_nomenclature(self):
        resultat = dict(RESULTAT_BASE, nomenclature=[{
            'categorie': 'Structure',
            'designation': 'Rail de fixation aluminium',
            'quantite': 24.0, 'unite': 'u', 'spec': '', 'produit_id': None,
            'reference': None}])
        html = html_de_section(contexte(resultat))
        _entetes, lignes = table_nomenclature(resultat)
        for ligne in lignes:
            self.assertIn(escape(str(ligne[0])), html)

    def test_sans_lignes_section_vide(self):
        html = html_de_section(contexte({'pose': {}, 'electrique': {}}))
        self.assertEqual(html, '')

    def test_html_de_table_trois_colonnes(self):
        entetes, lignes = table_nomenclature(RESULTAT_BASE)
        html = html_de_table(entetes, lignes)
        self.assertEqual(html.count('<th>'), 3)
        self.assertEqual(html.count('<tr>'), 1 + len(lignes))

    def test_la_section_refuse_un_mot_d_argent_en_le_nommant(self):
        resultat = dict(RESULTAT_BASE, nomenclature=[{
            'categorie': 'Structure', 'designation': 'Rail — 120 MAD',
            'quantite': 1, 'unite': 'u', 'spec': '', 'produit_id': None,
            'reference': None}])
        with self.assertRaises(ExportRefuse) as capture:
            html_de_section(contexte(resultat))
        self.assertIn('mad', str(capture.exception).lower())

    def test_la_fixture_du_contrat_s_imprime_sans_montant(self):
        html = html_de_section(contexte(copy.deepcopy(RESULTAT_CONTRAT)))
        for mot in ('prix', 'achat', 'marge'):
            self.assertNotIn(mot, html.lower())


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
