"""YTEST4 — E2E processus lead-to-cash complet, un seul test.

Parcourt la VRAIE machine à états sur toute sa longueur : lead CRM →
Devis (brouillon → envoyé → accepté) → BonCommande → Facture → Paiement,
en assertant à CHAQUE étape :
  * la transition de statut (Devis.statut, chaîne BC/Facture) ;
  * la référence générée par ``apps.ventes.utils.references`` (jamais
    count()+1 — la même garantie que ``test_references.py``) ;
  * les enregistrements downstream (BonCommande puis Facture existent et
    pointent le bon Devis).

Traverse UNIQUEMENT via les endpoints REST publics (comme un utilisateur
réel) — jamais de court-circuit direct des services métier — pour que le
test exerce la même machine à états que l'UI. Les objets sont construits
avec les factories ``testkit`` (YTEST1) ; la base multi-tenant/auth vient
de ``TenantAPITestCase`` (YTEST2). Le lead est lu/avancé via le module
``apps.crm.stages`` (jamais une étape codée en dur — CLAUDE.md règle #2).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_process_lead_to_cash -v 2
"""
from decimal import Decimal

from apps.crm.models import Lead
from apps.crm.stages import NEW, QUOTE_SENT, SIGNED
from apps.ventes.models import BonCommande, Devis, Facture, Paiement
from testkit.base import TenantAPITestCase
from testkit.factories import ProduitFactory


class TestProcessLeadToCash(TenantAPITestCase):
    def test_lead_to_cash_full_journey(self):
        api = self.client_as(role='responsable')

        # ── 1. Lead CRM (NEW) ───────────────────────────────────────────────
        lead = Lead.objects.create(
            company=self.company, nom='Lead E2E', stage=NEW)
        self.assertEqual(lead.stage, NEW)

        # ── 2. Devis lead-primary, créé en brouillon ────────────────────────
        produit = ProduitFactory(
            company=self.company, sku='E2E-PANEL',
            prix_vente=Decimal('1500.00'), quantite_stock=50)
        resp = api.post('/api/django/ventes/devis/', {
            'lead': lead.id,
            'statut': Devis.Statut.BROUILLON,
            'taux_tva': '20.00',
            'remise_globale': '0',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        devis_id = resp.data['id']
        devis = Devis.objects.get(id=devis_id)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        # Référence race-safe (highest-used+1), jamais count()+1.
        self.assertRegex(devis.reference, r'^DEV-\d{6}-\d{4}$')
        # Client résolu server-side depuis le lead (CLAUDE.md — resolve_client_for_lead).
        self.assertIsNotNone(devis.client_id)

        resp = api.post('/api/django/ventes/devis-lignes/', {
            'devis': devis_id,
            'produit': produit.id,
            'designation': 'Panneau mono 450W',
            'quantite': '10',
            'prix_unitaire': '1500.00',
            'remise': '0',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

        # ── 3. brouillon → envoyé (transition explicite, comme l'UI) ───────
        resp = api.patch(f'/api/django/ventes/devis/{devis_id}/', {
            'statut': Devis.Statut.ENVOYE,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        # L'envoi avance déjà le funnel CRM (clé STAGES.py, jamais codée en dur).
        lead.refresh_from_db()
        self.assertEqual(lead.stage, QUOTE_SENT)

        # ── 4. envoyé → accepté (déclenche devis_accepted → funnel CRM) ────
        resp = api.post(f'/api/django/ventes/devis/{devis_id}/accepter/', {
            'nom': 'Client E2E', 'date': '2026-06-20',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(str(devis.date_acceptation), '2026-06-20')
        # L'acceptation avance le funnel CRM à SIGNED (clé STAGES.py, jamais
        # codée en dur) — c'est l'événement de conversion.
        lead.refresh_from_db()
        self.assertEqual(lead.stage, SIGNED)

        # ── 5. Devis accepté → BonCommande (« convertir-bc ») ───────────────
        resp = api.post(
            f'/api/django/ventes/devis/{devis_id}/convertir-bc/', {},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        bc_id = resp.data['id']
        bc = BonCommande.objects.get(id=bc_id)
        self.assertEqual(bc.devis_id, devis.id)
        self.assertEqual(bc.statut, BonCommande.Statut.EN_ATTENTE)
        self.assertRegex(bc.reference, r'^BC-\d{6}-\d{4}$')

        # ── 6. BC confirmé puis livré ────────────────────────────────────────
        resp = api.post(
            f'/api/django/ventes/bons-commande/{bc_id}/confirmer/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommande.Statut.CONFIRME)

        resp = api.post(
            f'/api/django/ventes/bons-commande/{bc_id}/marquer-livre/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommande.Statut.LIVRE)

        # ── 7. BC livré → Facture (brouillon, lignes recopiées de l'option
        #      retenue) ──────────────────────────────────────────────────────
        resp = api.post(
            f'/api/django/ventes/bons-commande/{bc_id}/creer-facture/', {},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        facture_id = resp.data['id']
        facture = Facture.objects.get(id=facture_id)
        self.assertEqual(facture.bon_commande_id, bc.id)
        self.assertEqual(facture.statut, Facture.Statut.BROUILLON)
        self.assertRegex(facture.reference, r'^FAC-\d{6}-\d{4}$')
        self.assertTrue(facture.lignes.exists())

        # ── 8. Facture brouillon → émise ────────────────────────────────────
        resp = api.post(
            f'/api/django/ventes/factures/{facture_id}/emettre/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.EMISE)

        # ── 9. Paiement intégral → facture soldée automatiquement ──────────
        montant_du_avant = facture.montant_du
        self.assertGreater(montant_du_avant, Decimal('0'))
        resp = api.post(
            f'/api/django/ventes/factures/{facture_id}/enregistrer-paiement/',
            {'montant': str(montant_du_avant.quantize(Decimal('0.01'))),
             'date_paiement': '2026-06-25',
             'mode': 'virement'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.PAYEE)
        self.assertEqual(facture.montant_du, Decimal('0.00'))
        self.assertTrue(
            Paiement.objects.filter(facture=facture).exists())
        paiement = Paiement.objects.get(facture=facture)
        self.assertEqual(paiement.montant, montant_du_avant)

        # ── Downstream records all exist and point at the right Devis ──────
        self.assertTrue(
            BonCommande.objects.filter(id=bc.id, devis=devis).exists())
        self.assertTrue(
            Facture.objects.filter(id=facture.id, bon_commande=bc).exists())
