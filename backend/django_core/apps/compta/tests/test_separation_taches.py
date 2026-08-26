"""Tests COMPTA40 — Séparation des tâches (saisie vs validation vs clôture).

Couvre : le service ``valider_ecriture`` (le saisisseur ne valide pas sa propre
écriture ; un tiers habilité le peut ; refus si déjà validée), l'endpoint
``valider`` (403 sans permission ``compta_valider``, 400 en cas de violation de
la séparation), la traçabilité (``valide_par``/``date_validation``), et le
verrou de clôture derrière ``compta_cloturer``. Messages en français.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    EcritureComptable, ExerciceComptable, Journal, PeriodeComptable)
from apps.roles.models import Role

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


def make_ecriture(company, jour, libelle, montant, *, created_by=None):
    journal = services._journal(company, Journal.Type.OPERATIONS_DIVERSES)
    lignes = [
        {'compte': services.get_compte(company, '5141'),
         'debit': Decimal(montant), 'credit': Decimal('0')},
        {'compte': services.get_compte(company, '7121'),
         'debit': Decimal('0'), 'credit': Decimal(montant)},
    ]
    return services.creer_ecriture(
        company, journal, jour, libelle, lignes, created_by=created_by)


class ValiderEcritureServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('compta40-co', 'COMPTA40 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.saisisseur = make_user(self.co, 'compta40-saisi')
        self.valideur = make_user(self.co, 'compta40-valid')

    def test_saisisseur_ne_valide_pas_sa_propre_ecriture(self):
        ec = make_ecriture(
            self.co, date(2026, 3, 1), 'Vente', '1000',
            created_by=self.saisisseur)
        with self.assertRaises(ValidationError) as ctx:
            services.valider_ecriture(ec, user=self.saisisseur)
        self.assertIn('Séparation des tâches', str(ctx.exception))
        ec.refresh_from_db()
        self.assertEqual(ec.statut, EcritureComptable.Statut.BROUILLON)
        self.assertIsNone(ec.valide_par_id)

    def test_un_tiers_valide(self):
        ec = make_ecriture(
            self.co, date(2026, 3, 1), 'Vente', '1000',
            created_by=self.saisisseur)
        services.valider_ecriture(ec, user=self.valideur)
        ec.refresh_from_db()
        self.assertEqual(ec.statut, EcritureComptable.Statut.VALIDEE)
        self.assertEqual(ec.valide_par_id, self.valideur.id)
        self.assertIsNotNone(ec.date_validation)

    def test_refuse_si_deja_validee(self):
        ec = make_ecriture(
            self.co, date(2026, 3, 1), 'Vente', '1000',
            created_by=self.saisisseur)
        services.valider_ecriture(ec, user=self.valideur)
        with self.assertRaises(ValidationError) as ctx:
            services.valider_ecriture(ec, user=self.valideur)
        self.assertIn('déjà validée', str(ctx.exception))

    def test_valideur_requis(self):
        ec = make_ecriture(
            self.co, date(2026, 3, 1), 'Vente', '1000',
            created_by=self.saisisseur)
        with self.assertRaises(ValidationError):
            services.valider_ecriture(ec, user=None)


class ValiderEndpointTests(TestCase):
    def setUp(self):
        self.co = make_company('compta40-ep', 'COMPTA40 EP')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        # Comptes légacy (role_legacy) → repli historique responsable/admin.
        self.saisisseur = make_user(self.co, 'compta40-ep-saisi')
        self.valideur = make_user(self.co, 'compta40-ep-valid')

    def test_endpoint_saisisseur_refuse_400(self):
        ec = make_ecriture(
            self.co, date(2026, 3, 1), 'Vente', '1000',
            created_by=self.saisisseur)
        resp = auth(self.saisisseur).post(
            f'/api/django/compta/ecritures/{ec.pk}/valider/')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Séparation des tâches', resp.data['detail'])

    def test_endpoint_tiers_valide_200(self):
        ec = make_ecriture(
            self.co, date(2026, 3, 1), 'Vente', '1000',
            created_by=self.saisisseur)
        resp = auth(self.valideur).post(
            f'/api/django/compta/ecritures/{ec.pk}/valider/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['statut'], EcritureComptable.Statut.VALIDEE)
        self.assertEqual(resp.data['valide_par'], self.valideur.id)

    def test_endpoint_403_sans_permission_compta_valider(self):
        # Rôle fin SANS compta_valider → 403 (jugé sur permissions granulaires).
        role = Role.objects.create(
            company=self.co, nom='Saisie seule',
            permissions=['compta_saisir'])
        borne = make_user(self.co, 'compta40-borne')
        borne.role = role
        borne.save()
        ec = make_ecriture(
            self.co, date(2026, 3, 1), 'Vente', '1000',
            created_by=self.saisisseur)
        resp = auth(borne).post(
            f'/api/django/compta/ecritures/{ec.pk}/valider/')
        self.assertEqual(resp.status_code, 403)


class ClotureGateTests(TestCase):
    def setUp(self):
        self.co = make_company('compta40-clo', 'COMPTA40 CLO')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.exercice = ExerciceComptable.objects.create(
            company=self.co, libelle='Exercice 2026',
            date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31))
        self.periode = PeriodeComptable.objects.create(
            company=self.co, exercice=self.exercice, libelle='Janvier 2026',
            date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31))

    def test_cloture_periode_403_sans_permission(self):
        role = Role.objects.create(
            company=self.co, nom='Compta sans clôture',
            permissions=['compta_saisir', 'compta_valider'])
        agent = make_user(self.co, 'compta40-noclo')
        agent.role = role
        agent.save()
        resp = auth(agent).post(
            f'/api/django/compta/periodes/{self.periode.pk}/cloturer/')
        self.assertEqual(resp.status_code, 403)
        self.periode.refresh_from_db()
        self.assertFalse(self.periode.verrouillee)

    def test_cloture_periode_ok_avec_permission(self):
        role = Role.objects.create(
            company=self.co, nom='Direction compta',
            permissions=['compta_cloturer'])
        directeur = make_user(self.co, 'compta40-dir')
        directeur.role = role
        directeur.save()
        resp = auth(directeur).post(
            f'/api/django/compta/periodes/{self.periode.pk}/cloturer/')
        self.assertEqual(resp.status_code, 200)
        self.periode.refresh_from_db()
        self.assertTrue(self.periode.verrouillee)

    def test_cloture_exercice_403_sans_permission(self):
        role = Role.objects.create(
            company=self.co, nom='Compta courante',
            permissions=['compta_saisir'])
        agent = make_user(self.co, 'compta40-exno')
        agent.role = role
        agent.save()
        resp = auth(agent).post(
            f'/api/django/compta/exercices/{self.exercice.pk}/cloturer/')
        self.assertEqual(resp.status_code, 403)

    def test_cloture_legacy_responsable_conserve_acces(self):
        # Compte légacy (sans rôle fin) → repli historique : accès conservé.
        legacy = make_user(self.co, 'compta40-legacy', role='responsable')
        resp = auth(legacy).post(
            f'/api/django/compta/periodes/{self.periode.pk}/cloturer/')
        self.assertEqual(resp.status_code, 200)


class SaisieEcritureGateTests(TestCase):
    """WIR175 — le CRUD des écritures et l'extourne exigent ``compta_saisir``.

    Avant : seul ``IsResponsableOrAdmin`` gardait ces routes, donc tout rôle fin
    portant UNE permission d'écriture quelconque (un Commercial et son
    ``crm_creer``) pouvait passer, modifier, supprimer ou contre-passer une
    écriture comptable. ``valider`` / la séparation des tâches restent
    inchangés : les deux permissions sont DISJOINTES dans les deux sens.
    """

    def setUp(self):
        self.co = make_company('wir175-co', 'WIR175 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.journal = services._journal(
            self.co, Journal.Type.OPERATIONS_DIVERSES)
        self.ecriture = make_ecriture(
            self.co, date(2026, 4, 1), 'Vente WIR175', '500')

    def _corps(self):
        return {
            'journal': self.journal.pk,
            'date_ecriture': '2026-04-02',
            'libelle': 'Saisie WIR175',
            'lignes': [
                {'compte': services.get_compte(self.co, '5141').pk,
                 'debit': '300.00', 'credit': '0.00'},
                {'compte': services.get_compte(self.co, '7121').pk,
                 'debit': '0.00', 'credit': '300.00'},
            ],
        }

    def _avec_role(self, username, nom, permissions):
        role = Role.objects.create(
            company=self.co, nom=nom, permissions=permissions)
        user = make_user(self.co, username)
        user.role = role
        user.save()
        return user

    # ── Commercial : 403 sur les quatre écritures ───────────────────────────
    def test_commercial_403_sur_create_update_destroy_extourner(self):
        # Extrait RÉEL du preset Commercial : aucune permission compta_*, mais
        # des permissions d'ÉCRITURE ailleurs (donc ``is_responsable`` vrai —
        # c'est exactement ce qui le laissait passer avant WIR175).
        commercial = self._avec_role(
            'wir175-commercial', 'Commercial WIR175',
            ['crm_voir', 'crm_creer', 'crm_modifier', 'ventes_creer'])
        api = auth(commercial)
        base = '/api/django/compta/ecritures/'

        self.assertEqual(
            api.post(base, self._corps(), format='json').status_code, 403)
        self.assertEqual(
            api.patch(f'{base}{self.ecriture.pk}/',
                      {'libelle': 'pirate'}, format='json').status_code, 403)
        self.assertEqual(
            api.delete(f'{base}{self.ecriture.pk}/').status_code, 403)
        self.assertEqual(
            api.post(f'{base}{self.ecriture.pk}/extourner/').status_code, 403)

        # Rien n'a bougé en base.
        self.ecriture.refresh_from_db()
        self.assertEqual(self.ecriture.libelle, 'Vente WIR175')
        self.assertEqual(
            EcritureComptable.objects.filter(company=self.co).count(), 1)

    # ── compta_valider SEUL ne crée pas ─────────────────────────────────────
    def test_compta_valider_seul_ne_cree_pas_ni_n_extourne(self):
        valideur = self._avec_role(
            'wir175-valideur', 'Valideur compta', ['compta_valider'])
        api = auth(valideur)
        base = '/api/django/compta/ecritures/'
        self.assertEqual(
            api.post(base, self._corps(), format='json').status_code, 403)
        self.assertEqual(
            api.post(f'{base}{self.ecriture.pk}/extourner/').status_code, 403)

    # ── compta_saisir : accès rendu ─────────────────────────────────────────
    def test_compta_saisir_cree_et_extourne(self):
        saisisseur = self._avec_role(
            'wir175-saisi', 'Saisie compta', ['compta_saisir'])
        api = auth(saisisseur)
        base = '/api/django/compta/ecritures/'
        resp = api.post(base, self._corps(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        resp = api.post(f'{base}{self.ecriture.pk}/extourner/')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_compta_saisir_seul_ne_valide_pas(self):
        # La réciproque : la garde ``compta_valider`` de l'action ``valider``
        # n'est PAS écrasée par le nouveau ``get_permissions``.
        saisisseur = self._avec_role(
            'wir175-saisi2', 'Saisie compta 2', ['compta_saisir'])
        resp = auth(saisisseur).post(
            f'/api/django/compta/ecritures/{self.ecriture.pk}/valider/')
        self.assertEqual(resp.status_code, 403)

    # ── Lecture inchangée ───────────────────────────────────────────────────
    def test_lecture_reste_ouverte(self):
        lecteur = self._avec_role(
            'wir175-lecteur', 'Compta lecture', ['compta_saisir'])
        resp = auth(lecteur).get('/api/django/compta/ecritures/')
        self.assertEqual(resp.status_code, 200)

    # ── Repli LÉGACY intact ─────────────────────────────────────────────────
    def test_legacy_responsable_conserve_la_saisie(self):
        legacy = make_user(self.co, 'wir175-legacy', role='responsable')
        api = auth(legacy)
        base = '/api/django/compta/ecritures/'
        resp = api.post(base, self._corps(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            api.post(f'{base}{self.ecriture.pk}/extourner/').status_code, 201)

    def test_legacy_normal_reste_refuse(self):
        legacy = make_user(self.co, 'wir175-legacy-normal', role='normal')
        resp = auth(legacy).post(
            '/api/django/compta/ecritures/', self._corps(), format='json')
        self.assertEqual(resp.status_code, 403)
