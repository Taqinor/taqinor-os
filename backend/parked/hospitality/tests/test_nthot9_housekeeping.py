"""NTHOT9 — Housekeeping (statuts chambre + tâches femmes de chambre mobiles).

Done = terminer une tâche de ménage repasse la chambre à `libre`
automatiquement, une femme de chambre ne voit que ses tâches assignées, tests.
"""
from django.test import TestCase

from apps.hospitality import services
from apps.hospitality.models import Chambre, Reservation, TacheMenage, TypeChambre

from .helpers import auth, make_company, make_user, rows


class CheckOutCreatesTacheMenageTests(TestCase):
    def setUp(self):
        self.co = make_company('hot-hk-checkout', 'Hôtel')
        self.user = make_user(self.co, 'hot-hk-checkout-user')
        self.type_std = TypeChambre.objects.create(
            company=self.co, libelle='Standard')
        self.chambre = Chambre.objects.create(
            company=self.co, type_chambre=self.type_std, numero='1101',
            statut=Chambre.Statut.OCCUPEE)
        self.reservation = Reservation.objects.create(
            company=self.co, chambre=self.chambre,
            date_arrivee='2026-08-01', date_depart='2026-08-03',
            statut=Reservation.Statut.EN_COURS,
        )

    def test_check_out_creates_tache_menage_depart(self):
        services.check_out(self.reservation, user=self.user, override=True)
        tache = TacheMenage.objects.get(chambre=self.chambre)
        self.assertEqual(tache.type_tache, TacheMenage.TypeTache.DEPART)
        self.assertEqual(tache.statut, TacheMenage.Statut.A_FAIRE)


class TerminerTacheMenageServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('hot-hk-terminer', 'Hôtel')
        self.type_std = TypeChambre.objects.create(
            company=self.co, libelle='Standard')
        self.chambre = Chambre.objects.create(
            company=self.co, type_chambre=self.type_std, numero='1102',
            statut=Chambre.Statut.SALE)
        self.tache = TacheMenage.objects.create(
            company=self.co, chambre=self.chambre,
            type_tache=TacheMenage.TypeTache.DEPART)

    def test_terminer_repasse_chambre_libre(self):
        services.terminer_tache_menage(self.tache)
        self.tache.refresh_from_db()
        self.chambre.refresh_from_db()
        self.assertEqual(self.tache.statut, TacheMenage.Statut.TERMINEE)
        self.assertIsNotNone(self.tache.date_completion)
        self.assertEqual(self.chambre.statut, Chambre.Statut.LIBRE)

    def test_terminer_deja_terminee_leve_erreur(self):
        services.terminer_tache_menage(self.tache)
        with self.assertRaises(services.TacheMenageError):
            services.terminer_tache_menage(self.tache)

    def test_terminer_ne_touche_pas_chambre_hors_service(self):
        self.chambre.statut = Chambre.Statut.HORS_SERVICE
        self.chambre.save(update_fields=['statut'])
        services.terminer_tache_menage(self.tache)
        self.chambre.refresh_from_db()
        self.assertEqual(self.chambre.statut, Chambre.Statut.HORS_SERVICE)


class TacheMenageApiTests(TestCase):
    BASE = '/api/django/hospitality/taches-menage/'

    def setUp(self):
        self.co = make_company('hot-hk-api', 'Hôtel')
        self.type_std = TypeChambre.objects.create(
            company=self.co, libelle='Standard')
        self.chambre = Chambre.objects.create(
            company=self.co, type_chambre=self.type_std, numero='1103',
            statut=Chambre.Statut.SALE)
        self.femme1 = make_user(self.co, 'hot-hk-femme1', role='normal')
        self.femme2 = make_user(self.co, 'hot-hk-femme2', role='normal')
        self.responsable = make_user(self.co, 'hot-hk-resp', role='responsable')
        self.tache1 = TacheMenage.objects.create(
            company=self.co, chambre=self.chambre, assignee=self.femme1)
        self.tache2 = TacheMenage.objects.create(
            company=self.co, chambre=self.chambre, assignee=self.femme2)

    def test_femme_de_chambre_ne_voit_que_ses_taches(self):
        resp = auth(self.femme1).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['id'], self.tache1.id)

    def test_responsable_voit_toutes_les_taches(self):
        resp = auth(self.responsable).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 2)

    def test_femme_ne_peut_pas_terminer_tache_dautrui(self):
        resp = auth(self.femme1).post(
            f'{self.BASE}{self.tache2.pk}/terminer/')
        self.assertEqual(resp.status_code, 404)

    def test_femme_termine_sa_propre_tache(self):
        resp = auth(self.femme1).post(
            f'{self.BASE}{self.tache1.pk}/terminer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.chambre.refresh_from_db()
        self.assertEqual(self.chambre.statut, Chambre.Statut.LIBRE)
