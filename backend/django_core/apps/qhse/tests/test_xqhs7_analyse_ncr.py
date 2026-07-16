"""Tests XQHS7 — Analyse structurée 5-Pourquoi / 8D sur NCR + export PDF interne.

Couvre :

* la création/mise à jour de l'``AnalyseNcr`` (5-Pourquoi ≤5, 8D partiel) ;
* la validation ``clean()`` (5-Pourquoi borné) ;
* le HTML de rendu (pur, sans WeasyPrint) reprend le 5-Pourquoi, le 8D et
  les CAPA liées, sans jeton brut — jamais de prix d'achat ;
* le scoping société.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from authentication.models import Company

from apps.qhse.models import (
    ActionCorrectivePreventive, AnalyseNcr, NonConformite,
)
from apps.qhse.services import (
    _analyse_ncr_html, enregistrer_analyse_ncr, rendre_analyse_ncr_pdf,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_ncr(company, titre='NCR test'):
    return NonConformite.objects.create(company=company, titre=titre)


class EnregistrerAnalyseNcrTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs7-enr', 'CoXqhs7Enr')

    def test_cree_analyse_5_pourquoi(self):
        ncr = make_ncr(self.company)
        analyse = enregistrer_analyse_ncr(ncr, cinq_pourquoi=[
            {'pourquoi': 'Pourquoi 1', 'reponse': 'Réponse 1'},
        ])
        self.assertEqual(len(analyse.cinq_pourquoi), 1)
        self.assertEqual(analyse.non_conformite, ncr)

    def test_reutilise_analyse_existante(self):
        ncr = make_ncr(self.company)
        enregistrer_analyse_ncr(ncr, cinq_pourquoi=[{'pourquoi': 'P1', 'reponse': 'R1'}])
        enregistrer_analyse_ncr(ncr, huit_d={'D1': {'texte': 'Équipe', 'statut': 'fait'}})
        self.assertEqual(AnalyseNcr.objects.filter(non_conformite=ncr).count(), 1)
        analyse = AnalyseNcr.objects.get(non_conformite=ncr)
        self.assertEqual(len(analyse.cinq_pourquoi), 1)
        self.assertIn('D1', analyse.huit_d)

    def test_huit_d_merge_conserve_disciplines_existantes(self):
        ncr = make_ncr(self.company)
        enregistrer_analyse_ncr(ncr, huit_d={'D1': {'texte': 'Équipe', 'statut': 'fait'}})
        analyse = enregistrer_analyse_ncr(
            ncr, huit_d={'D2': {'texte': 'Problème', 'statut': 'fait'}})
        self.assertIn('D1', analyse.huit_d)
        self.assertIn('D2', analyse.huit_d)

    def test_plus_de_5_pourquoi_leve_erreur(self):
        ncr = make_ncr(self.company)
        trop = [{'pourquoi': f'P{i}', 'reponse': f'R{i}'} for i in range(6)]
        with self.assertRaises(ValidationError):
            enregistrer_analyse_ncr(ncr, cinq_pourquoi=trop)


class AnalyseNcrHtmlTests(TestCase):
    """``_analyse_ncr_html`` est pur (pas de WeasyPrint) — testable partout."""

    def setUp(self):
        self.company = make_company('co-xqhs7-html', 'CoXqhs7Html')

    def test_html_contient_titre_et_pourquoi(self):
        ncr = make_ncr(self.company, titre='Défaut étanchéité')
        analyse = enregistrer_analyse_ncr(ncr, cinq_pourquoi=[
            {'pourquoi': 'Pourquoi fuite ?', 'reponse': 'Joint mal posé'},
        ])
        html = _analyse_ncr_html(analyse)
        self.assertIn('Défaut étanchéité', html)
        self.assertIn('Pourquoi fuite ?', html)
        self.assertIn('Joint mal posé', html)

    def test_html_contient_8d(self):
        ncr = make_ncr(self.company)
        analyse = enregistrer_analyse_ncr(
            ncr, huit_d={'D1': {'texte': 'Équipe QHSE', 'statut': 'fait'}})
        html = _analyse_ncr_html(analyse)
        self.assertIn('Équipe QHSE', html)

    def test_html_contient_capa_liees(self):
        ncr = make_ncr(self.company)
        ActionCorrectivePreventive.objects.create(
            company=self.company, non_conformite=ncr,
            description='Reprendre le joint')
        analyse = enregistrer_analyse_ncr(ncr, cinq_pourquoi=[])
        html = _analyse_ncr_html(analyse)
        self.assertIn('Reprendre le joint', html)

    def test_html_ne_laisse_aucun_jeton_brut(self):
        ncr = make_ncr(self.company)
        analyse = enregistrer_analyse_ncr(ncr, cinq_pourquoi=[])
        html = _analyse_ncr_html(analyse)
        self.assertNotIn('{{', html)
        self.assertNotIn('}}', html)

    def test_html_pas_de_prix_achat(self):
        ncr = make_ncr(self.company)
        analyse = enregistrer_analyse_ncr(ncr, cinq_pourquoi=[])
        html = _analyse_ncr_html(analyse)
        self.assertNotIn('prix_achat', html)


class RendreAnalyseNcrPdfTests(TestCase):
    """``rendre_analyse_ncr_pdf`` importe WeasyPrint FONCTION-LOCAL — on mocke
    le module entier via sys.modules pour rester rapide et sans dépendance
    lourde au test (même approche que les autres PDF internes de l'app)."""

    def setUp(self):
        self.company = make_company('co-xqhs7-pdf', 'CoXqhs7Pdf')

    def test_appelle_weasyprint(self):
        import sys
        import types
        ncr = make_ncr(self.company)
        analyse = enregistrer_analyse_ncr(ncr, cinq_pourquoi=[])

        fake_module = types.ModuleType('weasyprint')

        def _write_pdf(self, target=None):
            data = b'%PDF-1.4 fake'
            if target is not None:
                target.write(data)
                return None
            return data

        fake_html_instance = type('FakeHTML', (), {'write_pdf': _write_pdf})()
        fake_module.HTML = lambda string: fake_html_instance

        with patch.dict(sys.modules, {'weasyprint': fake_module}):
            pdf_bytes = rendre_analyse_ncr_pdf(analyse)
        self.assertEqual(pdf_bytes, b'%PDF-1.4 fake')
