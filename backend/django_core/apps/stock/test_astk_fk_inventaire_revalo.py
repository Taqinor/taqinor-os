"""ASTK1 — FK `produit` des sessions d'inventaire et des revalorisations
bornées à la société ; `produit`/`nouveau_cout` figés après création ;
`average_cost_with_source` ne lit que les documents de la société du produit.

Rejoue les sondes MVT-1 / MVT-2 de l'audit stock du 2026-10-06 : avant
correction, POST d'une session sur le produit d'une autre société = 201,
valider = 200 et le stock de B passait de 100 à 0 ; PATCH d'une
revalorisation vers le produit de B = 200 et le coût de B devenait
(1.00, 'revalorisation').

Run:
    python manage.py test apps.stock.test_astk_fk_inventaire_revalo -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import F
from django.test import TestCase
from rest_framework.relations import PrimaryKeyRelatedField
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.stock.models import (
    InventaireSession, LigneInventaire, MouvementStock, Produit,
    RevalorisationStock,
)
from apps.stock.services import (
    average_cost_with_source, creer_revalorisation, valider_inventaire_session,
)

User = get_user_model()

ID_ABSENT = 99999999


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _nb(reponse):
    data = reponse.json()
    return data['count'] if isinstance(data, dict) else len(data)


def _inexistant(pk):
    """Message DRF « objet inexistant » pour ``pk`` (langue active)."""
    gabarit = PrimaryKeyRelatedField.default_error_messages['does_not_exist']
    return str(gabarit).format(pk_value=pk)


def _sans_id(corps, pk):
    """Le message DRF « objet inexistant » cite l'id : on le remplace par un
    jeton pour comparer la réponse d'un id étranger à celle d'un id absent."""
    if isinstance(corps, dict):
        return {k: _sans_id(v, pk) for k, v in corps.items()}
    if isinstance(corps, (list, tuple)):
        return [_sans_id(v, pk) for v in corps]
    return '<INEXISTANT>' if str(corps) == _inexistant(pk) else str(corps)


class FkInventaireRevaloTests(TestCase):
    def setUp(self):
        self.co_a = Company.objects.create(nom='astk1-a', slug='astk1-a')
        self.co_b = Company.objects.create(nom='astk1-b', slug='astk1-b')
        self.admin_a = User.objects.create_user(
            username='astk1-admin-a', password='x', company=self.co_a,
            role_legacy='admin')
        self.api = _api(self.admin_a)
        self.pb = Produit.objects.create(
            company=self.co_b, nom='PRODUIT-B-SECRET', sku='ASTK1-PB',
            prix_vente=Decimal('80'), prix_achat=Decimal('50'),
            quantite_stock=100)
        self.pa = Produit.objects.create(
            company=self.co_a, nom='Produit A', sku='ASTK1-PA',
            prix_vente=Decimal('80'), prix_achat=Decimal('40'),
            quantite_stock=10)

    def _session(self, produit_id):
        return self.api.post(
            '/api/django/stock/inventaire-sessions/',
            {'motif': 'comptage', 'lignes': [{
                'produit': produit_id, 'quantite_theorique': 100,
                'quantite_comptee': 0}]},
            format='json')

    def _invariants_b(self):
        self.pb.refresh_from_db()
        self.assertEqual(self.pb.quantite_stock, 100)
        self.assertEqual(
            average_cost_with_source(self.pb), (Decimal('50'), 'catalogue'))
        self.assertFalse(MouvementStock.objects.exclude(
            company_id=F('produit__company_id')).exists())

    def test_ligne_inventaire_produit_etranger_refuse(self):
        r_absent = self._session(ID_ABSENT)
        r = self._session(self.pb.pk)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('<INEXISTANT>', str(_sans_id(r.json(), self.pb.pk)))
        self.assertEqual(r_absent.status_code, 400, r_absent.content)
        self.assertEqual(_sans_id(r.json(), self.pb.pk),
                         _sans_id(r_absent.json(), ID_ABSENT))
        self.assertNotIn('PRODUIT-B-SECRET', r.content.decode())
        # Persistance : aucune session créée, rien de B n'a bougé.
        self.assertEqual(
            _nb(self.api.get('/api/django/stock/inventaire-sessions/')), 0)
        self.assertFalse(InventaireSession.objects.exists())
        self._invariants_b()

    def test_validation_relit_le_produit_dans_la_societe(self):
        # Ligne héritée (écrite hors API) pointant le produit de B : la
        # validation la refuse au lieu de déplacer le stock de B.
        session = InventaireSession.objects.create(
            company=self.co_a, reference='INV-ASTK1', motif='x')
        LigneInventaire.objects.create(
            session=session, produit=self.pb, quantite_theorique=100,
            quantite_comptee=0)
        with self.assertRaises(ValueError):
            valider_inventaire_session(session, self.admin_a)
        session.refresh_from_db()
        self.assertNotEqual(session.statut, InventaireSession.Statut.VALIDE)
        self._invariants_b()

    def test_revalo_patch_produit_etranger_refuse(self):
        revalo = creer_revalorisation(
            company=self.co_a, produit=self.pa, nouveau_cout='45',
            motif='baisse', user=self.admin_a)
        url = f'/api/django/stock/revalorisations-stock/{revalo.pk}/'
        r_absent = self.api.patch(
            url, {'produit': ID_ABSENT, 'nouveau_cout': '1'}, format='json')
        r = self.api.patch(
            url, {'produit': self.pb.pk, 'nouveau_cout': '1'}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('<INEXISTANT>', str(_sans_id(r.json(), self.pb.pk)))
        self.assertEqual(_sans_id(r.json(), self.pb.pk),
                         _sans_id(r_absent.json(), ID_ABSENT))
        self.assertNotIn('PRODUIT-B-SECRET', r.content.decode())
        r_val = self.api.post(f'{url}valider/', {}, format='json')
        self.assertEqual(r_val.status_code, 200, r_val.content)
        revalo.refresh_from_db()
        self.assertEqual(revalo.produit_id, self.pa.pk)
        self.assertEqual(revalo.nouveau_cout, Decimal('45'))
        self.assertEqual(
            RevalorisationStock.objects.filter(produit=self.pb).count(), 0)
        self._invariants_b()

    def test_revalo_nouveau_cout_fige(self):
        revalo = creer_revalorisation(
            company=self.co_a, produit=self.pa, nouveau_cout='45',
            motif='baisse', user=self.admin_a)
        url = f'/api/django/stock/revalorisations-stock/{revalo.pk}/'
        r = self.api.patch(url, {'nouveau_cout': '1'}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('nouveau_cout', r.json())
        # Le motif d'un brouillon reste modifiable.
        r_motif = self.api.patch(url, {'motif': 'autre'}, format='json')
        self.assertEqual(r_motif.status_code, 200, r_motif.content)
        revalo.refresh_from_db()
        self.assertEqual(revalo.nouveau_cout, Decimal('45'))
        self.assertEqual(revalo.motif, 'autre')

    def test_cout_moyen_borne_societe(self):
        # Revalorisation VALIDÉE de A pointant (données héritées) le produit
        # de B : elle ne déplace jamais le coût de B.
        RevalorisationStock.objects.create(
            company=self.co_a, produit=self.pb, ancien_cout=Decimal('50'),
            nouveau_cout=Decimal('1'), quantite_snapshot=100,
            delta_valeur=Decimal('-4900'), motif='intrus',
            statut=RevalorisationStock.Statut.VALIDEE)
        RevalorisationStock.objects.filter(produit=self.pb).update(
            date_validation='2026-10-01T10:00:00Z')
        self._invariants_b()
