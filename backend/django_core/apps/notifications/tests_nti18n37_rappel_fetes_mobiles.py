"""NTI18N37 — rappel Beat de saisie des fêtes mobiles de l'année N+1.

Couverture :
  - hors novembre-décembre : ne fait rien, quelle que soit la saisie ;
  - en saison, saisie incomplète (0 ou partielle) -> notifie une fois par
    société via `EventType.FETES_MOBILES_A_SAISIR` ;
  - en saison, saisie COMPLÈTE (4/4) -> aucune notification (le rappel
    s'arrête de lui-même) ;
  - cible les porteurs de `rh_voir` ; repli sur les managers si aucun.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.roles.models import Role

from .models import EventType, Notification
from .tasks import rappel_fetes_mobiles

User = get_user_model()

NOVEMBRE = timezone.make_aware(datetime.datetime(2026, 11, 15, 7, 40))
JUIN = timezone.make_aware(datetime.datetime(2026, 6, 15, 7, 40))


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _rh_admin(company, username):
    role = Role.objects.create(
        company=company, nom=f'{username}-role', permissions=['rh_voir'])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role)


def _manager_legacy(company, username):
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='admin')


class HorsSaisonTests(TestCase):
    def test_hors_novembre_decembre_ne_fait_rien(self):
        company = _company('nti18n37-hors-saison')
        _rh_admin(company, 'nti18n37-hs-admin')
        count = rappel_fetes_mobiles(now=JUIN)
        self.assertEqual(count, 0)
        self.assertFalse(Notification.objects.exists())


class SaisieIncompleteTests(TestCase):
    def setUp(self):
        self.company = _company('nti18n37-incomplete')
        self.admin = _rh_admin(self.company, 'nti18n37-inc-admin')

    def test_aucune_fete_saisie_notifie(self):
        count = rappel_fetes_mobiles(now=NOVEMBRE)
        self.assertEqual(count, 1)
        self.assertTrue(Notification.objects.filter(
            recipient=self.admin,
            event_type=EventType.FETES_MOBILES_A_SAISIR).exists())

    def test_saisie_partielle_notifie_encore(self):
        from apps.parametres.fetes_mobiles import enregistrer_fetes_mobiles
        enregistrer_fetes_mobiles(self.company, 2027, {
            'aid_el_fitr': '2027-03-20',
            'aid_el_adha': '2027-05-27',
        })
        count = rappel_fetes_mobiles(now=NOVEMBRE)
        self.assertEqual(count, 1)
        self.assertTrue(Notification.objects.filter(
            recipient=self.admin,
            event_type=EventType.FETES_MOBILES_A_SAISIR).exists())

    def test_repli_managers_si_aucun_rh_voir(self):
        company = _company('nti18n37-repli')
        manager = _manager_legacy(company, 'nti18n37-repli-manager')
        count = rappel_fetes_mobiles(now=NOVEMBRE)
        self.assertEqual(count, 1)
        self.assertTrue(Notification.objects.filter(
            recipient=manager,
            event_type=EventType.FETES_MOBILES_A_SAISIR).exists())


class SaisieCompleteTests(TestCase):
    def test_les_quatre_fetes_saisies_narrete_le_rappel(self):
        company = _company('nti18n37-complete')
        _rh_admin(company, 'nti18n37-comp-admin')
        from apps.parametres.fetes_mobiles import enregistrer_fetes_mobiles
        enregistrer_fetes_mobiles(company, 2027, {
            'aid_el_fitr': '2027-03-20',
            'aid_el_adha': '2027-05-27',
            '1er_moharram': '2027-06-16',
            'aid_el_mawlid': '2027-08-25',
        })
        count = rappel_fetes_mobiles(now=NOVEMBRE)
        self.assertEqual(count, 0)
        self.assertFalse(Notification.objects.exists())
