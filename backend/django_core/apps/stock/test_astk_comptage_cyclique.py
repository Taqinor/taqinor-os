"""ASTK38 — le comptage cyclique YSTCK1 applique l'ÉCART, jamais le niveau.

Constat C-ASTK-007 (sonde MVT-7) : ``appliquer_ecarts_comptage`` posait
``quantite_apres = ligne.quantite_comptee``. Une réception survenue entre le
snapshot du théorique et la clôture du comptage était effacée, et le mouvement
AJUSTEMENT était incohérent avec lui-même (quantite=2, avant=120, après=98).

Désormais une seule fonction ``appliquer_ecart_inventaire`` sert les deux
chemins (session d'inventaire AUD206 et comptage cyclique) : l'écart
compté − théorique est appliqué en delta au stock LIVE verrouillé.

Le scénario passe par l'API réelle installations (snapshot serveur du
théorique à l'ajout de ligne, saisie du compté, clôture ``terminer``).

Run :
    python manage.py test apps.stock.test_astk_comptage_cyclique -v 2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import SessionComptage
from apps.stock.models import (
    InventaireSession, LigneInventaire, MouvementStock, Produit,
)
from apps.stock.services import (
    appliquer_ecart_inventaire, record_stock_movement,
    valider_inventaire_session,
)
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


class ComptageCycliqueTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'astk38-co-{n}', nom=f'ASTK38 Co {n}')
        self.user = User.objects.create_user(
            username=f'astk38-{n}', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur 5 kW', sku=f'ASTK38-{n}',
            prix_achat=Decimal('100'), prix_vente=Decimal('150'),
            quantite_stock=100)
        self.session = SessionComptage.objects.create(
            company=self.company, reference=f'CYC-ASTK38-{n}',
            statut=SessionComptage.Statut.EN_COURS, created_by=self.user)

    def _entree(self, qte):
        p = Produit.objects.get(pk=self.produit.pk)
        record_stock_movement(
            company=self.company, produit=p,
            type_mouvement=MouvementStock.TypeMouvement.ENTREE,
            quantite=qte, quantite_avant=p.quantite_stock,
            quantite_apres=p.quantite_stock + qte,
            reference='REC-ASTK38', note='Réception intermédiaire',
            created_by=self.user)

    def _scenario(self):
        r = self.api.post(
            f'{BASE}/sessions-comptage/{self.session.id}/ajouter-ligne/',
            {'produit': self.produit.id}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['quantite_theorique'], 100)
        ligne_id = r.data['id']
        r = self.api.patch(
            f'{BASE}/comptage-lignes/{ligne_id}/',
            {'quantite_comptee': 98, 'compte': True}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        # Réception légitime arrivée avant la clôture du comptage.
        self._entree(20)
        r = self.api.post(
            f'{BASE}/sessions-comptage/{self.session.id}/terminer/')
        self.assertEqual(r.status_code, 200, r.content)

    def test_reception_intermediaire_conservee(self):
        self._scenario()
        self.produit.refresh_from_db()
        # 120 (live) + (98 − 100) = 118 ; avant ASTK38 : 98 (20 effacés).
        self.assertEqual(self.produit.quantite_stock, 118)

    def test_mouvement_ajustement_coherent_avec_lui_meme(self):
        self._scenario()
        mvt = MouvementStock.objects.get(
            company=self.company, reference=self.session.reference,
            type_mouvement=MouvementStock.TypeMouvement.AJUSTEMENT)
        self.assertEqual(mvt.quantite, 2)
        self.assertEqual(mvt.quantite_avant, 120)
        self.assertEqual(mvt.quantite_apres, 118)
        for m in MouvementStock.objects.filter(produit=self.produit):
            self.assertEqual(
                abs(m.quantite_apres - m.quantite_avant), m.quantite,
                f'mouvement {m.reference} incohérent')

    def test_session_inventaire_meme_helper(self):
        """La session d'inventaire (AUD206) et le comptage cyclique donnent
        le même stock pour le même scénario."""
        session = InventaireSession.objects.create(
            company=self.company, reference=f'INV-ASTK38-{next(_seq)}')
        LigneInventaire.objects.create(
            session=session, produit=self.produit,
            quantite_theorique=100, quantite_comptee=98)
        self._entree(20)
        valider_inventaire_session(session, self.user)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 118)

    def test_helper_ignore_produit_autre_societe(self):
        autre = Company.objects.create(
            slug=f'astk38-autre-{next(_seq)}', nom='Autre')
        self.assertIsNone(appliquer_ecart_inventaire(
            company=autre, produit_id=self.produit.id, ecart=-5,
            reference='X', note='x', user=None))
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 100)
