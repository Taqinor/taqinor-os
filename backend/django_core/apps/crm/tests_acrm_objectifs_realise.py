"""ACRM27 (C-ACRM-022) — le réalisé des objectifs et des défis ``ca_signe``
et ``nb_devis`` est CALCULÉ (plus un 0 constant).

Sonde V_VA LSEL-2 : un objectif ``ca_signe`` de 100 000 avec un devis
accepté ce mois affichait réalisé 0, taux 0.0. Désormais ``ca_signe`` = la
lecture de « Mes équipes » (``_ca_signe_mois`` → ``ca_signe_periode``) et
``nb_devis`` = devis envoyés dans la période ; aucune métrique proposée ne
rend un réalisé constant.

Aucun mock : leads, devis et rendez-vous réels.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.dates import aujourd_hui_local

from apps.crm import selectors, stages
from apps.crm.models import (
    Appointment, Client, Defi, Lead, ObjectifCommercial)
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()


class ObjectifsRealiseTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM27 Solaire', slug='acrm27-objectifs')
        self.user = User.objects.create_user(
            username='acrm27-com', password='x', company=self.company,
            role_legacy='responsable')
        self.today = aujourd_hui_local()
        self.client_c = Client.objects.create(
            company=self.company, nom='Client', prenom='Objectif')
        self.lead = Lead.objects.create(
            company=self.company, nom='Objectif', owner=self.user,
            client=self.client_c, stage=stages.SIGNED)
        Lead.objects.filter(pk=self.lead.pk).update(
            first_contacted_at=timezone.now())
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='ACRM27-P',
            prix_vente=Decimal('1000'), quantite_stock=50)
        self.accepte = self._devis('DEV-ACRM27-0001', 'accepte')
        self._devis('DEV-ACRM27-0002', 'envoye')
        Appointment.objects.create(
            company=self.company, lead=self.lead, created_by=self.user,
            scheduled_at=timezone.now(), statut=Appointment.Statut.EFFECTUE)

    def _devis(self, reference, statut):
        devis = Devis.objects.create(
            company=self.company, reference=reference, client=self.client_c,
            lead=self.lead, statut=statut, taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user,
            date_envoi=timezone.now(),
            date_acceptation=self.today if statut == 'accepte' else None)
        LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation='Panneau 550W',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'))
        return devis

    def _objectif(self, metric, cible):
        return ObjectifCommercial.objects.create(
            company=self.company, owner=self.user, metric=metric,
            cible=Decimal(cible), period_type='month',
            period_year=self.today.year, period_month=self.today.month)

    def test_ca_signe_egal_mes_equipes(self):
        objectif = self._objectif('ca_signe', '100000')
        mes_equipes = selectors._ca_signe_mois(
            self.company, [self.user.pk], self.today)
        self.assertEqual(mes_equipes, Decimal(str(self.accepte.total_ttc)))
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.user)}'))
        resp = api.get(f'/api/django/crm/objectifs/{objectif.pk}/attainment/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(Decimal(str(resp.data['realise'])), mes_equipes)
        self.assertAlmostEqual(
            float(resp.data['taux']),
            round(float(mes_equipes) / 100000 * 100, 1))

    def test_nb_devis_compte(self):
        attainment = selectors.compute_attainment(
            self._objectif('nb_devis', '5'))
        self.assertEqual(attainment['realise'], Decimal('2'))

    def test_chaque_metric_calculee(self):
        defi_fin = self.today + datetime.timedelta(days=1)
        for metric, _libelle in ObjectifCommercial.Metric.choices:
            attainment = selectors.compute_attainment(
                self._objectif(metric, '1'))
            self.assertGreater(attainment['realise'], 0, metric)
            defi = Defi.objects.create(
                company=self.company, nom=f'Défi {metric}', metrique=metric,
                periode_debut=self.today.replace(day=1),
                periode_fin=defi_fin)
            classement = selectors.classement_defi(defi)
            ligne = next((r for r in classement
                          if r['owner_id'] == self.user.pk), None)
            self.assertIsNotNone(ligne, metric)
            self.assertGreater(ligne['realise'], 0, metric)
