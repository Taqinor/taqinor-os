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


class TestVnt88VentesEnVigueur(TestCase):
    """VNT88 — ``devis_a_facturer`` et ``carnet_commande_par_mois`` lisent
    ``devis_signes_en_vigueur`` ; « facturé » = une facture ÉMISE."""

    def setUp(self):
        self.company = make_company(slug='vnt88-co', nom='VNT88 Co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='VNT88',
            telephone='+212600000088')
        self.jour = TODAY - timedelta(days=10)

    def _devis(self, ref):
        return Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut=Devis.Statut.ACCEPTE, date_acceptation=self.jour)

    def _facture(self, devis, statut, ref):
        return Facture.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            devis=devis, statut=statut, montant_ttc=Decimal('1000'))

    def _ids(self):
        return {d.id for d in devis_a_facturer(
            self.company, jours=7, today=TODAY)}

    def _carnet(self):
        from apps.ventes.selectors import carnet_commande_par_mois
        return carnet_commande_par_mois(
            self.company, self.jour.replace(day=1), TODAY)

    def test_version_remplacee_jamais_rappelee(self):
        v1 = self._devis('DEV-VNT88-V1')
        v2 = self._devis('DEV-VNT88-V2')
        Devis.objects.filter(pk=v2.pk).update(version_parent=v1)
        Devis.objects.filter(pk=v1.pk).update(superseded_by=v2,
                                              is_active=False)
        self.assertEqual(self._ids(), {v2.id})

    def test_facture_annulee_seule_rappelee(self):
        devis = self._devis('DEV-VNT88-ANN')
        self._facture(devis, Facture.Statut.ANNULEE, 'FAC-VNT88-ANN')
        self.assertIn(devis.id, self._ids())
        self.assertTrue(self._carnet())

    def test_brouillon_seul_rappele_emise_non(self):
        devis = self._devis('DEV-VNT88-BR')
        self._facture(devis, Facture.Statut.BROUILLON, 'BROUILLON-VNT88')
        self.assertIn(devis.id, self._ids())
        self._facture(devis, Facture.Statut.EMISE, 'FAC-VNT88-EM')
        self.assertNotIn(devis.id, self._ids())
        self.assertEqual(self._carnet(), {})
