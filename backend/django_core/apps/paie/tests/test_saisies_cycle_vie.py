"""Tests ZPAI6 — Cycle de vie explicite des saisies-arrêt.

Couvre :
* ``statut`` bascule automatiquement ``en_cours`` → ``soldee`` à
  l'application d'une retenue qui épuise le solde.
* ``annuler_saisie_arret`` — stoppe les retenues futures (``actif=False``)
  sans effacer l'historique (``montant_retenu`` intact) ; refuse une saisie
  déjà soldée ; idempotent sur une saisie déjà annulée.
* ``saisies_arret_du_bulletin`` — relie les lignes SAISIE du bulletin à leur
  saisie d'origine.
* API : action ``saisies/<id>/annuler/`` + isolation tenant.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser as User
from apps.paie.models import PeriodePaie, ProfilPaie, SaisieArret
from apps.paie.services import (
    annuler_saisie_arret,
    ensure_defaults,
    generer_bulletin,
    saisies_arret_du_bulletin,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class SaisieCycleVieServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('sa-cycle')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='SC1', nom='Test', prenom='Cycle')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), affilie_cnss=True, affilie_amo=True)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        # Petit montant_total pour qu'une seule retenue l'épuise.
        self.saisie = SaisieArret.objects.create(
            company=self.co, profil=self.profil, montant_total=Decimal('300'),
            montant_echeance=Decimal('300'), date_debut=date(2026, 6, 1),
            creancier='Trésor')

    def test_statut_defaut_en_cours(self):
        self.assertEqual(self.saisie.statut, SaisieArret.STATUT_EN_COURS)

    def test_bascule_soldee_a_epuisement(self):
        bulletin = generer_bulletin(self.profil, self.periode)
        valider_bulletin(bulletin)
        self.saisie.refresh_from_db()
        self.assertTrue(self.saisie.soldee)
        self.assertEqual(self.saisie.statut, SaisieArret.STATUT_SOLDEE)

    def test_annulation_stoppe_sans_effacer_historique(self):
        # Une saisie plus grande pour qu'elle ne se solde pas en un mois.
        saisie2 = SaisieArret.objects.create(
            company=self.co, profil=self.profil, montant_total=Decimal('5000'),
            montant_echeance=Decimal('100'), date_debut=date(2026, 6, 1),
            creancier='Banque')
        bulletin = generer_bulletin(self.profil, self.periode)
        valider_bulletin(bulletin)
        saisie2.refresh_from_db()
        retenu_avant = saisie2.montant_retenu
        self.assertGreater(retenu_avant, Decimal('0'))
        annuler_saisie_arret(saisie2, motif='Accord amiable')
        saisie2.refresh_from_db()
        self.assertEqual(saisie2.statut, SaisieArret.STATUT_ANNULEE)
        self.assertFalse(saisie2.actif)
        self.assertEqual(saisie2.motif_annulation, 'Accord amiable')
        self.assertIsNotNone(saisie2.date_annulation)
        # Historique intact.
        self.assertEqual(saisie2.montant_retenu, retenu_avant)

        # Période suivante : la saisie annulée ne sert plus de retenue.
        periode2 = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=7)
        bulletin2 = generer_bulletin(self.profil, periode2)
        valider_bulletin(bulletin2)
        saisie2.refresh_from_db()
        self.assertEqual(saisie2.montant_retenu, retenu_avant)

    def test_annulation_idempotente(self):
        annuler_saisie_arret(self.saisie)
        self.saisie.refresh_from_db()
        premiere_date = self.saisie.date_annulation
        annuler_saisie_arret(self.saisie)
        self.saisie.refresh_from_db()
        self.assertEqual(self.saisie.date_annulation, premiere_date)

    def test_refuse_annuler_saisie_soldee(self):
        bulletin = generer_bulletin(self.profil, self.periode)
        valider_bulletin(bulletin)
        self.saisie.refresh_from_db()
        self.assertEqual(self.saisie.statut, SaisieArret.STATUT_SOLDEE)
        with self.assertRaises(ValueError):
            annuler_saisie_arret(self.saisie)

    def test_saisies_arret_du_bulletin(self):
        bulletin = generer_bulletin(self.profil, self.periode)
        valider_bulletin(bulletin)
        liens = saisies_arret_du_bulletin(bulletin)
        self.assertEqual(len(liens), 1)
        self.assertEqual(liens[0]['saisie'].id, self.saisie.id)
        self.assertEqual(liens[0]['montant'], Decimal('300.00'))

    def test_saisies_arret_du_bulletin_vide_sans_saisie(self):
        self.saisie.delete()
        bulletin = generer_bulletin(self.profil, self.periode)
        self.assertEqual(saisies_arret_du_bulletin(bulletin), [])


class SaisieCycleVieApiTests(TestCase):
    BASE = '/api/django/paie/saisies/'

    def setUp(self):
        self.co = make_company('sa-cycle-api')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='SC2', nom='Test', prenom='Api')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'))
        self.saisie = SaisieArret.objects.create(
            company=self.co, profil=self.profil, montant_total=Decimal('300'),
            date_debut=date(2026, 6, 1), creancier='Trésor')
        self.user = make_user(self.co, 'sa-cycle-api-user')

    def test_action_annuler(self):
        resp = auth(self.user).post(
            f'{self.BASE}{self.saisie.id}/annuler/',
            {'motif': 'Décision judiciaire levée'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], SaisieArret.STATUT_ANNULEE)
        self.assertFalse(resp.data['actif'])

    def test_isolation_tenant(self):
        autre_co = make_company('sa-cycle-api-autre')
        autre_user = make_user(autre_co, 'sa-cycle-api-autre-user')
        resp = auth(autre_user).post(
            f'{self.BASE}{self.saisie.id}/annuler/', {}, format='json')
        self.assertEqual(resp.status_code, 404)
