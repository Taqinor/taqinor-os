"""ACRM37 (C-ACRM-032) — UN recalage de ``Lead.relance_date``
(``services._recaler_file``) pour tous les gestes de cadence.

Sonde V_VB LSVC1-4 : un vieux lead à ``relance_date`` 2020-01-01 démarrait sa
cadence aujourd'hui ; ``initialiser_plan_relance`` gardait la date passée
(« si elle est plus tôt, on la garde ») et le lead restait « en retard »
dans la file alors que sa première touche était à venir. Désormais chaque
geste (initialisation, fait, report, arrêt…) recale par ``_recaler_file``.

Aucun mock : services réels.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from core.dates import aujourd_hui_local

from apps.crm import selectors, services, stages
from apps.crm import cadence_plan
from apps.crm.models import Lead, RelanceEtape

User = get_user_model()


class RecalageUniqueTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM37 Solaire', slug='acrm37-recalage')
        self.user = User.objects.create_user(
            username='acrm37-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.lead = Lead.objects.create(
            company=self.company, nom='Recalage', owner=self.user,
            stage=stages.CONTACTED, telephone='+212661373737')
        RelanceEtape.objects.filter(lead=self.lead).delete()
        Lead.objects.filter(pk=self.lead.pk).update(
            relance_date=datetime.date(2020, 1, 1))
        self.lead.refresh_from_db()

    def _ouverte(self):
        return (RelanceEtape.objects
                .filter(lead=self.lead, statut=RelanceEtape.Statut.A_FAIRE)
                .order_by('due_at', 'pk').first())

    def _en_retard(self):
        return self.lead.pk in {le.pk for le in selectors.relances_du_jour(
            self.company, self.user, scope='overdue',
            today=aujourd_hui_local())}

    def test_date_passee_recalee_a_l_initialisation(self):
        cadence_plan.initialiser_plan_relance(
            self.lead, self.user, cadence='contact')
        self.lead.refresh_from_db()
        premiere = self._ouverte()
        self.assertEqual(self.lead.relance_date, premiere.due_date)
        self.assertFalse(self._en_retard())

    def test_chaque_geste_recale(self):
        cadence_plan.initialiser_plan_relance(
            self.lead, self.user, cadence='contact')
        touche = self._ouverte()
        issue = ('pas_de_reponse'
                 if touche.canal == RelanceEtape.Canal.APPEL else '')
        services.marquer_etape_relance(
            touche, self.user, RelanceEtape.Statut.FAIT, outcome=issue)
        self.lead.refresh_from_db()
        suivante = self._ouverte()
        self.assertIsNotNone(suivante)
        self.assertEqual(self.lead.relance_date, suivante.due_date)
        # Arrêt de la cadence : plus rien d'ouvert → la file se vide.
        cadence_plan.arreter_cadence(self.lead, user=self.user, motif='test')
        self.lead.refresh_from_db()
        prochaine = self._ouverte()
        self.assertEqual(self.lead.relance_date,
                         prochaine.due_date if prochaine else None)
