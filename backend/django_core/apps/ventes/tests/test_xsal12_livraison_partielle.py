"""XSAL12 — Livraisons partielles et reliquats sur le bon de commande client.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xsal12_livraison_partielle -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import BonCommande, Devis, LigneDevis, LivraisonBC

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='xsal12-co', nom='XSAL12 Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestLivraisonPartielle(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='xsal12user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        token = str(AccessToken.for_user(self.user))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.cl = Client.objects.create(
            company=self.company, nom='XSAL12', prenom='Client',
            email='xsal12@example.com', telephone='+212600000002')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='PAN-XSAL12',
            prix_vente=Decimal('900'), quantite_stock=100)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur hybride', sku='OND-XSAL12',
            prix_vente=Decimal('7000'), quantite_stock=20)
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-9001',
            client=self.cl, statut=Devis.Statut.ACCEPTE)
        self.ligne_panneau = LigneDevis.objects.create(
            devis=self.devis, produit=self.panneau, designation='Panneau 550W',
            quantite=Decimal('12'), prix_unitaire=Decimal('900'), remise=Decimal('0'))
        self.ligne_onduleur = LigneDevis.objects.create(
            devis=self.devis, produit=self.onduleur, designation='Onduleur hybride',
            quantite=Decimal('1'), prix_unitaire=Decimal('7000'), remise=Decimal('0'))
        self.bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-{MONTH}-9001',
            devis=self.devis, client=self.cl,
            statut=BonCommande.Statut.CONFIRME)

    def _livrer(self, lignes, **extra):
        return self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/livrer-partiel/',
            {'lignes': lignes, **extra}, format='json')

    def test_entrees_invalides_repondent_400_sans_ecriture(self):
        # ENF11 — ligne non objet, ligne_devis non entier, quantité illisible
        # ou infinie, date illisible : 400 (AttributeError/ValueError/
        # InvalidOperation/ValidationError → 500 auparavant), aucun stock bougé.
        ligne = {'ligne_devis': self.ligne_panneau.id, 'quantite': '1'}
        for corps in (
                {'lignes': ['x']},
                {'lignes': [{'ligne_devis': 'abc', 'quantite': '1'}]},
                {'lignes': [{'ligne_devis': self.ligne_panneau.id,
                             'quantite': 'abc'}]},
                {'lignes': [{'ligne_devis': self.ligne_panneau.id,
                             'quantite': 'Infinity'}]},
                {'lignes': 'abc'},
                # CI #997 fuzz (24/10) : la règle PUBLIÉE de la quantité
                # (strictement positive, 2 décimales au plus, chaîne ou
                # nombre fini ≤ 9 999 999 999,99) est aussi celle du serveur.
                {'lignes': [{'ligne_devis': self.ligne_panneau.id,
                             'quantite': '-36.2'}]},
                {'lignes': [{'ligne_devis': self.ligne_panneau.id,
                             'quantite': '0'}]},
                {'lignes': [{'ligne_devis': self.ligne_panneau.id,
                             'quantite': '1.234'}]},
                {'lignes': [{'ligne_devis': self.ligne_panneau.id,
                             'quantite': True}]},
                {'lignes': [{'ligne_devis': self.ligne_panneau.id,
                             'quantite': 1e12}]},
                {'lignes': [ligne], 'date_livraison': 'pas-une-date'}):
            resp = self.api.post(
                f'/api/django/ventes/bons-commande/{self.bc.id}/'
                'livrer-partiel/', corps, format='json')
            self.assertEqual(resp.status_code, 400, (corps, resp.data))
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 100)
        self.assertFalse(LivraisonBC.objects.exists())

    def test_confirmer_hors_attente_conflit_409(self):
        # ENF11 — conflit d'état : 409 (et non 400).
        resp = self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/confirmer/')
        self.assertEqual(resp.status_code, 409, resp.data)

    def test_livraison_partielle_decrements_only_delivered_qty(self):
        resp = self._livrer([{'ligne_devis': self.ligne_panneau.id, 'quantite': '8'}])
        self.assertEqual(resp.status_code, 200)
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 92)
        self.onduleur.refresh_from_db()
        self.assertEqual(self.onduleur.quantite_stock, 20)  # non touché

        self.bc.refresh_from_db()
        self.assertEqual(self.bc.statut, BonCommande.Statut.CONFIRME)
        reliquats = {r['ligne_devis_id']: r for r in self.bc.reliquat_par_ligne}
        self.assertEqual(reliquats[self.ligne_panneau.id]['reliquat'], Decimal('4'))
        self.assertTrue(self.bc.est_partiellement_livre)

    def test_solder_reliquat_flips_livre_once(self):
        self._livrer([{'ligne_devis': self.ligne_panneau.id, 'quantite': '8'}])
        self._livrer([{'ligne_devis': self.ligne_panneau.id, 'quantite': '4'}])
        self.bc.refresh_from_db()
        # Onduleur n'a jamais été livré -> pas encore LIVRE.
        self.assertNotEqual(self.bc.statut, BonCommande.Statut.LIVRE)

        resp = self._livrer([{'ligne_devis': self.ligne_onduleur.id, 'quantite': '1'}])
        self.assertEqual(resp.status_code, 200)
        self.bc.refresh_from_db()
        self.assertEqual(self.bc.statut, BonCommande.Statut.LIVRE)
        self.assertIsNotNone(self.bc.date_livraison_reelle)
        # Un seul passage à LIVRE (statut stable si on rappelle l'état).
        self.assertFalse(self.bc.est_partiellement_livre)

    def test_no_double_decompte_with_over_delivery(self):
        resp = self._livrer([{'ligne_devis': self.ligne_panneau.id, 'quantite': '20'}])
        self.assertEqual(resp.status_code, 409)  # ENF11 : au-delà du reliquat (état)
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 100)  # inchangé

    def test_stock_insuffisant_guard(self):
        self.panneau.quantite_stock = 2
        self.panneau.save()
        resp = self._livrer([{'ligne_devis': self.ligne_panneau.id, 'quantite': '2'}])
        # 2 <= reliquat (12) mais > stock dispo -> guard stock-insuffisant.
        self.assertEqual(resp.status_code, 200)
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 0)

        resp2 = self._livrer([{'ligne_devis': self.ligne_panneau.id, 'quantite': '3'}])
        self.assertEqual(resp2.status_code, 409)  # ENF11 : stock insuffisant (état)
        self.assertIn('insuffisant', resp2.data['detail'])

    def test_aud228_stock_insuffisant_autorise_si_reglage_societe_actif(self):
        """AUD228 — `AchatsParametres.stock_negatif_autorise` était ignoré ici
        (blocage en dur) ; routé par `check_negative_stock_guard`, le réglage
        société est désormais respecté : passage en négatif autorisé."""
        from apps.stock.models import AchatsParametres
        parametres = AchatsParametres.for_company(self.company)
        parametres.stock_negatif_autorise = True
        parametres.save()

        self.panneau.quantite_stock = 2
        self.panneau.save()
        resp = self._livrer([{'ligne_devis': self.ligne_panneau.id, 'quantite': '3'}])
        # Avant AUD228 : 400 quel que soit le réglage société. Après : le
        # réglage actif autorise le passage en négatif.
        self.assertEqual(resp.status_code, 200, resp.data)
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, -1)

    def test_marquer_livre_direct_still_works_without_partial(self):
        """Un BC sans livraison partielle reste marquable livré directement
        (comportement historique octet-identique)."""
        resp = self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/marquer-livre/')
        self.assertEqual(resp.status_code, 200)
        self.bc.refresh_from_db()
        self.assertEqual(self.bc.statut, BonCommande.Statut.LIVRE)
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 88)  # 100 - 12

    def test_creates_livraisonbc_record(self):
        self._livrer(
            [{'ligne_devis': self.ligne_panneau.id, 'quantite': '5'}],
            note='Première tournée')
        self.assertEqual(
            LivraisonBC.objects.filter(bon_commande=self.bc).count(), 1)
        livraison = LivraisonBC.objects.get(bon_commande=self.bc)
        self.assertEqual(livraison.note, 'Première tournée')
        self.assertEqual(livraison.lignes.count(), 1)

    def test_cross_tenant_bc_not_accessible(self):
        other_company = make_company(slug='xsal12-other', nom='Autre Co')
        other_user = User.objects.create_user(
            username='xsal12other', password='x', role_legacy='responsable',
            company=other_company)
        api = APIClient()
        token = str(AccessToken.for_user(other_user))
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        resp = api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/livrer-partiel/',
            {'lignes': [{'ligne_devis': self.ligne_panneau.id, 'quantite': '1'}]},
            format='json')
        self.assertEqual(resp.status_code, 404)
