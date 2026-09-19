"""NTI18N22 — décomposition optionnelle de l'adresse libre (CompanyProfile).

Couvre le périmètre `apps/parametres` uniquement : la décomposition côté
`Client` (apps.crm) et le câblage du moteur PDF (apps.ventes.quote_engine)
sont HORS périmètre de cette lane (autre app) — non couverts ici. Ce fichier
teste le modèle (champs additifs, optionnels) et le sélecteur
`selectors.adresse_affichage`, prêt à être consommé plus tard par le moteur
de rendu.
"""
from django.test import TestCase

from authentication.models import Company
from apps.parametres.models_company import CompanyProfile
from apps.parametres.selectors import adresse_affichage


def _company(slug='nti18n22-co', nom='NTI18N22 Co'):
    return Company.objects.create(nom=nom, slug=slug)


class CompanyProfileAdresseStructureeFieldsTests(TestCase):
    def test_fields_default_empty(self):
        profile = CompanyProfile.get(_company())
        self.assertEqual(profile.adresse_rue, '')
        self.assertEqual(profile.adresse_code_postal, '')
        self.assertEqual(profile.adresse_ville, '')
        self.assertEqual(profile.adresse_pays, '')

    def test_fields_are_editable(self):
        profile = CompanyProfile.get(_company('nti18n22-co-2', 'NTI18N22 Co 2'))
        profile.adresse_rue = '12 rue de la Paix'
        profile.adresse_code_postal = '20000'
        profile.adresse_ville = 'Casablanca'
        profile.adresse_pays = 'MA'
        profile.save(update_fields=[
            'adresse_rue', 'adresse_code_postal', 'adresse_ville',
            'adresse_pays'])
        profile.refresh_from_db()
        self.assertEqual(profile.adresse_rue, '12 rue de la Paix')
        self.assertEqual(profile.adresse_ville, 'Casablanca')


class AdresseAffichageSelectorTests(TestCase):
    def test_no_company_returns_empty_string(self):
        self.assertEqual(adresse_affichage(None), '')

    def test_falls_back_to_free_text_when_structured_fields_empty(self):
        # Non-régression : un client existant sans champs structurés continue
        # de s'afficher IDENTIQUEMENT (son adresse libre, telle quelle).
        company = _company('nti18n22-co-3', 'NTI18N22 Co 3')
        profile = CompanyProfile.get(company)
        profile.adresse = '45 avenue Hassan II, Rabat'
        profile.save(update_fields=['adresse'])
        self.assertEqual(
            adresse_affichage(company), '45 avenue Hassan II, Rabat')

    def test_uses_structured_fields_when_at_least_one_is_filled(self):
        company = _company('nti18n22-co-4', 'NTI18N22 Co 4')
        profile = CompanyProfile.get(company)
        profile.adresse = 'texte libre ignoré une fois structuré renseigné'
        profile.adresse_rue = '12 rue de la Paix'
        profile.adresse_code_postal = '20000'
        profile.adresse_ville = 'Casablanca'
        profile.adresse_pays = 'MA'
        profile.save(update_fields=[
            'adresse', 'adresse_rue', 'adresse_code_postal',
            'adresse_ville', 'adresse_pays'])
        self.assertEqual(
            adresse_affichage(company),
            '12 rue de la Paix, 20000 Casablanca, MA')

    def test_partial_structured_fields_still_used_over_free_text(self):
        company = _company('nti18n22-co-5', 'NTI18N22 Co 5')
        profile = CompanyProfile.get(company)
        profile.adresse = 'texte libre'
        profile.adresse_ville = 'Tanger'
        profile.save(update_fields=['adresse', 'adresse_ville'])
        self.assertEqual(adresse_affichage(company), 'Tanger')
