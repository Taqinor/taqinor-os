"""Tests ZPAI4 — Bulletin d'annulation / reprise (refund payslip négatif).

Couvre :
* ``creer_bulletin_annulation`` — recopie chaque ligne du bulletin d'origine à
  montant OPPOSÉ, liée via ``rectifie``, l'origine reste intacte/figée.
* Le cumul annuel net revient à 0 une fois l'annulation validée.
* Refuse une société différente / une période cible clôturée.
* Isolation tenant sur l'action API.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser as User
from apps.paie.models import BulletinPaie, PeriodePaie, ProfilPaie
from apps.paie.services import (
    cloturer_periode_paie,
    creer_bulletin_annulation,
    ensure_defaults,
    generer_bulletin,
    recalculer_cumul_annuel,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class BulletinAnnulationServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('annul')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='AN1', nom='Test', prenom='Annul')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), affilie_cnss=True, affilie_amo=True)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.periode_suivante = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=7)
        self.origine = generer_bulletin(self.profil, self.periode)
        valider_bulletin(self.origine)

    def test_annulation_lignes_opposees(self):
        annulation = creer_bulletin_annulation(
            self.origine, self.periode_suivante)
        self.assertEqual(
            annulation.type_bulletin, BulletinPaie.TYPE_ANNULATION)
        self.assertEqual(annulation.rectifie_id, self.origine.id)
        self.assertEqual(annulation.net_a_payer, -self.origine.net_a_payer)
        self.assertEqual(annulation.brut, -self.origine.brut)
        lignes_origine = list(self.origine.lignes.order_by('id'))
        lignes_annulation = list(annulation.lignes.order_by('id'))
        self.assertEqual(len(lignes_origine), len(lignes_annulation))
        for lo, la in zip(lignes_origine, lignes_annulation):
            self.assertEqual(la.code, lo.code)
            self.assertEqual(la.montant, -lo.montant)
        # L'origine reste intacte/figée.
        self.origine.refresh_from_db()
        self.assertEqual(self.origine.statut, BulletinPaie.STATUT_VALIDE)
        self.assertNotEqual(self.origine.net_a_payer, Decimal('0'))

    def test_cumul_annuel_revient_a_zero(self):
        annulation = creer_bulletin_annulation(
            self.origine, self.periode_suivante)
        valider_bulletin(annulation)
        cumul = recalculer_cumul_annuel(self.profil, 2026)
        self.assertEqual(cumul.net_a_payer, Decimal('0.00'))

    def test_refuse_societe_differente(self):
        autre_co = make_company('annul-autre')
        ensure_defaults(autre_co)
        autre_periode = PeriodePaie.objects.create(
            company=autre_co, annee=2026, mois=7)
        with self.assertRaises(ValueError):
            creer_bulletin_annulation(self.origine, autre_periode)

    def test_refuse_periode_cible_cloturee(self):
        cloturer_periode_paie(self.periode_suivante)
        with self.assertRaises(ValueError):
            creer_bulletin_annulation(self.origine, self.periode_suivante)

    def test_origine_reste_figee_apres_annulation(self):
        creer_bulletin_annulation(self.origine, self.periode_suivante)
        with self.assertRaises(BulletinPaie.BulletinVerrouille):
            self.origine.brut = Decimal('1')
            self.origine.save(update_fields=['brut'])

    def test_personnes_a_charge_reportees_sans_negation(self):
        """AUD707 — un salarié avec charge de famille peut être extourné.

        ``personnes_a_charge`` est un ``PositiveSmallIntegerField`` (CHECK
        >= 0) : le néguer avec les autres ``SNAPSHOT_FIELDS`` levait une
        ``IntegrityError`` et bloquait le SEUL mécanisme de correction d'un
        bulletin validé pour tout salarié ayant des personnes à charge.
        """
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='AN-PAC', nom='Test', prenom='Charge')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), affilie_cnss=True, affilie_amo=True)
        origine = generer_bulletin(profil, self.periode, personnes_a_charge=2)
        valider_bulletin(origine)
        self.assertEqual(origine.personnes_a_charge, 2)

        annulation = creer_bulletin_annulation(origine, self.periode_suivante)
        # Reporté à l'identique (jamais -2), et les montants restent opposés.
        self.assertEqual(annulation.personnes_a_charge, 2)
        self.assertEqual(annulation.net_a_payer, -origine.net_a_payer)
        annulation.refresh_from_db()
        self.assertEqual(annulation.personnes_a_charge, 2)


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class BulletinAnnulationApiTests(TestCase):
    BASE = '/api/django/paie/bulletins/'

    def setUp(self):
        self.co = make_company('annul-api')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='AN2', nom='Test', prenom='Api')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('8000'), affilie_cnss=True, affilie_amo=True)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.periode_suivante = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=7)
        self.origine = generer_bulletin(self.profil, self.periode)
        valider_bulletin(self.origine)
        self.user = make_user(self.co, 'annul-api-user')

    def test_action_annuler_cree_bulletin(self):
        resp = auth(self.user).post(
            f'{self.BASE}{self.origine.id}/annuler/',
            {'periode_cible': self.periode_suivante.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            resp.data['type_bulletin'], BulletinPaie.TYPE_ANNULATION)

    def test_action_annuler_periode_manquante(self):
        resp = auth(self.user).post(
            f'{self.BASE}{self.origine.id}/annuler/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_action_annuler_isolation_tenant(self):
        autre_co = make_company('annul-api-autre')
        ensure_defaults(autre_co)
        autre_periode = PeriodePaie.objects.create(
            company=autre_co, annee=2026, mois=7)
        resp = auth(self.user).post(
            f'{self.BASE}{self.origine.id}/annuler/',
            {'periode_cible': autre_periode.id}, format='json')
        self.assertEqual(resp.status_code, 404)
