"""CAD119 — la vraie date de création Odoo va dans un CHAMP, pas dans une note.

Audit L3 du 21/09/2026, section CAD-K. ``odoo_sync`` écrivait la date
d'origine dans une note en texte libre (« Créé dans Odoo: … ») que personne ne
peut requêter, et ``Lead.date_creation`` est en ``auto_now_add`` : tous les
leads synchronisés portaient la date de la SYNCHRONISATION. Le modèle à
copier existait à côté — la création Meta repose déjà la vraie heure
d'arrivée. Sans ce champ, tout futur import fausserait de nouveau les KPI de
délai (CAD87).

Ce fichier verrouille :

  * la date Odoo voyage dans une COLONNE du flux (``odoo_sync.build_rows``)
    et arrive sur ``Lead.date_creation_origine`` ;
  * ``Lead.date_origine`` lit cette date EN PRIORITÉ, et retombe sur
    ``date_creation`` quand elle est absente (leads natifs, lignes d'avant
    CAD119) ;
  * une date illisible ne fait jamais tomber un import : la colonne reste
    vide ;
  * et le KPI « joints sous 5 jours » ne bouge pas après un import de
    rattrapage.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from authentication.models import Company

from apps.crm import odoo_sync, stages
from apps.crm.management.commands.import_odoo_leads import (
    ODOO_FIELD_MAP, _date_odoo)
from apps.crm.models import Lead, LeadActivity
from apps.crm.selectors import kpi_cadences
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Une date de création Odoo telle qu'Odoo la publie : UTC, sans fuseau écrit.
CREATE_DATE_ODOO = '2024-03-08 09:12:44'


class ConversionTests(SimpleTestCase):
    def test_une_date_odoo_est_lue_en_utc(self):
        instant = _date_odoo(CREATE_DATE_ODOO)
        self.assertEqual(instant, datetime.datetime(
            2024, 3, 8, 9, 12, 44, tzinfo=datetime.timezone.utc))

    def test_une_date_illisible_ou_vide_ne_casse_rien(self):
        for valeur in ('', None, 'pas une date', '0000-00-00 00:00:00'):
            self.assertIsNone(_date_odoo(valeur), valeur)

    def test_les_deux_entetes_sont_reconnues(self):
        """Le champ natif Odoo (chemin fichier) et la clé de `build_rows`."""
        self.assertEqual(ODOO_FIELD_MAP['create_date'], 'date_creation_odoo')
        self.assertEqual(ODOO_FIELD_MAP['date_creation_odoo'],
                         'date_creation_odoo')

    def test_build_rows_porte_la_date_dans_une_colonne(self):
        rows = odoo_sync.build_rows([{
            'id': 4242,
            'name': 'Prospect Odoo',
            'create_date': CREATE_DATE_ODOO,
            'stage_id': [1, 'New'],
        }], {})
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]['date_creation_odoo'], CREATE_DATE_ODOO)
        # La note historique reste : elle est lisible par un humain, la
        # colonne est requêtable par une machine. Les deux servent.
        self.assertIn('Créé dans Odoo: ' + CREATE_DATE_ODOO, rows[0]['note'])

    def test_build_rows_sans_date_nemet_pas_la_colonne(self):
        rows = odoo_sync.build_rows([{
            'id': 4243, 'name': 'Sans date', 'stage_id': [1, 'New'],
        }], {})
        self.assertNotIn('date_creation_odoo', rows[0])


class DateOrigineTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='cad119', defaults={'nom': 'cad119'})
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='cad119-resp', password='x', role_legacy='responsable',
            company=self.company)

    def test_un_lead_importe_porte_sa_date_dorigine(self):
        lead = Lead.objects.create(
            company=self.company, nom='Prospect Odoo',
            source=Lead.Source.ODOO_IMPORT_TEST, stage=stages.NEW,
            date_creation_origine=_date_odoo(CREATE_DATE_ODOO))
        lead.refresh_from_db()
        self.assertEqual(lead.date_creation_origine,
                         _date_odoo(CREATE_DATE_ODOO))
        self.assertEqual(lead.date_origine, lead.date_creation_origine)
        # `date_creation` reste la date d'INSERTION : les deux sont vraies et
        # disent deux choses différentes.
        self.assertNotEqual(lead.date_creation, lead.date_creation_origine)

    def test_un_lead_natif_retombe_sur_sa_date_de_creation(self):
        lead = Lead.objects.create(
            company=self.company, nom='Natif', stage=stages.NEW)
        self.assertIsNone(lead.date_creation_origine)
        self.assertEqual(lead.date_origine, lead.date_creation)

    def test_le_champ_porte_sa_question(self):
        """« Chaque champ EST le script d'appel » : la question vit ici."""
        champ = Lead._meta.get_field('date_creation_origine')
        self.assertTrue(champ.help_text)
        self.assertTrue(champ.null)


class KpiApresImportTests(TestCase):
    """« Le KPI joints sous 5 jours ne bouge pas après un import. »"""

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='cad119-kpi', defaults={'nom': 'cad119-kpi'})
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='cad119-kpi-u', password='x', role_legacy='responsable',
            company=self.company)
        self.now = timezone.now()

    def _lead_joint(self, nom, **extra):
        lead = Lead.objects.create(
            company=self.company, nom=nom, stage=stages.NEW,
            owner=self.acteur, **extra)
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=self.now - datetime.timedelta(days=2))
        lead.refresh_from_db(fields=['date_creation'])
        activite = LeadActivity.objects.create(
            company=self.company, lead=lead, user=self.acteur,
            kind=LeadActivity.Kind.APPEL, body='Appel.', outcome='joint')
        LeadActivity.objects.filter(pk=activite.pk).update(
            created_at=lead.date_creation + datetime.timedelta(hours=1))
        return lead

    def test_un_import_de_rattrapage_ne_fait_pas_bouger_le_kpi(self):
        self._lead_joint('Natif')
        avant = kpi_cadences(self.company)['joints_sous_5j_pct']
        for index in range(15):
            Lead.objects.create(
                company=self.company, nom=f'Odoo {index}',
                source=Lead.Source.ODOO_IMPORT_TEST, stage=stages.NEW,
                date_creation_origine=_date_odoo(CREATE_DATE_ODOO))
        self.assertEqual(kpi_cadences(self.company)['joints_sous_5j_pct'],
                         avant)

    def test_le_delai_se_compte_depuis_la_date_dorigine(self):
        """Un lead dont l'origine est ancienne n'est pas « joint en 1 h »."""
        lead = self._lead_joint('Rattrapé')
        Lead.objects.filter(pk=lead.pk).update(
            date_creation_origine=self.now - datetime.timedelta(days=400))
        lead.refresh_from_db()
        self.assertEqual(lead.date_origine, lead.date_creation_origine)
        self.assertEqual(kpi_cadences(self.company)['joints_sous_5j_pct'], 0.0)
