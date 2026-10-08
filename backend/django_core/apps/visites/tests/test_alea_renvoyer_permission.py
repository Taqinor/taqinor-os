"""ALEA8 — ``renvoyer`` exige ``visites_valider`` (geste du bureau d'études).

Rejoue la sonde V4 LCOUT-4 : avec les rôles CANONIQUES, le Technicien
responsable (``visites_valider`` sans ``visites_modifier``) recevait 403 et le
Commercial terrain (``visites_modifier`` sans ``valider``) renvoyait sa propre
visite validée en 200. Aucun mock de permission : rôles réels du registre.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Lead
from apps.notifications.models import Notification
from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
from apps.visites.models import VisiteTerrain
from apps.visites.tests.test_visite_terrain import MESURES_COMPLETES, auth
from authentication.models import Company

User = get_user_model()

RENVOI = {'photos': [], 'mesures': [], 'motif': 'x'}


def _utilisateur_canonique(company, nom_role, username):
    permissions = dict(CANONICAL_SYSTEM_ROLES)[nom_role]
    role = Role.objects.create(company=company, nom=f'{nom_role} {username}',
                               permissions=list(permissions))
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


class RenvoyerPermissionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ALEA8', slug='alea8')
        self.terrain = _utilisateur_canonique(
            self.company, 'Commercial terrain', 'alea8-terrain')
        self.tech_resp = _utilisateur_canonique(
            self.company, 'Technicien responsable', 'alea8-techresp')
        self.lead = Lead.objects.create(company=self.company, nom='Alaoui')
        self.visite = VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, commercial=self.terrain,
            statut=VisiteTerrain.Statut.TERMINEE,
            mesures=dict(MESURES_COMPLETES))
        self.visite.statut = VisiteTerrain.Statut.VALIDEE
        self.visite.validee_par = self.tech_resp
        self.visite.save(update_fields=['statut', 'validee_par'])
        self.visite.refresh_from_db()
        self.url = f'/api/django/visites/visites/{self.visite.id}/renvoyer/'

    def test_prerequis_roles_canoniques(self):
        perms_resp = dict(CANONICAL_SYSTEM_ROLES)['Technicien responsable']
        perms_terrain = dict(CANONICAL_SYSTEM_ROLES)['Commercial terrain']
        self.assertIn('visites_valider', perms_resp)
        self.assertNotIn('visites_modifier', perms_resp)
        self.assertIn('visites_modifier', perms_terrain)
        self.assertNotIn('visites_valider', perms_terrain)

    def test_technicien_responsable_peut_renvoyer(self):
        resp = auth(self.tech_resp).post(self.url, RENVOI, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.visite.refresh_from_db()
        self.assertEqual(self.visite.statut, VisiteTerrain.Statut.A_REFAIRE)

    def test_commercial_terrain_refuse_sur_sa_visite(self):
        notifs_avant = Notification.objects.filter(
            recipient=self.terrain).count()
        resp = auth(self.terrain).post(self.url, RENVOI, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.visite.refresh_from_db()
        self.assertEqual(self.visite.statut, VisiteTerrain.Statut.VALIDEE)
        self.assertEqual(self.visite.validee_par_id, self.tech_resp.id)
        self.assertEqual(
            Notification.objects.filter(recipient=self.terrain).count(),
            notifs_avant)
        # Le gel VT3 tient toujours : le terrain ne réécrit pas les mesures.
        gel = auth(self.terrain).patch(
            f'/api/django/visites/visites/{self.visite.id}/mesures/',
            {'categorie': 'toiture', 'valeurs': {'pente_deg': 20}},
            format='json')
        self.assertEqual(gel.status_code, 400, gel.data)
