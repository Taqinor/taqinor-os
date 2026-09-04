"""Tests AUD421 — scripts/check_action_permission_override.py.

Stdlib pur (unittest), sans Django — miroir de la garde DB-free. Run :
    python -m unittest scripts.tests.test_check_action_permission_override -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_action_permission_override as guard  # noqa: E402


def _verdicts(src):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'views.py'
        path.write_text(src, encoding='utf-8')
        return {classe: (verdict, decouvertes)
                for _l, classe, verdict, decouvertes in guard.check_file(path)}


# LE TEST ROUGE du `Done =` — reproduction EXACTE du motif `devis.py` d'avant
# AUD403 : branchement brut sur `self.action`, repli en dur, et une @action qui
# déclare une permission que le branchement ne nomme JAMAIS. DRF appellera
# get_permissions() et la déclaration inline sera purement ignorée.
MOTIF_AUD403 = '''
class DevisViewSet(viewsets.ModelViewSet):
    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsAdminRole()]

    @action(detail=True, methods=['post'],
            permission_classes=[IsResponsableOrAdmin])
    def accepter(self, request, pk=None):
        return None
'''

PATRON_D_OR = '''
class PaiementViewSet(viewsets.ModelViewSet):
    def get_permissions(self):
        declarees = declared_action_permissions(self)
        if declarees is not None:
            return declarees
        return [IsAdminRole()]

    @action(detail=True, methods=['post'],
            permission_classes=[IsResponsableOrAdmin])
    def encaisser(self, request, pk=None):
        return None
'''

PATRON_REPLI_SUPER = '''
class DeclarationTVAViewSet(viewsets.ModelViewSet):
    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return super().get_permissions()

    @action(detail=True, methods=['post'],
            permission_classes=[IsResponsableOrAdmin])
    def teledeclarer(self, request, pk=None):
        return None
'''

PATRON_COUVERTURE_EXPLICITE = '''
READ_ACTIONS = ['list', 'retrieve']


class DevisViewSet(viewsets.ModelViewSet):
    def get_permissions(self):
        if self.action in READ_ACTIONS + ['historique']:
            return [IsAnyRole()]
        elif self.action in ('accepter', 'refuser'):
            return [HasPermissionOrLegacy('ventes_valider')()]
        return [IsAdminRole()]

    @action(detail=True, methods=['post'],
            permission_classes=[HasPermissionOrLegacy('ventes_valider')])
    def accepter(self, request, pk=None):
        return None

    @action(detail=True, methods=['get'], permission_classes=[IsAnyRole])
    def historique(self, request, pk=None):
        return None
'''

SANS_GET_PERMISSIONS = '''
class SimpleViewSet(viewsets.ModelViewSet):
    @action(detail=True, methods=['post'],
            permission_classes=[IsResponsableOrAdmin])
    def accepter(self, request, pk=None):
        return None
'''

ACTION_SANS_PERMISSIONS = '''
class AutreViewSet(viewsets.ModelViewSet):
    def get_permissions(self):
        return [IsAdminRole()]

    @action(detail=True, methods=['post'])
    def accepter(self, request, pk=None):
        return None
'''


class DetectionTests(unittest.TestCase):
    def test_le_motif_aud403_est_refuse(self):
        verdicts = _verdicts(MOTIF_AUD403)
        self.assertEqual(verdicts['DevisViewSet'][0], 'NU')
        self.assertEqual(verdicts['DevisViewSet'][1], ['accepter'])

    def test_le_patron_d_or_est_accepte(self):
        self.assertEqual(_verdicts(PATRON_D_OR)['PaiementViewSet'][0], 'or')

    def test_le_repli_super_est_accepte(self):
        self.assertEqual(
            _verdicts(PATRON_REPLI_SUPER)['DeclarationTVAViewSet'][0], 'repli')

    def test_la_couverture_explicite_est_acceptee(self):
        """Le patron `devis.py` d'APRÈS AUD403 : chaque action est nommée,
        y compris via une constante de module (`READ_ACTIONS`)."""
        self.assertEqual(
            _verdicts(PATRON_COUVERTURE_EXPLICITE)['DevisViewSet'][0],
            'couvert')

    def test_une_classe_sans_get_permissions_est_hors_perimetre(self):
        self.assertEqual(_verdicts(SANS_GET_PERMISSIONS), {})

    def test_une_action_sans_permission_classes_est_hors_perimetre(self):
        self.assertEqual(_verdicts(ACTION_SANS_PERMISSIONS), {})


class PerimetreTests(unittest.TestCase):
    def test_les_tests_et_migrations_sont_hors_perimetre(self):
        for chemin in ('apps/ventes/tests/test_devis.py',
                       'apps/ventes/tests_devis.py',
                       'apps/ventes/migrations/0001_init.py'):
            self.assertTrue(guard._is_test_path(Path(chemin)), chemin)

    def test_le_code_de_production_est_dans_le_perimetre(self):
        scannes = {guard._rel(p) for p in guard._iter_source_files()}
        self.assertIn('backend/django_core/apps/ventes/views/devis.py', scannes)
        self.assertIn('backend/django_core/authentication/views.py', scannes)


class AllowlistTests(unittest.TestCase):
    def test_la_ligne_de_base_du_sweep_est_gelee(self):
        allow = guard._load_allowlist()
        self.assertGreaterEqual(
            len(allow), 25,
            'la ligne de base du sweep AUD403 a été vidée : la garde '
            'échouerait sur des classes déjà vérifiées bénignes.')
        self.assertIn(
            'backend/django_core/apps/ventes/views/devis.py::DevisViewSet',
            allow)

    def test_le_patron_d_or_reel_est_detecte_sans_allowlist(self):
        """`ventes/views/paiement.py` passe par le PATRON, pas par la liste."""
        chemin = (guard.DJANGO_CORE / 'apps' / 'ventes' / 'views'
                  / 'paiement.py')
        verdicts = {classe: verdict
                    for _l, classe, verdict, _d in guard.check_file(chemin)}
        self.assertEqual(verdicts.get('PaiementViewSet'), 'or')
        self.assertNotIn(
            'backend/django_core/apps/ventes/views/paiement.py'
            '::PaiementViewSet',
            guard._load_allowlist())

    def test_le_depot_est_propre(self):
        """La garde passe sur le dépôt réel (aucune classe hors allowlist)."""
        self.assertEqual(guard.main([]), 0)


if __name__ == '__main__':
    unittest.main()
