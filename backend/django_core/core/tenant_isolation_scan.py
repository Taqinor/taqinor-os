"""Découverte des viewsets ``TenantMixin`` + factory générique tolérante
(YRBAC12).

``TenantMixin`` scope ~104 viewsets à ``request.user.company``, mais AUCUN
test transversal ne prouvait, avant YRBAC12, qu'un objet de la société B est
INVISIBLE (list) et 404 (retrieve/patch/delete) pour un utilisateur de la
société A. Ce module :

* ``discover_tenant_viewsets()`` parcourt l'URLconf racine (même technique que
  ``core.rbac_inventory``) et renvoie chaque ``ModelViewSet`` **ou**
  ``ReadOnlyModelViewSet`` concret qui porte ``TenantMixin`` dans son MRO, avec
  le chemin de base de son router. CRX17 — les ``ReadOnlyModelViewSet`` étaient
  exclus « faute d'update/destroy à tester » : c'était une faute de
  raisonnement, la fuite de LECTURE (list qui montre l'objet du voisin,
  retrieve qui répond 200) est exactement la même et n'était couverte nulle
  part. Les assertions PATCH/DELETE acceptent déjà 405 pour ces vues ;
* ``build_minimal_instance(model, company)`` est une factory TOLÉRANTE : elle
  ne pose QUE les champs obligatoires (``null=False``, pas de défaut, pas
  ``auto_now*``/``auto_created``), synthétise une valeur triviale par type de
  champ (construisant récursivement un ``Company``/``CustomUser`` minimal pour
  les FK obligatoires ``company``/``created_by``/``auteur``/``user`` — les deux
  seuls modèles FOUNDATION connus), et lève ``SkipModel`` (jamais une exception
  non gérée) dès qu'un champ obligatoire est un ``ForeignKey``/``ManyToMany``
  vers un AUTRE modèle, ou un type de champ non géré — ce modèle reste alors de
  la dette EXPLICITE listée par le test, jamais silencieusement exclue ;
* ``build_foreign_relation_payload(view_class, company)`` (CRX17) synthétise un
  corps de CRÉATION dont une relation inscriptible pointe une ligne d'une AUTRE
  société — le trou que le balai ne voyait pas : il n'exerçait que la LECTURE
  et l'ÉDITION d'un objet existant, jamais l'accrochage d'un objet NEUF à une
  ligne du voisin (l'audit CRM a trouvé 13 relations nues par ce chemin) ;
* ``detail_get_actions(view_class)`` (CRX17) énumère les
  ``@action(detail=True)`` acceptant GET : elles sortaient entièrement du
  balai, alors qu'une action qui n'appelle pas ``self.get_object()`` répond
  200 sur l'objet du voisin.

``core`` reste FONDATION : aucun import d'app métier au niveau module (les
imports de modèles concrets sont FONCTION-LOCAUX, déclenchés par la
découverte d'URL elle-même, jamais un import statique d'``apps.*``).
"""
from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from decimal import Decimal

from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework import viewsets

# Nettoyage défensif d'un pattern d'URL brut (regex ``re_path`` OU route
# ``path()``) en chemin appelable tel quel par un client de test — retire les
# ancres regex (^, $) et les groupes nommés type ``(?P<pk>[^/.]+)`` (jamais
# rencontrés sur une route LISTE, mais gardé en défense en profondeur).
_RE_ANCHORS = re.compile(r"[$^]")
_RE_NAMED_GROUP = re.compile(r"\(\?P<\w+>[^)]*\)")


class SkipModel(Exception):
    """Levée par ``build_minimal_instance`` quand un modèle ne peut pas être
    construit de façon triviale (dette explicite, jamais un skip silencieux)."""


