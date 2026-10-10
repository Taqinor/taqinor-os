"""ACRM13 (C-ACRM-008) — un 0 saisi du survivant SURVIT à la fusion.

Sonde V_VB LSVC2-5 : un survivant « toit plat » (``inclinaison_deg=0``,
``nb_etages=0``) fusionné avec un absorbé à 30° et 2 étages ressortait à
30.00 et 2.00 — l'idiome ``in (None, '', False)`` prenait 0 pour un vide
(``0 == False``). Désormais ``_est_vide`` (``None``/``''``, ``False``
seulement pour un booléen non nullable) est LA règle de ``merge_leads``,
``_completeness`` et de l'aperçu de fusion.

Aucun mock : ``merge_leads`` et la vue « doublons » réels.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import models
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import activity
from apps.crm.models import Lead
from apps.crm.services import merge_leads
from apps.crm.leads_doublons import _MERGE_FILL_FIELDS

User = get_user_model()
NUMERIQUES = (models.IntegerField, models.DecimalField, models.FloatField)


def _champs_numeriques():
    champs = []
    for nom in _MERGE_FILL_FIELDS:
        try:
            champ = Lead._meta.get_field(nom)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(champ, NUMERIQUES) and not champ.choices:
            champs.append(nom)
    return champs


class FusionZeroTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM13 Solaire', slug='acrm13-fusion')
        self.user = User.objects.create_user(
            username='acrm13-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.n = 0

    def _lead(self, **champs):
        self.n += 1
        lead = Lead.objects.create(
            company=self.company, nom='Doublon', owner=self.user,
            telephone='+212661131313')
        if champs:
            Lead.objects.filter(pk=lead.pk).update(**champs)
        return Lead.objects.get(pk=lead.pk)

    def test_zero_survit(self):
        champs = _champs_numeriques()
        self.assertIn('inclinaison_deg', champs)
        self.assertIn('nb_etages', champs)
        survivant = self._lead(**{c: 0 for c in champs})
        absorbe = self._lead(**{c: 1 for c in champs})
        merge_leads(survivant, [absorbe], self.user)
        survivant.refresh_from_db()
        for champ in champs:
            self.assertEqual(getattr(survivant, champ), 0, champ)

    def test_vide_complete(self):
        survivant = self._lead(inclinaison_deg=None, nb_etages=None)
        absorbe = self._lead(inclinaison_deg=Decimal('30'), nb_etages=2)
        merge_leads(survivant, [absorbe], self.user)
        survivant.refresh_from_db()
        self.assertEqual(survivant.inclinaison_deg, 30)
        self.assertEqual(survivant.nb_etages, 2)

    def test_apercu_coherent(self):
        self._lead(inclinaison_deg=0, nb_etages=0, email='a@example.com',
                   ville='Rabat', adresse='Rue 1', societe='S',
                   prenom='Survivant')
        self._lead(inclinaison_deg=Decimal('30'), nb_etages=2)
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.user)}'))
        resp = api.get('/api/django/crm/leads/doublons/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(resp.data), 1)
        combles = resp.data[0]['merge_preview']['champs_combles']
        for champ in ('inclinaison_deg', 'nb_etages'):
            self.assertNotIn(activity.TRACKED_FIELDS.get(champ, champ),
                             combles)
