"""AUD520 — le QR public d'un équipement vendu au comptoir ne renvoie plus 404.

Constat d'audit (le ROUGE figé ici) : ``equipement_public_signaler`` résolvait
le client UNIQUEMENT via ``installation.client``. Un équipement vendu au
comptoir (XPOS9 : ``installation`` vide, ``client_vente`` renseigné — le lien
client documenté sur le modèle) tombait donc sur le garde-fou 404 « Équipement
introuvable » à chaque scan, alors que les actions ``etiquettes``/
``partage_qr`` génèrent bien son étiquette QR publique.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_aud520 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Equipement, Ticket
from apps.stock.models import Produit

User = get_user_model()


class AUD520QrPublicVenteComptoirTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-aud520', defaults={'nom': 'Sav Co AUD520'})
        self.admin = User.objects.create_user(
            username='aud520_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='AUD520',
            email='aud520-client@example.invalid')
        self.produit = Produit.objects.create(
            company=self.company, nom='Pompe comptoir', sku='POMPE-AUD520',
            prix_achat=300, prix_vente=600)
        self.public = APIClient()

    def test_equipement_vendu_au_comptoir_cree_bien_un_ticket(self):
        """installation=None + client_vente rempli : avant AUD520, 404."""
        equip = Equipement.objects.create(
            company=self.company, produit=self.produit, installation=None,
            client_vente=self.client_obj, created_by=self.admin)
        token = equip.ensure_public_token()
        resp = self.public.post(
            f'/api/django/public/sav/equipement/{token}/signaler/',
            {'description': 'La pompe ne démarre plus.'})
        self.assertEqual(resp.status_code, 201, resp.content)
        ticket = Ticket.objects.get(reference=resp.data['reference'])
        self.assertEqual(ticket.client_id, self.client_obj.id)
        self.assertEqual(ticket.equipement_id, equip.id)
        self.assertIsNone(ticket.installation_id)
        self.assertEqual(ticket.company_id, self.company.id)

    def test_equipement_sans_chantier_ni_client_vente_reste_404(self):
        """Le filet de sécurité reste : personne à qui rattacher le ticket."""
        equip = Equipement.objects.create(
            company=self.company, produit=self.produit, installation=None,
            client_vente=None, created_by=self.admin)
        token = equip.ensure_public_token()
        resp = self.public.post(
            f'/api/django/public/sav/equipement/{token}/signaler/',
            {'description': 'Panne'})
        self.assertEqual(resp.status_code, 404, resp.content)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_equipement_avec_chantier_inchange(self):
        """Non-régression XSAV19 : le chemin chantier garde sa priorité."""
        inst = Installation.objects.create(
            company=self.company, reference='CHT-AUD520',
            client=self.client_obj)
        autre_client = Client.objects.create(
            company=self.company, nom='Autre', prenom='AUD520',
            email='aud520-autre@example.invalid')
        equip = Equipement.objects.create(
            company=self.company, produit=self.produit, installation=inst,
            client_vente=autre_client, created_by=self.admin)
        token = equip.ensure_public_token()
        resp = self.public.post(
            f'/api/django/public/sav/equipement/{token}/signaler/',
            {'description': 'Panne'})
        self.assertEqual(resp.status_code, 201, resp.content)
        ticket = Ticket.objects.get(reference=resp.data['reference'])
        self.assertEqual(ticket.client_id, self.client_obj.id)
        self.assertEqual(ticket.installation_id, inst.id)