@dataclass(frozen=True)
class TenantViewSetEntry:
    """Un viewset ``TenantMixin`` concret découvert sur le router, avec le
    préfixe de chemin sous lequel sa liste/son détail sont montés."""
    view_class: type
    list_path: str  # ex. "/api/django/litiges/reclamations/"

    @property
    def model(self):
        # NB : ne PAS utiliser ``qs and qs.model`` — évaluer la vérité d'un
        # QuerySet exécute une requête ; sur une base de test vide il renvoie
        # False et court-circuite vers le QuerySet vide (au lieu de .model),
        # ce qui faisait sauter TOUS les viewsets du balayage (exercised==0).
        qs = getattr(self.view_class, "queryset", None)
        return qs.model if qs is not None else None

    def detail_path(self, pk) -> str:
        return f"{self.list_path.rstrip('/')}/{pk}/"


def _iter_patterns(patterns, prefix=""):
    for entry in patterns:
        if isinstance(entry, URLResolver):
            new_prefix = prefix + str(entry.pattern)
            yield from _iter_patterns(entry.url_patterns, new_prefix)
        elif isinstance(entry, URLPattern):
            yield prefix + str(entry.pattern), entry


def _is_concrete_tenant_modelviewset(view_class) -> bool:
    if view_class is None:
        return False
    # CRX17 — ``ReadOnlyModelViewSet`` est INCLUS : il n'a certes ni update ni
    # destroy (les assertions correspondantes tolèrent 405), mais la fuite de
    # LECTURE — list qui montre l'objet du voisin, retrieve qui répond 200 —
    # est identique et n'était couverte par aucun test transversal.
    if not issubclass(view_class, (viewsets.ModelViewSet,
                                   viewsets.ReadOnlyModelViewSet)):
        return False
    # Exclut les viewsets sans TenantMixin dans le MRO (hors périmètre —
    # pas de garantie d'isolation à prouver ici).
    return any(base.__name__ == "TenantMixin" for base in view_class.__mro__)


def discover_tenant_viewsets() -> list[TenantViewSetEntry]:
    """Renvoie chaque ``ModelViewSet`` concret (list monté sur le router)
    portant ``TenantMixin``, dédupliqué par classe. Le chemin de LISTE
    (ex. ``…/reclamations/``) est dérivé du premier pattern SANS group vu pour
    cette vue — les détails/actions dérivent leur URL de ce même préfixe."""
    resolver = get_resolver()
    seen: dict[type, str] = {}
    for full_pattern, url_pattern in _iter_patterns(resolver.url_patterns):
        callback = url_pattern.callback
        view_class = getattr(callback, "cls", None)
        if not _is_concrete_tenant_modelviewset(view_class):
            continue
        if view_class in seen:
            continue
        # Distingue la route LISTE de la route DÉTAIL par les actions DRF
        # résolues sur le callback (fiable, indépendant du moteur d'URL
        # sous-jacent — regex ``re_path`` ou convertisseurs ``path()``),
        # plutôt que de re-parser le pattern brut.
        actions = getattr(callback, "actions", {}) or {}
        if "list" not in actions.values():
            continue
        cleaned = _RE_NAMED_GROUP.sub("", _RE_ANCHORS.sub("", full_pattern))
        path = "/" + cleaned.strip("/")
        path = re.sub(r"/+", "/", path)
        if not path.endswith("/"):
            path += "/"
        seen[view_class] = path
    return [
        TenantViewSetEntry(view_class=vc, list_path=path)
        for vc, path in sorted(seen.items(), key=lambda kv: kv[1])
    ]


# ── Factory générique tolérante ─────────────────────────────────────────────

# Modèles FOUNDATION qu'on sait construire trivialement quand un champ
# obligatoire les référence (au-delà de Company, posée explicitement par
# l'appelant). Tout AUTRE modèle référencé par un FK obligatoire → SkipModel
# (dette explicite listée par le test, jamais un skip muet).
_KNOWN_SIMPLE_RELATED = frozenset({
    "Company",
    "CustomUser",  # settings.AUTH_USER_MODEL — created_by/auteur/user courants.
})


_UNIQUE_COUNTER = {"n": 0}


