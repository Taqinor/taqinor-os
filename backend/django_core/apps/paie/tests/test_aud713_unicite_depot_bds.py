"""AUD713 — un seul dépôt BDS PRINCIPAL par période, garanti par la DB.

ÉTAT AVANT LE FIX. ``DepotBDS`` PROMETTAIT dans sa docstring qu'« une période
ne peut avoir qu'UN dépôt principal », mais son ``Meta`` ne portait AUCUNE
``unique_together``/``UniqueConstraint``, et ``deposer_bds_principal`` faisait
un ``filter().first()`` suivi d'un ``create()`` sans ``select_for_update()``
ni ``transaction.atomic()``. Deux appels concurrents créaient donc DEUX dépôts
principaux distincts pour la même période — une déclaration CNSS déposée deux
fois, sans que rien ne le signale.
"""
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from authentication.models import Company
from apps.paie.models import DepotBDS, PeriodePaie, ProfilPaie
from apps.paie.services import (
    deposer_bds_principal,
    ensure_defaults,
    generer_bulletin,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


class UniciteDepotBdsPrincipalTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='aud713', nom='AUD713')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='BDS1', nom='Depot', prenom='Test')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), numero_cnss='777888999',
            affilie_cnss=True, affilie_amo=True)
        valider_bulletin(generer_bulletin(profil, self.periode))

    def test_depot_principal_reste_idempotent(self):
        premier = deposer_bds_principal(self.periode)
        second = deposer_bds_principal(self.periode)
        self.assertEqual(premier.pk, second.pk)
        self.assertEqual(
            DepotBDS.objects.filter(
                periode=self.periode,
                type_depot=DepotBDS.TYPE_PRINCIPAL).count(), 1)

    def test_second_depot_principal_refuse_par_la_db(self):
        """La contrainte ferme la course quoi que fasse le code applicatif."""
        deposer_bds_principal(self.periode)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DepotBDS.objects.create(
                    company=self.co, periode=self.periode,
                    type_depot=DepotBDS.TYPE_PRINCIPAL, profils_couverts=[])

    def test_complementaires_restent_multiples(self):
        """La contrainte est PARTIELLE : elle ne vise que le principal."""
        principal = deposer_bds_principal(self.periode)
        for _ in range(2):
            DepotBDS.objects.create(
                company=self.co, periode=self.periode,
                type_depot=DepotBDS.TYPE_COMPLEMENTAIRE,
                depot_principal=principal, profils_couverts=['777888999'])
        self.assertEqual(
            DepotBDS.objects.filter(
                periode=self.periode,
                type_depot=DepotBDS.TYPE_COMPLEMENTAIRE).count(), 2)

    def test_unicite_scopee_par_societe(self):
        """Une AUTRE société dépose son propre principal sans conflit."""
        deposer_bds_principal(self.periode)
        autre = Company.objects.create(slug='aud713-b', nom='AUD713 B')
        ensure_defaults(autre)
        periode_autre = PeriodePaie.objects.create(
            company=autre, annee=2026, mois=6)
        depot = DepotBDS.objects.create(
            company=autre, periode=periode_autre,
            type_depot=DepotBDS.TYPE_PRINCIPAL, profils_couverts=[])
        self.assertIsNotNone(depot.pk)
