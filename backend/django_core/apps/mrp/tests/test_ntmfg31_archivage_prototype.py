"""NTMFG31 — Tâche planifiée : purge/archivage des OF prototype anciens.

Critère : seuls les OF prototype clôturés dépassant le seuil sont archivés,
les OF normaux ne sont jamais touchés, exécution idempotente (double-run sans
effet supplémentaire)."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.mrp.models import OrdreFabrication
from apps.mrp.services import archiver_of_prototype_anciens, parametres_mrp
from apps.mrp.tasks import archiver_of_prototype_anciens_task
from apps.stock.models import Produit

from ._fixtures import make_company, make_user


def make_produit(company, nom='Produit'):
    return Produit.objects.create(company=company, nom=nom, prix_vente=0, tva=20)


def make_of(company, produit, *, est_prototype, statut, jours_depuis_maj=0):
    of = OrdreFabrication.objects.create(
        company=company, produit=produit, quantite=1,
        statut=statut, est_prototype=est_prototype)
    if jours_depuis_maj:
        recul = timezone.now() - timedelta(days=jours_depuis_maj)
        OrdreFabrication.objects.filter(pk=of.pk).update(updated_at=recul)
        of.refresh_from_db()
    return of


class ArchiverPrototypesServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-ntmfg31-1', 'MRP NTMFG31 1')
        self.produit = make_produit(self.company)

    def test_prototype_clos_ancien_est_archive(self):
        of = make_of(
            self.company, self.produit, est_prototype=True,
            statut=OrdreFabrication.Statut.TERMINE, jours_depuis_maj=200)
        archives = archiver_of_prototype_anciens(self.company)
        self.assertEqual([a.pk for a in archives], [of.pk])
        of.refresh_from_db()
        self.assertTrue(of.is_deleted)
        self.assertFalse(
            OrdreFabrication.objects.filter(pk=of.pk).exists())  # masqué par défaut.
        self.assertTrue(
            OrdreFabrication.all_objects.filter(pk=of.pk).exists())  # jamais détruit.

    def test_prototype_clos_recent_reste_intact(self):
        of = make_of(
            self.company, self.produit, est_prototype=True,
            statut=OrdreFabrication.Statut.TERMINE, jours_depuis_maj=5)
        archives = archiver_of_prototype_anciens(self.company)
        self.assertEqual(archives, [])
        of.refresh_from_db()
        self.assertFalse(of.is_deleted)

    def test_of_normal_jamais_archive_meme_ancien(self):
        of = make_of(
            self.company, self.produit, est_prototype=False,
            statut=OrdreFabrication.Statut.TERMINE, jours_depuis_maj=400)
        archives = archiver_of_prototype_anciens(self.company)
        self.assertEqual(archives, [])
        of.refresh_from_db()
        self.assertFalse(of.is_deleted)

    def test_prototype_non_clos_ancien_reste_intact(self):
        of = make_of(
            self.company, self.produit, est_prototype=True,
            statut=OrdreFabrication.Statut.PLANIFIE, jours_depuis_maj=400)
        archives = archiver_of_prototype_anciens(self.company)
        self.assertEqual(archives, [])
        of.refresh_from_db()
        self.assertFalse(of.is_deleted)

    def test_idempotent_double_run(self):
        make_of(
            self.company, self.produit, est_prototype=True,
            statut=OrdreFabrication.Statut.TERMINE, jours_depuis_maj=200)
        premiere = archiver_of_prototype_anciens(self.company)
        seconde = archiver_of_prototype_anciens(self.company)
        self.assertEqual(len(premiere), 1)
        self.assertEqual(seconde, [])  # déjà archivé -> hors du queryset.

    def test_seuil_configurable_par_parametres_mrp(self):
        parametres = parametres_mrp(self.company)
        parametres.retention_prototype_jours = 10
        parametres.save(update_fields=['retention_prototype_jours'])
        of = make_of(
            self.company, self.produit, est_prototype=True,
            statut=OrdreFabrication.Statut.TERMINE, jours_depuis_maj=20)
        archives = archiver_of_prototype_anciens(self.company)
        self.assertEqual([a.pk for a in archives], [of.pk])


class ArchiverPrototypesTaskTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-ntmfg31-task-1', 'MRP NTMFG31 TASK 1')
        make_user(self.company, 'mrp-ntmfg31-task-user')
        self.produit = make_produit(self.company)

    def test_task_par_societe_sans_fuite_cross_tenant(self):
        autre_company = make_company('mrp-ntmfg31-task-2', 'MRP NTMFG31 TASK 2')
        autre_produit = make_produit(autre_company, 'Produit autre société')
        make_of(
            self.company, self.produit, est_prototype=True,
            statut=OrdreFabrication.Statut.TERMINE, jours_depuis_maj=200)
        of_autre = make_of(
            autre_company, autre_produit, est_prototype=True,
            statut=OrdreFabrication.Statut.TERMINE, jours_depuis_maj=5)

        result = archiver_of_prototype_anciens_task()

        self.assertEqual(result[self.company.id], 1)
        self.assertEqual(result[autre_company.id], 0)
        of_autre.refresh_from_db()
        self.assertFalse(of_autre.is_deleted)  # récent -> jamais touché.
