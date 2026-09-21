"""NTSCM7 — Tableau de bord réappro consolidé.

Critère d'acceptation : la liste distingue visuellement les 3 statuts et
l'action groupée crée un BCF brouillon par fournisseur avec les bonnes
lignes.

Le backend ne peut pas vérifier le rendu VISUEL (frontend
``frontend/src/pages/scm/ReapproPage.jsx``) ; ce test couvre la partie
serveur : le sélecteur renvoie bien les 3 statuts distincts selon le rapport
stock-actuel/point-de-commande/délai, et l'action ``creer-bcf`` groupe
correctement par fournisseur.

``Produit``/``Fournisseur``/``MouvementStock`` créés directement via
``apps.stock.models`` et ``PrixFournisseur`` via ``apps.achats.models``
UNIQUEMENT pour construire la fixture de test (frontière cross-app,
CLAUDE.md — même justification que les tests NTSCM2/3/5/6)."""
from django.test import TestCase
from django.utils import timezone

from apps.achats.models import PrixFournisseur
from apps.scm.services import recalculer_politiques_stock
from apps.stock.models import BonCommandeFournisseur, Fournisseur, MouvementStock, Produit

from .helpers import auth, make_company, make_user


class TableauBordReapproTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-reappro', 'Supply Réappro')
        self.admin = make_user(self.company, 'scm-reappro-admin', 'admin')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur Solaire SARL')

        # 3 produits : consommation IDENTIQUE (10/jour, stable), stock actuel
        # différent -> 3 statuts distincts pour le même ROP (=180 avec le
        # délai fournisseur par défaut 15 j : 10x15 + stock_sécurité 30).
        self.produit_ok = Produit.objects.create(
            company=self.company, nom='Câble 4mm2 (stock sain)',
            prix_vente=5, quantite_stock=300, fournisseur=self.fournisseur)
        self.produit_a_commander = Produit.objects.create(
            company=self.company, nom='Connecteur MC4 (à commander)',
            prix_vente=8, quantite_stock=170, fournisseur=self.fournisseur)
        self.produit_rupture = Produit.objects.create(
            company=self.company, nom='Fusible DC (rupture imminente)',
            prix_vente=12, quantite_stock=50, fournisseur=self.fournisseur)

        for produit in (self.produit_ok, self.produit_a_commander, self.produit_rupture):
            self._seed_stable_history(produit, mensuel=300)  # -> 10/jour
            PrixFournisseur.objects.create(
                company=self.company, produit=produit, fournisseur=self.fournisseur,
                prix_achat=3)

        recalculer_politiques_stock(self.company)

    def _seed_stable_history(self, produit, *, mensuel):
        today = timezone.localdate()
        idx_dernier = today.year * 12 + (today.month - 1) - 1
        qty_restante = 100000
        for offset in range(5, -1, -1):
            idx = idx_dernier - offset
            y, m0 = divmod(idx, 12)
            mvt = MouvementStock.objects.create(
                company=self.company, produit=produit,
                type_mouvement=MouvementStock.TypeMouvement.SORTIE,
                quantite=mensuel, quantite_avant=qty_restante,
                quantite_apres=qty_restante - mensuel)
            qty_restante -= mensuel
            mvt.date = timezone.make_aware(timezone.datetime(y, m0 + 1, 15))
            mvt.save(update_fields=['date'])

    def test_three_distinct_statuses(self):
        resp = auth(self.admin).get('/api/django/scm/tableau-bord-reappro/')
        self.assertEqual(resp.status_code, 200, resp.data)
        par_produit = {row['produit_id']: row for row in resp.data}

        self.assertEqual(par_produit[self.produit_ok.id]['statut'], 'ok')
        self.assertEqual(
            par_produit[self.produit_a_commander.id]['statut'], 'a_commander')
        self.assertEqual(
            par_produit[self.produit_rupture.id]['statut'], 'rupture_imminente')

        statuts = {row['statut'] for row in resp.data}
        self.assertEqual(statuts, {'ok', 'a_commander', 'rupture_imminente'})

    def test_filter_by_statut(self):
        resp = auth(self.admin).get(
            '/api/django/scm/tableau-bord-reappro/?statut=rupture_imminente')
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['produit_id'], self.produit_rupture.id)

    def test_creer_bcf_groups_by_supplier_with_correct_lines(self):
        resp = auth(self.admin).post(
            '/api/django/scm/tableau-bord-reappro/creer-bcf/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        bons = resp.data['bons_crees']
        # Les 2 produits À COMMANDER (à_commander + rupture_imminente)
        # partagent le MÊME fournisseur -> un seul BCF groupé.
        self.assertEqual(len(bons), 1)
        self.assertEqual(bons[0]['fournisseur_id'], self.fournisseur.id)
        self.assertEqual(bons[0]['nb_lignes'], 2)

        bon = BonCommandeFournisseur.objects.get(id=bons[0]['bon_commande_id'])
        self.assertEqual(bon.company_id, self.company.id)
        self.assertEqual(bon.fournisseur_id, self.fournisseur.id)
        self.assertEqual(bon.statut, BonCommandeFournisseur.Statut.BROUILLON)
        produits_commandes = set(bon.lignes.values_list('produit_id', flat=True))
        self.assertEqual(
            produits_commandes,
            {self.produit_a_commander.id, self.produit_rupture.id})

    def test_tenant_isolation(self):
        other_company = make_company('scm-reappro-b', 'Supply Réappro B')
        other_admin = make_user(other_company, 'scm-reappro-admin-b', 'admin')
        resp = auth(other_admin).get('/api/django/scm/tableau-bord-reappro/')
        self.assertEqual(resp.data, [])

    def test_forbidden_for_non_authenticated(self):
        from rest_framework.test import APIClient

        resp = APIClient().get('/api/django/scm/tableau-bord-reappro/')
        self.assertIn(resp.status_code, (401, 403))
