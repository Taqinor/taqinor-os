"""Test AUD171 — budget de requêtes du grand livre et du relevé fournisseur.

``_lignes_qs`` posait ``select_related('compte', 'ecriture')`` sans
``'ecriture__journal'``, alors que ``grand_livre`` lit
``ligne.ecriture.journal.code`` sur CHAQUE ligne (selectors.py:106) et que
``releve_fournisseur`` fait de même : une requête unitaire sur
``compta_journal`` par ligne, sur une action qui n'impose ni pagination ni
filtre de compte obligatoire. La bonne forme existait déjà dans le même
fichier (``journal_items``, ``export_fec``).

Le test est SÉMANTIQUE (aucun nombre épinglé) : il compare le nombre de
requêtes à deux volumes et exige qu'il soit IDENTIQUE.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import EcritureComptable, Journal, LigneEcriture


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class GrandLivreBudgetRequetesTests(TestCase):
    def setUp(self):
        self.co = make_company('aud171-co', 'AUD171 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.clients = services.get_compte(self.co, '3421')
        self.ventes = services.get_compte(self.co, '7121')
        # Deux journaux DIFFÉRENTS : le N+1 sur le journal ne se voit que si
        # plusieurs journaux sont en jeu.
        self.journaux = [
            services._journal(self.co, Journal.Type.VENTE),
            services._journal(self.co, Journal.Type.OPERATIONS_DIVERSES),
        ]

    def _passer(self, nb, depart=0):
        for i in range(depart, depart + nb):
            ecriture = EcritureComptable.objects.create(
                company=self.co, journal=self.journaux[i % 2],
                date_ecriture=date(2026, 5, 1), libelle=f'Vente {i}',
                reference=f'AUD171-{i}',
                statut=EcritureComptable.Statut.VALIDEE)
            LigneEcriture.objects.create(
                company=self.co, ecriture=ecriture, compte=self.clients,
                debit=Decimal('100'), credit=Decimal('0'))
            LigneEcriture.objects.create(
                company=self.co, ecriture=ecriture, compte=self.ventes,
                debit=Decimal('0'), credit=Decimal('100'))

    def _nb_requetes(self):
        with CaptureQueriesContext(connection) as ctx:
            resultat = selectors.grand_livre(self.co)
        self.assertTrue(resultat)
        return len(ctx.captured_queries)

    def test_grand_livre_nombre_de_requetes_independant_du_volume(self):
        self._passer(5)
        petit = self._nb_requetes()
        self._passer(25, depart=5)
        grand = self._nb_requetes()
        self.assertEqual(
            petit, grand,
            "Le grand livre fait une requête de plus par ligne (N+1 sur "
            "``ecriture.journal``).")
