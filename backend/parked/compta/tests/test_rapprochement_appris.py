"""Tests NTTRE4 — rapprochement bancaire auto APPRENANT.

Couvre : après un historique de pointages validés sur un libellé récurrent, une
nouvelle ligne de relevé au libellé similaire reçoit une suggestion apprise à
confiance ≥ 0.8 pointant une ligne GL non lettrée ; sans historique, aucune
suggestion ; le service ne poste jamais rien.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    CompteTresorerie, LigneReleve, PointageReleve)


def _journal_banque(company):
    from apps.compta.models import Journal
    return services._journal(company, Journal.Type.BANQUE)


def _ecriture_banque(company, montant, jour, reference=''):
    """Crée une écriture GL avec une ligne au débit banque (5141)."""
    lignes = [
        {'compte': services.get_compte(company, '5141'),
         'debit': Decimal(montant), 'credit': Decimal('0')},
        {'compte': services.get_compte(company, '3421'),
         'debit': Decimal('0'), 'credit': Decimal(montant)},
    ]
    ecr = services.creer_ecriture(
        company, _journal_banque(company), jour, 'Test NTTRE4', lignes,
        reference=reference)
    return ecr.lignes.get(compte__numero='5141')


class RapprochementApprisTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='nttre4', defaults={'nom': 'NTTRE4 Co'})
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.banque = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='BMCE', solde_initial=Decimal('0'),
            compte_comptable=services.get_compte(self.co, '5141'))

    def _historique(self, n, libelle):
        """Matérialise ``n`` pointages validés (libellé récurrent → GL 5141)."""
        rap = services.creer_rapprochement(
            self.co, self.banque, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 1, 31), solde_releve=Decimal('0'))
        for i in range(n):
            gl = _ecriture_banque(
                self.co, 100 + i, date(2026, 1, 5), reference='H%03d' % i)
            lr = services.ajouter_ligne_releve(
                rap, date_operation=date(2026, 1, 5), libelle=libelle,
                montant=Decimal(100 + i))
            PointageReleve.objects.create(
                company=self.co, ligne_releve=lr, ligne_gl=gl)

    def test_libelle_recurrent_donne_suggestion_confiance_haute(self):
        self._historique(20, 'PAIEMENT ORANGE')
        # Nouvelle ligne de relevé, libellé SIMILAIRE + GL 5141 non lettrée.
        rap2 = services.creer_rapprochement(
            self.co, self.banque, date_debut=date(2026, 2, 1),
            date_fin=date(2026, 2, 28), solde_releve=Decimal('0'))
        gl_neuf = _ecriture_banque(
            self.co, 250, date(2026, 2, 10), reference='NEW')
        lr = services.ajouter_ligne_releve(
            rap2, date_operation=date(2026, 2, 10),
            libelle='PAIEMENT ORANGE JUIN', montant=Decimal('250'))
        sugg = services.suggerer_rapprochement_appris(lr)
        self.assertIsNotNone(sugg)
        self.assertEqual(sugg['ligne_gl_id'], gl_neuf.id)
        self.assertGreaterEqual(sugg['confiance'], 0.8)
        self.assertEqual(sugg['frequence'], 20)
        self.assertTrue(sugg['montant_concordant'])
        # N'a RIEN posté : la ligne reste non pointée.
        lr.refresh_from_db()
        self.assertEqual(lr.statut, LigneReleve.Statut.NON_POINTEE)
        self.assertFalse(
            PointageReleve.objects.filter(ligne_releve=lr).exists())

    def test_sans_historique_aucune_suggestion(self):
        rap = services.creer_rapprochement(
            self.co, self.banque, date_debut=date(2026, 2, 1),
            date_fin=date(2026, 2, 28), solde_releve=Decimal('0'))
        lr = services.ajouter_ligne_releve(
            rap, date_operation=date(2026, 2, 10), libelle='INCONNU',
            montant=Decimal('99'))
        self.assertIsNone(services.suggerer_rapprochement_appris(lr))

    def test_libelle_totalement_different_sous_le_seuil(self):
        self._historique(5, 'PAIEMENT ORANGE')
        rap2 = services.creer_rapprochement(
            self.co, self.banque, date_debut=date(2026, 3, 1),
            date_fin=date(2026, 3, 31), solde_releve=Decimal('0'))
        _ecriture_banque(self.co, 80, date(2026, 3, 10))
        lr = services.ajouter_ligne_releve(
            rap2, date_operation=date(2026, 3, 10),
            libelle='ZZZZ QQQQ WWWW', montant=Decimal('80'))
        self.assertIsNone(services.suggerer_rapprochement_appris(lr))
