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

    def test_chantier_annule_desactive_et_reactive(self):
        """ACSV64 (C-ACSV-080) — annuler un chantier éteint ses contrats
        (marqueur ``[chantier-annule:<id>]``) : plus de visite préventive ;
        ``reactiver_contrats_chantier`` les rallume ; un contrat déjà inactif
        n'est jamais rallumé. ROUGE AVANT : actif, 2 tickets."""
        from rest_framework.test import APIClient
        from apps.installations.models import Installation
        from apps.sav.maintenance import generer_visites_dues
        from apps.sav.models import Ticket
        from apps.sav.services import reactiver_contrats_chantier
        ContratMaintenance.objects.filter(pk=self.contrat.pk).update(actif=False)
        a = Installation.objects.create(
            company=self.company, client=self.client_obj, reference='CH-ACSV64-A')
        b = Installation.objects.create(
            company=self.company, client=self.client_obj, reference='CH-ACSV64-B')

        def contrat(inst, actif=True):
            return ContratMaintenance.objects.create(
                company=self.company, client=self.client_obj, installation=inst,
                date_debut=timezone.localdate(), actif=actif)
        ca, cb, deja_inactif = contrat(a), contrat(b), contrat(a, actif=False)
        api = APIClient()
        api.force_authenticate(self.user)
        r = api.post(f'/api/django/installations/chantiers/{a.id}/annuler/',
                     {'motif': 'client parti'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        ca.refresh_from_db()
        self.assertFalse(ca.actif)
        self.assertIn(f'[chantier-annule:{a.id}]', ca.notes)
        self.assertEqual(generer_visites_dues(self.company, self.user, avance_jours=400), 1)
        self.assertEqual(set(Ticket.objects.filter(
            company=self.company, type=Ticket.Type.PREVENTIF).values_list(
                'installation_id', flat=True)), {b.id})
        self.assertEqual(reactiver_contrats_chantier(a, self.user), 1)
        ca.refresh_from_db()
        deja_inactif.refresh_from_db()
        cb.refresh_from_db()
        self.assertTrue(ca.actif)
        self.assertNotIn(f'[chantier-annule:{a.id}]', ca.notes)
        self.assertFalse(deja_inactif.actif)
        self.assertTrue(cb.actif)
