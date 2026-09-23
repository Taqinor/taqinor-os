"""CALX313 — choisir les colonnes et le pas de temps de l'export horaire.

CE QUE CE FICHIER PROUVE
-------------------------
``export_csv(quoi='horaire')`` servait toujours les mêmes sept colonnes
(renommées, CAL144) au pas horaire, sans sélection. Ce test prouve les
promesses du « Done » de CALX313, à l'appel du SERVICE (pur, sans base, sans
réseau — même patron que ``test_export_csv.py::RefusMotiveTest``, qui prouve
déjà les refus de ``quoi`` inconnu à ce niveau plutôt qu'en HTTP) :

1. ``colonnes=['t', 'p_ac_kw']`` produit EXACTEMENT deux colonnes, et le bloc
   de provenance les NOMME (ligne ``Colonnes retenues``).
2. Une colonne hors du vocabulaire réellement servi par la série (contrat
   CALX142, W3) est refusée EN LA NOMMANT — jamais un fichier tronqué en
   silence.
3. ``pas='15min'`` est refusé EXPLICITEMENT et ne produit AUCUN fichier —
   même quand la série horaire existe : ce module n'interpole JAMAIS une
   série horaire pour en simuler une à 15 minutes.
4. Le comportement D'AVANT CALX313 (appel sans ``colonnes=``/``pas=``) ne
   bouge pas d'un caractère — additif, jamais substitutif.

Run :
    python manage.py test apps.calepinage.tests.test_calx313_colonnes_export
"""
from __future__ import annotations

import csv
import io
import unittest

from apps.calepinage.services.export_csv import (
    COLONNES_HORAIRE, DEFAULT_COLONNES_HORAIRE, PAS_DISPONIBLES,
    ExportImpossible, export_csv,
)

#: Un document d'essai — deux heures de série (une mesurée, une sans donnée
#: sur certaines colonnes), un agrégat mensuel non vide. Les valeurs sont des
#: repères d'ESSAI assumés (D-CALX 7) : ce test vérifie la MISE EN FORME et
#: le VOCABULAIRE des colonnes, jamais un chiffre de production réel.
DOCUMENT = {
    'version_moteur': 'essai-calx313',
    'production': {
        'base': {'source': 'pvgis', 'base_rayonnement': 'PVGIS-SARAH3',
                 'fenetre_annees': '2020-2020', 'loss_passee_pct': 7.25},
        'total': {'p50_kwh': 1234.5},
        'mensuel': [{'mois': 1, 'p50_kwh': 600.25}],
    },
    'pertes': [],
    'points': [
        {'annee': 2020, 'mois': 1, 'jour': 15, 'heure': 12,
         'p_w': 6800.0, 'gi_w_m2': 880.0, 't2m_c': 19.8, 'p_ac_kw': 6.8,
         'p_dc_kw': 7.0, 'ecretage_kw': 0.0},
        {'annee': 2020, 'mois': 1, 'jour': 15, 'heure': 13,
         'p_w': None, 'gi_w_m2': None, 't2m_c': 18.9},
    ],
}


def lignes(texte):
    return list(csv.reader(io.StringIO(texte), delimiter=';'))


