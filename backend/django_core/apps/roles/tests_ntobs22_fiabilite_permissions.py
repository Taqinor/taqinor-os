"""NTOBS22 — catalogue de permissions fines pour les écrans Fiabilité
(lecture vs administration).

Périmètre de ce lot (lane ``apps/roles`` isolée) : SEUL le catalogue
(``ALL_PERMISSIONS``, héritage Directeur/Administrateur, exclusion de
``PERMISSION_MODULE``) est posé ici. Le câblage réel des 6 vues du groupe
Fiabilité (``core.maintenance_windows``/``core.sla``/``core.views`` —
``BackupRunViewSet`` — encore gardées ``IsDirecteurOrAdmin``/
``IsAdminOrResponsableTier`` codé en dur) est HORS périmètre (``core`` n'est
pas ``apps/roles``) et n'est PAS testé ici. Aucun rôle système « Comptable »
n'existe dans ce dépôt (cf. les sept rôles + Admin RH/Admin Ventes définis
plus haut dans ce module) : la distribution par défaut du plan
(« Comptable + Directeur ») n'a donc PAS été câblée automatiquement — le
Directeur/Administrateur hérite des deux codes via ``ALL_PERMISSIONS``,
``fiabilite_voir`` reste octroyable manuellement à tout rôle existant
(Viewer, par exemple) via l'éditeur de rôles.

Le test le plus important de ce fichier est
``test_fiabilite_voir_ne_rend_jamais_responsable`` : le plan nommait ce
premier code ``fiabilite_lecture`` (sans suffixe ``_voir``/``_view``), ce qui
aurait fait basculer ``CustomUser._role_grants_write`` sur ÉCRITURE pour
tout rôle qui le porterait seul — un rôle censé être STRICTEMENT lecture
seule serait alors devenu « responsable » et aurait ouvert tout endpoint
interne gardé ``IsResponsableOrAdmin``, bien au-delà de la Fiabilité. D'où
le renommage en ``fiabilite_voir`` catalogué ici.
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company, CustomUser

from .models import (
    ADMIN_PERMISSIONS,
    ALL_PERMISSIONS,
    DIRECTEUR_PERMISSIONS,
    PERMISSION_MODULE,
    Role,
)

User = get_user_model()

NTOBS22_CODES = ('fiabilite_voir', 'fiabilite_administration')


def _company(nom, slug):
    """Nom ET slug explicitement distincts (le slug est unique en base)."""
    return Company.objects.create(nom=nom, slug=slug)


class Ntobs22CatalogueTests(SimpleTestCase):
    def test_les_deux_codes_sont_catalogues(self):
        for code in NTOBS22_CODES:
            self.assertIn(code, ALL_PERMISSIONS, code)

    def test_directeur_et_admin_les_portent_par_heritage(self):
        for code in NTOBS22_CODES:
            self.assertIn(code, DIRECTEUR_PERMISSIONS, code)
            self.assertIn(code, ADMIN_PERMISSIONS, code)

    def test_fiabilite_absent_de_permission_module(self):
        """``apps.parametres`` n'est pas togglable (fondation, comme
        ``parametres_voir``) : les mapper masquerait leur case sur un
        toggle qui n'existe pas."""
        for code in NTOBS22_CODES:
            self.assertNotIn(code, PERMISSION_MODULE, code)

    def test_fiabilite_voir_ne_rend_jamais_responsable(self):
        self.assertFalse(CustomUser._role_grants_write(['fiabilite_voir']))

    def test_fiabilite_administration_est_bien_une_ecriture(self):
        self.assertTrue(
            CustomUser._role_grants_write(['fiabilite_administration']))

    def test_aucun_doublon_introduit(self):
        self.assertEqual(len(ALL_PERMISSIONS), len(set(ALL_PERMISSIONS)))


class RoleAssignationBoutEnBoutTests(TestCase):
    """Câblage réel `Role.permissions` → `CustomUser.is_responsable`."""

    def test_role_fiabilite_voir_seul_reste_lecture_seule(self):
        company = _company('NTOBS22 Lecture Co', 'ntobs22-lecture-co')
        role = Role.objects.create(
            company=company, nom='Lecture Fiabilité',
            permissions=['fiabilite_voir'])
        user = User.objects.create_user(
            username='ntobs22_lecteur', password='x',
            role=role, company=company)
        self.assertFalse(user.is_responsable)

    def test_role_fiabilite_administration_est_responsable(self):
        company = _company('NTOBS22 Admin Co', 'ntobs22-admin-co')
        role = Role.objects.create(
            company=company, nom='Administration Fiabilité',
            permissions=['fiabilite_administration'])
        user = User.objects.create_user(
            username='ntobs22_admin', password='x',
            role=role, company=company)
        self.assertTrue(user.is_responsable)

    def test_directeur_porte_les_deux_codes(self):
        company = _company('NTOBS22 Directeur Co', 'ntobs22-directeur-co')
        role = Role.objects.create(
            company=company, nom='Directeur',
            permissions=DIRECTEUR_PERMISSIONS, est_systeme=True)
        user = User.objects.create_user(
            username='ntobs22_directeur', password='x',
            role=role, company=company)
        for code in NTOBS22_CODES:
            self.assertIn(code, user.role.permissions, code)
        self.assertTrue(user.is_responsable)
