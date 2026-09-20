"""NTP2P36 — câblage du code fin ``approuver_note_frais_direction`` sur la
validation d'une note de frais ESCALADÉE en direction (NTP2P11).

``NoteFraisViewSet.valider`` (la vraie action NTP2P11) était gardée UNIQUEMENT
par le palier grossier ``compta_valider`` (YRBAC13), IDENTIQUE pour toute
note — y compris une note dont le montant dépasse le seuil d'escalade
configuré (``NoteFrais.escalade_direction``). Ce test prouve, comme
NTCON26/NTUX31/NTP2P36(installations/stock) : un rôle FIN portant
``compta_valider`` mais PAS le code fin reçoit 403 sur une note escaladée
(message FR explicite) ; le même rôle une fois le code ajouté franchit la
garde ; une note ORDINAIRE (non escaladée) reste validable SANS le code
(non-régression, la garde ne s'applique QUE sous escalade) ; un compte HÉRITÉ
(``role_legacy``) garde son accès aux deux via le repli légacy de
``core.permissions._user_has_or_legacy``.

Run :
    python manage.py test apps.compta.tests.test_ntp2p36_cablage_valider_note_frais_direction -v2
"""
import itertools
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.frais.models import NoteFrais, PlafondNoteFrais
from apps.frais.permissions import PERM_APPROUVER_NOTE_FRAIS_DIRECTION
from apps.roles.models import Role

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/compta/notes-frais'


def make_company():
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ntp2p36-frais-co-{n}', defaults={'nom': f'NTP2P36 Frais {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ntp2p36-frais-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_role_user(company, codes, username=None):
    role = Role.objects.create(
        company=company, nom=f'Rôle {username or next(_seq)}',
        permissions=list(codes))
    return User.objects.create_user(
        username=username or f'ntp2p36-frais-role-{next(_seq)}', password='x',
        company=company, role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ValiderNoteFraisDirectionCodeFinTests(TestCase):
    def setUp(self):
        self.company = make_company()
        services.seed_plan_comptable(self.company)
        services.seed_journaux(self.company)
        self.employe = make_user(self.company, role='normal')
        PlafondNoteFrais.objects.create(
            company=self.company, categorie=NoteFrais.Categorie.AUTRE,
            montant_max=Decimal('50000'),
            escalade_direction_au_dela_de=Decimal('3000'))

    def _note_soumise(self, montant):
        note = services.creer_note_frais(
            self.company, employe=self.employe, date_frais=date(2026, 2, 10),
            montant=Decimal(montant), motif='NTP2P36', user=self.employe)
        services.soumettre_note_frais(note)
        note.refresh_from_db()
        return note

    def test_refuse_sans_le_code_fin_sur_note_escaladee(self):
        note = self._note_soumise(4000)
        self.assertTrue(note.escalade_direction)
        appro = make_role_user(
            self.company, ['compta_valider'], 'ntp2p36-frais-sans-code')
        resp = auth(appro).post(
            f'{BASE}/{note.pk}/valider/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN,
                         resp.content)
        note.refresh_from_db()
        self.assertEqual(note.statut, NoteFrais.Statut.SOUMISE)

    def test_franchit_la_garde_avec_le_code_fin(self):
        note = self._note_soumise(4000)
        appro = make_role_user(
            self.company,
            ['compta_valider', PERM_APPROUVER_NOTE_FRAIS_DIRECTION],
            'ntp2p36-frais-avec-code')
        resp = auth(appro).post(
            f'{BASE}/{note.pk}/valider/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        note.refresh_from_db()
        self.assertEqual(note.statut, NoteFrais.Statut.VALIDEE)

    def test_note_ordinaire_ne_requiert_pas_le_code_fin(self):
        """Non-régression : sans escalade, `compta_valider` seul suffit."""
        note = self._note_soumise(500)
        self.assertFalse(note.escalade_direction)
        appro = make_role_user(
            self.company, ['compta_valider'], 'ntp2p36-frais-ordinaire')
        resp = auth(appro).post(
            f'{BASE}/{note.pk}/valider/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)

    def test_compte_legacy_garde_son_acces_sur_note_escaladee(self):
        """Non-régression : un compte hérité n'a rien perdu."""
        note = self._note_soumise(4000)
        appro = make_user(self.company, role='responsable')
        resp = auth(appro).post(
            f'{BASE}/{note.pk}/valider/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
