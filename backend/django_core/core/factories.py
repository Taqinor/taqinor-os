"""WOW14 — fabriques de test canoniques (sans dépendance : PAS de factory_boy).

Point d'entrée UNIQUE pour créer les objets de test communs (société, user,
client, produit, devis). Deux buts :

  * **Unicité garantie** — chaque champ unique (slug, username, sku, référence,
    email, téléphone) dérive d'un compteur ``itertools.count()`` partagé, donc
    aucune collision sous ``--keepdb`` ni ``--parallel`` (78 références en dur
    existaient dans la suite ; ``BUDGET-0000`` a collisionné en vraie CI).
  * **Une seule source à corriger** — quand un modèle gagne un champ requis, on
    édite UNE fonction ici au lieu des ~135 helpers ``create_company`` recopiés.

Règles d'écriture des tests : voir ``docs/TESTING.md``.
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

_seq = itertools.count(1)

User = get_user_model()


def _n():
    """Prochain entier unique du process de test (monotone)."""
    return next(_seq)


def make_company(nom=None, slug=None):
    """Société de test avec slug unique."""
    from authentication.models import Company
    i = _n()
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fac-co-{i}',
        defaults={'nom': nom or f'Factory Co {i}'})
    return company


def make_user(company, username=None, role='admin', role_legacy=None):
    """Utilisateur de test rattaché à ``company``.

    ``role_legacy`` (défaut = ``role``) est le champ historique lu par la
    plupart des permissions ; passer ``role_legacy=`` explicitement au besoin.
    """
    i = _n()
    return User.objects.create_user(
        username=username or f'fac-user-{i}', password='x',
        company=company, role_legacy=role_legacy or role)


def make_client(company, nom=None, email=None, prenom='Test'):
    """Client CRM de test (email/téléphone uniques)."""
    from apps.crm.models import Client
    i = _n()
    return Client.objects.create(
        company=company, nom=nom or f'Client{i}', prenom=prenom,
        email=email or f'fac-client-{i}@example.invalid',
        telephone=f'+2126{i:08d}')


def make_produit(company, nom=None, sku=None, prix_vente='100',
                 prix_achat='1', quantite_stock=100):
    """Produit de stock de test (sku unique)."""
    from apps.stock.models import Produit
    i = _n()
    return Produit.objects.create(
        company=company, nom=nom or f'Produit{i}', sku=sku or f'FAC-SKU-{i}',
        prix_vente=Decimal(str(prix_vente)), prix_achat=Decimal(str(prix_achat)),
        quantite_stock=quantite_stock)


def make_devis(company, client, created_by, reference=None, taux_tva='20'):
    """Devis de test (référence unique par société)."""
    from apps.ventes.models import Devis
    i = _n()
    month = timezone.now().strftime('%Y%m')
    return Devis.objects.create(
        company=company, reference=reference or f'FAC-{month}-{i:05d}',
        client=client, created_by=created_by, taux_tva=Decimal(str(taux_tva)))
