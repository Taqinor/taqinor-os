"""NTMFG16 — Ordre de préparation-échantillon / prototype (première pièce
bonne).

Critère : un OF prototype n'entre dans aucun calcul agrégé de production
normale, reste soumis au contrôle qualité, bascule en OF normal impossible
après clôture (créer un nouvel OF)."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.mrp.models import CoutStandard, Gamme, OperationGamme, OrdreFabrication, PosteDeCharge
from apps.mrp.selectors import analyse_couts, calculer_besoins_nets, oee_poste
from apps.mrp.services import (
    cloturer_of, confirmer_of, demarrer_operation, terminer_operation,
)
from apps.stock.models import Produit

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Produit', quantite_stock=0):
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=0, tva=20,
        quantite_stock=quantite_stock)


class PrototypeExclusionTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-proto-1', 'MRP Prototype 1')
        self.produit = make_produit(self.company)
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-PROTO', nom='Poste proto',
            cout_horaire=Decimal('100'))
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme proto', produit=self.produit)
        OperationGamme.objects.create(
            gamme=self.gamme, ordre=1, poste_charge=self.poste,
            libelle='Op proto', temps_unitaire_min=Decimal('60'))

    def _fabrique_of_termine(self, est_prototype):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=1,
            gamme=self.gamme, est_prototype=est_prototype)
        confirmer_of(of)
        of.refresh_from_db()
        op = of.operations.first()
        demarrer_operation(op)
        op.demarree_le = timezone.now() - timedelta(minutes=60)
        op.save(update_fields=['demarree_le'])
        terminer_operation(op, quantite_bonne=1)
        cloturer_of(of)
        of.refresh_from_db()
        return of

    def test_exclu_du_besoin_net_mrp(self):
        of_proto = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=10,
            gamme=self.gamme, statut='planifie', est_prototype=True)
        resultats = calculer_besoins_nets(
            self.company, produits=[self.produit.id],
            demande_independante={self.produit.id: 5})
        self.assertEqual(len(resultats), 1)
        # En-cours DOIT rester 0 : l'OF prototype ne compense jamais la demande.
        self.assertEqual(resultats[0]['en_cours_fabrication'], '0')
        self.assertIsNotNone(of_proto.id)

    def test_exclu_du_trs_oee(self):
        self._fabrique_of_termine(est_prototype=True)
        resultat = oee_poste(
            self.company, self.poste.id,
            timezone.localdate() - timedelta(days=1), timezone.localdate())
        self.assertFalse(resultat['donnees'])
        self.assertEqual(resultat['nb_operations'], 0)

    def test_exclu_de_l_analyse_couts(self):
        CoutStandard.objects.create(
            company=self.company, produit=self.produit, version=1,
            cout_matiere=Decimal('10'), cout_main_oeuvre=Decimal('10'),
            date_effective=timezone.localdate())
        self._fabrique_of_termine(est_prototype=True)
        resultats = analyse_couts(self.company)
        self.assertEqual(resultats, [])

    def test_of_normal_reste_compte(self):
        self._fabrique_of_termine(est_prototype=False)
        resultat = oee_poste(
            self.company, self.poste.id,
            timezone.localdate() - timedelta(days=1), timezone.localdate())
        self.assertTrue(resultat['donnees'])
        self.assertEqual(resultat['nb_operations'], 1)


class PrototypeVerrouApresClotureTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-proto-api-1', 'MRP Prototype API 1')
        self.user = make_user(self.company, 'mrp-proto-api-user')
        self.api = auth(self.user)
        self.produit = make_produit(self.company)
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-PROTO-API', nom='Poste proto API')
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme proto API', produit=self.produit)
        OperationGamme.objects.create(
            gamme=self.gamme, ordre=1, poste_charge=self.poste,
            libelle='Op', temps_unitaire_min=Decimal('1'))

    def test_bascule_refusee_apres_cloture(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=1,
            gamme=self.gamme, est_prototype=True)
        confirmer_of(of)
        of.refresh_from_db()
        op = of.operations.first()
        demarrer_operation(op)
        terminer_operation(op, quantite_bonne=1)
        cloturer_of(of)

        resp = self.api.patch(
            f'/api/django/mrp/ordres-fabrication/{of.id}/', {'est_prototype': False},
            format='json')
        self.assertEqual(resp.status_code, 400)

    def test_bascule_autorisee_avant_cloture(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=1,
            gamme=self.gamme, est_prototype=True)
        resp = self.api.patch(
            f'/api/django/mrp/ordres-fabrication/{of.id}/', {'est_prototype': False},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['est_prototype'])
