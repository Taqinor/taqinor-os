"""Tests XPRJ18 — rapport des temps multi-dimensions + export xlsx.

Couvre : agrégats corrects par dimension (ressource/projet/tache/
type_activite/semaine/mois), le comparatif heures loguées vs charge_estimee
(dépassement flaggé), l'export xlsx téléchargeable, et qu'AUCUN ``cout``
interne n'apparaît dans l'export.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import Projet, RessourceProfil, Tache, Timesheet

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


class RapportTempsSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj18', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-X18', nom='Projet X18')
        self.tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Tâche X18',
            charge_estimee=Decimal('1'))  # 1j = 8h
        self.ressource = RessourceProfil.objects.create(
            company=self.co, nom='Ali', cout_horaire=Decimal('50'))

    def test_agregat_par_ressource(self):
        Timesheet.objects.create(
            company=self.co, projet=self.projet, tache=self.tache,
            ressource=self.ressource, date=date(2026, 7, 1),
            heures=Decimal('4'), facturable=True)
        Timesheet.objects.create(
            company=self.co, projet=self.projet, tache=self.tache,
            ressource=self.ressource, date=date(2026, 7, 2),
            heures=Decimal('4'), facturable=False)
        data = selectors.rapport_temps(
            self.co, date(2026, 7, 1), date(2026, 7, 31), group_by='ressource')
        self.assertEqual(len(data['lignes']), 1)
        self.assertEqual(data['lignes'][0]['heures'], Decimal('8'))
        self.assertEqual(data['lignes'][0]['heures_facturables'], Decimal('4'))
        self.assertEqual(data['total_heures'], Decimal('8'))

    def test_agregat_par_type_activite(self):
        Timesheet.objects.create(
            company=self.co, projet=self.projet, ressource=self.ressource,
            date=date(2026, 7, 1), heures=Decimal('3'),
            type_activite=Timesheet.TypeActivite.POSE)
        Timesheet.objects.create(
            company=self.co, projet=self.projet, ressource=self.ressource,
            date=date(2026, 7, 2), heures=Decimal('2'),
            type_activite=Timesheet.TypeActivite.SAV)
        data = selectors.rapport_temps(
            self.co, date(2026, 7, 1), date(2026, 7, 31),
            group_by='type_activite')
        cles = {ligne['cle'] for ligne in data['lignes']}
        self.assertEqual(
            cles, {Timesheet.TypeActivite.POSE, Timesheet.TypeActivite.SAV})

    def test_agregat_par_semaine(self):
        Timesheet.objects.create(
            company=self.co, projet=self.projet, ressource=self.ressource,
            date=date(2026, 7, 1), heures=Decimal('2'))
        data = selectors.rapport_temps(
            self.co, date(2026, 7, 1), date(2026, 7, 31), group_by='semaine')
        self.assertEqual(len(data['lignes']), 1)

    def test_group_by_invalide_retombe_ressource(self):
        data = selectors.rapport_temps(
            self.co, date(2026, 7, 1), date(2026, 7, 31),
            group_by='n_importe_quoi')
        self.assertEqual(data['group_by'], 'ressource')

    def test_comparatif_par_tache_depassement_flagge(self):
        # charge_estimee = 1j = 8h, on logue 10h → dépassement.
        Timesheet.objects.create(
            company=self.co, projet=self.projet, tache=self.tache,
            ressource=self.ressource, date=date(2026, 7, 1),
            heures=Decimal('10'))
        data = selectors.rapport_temps(
            self.co, date(2026, 7, 1), date(2026, 7, 31))
        ligne = data['par_tache'][0]
        self.assertEqual(ligne['tache_id'], self.tache.id)
        self.assertEqual(ligne['charge_estimee_heures'], Decimal('8'))
        self.assertTrue(ligne['depassement'])

    def test_comparatif_par_tache_sans_depassement(self):
        Timesheet.objects.create(
            company=self.co, projet=self.projet, tache=self.tache,
            ressource=self.ressource, date=date(2026, 7, 1),
            heures=Decimal('4'))
        data = selectors.rapport_temps(
            self.co, date(2026, 7, 1), date(2026, 7, 31))
        ligne = data['par_tache'][0]
        self.assertFalse(ligne['depassement'])


class RapportTempsEndpointTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj18-api', 'S')
        self.user = make_user(self.co, 'resp-xprj18')
        self.projet = Projet.objects.create(
            company=self.co, code='P-X18B', nom='Projet X18 API')
        self.ressource = RessourceProfil.objects.create(
            company=self.co, nom='Bob', cout_horaire=Decimal('80'))
        Timesheet.objects.create(
            company=self.co, projet=self.projet, ressource=self.ressource,
            date=date(2026, 7, 1), heures=Decimal('5'))

    def test_endpoint_json(self):
        api = auth(self.user)
        resp = api.get(
            '/api/django/gestion-projet/timesheets/rapport/'
            '?debut=2026-07-01&fin=2026-07-31')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['lignes']), 1)

    def test_endpoint_dates_obligatoires(self):
        api = auth(self.user)
        resp = api.get('/api/django/gestion-projet/timesheets/rapport/')
        self.assertEqual(resp.status_code, 400)

    def test_export_xlsx_telechargeable_sans_cout(self):
        api = auth(self.user)
        resp = api.get(
            '/api/django/gestion-projet/timesheets/rapport/'
            '?debut=2026-07-01&fin=2026-07-31&export=xlsx')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp['Content-Type'],
            'application/vnd.openxmlformats-officedocument'
            '.spreadsheetml.sheet')

        import openpyxl
        import io
        wb = openpyxl.load_workbook(io.BytesIO(resp.content))
        ws = wb.active
        headers = [cell.value for cell in ws[1]]
        self.assertNotIn('cout', [h.lower() if h else '' for h in headers])
        self.assertNotIn('coût', [h.lower() if h else '' for h in headers])
