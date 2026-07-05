"""Verrouille la correspondance entre le kwarg ``permission_classes`` de chaque
``@action`` de ``TicketViewSet`` et le tier réellement appliqué par
``get_permissions()``.

Contexte du bug : ``TicketViewSet.get_permissions()`` est une surcharge qui
n'inspecte PAS ``self.permission_classes`` — elle branche sur ``self.action``
via des listes en dur. Toute ``@action`` décorée avec ``permission_classes=[…]``
mais ABSENTE de ces listes retombe silencieusement sur ``IsAdminRole`` (plus
restrictif que voulu — le kwarg du décorateur devient du code mort).

Le test central lit dynamiquement le ``permission_classes`` déclaré par chaque
``@action`` et vérifie que ``get_permissions()`` renvoie EXACTEMENT le même tier
— donc il attrape aussi toute future ``@action`` ajoutée sans mise à jour de
``get_permissions()``.
"""
import inspect

from django.test import TestCase

from apps.sav.views import TicketViewSet


def _action_methods():
    """Toutes les méthodes ``@action`` de TicketViewSet (marquées par DRF avec
    un attribut ``mapping``) portant un ``permission_classes`` explicite."""
    out = {}
    for name, method in inspect.getmembers(TicketViewSet, inspect.isfunction):
        if not hasattr(method, 'mapping'):
            continue  # pas une @action
        declared = (getattr(method, 'kwargs', {}) or {}).get('permission_classes')
        if declared:
            out[name] = declared
    return out


def _tier_name(action):
    view = TicketViewSet()
    view.action = action
    perms = view.get_permissions()
    assert len(perms) == 1, f"{action}: {len(perms)} permission(s)"
    return type(perms[0]).__name__


class TicketActionPermissionTierTests(TestCase):
    def test_get_permissions_honors_every_action_decorator(self):
        """Chaque @action doit obtenir, via get_permissions(), le MÊME tier que
        son décorateur permission_classes déclare (jamais un IsAdminRole subi)."""
        decorated = _action_methods()
        self.assertTrue(decorated, "aucune @action détectée — test cassé ?")
        for name, declared in decorated.items():
            with self.subTest(action=name):
                expected = declared[0].__name__  # ex. HasPermissionOrLegacy_sav_gerer
                actual = _tier_name(name)
                self.assertEqual(
                    actual, expected,
                    f"@action '{name}' déclare {expected} mais get_permissions() "
                    f"renvoie {actual} — ajoute '{name}' au bon bucket de "
                    f"TicketViewSet.get_permissions().")

    def test_no_ticket_action_falls_through_to_admin(self):
        """Aucune @action de TicketViewSet n'est censée être admin-only : une
        qui retombe sur IsAdminRole trahit un oubli dans get_permissions()."""
        for name in _action_methods():
            with self.subTest(action=name):
                self.assertNotEqual(
                    _tier_name(name), 'IsAdminRole',
                    f"@action '{name}' retombe sur IsAdminRole (oubli dans "
                    f"get_permissions()).")

    def test_previously_broken_actions_regression(self):
        """Régression explicite : ces endpoints déclaraient sav_gerer/sav_voir
        mais exigeaient IsAdminRole avant le correctif."""
        gerer = ['pieces_compatibles', 'premier_reponse', 'pieces',
                 'supprimer_piece', 'pieces_retirees', 'generer_facture',
                 'prets_equipement', 'retourner_pret', 'creer_lead', 'checklist']
        for name in gerer:
            with self.subTest(action=name):
                self.assertEqual(_tier_name(name), 'HasPermissionOrLegacy_sav_gerer')
        self.assertEqual(_tier_name('triage_ia'), 'HasPermissionOrLegacy_sav_voir')

    def test_destroy_stays_admin_only(self):
        self.assertEqual(_tier_name('destroy'), 'IsAdminRole')

    def test_reads_stay_sav_voir(self):
        for name in ['historique', 'rapport_pdf', 'lien_client', 'similaires']:
            with self.subTest(action=name):
                self.assertEqual(_tier_name(name), 'HasPermissionOrLegacy_sav_voir')