def _next_unique_suffix() -> str:
    _UNIQUE_COUNTER["n"] += 1
    return f"y12-{_UNIQUE_COUNTER['n']}"


def _build_known_related(related_model, company):
    """Construit une instance MINIMALE d'un modèle FOUNDATION connu, scopée à
    ``company`` quand ce modèle porte lui-même un champ ``company``."""
    if related_model.__name__ == "Company":
        return company
    if related_model.__name__ == "CustomUser":
        return related_model.objects.create_user(
            username=f"yrbac12-fk-{_next_unique_suffix()}",
            password="x",
            company=company,
        )
    raise SkipModel(f"modèle FOUNDATION non géré : {related_model.__name__}")


def _synthetic_scalar(field):
    """Valeur triviale pour un champ scalaire (jamais pour une FK/M2M)."""
    from django.db import models as m

    if isinstance(field, m.BooleanField):
        return False
    if isinstance(field, (m.CharField, m.SlugField, m.TextField)):
        if field.choices:
            return field.choices[0][0]
        max_len = getattr(field, "max_length", None) or 20
        value = "t"
        if getattr(field, "unique", False):
            # Un champ unique= sans défaut a besoin d'une valeur distincte à
            # chaque appel (plusieurs sociétés/tests dans la même suite).
            value = _next_unique_suffix()
        return value[:max_len] if max_len else value
    if isinstance(field, m.EmailField):
        if getattr(field, "unique", False):
            return f"{_next_unique_suffix()}@example.com"
        return "yrbac12@example.com"
    if isinstance(field, (m.IntegerField, m.PositiveIntegerField,
                          m.PositiveSmallIntegerField, m.SmallIntegerField,
                          m.BigIntegerField)):
        return 0
    if isinstance(field, m.DecimalField):
        return Decimal("0")
    if isinstance(field, m.FloatField):
        return 0.0
    if isinstance(field, m.DateTimeField):
        from django.utils import timezone
        return timezone.now()
    if isinstance(field, m.DateField):
        return datetime.date.today()
    if isinstance(field, m.DurationField):
        return datetime.timedelta()
    if isinstance(field, (m.JSONField,)):
        return {}
    if isinstance(field, (m.UUIDField,)):
        import uuid
        return uuid.uuid4()
    raise SkipModel(f"type de champ non géré : {type(field).__name__}")


def _is_required(field) -> bool:
    """True si le champ DOIT recevoir une valeur explicite à la création."""
    if getattr(field, "auto_created", False):
        return False
    if getattr(field, "primary_key", False):
        return False
    if getattr(field, "has_default", lambda: False)():
        return False
    if getattr(field, "null", False) or getattr(field, "blank", False):
        # blank=True seul n'exempte pas un CharField non-null en base, mais
        # dans la quasi-totalité de ce repo blank=True s'accompagne d'un
        # default='' explicite (convention constante) — traiter blank=True
        # comme "a une valeur par défaut effective" est donc sûr ici et évite
        # des faux-positifs de dette.
        return False
    if field.__class__.__name__ in ("AutoField", "BigAutoField"):
        return False
    return True


