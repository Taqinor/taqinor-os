"""NTI18N20 — Pack pays Espagne, préparation de champs (squelette, non actif).

Couvre uniquement le périmètre `apps/parametres` (`CompanyProfile`) : le
champ NIF/CIF côté `Client` (apps.crm) et le dictionnaire de libellés PDF
espagnols (`apps.ventes.quote_engine.i18n_labels`, NTI18N5 — non construit)
sont HORS périmètre de cette lane (autre app) et ne sont pas couverts ici.

Validation de forme du NIF/CIF : déjà testée par NTI18N19
(`tests_nti18n19_tax_id_validators.py`, `validate_nif_cif_es`) — non dupliquée.
"""
from django.test import TestCase

from authentication.models import Company
from apps.parametres.models_company import CompanyProfile


def _company(slug='nti18n20-co', nom='NTI18N20 Co'):
    return Company.objects.create(nom=nom, slug=slug)


class CompanyProfileEsPrepFieldsTests(TestCase):
    def test_fields_default_empty_for_existing_companies(self):
        company = _company()
        profile = CompanyProfile.get(company)
        self.assertEqual(profile.nif_cif, '')
        self.assertEqual(profile.adresse_provincia, '')
        self.assertEqual(profile.adresse_comunidad_autonoma, '')

    def test_fields_are_editable_and_optional(self):
        company = _company('nti18n20-co-2', 'NTI18N20 Co 2')
        profile = CompanyProfile.get(company)
        profile.nif_cif = 'B12345674'
        profile.adresse_provincia = 'Madrid'
        profile.adresse_comunidad_autonoma = 'Comunidad de Madrid'
        profile.save(update_fields=[
            'nif_cif', 'adresse_provincia', 'adresse_comunidad_autonoma'])
        profile.refresh_from_db()
        self.assertEqual(profile.nif_cif, 'B12345674')
        self.assertEqual(profile.adresse_provincia, 'Madrid')
        self.assertEqual(
            profile.adresse_comunidad_autonoma, 'Comunidad de Madrid')

    def test_existing_company_pdf_rendering_untouched_by_default(self):
        # Non-régression : une société sans ces champs renseignés garde un
        # profil strictement identique à avant cette tâche (aucun champ requis,
        # aucune validation bloquante branchée).
        company = _company('nti18n20-co-3', 'NTI18N20 Co 3')
        profile = CompanyProfile.get(company)
        self.assertFalse(profile.nif_cif)
        self.assertFalse(profile.adresse_provincia)
        self.assertFalse(profile.adresse_comunidad_autonoma)
