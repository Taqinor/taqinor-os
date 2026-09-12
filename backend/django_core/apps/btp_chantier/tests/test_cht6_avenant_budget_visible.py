"""CHT6 — Avenant « impact budget » : rendre le best-effort VISIBLE.

Avant ce fix, ``_resoudre_budget_projet_id`` avalait tout (``except
Exception: return None``) : l'utilisateur cochait « impact budget », obtenait
une approbation avec ``budget_projet_id=None`` strictement indiscernable du
cas normal, et aucune trace nulle part (ni écran, ni journal).

Couvre :
* aucun projet rattaché → approbation OK + note de chatter explicite ;
* projet rattaché sans budget → note avec SA raison (distincte) ;
* budget résolu → AUCUNE note d'erreur (non-régression) ;
* exception technique → approbation OK + note + ``logger.warning`` (le
  ``try/except`` reste, il protège la transaction atomique) ;
* les raisons renvoyées par le sélecteur (contrat de la valeur de retour).
"""
from unittest.mock import patch

from django.test import TestCase
from rest_framework import status

from apps.btp_chantier import services
from apps.btp_chantier.models import AvenantChantier

from .helpers import (
    auth, make_chantier, make_company, make_projet_lie, make_user,
)

BASE = '/api/django/btp-chantier/avenants-chantier/'
LOGGER = 'apps.btp_chantier.services'


def make_budget(company, projet):
    from apps.gestion_projet.models import BudgetProjet
    return BudgetProjet.objects.create(
        company=company, projet=projet, libelle='Budget',
        statut=BudgetProjet.Statut.VALIDE)


def notes(avenant):
    from apps.records.services import chatter_qs
    return [a.body for a in chatter_qs(avenant, avenant.company)]


class AvenantBudgetNonResoluTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.chantier = make_chantier(self.co)

    def _avenant(self, reference):
        return AvenantChantier.objects.create(
            company=self.co, chantier=self.chantier,
            reference=reference, description='Test CHT6',
            montant_ht='3300.00', impact_budget=True)

    def _approuver(self, avenant):
        return auth(self.user).post(
            f'{BASE}{avenant.id}/approuver/', {}, format='json')

    def test_sans_projet_rattache_note_posee(self):
        avenant = self._avenant('AVC-CHT6-0001')
        resp = self._approuver(avenant)

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertIsNone(resp.data['budget_projet_id'])
        corps = notes(avenant)
        self.assertEqual(len(corps), 1, corps)
        self.assertIn('Impact budget', corps[0])
        self.assertIn('aucun projet', corps[0])

    def test_projet_sans_budget_note_avec_sa_raison(self):
        make_projet_lie(self.co, self.chantier)
        avenant = self._avenant('AVC-CHT6-0002')
        resp = self._approuver(avenant)

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertIsNone(resp.data['budget_projet_id'])
        corps = notes(avenant)
        self.assertEqual(len(corps), 1, corps)
        self.assertIn('aucun budget', corps[0])

    def test_budget_resolu_aucune_note(self):
        projet = make_projet_lie(self.co, self.chantier)
        budget = make_budget(self.co, projet)
        avenant = self._avenant('AVC-CHT6-0003')
        resp = self._approuver(avenant)

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['budget_projet_id'], budget.id)
        self.assertEqual(notes(avenant), [])

    def test_exception_technique_approbation_ok_note_et_log(self):
        make_projet_lie(self.co, self.chantier)
        avenant = self._avenant('AVC-CHT6-0004')
        with patch('apps.gestion_projet.selectors.budget_effectif',
                   side_effect=RuntimeError('panne simulée')):
            with self.assertLogs(LOGGER, level='WARNING') as journal:
                resp = self._approuver(avenant)

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertIsNone(resp.data['budget_projet_id'])
        avenant.refresh_from_db()
        self.assertEqual(avenant.statut, AvenantChantier.Statut.APPROUVE)
        self.assertTrue(
            any('budget projet non résolu' in ligne for ligne in journal.output),
            journal.output)
        # ``exc_info=True`` : la trace de la panne est bien journalisée.
        self.assertTrue(
            any('panne simulée' in ligne for ligne in journal.output),
            journal.output)
        corps = notes(avenant)
        self.assertEqual(len(corps), 1, corps)
        self.assertIn('erreur technique', corps[0])

    def test_impact_budget_faux_aucune_note(self):
        # Non-régression : sans « impact budget », rien ne change (la facture
        # d'acompte reste le chemin NTCON7, aucune note de budget).
        from .helpers import make_client_crm
        chantier = make_chantier(self.co, client=make_client_crm(self.co))
        avenant = AvenantChantier.objects.create(
            company=self.co, chantier=chantier, reference='AVC-CHT6-0005',
            description='Sans impact budget', montant_ht='1000.00',
            impact_budget=False)
        resp = self._approuver(avenant)

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertIsNotNone(resp.data['facture_id'])
        self.assertEqual(notes(avenant), [])


class RaisonsResolutionBudgetTests(TestCase):
    """Contrat de la valeur de retour ``(budget_id, raison)``."""

    def setUp(self):
        self.co = make_company()
        self.chantier = make_chantier(self.co)

    def test_aucun_projet_rattache(self):
        self.assertEqual(
            services._resoudre_budget_projet_id(self.chantier),
            (None, services.BUDGET_AUCUN_PROJET))

    def test_aucun_budget(self):
        make_projet_lie(self.co, self.chantier)
        self.assertEqual(
            services._resoudre_budget_projet_id(self.chantier),
            (None, services.BUDGET_AUCUN_BUDGET))

    def test_budget_resolu_sans_raison(self):
        projet = make_projet_lie(self.co, self.chantier)
        budget = make_budget(self.co, projet)
        self.assertEqual(
            services._resoudre_budget_projet_id(self.chantier),
            (budget.id, ''))

    def test_erreur_technique(self):
        make_projet_lie(self.co, self.chantier)
        with patch('apps.gestion_projet.selectors.budget_effectif',
                   side_effect=RuntimeError('panne simulée')):
            with self.assertLogs(LOGGER, level='WARNING'):
                resultat = services._resoudre_budget_projet_id(self.chantier)
        self.assertEqual(resultat, (None, services.BUDGET_ERREUR))