def build_minimal_instance(model, company):
    """Crée et renvoie une instance MINIMALE de ``model`` dans ``company``.

    Pose ``company`` explicitement (jamais déduite), puis pour chaque AUTRE
    champ obligatoire (cf. ``_is_required``) : une FK obligatoire vers un
    modèle FOUNDATION connu (``_KNOWN_SIMPLE_RELATED``) est construite
    récursivement ; toute FK vers un AUTRE modèle, ou tout type de champ non
    géré, lève ``SkipModel`` — ce modèle devient de la dette EXPLICITE listée
    par le test appelant (jamais un skip silencieux).
    """
    from django.db import models as m

    if not hasattr(model, "_meta"):
        raise SkipModel("pas un modèle Django")

    field_names = {f.name for f in model._meta.get_fields()}
    if "company" not in field_names:
        raise SkipModel("pas de champ company (hors périmètre multi-tenant)")

    kwargs = {"company": company}
    for field in model._meta.get_fields():
        if field.name == "company":
            continue
        if not hasattr(field, "attname"):
            continue  # relation inverse, pas un champ concret local
        if not _is_required(field):
            continue
        if isinstance(field, m.ForeignKey):
            related = field.related_model
            if related.__name__ not in _KNOWN_SIMPLE_RELATED:
                raise SkipModel(
                    f"FK obligatoire non triviale : {field.name} -> "
                    f"{related.__name__}")
            kwargs[field.name] = _build_known_related(related, company)
            continue
        if isinstance(field, m.ManyToManyField):
            # M2M obligatoire (rare) : pas géré par cette factory minimale.
            raise SkipModel(f"ManyToMany obligatoire : {field.name}")
        kwargs[field.name] = _synthetic_scalar(field)

    return model.objects.create(**kwargs)


# ── CRX17 — CRÉATION avec une relation vers une AUTRE société ───────────────
#
# Le balai ne testait que list/retrieve/patch/delete d'un objet EXISTANT du
# voisin. Le chemin réellement exploité par un client malveillant est l'autre :
# créer un objet DANS SA société mais l'ACCROCHER à une ligne du voisin (un
# lead, un client, une liste de prix…). Ce cas n'était couvert nulle part —
# l'audit CRM du 02/09 y a trouvé 13 relations nues d'un coup.


def _model_has_company(model) -> bool:
    try:
        return any(f.name == "company" for f in model._meta.get_fields())
    except Exception:  # noqa: BLE001 — modèle exotique : hors périmètre
        return False


def _synthetic_serializer_value(field, field_name):
    """Valeur triviale pour un champ de SÉRIALISEUR obligatoire (non relation).

    Volontairement plus étroite que ``_synthetic_scalar`` (champs de MODÈLE) :
    tout ce qui n'est pas trivialement synthétisable lève ``SkipModel`` — le
    viewset devient de la dette EXPLICITE listée par le test, jamais un cas
    faussement « vérifié » avec un corps bancal.
    """
    from rest_framework import serializers as drf

    # ChoiceField AVANT CharField (ChoiceField n'en dérive pas, mais les
    # sous-classes typées — Email/Slug/URL — en dérivent : ordre du plus
    # spécifique au plus général).
    if isinstance(field, drf.MultipleChoiceField):
        raise SkipModel(f"champ non synthétisable : {field_name}")
    if isinstance(field, drf.ChoiceField):
        choices = [key for key in field.choices]
        if not choices:
            raise SkipModel(f"choix vide : {field_name}")
        return choices[0]
    if isinstance(field, drf.BooleanField):
        return False
    if isinstance(field, drf.EmailField):
        return f"{_next_unique_suffix()}@example.com"
    if isinstance(field, drf.UUIDField):
        import uuid
        return str(uuid.uuid4())
    if isinstance(field, drf.URLField):
        return "https://example.com/"
    if isinstance(field, (drf.SlugField, drf.CharField)):
        max_len = getattr(field, "max_length", None)
        value = _next_unique_suffix()
        return value[:max_len] if max_len else value
    if isinstance(field, drf.IntegerField):
        return 1
    if isinstance(field, (drf.DecimalField, drf.FloatField)):
        return "1"
    if isinstance(field, drf.DateTimeField):
        from django.utils import timezone
        return timezone.now().isoformat()
    if isinstance(field, drf.DateField):
        return datetime.date.today().isoformat()
    if isinstance(field, drf.DurationField):
        return "00:00:00"
    if isinstance(field, drf.JSONField):
        return {}
    if isinstance(field, drf.ListField):
        return []
    raise SkipModel(
        f"champ obligatoire non synthétisable : {field_name} "
        f"({type(field).__name__})")


