"""Tests ZACC6 — Note de frais MULTI-LIGNES : regrouper N dépenses en UN
rapport de frais soumis en une fois.

Couvre : un employé groupe 3 notes en un rapport, la validation poste une
écriture unique équilibrée (Σ = somme des 3), le remboursement solde en un
paiement, un rapport déjà remboursé n'est pas re-postable, notes hors rapport
inchangées.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta import services
from apps.compta.models import (
    CompteTresorerie, EcritureComptable, NoteFrais, RapportNoteFrais,
)

User = get_user_model()


def make_company(slug='zacc6-co', nom='ZACC6 Co'):
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
        self.employe = make_user(self.company, 'zacc6-employe', role='normal')
        self.admin = make_user(self.company, 'zacc6-admin')
        self.api = auth(self.admin)
        self.note1 = services.creer_note_frais(
            self.company, employe=self.employe, date_frais=date(2026, 3, 1),
            montant=Decimal('100'), motif='Taxi')
        self.note2 = services.creer_note_frais(
            self.company, employe=self.employe, date_frais=date(2026, 3, 5),
            montant=Decimal('250'), motif='Hôtel')
        self.note3 = services.creer_note_frais(
            self.company, employe=self.employe, date_frais=date(2026, 3, 10),
            montant=Decimal('50'), motif='Repas')
        self.banque = CompteTresorerie.objects.filter(
            company=self.company,
            type_compte=CompteTresorerie.Type.BANQUE).first()
        if self.banque is None:
            compte_banque = services.get_compte(self.company, '5141')
            self.banque = CompteTresorerie.objects.create(
                company=self.company, libelle='Banque test',
                type_compte=CompteTresorerie.Type.BANQUE,
                compte_comptable=compte_banque)


class TestServices(_Base):
    def test_regrouper_trois_notes_en_un_rapport(self):
        rapport = services.creer_rapport_note_frais(
            self.company, employe=self.employe,
            note_frais_ids=[self.note1.id, self.note2.id, self.note3.id])
        self.assertTrue(rapport.reference.startswith('RNF-'))
        self.assertEqual(rapport.notes.count(), 3)
        self.assertEqual(rapport.montant_total, Decimal('400'))
        self.note1.refresh_from_db()
        self.assertEqual(self.note1.rapport_id, rapport.id)

    def test_validation_poste_ecriture_unique_equilibree(self):
        rapport = services.creer_rapport_note_frais(
            self.company, employe=self.employe,
            note_frais_ids=[self.note1.id, self.note2.id, self.note3.id])
        services.soumettre_rapport_note_frais(rapport)
        rapport = services.valider_rapport_note_frais(
            rapport, user=self.admin)
        rapport.refresh_from_db()
        self.assertEqual(rapport.statut, RapportNoteFrais.Statut.VALIDE)
        ecriture = rapport.ecriture_charge
        self.assertIsNotNone(ecriture)
        lignes = ecriture.lignes.all()
        total_debit = sum(
            (li.debit for li in lignes), Decimal('0'))
        total_credit = sum(
            (li.credit for li in lignes), Decimal('0'))
        self.assertEqual(total_debit, total_credit)
        self.assertEqual(total_debit, Decimal('400'))
        # Une SEULE écriture (pas trois) : le nombre de lignes de crédit sur
        # le compte 4432 personnel-créditeur doit être 1.
        lignes_credit_personnel = [
            li for li in lignes if li.credit == Decimal('400')]
        self.assertEqual(len(lignes_credit_personnel), 1)
        for note in (self.note1, self.note2, self.note3):
            note.refresh_from_db()
            self.assertEqual(note.statut, NoteFrais.Statut.VALIDEE)
            self.assertEqual(note.ecriture_charge_id, ecriture.id)

    def test_remboursement_solde_en_un_paiement(self):
        rapport = services.creer_rapport_note_frais(
            self.company, employe=self.employe,
            note_frais_ids=[self.note1.id, self.note2.id, self.note3.id])
        services.soumettre_rapport_note_frais(rapport)
        rapport = services.valider_rapport_note_frais(
            rapport, user=self.admin)
        rapport = services.rembourser_rapport_note_frais(
            rapport, compte_tresorerie=self.banque, user=self.admin)
        self.assertEqual(rapport.statut, RapportNoteFrais.Statut.REMBOURSE)
        ecriture_rbt = rapport.ecriture_remboursement
        self.assertIsNotNone(ecriture_rbt)
        total_debit = sum(
            (li.debit for li in ecriture_rbt.lignes.all()), Decimal('0'))
        self.assertEqual(total_debit, Decimal('400'))
        for note in (self.note1, self.note2, self.note3):
            note.refresh_from_db()
            self.assertEqual(note.statut, NoteFrais.Statut.REMBOURSEE)

    def test_rapport_deja_rembourse_non_repostable(self):
        rapport = services.creer_rapport_note_frais(
            self.company, employe=self.employe,
            note_frais_ids=[self.note1.id, self.note2.id])
        services.soumettre_rapport_note_frais(rapport)
        rapport = services.valider_rapport_note_frais(
            rapport, user=self.admin)
        rapport = services.rembourser_rapport_note_frais(
            rapport, compte_tresorerie=self.banque, user=self.admin)
        nb_ecritures_avant = EcritureComptable.objects.filter(
            company=self.company).count()
        # Idempotent : rejouer le remboursement ne poste rien de plus.
        rapport2 = services.rembourser_rapport_note_frais(
            rapport, compte_tresorerie=self.banque, user=self.admin)
        nb_ecritures_apres = EcritureComptable.objects.filter(
            company=self.company).count()
        self.assertEqual(rapport2.id, rapport.id)
        self.assertEqual(nb_ecritures_avant, nb_ecritures_apres)

    def test_notes_hors_rapport_inchangees(self):
        note_isolee = services.creer_note_frais(
            self.company, employe=self.employe, date_frais=date(2026, 3, 15),
            montant=Decimal('75'), motif='Isolée, hors rapport')
        services.soumettre_note_frais(note_isolee)
        note_isolee = services.valider_note_frais(
            note_isolee, user=self.admin)
        self.assertEqual(note_isolee.statut, NoteFrais.Statut.VALIDEE)
        self.assertIsNone(note_isolee.rapport_id)
        # L'écriture de la note isolée est bien la SIENNE, pas mêlée au
        # rapport.
        self.assertIsNotNone(note_isolee.ecriture_charge_id)

    def test_note_deja_dans_un_rapport_refuse_second_rapport(self):
        services.creer_rapport_note_frais(
            self.company, employe=self.employe,
            note_frais_ids=[self.note1.id])
        with self.assertRaises(Exception):
            services.creer_rapport_note_frais(
                self.company, employe=self.employe,
                note_frais_ids=[self.note1.id, self.note2.id])

    def test_valider_rapport_sans_notes_soumises_leve(self):
        rapport = services.creer_rapport_note_frais(
            self.company, employe=self.employe,
            note_frais_ids=[self.note1.id])
        # Rejeter la note plutôt que la soumettre : le rapport n'a alors
        # aucune note SOUMISE à valider.
        services.soumettre_rapport_note_frais(rapport)
        self.note1.refresh_from_db()
        services.rejeter_note_frais(self.note1, user=self.admin)
        with self.assertRaises(Exception):
            services.valider_rapport_note_frais(rapport, user=self.admin)


class TestEndpoint(_Base):
    def test_creer_endpoint(self):
        resp = self.api.post(
            '/api/django/compta/rapports-notes-frais/',
            {'employe': self.employe.id, 'libelle': 'Mars 2026',
             'note_frais_ids': [self.note1.id, self.note2.id]},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            Decimal(str(resp.data['montant_total'])), Decimal('350'))

    def test_cycle_complet_endpoint(self):
        resp = self.api.post(
            '/api/django/compta/rapports-notes-frais/',
            {'employe': self.employe.id,
             'note_frais_ids': [self.note1.id, self.note2.id, self.note3.id]},
            format='json')
        rid = resp.data['id']
        resp = self.api.post(
            f'/api/django/compta/rapports-notes-frais/{rid}/soumettre/')
        self.assertEqual(resp.status_code, 200)
        resp = self.api.post(
            f'/api/django/compta/rapports-notes-frais/{rid}/valider/')
        self.assertEqual(resp.status_code, 200, resp.data)
        resp = self.api.post(
            f'/api/django/compta/rapports-notes-frais/{rid}/rembourser/',
            {'compte_tresorerie': self.banque.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'rembourse')

    def test_isolation_societe(self):
        autre = make_company('zacc6-autre', 'Autre Co')
        services.seed_plan_comptable(autre)
        employe_autre = make_user(autre, 'zacc6-autre-employe', role='normal')
        note_autre = services.creer_note_frais(
            autre, employe=employe_autre, date_frais=date(2026, 3, 1),
            montant=Decimal('10'), motif='X')
        resp = self.api.post(
            '/api/django/compta/rapports-notes-frais/',
            {'employe': self.employe.id, 'note_frais_ids': [note_autre.id]},
            format='json')
        self.assertEqual(resp.status_code, 400)
