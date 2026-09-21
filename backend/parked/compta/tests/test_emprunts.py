"""Tests XACC14 — Emprunts & crédits-bails (financements de la société).

Couvre : génération du tableau d'amortissement complet (somme des principaux
= capital), posting d'une échéance en écriture GL équilibrée idempotente,
l'encours restant dû dans la position de trésorerie, et l'injection des
échéances futures dans le prévisionnel 13 semaines (FG126).
"""
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.core.exceptions import ValidationError
from django.test import TestCase

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import Emprunt, LigneEcriture

# PACT10 — l'exemple de réponse committé, porteur du contrat front ↔ back.
ECHANTILLON_PREVISIONNEL = (
    Path(__file__).resolve().parent.parent
    / 'contract_samples' / 'previsionnel_tresorerie.json')


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TableauAmortissementTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc14-svc', 'XACC14 Svc')

    def test_tableau_complet_somme_principal_egale_capital(self):
        emprunt = Emprunt.objects.create(
            company=self.co, banque='Banque Populaire',
            type_financement=Emprunt.Type.EMPRUNT,
            capital=Decimal('120000'), taux_annuel=Decimal('6.000'),
            duree_mois=12, date_debut=date(2026, 1, 1),
        )
        echeances = services.generer_tableau_amortissement(emprunt)
        self.assertEqual(len(echeances), 12)
        total_principal = sum((e.principal for e in echeances), Decimal('0'))
        self.assertEqual(total_principal, Decimal('120000.00'))
        # Le capital restant dû de la dernière échéance doit être nul.
        self.assertEqual(echeances[-1].capital_restant_du, Decimal('0.00'))

    def test_taux_zero_division_simple(self):
        emprunt = Emprunt.objects.create(
            company=self.co, banque='Leasing Co',
            type_financement=Emprunt.Type.LEASING,
            capital=Decimal('12000'), taux_annuel=Decimal('0'),
            duree_mois=12, date_debut=date(2026, 1, 1),
        )
        echeances = services.generer_tableau_amortissement(emprunt)
        total_principal = sum((e.principal for e in echeances), Decimal('0'))
        self.assertEqual(total_principal, Decimal('12000.00'))
        self.assertTrue(all(e.interets == Decimal('0.00') for e in echeances))

    def test_regeneration_refusee_si_echeance_postee(self):
        emprunt = Emprunt.objects.create(
            company=self.co, banque='Banque X',
            capital=Decimal('10000'), taux_annuel=Decimal('5'),
            duree_mois=6, date_debut=date(2026, 1, 1),
        )
        services.generer_tableau_amortissement(emprunt)
        premiere = emprunt.echeances.order_by('numero').first()
        services.poster_echeance_emprunt(premiere)
        with self.assertRaises(ValidationError):
            services.generer_tableau_amortissement(emprunt)


class PosterEcheanceTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc14-post', 'XACC14 Post')
        self.emprunt = Emprunt.objects.create(
            company=self.co, banque='Banque Populaire',
            capital=Decimal('60000'), taux_annuel=Decimal('4.5'),
            duree_mois=6, date_debut=date(2026, 1, 1),
        )
        services.generer_tableau_amortissement(self.emprunt)

    def test_poster_echeance_ecriture_equilibree(self):
        echeance = self.emprunt.echeances.order_by('numero').first()
        ecriture = services.poster_echeance_emprunt(echeance)
        lignes = LigneEcriture.objects.filter(ecriture=ecriture)
        debit = sum((line.debit for line in lignes), Decimal('0'))
        credit = sum((line.credit for line in lignes), Decimal('0'))
        self.assertEqual(debit, credit)
        self.assertEqual(debit, echeance.mensualite)
        numeros = {line.compte.numero for line in lignes}
        self.assertIn('1481', numeros)
        self.assertIn('5141', numeros)

    def test_poster_idempotent(self):
        echeance = self.emprunt.echeances.order_by('numero').first()
        ec1 = services.poster_echeance_emprunt(echeance)
        echeance.refresh_from_db()
        ec2 = services.poster_echeance_emprunt(echeance)
        self.assertEqual(ec1.id, ec2.id)

    def test_leasing_utilise_compte_1671(self):
        emprunt_leasing = Emprunt.objects.create(
            company=self.co, banque='Wafabail',
            type_financement=Emprunt.Type.LEASING,
            capital=Decimal('30000'), taux_annuel=Decimal('5'),
            duree_mois=6, date_debut=date(2026, 1, 1),
        )
        services.generer_tableau_amortissement(emprunt_leasing)
        echeance = emprunt_leasing.echeances.order_by('numero').first()
        ecriture = services.poster_echeance_emprunt(echeance)
        numeros = {
            line.compte.numero
            for line in LigneEcriture.objects.filter(ecriture=ecriture)}
        self.assertIn('1671', numeros)


class EncoursEtPrevisionnelTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc14-treso', 'XACC14 Treso')
        self.emprunt = Emprunt.objects.create(
            company=self.co, banque='Banque Populaire',
            capital=Decimal('24000'), taux_annuel=Decimal('0'),
            duree_mois=12, date_debut=date(2026, 1, 1),
        )
        services.generer_tableau_amortissement(self.emprunt)

    def test_encours_restant_du_diminue_apres_posting(self):
        # Rien de postée encore : encours = capital initial intact.
        self.assertEqual(self.emprunt.encours_restant_du, Decimal('24000.00'))
        premiere = self.emprunt.echeances.order_by('numero').first()
        services.poster_echeance_emprunt(premiere)
        self.emprunt.refresh_from_db()
        self.assertEqual(
            self.emprunt.encours_restant_du,
            Decimal('24000.00') - premiere.principal)

    def test_encours_apparait_dans_position_tresorerie(self):
        position = selectors.position_tresorerie(self.co)
        self.assertIn('encours_emprunts', position)

    def test_injection_previsionnel_echeances_futures(self):
        from datetime import date as d
        lignes = services.injecter_echeances_previsionnel(
            self.co, date_debut=d(2026, 1, 1), nb_semaines=13)
        self.assertTrue(len(lignes) > 0)
        self.assertTrue(all(ligne['montant'] < 0 for ligne in lignes))


