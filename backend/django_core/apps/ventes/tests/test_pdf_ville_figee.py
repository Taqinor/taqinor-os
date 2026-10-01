# -*- coding: utf-8 -*-
"""QJR591 — le PDF garde la ville sur laquelle le devis a été chiffré et
l'affiche « X, près de Y ».

Constat : ``builder.py`` relisait la ville du lead à CHAQUE rendu : corriger
la ville d'un lead changeait en silence la production et le ROI d'un devis
ENVOYÉ. ``pipeline.rafraichir_etudes`` consigne désormais la ville de calcul
dans ``etude_params['ville_calcul']`` et le builder la lit.

Run :
    python manage.py test apps.ventes.tests.test_pdf_ville_figee -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

User = get_user_model()


class LibelleVille(SimpleTestCase):
    def test_pres_de_quand_elles_different(self):
        from apps.ventes.quote_engine.builder import _libelle_ville
        self.assertEqual(_libelle_ville('Douar X', 'Settat'),
                         'Douar X, près de Settat')
        self.assertEqual(_libelle_ville('Settat', 'Settat'), 'Settat')
        self.assertEqual(_libelle_ville('', 'Settat'), 'Settat')
        self.assertEqual(_libelle_ville('Agadir', ''), 'Agadir')
        self.assertEqual(_libelle_ville('', ''), '')


class VilleFigeeAuChiffrage(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(slug='qjr591', nom='qjr591')
        cls.user = User.objects.create_user(
            username='qjr591', password='x', company=cls.company,
            role_legacy='admin')
        cls.client_obj = Client.objects.create(company=cls.company,
                                               nom='QJR591')

    def _devis(self, ville, ville_reference, statut='envoye'):
        lead = Lead.objects.create(
            company=self.company, nom='QJR591', client=self.client_obj,
            ville=ville, ville_reference=ville_reference,
            facture_hiver=Decimal('900'), ete_differente=False,
            type_installation='residentiel')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR591-%s' % lead.pk,
            client=self.client_obj, lead=lead, statut=statut,
            taux_tva=Decimal('20.00'), created_by=self.user,
            mode_installation='residentiel')
        for ordre, (nom, qte, prix) in enumerate((
                ('Panneau Jinko 550W', 10, '1100'),
                ('Onduleur réseau Huawei 5kW', 1, '14000'))):
            produit = Produit.objects.create(
                company=self.company, nom=nom,
                sku='Q591-%s-%d' % (lead.pk, ordre),
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=10)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=nom,
                quantite=Decimal(qte), prix_unitaire=Decimal(prix),
                ordre=ordre)
        return lead, devis

    def _chiffrer(self, devis):
        from apps.ventes.domain.pipeline import rafraichir_etudes
        rafraichir_etudes(devis)
        devis.refresh_from_db()
        return devis

    def test_ville_consignee_au_chiffrage(self):
        _lead, devis = self._devis('Douar X', 'Settat')
        devis = self._chiffrer(devis)
        self.assertEqual(devis.etude_params.get('ville_calcul'),
                         {'ville': 'Douar X', 'reference': 'Settat'})

    def test_patch_lead_ne_change_ni_ville_ni_productible(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        lead, devis = self._devis('Settat', '')
        devis = self._chiffrer(devis)
        avant = build_quote_data(devis)
        Lead.objects.filter(pk=lead.pk).update(ville='Marrakech')
        devis = Devis.objects.get(pk=devis.pk)
        apres = build_quote_data(devis)
        self.assertEqual(apres['client_city'], 'Settat')
        self.assertEqual(apres['client_ville_libelle'], 'Settat')
        self.assertEqual(
            (apres.get('hypotheses') or {}).get('productible_ville'),
            (avant.get('hypotheses') or {}).get('productible_ville'))
        self.assertEqual(apres.get('production_annuelle'),
                         avant.get('production_annuelle'))

    def test_reappliquer_lead_reprend_la_ville_du_lead(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        lead, devis = self._devis('Settat', '')
        devis = self._chiffrer(devis)
        Lead.objects.filter(pk=lead.pk).update(ville='Marrakech')
        from apps.ventes.domain.pipeline import reappliquer_lead
        reappliquer_lead(Devis.objects.get(pk=devis.pk), user=self.user,
                         company=self.company)
        devis = Devis.objects.get(pk=devis.pk)
        self.assertEqual(build_quote_data(devis)['client_city'], 'Marrakech')

    def test_libelle_pres_de(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        _lead, devis = self._devis('Douar X', 'Settat')
        devis = self._chiffrer(devis)
        data = build_quote_data(devis)
        self.assertEqual(data['client_city'], 'Settat')
        self.assertEqual(data['client_ville_libelle'],
                         'Douar X, près de Settat')

    def test_devis_ancien_sans_ville_calcul_relit_le_lead(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        _lead, devis = self._devis('Douar X', 'Settat')
        self.assertNotIn('ville_calcul', devis.etude_params or {})
        data = build_quote_data(devis)
        self.assertEqual(data['client_city'], 'Settat')
        self.assertEqual(data['client_ville_libelle'],
                         'Douar X, près de Settat')
