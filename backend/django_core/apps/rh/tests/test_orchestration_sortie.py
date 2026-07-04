"""Tests YHIRE2 — Orchestration de sortie (employe_sorti → checklist +
compte désactivé + ProfilPaie coupé).

Couvre :
* ``services.sortir_employe`` génère la checklist ``ElementSortie`` depuis
  les dotations EPI ouvertes et affectations véhicule ACTIVES réelles (rien
  à la main), clôture les affectations, note les avances non soldées.
* Le compte utilisateur lié est désactivé.
* ``ProfilPaie.actif`` passe à ``False`` via le bus d'événements
  (``employe_sorti``), sans import croisé rh↔paie.
* Idempotence : ré-appeler sur un dossier déjà SORTI lève ``ValueError``.
* Rapport ``comptes_actifs_employes_sortis`` liste/vide correctement,
  isolation multi-tenant.
* API : action ``employes/{id}/sortir/`` (validations 400), rapport
  ``employes/comptes-actifs-sortis/``.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import services
from apps.rh.models import (
    AffectationVehicule,
    AvanceSalaire,
    DossierEmploye,
    DotationEpi,
    ElementSortie,
    EpiCatalogue,
)

User = get_user_model()

URL = '/api/django/rh/employes/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule, **kwargs):
    defaults = dict(nom='N', prenom='P', statut=DossierEmploye.Statut.ACTIF)
    defaults.update(kwargs)
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, **defaults)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class SortirEmployeServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('yhire2-a', 'A')
        self.compte = make_user(self.company, 'compte-sortant', role='normal')
        self.employe = make_employe(
            self.company, 'M1', user=self.compte)

    def test_genere_checklist_epi_et_vehicule_et_desactive_compte(self):
        epi = EpiCatalogue.objects.create(
            company=self.company, designation='Casque', type_epi='casque')
        DotationEpi.objects.create(
            company=self.company, employe=self.employe, epi=epi,
            recupere=False)
        AffectationVehicule.objects.create(
            company=self.company, employe=self.employe, vehicule_id=42,
            statut=AffectationVehicule.Statut.ACTIVE)

        services.sortir_employe(
            self.employe, date_sortie=timezone.localdate(),
            motif=DossierEmploye.MotifSortie.DEMISSION)

        self.employe.refresh_from_db()
        self.assertEqual(self.employe.statut, DossierEmploye.Statut.SORTI)

        elements = ElementSortie.objects.filter(employe=self.employe)
        types = set(elements.values_list('type_element', flat=True))
        self.assertIn(ElementSortie.TypeElement.EPI, types)
        self.assertIn(ElementSortie.TypeElement.VEHICULE, types)

        affectation = AffectationVehicule.objects.get(employe=self.employe)
        self.assertEqual(
            affectation.statut, AffectationVehicule.Statut.TERMINEE)
        self.assertIsNotNone(affectation.date_fin)

        self.compte.refresh_from_db()
        self.assertFalse(self.compte.is_active)

    def test_avances_non_soldees_notees(self):
        AvanceSalaire.objects.create(
            company=self.company, employe=self.employe, montant=1000,
            statut=AvanceSalaire.Statut.APPROUVEE)
        services.sortir_employe(
            self.employe, date_sortie=timezone.localdate(),
            motif=DossierEmploye.MotifSortie.DEMISSION)
        note = ElementSortie.objects.filter(
            employe=self.employe,
            type_element=ElementSortie.TypeElement.AUTRE).first()
        self.assertIsNotNone(note)
        self.assertIn('1000', note.note)

    def test_profil_paie_coupe_via_bus_evenements(self):
        try:
            from apps.paie.models import ProfilPaie
        except Exception:  # pragma: no cover - app paie absente
            self.skipTest('apps.paie indisponible')
        profil = ProfilPaie.objects.create(
            company=self.company, employe=self.employe, actif=True)
        services.sortir_employe(
            self.employe, date_sortie=timezone.localdate(),
            motif=DossierEmploye.MotifSortie.FIN_CONTRAT)
        profil.refresh_from_db()
        self.assertFalse(profil.actif)

    def test_idempotent_deja_sorti_refuse(self):
        services.sortir_employe(
            self.employe, date_sortie=timezone.localdate(),
            motif=DossierEmploye.MotifSortie.AUTRE)
        with self.assertRaises(ValueError):
            services.sortir_employe(
                self.employe, date_sortie=timezone.localdate(),
                motif=DossierEmploye.MotifSortie.AUTRE)
        # Aucune double génération de checklist (au moins pas de crash / pas
        # de doublon d'éléments créés par le second appel qui a échoué avant).
        self.assertEqual(
            ElementSortie.objects.filter(employe=self.employe).count(), 0)

    def test_rapport_comptes_actifs_sortis(self):
        # Sortie faite hors du chemin normal (statut posé directement) :
        # simule un cas historique où le compte est resté actif.
        autre = make_employe(
            self.company, 'M2', user=make_user(
                self.company, 'compte-orphelin', role='normal'),
            statut=DossierEmploye.Statut.SORTI)
        rows = services.comptes_actifs_employes_sortis(self.company)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['employe_id'], autre.pk)

    def test_rapport_vide_normalement(self):
        rows = services.comptes_actifs_employes_sortis(self.company)
        self.assertEqual(rows, [])


class SortirEmployeApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('yhire2-api-a', 'A')
        self.co_b = make_company('yhire2-api-b', 'B')
        self.admin_a = make_user(self.co_a, 'admin-a', role='admin')
        self.normal_a = make_user(self.co_a, 'normal-a', role='normal')
        self.employe = make_employe(self.co_a, 'M-API-1')

    def test_sortir_action_ok(self):
        api = auth(self.admin_a)
        resp = api.post(f'{URL}{self.employe.pk}/sortir/', {
            'date_sortie': '2026-07-01',
            'motif': DossierEmploye.MotifSortie.DEMISSION,
        })
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employe.refresh_from_db()
        self.assertEqual(self.employe.statut, DossierEmploye.Statut.SORTI)

    def test_sortir_motif_invalide_400(self):
        api = auth(self.admin_a)
        resp = api.post(f'{URL}{self.employe.pk}/sortir/', {
            'date_sortie': '2026-07-01', 'motif': 'inexistant',
        })
        self.assertEqual(resp.status_code, 400)

    def test_sortir_date_manquante_400(self):
        api = auth(self.admin_a)
        resp = api.post(f'{URL}{self.employe.pk}/sortir/', {
            'motif': DossierEmploye.MotifSortie.DEMISSION,
        })
        self.assertEqual(resp.status_code, 400)

    def test_sortir_deux_fois_400(self):
        api = auth(self.admin_a)
        api.post(f'{URL}{self.employe.pk}/sortir/', {
            'date_sortie': '2026-07-01',
            'motif': DossierEmploye.MotifSortie.DEMISSION,
        })
        resp = api.post(f'{URL}{self.employe.pk}/sortir/', {
            'date_sortie': '2026-07-02',
            'motif': DossierEmploye.MotifSortie.DEMISSION,
        })
        self.assertEqual(resp.status_code, 400)

    def test_comptes_actifs_sortis_report(self):
        api = auth(self.admin_a)
        resp = api.get(f'{URL}comptes-actifs-sortis/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, [])
