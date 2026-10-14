"""
ZFAC12 — Rappel de courtoisie pré-échéance côté DEVIS accepté non facturé
(backlog à facturer).

Un devis accepté sans facture depuis > N jours remonte dans la liste
« à facturer » et déclenche un log/tâche, un devis déjà facturé est ignoré,
N réglable, scoping société.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_zfac12_devis_a_facturer -v 2
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.ventes.models import Devis, DevisActivity, Facture
from apps.ventes.scheduled import devis_a_facturer_reminder
from apps.ventes.selectors import devis_a_facturer

TODAY = timezone.now().date()


def make_company(slug='zfac12-co', nom='ZFAC12 Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestDevisAFacturer(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ZFAC12',
            telephone='+212600000011')

    def _devis(self, ref, date_acceptation):
        return Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut=Devis.Statut.ACCEPTE, date_acceptation=date_acceptation,
        )

    def test_old_accepted_devis_without_facture_flagged(self):
        old_devis = self._devis(
            'DEV-ZFAC12-0001', TODAY - timedelta(days=10))
        recent_devis = self._devis(
            'DEV-ZFAC12-0002', TODAY - timedelta(days=2))
        candidats = devis_a_facturer(self.company, jours=7, today=TODAY)
        ids = {d.id for d in candidats}
        self.assertIn(old_devis.id, ids)
        self.assertNotIn(recent_devis.id, ids)

    def test_devis_already_invoiced_ignored(self):
        devis = self._devis('DEV-ZFAC12-0003', TODAY - timedelta(days=10))
        Facture.objects.create(
            company=self.company, reference='FAC-ZFAC12-0001',
            client=self.client_obj, devis=devis,
            statut=Facture.Statut.EMISE, montant_ttc=Decimal('1000'))
        candidats = devis_a_facturer(self.company, jours=7, today=TODAY)
        self.assertNotIn(devis.id, {d.id for d in candidats})

    def test_configurable_n_days(self):
        devis = self._devis('DEV-ZFAC12-0004', TODAY - timedelta(days=3))
        self.assertEqual(
            len(devis_a_facturer(self.company, jours=7, today=TODAY)), 0)
        candidats = devis_a_facturer(self.company, jours=2, today=TODAY)
        self.assertIn(devis.id, {d.id for d in candidats})

    def test_reminder_task_logs_chatter_entry(self):
        devis = self._devis('DEV-ZFAC12-0005', TODAY - timedelta(days=10))
        count = devis_a_facturer_reminder(jours=7)
        self.assertEqual(count, 1)
        entry = DevisActivity.objects.filter(
            devis=devis, field='a_facturer').first()
        self.assertIsNotNone(entry)

    def test_reminder_task_idempotent_same_day(self):
        self._devis('DEV-ZFAC12-0006', TODAY - timedelta(days=10))
        devis_a_facturer_reminder(jours=7)
        second_count = devis_a_facturer_reminder(jours=7)
        self.assertEqual(second_count, 0)

    def test_scoping_by_company(self):
        other_company = make_company(slug='zfac12-other', nom='Other Co')
        other_client = Client.objects.create(
            company=other_company, nom='Autre', prenom='Client',
            telephone='+212600000012')
        Devis.objects.create(
            company=other_company, reference='DEV-ZFAC12-OTHER',
            client=other_client, statut=Devis.Statut.ACCEPTE,
            date_acceptation=TODAY - timedelta(days=10))
        candidats = devis_a_facturer(self.company, jours=7, today=TODAY)
        self.assertEqual(candidats, [])

    def test_vnt88_version_remplacee_jamais_rappelee(self):
        """VNT88 — V1 acceptée remplacée par une V2 acceptée (les factures
        re-pointées sur la V2) : seule la V2, vente en vigueur, est lue."""
        v2 = self._devis('DEV-ZFAC12-V2', TODAY - timedelta(days=10))
        v1 = self._devis('DEV-ZFAC12-V1', TODAY - timedelta(days=20))
        Devis.objects.filter(pk=v1.pk).update(is_active=False,
                                              superseded_by=v2)
        ids = {d.id for d in devis_a_facturer(
            self.company, jours=7, today=TODAY)}
        self.assertNotIn(v1.id, ids)
        self.assertIn(v2.id, ids)
        Facture.objects.create(
            company=self.company, reference='FAC-ZFAC12-V2',
            client=self.client_obj, devis=v2,
            statut=Facture.Statut.EMISE, montant_ttc=Decimal('1000'))
        self.assertEqual(
            devis_a_facturer(self.company, jours=7, today=TODAY), [])

    def test_vnt88_seule_facture_annulee_rappelle_le_devis(self):
        devis = self._devis('DEV-ZFAC12-ANN', TODAY - timedelta(days=10))
        Facture.objects.create(
            company=self.company, reference='FAC-ZFAC12-ANN',
            client=self.client_obj, devis=devis,
            statut=Facture.Statut.ANNULEE, montant_ttc=Decimal('1000'))
        self.assertIn(devis.id, {d.id for d in devis_a_facturer(
            self.company, jours=7, today=TODAY)})

    def test_vnt88_carnet_de_commandes_sur_la_vente_en_vigueur(self):
        from apps.ventes.selectors_facturation import carnet_commande_par_mois
        v2 = self._devis('DEV-ZFAC12-C2', TODAY)
        v1 = self._devis('DEV-ZFAC12-C1', TODAY)
        Devis.objects.filter(pk=v1.pk).update(is_active=False,
                                              superseded_by=v2)
        annulee = self._devis('DEV-ZFAC12-C3', TODAY)
        Facture.objects.create(
            company=self.company, reference='FAC-ZFAC12-C3',
            client=self.client_obj, devis=annulee,
            statut=Facture.Statut.ANNULEE, montant_ttc=Decimal('1000'))
        carnet = carnet_commande_par_mois(self.company, TODAY, TODAY)
        attendu = sum((Decimal(str(d.total_ttc)) for d in Devis.objects.filter(
            pk__in=[v2.pk, annulee.pk])), Decimal('0'))
        self.assertEqual(sum(carnet.values(), Decimal('0')), attendu)
        from apps.ventes.selectors_facturation import (
            _ventes_sans_facture_active)
        self.assertEqual(
            {d.id for d in _ventes_sans_facture_active(self.company)},
            {v2.id, annulee.id})
