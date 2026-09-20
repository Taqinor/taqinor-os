"""CAL144 — l'export CSV : ouvrable dans Excel, sourcé, sans un seul prix.

Tests PURS sur le service (aucune base, aucun réseau), plus une vérification
que l'action est bien RATTACHÉE au viewset avec la bonne URL et la bonne
garde — celle-ci a besoin des réglages Django, donc elle se saute proprement
si le module de test est exécuté hors du harnais.
"""
from __future__ import annotations

import csv
import io
import unittest

from apps.calepinage.services.export_csv import (
    ENCODAGE_TABLEUR, EXPORTS, ExportImpossible, encoder_pour_tableur,
    export_csv, nom_de_fichier,
)

#: Un document d'essai : deux heures de série, deux mois d'agrégat. Les
#: valeurs sont des repères d'ESSAI assumés — ce test vérifie la MISE EN
#: FORME, pas un chiffre de production.
DOCUMENT = {
    'version_moteur': 'essai-1',
    'production': {
        'base': {'source': 'pvgis', 'base_rayonnement': 'PVGIS-SARAH3',
                 'fenetre_annees': '2020-2020', 'loss_passee_pct': 7.25},
        'total': {'p50_kwh': 1234.5},
        'mensuel': [{'mois': 1, 'p50_kwh': 600.25},
                    {'mois': 2, 'p50_kwh': 634.25}],
    },
    'pertes': [
        {'poste': 'shading', 'pct': 3.5, 'source': 'mesure'},
        {'poste': 'availability', 'pct': 3.75, 'source': None},
    ],
    'points': [
        {'annee': 2020, 'mois': 1, 'jour': 15, 'heure': 12,
         'p_w': 562.74, 'gi_w_m2': 785.26, 't2m_c': 18.45},
        {'annee': 2020, 'mois': 1, 'jour': 15, 'heure': 13,
         'p_w': None, 'gi_w_m2': None, 't2m_c': 18.9},
    ],
    'shading12x24': [[1.0] * 24 for _ in range(12)],
}


def lignes(texte):
    return list(csv.reader(io.StringIO(texte), delimiter=';'))


class ExportHoraireTest(unittest.TestCase):

    def test_entete_de_provenance_puis_le_tableau(self):
        texte = export_csv(DOCUMENT, quoi='horaire')
        table = lignes(texte)
        entetes = {ligne[0] for ligne in table if ligne}
        self.assertIn('Base de rayonnement', entetes)
        self.assertIn("Fenêtre d'années", entetes)
        self.assertIn('Version du moteur', entetes)
        self.assertIn('Pertes passées à PVGIS (%)', entetes)
        self.assertIn('PVGIS-SARAH3', texte)
        self.assertIn('2020-2020', texte)
        # Un poste non sourcé est NOMMÉ comme tel, il ne disparaît pas.
        self.assertIn('source non renseignée', texte)

    def test_colonnes_nommees_avec_leur_unite(self):
        table = lignes(export_csv(DOCUMENT, quoi='horaire'))
        entete = [ligne for ligne in table
                  if ligne and ligne[0] == 'annee'][0]
        self.assertEqual(entete, ['annee', 'mois', 'jour', 'heure',
                                  'production_kw', 'irradiance_plan_w_m2',
                                  'temperature_air_c'])

    def test_decimale_francaise_et_heure_sans_mesure_laissee_vide(self):
        table = lignes(export_csv(DOCUMENT, quoi='horaire'))
        depart = [rang for rang, ligne in enumerate(table)
                  if ligne and ligne[0] == 'annee'][0]
        premiere, seconde = table[depart + 1], table[depart + 2]
        self.assertEqual(premiere[4], '0,563')     # 562,74 W → kW
        self.assertEqual(premiere[6], '18,45')
        # Une heure sans mesure reste VIDE : ce n'est pas une heure à 0 kW.
        self.assertEqual(seconde[4], '')
        self.assertEqual(seconde[5], '')
        self.assertEqual(seconde[6], '18,90')

    def test_le_bom_utf8_est_pose_pour_excel(self):
        octets = encoder_pour_tableur(export_csv(DOCUMENT, quoi='horaire'))
        self.assertTrue(octets.startswith(b'\xef\xbb\xbf'))
        self.assertIn('Fenêtre', octets.decode(ENCODAGE_TABLEUR))

    def test_aucun_prix_dans_lexport(self):
        texte = ' '.join(export_csv(DOCUMENT, quoi=quoi).lower()
                         for quoi in EXPORTS)
        for interdit in ('prix', 'prix_achat', 'marge', 'mad', 'tarif',
                         'montant'):
            self.assertNotIn(interdit, texte)


