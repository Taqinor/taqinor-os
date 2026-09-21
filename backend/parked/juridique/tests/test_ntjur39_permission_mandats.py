"""NTJUR39 — permission fine « gérer les mandats et honoraires ».

Critère d'acceptation : « un utilisateur [qui voit les dossiers] mais sans
``juridique_gerer_mandats`` reçoit un 403 explicite sur ``POST mandats/`` ».
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.compta.models import Provision
from apps.juridique.models import (
    CabinetAvocat, DossierJuridique, MandatAvocat, NoteHonoraires,
)
from apps.roles.models import ALL_PERMISSIONS, PERMISSION_MODULE, Role

from ._base import auth, make_company

User = get_user_model()
DOSSIERS = '/api/django/juridique/dossiers/'
MANDATS = '/api/django/juridique/mandats/'
NOTES = '/api/django/juridique/notes-honoraires/'

PERMISSION = 'juridique_gerer_mandats'
BASE = ['juridique_voir', 'juridique_gerer', 'compta_saisir']


class PermissionMandatsTests(TestCase):
    def setUp(self):
        self.company = make_company('jur-m39-co', 'Juridique M39')
        self.dossier = DossierJuridique.objects.create(
            company=self.company, reference='JUR-2026-0001',
            titre='Contentieux bail', date_ouverture=date(2026, 7, 1))
        self.cabinet = CabinetAvocat.objects.create(
            company=self.company, nom='Cabinet Fassi')
        self.mandat = MandatAvocat.objects.create(
            company=self.company, dossier=self.dossier, cabinet=self.cabinet,
            date_mandat=date(2026, 7, 2), montant_forfait=Decimal('30000'))

    def _user_avec(self, username, permissions):
        role = Role.objects.create(
            company=self.company, nom=f'Rôle {username}',
            permissions=list(permissions))
        return User.objects.create_user(
            username=username, password='x', company=self.company, role=role)

    def _corps_mandat(self):
        return {
            'dossier': self.dossier.id, 'cabinet': self.cabinet.id,
            'date_mandat': '2026-07-03', 'mode_facturation': 'forfait',
            'montant_forfait': '50000.00',
        }

    def test_la_permission_est_bien_au_catalogue(self):
        self.assertIn(PERMISSION, ALL_PERMISSIONS)
        self.assertEqual(PERMISSION_MODULE[PERMISSION], 'juridique')

    def test_sans_la_permission_post_mandats_renvoie_403(self):
        user = self._user_avec('jur-m39-sans', BASE)
        api = auth(user)
        resp = api.post(MANDATS, self._corps_mandat(), format='json')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertEqual(
            MandatAvocat.objects.filter(company=self.company).count(), 1)
        # …mais il CONSULTE toujours son dossier et ses mandats.
        self.assertEqual(api.get(f'{DOSSIERS}{self.dossier.id}/').status_code,
                         200)
        self.assertEqual(api.get(MANDATS).status_code, 200)

    def test_sans_la_permission_les_notes_d_honoraires_sont_403(self):
        user = self._user_avec('jur-m39-sans-note', BASE)
        api = auth(user)
        resp = api.post(NOTES, {
            'mandat': self.mandat.id, 'date_facture': '2026-07-05',
            'montant_ht': '1000.00', 'montant_ttc': '1200.00',
        }, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertFalse(NoteHonoraires.objects.exists())

    def test_sans_la_permission_proposer_provision_est_403(self):
        user = self._user_avec('jur-m39-sans-prov', BASE)
        resp = auth(user).post(
            f'{DOSSIERS}{self.dossier.id}/proposer-provision/',
            {'montant': '10000.00', 'confirme': True}, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertFalse(Provision.objects.filter(
            company=self.company).exists())

    def test_avec_la_permission_tout_passe(self):
        user = self._user_avec('jur-m39-avec', BASE + [PERMISSION])
        api = auth(user)
        cree = api.post(MANDATS, self._corps_mandat(), format='json')
        self.assertEqual(cree.status_code, 201, cree.data)
        note = api.post(NOTES, {
            'mandat': cree.data['id'], 'date_facture': '2026-07-05',
            'montant_ht': '1000.00', 'montant_ttc': '1200.00',
        }, format='json')
        self.assertEqual(note.status_code, 201, note.data)
        prov = api.post(
            f'{DOSSIERS}{self.dossier.id}/proposer-provision/',
            {'montant': '10000.00', 'confirme': True}, format='json')
        self.assertEqual(prov.status_code, 201, prov.data)

    def test_sans_la_permission_l_activation_d_un_mandat_est_403(self):
        user = self._user_avec('jur-m39-sans-activer', BASE)
        resp = auth(user).post(f'{MANDATS}{self.mandat.id}/activer/', {},
                               format='json')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.mandat.refresh_from_db()
        self.assertEqual(self.mandat.statut, MandatAvocat.Statut.BROUILLON)
