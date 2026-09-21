"""NTMKT23 — Bibliothèque de blocs de contenu réutilisables.

L'insertion se fait par COPIE côté éditeur (le corps de la campagne porte le
fragment, pas une référence) : ce test verrouille l'invariant côté données —
modifier le bloc source ne change JAMAIS le corps d'une campagne écrite.
"""
from django.db import IntegrityError, transaction
from django.test import TestCase

from authentication.models import Company

from apps.marketing.models import BlocContenu, Campagne


class BlocContenuTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='ntmkt23', nom='NTMKT23')
        self.bloc = BlocContenu.objects.create(
            company=self.co, nom='CTA prendre RDV',
            type_bloc=BlocContenu.Type.CTA,
            contenu='<a href="#">Prendre RDV</a>')

    def test_le_bloc_est_scope_a_sa_societe(self):
        autre = Company.objects.create(slug='ntmkt23b', nom='Autre')
        self.assertFalse(
            BlocContenu.objects.filter(company=autre).exists())
        # Le même nom est libre dans une AUTRE société.
        BlocContenu.objects.create(
            company=autre, nom='CTA prendre RDV', contenu='autre')
        self.assertEqual(BlocContenu.objects.count(), 2)

    def test_nom_unique_par_societe(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                BlocContenu.objects.create(
                    company=self.co, nom='CTA prendre RDV', contenu='doublon')

    def test_modifier_le_bloc_ne_retro_modifie_pas_les_campagnes(self):
        corps = f'Bonjour\n{self.bloc.contenu}'
        c1 = Campagne.objects.create(company=self.co, nom='Promo 1',
                                     corps=corps)
        c2 = Campagne.objects.create(company=self.co, nom='Promo 2',
                                     corps=corps)
        self.bloc.contenu = '<a href="#">NOUVEAU CTA</a>'
        self.bloc.save(update_fields=['contenu'])
        c1.refresh_from_db()
        c2.refresh_from_db()
        self.assertIn('Prendre RDV', c1.corps)
        self.assertIn('Prendre RDV', c2.corps)
        self.assertNotIn('NOUVEAU CTA', c1.corps)
