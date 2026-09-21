"""Tests XPAI13 — Export XML EDI SIMPL-IR (état 9421).

Couvre : ``export_xml_simpl_ir_9421`` produit un XML bien formé, valide
contre le schéma embarqué (``XSD_SIMPL_IR_9421``), avec des totaux
identiques à l'état JSON existant (``etat_ir_9421_annuel``) ; distingue
permanent/occasionnel par type de rémunération ; ``valider_xml_simpl_ir_9421``
détecte un XML mal formé et une structure non conforme.
"""
import xml.etree.ElementTree as ET
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import (
    ensure_defaults,
    etat_ir_9421_annuel,
    export_xml_simpl_ir_9421,
    generer_bulletin,
    valider_bulletin,
    valider_xml_simpl_ir_9421,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class ExportXmlSimplIr9421Tests(TestCase):
    def setUp(self):
        self.co = make_company('xpai13-xml')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _employe(self, mat, type_remuneration=ProfilPaie.TYPE_MENSUEL,
                 salaire=Decimal('10000')):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='Nom' + mat, prenom='P')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=type_remuneration,
            salaire_base=salaire, affilie_cnss=True, affilie_amo=True)
        b = generer_bulletin(profil, self.periode)
        valider_bulletin(b)
        return profil

    def test_xml_bien_forme(self):
        self._employe('A1')
        xml = export_xml_simpl_ir_9421(self.co, 2026)
        # Ne lève pas ParseError.
        ET.fromstring(xml)

    def test_racine_et_structure(self):
        self._employe('A2')
        xml = export_xml_simpl_ir_9421(self.co, 2026)
        root = ET.fromstring(xml)
        self.assertEqual(root.tag, 'Etat9421')
        self.assertIsNotNone(root.find('Entete'))
        self.assertIsNotNone(root.find('Totaux'))
        self.assertEqual(len(root.findall('Salarie')), 1)

    def test_totaux_identiques_a_etat_json(self):
        self._employe('A3')
        self._employe('A4')
        etat = etat_ir_9421_annuel(self.co, 2026)
        xml = export_xml_simpl_ir_9421(self.co, 2026)
        root = ET.fromstring(xml)
        totaux = root.find('Totaux')
        self.assertEqual(
            totaux.attrib['totalBrutImposable'],
            str(etat['total_brut_imposable']))
        self.assertEqual(
            totaux.attrib['totalIr'], str(etat['total_ir']))

    def test_categorie_permanent_vs_occasionnel(self):
        self._employe('A5', type_remuneration=ProfilPaie.TYPE_MENSUEL)
        self._employe('A6', type_remuneration=ProfilPaie.TYPE_JOURNALIER)
        xml = export_xml_simpl_ir_9421(self.co, 2026)
        root = ET.fromstring(xml)
        categories = {s.attrib['categorie'] for s in root.findall('Salarie')}
        self.assertEqual(categories, {'permanent', 'occasionnel'})

    def test_valide_contre_schema_embarque(self):
        self._employe('A7')
        xml = export_xml_simpl_ir_9421(self.co, 2026)
        self.assertTrue(valider_xml_simpl_ir_9421(xml))


class ValiderXmlSimplIr9421Tests(TestCase):
    def test_mal_forme_leve(self):
        with self.assertRaises(ValueError):
            valider_xml_simpl_ir_9421('<Etat9421><Entete></Etat9421>')

    def test_racine_incorrecte_leve(self):
        with self.assertRaises(ValueError):
            valider_xml_simpl_ir_9421(
                '<AutreRacine><Entete annee="2026" '
                'nombreSalaries="0"/><Totaux totalBrutImposable="0" '
                'totalNetImposable="0" totalIr="0"/></AutreRacine>')

    def test_entete_manquante_leve(self):
        with self.assertRaises(ValueError):
            valider_xml_simpl_ir_9421(
                '<Etat9421><Totaux totalBrutImposable="0" '
                'totalNetImposable="0" totalIr="0"/></Etat9421>')

    def test_attribut_manquant_leve(self):
        with self.assertRaises(ValueError):
            valider_xml_simpl_ir_9421(
                '<Etat9421><Entete annee="2026"/>'
                '<Totaux totalBrutImposable="0" totalNetImposable="0" '
                'totalIr="0"/></Etat9421>')

    def test_document_conforme_valide(self):
        xml = (
            '<Etat9421><Entete annee="2026" nombreSalaries="0"/>'
            '<Totaux totalBrutImposable="0.00" totalNetImposable="0.00" '
            'totalIr="0.00"/></Etat9421>')
        self.assertTrue(valider_xml_simpl_ir_9421(xml))