def build_foreign_relation_payload(view_class, company):
    """Corps de CRÉATION dont ≥1 relation pointe une ligne de ``company``.

    ``company`` est la société ÉTRANGÈRE (celle du voisin). Renvoie
    ``(payload, noms_des_relations_etrangeres)``. Lève ``SkipModel`` dès qu'un
    champ obligatoire n'est pas synthétisable ou qu'aucune relation
    company-scopée inscriptible n'existe — dette explicite, jamais un test
    faussement vert.
    """
    from rest_framework import serializers as drf

    serializer_class = getattr(view_class, "serializer_class", None)
    if serializer_class is None:
        raise SkipModel("pas de serializer_class de classe")
    try:
        fields = serializer_class().fields
    except Exception as exc:  # noqa: BLE001 — dette explicite, pas un crash
        raise SkipModel(f"sérialiseur non instanciable : {exc}")

    payload = {}
    etrangeres = []
    for name, field in fields.items():
        if field.read_only or isinstance(field, drf.HiddenField):
            continue
        relation = getattr(field, "child_relation", None) or field
        many = relation is not field
        if isinstance(relation, drf.PrimaryKeyRelatedField):
            queryset = getattr(relation, "queryset", None)
            if queryset is None or not _model_has_company(queryset.model):
                if field.required:
                    raise SkipModel(
                        f"relation obligatoire hors périmètre : {name}")
                continue
            cible = build_minimal_instance(queryset.model, company)
            payload[name] = [cible.pk] if many else cible.pk
            etrangeres.append(name)
            continue
        if isinstance(relation, drf.RelatedField):
            # Slug/Hyperlink/StringRelated : la valeur attendue n'est pas un pk,
            # on ne devine pas — dette explicite si le champ est obligatoire.
            if field.required:
                raise SkipModel(f"relation non-PK obligatoire : {name}")
            continue
        if isinstance(field, drf.BaseSerializer):
            if field.required:
                raise SkipModel(f"sérialiseur imbriqué obligatoire : {name}")
            continue
        if not field.required:
            continue
        payload[name] = _synthetic_serializer_value(field, name)

    if not etrangeres:
        raise SkipModel("aucune relation company-scopée inscriptible")
    return payload, etrangeres


def detail_get_actions(view_class, limit=3) -> list[str]:
    """``url_path`` des ``@action(detail=True)`` acceptant GET (≤ ``limit``).

    Bornée volontairement : le balai tourne sur des centaines de viewsets, on
    veut une COUVERTURE DE BASE de la surface @action, pas un test exhaustif
    qui multiplierait par dix la durée de la suite.
    """
    try:
        extra = view_class.get_extra_actions()
    except Exception:  # noqa: BLE001 — vue exotique : aucune action exercée
        return []
    chemins = []
    for action in extra:
        if not getattr(action, "detail", False):
            continue
        mapping = getattr(action, "mapping", None) or {}
        try:
            methodes = set(mapping)
        except TypeError:
            continue
        if "get" not in methodes:
            continue
        url_path = getattr(action, "url_path", None)
        if not url_path or "<" in url_path or "(" in url_path:
            continue  # action paramétrée : pas d'URL synthétisable
        chemins.append(url_path)
        if len(chemins) >= limit:
            break
    return chemins


# ── NTPLT8 — Scan d'ÉTANCHÉITÉ des DONNÉES vivantes (DRY-RUN mensuel) ────────
#
# YRBAC12 (ci-dessus) teste le CODE en CI. NTPLT8 contrôle les DONNÉES en prod :
# une tâche beat mensuelle DRY-RUN vérifie qu'aucune ligne des grosses tables
# company-scopées n'a un ``company_id`` NULL ou ORPHELIN (société supprimée). Le
# rapport est remonté aux admins + journalisé en audit via un REPORTEUR
# enregistré (core ne peut importer ni notifications ni audit — pattern hook,
# comme core.retention / core.limits).

import logging as _logging  # noqa: E402 — proche de son unique usage (scan)

_logger = _logging.getLogger(__name__)

