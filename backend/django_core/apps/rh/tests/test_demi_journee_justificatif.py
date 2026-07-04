"""Tests XRH3 — congés demi-journée + justificatif maladie.

Couvre :
* ``services.calculer_jours_demande`` retranche 0,5 j par drapeau demi-journée
  (borné à 0 minimum) ;
* l'endpoint création applique la même règle (jours calculés côté serveur) ;
* ``services.valider_demande`` REFUSE (ValueError → 400) une demande dont les
  jours dépassent ``jours_max_sans_justificatif`` sans justificatif joint, et
  l'accepte avec un justificatif ;
* un type sans plafond configuré (``None``) ne bloque jamais ;
* isolation multi-société.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.rh import services
from apps.rh.models import DemandeConge, DossierEmploye, TypeAbsence

User = get_user_model()

BASE = '/api/django/rh/demandes-conge/'


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


class CalculerJoursDemiJourneeTests(TestCase):
    def setUp(self):
        self.co = make_company('demi-a', 'A')
        self.cp = TypeAbsence.objects.create(
            company=self.co, code='CP', libelle='Congé payé',
            decompte_jours_ouvres=True, deduit_solde=True)

    def test_demi_journee_debut_retranche_0_5(self):
        # lundi 2026-06-22 → vendredi 2026-06-26 = 5 jours ouvrés.
        jours = services.calculer_jours_demande(
            self.cp, date(2026, 6, 22), date(2026, 6, 26),
            demi_journee_debut=True)
        self.assertEqual(jours, Decimal('4.5'))

    def test_demi_journee_debut_et_fin(self):
        jours = services.calculer_jours_demande(
            self.cp, date(2026, 6, 22), date(2026, 6, 26),
            demi_journee_debut=True, demi_journee_fin=True)
        self.assertEqual(jours, Decimal('4'))

    def test_un_jour_avec_demi_journee_decompte_0_5(self):
        # Un seul jour, une demi-journée : 1 - 0,5 = 0,5 j.
        jours = services.calculer_jours_demande(
            self.cp, date(2026, 6, 22), date(2026, 6, 22),
            demi_journee_debut=True)
        self.assertEqual(jours, Decimal('0.5'))

    def test_jamais_negatif(self):
        jours = services.calculer_jours_demande(
            self.cp, date(2026, 6, 22), date(2026, 6, 22),
            demi_journee_debut=True, demi_journee_fin=True)
        self.assertEqual(jours, Decimal('0'))

    def test_api_create_applique_demi_journee(self):
        co = self.co
        user = make_user(co, 'demi-api-1')
        emp = DossierEmploye.objects.create(
            company=co, matricule='E1', nom='X', prenom='Y')
        resp = auth(user).post(BASE, {
            'employe': emp.id, 'type_absence': self.cp.id,
            'date_debut': '2026-06-22', 'date_fin': '2026-06-26',
            'demi_journee_debut': True}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Decimal(resp.data['jours']), Decimal('4.5'))


class JustificatifValidationTests(TestCase):
    def setUp(self):
        self.co = make_company('just-a', 'A')
        self.emp = DossierEmploye.objects.create(
            company=self.co, matricule='E1', nom='X', prenom='Y')
        self.maladie = TypeAbsence.objects.create(
            company=self.co, code='MAL', libelle='Maladie',
            decompte_jours_ouvres=False, deduit_solde=False,
            jours_max_sans_justificatif=4)

    def test_maladie_5j_sans_justificatif_refusee(self):
        demande = DemandeConge.objects.create(
            company=self.co, employe=self.emp, type_absence=self.maladie,
            date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 5),
            jours=Decimal('5'))
        with self.assertRaises(ValueError):
            services.valider_demande(demande)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, DemandeConge.Statut.SOUMISE)

    def test_maladie_5j_avec_justificatif_validee(self):
        fichier = SimpleUploadedFile(
            'certificat.pdf', b'%PDF-1.4 test', content_type='application/pdf')
        demande = DemandeConge.objects.create(
            company=self.co, employe=self.emp, type_absence=self.maladie,
            date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 5),
            jours=Decimal('5'), justificatif=fichier)
        services.valider_demande(demande)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, DemandeConge.Statut.VALIDEE)

    def test_maladie_sous_le_seuil_pas_de_justificatif_requis(self):
        demande = DemandeConge.objects.create(
            company=self.co, employe=self.emp, type_absence=self.maladie,
            date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 3),
            jours=Decimal('3'))
        services.valider_demande(demande)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, DemandeConge.Statut.VALIDEE)

    def test_type_sans_plafond_ne_bloque_jamais(self):
        cp = TypeAbsence.objects.create(
            company=self.co, code='CP', libelle='Congé payé',
            decompte_jours_ouvres=True, deduit_solde=True,
            jours_max_sans_justificatif=None)
        demande = DemandeConge.objects.create(
            company=self.co, employe=self.emp, type_absence=cp,
            date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 10),
            jours=Decimal('10'))
        services.valider_demande(demande)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, DemandeConge.Statut.VALIDEE)

    def test_endpoint_valider_renvoie_400_avec_message_francais(self):
        user = make_user(self.co, 'just-api-1')
        demande = DemandeConge.objects.create(
            company=self.co, employe=self.emp, type_absence=self.maladie,
            date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 5),
            jours=Decimal('5'))
        resp = auth(user).post(f'{BASE}{demande.id}/valider/', {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Justificatif', resp.data['detail'])

    def test_isolation_societe_type_absence(self):
        co_b = make_company('just-b', 'B')
        user_b = make_user(co_b, 'just-b')
        resp = auth(user_b).post(BASE, {
            'employe': self.emp.id, 'type_absence': self.maladie.id,
            'date_debut': '2026-06-01', 'date_fin': '2026-06-05'},
            format='json')
        self.assertEqual(resp.status_code, 400)
