"""ERR-QAC-MULTIVILLA-MATERIEL-XN — un devis « ×N villas identiques » porte les
lignes d'UNE villa ; il est facturé ×N (ERR-QAC-MULTIVILLA-TOTAL-XN) et,
décision fondateur 30/09/2026 (« material ×N too »), son MATÉRIEL compte
aussi N villas : décrément de stock (facturation directe + livraison BC),
suivi des livraisons du BC (``reliquat_par_ligne``) et nomenclature du
chantier. N=1 → comportement strictement inchangé.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import BonCommande, Devis, LigneDevis
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
# Références espacées de 10 (les références faites main ne doivent jamais
# entrer en collision avec un autre module du même shard).
_CTR = [0]


def _nxt():
    _CTR[0] += 10
    return _CTR[0]


class _Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='MATXN Co', slug=f'matxn-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'matxn_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='MATXN', prenom='Client',
            telephone='+212600000318')

    def _devis(self, n=None):
        etude = {'scenario': 'Sans batterie', 'puissance_kwc': 5.5}
        if n is not None:
            etude['nombre_proprietes'] = n
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-MATXN{_nxt()}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'), etude_params=etude)
        self.produits = {}
        for desig, qty, pu in [('Onduleur réseau 5kW', '1', '11700'),
                               ('Panneau mono 550W', '10', '1100')]:
            produit = Produit.objects.create(
                company=self.company, nom=desig, sku=f'MATXN-{_nxt()}',
                prix_vente=Decimal(pu), quantite_stock=100,
                tva=Decimal('20.00'))
            self.produits[desig] = produit
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                taux_tva=Decimal('20'))
        return Devis.objects.get(pk=devis.pk)

    def _bc(self, devis):
        return BonCommande.objects.create(
            company=self.company, reference=f'BC-{MONTH}-MATXN{_nxt()}',
            devis=devis, client=self.client_obj,
            statut=BonCommande.Statut.CONFIRME)

    def _stocks(self):
        return {nom: Produit.objects.get(pk=p.pk).quantite_stock
                for nom, p in self.produits.items()}


class TestStockFacturationDirecte(_Base):
    def _reserver(self, n):
        from apps.ventes.domain.facturation_ops import (
            reserver_stock_devis_facture,
        )
        devis = self._devis(n)
        self.assertTrue(reserver_stock_devis_facture(
            devis=devis, user=self.user, company=self.company))
        return self._stocks()

    def test_n1_inchange(self):
        self.assertEqual(self._reserver(None), {
            'Onduleur réseau 5kW': 99, 'Panneau mono 550W': 90})

    def test_n3_decompte_trois_villas(self):
        self.assertEqual(self._reserver(3), {
            'Onduleur réseau 5kW': 97, 'Panneau mono 550W': 70})


class TestStockLivraisonBC(_Base):
    def _livrer(self, n):
        bc = self._bc(self._devis(n))
        resp = self.api.post(
            f'/api/django/ventes/bons-commande/{bc.id}/marquer-livre/')
        self.assertEqual(resp.status_code, 200, resp.data)
        return self._stocks()

    def test_n1_inchange(self):
        self.assertEqual(self._livrer(None), {
            'Onduleur réseau 5kW': 99, 'Panneau mono 550W': 90})

    def test_n3_livre_trois_villas(self):
        self.assertEqual(self._livrer(3), {
            'Onduleur réseau 5kW': 97, 'Panneau mono 550W': 70})


class TestReliquatLivraisonBC(_Base):
    def test_n1_quantites_commandees_inchangees(self):
        bc = self._bc(self._devis(None))
        par_desig = {r['designation']: r['quantite_commandee']
                     for r in bc.reliquat_par_ligne}
        self.assertEqual(par_desig, {'Onduleur réseau 5kW': Decimal('1'),
                                     'Panneau mono 550W': Decimal('10')})

    def test_n3_kit_dune_villa_ne_solde_pas_le_bc(self):
        devis = self._devis(3)
        bc = self._bc(devis)
        par_desig = {r['designation']: r for r in bc.reliquat_par_ligne}
        self.assertEqual(
            par_desig['Panneau mono 550W']['quantite_commandee'],
            Decimal('30'))
        self.assertEqual(par_desig['Onduleur réseau 5kW']['reliquat'],
                         Decimal('3'))
        onduleur = devis.lignes.get(designation='Onduleur réseau 5kW')
        panneau = devis.lignes.get(designation='Panneau mono 550W')
        url = f'/api/django/ventes/bons-commande/{bc.id}/livrer-partiel/'
        # Le kit d'UNE villa : le BC reste à livrer (reliquat 2 + 20).
        resp = self.api.post(url, {'lignes': [
            {'ligne_devis': onduleur.id, 'quantite': '1'},
            {'ligne_devis': panneau.id, 'quantite': '10'}]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommande.Statut.CONFIRME)
        self.assertTrue(bc.est_partiellement_livre)
        reliquats = {r['designation']: r['reliquat']
                     for r in bc.reliquat_par_ligne}
        self.assertEqual(reliquats, {'Onduleur réseau 5kW': Decimal('2'),
                                     'Panneau mono 550W': Decimal('20')})
        # Les deux autres villas : le BC est soldé.
        resp = self.api.post(url, {'lignes': [
            {'ligne_devis': onduleur.id, 'quantite': '2'},
            {'ligne_devis': panneau.id, 'quantite': '20'}]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommande.Statut.LIVRE)
        self.assertEqual(self._stocks(), {
            'Onduleur réseau 5kW': 97, 'Panneau mono 550W': 70})