class ExportMensuelEtOmbrageTest(unittest.TestCase):

    def test_mensuel_porte_ses_mois_et_son_total(self):
        table = lignes(export_csv(DOCUMENT, quoi='mensuel'))
        self.assertIn(['mois', 'production_kwh'], table)
        self.assertIn(['1', '600,2'], table)
        self.assertIn(['total_annuel', '1234,5'], table)

    def test_ombrage_rend_douze_lignes_de_vingt_quatre_heures(self):
        table = lignes(export_csv(DOCUMENT, quoi='ombrage'))
        entete = [ligne for ligne in table if ligne and ligne[0] == 'mois'][0]
        self.assertEqual(len(entete), 25)          # mois + 24 heures
        self.assertEqual(entete[1], 'h00')
        corps = table[table.index(entete) + 1:]
        corps = [ligne for ligne in corps if ligne]
        self.assertEqual(len(corps), 12)
        self.assertTrue(all(len(ligne) == 25 for ligne in corps))


class RefusMotiveTest(unittest.TestCase):
    """Donnée absente ⇒ refus nommé, jamais un fichier de zéros."""

    def test_serie_absente_refusee(self):
        document = dict(DOCUMENT, points=[])
        with self.assertRaises(ExportImpossible) as capture:
            export_csv(document, quoi='horaire')
        self.assertEqual(capture.exception.champ, 'points')
        self.assertIn('simulation', capture.exception.motif)

    def test_mensuel_absent_refuse(self):
        document = dict(DOCUMENT, production={'base': {}, 'mensuel': []})
        with self.assertRaises(ExportImpossible) as capture:
            export_csv(document, quoi='mensuel')
        self.assertEqual(capture.exception.champ, 'mensuel')

    def test_matrice_dombrage_incomplete_refusee(self):
        document = dict(DOCUMENT, shading12x24=[[1.0] * 24 for _ in range(3)])
        with self.assertRaises(ExportImpossible) as capture:
            export_csv(document, quoi='ombrage')
        self.assertEqual(capture.exception.champ, 'shading12x24')

    def test_export_inconnu_refuse_en_listant_les_exports(self):
        with self.assertRaises(ExportImpossible) as capture:
            export_csv(DOCUMENT, quoi='annuel')
        self.assertEqual(capture.exception.champ, 'quoi')
        for connu in EXPORTS:
            self.assertIn(connu, capture.exception.motif)

    def test_nom_de_fichier_sans_donnee_client(self):
        self.assertEqual(nom_de_fichier(7, 'horaire'),
                         'calepinage-7-horaire.csv')


class ActionRattacheeTest(unittest.TestCase):
    """L'action est bien montée sur le viewset, en lecture seule."""

    def test_url_mapping_et_garde(self):
        try:
            from apps.calepinage.views.calepinages import CalepinageViewSet
            from apps.calepinage.views import sorties  # noqa: F401
        except Exception as erreur:  # pragma: no cover - hors harnais Django
            self.skipTest(f'Réglages Django indisponibles : {erreur}')
        action = CalepinageViewSet.export_csv
        self.assertEqual(action.url_path, 'export-csv')
        self.assertEqual(action.mapping, {'get': 'export_csv'})
        self.assertEqual(
            [garde.__name__
             for garde in action.kwargs['permission_classes']],
            ['PeutVoirCalepinage'])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
