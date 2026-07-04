"""Tests des heures attendues & heures supplémentaires (ZPRJ5).

Couvre : l'attendu exclut fériés (indispo)/jours non ouvrés ; l'écart correct
sur jours sous/sur-chargés ; sous-charge et heures sup ; réponse vide propre
si ressource sans user (calculable quand même — pas de filtre côté sélecteur,
contrairement à XPRJ7) ; utilise le réglage temps de la société (ZPRJ1) ;
distinct de ``temps_manquants`` (XPRJ7) ; isolation tenant côté endpoint.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import (
    Indisponibilite, Projet, ReglageTemps, RessourceProfil, Tache, Timesheet,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class HeuresAttenduesSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-z5-sel', 'S')
        self.projet = Projet.objects.create(company=self.co, code='P-Z5', nom='P')
        self.tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T', ordre=1)
        self.ressource = RessourceProfil.objects.create(
            company=self.co, nom='R1', actif=True)

    def test_attendu_8h_par_jour_ouvre_par_defaut(self):
        # Lundi 1 juin -> vendredi 5 juin 2026 : 5 jours ouvrés.
        data = selectors.heures_attendues_vs_saisies(
            self.co, self.ressource, date(2026, 6, 1), date(2026, 6, 5))
        self.assertEqual(data['jours_attendus'], 5)
        self.assertEqual(data['total_attendu'], 40.0)
        self.assertEqual(data['heures_attendues_jour'], 8.0)

    def test_utilise_heures_par_jour_configure(self):
        ReglageTemps.objects.update_or_create(
            company=self.co, defaults={'heures_par_jour': Decimal('6')})
        data = selectors.heures_attendues_vs_saisies(
            self.co, self.ressource, date(2026, 6, 1), date(2026, 6, 1))
        self.assertEqual(data['heures_attendues_jour'], 6.0)
        self.assertEqual(data['total_attendu'], 6.0)

    def test_exclut_indisponibilite(self):
        Indisponibilite.objects.create(
            company=self.co, ressource=self.ressource,
            date_debut=date(2026, 6, 2), date_fin=date(2026, 6, 2),
            type_indispo='conge')
        data = selectors.heures_attendues_vs_saisies(
            self.co, self.ressource, date(2026, 6, 1), date(2026, 6, 5))
        self.assertEqual(data['jours_attendus'], 4)  # 5 - 1 (indispo)
        dates = [j['date'] for j in data['par_jour']]
        self.assertNotIn('2026-06-02', dates)

    def test_exclut_weekend(self):
        # 6-7 juin 2026 = samedi/dimanche.
        data = selectors.heures_attendues_vs_saisies(
            self.co, self.ressource, date(2026, 6, 6), date(2026, 6, 7))
        self.assertEqual(data['jours_attendus'], 0)
        self.assertEqual(data['total_attendu'], 0.0)

    def test_ecart_sous_charge(self):
        Timesheet.objects.create(
            company=self.co, projet=self.projet, tache=self.tache,
            ressource=self.ressource, date=date(2026, 6, 1),
            heures=Decimal('4'))
        data = selectors.heures_attendues_vs_saisies(
            self.co, self.ressource, date(2026, 6, 1), date(2026, 6, 1))
        jour = data['par_jour'][0]
        self.assertEqual(jour['saisi'], 4.0)
        self.assertEqual(jour['ecart'], -4.0)  # sous-charge
        self.assertEqual(data['ecart_cumule'], -4.0)

    def test_ecart_heures_supplementaires(self):
        Timesheet.objects.create(
            company=self.co, projet=self.projet, tache=self.tache,
            ressource=self.ressource, date=date(2026, 6, 1),
            heures=Decimal('10'))
        data = selectors.heures_attendues_vs_saisies(
            self.co, self.ressource, date(2026, 6, 1), date(2026, 6, 1))
        jour = data['par_jour'][0]
        self.assertEqual(jour['ecart'], 2.0)  # heures sup
        self.assertEqual(data['ecart_cumule'], 2.0)

    def test_pile_attendu_ecart_zero(self):
        Timesheet.objects.create(
            company=self.co, projet=self.projet, tache=self.tache,
            ressource=self.ressource, date=date(2026, 6, 1),
            heures=Decimal('8'))
        data = selectors.heures_attendues_vs_saisies(
            self.co, self.ressource, date(2026, 6, 1), date(2026, 6, 1))
        self.assertEqual(data['par_jour'][0]['ecart'], 0.0)

    def test_fenetre_vide_aucun_jour(self):
        data = selectors.heures_attendues_vs_saisies(
            self.co, self.ressource, date(2026, 6, 5), date(2026, 6, 1))
        self.assertEqual(data['jours_attendus'], 0)

    def test_ressource_sans_user_calculable(self):
        # Contrairement à temps_manquants (filtre user__isnull=False), ce
        # sélecteur reste calculable pour une ressource sans compte.
        data = selectors.heures_attendues_vs_saisies(
            self.co, self.ressource, date(2026, 6, 1), date(2026, 6, 1))
        self.assertEqual(data['jours_attendus'], 1)


class HeuresAttenduesApiTests(TestCase):
    BASE = '/api/django/gestion-projet/timesheets/heures-attendues/'

    def setUp(self):
        self.co_a = make_company('gp-z5-a', 'A')
        self.co_b = make_company('gp-z5-b', 'B')
        self.user_a = make_user(self.co_a, 'z5-api-a')
        self.user_b = make_user(self.co_b, 'z5-api-b')
        self.ressource = RessourceProfil.objects.create(
            company=self.co_a, nom='R', actif=True)

    def test_endpoint_retourne_ecart(self):
        api = auth(self.user_a)
        resp = api.get(
            self.BASE,
            {'ressource': self.ressource.id, 'debut': '2026-06-01',
             'fin': '2026-06-05'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['jours_attendus'], 5)

    def test_params_manquants_400(self):
        api = auth(self.user_a)
        resp = api.get(self.BASE, {'ressource': self.ressource.id})
        self.assertEqual(resp.status_code, 400)

    def test_ressource_autre_societe_404(self):
        api = auth(self.user_b)
        resp = api.get(
            self.BASE,
            {'ressource': self.ressource.id, 'debut': '2026-06-01',
             'fin': '2026-06-05'})
        self.assertEqual(resp.status_code, 404)
