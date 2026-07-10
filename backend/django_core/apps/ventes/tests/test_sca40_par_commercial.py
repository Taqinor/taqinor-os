"""SCA40 — `par_commercial` en UNE seule requête groupée (fin du N+1).

Le bloc « par commercial » du dashboard exécutait auparavant un
``LigneDevis.aggregate()`` par commercial DISTINCT dans une boucle Python : le
nombre de requêtes croissait linéairement avec la taille de l'équipe (N+1 non
borné). Il est remplacé par une seule requête ``values().annotate()`` groupée.

Deux garanties testées :
  1. FLATNESS du budget requêtes — le nombre de requêtes SQL du endpoint NE
     grandit PAS quand on passe de 2 à 6 commerciaux (motif
     ``core/test_utils.AssertQueryBudgetMixin``) ;
  2. JSON strictement identique — les valeurs `par_commercial` (décompte +
     valeur pipeline) sont exactement celles que produisait l'ancienne boucle,
     y compris pour un commercial dont un devis n'a AUCUNE ligne.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from core.test_utils import AssertQueryBudgetMixin
from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()
URL = '/api/django/ventes/dashboard/'


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Sca40ParCommercialTests(AssertQueryBudgetMixin, TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='sca40-co', nom='SCA40 Co')
        # L'utilisateur qui appelle le dashboard (rôle responsable).
        self.caller = User.objects.create_user(
            username='sca40_caller', password='x',
            role_legacy='responsable', company=self.co)
        self.api = _auth(self.caller)
        self.cli = Client.objects.create(
            company=self.co, nom='C', prenom='SCA40',
            email='sca40@example.invalid')
        self.produit, _ = Produit.objects.get_or_create(
            company=self.co, sku='SCA40-P',
            defaults={'nom': 'Produit SCA40',
                      'prix_vente': Decimal('10000'), 'tva': Decimal('20')})
        self._ref = 0
        self._comm_seq = 0

    def _next_ref(self):
        self._ref += 1
        return f'DEV-SCA40-{self._ref:04d}'

    def _commercial(self, i):
        return User.objects.create_user(
            username=f'sca40_comm_{i}', password='x',
            first_name=f'Prenom{i}', last_name=f'Nom{i}',
            role_legacy='commercial', company=self.co)

    def _devis_envoye(self, commercial):
        return Devis.objects.create(
            company=self.co, created_by=commercial, client=self.cli,
            reference=self._next_ref(), statut='envoye',
            taux_tva=Decimal('20'))

    def _ligne(self, devis, prix, qte=1, remise=Decimal('0')):
        LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation='L',
            quantite=qte, prix_unitaire=prix, taux_tva=Decimal('20'),
            remise=remise)

    def _make_commercials(self, n):
        """Crée n commerciaux, chacun avec un devis envoyé + une ligne.

        L'index d'username est monotone entre appels : deux appels successifs
        (2 puis 4) créent 6 commerciaux distincts sans collision d'username.
        """
        for _ in range(n):
            comm = self._commercial(self._comm_seq)
            self._comm_seq += 1
            d = self._devis_envoye(comm)
            self._ligne(d, prix=Decimal('8000'))

    def test_query_count_flat_as_commercials_grow(self):
        """Le budget requêtes du dashboard ne grandit pas avec le nombre de
        commerciaux (preuve que le N+1 par-commercial est éliminé)."""
        self._make_commercials(2)
        with self.assertMaxQueries(60) as ctx_small:
            self.api.get(URL)
        count_small = len(ctx_small.captured_queries)

        self._make_commercials(4)  # total 6 commerciaux
        with self.assertMaxQueries(count_small) as ctx_big:
            self.api.get(URL)
        count_big = len(ctx_big.captured_queries)

        self.assertEqual(
            count_big, count_small,
            f"Le nombre de requêtes est passé de {count_small} (2 commerciaux) "
            f"à {count_big} (6 commerciaux) — régression N+1 dans le bloc "
            f"par_commercial du dashboard.")

    def test_par_commercial_values_exact(self):
        """Valeurs exactes : décompte + valeur pipeline, y compris un devis
        sans ligne (compte pour 1, pipeline nul)."""
        comm = self._commercial(99)
        # Deux devis envoyés : un avec ligne 8000 HT, un SANS ligne.
        d1 = self._devis_envoye(comm)
        self._ligne(d1, prix=Decimal('8000'))
        self._devis_envoye(comm)  # aucune ligne

        r = self.api.get(URL)
        rows = [row for row in r.data['par_commercial']
                if row['commercial'] == 'Prenom99 Nom99']
        self.assertEqual(len(rows), 1)
        row = rows[0]
        # 2 devis envoyés → devis_actifs = 2 (le devis sans ligne compte).
        self.assertEqual(row['devis_actifs'], 2)
        # pipeline = 8000 (une seule ligne) × 1.20 = 9600.0 → '9600.0'.
        self.assertEqual(row['valeur_pipeline'],
                         str(round(8000.0 * 1.20, 2)))

    def test_par_commercial_multiple_lignes_summed(self):
        """Plusieurs lignes sur un même devis sont sommées (pas de double
        comptage du devis dans devis_actifs grâce à distinct)."""
        comm = self._commercial(50)
        d = self._devis_envoye(comm)
        self._ligne(d, prix=Decimal('5000'))
        self._ligne(d, prix=Decimal('3000'))

        r = self.api.get(URL)
        rows = [row for row in r.data['par_commercial']
                if row['commercial'] == 'Prenom50 Nom50']
        self.assertEqual(len(rows), 1)
        row = rows[0]
        # UN seul devis malgré 2 lignes.
        self.assertEqual(row['devis_actifs'], 1)
        # (5000 + 3000) × 1.20 = 9600.0.
        self.assertEqual(row['valeur_pipeline'],
                         str(round((5000.0 + 3000.0) * 1.20, 2)))
