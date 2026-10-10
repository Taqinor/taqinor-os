"""Bus d'événements métier (M6) — `core.events.devis_accepted` câblé au
récepteur CRM (`apps.crm.receivers`) qui avance l'étape du lead.

Couvre un trou réel : `test_acceptation.py` vérifie les métadonnées/chatter/
chantier de l'acceptation d'un devis, mais JAMAIS l'avancée d'étape du lead qui
en découle. On teste ici, à la fois :
  • le câblage de bout en bout (POST accepter/ → signal → récepteur → SIGNED) ;
  • le récepteur en isolation (émission directe du signal), ce qui garantit que
    l'abonnement (CrmConfig.ready) est bien en place ;
  • les garde-fous de `avancer_stage_pour_devis` : ne recule jamais, ignore les
    leads perdus.

Les clés d'étape ('QUOTE_SENT', 'SIGNED'…) suivent la convention des tests
existants (cf. test_acceptation.py) ; la source canonique reste STAGES.py.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead, LeadActivity
from apps.ventes.models import Devis
from core.events import devis_accepted
import datetime
import itertools
from core.events import devis_sent
from testkit.time import frozen
from apps.crm import horaires, stages
from apps.crm.models import RelanceEtape
from apps.crm.receivers_cadence import LIBELLE_FAIRE_SIGNER_AVENANT
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape
from apps.ventes.domain.revision import reviser_devis

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestDevisAcceptedAdvancesLeadStage(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='evt-co', defaults={'nom': 'Evt Co'})
        self.user = User.objects.create_user(
            username='evt_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = _auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Evt',
            email='evt@example.com', telephone='+212600000009')

    def _devis(self, lead, num, statut=Devis.Statut.ENVOYE):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{num:04d}',
            client=self.client_obj, lead=lead, statut=statut,
            taux_tva=Decimal('20'))

    def test_accepting_devis_advances_lead_to_signed(self):
        """Bout en bout : POST accepter/ émet le signal → l'étape passe à SIGNED
        et une entrée d'historique automatique est consignée sur le lead."""
        lead = Lead.objects.create(
            company=self.company, nom='Lead Evt', stage='QUOTE_SENT')
        devis = self._devis(lead, num=1)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'Client', 'date': '2026-06-10'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'SIGNED')
        auto = (LeadActivity.objects
                .filter(lead=lead, field='stage').order_by('-id').first())
        self.assertIsNotNone(auto)
        self.assertIn('auto', auto.body)

    def test_signal_directly_triggers_crm_receiver(self):
        """Récepteur en isolation : émettre `devis_accepted` suffit à avancer
        l'étape — preuve que l'abonnement (ready()) est câblé."""
        lead = Lead.objects.create(
            company=self.company, nom='Lead Sig', stage='NEW')
        devis = self._devis(lead, num=2, statut=Devis.Statut.ACCEPTE)
        devis_accepted.send(
            sender=None, devis=devis, user=self.user, ancien_statut='envoye')
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'SIGNED')

    def test_never_recedes_an_already_signed_lead(self):
        lead = Lead.objects.create(
            company=self.company, nom='Lead Signed', stage='SIGNED')
        devis = self._devis(lead, num=3, statut=Devis.Statut.ACCEPTE)
        devis_accepted.send(
            sender=None, devis=devis, user=self.user, ancien_statut='envoye')
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'SIGNED')

    def test_ignores_lost_lead(self):
        """D-ADEV-5 = (a) (fondateur, 08/10/2026 ; ADEV63) : un lead PERDU dont
        le client signe le devis est relevé de Perdu puis passe en Signé (le
        nom du test est conservé pour l'historique ; la règle a changé)."""
        lead = Lead.objects.create(
            company=self.company, nom='Lead Perdu', stage='QUOTE_SENT',
            perdu=True)
        devis = self._devis(lead, num=4, statut=Devis.Statut.ACCEPTE)
        devis_accepted.send(
            sender=None, devis=devis, user=self.user, ancien_statut='envoye')
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'SIGNED')
        self.assertFalse(lead.perdu)


# ADEV57 (déplacé depuis tests_adev57_cadence_avenant.py — AMET84 : un test par module)
User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
A_FAIRE = RelanceEtape.Statut.A_FAIRE

_seq = itertools.count(1)


class CadenceAvenant(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'ADEV57 {n}', slug=f'adev57-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'adev57-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Prospect ADEV57 {n}',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone=f'+21266570{n:04d}')
        self.client_obj = Client.objects.create(
            company=self.company, nom=f'Client ADEV57 {n}',
            email=f'adev57-{n}@example.com')
        self.v1 = Devis.objects.create(
            company=self.company, reference=f'DEV-ADEV57-{n:05d}',
            client=self.client_obj, lead=self.lead,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20.00'),
            date_envoi=GEL)

    def _envoyer(self, devis):
        devis_sent.send(sender='test', devis=devis, user=self.acteur,
                        ancien_statut='brouillon')

    def _cadence(self):
        return self.lead.relance_etapes.filter(cadence='apres_devis')

    def _taches_avenant(self):
        return self.lead.relance_etapes.filter(
            libelle=LIBELLE_FAIRE_SIGNER_AVENANT, statut=A_FAIRE)

    def _v2_envoyee(self):
        v2 = reviser_devis(self.v1, user=self.acteur)
        Devis.objects.filter(pk=v2.pk).update(
            statut=Devis.Statut.ENVOYE, date_envoi=GEL)
        v2.refresh_from_db()
        self._envoyer(v2)
        return v2

    def test_avenant_n_ouvre_aucune_cadence(self):
        # V1 acceptée (lead signé), puis révisée : la V2 est un avenant.
        Devis.objects.filter(pk=self.v1.pk).update(
            statut=Devis.Statut.ACCEPTE)
        Lead.objects.filter(pk=self.lead.pk).update(stage=stages.SIGNED)
        self.v1.refresh_from_db()
        self.lead.refresh_from_db()

        self._v2_envoyee()

        self.assertEqual(self._cadence().count(), 0)
        self.assertEqual(self._taches_avenant().count(), 1)

    def test_la_tache_avenant_n_est_pas_doublee(self):
        Devis.objects.filter(pk=self.v1.pk).update(
            statut=Devis.Statut.ACCEPTE)
        self.v1.refresh_from_db()
        v2 = self._v2_envoyee()
        self._envoyer(v2)
        self.assertEqual(self._taches_avenant().count(), 1)
        self.assertEqual(self._cadence().count(), 0)

    def test_premier_devis_envoye_garde_sa_cadence_normale(self):
        self._envoyer(self.v1)
        self.assertGreater(self._cadence().filter(statut=A_FAIRE).count(), 0)
        self.assertEqual(self._taches_avenant().count(), 0)

    def test_revision_d_un_devis_non_accepte_garde_la_cadence(self):
        # V1 seulement ENVOYÉE (QJR561) : ce n'est pas un avenant.
        self._v2_envoyee()
        self.assertGreater(self._cadence().filter(statut=A_FAIRE).count(), 0)
        self.assertEqual(self._taches_avenant().count(), 0)
