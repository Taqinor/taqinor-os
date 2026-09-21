"""Tests YHIRE7 — Propagation des effets des sanctions disciplinaires.

Couvre :
* Une mise à pied NOTIFIEE avec ``duree_jours`` crée UNE ``DemandeConge``
  déjà VALIDÉE, non rémunérée, ne déduisant pas le solde, sur la bonne
  période (idempotent : re-propager ne double pas).
* L'annulation de la sanction (contestation gagnée) annule l'absence liée.
* Un LICENCIEMENT sans confirmation explicite ne déclenche AUCUNE sortie
  (409) ; avec confirmation, déclenche ``sortir_employe`` (statut SORTI).
* API : création directe NOTIFIEE propage, ``annuler`` retire l'effet,
  ``declencher-sortie`` respecte la confirmation explicite.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import services
from apps.rh.models import DemandeConge, DossierEmploye, Sanction, TypeAbsence

User = get_user_model()

URL = '/api/django/rh/sanctions/'


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


def seed_type_map(company):
    return TypeAbsence.objects.create(
        company=company, code='MAP', libelle='Mise à pied disciplinaire',
        decompte_jours_ouvres=False, deduit_solde=False, remunere=False,
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class PropagerEffetsSanctionServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('yhire7-a', 'A')
        self.employe = make_employe(self.company, 'M1')
        seed_type_map(self.company)

    def test_mise_a_pied_cree_absence_non_remuneree(self):
        sanction = Sanction.objects.create(
            company=self.company, employe=self.employe,
            type_sanction=Sanction.TypeSanction.MISE_A_PIED,
            duree_jours=3,
            date_notification=timezone.localdate(),
            statut=Sanction.Statut.NOTIFIEE,
        )
        demande = services.propager_effets_sanction_notification(sanction)
        self.assertIsNotNone(demande)
        self.assertEqual(demande.statut, DemandeConge.Statut.VALIDEE)
        self.assertEqual(demande.jours, 3)
        self.assertFalse(demande.type_absence.remunere)
        self.assertFalse(demande.type_absence.deduit_solde)

    def test_idempotent_ne_double_pas(self):
        sanction = Sanction.objects.create(
            company=self.company, employe=self.employe,
            type_sanction=Sanction.TypeSanction.MISE_A_PIED,
            duree_jours=2,
            date_notification=timezone.localdate(),
            statut=Sanction.Statut.NOTIFIEE,
        )
        services.propager_effets_sanction_notification(sanction)
        services.propager_effets_sanction_notification(sanction)
        self.assertEqual(
            DemandeConge.objects.filter(employe=self.employe).count(), 1)

    def test_autre_type_sanction_aucun_effet(self):
        sanction = Sanction.objects.create(
            company=self.company, employe=self.employe,
            type_sanction=Sanction.TypeSanction.AVERTISSEMENT,
            statut=Sanction.Statut.NOTIFIEE,
        )
        services.propager_effets_sanction_notification(sanction)
        self.assertEqual(
            DemandeConge.objects.filter(employe=self.employe).count(), 0)

    def test_annulation_retire_effet(self):
        sanction = Sanction.objects.create(
            company=self.company, employe=self.employe,
            type_sanction=Sanction.TypeSanction.MISE_A_PIED,
            duree_jours=1,
            date_notification=timezone.localdate(),
            statut=Sanction.Statut.NOTIFIEE,
        )
        services.propager_effets_sanction_notification(sanction)
        services.propager_effets_sanction_annulation(sanction)
        demande = DemandeConge.objects.get(employe=self.employe)
        self.assertEqual(demande.statut, DemandeConge.Statut.ANNULEE)


class LicenciementDeclencheSortieTests(TestCase):
    def setUp(self):
        self.company = make_company('yhire7-b', 'B')
        self.employe = make_employe(self.company, 'M2')

    def test_sans_confirmation_leve_exception(self):
        sanction = Sanction.objects.create(
            company=self.company, employe=self.employe,
            type_sanction=Sanction.TypeSanction.LICENCIEMENT,
            date_notification=timezone.localdate(),
            statut=Sanction.Statut.NOTIFIEE,
        )
        with self.assertRaises(services.SortieNonConfirmeeError):
            services.proposer_sortie_pour_licenciement(sanction)
        self.employe.refresh_from_db()
        self.assertNotEqual(self.employe.statut, DossierEmploye.Statut.SORTI)

    def test_avec_confirmation_declenche_sortie(self):
        sanction = Sanction.objects.create(
            company=self.company, employe=self.employe,
            type_sanction=Sanction.TypeSanction.LICENCIEMENT,
            date_notification=timezone.localdate(),
            statut=Sanction.Statut.NOTIFIEE,
        )
        services.proposer_sortie_pour_licenciement(sanction, confirmer=True)
        self.employe.refresh_from_db()
        self.assertEqual(self.employe.statut, DossierEmploye.Statut.SORTI)
        self.assertEqual(
            self.employe.motif_sortie, DossierEmploye.MotifSortie.LICENCIEMENT)


class SanctionApiTests(TestCase):
    def setUp(self):
        self.company = make_company('yhire7-api', 'API')
        self.admin = make_user(self.company, 'admin-yhire7', role='admin')
        self.employe = make_employe(self.company, 'M3')
        seed_type_map(self.company)

    def test_creation_notifiee_propage(self):
        api = auth(self.admin)
        resp = api.post(URL, {
            'employe': self.employe.pk,
            'type_sanction': Sanction.TypeSanction.MISE_A_PIED,
            'duree_jours': 2,
            'date_notification': timezone.localdate().isoformat(),
            'statut': Sanction.Statut.NOTIFIEE,
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            DemandeConge.objects.filter(employe=self.employe).count(), 1)

    def test_annuler_retire_effet_api(self):
        sanction = Sanction.objects.create(
            company=self.company, employe=self.employe,
            type_sanction=Sanction.TypeSanction.MISE_A_PIED,
            duree_jours=1, date_notification=timezone.localdate(),
            statut=Sanction.Statut.NOTIFIEE,
        )
        services.propager_effets_sanction_notification(sanction)
        api = auth(self.admin)
        resp = api.post(f'{URL}{sanction.pk}/annuler/')
        self.assertEqual(resp.status_code, 200)
        demande = DemandeConge.objects.get(employe=self.employe)
        self.assertEqual(demande.statut, DemandeConge.Statut.ANNULEE)

    def test_declencher_sortie_sans_confirmer_409(self):
        sanction = Sanction.objects.create(
            company=self.company, employe=self.employe,
            type_sanction=Sanction.TypeSanction.LICENCIEMENT,
            date_notification=timezone.localdate(),
            statut=Sanction.Statut.NOTIFIEE,
        )
        api = auth(self.admin)
        resp = api.post(f'{URL}{sanction.pk}/declencher-sortie/', {})
        self.assertEqual(resp.status_code, 409)
        self.employe.refresh_from_db()
        self.assertNotEqual(self.employe.statut, DossierEmploye.Statut.SORTI)

    def test_declencher_sortie_avec_confirmer_200(self):
        sanction = Sanction.objects.create(
            company=self.company, employe=self.employe,
            type_sanction=Sanction.TypeSanction.LICENCIEMENT,
            date_notification=timezone.localdate(),
            statut=Sanction.Statut.NOTIFIEE,
        )
        api = auth(self.admin)
        resp = api.post(
            f'{URL}{sanction.pk}/declencher-sortie/', {'confirmer': True})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employe.refresh_from_db()
        self.assertEqual(self.employe.statut, DossierEmploye.Statut.SORTI)
