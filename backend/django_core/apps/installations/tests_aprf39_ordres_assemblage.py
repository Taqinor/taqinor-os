"""APRF39 (C-APRF-019) — la liste des ordres d'assemblage calcule coût et temps
sur des données PRÉCHARGÉES : 2 puis 8 ordres à 4 lignes coûtent le même
nombre de requêtes, avec des coûts et temps identiques.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_aprf39_ordres_assemblage"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import (
    EtapeAssemblage, EtapeOrdre, Kit, OrdreAssemblage, OrdreAssemblageLigne,
)
from apps.installations.services import totaux_temps_ordre
from apps.stock.models import Produit

User = get_user_model()
URL = '/api/django/installations/ordres-assemblage/'


class OrdresAssemblageListeTests(TestCase):
    def setUp(self):
        from authentication.models import Company
        self.company, _ = Company.objects.get_or_create(
            slug='co-aprf39', defaults={'nom': 'Co APRF39'})
        self.user = User.objects.create_user(
            username='resp-aprf39', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.compose = Produit.objects.create(
            company=self.company, nom='Compose', prix_vente=10,
            prix_achat=0, quantite_stock=0)
        self.pieces = [Produit.objects.create(
            company=self.company, nom=f'Piece {i}', prix_vente=10,
            prix_achat=Decimal('5.00') + i, quantite_stock=100)
            for i in range(4)]
        self.kit = Kit.objects.create(
            company=self.company, nom='Kit APRF39',
            produit_compose=self.compose)
        self.etapes = [EtapeAssemblage.objects.create(
            kit=self.kit, ordre=i, libelle=f'Etape {i}',
            duree_attendue_min=10 * (i + 1)) for i in range(2)]
        self.n = 0

    def _ordres(self, nb):
        for _ in range(nb):
            self.n += 1
            ordre = OrdreAssemblage.objects.create(
                company=self.company, reference=f'ASM-APRF39-{self.n}',
                kit=self.kit, quantite=2, responsable=self.user)
            for p in self.pieces:
                OrdreAssemblageLigne.objects.create(
                    ordre=ordre, produit=p, quantite=3)
            for e in self.etapes:
                EtapeOrdre.objects.create(
                    ordre=ordre, etape_modele=e, duree_reelle_min=7)

    def _liste(self):
        with CaptureQueriesContext(connection) as ctx:
            r = self.api.get(URL)
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        rows = r.data['results'] if isinstance(r.data, dict) else r.data
        return len(ctx.captured_queries), rows

    def test_requetes_identiques_a_deux_tailles(self):
        self._ordres(2)
        n2, rows2 = self._liste()
        self._ordres(6)
        n8, rows8 = self._liste()
        self.assertEqual(len(rows2), 2)
        self.assertEqual(len(rows8), 8)
        self.assertEqual(n2, n8, (n2, n8))

    def test_valeurs_inchangees(self):
        self._ordres(3)
        _, rows = self._liste()
        attendu_cout = sum(
            (Decimal(3) * p.prix_achat for p in self.pieces), Decimal('0'))
        for row in rows:
            self.assertEqual(Decimal(row['cout_prevu']), attendu_cout)
            self.assertEqual(row['temps_prevu_min'], 30)
            self.assertEqual(row['temps_reel_min'], 14)
            self.assertEqual(row['responsable'], self.user.id)
            self.assertEqual(row['responsable_nom'], self.user.username)
            self.assertEqual(len(row['lignes']), 4)

    def test_totaux_unitaire_inchange(self):
        self._ordres(1)
        ordre = OrdreAssemblage.objects.get(company=self.company)
        self.assertEqual(totaux_temps_ordre(ordre),
                         {'prevu': 30, 'reel': 14, 'complet': False})
