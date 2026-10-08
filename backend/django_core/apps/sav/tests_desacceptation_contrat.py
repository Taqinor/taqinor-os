"""Décision fondateur (08/10/2026) — le contrat de maintenance créé à
l'acceptation d'un devis (XCTR1, marqueur ``[devis:<id>]``) suit la
dés-acceptation : désactivé (jamais supprimé), réactivé à la ré-acceptation
(jamais doublé) ; un contrat déjà ENGAGÉ (facturation active) bloque.

Run :
    docker compose exec django_core python manage.py test \
        apps.sav.tests_desacceptation_contrat -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.sav.models import ContratMaintenance
from apps.ventes import services as ventes_services
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class TestContratDesacceptation(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-desaccept', defaults={'nom': 'SAV Désaccept'})
        self.user = User.objects.create_user(
            username='sav_desaccept', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Contrat',
            email='contrat@example.com', telephone='+212600000099')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-9301',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            date_envoi=timezone.now(), taux_tva=Decimal('20'))
        ventes_services.accept_devis(
            devis=self.devis, user=self.user, nom='M. Contrat',
            option=Devis.OptionAcceptee.SANS_BATTERIE)
        # Le contrat tel que XCTR1 le pose (le devis de test n'a pas de
        # ligne récurrente : on le crée avec le même marqueur).
        self.contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            date_debut=timezone.localdate(), actif=True,
            facturation_active=False,
            notes=f'Créé automatiquement depuis le devis [devis:{self.devis.pk}]')

    def test_desactive_puis_reactive_sans_doublon(self):
        ventes_services.annuler_acceptation(devis=self.devis, user=self.user)
        self.contrat.refresh_from_db()
        self.assertFalse(self.contrat.actif)
        self.assertIn(f'[devis-desaccepte:{self.devis.pk}]', self.contrat.notes)

        self.devis.refresh_from_db()
        ventes_services.accept_devis(
            devis=self.devis, user=self.user, nom='M. Contrat',
            option=Devis.OptionAcceptee.SANS_BATTERIE)
        self.contrat.refresh_from_db()
        self.assertTrue(self.contrat.actif)
        self.assertIn(f'[devis:{self.devis.pk}]', self.contrat.notes)
        self.assertEqual(ContratMaintenance.objects.filter(
            company=self.company,
            notes__contains=f'[devis:{self.devis.pk}]').count(), 1)

    def test_contrat_engage_bloque(self):
        ContratMaintenance.objects.filter(pk=self.contrat.pk).update(
            facturation_active=True)
        with self.assertRaises(
                ventes_services.AnnulationAcceptationBloquee) as ctx:
            ventes_services.annuler_acceptation(
                devis=self.devis, user=self.user)
        self.assertIn('contrat de maintenance', ctx.exception.message)
        self.devis.refresh_from_db()
        self.contrat.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ACCEPTE)
        self.assertTrue(self.contrat.actif)
