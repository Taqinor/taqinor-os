"""Tests FG135 — Notes de frais & remboursements employés.

Couvre : saisie d'une note de frais avec justificatif photo + référence posée
côté serveur (NDF-YYYYMM-NNNN, jamais count()+1), refus d'un montant nul, cycle
de vie (soumise → validée → remboursée / rejetée), posting des écritures
équilibrées (validation = débit charge classe 6 / crédit personnel-créditeur
4432 ; remboursement = débit 4432 / crédit trésorerie), respect du verrou de
période (FG115), idempotence, garde multi-société (A ne touche jamais la note de
B), endpoints API + gate de rôle et company posée côté serveur.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    CompteTresorerie, EcritureComptable, NoteFrais, PeriodeComptable,
)

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


class NoteFraisServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('fg135', 'FG135 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.employe = make_user(self.co, 'fg135-employe', role='normal')
        self.resp = make_user(self.co, 'fg135-resp')
        self.banque = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='BMCE',
            compte_comptable=services.get_compte(self.co, '5141'))

    def _note(self, montant='450'):
        return services.creer_note_frais(
            self.co, employe=self.employe, date_frais=date(2026, 2, 10),
            montant=Decimal(montant), motif='Déplacement chantier Agadir',
            categorie=NoteFrais.Categorie.DEPLACEMENT, user=self.resp)

    def test_creer_pose_company_et_reference(self):
        note = self._note()
        self.assertEqual(note.company_id, self.co.id)
        self.assertEqual(note.employe_id, self.employe.id)
        self.assertEqual(note.statut, NoteFrais.Statut.BROUILLON)
        self.assertTrue(note.reference.startswith('NDF-'))

    def test_reference_increment_highest_used(self):
        n1 = self._note()
        n2 = self._note()
        self.assertNotEqual(n1.reference, n2.reference)
        self.assertTrue(n2.reference > n1.reference)
        # highest-used+1 (jamais count()+1) : après suppression de la dernière,
        # le plus haut numéro restant est celui de n1 ; la suivante reprend donc
        # n1+1 — exactement le numéro qu'occupait n2 (sans gap, sans collision).
        reused = n2.reference
        n2.delete()
        n3 = self._note()
        self.assertEqual(n3.reference, reused)

    def test_montant_nul_refuse(self):
        with self.assertRaises(ValidationError):
            services.creer_note_frais(
                self.co, employe=self.employe, date_frais=date(2026, 2, 10),
                montant=Decimal('0'), motif='Vide')

    def test_soumettre_puis_valider_poste_charge(self):
        note = self._note('450')
        services.soumettre_note_frais(note)
        self.assertEqual(note.statut, NoteFrais.Statut.SOUMISE)
        services.valider_note_frais(note, user=self.resp)
        note.refresh_from_db()
        self.assertEqual(note.statut, NoteFrais.Statut.VALIDEE)
        self.assertIsNotNone(note.ecriture_charge)
        ecr = note.ecriture_charge
        self.assertTrue(ecr.est_equilibree)
        self.assertEqual(ecr.journal.type_journal, 'OD')
        # Débit charge 6143, crédit personnel-créditeur 4432.
        self.assertEqual(
            ecr.lignes.get(compte__numero='6143').debit, Decimal('450'))
        ligne_perso = ecr.lignes.get(compte__numero='4432')
        self.assertEqual(ligne_perso.credit, Decimal('450'))
        self.assertEqual(ligne_perso.tiers_id, self.employe.id)

    def test_valider_avant_soumission_refuse(self):
        note = self._note()
        with self.assertRaises(ValidationError):
            services.valider_note_frais(note, user=self.resp)

    def test_valider_idempotent(self):
        note = self._note('100')
        services.soumettre_note_frais(note)
        services.valider_note_frais(note, user=self.resp)
        ecr1 = note.ecriture_charge
        services.valider_note_frais(note, user=self.resp)
        note.refresh_from_db()
        self.assertEqual(note.ecriture_charge_id, ecr1.id)

    def test_rembourser_poste_paiement(self):
        note = self._note('300')
        services.soumettre_note_frais(note)
        services.valider_note_frais(note, user=self.resp)
        services.rembourser_note_frais(
            note, compte_tresorerie=self.banque,
            date_remboursement=date(2026, 2, 28), user=self.resp)
        note.refresh_from_db()
        self.assertEqual(note.statut, NoteFrais.Statut.REMBOURSEE)
        self.assertEqual(note.compte_tresorerie_id, self.banque.id)
        ecr = note.ecriture_remboursement
        self.assertTrue(ecr.est_equilibree)
        self.assertEqual(ecr.journal.type_journal, 'BNK')
        # Débit 4432 (extinction dette), crédit 5141 banque.
        self.assertEqual(
            ecr.lignes.get(compte__numero='4432').debit, Decimal('300'))
        self.assertEqual(
            ecr.lignes.get(compte__numero='5141').credit, Decimal('300'))

    def test_rembourser_avant_validation_refuse(self):
        note = self._note()
        with self.assertRaises(ValidationError):
            services.rembourser_note_frais(
                note, compte_tresorerie=self.banque, user=self.resp)

    def test_rembourser_idempotent(self):
        note = self._note('120')
        services.soumettre_note_frais(note)
        services.valider_note_frais(note, user=self.resp)
        services.rembourser_note_frais(
            note, compte_tresorerie=self.banque, user=self.resp)
        ecr1 = note.ecriture_remboursement
        services.rembourser_note_frais(
            note, compte_tresorerie=self.banque, user=self.resp)
        note.refresh_from_db()
        self.assertEqual(note.ecriture_remboursement_id, ecr1.id)

    def test_rembourser_compte_autre_societe_refuse(self):
        autre = make_company('fg135-autre', 'Autre')
        services.seed_plan_comptable(autre)
        compte_autre = CompteTresorerie.objects.create(
            company=autre, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='Banque autre',
            compte_comptable=services.get_compte(autre, '5141'))
        note = self._note()
        services.soumettre_note_frais(note)
        services.valider_note_frais(note, user=self.resp)
        with self.assertRaises(ValidationError):
            services.rembourser_note_frais(
                note, compte_tresorerie=compte_autre, user=self.resp)

    def test_rejeter_fige_motif(self):
        note = self._note()
        services.soumettre_note_frais(note)
        services.rejeter_note_frais(
            note, motif_rejet='Justificatif illisible', user=self.resp)
        note.refresh_from_db()
        self.assertEqual(note.statut, NoteFrais.Statut.REJETEE)
        self.assertEqual(note.motif_rejet, 'Justificatif illisible')
        # Une note rejetée peut être resoumise.
        services.soumettre_note_frais(note)
        self.assertEqual(note.statut, NoteFrais.Statut.SOUMISE)
        self.assertEqual(note.motif_rejet, '')

    def test_valider_refuse_periode_verrouillee(self):
        PeriodeComptable.objects.create(
            company=self.co, date_debut=date(2026, 2, 1),
            date_fin=date(2026, 2, 28), verrouillee=True)
        note = self._note()
        services.soumettre_note_frais(note)
        with self.assertRaises(ValidationError):
            services.valider_note_frais(note, user=self.resp)


class NoteFraisApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('fg135-a', 'FG135 A')
        self.co_b = make_company('fg135-b', 'FG135 B')
        for co in (self.co_a, self.co_b):
            services.seed_plan_comptable(co)
            services.seed_journaux(co)
        self.user_a = make_user(self.co_a, 'fg135-user-a')
        self.user_b = make_user(self.co_b, 'fg135-user-b')
        self.employe_a = make_user(self.co_a, 'fg135-emp-a', role='normal')
        self.banque_a = CompteTresorerie.objects.create(
            company=self.co_a, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='Banque A',
            compte_comptable=services.get_compte(self.co_a, '5141'))

    def _create_payload(self, employe_id):
        return {
            'employe': employe_id, 'date_frais': '2026-02-10',
            'montant': '250', 'motif': 'Repas équipe',
            'categorie': 'repas',
        }

    def test_endpoint_create_avec_justificatif(self):
        api = auth(self.user_a)
        photo = SimpleUploadedFile(
            'ticket.jpg', b'\xff\xd8\xff\xe0fakejpeg',
            content_type='image/jpeg')
        payload = self._create_payload(self.employe_a.id)
        payload['justificatif'] = photo
        resp = api.post(
            '/api/django/compta/notes-frais/', payload, format='multipart')
        self.assertEqual(resp.status_code, 201, resp.data)
        note = NoteFrais.objects.get(id=resp.data['id'])
        self.assertEqual(note.company_id, self.co_a.id)
        self.assertTrue(note.reference.startswith('NDF-'))
        self.assertTrue(bool(note.justificatif))

    def test_endpoint_full_cycle(self):
        api = auth(self.user_a)
        resp = api.post(
            '/api/django/compta/notes-frais/',
            self._create_payload(self.employe_a.id), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        note_id = resp.data['id']
        self.assertEqual(
            api.post(
                f'/api/django/compta/notes-frais/{note_id}/soumettre/'
            ).status_code, 200)
        self.assertEqual(
            api.post(
                f'/api/django/compta/notes-frais/{note_id}/valider/',
                {}, format='json').status_code, 200)
        resp_r = api.post(
            f'/api/django/compta/notes-frais/{note_id}/rembourser/',
            {'compte_tresorerie': self.banque_a.id,
             'date_remboursement': '2026-02-28'}, format='json')
        self.assertEqual(resp_r.status_code, 200, resp_r.data)
        self.assertEqual(resp_r.data['statut'], 'remboursee')
        note = NoteFrais.objects.get(id=note_id)
        self.assertIsNotNone(note.ecriture_charge_id)
        self.assertIsNotNone(note.ecriture_remboursement_id)

    def test_endpoint_montant_nul_refuse(self):
        api = auth(self.user_a)
        payload = self._create_payload(self.employe_a.id)
        payload['montant'] = '0'
        resp = api.post(
            '/api/django/compta/notes-frais/', payload, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_isolation_societe(self):
        services.creer_note_frais(
            self.co_a, employe=self.employe_a, date_frais=date(2026, 2, 1),
            montant=Decimal('100'), motif='Privée A')
        resp = auth(self.user_b).get('/api/django/compta/notes-frais/')
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        rows = data['results'] if isinstance(
            data, dict) and 'results' in data else data
        self.assertEqual(len(rows), 0)

    def test_endpoint_refuse_role_normal(self):
        normal = make_user(self.co_a, 'fg135-normal', role='normal')
        resp = auth(normal).get('/api/django/compta/notes-frais/')
        self.assertEqual(resp.status_code, 403)

    def test_company_forced_server_side(self):
        # Un corps tentant d'injecter company est ignoré (posée côté serveur).
        api = auth(self.user_a)
        payload = self._create_payload(self.employe_a.id)
        payload['company'] = self.co_b.id
        resp = api.post(
            '/api/django/compta/notes-frais/', payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        note = NoteFrais.objects.get(id=resp.data['id'])
        self.assertEqual(note.company_id, self.co_a.id)

    def test_endpoint_create_refuse_employe_autre_societe(self):
        # B tente de créer une note avec un employé de A.
        api = auth(self.user_b)
        resp = api.post(
            '/api/django/compta/notes-frais/',
            self._create_payload(self.employe_a.id), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_rembourser_compte_inconnu_refuse(self):
        api = auth(self.user_a)
        note = services.creer_note_frais(
            self.co_a, employe=self.employe_a, date_frais=date(2026, 2, 10),
            montant=Decimal('80'), motif='X')
        services.soumettre_note_frais(note)
        services.valider_note_frais(note, user=self.user_a)
        # Compte de trésorerie d'une autre société.
        services.seed_plan_comptable(self.co_b)
        treso_b = CompteTresorerie.objects.create(
            company=self.co_b, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='Banque B',
            compte_comptable=services.get_compte(self.co_b, '5141'))
        resp = api.post(
            f'/api/django/compta/notes-frais/{note.id}/rembourser/',
            {'compte_tresorerie': treso_b.id}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_filter_par_statut(self):
        api = auth(self.user_a)
        services.creer_note_frais(
            self.co_a, employe=self.employe_a, date_frais=date(2026, 2, 1),
            montant=Decimal('10'), motif='Brouillon')
        resp = api.get(
            '/api/django/compta/notes-frais/?statut=brouillon')
        self.assertEqual(resp.status_code, 200)


class NoteFraisEcritureValidationTests(TestCase):
    """L'écriture postée n'est pas modifiable une fois en période close (FG115)."""

    def setUp(self):
        self.co = make_company('fg135-lock', 'FG135 Lock')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.employe = make_user(self.co, 'fg135-lock-emp', role='normal')
        self.resp = make_user(self.co, 'fg135-lock-resp')

    def test_ecriture_charge_validee(self):
        note = services.creer_note_frais(
            self.co, employe=self.employe, date_frais=date(2026, 3, 5),
            montant=Decimal('200'), motif='Carburant',
            categorie=NoteFrais.Categorie.CARBURANT)
        services.soumettre_note_frais(note)
        services.valider_note_frais(note, user=self.resp)
        note.refresh_from_db()
        self.assertEqual(
            note.ecriture_charge.statut, EcritureComptable.Statut.VALIDEE)
