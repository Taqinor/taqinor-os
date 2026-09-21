"""NTSRV18 — Suggestions d'articles KB dans le ticket.

Critère d'acceptation testé : un ticket sur un produit ayant un article KB
lié (``KbArticleLien``) l'affiche en suggestion.

Couvre aussi : seuls les articles PUBLIÉS remontent (jamais un brouillon),
le complètement par mots-clés quand les liens explicites ne suffisent pas,
le plafond ``limit`` et la déduplication, et l'isolation société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.kb.models import KbArticle, KbArticleLien
from apps.kb.selectors import articles_pour_contexte
from apps.stock.models import Produit

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_article(company, titre, corps='', statut=KbArticle.Statut.PUBLIE):
    return KbArticle.objects.create(
        company=company, titre=titre, corps=corps, statut=statut)


class TestArticlesPourContexte(TestCase):
    def setUp(self):
        self.company = make_company('ntsrv18-co', 'NTSRV18 Co')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur Huawei SUN2000',
            prix_vente=1000, prix_achat=700, quantite_stock=5)

    def test_article_lie_au_produit_de_lequipement_est_suggere(self):
        article = make_article(self.company, 'Panne onduleur Huawei — code E001')
        KbArticleLien.objects.create(
            company=self.company, article=article,
            type_cible=KbArticleLien.TypeCible.PRODUIT,
            cible_id=self.produit.id)
        result = articles_pour_contexte(
            self.company, equipement_produit=self.produit.id)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], article.id)

    def test_article_brouillon_lie_nest_jamais_suggere(self):
        article = make_article(
            self.company, 'Brouillon interne', statut=KbArticle.Statut.BROUILLON)
        KbArticleLien.objects.create(
            company=self.company, article=article,
            type_cible=KbArticleLien.TypeCible.PRODUIT,
            cible_id=self.produit.id)
        result = articles_pour_contexte(
            self.company, equipement_produit=self.produit.id)
        self.assertEqual(result, [])

    def test_article_lie_a_la_categorie_ticket(self):
        article = make_article(self.company, 'Procédure panne onduleur')
        KbArticleLien.objects.create(
            company=self.company, article=article,
            type_cible=KbArticleLien.TypeCible.TYPE_INTERVENTION,
            cible_id=42)
        result = articles_pour_contexte(self.company, categorie_ticket=42)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], article.id)

    def test_fallback_mots_cles_quand_aucun_lien_explicite(self):
        make_article(
            self.company, 'Guide onduleur qui clignote rouge',
            corps='vérifier le disjoncteur AC et le câblage')
        result = articles_pour_contexte(
            self.company, mots_cles_description='onduleur clignote rouge')
        self.assertEqual(len(result), 1)

    def test_liens_explicites_priment_sur_les_mots_cles_sans_doublon(self):
        article = make_article(
            self.company, 'Onduleur Huawei — panne réseau',
            corps='onduleur panne réseau')
        KbArticleLien.objects.create(
            company=self.company, article=article,
            type_cible=KbArticleLien.TypeCible.PRODUIT,
            cible_id=self.produit.id)
        result = articles_pour_contexte(
            self.company, equipement_produit=self.produit.id,
            mots_cles_description='onduleur panne réseau')
        # Le même article, lié ET matché par mots-clés, n'apparaît qu'une fois.
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], article.id)

    def test_plafond_limit_respecte(self):
        for i in range(5):
            article = make_article(self.company, f'Article {i}')
            KbArticleLien.objects.create(
                company=self.company, article=article,
                type_cible=KbArticleLien.TypeCible.PRODUIT,
                cible_id=self.produit.id)
        result = articles_pour_contexte(
            self.company, equipement_produit=self.produit.id, limit=3)
        self.assertEqual(len(result), 3)

    def test_sans_contexte_renvoie_liste_vide(self):
        make_article(self.company, 'Article publié isolé')
        result = articles_pour_contexte(self.company)
        self.assertEqual(result, [])

    def test_isolation_societe(self):
        autre_co = make_company('ntsrv18-autre-co', 'NTSRV18 Autre Co')
        autre_produit = Produit.objects.create(
            company=autre_co, nom='Autre onduleur',
            prix_vente=1000, prix_achat=700, quantite_stock=5)
        article = make_article(autre_co, 'Article autre société')
        KbArticleLien.objects.create(
            company=autre_co, article=article,
            type_cible=KbArticleLien.TypeCible.PRODUIT,
            cible_id=autre_produit.id)
        result = articles_pour_contexte(
            self.company, equipement_produit=autre_produit.id)
        self.assertEqual(result, [])
