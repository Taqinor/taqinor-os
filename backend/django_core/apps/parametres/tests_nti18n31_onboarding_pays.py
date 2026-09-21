"""NTI18N31 — assistant « Onboarding pays » à la création d'une société.

Étapes « Pays » (`CompanyProfile.pays`, NTI18N13) et « Pack pays »
(`CompanyProfile.pack_pays`, NTI18N16 — COST, GATED-founder) NON
persistées : ces deux champs n'existent pas encore sur `CompanyProfile`
(vérifié dans `onboarding_pays.py`) — seul le seeder de fériés MAROCAIN
(`seed_ma_holidays`) est actionnable aujourd'hui. Ce fichier le couvre
explicitement (`seeder_disponible('MA')` vrai, les 3 autres pays faux tant
que NTI18N13 n'est pas construit).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.notifications.models import Holiday
from apps.parametres.models_company import CompanyProfile
from apps.parametres.onboarding_pays import (
    provisionner_localisation, seeder_disponible,
)

User = get_user_model()

BASE = '/api/django/parametres/onboarding-localisation/'


def _feries_marocains_attendus():
    """Nombre de lignes `Holiday` que le seeder MA pose sur une société neuve.

    CAD40 (21/09/2026) : `seed_ma_holidays` ne pose plus seulement les 9
    fériés FIXES — il ajoute les fêtes MOBILES que `core.calendar` CONNAÎT
    pour l'année en cours (aucune n'est calculée : une année inconnue n'en
    reçoit aucune, et la commande réclame une saisie à la main). Le compte
    dépend donc de l'année ET du contenu de `MOROCCAN_MOVABLE_HOLIDAYS` : on
    le DÉRIVE des deux sources plutôt que de figer un nombre qui périme au
    premier ajout d'année.
    """
    from core.calendar import movable_holidays
    from core.dates import aujourd_hui_local
    from apps.notifications.management.commands.seed_ma_holidays import (
        MA_FIXED_HOLIDAYS,
    )

    return len(MA_FIXED_HOLIDAYS) + len(
        movable_holidays(aujourd_hui_local().year))


def _company(slug='nti18n31-co', nom='NTI18N31 Co'):
    return Company.objects.create(nom=nom, slug=slug)


def _auth(user):
    api = APIClient()
    token = str(AccessToken.for_user(user))
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return api


class SeederDisponibleTests(TestCase):
    def test_ma_is_available_today(self):
        self.assertTrue(seeder_disponible('MA'))

    def test_fr_sn_ci_available_since_nti18n13(self):
        # NTI18N13 (drain 20/09/2026) a livré seed_holidays_fr/sn/ci dans
        # apps/notifications — la détection dynamique doit les voir sans
        # qu'aucune liste ne soit tenue à la main ici.
        self.assertTrue(seeder_disponible('FR'))
        self.assertTrue(seeder_disponible('SN'))
        self.assertTrue(seeder_disponible('CI'))

    def test_unknown_pays_never_raises(self):
        self.assertFalse(seeder_disponible('ZZ'))


class ProvisionnerLocalisationTests(TestCase):
    def test_updates_only_the_provided_fields(self):
        company = _company('nti18n31-co-2', 'NTI18N31 Co 2')
        resultat = provisionner_localisation(
            company, pays='MA', devise='EUR')
        self.assertEqual(resultat['champs_modifies'], ['devise_defaut'])
        profile = CompanyProfile.get(company)
        self.assertEqual(profile.devise_defaut, 'EUR')
        # fuseau_horaire/langue_repli non fournis -> restent au défaut.
        self.assertEqual(profile.fuseau_horaire, 'Africa/Casablanca')
        self.assertEqual(profile.langue_repli, 'fr')

    def test_seeds_moroccan_holidays_when_pays_ma(self):
        company = _company('nti18n31-co-3', 'NTI18N31 Co 3')
        resultat = provisionner_localisation(company, pays='MA')
        self.assertTrue(resultat['feries_seedes'])
        self.assertEqual(resultat['seeder_utilise'], 'seed_ma_holidays')
        attendus = _feries_marocains_attendus()
        # Anti-faux-vert : les 9 fixes sont un plancher, jamais zéro.
        self.assertGreaterEqual(attendus, 9)
        self.assertEqual(
            Holiday.objects.filter(company=company).count(), attendus)

    def test_seeding_is_idempotent(self):
        company = _company('nti18n31-co-4', 'NTI18N31 Co 4')
        provisionner_localisation(company, pays='MA')
        provisionner_localisation(company, pays='MA')
        self.assertEqual(
            Holiday.objects.filter(company=company).count(),
            _feries_marocains_attendus())

    def test_unavailable_seeder_for_pays_never_raises_no_holidays_created(self):
        # 'DE' n'a AUCUN seeder mappé dans SEEDERS_FERIES_PAR_PAYS (FR/SN/CI
        # livrés depuis NTI18N13, cf. test_fr_sn_ci_available_since_nti18n13
        # ci-dessus) : reste le cas vraiment indisponible que ce test couvre.
        company = _company('nti18n31-co-5', 'NTI18N31 Co 5')
        resultat = provisionner_localisation(company, pays='DE')
        self.assertFalse(resultat['feries_seedes'])
        self.assertIsNone(resultat['seeder_utilise'])
        self.assertEqual(Holiday.objects.filter(company=company).count(), 0)

    def test_all_three_settings_in_one_call(self):
        company = _company('nti18n31-co-6', 'NTI18N31 Co 6')
        resultat = provisionner_localisation(
            company, pays='MA', devise='MAD',
            fuseau_horaire='Africa/Casablanca', langue_repli='ar')
        profile = resultat['profile']
        self.assertEqual(profile.devise_defaut, 'MAD')
        self.assertEqual(profile.fuseau_horaire, 'Africa/Casablanca')
        self.assertEqual(profile.langue_repli, 'ar')
        self.assertTrue(resultat['feries_seedes'])


class OnboardingLocalisationEndpointTests(TestCase):
    def setUp(self):
        self.company = _company('nti18n31-co-7', 'NTI18N31 Co 7')
        self.admin = User.objects.create_user(
            username='nti18n31_admin', password='x',
            role_legacy='admin', company=self.company)

    def test_admin_can_run_the_wizard_in_one_call(self):
        api = _auth(self.admin)
        resp = api.post(BASE, {
            'pays': 'MA', 'devise': 'MAD',
            'fuseau_horaire': 'Africa/Casablanca', 'langue_repli': 'fr',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['feries_seedes'])
        self.assertEqual(resp.data['seeder_utilise'], 'seed_ma_holidays')

    def test_unknown_pays_returns_400(self):
        api = _auth(self.admin)
        resp = api.post(BASE, {'pays': 'ZZ'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_requires_authentication(self):
        api = APIClient()
        resp = api.post(BASE, {'pays': 'MA'}, format='json')
        self.assertIn(resp.status_code, (401, 403))
