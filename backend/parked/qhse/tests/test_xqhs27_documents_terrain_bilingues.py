"""Tests XQHS27 — Documents terrain QHSE imprimables bilingues FR/AR.

Couvre les trois documents (permis de travail, induction sécurité, causerie
sécurité) : rendu HTML propre (pas de jeton brut), aucun prix, bascule
FR/AR (RTL + libellés arabes non "tofu" — au moins un caractère arabe
présent), endpoint PDF (WeasyPrint mocké via ``sys.modules``, même patron
que ``test_xqhs7_analyse_ncr.py``), scoping société (404 hors société), et
lecture EXCLUSIVE de ``CauserieSecurite`` (modèle ``rh``) via
``apps.rh.selectors.causerie_securite_for_id`` (jamais ``rh.models`` importé
depuis ``qhse``).
"""
import sys
import types
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import InductionSecurite, PermisTravail
from apps.qhse.pdf_terrain import (
    _causerie_securite_html, _induction_securite_html, _permis_travail_html,
)
from apps.rh.models import CauserieParticipant, CauserieSecurite, DossierEmploye

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _fake_weasyprint():
    """Faux module ``weasyprint`` : ``write_pdf`` mirrors the real WeasyPrint
    API (``target=None`` accepte à la fois ``write_pdf()`` [renvoie les
    octets] et ``write_pdf(buf)`` [écrit dans la cible]) — compatible avec
    ``core.pdf.render_pdf`` (ARC11/ARC12, appel sans cible) ET tout appelant
    encore non migré qui passerait un buffer."""
    fake_module = types.ModuleType('weasyprint')

    def _write_pdf(self, target=None):
        data = b'%PDF-1.4 fake'
        if target is not None:
            target.write(data)
            return None
        return data

    fake_html_instance = type('FakeHTML', (), {'write_pdf': _write_pdf})()
    fake_module.HTML = lambda string: fake_html_instance
    return fake_module


def make_permis(company, **kwargs):
    defaults = dict(
        titre='Pose toiture', type_permis='hauteur', statut='brouillon',
        reference='PT-XQHS27-0001',
        date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 30))
    defaults.update(kwargs)
    return PermisTravail.objects.create(company=company, **defaults)


def make_induction(company, **kwargs):
    defaults = dict(
        personne_nom='Karim Alaoui', est_sous_traitant=False,
        date_induction=date(2026, 6, 2), anime_par='Sami',
        themes='EPI, circulation engins')
    defaults.update(kwargs)
    return InductionSecurite.objects.create(company=company, **defaults)


def make_causerie(company, **kwargs):
    defaults = dict(theme='Port du harnais', date_causerie=date(2026, 6, 3))
    defaults.update(kwargs)
    return CauserieSecurite.objects.create(company=company, **defaults)


class Xqhs27HtmlRenderingTests(TestCase):
    """Le HTML généré ne laisse aucun jeton brut, aucun prix."""

    def setUp(self):
        self.company = make_company('co-xqhs27-html', 'CoXqhs27Html')

    def test_permis_html_fr_pas_de_jeton_brut(self):
        permis = make_permis(self.company)
        html = _permis_travail_html(permis, 'fr')
        self.assertNotIn('{{', html)
        self.assertNotIn('}}', html)
        self.assertIn('Pose toiture', html)
        self.assertNotIn('prix_achat', html)

    def test_permis_html_ar_rtl_et_glyphes_arabes(self):
        permis = make_permis(self.company)
        html = _permis_travail_html(permis, 'ar')
        self.assertIn("dir='rtl'", html)
        # Au moins un caractère arabe présent (pas de "tofu" — vrai texte AR).
        self.assertTrue(any('؀' <= ch <= 'ۿ' for ch in html))

    def test_induction_html_fr(self):
        induction = make_induction(self.company)
        html = _induction_securite_html(induction, 'fr')
        self.assertIn('Karim Alaoui', html)
        self.assertNotIn('{{', html)

    def test_induction_html_ar(self):
        induction = make_induction(
            self.company, est_sous_traitant=True,
            entreprise_externe='Sous-traitant SARL')
        html = _induction_securite_html(induction, 'ar')
        self.assertIn("dir='rtl'", html)
        self.assertIn('Sous-traitant SARL', html)

    def test_causerie_html_emargement(self):
        causerie = make_causerie(self.company)
        employe = DossierEmploye.objects.create(
            company=self.company, matricule='M1', nom='Fassi', prenom='Amine')
        CauserieParticipant.objects.create(
            company=self.company, causerie=causerie, participant=employe,
            present=True)
        html = _causerie_securite_html(causerie, 'fr')
        self.assertIn('Port du harnais', html)
        self.assertIn('Fassi', html)
        self.assertNotIn('{{', html)

    def test_causerie_html_ar(self):
        causerie = make_causerie(self.company)
        html = _causerie_securite_html(causerie, 'ar')
        self.assertIn("dir='rtl'", html)


class Xqhs27PdfEndpointTests(TestCase):
    """Endpoints PDF : scoping société + WeasyPrint mocké (rapide, sans lib
    lourde), même patron que ``test_xqhs7_analyse_ncr.py``."""

    def setUp(self):
        self.company = make_company('co-xqhs27-pdf', 'CoXqhs27Pdf')
        self.other_company = make_company('co-xqhs27-pdf-2', 'CoXqhs27Pdf2')
        self.user = make_user(self.company, 'xqhs27-resp')
        self.client_api = auth_client(self.user)

    def test_permis_pdf_endpoint(self):
        permis = make_permis(self.company)
        with patch.dict(sys.modules, {'weasyprint': _fake_weasyprint()}):
            resp = self.client_api.get(
                f'/api/django/qhse/permis-travail/{permis.pk}/pdf/?lang=ar')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertEqual(resp.content, b'%PDF-1.4 fake')

    def test_permis_pdf_hors_societe_404(self):
        permis = make_permis(self.other_company)
        with patch.dict(sys.modules, {'weasyprint': _fake_weasyprint()}):
            resp = self.client_api.get(
                f'/api/django/qhse/permis-travail/{permis.pk}/pdf/')
        self.assertEqual(resp.status_code, 404)

    def test_induction_pdf_endpoint(self):
        induction = make_induction(self.company)
        with patch.dict(sys.modules, {'weasyprint': _fake_weasyprint()}):
            resp = self.client_api.get(
                f'/api/django/qhse/inductions-securite/{induction.pk}/pdf/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b'%PDF-1.4 fake')

    def test_causerie_pdf_endpoint(self):
        causerie = make_causerie(self.company)
        with patch.dict(sys.modules, {'weasyprint': _fake_weasyprint()}):
            resp = self.client_api.get(
                f'/api/django/qhse/causeries/{causerie.pk}/pdf/?lang=fr')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b'%PDF-1.4 fake')

    def test_causerie_pdf_hors_societe_404(self):
        causerie = make_causerie(self.other_company)
        with patch.dict(sys.modules, {'weasyprint': _fake_weasyprint()}):
            resp = self.client_api.get(
                f'/api/django/qhse/causeries/{causerie.pk}/pdf/')
        self.assertEqual(resp.status_code, 404)

    def test_causerie_pdf_inexistante_404(self):
        with patch.dict(sys.modules, {'weasyprint': _fake_weasyprint()}):
            resp = self.client_api.get('/api/django/qhse/causeries/999999/pdf/')
        self.assertEqual(resp.status_code, 404)
