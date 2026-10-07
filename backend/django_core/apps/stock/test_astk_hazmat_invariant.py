"""ASTK200 (C-ASTK-048, volet WMS-12) — invariant hazmat au point d'écriture
du casier : un produit à classe de danger entrant dans un casier non déclaré
compatible est refusé (scanner, déplacement d'unité, retour client).

Sonde WMS-12 : entrée lithium dans un casier non déclaré → 201.

Source réelle : `casier_accepte_produit` (services_hazmat), vue
`scanner/mouvement/`, `deplacer_unite_logistique` — aucun mock.

Run :
    python manage.py test apps.stock.test_astk_hazmat_invariant -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import BinLocation
from apps.stock.models import (
    CompatibiliteHazmatCasier, EmplacementStock, MouvementStock, Produit,
)
from apps.stock.services import (
    ajouter_ligne_unite_logistique, creer_unite_logistique,
    deplacer_unite_logistique,
)
from authentication.models import Company

User = get_user_model()

URL = '/api/django/stock/scanner/mouvement/'
MSG = 'Casier non autorisé pour la classe de danger « Batterie lithium ».'


class HazmatTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='ASTK200', slug='astk200-co')
        self.user = User.objects.create_user(
            username='astk200-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        depot = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt ASTK200', is_principal=True)
        self.nu = BinLocation.objects.create(
            company=self.company, emplacement=depot, code='N-01-01',
            zone='N', allee='01', casier='01', ordre=10)
        self.compatible = BinLocation.objects.create(
            company=self.company, emplacement=depot, code='H-01-01',
            zone='H', allee='01', casier='01', ordre=20)
        CompatibiliteHazmatCasier.objects.create(
            company=self.company, bin=self.compatible,
            classe_danger=Produit.ClasseDanger.BATTERIE_LITHIUM)
        self.batterie = Produit.objects.create(
            company=self.company, nom='Batterie ASTK200', sku='BAT-ASTK200',
            prix_vente=Decimal('5000'), prix_achat=Decimal('3000'),
            quantite_stock=10,
            classe_danger=Produit.ClasseDanger.BATTERIE_LITHIUM)
        self.cable = Produit.objects.create(
            company=self.company, nom='Câble ASTK200', sku='CAB-ASTK200',
            prix_vente=Decimal('20'), prix_achat=Decimal('10'),
            quantite_stock=10)

    def _entree(self, produit, casier):
        return self.api.post(URL, {
            'produit': produit.id, 'type_mouvement': 'entree', 'quantite': 1,
            'bin_destination': casier.id}, format='json')

    def test_scanner_refuse_casier_incompatible(self):
        nb = MouvementStock.objects.count()
        rep = self._entree(self.batterie, self.nu)
        self.assertEqual(rep.status_code, 400, rep.data)
        # Corps DRF natif + enveloppe YAPIC3 additive sous « error ».
        self.assertEqual(rep.data['error']['code'], 'validation_error')
        self.assertEqual(
            {k: v for k, v in rep.data.items() if k != 'error'},
            {'bin_destination': [MSG]})
        # Persistance : aucun mouvement créé, stock inchangé.
        self.assertEqual(MouvementStock.objects.count(), nb)
        self.batterie.refresh_from_db()
        self.assertEqual(self.batterie.quantite_stock, 10)

    def test_casier_compatible_accepte(self):
        rep = self._entree(self.batterie, self.compatible)
        self.assertEqual(rep.status_code, 201, rep.data)
        # Un produit sans classe de danger passe partout (historique).
        rep = self._entree(self.cable, self.nu)
        self.assertEqual(rep.status_code, 201, rep.data)

    def test_deplacement_unite_refuse(self):
        unite = creer_unite_logistique(
            company=self.company, type_unite='colis')
        ajouter_ligne_unite_logistique(
            company=self.company, unite=unite, produit=self.batterie,
            quantite=1)
        unite.bin_actuel = self.compatible
        unite.save(update_fields=['bin_actuel'])
        nb = MouvementStock.objects.count()
        with self.assertRaises(ValidationError) as ctx:
            deplacer_unite_logistique(
                unite=unite, bin_destination=self.nu, user=self.user)
        self.assertEqual(ctx.exception.detail['bin_destination'][0], MSG)
        self.assertEqual(MouvementStock.objects.count(), nb)
        unite.refresh_from_db()
        self.assertEqual(unite.bin_actuel_id, self.compatible.id)
