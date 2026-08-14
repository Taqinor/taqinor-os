"""NTWMS15 — cross-dock : de la réception directement à l'expédition.

Critère d'acceptation testé : une réception dont TOUTES les lignes matchent
une vague en attente peut être expédiée le jour même SANS jamais passer par un
casier de stockage (le put-away NTWMS2 est explicitement sauté).

Le drapeau « destinée au cross-dock » n'est pas une colonne de
``achats.ReceptionFournisseur`` (app hors périmètre de cette lane) mais
l'existence des ``AffectationCrossDock`` de ``stock`` — même information, du
bon côté de la frontière d'apps (voir la docstring du modèle).

Run :
    python manage.py test apps.stock.test_ntwms15_cross_dock -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    AffectationCrossDock, BonCommandeFournisseur, EmplacementStock,
    Fournisseur, LigneBonCommandeFournisseur, LigneReceptionFournisseur,
    MouvementStock, Produit, ReceptionFournisseur, UniteLogistique,
)
from apps.stock.services import (
    affecter_reception_cross_dock, creer_vague_depuis_besoins, lancer_vague,
    proposer_cross_dock, reception_est_cross_dock, sceller_unite_logistique,
)

User = get_user_model()

# Date FIXE : jamais `today()` (une suite qui bascule à minuit devient flaky).
DATE_REF = datetime.date(2026, 4, 9)


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms15Base(TestCase):
    def setUp(self):
        self.company = make_company('ntwms15-co', 'NTWMS15 Co')
        self.autre = make_company('ntwms15-autre', 'NTWMS15 Autre')
        self.admin = User.objects.create_user(
            username='ntwms15_admin', password='x', role_legacy='admin',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS15', is_principal=True)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur NTWMS15')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur 5kW', sku='OND5-NTWMS15',
            prix_achat=Decimal('7000'), prix_vente=Decimal('9000'),
            quantite_stock=0)
        self.autre_produit = Produit.objects.create(
            company=self.company, nom='Câble solaire', sku='CAB-NTWMS15',
            prix_achat=Decimal('12'), prix_vente=Decimal('20'),
            quantite_stock=0)
        self.bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-NTWMS15-0001',
            fournisseur=self.fournisseur, date_commande=DATE_REF,
            emplacement_destination=self.emplacement)
        self.api = auth(self.admin)

    def _reception(self, lignes):
        """Réception BROUILLON + ses lignes (produit, quantité)."""
        reception = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-NTWMS15-{len(lignes)}',
            bon_commande=self.bcf, date_reception=DATE_REF)
        for produit, quantite in lignes:
            ligne_bcf = LigneBonCommandeFournisseur.objects.create(
                bon_commande=self.bcf, produit=produit, quantite=quantite,
                prix_achat_unitaire=produit.prix_achat)
            LigneReceptionFournisseur.objects.create(
                reception=reception, ligne_commande=ligne_bcf,
                produit=produit, quantite=quantite)
        return reception

    def _vague_en_attente(self, besoins, lancer=False):
        vague = creer_vague_depuis_besoins(
            company=self.company, user=self.admin, besoins=besoins)
        if lancer:
            lancer_vague(vague)
        return vague


class TestPropositionCrossDock(Ntwms15Base):
    def test_ligne_attendue_par_une_vague_est_proposee(self):
        self._vague_en_attente(
            [{'produit_id': self.produit.id, 'quantite': 4}])
        reception = self._reception([(self.produit, 4)])

        propositions = proposer_cross_dock(reception)

        self.assertEqual(len(propositions), 1)
        self.assertEqual(propositions[0]['produit_id'], self.produit.id)
        self.assertEqual(len(propositions[0]['vagues']), 1)
        self.assertEqual(propositions[0]['vagues'][0]['reste_a_prelever'], 4)
        self.assertFalse(propositions[0]['deja_affectee'])

    def test_aucune_vague_en_attente_aucune_proposition(self):
        reception = self._reception([(self.produit, 4)])
        propositions = proposer_cross_dock(reception)
        self.assertEqual(propositions[0]['vagues'], [])
        self.assertFalse(reception_est_cross_dock(reception))

    def test_vague_terminee_ne_justifie_aucun_cross_dock(self):
        vague = self._vague_en_attente(
            [{'produit_id': self.produit.id, 'quantite': 4}], lancer=True)
        ligne = vague.lignes.first()
        ligne.quantite_prelevee = ligne.quantite_demandee
        ligne.save(update_fields=['quantite_prelevee'])

        reception = self._reception([(self.produit, 4)])
        self.assertEqual(proposer_cross_dock(reception)[0]['vagues'], [])


class TestAffectationCrossDock(Ntwms15Base):
    def test_reception_entierement_matchee_part_sans_passer_en_casier(self):
        """Le critère d'acceptation, de bout en bout."""
        self._vague_en_attente([
            {'produit_id': self.produit.id, 'quantite': 4},
            {'produit_id': self.autre_produit.id, 'quantite': 30},
        ], lancer=True)
        reception = self._reception(
            [(self.produit, 4), (self.autre_produit, 30)])

        resultat = affecter_reception_cross_dock(
            reception=reception, user=self.admin)

        self.assertEqual(len(resultat['lignes_affectees']), 2)
        self.assertTrue(resultat['reception_entierement_cross_dockee'])
        self.assertTrue(reception_est_cross_dock(reception))

        # Le contenu est bien dans un colis prêt à partir…
        colis = UniteLogistique.objects.get(id=resultat['unite_logistique'])
        self.assertEqual(colis.statut, UniteLogistique.Statut.EN_PREPARATION)
        self.assertEqual(colis.lignes.count(), 2)
        # …et le colis peut être scellé le jour même.
        sceller_unite_logistique(unite=colis, user=self.admin)
        colis.refresh_from_db()
        self.assertEqual(colis.statut, UniteLogistique.Statut.SCELLE)

        # AUCUN mouvement de rangement vers un casier de stockage.
        self.assertFalse(
            MouvementStock.objects
            .filter(company=self.company, bin_destination__isnull=False)
            .exists())

    def test_affectation_est_idempotente_par_ligne(self):
        self._vague_en_attente(
            [{'produit_id': self.produit.id, 'quantite': 4}])
        reception = self._reception([(self.produit, 4)])
        affecter_reception_cross_dock(reception=reception, user=self.admin)

        with self.assertRaises(ValueError):
            affecter_reception_cross_dock(reception=reception, user=self.admin)
        self.assertEqual(
            AffectationCrossDock.objects.filter(company=self.company).count(),
            1)

    def test_sans_vague_en_attente_le_service_refuse(self):
        reception = self._reception([(self.produit, 4)])
        with self.assertRaises(ValueError):
            affecter_reception_cross_dock(reception=reception, user=self.admin)

    def test_colis_scelle_refuse_un_ajout_cross_dock(self):
        self._vague_en_attente(
            [{'produit_id': self.produit.id, 'quantite': 4}])
        reception = self._reception([(self.produit, 4)])
        colis = UniteLogistique.objects.create(
            company=self.company, sscc='0' * 18)
        colis.statut = UniteLogistique.Statut.SCELLE
        colis.save(update_fields=['statut'])

        with self.assertRaises(ValueError):
            affecter_reception_cross_dock(
                reception=reception, user=self.admin, unite=colis)


