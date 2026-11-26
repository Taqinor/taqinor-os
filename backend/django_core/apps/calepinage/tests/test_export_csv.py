"""CAL144 — l'export CSV : ouvrable dans Excel, sourcé, sans un seul prix.

Tests PURS sur le service (aucune base, aucun réseau), plus une vérification
que l'action est bien RATTACHÉE au viewset avec la bonne URL et la bonne
garde — celle-ci a besoin des réglages Django, donc elle se saute proprement
si le module de test est exécuté hors du harnais.
"""
from __future__ import annotations

import importlib
import csv
import io
import unittest

from apps.calepinage.services.export_csv import (
    ENCODAGE_TABLEUR, EXPORTS, MOTIF_PERTE_NON_CONSERVEE,
    MOTIF_POSTES_ABSENTS, ExportImpossible, encoder_pour_tableur, export_csv,
)
# ACAL234 — le jumeau ``export_csv.nom_de_fichier`` est supprimé : le CSV est
# nommé par LE constructeur du module (``quoi`` remplace le titre).
from apps.calepinage.services.planche import nom_de_fichier

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
    'acces_modules': {'PAN-1#1': 0.9, 'PAN-1#2': None},
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


class OmbrageModulesTest(unittest.TestCase):
    """ACAL754 — une ligne par module, l'accès solaire annuel du document."""

    @staticmethod
    def _layout():
        def pan(identifiant, valeurs):
            return {'id': identifiant, 'geometry': {
                'solarAccess': {'values': valeurs}}}
        return {'zones': [pan('P1', [0.5, 0.25, 1.0]),
                          pan('P2', [0.75, None])]}

    def _document(self):
        from apps.calepinage.services.ombrage_chaines import (
            acces_des_modules,
        )
        return {**DOCUMENT, 'acces_modules': acces_des_modules(self._layout())}

    def test_cinq_lignes_dans_l_ordre_des_pans_valeurs_du_document(self):
        table = lignes(export_csv(self._document(), quoi='ombrage_modules'))
        entete = table.index(['module', 'acces_solaire'])
        corps = [ligne for ligne in table[entete + 1:] if ligne]
        # Valeurs écrites ICI à partir du document d'essai, pas de la sortie.
        self.assertEqual(corps, [
            ['P1#1', '0,500'], ['P1#2', '0,250'], ['P1#3', '1,000'],
            ['P2#1', '0,750'], ['P2#2', ''],
        ])

    def test_la_resolution_annuelle_est_dite_dans_l_entete(self):
        texte = export_csv(self._document(), quoi='ombrage_modules')
        self.assertIn('Résolution', texte)
        self.assertIn("le mois et l'heure par module ne sont pas calculés",
                      texte)
        self.assertIn('Provenance', texte)

    def test_sans_acces_par_module_refus_nomme_acces_modules(self):
        for vide in ({}, None):
            with self.assertRaises(ExportImpossible) as capture:
                export_csv({**DOCUMENT, 'acces_modules': vide},
                           quoi='ombrage_modules')
            self.assertEqual(capture.exception.champ, 'acces_modules')
            self.assertIn("Aucun accès solaire par module",
                          capture.exception.motif)


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
        class Pivot:
            pk = 7
            titre = 'Villa de M. Client'

        self.assertEqual(nom_de_fichier(Pivot(), 'csv', quoi='horaire'),
                         'calepinage-7-horaire.csv')


class CalepinageFactice:
    """Le strict nécessaire que lit ``document_exportable`` — aucune base."""

    def __init__(self, resultat, roof_layout=None, version_moteur='essai-1'):
        self.resultat = resultat
        self.roof_layout = roof_layout or {}
        self.version_moteur = version_moteur


