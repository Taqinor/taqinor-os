"""Tests NTWFL30 — alerte de charge d'approbateur (surcharge).

Acceptance criteria couverte : un approbateur avec PLUS de 20 items en attente
est signalé dans le rapport admin. Le rapport SUGGÈRE une redistribution ou une
délégation temporaire — il ne redistribue ni ne délègue jamais lui-même.
"""
from django.test import TestCase

from authentication.models import Company, CustomUser
from testkit.base import TenantAPITestCase

from core import workflow
from core.models import (
    WorkflowDefinition, WorkflowInstance, WorkflowStepDefinition,
    WorkflowStepInstance,
)
from core.selectors import (
    SEUIL_SURCHARGE_APPROBATEUR, charge_approbateur,
    rapport_charge_approbateurs,
)

URL = '/api/django/core/workflows/charge-approbateurs/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _definition_une_etape(company, code):
    wf = WorkflowDefinition.objects.create(
        company=company, code=code, nom=f'Processus {code}')
    WorkflowStepDefinition.objects.create(
        definition=wf, ordre=1, nom='Validation', role_requis='Responsable')
    return wf


def _charger(wf, company, assignee, nombre):
    """Crée ``nombre`` étapes EN ATTENTE assignées à ``assignee``."""
    pks = []
    for _ in range(nombre):
        instance = workflow.demarrer_workflow(wf, company, company)
        step = workflow.etape_courante_de(instance)
        step.assignee = assignee
        step.save(update_fields=['assignee'])
        pks.append(step.pk)
    return pks


class ChargeApprobateurTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntwfl30', 'NTWFL30')
        cls.autre_company = make_company('ntwfl30-autre', 'NTWFL30 Autre')
        cls.surcharge = CustomUser.objects.create_user(
            username='ntwfl30-surcharge', password='mdp-68402',
            company=cls.company)
        cls.tranquille = CustomUser.objects.create_user(
            username='ntwfl30-tranquille', password='mdp-68403',
            company=cls.company)
        cls.wf = _definition_une_etape(cls.company, 'ntwfl30-wf')
        # Strictement AU-DELÀ du seuil pour l'un, bien en dessous pour l'autre.
        cls.nb_surcharge = SEUIL_SURCHARGE_APPROBATEUR + 1
        cls.nb_tranquille = 3
        _charger(cls.wf, cls.company, cls.surcharge, cls.nb_surcharge)
        _charger(cls.wf, cls.company, cls.tranquille, cls.nb_tranquille)

    def test_charge_par_utilisateur(self):
        self.assertEqual(
            charge_approbateur(self.company, self.surcharge),
            self.nb_surcharge)
        self.assertEqual(
            charge_approbateur(self.company, self.tranquille),
            self.nb_tranquille)

    def test_approbateur_au_dela_du_seuil_est_signale(self):
        rapport = rapport_charge_approbateurs(self.company)
        self.assertEqual(rapport['seuil'], SEUIL_SURCHARGE_APPROBATEUR)
        par_user = {
            ligne['utilisateur_id']: ligne
            for ligne in rapport['approbateurs']
        }
        signale = par_user[self.surcharge.pk]
        self.assertTrue(signale['surcharge'])
        self.assertEqual(signale['nb_en_attente'], self.nb_surcharge)
        self.assertIn('délégation temporaire', signale['suggestion'])

        ok = par_user[self.tranquille.pk]
        self.assertFalse(ok['surcharge'])
        self.assertEqual(ok['suggestion'], '')

    def test_tri_par_charge_decroissante(self):
        rapport = rapport_charge_approbateurs(self.company)
        charges = [ligne['nb_en_attente']
                   for ligne in rapport['approbateurs']]
        self.assertEqual(charges, sorted(charges, reverse=True))

    def test_seuil_personnalise(self):
        rapport = rapport_charge_approbateurs(
            self.company, seuil=self.nb_tranquille - 1)
        par_user = {ligne['utilisateur_id']: ligne
                    for ligne in rapport['approbateurs']}
        self.assertTrue(par_user[self.tranquille.pk]['surcharge'])
        # Le seuil est STRICT : une charge ÉGALE au seuil n'alerte pas.
        egal = rapport_charge_approbateurs(
            self.company, seuil=self.nb_tranquille)
        par_user_egal = {ligne['utilisateur_id']: ligne
                         for ligne in egal['approbateurs']}
        self.assertFalse(par_user_egal[self.tranquille.pk]['surcharge'])

    def test_etape_decidee_ne_compte_plus(self):
        avant = charge_approbateur(self.company, self.tranquille)
        step = WorkflowStepInstance.objects.filter(
            company=self.company, assignee=self.tranquille,
            statut=WorkflowStepInstance.STATUT_EN_ATTENTE).first()
        workflow.approuver_etape(step.instance, user=self.tranquille)
        self.assertEqual(
            charge_approbateur(self.company, self.tranquille), avant - 1)

    def test_processus_annule_ne_compte_plus(self):
        avant = charge_approbateur(self.company, self.tranquille)
        step = WorkflowStepInstance.objects.filter(
            company=self.company, assignee=self.tranquille,
            statut=WorkflowStepInstance.STATUT_EN_ATTENTE).first()
        WorkflowInstance.objects.filter(pk=step.instance_id).update(
            statut=WorkflowInstance.STATUT_ANNULE)
        self.assertEqual(
            charge_approbateur(self.company, self.tranquille), avant - 1)

    def test_isolation_tenant(self):
        wf_autre = _definition_une_etape(
            self.autre_company, 'ntwfl30-autre-wf')
        _charger(wf_autre, self.autre_company, self.surcharge, 2)
        # La charge vue depuis ``self.company`` ignore l'autre société.
        self.assertEqual(
            charge_approbateur(self.company, self.surcharge),
            self.nb_surcharge)
        ids = {ligne['utilisateur_id']
               for ligne in rapport_charge_approbateurs(
                   self.autre_company)['approbateurs']}
        self.assertEqual(ids, {self.surcharge.pk})

    def test_sans_societe_rapport_vide(self):
        self.assertEqual(charge_approbateur(None, self.surcharge), 0)
        self.assertEqual(
            rapport_charge_approbateurs(None)['approbateurs'], [])

    def test_periode_hors_mois_ne_compte_rien(self):
        self.assertEqual(
            charge_approbateur(self.company, self.surcharge,
                               periode='1999-01'),
            0)


