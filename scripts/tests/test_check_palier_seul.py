"""ADRG79 — scripts/check_palier_seul.py (routes d'écriture au seul palier).

Stdlib pur (unittest), sans Django — dépôt factice en dossier temporaire
(patron ``test_check_action_permission_override.py``). Run :
    python -m unittest scripts.tests.test_check_palier_seul -v
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_palier_seul as guard  # noqa: E402 — après sys.path/setup() (D-ENF22)

REL = "backend/django_core/apps/demo/views.py"

PALIER_SEUL = '''
class DemoViewSet(viewsets.ModelViewSet):
    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]
'''

AVEC_CODE = '''
class DemoViewSet(viewsets.ModelViewSet):
    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        if self.action == 'create':
            return [IsResponsableOrAdmin(), DroitDeLaGrille('x_creer')()]
        return [IsResponsableOrAdmin(), HasPermissionOrLegacy('x_gerer')()]
'''


def _run(src, dette=None, argv=()):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = root / REL
        path.parent.mkdir(parents=True)
        path.write_text(src, encoding="utf-8")
        (root / "scripts").mkdir()
        if dette is not None:
            (root / guard.DETTE).write_text("\n".join(dette) + "\n", encoding="utf-8")
        out = io.StringIO()
        with redirect_stdout(out):
            code = guard.main(list(argv), root=root)
        dette_ecrite = guard.lire_dette(root)
        return code, out.getvalue(), dette_ecrite


class PalierSeulTests(unittest.TestCase):
    def test_route_neuve_au_seul_palier_refusee(self):
        code, sortie, _ = _run(PALIER_SEUL)
        self.assertEqual(code, 1)
        self.assertIn(f"{REL}::DemoViewSet.create", sortie)

    def test_route_avec_code_de_la_grille_acceptee(self):
        code, sortie, _ = _run(AVEC_CODE)
        self.assertEqual(code, 0, sortie)

    def test_dette_sans_site_perimee(self):
        code, sortie, _ = _run(AVEC_CODE, dette=[f"{REL}::DemoViewSet.create"])
        self.assertEqual(code, 1)
        self.assertIn("dette périmée", sortie)

    def test_amorcage_puis_vert(self):
        _code, _sortie, dette = _run(PALIER_SEUL, argv=["--amorcer"])
        self.assertIn(f"{REL}::DemoViewSet.create", dette)
        code, sortie, _ = _run(PALIER_SEUL, dette=sorted(dette))
        self.assertEqual(code, 0, sortie)

    def test_action_d_ecriture_et_vue_fonction(self):
        src = '''
class DemoViewSet(viewsets.GenericViewSet):
    permission_classes = [IsResponsableOrAdmin]

    @action(detail=True, methods=['post'])
    def valider(self, request, pk=None):
        return None

    @action(detail=True, methods=['get'])
    def lire(self, request, pk=None):
        return None


@api_view(['POST'])
@permission_classes([IsResponsableOrAdmin])
def relancer(request):
    return None


@api_view(['POST'])
@permission_classes([IsResponsableOrAdmin, IsAdminRole])
def purger(request):
    return None
'''
        _code, _sortie, dette = _run(src, argv=["--amorcer"])
        self.assertEqual(dette, {f"{REL}::DemoViewSet.valider", f"{REL}::relancer"})


if __name__ == "__main__":
    unittest.main()
