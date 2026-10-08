"""ASAV8 — retrait de pièce borné au chantier / client du ticket.

``retirer_piece`` ne trouve l'équipement que dans le périmètre du ticket
(chantier, ou client), exige le produit de l'équipement trouvé, et ne bascule
un équipement ``REMPLACE`` qu'une fois : un rejeu est refusé (409) sans
nouveau mouvement de stock, RMA ni signal.

Run :
    python manage.py test apps.sav.tests_asav8_retrait_borne -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Equipement, PieceRetiree, Ticket, WarrantyClaim
from apps.stock.models import Produit
from core.events import equipement_remplace

User = get_user_model()


class RetraitBorneTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav8-co', defaults={'nom': 'ASAV8 Co'})
        self.user = User.objects.create_user(
            username='asav8_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_a = Client.objects.create(
            company=self.company, nom='A', prenom='Client')
        self.client_b = Client.objects.create(
            company=self.company, nom='B', prenom='Client')
        self.inst_a = Installation.objects.create(
            company=self.company, reference='CHT-ASAV8-A', client=self.client_a)
        self.inst_b = Installation.objects.create(
            company=self.company, reference='CHT-ASAV8-B', client=self.client_b)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ASAV8', sku='OND-ASAV8',
            prix_achat=0, prix_vente=1000, quantite_stock=Decimal('10'))
        self.autre_produit = Produit.objects.create(
            company=self.company, nom='Panneau ASAV8', sku='PAN-ASAV8',
            prix_achat=0, prix_vente=200)
        self.eq_a = Equipement.objects.create(
            company=self.company, produit=self.produit,
            installation=self.inst_a, numero_serie='SN-A')
        self.eq_b = Equipement.objects.create(
            company=self.company, produit=self.produit,
            installation=self.inst_b, numero_serie='SN-B')
        self.eq_c = Equipement.objects.create(
            company=self.company, produit=self.produit,
            installation=self.inst_a, numero_serie='SN-C')
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-ASAV8-1',
            client=self.client_a, installation=self.inst_a,
            type=Ticket.Type.CORRECTIF, created_by=self.user)
        self.url = f'/api/django/sav/tickets/{self.ticket.pk}/pieces-retirees/'

    def _post(self, **corps):
        return self.api.post(self.url, corps, format='json')

    def test_serie_autre_client_400(self):
        r = self._post(produit=self.produit.pk, numero_serie='SN-B',
                       destination='retour_fournisseur')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('numero_serie', r.data)
        self.eq_b.refresh_from_db()
        self.assertEqual(self.eq_b.statut, Equipement.Statut.EN_SERVICE)
        self.assertIsNone(self.eq_b.remplace_par_ticket_id)
        self.assertFalse(WarrantyClaim.objects.filter(
            equipement=self.eq_b).exists())
        self.assertFalse(PieceRetiree.objects.filter(
            ticket=self.ticket).exists())

    def test_double_retrait_409_un_mouvement(self):
        r1 = self._post(produit=self.produit.pk, numero_serie='SN-A',
                        destination='stock_occasion', quantite='1')
        self.assertEqual(r1.status_code, 201, r1.content)
        r2 = self._post(produit=self.produit.pk, numero_serie='SN-A',
                        destination='stock_occasion', quantite='1')
        self.assertEqual(r2.status_code, 409, r2.content)
        self.assertIn('SAV-ASAV8-1', str(r2.data))
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, Decimal('11'))
        self.assertEqual(
            PieceRetiree.objects.filter(ticket=self.ticket).count(), 1)
        self.eq_a.refresh_from_db()
        self.assertEqual(self.eq_a.statut, Equipement.Statut.REMPLACE)
        self.assertEqual(self.eq_a.remplace_par_ticket_id, self.ticket.pk)

    def test_un_seul_signal(self):
        recus = []

        def _recepteur(sender, equipement=None, **kw):
            recus.append(equipement.numero_serie)
        equipement_remplace.connect(_recepteur, weak=False)
        try:
            for _ in range(2):
                self._post(produit=self.produit.pk, numero_serie='SN-A',
                           destination='rebut')
        finally:
            equipement_remplace.disconnect(_recepteur)
        self.assertEqual(recus, ['SN-A'])

    def test_produit_different_400(self):
        r = self._post(produit=self.autre_produit.pk, numero_serie='SN-C',
                       destination='rebut')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('produit', r.data)
        self.eq_c.refresh_from_db()
        self.assertEqual(self.eq_c.statut, Equipement.Statut.EN_SERVICE)
