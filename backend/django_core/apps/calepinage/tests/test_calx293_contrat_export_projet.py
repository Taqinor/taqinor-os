"""CALX293 — le contrat de l'export JSON « projet + résultats » (PACT10).

CE QUE CE FICHIER GARDE
------------------------
`contract_samples/export_projet.json` part SEUL sur `main`, avant toute
vue — aucun `views/export_projet.py` n'existe encore. Ce test vérifie donc
l'ÉCHANTILLON lui-même, pas une réponse HTTP réelle, contre les trois
promesses du « Done » de CALX293 :

1. l'exemple committé se charge et tient son enveloppe PACT10 ;
2. `format_version == 1` — un ENTIER versionné dans le fichier, jamais une
   date ;
3. le fichier est REJETÉ (par le détecteur ci-dessous, qui reprend le
   vocabulaire `prix_*`/`cout_*`/`marge_*` du « Done ») dès qu'une clé de
   cette famille y apparaît — et l'exemple committé en est indemne.

Aucune base de données, aucun réseau.

Run :
    python manage.py test \
        apps.calepinage.tests.test_calx293_contrat_export_projet
"""
from __future__ import annotations

import json
import pathlib
import unittest

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')


def charger(nom):
    return json.loads((ECHANTILLONS / nom).read_text(encoding='utf-8'))


CONTRAT = charger('export_projet.json')

#: CALX293 (« Done ») nomme littéralement cette famille de préfixes — le
#: détecteur ci-dessous la reprend au mot près, en plus du mot NU (« prix »
#: seul est déjà un aveu, même esprit que
#: `note_calcul.CLES_INTERDITES_EXACTES`).
PREFIXES_DE_MONTANT = ('prix_', 'cout_', 'marge_')
MOTS_NUS_DE_MONTANT = ('prix', 'cout', 'marge')


def cle_de_montant(cle):
    texte = str(cle).lower()
    return (texte in MOTS_NUS_DE_MONTANT
            or any(texte.startswith(prefixe)
                   for prefixe in PREFIXES_DE_MONTANT))


def cles_de_montant(objet, chemin='<racine>'):
    """``[(chemin, cle)]`` — chaque clé de la famille `prix_*`/`cout_*`/
    `marge_*` (ou nue), où qu'elle vive dans le document. Fonction PURE :
    aucune requête, aucune écriture — c'est elle que le premier test
    prouve ROUGE en lui donnant une clé posée volontairement."""
    trouvees = []
    if isinstance(objet, dict):
        for cle, valeur in objet.items():
            if cle_de_montant(cle):
                trouvees.append((chemin, str(cle)))
            trouvees.extend(cles_de_montant(valeur, f'{chemin}.{cle}'))
    elif isinstance(objet, (list, tuple)):
        for index, item in enumerate(objet):
            trouvees.extend(cles_de_montant(item, f'{chemin}[{index}]'))
    return trouvees


class EnveloppeTest(unittest.TestCase):

    def test_enveloppe_complete(self):
        for cle in ('endpoint', 'pourquoi', 'exemple'):
            self.assertIn(cle, CONTRAT,
                          f'export_projet.json : clé « {cle} » absente — '
                          'check_api_shapes ne saurait pas le lire.')
        self.assertTrue(CONTRAT['endpoint'].strip())

    def test_la_route_est_le_nouvel_export_projet(self):
        self.assertEqual(
            CONTRAT['endpoint'],
            'GET /api/django/calepinage/calepinages/<int:pk>/'
            'export-projet.json/')

    def test_l_exemple_porte_les_cles_annoncees_par_le_done(self):
        # CALX314 — ``provenance`` rejoint le fichier avant sa première
        # livraison (même merge que la route CALX312).
        attendues = {'format_version', 'produit_le', 'calepinage', 'site',
                     'equipements', 'roof_layout', 'layout_hash',
                     'version_moteur', 'resultat', 'pertes',
                     'avertissements', 'provenance'}
        self.assertEqual(set(CONTRAT['exemple']), attendues)
        self.assertEqual(set(CONTRAT['exemple_vide']), attendues,
                         "exemple_vide doit garder TOUTES les clés (règle "
                         "3 du README) — jamais une clé absente pour dire "
                         "l'absence de donnée.")


class FormatVersionTest(unittest.TestCase):
    """Un ENTIER versionné, jamais dérivé d'une date."""

    def test_format_version_vaut_un(self):
        self.assertEqual(CONTRAT['exemple']['format_version'], 1)
        self.assertIsInstance(CONTRAT['exemple']['format_version'], int)

    def test_format_version_est_le_meme_sur_l_exemple_vide(self):
        # Le NUMÉRO DE FORMAT ne dépend jamais de l'état du calepinage —
        # seul son CONTENU change entre `exemple` et `exemple_vide`.
        self.assertEqual(CONTRAT['exemple_vide']['format_version'], 1)

    def test_produit_le_est_un_horodatage_distinct_de_format_version(self):
        """CALX293 : `produit_le` (horodatage réel) et `format_version`
        (entier versionné) sont deux clés DISTINCTES — la doctrine du
        contrat l'exige explicitement (« la distinction entre les deux est
        délibérée »)."""
        self.assertNotEqual(CONTRAT['exemple']['produit_le'],
                            CONTRAT['exemple']['format_version'])
        self.assertIsInstance(CONTRAT['exemple']['produit_le'], str)
        self.assertTrue(CONTRAT['exemple']['produit_le'].endswith('Z'),
                        'un horodatage sans fuseau explicite est un piège '
                        '(règle datetime naïf) — celui-ci doit être UTC.')


