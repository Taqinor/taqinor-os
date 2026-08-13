"""NTCPQ12 — Bibliothèque de clauses réutilisables : CRUD REST, prévisualisation
de la condition en langage clair et test à blanc contre un devis existant.

Couvre :
* un admin crée / désactive une clause sans toucher au code (company serveur) ;
* la condition est prévisualisée en langage clair ;
* un devis existant « testé » indique si la clause s'appliquerait (sans rien
  écrire — le snapshot ne se fige qu'à l'envoi, NTCPQ11) ;
* isolation société + écriture refusée à un rôle normal.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.cpq.models import ClauseCGV
from apps.cpq.selectors import condition_en_clair
from apps.ventes.models import LigneDevis
from authentication.models import CustomUser
from testkit.factories import (
    CompanyFactory, DevisFactory, ProduitFactory, UserFactory,
)

CLAUSES = '/api/django/cpq/clauses-cgv/'

CONDITION = {
    'op': 'and',
    'conditions': [
        {'field': 'montant', 'operator': 'gt', 'value': 500000},
    ],
}


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestClausesCGVCrud(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.admin = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.normal = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_NORMAL)

    def _devis(self, mode, prix):
        produit = ProduitFactory(company=self.company)
        devis = DevisFactory(company=self.company, mode_installation=mode)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=produit.nom,
            quantite=Decimal('1'), prix_unitaire=Decimal(prix))
        return devis

    def test_creer_clause_company_posee_serveur(self):
        resp = auth(self.admin).post(CLAUSES, {
            'nom': 'Garantie étendue',
            'corps_texte': 'Garantie étendue 5 ans.',
            'type_deal': 'industriel',
            'applicable_si': CONDITION,
            'company': 999999,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        clause = ClauseCGV.objects.get(id=resp.data['id'])
        self.assertEqual(clause.company_id, self.company.id)

    def test_desactiver_clause_sans_toucher_au_code(self):
        clause = ClauseCGV.objects.create(
            company=self.company, nom='Clause X', actif=True)
        resp = auth(self.admin).patch(
            f'{CLAUSES}{clause.id}/', {'actif': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        clause.refresh_from_db()
        self.assertFalse(clause.actif)

    def test_condition_lisible_en_langage_clair(self):
        clause = ClauseCGV.objects.create(
            company=self.company, nom='Garantie étendue',
            type_deal='industriel', applicable_si=CONDITION)
        resp = auth(self.normal).get(f'{CLAUSES}{clause.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['condition_lisible'],
                         'type_deal=industriel ET montant>500000')

    def test_condition_lisible_sans_condition(self):
        self.assertEqual(condition_en_clair({}), 'toujours')
        self.assertEqual(
            condition_en_clair({'op': 'not', 'conditions': [
                {'field': 'a', 'operator': 'eq', 'value': 1}]}),
            'NON (a=1)')

    def test_arbre_invalide_refuse(self):
        resp = auth(self.admin).post(CLAUSES, {
            'nom': 'Bancale',
            'applicable_si': {'op': 'xor', 'conditions': []},
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_tester_a_blanc_sur_un_devis_existant(self):
        clause = ClauseCGV.objects.create(
            company=self.company, nom='Garantie étendue',
            type_deal='industriel', applicable_si=CONDITION)
        gros = self._devis('industriel', '600000.00')
        petit = self._devis('residentiel', '30000.00')
        api = auth(self.normal)
        resp = api.get(f'{CLAUSES}{clause.id}/tester/?devis_id={gros.id}')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['applicable'])
        resp = api.get(f'{CLAUSES}{clause.id}/tester/?devis_id={petit.id}')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['applicable'])
        # Test à blanc : rien n'est figé sur le devis.
        gros.refresh_from_db()
        self.assertIsNone(gros.clauses_appliquees)

    def test_tester_devis_dune_autre_societe_404(self):
        clause = ClauseCGV.objects.create(
            company=self.company, nom='Clause X')
        autre = DevisFactory(company=CompanyFactory())
        resp = auth(self.admin).get(
            f'{CLAUSES}{clause.id}/tester/?devis_id={autre.id}')
        self.assertEqual(resp.status_code, 404)

    def test_isolation_societe_en_lecture(self):
        ClauseCGV.objects.create(company=CompanyFactory(), nom='Ailleurs')
        resp = auth(self.normal).get(CLAUSES)
        self.assertEqual(resp.status_code, 200, resp.data)
        noms = [c['nom'] for c in (resp.data.get('results') or resp.data)]
        self.assertNotIn('Ailleurs', noms)

    def test_ecriture_refusee_a_un_role_normal(self):
        resp = auth(self.normal).post(
            CLAUSES, {'nom': 'Interdite'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)
