"""NTCPQ11 — Clauses/CGV dynamiques par type de deal + snapshot figé à l'envoi."""
from decimal import Decimal

from django.test import TestCase

from apps.cpq.models import ClauseCGV
from apps.cpq.selectors import clauses_applicables
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.services import (
    contexte_clauses_devis, figer_clauses_devis, mark_devis_sent,
)
from testkit.factories import CompanyFactory, DevisFactory, ProduitFactory


class TestClausesCGV(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.produit = ProduitFactory(
            company=self.company, prix_vente=Decimal('600000.00'))
        self.clause = ClauseCGV.objects.create(
            company=self.company, nom='Garantie étendue',
            corps_texte='Garantie étendue 5 ans sur les équipements.',
            type_deal='industriel',
            applicable_si={
                'op': 'and',
                'conditions': [
                    {'field': 'montant', 'operator': 'gt', 'value': 500000},
                ],
            })

    def _devis(self, mode):
        devis = DevisFactory(company=self.company, mode_installation=mode)
        # Désignation « Onduleur réseau » : le builder du moteur de devis
        # (quote_engine/builder.py) refuse le rendu à options tant qu'aucune
        # ligne n'expose un onduleur — sans lien avec la logique des clauses.
        LigneDevis.objects.create(
            devis=devis, produit=self.produit,
            designation=f'Onduleur réseau {self.produit.nom}',
            quantite=Decimal('1'),
            prix_unitaire=Decimal('600000.00'))
        return devis

    def test_contexte_expose_type_deal_et_montant(self):
        devis = self._devis('industriel')
        ctx = contexte_clauses_devis(devis)
        self.assertEqual(ctx['type_deal'], 'industriel')
        self.assertGreater(ctx['montant'], 500000)
        self.assertNotIn('marge', ctx)

    def test_clause_sapplique_a_un_industriel_au_dessus_du_seuil(self):
        devis = self._devis('industriel')
        clauses = clauses_applicables(
            company=self.company, context=contexte_clauses_devis(devis))
        self.assertEqual([c['nom'] for c in clauses], ['Garantie étendue'])

    def test_clause_invisible_sur_un_residentiel_standard(self):
        devis = DevisFactory(
            company=self.company, mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=devis, produit=self.produit,
            designation=self.produit.nom, quantite=Decimal('1'),
            prix_unitaire=Decimal('30000.00'))
        clauses = clauses_applicables(
            company=self.company, context=contexte_clauses_devis(devis))
        self.assertEqual(clauses, [])

    def test_clause_invisible_sous_le_seuil_de_montant(self):
        devis = DevisFactory(
            company=self.company, mode_installation='industriel')
        LigneDevis.objects.create(
            devis=devis, produit=self.produit,
            designation=self.produit.nom, quantite=Decimal('1'),
            prix_unitaire=Decimal('10000.00'))
        clauses = clauses_applicables(
            company=self.company, context=contexte_clauses_devis(devis))
        self.assertEqual(clauses, [])

    def test_clause_inactive_ignoree(self):
        self.clause.actif = False
        self.clause.save(update_fields=['actif'])
        devis = self._devis('industriel')
        self.assertEqual(clauses_applicables(
            company=self.company,
            context=contexte_clauses_devis(devis)), [])

    def test_isolation_societe(self):
        autre = CompanyFactory()
        devis = self._devis('industriel')
        self.assertEqual(clauses_applicables(
            company=autre, context=contexte_clauses_devis(devis)), [])

    def test_snapshot_fige_a_lenvoi_et_jamais_recalcule(self):
        devis = self._devis('industriel')
        self.assertIsNone(devis.clauses_appliquees)
        mark_devis_sent(devis=devis)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertEqual(
            [c['nom'] for c in devis.clauses_appliquees], ['Garantie étendue'])
        # Éditer la clause après l'envoi ne réécrit JAMAIS le snapshot.
        self.clause.corps_texte = 'TEXTE MODIFIÉ APRÈS ENVOI'
        self.clause.save(update_fields=['corps_texte'])
        figer_clauses_devis(devis)
        devis.refresh_from_db()
        self.assertEqual(
            devis.clauses_appliquees[0]['corps_texte'],
            'Garantie étendue 5 ans sur les équipements.')

    def test_snapshot_vide_reste_fige(self):
        devis = self._devis('residentiel')
        figer_clauses_devis(devis)
        devis.refresh_from_db()
        self.assertEqual(devis.clauses_appliquees, [])

    def test_builder_expose_les_clauses_en_lecture_seule(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis('industriel')
        figer_clauses_devis(devis)
        devis.refresh_from_db()
        data = build_quote_data(devis)
        self.assertEqual(
            [c['nom'] for c in data['clauses_cgv']], ['Garantie étendue'])

    def test_builder_sans_clause_nexpose_pas_la_cle(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis('residentiel')
        data = build_quote_data(devis)
        self.assertNotIn('clauses_cgv', data)