# Reporteur enregistré : callable(report: dict) -> None. Peuplé par les apps
# notifications/audit dans leur ``ready()`` ; ``None`` = simple log.
_SCAN_REPORTER = None

# Plafond de comptage par table (borne le scan — on veut savoir « y a-t-il des
# anomalies », pas un décompte exact sur des dizaines de millions de lignes).
_ANOMALY_MAX = 10_000


def register_scan_reporter(fn) -> None:
    """Enregistre le reporteur d'anomalies d'étanchéité (idempotent : remplace).

    ``fn(report)`` reçoit le rapport (``dict``) et est responsable de notifier
    les admins + écrire l'entrée d'audit. ``core`` ne connaît que ce callable."""
    global _SCAN_REPORTER
    _SCAN_REPORTER = fn


def clear_scan_reporter() -> None:
    """Retire le reporteur (test uniquement)."""
    global _SCAN_REPORTER
    _SCAN_REPORTER = None


def _count_bounded(cursor, sql, params) -> int:
    """COUNT borné (≤ _ANOMALY_MAX) d'une sous-requête d'anomalie."""
    cursor.execute(sql, params)
    row = cursor.fetchone()
    return int(row[0]) if row else 0


def scan_live_isolation() -> dict:
    """Balaye les tables company-scopées à la recherche de lignes NULL/orphelin.

    Pour chaque table découverte (``core.rls.discover_company_scoped_tables``) :
      * ``null`` — nombre de lignes avec ``company_id`` NULL (borné) ;
      * ``orphan`` — nombre de lignes dont ``company_id`` ne pointe plus une
        société existante (société supprimée), borné.

    DRY-RUN pur : ne modifie RIEN. Renvoie un rapport
    ``{'tables': [...], 'anomalies': int, 'scanned': int}`` et, si des anomalies
    existent, appelle le reporteur enregistré (best-effort). Une table qui
    échoue au scan ne bloque pas les autres.
    """
    from django.db import connection
    from . import rls

    tables = []
    total_anomalies = 0
    scanned = 0
    with connection.cursor() as cursor:
        for entry in rls.discover_company_scoped_tables():
            col = entry.company_column
            try:
                null_count = _count_bounded(
                    cursor,
                    f'SELECT COUNT(*) FROM (SELECT 1 FROM "{entry.table}" '
                    f'WHERE "{col}" IS NULL LIMIT {_ANOMALY_MAX}) s', [])
                orphan_count = _count_bounded(
                    cursor,
                    f'SELECT COUNT(*) FROM (SELECT 1 FROM "{entry.table}" t '
                    f'WHERE t."{col}" IS NOT NULL AND NOT EXISTS ('
                    f'SELECT 1 FROM "authentication_company" c '
                    f'WHERE c.id = t."{col}") LIMIT {_ANOMALY_MAX}) s', [])
            except Exception:  # noqa: BLE001 — table KO ne bloque pas le reste
                _logger.warning('scan_live_isolation: échec sur %s',
                                entry.table)
                continue
            scanned += 1
            if null_count or orphan_count:
                total_anomalies += null_count + orphan_count
                tables.append({
                    'table': entry.table, 'label': entry.label,
                    'null': null_count, 'orphan': orphan_count,
                })

    report = {
        'tables': tables, 'anomalies': total_anomalies, 'scanned': scanned,
    }
    if total_anomalies:
        _report_anomalies(report)
    return report


def _report_anomalies(report: dict) -> None:
    """Remonte le rapport d'anomalies (reporteur enregistré, sinon log)."""
    if _SCAN_REPORTER is None:
        _logger.warning('scan_live_isolation: %d anomalie(s) sur %d table(s) '
                        '(aucun reporteur enregistré)',
                        report['anomalies'], len(report['tables']))
        return
    try:
        _SCAN_REPORTER(report)
    except Exception:  # noqa: BLE001 — un reporteur KO ne casse pas le scan
        _logger.exception('scan_live_isolation: reporteur en échec')
