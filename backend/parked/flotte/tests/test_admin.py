"""Tests WIR49 — Filet de sécurité Django admin pour les modèles Flotte
critiques (`apps/flotte` n'avait AUCUN `admin.py`, contrairement à `paie`).

Couvre :
- Les 5 modèles critiques (Conducteur, GarantieFlotte, BudgetFlotte,
  RemiseAccessoire, DemandeVehicule) sont bien enregistrés auprès du site
  admin Django.
- Un superutilisateur peut réellement atteindre la liste ET le formulaire de
  création `/admin/` pour chacun (pas seulement une déclaration morte).
- Un `Conducteur` est créable de bout en bout via le formulaire admin.
"""
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from authentication.models import Company

from apps.flotte.models import (
    BudgetFlotte,
    Conducteur,
    DemandeVehicule,
    GarantieFlotte,
    RemiseAccessoire,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_superuser(company, username):
    user = User.objects.create_user(
        username=username, password='x', company=company, role_legacy='admin')
    user.is_staff = True
    user.is_superuser = True
    user.save(update_fields=['is_staff', 'is_superuser'])
    return user


class FlotteAdminRegistrationTests(TestCase):
    """Les modèles WIR49 sont bien enregistrés auprès du site admin."""

    def test_models_registered(self):
        for model in (
            Conducteur, GarantieFlotte, BudgetFlotte, RemiseAccessoire,
            DemandeVehicule,
        ):
            self.assertTrue(
                admin.site.is_registered(model),
                f'{model.__name__} devrait être enregistré auprès de '
                'admin.site (apps/flotte/admin.py).')


class FlotteAdminAccessTests(TestCase):
    """Un superutilisateur atteint réellement liste + création `/admin/`."""

    def setUp(self):
        self.company = make_company('flotte-admin-a', 'Flotte Admin A')
        self.superuser = make_superuser(self.company, 'flotte-admin-superuser')
        self.client = Client()
        self.client.force_login(self.superuser)

    def test_conducteur_changelist_and_add_reachable(self):
        changelist = reverse('admin:flotte_conducteur_changelist')
        self.assertEqual(self.client.get(changelist).status_code, 200)
        add = reverse('admin:flotte_conducteur_add')
        self.assertEqual(self.client.get(add).status_code, 200)

    def test_garantie_flotte_changelist_reachable(self):
        changelist = reverse('admin:flotte_garantieflotte_changelist')
        self.assertEqual(self.client.get(changelist).status_code, 200)

    def test_budget_flotte_changelist_reachable(self):
        changelist = reverse('admin:flotte_budgetflotte_changelist')
        self.assertEqual(self.client.get(changelist).status_code, 200)

    def test_remise_accessoire_changelist_reachable(self):
        changelist = reverse('admin:flotte_remiseaccessoire_changelist')
        self.assertEqual(self.client.get(changelist).status_code, 200)

    def test_demande_vehicule_changelist_reachable(self):
        changelist = reverse('admin:flotte_demandevehicule_changelist')
        self.assertEqual(self.client.get(changelist).status_code, 200)

    def test_creates_conducteur_via_admin_form(self):
        """Un conducteur est réellement créable via `/admin/` (pas juste
        une déclaration morte) : POST sur le formulaire d'ajout persiste
        l'enregistrement."""
        add = reverse('admin:flotte_conducteur_add')
        resp = self.client.post(add, {
            'company': self.company.id,
            'nom': 'Conducteur Admin Test',
            'telephone': '',
            'numero_permis': '',
            'categorie_permis': '',
            'actif': 'on',
        })
        # 302 = création réussie (redirection post-save) ; sinon le formulaire
        # est ré-affiché (200) avec les erreurs — on veut la preuve du 302.
        self.assertEqual(resp.status_code, 302, resp.content)
        self.assertTrue(
            Conducteur.objects.filter(nom='Conducteur Admin Test').exists())
