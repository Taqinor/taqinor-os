"""Tests FG46 — échéancier personnalisé + acompte persisté sur Devis."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis
from apps.ventes.utils.echeancier import schedule_for_devis

User = get_user_model()


def _company(slug='ech-fg46', nom='Ech FG46'):
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return c


def _user(co, username='ech_user'):
    return User.objects.create_user(
        username=username, password='x', role_legacy='responsable', company=co)


def _client(co):
    return Client.objects.create(
        company=co, nom='Ech', prenom='Client',
        email='ech@example.com', telephone='+212600000089')


def _devis(co, user, client, ref='DEV-ECH-001', echeancier=None,
           acompte_pct=None, acompte_montant=None):
    return Devis.objects.create(
        company=co, created_by=user, client=client,
        reference=ref, statut='brouillon',
        echeancier=echeancier,
        acompte_pct=acompte_pct,
        acompte_montant=acompte_montant,
    )


class TestDevisEcheancierFields(TestCase):
    """Vérifie que les 3 nouveaux champs existent et sont nullable."""

    def setUp(self):
        self.co = _company()
        self.user = _user(self.co)
        self.cli = _client(self.co)

    def test_echeancier_field_null_by_default(self):
        d = _devis(self.co, self.user, self.cli, ref='DEV-ECH-NULL')
        self.assertIsNone(d.echeancier)

    def test_acompte_pct_nullable(self):
        d = _devis(self.co, self.user, self.cli, ref='DEV-ECH-PCT')
        self.assertIsNone(d.acompte_pct)

    def test_acompte_montant_nullable(self):
        d = _devis(self.co, self.user, self.cli, ref='DEV-ECH-MONT')
        self.assertIsNone(d.acompte_montant)

    def test_echeancier_stored_and_retrieved(self):
        custom = [
            {'libelle': 'Démarrage', 'type': 'acompte', 'pct_or_montant': 40},
            {'libelle': 'Livraison', 'type': 'intermediaire', 'pct_or_montant': 50},
            {'libelle': 'Réception', 'type': 'solde', 'pct_or_montant': 10},
        ]
        d = _devis(self.co, self.user, self.cli, ref='DEV-ECH-JSON',
                   echeancier=custom)
        d.refresh_from_db()
        self.assertEqual(len(d.echeancier), 3)
        self.assertEqual(d.echeancier[0]['libelle'], 'Démarrage')
        self.assertEqual(d.echeancier[0]['pct_or_montant'], 40)

    def test_acompte_pct_stored(self):
        d = _devis(self.co, self.user, self.cli, ref='DEV-ECH-PCT2',
                   acompte_pct=Decimal('30.00'))
        d.refresh_from_db()
        self.assertEqual(d.acompte_pct, Decimal('30.00'))

    def test_acompte_montant_stored(self):
        d = _devis(self.co, self.user, self.cli, ref='DEV-ECH-M2',
                   acompte_montant=Decimal('54000.00'))
        d.refresh_from_db()
        self.assertEqual(d.acompte_montant, Decimal('54000.00'))


class TestScheduleForDevisCustom(TestCase):
    """Vérifie que schedule_for_devis retourne le custom écheancier quand présent."""

    def setUp(self):
        self.co = _company(slug='sch-fg46b', nom='Sch FG46b')
        self.user = _user(self.co, username='sch_user')
        self.cli = _client(self.co)

    def test_default_schedule_is_3_tranches(self):
        d = _devis(self.co, self.user, self.cli, ref='DEV-SCH-DEF')
        schedule = schedule_for_devis(d)
        self.assertEqual(len(schedule), 3)

    def test_custom_schedule_overrides_default(self):
        custom = [
            {'libelle': 'A', 'type': 'acompte', 'pct_or_montant': 50},
            {'libelle': 'B', 'type': 'solde', 'pct_or_montant': 50},
        ]
        d = _devis(self.co, self.user, self.cli, ref='DEV-SCH-CUST',
                   echeancier=custom)
        schedule = schedule_for_devis(d)
        self.assertEqual(len(schedule), 2)

    def test_custom_schedule_keys_and_pcts(self):
        custom = [
            {'libelle': 'Acompte', 'type': 'acompte', 'pct_or_montant': 40},
            {'libelle': 'Intermédiaire', 'type': 'intermediaire', 'pct_or_montant': 40},
            {'libelle': 'Solde final', 'type': 'solde', 'pct_or_montant': 20},
        ]
        d = _devis(self.co, self.user, self.cli, ref='DEV-SCH-KEYS',
                   echeancier=custom)
        schedule = schedule_for_devis(d)
        keys = [k for k, _ in schedule]
        pcts = [p for _, p in schedule]
        self.assertEqual(keys, ['acompte', 'intermediaire', 'solde'])
        self.assertEqual(pcts, [40.0, 40.0, 20.0])

    def test_malformed_echeancier_falls_back_to_default(self):
        """Un écheancier JSON invalide doit gracieusement utiliser le défaut."""
        d = _devis(self.co, self.user, self.cli, ref='DEV-SCH-BAD',
                   echeancier='not-a-list')
        # Ne doit pas lever d'exception
        schedule = schedule_for_devis(d)
        self.assertEqual(len(schedule), 3)  # repli sur défaut

    def test_empty_list_echeancier_falls_back_to_default(self):
        """Liste vide → défaut."""
        d = _devis(self.co, self.user, self.cli, ref='DEV-SCH-EMPTY',
                   echeancier=[])
        schedule = schedule_for_devis(d)
        self.assertEqual(len(schedule), 3)

    def test_custom_2_tranches_50_50(self):
        custom = [
            {'libelle': 'À la commande', 'type': 'acompte', 'pct_or_montant': 50},
            {'libelle': 'À la livraison', 'type': 'solde', 'pct_or_montant': 50},
        ]
        d = _devis(self.co, self.user, self.cli, ref='DEV-SCH-50',
                   echeancier=custom)
        schedule = schedule_for_devis(d)
        self.assertEqual(len(schedule), 2)
        self.assertAlmostEqual(schedule[0][1], 50.0)
        self.assertAlmostEqual(schedule[1][1], 50.0)
