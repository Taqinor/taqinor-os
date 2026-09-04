"""AUD418 — la colonne « budget » d'un état personnalisé re-vérifie la
société À LA LECTURE.

Constat d'origine : ``evaluer_etat_personnalise`` reçoit ``company =
etat.company`` mais la branche colonne-budget agrégeait
``BudgetLigne.objects.filter(budget_id=colonne.budget_id)`` SANS
``company=company``, alors que les ~11 autres agrégats du même fichier le
posent systématiquement. La seule garantie que ``colonne.budget_id`` désigne
un budget de la MÊME société était
``ColonneEtatPersonnaliseSerializer.validate_budget`` — un contrôle posé
UNIQUEMENT à l'écriture, par ce sérialiseur précis.

Le test reproduit exactement le scénario du constat : le ``budget_id`` est
forcé HORS sérialiseur (``.update()`` direct), comme le ferait un admin non
scopé, un script de migration de données ou un futur endpoint bulk.

Test ROUGE d'abord : ``test_budget_dune_autre_societe_nest_plus_agrege``
affichait AUJOURD'HUI les montants budgétaires de la société concurrente
dans l'état financier de la victime.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import (
    Budget, BudgetLigne, ColonneEtatPersonnalise,
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class BudgetColonneScopeSocieteTests(TestCase):
    def setUp(self):
        self.victime = make_company('aud418', 'AUD418 victime')
        self.concurrent = make_company('aud418b', 'AUD418 concurrent')

        # Budget CONCURRENT, garni : c'est ce qui ne doit jamais fuiter.
        self.budget_concurrent = Budget.objects.create(
            company=self.concurrent, annee=2026, libelle='Budget concurrent')
        BudgetLigne.objects.create(
            company=self.concurrent, budget=self.budget_concurrent,
            compte=services._assurer_compte(self.concurrent, '6111'),
            m01=Decimal('100000.00'))

        # Budget de la victime, garni d'un montant DISTINCT et reconnaissable.
        self.budget_victime = Budget.objects.create(
            company=self.victime, annee=2026, libelle='Budget victime')
        BudgetLigne.objects.create(
            company=self.victime, budget=self.budget_victime,
            compte=services._assurer_compte(self.victime, '6111'),
            m01=Decimal('7.00'))

        self.etat = services.creer_etat_personnalise(
            self.victime, libelle='État',
            lignes=[{'libelle': 'Charges', 'type_ligne': 'total',
                     'formule': '6'}],
            colonnes=[{'libelle': 'Budget', 'type_colonne': 'budget',
                       'budget': self.budget_victime}])
        self.colonne = self.etat.colonnes.get()

    def _valeur_budget(self):
        rendu = selectors.evaluer_etat_personnalise(self.etat)
        return rendu['lignes'][0]['valeurs'][self.colonne.id]

    def test_budget_de_la_societe_reste_agrege(self):
        """Non-régression : le cas nominal est intact."""
        self.assertEqual(self._valeur_budget(), Decimal('7.00'))

    def test_budget_dune_autre_societe_nest_plus_agrege(self):
        """ROUGE avant correctif : les 100 000 du concurrent s'affichaient
        dans l'état de la victime."""
        # Écriture HORS sérialiseur — le seul endroit où la société était
        # vérifiée. C'est le scénario même du constat.
        ColonneEtatPersonnalise.objects.filter(id=self.colonne.id).update(
            budget_id=self.budget_concurrent.id)

        valeur = self._valeur_budget()
        self.assertEqual(valeur, Decimal('0'))
        self.assertNotEqual(valeur, Decimal('100000.00'))

    def test_aucune_erreur_sans_budget_reference(self):
        ColonneEtatPersonnalise.objects.filter(id=self.colonne.id).update(
            budget_id=None)
        self.assertEqual(self._valeur_budget(), Decimal('0'))
