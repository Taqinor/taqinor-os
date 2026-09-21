"""NTJUR12 — budget juridique consommé vs engagé + tableau de bord.

Critère d'acceptation : « un dossier à 120 % de son budget alloué apparaît
dans la liste des dépassements du tableau de bord ».
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.juridique import selectors
from apps.juridique.models import (
    CabinetAvocat, DossierJuridique, MandatAvocat, NoteHonoraires,
)

from ._base import auth, make_admin, make_company, make_responsable

URL = '/api/django/juridique/dossiers/'


class BudgetJuridiqueTests(TestCase):
    def setUp(self):
        self.company = make_company('jur-b12-co', 'Juridique B12')
        self.admin = make_admin(self.company, 'jur-b12-admin')
        self.api = auth(self.admin)
        self.cabinet = CabinetAvocat.objects.create(
            company=self.company, nom='Cabinet Alami')

    def _dossier(self, reference, budget=None, nature=None, confidentiel=False):
        return DossierJuridique.objects.create(
            company=self.company, reference=reference, titre=f'D {reference}',
            date_ouverture=date(2026, 1, 10), budget_alloue=budget,
            nature=nature or DossierJuridique.Nature.CONTENTIEUX,
            confidentialite=(
                DossierJuridique.NiveauConfidentialite.CONFIDENTIEL
                if confidentiel
                else DossierJuridique.NiveauConfidentialite.INTERNE))

    def _mandat(self, dossier, forfait='50000'):
        return MandatAvocat.objects.create(
            company=self.company, dossier=dossier, cabinet=self.cabinet,
            date_mandat=date(2026, 1, 11),
            montant_forfait=Decimal(forfait))

    def _note(self, mandat, ttc, statut):
        return NoteHonoraires.objects.create(
            company=self.company, mandat=mandat, reference=f'NHJ-{ttc}',
            date_facture=date(2026, 2, 1), montant_ht=Decimal(ttc),
            montant_ttc=Decimal(ttc), statut=statut)

    def test_budget_engage_et_consomme(self):
        dossier = self._dossier('JUR-2026-0001', budget=Decimal('100000'))
        mandat = self._mandat(dossier, '50000')
        self._note(mandat, '30000', NoteHonoraires.Statut.VALIDEE)
        # Une note simplement REÇUE n'est pas encore consommée.
        self._note(mandat, '9000', NoteHonoraires.Statut.RECUE)
        resp = self.api.get(f'{URL}{dossier.id}/budget/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['engage'], '50000.00')
        self.assertEqual(resp.data['consomme'], '30000.00')
        self.assertEqual(resp.data['pourcentage_consomme'], 30.0)
        self.assertFalse(resp.data['depassement'])

    def test_budget_sans_enveloppe_ne_divise_jamais_par_zero(self):
        dossier = self._dossier('JUR-2026-0002', budget=None)
        mandat = self._mandat(dossier, '10000')
        self._note(mandat, '5000', NoteHonoraires.Statut.PAYEE)
        resp = self.api.get(f'{URL}{dossier.id}/budget/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['pourcentage_consomme'])
        self.assertFalse(resp.data['depassement'])

        zero = self._dossier('JUR-2026-0003', budget=Decimal('0'))
        resp_zero = self.api.get(f'{URL}{zero.id}/budget/')
        self.assertIsNone(resp_zero.data['pourcentage_consomme'])

    def test_dossier_a_120_pourcent_apparait_dans_les_depassements(self):
        dossier = self._dossier('JUR-2026-0004', budget=Decimal('100000'))
        mandat = self._mandat(dossier, '80000')
        self._note(mandat, '120000', NoteHonoraires.Statut.VALIDEE)
        resp = self.api.get(f'{URL}tableau-bord/')
        self.assertEqual(resp.status_code, 200, resp.data)
        refs = [d['reference'] for d in resp.data['depassements']]
        self.assertIn('JUR-2026-0004', refs)
        ligne = resp.data['depassements'][0]
        self.assertEqual(ligne['pourcentage_consomme'], 120.0)

    def test_tableau_de_bord_totalise_par_nature(self):
        contentieux = self._dossier('JUR-2026-0005',
                                    nature=DossierJuridique.Nature.CONTENTIEUX)
        recouvrement = self._dossier(
            'JUR-2026-0006', nature=DossierJuridique.Nature.RECOUVREMENT)
        self._mandat(contentieux, '20000')
        self._mandat(recouvrement, '5000')
        resp = self.api.get(f'{URL}tableau-bord/')
        par_nature = {s['nature']: s for s in resp.data['par_nature']}
        self.assertEqual(par_nature['contentieux']['engage'], '20000.00')
        self.assertEqual(par_nature['recouvrement']['engage'], '5000.00')
        self.assertEqual(resp.data['total_engage'], '25000.00')

    def test_aucune_fuite_par_agregat_sur_un_dossier_confidentiel(self):
        """Un rôle non autorisé voit des totaux qui EXCLUENT le confidentiel."""
        public = self._dossier('JUR-2026-0007')
        secret = self._dossier('JUR-2026-0008', confidentiel=True)
        self._mandat(public, '10000')
        self._mandat(secret, '999000')
        responsable = make_responsable(self.company, 'jur-b12-resp')
        vu = auth(responsable).get(f'{URL}tableau-bord/')
        self.assertEqual(vu.data['total_engage'], '10000.00')
        # Le dossier confidentiel ne compte même pas dans le NOMBRE : un
        # compteur qui bouge trahirait déjà son existence.
        self.assertEqual(vu.data['nombre_dossiers'], 1)
        # L'administrateur, lui, voit le total complet.
        complet = self.api.get(f'{URL}tableau-bord/')
        self.assertEqual(complet.data['total_engage'], '1009000.00')
        self.assertEqual(complet.data['nombre_dossiers'], 2)

    def test_le_selecteur_est_utilisable_en_lecture_cross_app(self):
        dossier = self._dossier('JUR-2026-0009', budget=Decimal('1000'))
        budget = selectors.budget_dossier(dossier)
        self.assertEqual(budget['consomme'], '0.00')
        self.assertEqual(budget['pourcentage_consomme'], 0.0)
