"""ASAV4 (D-ASAV-6) — la couverture d'un ticket (garantie ET contrat) se juge
à la date d'OUVERTURE du ticket, jamais au jour de la lecture/facturation.

Run :
    python manage.py test apps.sav.tests_asav4_couverture_date_ouverture -v2
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.dateutils import add_months
from apps.sav.models import ContratMaintenance, Equipement, Ticket
from apps.stock.models import Produit

User = get_user_model()


class CouvertureDateOuvertureTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav4-co', defaults={'nom': 'ASAV4 Co'})
        self.user = User.objects.create_user(
            username='asav4_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV4')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ASAV4',
            client=self.client_obj)
        self.today = timezone.localdate()

    def _equipement(self, mois_pose):
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-ASAV4',
            prix_achat=0, prix_vente=5000)
        eq = Equipement.objects.create(
            company=self.company, produit=produit, installation=self.inst,
            numero_serie='ASAV4-SN',
            date_pose=add_months(self.today, -mois_pose))
        eq.recompute_garanties()
        eq.save(update_fields=['date_fin_garantie',
                               'date_fin_garantie_production'])
        return eq

    def _ticket(self, ref, *, jours, equipement=None):
        return Ticket.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            installation=self.inst, equipement=equipement,
            type=Ticket.Type.CORRECTIF, created_by=self.user,
            date_ouverture=self.today - timedelta(days=jours))

    def test_garantie_jugee_a_l_ouverture(self):
        # Légale (12 mois) échue depuis ~2 mois ; ticket ouvert il y a 4 mois.
        eq = self._equipement(mois_pose=14)
        ticket = self._ticket('SAV-A4-1', jours=120, equipement=eq)
        self.assertEqual(ticket.sous_garantie_calcule,
                         Ticket.SousGarantie.OUI)
        self.assertEqual(ticket.couverture_calculee(),
                         Ticket.Couverture.GARANTIE)

    def test_contrat_juge_a_l_ouverture(self):
        ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            installation=self.inst, actif=True,
            date_debut=self.today - timedelta(days=14 * 30), duree_mois=12)
        ticket = self._ticket('SAV-A4-2', jours=90)
        self.assertEqual(ticket.couverture_calculee(),
                         Ticket.Couverture.CONTRAT)

    def test_ouvert_apres_echeance_facturable(self):
        eq = self._equipement(mois_pose=14)
        ticket = self._ticket('SAV-A4-3', jours=5, equipement=eq)
        self.assertEqual(ticket.sous_garantie_calcule,
                         Ticket.SousGarantie.NON)
        self.assertEqual(ticket.couverture_calculee(),
                         Ticket.Couverture.FACTURABLE)
