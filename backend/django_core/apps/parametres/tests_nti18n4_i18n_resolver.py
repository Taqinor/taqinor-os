"""NTI18N4 — apps/parametres/i18n_resolver.py.

Couvre la chaîne de priorité complète : langue explicite > Client.
langue_document > repli société (NTI18N34, pas encore construit — lu
défensivement) > FR. Utilisé par `/proposal` (query param `?langue=`) et par
les PDF factures/BL legacy (`apps.ventes.utils.libelles_ar.document_langue`,
généralisée par cette tâche).
"""
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.parametres.i18n_resolver import (
    LANGUE_PAR_DEFAUT, resolve_langue_sortie,
)


def _company(slug='nti18n4-co', nom='NTI18N4 Co'):
    return Company.objects.create(nom=nom, slug=slug)


class ResolveLangueSortieTests(TestCase):
    def setUp(self):
        self.company = _company()

    def test_no_args_returns_fr(self):
        self.assertEqual(resolve_langue_sortie(), LANGUE_PAR_DEFAUT)
        self.assertEqual(resolve_langue_sortie(), 'fr')

    def test_explicit_wins_over_everything(self):
        client = Client.objects.create(
            company=self.company, nom='Client AR', langue_document='ar')
        self.assertEqual(
            resolve_langue_sortie(
                langue_explicite='en', client=client, company=self.company),
            'en')

    def test_invalid_explicit_is_ignored_falls_through(self):
        client = Client.objects.create(
            company=self.company, nom='Client AR', langue_document='ar')
        # 'darija' n'est pas une langue d'INTERFACE supportée par ce cadre
        # (distinct de Lead.langue_preferee) : ignorée, la chaîne continue.
        self.assertEqual(
            resolve_langue_sortie(langue_explicite='darija', client=client),
            'ar')

    def test_client_langue_document_wins_over_company_and_default(self):
        client = Client.objects.create(
            company=self.company, nom='Client AR', langue_document='ar')
        self.assertEqual(
            resolve_langue_sortie(client=client, company=self.company), 'ar')

    def test_client_fr_is_a_valid_resolved_value(self):
        client = Client.objects.create(
            company=self.company, nom='Client FR', langue_document='fr')
        self.assertEqual(resolve_langue_sortie(client=client), 'fr')

    def test_no_client_no_company_falls_back_to_fr(self):
        self.assertEqual(resolve_langue_sortie(), 'fr')

    def test_company_without_langue_repli_field_never_raises(self):
        # NTI18N34 n'est pas construit : `CompanyProfile.langue_repli`
        # n'existe pas encore. La résolution doit rester silencieuse et
        # retomber sur FR, jamais lever d'AttributeError/exception.
        self.assertEqual(
            resolve_langue_sortie(client=None, company=self.company), 'fr')

    def test_client_without_langue_document_attribute_never_raises(self):
        class ObjetQuelconque:
            pass
        self.assertEqual(
            resolve_langue_sortie(client=ObjetQuelconque()), 'fr')
