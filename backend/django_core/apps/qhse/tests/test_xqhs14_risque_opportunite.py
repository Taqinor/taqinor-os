"""Tests XQHS14 — Registre des risques & opportunités SMQ (ISO 6.1) +
contexte/parties intéressées (clause 4).

Couvre :

* la criticité inhérente/résiduelle calculée et stockée au save() ;
* la liaison CAPA idempotente ;
* la détection des revues dues ;
* PartieInteressee et ContexteOrganisation (1 par société) ;
* le scoping société.
"""
from datetime import date, timedelta

from django.test import TestCase

from authentication.models import Company

from apps.qhse.models import (
    ActionCorrectivePreventive, ContexteOrganisation, NonConformite,
    PartieInteressee, RisqueOpportunite, RisqueOpportuniteCapa,
)
from apps.qhse.services import (
    lier_capa_risque_opportunite, risques_opportunites_revue_due,
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class CriticiteCalculeeTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs14-crit', 'CoXqhs14Crit')

    def test_criticite_inherente_calculee(self):
        ro = RisqueOpportunite.objects.create(
            company=self.company, description='Rupture fournisseur clé',
            probabilite_inherente=4, gravite_inherente=3)
        self.assertEqual(ro.criticite_inherente, 12)

    def test_criticite_residuelle_calculee_si_fournie(self):
        ro = RisqueOpportunite.objects.create(
            company=self.company, description='Risque X',
            probabilite_inherente=4, gravite_inherente=3,
            probabilite_residuelle=2, gravite_residuelle=2)
        self.assertEqual(ro.criticite_residuelle, 4)

    def test_criticite_residuelle_none_sans_traitement(self):
        ro = RisqueOpportunite.objects.create(
            company=self.company, description='Risque Y',
            probabilite_inherente=3, gravite_inherente=3)
        self.assertIsNone(ro.criticite_residuelle)


class LierCapaTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs14-capa', 'CoXqhs14Capa')
        self.ncr = NonConformite.objects.create(
            company=self.company, titre='NCR support')
        self.capa = ActionCorrectivePreventive.objects.create(
            company=self.company, non_conformite=self.ncr,
            description='Plan de mitigation')

    def test_lie_capa(self):
        ro = RisqueOpportunite.objects.create(
            company=self.company, description='Risque lié')
        lien = lier_capa_risque_opportunite(ro, self.capa)
        self.assertIsInstance(lien, RisqueOpportuniteCapa)
        self.assertEqual(ro.capa_liees.count(), 1)

    def test_idempotent(self):
        ro = RisqueOpportunite.objects.create(
            company=self.company, description='Risque lié 2')
        lier_capa_risque_opportunite(ro, self.capa)
        lier_capa_risque_opportunite(ro, self.capa)
        self.assertEqual(ro.capa_liees.count(), 1)


class RisquesOpportunitesRevueDueTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs14-due', 'CoXqhs14Due')

    def test_due_sans_date_revue(self):
        ro = RisqueOpportunite.objects.create(
            company=self.company, description='Nouveau risque')
        dus = risques_opportunites_revue_due(self.company)
        self.assertIn(ro, dus)

    def test_pas_due_avant_frequence(self):
        ro = RisqueOpportunite.objects.create(
            company=self.company, description='Risque récent',
            date_revue=date.today() - timedelta(days=10),
            frequence_revue_jours=180)
        dus = risques_opportunites_revue_due(self.company)
        self.assertNotIn(ro, dus)

    def test_due_apres_frequence_depassee(self):
        ro = RisqueOpportunite.objects.create(
            company=self.company, description='Risque ancien',
            date_revue=date.today() - timedelta(days=200),
            frequence_revue_jours=180)
        dus = risques_opportunites_revue_due(self.company)
        self.assertIn(ro, dus)

    def test_isolation_societe(self):
        autre = make_company('co-xqhs14-due-autre', 'CoXqhs14DueAutre')
        RisqueOpportunite.objects.create(
            company=self.company, description='Risque isolé')
        dus = risques_opportunites_revue_due(autre)
        self.assertEqual(dus, [])


class PartieInteresseeEtContexteTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs14-partie', 'CoXqhs14Partie')

    def test_cree_partie_interessee(self):
        partie = PartieInteressee.objects.create(
            company=self.company, partie='Client',
            attentes='Qualité et délais', pertinence=PartieInteressee.Pertinence.FORTE)
        self.assertEqual(partie.pertinence, PartieInteressee.Pertinence.FORTE)

    def test_contexte_unique_par_societe(self):
        ContexteOrganisation.objects.create(
            company=self.company, swot='Forces: équipe qualifiée')
        with self.assertRaises(Exception):
            ContexteOrganisation.objects.create(company=self.company, swot='Autre')
