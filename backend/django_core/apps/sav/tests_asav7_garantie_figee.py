"""ASAV7 — les horloges de garantie d'un équipement ne bougent que si
``date_pose`` ou ``produit`` changent, et jamais sur un équipement au rebut.

Éditer une note recalculait la fin de garantie depuis la durée COURANTE du
catalogue : deux équipements jumeaux finissaient avec deux fins différentes.

Run :
    python manage.py test apps.sav.tests_asav7_garantie_figee -v2
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.dateutils import add_months
from apps.sav.models import Equipement
from apps.stock.models import Produit

User = get_user_model()
BASE = '/api/django/sav/equipements'


class GarantieFigeeTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav7-co', defaults={'nom': 'ASAV7 Co'})
        self.user = User.objects.create_user(
            username='asav7_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV7')
        self.installation = Installation.objects.create(
            company=self.company, reference='CHT-ASAV7', client=client)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ASAV7', sku='OND-ASAV7',
            prix_achat=0, prix_vente=1000, garantie_mois=60)
        today = timezone.localdate()
        self.pose = add_months(today, -24)
        self.fin = add_months(self.pose, 60)
        self.jumeau_a = self._equipement('ASAV7-A', self.pose)
        self.jumeau_b = self._equipement('ASAV7-B', self.pose)
        self.rebut = self._equipement('ASAV7-R', add_months(today, -6))
        self.fin_rebut = self.rebut.date_fin_garantie
        Equipement.objects.filter(pk=self.rebut.pk).update(
            mis_au_rebut=True, date_rebut=today, motif_rebut='HS')
        # Le catalogue change APRÈS la pose : 60 → 12 mois.
        Produit.objects.filter(pk=self.produit.pk).update(garantie_mois=12)

    def _equipement(self, serie, pose):
        equip = Equipement.objects.create(
            company=self.company, produit=self.produit,
            installation=self.installation, numero_serie=serie,
            date_pose=pose)
        equip.recompute_garanties()
        equip.save(update_fields=[
            'date_fin_garantie', 'date_fin_garantie_production'])
        return equip

    def _patch(self, equip, corps):
        r = self.api.patch(f'{BASE}/{equip.pk}/', corps, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        equip.refresh_from_db()
        return r

    def test_patch_note_ne_recalcule_pas(self):
        r = self._patch(self.jumeau_a, {'note': 'nettoyage'})
        self.assertEqual(self.jumeau_a.date_fin_garantie, self.fin)
        self.jumeau_b.refresh_from_db()
        self.assertEqual(
            self.jumeau_a.date_fin_garantie, self.jumeau_b.date_fin_garantie)
        self.assertEqual(r.data.get('date_fin_garantie'), self.fin.isoformat())

    def test_rebut_fige(self):
        self._patch(self.rebut, {'note': 'archive'})
        self.assertEqual(self.rebut.date_fin_garantie, self.fin_rebut)
        nouvelle = self.rebut.date_pose - timedelta(days=30)
        self._patch(self.rebut, {'date_pose': nouvelle.isoformat()})
        self.assertEqual(self.rebut.date_fin_garantie, self.fin_rebut)

    def test_patch_date_pose_recalcule(self):
        nouvelle = self.pose + timedelta(days=10)
        self._patch(self.jumeau_b, {'date_pose': nouvelle.isoformat()})
        self.assertEqual(
            self.jumeau_b.date_fin_garantie, add_months(nouvelle, 12))
