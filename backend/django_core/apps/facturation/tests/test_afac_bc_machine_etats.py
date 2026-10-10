"""AFAC15 (C-AFAC-001 + C-AFAC-006) — la livraison d'un BC suit sa machine à
états avec un reliquat UNIQUE.

  * « Livrer » ne sort que le reliquat non encore sorti (rien si la vente est
    déjà sortie par la facture directe) ;
  * « Livrer partiellement » seulement sur un BC confirmé, sur le panier
    VENDU (`option_lines`) ;
  * annulation refusée après une livraison partielle ; un BC annulé ne
    repasse jamais « livré ».

Rejoue les sondes FBC-1 (partiel 4 puis Livrer : stock 16 au lieu de 20 ;
facture directe puis BC livré : stock 10) et FBC-6 (BC en attente livré
partiellement ; BC annulé devenu livré ; batterie de l'option écartée
proposée au reliquat ; partiel puis annuler : 200). Endpoints réels, aucun
mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_bc_machine_etats"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class BcMachineEtatsTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC15 Co', slug=f'afac15-co-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'afac15_resp_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='BC', prenom='AFAC15',
            email=f'afac15-{_nxt()}@example.invalid')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    # ── fixtures ────────────────────────────────────────────────────────
    def _produit(self, nom, stock=30, prix='1000'):
        from apps.stock.models import Produit
        return Produit.objects.create(
            company=self.company, nom=nom, sku=f'AFAC15-{_nxt()}',
            prix_vente=Decimal(prix), quantite_stock=stock,
            tva=Decimal('20.00'))

    def _devis_panneaux(self, qte='10'):
        from apps.ventes.models import Devis, LigneDevis
        self.panneau = self._produit('Panneau 550W')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-AFAC15-{_nxt()}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'), mode_installation='residentiel')
        self.ligne = LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation='Panneau 550W',
            quantite=Decimal(qte), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('20.00'))
        return devis

    def _bc(self, devis, statut='confirme'):
        from apps.ventes.models import BonCommande
        return BonCommande.objects.create(
            company=self.company, reference=f'BC-AFAC15-{_nxt()}',
            devis=devis, client=self.client_obj, statut=statut)

    def _url(self, bc, geste):
        return f'/api/django/ventes/bons-commande/{bc.id}/{geste}/'

    def _partiel(self, bc, ligne, qte):
        return self.api.post(self._url(bc, 'livrer-partiel'), {
            'lignes': [{'ligne_devis': ligne.id, 'quantite': qte}]},
            format='json')

    def _sorti(self, produit, references):
        from apps.stock.models import MouvementStock
        total = MouvementStock.objects.filter(
            produit=produit, type_mouvement='sortie',
            reference__in=references).aggregate(t=Sum('quantite'))['t']
        return total or 0

    def _stock(self, produit):
        produit.refresh_from_db()
        return produit.quantite_stock

    # ── scénarios ───────────────────────────────────────────────────────
    def test_partiel_puis_livrer(self):
        devis = self._devis_panneaux()
        bc = self._bc(devis)
        r = self._partiel(bc, self.ligne, '4')
        self.assertEqual(r.status_code, 200, r.data)
        r = self.api.post(self._url(bc, 'marquer-livre'))
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._stock(self.panneau), 20)
        self.assertEqual(
            self._sorti(self.panneau, [bc.reference, devis.reference]), 10)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, 'livre')

    def test_facture_directe_puis_bc_livre(self):
        devis = self._devis_panneaux()
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/facturer-complet/',
            {'paiements': []}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self._stock(self.panneau), 20)
        bc = self._bc(devis)
        r = self.api.post(self._url(bc, 'marquer-livre'))
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._stock(self.panneau), 20)
        self.assertEqual(
            self._sorti(self.panneau, [bc.reference, devis.reference]), 10)

    def test_partiel_exige_confirme(self):
        devis = self._devis_panneaux()
        bc = self._bc(devis, statut='en_attente')
        r = self._partiel(bc, self.ligne, '4')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('confirmé', r.data['detail'])
        self.assertEqual(self._stock(self.panneau), 30)

    def test_bc_annule_jamais_livre(self):
        devis = self._devis_panneaux()
        bc = self._bc(devis, statut='annule')
        r = self._partiel(bc, self.ligne, '10')
        self.assertEqual(r.status_code, 400, r.data)
        r = self.api.post(self._url(bc, 'marquer-livre'))
        self.assertEqual(r.status_code, 400, r.data)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, 'annule')
        self.assertEqual(self._stock(self.panneau), 30)

    def test_panier_option_vendue(self):
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-AFAC15-{_nxt()}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            etude_params={'scenario': 'Les deux (Sans + Avec)'},
            option_acceptee=Devis.OptionAcceptee.SANS_BATTERIE)
        lignes = {}
        produits = {}
        for desig, qty in [('Onduleur réseau', '1'), ('Onduleur hybride', '1'),
                           ('Panneau mono 550W', '10'), ('Batterie 5 kWh', '1')]:
            produits[desig] = self._produit(desig)
            lignes[desig] = LigneDevis.objects.create(
                devis=devis, produit=produits[desig], designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal('1000'),
                taux_tva=Decimal('20.00'))
        bc = self._bc(devis)
        ids = {r['ligne_devis_id'] for r in bc.reliquat_par_ligne}
        self.assertNotIn(lignes['Batterie 5 kWh'].id, ids)
        self.assertNotIn(lignes['Onduleur hybride'].id, ids)
        r = self._partiel(bc, lignes['Batterie 5 kWh'], '1')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(self._stock(produits['Batterie 5 kWh']), 30)
        r = self.api.post(self._url(bc, 'livrer-partiel'), {'lignes': [
            {'ligne_devis': lignes['Onduleur réseau'].id, 'quantite': '1'},
            {'ligne_devis': lignes['Panneau mono 550W'].id, 'quantite': '10'},
        ]}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, 'livre')
        self.assertEqual(self._stock(produits['Batterie 5 kWh']), 30)

    def test_annuler_apres_partiel_refuse(self):
        devis = self._devis_panneaux()
        bc = self._bc(devis)
        self.assertEqual(self._partiel(bc, self.ligne, '4').status_code, 200)
        r = self.api.post(self._url(bc, 'annuler'))
        self.assertEqual(r.status_code, 400, r.data)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, 'confirme')
        self.assertEqual(self._sorti(self.panneau, [bc.reference]), 4)

    def test_toggle_on_reservation(self):
        from apps.installations.models import Installation, StockReservation
        from apps.parametres.models import CompanyProfile
        prof = CompanyProfile.get(company=self.company)
        prof.reserver_stock_bc = True
        prof.save()
        devis = self._devis_panneaux()
        Installation.objects.create(
            company=self.company, reference=f'CHT-AFAC15-{_nxt()}',
            client=self.client_obj, devis=devis,
            statut=Installation.Statut.SIGNE)
        bc = self._bc(devis, statut='en_attente')
        r = self.api.post(self._url(bc, 'confirmer'))
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._partiel(bc, self.ligne, '4').status_code, 200)
        resa = StockReservation.objects.get(produit=self.panneau)
        self.assertEqual(resa.quantite, 6)
        r = self.api.post(self._url(bc, 'marquer-livre'))
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._stock(self.panneau), 20)

    def test_creation_manuelle_refuse_un_second_bc_et_emet_l_evenement(self):
        """AMET5 (C-AMET-008) — la création manuelle (POST) passe par la
        MÊME porte que `convertir_en_bc` : BC créé + `bon_commande_cree`
        émis une fois ; un second BC pour le même devis = 400, message
        identique, aucune écriture ni second événement."""
        from apps.ventes.models import BonCommande
        from core.events import bon_commande_cree
        recus = []

        def _recepteur(sender, instance=None, **kwargs):
            recus.append(instance.pk)
        bon_commande_cree.connect(_recepteur, weak=False)
        self.addCleanup(bon_commande_cree.disconnect, _recepteur)
        devis = self._devis_panneaux()
        corps = {'client': self.client_obj.id, 'devis': devis.id}
        r = self.api.post('/api/django/ventes/bons-commande/', corps,
                          format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(BonCommande.objects.filter(devis=devis).count(), 1)
        self.assertEqual(recus, [r.data['id']])
        r2 = self.api.post('/api/django/ventes/bons-commande/', corps,
                           format='json')
        self.assertEqual(r2.status_code, 400, r2.data)
        self.assertIn('Un bon de commande existe déjà pour ce devis.',
                      str(r2.data))
        self.assertEqual(BonCommande.objects.filter(devis=devis).count(), 1)
        self.assertEqual(len(recus), 1)
