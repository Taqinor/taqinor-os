"""NTEXT20 — points d'extension UI : BOUTONS custom sur une fiche.

``GET core/ui-boutons/?cible=crm.lead`` renvoie les boutons APPLICABLES au
demandeur (actifs + palier de rôle) ; ``POST <id>/declencher/`` délègue le
déclenchement réel à un gestionnaire ENREGISTRÉ par l'app propriétaire du
``type_action`` (``core.ui_extensions.register_trigger_handler`` — même
patron que ``core.workflow.register_delegation_resolver``) : ``core`` ne
connaît aucune app métier.
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core import ui_extensions
from core.models import UiActionBouton

User = get_user_model()

URL = '/api/django/core/ui-boutons/'

_seq = itertools.count(1)


def make_company(nom=None):
    return Company.objects.create(nom=nom or f'NTEXT20 Co {next(_seq)}')


def make_user(company, role='normal', username=None):
    return User.objects.create_user(
        username=username or f'ntext20-u{next(_seq)}', password='x',
        role_legacy=role, company=company)


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class BoutonsApplicablesTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.commercial = make_user(self.company, role='normal')
        self.admin = make_user(self.company, role='admin')

    def test_bouton_applicable_apparait_dans_la_cible(self):
        UiActionBouton.objects.create(
            company=self.company, cible='crm.lead', libelle='Relancer',
            type_action=UiActionBouton.TypeAction.AUTOMATION, ref=1)
        res = _auth(self.commercial).get(f'{URL}?cible=crm.lead')
        self.assertEqual(res.status_code, 200, res.data)
        libelles = [b['libelle'] for b in res.data]
        self.assertIn('Relancer', libelles)

    def test_bouton_inactif_absent(self):
        UiActionBouton.objects.create(
            company=self.company, cible='crm.lead', libelle='Désactivé',
            type_action=UiActionBouton.TypeAction.AUTOMATION, ref=1,
            actif=False)
        res = _auth(self.commercial).get(f'{URL}?cible=crm.lead')
        self.assertNotIn(
            'Désactivé', [b['libelle'] for b in res.data])

    def test_bouton_reserve_a_un_palier_absent_pour_les_autres(self):
        UiActionBouton.objects.create(
            company=self.company, cible='crm.lead', libelle='Admin only',
            type_action=UiActionBouton.TypeAction.AUTOMATION, ref=1,
            role_tier='admin')
        res_commercial = _auth(self.commercial).get(f'{URL}?cible=crm.lead')
        self.assertNotIn(
            'Admin only', [b['libelle'] for b in res_commercial.data])
        res_admin = _auth(self.admin).get(f'{URL}?cible=crm.lead')
        self.assertIn('Admin only', [b['libelle'] for b in res_admin.data])

    def test_bouton_dune_autre_cible_absent(self):
        UiActionBouton.objects.create(
            company=self.company, cible='ventes.devis', libelle='Autre fiche',
            type_action=UiActionBouton.TypeAction.AUTOMATION, ref=1)
        res = _auth(self.commercial).get(f'{URL}?cible=crm.lead')
        self.assertNotIn('Autre fiche', [b['libelle'] for b in res.data])

    def test_creation_reservee_a_l_admin(self):
        res = _auth(self.commercial).post(URL, {
            'cible': 'crm.lead', 'libelle': 'X',
            'type_action': 'automation', 'ref': 1,
        }, format='json')
        self.assertEqual(res.status_code, 403)
        res_admin = _auth(self.admin).post(URL, {
            'cible': 'crm.lead', 'libelle': 'X',
            'type_action': 'automation', 'ref': 1,
        }, format='json')
        self.assertEqual(res_admin.status_code, 201, res_admin.data)


class DeclencherBoutonTests(TestCase):
    """Le registre (``core.ui_extensions``) délègue le déclenchement réel à
    un gestionnaire enregistré — jamais exécuté par ``core`` lui-même."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.bouton = UiActionBouton.objects.create(
            company=self.company, cible='crm.lead', libelle='Relancer',
            type_action=UiActionBouton.TypeAction.AUTOMATION, ref=42)
        self._original = dict(ui_extensions._TRIGGER_HANDLERS)

    def tearDown(self):
        ui_extensions._TRIGGER_HANDLERS.clear()
        ui_extensions._TRIGGER_HANDLERS.update(self._original)

    def test_sans_gestionnaire_enregistre_noop_propre(self):
        ui_extensions._TRIGGER_HANDLERS.pop('automation', None)
        res = _auth(self.user).post(
            f'{URL}{self.bouton.pk}/declencher/',
            {'target_model': 'crm.lead', 'target_id': 1}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertFalse(res.data['ok'])
        self.assertIn('automation', res.data['message'])

    def test_gestionnaire_enregistre_est_appele_avec_la_reference(self):
        appels = []

        def _fake_handler(company, ref, target_model, target_id, user):
            appels.append((company, ref, target_model, target_id))
            return True, 'Automatisation déclenchée.'

        ui_extensions.register_trigger_handler('automation', _fake_handler)
        res = _auth(self.user).post(
            f'{URL}{self.bouton.pk}/declencher/',
            {'target_model': 'crm.lead', 'target_id': 7}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(res.data['ok'])
        self.assertEqual(len(appels), 1)
        self.assertEqual(appels[0], (self.company, 42, 'crm.lead', 7))

    def test_target_manquant_refuse_400(self):
        res = _auth(self.user).post(
            f'{URL}{self.bouton.pk}/declencher/', {}, format='json')
        self.assertEqual(res.status_code, 400)
