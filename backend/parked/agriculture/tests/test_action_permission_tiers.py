"""Verrouille la correspondance entre le kwarg ``permission_classes`` de
chaque ``@action`` Agriculture et le tier réellement appliqué par
``get_permissions()`` (même patron que
``apps.sav.tests_ticket_action_permissions``).

Contexte du bug corrigé : ``_AgricultureBaseViewSet.get_permissions()`` était
une surcharge qui branchait UNIQUEMENT sur ``self.action in READ_ACTIONS``
(``list``/``retrieve``) — toute ``@action`` décorée ``permission_classes=[…]``
mais absente de ``READ_ACTIONS`` retombait silencieusement sur
``IsResponsableOrAdmin``, jetant en silence le kwarg du décorateur. Le
correctif introduit ``core.permissions.declared_action_permissions`` : une
garde déclarée par l'``@action`` elle-même PRIME désormais sur le tiering
lecture/écriture.

Comportement DÉLIBÉRÉMENT relâché (autorisé fondateur) par ce correctif :
``CampagneCulturaleViewSet.cout_irrigation`` (``cout-irrigation``) et
``LotRecolteViewSet.tracabilite`` (``tracabilite``) déclarent tous deux
``[IsAnyRole]`` et exigent désormais réellement ``IsAnyRole`` au lieu de
l'``IsResponsableOrAdmin`` subi avant correctif. INCHANGÉ :
``CampagneCulturaleViewSet.registre_phyto_pdf`` (``registre-phyto-pdf``,
``[IsResponsableOrAdmin]``) et le tiering list/retrieve (IsAnyRole) vs
create/update/destroy (IsResponsableOrAdmin) des autres viewsets Agriculture.

Ce module prouve, à trois niveaux :

1. Le tier RENVOYÉ par ``get_permissions()`` correspond EXACTEMENT au tier
   DÉCLARÉ par chaque ``@action`` Agriculture — attrape aussi toute future
   ``@action`` ajoutée sans que ``get_permissions`` ne la respecte.
2. Le tier est réellement ENFORCÉ en HTTP (APIClient) : un rôle non
   responsable passe désormais sur les deux endpoints relâchés, un appel non
   authentifié est rejeté, et la relaxation ne s'est PAS propagée à l'action
   PDF (toujours Responsable/Admin).
3. L'isolation multi-tenant reste intacte : un utilisateur d'une AUTRE société
   reçoit 404 (jamais 200) sur les deux endpoints relâchés — la relaxation du
   rôle ne relâche pas le scoping société.
"""
import inspect

from django.test import TestCase
from rest_framework.test import APIClient

from apps.agriculture import views as agriculture_views
from apps.agriculture.models import CampagneCulturale, Exploitation, Parcelle
from apps.agriculture.services import creer_lot_recolte
from apps.agriculture.views import (
    CampagneCulturaleViewSet, LotRecolteViewSet, _AgricultureBaseViewSet,
)

from .helpers import auth, make_company, make_user

# ─────────────────────────────────────────────────────────────────────────
# Découverte générique des @action Agriculture qui déclarent
# permission_classes — même mécanique que le précédent apps.sav.
# ─────────────────────────────────────────────────────────────────────────


def _agriculture_viewsets():
    """Chaque classe de viewset Agriculture concrète (hérite de
    ``_AgricultureBaseViewSet``, base elle-même exclue)."""
    out = []
    for _name, obj in inspect.getmembers(agriculture_views, inspect.isclass):
        if obj is _AgricultureBaseViewSet:
            continue
        if issubclass(obj, _AgricultureBaseViewSet):
            out.append(obj)
    return out


def _declared_actions(viewset_cls):
    """{nom_action: permission_classes déclarées} pour chaque ``@action`` du
    viewset qui pose explicitement ``permission_classes`` sur son
    décorateur."""
    out = {}
    for name, method in inspect.getmembers(viewset_cls, inspect.isfunction):
        if not hasattr(method, 'mapping'):
            continue  # pas une @action DRF
        declared = (getattr(method, 'kwargs', {}) or {}).get('permission_classes')
        if declared:
            out[name] = declared
    return out


def _tier_names(viewset_cls, action_name):
    view = viewset_cls()
    view.action = action_name
    perms = view.get_permissions()
    return [type(p).__name__ for p in perms]


