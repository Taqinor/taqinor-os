"""Mixins de sérialiseur réutilisables (fondation ``core``).

YRBAC7 — ``SensitiveFieldMaskMixin``
------------------------------------

Généralise le masquage champ-sensible aujourd'hui codé cas par cas (stock/crm/
rh). Un sérialiseur déclare ``sensitive_fields = {'prix_achat': 'prix_achat_voir',
'marge_pct': 'marge_voir'}`` et le mixin RETIRE (pas met à ``null``) chaque champ
quand l'utilisateur de la requête n'a pas la permission associée. L'utilisateur
est lu depuis le ``context['request']`` — JAMAIS depuis le body.

Comportement de repli conservé (comme ``HasPermissionOrLegacy`` /
``can_view_buy_prices``) : un compte SANS rôle fin (légacy) garde l'accès
historique et n'est donc PAS masqué. Le superuser voit tout.

YRBAC8 — ``ServerControlledFieldsMixin``
----------------------------------------

Garde anti-mass-assignment : retire du body entrant les champs de gouvernance
(``company``, ``created_by``, ``is_*``, ``role``…) avant validation, pour qu'un
client ne puisse jamais forcer la société, le propriétaire ou un flag privilège.

``core`` reste FONDATION : ces mixins ne dépendent d'aucune app métier.
"""
from __future__ import annotations


def _user_may_see(user, permission_code) -> bool:
    """Vrai si ``user`` peut voir un champ gardé par ``permission_code``.

    * pas d'utilisateur / non authentifié → masqué (False) ;
    * superuser → True ;
    * compte SANS rôle fin (``role`` absent) → repli historique True (on ne
      retire jamais un accès existant à un compte légacy) ;
    * sinon → l'utilisateur doit porter la permission ERP ``permission_code``.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    if getattr(user, "role_id", None) is None and getattr(user, "role", None) is None:
        return True  # compte légacy sans rôle fin → comportement historique
    checker = getattr(user, "has_erp_permission", None)
    if callable(checker):
        return bool(checker(permission_code))
    return False


class SensitiveFieldMaskMixin:
    """Retire du payload les champs sensibles non autorisés (YRBAC7).

    Déclarez ``sensitive_fields`` = ``{nom_champ: codename_permission}`` sur le
    sérialiseur. À la sérialisation, tout champ dont l'utilisateur de la requête
    n'a pas la permission est ABSENT de la représentation (pas ``None``).

    Le mixin surcharge ``to_representation`` : il ne modifie jamais l'instance
    ni la base, seulement la sortie. Sans ``context['request']`` (ex. rendu
    interne/serveur), rien n'est masqué (comportement inchangé).
    """

    sensitive_fields: dict = {}

    def _request_user(self):
        request = self.context.get("request") if hasattr(self, "context") else None
        return getattr(request, "user", None) if request is not None else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self.sensitive_fields:
            return data
        user = self._request_user()
        if user is None:
            # Pas de requête (rendu serveur/interne) → ne rien masquer.
            return data
        for field_name, permission_code in self.sensitive_fields.items():
            if field_name in data and not _user_may_see(user, permission_code):
                data.pop(field_name, None)
        return data


# ─────────────────────────────────────────────────────────────────────────────
# YRBAC8 — Champs pilotés serveur : jamais posés par le body
# ─────────────────────────────────────────────────────────────────────────────

# Champs de gouvernance qu'un client ne doit JAMAIS pouvoir poser via le body
# d'un POST/PATCH : ils sont toujours dérivés côté serveur. Un sérialiseur peut
# étendre cette liste via ``server_controlled_fields``.
DEFAULT_SERVER_CONTROLLED_FIELDS = frozenset({
    "company",
    "company_id",
    "created_by",
    "created_by_id",
    "updated_by",
    "owner",
    "role",
    "role_id",
    "is_staff",
    "is_superuser",
    "is_active",
})


# ─────────────────────────────────────────────────────────────────────────────
# NTDMO9 — Masquage PII en MODE PRÉSENTATION (démo devant prospect)
# ─────────────────────────────────────────────────────────────────────────────

# Valeurs de remplacement par champ masqué (adresse exacte, email, téléphone).
# La ville n'est JAMAIS dans cette liste : elle reste visible (« garder ville,
# masquer le reste »).
_PRESENTATION_MASKS = {
    'email': '***@***',
    'telephone': '06 ** ** ** **',
    'adresse': '••• (masqué en mode présentation)',
}


def _company_masks_pii(user) -> bool:
    """Vrai si la société de ``user`` masque les PII en mode présentation.

    Double garde (défense en profondeur, NTDMO9) : le masquage n'est actif que
    si la société est BIEN une société de DÉMONSTRATION (``est_demo``) ET que le
    ``mode_presentation_actif`` est vrai. Une société RÉELLE dont le drapeau
    serait manipulé n'est JAMAIS masquée. Sans utilisateur/société → jamais
    masqué (rendu serveur interne, comportement inchangé)."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    company = getattr(user, 'company', None)
    if company is None:
        return False
    return bool(getattr(company, 'est_demo', False)) and bool(
        getattr(company, 'mode_presentation_actif', False))


