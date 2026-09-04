"""AUD310 — DGD ``situations_incluses`` : agrégation financière cross-société
non filtrée par company.

Avant ce fix : ``DecompteGeneral.situations_incluses`` (JSONField écrivable,
IDs de ``gestion_projet.SituationTravaux``) n'avait aucun
``validate_situations_incluses`` — un utilisateur société A pouvait créer/
PATCH un DGD référençant l'ID (devinable) d'une ``SituationTravaux`` de la
société B, et ``selectors.calculer_dgd`` agrégeait le montant de B dans les
totaux de A SANS filtre société, imprimés sur le PDF DGD (document
contractuel de clôture de chantier).

Couvre :
* écriture (POST) refusée (400) quand ``situations_incluses`` référence une
  situation d'une autre société ;
* l'agrégat lui-même (``selectors.calculer_dgd``) ne somme JAMAIS une ligne
  d'une autre société, même sur un DGD déjà corrompu (écrit hors serializer,
  défense en profondeur) ;
* le cas normal (situations de SA PROPRE société) continue de fonctionner.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework import status

from apps.btp_chantier import selectors
from apps.btp_chantier.models import DecompteGeneral

from .helpers import (
    auth, make_chantier, make_company, make_ligne_situation,
    make_projet_lie, make_situation, make_user,
)

BASE = '/api/django/btp-chantier/decomptes-generaux/'


class DgdSituationsInclusesCrossCompanyTests(TestCase):
    def setUp(self):
        self.co_a = make_company()
        self.co_b = make_company()
        self.user_a = make_user(self.co_a)
        self.chantier_a = make_chantier(self.co_a)
        self.projet_a = make_projet_lie(self.co_a, self.chantier_a)
        self.situation_a = make_situation(self.co_a, self.projet_a, numero=1)
        make_ligne_situation(
            self.co_a, self.situation_a, montant_periode=Decimal('20000.00'))

        self.chantier_b = make_chantier(self.co_b)
        self.projet_b = make_projet_lie(self.co_b, self.chantier_b)
        self.situation_b = make_situation(self.co_b, self.projet_b, numero=1)
        make_ligne_situation(
            self.co_b, self.situation_b, montant_periode=Decimal('999999.00'))

    def test_create_dgd_referencing_other_company_situation_rejected(self):
        api = auth(self.user_a)
        resp = api.post(BASE, {
            'chantier': self.chantier_a.id,
            'montant_marche_initial_ht': '100000.00',
            'situations_incluses': [self.situation_b.id],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, resp.data)
        self.assertFalse(
            DecompteGeneral.objects.filter(chantier=self.chantier_a).exists())

    def test_patch_dgd_adding_other_company_situation_rejected(self):
        dgd = DecompteGeneral.objects.create(
            company=self.co_a, chantier=self.chantier_a,
            reference='DGD-AUD310-0001', montant_marche_initial_ht=0,
            situations_incluses=[self.situation_a.id])
        api = auth(self.user_a)
        resp = api.patch(f'{BASE}{dgd.id}/', {
            'situations_incluses': [self.situation_a.id, self.situation_b.id],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, resp.data)
        dgd.refresh_from_db()
        self.assertEqual(dgd.situations_incluses, [self.situation_a.id])

    def test_own_company_situations_still_work(self):
        api = auth(self.user_a)
        resp = api.post(BASE, {
            'chantier': self.chantier_a.id,
            'montant_marche_initial_ht': '100000.00',
            'situations_incluses': [self.situation_a.id],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(
            Decimal(resp.data['total_situations_facturees_ht']),
            Decimal('20000.00'))

    def test_calculer_dgd_never_sums_other_company_even_if_already_corrupted(self):
        # Défense en profondeur : un DGD déjà corrompu (écrit hors serializer
        # — migration de données, écriture directe...) ne doit JAMAIS voir
        # son agrégat inclure une ligne d'une autre société.
        dgd = DecompteGeneral.objects.create(
            company=self.co_a, chantier=self.chantier_a,
            reference='DGD-AUD310-0002', montant_marche_initial_ht=0,
            situations_incluses=[self.situation_a.id, self.situation_b.id])
        totaux = selectors.calculer_dgd(dgd)
        self.assertEqual(
            totaux['total_situations_facturees_ht'], Decimal('20000.00'))
        self.assertNotEqual(
            totaux['total_situations_facturees_ht'], Decimal('1019999.00'))

    def test_selector_flags_out_of_company_ids(self):
        hors_societe = selectors.situations_incluses_hors_societe(
            [self.situation_a.id, self.situation_b.id], self.co_a)
        self.assertEqual(hors_societe, [self.situation_b.id])
