"""NTI18N33 — assistant de saisie guidée des fêtes mobiles hégiriennes.

Déclenchement par le rappel automatique de fin d'année (NTI18N37 — job
Celery beat, autre tâche) : HORS périmètre, non couvert ici. Ce fichier
couvre la validation/l'enregistrement (``fetes_mobiles.py``) et les vues.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.notifications.models import Holiday
from apps.parametres.fetes_mobiles import (
    FETES_MOBILES_LIBELLES,
    enregistrer_fetes_mobiles,
    fetes_mobiles_saisies,
    valider_saisie,
)

User = get_user_model()

BASE = '/api/django/parametres/fetes-mobiles/'


def _company(slug='nti18n33-co', nom='NTI18N33 Co'):
    return Company.objects.create(nom=nom, slug=slug)


def _auth(user):
    api = APIClient()
    token = str(AccessToken.for_user(user))
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return api


def _annee_future():
    return datetime.date.today().year + 1


def _dates_valides(annee):
    return {
        'aid_el_fitr': f'{annee}-03-09',
        'aid_el_adha': f'{annee}-05-16',
        '1er_moharram': f'{annee}-06-06',
        'aid_el_mawlid': f'{annee}-08-15',
    }


class ValiderSaisieTests(TestCase):
    def test_valid_complete_dates_no_errors(self):
        annee = _annee_future()
        self.assertEqual(valider_saisie(annee, _dates_valides(annee)), [])

    def test_missing_key_blocks_save(self):
        annee = _annee_future()
        dates = _dates_valides(annee)
        del dates['aid_el_mawlid']
        erreurs = valider_saisie(annee, dates)
        self.assertTrue(erreurs)
        self.assertIn('Aïd el-Mawlid', erreurs[0])

    def test_empty_value_blocks_save(self):
        annee = _annee_future()
        dates = _dates_valides(annee)
        dates['aid_el_adha'] = ''
        erreurs = valider_saisie(annee, dates)
        self.assertTrue(any('Aïd el-Adha' in e for e in erreurs))

    def test_past_date_blocks_save(self):
        annee = _annee_future()
        dates = _dates_valides(annee)
        dates['1er_moharram'] = '2000-01-01'
        erreurs = valider_saisie(annee, dates)
        self.assertTrue(any('passé' in e for e in erreurs))

    def test_date_outside_target_year_blocks_save(self):
        annee = _annee_future()
        dates = _dates_valides(annee)
        dates['aid_el_fitr'] = f'{annee + 1}-03-09'
        erreurs = valider_saisie(annee, dates)
        self.assertTrue(any(str(annee) in e for e in erreurs))

    def test_all_four_missing_reports_all_four(self):
        annee = _annee_future()
        erreurs = valider_saisie(annee, {})
        self.assertEqual(len(erreurs), 4)


class EnregistrerFetesMobilesTests(TestCase):
    def test_valid_dates_create_holiday_rows(self):
        company = _company()
        annee = _annee_future()
        enregistrer_fetes_mobiles(company, annee, _dates_valides(annee))
        self.assertEqual(
            Holiday.objects.filter(
                company=company, recurrent_annuel=False).count(), 4)

    def test_invalid_dates_raise_and_write_nothing(self):
        company = _company('nti18n33-co-2', 'NTI18N33 Co 2')
        annee = _annee_future()
        dates = _dates_valides(annee)
        del dates['aid_el_fitr']
        with self.assertRaises(ValueError):
            enregistrer_fetes_mobiles(company, annee, dates)
        # JAMAIS d'enregistrement partiel : aucune des 4 lignes n'est créée.
        self.assertEqual(
            Holiday.objects.filter(company=company).count(), 0)

    def test_saisies_reflects_state_and_prefills_the_screen(self):
        company = _company('nti18n33-co-3', 'NTI18N33 Co 3')
        annee = _annee_future()
        enregistrer_fetes_mobiles(company, annee, _dates_valides(annee))
        etat = fetes_mobiles_saisies(company, annee)
        for cle, libelle in FETES_MOBILES_LIBELLES.items():
            self.assertIsNotNone(etat[cle], libelle)

    def test_saisies_empty_before_any_entry(self):
        company = _company('nti18n33-co-4', 'NTI18N33 Co 4')
        etat = fetes_mobiles_saisies(company, _annee_future())
        self.assertTrue(all(v is None for v in etat.values()))


class FetesMobilesEndpointTests(TestCase):
    def setUp(self):
        self.company = _company('nti18n33-co-5', 'NTI18N33 Co 5')
        self.admin = User.objects.create_user(
            username='nti18n33_admin', password='x',
            role_legacy='admin', company=self.company)

    def test_get_requires_annee_param(self):
        api = _auth(self.admin)
        resp = api.get(BASE)
        self.assertEqual(resp.status_code, 400)

    def test_post_valid_dates_returns_200(self):
        api = _auth(self.admin)
        annee = _annee_future()
        resp = api.post(
            BASE + 'enregistrer/',
            {'annee': annee, 'dates': _dates_valides(annee)}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_post_blocks_incomplete_dates_with_400(self):
        api = _auth(self.admin)
        annee = _annee_future()
        dates = _dates_valides(annee)
        del dates['aid_el_adha']
        resp = api.post(
            BASE + 'enregistrer/',
            {'annee': annee, 'dates': dates}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Aïd el-Adha', resp.data['detail'])
