"""AGR615 — relevé m³ et facturation à l'usage en m³ : jamais des kWh
étiquetés m³.

Run :
    python manage.py test apps.sav.tests_agr615_releves_m3 -v 2
"""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring.models import ProductionReading
from apps.sav.models import ContratMaintenance, Equipement, Ticket
from apps.sav.selectors import usage_m3_periode
from apps.sav.services import (
    ReleveDecroissantError, calculer_ligne_usage_contrat,
    enregistrer_releve_compteur,
)
from apps.stock.models import Produit

User = get_user_model()
CONTRATS = Path(__file__).resolve().parent / 'contract_samples'


def _contrat(nom):
    return json.loads((CONTRATS / f'{nom}.json').read_text(encoding='utf-8'))


class _Base(TestCase):
    slug = 'agr615'

    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug=f'{self.slug}-co', defaults={'nom': 'AGR615 Co'})
        self.admin = User.objects.create_user(
            username=f'{self.slug}_admin', password='x', role_legacy='admin',
            company=self.co)
        self.cli = Client.objects.create(
            company=self.co, nom='Ferme', prenom='AGR615',
            email=f'{self.slug}-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.co, reference=f'CHT-{self.slug.upper()}',
            client=self.cli, type_installation='agricole')
        self.produit = Produit.objects.create(
            company=self.co, nom='Pompe AGR615', sku=f'POMPE-{self.slug}',
            prix_vente=600)
        self.equip = Equipement.objects.create(
            company=self.co, produit=self.produit, installation=self.inst,
            created_by=self.admin)

    def _releve(self, valeur, jour, type_releve='m3', equip=None):
        return enregistrer_releve_compteur(
            company=self.co, equipement=equip or self.equip,
            type_releve=type_releve, valeur=Decimal(str(valeur)),
            date_releve=jour, created_by=self.admin)[0]


class UsageM3Tests(_Base):
    def _contrat_m3(self):
        return ContratMaintenance.objects.create(
            company=self.co, client=self.cli, installation=self.inst,
            date_debut=date(2027, 1, 1), actif=True,
            tarif_usage=Decimal('0.40'),
            unite_usage=ContratMaintenance.UniteUsage.M3)

    def test_60_m3_releves_factures_au_tarif(self):
        contrat = self._contrat_m3()
        self._releve(100, date(2027, 1, 5))
        self._releve(160, date(2027, 2, 4))
        self.assertEqual(
            usage_m3_periode(contrat, date(2027, 1, 5), date(2027, 2, 5)),
            Decimal('60'))
        montant, description = calculer_ligne_usage_contrat(
            contrat, date(2027, 1, 5), date(2027, 2, 5))
        self.assertEqual(montant, Decimal('24.00'))  # 60 × 0,40
        self.assertIn('60.00 m³ relevés', description)
        self.assertNotIn('kWh', description)

    def test_sans_releve_m3_jamais_les_kwh(self):
        contrat = self._contrat_m3()
        ProductionReading.objects.create(
            company=self.co, installation=self.inst,
            date=date(2027, 1, 10), energy_kwh=Decimal('999'))
        self._releve(50, date(2027, 1, 10), type_releve='heures')
        montant, motif = calculer_ligne_usage_contrat(
            contrat, date(2027, 1, 1), date(2027, 2, 1))
        self.assertIsNone(montant)
        self.assertEqual(
            motif, _contrat('releves_compteur')['ligne_usage_omise']['motif'])
        self.assertNotIn('999', motif)

    def test_borne_sans_releve_none(self):
        contrat = self._contrat_m3()
        self._releve(100, date(2027, 1, 20))  # aucun relevé ≤ début
        self.assertIsNone(
            usage_m3_periode(contrat, date(2027, 1, 5), date(2027, 2, 5)))

    def test_equipements_m2m_prioritaires(self):
        contrat = self._contrat_m3()
        autre = Equipement.objects.create(
            company=self.co, produit=self.produit, installation=self.inst,
            created_by=self.admin)
        contrat.equipements.add(autre)
        self._releve(100, date(2027, 1, 5))
        self._releve(160, date(2027, 2, 1))
        self._releve(10, date(2027, 1, 5), equip=autre)
        self._releve(15, date(2027, 2, 1), equip=autre)
        self.assertEqual(
            usage_m3_periode(contrat, date(2027, 1, 5), date(2027, 2, 5)),
            Decimal('5'))

    def test_contrat_kwh_inchange(self):
        contrat = ContratMaintenance.objects.create(
            company=self.co, client=self.cli, installation=self.inst,
            date_debut=date(2027, 1, 1), actif=True,
            tarif_usage=Decimal('1.5'),
            unite_usage=ContratMaintenance.UniteUsage.KWH)
        self._releve(100, date(2027, 1, 5))
        self._releve(160, date(2027, 2, 4))
        ProductionReading.objects.create(
            company=self.co, installation=self.inst,
            date=date(2027, 1, 10), energy_kwh=Decimal('20'))
        montant, description = calculer_ligne_usage_contrat(
            contrat, date(2027, 1, 1), date(2027, 2, 1))
        self.assertEqual(montant, Decimal('30.00'))  # 20 kWh × 1,5
        self.assertIn('kWh', description)


class ReleveM3Tests(_Base):
    slug = 'agr615r'

    def test_releve_m3_decroissant_refuse(self):
        self._releve(1838, date(2027, 2, 4))
        with self.assertRaises(ReleveDecroissantError) as ctx:
            self._releve(1000, date(2027, 2, 10))
        self.assertIn('le compteur ne peut pas reculer', str(ctx.exception))

    def test_seuil_xsav17_m3_ticket_libelle_m3(self):
        self.equip.entretien_toutes_les_heures = Decimal('500')
        self.equip.save(update_fields=['entretien_toutes_les_heures'])
        self._releve(600, date(2027, 2, 4))
        ticket = Ticket.objects.get(equipement=self.equip)
        self.assertIn('m³', ticket.description)
        self.assertNotIn('kWh', ticket.description)

    def test_api_m3_et_contrat_partage(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        url = f'/api/django/sav/equipements/{self.equip.id}/releves-compteur/'
        contrat = _contrat('releves_compteur')
        r = api.post(url, {'type': 'm3', 'valeur': '1250',
                           'date': '2027-01-05'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNone(r.data['moyenne_jour_depuis_precedent'])
        r = api.post(url, contrat['corps_post'], format='json')
        self.assertEqual(r.status_code, 201, r.data)
        # (2391 − 1250) ÷ 60 jours = 19,0 m³/jour.
        self.assertEqual(r.data['moyenne_jour_depuis_precedent'], 19.0)
        self.assertEqual(set(r.data), set(contrat['exemple_201']))
        for cle, val in contrat['exemple_201'].items():
            if val is not None:
                self.assertIsInstance(r.data[cle], type(val), cle)
        r = api.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.data[0]), set(contrat['exemple']))
        for cle, val in contrat['exemple'].items():
            self.assertIsInstance(r.data[0][cle], type(val), cle)
        # Recul refusé avec le message du contrat.
        r = api.post(url, {'type': 'm3', 'valeur': '10'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('le compteur ne peut pas reculer', r.data['detail'])
        r = api.post(url, {'type': 'litres', 'valeur': '10'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data, contrat['exemple_400_type'])
