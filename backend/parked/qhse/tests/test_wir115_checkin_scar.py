"""WIR115 — API Check-in sécurité (CheckinSecurite) + SCAR
(DemandeActionFournisseur).

Couvre : création scopée société (company + technicien posés côté serveur),
action ``checkout``, filtre ``?en_retard=1``, cycle SCAR ``repondre``/
``verifier`` (statuts + verifiee_par), et l'isolation inter-sociétés.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.qhse.models import (
    CheckinSecurite, DemandeActionFournisseur, NonConformite,
)
from apps.stock.models import Fournisseur

User = get_user_model()

CHECKINS = '/api/django/qhse/checkins-securite/'
SCAR = '/api/django/qhse/demandes-action-fournisseur/'


def _company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CheckinSecuriteApiTests(TestCase):
    def setUp(self):
        self.company = _company('wir115-co', 'WIR115 Co')
        self.user = _user(self.company, 'wir115-resp')
        self.api = _auth(self.user)

    def test_create_pose_company_et_technicien(self):
        resp = self.api.post(
            CHECKINS, {'site_ref': 'Toiture Anfa'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        checkin = CheckinSecurite.objects.get(id=resp.data['id'])
        self.assertEqual(checkin.company_id, self.company.id)
        # technicien = utilisateur courant, heure_checkin posée par défaut.
        self.assertEqual(checkin.technicien_id, self.user.id)
        self.assertIsNotNone(checkin.heure_checkin)

    def test_checkout_action(self):
        checkin = CheckinSecurite.objects.create(
            company=self.company, technicien=self.user, site_ref='X',
            heure_checkin=timezone.now())
        resp = self.api.post(f'{CHECKINS}{checkin.id}/checkout/')
        self.assertEqual(resp.status_code, 200, resp.data)
        checkin.refresh_from_db()
        self.assertIsNotNone(checkin.heure_checkout_reelle)

    def test_filtre_en_retard(self):
        now = timezone.now()
        # En retard : check-out prévu il y a 2h, délai 30 min, pas de check-out.
        retard = CheckinSecurite.objects.create(
            company=self.company, technicien=self.user, site_ref='retard',
            heure_checkin=now - timedelta(hours=3),
            heure_checkout_prevue=now - timedelta(hours=2),
            delai_escalade_min=30)
        # Pas en retard : check-out prévu dans le futur.
        CheckinSecurite.objects.create(
            company=self.company, technicien=self.user, site_ref='ok',
            heure_checkin=now, heure_checkout_prevue=now + timedelta(hours=1))
        resp = self.api.get(CHECKINS, {'en_retard': '1'})
        self.assertEqual(resp.status_code, 200)
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        ids = [row['id'] for row in rows]
        self.assertIn(retard.id, ids)
        self.assertEqual(len(ids), 1)

    def test_isolation_inter_societes(self):
        other = _company('wir115-co-x', 'Other')
        other_user = _user(other, 'wir115-x')
        CheckinSecurite.objects.create(
            company=other, technicien=other_user, site_ref='hors')
        data = self.api.get(CHECKINS).data
        rows = data['results'] if isinstance(data, dict) else data
        self.assertEqual(len(rows), 0)


class ScarApiTests(TestCase):
    def setUp(self):
        self.company = _company('wir115-scar', 'WIR115 SCAR')
        self.user = _user(self.company, 'wir115-scar-resp')
        self.api = _auth(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='ACME')
        self.ncr = NonConformite.objects.create(
            company=self.company, titre='NCR fournisseur')

    def test_create_et_cycle_repondre_verifier(self):
        resp = self.api.post(SCAR, {
            'fournisseur': self.fournisseur.id,
            'ncr_source': self.ncr.id,
            'description_defaut': 'Panneaux fêlés',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        scar_id = resp.data['id']
        self.assertEqual(resp.data['statut'], 'emise')

        # repondre : emise → repondue
        r2 = self.api.post(f'{SCAR}{scar_id}/repondre/', {
            'cause_racine_fournisseur': 'Transport',
            'action_fournisseur': 'Renfort emballage',
        }, format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertEqual(r2.data['statut'], 'repondue')
        self.assertEqual(r2.data['cause_racine_fournisseur'], 'Transport')

        # verifier efficace → close, verifiee_par = utilisateur courant
        r3 = self.api.post(f'{SCAR}{scar_id}/verifier/', {
            'efficace': True}, format='json')
        self.assertEqual(r3.status_code, 200, r3.data)
        self.assertEqual(r3.data['statut'], 'close')
        scar = DemandeActionFournisseur.objects.get(id=scar_id)
        self.assertTrue(scar.efficace)
        self.assertEqual(scar.verifiee_par_id, self.user.id)

    def test_verifier_non_efficace_reste_verifiee(self):
        scar = DemandeActionFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            ncr_source=self.ncr, statut='repondue')
        resp = self.api.post(f'{SCAR}{scar.id}/verifier/', {
            'efficace': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'verifiee')

    def test_repondre_refuse_hors_emise(self):
        scar = DemandeActionFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            ncr_source=self.ncr, statut='close')
        resp = self.api.post(f'{SCAR}{scar.id}/repondre/', {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_fournisseur_hors_societe_refuse(self):
        other = _company('wir115-scar-x', 'Other SCAR')
        f_etranger = Fournisseur.objects.create(company=other, nom='Etranger')
        resp = self.api.post(SCAR, {
            'fournisseur': f_etranger.id,
            'ncr_source': self.ncr.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
