"""QG2 — Le cache d'idempotence du rendu PDF doit refléter les éditions.

Avant QG2, la signature de rendu était keyée sur (devis_id, pdf_options)
uniquement : après un « Éditer » (lignes/remise changées), les MÊMES options
renvoyaient l'ANCIEN PDF depuis MinIO. On intègre désormais une empreinte du
CONTENU du devis (`_content_version`) à la signature :

  * édition → la signature change (cache raté → re-rendu, PDF à jour) ;
  * contenu inchangé → la signature reste stable (cache conservé → pas de
    re-rendu inutile).

Ce module teste les fonctions PURES de signature (aucune infra MinIO/Celery
requise) : c'est ce qui gouverne le hit/miss du cache.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.tasks import _content_version, _render_signature


class RenderSignatureTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='QG2 Co', slug='qg2-co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QG2')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='PV-550',
            prix_vente=Decimal('1000'))
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QG2-0001',
            client=self.client_obj, statut=Devis.Statut.BROUILLON)
        self.ligne = LigneDevis.objects.create(
            devis=self.devis, produit=self.produit, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('20'))
        self.opts = {'pdf_mode': 'full'}

    def test_unchanged_devis_keeps_stable_signature(self):
        """À contenu inchangé, la signature est stable → cache conservé."""
        sig1 = _render_signature(self.devis.id, self.opts)
        sig2 = _render_signature(self.devis.id, self.opts)
        self.assertEqual(sig1, sig2)
        self.assertTrue(_content_version(self.devis.id))

    def test_editing_line_quantity_changes_signature(self):
        """Éditer une quantité change la signature → cache raté → re-rendu."""
        sig_before = _render_signature(self.devis.id, self.opts)
        self.ligne.quantite = Decimal('12')
        self.ligne.save(update_fields=['quantite'])
        sig_after = _render_signature(self.devis.id, self.opts)
        self.assertNotEqual(sig_before, sig_after)

    def test_editing_line_price_changes_signature(self):
        sig_before = _render_signature(self.devis.id, self.opts)
        self.ligne.prix_unitaire = Decimal('1100')
        self.ligne.save(update_fields=['prix_unitaire'])
        sig_after = _render_signature(self.devis.id, self.opts)
        self.assertNotEqual(sig_before, sig_after)

    def test_adding_and_removing_line_changes_signature(self):
        sig0 = _render_signature(self.devis.id, self.opts)
        extra = LigneDevis.objects.create(
            devis=self.devis, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20'))
        sig1 = _render_signature(self.devis.id, self.opts)
        self.assertNotEqual(sig0, sig1)
        extra.delete()
        sig2 = _render_signature(self.devis.id, self.opts)
        self.assertEqual(sig0, sig2)  # retour au contenu d'origine

    def test_changing_global_discount_changes_signature(self):
        sig_before = _render_signature(self.devis.id, self.opts)
        self.devis.remise_globale = Decimal('10')
        self.devis.save(update_fields=['remise_globale'])
        sig_after = _render_signature(self.devis.id, self.opts)
        self.assertNotEqual(sig_before, sig_after)

    def test_different_pdf_options_still_differ(self):
        """Les options de format restent discriminantes (comportement conservé)."""
        sig_full = _render_signature(self.devis.id, {'pdf_mode': 'full'})
        sig_one = _render_signature(self.devis.id, {'pdf_mode': 'onepage'})
        self.assertNotEqual(sig_full, sig_one)
