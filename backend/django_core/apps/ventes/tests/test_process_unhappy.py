"""YTEST5 — E2E chemins malheureux : devis refusé, devis expiré, avoir.

Trois cas, chacun assertant l'ABSENCE de l'effet aval interdit + le statut
correct :

  * devis « refusé » — le funnel CRM ne passe PAS à SIGNED (clé STAGES.py,
    jamais codée en dur) ;
  * devis « expiré » — aucun BonCommande n'est créé (la conversion
    ``convertir-bc`` exige le statut « accepté ») ;
  * avoir / crédit sur une facture existante — réutilise le code d'avoir déjà
    couvert par ``test_avoirs.py`` : le montant dû baisse et le statut de
    l'avoir est correct.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_process_unhappy -v 2
"""
from decimal import Decimal

from apps.crm.models import Lead
from apps.crm.stages import QUOTE_SENT, SIGNED
from apps.ventes.models import Avoir, BonCommande, Devis, Facture, LigneFacture
from testkit.base import TenantAPITestCase
from testkit.factories import ClientFactory, DevisFactory, ProduitFactory


class TestDevisRefuseUnhappyPath(TenantAPITestCase):
    def test_refuse_never_advances_lead_to_signed(self):
        """Un devis refusé ne fait JAMAIS avancer le lead à SIGNED."""
        api = self.client_as(role='responsable')
        lead = Lead.objects.create(
            company=self.company, nom='Lead Refuse E2E', stage=QUOTE_SENT)
        devis = DevisFactory(
            company=self.company, lead=lead,
            client=ClientFactory(company=self.company),
            statut=Devis.Statut.ENVOYE)

        resp = api.post(f'/api/django/ventes/devis/{devis.id}/refuser/', {
            'motif': 'Prix trop élevé', 'marquer_lead_perdu': True,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.REFUSE)
        lead.refresh_from_db()
        # Effet aval INTERDIT : le lead ne doit jamais atteindre SIGNED sur un
        # devis refusé.
        self.assertNotEqual(lead.stage, SIGNED)
        self.assertTrue(lead.perdu)

        # Effet aval INTERDIT : aucun BonCommande ne peut naître d'un devis
        # refusé (convertir-bc exige le statut « accepté »).
        resp_bc = api.post(
            f'/api/django/ventes/devis/{devis.id}/convertir-bc/', {},
            format='json')
        self.assertEqual(resp_bc.status_code, 400, resp_bc.data)
        self.assertFalse(BonCommande.objects.filter(devis=devis).exists())


class TestDevisExpireUnhappyPath(TenantAPITestCase):
    def test_expire_creates_no_bon_commande(self):
        """Un devis expiré ne peut produire aucun bon de commande."""
        api = self.client_as(role='responsable')
        devis = DevisFactory(
            company=self.company,
            client=ClientFactory(company=self.company),
            statut=Devis.Statut.EXPIRE)

        resp = api.post(
            f'/api/django/ventes/devis/{devis.id}/convertir-bc/', {},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertFalse(BonCommande.objects.filter(devis=devis).exists())

        # Statut inchangé : rester expiré, jamais basculer vers accepté par
        # effet de bord d'une tentative de conversion refusée.
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.EXPIRE)

        # Un devis figé (expiré) ne peut plus être librement édité (YDOCF2) —
        # confirme qu'il n'existe pas de porte dérobée vers « accepté ».
        resp_patch = api.patch(f'/api/django/ventes/devis/{devis.id}/', {
            'statut': Devis.Statut.ACCEPTE,
        }, format='json')
        self.assertEqual(resp_patch.status_code, 400, resp_patch.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.EXPIRE)


class TestAvoirUnhappyPath(TenantAPITestCase):
    """Chemin avoir / crédit — réutilise la garde et le calcul déjà couverts
    par test_avoirs.py, exercés ici depuis une facture ISSUE du parcours
    lead-to-cash (bout de chaîne du parcours malheureux « retour client »)."""

    def setUp(self):
        super().setUp()
        self.client_obj = ClientFactory(company=self.company)
        self.produit = ProduitFactory(
            company=self.company, sku='UNHAPPY-AVOIR',
            prix_vente=Decimal('2000.00'), quantite_stock=20)
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-UNHAPPY-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit,
            designation='Onduleur retourné', quantite=Decimal('1'),
            prix_unitaire=Decimal('2000'), taux_tva=Decimal('20.00'))

    def test_avoir_lowers_montant_du_and_is_emise(self):
        """L'avoir crédite la facture : montant_du baisse, statut correct,
        aucune facture supplémentaire n'est créée par effet de bord."""
        api = self.client_as(role='admin')
        montant_du_avant = self.facture.montant_du
        self.assertEqual(montant_du_avant, Decimal('2400.00'))

        resp = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'motif': 'Retour client — non conforme'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

        avoir = Avoir.objects.get(id=resp.data['id'])
        self.assertEqual(avoir.statut, Avoir.Statut.EMISE)
        self.assertEqual(avoir.total_ttc, Decimal('2400.00'))

        self.facture.refresh_from_db()
        self.assertEqual(self.facture.montant_du, Decimal('0.00'))
        self.assertLess(self.facture.montant_du, montant_du_avant)
        # Effet aval INTERDIT : un avoir ne crée jamais de facture additionnelle.
        self.assertEqual(
            Facture.objects.filter(client=self.client_obj).count(), 1)

    def test_avoir_on_draft_facture_rejected_no_avoir_created(self):
        """Effet aval interdit : pas d'avoir sur une facture encore brouillon."""
        self.facture.statut = Facture.Statut.BROUILLON
        self.facture.save(update_fields=['statut'])
        api = self.client_as(role='admin')
        resp = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'motif': 'x'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertFalse(Avoir.objects.filter(facture=self.facture).exists())
