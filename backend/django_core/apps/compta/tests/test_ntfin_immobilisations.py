"""Tests NTFIN40-45 — Immobilisations avancées.

Couvre :

* NTFIN40 — un actif à 2 composants (durées 25 et 10 ans) produit deux
  dotations distinctes sommant à la dotation totale.
* NTFIN41 — un actif VNC 500k / recouvrable 400k poste une dépréciation de
  100k, réversible.
* NTFIN42 — muter un actif réaffecte son centre à compter de la mutation.
* NTFIN43 — un CIP de 300k mis en service crée une immo de 300k et solde le 23.
* NTFIN44 — VNC IFRS (composants) ≠ VNC CGNC (plan) quand les durées diffèrent.
* NTFIN45 — projection 5 ans d'un actif linéaire 25 ans.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import (
    CentreCout, ComposantImmobilisation, DepreciationImmobilisation,
    Immobilisation, ImmobilisationEnCours,
    MutationImmobilisation, PlanAmortissement, ReferentielComptable)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class ComposantsTests(TestCase):
    def setUp(self):
        self.co = make_company('ntfin40', 'NTFIN40')
        self.immo = Immobilisation.objects.create(
            company=self.co, libelle='Centrale solaire',
            cout=Decimal('350000'), date_acquisition=date(2026, 1, 1))

    def test_deux_composants_dotations_distinctes(self):
        ComposantImmobilisation.objects.create(
            company=self.co, immobilisation=self.immo, libelle='Structure',
            valeur=Decimal('250000'), duree_amortissement=25)
        ComposantImmobilisation.objects.create(
            company=self.co, immobilisation=self.immo, libelle='Onduleur',
            valeur=Decimal('100000'), duree_amortissement=10)
        data = selectors.plans_composants_immobilisation(self.immo)
        dotations = {c['libelle']: c['dotation_annuelle']
                     for c in data['composants']}
        self.assertEqual(dotations['Structure'], Decimal('10000.00'))
        self.assertEqual(dotations['Onduleur'], Decimal('10000.00'))
        self.assertEqual(data['dotation_annuelle_totale'], Decimal('20000.00'))


class DepreciationTests(TestCase):
    def setUp(self):
        self.co = make_company('ntfin41', 'NTFIN41')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.immo = Immobilisation.objects.create(
            company=self.co, libelle='Matériel',
            cout=Decimal('500000'), date_acquisition=date(2026, 1, 1))

    def test_depreciation_postee(self):
        dep = DepreciationImmobilisation.objects.create(
            company=self.co, immobilisation=self.immo, date_test=date(2026, 6, 30),
            valeur_recuperable=Decimal('400000'),
            valeur_comptable=Decimal('500000'))
        services.poster_depreciation_immobilisation(dep)
        dep.refresh_from_db()
        self.assertEqual(dep.perte_valeur, Decimal('100000'))
        self.assertIsNotNone(dep.ecriture_id)

    def test_reprise_reversible(self):
        dep = DepreciationImmobilisation.objects.create(
            company=self.co, immobilisation=self.immo, date_test=date(2026, 6, 30),
            valeur_recuperable=Decimal('400000'),
            valeur_comptable=Decimal('500000'), reversible=True)
        services.poster_depreciation_immobilisation(dep)
        reprise = services.reprendre_depreciation_immobilisation(
            dep, Decimal('30000'), date_reprise=date(2026, 12, 31))
        self.assertTrue(reprise.reprise)
        self.assertIsNotNone(reprise.ecriture_id)


class MutationTests(TestCase):
    def setUp(self):
        self.co = make_company('ntfin42', 'NTFIN42')
        self.immo = Immobilisation.objects.create(
            company=self.co, libelle='Camion', cout=Decimal('200000'),
            date_acquisition=date(2026, 1, 1))
        self.agadir = CentreCout.objects.create(
            company=self.co, code='AGA', libelle='Agadir')
        self.casa = CentreCout.objects.create(
            company=self.co, code='CASA', libelle='Casablanca')

    def test_mutation_tracee(self):
        mut = services.muter_immobilisation(
            self.immo, ancien_centre=self.agadir, nouveau_centre=self.casa,
            date=date(2026, 7, 1), motif='Réaffectation')
        self.assertEqual(mut.nouveau_centre_id, self.casa.id)
        self.assertEqual(
            MutationImmobilisation.objects.filter(
                immobilisation=self.immo).count(), 1)


class CIPTests(TestCase):
    def setUp(self):
        self.co = make_company('ntfin43', 'NTFIN43')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.cip = ImmobilisationEnCours.objects.create(
            company=self.co, libelle='Chantier centrale',
            compte_encours='231', montant_cumule=Decimal('300000'))

    def test_mise_en_service_cree_immo(self):
        immo = services.mettre_en_service_encours(
            self.cip, date_mise_en_service=date(2026, 9, 1))
        self.cip.refresh_from_db()
        self.assertEqual(immo.cout, Decimal('300000'))
        self.assertEqual(self.cip.statut,
                         ImmobilisationEnCours.Statut.MIS_EN_SERVICE)
        self.assertEqual(self.cip.immobilisation_id, immo.id)


class RegistreProjectionTests(TestCase):
    def setUp(self):
        self.co = make_company('ntfin44', 'NTFIN44')
        self.immo = Immobilisation.objects.create(
            company=self.co, libelle='Onduleur', cout=Decimal('100000'),
            date_acquisition=date(2026, 1, 1))
        PlanAmortissement.objects.create(
            company=self.co, immobilisation=self.immo, duree_annees=25,
            base_amortissable=Decimal('100000'), date_debut=date(2026, 1, 1))
        # Vue IFRS par composants : durée 10 ans.
        ComposantImmobilisation.objects.create(
            company=self.co, immobilisation=self.immo, libelle='Onduleur',
            valeur=Decimal('100000'), duree_amortissement=10)
        self.ifrs = ReferentielComptable.objects.create(
            company=self.co, code=ReferentielComptable.Code.IFRS,
            libelle='IFRS', est_principal=False)

    def test_vnc_ifrs_differe_de_cgnc(self):
        cgnc = selectors.registre_immobilisations(
            self.co, referentiel=None, date_reference=date(2030, 6, 30))
        ifrs = selectors.registre_immobilisations(
            self.co, referentiel=self.ifrs, date_reference=date(2030, 6, 30))
        vnc_cgnc = cgnc['lignes'][0]['vnc']
        vnc_ifrs = ifrs['lignes'][0]['vnc']
        self.assertNotEqual(vnc_cgnc, vnc_ifrs)

    def test_projection_5_ans(self):
        data = selectors.projection_dotations(self.co, annees=5)
        actif = data['par_actif'][0]
        self.assertEqual(len(actif['projection']), 5)
        self.assertEqual(actif['dotation_annuelle'], Decimal('4000.00'))
