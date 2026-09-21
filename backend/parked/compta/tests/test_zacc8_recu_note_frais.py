"""Tests ZACC8 — Attestation / reçu PDF de remboursement de note de frais.

Couvre : le reçu d'une note remboursée se télécharge aux bons montants
(total en lettres), une note non remboursée -> 400 explicite, company-scopé
(404 cross-company), tests de rendu (contenu HTML avant WeasyPrint). Même
couverture pour le reçu de RAPPORT (ZACC6 + ZACC8).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta import services
from apps.compta.models import CompteTresorerie
from apps.compta.pdf_notes_frais import (
    render_recu_note_frais_html,
    render_recu_rapport_note_frais_html,
)

User = get_user_model()


def make_company(slug='zacc8-co', nom='ZACC8 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _Base(TestCase):
    def setUp(self):
        self.company = make_company()
        services.seed_plan_comptable(self.company)
        services.seed_journaux(self.company)
        self.employe = make_user(self.company, 'zacc8-employe', role='normal')
        self.admin = make_user(self.company, 'zacc8-admin')
        self.api = auth(self.admin)
        compte_banque = services.get_compte(self.company, '5141')
        self.banque = CompteTresorerie.objects.create(
            company=self.company, libelle='Banque test',
            type_compte=CompteTresorerie.Type.BANQUE,
            compte_comptable=compte_banque)


class TestHtmlRendering(_Base):
    def test_recu_note_html_contient_montant_en_lettres(self):
        note = services.creer_note_frais(
            self.company, employe=self.employe, date_frais=date(2026, 3, 1),
            montant=Decimal('1000'), motif='Taxi aéroport')
        services.soumettre_note_frais(note)
        note = services.valider_note_frais(note, user=self.admin)
        note = services.rembourser_note_frais(
            note, compte_tresorerie=self.banque, user=self.admin)
        html = render_recu_note_frais_html(note)
        self.assertIn('1 000,00', html)
        self.assertIn('Mille dirhams', html)
        self.assertIn('Taxi aéroport', html)

    def test_recu_note_entete_optionnelle(self):
        note = services.creer_note_frais(
            self.company, employe=self.employe, date_frais=date(2026, 3, 1),
            montant=Decimal('100'), motif='X')
        services.soumettre_note_frais(note)
        note = services.valider_note_frais(note, user=self.admin)
        note = services.rembourser_note_frais(
            note, compte_tresorerie=self.banque, user=self.admin)
        html = render_recu_note_frais_html(note, None)
        self.assertIn('Reçu de remboursement de note de frais', html)

    def test_recu_rapport_html_cumule_montant_en_lettres(self):
        n1 = services.creer_note_frais(
            self.company, employe=self.employe, date_frais=date(2026, 3, 1),
            montant=Decimal('300'), motif='Taxi')
        n2 = services.creer_note_frais(
            self.company, employe=self.employe, date_frais=date(2026, 3, 2),
            montant=Decimal('200'), motif='Repas')
        rapport = services.creer_rapport_note_frais(
            self.company, employe=self.employe,
            note_frais_ids=[n1.id, n2.id])
        services.soumettre_rapport_note_frais(rapport)
        rapport = services.valider_rapport_note_frais(
            rapport, user=self.admin)
        rapport = services.rembourser_rapport_note_frais(
            rapport, compte_tresorerie=self.banque, user=self.admin)
        html = render_recu_rapport_note_frais_html(rapport)
        self.assertIn('500,00', html)
        self.assertIn('Cinq-cents dirhams', html)


class TestEndpoint(_Base):
    def test_recu_pdf_note_non_remboursee_400(self):
        note = services.creer_note_frais(
            self.company, employe=self.employe, date_frais=date(2026, 3, 1),
            montant=Decimal('100'), motif='X')
        resp = self.api.get(
            f'/api/django/compta/notes-frais/{note.id}/recu-pdf/')
        self.assertEqual(resp.status_code, 400)

    def test_recu_pdf_note_remboursee_ou_503(self):
        note = services.creer_note_frais(
            self.company, employe=self.employe, date_frais=date(2026, 3, 1),
            montant=Decimal('100'), motif='X')
        services.soumettre_note_frais(note)
        note = services.valider_note_frais(note, user=self.admin)
        note = services.rembourser_note_frais(
            note, compte_tresorerie=self.banque, user=self.admin)
        resp = self.api.get(
            f'/api/django/compta/notes-frais/{note.id}/recu-pdf/')
        self.assertIn(resp.status_code, (200, 503))
        if resp.status_code == 200:
            self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_recu_pdf_note_cross_company_404(self):
        autre = make_company('zacc8-autre', 'Autre Co')
        services.seed_plan_comptable(autre)
        employe_autre = make_user(autre, 'zacc8-autre-employe', role='normal')
        note_autre = services.creer_note_frais(
            autre, employe=employe_autre, date_frais=date(2026, 3, 1),
            montant=Decimal('50'), motif='Y')
        resp = self.api.get(
            f'/api/django/compta/notes-frais/{note_autre.id}/recu-pdf/')
        self.assertEqual(resp.status_code, 404)

    def test_recu_pdf_rapport_non_rembourse_400(self):
        note = services.creer_note_frais(
            self.company, employe=self.employe, date_frais=date(2026, 3, 1),
            montant=Decimal('100'), motif='X')
        rapport = services.creer_rapport_note_frais(
            self.company, employe=self.employe, note_frais_ids=[note.id])
        resp = self.api.get(
            f'/api/django/compta/rapports-notes-frais/{rapport.id}/'
            f'recu-pdf/')
        self.assertEqual(resp.status_code, 400)

    def test_recu_pdf_rapport_rembourse_ou_503(self):
        note = services.creer_note_frais(
            self.company, employe=self.employe, date_frais=date(2026, 3, 1),
            montant=Decimal('100'), motif='X')
        rapport = services.creer_rapport_note_frais(
            self.company, employe=self.employe, note_frais_ids=[note.id])
        services.soumettre_rapport_note_frais(rapport)
        rapport = services.valider_rapport_note_frais(
            rapport, user=self.admin)
        rapport = services.rembourser_rapport_note_frais(
            rapport, compte_tresorerie=self.banque, user=self.admin)
        resp = self.api.get(
            f'/api/django/compta/rapports-notes-frais/{rapport.id}/'
            f'recu-pdf/')
        self.assertIn(resp.status_code, (200, 503))
