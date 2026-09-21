"""NTSCM37 — Permissions fines par rôle sur le module SCM.

Critère d'acceptation : un utilisateur du rôle Acheteur sans `scm.sop.animer`
reçoit 403 sur `avancer-statut/`.

ADAPTATION DE PÉRIMÈTRE : aucun rôle « Acheteur » n'existe dans ce repo
(`apps.roles.models` ne définit que Administrateur/Responsable/Utilisateur) —
le test ci-dessous crée un rôle fin ÉQUIVALENT (mêmes permissions SCM que
`RESPONSABLE_PERMISSIONS`, donc `scm_sop_voir` SANS `scm_sop_animer`,
exactement ce que le plan attend de l'« Acheteur »)."""
from django.test import TestCase

from apps.roles.models import ALL_PERMISSIONS, RESPONSABLE_PERMISSIONS, Role
from apps.scm.models import CyclePlanificationSOP

from .helpers import auth, make_company, make_user


class PermissionsFinesScmTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-perms-fines', 'Supply Permissions')
        self.cycle = CyclePlanificationSOP.objects.create(
            company=self.company, periode='2026-01')

        self.role_acheteur = Role.objects.create(
            company=self.company, nom='Acheteur (équivalent)',
            permissions=RESPONSABLE_PERMISSIONS)
        self.role_admin_fin = Role.objects.create(
            company=self.company, nom='Administrateur (fin)',
            permissions=ALL_PERMISSIONS, est_systeme=True)

        self.acheteur = make_user(self.company, 'scm-perm-acheteur', 'normal')
        self.acheteur.role = self.role_acheteur
        self.acheteur.save(update_fields=['role'])

        self.admin_fin = make_user(self.company, 'scm-perm-admin-fin', 'normal')
        self.admin_fin.role = self.role_admin_fin
        self.admin_fin.save(update_fields=['role'])

    def test_acheteur_sans_sop_animer_refuse_sur_avancer_statut(self):
        resp = auth(self.acheteur).post(
            f'/api/django/scm/cycles-sop/{self.cycle.id}/avancer-statut/', {},
            format='json')
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_acheteur_peut_lire_les_cycles(self):
        resp = auth(self.acheteur).get('/api/django/scm/cycles-sop/')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_administrateur_fin_avec_sop_animer_peut_avancer_le_statut(self):
        resp = auth(self.admin_fin).post(
            f'/api/django/scm/cycles-sop/{self.cycle.id}/avancer-statut/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_acheteur_peut_editer_une_politique_de_stock_en_lot(self):
        from apps.stock.models import Produit
        produit = Produit.objects.create(
            company=self.company, nom='Batterie 10kWh', prix_vente=25000,
            quantite_stock=8)
        resp = auth(self.acheteur).post(
            '/api/django/scm/politiques-stock/creer-en-lot/',
            {'produit_ids': [produit.id], 'service_level_pct': 90},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
