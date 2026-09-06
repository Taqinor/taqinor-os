"""AUD721 — l'immuabilité du bulletin validé ne s'arrête plus à /admin/.

DÉFAUT (rouge avant ce correctif) : la garde de `BulletinPaie.save`/`delete`
(« ne dépend pas de la couche API ») ne s'applique QU'À un `instance.delete()`
Python.

* `BulletinPaieAdmin` / `LigneBulletinAdmin` n'avaient ni
  `has_delete_permission` ni `get_actions()` retirant l'action groupée
  « Supprimer les objets sélectionnés » — qui exécute un DELETE SQL EN MASSE
  sans jamais invoquer les surcharges Python : un bulletin VALIDÉ partait sans
  lever `BulletinVerrouille` ;
* `ProfilPaieAdmin` / `PeriodePaieAdmin` n'avaient aucune garde non plus, et
  `BulletinPaie` était en `on_delete=CASCADE` sur `profil` ET `periode` :
  supprimer l'un des deux depuis `/admin/` cascadait sur TOUS les bulletins,
  validés compris.

Après correctif : FK en PROTECT (la base refuse), `delete_selected` retiré des
quatre `ModelAdmin`, et `has_delete_permission` refuse sur une pièce figée.
"""
from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models import ProtectedError
from django.test import RequestFactory, TestCase

from authentication.models import Company
from apps.paie.admin import (
    BulletinPaieAdmin,
    LigneBulletinAdmin,
    PeriodePaieAdmin,
    ProfilPaieAdmin,
)
from apps.paie.models import BulletinPaie, LigneBulletin, PeriodePaie, ProfilPaie
from apps.paie.services import ensure_defaults, generer_bulletin, valider_bulletin
from apps.paie.tests.test_avantages import make_dossier, make_profil
from apps.rh.models import DossierEmploye  # noqa: F401  (registre app RH)

User = get_user_model()


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class BulletinValideAdminTests(TestCase):
    def setUp(self):
        self.co = make_company('aud721-paie')
        ensure_defaults(self.co)
        self.dossier = make_dossier(self.co, 'A721')
        self.profil = make_profil(self.co, self.dossier, Decimal('10000'))
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.bulletin = generer_bulletin(self.profil, self.periode)
        valider_bulletin(self.bulletin)
        self.bulletin.refresh_from_db()
        self.superuser = User.objects.create_superuser(
            username='aud721-admin', password='x', email='a@b.ma')
        self.superuser.company = self.co
        self.superuser.save(update_fields=['company'])
        self.request = RequestFactory().get('/admin/')
        self.request.user = self.superuser

    # ── L'action groupée (DELETE SQL en masse) est retirée ────────────────
    def test_delete_selected_retiree_des_quatre_admins(self):
        for classe, modele in (
                (BulletinPaieAdmin, BulletinPaie),
                (LigneBulletinAdmin, LigneBulletin),
                (ProfilPaieAdmin, ProfilPaie),
                (PeriodePaieAdmin, PeriodePaie)):
            model_admin = classe(modele, admin.site)
            self.assertNotIn(
                'delete_selected', model_admin.get_actions(self.request),
                f'{classe.__name__} expose encore la suppression en masse')

    # ── has_delete_permission ─────────────────────────────────────────────
    def test_bulletin_valide_non_supprimable_depuis_admin(self):
        model_admin = BulletinPaieAdmin(BulletinPaie, admin.site)
        self.assertFalse(
            model_admin.has_delete_permission(self.request, self.bulletin))

    def test_ligne_de_bulletin_valide_non_supprimable_depuis_admin(self):
        ligne = self.bulletin.lignes.first()
        self.assertIsNotNone(ligne)
        model_admin = LigneBulletinAdmin(LigneBulletin, admin.site)
        self.assertFalse(
            model_admin.has_delete_permission(self.request, ligne))

    def test_profil_et_periode_porteurs_de_bulletins_non_supprimables(self):
        self.assertFalse(
            ProfilPaieAdmin(ProfilPaie, admin.site)
            .has_delete_permission(self.request, self.profil))
        self.assertFalse(
            PeriodePaieAdmin(PeriodePaie, admin.site)
            .has_delete_permission(self.request, self.periode))

    def test_bulletin_brouillon_reste_supprimable(self):
        """Le durcissement ne fige QUE ce qui est validé."""
        periode2 = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=7)
        brouillon = generer_bulletin(self.profil, periode2)
        model_admin = BulletinPaieAdmin(BulletinPaie, admin.site)
        self.assertTrue(
            model_admin.has_delete_permission(self.request, brouillon))

    # ── PROTECT côté base : plus aucune cascade sur les bulletins ─────────
    def test_supprimer_la_periode_ne_cascade_plus_sur_les_bulletins(self):
        with self.assertRaises(ProtectedError):
            self.periode.delete()
        self.assertTrue(
            BulletinPaie.objects.filter(pk=self.bulletin.pk).exists())

    def test_supprimer_le_profil_ne_cascade_plus_sur_les_bulletins(self):
        with self.assertRaises(ProtectedError):
            self.profil.delete()
        self.assertTrue(
            BulletinPaie.objects.filter(pk=self.bulletin.pk).exists())

    def test_suppression_en_masse_du_queryset_est_bloquee_aussi(self):
        """Le chemin exact que l'action groupée /admin/ empruntait."""
        with self.assertRaises(ProtectedError):
            PeriodePaie.objects.filter(pk=self.periode.pk).delete()
        self.assertTrue(
            BulletinPaie.objects.filter(pk=self.bulletin.pk).exists())
