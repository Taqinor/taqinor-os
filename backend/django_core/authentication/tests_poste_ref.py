"""DC17 — référentiel ``CustomUser.poste`` (texte libre) → ``rh.Poste`` (FG160).

Couvre la migration de données réversible : dédup des intitulés distincts PAR
SOCIÉTÉ, isolation multi-tenant (jamais de fusion inter-sociétés), rattachement
de ``poste_ref`` au bon Poste, conservation INTACTE de la colonne texte legacy,
idempotence, et innocuité du sens inverse (détache les FK, ne supprime aucun
Poste, ne touche pas au texte).
"""
from django.test import TestCase

from authentication.models import Company, CustomUser
from authentication.poste_sync import backfill_poste_ref

from apps.rh.models import Poste


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, poste=''):
    return CustomUser.objects.create_user(
        username=username, password='x', company=company, poste=poste)


class BackfillPosteRefTests(TestCase):
    def setUp(self):
        self.co_a = make_company('pr-a', 'Société A')
        self.co_b = make_company('pr-b', 'Société B')

    # ── Dédup correcte ────────────────────────────────────────────────────────
    def test_dedup_distinct_strings_per_company(self):
        """Deux intitulés distincts → deux Postes ; un partagé → un seul Poste."""
        u1 = make_user(self.co_a, 'a1', 'Technicien')
        u2 = make_user(self.co_a, 'a2', 'Technicien')
        u3 = make_user(self.co_a, 'a3', 'Commercial')

        n = backfill_poste_ref(CustomUser, Poste)
        self.assertEqual(n, 3)

        # Un seul Poste « Technicien » + un « Commercial » pour la société A.
        self.assertEqual(Poste.objects.filter(company=self.co_a).count(), 2)
        u1.refresh_from_db()
        u2.refresh_from_db()
        u3.refresh_from_db()
        self.assertIsNotNone(u1.poste_ref_id)
        # Les deux « Technicien » pointent EXACTEMENT le même Poste.
        self.assertEqual(u1.poste_ref_id, u2.poste_ref_id)
        self.assertNotEqual(u1.poste_ref_id, u3.poste_ref_id)
        self.assertEqual(u1.poste_ref.intitule, 'Technicien')
        self.assertEqual(u3.poste_ref.intitule, 'Commercial')

    def test_dedup_case_and_whitespace_insensitive(self):
        """« Commercial » / « commercial » / «  Commercial  » → un seul Poste."""
        u1 = make_user(self.co_a, 'c1', 'Commercial')
        u2 = make_user(self.co_a, 'c2', 'commercial')
        u3 = make_user(self.co_a, 'c3', '  Commercial  ')

        backfill_poste_ref(CustomUser, Poste)

        self.assertEqual(Poste.objects.filter(company=self.co_a).count(), 1)
        u1.refresh_from_db()
        u2.refresh_from_db()
        u3.refresh_from_db()
        self.assertEqual(u1.poste_ref_id, u2.poste_ref_id)
        self.assertEqual(u1.poste_ref_id, u3.poste_ref_id)
        # L'intitulé stocké garde la casse de la 1re occurrence (sans espaces).
        self.assertEqual(u1.poste_ref.intitule, 'Commercial')

    def test_empty_poste_left_unlinked(self):
        """Un compte sans poste texte ne reçoit aucun ``poste_ref``."""
        u = make_user(self.co_a, 'empty', '')
        backfill_poste_ref(CustomUser, Poste)
        u.refresh_from_db()
        self.assertIsNone(u.poste_ref_id)
        self.assertEqual(Poste.objects.count(), 0)

    # ── Isolation multi-tenant (PER COMPANY) ──────────────────────────────────
    def test_per_company_isolation(self):
        """Le même intitulé dans deux sociétés crée DEUX Postes distincts."""
        ua = make_user(self.co_a, 'ta', 'Technicien')
        ub = make_user(self.co_b, 'tb', 'Technicien')

        backfill_poste_ref(CustomUser, Poste)

        self.assertEqual(Poste.objects.filter(company=self.co_a).count(), 1)
        self.assertEqual(Poste.objects.filter(company=self.co_b).count(), 1)
        ua.refresh_from_db()
        ub.refresh_from_db()
        # Jamais fusionnés : chaque compte pointe le Poste de SA société.
        self.assertNotEqual(ua.poste_ref_id, ub.poste_ref_id)
        self.assertEqual(ua.poste_ref.company_id, self.co_a.id)
        self.assertEqual(ub.poste_ref.company_id, self.co_b.id)

    # ── Réutilisation d'un Poste existant ─────────────────────────────────────
    def test_reuses_existing_poste(self):
        """Un Poste FG160 déjà présent est RÉUTILISÉ, pas dupliqué."""
        existant = Poste.objects.create(
            company=self.co_a, intitule='Chef de chantier')
        u = make_user(self.co_a, 'chef', 'chef de chantier')  # casse différente

        backfill_poste_ref(CustomUser, Poste)

        self.assertEqual(Poste.objects.filter(company=self.co_a).count(), 1)
        u.refresh_from_db()
        self.assertEqual(u.poste_ref_id, existant.id)

    # ── Idempotence ───────────────────────────────────────────────────────────
    def test_idempotent(self):
        """Un second passage ne crée aucun doublon et ne rebascule rien."""
        make_user(self.co_a, 'a1', 'Technicien')
        make_user(self.co_a, 'a2', 'Technicien')

        first = backfill_poste_ref(CustomUser, Poste)
        self.assertEqual(first, 2)
        second = backfill_poste_ref(CustomUser, Poste)
        self.assertEqual(second, 0)  # déjà rattachés
        self.assertEqual(Poste.objects.filter(company=self.co_a).count(), 1)

    # ── Colonne texte legacy intacte ──────────────────────────────────────────
    def test_legacy_text_column_untouched(self):
        """La colonne ``poste`` (texte libre) n'est jamais modifiée."""
        u = make_user(self.co_a, 'a1', 'Technicien pose')
        backfill_poste_ref(CustomUser, Poste)
        u.refresh_from_db()
        self.assertEqual(u.poste, 'Technicien pose')

    # ── Sens inverse de la migration (réversibilité) ──────────────────────────
    def test_reverse_detaches_without_destroying(self):
        """Le détachement (sens inverse) remet ``poste_ref=None`` mais conserve
        les Postes ET le texte legacy."""
        u = make_user(self.co_a, 'a1', 'Technicien')
        backfill_poste_ref(CustomUser, Poste)
        u.refresh_from_db()
        self.assertIsNotNone(u.poste_ref_id)

        # Reproduit la logique du sens inverse de 0013 (unbackfill).
        CustomUser.objects.exclude(poste_ref__isnull=True).update(
            poste_ref=None)

        u.refresh_from_db()
        self.assertIsNone(u.poste_ref_id)        # FK détaché
        self.assertEqual(u.poste, 'Technicien')   # texte legacy préservé
        # Les Postes créés ne sont PAS supprimés (peuvent servir ailleurs).
        self.assertEqual(Poste.objects.filter(company=self.co_a).count(), 1)


class PosteRefFkBehaviourTests(TestCase):
    """Le FK ``poste_ref`` est nullable et se détache (SET_NULL) à la suppression
    du Poste — additif, jamais de cascade sur le compte."""

    def setUp(self):
        self.co = make_company('pr-fk', 'Société FK')

    def test_set_null_on_poste_delete(self):
        poste = Poste.objects.create(company=self.co, intitule='Technicien')
        u = make_user(self.co, 'fk1', 'Technicien')
        u.poste_ref = poste
        u.save(update_fields=['poste_ref'])

        poste.delete()

        u.refresh_from_db()
        self.assertIsNone(u.poste_ref_id)  # compte conservé, FK détaché
        self.assertTrue(CustomUser.objects.filter(pk=u.pk).exists())

    def test_related_name_label_prefixed(self):
        """L'accès inverse est ``Poste.auth_users`` (préfixé, sans collision avec
        ``Poste.employes`` de DossierEmploye)."""
        poste = Poste.objects.create(company=self.co, intitule='Commercial')
        u = make_user(self.co, 'fk2', 'Commercial')
        u.poste_ref = poste
        u.save(update_fields=['poste_ref'])
        self.assertEqual(list(poste.auth_users.all()), [u])
