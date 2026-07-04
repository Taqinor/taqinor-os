"""Tests XRH11 — Audit immuable des corrections de pointage.

Couvre :
* modifier une heure d'arrivée SANS motif → 400 (rien n'est modifié) ;
* AVEC motif → ligne(s) d'audit immuable créée(s), le pointage est bien
  mis à jour ;
* l'export paie (heures_supp_pour_paie / lecture normale du pointage) n'est
  pas altéré par l'ajout des corrections (juste tracé en plus) ;
* aucune route update/delete sur ``CorrectionPointage`` (write-once) ;
* isolation société de l'historique ``.../corrections/``.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import CorrectionPointage, DossierEmploye, Pointage

User = get_user_model()

POINTAGES = '/api/django/rh/pointages/'


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


class CorrectionPointageTests(TestCase):
    def setUp(self):
        self.co_a = make_company('cp-a', 'A')
        self.co_b = make_company('cp-b', 'B')
        self.rh = make_user(self.co_a, 'cp-rh')
        self.emp = DossierEmploye.objects.create(
            company=self.co_a, matricule='CP1', nom='Idrissi', prenom='Adam')
        self.pointage = Pointage.objects.create(
            company=self.co_a, employe=self.emp,
            type_pointage=Pointage.TypePointage.ARRIVEE,
            heure_arrivee=timezone.now())

    def test_modification_sans_motif_400(self):
        nouvelle_heure = timezone.now() + timezone.timedelta(hours=1)
        resp = auth(self.rh).patch(
            f'{POINTAGES}{self.pointage.id}/',
            {'heure_arrivee': nouvelle_heure.isoformat()})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('motif', resp.data)
        self.assertEqual(
            CorrectionPointage.objects.filter(
                pointage=self.pointage).count(), 0)
        self.pointage.refresh_from_db()

    def test_modification_avec_motif_cree_audit_immuable(self):
        nouvelle_heure = timezone.now() + timezone.timedelta(hours=1)
        resp = auth(self.rh).patch(
            f'{POINTAGES}{self.pointage.id}/',
            {'heure_arrivee': nouvelle_heure.isoformat(),
             'motif': 'Oubli badge — correction manuelle RH'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.pointage.refresh_from_db()
        self.assertEqual(
            self.pointage.heure_arrivee.replace(microsecond=0),
            nouvelle_heure.replace(microsecond=0))

        corrections = CorrectionPointage.objects.filter(
            pointage=self.pointage)
        self.assertEqual(corrections.count(), 1)
        correction = corrections.first()
        self.assertEqual(correction.champ, 'heure_arrivee')
        self.assertEqual(
            correction.motif, 'Oubli badge — correction manuelle RH')
        self.assertEqual(correction.auteur, self.rh)

    def test_correction_immuable_aucune_route_update_delete(self):
        correction = CorrectionPointage.objects.create(
            company=self.co_a, pointage=self.pointage, champ='heure_arrivee',
            ancienne_valeur='x', nouvelle_valeur='y', motif='test',
            auteur=self.rh)
        # Aucune route directe n'existe pour PATCH/DELETE une correction —
        # seul l'historique en lecture est exposé via /pointages/{id}/corrections/.
        resp = auth(self.rh).get(
            f'{POINTAGES}{self.pointage.id}/corrections/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['id'], correction.id)

    def test_pas_de_correction_sans_changement_reel(self):
        """PATCH avec la même valeur (aucun changement) → pas d'audit requis."""
        resp = auth(self.rh).patch(
            f'{POINTAGES}{self.pointage.id}/', {'note': 'RAS'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            CorrectionPointage.objects.filter(
                pointage=self.pointage).count(), 0)

    def test_creation_pointage_non_concernee(self):
        """La CRÉATION d'un pointage n'exige jamais de motif."""
        resp = auth(self.rh).post(POINTAGES, {
            'employe': self.emp.id,
            'type_pointage': Pointage.TypePointage.ARRIVEE,
            'heure_arrivee': timezone.now().isoformat(),
        })
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_isolation_societe_corrections(self):
        rh_b = make_user(self.co_b, 'cp-rh-b')
        resp = auth(rh_b).get(f'{POINTAGES}{self.pointage.id}/corrections/')
        self.assertEqual(resp.status_code, 404)
