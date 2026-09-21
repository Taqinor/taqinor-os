"""NTGRC13 — registre des risques d'entreprise (ERM) + matrice 5×5.

Garanties : les DEUX criticités se recalculent à l'enregistrement, la matrice
renvoie le comptage par case (25 cases toujours présentes), la référence RQ
est race-safe et tout reste scopé société.
"""
from django.test import TestCase

from apps.grc.models import RisqueEntreprise
from apps.grc.selectors import matrice_risques
from apps.grc.services import creer_risque
from authentication.models import Company
from testkit.base import TenantAPITestCase


class CriticitesCalculeesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC13 SA', slug='ntgrc13')

    def test_les_deux_criticites_sont_calculees_a_lenregistrement(self):
        risque = creer_risque(
            self.company, titre='Rupture fournisseur',
            probabilite=4, impact=5,
            probabilite_residuelle=2, impact_residuel=3)
        self.assertEqual(risque.criticite_inherente, 20)
        self.assertEqual(risque.criticite_residuelle, 6)

    def test_la_criticite_suit_une_recotation(self):
        risque = creer_risque(
            self.company, titre='X', probabilite=1, impact=1)
        risque.probabilite = 5
        risque.impact = 4
        risque.save()
        risque.refresh_from_db()
        self.assertEqual(risque.criticite_inherente, 20)

    def test_la_criticite_est_recalculee_meme_avec_update_fields(self):
        """Un save ciblé ne doit pas laisser une criticité périmée en base."""
        risque = creer_risque(
            self.company, titre='X', probabilite=1, impact=1)
        risque.impact = 5
        risque.save(update_fields=['impact'])
        risque.refresh_from_db()
        self.assertEqual(risque.criticite_inherente, 5)

    def test_une_cotation_hors_echelle_est_bornee_jamais_une_exception(self):
        risque = creer_risque(
            self.company, titre='X', probabilite=99, impact=0)
        self.assertEqual(risque.probabilite, 5)
        self.assertEqual(risque.impact, 1)
        self.assertEqual(risque.criticite_inherente, 5)

    def test_la_reference_rq_est_race_safe(self):
        r1 = creer_risque(self.company, titre='A')
        r2 = creer_risque(self.company, titre='B')
        self.assertTrue(r1.reference.startswith('RQ-'))
        self.assertNotEqual(r1.reference, r2.reference)


class MatriceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC13 M', slug='ntgrc13-m')
        cls.autre = Company.objects.create(nom='NTGRC13 B', slug='ntgrc13-b')

    def test_les_25_cases_sont_toujours_presentes(self):
        matrice = matrice_risques(self.company)
        self.assertEqual(len(matrice['cases']), 25)
        self.assertEqual(matrice['total'], 0)

    def test_le_comptage_tombe_dans_la_bonne_case(self):
        creer_risque(self.company, titre='A', probabilite=3, impact=4)
        creer_risque(self.company, titre='B', probabilite=3, impact=4)
        creer_risque(self.company, titre='C', probabilite=1, impact=1)
        matrice = matrice_risques(self.company)
        par_case = {(c['probabilite'], c['impact']): c['nombre']
                    for c in matrice['cases']}
        self.assertEqual(par_case[(3, 4)], 2)
        self.assertEqual(par_case[(1, 1)], 1)
        self.assertEqual(matrice['total'], 3)

    def test_un_risque_clos_sort_de_la_matrice(self):
        risque = creer_risque(
            self.company, titre='A', probabilite=3, impact=4)
        risque.statut = RisqueEntreprise.STATUT_CLOS
        risque.save()
        self.assertEqual(matrice_risques(self.company)['total'], 0)

    def test_la_matrice_residuelle_compte_lapres_traitement(self):
        creer_risque(self.company, titre='A', probabilite=5, impact=5,
                     probabilite_residuelle=1, impact_residuel=2)
        par_case = {(c['probabilite'], c['impact']): c['nombre']
                    for c in matrice_risques(self.company,
                                             residuelle=True)['cases']}
        self.assertEqual(par_case[(1, 2)], 1)
        self.assertEqual(par_case[(5, 5)], 0)

    def test_la_matrice_est_bornee_a_la_societe(self):
        creer_risque(self.autre, titre='A', probabilite=3, impact=3)
        self.assertEqual(matrice_risques(self.company)['total'], 0)


class EndpointRisquesTests(TenantAPITestCase):
    BASE = '/api/django/grc/risques-entreprise/'

    def _admin(self):
        return self.client_as(role='admin')

    def test_creation_impose_societe_et_reference(self):
        r = self._admin().post(
            self.BASE,
            {'titre': 'Cyberattaque', 'categorie': 'si',
             'probabilite': 3, 'impact': 5},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['criticite_inherente'], 15)
        risque = RisqueEntreprise.objects.get(pk=r.data['id'])
        self.assertEqual(risque.company, self.company)
        self.assertTrue(risque.reference.startswith('RQ-'))

    def test_une_cotation_hors_echelle_nomme_le_champ_fautif(self):
        r = self._admin().post(
            self.BASE, {'titre': 'X', 'probabilite': 9}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('probabilite', r.data)

    def test_endpoint_matrice(self):
        creer_risque(self.company, titre='A', probabilite=2, impact=2)
        r = self._admin().get(f'{self.BASE}matrice/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.data['cases']), 25)
        self.assertEqual(r.data['total'], 1)

    def test_liste_scopee_societe(self):
        creer_risque(self.other_company, titre='Etranger')
        r = self._admin().get(self.BASE)
        lignes = r.data.get('results', r.data)
        self.assertEqual(lignes, [])
