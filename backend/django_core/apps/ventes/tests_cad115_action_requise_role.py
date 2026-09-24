"""CAD115 (SIG9) — « Action requise » (Ventes) s'ouvre au rôle qui relance, et
chaque ligne affiche la prochaine touche CRM déjà programmée.

Audit L3 cadence de suivi client, 21/09/2026 : le tableau Ventes (non ouvert
24 h / ouvert non signé 48 h / rouvert 3×) était réservé aux rôles
responsable/admin et proposait ses PROPRES brouillons WhatsApp, sans aucun
arbitrage avec la file calendaire du CRM (``crm.RelanceEtape``) — les deux
pouvaient réclamer le même devis le même jour avec deux messages différents.
L'arbitrage existant côté devis (``crm.selectors.devis_a_cadence_active``,
MRY7) supprime déjà le nudge vendeur QJ4 ; il manquait la RÉCIPROQUE côté
Ventes : savoir qu'une touche CRM est déjà programmée avant de relancer.

Ce fichier verrouille les deux corrections, et rien d'autre :
  * le rôle qui relance (``normal``) voit désormais le tableau — garde
    serveur alignée sur le nav (``IsAnyRole``, apps/ventes/views/devis.py) ;
  * chaque ligne publie ``prochaine_touche_crm``, lue via le selector CRM
    sanctionné ``apps.crm.selectors.prochaine_touche_par_lead`` (jamais un
    import de ``apps.crm.models`` côté ventes) — ``None`` sans lead, sans
    touche À FAIRE, ou pour un devis d'une autre société, jamais une valeur
    inventée.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client, Lead, RelanceEtape
from apps.ventes.models import Devis
from apps.ventes.selectors import devis_action_requise

User = get_user_model()
URL = '/api/django/ventes/devis/action-requise/'


class Cad115RoleApiTests(TestCase):
    """La garde serveur suit le nav : le rôle qui relance n'est plus 403."""

    def setUp(self):
        self.company = Company.objects.create(nom='CAD115 Role Co')
        self.normal = User.objects.create_user(
            username='cad115_normal', password='x',
            role_legacy='normal', company=self.company)
        self.api = APIClient()

    def test_role_normal_voit_desormais_le_tableau(self):
        """LE défaut de CAD115 (SIG9) : ce rôle tombait sur un 403."""
        self.api.force_authenticate(user=self.normal)
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('buckets', resp.data)
        self.assertIn('devis', resp.data)

    def test_anonyme_toujours_refuse(self):
        resp = APIClient().get(URL)
        self.assertIn(resp.status_code, (401, 403))


class Cad115ProchaineToucheTests(TestCase):
    """SIG9 — chaque ligne arbitre avec la file calendaire du CRM."""

    def setUp(self):
        self.company = Company.objects.create(nom='CAD115 Touche Co')
        self.autre = Company.objects.create(nom='CAD115 Autre Co')
        self.user = User.objects.create_user(
            username='cad115_resp', password='x',
            role_legacy='responsable', company=self.company)
        self.today = timezone.localdate()

    def _devis_envoye(self, ref, *, company=None, lead=None):
        company = company or self.company
        client = Client.objects.create(
            company=company, nom='Client', email=f'{ref}@ex.com')
        return Devis.objects.create(
            company=company, reference=ref, client=client, lead=lead,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'),
            date_envoi=timezone.now() - datetime.timedelta(days=9),
            created_by=self.user)

    def test_ligne_porte_la_prochaine_touche_crm_programmee(self):
        lead = Lead.objects.create(company=self.company, nom='Prospect')
        devis = self._devis_envoye('DEV-CAD115-0001', lead=lead)
        due_at = timezone.now() + datetime.timedelta(days=2)
        RelanceEtape.objects.create(
            company=self.company, lead=lead, ordre=1,
            due_date=due_at.date(), due_at=due_at, canal='whatsapp',
            cadence='apres_devis', devis=devis,
            statut=RelanceEtape.Statut.A_FAIRE)
        board = devis_action_requise(self.company, today=self.today)
        touche = board['devis'][devis.id]['prochaine_touche_crm']
        self.assertIsNotNone(touche)
        self.assertEqual(touche['due_at'], due_at.isoformat())
        self.assertEqual(touche['due_date'], due_at.date().isoformat())
        self.assertEqual(touche['cadence'], 'apres_devis')
        self.assertEqual(touche['canal'], 'whatsapp')
        self.assertEqual(
            sorted(touche), ['cadence', 'canal', 'due_at', 'due_date'])

    def test_touche_deja_faite_n_est_pas_la_prochaine(self):
        lead = Lead.objects.create(company=self.company, nom='Prospect2')
        devis = self._devis_envoye('DEV-CAD115-0002', lead=lead)
        RelanceEtape.objects.create(
            company=self.company, lead=lead, ordre=1,
            due_date=self.today, canal='appel', cadence='apres_devis',
            devis=devis, statut=RelanceEtape.Statut.FAIT)
        board = devis_action_requise(self.company, today=self.today)
        self.assertIsNone(board['devis'][devis.id]['prochaine_touche_crm'])

    def test_devis_sans_lead_touche_est_null(self):
        devis = self._devis_envoye('DEV-CAD115-0003')
        board = devis_action_requise(self.company, today=self.today)
        self.assertIsNone(board['devis'][devis.id]['prochaine_touche_crm'])

    def test_lead_sans_aucune_touche_est_null(self):
        lead = Lead.objects.create(company=self.company, nom='Prospect4')
        devis = self._devis_envoye('DEV-CAD115-0004', lead=lead)
        board = devis_action_requise(self.company, today=self.today)
        self.assertIsNone(board['devis'][devis.id]['prochaine_touche_crm'])

    def test_touche_d_une_autre_societe_ne_fuite_jamais(self):
        """Multi-tenant : la touche du lead d'une AUTRE société n'apparaît
        jamais sur la ligne de CETTE société, même quand les deux devis
        partagent le même jour d'envoi."""
        lead = Lead.objects.create(company=self.company, nom='Prospect5')
        devis = self._devis_envoye('DEV-CAD115-0005', lead=lead)

        autre_lead = Lead.objects.create(company=self.autre, nom='Fuite')
        self._devis_envoye(
            'DEV-CAD115-INTRUS', company=self.autre, lead=autre_lead)
        RelanceEtape.objects.create(
            company=self.autre, lead=autre_lead, ordre=1,
            due_date=self.today, canal='email', cadence='apres_devis',
            statut=RelanceEtape.Statut.A_FAIRE)

        board = devis_action_requise(self.company, today=self.today)
        self.assertIsNone(board['devis'][devis.id]['prochaine_touche_crm'])
