# -*- coding: utf-8 -*-
"""ASEC25 — ``SEC_COMPTE_DEMO_ACTIF`` tourne quel que soit ``settings.DEBUG``.

Avant : ``regles_securite.py`` rendait ``[]`` sous ``DEBUG=True`` — et la prod
a tourné en DEBUG (C-ASEC-029), donc la règle était muette là où elle devait
parler. Le critère est désormais ``Company.est_demo`` (jamais DEBUG ni le
slug) : une société démo avec un compte actif lève la violation dans les deux
modes, la société réelle (sans compte de seed) jamais.

Test-du-test : remettre ``if settings.DEBUG: return []`` ⇒
``test_debug_true_violation_levee`` échoue.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.ventes.coherence.moteur import _Ctx
from apps.ventes.coherence.registre import REGISTRE, charger_regles
from authentication.models import Company

User = get_user_model()


class RegleCompteDemoTests(TestCase):

    def setUp(self):
        charger_regles()
        self.demo = Company.objects.create(
            nom='Démo ASEC25', slug='asec25-demo', est_demo=True)
        self.reelle = Company.objects.create(
            nom='Réelle ASEC25', slug='asec25-reelle')
        self.compte_demo = User.objects.create_user(
            username='demo_admin_full', password='x',
            role_legacy='responsable', company=self.demo, is_active=True)
        User.objects.create_user(
            username='asec25_inactif', password='x',
            role_legacy='responsable', company=self.demo, is_active=False)
        User.objects.create_user(
            username='asec25_vrai', password='x',
            role_legacy='responsable', company=self.reelle, is_active=True)

    def _run(self, company):
        r = REGISTRE['SEC_COMPTE_DEMO_ACTIF']
        return r.check(r, company, _Ctx(company))

    def _verifie_violation_demo(self):
        out = self._run(self.demo)
        self.assertEqual([v.object_id for v in out], [self.compte_demo.pk])
        self.assertEqual(out[0].object_type, 'utilisateur')
        self.assertEqual(out[0].reference, 'demo_admin_full')
        self.assertEqual(out[0].company_id, self.demo.pk)

    @override_settings(DEBUG=True)
    def test_debug_true_violation_levee(self):
        self._verifie_violation_demo()

    @override_settings(DEBUG=False)
    def test_debug_false_violation_levee(self):
        self._verifie_violation_demo()

    def test_societe_reelle_sans_violation(self):
        for debug in (True, False):
            with self.settings(DEBUG=debug):
                self.assertEqual(self._run(self.reelle), [])
