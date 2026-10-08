"""ALEA24 — garde de classe « table d'actions → code permissif par défaut ».

Chaque action d'écriture de ``VisiteTerrainViewSet`` (create, update,
partial_update, destroy et toute ``@action`` non GET) doit porter un code
EXPLICITE dans ``PERMISSIONS_ECRITURE`` ; une action absente est refusée au
lieu de retomber sur ``visites_modifier`` (le trou qui laissait ``renvoyer``
au Commercial terrain — ALEA8). Rouge sur 51f22174f (seules ``create`` et
``valider`` déclarées).
"""
from django.test import SimpleTestCase

from apps.roles.permissions_registre import ALL_PERMISSIONS
from apps.visites.views import CODE_ACTION_NON_DECLAREE, VisiteTerrainViewSet

CRUD_ECRITURE = ('create', 'update', 'partial_update', 'destroy')
METHODES_SURES = {'get', 'head', 'options'}


def actions_ecriture():
    """Les actions d'écriture du viewset, par INTROSPECTION (aucune liste
    écrite à la main : une nouvelle ``@action`` POST/PATCH/DELETE y entre
    d'elle-même)."""
    noms = set(CRUD_ECRITURE)
    for extra in VisiteTerrainViewSet.get_extra_actions():
        methodes = {m.lower() for m in extra.mapping.keys()}
        if methodes - METHODES_SURES:
            noms.add(extra.__name__)
    return noms


def _vue(action):
    vue = VisiteTerrainViewSet()
    vue.action = action
    return vue


class GardeCodesActionsTests(SimpleTestCase):
    def test_introspection_trouve_les_actions_connues(self):
        """Anti-faux-vert : l'introspection voit bien les gestes du terrain."""
        noms = actions_ecriture()
        for attendu in ('photos', 'supprimer_photo', 'mesures', 'terminer',
                        'valider', 'renvoyer', 'qualification', 'calage',
                        'assembler_photos', 'arriver', 'demarrer_route'):
            self.assertIn(attendu, noms)
        self.assertNotIn('photo_toit', noms)  # GET seulement

    def test_toute_action_ecriture_a_un_code_explicite(self):
        table = VisiteTerrainViewSet.PERMISSIONS_ECRITURE
        oubliees = sorted(actions_ecriture() - set(table))
        self.assertEqual(
            oubliees, [],
            'Action(s) d\'écriture de VisiteTerrainViewSet sans code explicite '
            f'dans PERMISSIONS_ECRITURE : {oubliees}')

    def test_les_codes_declares_existent(self):
        for action, code in VisiteTerrainViewSet.PERMISSIONS_ECRITURE.items():
            with self.subTest(action=action):
                self.assertIn(code, ALL_PERMISSIONS)

    def test_action_non_declaree_refusee(self):
        code = _vue('action_inventee').write_permission
        self.assertEqual(code, CODE_ACTION_NON_DECLAREE)
        self.assertNotEqual(code, 'visites_modifier')
        self.assertNotIn(code, ALL_PERMISSIONS)

    def test_codes_attendus(self):
        self.assertEqual(_vue('create').write_permission, 'visites_creer')
        self.assertEqual(_vue('valider').write_permission, 'visites_valider')
        self.assertEqual(_vue('renvoyer').write_permission, 'visites_valider')
        self.assertEqual(_vue('terminer').write_permission,
                         'visites_modifier')
