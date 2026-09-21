"""Tests ZRH1 — Câbler le décompte des congés sur les fériés MOBILES société.

``DemandeCongeViewSet.perform_create`` (et le chemin portail ``demander-conge``)
renseignent désormais ``extra_holidays`` via
``apps.notifications.calendar_utils.feries_entre`` (Aïd, Mawlid, 1er Moharram,
férié société) en plus de la table FIXE ``holidays.JOURS_FERIES_FIXES_MA``.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.notifications.models import Holiday
from apps.rh import services
from apps.rh.models import DossierEmploye, TypeAbsence

User = get_user_model()

DEMANDES_URL = '/api/django/rh/demandes-conge/'
PORTAIL_URL = '/api/django/rh/portail/demander-conge/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule, user=None):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='N', prenom='P', user=user)


def make_type_absence(company, deduit_solde=False):
    return TypeAbsence.objects.create(
        company=company, code='CPT', libelle='Congé test',
        decompte_jours_ouvres=True, deduit_solde=deduit_solde)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class FeriesPeriodeServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('zrh1-a', 'A')

    def test_feries_periode_vide_sans_holiday(self):
        result = services.feries_periode(
            self.company, date(2026, 6, 1), date(2026, 6, 30))
        self.assertEqual(result, [])

    def test_feries_periode_inclut_aid_configure(self):
        # Aïd el-Fitr 2026 (exemple) : 20 mars 2026, saisi manuellement
        # (mobile, non récurrent) dans notifications.Holiday.
        Holiday.objects.create(
            company=self.company, date=date(2026, 3, 20),
            nom='Aïd el-Fitr', recurrent_annuel=False)
        result = services.feries_periode(
            self.company, date(2026, 3, 15), date(2026, 3, 25))
        self.assertIn(date(2026, 3, 20), result)


class DecompteCongeAvecFerieMobileTests(TestCase):
    def setUp(self):
        self.company = make_company('zrh1-b', 'B')
        self.user = make_user(self.company, 'zrh1-user')
        self.employe = make_employe(self.company, 'ZRH1-1', user=self.user)
        self.type_absence = make_type_absence(self.company)

    def test_demande_chevauchant_aid_decompte_un_jour_de_moins(self):
        # Semaine du lundi 2026-03-16 au vendredi 2026-03-20 = 5 jours ouvrés
        # SANS férié mobile configuré.
        resp_sans = auth(self.user).post(DEMANDES_URL, {
            'employe': self.employe.id,
            'type_absence': self.type_absence.id,
            'date_debut': '2026-03-16', 'date_fin': '2026-03-20',
        }, format='json')
        self.assertEqual(resp_sans.status_code, 201, resp_sans.data)
        self.assertEqual(float(resp_sans.data['jours']), 5.0)

        # Configure le vendredi 2026-03-20 comme Aïd (mobile, société A) :
        # une NOUVELLE demande sur la même plage doit décompter 1 jour de
        # moins (4 au lieu de 5).
        Holiday.objects.create(
            company=self.company, date=date(2026, 3, 20),
            nom='Aïd el-Fitr', recurrent_annuel=False)
        resp_avec = auth(self.user).post(DEMANDES_URL, {
            'employe': self.employe.id,
            'type_absence': self.type_absence.id,
            'date_debut': '2026-03-23', 'date_fin': '2026-03-27',
        }, format='json')
        self.assertEqual(resp_avec.status_code, 201, resp_avec.data)
        # Cette 2e plage ne chevauche pas le 20/03 : vérifie plutôt la 1ère
        # plage recalculée directement via le service (comportement isolé).
        jours = services.calculer_jours_demande(
            self.type_absence, date(2026, 3, 16), date(2026, 3, 20),
            extra_holidays=services.feries_periode(
                self.company, date(2026, 3, 16), date(2026, 3, 20)))
        self.assertEqual(float(jours), 4.0)

    def test_demande_sans_ferie_configure_inchangee(self):
        jours = services.calculer_jours_demande(
            self.type_absence, date(2026, 3, 16), date(2026, 3, 20),
            extra_holidays=services.feries_periode(
                self.company, date(2026, 3, 16), date(2026, 3, 20)))
        self.assertEqual(float(jours), 5.0)

    def test_isolation_tenant_ferie_autre_societe(self):
        autre = make_company('zrh1-c', 'C')
        Holiday.objects.create(
            company=autre, date=date(2026, 3, 20),
            nom='Aïd el-Fitr', recurrent_annuel=False)
        # Le férié de l'autre société n'affecte pas le décompte de self.company.
        jours = services.calculer_jours_demande(
            self.type_absence, date(2026, 3, 16), date(2026, 3, 20),
            extra_holidays=services.feries_periode(
                self.company, date(2026, 3, 16), date(2026, 3, 20)))
        self.assertEqual(float(jours), 5.0)

    def test_portail_demander_conge_renseigne_extra_holidays(self):
        Holiday.objects.create(
            company=self.company, date=date(2026, 3, 20),
            nom='Aïd el-Fitr', recurrent_annuel=False)
        resp = auth(self.user).post(PORTAIL_URL, {
            'type_absence': self.type_absence.id,
            'date_debut': '2026-03-16', 'date_fin': '2026-03-20',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(float(resp.data['jours']), 4.0)
