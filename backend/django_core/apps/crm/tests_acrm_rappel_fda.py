"""ACRM45 (C-ACRM-040) — le rappel FDA se retrouve par une CLÉ STABLE
(``rappel_fda``), jamais par son libellé.

Sondes V_VC LSVC4-6 / LSVC4-7 : corriger la date d'approbation posait un
SECOND rappel (le libellé porte la date), un refus les laissait ouverts tous
les deux, et ``relance_date`` restait vide (le lead absent de
``relances_du_jour``). Désormais : la date change → l'étape ouverte est
déplacée ; le statut quitte « accordé » → elle est annulée (tracée) ; la file
est recalée à chaque geste.

PATCH réel de la fiche lead ; aucun mock.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.dates import aujourd_hui_local

from apps.crm import selectors
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.cadence_filet import CLE_RAPPEL_FDA

User = get_user_model()


class RappelFdaTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM45 Solaire', slug='acrm45-fda')
        self.user = User.objects.create_user(
            username='acrm45-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.lead = Lead.objects.create(
            company=self.company, nom='Pompage', owner=self.user,
            telephone='+212661454545')
        RelanceEtape.objects.filter(lead=self.lead).delete()
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.user)}'))
        self.url = f'/api/django/crm/leads/{self.lead.pk}/'

    def _patch(self, corps):
        resp = self.api.patch(self.url, corps, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.lead.refresh_from_db()

    def _ouvertes(self):
        return list(RelanceEtape.objects.filter(
            lead=self.lead, cle=CLE_RAPPEL_FDA,
            statut=RelanceEtape.Statut.A_FAIRE))

    def test_changement_date_un_seul_rappel(self):
        self._patch({'dossier_subvention': 'accorde',
                     'dossier_subvention_le': '2026-10-10'})
        self.assertEqual(len(self._ouvertes()), 1)
        self._patch({'dossier_subvention_le': '2026-10-12'})
        ouvertes = self._ouvertes()
        self.assertEqual(len(ouvertes), 1)
        self.assertIn('Approbation préalable du 12/10', ouvertes[0].libelle)
        self.assertEqual(RelanceEtape.objects.filter(
            lead=self.lead, statut=RelanceEtape.Statut.A_FAIRE,
            libelle__startswith='Approbation préalable du').count(), 1)

    def test_refus_annule(self):
        self._patch({'dossier_subvention': 'accorde',
                     'dossier_subvention_le': '2026-10-10'})
        self._patch({'dossier_subvention': 'refuse'})
        self.assertEqual(self._ouvertes(), [])
        self.assertTrue(RelanceEtape.objects.filter(
            lead=self.lead, cle=CLE_RAPPEL_FDA,
            statut=RelanceEtape.Statut.ANNULEE).exists())
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead, body__startswith='Rappel du délai FDA annulé'
        ).exists())

    def test_file_recalee(self):
        self._patch({'dossier_subvention': 'accorde',
                     'dossier_subvention_le': '2026-10-10'})
        [etape] = self._ouvertes()
        self.assertEqual(self.lead.relance_date, etape.due_date)
        semaine = {le.pk for le in selectors.relances_du_jour(
            self.company, self.user, scope='week',
            today=aujourd_hui_local())}
        self.assertIn(self.lead.pk, semaine)