class ChargeApprobateurApiTests(TenantAPITestCase):
    def test_admin_lit_le_rapport(self):
        wf = _definition_une_etape(self.company, 'api-charge')
        approbateur = CustomUser.objects.create_user(
            username='api-ntwfl30-appro', password='mdp-68404',
            company=self.company)
        attendu = SEUIL_SURCHARGE_APPROBATEUR + 2
        _charger(wf, self.company, approbateur, attendu)

        r = self.client_as(role=CustomUser.ROLE_ADMIN).get(URL)
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertEqual(body['seuil'], SEUIL_SURCHARGE_APPROBATEUR)
        ligne = next(el for el in body['approbateurs']
                     if el['utilisateur_id'] == approbateur.pk)
        self.assertEqual(ligne['nb_en_attente'], attendu)
        self.assertTrue(ligne['surcharge'])

    def test_seuil_query_param_respecte(self):
        wf = _definition_une_etape(self.company, 'api-charge-seuil')
        approbateur = CustomUser.objects.create_user(
            username='api-ntwfl30-seuil', password='mdp-68405',
            company=self.company)
        _charger(wf, self.company, approbateur, 2)

        r = self.client_as(role=CustomUser.ROLE_ADMIN).get(URL, {'seuil': 1})
        self.assertEqual(r.status_code, 200, r.content)
        ligne = next(el for el in r.json()['approbateurs']
                     if el['utilisateur_id'] == approbateur.pk)
        self.assertTrue(ligne['surcharge'])

    def test_seuil_invalide_refuse(self):
        client = self.client_as(role=CustomUser.ROLE_ADMIN)
        self.assertEqual(client.get(URL, {'seuil': 'beaucoup'}).status_code,
                         400)
        self.assertEqual(client.get(URL, {'seuil': '-1'}).status_code, 400)

    def test_palier_limite_refuse(self):
        r = self.client_as(role=CustomUser.ROLE_NORMAL).get(URL)
        self.assertEqual(r.status_code, 403, r.content)
