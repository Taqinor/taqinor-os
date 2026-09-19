"""CAL11 — les trois portes de création, et leur idempotence.

Ce qui est prouvé ici :

* deux appels successifs sur le MÊME devis rendent le MÊME calepinage (parité
  CRM : le geste « Concevoir la toiture » ne fabrique pas un doublon) ;
* la création depuis un devis REPREND sa conception (``roof_layout`` /
  ``layout_hash``) et son rattachement (client, lead) ;
* les portes lead et client créent un calepinage SANS devis — objet de
  première classe ;
* un devis / lead / client d'une AUTRE société lève une erreur métier et NE
  CRÉE RIEN ; le message nomme le champ fautif, en français ;
* aucun statut de devis n'est jamais écrit (règle #4) ;
* la société et l'auteur sont posés côté serveur.

Run :
    python manage.py test apps.calepinage.tests.test_services_creation -v2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.creation import (
    CreationRefusee,
    creer_pour_client,
    creer_pour_lead,
    obtenir_ou_creer_pour_devis,
)
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()

LAYOUT = {'zones': [{'id': 'z1'}], 'result': {'panels': 12}}
EMPREINTE = 'b' * 64


class BaseCreation(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Création Co',
                                              slug='creation-co')
        self.autre = Company.objects.create(nom='Autre Co',
                                            slug='autre-co-11')
        self.user = User.objects.create_user(username='cal_auteur',
                                             password='x',
                                             company=self.company)
        self.client_a = Client.objects.create(company=self.company,
                                              nom='Bâtiment Atlas')
        self.client_b = Client.objects.create(company=self.autre,
                                              nom='Bâtiment Rif')
        self.lead_a = Lead.objects.create(company=self.company,
                                          nom='Toiture Anfa')
        self.lead_b = Lead.objects.create(company=self.autre,
                                          nom='Toiture Rif')
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_a, lead=self.lead_a,
            reference='DEV-202609-0001', roof_layout=LAYOUT,
            layout_hash=EMPREINTE)
        self.devis_etranger = Devis.objects.create(
            company=self.autre, client=self.client_b,
            reference='DEV-202609-0002')


class PorteDevisTest(BaseCreation):
    def test_idempotence(self):
        premier, cree = obtenir_ou_creer_pour_devis(self.devis.pk,
                                                    self.company,
                                                    user=self.user)
        self.assertTrue(cree)
        second, cree_2 = obtenir_ou_creer_pour_devis(self.devis.pk,
                                                     self.company)
        self.assertFalse(cree_2)
        self.assertEqual(premier.pk, second.pk)
        self.assertEqual(Calepinage.objects.count(), 1)

    def test_reprend_la_conception_du_devis(self):
        calepinage, _ = obtenir_ou_creer_pour_devis(self.devis.pk,
                                                    self.company)
        self.assertEqual(calepinage.roof_layout, LAYOUT)
        self.assertEqual(calepinage.layout_hash, EMPREINTE)

    def test_reprend_le_rattachement_du_devis(self):
        calepinage, _ = obtenir_ou_creer_pour_devis(self.devis.pk,
                                                    self.company)
        self.assertEqual(calepinage.client_id, self.client_a.pk)
        self.assertEqual(calepinage.lead_id, self.lead_a.pk)
        self.assertEqual(calepinage.devis_id, self.devis.pk)

    def test_societe_et_auteur_poses_cote_serveur(self):
        calepinage, _ = obtenir_ou_creer_pour_devis(self.devis.pk,
                                                    self.company,
                                                    user=self.user)
        self.assertEqual(calepinage.company_id, self.company.pk)
        self.assertEqual(calepinage.cree_par_id, self.user.pk)

    def test_aucun_statut_de_devis_ecrit(self):
        avant = Devis.objects.get(pk=self.devis.pk).statut
        obtenir_ou_creer_pour_devis(self.devis.pk, self.company)
        self.assertEqual(Devis.objects.get(pk=self.devis.pk).statut, avant)

    def test_devis_d_une_autre_societe_refuse_et_ne_cree_rien(self):
        with self.assertRaises(CreationRefusee) as capture:
            obtenir_ou_creer_pour_devis(self.devis_etranger.pk, self.company)
        self.assertEqual(capture.exception.champ, 'devis')
        self.assertEqual(Calepinage.objects.count(), 0)

    def test_devis_absent_refuse(self):
        with self.assertRaises(CreationRefusee) as capture:
            obtenir_ou_creer_pour_devis(None, self.company)
        self.assertEqual(capture.exception.champ, 'devis')


class PorteLeadTest(BaseCreation):
    def test_cree_sans_devis(self):
        calepinage = creer_pour_lead(self.lead_a.pk, self.company,
                                     user=self.user)
        self.assertEqual(calepinage.lead_id, self.lead_a.pk)
        self.assertIsNone(calepinage.devis_id)
        self.assertEqual(calepinage.company_id, self.company.pk)

    def test_lead_d_une_autre_societe_refuse_et_ne_cree_rien(self):
        with self.assertRaises(CreationRefusee) as capture:
            creer_pour_lead(self.lead_b.pk, self.company)
        self.assertEqual(capture.exception.champ, 'lead')
        self.assertEqual(Calepinage.objects.count(), 0)

    def test_lead_absent_refuse_en_nommant_le_champ(self):
        with self.assertRaises(CreationRefusee) as capture:
            creer_pour_lead(None, self.company)
        self.assertEqual(capture.exception.champ, 'lead')

    def test_titre_derive_du_lead(self):
        calepinage = creer_pour_lead(self.lead_a.pk, self.company)
        self.assertIn('Toiture Anfa', calepinage.titre)


class PorteClientTest(BaseCreation):
    def test_cree_sans_devis(self):
        calepinage = creer_pour_client(self.client_a.pk, self.company)
        self.assertEqual(calepinage.client_id, self.client_a.pk)
        self.assertIsNone(calepinage.devis_id)
        self.assertIsNone(calepinage.lead_id)

    def test_client_d_une_autre_societe_refuse_et_ne_cree_rien(self):
        with self.assertRaises(CreationRefusee) as capture:
            creer_pour_client(self.client_b.pk, self.company)
        self.assertEqual(capture.exception.champ, 'client')
        self.assertEqual(Calepinage.objects.count(), 0)

    def test_client_absent_refuse(self):
        with self.assertRaises(CreationRefusee) as capture:
            creer_pour_client(None, self.company)
        self.assertEqual(capture.exception.champ, 'client')


class SocieteObligatoireTest(BaseCreation):
    def test_sans_societe_chaque_porte_refuse(self):
        for appel in (
            lambda: obtenir_ou_creer_pour_devis(self.devis.pk, None),
            lambda: creer_pour_lead(self.lead_a.pk, None),
            lambda: creer_pour_client(self.client_a.pk, None),
        ):
            with self.assertRaises(CreationRefusee) as capture:
                appel()
            self.assertEqual(capture.exception.champ, 'company')
        self.assertEqual(Calepinage.objects.count(), 0)
