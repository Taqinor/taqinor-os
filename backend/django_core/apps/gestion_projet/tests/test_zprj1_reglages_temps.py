"""Tests des réglages société temps (ZPRJ1) — arrondi & unité d'encodage.

Couvre : ``get_or_create_reglage_temps`` get-or-create scopé société (jamais
dupliqué, isolation tenant) ; ``arrondir_duree`` respecte mode/pas sur cas
limites (0, exact, +1 minute) pour les 3 modes ; ``plan_de_charge`` utilise
``heures_par_jour`` configuré ; l'endpoint ``reglages-temps/mon-reglage/``
(GET+PATCH, responsable/admin) ; le chrono XPRJ5 consomme désormais le
réglage par défaut (plus une constante en dur).
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors, services
from apps.gestion_projet.models import (
    ChronoEnCours, Projet, ReglageTemps, RessourceProfil, Tache,
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


class GetOrCreateReglageTempsTests(TestCase):
    def setUp(self):
        self.co_a = make_company('gp-z1-a', 'A')
        self.co_b = make_company('gp-z1-b', 'B')

    def test_get_or_create_pas_de_doublon(self):
        r1 = services.get_or_create_reglage_temps(self.co_a)
        r2 = services.get_or_create_reglage_temps(self.co_a)
        self.assertEqual(r1.id, r2.id)
        self.assertEqual(
            ReglageTemps.objects.filter(company=self.co_a).count(), 1)

    def test_valeurs_par_defaut(self):
        r = services.get_or_create_reglage_temps(self.co_a)
        self.assertEqual(r.arrondi_minutes, 15)
        self.assertEqual(r.mode_arrondi, ReglageTemps.ModeArrondi.SUPERIEUR)
        self.assertEqual(r.unite_saisie, ReglageTemps.UniteSaisie.HEURES)
        self.assertEqual(r.heures_par_jour, Decimal('8'))

    def test_isolation_societe(self):
        services.get_or_create_reglage_temps(self.co_a)
        self.assertFalse(
            ReglageTemps.objects.filter(company=self.co_b).exists())


class ArrondirDureeTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-z1-arr', 'S')

    def test_zero_heures_reste_zero(self):
        for mode in ('inferieur', 'superieur', 'proche'):
            ReglageTemps.objects.update_or_create(
                company=self.co, defaults={'mode_arrondi': mode})
            self.assertEqual(
                services.arrondir_duree(self.co, 0), Decimal('0.00'))

    def test_duree_exacte_sur_palier_inchangee(self):
        ReglageTemps.objects.update_or_create(
            company=self.co, defaults={
                'arrondi_minutes': 15, 'mode_arrondi': 'superieur'})
        # 30 minutes = 0.5h, exactement 2 paliers de 15 min.
        self.assertEqual(
            services.arrondir_duree(self.co, Decimal('0.5')), Decimal('0.50'))

    def test_mode_superieur_plus_une_minute_monte(self):
        ReglageTemps.objects.update_or_create(
            company=self.co, defaults={
                'arrondi_minutes': 15, 'mode_arrondi': 'superieur'})
        # 16 minutes -> palier supérieur (30 min = 0.5h).
        heures = Decimal('16') / Decimal('60')
        self.assertEqual(
            services.arrondir_duree(self.co, heures), Decimal('0.50'))

    def test_mode_inferieur_plus_une_minute_reste_en_dessous(self):
        ReglageTemps.objects.update_or_create(
            company=self.co, defaults={
                'arrondi_minutes': 15, 'mode_arrondi': 'inferieur'})
        # 16 minutes -> palier inférieur (15 min = 0.25h).
        heures = Decimal('16') / Decimal('60')
        self.assertEqual(
            services.arrondir_duree(self.co, heures), Decimal('0.25'))

    def test_mode_proche_choisit_le_plus_proche(self):
        ReglageTemps.objects.update_or_create(
            company=self.co, defaults={
                'arrondi_minutes': 10, 'mode_arrondi': 'proche'})
        # 14 minutes -> plus proche de 10 (palier inf) que 20 (palier sup)
        # -> 10 min = 0.1667h arrondi 0.17.
        heures = Decimal('14') / Decimal('60')
        self.assertEqual(
            services.arrondir_duree(self.co, heures),
            (Decimal('10') / Decimal('60')).quantize(Decimal('0.01')))
        # 16 minutes -> plus proche de 20 (palier sup).
        heures2 = Decimal('16') / Decimal('60')
        self.assertEqual(
            services.arrondir_duree(self.co, heures2),
            (Decimal('20') / Decimal('60')).quantize(Decimal('0.01')))

    def test_pas_par_defaut_si_reglage_absent(self):
        co2 = make_company('gp-z1-arr-defaut', 'S2')
        heures = Decimal('1') / Decimal('60')
        # aucun ReglageTemps encore créé pour co2 -> get_or_create silencieux,
        # défauts (15 min, supérieur) -> 15 min = 0.25h.
        self.assertEqual(
            services.arrondir_duree(co2, heures), Decimal('0.25'))


class ChronoConsommeReglageTests(TestCase):
    """Le chrono XPRJ5 utilise désormais le réglage société par défaut."""

    def setUp(self):
        self.co = make_company('gp-z1-chrono', 'S')
        self.user = make_user(self.co, 'z1-chrono-u')
        self.projet = Projet.objects.create(company=self.co, code='P-Z1', nom='P')
        self.tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T', ordre=1)
        RessourceProfil.objects.create(company=self.co, nom='R', user=self.user)

    def test_arret_par_defaut_utilise_reglage_societe(self):
        ReglageTemps.objects.update_or_create(
            company=self.co, defaults={
                'arrondi_minutes': 30, 'mode_arrondi': 'superieur'})
        services.demarrer_chrono(self.tache, self.user)
        chrono = ChronoEnCours.objects.get(user=self.user)
        chrono.demarre_a = timezone.now() - timedelta(minutes=5)
        chrono.save(update_fields=['demarre_a'])
        timesheet = services.arreter_chrono(self.user)
        # 5 min avec pas de 30 min (supérieur) -> 30 min = 0.5h.
        self.assertEqual(timesheet.heures, Decimal('0.50'))

    def test_override_pas_minutes_encore_supporte(self):
        services.demarrer_chrono(self.tache, self.user)
        chrono = ChronoEnCours.objects.get(user=self.user)
        chrono.demarre_a = timezone.now() - timedelta(minutes=20)
        chrono.save(update_fields=['demarre_a'])
        # Override explicite à 60 minutes -> 1h.
        timesheet = services.arreter_chrono(self.user, pas_minutes=60)
        self.assertEqual(timesheet.heures, Decimal('1.00'))


class PlanDeChargeReglageTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-z1-plan', 'S')

    def test_plan_de_charge_utilise_heures_par_jour_configure(self):
        ReglageTemps.objects.update_or_create(
            company=self.co, defaults={'heures_par_jour': Decimal('6')})
        RessourceProfil.objects.create(company=self.co, nom='R1', actif=True)
        debut = date(2026, 6, 1)  # lundi
        fin = date(2026, 6, 1)
        data = selectors.plan_de_charge(self.co, debut, fin)
        self.assertEqual(data['heures_par_jour'], 6.0)
        self.assertEqual(data['lignes'][0]['capacite_heures'], 6.0)

    def test_plan_de_charge_sans_reglage_utilise_defaut_8h(self):
        RessourceProfil.objects.create(company=self.co, nom='R1', actif=True)
        debut = date(2026, 6, 1)
        fin = date(2026, 6, 1)
        data = selectors.plan_de_charge(self.co, debut, fin)
        self.assertEqual(data['heures_par_jour'], 8.0)

    def test_override_explicite_prioritaire(self):
        ReglageTemps.objects.update_or_create(
            company=self.co, defaults={'heures_par_jour': Decimal('6')})
        RessourceProfil.objects.create(company=self.co, nom='R1', actif=True)
        debut = date(2026, 6, 1)
        fin = date(2026, 6, 1)
        data = selectors.plan_de_charge(self.co, debut, fin, heures_par_jour=4)
        self.assertEqual(data['heures_par_jour'], 4.0)


class ReglageTempsApiTests(TestCase):
    BASE = '/api/django/gestion-projet/reglages-temps/mon-reglage/'

    def setUp(self):
        self.co_a = make_company('gp-z1-api-a', 'A')
        self.co_b = make_company('gp-z1-api-b', 'B')
        self.user_a = make_user(self.co_a, 'z1-api-a')
        self.user_b = make_user(self.co_b, 'z1-api-b')

    def test_get_cree_a_la_demande(self):
        api = auth(self.user_a)
        resp = api.get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['arrondi_minutes'], 15)
        self.assertEqual(
            ReglageTemps.objects.filter(company=self.co_a).count(), 1)

    def test_patch_modifie_le_reglage(self):
        api = auth(self.user_a)
        resp = api.patch(
            self.BASE, {'arrondi_minutes': 30, 'mode_arrondi': 'proche'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['arrondi_minutes'], 30)
        self.assertEqual(resp.data['mode_arrondi'], 'proche')

    def test_isolation_societe(self):
        api_a = auth(self.user_a)
        api_a.patch(self.BASE, {'arrondi_minutes': 45}, format='json')
        api_b = auth(self.user_b)
        resp_b = api_b.get(self.BASE)
        self.assertEqual(resp_b.data['arrondi_minutes'], 15)  # défaut, pas 45

    def test_role_normal_interdit(self):
        normal = make_user(self.co_a, 'z1-api-normal', role='normal')
        api = auth(normal)
        resp = api.get(self.BASE)
        self.assertEqual(resp.status_code, 403)
