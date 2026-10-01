"""QJR561 — le suivi après-devis passe sur la RÉVISION envoyée.

ROUGE AVANT : à l'envoi de la v2, ``_planifier_apres_devis_on_devis_sent``
trouvait les barreaux ouverts de la v1, écrivait « Cadence déjà en cours pour
<v1> — aucune seconde série » et sortait : le client était relancé sur
l'ancien document. Désormais les barreaux des prédécesseurs de révision sont
RE-POINTÉS sur la v2 (nombre et dates inchangés), avec une note.

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.crm.tests_cadence_revision"
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
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape
from apps.ventes.domain.cycle_vie import reviser_devis
from apps.ventes.models import Devis

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
A_FAIRE = RelanceEtape.Statut.A_FAIRE

_seq = itertools.count(1)


class CadenceSuitLaRevision(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'QJR561 {n}', slug=f'qjr561-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'qjr561-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Prospect QJR561 {n}',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone=f'+21266561{n:04d}')
        client = Client.objects.create(
            company=self.company, nom=f'Client QJR561 {n}',
            email=f'qjr561-{n}@example.com')
        self.v1 = Devis.objects.create(
            company=self.company, reference=f'DEV-QJR561-{n:05d}',
            client=client, lead=self.lead, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'), date_envoi=GEL)

    def _envoyer(self, devis):
        devis_sent.send(sender='test', devis=devis, user=self.acteur,
                        ancien_statut='brouillon')

    def _barreaux(self):
        return self.lead.relance_etapes.filter(
            cadence='apres_devis', statut=A_FAIRE).order_by('ordre')

    def test_envoyer_la_v2_re_pointe_le_suivi_sans_redater(self):
        self._envoyer(self.v1)
        avant = list(self._barreaux().values_list('ordre', 'due_at'))
        self.assertTrue(avant, 'la cadence après devis de v1 doit exister')

        v2 = reviser_devis(self.v1, user=self.acteur)
        Devis.objects.filter(pk=v2.pk).update(
            statut=Devis.Statut.ENVOYE, date_envoi=GEL)
        v2.refresh_from_db()
        self._envoyer(v2)

        self.assertEqual(
            set(self._barreaux().values_list('devis_id', flat=True)), {v2.pk})
        self.assertEqual(
            list(self._barreaux().values_list('ordre', 'due_at')), avant)
        self.assertTrue(self.lead.activites.filter(
            body=f'Suivi repris sur la révision {v2.reference}.').exists())
        self.assertFalse(self.lead.activites.filter(
            body__startswith='Cadence après devis déjà en cours').exists())

    def test_un_autre_devis_sans_lien_ne_lance_toujours_pas_de_seconde_serie(
            self):
        self._envoyer(self.v1)
        autre = Devis.objects.create(
            company=self.company, reference='DEV-QJR561-AUTRE',
            client=self.v1.client, lead=self.lead,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20.00'),
            date_envoi=GEL)
        self._envoyer(autre)
        self.assertEqual(
            set(self._barreaux().values_list('devis_id', flat=True)),
            {self.v1.pk})
        self.assertTrue(self.lead.activites.filter(
            body__startswith='Cadence après devis déjà en cours').exists())
