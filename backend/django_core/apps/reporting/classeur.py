"""XPLT22 — Classeur léger embarqué avec données live (mini-spreadsheet BI).

Différenciateur Odoo : aucun tableur in-app — les modèles financiers
partaient en export Excel mort. ``Classeur`` (même app, cf. ``models.py``)
persiste une grille de cellules (``cellules``) + des plages LIÉES à des
``core.SavedQuery`` (``liens``, re-exécutées au chargement). Les formules
(``=SOMME(A1:A3)``, ``=A1+B1``…) sont évaluées par l'évaluateur AST-sûr de
``core.formula`` — JAMAIS ``eval`` JS/Python libre.

Sécurité : une plage liée à une ``SavedQuery`` que le lecteur ne peut pas voir
(visibilité perso/partagé, comme ``Dashboard``) reste VIDE — jamais une fuite
cross-utilisateur ou cross-société."""
import re

from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.mixins import TenantMixin

from .models import Classeur, ClasseurPartageInterne

_CELL_REF_RE = re.compile(r'\b([A-Z]+)([0-9]+)\b')
_RANGE_RE = re.compile(r'\b([A-Z]+[0-9]+):([A-Z]+[0-9]+)\b')
_SOMME_RE = re.compile(r'^SOMME\(([^)]*)\)$', re.IGNORECASE)


def _col_to_index(col):
    """'A' -> 0, 'B' -> 1, … 'Z' -> 25, 'AA' -> 26 (base-26, sans zéro)."""
    idx = 0
    for ch in col:
        idx = idx * 26 + (ord(ch) - ord('A') + 1)
    return idx - 1


def _range_cells(start, end):
    """Liste des références de cellule d'une plage rectangulaire [start, end]
    INCLUSIVE (ex. 'A1:B2' -> ['A1', 'A2', 'B1', 'B2']), triée déterministe."""
    m1 = _CELL_REF_RE.match(start)
    m2 = _CELL_REF_RE.match(end)
    if not m1 or not m2:
        return []
    c1, r1 = _col_to_index(m1.group(1)), int(m1.group(2))
    c2, r2 = _col_to_index(m2.group(1)), int(m2.group(2))
    lo_c, hi_c = min(c1, c2), max(c1, c2)
    lo_r, hi_r = min(r1, r2), max(r1, r2)
    cells = []
    for c in range(lo_c, hi_c + 1):
        col = ''
        n = c + 1
        while n > 0:
            n, rem = divmod(n - 1, 26)
            col = chr(ord('A') + rem) + col
        for r in range(lo_r, hi_r + 1):
            cells.append(f'{col}{r}')
    return cells


def _cell_value(classeur, ref, *, user, _visiting=None):
    """Valeur RÉSOLUE d'une cellule (récursive sur les formules simples,
    garde anti-cycle). Une plage LIÉE (``liens``) est résolue via
    ``resolve_range`` ; une cellule absente vaut 0 (grille tolérante,
    jamais d'exception sur une référence vide)."""
    _visiting = _visiting or set()
    if ref in _visiting:
        return None  # cycle -> vide (jamais de boucle infinie)
    cell = (classeur.cellules or {}).get(ref)
    if cell is None:
        return 0
    if 'valeur' in cell:
        return cell['valeur']
    formule = cell.get('formule')
    if not formule:
        return 0
    _visiting = _visiting | {ref}
    try:
        return evaluate_formula(classeur, formule, user=user, _visiting=_visiting)
    except Exception:  # pragma: no cover - dégradation défensive
        return None


def resolve_range(classeur, range_ref, *, user):
    """XPLT22 — valeurs d'une plage, en respectant les droits du LECTEUR.

    Si ``range_ref`` est une plage LIÉE (``classeur.liens``) à une
    ``core.SavedQuery``, ré-exécute la requête (droits du lecteur — une
    requête invisible pour ``user`` renvoie une plage VIDE, jamais une
    fuite). Sinon résout les cellules brutes de la grille."""
    lien = (classeur.liens or {}).get(range_ref)
    if lien and lien.get('saved_query_id'):
        return _resolve_linked_range(classeur, lien['saved_query_id'], user=user)
    if ':' in range_ref:
        refs = _range_cells(*range_ref.split(':', 1))
    else:
        refs = [range_ref]
    return [_cell_value(classeur, r, user=user) for r in refs]


