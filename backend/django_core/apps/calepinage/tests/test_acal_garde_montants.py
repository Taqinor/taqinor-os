"""ACAL231 - UNE garde « aucun montant » a frontieres de mot, jamais sur un texte SAISI.

Un client « Hammadi » (contient « mad »), un client « El Madani », un pan
« Remise » ou un motif « remise aux normes » ne font plus refuser le plan de
pose, le classeur ou le rapport d'etude ; une designation de catalogue qui
porte le MOT ENTIER prix, montant, marge, tva ou tarif reste refusee (400
nomme). Essais PURS - la garde et ses appelants, sans base ni rendu PDF.

Run :
    python manage.py test apps.calepinage.tests.test_acal_garde_montants -v2
"""
import copy

from django.test import SimpleTestCase

from apps.calepinage.services import export_tableur, planche, sld
from apps.calepinage.services.export_tableur import (
    ExportRefuse, table_modules, table_nomenclature, tables_du_resultat,
    verifier_absence_de_prix,
)
from apps.calepinage.services.garde_montants import (
    MOTS_D_ARGENT, mots_d_argent,
)
from apps.calepinage.services.planche import (
    PlanDePoseRefuse, geometrie_de_planche, verifier_absence_d_argent,
)
from apps.calepinage.services.rapport import RapportRefuse
from apps.calepinage.services.rapport.nomenclature import html_de_section

from .test_cal171_planche import LAYOUT


def _layout_nomme(libelle):
    layout = copy.deepcopy(LAYOUT)
    layout['zones'][0]['label'] = libelle
    return layout


class SansFauxPositifTest(SimpleTestCase):
    def test_plan_de_pose_rend_un_calepinage_hammadi_et_madani(self):
        for nom in ('Villa Hammadi', 'Villa El Madani'):
            self.assertEqual(mots_d_argent(nom), [], nom)
            # Le texte guarde du plan de pose est le bandeau (catalogue /
            # moteur) : un nom de calepinage n'y entre jamais.
            verifier_absence_d_argent('Chaînes : 2\nOnduleur ONDULEUR-ESSAI')

    def test_classeur_rend_un_pan_nomme_remise(self):
        geometrie = geometrie_de_planche(_layout_nomme('Remise'))
        tables = tables_du_resultat(geometrie, None)    # ne leve pas
        entetes, lignes = table_modules(geometrie, None)
        self.assertTrue(any(ligne[0] == 'Remise' for ligne in lignes))
        self.assertEqual([t[0] for t in tables][:1], ['Modules'])
        classeur = export_tableur.classeur_octets(tables)
        self.assertTrue(classeur.startswith(b'PK'))

    def test_rapport_etude_200_avec_motif_remise_aux_normes(self):
        # Un organe ajoute par la societe porte son motif SAISI dans la
        # specification : la garde ne la lit pas (plus de 500).
        resultat = {'nomenclature': [{
            'categorie': 'Protection AC', 'designation': 'Disjoncteur AC',
            'quantite': 1, 'unite': 'u',
            'spec': 'décision société — remise aux normes',
            'produit_id': None, 'reference': None}]}
        entetes, lignes = table_nomenclature(resultat)
        verifier_absence_de_prix(entetes, lignes)        # ne leve pas
        html = html_de_section({'resultat': resultat, 'langue': 'fr'})
        self.assertIn('remise aux normes', html)


class RefusAttenduTest(SimpleTestCase):
    def test_designation_catalogue_avec_mot_entier_prix_est_refusee(self):
        for mot in ('prix', 'montant', 'marge', 'tva', 'tarif'):
            resultat = {'nomenclature': [{
                'categorie': 'Structure', 'designation': 'Rail %s 6 m' % mot,
                'quantite': 1, 'unite': 'u', 'spec': '', 'produit_id': None,
                'reference': None}]}
            entetes, lignes = table_nomenclature(resultat)
            with self.assertRaises(ExportRefuse, msg=mot):
                verifier_absence_de_prix(entetes, lignes)

    def test_la_reference_catalogue_reste_gardee(self):
        resultat = {'nomenclature': [{
            'categorie': 'Structure', 'designation': 'Rail', 'quantite': 1,
            'unite': 'u', 'spec': '', 'produit_id': 3,
            'reference': 'TARIF-2026'}]}
        entetes, lignes = table_nomenclature(resultat)
        with self.assertRaises(ExportRefuse):
            verifier_absence_de_prix(entetes, lignes)

    def test_un_en_tete_monetaire_est_refuse(self):
        with self.assertRaises(ExportRefuse):
            verifier_absence_de_prix(['Désignation', "Prix d'achat"], [])

    def test_export_refuse_dans_une_section_devient_rapport_refuse_400(self):
        resultat = {'nomenclature': [{
            'categorie': 'Structure', 'designation': 'Rail 120 MAD',
            'quantite': 1, 'unite': 'u', 'spec': '', 'produit_id': None,
            'reference': None}]}
        with self.assertRaises(RapportRefuse) as capture:
            html_de_section({'resultat': resultat, 'langue': 'fr'})
        self.assertEqual(capture.exception.champ, 'nomenclature')

    def test_le_plan_de_pose_refuse_un_mot_entier(self):
        with self.assertRaises(PlanDePoseRefuse):
            verifier_absence_d_argent('Onduleur (prix sur demande)')


class UneSeuleListeTest(SimpleTestCase):
    def test_une_seule_liste_de_mots(self):
        self.assertIs(export_tableur.MOTS_D_ARGENT, MOTS_D_ARGENT)
        self.assertIs(sld.MOTS_D_ARGENT, MOTS_D_ARGENT)
        self.assertFalse(hasattr(planche, 'MOTS_D_ARGENT_POSE'))