class TestEndpointsCrossDock(Ntwms15Base):
    def test_proposer_puis_affecter_via_api(self):
        self._vague_en_attente(
            [{'produit_id': self.produit.id, 'quantite': 4}])
        reception = self._reception([(self.produit, 4)])

        url = f'/api/django/stock/receptions-fournisseur/{reception.id}/'
        proposition = self.api.get(url + 'proposer-cross-dock/')
        self.assertEqual(proposition.status_code, 200)
        self.assertFalse(proposition.data['entierement_cross_dockee'])
        self.assertEqual(len(proposition.data['lignes']), 1)

        affectation = self.api.post(url + 'affecter-cross-dock/', {},
                                    format='json')
        self.assertEqual(affectation.status_code, 200)
        self.assertTrue(
            affectation.data['reception_entierement_cross_dockee'])
        self.assertEqual(len(affectation.data['sscc']), 18)

    def test_refus_lisible_quand_rien_ne_matche(self):
        reception = self._reception([(self.produit, 4)])
        url = (f'/api/django/stock/receptions-fournisseur/{reception.id}/'
               'affecter-cross-dock/')
        reponse = self.api.post(url, {}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('detail', reponse.data)

    def test_autre_societe_ne_voit_pas_la_reception(self):
        intrus = User.objects.create_user(
            username='ntwms15_intrus', password='x', role_legacy='admin',
            company=self.autre)
        reception = self._reception([(self.produit, 4)])
        reponse = auth(intrus).get(
            f'/api/django/stock/receptions-fournisseur/{reception.id}/'
            'proposer-cross-dock/')
        self.assertEqual(reponse.status_code, 404)
