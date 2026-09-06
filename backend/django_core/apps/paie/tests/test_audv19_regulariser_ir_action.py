"""AUDV19 (DRAFT165-77, XPAI2) — action `regulariser-ir` sur le bulletin.

`appliquer_regularisation_ir` existait déjà, testée en profondeur au niveau
service (`test_regularisation_ir.py`, incl. AUD709 — exonération de régime)
mais aucune vue ne l'exposait : un gestionnaire paie ne pouvait déclencher la
régularisation IR annuelle QUE via le shell Django. Ce fichier teste UNIQUEMENT
le câblage HTTP (permission, catch BulletinVerrouille, forme de la réponse) —
la logique de calcul elle-même reste couverte par `test_regularisation_ir.py`
(non dupliquée ici).

Run:
    python manage.py test apps.paie.tests.test_audv19_regulariser_ir_action -v 2
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.paie.models import BaremeIR, PeriodePaie, ProfilPaie, TrancheIR
from apps.paie.services import (
    ensure_defaults, generer_bulletin, valider_bulletin,
)
from apps.rh.models import DossierEmploye

User = get_user_model()

BASE = '/api/django/paie/bulletins/'


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


def make_user_role(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class RegulariserIrActionTests(TestCase):
    def setUp(self):
        self.co = make_company('audv19-co')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='AUDV19-1', nom='Nom', prenom='P')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('8000'),
            affilie_cnss=True, affilie_amo=True)
        for mois in range(1, 12):
            periode = PeriodePaie.objects.create(
                company=self.co, annee=2026, mois=mois)
            b = generer_bulletin(self.profil, periode)
            valider_bulletin(b)
        self._durcir_bareme_mi_annee()
        self.periode_dec = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=12)
        self.bulletin_dec = generer_bulletin(self.profil, self.periode_dec)

    def _durcir_bareme_mi_annee(self):
        """Même levier légitime que `test_regularisation_ir.py` : un barème
        IR plus sévère en vigueur à mi-année produit un delta non nul SANS
        jamais réécrire un bulletin déjà validé (immuabilité PAIE17)."""
        bareme = BaremeIR.objects.create(
            company=self.co, date_effet=date(2026, 6, 1),
            libelle='Barème IR 2026 (révisé, AUDV19)')
        tranches = [
            (Decimal('0'), Decimal('2500'), Decimal('0'), Decimal('0')),
            (Decimal('2500.01'), Decimal('4166.67'),
             Decimal('15'), Decimal('300')),
            (Decimal('4166.68'), Decimal('5000'),
             Decimal('25'), Decimal('800')),
            (Decimal('5000.01'), Decimal('6666.67'),
             Decimal('35'), Decimal('1400')),
            (Decimal('6666.68'), Decimal('15000'),
             Decimal('40'), Decimal('1700')),
            (Decimal('15000.01'), None, Decimal('42'), Decimal('2400')),
        ]
        for ordre, (bmin, bmax, taux, somme) in enumerate(tranches, start=1):
            TrancheIR.objects.create(
                company=self.co, bareme=bareme, borne_min=bmin,
                borne_max=bmax, taux=taux, somme_a_deduire=somme,
                ordre=ordre)

    def test_refuse_sans_paie_gerer(self):
        user = make_user_role(self.co, 'audv19-lecture', ['paie_voir'])
        resp = auth(user).post(
            f'{BASE}{self.bulletin_dec.id}/regulariser-ir/', {}, format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(
            self.bulletin_dec.lignes.filter(code='IR-REGUL').exists())

    def test_applique_et_renvoie_le_delta(self):
        user = make_user_role(self.co, 'audv19-gerer', ['paie_gerer'])
        resp = auth(user).post(
            f'{BASE}{self.bulletin_dec.id}/regulariser-ir/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('regularisation_ir_delta', resp.data)
        delta = Decimal(resp.data['regularisation_ir_delta'])
        self.assertNotEqual(delta, Decimal('0'))
        self.bulletin_dec.refresh_from_db()
        ligne = self.bulletin_dec.lignes.get(code='IR-REGUL')
        self.assertEqual(ligne.montant, abs(delta))
        # La réponse sérialise le bulletin À JOUR (ir/net_a_payer post-delta).
        self.assertEqual(
            Decimal(str(resp.data['ir'])), self.bulletin_dec.ir)

    def test_refuse_sur_bulletin_valide(self):
        valider_bulletin(self.bulletin_dec)
        user = make_user_role(self.co, 'audv19-gerer2', ['paie_gerer'])
        resp = auth(user).post(
            f'{BASE}{self.bulletin_dec.id}/regulariser-ir/', {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('detail', resp.data)

    def test_idempotent_sur_deux_appels(self):
        user = make_user_role(self.co, 'audv19-gerer3', ['paie_gerer'])
        auth(user).post(
            f'{BASE}{self.bulletin_dec.id}/regulariser-ir/', {}, format='json')
        auth(user).post(
            f'{BASE}{self.bulletin_dec.id}/regulariser-ir/', {}, format='json')
        self.assertEqual(
            self.bulletin_dec.lignes.filter(code='IR-REGUL').count(), 1)