class PrevisionnelEcheancesEmpruntTests(TestCase):
    """AUDV01 / DRAFT165-34 — les remboursements de crédit sont VISIBLES dans
    le prévisionnel roulant, et par UNE seule source.

    Le rapport d'orphelines relevait que ``injecter_echeances_previsionnel``
    n'avait aucun appelant : la fonction et ``selectors.previsionnel_
    tresorerie`` portaient chacune sa copie de la même règle. Rien ne le
    voyait — aucun test n'appelait le SÉLECTEUR avec une échéance d'emprunt en
    base ; les deux copies pouvaient diverger en silence. Ces tests ferment le
    trou des deux côtés : la ligne existe dans la sortie du sélecteur, et les
    deux chemins donnent le même total.
    """

    def setUp(self):
        self.co = make_company('audv01-prev', 'AUDV01 Prévisionnel')
        self.emprunt = Emprunt.objects.create(
            company=self.co, banque='Banque Populaire',
            capital=Decimal('24000'), taux_annuel=Decimal('0'),
            duree_mois=12, date_debut=date(2026, 1, 1),
        )
        services.generer_tableau_amortissement(self.emprunt)
        # Échéances mensuelles au 1er de chaque mois : 2026-02-01 … 2027-01-01.
        self.debut = date(2026, 2, 1)

    def _lignes_emprunt(self, previsionnel):
        return [
            ligne
            for semaine in previsionnel['semaines']
            for ligne in semaine['lignes']
            if ligne['type'] == 'echeance_emprunt'
        ]

    def test_le_previsionnel_nomme_les_echeances_emprunt(self):
        prev = selectors.previsionnel_tresorerie(
            self.co, date_debut=self.debut, nb_semaines=13)
        lignes = self._lignes_emprunt(prev)
        self.assertTrue(
            lignes,
            "Aucune ligne d'échéance d'emprunt dans le prévisionnel : le "
            "remboursement de crédit serait invisible du comptable.")
        # Décaissement : montant NÉGATIF, et compté en `sorties` (valeur absolue).
        self.assertTrue(all(ligne['montant'] < 0 for ligne in lignes))
        self.assertIn('Banque Populaire', lignes[0]['libelle'])
        total_sorties = sum(
            (semaine['sorties'] for semaine in prev['semaines']), Decimal('0'))
        self.assertEqual(
            total_sorties,
            sum((-ligne['montant'] for ligne in lignes), Decimal('0')))

    def test_une_echeance_postee_quitte_le_previsionnel(self):
        """Postée = déjà sortie de la banque : ce n'est plus un PRÉVISIONNEL."""
        avant = len(self._lignes_emprunt(selectors.previsionnel_tresorerie(
            self.co, date_debut=self.debut, nb_semaines=13)))
        premiere = self.emprunt.echeances.order_by('numero').first()
        services.poster_echeance_emprunt(premiere)
        apres = len(self._lignes_emprunt(selectors.previsionnel_tresorerie(
            self.co, date_debut=self.debut, nb_semaines=13)))
        self.assertEqual(apres, avant - 1)

    def test_service_et_selecteur_ne_peuvent_plus_diverger(self):
        """Le sélecteur CONSOMME le service : mêmes dates, mêmes montants."""
        prev = selectors.previsionnel_tresorerie(
            self.co, date_debut=self.debut, nb_semaines=13)
        # Le sélecteur cale son horizon sur le LUNDI de la semaine demandée.
        lundi = self.debut - timedelta(days=self.debut.weekday())
        service = services.injecter_echeances_previsionnel(
            self.co, date_debut=lundi, nb_semaines=13)
        self.assertEqual(
            [(ligne['date'], ligne['montant'])
             for ligne in self._lignes_emprunt(prev)],
            [(ligne['date'], ligne['montant']) for ligne in service])

    def test_la_ligne_a_exactement_les_cles_du_contrat_committe(self):
        """PACT10 — l'exemple committé est affirmé contre la VRAIE réponse.

        ``scripts/check_api_shapes.py`` ne descend pas dans
        ``semaines[].lignes[]`` : sans cette assertion, l'exemple pourrirait
        dans son coin — ce que le README de ``contract_samples/`` désigne comme
        pire que pas d'exemple du tout.
        """
        contrat = json.loads(ECHANTILLON_PREVISIONNEL.read_text(encoding='utf-8'))
        exemple = contrat['exemple']
        prev = selectors.previsionnel_tresorerie(
            self.co, date_debut=self.debut, nb_semaines=13)
        self.assertEqual(sorted(exemple), sorted(prev))
        self.assertEqual(
            sorted(exemple['semaines'][0]), sorted(prev['semaines'][0]))
        ligne_exemple = next(
            ligne
            for semaine in exemple['semaines']
            for ligne in semaine['lignes']
            if ligne['type'] == 'echeance_emprunt')
        ligne_reelle = self._lignes_emprunt(prev)[0]
        self.assertEqual(sorted(ligne_exemple), sorted(ligne_reelle))
        self.assertEqual(ligne_exemple['categorie'], ligne_reelle['categorie'])
