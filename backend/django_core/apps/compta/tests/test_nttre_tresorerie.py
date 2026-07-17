"""Tests NTTRE5/6/7/8/27 — trésorerie avancée (compta-extension).

Couvre :
* NTTRE5 — workflow à 4 yeux : sans le flag, comportement inchangé ; avec le
  flag, poster refuse tant que deux approbateurs DISTINCTS (≠ créateur) n'ont pas
  validé.
* NTTRE6 — pouvoirs bancaires : un run dépassant le plafond seul du premier
  approbateur exige une seconde signature même flag désactivé.
* NTTRE7 — protêt : constaté seulement sur un effet impayé, trace frais + date.
* NTTRE8 — seuils : un compte passé sous son seuil est listé par le sélecteur ;
  la notification est dé-doublonnée par jour.
* NTTRE27 — réglages trésorerie singleton (défauts, GET/PATCH).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import (
    CompteTresorerie, Effet, ParametresTresorerie, PaymentRun,
    PouvoirBancaire, VirementInterne)

User = get_user_model()


def _company(slug):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return co


def _user(co, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=co, role_legacy=role)


class _Base(TestCase):
    def setUp(self):
        self.co = _company('nttre-tre')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.banque = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='BMCE', compte_comptable=services.get_compte(self.co, '5141'))
        self.createur = _user(self.co, 'nttre-createur')
        self.appro1 = _user(self.co, 'nttre-appro1')
        self.appro2 = _user(self.co, 'nttre-appro2')
        self.today = timezone.localdate()

    def _run(self, total=Decimal('1000')):
        return services.creer_payment_run(
            self.co, date_paiement=self.today, mode_paiement='virement',
            compte_tresorerie=self.banque, reference='RUN-1',
            lignes=[{'tiers_id': 1, 'montant': total, 'reference': 'F001',
                     'beneficiaire': 'Fournisseur A',
                     'rib': '011780000012345678901234'}],
            user=self.createur)


class DoubleValidationTests(_Base):
    def test_flag_off_comportement_inchange(self):
        run = self._run()
        # Flag désactivé (défaut) : poster réussit sans approbation (historique).
        ecr = services.poster_payment_run(run, user=self.createur)
        self.assertIsNotNone(ecr)
        run.refresh_from_db()
        self.assertEqual(run.statut, PaymentRun.Statut.POSTEE)

    def test_flag_on_bloque_sans_deux_approbateurs(self):
        params = services.get_parametres_tresorerie(self.co)
        params.double_validation_paiement_actif = True
        params.save()
        run = self._run()
        with self.assertRaises(ValidationError):
            services.poster_payment_run(run, user=self.createur)

    def test_createur_ne_peut_pas_approuver(self):
        run = self._run()
        with self.assertRaises(ValidationError):
            services.approuver_payment_run(run, self.createur)

    def test_second_approbateur_distinct_du_premier(self):
        run = self._run()
        services.approuver_payment_run(run, self.appro1)
        run.refresh_from_db()
        self.assertEqual(run.statut, PaymentRun.Statut.EN_ATTENTE_APPROBATION)
        with self.assertRaises(ValidationError):
            services.approuver_final_payment_run(run, self.appro1)

    def test_flag_on_deux_approbateurs_distincts_poste(self):
        params = services.get_parametres_tresorerie(self.co)
        params.double_validation_paiement_actif = True
        params.save()
        run = self._run()
        services.approuver_payment_run(run, self.appro1)
        services.approuver_final_payment_run(run, self.appro2)
        run.refresh_from_db()
        self.assertTrue(run.approbations_distinctes)
        ecr = services.poster_payment_run(run, user=self.appro2)
        self.assertIsNotNone(ecr)
        run.refresh_from_db()
        self.assertEqual(run.statut, PaymentRun.Statut.POSTEE)


class PouvoirBancaireTests(_Base):
    def test_plafond_depasse_exige_seconde_signature(self):
        # Flag société OFF, mais le premier approbateur n'a qu'un plafond 200k.
        PouvoirBancaire.objects.create(
            company=self.co, compte_tresorerie=self.banque,
            titulaire_nom='Titulaire A', utilisateur=self.appro1,
            plafond_signature_seul=Decimal('200000'),
            statut=PouvoirBancaire.Statut.ACTIF)
        run = self._run(total=Decimal('500000'))
        services.approuver_payment_run(run, self.appro1)
        run.refresh_from_db()
        self.assertTrue(services.double_validation_requise(run))
        with self.assertRaises(ValidationError):
            services.poster_payment_run(run, user=self.appro1)
        # Une seconde signature distincte lève le blocage.
        services.approuver_final_payment_run(run, self.appro2)
        self.assertIsNotNone(services.poster_payment_run(run, user=self.appro2))

    def test_endpoint_crud_et_revocation(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.createur)}')
        resp = api.post('/api/django/compta/pouvoirs-bancaires/', {
            'compte_tresorerie': self.banque.id, 'titulaire_nom': 'Signataire',
            'plafond_signature_seul': '100000'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        pid = resp.data['id']
        resp2 = api.post(
            f'/api/django/compta/pouvoirs-bancaires/{pid}/revoquer/')
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.data['statut'], PouvoirBancaire.Statut.REVOQUE)


class ProtetTests(_Base):
    def _effet_impaye(self):
        effet = Effet.objects.create(
            company=self.co, sens=Effet.Sens.RECEVOIR,
            type_effet=Effet.TypeEffet.CHEQUE, montant=Decimal('1000'),
            date_emission=self.today, date_echeance=self.today,
            statut=Effet.Statut.IMPAYE)
        return effet

    def test_protet_sur_effet_impaye(self):
        effet = self._effet_impaye()
        services.constater_protet(
            effet, frais_protet=Decimal('350'), user=self.createur)
        effet.refresh_from_db()
        self.assertEqual(effet.frais_protet, Decimal('350'))
        self.assertIsNotNone(effet.date_protet)
        # Le statut reste impayé (le protêt n'est qu'une trace).
        self.assertEqual(effet.statut, Effet.Statut.IMPAYE)

    def test_protet_refuse_sur_effet_non_impaye(self):
        effet = Effet.objects.create(
            company=self.co, sens=Effet.Sens.RECEVOIR,
            type_effet=Effet.TypeEffet.CHEQUE, montant=Decimal('1000'),
            date_emission=self.today, date_echeance=self.today,
            statut=Effet.Statut.PORTEFEUILLE)
        with self.assertRaises(ValidationError):
            services.constater_protet(effet, frais_protet=Decimal('100'))


class SeuilAlerteTests(_Base):
    def test_compte_sous_seuil_liste_apres_virement(self):
        # Un second compte destination avec un seuil ; source = banque.
        caisse = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.CAISSE,
            libelle='Caisse', solde_initial=Decimal('0'),
            compte_comptable=services.get_compte(self.co, '5161'))
        # Banque part avec solde initial 1000, seuil bas 800.
        self.banque.solde_initial = Decimal('1000')
        self.banque.seuil_alerte_bas = Decimal('800')
        self.banque.save()
        vir = VirementInterne.objects.create(
            company=self.co, compte_source=self.banque,
            compte_destination=caisse, montant=Decimal('500'),
            date_virement=self.today)
        services.poster_virement(vir, user=self.createur)
        sous_seuil = selectors.comptes_sous_seuil(self.co)
        ids = [c['id'] for c in sous_seuil]
        self.assertIn(self.banque.id, ids)

    def test_notification_dedupe_par_jour(self):
        self.banque.solde_initial = Decimal('100')
        self.banque.seuil_alerte_bas = Decimal('800')
        self.banque.save()
        first = services.notifier_comptes_sous_seuil(self.co, user=self.createur)
        self.assertIn(self.banque.id, first)
        # Deuxième appel le même jour : pas de doublon.
        second = services.notifier_comptes_sous_seuil(
            self.co, user=self.createur)
        self.assertEqual(second, [])


class ParametresTresorerieTests(_Base):
    def test_defauts_sans_regression(self):
        params = services.get_parametres_tresorerie(self.co)
        self.assertFalse(params.double_validation_paiement_actif)
        self.assertEqual(params.delai_alerte_rupture_jours, 14)
        self.assertEqual(
            params.format_export_virement_defaut,
            ParametresTresorerie.FormatExport.CSV)
        self.assertEqual(params.comptes_frais_bancaires, ['6147'])

    def test_endpoint_get_patch(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.createur)}')
        resp = api.get('/api/django/compta/parametres-tresorerie/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['double_validation_paiement_actif'])
        resp2 = api.patch('/api/django/compta/parametres-tresorerie/',
                          {'double_validation_paiement_actif': True},
                          format='json')
        self.assertEqual(resp2.status_code, 200)
        self.assertTrue(resp2.data['double_validation_paiement_actif'])
        params = services.get_parametres_tresorerie(self.co)
        self.assertTrue(params.double_validation_paiement_actif)
