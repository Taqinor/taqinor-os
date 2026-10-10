"""ADEV57 (D-ADEV-6 (a)) — la révision d'un devis ACCEPTÉ n'ouvre aucune cadence.

ROUGE AVANT : à l'envoi de la V2 (avenant) d'un devis signé,
``_planifier_apres_devis_on_devis_sent`` ouvrait la cadence « après devis »
(196 étapes à faire, sonde VA p10) sur un client déjà signé. Désormais : 0
étape de cadence, UNE tâche « Faire signer l’avenant » ; un premier devis
envoyé garde sa cadence normale.

TEST-DU-TEST : retirer la condition ``_a_un_predecesseur_accepte`` de
``receivers_cadence`` ⇒ ``test_avenant_n_ouvre_aucune_cadence`` redevient
rouge (la cadence s'ouvre, aucune tâche avenant).

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.crm.tests_adev57_cadence_avenant"
"""
import datetime
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from core.events import devis_sent
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Client, Lead, RelanceEtape
from apps.crm.receivers_cadence import LIBELLE_FAIRE_SIGNER_AVENANT
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape
from apps.ventes.domain.revision import reviser_devis
from apps.ventes.models import Devis

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
