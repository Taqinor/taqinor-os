"""AUD419 — la lecture des règlements fournisseurs n'est plus ouverte à tous.

`PaiementFournisseurViewSet.get_permissions()` renvoyait `IsAnyRole()` pour
`READ_ACTIONS` : tout compte authentifié de la société — un magasinier sans la
moindre permission financière — listait `montant`/`date_paiement`/`facture` de
CHAQUE règlement, soit les rapprochements de trésorerie complets.

La question « un rôle métier a-t-il besoin de cette lecture ? » est tranchée par
preuve : l'unique écran consommateur (`/stock/paiements-fournisseur`, PACT51)
déclare déjà `roles: ['responsable','admin']` dans
`frontend/src/features/stock/module.config.jsx`, seule référence à cette
ressource dans tout le frontend. Resserrer aligne l'API sur son écran.

Ces tests sont ROUGES avant le correctif (200 avec les montants) et VERTS après
(403), tandis que Responsable et Admin restent à 200.

Run :
    python manage.py test apps.stock.test_aud419_paiement_fournisseur_lecture
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.stock.models import (
    FactureFournisseur, Fournisseur, PaiementFournisseur,
)

User = get_user_model()

URL = '/api/django/stock/paiements-fournisseur/'


class Aud419LecturePaiementsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='AUD419 Co', slug='aud419-co')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur AUD419', type='service')
        self.facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-AUD419-1',
            fournisseur=self.fournisseur,
            date_facture=datetime.date(2026, 5, 12),
            montant_ttc=Decimal('1000'))
        self.paiement = PaiementFournisseur.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('400'),
            date_paiement=datetime.date(2026, 5, 20))

    def _api(self, role_legacy, username):
        user = User.objects.create_user(
            username=username, password='pw-aud419-x',
            role_legacy=role_legacy, company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    # ── Le constat de l'audit ─────────────────────────────────────────────
    def test_role_minimal_ne_liste_plus_les_reglements(self):
        resp = self._api('normal', 'magasinier419').get(URL)
        self.assertEqual(resp.status_code, 403, resp.content)
        # Aucune donnée de règlement n'a fuité dans le corps de la réponse.
        self.assertNotIn(b'date_paiement', resp.content)
        self.assertNotIn(b'montant', resp.content)

    def test_role_minimal_ne_lit_plus_un_reglement_isole(self):
        resp = self._api('normal', 'magasinier419b').get(
            f'{URL}{self.paiement.id}/')
        self.assertEqual(resp.status_code, 403, resp.content)

    # ── Non-régression : les rôles légitimes sont inchangés ───────────────
    def test_responsable_liste_toujours(self):
        resp = self._api('responsable', 'resp419').get(URL)
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_admin_liste_toujours(self):
        resp = self._api('admin', 'admin419').get(URL)
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_admin_lit_toujours_un_reglement_isole(self):
        resp = self._api('admin', 'admin419b').get(
            f'{URL}{self.paiement.id}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(str(resp.data['id']), str(self.paiement.id))

    def test_la_suppression_reste_reservee_a_ladmin(self):
        resp = self._api('responsable', 'resp419b').delete(
            f'{URL}{self.paiement.id}/')
        self.assertEqual(resp.status_code, 403, resp.content)
