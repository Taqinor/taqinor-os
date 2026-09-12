"""
NTP2P34 — Tâche planifiée de recalcul des scores de risque fournisseur.

CRITÈRE D'ACCEPTATION : un document fournisseur qui expire dans la nuit fait
baisser son score visible dès le lendemain matin sans action manuelle —
``score_risque_fournisseur`` (NTP2P8) est un calcul PUR sans cache stocké,
donc déjà à jour à tout instant ; cette tâche PROUVE le sweep quotidien
(recalcul de tous les fournisseurs actifs) sans lever d'exception, best-
effort par société et par fournisseur, no-op silencieux si le sélecteur
NTP2P8 est absent.

Run :
    python manage.py test \
        apps.stock.test_ntp2p34_recompute_scores_risque -v2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import Fournisseur
from apps.stock.tasks import recompute_scores_risque_task

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=[])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


class RecomputeScoresRisqueTaskTests(TestCase):
    def setUp(self):
        self.company = _company('ntp2p34-co')
        self.user = _user(self.company, 'ntp2p34-user')

    def test_recalcule_tous_les_fournisseurs_actifs(self):
        Fournisseur.objects.create(company=self.company, nom='Four A')
        Fournisseur.objects.create(company=self.company, nom='Four B')
        result = recompute_scores_risque_task()
        self.assertEqual(result[self.company.id], 2)

    def test_fournisseur_archive_exclu(self):
        Fournisseur.objects.create(company=self.company, nom='Four Actif')
        Fournisseur.objects.create(
            company=self.company, nom='Four Archivé', is_archived=True)
        result = recompute_scores_risque_task()
        self.assertEqual(result[self.company.id], 1)

    def test_aucun_fournisseur_renvoie_zero(self):
        result = recompute_scores_risque_task()
        self.assertEqual(result[self.company.id], 0)

    def test_societe_suspendue_jamais_balayee(self):
        suspendue = _company('ntp2p34-suspendue')
        suspendue.actif = False
        suspendue.save(update_fields=['actif'])
        Fournisseur.objects.create(company=suspendue, nom='Four suspendu')
        result = recompute_scores_risque_task()
        self.assertNotIn(suspendue.id, result)

    def test_un_fournisseur_en_echec_n_arrete_pas_les_suivants(self):
        from unittest import mock

        Fournisseur.objects.create(company=self.company, nom='Four A')
        Fournisseur.objects.create(company=self.company, nom='Four B')
        from apps.stock import selectors as stock_selectors
        real = stock_selectors.score_risque_fournisseur
        calls = {'n': 0}

        def _boom(company, fournisseur_id):
            calls['n'] += 1
            if calls['n'] == 1:
                raise RuntimeError('boom')
            return real(company, fournisseur_id)

        with mock.patch.object(
                stock_selectors, 'score_risque_fournisseur', _boom):
            result = recompute_scores_risque_task()
        self.assertEqual(result[self.company.id], 1)
