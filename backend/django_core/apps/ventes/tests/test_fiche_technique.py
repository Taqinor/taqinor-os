"""FG254 / DC35 + WIR104 — fiche technique : UNE SEULE surface exposée.

WIR104 a tranché le doublon : ``/ventes/fiches-techniques/`` (jamais appelé —
le frontend n'utilise que ``stockApi``) doublait ``/stock/fiches-techniques/``.
La route, le ViewSet et le serializer de ventes ont été RETIRÉS ; le modèle
``ventes.FicheTechnique`` reste en base (aucune migration destructive) mais
n'a plus d'API.

Ce module verrouille donc désormais :
  - l'invariant modèle (une seule fiche par société+produit), toujours vrai ;
  - la surface ventes RÉELLEMENT retirée (la route ne résout plus) ;
  - la surface stock, elle, toujours exposée et fonctionnelle.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_fiche_technique -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
from rest_framework.test import APIClient

from apps.ventes.models import FicheTechnique
from apps.stock.models import Produit
from authentication.models import Company

User = get_user_model()


def make_company(slug):
    return Company.objects.create(nom=f'Co {slug}', slug=slug)


def make_user(company, name):
    return User.objects.create_user(
        username=name, password='x',
        role_legacy='responsable', company=company)


def make_produit(company, nom='Panneau 550W'):
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=Decimal('1000'))


class FicheTechniqueModelTest(TestCase):
    def test_unique_per_company_produit(self):
        co = make_company('ft-uniq')
        prod = make_produit(co)
        FicheTechnique.objects.create(
            company=co, produit=prod, type_fiche='panneau', pmax_w=550)
        with self.assertRaises(IntegrityError):
            FicheTechnique.objects.create(
                company=co, produit=prod, type_fiche='panneau', pmax_w=560)


class WIR104SurfaceUniqueTest(TestCase):
    """Le doublon est retiré : une seule surface « fiche technique »."""

    def setUp(self):
        self.company = make_company('ft-wir104')
        self.user = make_user(self.company, 'ft_wir104_user')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.prod = make_produit(self.company)

    def test_route_ventes_retiree(self):
        # Plus aucun nom de route côté ventes…
        with self.assertRaises(NoReverseMatch):
            reverse('fiche-technique-list')
        # …et le chemin historique ne résout plus.
        resp = self.api.get('/api/django/ventes/fiches-techniques/')
        self.assertEqual(resp.status_code, 404)

    def test_surface_stock_reste_la_seule_exposee(self):
        resp = self.api.get('/api/django/stock/fiches-techniques/')
        self.assertEqual(resp.status_code, 200)

    def test_viewset_ventes_nest_plus_exporte(self):
        from apps.ventes import views as ventes_views
        self.assertFalse(hasattr(ventes_views, 'FicheTechniqueViewSet'))