class DocumentExportableTest(unittest.TestCase):
    """CALX193 — la vue passe la LISTE de points, pas le bloc entier.

    `views/export_csv.py:83` écrivait `resultat.get('serie_horaire') or []`,
    donc le BLOC là où `_export_horaire` itère une liste : dès que la chaîne
    écrit la clé (contrat CALX142 : `pas_minutes`, `tronquee`, `colonnes`,
    `points`), l'export doit lire `points`.
    """

    def vue(self):
        from apps.calepinage.services.export_csv import document_exportable
        from .acal_livrables_helpers import patch_servi_frais

        def composer(calepinage):
            with patch_servi_frais():
                return document_exportable(calepinage)
        return composer

    def test_le_bloc_calx142_est_lu_par_sa_cle_points(self):
        document_exportable = self.vue()
        bloc = {'pas_minutes': 60, 'tronquee': False,
                'colonnes': ['annee', 'mois', 'jour', 'heure', 'p_w',
                             'gi_w_m2', 't2m_c'],
                'points': DOCUMENT['points']}
        document = document_exportable(CalepinageFactice(
            {'production': DOCUMENT['production'],
             'pertes': DOCUMENT['pertes'], 'serie_horaire': bloc}))
        self.assertEqual(document['points'], DOCUMENT['points'])
        table = lignes(export_csv(document, quoi='horaire'))
        entete = [ligne for ligne in table
                  if ligne and ligne[0] == 'annee'][0]
        self.assertEqual(entete, ['annee', 'mois', 'jour', 'heure',
                                  'production_kw', 'irradiance_plan_w_m2',
                                  'temperature_air_c'])
        self.assertEqual(table[table.index(entete) + 1][4], '0,563')

    def test_un_calepinage_non_simule_garde_le_refus_francais(self):
        document_exportable = self.vue()
        document = document_exportable(CalepinageFactice({}))
        self.assertEqual(document['points'], [])
        with self.assertRaises(ExportImpossible) as capture:
            export_csv(document, quoi='horaire')
        self.assertEqual(capture.exception.champ, 'points')
        self.assertIn('simulation', capture.exception.motif)

    def test_une_serie_deja_en_base_sous_forme_de_liste_reste_lisible(self):
        document_exportable = self.vue()
        document = document_exportable(CalepinageFactice(
            {'serie_horaire': DOCUMENT['points']}))
        self.assertEqual(document['points'], DOCUMENT['points'])

    def test_un_bloc_sans_points_refuse_plutot_que_de_casser(self):
        document_exportable = self.vue()
        document = document_exportable(CalepinageFactice(
            {'serie_horaire': {'pas_minutes': 60, 'points': []}}))
        self.assertEqual(document['points'], [])


class ActionRattacheeTest(unittest.TestCase):
    """L'action est bien montée sur le viewset, en lecture seule."""

    def test_url_mapping_et_garde(self):
        from apps.calepinage.views.calepinages import CalepinageViewSet
        importlib.import_module('apps.calepinage.views.export_csv')
        # CALX7 — l'action de CE fichier s'appelle ``export_csv_simulation``
        # depuis qu'elle a cessé de masquer ``SortiesMixin.export_csv``
        # (``export.csv``, CAL179). Son ``url_path`` public, lui, est INCHANGÉ.
        action = CalepinageViewSet.export_csv_simulation
        self.assertEqual(action.url_path, 'export-csv')
        self.assertEqual(action.mapping, {'get': 'export_csv_simulation'})
        self.assertEqual(
            [garde.__name__
             for garde in action.kwargs['permission_classes']],
            ['PeutVoirCalepinage'])


class ColonnesPublieesTest(unittest.TestCase):
    """ERR-ENF11-FUZZ-CALEPINAGE - ``?colonnes=`` publie le vocabulaire que le
    service applique : le motif accepte les noms connus et refuse le reste."""

    def test_motif_accepte_les_noms_connus_refuse_le_reste(self):
        import re

        from apps.calepinage.services.export_csv import COLONNES_HORAIRE
        from apps.calepinage.views.export_csv import _MOTIF_COLONNES

        # fullmatch : le ``$`` publié vaut « fin de chaîne » (ECMA) ; en
        # Python ``match`` tolérerait un saut de ligne final.
        motif = re.compile(_MOTIF_COLONNES)
        noms = sorted(COLONNES_HORAIRE)
        self.assertTrue(motif.fullmatch(noms[0]))
        self.assertTrue(motif.fullmatch(','.join(noms)))
        for faux in ('', ',', 'inconnue', noms[0] + ',inconnue',
                     noms[0] + ',', noms[0] + chr(10)):
            self.assertIsNone(motif.fullmatch(faux), repr(faux))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()


class EnteteSansPerteNiPostesTest(unittest.TestCase):
    """ACAL1929 — une perte ou des postes absents sont DITS, jamais une cellule vide."""

    def _entete(self, document):
        return {ligne[0]: ligne[1] for ligne in lignes(export_csv(document, quoi='horaire'))
                if len(ligne) > 1 and ligne[0] in ('Pertes passées à PVGIS (%)', 'Détail des pertes')}

    def test_la_perte_envoyee_et_les_postes_publies_sont_ecrits(self):
        entete = self._entete(DOCUMENT)
        self.assertEqual(entete['Pertes passées à PVGIS (%)'], '7,250')
        self.assertIn('shading 3,50 %', entete['Détail des pertes'])

    def test_une_perte_absente_dit_pourquoi_en_clair(self):
        document = {**DOCUMENT, 'production': {
            **DOCUMENT['production'], 'base': {'source': 'pvgis'}}, 'pertes': []}
        entete = self._entete(document)
        self.assertEqual(entete['Pertes passées à PVGIS (%)'], MOTIF_PERTE_NON_CONSERVEE)
        self.assertTrue(entete['Pertes passées à PVGIS (%)'].startswith('non publiée : '))
        self.assertEqual(entete['Détail des pertes'], MOTIF_POSTES_ABSENTS)
        self.assertTrue(entete['Détail des pertes'].startswith('non publiés : '))
