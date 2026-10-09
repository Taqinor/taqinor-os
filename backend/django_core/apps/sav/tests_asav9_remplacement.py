"""ASAV9 — remplacer un équipement en UN geste serveur : le neuf entre au parc
(même chantier / client), le registre des contrats est substitué, la garantie
repart à la date du remplacement (au moins la fin restante de l'ancien).

Run :
    python manage.py test apps.sav.tests_asav9_remplacement -v2
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.dateutils import add_months
from apps.sav.models import ContratMaintenance, Equipement, Ticket
from apps.stock.models import Produit

User = get_user_model()


class RemplacementTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav9-co', defaults={'nom': 'ASAV9 Co'})
        self.user = User.objects.create_user(
            username='asav9_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV9')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ASAV9',
            client=self.client_obj)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-ASAV9',
            prix_achat=0, prix_vente=5000, garantie_mois=60)
        self.today = timezone.localdate()
        self.ancien = Equipement.objects.create(
            company=self.company, produit=self.produit,
            installation=self.inst, numero_serie='SN-A',
            date_pose=add_months(self.today, -6))
        self.ancien.recompute_garanties()
        self.ancien.save(update_fields=[
            'date_fin_garantie', 'date_fin_garantie_production'])
        self.contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            installation=self.inst, actif=True,
            date_debut=self.today - timedelta(days=30))
        self.contrat.equipements.add(self.ancien)
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-A9-1',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, created_by=self.user,
            date_ouverture=self.today)

    def _post(self, **extra):
        corps = {'produit': self.produit.id, 'numero_serie': 'SN-A',
                 'destination': 'rebut', 'serie_neuve': 'SN-A2', **extra}
        return self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/pieces-retirees/',
            corps, format='json')

    def test_neuf_entre_au_parc(self):
        r = self._post()
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['equipement_neuf']['numero_serie'], 'SN-A2')
        neuf = Equipement.objects.get(company=self.company,
                                      numero_serie='SN-A2')
        self.assertEqual(neuf.statut, Equipement.Statut.EN_SERVICE)
        self.assertEqual(neuf.installation_id, self.inst.id)
        self.ancien.refresh_from_db()
        self.assertEqual(self.ancien.statut, Equipement.Statut.REMPLACE)

    def test_registre_contrat_substitue(self):
        self._post()
        neuf = Equipement.objects.get(numero_serie='SN-A2')
        self.assertTrue(self.contrat.couvre_equipement(neuf))
        self.assertFalse(
            self.contrat.equipements.filter(pk=self.ancien.pk).exists())

    def test_horloges_selon_decision(self):
        self._post()
        neuf = Equipement.objects.get(numero_serie='SN-A2')
        self.assertEqual(neuf.date_pose, self.today)
        # Durée du neuf (60 mois) depuis le remplacement, au moins la fin
        # restante de l'ancien.
        self.assertGreaterEqual(neuf.date_fin_garantie,
                                self.ancien.date_fin_garantie_effective)
        self.assertEqual(neuf.date_fin_garantie,
                         add_months(self.today, 60))

    def test_serie_neuve_doublon_400(self):
        r = self._post(serie_neuve='SN-A')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('serie_neuve', r.data)
        self.ancien.refresh_from_db()
        self.assertEqual(self.ancien.statut, Equipement.Statut.EN_SERVICE)

    def test_sans_serie_neuve_comportement_asav8(self):
        r = self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/pieces-retirees/',
            {'produit': self.produit.id, 'numero_serie': 'SN-A',
             'destination': 'rebut'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIsNone(r.data['equipement_neuf'])
        self.assertEqual(Equipement.objects.filter(
            company=self.company).count(), 1)
