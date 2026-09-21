"""NTSCM28 — Tableau de bord SCM exécutif (KPI de synthèse).

Critère d'acceptation : les 4 KPI s'affichent avec des valeurs cohérentes sur
le jeu de données de test, aucun ``prix_achat`` n'apparaît en clair."""
from django.test import TestCase

from apps.scm.models import ClassificationABC
from apps.scm.selectors import tableau_bord_executif
from apps.stock.models import Produit

from .helpers import auth, make_company, make_user


class TableauBordExecutifTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-tb-exec', 'Supply TB Exécutif')
        self.admin = make_user(self.company, 'scm-tb-exec-admin', 'admin')
        self.produit = Produit.objects.create(
            company=self.company, nom='Coffret DC', prix_vente=1500,
            quantite_stock=40, prix_achat=900)
        ClassificationABC.objects.create(
            company=self.company, produit=self.produit, classe='A',
            valeur_cumulee_ht=60000, part_valeur_pct=100, rang=1)

    def test_4_kpi_presents_sans_prix_achat(self):
        resultat = tableau_bord_executif(self.company)
        for cle in (
                'taux_service_pct', 'otif_pondere_pct', 'mape_global_pct',
                'valeur_stock_par_classe_abc'):
            self.assertIn(cle, resultat)

        self.assertEqual(resultat['valeur_stock_par_classe_abc']['A'], '60000.00')
        # Le `prix_achat` du produit (900) ne doit apparaître NULLE PART dans
        # la sortie chiffrée du tableau de bord exécutif.
        self.assertNotIn('900', str(resultat['valeur_stock_par_classe_abc']))

    def test_endpoint_tableau_bord(self):
        resp = auth(self.admin).get('/api/django/scm/tableau-bord/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('valeur_stock_par_classe_abc', resp.data)
        self.assertEqual(resp.data['valeur_stock_par_classe_abc']['A'], '60000.00')