def _resolve_linked_range(classeur, saved_query_id, *, user):
    """Ré-exécute la ``SavedQuery`` liée SI le lecteur y a droit (même
    visibilité perso/partagé/société que le reste de ``core``) ; sinon renvoie
    une liste VIDE (jamais une exception, jamais une fuite)."""
    from django.db.models import Q
    from core.models import SavedQuery
    from core import data_explorer

    sq = (SavedQuery.objects
          .filter(company=classeur.company, id=saved_query_id)
          .filter(Q(owner=user) | Q(partage=True) | Q(owner__isnull=True))
          .first())
    if sq is None:
        return []  # invisible pour ce lecteur (ou inconnue) -> plage vide
    try:
        rows = data_explorer.run_query(sq.dataset, classeur.company, user, sq.spec)
    except Exception:  # pragma: no cover - dégradation défensive
        return []
    # Aplati les lignes en une liste de valeurs numériques (premier champ
    # numérique de chaque ligne) — représentation simple pour SOMME/moyenne.
    out = []
    for row in rows:
        for v in row.values():
            if isinstance(v, (int, float)):
                out.append(v)
                break
    return out


def evaluate_formula(classeur, formule, *, user, _visiting=None):
    """XPLT22 — évalue une formule ``=…`` (le ``=`` initial est optionnel).

    Deux formes reconnues :
      * ``SOMME(plage)`` — somme directe d'une plage (brute ou LIÉE) ;
      * toute autre expression — les références de cellule (``A1``, ``B2``…)
        sont substituées par leur valeur RÉSOLUE puis évaluées par
        ``core.formula.evaluer_formule`` (AST-sûr, jamais ``eval``)."""
    from core.formula import evaluer_formule

    expr = formule.lstrip('=').strip()
    m = _SOMME_RE.match(expr)
    if m:
        range_ref = m.group(1).strip()
        vals = resolve_range(classeur, range_ref, user=user)
        nums = [v for v in vals if isinstance(v, (int, float))]
        return sum(nums)

    # Substitue chaque référence de cellule par sa valeur résolue, sous forme
    # d'un contexte de variables (jamais une injection de code : les valeurs
    # SONT le contexte, l'expression reste évaluée par l'AST sûr).
    context = {}
    refs = sorted(set(_CELL_REF_RE.findall(expr)), key=lambda t: (t[0], t[1]))
    translated = expr
    for col, row in refs:
        ref = f'{col}{row}'
        varname = f'_cell_{col}_{row}'
        value = _cell_value(classeur, ref, user=user, _visiting=_visiting)
        context[varname] = value if isinstance(value, (int, float)) else 0
        translated = re.sub(rf'\b{re.escape(ref)}\b', varname, translated)

    return evaluer_formule(translated, context)


class ClasseurSerializer(serializers.ModelSerializer):
    class Meta:
        model = Classeur
        fields = [
            'id', 'titre', 'cellules', 'liens', 'partage',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ClasseurViewSet(TenantMixin, viewsets.ModelViewSet):
    """XPLT22 — CRUD du classeur + action d'évaluation live des cellules.

    Visibilité perso/partagée comme ``Dashboard``/``SavedQuery`` : un
    utilisateur voit SES classeurs + les partagés société + ceux sans
    propriétaire, PLUS ceux explicitement partagés en interne avec lui
    (``ClasseurPartageInterne``, réutilise le pattern XPLT10)."""
    serializer_class = ClasseurSerializer
    permission_classes = [IsAuthenticated]
    queryset = Classeur.objects.all()

    def get_queryset(self):
        from django.db.models import Q
        qs = super().get_queryset()
        user = self.request.user
        role = getattr(user, 'role_legacy', '') or ''
        partages_ids = ClasseurPartageInterne.objects.filter(
            classeur__company=getattr(user, 'company', None),
        ).filter(Q(utilisateur=user) | Q(role=role)).values_list(
            'classeur_id', flat=True)
        return qs.filter(
            Q(proprietaire=user) | Q(partage=True) | Q(proprietaire__isnull=True)
            | Q(id__in=list(partages_ids))
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, proprietaire=self.request.user)

    def perform_update(self, serializer):
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['get'])
    def rafraichir(self, request, pk=None):
        """XPLT22 — recalcule TOUTES les cellules du classeur (formules +
        plages liées re-exécutées) avec les droits du lecteur COURANT."""
        classeur = self.get_object()
        user = request.user
        resolved = {}
        for ref in (classeur.cellules or {}):
            resolved[ref] = _cell_value(classeur, ref, user=user)
        return Response({'cellules': resolved})

    @action(detail=True, methods=['post'], url_path='evaluer')
    def evaluer(self, request, pk=None):
        """XPLT22 — évalue UNE formule ad-hoc sans la persister (aperçu live
        pendant la saisie). Corps : ``{"formule": "=SOMME(A1:A3)"}``."""
        classeur = self.get_object()
        formule = (request.data.get('formule') or '').strip()
        if not formule:
            return Response({'detail': 'Champ « formule » requis.'}, status=400)
        try:
            valeur = evaluate_formula(classeur, formule, user=request.user)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response({'valeur': valeur})
