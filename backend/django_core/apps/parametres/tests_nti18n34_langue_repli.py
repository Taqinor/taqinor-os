"""NTI18N34 — CompanyProfile.langue_repli + son usage par i18n_resolver.

`tests_nti18n4_i18n_resolver.py` (NTI18N4, déjà mergé) couvre le comportement
DÉFENSIF d'avant cette tâche (champ absent) et reste vrai après elle (défaut
'fr' du modèle produit le même résultat) — non dupliqué ici. Ce fichier
couvre le comportement NOUVEAU : une société qui choisit explicitement une
langue de repli différente de FR.
"""
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.parametres.models_company import CompanyProfile
from apps.parametres.i18n_resolver import resolve_langue_sortie


def _company(slug='nti18n34-co', nom='NTI18N34 Co'):
    return Company.objects.create(nom=nom, slug=slug)


class CompanyProfileLangueRepliFieldTests(TestCase):
    def test_default_is_fr_for_existing_companies(self):
        profile = CompanyProfile.get(_company())
        self.assertEqual(profile.langue_repli, 'fr')


class ResolveLangueSortieAvecLangueRepliTests(TestCase):
    def test_company_langue_repli_en_used_when_no_client(self):
        company = _company('nti18n34-co-2', 'NTI18N34 Co 2')
        profile = CompanyProfile.get(company)
        profile.langue_repli = 'en'
        profile.save(update_fields=['langue_repli'])
        self.assertEqual(resolve_langue_sortie(company=company), 'en')

    def test_company_langue_repli_ar_used_when_client_has_no_preference(self):
        company = _company('nti18n34-co-3', 'NTI18N34 Co 3')
        profile = CompanyProfile.get(company)
        profile.langue_repli = 'ar'
        profile.save(update_fields=['langue_repli'])
        client = Client.objects.create(company=company, nom='Client sans pref')
        self.assertEqual(
            resolve_langue_sortie(client=client, company=company), 'ar')

    def test_client_langue_document_still_wins_over_company_repli(self):
        # Ordre de priorité NTI18N4 inchangé : Client.langue_document > repli
        # société, même quand la société a choisi une langue de repli non-FR.
        company = _company('nti18n34-co-4', 'NTI18N34 Co 4')
        profile = CompanyProfile.get(company)
        profile.langue_repli = 'en'
        profile.save(update_fields=['langue_repli'])
        client = Client.objects.create(
            company=company, nom='Client AR', langue_document='ar')
        self.assertEqual(
            resolve_langue_sortie(client=client, company=company), 'ar')

    def test_explicit_langue_still_wins_over_company_repli(self):
        company = _company('nti18n34-co-5', 'NTI18N34 Co 5')
        profile = CompanyProfile.get(company)
        profile.langue_repli = 'ar'
        profile.save(update_fields=['langue_repli'])
        self.assertEqual(
            resolve_langue_sortie(langue_explicite='en', company=company),
            'en')

    def test_existing_company_without_explicit_choice_still_resolves_fr(self):
        # Non-régression : une société qui n'a jamais touché ce réglage
        # continue de générer ses documents en FR par défaut.
        company = _company('nti18n34-co-6', 'NTI18N34 Co 6')
        self.assertEqual(resolve_langue_sortie(company=company), 'fr')
