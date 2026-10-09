"""ERR-ASTK59-QUARANTAINE-QUANTITE-SAISIE — la quarantaine posée après un
contrôle NON CONFORME bloque la quantité RÉELLEMENT entrée (plafonnée au
reste dû, ASTK59), jamais la quantité saisie : une sur-livraison 12 sur un
reste de 10 bloque 10, et le disponible hors quarantaine reste à 0 (jamais
−2).

Run :
    python manage.py test apps.stock.test_astk59_quarantaine_quantite_appliquee
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock.models import (
    BlocageQualite, BonCommandeFournisseur, Categorie, ControleReception,
    Fournisseur, PlanEchantillonnage, Produit, ReceptionFournisseur,
)
from apps.stock.services import (
    confirm_reception_fournisseur, quantite_disponible_hors_quarantaine,
)
from apps.stock.services_qualite_reception import (
    enregistrer_controle_reception,
)
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)


class QuarantaineQuantiteAppliqueeTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'errastk59-co-{n}', nom=f'ERR ASTK59 Co {n}')
        self.admin = User.objects.create_user(
            username=f'errastk59-{n}', password='x', role_legacy='admin',
            company=self.company)
        categorie = Categorie.objects.create(
            company=self.company, nom=f'Onduleurs ERR-ASTK59 {n}')
        PlanEchantillonnage.objects.create(
            company=self.company, categorie=categorie,
            taux_echantillon_pct=20)
        fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ERR-ASTK59')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ERR-ASTK59',
            sku=f'ERRASTK59-{n}', categorie=categorie,
            prix_achat=Decimal('1000'), prix_vente=Decimal('1500'),
            quantite_stock=0)
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-ERRASTK59-{n}',
            fournisseur=fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne_cmd = bc.lignes.create(
            produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('1000'))
        self.reception = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-ERRASTK59-{n}',
            bon_commande=bc)
        # Sur-livraison : 12 saisis pour un reste dû de 10.
        self.reception.lignes.create(
            ligne_commande=ligne_cmd, produit=self.produit, quantite=12)
        enregistrer_controle_reception(
            reception=self.reception, user=self.admin,
            resultat=ControleReception.Resultat.NON_CONFORME,
            unites_controlees=2, observation='Boîtiers fissurés')

    def test_quarantaine_sur_quantite_appliquee(self):
        confirm_reception_fournisseur(self.reception, self.admin)
        ligne = self.reception.lignes.get()
        self.assertEqual(ligne.quantite_appliquee, 10)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 10)
        blocage = BlocageQualite.objects.get(reception=self.reception)
        self.assertEqual(blocage.statut, BlocageQualite.Statut.EN_QUARANTAINE)
        # Avant le correctif : 12 (la saisie) pour 10 entrés.
        self.assertEqual(blocage.quantite, 10)
        self.assertEqual(
            quantite_disponible_hors_quarantaine(self.company, self.produit),
            0)
