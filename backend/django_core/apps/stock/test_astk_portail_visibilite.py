"""ASTK193 (C-ASTK-044, volet FOUR-9) — la porte à jeton sert la même liste
de BCF que la porte compte : un BCF brouillon n'est plus visible du
fournisseur.

Sonde FOUR-9 : BCF brouillon présent par jeton (True), absent par compte
(False). Factures : la porte jeton (`factures_sous_traitant_qs_generique`) et
la porte compte (`selectors.factures_portail_fournisseur`) partagent la MÊME
liste de base (le sélecteur compte ne fait qu'enrichir le statut de
règlement) — conformes, vérifié ci-dessous.

Source réelle : vue publique, `services.portail_fournisseur_documents`,
`selectors.bcf_portail_fournisseur` — aucun mock.

Run :
    python manage.py test apps.stock.test_astk_portail_visibilite -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.stock.models import (
    BonCommandeFournisseur, FactureFournisseur, Fournisseur, Produit,
)
from apps.stock.selectors import (
    bcf_portail_fournisseur, factures_portail_fournisseur,
)
from apps.stock.services import generer_token_portail_fournisseur
from authentication.models import Company

User = get_user_model()

PUBLIC = '/api/django/public/stock/portail-fournisseur/'


class VisibiliteTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='ASTK193', slug='astk193-co')
        user = User.objects.create_user(
            username='astk193-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK193')
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur ASTK193', sku='OND-ASTK193',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'))
        self.bcf = {}
        for statut in (BonCommandeFournisseur.Statut.BROUILLON,
                       BonCommandeFournisseur.Statut.ENVOYE,
                       BonCommandeFournisseur.Statut.ANNULE):
            bc = BonCommandeFournisseur.objects.create(
                company=self.company, reference=f'BCF-ASTK193-{statut}',
                fournisseur=self.fournisseur, statut=statut,
                created_by=user)
            bc.lignes.create(produit=produit, quantite=1,
                             prix_achat_unitaire=Decimal('1200'))
            self.bcf[statut] = bc
        FactureFournisseur.objects.create(
            company=self.company, reference='FF-ASTK193-1',
            fournisseur=self.fournisseur,
            date_facture=datetime.date(2026, 9, 1),
            montant_ht=Decimal('1000'), montant_tva=Decimal('0'),
            montant_ttc=Decimal('1000'))
        self.token = generer_token_portail_fournisseur(
            self.company, self.fournisseur, user).token

    def _porte_jeton(self):
        rep = APIClient().get(f'{PUBLIC}{self.token}/')
        self.assertEqual(rep.status_code, 200, rep.data)
        return rep.data

    def test_brouillon_absent_porte_jeton(self):
        ids = {b['id'] for b in self._porte_jeton()['bons_commande']}
        self.assertNotIn(
            self.bcf[BonCommandeFournisseur.Statut.BROUILLON].id, ids)
        self.assertNotIn(
            self.bcf[BonCommandeFournisseur.Statut.ANNULE].id, ids)
        self.assertEqual(
            ids, {self.bcf[BonCommandeFournisseur.Statut.ENVOYE].id})

    def test_deux_portes_meme_liste(self):
        jeton = [b['id'] for b in self._porte_jeton()['bons_commande']]
        compte = [b['id'] for b in bcf_portail_fournisseur(
            self.company, self.fournisseur.id)]
        self.assertEqual(jeton, compte)

    def test_factures_meme_liste_de_base(self):
        jeton = [f['id'] for f in self._porte_jeton()['factures']]
        compte = [f['id'] for f in factures_portail_fournisseur(
            self.company, self.fournisseur.id)]
        self.assertEqual(jeton, compte)
