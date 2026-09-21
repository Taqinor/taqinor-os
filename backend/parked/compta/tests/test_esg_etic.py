"""Tests COMPTA29 — ESG (état des soldes de gestion) + ETIC.

L'ESG dérive la cascade des soldes intermédiaires de gestion (marge → valeur
ajoutée → EBE → résultat courant → résultat net) du seul grand livre (comptes de
gestion classes 6 & 7). L'ETIC assemble les tableaux annexes (immobilisations,
provisions, engagements hors-bilan) sans recalcul. Tout est en lecture seule,
scopé société.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import (
    EcritureComptable, ExerciceComptable, Journal, LigneEcriture,
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class EsgTests(TestCase):
    def setUp(self):
        self.co = make_company('compta-esg', 'Compta ESG')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.journal = Journal.objects.filter(
            company=self.co, type_journal=Journal.Type.VENTE).first()

    def _ecriture(self, lignes):
        """lignes = [(numero, debit, credit), …] — écriture équilibrée."""
        ecr = EcritureComptable.objects.create(
            company=self.co, journal=self.journal,
            date_ecriture=date(2026, 3, 1), libelle='Test ESG',
            statut=EcritureComptable.Statut.VALIDEE)
        for numero, debit, credit in lignes:
            compte = services._assurer_compte(self.co, numero)
            LigneEcriture.objects.create(
                company=self.co, ecriture=ecr, compte=compte,
                debit=Decimal(debit), credit=Decimal(credit), libelle='l')
        return ecr

    def test_marge_valeur_ajoutee_resultat_net(self):
        # Ventes de biens produits 712 = 1000 (crédit), consommation 612 = 400,
        # personnel 617 = 200, impôt sur résultat 67 = 100. Contrepartie treso.
        self._ecriture([('7121', '0', '1000'), ('5141', '1000', '0')])
        self._ecriture([('6121', '400', '0'), ('4411', '0', '400')])
        self._ecriture([('6171', '200', '0'), ('4411', '0', '200')])
        self._ecriture([('6701', '100', '0'), ('4411', '0', '100')])
        data = selectors.esg(self.co)
        soldes = {s['code']: s['montant'] for s in data['soldes']}
        self.assertEqual(soldes['PROD'], Decimal('1000'))
        # VA = marge(0) + production(1000) − conso(400) = 600
        self.assertEqual(soldes['VA'], Decimal('600'))
        # EBE = VA(600) − personnel(200) − impôts&taxes(0) = 400
        self.assertEqual(soldes['EBE'], Decimal('400'))
        # Résultat net = ... − IS(100). Exploitation=400, courant=400,
        # avant impôts=400, net=300.
        self.assertEqual(soldes['RN'], Decimal('300'))
        self.assertEqual(data['resultat_net'], Decimal('300'))

    def test_marge_brute_marchandises(self):
        # Ventes marchandises 711 = 800, achats revendus 611 = 500 → marge 300.
        self._ecriture([('7111', '0', '800'), ('5141', '800', '0')])
        self._ecriture([('6111', '500', '0'), ('4411', '0', '500')])
        data = selectors.esg(self.co)
        soldes = {s['code']: s['montant'] for s in data['soldes']}
        self.assertEqual(soldes['MARGE'], Decimal('300'))

    def test_esg_scope_societe(self):
        autre = make_company('compta-esg-autre', 'Autre')
        services.seed_plan_comptable(autre)
        services.seed_journaux(autre)
        self._ecriture([('7121', '0', '500'), ('5141', '500', '0')])
        # L'autre société ne voit rien.
        data = selectors.esg(autre)
        self.assertEqual(data['resultat_net'], Decimal('0'))


class EticTests(TestCase):
    def setUp(self):
        self.co = make_company('compta-etic', 'Compta ETIC')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.exercice = ExerciceComptable.objects.create(
            company=self.co, libelle='2026',
            date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31))

    def test_etic_structure_sections(self):
        data = selectors.etic(self.co, self.exercice)
        self.assertEqual(data['exercice'], '2026')
        self.assertIn('immobilisations', data)
        self.assertIn('provisions', data)
        self.assertIn('engagements_hors_bilan', data)
        self.assertIn('cautions_bancaires', data['engagements_hors_bilan'])
        self.assertIn('resultat', data)
        self.assertTrue(data['principes_methodes'])
        self.assertEqual(len(data['sections']), 5)
