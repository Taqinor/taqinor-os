"""factory_boy factories for TAQINOR OS tests (YTEST1).

Replaces the copy-pasted ``make_company``/``make_user``/... helpers that were
hand-rolled with ``objects.create`` in ~400 test files. Every factory attaches
a ``company`` by default (multi-tenant is the rule, not the exception — see
CLAUDE.md) and only sets fields that are actually required to save; tests
override whatever field they're exercising.

Usage
-----
``build()`` constructs an in-memory instance with NO database hit — use it
for pure logic / serializer validation where persistence isn't the point.
``create()`` persists (and persists related objects via ``SubFactory``) — use
it whenever the test needs real querysets/joins/DB constraints.

    from testkit.factories import DevisFactory, another_tenant

    devis = DevisFactory()                      # single-tenant happy path
    other_company, other_user = another_tenant() # isolation tests

Dev-only dependency (``factory_boy`` — requirements-dev.txt), never imported
by production code.
"""
from decimal import Decimal

import factory
from factory.django import DjangoModelFactory

from authentication.models import Company, CustomUser


class CompanyFactory(DjangoModelFactory):
    class Meta:
        model = Company
        django_get_or_create = ('slug',)

    nom = factory.Sequence(lambda n: f'Société Test {n}')
    slug = factory.Sequence(lambda n: f'societe-test-{n}')
    actif = True


class UserFactory(DjangoModelFactory):
    class Meta:
        model = CustomUser
        django_get_or_create = ('username',)

    username = factory.Sequence(lambda n: f'testuser{n}')
    email = factory.LazyAttribute(lambda o: f'{o.username}@example.com')
    company = factory.SubFactory(CompanyFactory)
    role_legacy = CustomUser.ROLE_NORMAL
    is_active = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Route through ``create_user`` so the password is hashed properly,
        matching how real accounts are provisioned."""
        password = kwargs.pop('password', 'x')
        manager = cls._get_manager(model_class)
        return manager.create_user(*args, password=password, **kwargs)


class ClientFactory(DjangoModelFactory):
    class Meta:
        model = 'crm.Client'

    company = factory.SubFactory(CompanyFactory)
    nom = factory.Sequence(lambda n: f'Client{n}')
    prenom = 'Test'
    email = factory.LazyAttribute(
        lambda o: f'{o.nom.lower()}@example.com')
    telephone = '+212600000000'


class ProduitFactory(DjangoModelFactory):
    class Meta:
        model = 'stock.Produit'

    company = factory.SubFactory(CompanyFactory)
    nom = factory.Sequence(lambda n: f'Produit Test {n}')
    prix_achat = Decimal('0')
    prix_vente = Decimal('100.00')
    quantite_stock = 0
    seuil_alerte = 0


class DevisFactory(DjangoModelFactory):
    class Meta:
        model = 'ventes.Devis'

    company = factory.SubFactory(CompanyFactory)
    reference = factory.Sequence(lambda n: f'DEV-TEST-{n:04d}')
    # SelfAttribute keeps the client in the SAME company as the devis by
    # default (multi-tenant graphs must be internally consistent) — pass an
    # explicit ``client=...`` from another company to build isolation tests.
    client = factory.SubFactory(ClientFactory, company=factory.SelfAttribute('..company'))
    statut = 'brouillon'
    taux_tva = Decimal('20.00')


class LigneDevisFactory(DjangoModelFactory):
    class Meta:
        model = 'ventes.LigneDevis'

    devis = factory.SubFactory(DevisFactory)
    produit = factory.SubFactory(ProduitFactory, company=factory.SelfAttribute('..devis.company'))
    designation = factory.LazyAttribute(lambda o: o.produit.nom)
    quantite = Decimal('1')
    prix_unitaire = Decimal('100.00')
    remise = Decimal('0')


def another_tenant():
    """Build a second, independent (company, user) pair for isolation tests
    — e.g. asserting a viewset 404s/hides an object that belongs to a
    different company than the requesting user's."""
    company = CompanyFactory()
    user = UserFactory(company=company)
    return company, user
