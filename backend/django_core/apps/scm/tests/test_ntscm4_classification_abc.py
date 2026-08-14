"""NTSCM4 — Classification ABC des articles.

Critère d'acceptation : sur un jeu de données avec 3 produits dominant 80% du
volume valeur, ceux-ci sont classés A ; test vérifie la somme des classes =
100% des produits.

ADAPTATION DE PÉRIMÈTRE — voir ``apps/scm/models.py::ClassificationABC`` et
``apps/scm/selectors.py::classifier_abc`` : le plan d'origine prévoyait un
champ persisté sur ``stock.Produit`` ; cette lane ne peut pas écrire dans
``apps/stock`` (frontière cross-app, CLAUDE.md), le classement est donc
persisté dans ``scm.ClassificationABC``.

``Produit``/``MouvementStock`` créés directement via ``apps.stock.models``
UNIQUEMENT pour construire la fixture de test (même justification que les
tests NTSCM2/3)."""
from django.test import TestCase
from django.utils import timezone

from apps.scm.models import ClassificationABC
from apps.scm.selectors import classifier_abc
from apps.stock.models import MouvementStock, Produit

from .helpers import make_company


def _sortie(company, produit, quantite):
    MouvementStock.objects.create(
        company=company, produit=produit,
        type_mouvement=MouvementStock.TypeMouvement.SORTIE,
        quantite=quantite, quantite_avant=quantite, quantite_apres=0,
        date=timezone.now())


class ClassifierAbcTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-abc', 'Supply ABC')
        # 3 produits À FORTE valeur : cumul = 90 000 / 120 000 = 75% de la
        # valeur totale (marge confortable sous le seuil A <= 80%).
        self.gros_1 = Produit.objects.create(
            company=self.company, nom='Onduleur premium', prix_vente=40000)
        self.gros_2 = Produit.objects.create(
            company=self.company, nom='Kit hybride', prix_vente=30000)
        self.gros_3 = Produit.objects.create(
            company=self.company, nom='Batterie lithium', prix_vente=20000)
        # 7 produits à faible valeur (queue longue) : 30 000 au total.
        petits_quantites = [5, 5, 4, 4, 4, 4, 4]
        self.petits = [
            Produit.objects.create(
                company=self.company, nom=f'Accessoire {i}', prix_vente=1000)
            for i in range(7)
        ]
        _sortie(self.company, self.gros_1, 1)
        _sortie(self.company, self.gros_2, 1)
        _sortie(self.company, self.gros_3, 1)
        for p, qte in zip(self.petits, petits_quantites):
            _sortie(self.company, p, qte)

    def test_dominant_products_classed_a_and_coverage_is_complete(self):
        resultat = classifier_abc(self.company, fenetre_mois=12)

        classe_par_produit = {r['produit'].id: r['classe'] for r in resultat}
        self.assertEqual(classe_par_produit[self.gros_1.id], 'A')
        self.assertEqual(classe_par_produit[self.gros_2.id], 'A')
        self.assertEqual(classe_par_produit[self.gros_3.id], 'A')

        # Couverture à 100% : chaque produit reçoit exactement une classe.
        total_produits = 3 + len(self.petits)
        self.assertEqual(len(resultat), total_produits)
        nb_par_classe = {'A': 0, 'B': 0, 'C': 0}
        for r in resultat:
            nb_par_classe[r['classe']] += 1
        self.assertEqual(sum(nb_par_classe.values()), total_produits)

    def test_result_is_persisted_and_scoped_by_company(self):
        classifier_abc(self.company, fenetre_mois=12)
        self.assertEqual(
            ClassificationABC.objects.filter(company=self.company).count(),
            10)
        ligne = ClassificationABC.objects.get(
            company=self.company, produit=self.gros_1)
        self.assertEqual(ligne.classe, 'A')
        self.assertEqual(ligne.rang, 1)

    def test_recalcul_is_idempotent(self):
        classifier_abc(self.company, fenetre_mois=12)
        first_count = ClassificationABC.objects.filter(company=self.company).count()
        classifier_abc(self.company, fenetre_mois=12)
        second_count = ClassificationABC.objects.filter(company=self.company).count()
        self.assertEqual(first_count, second_count)

    def test_zero_sales_products_are_classed_c(self):
        no_sales_company = make_company('scm-abc-nosales', 'Supply ABC Sans Vente')
        Produit.objects.create(
            company=no_sales_company, nom='Produit jamais vendu', prix_vente=999)
        resultat = classifier_abc(no_sales_company, fenetre_mois=12)
        self.assertEqual(len(resultat), 1)
        self.assertEqual(resultat[0]['classe'], 'C')

    def test_recalculer_endpoint_scoped_and_admin_only(self):
        from .helpers import auth, make_user

        admin = make_user(self.company, 'scm-abc-admin', 'admin')
        resp = auth(admin).post(
            '/api/django/scm/classification-abc/recalculer/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['nb_produits_classes'], 10)
