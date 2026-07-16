"""Tests ARC6 — service de numérotation de fondation relogé (core.numbering).

Prouve que l'algorithme relogé produit EXACTEMENT les mêmes formats que
l'historique `apps.ventes.utils.references` (non-régression bit-identique), qu'il
suit la règle plus-haut-utilisé+1 (jamais count()+1), qu'il réessaie sur une course
de référence (deux sauvegardes concurrentes → numéros distincts, la perdante prend
le suivant), et que le shim ventes ré-exporte bien les mêmes objets que la fondation.

Le service métier (Devis/BonCommande/Facture) sert de modèle-cible réel : `core`
ne dépend d'aucune app métier — c'est le TEST (couche d'intégration) qui apporte le
modèle, la fonction elle-même le reçoit en paramètre.

Run :
    docker compose exec django_core python manage.py test \
        core.tests.test_numbering -v 2
"""
from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from core.numbering import next_reference, create_with_reference

MONTH = timezone.now().strftime('%Y%m')
YEAR = timezone.now().strftime('%Y')


def make_company(slug='core-num-co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': 'Core Numbering Co'},
    )
    return company


def make_client(company):
    from apps.crm.models import Client
    return Client.objects.create(
        company=company, nom='Num', prenom='Test',
        email='num@example.com', telephone='+212600000009', adresse='Rabat',
    )


def make_devis(company, client, reference):
    from apps.ventes.models import Devis
    return Devis.objects.create(
        company=company, reference=reference, client=client,
        statut='brouillon', taux_tva=Decimal('20.00'),
    )


class CoreNextReferenceTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)

    def test_starts_at_one_on_empty_table(self):
        from apps.ventes.models import Devis
        self.assertEqual(
            next_reference(Devis, 'DEV', self.company), f'DEV-{MONTH}-0001')

    def test_uses_highest_existing_number_not_the_count(self):
        # Une seule ligne numérotée -0002 : count (1) régénérerait -0002 et
        # planterait — le service DOIT renvoyer -0003 (plus-haut-utilisé+1).
        from apps.ventes.models import Devis
        make_devis(self.company, self.client_obj, f'DEV-{MONTH}-0002')
        self.assertEqual(
            next_reference(Devis, 'DEV', self.company), f'DEV-{MONTH}-0003')

    def test_clears_gaps(self):
        from apps.ventes.models import Devis
        make_devis(self.company, self.client_obj, f'DEV-{MONTH}-0001')
        make_devis(self.company, self.client_obj, f'DEV-{MONTH}-0010')
        self.assertEqual(
            next_reference(Devis, 'DEV', self.company), f'DEV-{MONTH}-0011')

    def test_per_company_isolation(self):
        from apps.crm.models import Client
        from apps.ventes.models import Devis
        other = make_company(slug='core-num-other')
        other_client = Client.objects.create(
            company=other, nom='Autre', email='a@example.com',
            telephone='+212600000010', adresse='Fès',
        )
        make_devis(other, other_client, f'DEV-{MONTH}-0042')
        self.assertEqual(
            next_reference(Devis, 'DEV', self.company), f'DEV-{MONTH}-0001')

    def test_custom_padding_and_periods_match_historical(self):
        from apps.ventes.models import Devis
        # Défauts explicites = forme mensuelle historique 4-pad.
        self.assertEqual(
            next_reference(Devis, 'DEV', self.company, padding=4, period='monthly'),
            f'DEV-{MONTH}-0001')
        self.assertEqual(
            next_reference(Devis, 'DEV', self.company, padding=6),
            f'DEV-{MONTH}-000001')
        self.assertEqual(
            next_reference(Devis, 'DEV', self.company, period='yearly'),
            f'DEV-{YEAR}-0001')
        self.assertEqual(
            next_reference(Devis, 'DEV', self.company, period='none'),
            'DEV-0001')


class CoreCreateWithReferenceRetryTests(TestCase):
    """Deux sauvegardes concurrentes → numéros distincts (la perdante réessaie)."""

    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)

    def test_retries_when_a_concurrent_save_steals_the_number(self):
        from apps.ventes.models import Devis
        calls = {'n': 0}

        def save_fn(ref):
            calls['n'] += 1
            if calls['n'] == 1:
                # Simule la perte de course : une requête concurrente a committé
                # la même référence d'abord, notre insert heurte la contrainte
                # d'unicité. Le helper doit réessayer au lieu de planter.
                raise IntegrityError(
                    'duplicate key value violates unique constraint '
                    '"ventes_devis_company_id_reference_2a3bcb46_uniq"'
                )
            return make_devis(self.company, self.client_obj, ref)

        devis = create_with_reference(Devis, 'DEV', self.company, save_fn)
        self.assertEqual(calls['n'], 2)
        self.assertTrue(devis.reference.startswith(f'DEV-{MONTH}-'))

    def test_two_sequential_creates_get_distinct_numbers(self):
        from apps.ventes.models import Devis
        d1 = create_with_reference(
            Devis, 'DEV', self.company,
            lambda ref: make_devis(self.company, self.client_obj, ref))
        d2 = create_with_reference(
            Devis, 'DEV', self.company,
            lambda ref: make_devis(self.company, self.client_obj, ref))
        self.assertNotEqual(d1.reference, d2.reference)
        self.assertEqual(d1.reference, f'DEV-{MONTH}-0001')
        self.assertEqual(d2.reference, f'DEV-{MONTH}-0002')

    def test_non_reference_integrity_errors_are_not_swallowed(self):
        from apps.ventes.models import Devis

        def save_fn(ref):
            raise IntegrityError('null value in column "client_id"')

        with self.assertRaises(IntegrityError):
            create_with_reference(Devis, 'DEV', self.company, save_fn)


class VentesShimReExportsCoreTests(TestCase):
    """Le shim ventes ré-exporte les MÊMES objets que la fondation (bit-identique)."""

    def test_shim_reexports_are_the_same_objects(self):
        from apps.ventes.utils import references as shim
        import core.numbering as core_num
        self.assertIs(shim.next_reference, core_num.next_reference)
        self.assertIs(shim.create_with_reference, core_num.create_with_reference)
        self.assertIs(shim.MAX_ATTEMPTS, core_num.MAX_ATTEMPTS)
