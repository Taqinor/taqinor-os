"""CHT1 — ``_resoudre_budget_projet_id`` : défense en profondeur multi-sociétés.

``gestion_projet.ProjetChantier.chantier_id`` est une référence LÂCHE : aucun
FK, aucune contrainte de base. Le sérialiseur refuse désormais une écriture
cross-société (voir ``gestion_projet.tests.test_cht1_chantier_cross_societe``),
mais une ligne peut exister hors sérialiseur (migration de données, écriture
directe, historique). L'approbation d'un avenant de la société A ne doit alors
JAMAIS résoudre le budget d'un projet de la société B.

Couvre :
* ligne plantée par la société B sur le chantier de A → ``budget_projet_id``
  reste ``None`` à l'approbation de l'avenant de A (ROUGE avant le fix : le
  filtre ne portait que sur ``chantier_id``, donc le budget de B était résolu) ;
* non-régression : la ligne LÉGITIME de A résout bien le budget de A.
"""
from django.test import TestCase
from rest_framework import status

from apps.btp_chantier.models import AvenantChantier

from .helpers import (
    auth, make_chantier, make_company, make_projet_lie, make_user,
)

BASE = '/api/django/btp-chantier/avenants-chantier/'


def make_budget(company, projet):
    from apps.gestion_projet.models import BudgetProjet
    return BudgetProjet.objects.create(
        company=company, projet=projet, libelle='Budget',
        statut=BudgetProjet.Statut.VALIDE)


class BudgetProjetCrossSocieteTests(TestCase):
    def setUp(self):
        self.co_a = make_company()
        self.co_b = make_company()
        self.user_a = make_user(self.co_a)
        self.chantier_a = make_chantier(self.co_a)

    def _avenant(self, reference):
        return AvenantChantier.objects.create(
            company=self.co_a, chantier=self.chantier_a,
            reference=reference, description='Test CHT1',
            montant_ht='4200.00', impact_budget=True)

    def test_ligne_plantee_par_autre_societe_ne_resout_aucun_budget(self):
        # La société B rattache (hors sérialiseur) le chantier de A à SON
        # projet, qui porte un budget validé.
        projet_b = make_projet_lie(self.co_b, self.chantier_a)
        budget_b = make_budget(self.co_b, projet_b)

        avenant = self._avenant('AVC-CHT1-0001')
        api = auth(self.user_a)
        resp = api.post(f'{BASE}{avenant.id}/approuver/', {}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['statut'], 'approuve')
        self.assertIsNone(resp.data['budget_projet_id'])
        avenant.refresh_from_db()
        self.assertIsNone(avenant.budget_projet_id)
        self.assertNotEqual(avenant.budget_projet_id, budget_b.id)

    def test_ligne_legitime_resout_le_budget_de_sa_societe(self):
        projet_a = make_projet_lie(self.co_a, self.chantier_a)
        budget_a = make_budget(self.co_a, projet_a)

        avenant = self._avenant('AVC-CHT1-0002')
        api = auth(self.user_a)
        resp = api.post(f'{BASE}{avenant.id}/approuver/', {}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['budget_projet_id'], budget_a.id)

    def test_ligne_plantee_ne_masque_pas_la_ligne_legitime(self):
        # Les DEUX lignes existent : celle de B ne doit ni gagner, ni empêcher
        # la résolution du budget légitime de A.
        make_projet_lie(self.co_b, self.chantier_a)
        projet_a = make_projet_lie(self.co_a, self.chantier_a)
        budget_a = make_budget(self.co_a, projet_a)

        avenant = self._avenant('AVC-CHT1-0003')
        api = auth(self.user_a)
        resp = api.post(f'{BASE}{avenant.id}/approuver/', {}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['budget_projet_id'], budget_a.id)
