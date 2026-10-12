"""ALEA32 — UNE définition de « en retard », lue partout pareil.

Une touche ``a_faire`` due le vendredi 09/10/2026 : le dimanche 11/10, aucun
jour ouvré de la société ne s'est écoulé depuis l'échéance — elle n'est en
retard NULLE PART (badge ``overdue``, drapeau ``touche_en_retard`` du lead,
scope ``overdue``, chaîne commerciale, ligne du digest de 08:30, cockpit
« Contrôle du suivi », suivi ``statut=en_retard``). Le lundi 12/10 elle l'est
PARTOUT ; un jour férié de la société décale le lundi au mardi, partout.

Horloge par ``testkit.time.frozen`` (aucun mock de la source testée) :
``core.dates.aujourd_hui_local`` et les ``maintenant`` du code lisent la
vraie horloge gelée.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.controle_suivi import controle_suivi, seuil_retard
from apps.crm.management.commands.notifier_relances_dues import (
    _ligne_dossier)
from apps.crm.models import Lead, RelanceEtape
from apps.crm.selectors import (
    STATUT_EN_RETARD, chaine_commerciale, relance_etapes_dues,
    relance_etapes_periode)
from apps.crm.serializers_cadence import RelanceEtapeSerializer
from apps.notifications.models import Holiday
from apps.parametres.models import CompanyProfile
from apps.roles.models import Role
from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS

User = get_user_model()

VENDREDI = datetime.date(2026, 10, 9)
DIMANCHE = datetime.datetime(2026, 10, 11, 10, 0, tzinfo=horaires.CASABLANCA)
LUNDI = datetime.datetime(2026, 10, 12, 10, 0, tzinfo=horaires.CASABLANCA)
MARDI = datetime.datetime(2026, 10, 13, 10, 0, tzinfo=horaires.CASABLANCA)


class RetardUniqueTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='Retard Solaire', slug='alea32-retard')
        CompanyProfile.objects.get_or_create(company=self.company)
        role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=COMMERCIAL_PERMISSIONS, est_systeme=True)
        self.meryem = User.objects.create_user(
            username='alea32-meryem', password='x',
            company=self.company, role=role)
        self.lead = Lead.objects.create(
            company=self.company, nom='Retard', prenom='P',
            owner=self.meryem, stage=stages.CONTACTED,
            telephone='+212661000321')
        self.etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='generique',
            ordre=1, canal=RelanceEtape.Canal.APPEL, libelle='Faire le devis',
            cle='devis',
            due_at=datetime.datetime.combine(
                VENDREDI, datetime.time(9, 0), tzinfo=horaires.CASABLANCA),
            due_date=VENDREDI)

    def _lectures(self, instant):
        """Les sept lectures de « en retard », à ``instant``."""
        with frozen(instant):
            today = instant.date()
            etape = RelanceEtape.objects.select_related('lead').get(
                pk=self.etape.pk)
            api = APIClient()
            api.credentials(HTTP_AUTHORIZATION=(
                f'Bearer {AccessToken.for_user(self.meryem)}'))
            resp = api.get('/api/django/crm/leads/')
            self.assertEqual(resp.status_code, 200)
            rows = (resp.data['results'] if isinstance(resp.data, dict)
                    else resp.data)
            ligne_lead = next(r for r in rows if r['id'] == self.lead.pk)
            chaine = chaine_commerciale(self.meryem, self.company)
            ligne_chaine = next(
                ligne for ligne in chaine['devis_a_preparer']['leads']
                if ligne['id'] == self.lead.pk)
            controle = controle_suivi(self.company, self.meryem,
                                      maintenant=instant)
            suivi, resume = relance_etapes_periode(
                self.company, self.meryem,
                date_debut=VENDREDI - datetime.timedelta(days=3),
                date_fin=today, statut=STATUT_EN_RETARD)
            return {
                'badge': RelanceEtapeSerializer(etape).data['overdue'],
                'drapeau_lead': ligne_lead['touche_en_retard'],
                'scope_overdue': self.etape.pk in set(relance_etapes_dues(
                    self.company, self.meryem, scope='overdue',
                    today=today).values_list('pk', flat=True)),
                'chaine_commerciale': ligne_chaine['en_retard'],
                'digest': '— en retard' in _ligne_dossier(etape, today),
                'cockpit': controle['exceptions']['en_retard']['total'] == 1,
                'suivi_en_retard': (
                    self.etape.pk in {e.pk for e in suivi}
                    and resume['en_retard'] == 1),
            }

    def test_dimanche_pas_en_retard_partout(self):
        lectures = self._lectures(DIMANCHE)
        self.assertEqual(lectures, {cle: False for cle in lectures})

    def test_lundi_en_retard_partout(self):
        lectures = self._lectures(LUNDI)
        self.assertEqual(lectures, {cle: True for cle in lectures})

    def test_ferie_respecte(self):
        Holiday.objects.create(company=self.company, nom='Férié société',
                               date=LUNDI.date())
        lundi = self._lectures(LUNDI)
        self.assertEqual(lundi, {cle: False for cle in lundi})
        mardi = self._lectures(MARDI)
        self.assertEqual(mardi, {cle: True for cle in mardi})

    def test_seuil_est_le_dernier_jour_compte(self):
        self.assertEqual(seuil_retard(self.company, DIMANCHE.date()),
                         VENDREDI)
        self.assertEqual(seuil_retard(self.company, LUNDI.date()),
                         LUNDI.date())
