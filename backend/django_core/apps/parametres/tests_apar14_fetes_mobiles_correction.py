"""APAR14 — corriger une fête mobile FUTURE quand une autre fête de l'année
est déjà passée : le passé n'est refusé que pour une date nouvelle ou
modifiée, et une saisie partielle (correction) est acceptée (C-APAR-018)."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.notifications.models import Holiday
from apps.parametres.fetes_mobiles import (
    FETES_MOBILES_LIBELLES,
    SaisieFetesInvalide,
    enregistrer_fetes_mobiles,
    fetes_mobiles_saisies,
    valider_saisie,
)
from authentication.models import Company

User = get_user_model()

AUJOURD_HUI = datetime.date(2026, 10, 8)
SAISIES_2026 = {
    'aid_el_fitr': '2026-03-20',     # passé au 08/10/2026
    'aid_el_adha': '2026-10-20',
    '1er_moharram': '2026-11-16',
    'aid_el_mawlid': '2026-12-25',
}


class CorrectionFetesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APAR14 Co', slug='apar14-co')
        for cle, iso in SAISIES_2026.items():
            Holiday.objects.create(
                company=self.company, nom=FETES_MOBILES_LIBELLES[cle],
                date=datetime.date.fromisoformat(iso), recurrent_annuel=False)

    def test_quatre_dates_dont_une_future_decalee(self):
        dates = dict(SAISIES_2026, aid_el_mawlid='2026-12-26')
        existantes = fetes_mobiles_saisies(self.company, 2026)
        self.assertEqual(
            valider_saisie(2026, dates, existantes, AUJOURD_HUI), [])
        enregistrer_fetes_mobiles(
            self.company, 2026, dates, aujourd_hui=AUJOURD_HUI)
        etat = fetes_mobiles_saisies(self.company, 2026)
        self.assertEqual(etat['aid_el_fitr'], '2026-03-20')

    def test_seulement_la_date_future(self):
        enregistrer_fetes_mobiles(
            self.company, 2026, {'aid_el_adha': '2026-10-21'},
            aujourd_hui=AUJOURD_HUI)
        self.assertTrue(Holiday.objects.filter(
            company=self.company, nom='Aïd el-Adha',
            date=datetime.date(2026, 10, 21)).exists())
        # Les fêtes non renvoyées restent identiques.
        self.assertTrue(Holiday.objects.filter(
            company=self.company, nom='Aïd el-Fitr',
            date=datetime.date(2026, 3, 20)).exists())

    def test_date_passee_modifiee_reste_refusee_sous_son_champ(self):
        dates = dict(SAISIES_2026, aid_el_fitr='2026-03-21')
        with self.assertRaises(SaisieFetesInvalide) as ctx:
            enregistrer_fetes_mobiles(
                self.company, 2026, dates, aujourd_hui=AUJOURD_HUI)
        self.assertEqual(list(ctx.exception.erreurs), ['aid_el_fitr'])
        self.assertIn('passé', ctx.exception.erreurs['aid_el_fitr'][0])

    def test_premiere_saisie_reste_tout_ou_rien(self):
        autre = Company.objects.create(nom='APAR14 B', slug='apar14-b')
        erreurs = valider_saisie(
            2026, {'aid_el_adha': '2026-10-20'},
            fetes_mobiles_saisies(autre, 2026), AUJOURD_HUI)
        self.assertEqual(len(erreurs), 3)


class CorrectionFetesEndpointTests(TestCase):
    """Même scénario par l'API (date du jour réelle)."""

    def test_post_correction_200_et_relecture(self):
        today = datetime.date.today()
        hier = today - datetime.timedelta(days=1)
        demain = today + datetime.timedelta(days=1)
        if hier.year != today.year or demain.year != today.year:
            self.skipTest('fenêtre de fin/début d’année')
        annee = today.year
        company = Company.objects.create(nom='APAR14 E', slug='apar14-e')
        admin = User.objects.create_user(
            username='apar14_admin', password='x', role_legacy='admin',
            company=company)
        Holiday.objects.create(company=company, nom='Aïd el-Fitr', date=hier,
                               recurrent_annuel=False)
        Holiday.objects.create(company=company, nom='Aïd el-Mawlid',
                               date=demain, recurrent_annuel=False)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(admin)}')
        nouvelle = demain + datetime.timedelta(days=1)
        if nouvelle.year != annee:
            self.skipTest('fenêtre de fin d’année')
        r = api.post('/api/django/parametres/fetes-mobiles/enregistrer/', {
            'annee': annee,
            'dates': {'aid_el_fitr': hier.isoformat(),
                      'aid_el_mawlid': nouvelle.isoformat()},
        }, format='json')
        # Adha et Moharram jamais saisis → manquants (première saisie) : 400
        # sous CES champs seulement, jamais sous Aïd el-Fitr.
        self.assertEqual(r.status_code, 400, r.data)
        self.assertNotIn('aid_el_fitr', r.data['erreurs'])
        self.assertEqual(
            sorted(r.data['erreurs']), ['1er_moharram', 'aid_el_adha'])
        Holiday.objects.create(company=company, nom='Aïd el-Adha',
                               date=demain, recurrent_annuel=False)
        Holiday.objects.create(company=company, nom='1er Moharram',
                               date=demain, recurrent_annuel=False)
        r = api.post('/api/django/parametres/fetes-mobiles/enregistrer/', {
            'annee': annee,
            'dates': {'aid_el_fitr': hier.isoformat(),
                      'aid_el_mawlid': nouvelle.isoformat()},
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        etat = api.get('/api/django/parametres/fetes-mobiles/',
                       {'annee': annee}).data
        self.assertEqual(etat['aid_el_fitr'], hier.isoformat())
