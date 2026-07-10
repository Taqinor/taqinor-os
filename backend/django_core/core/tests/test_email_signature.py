"""SCA25 — sélecteur ``core.selectors.resolve_email_signature``.

Couvre le repli neutre « L'équipe {nom} », l'usage d'un ``BrandedTemplate``
(kind ``email``, code ``signature``) rendu par ``core.templating``, le repli
quand le modèle est vide/inactif, et l'isolation par société. ``core`` reste
FONDATION : le nom de la société est TOUJOURS fourni par l'appelant (jamais lu
d'un modèle métier ici).
"""
from django.test import TestCase

from authentication.models import Company
from core.models import BrandedTemplate
from core.selectors import EMAIL_SIGNATURE_CODE, resolve_email_signature


class ResolveEmailSignatureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME Solar')
        cls.other = Company.objects.create(nom='Autre Société')

    def test_fallback_uses_company_name(self):
        """Sans modèle, la signature est « L'équipe {nom fourni} »."""
        self.assertEqual(
            resolve_email_signature(self.company, 'ACME Solar'),
            "L'équipe ACME Solar")

    def test_fallback_founder_name_preserves_taqinor(self):
        """Le fondateur (nom=TAQINOR) obtient « L'équipe TAQINOR » PAR LA
        DONNÉE — aucun nom codé en dur."""
        founder = Company.objects.create(nom='TAQINOR')
        self.assertEqual(
            resolve_email_signature(founder, 'TAQINOR'),
            "L'équipe TAQINOR")

    def test_fallback_without_name(self):
        """Nom vide → « L'équipe » seul (jamais « L'équipe None »)."""
        self.assertEqual(resolve_email_signature(self.company, ''), "L'équipe")

    def test_none_company_returns_fallback(self):
        self.assertEqual(
            resolve_email_signature(None, 'ACME Solar'), "L'équipe ACME Solar")

    def test_branded_template_overrides_fallback(self):
        """Un BrandedTemplate email/signature actif pilote la signature."""
        BrandedTemplate.objects.create(
            company=self.company, kind=BrandedTemplate.KIND_EMAIL,
            code=EMAIL_SIGNATURE_CODE, nom='Signature',
            corps='Bien à vous,\nLe pôle commercial {{ nom }}')
        out = resolve_email_signature(self.company, 'ACME Solar')
        self.assertEqual(out, 'Bien à vous,\nLe pôle commercial ACME Solar')

    def test_branded_template_extra_context_placeholder(self):
        """Les placeholders reçoivent aussi le contexte additionnel (référence)."""
        BrandedTemplate.objects.create(
            company=self.company, kind=BrandedTemplate.KIND_EMAIL,
            code=EMAIL_SIGNATURE_CODE, nom='Signature',
            corps='Réf. {{ reference }} — {{ nom }}')
        out = resolve_email_signature(
            self.company, 'ACME Solar', reference='DEV-1')
        self.assertEqual(out, 'Réf. DEV-1 — ACME Solar')

    def test_empty_template_falls_back(self):
        """Un modèle au corps vide retombe sur « L'équipe {nom} »."""
        BrandedTemplate.objects.create(
            company=self.company, kind=BrandedTemplate.KIND_EMAIL,
            code=EMAIL_SIGNATURE_CODE, nom='Signature', corps='   ')
        self.assertEqual(
            resolve_email_signature(self.company, 'ACME Solar'),
            "L'équipe ACME Solar")

    def test_inactive_template_ignored(self):
        BrandedTemplate.objects.create(
            company=self.company, kind=BrandedTemplate.KIND_EMAIL,
            code=EMAIL_SIGNATURE_CODE, nom='Signature',
            corps='Cordialement, le pôle', actif=False)
        self.assertEqual(
            resolve_email_signature(self.company, 'ACME Solar'),
            "L'équipe ACME Solar")

    def test_isolation_between_companies(self):
        """Le modèle d'une société ne fuit pas sur l'autre."""
        BrandedTemplate.objects.create(
            company=self.company, kind=BrandedTemplate.KIND_EMAIL,
            code=EMAIL_SIGNATURE_CODE, nom='Signature',
            corps='Signature ACME')
        self.assertEqual(
            resolve_email_signature(self.other, 'Autre Société'),
            "L'équipe Autre Société")