class AucuneCleDeMontantTest(unittest.TestCase):
    """Done CALX293 : rejette le fichier si une clé `prix_*`/`cout_*`/
    `marge_*` y apparaît."""

    def test_le_detecteur_rougit_sur_prix_ajoute_a_plat(self):
        self.assertEqual(cles_de_montant({'prix_vente_mad': 100}),
                         [('<racine>', 'prix_vente_mad')])

    def test_le_detecteur_rougit_sur_cout_imbrique(self):
        trouvees = cles_de_montant(
            {'equipements': {'panneau': {'cout_unitaire': 12}}})
        self.assertEqual(trouvees,
                         [('<racine>.equipements.panneau', 'cout_unitaire')])

    def test_le_detecteur_rougit_sur_marge_dans_une_liste(self):
        trouvees = cles_de_montant({'pertes': [{'marge_pct': 1}]})
        self.assertEqual(len(trouvees), 1)

    def test_le_detecteur_rougit_sur_le_mot_nu(self):
        self.assertEqual(cles_de_montant({'prix': 1, 'cout': 2, 'marge': 3}),
                         [('<racine>', 'prix'), ('<racine>', 'cout'),
                          ('<racine>', 'marge')])

    def test_un_document_propre_ne_declenche_rien(self):
        self.assertEqual(
            cles_de_montant({'produit': 1, 'quantite': 4,
                            'specs': {'pmax_wc': 550}}),
            [])

    def test_l_exemple_committe_est_indemne(self):
        self.assertEqual(cles_de_montant(CONTRAT['exemple']), [])

    def test_l_exemple_vide_est_indemne(self):
        self.assertEqual(cles_de_montant(CONTRAT['exemple_vide']), [])

    def test_aucun_specs_d_equipement_ne_porte_prix_achat(self):
        """D5 — rappel explicite : `Produit.prix_achat` alimente un
        indicateur GÉNÉRATEUR et ne doit JAMAIS fuiter dans une sortie
        client, même indirectement via les `specs` d'un équipement."""
        equipements = CONTRAT['exemple']['equipements']
        for famille in ('panneau', 'onduleur', 'batterie', 'optimiseur'):
            entree = equipements.get(famille)
            if not entree:
                continue
            self.assertNotIn('prix_achat', entree.get('specs', {}))


class DisciplineDuNullTest(unittest.TestCase):
    """Un calepinage jamais simulé exporte `resultat: null`, `pertes: []`
    — jamais un résultat à moitié rempli, jamais un chiffre à zéro."""

    def test_resultat_vaut_null_sur_le_calepinage_neuf(self):
        self.assertIsNone(CONTRAT['exemple_vide']['resultat'])
        self.assertIsNone(CONTRAT['exemple_vide']['roof_layout'])
        self.assertIsNone(CONTRAT['exemple_vide']['layout_hash'])

    def test_pertes_reste_une_liste_vide_jamais_null(self):
        # Même exception de type que `calepinage_resultat.json` (D-CALX 11) :
        # `pertes` est toujours une LISTE, vide ou non — jamais `null`.
        self.assertEqual(CONTRAT['exemple_vide']['pertes'], [])
        self.assertIsInstance(CONTRAT['exemple']['pertes'], list)

    def test_resultat_est_bien_rempli_quand_le_calepinage_est_simule(self):
        resultat = CONTRAT['exemple']['resultat']
        self.assertIsNotNone(resultat)
        self.assertIn('production', resultat)
        self.assertIn('electrique', resultat)
        self.assertIn('pose', resultat)


class ReutiliseLeVocabulaireDesAutresContratsTest(unittest.TestCase):
    """Aucune clé inventée : `pertes` reprend le même vocabulaire que
    `calepinage_resultat.json` (poste/libelle/pct/source)."""

    def test_chaque_poste_de_pertes_porte_les_quatre_cles_connues(self):
        for poste in CONTRAT['exemple']['pertes']:
            self.assertEqual(set(poste),
                             {'poste', 'libelle', 'pct', 'source'})

    def test_un_poste_non_source_reste_publie_avec_source_null(self):
        # D-CALX : un poste non sourcé est rendu TEL QUEL (`source: null`),
        # jamais masqué.
        sans_source = [p for p in CONTRAT['exemple']['pertes']
                       if p['source'] is None]
        self.assertTrue(sans_source,
                        "l'exemple doit montrer au moins un poste sans "
                        'source, pour la même raison que '
                        'calepinage_resultat.json.')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