class AgricultureActionPermissionTierTests(TestCase):
    def test_get_permissions_honors_every_action_decorator(self):
        """Chaque @action Agriculture doit obtenir, via get_permissions(), le
        MÊME tier que son décorateur permission_classes déclare (jamais un
        IsResponsableOrAdmin subi)."""
        found_any = False
        for viewset_cls in _agriculture_viewsets():
            for action_name, declared in _declared_actions(viewset_cls).items():
                found_any = True
                expected = [perm.__name__ for perm in declared]
                with self.subTest(viewset=viewset_cls.__name__, action=action_name):
                    actual = _tier_names(viewset_cls, action_name)
                    self.assertEqual(
                        actual, expected,
                        f"{viewset_cls.__name__}.{action_name} déclare "
                        f"{expected} mais get_permissions() renvoie {actual} "
                        f"— la garde de l'@action doit primer "
                        f"(declared_action_permissions).")
        self.assertTrue(
            found_any,
            "aucune @action Agriculture déclarant permission_classes "
            "détectée — test cassé ?")

    def test_relaxed_read_actions_now_isanyrole(self):
        """Régression : cout-irrigation et tracabilite exigeaient
        IsResponsableOrAdmin avant le correctif get_permissions() ; ils
        exposent désormais IsAnyRole, exactement ce que déclare leur
        décorateur."""
        self.assertEqual(
            _tier_names(CampagneCulturaleViewSet, 'cout_irrigation'),
            ['IsAnyRole'])
        self.assertEqual(
            _tier_names(LotRecolteViewSet, 'tracabilite'),
            ['IsAnyRole'])

    def test_registre_phyto_pdf_stays_responsable_or_admin(self):
        """La relaxation ne doit PAS avoir déteint sur l'action PDF/export —
        elle reste strictement Responsable/Admin."""
        self.assertEqual(
            _tier_names(CampagneCulturaleViewSet, 'registre_phyto_pdf'),
            ['IsResponsableOrAdmin'])


# ─────────────────────────────────────────────────────────────────────────
# Enforcement HTTP réel + isolation multi-tenant.
# ─────────────────────────────────────────────────────────────────────────


class AgricultureActionPermissionHttpTests(TestCase):
    def setUp(self):
        self.co_a = make_company('agr-perm-a', 'Ferme Permissions A')
        self.co_b = make_company('agr-perm-b', 'Ferme Permissions B')
        # Rôle non-responsable authentifié (legacy 'normal' : is_responsable
        # est False — cf. authentication.models.CustomUser.is_responsable —
        # mais IsAnyRole ne demande qu'un compte interne authentifié).
        self.normal_a = make_user(self.co_a, 'agr-perm-normal-a', 'normal')
        # Société B : même un compte plein-pouvoir (admin) de la MAUVAISE
        # société doit être bloqué par le scoping tenant, pas par le rôle —
        # ça prouve que l'isolation vient du queryset, pas de la permission.
        self.admin_b = make_user(self.co_b, 'agr-perm-admin-b', 'admin')

        exploitation_a = Exploitation.objects.create(
            company=self.co_a, nom='Domaine A')
        self.parcelle_a = Parcelle.objects.create(
            company=self.co_a, exploitation=exploitation_a, nom='Parcelle A')
        self.campagne_a = CampagneCulturale.objects.create(
            company=self.co_a, parcelle=self.parcelle_a, culture='Blé',
            date_recolte_prevue='2026-06-30')
        self.lot_a = creer_lot_recolte(
            company=self.co_a, campagne=self.campagne_a,
            date_recolte='2026-06-30', quantite_qtl='10')

        self.cout_irrigation_url = (
            f'/api/django/agriculture/campagnes/{self.campagne_a.id}'
            '/cout-irrigation/')
        self.tracabilite_url = (
            f'/api/django/agriculture/lots-recolte/{self.lot_a.id}'
            '/tracabilite/')
        self.registre_phyto_url = (
            f'/api/django/agriculture/campagnes/{self.campagne_a.id}'
            '/registre-phyto-pdf/')

    # --- rôle non-responsable désormais AUTORISÉ (la relaxation) ---

    def test_cout_irrigation_allowed_for_non_responsable_role(self):
        resp = auth(self.normal_a).get(self.cout_irrigation_url)
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_tracabilite_allowed_for_non_responsable_role(self):
        resp = auth(self.normal_a).get(self.tracabilite_url)
        self.assertEqual(resp.status_code, 200, resp.data)

    # --- accès refusé : appel non authentifié ---

    def test_cout_irrigation_requires_authentication(self):
        resp = APIClient().get(self.cout_irrigation_url)
        self.assertIn(resp.status_code, (401, 403))

    def test_tracabilite_requires_authentication(self):
        resp = APIClient().get(self.tracabilite_url)
        self.assertIn(resp.status_code, (401, 403))

    # --- la relaxation n'a PAS fuité vers l'action PDF/export ---

    def test_registre_phyto_pdf_stays_forbidden_for_non_responsable(self):
        resp = auth(self.normal_a).get(self.registre_phyto_url)
        self.assertEqual(resp.status_code, 403, resp.data)

    # --- isolation multi-tenant : la relaxation du rôle ne relâche PAS le
    # scoping société — garde de non-régression critique ---

    def test_cout_irrigation_cross_tenant_returns_404(self):
        resp = auth(self.admin_b).get(self.cout_irrigation_url)
        self.assertEqual(resp.status_code, 404, resp.data)

    def test_tracabilite_cross_tenant_returns_404(self):
        resp = auth(self.admin_b).get(self.tracabilite_url)
        self.assertEqual(resp.status_code, 404, resp.data)
