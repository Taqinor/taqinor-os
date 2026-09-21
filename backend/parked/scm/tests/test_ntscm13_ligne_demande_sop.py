"""NTSCM13 — Snapshot demande consensuelle par cycle S&OP.

Critère d'acceptation : modifier ``PrevisionDemande`` après le gel n'affecte
plus les lignes du cycle déjà en revue, vérifié par test.

``Produit`` créé directement via ``apps.stock.models`` UNIQUEMENT pour
construire la fixture de test (frontière cross-app, CLAUDE.md)."""
from decimal import Decimal

from django.test import TestCase

from apps.scm.models import CyclePlanificationSOP, LigneDemandeSOP, PrevisionDemande
from apps.scm.services import avancer_statut_cycle, geler_previsions_cycle
from apps.stock.models import Produit

from .helpers import auth, make_company, make_user


class GelerPrevisionsCycleTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-ligne-demande', 'Supply Ligne Demande')
        self.admin = make_user(self.company, 'scm-ligne-demande-admin', 'admin')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W', prix_vente=1200)
        PrevisionDemande.objects.create(
            company=self.company, produit=self.produit, segment='residentiel',
            periode='2026-09', quantite_prevue=Decimal('70'))
        PrevisionDemande.objects.create(
            company=self.company, produit=self.produit, segment='industriel',
            periode='2026-09', quantite_prevue=Decimal('30'))
        self.cycle = CyclePlanificationSOP.objects.create(
            company=self.company, periode='2026-09')

    def test_gel_aggregates_all_segments_for_a_product(self):
        lignes = geler_previsions_cycle(self.cycle)
        self.assertEqual(len(lignes), 1)
        ligne = lignes[0]
        self.assertEqual(ligne.produit_id, self.produit.id)
        self.assertEqual(ligne.quantite_prevision_systeme, Decimal('100.00'))
        self.assertEqual(ligne.quantite_finale, Decimal('100.00'))

    def test_modifying_prevision_after_freeze_does_not_affect_frozen_line(self):
        avancer_statut_cycle(self.cycle, self.admin)  # brouillon -> revue_demande
        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.statut, CyclePlanificationSOP.Statut.REVUE_DEMANDE)

        ligne = LigneDemandeSOP.objects.get(cycle=self.cycle, produit=self.produit)
        self.assertEqual(ligne.quantite_prevision_systeme, Decimal('100.00'))

        # On modifie la prévision APRÈS le gel — la ligne déjà en revue ne
        # doit plus bouger (`geler_previsions_cycle` n'est rappelé qu'au
        # passage brouillon -> revue_demande, jamais aux étapes suivantes).
        prevision = PrevisionDemande.objects.get(
            company=self.company, produit=self.produit, segment='residentiel',
            periode='2026-09')
        prevision.quantite_prevue = Decimal('9999')
        prevision.save()

        # Avance à l'étape suivante (revue_offre) : ne rejoue PAS le gel.
        avancer_statut_cycle(self.cycle, self.admin)

        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite_prevision_systeme, Decimal('100.00'))
        self.assertEqual(ligne.quantite_finale, Decimal('100.00'))

    def test_quantite_finale_uses_adjustment_when_present(self):
        geler_previsions_cycle(self.cycle)
        ligne = LigneDemandeSOP.objects.get(cycle=self.cycle, produit=self.produit)
        ligne.quantite_ajustee_commercial = Decimal('150')
        ligne.motif_ajustement = 'Grosse commande signée hors prévision'
        ligne.save()
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite_finale, Decimal('150.00'))
        # Le système gelé reste visible, distinct de l'ajustement.
        self.assertEqual(ligne.quantite_prevision_systeme, Decimal('100.00'))


class AjusterDemandeApiTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-ligne-demande-api', 'Supply Ligne Demande API')
        self.admin = make_user(self.company, 'scm-ligne-demande-api-admin', 'admin')
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie 5kWh', prix_vente=15000)
        PrevisionDemande.objects.create(
            company=self.company, produit=self.produit, periode='2026-10',
            quantite_prevue=Decimal('40'))
        self.cycle = CyclePlanificationSOP.objects.create(
            company=self.company, periode='2026-10')
        avancer_statut_cycle(self.cycle, self.admin)  # gèle la demande

    def test_ajuster_demande_requires_motif(self):
        resp = auth(self.admin).post(
            f'/api/django/scm/cycles-sop/{self.cycle.id}/ajuster-demande/',
            {'produit_id': self.produit.id, 'quantite_ajustee': '55'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_ajuster_demande_updates_quantite_finale(self):
        resp = auth(self.admin).post(
            f'/api/django/scm/cycles-sop/{self.cycle.id}/ajuster-demande/',
            {
                'produit_id': self.produit.id, 'quantite_ajustee': '55',
                'motif': 'Retour terrain commercial',
            }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['quantite_finale'], '55.00')
        self.assertEqual(resp.data['quantite_prevision_systeme'], '40.00')

    def test_lignes_demande_endpoint(self):
        resp = auth(self.admin).get(
            f'/api/django/scm/cycles-sop/{self.cycle.id}/lignes-demande/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['produit'], self.produit.id)