class ColonnesChoisiesTest(unittest.TestCase):

    def test_deux_colonnes_choisies_produisent_exactement_deux_colonnes(self):
        texte = export_csv(DOCUMENT, quoi='horaire',
                           colonnes=['t', 'p_ac_kw'])
        table = lignes(texte)
        self.assertIn(['t', 'p_ac_kw'], table,
                      "l'en-tête doit porter EXACTEMENT les deux colonnes "
                      'demandées, ni plus ni moins.')

    def test_le_bloc_de_provenance_nomme_les_colonnes_retenues(self):
        texte = export_csv(DOCUMENT, quoi='horaire',
                           colonnes=['t', 'p_ac_kw'])
        table = lignes(texte)
        self.assertIn(['Colonnes retenues', 't, p_ac_kw'], table)

    def test_t_est_un_alias_reel_de_heure_jamais_une_valeur_inventee(self):
        texte = export_csv(DOCUMENT, quoi='horaire', colonnes=['t'])
        table = lignes(texte)
        depart = table.index(['t'])
        self.assertEqual(table[depart + 1], ['12'])
        self.assertEqual(table[depart + 2], ['13'])

    def test_colonne_inconnue_refusee_en_la_nommant(self):
        with self.assertRaises(ExportImpossible) as capture:
            export_csv(DOCUMENT, quoi='horaire', colonnes=['t', 'invente'])
        self.assertEqual(capture.exception.champ, 'colonnes')
        motif = capture.exception.motif
        self.assertIn('invente', motif,
                      'le refus doit NOMMER la colonne inconnue, pas juste '
                      'dire « colonne invalide ».')
        # Seule la colonne réellement inconnue est nommée dans le premier
        # « … » du motif — la colonne CONNUE (`t`) de la même demande ne
        # doit pas y apparaître (elle réapparaît plus loin, dans la liste
        # « colonnes disponibles », ce qui est attendu).
        premiere_citation = motif.split('»')[0].split('«')[-1].strip()
        self.assertEqual(premiere_citation, 'invente')

    def test_colonnes_vide_est_refusee(self):
        with self.assertRaises(ExportImpossible) as capture:
            export_csv(DOCUMENT, quoi='horaire', colonnes=[])
        self.assertEqual(capture.exception.champ, 'colonnes')

    def test_sans_colonnes_le_comportement_d_avant_calx313_ne_bouge_pas(self):
        texte = export_csv(DOCUMENT, quoi='horaire')
        table = lignes(texte)
        entete = [ligne for ligne in table
                  if ligne and ligne[0] == 'annee'][0]
        self.assertEqual(entete, list(DEFAULT_COLONNES_HORAIRE))

    def test_tout_le_vocabulaire_declare_est_extractible_sans_lever(self):
        # Chaque colonne du vocabulaire (les sept renommées, les treize
        # additives du bloc W3, l'alias `t`) doit se lire sans erreur, même
        # quand le point ne la porte pas (cellule vide, jamais un défaut).
        texte = export_csv(DOCUMENT, quoi='horaire',
                           colonnes=sorted(COLONNES_HORAIRE))
        table = lignes(texte)
        self.assertIn(sorted(COLONNES_HORAIRE), table)


class PasDeTempsTest(unittest.TestCase):

    def test_pas_horaire_est_le_defaut_et_produit_un_fichier(self):
        self.assertTrue(export_csv(DOCUMENT, quoi='horaire'))

    def test_pas_15min_refuse_explicitement_et_aucun_fichier(self):
        with self.assertRaises(ExportImpossible) as capture:
            export_csv(DOCUMENT, quoi='horaire', pas='15min')
        self.assertEqual(capture.exception.champ, 'pas')
        self.assertIn('15 minutes', capture.exception.motif)
        self.assertIn('interpole', capture.exception.motif)

    def test_pas_15min_refuse_meme_si_la_serie_horaire_existe(self):
        # Le refus porte sur le PAS demandé, pas sur la disponibilité de la
        # donnée : DOCUMENT porte bien une série horaire complète, et
        # pourtant rien ne sort — jamais une interpolation.
        self.assertTrue(DOCUMENT['points'])
        with self.assertRaises(ExportImpossible):
            export_csv(DOCUMENT, quoi='horaire', pas='15min')

    def test_pas_inconnu_refuse_en_le_nommant(self):
        with self.assertRaises(ExportImpossible) as capture:
            export_csv(DOCUMENT, quoi='horaire', pas='journalier')
        self.assertEqual(capture.exception.champ, 'pas')
        self.assertIn('journalier', capture.exception.motif)

    def test_pas_disponibles_declare_les_deux_valeurs_connues(self):
        self.assertEqual(PAS_DISPONIBLES, ('horaire', '15min'))


class AucunMotDeMontantTest(unittest.TestCase):
    """D5 — un export d'énergie, jamais un prix, même colonnes= au complet."""

    def test_aucun_mot_de_montant_dans_le_vocabulaire_ni_le_fichier(self):
        texte = export_csv(DOCUMENT, quoi='horaire',
                           colonnes=sorted(COLONNES_HORAIRE)).lower()
        for interdit in ('prix', 'prix_achat', 'marge', 'mad', 'tarif',
                         'montant', 'cout'):
            self.assertNotIn(interdit, texte)
        for nom_colonne in COLONNES_HORAIRE:
            for interdit in ('prix', 'marge', 'cout', 'tarif', 'montant'):
                self.assertNotIn(interdit, nom_colonne.lower())


class ParametresProprosAlHoraireTest(unittest.TestCase):
    """``colonnes=``/``pas=`` n'existent que pour l'export horaire."""

    def test_mensuel_reste_utilisable_colonnes_et_pas_ignores(self):
        # `export_csv()` ne transmet `colonnes`/`pas` qu'à l'export horaire
        # (voir son dispatch) : un appel `quoi='mensuel'` avec ces deux
        # paramètres continue de servir l'agrégat mensuel normalement.
        texte = export_csv(DOCUMENT, quoi='mensuel', colonnes=['t'],
                           pas='15min')
        table = lignes(texte)
        self.assertIn(['mois', 'production_kwh'], table)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
