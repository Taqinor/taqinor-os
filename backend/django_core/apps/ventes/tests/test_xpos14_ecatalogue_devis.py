"""XPOS14 — E-catalogue → « Demander un devis » (panier de demande).

Couvre :
  * lecture publique du catalogue par token (produits exposés, prix TTC
    seulement, jamais `prix_achat`) ;
  * token inconnu/inactif → 404 ;
  * une sélection soumise crée un Lead + un Devis brouillon liés avec les
    bonnes lignes (produit/quantité/prix repris du catalogue) ;
  * dédup : une 2e soumission avec le même téléphone réutilise le lead
    existant (pas de doublon, même chemin que create_lead_from_livechat) ;
  * honeypot (`site_web` rempli) → 201 factice, rien créé ;
  * scoping société : le devis/lead créés appartiennent à la société du
    catalogue.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.compta.models import ECatalogue
from apps.crm.models import Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis


def make_company(slug='xpos14-co', nom='XPOS14 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class Xpos14TestBase(TestCase):
    def setUp(self):
        self.company = make_company()
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau PV 550W', sku='XPOS14-PV1',
            prix_vente=Decimal('1200'), prix_achat=Decimal('900'),
            quantite_stock=100, tva=Decimal('10.00'))
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur 5kW', sku='XPOS14-OND1',
            prix_vente=Decimal('8000'), prix_achat=Decimal('6000'),
            quantite_stock=10, tva=Decimal('20.00'))
        self.cat = ECatalogue.objects.create(
            company=self.company, titre='Catalogue solaire',
            token='xpos14-tok-abc123', produit_ids=[
                self.panneau.id, self.onduleur.id])
        self.api = APIClient()

    def _url(self, path):
        return f'/api/django/public/ecatalogue/{self.cat.token}/{path}'


class TestEcataloguePublicRead(Xpos14TestBase):
    def test_lecture_publique_expose_produits_prix_ttc(self):
        r = self.api.get(self._url(''))
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['titre'], 'Catalogue solaire')
        noms = {p['nom'] for p in r.data['produits']}
        self.assertEqual(noms, {'Panneau PV 550W', 'Onduleur 5kW'})
        for p in r.data['produits']:
            self.assertNotIn('prix_achat', p)

    def test_token_inconnu_404(self):
        r = self.api.get('/api/django/public/ecatalogue/does-not-exist/')
        self.assertEqual(r.status_code, 404)

    def test_token_inactif_404(self):
        self.cat.actif = False
        self.cat.save()
        r = self.api.get(self._url(''))
        self.assertEqual(r.status_code, 404)


class TestDemanderDevis(Xpos14TestBase):
    def test_selection_cree_lead_et_devis_brouillon(self):
        r = self.api.post(self._url('demander-devis/'), {
            'nom': 'Karim Alaoui',
            'telephone': '+212611223344',
            'email': 'karim@example.ma',
            'lignes': [
                {'produit': self.panneau.id, 'quantite': '6'},
                {'produit': self.onduleur.id, 'quantite': '1'},
            ],
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)

        lead = Lead.objects.get(company=self.company, telephone='+212611223344')
        self.assertEqual(lead.nom, 'Karim Alaoui')

        devis = Devis.objects.get(lead=lead)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertEqual(devis.company_id, self.company.id)
        lignes = list(devis.lignes.all())
        self.assertEqual(len(lignes), 2)
        produits_lignes = {ligne.produit_id: ligne.quantite for ligne in lignes}
        self.assertEqual(produits_lignes[self.panneau.id], Decimal('6'))
        self.assertEqual(produits_lignes[self.onduleur.id], Decimal('1'))

    def test_dedup_meme_telephone_reutilise_le_lead(self):
        # QX41 — le verrou d'idempotence absorbe un rejeu STRICTEMENT identique
        # (double-clic : mêmes coordonnées ET même panier). Ici on modélise
        # DEUX demandes DISTINCTES de la même personne (paniers différents) :
        # le lead est réutilisé (même téléphone) mais chaque demande produit
        # bien son propre devis.
        r1 = self.api.post(self._url('demander-devis/'), {
            'nom': 'Sara Idrissi',
            'telephone': '+212677889900',
            'lignes': [{'produit': self.panneau.id, 'quantite': '2'}],
        }, format='json')
        self.assertEqual(r1.status_code, 201, r1.data)
        r2 = self.api.post(self._url('demander-devis/'), {
            'nom': 'Sara Idrissi',
            'telephone': '+212677889900',
            'lignes': [{'produit': self.panneau.id, 'quantite': '5'}],
        }, format='json')
        self.assertEqual(r2.status_code, 201, r2.data)

        leads = Lead.objects.filter(
            company=self.company, telephone='+212677889900')
        self.assertEqual(leads.count(), 1)
        # Deux devis (un par soumission distincte) mais un seul lead.
        self.assertEqual(Devis.objects.filter(lead=leads.first()).count(), 2)

    def test_honeypot_rempli_ne_cree_rien(self):
        r = self.api.post(self._url('demander-devis/'), {
            'nom': 'Bot',
            'telephone': '+212600000000',
            'site_web': 'http://spam.example',
            'lignes': [{'produit': self.panneau.id, 'quantite': '1'}],
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertFalse(
            Lead.objects.filter(
                company=self.company, telephone='+212600000000').exists())

    def test_sans_produit_400(self):
        r = self.api.post(self._url('demander-devis/'), {
            'nom': 'X', 'telephone': '+212600000001', 'lignes': [],
        }, format='json')
        self.assertEqual(r.status_code, 400)

    def test_sans_nom_ni_contact_400(self):
        r = self.api.post(self._url('demander-devis/'), {
            'lignes': [{'produit': self.panneau.id, 'quantite': '1'}],
        }, format='json')
        self.assertEqual(r.status_code, 400)

    def test_token_inconnu_404_sur_soumission(self):
        r = self.api.post(
            '/api/django/public/ecatalogue/does-not-exist/demander-devis/',
            {'nom': 'X', 'telephone': '+212600000002',
             'lignes': [{'produit': self.panneau.id, 'quantite': '1'}]},
            format='json')
        self.assertEqual(r.status_code, 404)
