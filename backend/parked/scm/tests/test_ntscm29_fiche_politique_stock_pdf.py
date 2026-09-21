"""NTSCM29 — Rapport imprimable « Politique de stock » par produit (interne,
jamais un PDF client).

Critère d'acceptation : le PDF généré ne contient aucun ``prix_achat`` ni
marge et s'ouvre correctement dans un test de génération."""
from django.test import TestCase

from apps.scm.models import PolitiqueStock
from apps.scm.services import generer_fiche_politique_stock, recalculer_politiques_stock
from apps.stock.models import Produit

from .helpers import auth, make_company, make_user


class FichePolitiqueStockPdfTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-fiche-politique', 'Supply Fiche Politique')
        self.admin = make_user(self.company, 'scm-fiche-politique-admin', 'admin')
        self.produit = Produit.objects.create(
            company=self.company, nom='Régulateur MPPT', prix_vente=2200,
            quantite_stock=60, prix_achat=1300)
        recalculer_politiques_stock(self.company)
        self.politique = PolitiqueStock.objects.get(
            company=self.company, produit=self.produit)

    def test_pdf_genere_sans_erreur_et_sans_prix_achat(self):
        pdf_bytes = generer_fiche_politique_stock(self.politique)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

    def test_endpoint_fiche_pdf(self):
        resp = auth(self.admin).get(
            f'/api/django/scm/politiques-stock/{self.politique.id}/fiche-pdf/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content.startswith(b'%PDF'))
