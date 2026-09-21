"""Tests PAIE17 — Bulletin de paie matérialisé + lignes (snapshot immuable).

Couvre :
* ``generer_bulletin`` — matérialise le snapshot (montants + lignes) depuis
  ``calculer_bulletin`` ; recalcule un bulletin BROUILLON ; refuse de régénérer
  un bulletin VALIDÉ.
* ``valider_bulletin`` — fige le bulletin (``brouillon → valide``,
  ``date_validation`` posée) ; re-valider = no-op.
* IMMUTABILITÉ (garde modèle) : après validation, ``save`` d'un montant,
  ``delete`` du bulletin, et création/modification/suppression d'une ligne
  lèvent ``BulletinVerrouille``.
* API : ``generer`` crée/recalcule, ``valider`` fige, société posée côté
  serveur, isolation, palier paie.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.paie.models import (
    BulletinPaie,
    LigneBulletin,
    PeriodePaie,
)
from apps.paie.services import (
    ensure_defaults,
    generer_bulletin,
    valider_bulletin,
)
from apps.paie.tests.test_avantages import make_dossier, make_profil
from apps.rh.models import DossierEmploye  # noqa: F401  (registre app RH)

User = get_user_model()


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


# ── Service : génération & validation ──────────────────────────────────────

class GenererBulletinTests(TestCase):
    def setUp(self):
        self.co = make_company('bp-gen')
        ensure_defaults(self.co)
        self.dossier = make_dossier(self.co, 'BP1')
        self.profil = make_profil(self.co, self.dossier, Decimal('10000'))
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def test_genere_snapshot_et_lignes(self):
        bulletin = generer_bulletin(self.profil, self.periode)
        self.assertEqual(bulletin.statut, BulletinPaie.STATUT_BROUILLON)
        self.assertEqual(bulletin.company, self.co)
        self.assertEqual(bulletin.brut, Decimal('10000.00'))
        self.assertEqual(bulletin.cnss_patronale, Decimal('538.80'))
        self.assertEqual(bulletin.amo_patronale, Decimal('226.00'))
        # Au moins la ligne Salaire de base.
        self.assertTrue(bulletin.lignes.filter(code='SB').exists())

    def test_un_seul_bulletin_par_periode_profil(self):
        b1 = generer_bulletin(self.profil, self.periode)
        b2 = generer_bulletin(self.profil, self.periode)
        self.assertEqual(b1.pk, b2.pk)
        self.assertEqual(
            BulletinPaie.objects.filter(
                periode=self.periode, profil=self.profil).count(), 1)

    def test_regenere_brouillon_remplace_lignes(self):
        bulletin = generer_bulletin(self.profil, self.periode)
        n1 = bulletin.lignes.count()
        bulletin2 = generer_bulletin(self.profil, self.periode)
        # Pas de doublon de lignes après recalcul.
        self.assertEqual(bulletin2.lignes.count(), n1)

    def test_validation_fige_et_date(self):
        bulletin = generer_bulletin(self.profil, self.periode)
        valider_bulletin(bulletin)
        bulletin.refresh_from_db()
        self.assertEqual(bulletin.statut, BulletinPaie.STATUT_VALIDE)
        self.assertIsNotNone(bulletin.date_validation)

    def test_revalidation_noop(self):
        bulletin = generer_bulletin(self.profil, self.periode)
        valider_bulletin(bulletin)
        d1 = bulletin.date_validation
        valider_bulletin(bulletin)
        self.assertEqual(bulletin.date_validation, d1)

    def test_regenerer_valide_interdit(self):
        bulletin = generer_bulletin(self.profil, self.periode)
        valider_bulletin(bulletin)
        with self.assertRaises(BulletinPaie.BulletinVerrouille):
            generer_bulletin(self.profil, self.periode)


# ── Immuabilité (garde modèle) ─────────────────────────────────────────────

class ImmuabiliteTests(TestCase):
    def setUp(self):
        self.co = make_company('bp-imm')
        ensure_defaults(self.co)
        self.dossier = make_dossier(self.co, 'IMM1')
        self.profil = make_profil(self.co, self.dossier, Decimal('10000'))
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.bulletin = generer_bulletin(self.profil, self.periode)
        valider_bulletin(self.bulletin)
        self.bulletin.refresh_from_db()

    def test_save_montant_apres_validation_interdit(self):
        self.bulletin.brut = Decimal('99999.00')
        with self.assertRaises(BulletinPaie.BulletinVerrouille):
            self.bulletin.save()

    def test_save_partiel_montant_apres_validation_interdit(self):
        self.bulletin.net_a_payer = Decimal('1.00')
        with self.assertRaises(BulletinPaie.BulletinVerrouille):
            self.bulletin.save(update_fields=['net_a_payer'])

    def test_delete_bulletin_valide_interdit(self):
        with self.assertRaises(BulletinPaie.BulletinVerrouille):
            self.bulletin.delete()

    def test_modifier_ligne_apres_validation_interdit(self):
        ligne = self.bulletin.lignes.first()
        ligne.montant = Decimal('0.01')
        with self.assertRaises(BulletinPaie.BulletinVerrouille):
            ligne.save()

    def test_supprimer_ligne_apres_validation_interdit(self):
        ligne = self.bulletin.lignes.first()
        with self.assertRaises(BulletinPaie.BulletinVerrouille):
            ligne.delete()

    def test_creer_ligne_sur_bulletin_valide_interdit(self):
        with self.assertRaises(BulletinPaie.BulletinVerrouille):
            LigneBulletin.objects.create(
                company=self.co, bulletin=self.bulletin,
                code='X', libelle='Hack', montant=Decimal('1'))

    def test_brouillon_reste_modifiable(self):
        """Avant validation, le snapshot est librement modifiable/supprimable."""
        co2 = make_company('bp-brouillon')
        ensure_defaults(co2)
        dossier = make_dossier(co2, 'BR1')
        profil = make_profil(co2, dossier, Decimal('8000'))
        periode = PeriodePaie.objects.create(company=co2, annee=2026, mois=6)
        bulletin = generer_bulletin(profil, periode)
        bulletin.net_a_payer = Decimal('123.00')
        bulletin.save()  # autorisé en brouillon
        ligne = bulletin.lignes.first()
        ligne.montant = Decimal('5.00')
        ligne.save()  # autorisé en brouillon
        bulletin.delete()  # autorisé en brouillon


# ── API ────────────────────────────────────────────────────────────────────

def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class BulletinApiTests(TestCase):
    BASE = '/api/django/paie/bulletins/'

    def setUp(self):
        self.co = make_company('bp-api')
        ensure_defaults(self.co)
        self.user = make_user(self.co, 'bp-api-user')
        self.dossier = make_dossier(self.co, 'API1')
        self.profil = make_profil(self.co, self.dossier, Decimal('10000'))
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def test_generer_cree_bulletin_scope_societe(self):
        resp = auth(self.user).post(
            self.BASE + 'generer/',
            {'periode': self.periode.id, 'profil': self.profil.id},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        obj = BulletinPaie.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co)
        self.assertEqual(obj.statut, 'brouillon')
        self.assertTrue(resp.data['lignes'])

    def test_generer_champs_manquants_400(self):
        resp = auth(self.user).post(self.BASE + 'generer/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_valider_fige_le_bulletin(self):
        bulletin = generer_bulletin(self.profil, self.periode)
        resp = auth(self.user).post(
            f'{self.BASE}{bulletin.id}/valider/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        bulletin.refresh_from_db()
        self.assertEqual(bulletin.statut, 'valide')

    def test_generer_apres_validation_400(self):
        bulletin = generer_bulletin(self.profil, self.periode)
        valider_bulletin(bulletin)
        resp = auth(self.user).post(
            self.BASE + 'generer/',
            {'periode': self.periode.id, 'profil': self.profil.id},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_role_normal_refuse(self):
        normal = make_user(self.co, 'bp-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)

    def test_list_isolation(self):
        generer_bulletin(self.profil, self.periode)
        co_b = make_company('bp-api-b')
        user_b = make_user(co_b, 'bp-api-userb')
        resp = auth(user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        rows = data['results'] if isinstance(data, dict) and 'results' in data else data
        self.assertEqual(len(rows), 0)
