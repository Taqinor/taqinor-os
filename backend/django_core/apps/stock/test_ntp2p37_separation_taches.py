"""
NTP2P37 — Séparation des tâches (SoD) : demandeur ≠ approbateur.

CRITÈRE D'ACCEPTATION : avec ``sod_stricte`` actif, le créateur d'une demande
d'achat ne peut PAS approuver sa propre étape (400 explicite, contrôle
SERVEUR — même en appelant l'API directement).

Couvre aussi : le no-op total quand le réglage est OFF (défaut — les petites
structures à un seul décideur ne sont pas cassées), le cas d'un approbateur
TIERS (toujours autorisé), et la validation direction d'une note de frais
escaladée (NTP2P11).

Run :
    python manage.py test apps.stock.test_ntp2p37_separation_taches -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import (
    DemandeAchat, DemandeAchatLigne, EtapeApprobationAchat,
    RegleApprobationAchat,
)
from apps.stock import selectors as stock_selectors
from apps.stock.models import AchatsParametres

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ntp2p37-co-{n}', defaults={'nom': f'NTP2P37 Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ntp2p37-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def activer_sod(company):
    params = AchatsParametres.for_company(company)
    params.sod_stricte = True
    params.save(update_fields=['sod_stricte'])
    return params


class SodDemandeAchatTests(TestCase):

    def setUp(self):
        self.company = make_company()
        self.demandeur = make_user(self.company)
        self.tiers = make_user(self.company)
        RegleApprobationAchat.objects.create(
            company=self.company, libelle='Au-delà de 1 000 MAD',
            montant_min=1000, nombre_approbateurs=1)

    def _demande_soumise(self):
        da = DemandeAchat.objects.create(
            company=self.company, reference=f'DA-SOD-{next(_seq):04d}',
            objet='Réquisition SoD', created_by=self.demandeur)
        DemandeAchatLigne.objects.create(
            demande=da, designation='Article', quantite=1, prix_estime=5000)
        resp = auth(self.demandeur).post(
            f'{BASE}/demandes-achat/{da.pk}/soumettre/')
        self.assertEqual(resp.status_code, 200)
        return da

    def test_reglage_off_par_defaut(self):
        self.assertFalse(stock_selectors.sod_stricte_active(self.company))

    def test_sans_sod_le_createur_peut_approuver(self):
        """Non-régression : réglage OFF = comportement historique."""
        da = self._demande_soumise()
        resp = auth(self.demandeur).post(
            f'{BASE}/demandes-achat/{da.pk}/approuver-etape/', {},
            format='json')
        self.assertEqual(resp.status_code, 200)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.APPROUVEE)

    def test_avec_sod_le_createur_est_refuse(self):
        """CRITÈRE D'ACCEPTATION — contrôle SERVEUR, appel API direct."""
        activer_sod(self.company)
        da = self._demande_soumise()
        resp = auth(self.demandeur).post(
            f'{BASE}/demandes-achat/{da.pk}/approuver-etape/', {},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Séparation des tâches', resp.data['detail'])
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.SOUMISE)
        etape = da.etapes_approbation.first()
        self.assertEqual(etape.statut,
                         EtapeApprobationAchat.Statut.EN_ATTENTE)

    def test_avec_sod_un_tiers_peut_approuver(self):
        activer_sod(self.company)
        da = self._demande_soumise()
        resp = auth(self.tiers).post(
            f'{BASE}/demandes-achat/{da.pk}/approuver-etape/', {},
            format='json')
        self.assertEqual(resp.status_code, 200)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.APPROUVEE)

    def test_avec_sod_le_createur_ne_peut_pas_rejeter_non_plus(self):
        activer_sod(self.company)
        da = self._demande_soumise()
        resp = auth(self.demandeur).post(
            f'{BASE}/demandes-achat/{da.pk}/rejeter-etape/', {},
            format='json')
        self.assertEqual(resp.status_code, 400)

    def test_sod_dune_autre_societe_sans_effet(self):
        activer_sod(make_company())
        da = self._demande_soumise()
        resp = auth(self.demandeur).post(
            f'{BASE}/demandes-achat/{da.pk}/approuver-etape/', {},
            format='json')
        self.assertEqual(resp.status_code, 200)


class SodNoteFraisTests(TestCase):

    def setUp(self):
        from apps.frais.models import NoteFrais, PlafondNoteFrais

        self.company = make_company()
        self.employe = make_user(self.company)
        self.tiers = make_user(self.company)
        PlafondNoteFrais.objects.create(
            company=self.company, categorie=NoteFrais.Categorie.AUTRE,
            montant_max=Decimal('50000'),
            escalade_direction_au_dela_de=Decimal('3000'))

    def _note_soumise(self, montant):
        from apps.compta import services as compta_services
        from apps.frais.models import NoteFrais

        note = NoteFrais.objects.create(
            company=self.company, employe=self.employe,
            reference=f'NDF-SOD-{next(_seq):04d}',
            date_frais=timezone.localdate(), montant=Decimal(montant),
            motif='SoD', categorie=NoteFrais.Categorie.AUTRE,
            created_by=self.employe)
        return compta_services.soumettre_note_frais(note)

    def test_sans_sod_le_createur_peut_valider(self):
        from apps.compta import services as compta_services

        note = self._note_soumise(4000)
        self.assertTrue(note.escalade_direction)
        compta_services.valider_note_frais(note, user=self.employe)
        note.refresh_from_db()
        self.assertEqual(note.statut, note.Statut.VALIDEE)

    def test_avec_sod_le_createur_dune_note_escaladee_est_refuse(self):
        from apps.compta import services as compta_services

        activer_sod(self.company)
        note = self._note_soumise(4000)
        with self.assertRaises(ValidationError):
            compta_services.valider_note_frais(note, user=self.employe)
        note.refresh_from_db()
        self.assertEqual(note.statut, note.Statut.SOUMISE)

    def test_avec_sod_une_note_non_escaladee_reste_validable(self):
        from apps.compta import services as compta_services

        activer_sod(self.company)
        note = self._note_soumise(500)
        self.assertFalse(note.escalade_direction)
        compta_services.valider_note_frais(note, user=self.employe)
        note.refresh_from_db()
        self.assertEqual(note.statut, note.Statut.VALIDEE)

    def test_avec_sod_un_tiers_peut_valider_une_note_escaladee(self):
        from apps.compta import services as compta_services

        activer_sod(self.company)
        note = self._note_soumise(4000)
        compta_services.valider_note_frais(note, user=self.tiers)
        note.refresh_from_db()
        self.assertEqual(note.statut, note.Statut.VALIDEE)
