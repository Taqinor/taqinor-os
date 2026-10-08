"""ASTK213 — action `taches-reappro-interne/<id>/executer/` : pose le
TRANSFERT casier source → casier cible par le chemin du poste scanner et
ferme la tâche, une seule fois.

Rouge avant : aucune action `executer` (404), statut éditable par PATCH.

Source réelle : TacheReapproInterneViewSet, services_reappro_casier,
enregistrer_mouvement_scanne → record_stock_movement → BinAffectation
(ASTK195) — aucun mock.

Run :
    python manage.py test apps.stock.test_astk_tache_reappro -v 2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import BinAffectation, BinLocation
from apps.stock.models import (
    EmplacementStock, MouvementStock, Produit, TacheReapproInterne,
)
from authentication.models import Company

User = get_user_model()

URL = '/api/django/stock/taches-reappro-interne/'
CONTRAT = (Path(__file__).resolve().parent / 'contract_samples'
           / 'wms_casiers.json')


class ExecuterTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='ASTK213', slug='astk213-co')
        user = User.objects.create_user(
            username='astk213-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        depot = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt ASTK213', is_principal=True)
        self.source = BinLocation.objects.create(
            company=self.company, emplacement=depot, code='S-01-01',
            zone='S', allee='01', casier='01', ordre=120)
        self.cible = BinLocation.objects.create(
            company=self.company, emplacement=depot, code='P-01-01',
            zone='P', allee='01', casier='01', ordre=100)
        self.produit = Produit.objects.create(
            company=self.company, nom='Connecteur ASTK213', sku='MC4-ASTK213',
            prix_vente=Decimal('18'), prix_achat=Decimal('10'),
            quantite_stock=50)
        BinAffectation.objects.create(
            company=self.company, bin=self.source, produit=self.produit,
            quantite=10)
        self.tache = TacheReapproInterne.objects.create(
            company=self.company, produit=self.produit, bin_cible=self.cible,
            bin_source=self.source, quantite=5)

    def _executer(self):
        return self.api.post(f'{URL}{self.tache.pk}/executer/', {},
                             format='json')

    def _qte(self, casier):
        aff = BinAffectation.objects.filter(
            bin=casier, produit=self.produit).first()
        return aff.quantite if aff else 0

    def test_executer_transfere_et_ferme(self):
        rep = self._executer()
        self.assertEqual(rep.status_code, 200, rep.data)
        self.assertEqual(rep.data['statut'], 'faite')
        self.assertEqual(rep.data['quantite'], 5)
        mouvement = MouvementStock.objects.get(pk=rep.data['mouvement_id'])
        self.assertEqual(mouvement.type_mouvement,
                         MouvementStock.TypeMouvement.TRANSFERT)
        self.assertEqual((mouvement.bin_source_id,
                          mouvement.bin_destination_id),
                         (self.source.id, self.cible.id))
        # Persistance : tâche et casiers relus.
        self.tache.refresh_from_db()
        self.assertEqual(self.tache.statut, TacheReapproInterne.Statut.FAITE)
        self.assertEqual((self._qte(self.source), self._qte(self.cible)),
                         (5, 5))

    def test_double_execution_409(self):
        self.assertEqual(self._executer().status_code, 200)
        nb = MouvementStock.objects.count()
        rep = self._executer()
        self.assertEqual(rep.status_code, 409, rep.data)
        self.assertEqual(rep.data, {'detail': 'Tâche déjà exécutée.'})
        self.assertEqual(MouvementStock.objects.count(), nb)

    def test_statut_non_editable(self):
        rep = self.api.patch(f'{URL}{self.tache.pk}/', {'statut': 'faite'},
                             format='json')
        self.assertIn(rep.status_code, (200, 400), rep.data)
        self.tache.refresh_from_db()
        self.assertEqual(self.tache.statut,
                         TacheReapproInterne.Statut.A_FAIRE)
        self.assertFalse(MouvementStock.objects.exists())

    def test_executer_conforme_contrat(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        exemple = contrat['routes']['taches_reappro_interne_executer'][
            'exemple']
        rep = self._executer()
        self.assertEqual(rep.status_code, 200, rep.data)
        self.assertEqual(sorted(rep.data), sorted(exemple))
        self.assertEqual(rep.data['statut'], exemple['statut'])
