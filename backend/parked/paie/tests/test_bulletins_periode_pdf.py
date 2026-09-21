"""Tests ZPAI5 — Impression en lot des bulletins d'une période (PDF fusionné).

Couvre :
* ``render_bulletins_periode_pdf`` — ne fusionne que les bulletins VALIDÉS
  (exclut les brouillons), ordre matricule/nom, lève ``ValueError`` si aucun
  bulletin validé.
* Comptage de pages du PDF fusionné (une page par bulletin, moteur WeasyPrint
  réel — skip si WeasyPrint est absent de l'environnement, comme le reste de
  la suite paie qui ne teste le rendu PDF qu'au niveau HTML).
* L'action API ``periodes/<id>/bulletins-pdf/`` — 400 propre sans bulletin
  validé.
"""
from decimal import Decimal
from unittest import skipUnless

from django.test import TestCase, tag
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser as User
from apps.paie import builders
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import ensure_defaults, generer_bulletin, valider_bulletin
from apps.rh.models import DossierEmploye

try:
    import weasyprint  # noqa: F401
    import fitz  # noqa: F401
    _PDF_LIBS_DISPONIBLES = True
except ImportError:
    _PDF_LIBS_DISPONIBLES = False


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class BulletinsPeriodePdfSelectionTests(TestCase):
    """Sélection/ordre/exclusion — sans dépendre de WeasyPrint (monkeypatch)."""

    def setUp(self):
        self.co = make_company('lot-pdf')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

        def make_profil(matricule, nom):
            dossier = DossierEmploye.objects.create(
                company=self.co, matricule=matricule, nom=nom, prenom='X')
            return ProfilPaie.objects.create(
                company=self.co, employe=dossier,
                type_remuneration=ProfilPaie.TYPE_MENSUEL,
                salaire_base=Decimal('8000'), affilie_cnss=True,
                affilie_amo=True)

        self.profil_b = make_profil('B002', 'Bravo')
        self.profil_a = make_profil('A001', 'Alpha')
        self.profil_c = make_profil('C003', 'Charlie')

        self.bulletin_a = generer_bulletin(self.profil_a, self.periode)
        valider_bulletin(self.bulletin_a)
        self.bulletin_b = generer_bulletin(self.profil_b, self.periode)
        valider_bulletin(self.bulletin_b)
        # Brouillon volontairement laissé non validé.
        self.brouillon_c = generer_bulletin(self.profil_c, self.periode)

    def test_aucun_bulletin_valide_leve(self):
        vide_periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=7)
        with self.assertRaises(ValueError):
            builders.render_bulletins_periode_pdf(vide_periode)

    @staticmethod
    def _pdf_page_minimale():
        """Un PDF valide d'une page (fitz), sans dépendre de WeasyPrint."""
        import fitz

        doc = fitz.open()
        try:
            doc.new_page()
            return doc.tobytes()
        finally:
            doc.close()

    def test_ordre_et_exclusion_brouillon(self):
        appels = []

        def _fake_render(bulletin):
            appels.append(bulletin)
            return self._pdf_page_minimale()

        original = builders.render_bulletin_pdf
        try:
            builders.render_bulletin_pdf = _fake_render
            pdf_bytes = builders.render_bulletins_periode_pdf(self.periode)
        finally:
            builders.render_bulletin_pdf = original
        # Seuls les 2 bulletins validés sont pris, dans l'ordre matricule.
        self.assertEqual(len(appels), 2)
        self.assertEqual(appels[0].id, self.bulletin_a.id)
        self.assertEqual(appels[1].id, self.bulletin_b.id)
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        try:
            self.assertEqual(doc.page_count, 2)
        finally:
            doc.close()


@tag('pdf')  # WOW5 — rendu WeasyPrint réel → hors gate rapide (tourne dans release-verify)
@skipUnless(_PDF_LIBS_DISPONIBLES, "WeasyPrint/PyMuPDF indisponibles ici")
class BulletinsPeriodePdfRealTests(TestCase):
    def setUp(self):
        self.co = make_company('lot-pdf-real')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.bulletins = []
        for i in range(3):
            dossier = DossierEmploye.objects.create(
                company=self.co, matricule=f'R00{i}', nom=f'Nom{i}',
                prenom='Test')
            profil = ProfilPaie.objects.create(
                company=self.co, employe=dossier,
                type_remuneration=ProfilPaie.TYPE_MENSUEL,
                salaire_base=Decimal('9000'), affilie_cnss=True,
                affilie_amo=True)
            bulletin = generer_bulletin(profil, self.periode)
            valider_bulletin(bulletin)
            self.bulletins.append(bulletin)

    def test_pdf_fusionne_contient_n_pages(self):
        pdf_bytes = builders.render_bulletins_periode_pdf(self.periode)
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        try:
            self.assertEqual(doc.page_count, 3)
        finally:
            doc.close()

    def test_action_api_bulletins_pdf(self):
        user = make_user(self.co, 'lot-pdf-user')
        resp = auth(user).get(
            f'/api/django/paie/periodes/{self.periode.id}/bulletins-pdf/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_action_api_400_sans_bulletin_valide(self):
        user = make_user(self.co, 'lot-pdf-user2')
        vide_periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=8)
        resp = auth(user).get(
            f'/api/django/paie/periodes/{vide_periode.id}/bulletins-pdf/')
        self.assertEqual(resp.status_code, 400)
