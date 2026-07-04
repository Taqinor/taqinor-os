"""Tests XACC34 — Remise à l'escompte & endossement des effets.

Couvre : un escompte poste le net + agios (écriture équilibrée, verrou
respecté), l'échéance apure 5520, l'impayé post-escompte ré-ouvre la
créance, transitions illégales -> 400.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import CompteTresorerie, Effet, LigneEcriture

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class EscompteServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc34-svc', 'XACC34 Svc')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.user = make_user(self.co, 'xacc34-svc-user')
        self.banque = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='BMCE', compte_comptable=services.get_compte(self.co, '5141'))
        self.effet = services.enregistrer_effet(
            self.co, sens=Effet.Sens.RECEVOIR, montant=Decimal('10000'),
            date_emission=date(2026, 5, 1), date_echeance=date(2026, 8, 1),
            tireur='Client X', user=self.user)

    def test_escompte_poste_net_et_agios_equilibre(self):
        effet = services.escompter_effet(
            self.effet, compte_tresorerie=self.banque,
            agios=Decimal('150'), interets=Decimal('50'),
            date_escompte=date(2026, 6, 1), user=self.user)
        self.assertEqual(effet.statut, Effet.Statut.ESCOMPTE)
        self.assertIsNotNone(effet.ecriture_escompte_id)
        lignes = LigneEcriture.objects.filter(
            ecriture_id=effet.ecriture_escompte_id)
        debit = sum((x.debit for x in lignes), Decimal('0'))
        credit = sum((x.credit for x in lignes), Decimal('0'))
        self.assertEqual(debit, credit)
        self.assertEqual(credit, Decimal('10000.00'))  # crédit 5520 = brut.
        numeros = {x.compte.numero for x in lignes}
        self.assertIn('5520', numeros)
        self.assertIn('5141', numeros)  # net crédité en banque (débit ici).

    def test_apurement_solde_5520(self):
        services.escompter_effet(
            self.effet, compte_tresorerie=self.banque,
            agios=Decimal('100'), date_escompte=date(2026, 6, 1),
            user=self.user)
        effet = services.apurer_escompte_effet(
            self.effet, date_apurement=date(2026, 8, 1), user=self.user)
        self.assertEqual(effet.statut, Effet.Statut.ENCAISSE)
        lignes = LigneEcriture.objects.filter(
            ecriture_id=effet.ecriture_apurement_escompte_id)
        numeros = {x.compte.numero for x in lignes}
        self.assertIn('5520', numeros)
        self.assertIn('3425', numeros)

    def test_impaye_post_escompte_rouvre_creance(self):
        services.escompter_effet(
            self.effet, compte_tresorerie=self.banque,
            agios=Decimal('100'), date_escompte=date(2026, 6, 1),
            user=self.user)
        effet = services.rejeter_effet(
            self.effet, date_rejet=date(2026, 8, 1), frais_rejet=Decimal('30'),
            user=self.user)
        self.assertEqual(effet.statut, Effet.Statut.IMPAYE)
        self.assertEqual(effet.frais_rejet, Decimal('30'))

    def test_transition_illegale_effet_deja_encaisse_refusee(self):
        services.encaisser_effet(self.effet, user=self.user)
        with self.assertRaises(Exception):
            services.escompter_effet(
                self.effet, compte_tresorerie=self.banque, user=self.user)

    def test_agios_superieurs_au_montant_refuses(self):
        with self.assertRaises(Exception):
            services.escompter_effet(
                self.effet, compte_tresorerie=self.banque,
                agios=Decimal('20000'), user=self.user)


class EndossementServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc34-endo', 'XACC34 Endo')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.user = make_user(self.co, 'xacc34-endo-user')
        self.effet = services.enregistrer_effet(
            self.co, sens=Effet.Sens.RECEVOIR, montant=Decimal('5000'),
            date_emission=date(2026, 5, 1), date_echeance=date(2026, 8, 1),
            user=self.user)

    def test_endosser_change_statut_et_beneficiaire(self):
        effet = services.endosser_effet(
            self.effet, beneficiaire='Fournisseur Y',
            date_endossement=date(2026, 6, 1), user=self.user)
        self.assertEqual(effet.statut, Effet.Statut.ENDOSSE)
        self.assertEqual(effet.beneficiaire_endossement, 'Fournisseur Y')

    def test_endosser_sans_beneficiaire_refuse(self):
        with self.assertRaises(Exception):
            services.endosser_effet(self.effet, beneficiaire='', user=self.user)

    def test_endosser_effet_a_payer_refuse(self):
        effet_payer = services.enregistrer_effet(
            self.co, sens=Effet.Sens.PAYER, montant=Decimal('2000'),
            date_emission=date(2026, 5, 1), date_echeance=date(2026, 8, 1),
            user=self.user)
        with self.assertRaises(Exception):
            services.endosser_effet(
                effet_payer, beneficiaire='X', user=self.user)


class EscompteApiTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc34-api', 'XACC34 Api')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.user = make_user(self.co, 'xacc34-api-user')
        self.banque = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='BMCE 2', compte_comptable=services.get_compte(self.co, '5141'))
        self.effet = services.enregistrer_effet(
            self.co, sens=Effet.Sens.RECEVOIR, montant=Decimal('8000'),
            date_emission=date(2026, 5, 1), date_echeance=date(2026, 8, 1),
            user=self.user)

    def test_escompter_endpoint(self):
        resp = auth(self.user).post(
            f'/api/django/compta/effets/{self.effet.id}/escompter/',
            {'compte_tresorerie': self.banque.id, 'agios': '100'},
            format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['statut'], Effet.Statut.ESCOMPTE)

    def test_endosser_endpoint(self):
        resp = auth(self.user).post(
            f'/api/django/compta/effets/{self.effet.id}/endosser/',
            {'beneficiaire': 'Tiers Z'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['beneficiaire_endossement'], 'Tiers Z')
