"""Tests XACC17 — Table de taux de change + contre-valeur MAD au grand livre.

Couvre : créer une facture EUR sans taux applique le taux du jour de la
table, la contre-valeur MAD au taux applicable, le repli 1:1 sans table
(comportement actuel intact), et la règle « never snap » (un taux SAISI
n'est jamais écrasé par un feed).
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import TauxDevise


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TauxDeviseServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc17-svc', 'XACC17 Svc')

    def test_enregistrer_taux_manuel(self):
        taux = services.enregistrer_taux_devise(
            self.co, devise='EUR', date_taux=date(2026, 6, 1),
            taux_vers_mad=Decimal('10.85'))
        self.assertEqual(taux.devise, 'EUR')
        self.assertEqual(taux.source, TauxDevise.Source.MANUEL)

    def test_mad_refuse_table(self):
        with self.assertRaises(ValidationError):
            services.enregistrer_taux_devise(
                self.co, devise='MAD', date_taux=date(2026, 6, 1),
                taux_vers_mad=Decimal('1'))

    def test_feed_ne_snap_jamais_saisie_manuelle(self):
        services.enregistrer_taux_devise(
            self.co, devise='EUR', date_taux=date(2026, 6, 1),
            taux_vers_mad=Decimal('11.00'), source=TauxDevise.Source.MANUEL)
        # Un feed automatique du même jour ne doit PAS écraser la saisie.
        taux = services.enregistrer_taux_devise(
            self.co, devise='EUR', date_taux=date(2026, 6, 1),
            taux_vers_mad=Decimal('10.50'), source=TauxDevise.Source.BKAM)
        self.assertEqual(taux.taux_vers_mad, Decimal('11.00'))
        self.assertEqual(taux.source, TauxDevise.Source.MANUEL)

    def test_taux_du_jour_prend_le_plus_recent_anterieur(self):
        services.enregistrer_taux_devise(
            self.co, devise='EUR', date_taux=date(2026, 6, 1),
            taux_vers_mad=Decimal('10.80'))
        services.enregistrer_taux_devise(
            self.co, devise='EUR', date_taux=date(2026, 6, 5),
            taux_vers_mad=Decimal('10.90'))
        taux = selectors.taux_du_jour(self.co, 'EUR', date(2026, 6, 10))
        self.assertEqual(taux.taux_vers_mad, Decimal('10.90'))
        taux_avant = selectors.taux_du_jour(self.co, 'EUR', date(2026, 6, 3))
        self.assertEqual(taux_avant.taux_vers_mad, Decimal('10.80'))

    def test_mad_toujours_none_pas_de_table_necessaire(self):
        self.assertIsNone(selectors.taux_du_jour(self.co, 'MAD'))


class ContreValeurMadTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc17-cv', 'XACC17 CV')

    def test_facture_eur_sans_taux_applique_taux_du_jour(self):
        services.enregistrer_taux_devise(
            self.co, devise='EUR', date_taux=date(2026, 6, 1),
            taux_vers_mad=Decimal('10.85'))
        cv = services.contre_valeur_mad(
            Decimal('1000'), 'EUR', self.co, une_date=date(2026, 6, 10))
        self.assertEqual(cv, Decimal('10850.00'))

    def test_taux_saisi_explicite_prioritaire(self):
        services.enregistrer_taux_devise(
            self.co, devise='EUR', date_taux=date(2026, 6, 1),
            taux_vers_mad=Decimal('10.85'))
        cv = services.contre_valeur_mad(
            Decimal('1000'), 'EUR', self.co, taux_vers_mad=Decimal('11.20'))
        self.assertEqual(cv, Decimal('11200.00'))

    def test_sans_table_repli_1_pour_1_intact(self):
        cv = services.contre_valeur_mad(Decimal('1000'), 'USD', self.co)
        self.assertEqual(cv, Decimal('1000.00'))

    def test_mad_toujours_1_pour_1(self):
        cv = services.contre_valeur_mad(Decimal('1000'), 'MAD', self.co)
        self.assertEqual(cv, Decimal('1000.00'))

    def test_isolation_multi_societe(self):
        co_b = make_company('xacc17-b', 'XACC17 B')
        services.enregistrer_taux_devise(
            self.co, devise='EUR', date_taux=date(2026, 6, 1),
            taux_vers_mad=Decimal('10.85'))
        self.assertIsNone(selectors.taux_du_jour(co_b, 'EUR'))
