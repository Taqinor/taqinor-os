"""NTSCM20 — Suggestions de transfert multi-sites pilotées par écart
offre/demande (anticipatif, étend FG326 réactif).

Critère d'acceptation : un dépôt A avec surstock projeté +50 et un dépôt B
avec rupture projetée -30 sur le même produit apparaissent comme paire
suggérée avec quantité 30.

``EmplacementStock``/``StockEmplacement`` créés directement via
``apps.stock.models`` UNIQUEMENT pour construire la fixture de test
(frontière cross-app, CLAUDE.md)."""
from django.test import TestCase
from django.utils import timezone

from apps.scm.models import PrevisionDemande
from apps.scm.selectors import suggerer_transferts_inter_sites
from apps.stock.models import EmplacementStock, Produit, StockEmplacement

from .helpers import auth, make_company, make_user


class SuggestionsTransfertInterSitesTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-transfert', 'Supply Transfert')
        self.admin = make_user(self.company, 'scm-transfert-admin', 'admin')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W', prix_vente=1200,
            quantite_stock=120)

        self.nord = EmplacementStock.objects.create(
            company=self.company, nom='Nord', is_principal=False)
        self.sud = EmplacementStock.objects.create(
            company=self.company, nom='Sud', is_principal=False)

        StockEmplacement.objects.create(
            company=self.company, produit=self.produit, emplacement=self.nord,
            quantite=100, seuil_max=50)
        StockEmplacement.objects.create(
            company=self.company, produit=self.produit, emplacement=self.sud,
            quantite=20, seuil_min=0)

        self.periode = timezone.localdate().strftime('%Y-%m')
        PrevisionDemande.objects.create(
            company=self.company, produit=self.produit, segment='Nord',
            periode=self.periode, quantite_prevue=0)
        PrevisionDemande.objects.create(
            company=self.company, produit=self.produit, segment='Sud',
            periode=self.periode, quantite_prevue=50)

    def test_paire_suggeree_avec_quantite_min_surplus_deficit(self):
        suggestions = suggerer_transferts_inter_sites(self.company)
        self.assertEqual(len(suggestions), 1)
        suggestion = suggestions[0]
        self.assertEqual(suggestion['produit_id'], self.produit.id)
        self.assertEqual(suggestion['emplacement_source_id'], self.nord.id)
        self.assertEqual(suggestion['emplacement_destination_id'], self.sud.id)
        self.assertEqual(suggestion['quantite_suggeree'], 30)

    def test_aucune_suggestion_sans_ecart(self):
        StockEmplacement.objects.filter(
            company=self.company, emplacement=self.sud).update(quantite=80)
        suggestions = suggerer_transferts_inter_sites(self.company)
        self.assertEqual(suggestions, [])

    def test_endpoint_suggestions_transfert(self):
        resp = auth(self.admin).get('/api/django/scm/suggestions-transfert/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['quantite_suggeree'], 30)
