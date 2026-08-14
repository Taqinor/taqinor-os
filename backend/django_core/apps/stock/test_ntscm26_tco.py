"""NTSCM26 — simulateur de coût total d'acquisition (TCO) par fournisseur.

Critère d'acceptation testé : un fournisseur MOINS CHER au prix nu mais avec
un historique de RETARDS et d'INCIDENTS peut apparaître PLUS CHER en TCO qu'un
concurrent — vérifié avec des données synthétiques.

Toutes les dates sont FIXES et injectées.

Run :
    python manage.py test apps.stock.test_ntscm26_tco -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, IncidentQualiteFournisseur,
    LigneBonCommandeFournisseur, PrixFournisseur, Produit,
    ReceptionFournisseur,
)
from apps.stock.selectors import comparer_tco_fournisseurs, cout_total_acquisition

User = get_user_model()

AUJOURDHUI = datetime.date(2026, 6, 30)
COMMANDE_LE = datetime.date(2026, 6, 1)


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntscm26Base(TestCase):
    def setUp(self):
        self.company = make_company('ntscm26-co', 'NTSCM26 Co')
        self.autre = make_company('ntscm26-autre', 'NTSCM26 Autre')
        self.admin = User.objects.create_user(
            username='ntscm26_admin', password='x', role_legacy='admin',
            company=self.company)
        self.normal = User.objects.create_user(
            username='ntscm26_normal', password='x', role_legacy='normal',
            company=self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550 Wc', sku='PAN-NTSCM26',
            prix_achat=Decimal('900'), prix_vente=Decimal('1200'),
            quantite_stock=50)

        # « Discount » : moins cher (900) mais LENT et à incidents.
        self.discount = Fournisseur.objects.create(
            company=self.company, nom='Discount NTSCM26')
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.discount, prix_achat=Decimal('900'),
            delai_livraison_jours=10)
        # « Fiable » : plus cher (960) mais À L'HEURE et sans incident.
        self.fiable = Fournisseur.objects.create(
            company=self.company, nom='Fiable NTSCM26')
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fiable, prix_achat=Decimal('960'),
            delai_livraison_jours=10)
        self._seq = 0

    def _livraison(self, fournisseur, jours_reels):
        self._seq += 1
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-NTSCM26-{self._seq:04d}',
            fournisseur=fournisseur, date_commande=COMMANDE_LE)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=10,
            quantite_recue=10, prix_achat_unitaire=Decimal('900'))
        ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-NTSCM26-{self._seq:04d}',
            bon_commande=bc, statut=ReceptionFournisseur.Statut.CONFIRME,
            date_reception=COMMANDE_LE + datetime.timedelta(days=jours_reels))
        return bc


class Ntscm26TcoTests(Ntscm26Base):
    def test_le_moins_cher_au_prix_nu_peut_etre_le_plus_cher_en_tco(self):
        # Discount : 20 jours au lieu de 10 = 10 jours de retard.
        self._livraison(self.discount, 20)
        IncidentQualiteFournisseur.objects.create(
            company=self.company, fournisseur=self.discount,
            produit=self.produit, date_incident=datetime.date(2026, 6, 5),
            gravite=IncidentQualiteFournisseur.Gravite.MAJEURE,
            cout_impact_mad=Decimal('300'))
        # Fiable : pile à l'heure, aucun incident.
        self._livraison(self.fiable, 10)

        classement = comparer_tco_fournisseurs(
            self.company, self.produit, cout_rupture_jour='50',
            aujourdhui=AUJOURDHUI)

        par_nom = {ligne['fournisseur_nom']: ligne for ligne in classement}
        discount = par_nom['Discount NTSCM26']
        fiable = par_nom['Fiable NTSCM26']

        # Prix NU : Discount gagne.
        self.assertEqual(discount['prix_nu'], '900')
        self.assertEqual(fiable['prix_nu'], '960')
        # TCO : 900 + (10 j × 50) + 300 = 1700 contre 960.
        self.assertEqual(discount['tco'], '1700')
        self.assertEqual(fiable['tco'], '960')
        # Le classement est trié par TCO croissant : Fiable passe DEVANT.
        self.assertEqual(classement[0]['fournisseur_nom'], 'Fiable NTSCM26')

    def test_le_prix_nu_est_toujours_renvoye_a_cote_du_tco(self):
        res = cout_total_acquisition(
            self.company, self.discount, self.produit,
            aujourdhui=AUJOURDHUI)
        self.assertIn('prix_nu', res)
        self.assertIn('tco', res)

    def test_sans_cout_de_rupture_parametre_le_retard_ne_pese_rien(self):
        self._livraison(self.discount, 20)
        res = cout_total_acquisition(
            self.company, self.discount, self.produit,
            aujourdhui=AUJOURDHUI)
        self.assertEqual(res['cout_retard'], '0')
        self.assertEqual(res['tco'], '900')

    def test_un_fournisseur_sans_historique_a_un_tco_egal_au_prix_nu(self):
        res = cout_total_acquisition(
            self.company, self.fiable, self.produit, cout_rupture_jour='50',
            aujourdhui=AUJOURDHUI)
        self.assertEqual(res['nb_incidents'], 0)
        self.assertEqual(res['tco'], '960')

    def test_une_livraison_en_avance_ne_cree_jamais_un_credit(self):
        self._livraison(self.discount, 4)  # 6 jours d'AVANCE
        res = cout_total_acquisition(
            self.company, self.discount, self.produit,
            cout_rupture_jour='50', aujourdhui=AUJOURDHUI)
        self.assertEqual(res['retard_moyen_jours'], '0')
        self.assertEqual(res['tco'], '900')

    def test_les_incidents_dune_autre_societe_ne_comptent_pas(self):
        autre_fournisseur = Fournisseur.objects.create(
            company=self.autre, nom='Voisin NTSCM26')
        IncidentQualiteFournisseur.objects.create(
            company=self.autre, fournisseur=autre_fournisseur,
            date_incident=datetime.date(2026, 6, 5),
            cout_impact_mad=Decimal('9999'))
        res = cout_total_acquisition(
            self.company, self.discount, self.produit,
            aujourdhui=AUJOURDHUI)
        self.assertEqual(res['nb_incidents'], 0)


class Ntscm26ApiTests(Ntscm26Base):
    def _url(self):
        return f'/api/django/stock/produits/{self.produit.id}/comparer-tco/'

    def test_endpoint_renvoie_le_classement_tco(self):
        res = auth(self.admin).get(self._url(), {'cout_rupture_jour': '50'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data['fournisseurs']), 2)

    def test_endpoint_refuse_un_role_normal_car_couts_internes(self):
        self.assertEqual(auth(self.normal).get(self._url()).status_code, 403)

    def test_endpoint_refuse_lanonyme(self):
        self.assertEqual(APIClient().get(self._url()).status_code, 401)
