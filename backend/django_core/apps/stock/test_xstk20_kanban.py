"""XSTK20 — Réappro kanban / deux-bacs par scan de carte.

Couvre :
  - impression d'une carte kanban depuis l'écran emplacement
    (`EmplacementStockViewSet.etiquettes_kanban`), jeton
    `KANBAN:<produit>:<emplacement>`, seuil_max (FG62) affiché en sous-titre ;
  - scan de la carte (`resolve`) crée une DemandeTransfert (FG325) préremplie
    depuis le dépôt principal, quantité = seuil_max s'il est défini ;
  - IDEMPOTENCE : un second scan tant qu'une demande demandé/approuvé existe
    pour le même couple (produit, destination) NE duplique PAS ;
  - un nouveau scan APRÈS exécution/refus de la précédente demande recrée
    une nouvelle demande (le cycle kanban continue) ;
  - le dépôt principal ne peut pas être la destination d'un réappro kanban ;
  - scoping société strict (jamais d'accès/fuite cross-tenant) ;
  - AUCUN prix d'achat/marge dans la sortie carte/scan.

Run :
    python manage.py test apps.stock.test_xstk20_kanban -v2
"""
from apps.installations.models import DemandeTransfert
from apps.stock.models import EmplacementStock, Produit, StockEmplacement
from apps.stock import labels
from testkit.base import TenantAPITestCase


class TestKanbanCards(TenantAPITestCase):
    """Impression de la carte (écran emplacement)."""

    def setUp(self):
        super().setUp()
        self.principal = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt principal', is_principal=True)
        self.camion = EmplacementStock.objects.create(
            company=self.company, nom='Camionnette 1')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='PAN-550',
            prix_vente=1500, prix_achat=900)
        StockEmplacement.objects.create(
            company=self.company, produit=self.produit,
            emplacement=self.camion, quantite=2, seuil_min=1, seuil_max=10)

    def test_etiquette_kanban_html_contains_token_and_seuil(self):
        resp = self.client_as().get(
            f'/api/django/stock/emplacements/{self.camion.id}/'
            f'etiquettes-kanban/?ids={self.produit.id}&sortie=html')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        token = labels.kanban_token(self.produit.id, self.camion.id)
        self.assertIn(token, body)
        self.assertIn('recompl. 10', body)

    def test_etiquette_kanban_never_exposes_prix_achat(self):
        resp = self.client_as().get(
            f'/api/django/stock/emplacements/{self.camion.id}/'
            f'etiquettes-kanban/?ids={self.produit.id}&sortie=html')
        self.assertNotIn('900', resp.content.decode())

    def test_etiquette_kanban_requires_ids(self):
        resp = self.client_as().get(
            f'/api/django/stock/emplacements/{self.camion.id}/'
            f'etiquettes-kanban/?sortie=html')
        self.assertEqual(resp.status_code, 400)

    def test_etiquette_kanban_pdf_default_output(self):
        resp = self.client_as().get(
            f'/api/django/stock/emplacements/{self.camion.id}/'
            f'etiquettes-kanban/?ids={self.produit.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_readonly_role_can_print(self):
        resp = self.client_as(role='Commerciale').get(
            f'/api/django/stock/emplacements/{self.camion.id}/'
            f'etiquettes-kanban/?ids={self.produit.id}&sortie=html')
        self.assertEqual(resp.status_code, 200)


class TestKanbanScanCreatesDemande(TenantAPITestCase):
    """Scan de la carte → DemandeTransfert préremplie (idempotent)."""

    def setUp(self):
        super().setUp()
        self.principal = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt principal', is_principal=True)
        self.camion = EmplacementStock.objects.create(
            company=self.company, nom='Camionnette 1')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='PAN-550',
            prix_vente=1500, prix_achat=900)
        self.token = labels.kanban_token(self.produit.id, self.camion.id)

    def _scan(self, token=None, client=None):
        client = client or self.client_as()
        return client.get(
            f'/api/django/stock/produits/resolve/?code={token or self.token}')

    def test_scan_without_seuil_creates_demande_with_default_qty(self):
        resp = self._scan()
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['type'], 'demande_transfert')
        self.assertTrue(data['created'])
        self.assertEqual(data['quantite'], 1)
        demande = DemandeTransfert.objects.get(id=data['id'])
        self.assertEqual(demande.produit_id, self.produit.id)
        self.assertEqual(demande.source_id, self.principal.id)
        self.assertEqual(demande.destination_id, self.camion.id)
        self.assertEqual(demande.statut, DemandeTransfert.Statut.DEMANDE)
        self.assertEqual(demande.company_id, self.company.id)

    def test_scan_uses_seuil_max_as_quantite(self):
        StockEmplacement.objects.create(
            company=self.company, produit=self.produit,
            emplacement=self.camion, quantite=2, seuil_min=1, seuil_max=8)
        resp = self._scan()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['quantite'], 8)

    def test_second_scan_does_not_duplicate_open_demande(self):
        first = self._scan().json()
        second = self._scan().json()
        self.assertTrue(first['created'])
        self.assertFalse(second['created'])
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(
            DemandeTransfert.objects.filter(
                company=self.company, produit=self.produit,
                destination=self.camion).count(),
            1)

    def test_scan_after_demande_executed_creates_new_one(self):
        first_id = self._scan().json()['id']
        demande = DemandeTransfert.objects.get(id=first_id)
        demande.statut = DemandeTransfert.Statut.EXECUTE
        demande.save(update_fields=['statut'])

        second = self._scan().json()
        self.assertTrue(second['created'])
        self.assertNotEqual(second['id'], first_id)
        self.assertEqual(
            DemandeTransfert.objects.filter(
                company=self.company, produit=self.produit,
                destination=self.camion).count(),
            2)

    def test_scan_after_demande_refused_creates_new_one(self):
        first_id = self._scan().json()['id']
        demande = DemandeTransfert.objects.get(id=first_id)
        demande.statut = DemandeTransfert.Statut.REFUSE
        demande.save(update_fields=['statut'])

        second = self._scan().json()
        self.assertTrue(second['created'])
        self.assertNotEqual(second['id'], first_id)

    def test_scan_approved_demande_still_blocks_duplicate(self):
        first_id = self._scan().json()['id']
        demande = DemandeTransfert.objects.get(id=first_id)
        demande.statut = DemandeTransfert.Statut.APPROUVE
        demande.save(update_fields=['statut'])

        second = self._scan().json()
        self.assertFalse(second['created'])
        self.assertEqual(second['id'], first_id)

    def test_principal_as_destination_rejected(self):
        token = labels.kanban_token(self.produit.id, self.principal.id)
        resp = self._scan(token=token)
        self.assertEqual(resp.status_code, 400)

    def test_unknown_produit_404_equivalent_400(self):
        token = labels.kanban_token(999999, self.camion.id)
        resp = self._scan(token=token)
        self.assertEqual(resp.status_code, 400)

    def test_malformed_kanban_token_400(self):
        resp = self._scan(token=f'KANBAN:{self.produit.id}:abc')
        self.assertEqual(resp.status_code, 400)

    def test_cross_tenant_produit_cannot_be_scanned(self):
        other_client = self.client_as(user=self.other_user)
        resp = self._scan(client=other_client)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(
            DemandeTransfert.objects.filter(
                company=self.other_company, produit_id=self.produit.id)
            .exists())

    def test_scan_response_never_exposes_prix_achat(self):
        resp = self._scan()
        self.assertNotIn('900', resp.content.decode())
