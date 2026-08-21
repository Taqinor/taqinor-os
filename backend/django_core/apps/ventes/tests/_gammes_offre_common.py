"""Fixtures partagées de la suite `test_gammes_offre*`.

Extraites TELLES QUELLES de `test_gammes_offre.py` le 2026-08-21, quand ce
module (195,6 s mesurées en CI, à lui seul TOUT le contenu du shard le plus
lent — `backend-tests-shard (0)`, ~8,7 min bout-en-bout) a été scindé PAR
CLASSE : le planificateur `scripts/ci_shard.py` place des MODULES, donc six
classes enfermées dans un seul fichier ne pouvaient jamais partir sur des
lanes différentes, quel que soit le nombre de lanes.

Le préfixe `_` garde ce fichier HORS de la découverte Django (`test*.py`) :
il ne porte aucun test, seulement les fabriques et la classe de base
partagées par les six parties.

Aucun helper n'a changé d'un octet : mêmes objets, mêmes valeurs.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.services import creer_variante_gamme

User = get_user_model()


# ─── Helpers ───────────────────────────────────────────────────────────────

def make_company(slug='gamme-co'):
    from authentication.models import Company
    return Company.objects.get_or_create(
        slug=slug, defaults={'nom': 'Gamme Co'})[0]


def make_user(company, username=None):
    uname = username or f'u_{company.slug}'
    try:
        return User.objects.get(username=uname)
    except User.DoesNotExist:
        return User.objects.create_user(
            username=uname, password='x',
            role_legacy='responsable', company=company)


def make_client_obj(company):
    return Client.objects.create(
        company=company, nom='Alaoui', prenom='Salma',
        email='salma@gamme.ma', telephone='+212611000020')


def make_produit(company, nom, sku, prix_vente, prix_achat='1'):
    return Produit.objects.create(
        company=company, nom=nom, sku=sku,
        prix_vente=Decimal(str(prix_vente)),
        prix_achat=Decimal(str(prix_achat)),
        quantite_stock=50)


def make_devis(company, user, client_obj, ref, statut='brouillon'):
    return Devis.objects.create(
        company=company, reference=ref, client=client_obj,
        statut=statut, created_by=user)


def add_ligne(devis, produit, qty='6', pu='2000'):
    return LigneDevis.objects.create(
        devis=devis, produit=produit, designation=produit.nom,
        quantite=Decimal(str(qty)), prix_unitaire=Decimal(str(pu)),
        remise=Decimal('0'))


def url_gamme(devis_id):
    return f'/api/django/ventes/devis/{devis_id}/dupliquer-variante-gamme/'


def url_proposal(token):
    return f'/api/django/ventes/proposal/{token}/'


def url_accept(token):
    return f'/api/django/ventes/proposal/{token}/accept/'


class GammeBase(TestCase):
    def setUp(self):
        self.company = make_company('gamme-main')
        self.user = make_user(self.company)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)
        self.client_obj = make_client_obj(self.company)
        self.panneau = make_produit(
            self.company, 'Panneau 550W', 'P550-GAM', '2000', prix_achat='1200')
        self.onduleur = make_produit(
            self.company, 'Onduleur réseau 5kW', 'OND5-GAM', '9000',
            prix_achat='6000')

    def _paire(self, ref='DEV-GAM-001', nom='Premium', recommandee=False):
        source = make_devis(self.company, self.user, self.client_obj, ref)
        add_ligne(source, self.panneau, qty='10')
        add_ligne(source, self.onduleur, qty='1', pu='9000')
        soeur = creer_variante_gamme(
            source, nom, user=self.user, recommandee=recommandee)
        source.refresh_from_db()
        return source, soeur
