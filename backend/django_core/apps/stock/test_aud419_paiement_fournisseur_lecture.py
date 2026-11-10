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

    def test_lectures_stock_bornees_au_module(self):
        """APFS106 (C-APFS-080/081, D-APFS-4) — balai des routeurs ``stock``
        et ``achats`` : la lecture ``list`` de CHAQUE vue est refusée à Admin
        RH et Commercial terrain (aucun code stock) ; Commercial, Technicien
        (``stock_voir``), Directeur et le compte hérité lisent les 44 vues
        rouvertes ; le fournisseur (RIB) : 403 à Admin RH, 200 au Technicien.
        Hors balai : la fiche technique (propriétaire calepinage, APFS109)."""
        from apps.achats.urls import router as routeur_achats
        from apps.roles import permissions_registre as registre
        from apps.roles.models import Role
        from apps.stock.urls import router as routeur_stock
        from authentication.tests_asec11_responsable_module import (
            lectures_acceptees,
        )

        def compte(nom, permissions):
            role = Role.objects.create(company=self.company, nom=nom,
                                       permissions=list(permissions),
                                       est_systeme=False)
            return User.objects.create_user(
                username=f'apfs106-{nom}', password='x', company=self.company,
                role=role, role_legacy='responsable')
        refuses = {nom: compte(nom, perms) for nom, perms in (
            ('admin_rh', registre.ADMIN_RH_PERMISSIONS),
            ('commercial_terrain', registre.COMMERCIAL_TERRAIN_PERMISSIONS))}
        admis = {nom: compte(nom, perms) for nom, perms in (
            ('commercial', registre.COMMERCIAL_PERMISSIONS),
            ('technicien', registre.TECHNICIEN_PERMISSIONS),
            ('directeur', registre.DIRECTEUR_PERMISSIONS))}
        admis['herite'] = User.objects.create_user(
            username='apfs106-herite', password='x', company=self.company,
            role_legacy='responsable')
        vues = list(dict.fromkeys(
            vs for routeur in (routeur_stock, routeur_achats)
            for _prefixe, vs, _nom in routeur.registry
            if not vs.__module__.endswith('.fiche_technique')))
        for (vue, nom), accepte in lectures_acceptees(vues, refuses).items():
            self.assertFalse(accepte, f'{vue} : lecture ouverte à {nom}')
        rouvertes = [vs for vs in vues if any(
            'LectureDuModule' == type(g).__name__
            for g in _gardes_de_liste(vs))]
        self.assertEqual(len(rouvertes), 44, [vs.__name__ for vs in rouvertes])
        for (vue, nom), accepte in lectures_acceptees(rouvertes, admis).items():
            self.assertTrue(accepte, f'{vue} : lecture refusée à {nom}')
        Fournisseur.objects.filter(pk=self.fournisseur.pk).update(
            rib='011780000012345678901234')
        for user, attendu in ((refuses['admin_rh'], 403),
                              (admis['technicien'], 200)):
            api = APIClient()
            api.force_authenticate(user)
            r = api.get(f'/api/django/stock/fournisseurs/{self.fournisseur.pk}/')
            self.assertEqual(r.status_code, attendu, r.content[:200])


def _gardes_de_liste(classe):
    """Gardes de la lecture ``list`` d'un viewset (sans requête)."""
    from types import SimpleNamespace
    vue = classe()
    vue.action = 'list'
    vue.format_kwarg = None
    vue.request = SimpleNamespace(method='GET', user=None)
    return vue.get_permissions()
