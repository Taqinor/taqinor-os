"""NTWMS36 — interleaving des tâches (rangement + prélèvement combinés).

Critère d'acceptation testé : après avoir rangé un produit en ZONE C, le poste
scanner propose une ligne de prélèvement en zone C — ou, à défaut, une ligne
sur le TRAJET RETOUR (du fond vers la sortie) — avant de renvoyer l'opérateur
au dock de réception à vide.

Run :
    python manage.py test apps.stock.test_ntwms36_interleaving -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import EmplacementStock, Produit
from apps.stock.models_wms import LignePicking, VaguePicking
from apps.stock.selectors import suggerer_tache_retour

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms36Base(TestCase):
    def setUp(self):
        from apps.installations.models import BinLocation

        self.company = make_company('ntwms36-co', 'NTWMS36 Co')
        self.autre = make_company('ntwms36-autre', 'NTWMS36 Autre')
        self.magasinier = User.objects.create_user(
            username='ntwms36_magasinier', password='x', role_legacy='normal',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS36', is_principal=True)

        # Ordre de parcours : A (proche du quai) … C … Z (au fond).
        self.bins = {
            code: BinLocation.objects.create(
                company=self.company, emplacement=self.emplacement,
                code=f'{code}-01-01', zone=code, allee='01', casier='01',
                ordre=ordre)
            for code, ordre in [('A', 10), ('C', 300), ('Z', 900)]
        }
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur 5 kW', sku='OND5-NTWMS36',
            prix_achat=Decimal('7000'), prix_vente=Decimal('9000'),
            quantite_stock=50)
        self.vague = VaguePicking.objects.create(
            company=self.company, reference='VAG-NTWMS36-0001',
            statut=VaguePicking.Statut.LANCEE)

    def _ligne(self, zone, *, demandee=5, prelevee=0, ordre=100):
        return LignePicking.objects.create(
            company=self.company, vague=self.vague, produit=self.produit,
            quantite_demandee=demandee, quantite_prelevee=prelevee,
            bin=self.bins[zone], ordre_parcours=ordre)


class Ntwms36Tests(Ntwms36Base):
    def test_la_meme_zone_est_proposee_en_priorite(self):
        self._ligne('A', ordre=10)
        ligne_c = self._ligne('C', ordre=300)
        self._ligne('Z', ordre=900)

        suggestions = suggerer_tache_retour(
            self.company, zone_courante='C', operateur=self.magasinier)

        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]['ligne_id'], ligne_c.id)
        self.assertEqual(suggestions[0]['zone'], 'C')
        self.assertTrue(suggestions[0]['meme_zone'])

    def test_a_defaut_on_redescend_vers_la_sortie_jamais_vers_le_fond(self):
        # Aucune ligne en zone C : la suggestion part du casier le PLUS LOIN
        # (ordre décroissant), c'est-à-dire sur le trajet de retour.
        self._ligne('A', ordre=10)
        ligne_z = self._ligne('Z', ordre=900)

        suggestions = suggerer_tache_retour(self.company, zone_courante='C')

        self.assertEqual(suggestions[0]['ligne_id'], ligne_z.id)
        self.assertFalse(suggestions[0]['meme_zone'])

    def test_une_ligne_deja_entierement_prelevee_nest_jamais_proposee(self):
        self._ligne('C', demandee=5, prelevee=5, ordre=300)
        self.assertEqual(
            suggerer_tache_retour(self.company, zone_courante='C'), [])

    def test_une_vague_en_brouillon_nest_jamais_proposee(self):
        brouillon = VaguePicking.objects.create(
            company=self.company, reference='VAG-NTWMS36-0002',
            statut=VaguePicking.Statut.BROUILLON)
        LignePicking.objects.create(
            company=self.company, vague=brouillon, produit=self.produit,
            quantite_demandee=3, bin=self.bins['C'], ordre_parcours=300)
        self.assertEqual(
            suggerer_tache_retour(self.company, zone_courante='C'), [])

    def test_la_limite_est_respectee(self):
        self._ligne('C', ordre=300)
        self._ligne('C', ordre=310)
        self._ligne('Z', ordre=900)
        self.assertEqual(
            len(suggerer_tache_retour(self.company, zone_courante='C',
                                      limite=2)), 2)

    def test_aucune_ligne_dune_autre_societe(self):
        autre_produit = Produit.objects.create(
            company=self.autre, nom='Voisin', sku='VOISIN-36',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'),
            quantite_stock=1)
        autre_vague = VaguePicking.objects.create(
            company=self.autre, reference='VAG-NTWMS36-0009',
            statut=VaguePicking.Statut.LANCEE)
        LignePicking.objects.create(
            company=self.autre, vague=autre_vague, produit=autre_produit,
            quantite_demandee=9, ordre_parcours=1)
        self.assertEqual(
            suggerer_tache_retour(self.company, zone_courante='C'), [])

    def test_la_suggestion_nengage_rien(self):
        ligne = self._ligne('C', ordre=300)
        suggerer_tache_retour(self.company, zone_courante='C')
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite_prelevee, 0)


class Ntwms36EndpointTests(Ntwms36Base):
    URL = '/api/django/stock/tache-retour/'

    def test_endpoint_repond_au_magasinier(self):
        ligne = self._ligne('C', ordre=300)
        res = auth(self.magasinier).get(self.URL, {'zone': 'C'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['zone_courante'], 'C')
        self.assertEqual(res.data['suggestions'][0]['ligne_id'], ligne.id)

    def test_endpoint_refuse_lanonyme(self):
        self.assertEqual(APIClient().get(self.URL).status_code, 401)