class SerializerMaskMixin:
    """Masque les PII (email/téléphone/adresse exacte) en LECTURE quand la
    société courante est en mode présentation (NTDMO9).

    À poser sur les sérialiseurs de LECTURE ``Client``/``Lead`` du CRM/ventes.
    Le masquage :

    * n'a lieu QUE si ``request.user.company.est_demo`` ET
      ``mode_presentation_actif`` sont vrais (double garde) → une société où le
      drapeau reste False se comporte de façon BYTE-IDENTIQUE (non-régression
      totale), et une société RÉELLE n'est jamais affectée même si le drapeau
      est manipulé ;
    * est en LECTURE SEULE (``to_representation``) — il ne modifie jamais
      l'instance ni la base, et ne touche donc JAMAIS l'écriture ni les
      documents officiels (factures / PDF ``/proposal``, règle #4) ;
    * garde la ``ville`` (jamais masquée) et ne masque que les champs listés
      dans ``presentation_mask_fields``.

    Sans ``context['request']`` (rendu serveur/interne) rien n'est masqué.
    """

    # Champs masqués en mode présentation (la ``ville`` en est volontairement
    # absente). Un sérialiseur peut restreindre/étendre cette liste.
    presentation_mask_fields = ('email', 'telephone', 'adresse')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request') if hasattr(self, 'context') \
            else None
        user = getattr(request, 'user', None) if request is not None else None
        if not _company_masks_pii(user):
            return data
        for field_name in self.presentation_mask_fields:
            if field_name in data and data.get(field_name):
                data[field_name] = _PRESENTATION_MASKS.get(
                    field_name, '***')
        return data


class ServerControlledFieldsMixin:
    """Ignore les champs de gouvernance présents dans le body (YRBAC8).

    Anti-mass-assignment transversal : avant validation, retire du payload
    entrant tout champ de ``DEFAULT_SERVER_CONTROLLED_FIELDS`` (étendu par
    ``server_controlled_fields`` sur le sérialiseur). La valeur de ces champs
    vient TOUJOURS du serveur (``perform_create``/``TenantMixin``/défaut modèle),
    jamais du client — injecter ``company=<autre>`` ou ``is_superuser=true`` dans
    un POST/PATCH est simplement ignoré.

    ``core`` reste FONDATION : aucune dépendance app métier.
    """

    server_controlled_fields: frozenset = frozenset()

    def _server_controlled(self) -> frozenset:
        return DEFAULT_SERVER_CONTROLLED_FIELDS | frozenset(
            self.server_controlled_fields)

    def to_internal_value(self, data):
        blocked = self._server_controlled()
        if hasattr(data, "keys") and any(k in blocked for k in list(data.keys())):
            # Copie mutable (QueryDict est immuable) puis purge les champs.
            try:
                data = data.copy()
            except AttributeError:
                data = dict(data)
            if hasattr(data, "_mutable"):
                data._mutable = True
            for key in list(data.keys()):
                if key in blocked:
                    data.pop(key, None)
        return super().to_internal_value(data)


def _chaine_nullable(modele, source) -> bool:
    """Vrai si le chemin pointé (``a.b.c``) traverse, depuis ``modele``, au moins
    une colonne/relation ``null=True`` (le champ lecture seule vaut alors
    ``None``). Chemin non résoluble (propriété, méthode) ou relation inverse
    (``photos.count``) → False : on ne rend jamais nullable ce qui ne l'est pas."""
    courant = modele
    for partie in source.split("."):
        if courant is None:
            return False
        try:
            champ = courant._meta.get_field(partie)
        except Exception:  # noqa: BLE001 - propriété / méthode : non résoluble
            return False
        if not getattr(champ, "concrete", False):
            return False
        if champ.null:
            return True
        courant = champ.related_model if champ.is_relation else None
    return False


class NullableDottedSourcesMixin:
    """ENF11 — un champ lecture seule à ``source='fk.attribut'`` vaut ``None``
    (et non « absent ») quand la clé ou la colonne traversée est nullable : le
    schéma OpenAPI doit le dire (``allow_null``), sinon la réponse conforme du
    serveur « viole » son propre schéma. N'agit que sur les chemins dont le
    modèle prouve la nullabilité ; ``to_representation`` est inchangé.

    ``core`` reste FONDATION : aucune dépendance app métier.
    """

    def get_fields(self):
        champs = super().get_fields()
        modele = getattr(getattr(self, "Meta", None), "model", None)
        if modele is None:
            return champs
        for champ in champs.values():
            source = getattr(champ, "source", None)
            if (champ.read_only and not champ.allow_null and source
                    and "." in source and source != "*"
                    and _chaine_nullable(modele, source)):
                champ.allow_null = True
        return champs
