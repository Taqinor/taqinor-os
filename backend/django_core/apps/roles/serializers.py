import re

from rest_framework import serializers

from core.champs_stricts import ChampsStrictsMixin

from .models import Role
from .permissions_registre import (
    ALL_PERMISSIONS,
    ELEVATED_PERMISSIONS,
    codes_non_octroyables,
)
from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from drf_spectacular.utils import extend_schema_field, inline_serializer

#: CI #1000 — UN SEUL prédicat pour un code de permission de rôle : le schéma
#: publie ce motif et ``CodePermission`` l'applique (``fullmatch``). Le schéma
#: ne disait que « chaîne » alors que le serveur refusait tout code hors
#: catalogue (``"00"`` « conforme » → 400). Catalogue ``ALL_PERMISSIONS`` OU
#: famille ODY26 « app visible » (``permissions_registre.EST_PERMISSION_APP``).
MOTIF_CODE_PERMISSION = '^(?:%s|app_[a-z0-9][a-z0-9_]*_voir)$' % '|'.join(
    re.escape(code) for code in ALL_PERMISSIONS)
_RE_CODE_PERMISSION = re.compile(MOTIF_CODE_PERMISSION)


class CodePermission(serializers.CharField):
    """Code de permission d'un rôle (catalogue ou « app visible »). Pas de
    rognage : un code à blancs de bord est HORS motif, pas corrigé.

    CI #1000 (2) — le motif ne vaut que pour l'ÉCRITURE : un rôle stocké porte
    aussi des codes hérités (``portail_client_acces``, variantes ``app_*``,
    codes semés) que le serveur LIT sans les refuser. La RÉPONSE est donc une
    chaîne libre (``_CodePermission``) ; seule la requête publie le motif."""

    def __init__(self, **kwargs):
        kwargs.setdefault('trim_whitespace', False)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        # Vraie chaîne JSON seulement (jamais ``0`` -> ``"0"``), comme
        # ``ChaineStricte`` — dont l'extension de schéma générique (motif sans
        # nul) primerait sur ``_CodePermission`` : d'où la base ``CharField``.
        if not isinstance(data, str):
            self.fail('invalid')
        valeur = super().to_internal_value(data)
        if not _RE_CODE_PERMISSION.fullmatch(valeur):
            self.fail('invalid')
        return valeur


class _CodePermission(OpenApiSerializerFieldExtension):
    target_class = 'apps.roles.serializers.CodePermission'

    def map_serializer_field(self, auto_schema, direction):
        if direction == 'request':
            return {'type': 'string', 'pattern': MOTIF_CODE_PERMISSION}
        return {'type': 'string'}


class RoleSerializer(ChampsStrictsMixin, serializers.ModelSerializer):
    # ENF11 — liste de codes TEXTE déclarée au schéma : `null`, un objet ou un
    # code non texte répondent 400 (le JSONField du modèle acceptait tout).
    permissions = serializers.ListField(child=CodePermission(), required=False)
    users_count = serializers.SerializerMethodField()
    # Liste légère des utilisateurs portant ce rôle (id + nom d'affichage), pour
    # l'expansion « Utilisateurs » dans l'éditeur de rôles (Feature RBAC).
    users = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ('id', 'nom', 'permissions', 'est_systeme',
                  'users_count', 'users', 'entites_visibles', 'perimetre')
        read_only_fields = ('id', 'est_systeme', 'users_count', 'users')
        extra_kwargs = {
            'entites_visibles': {'required': False},
            'perimetre': {'required': False},
        }

    def to_internal_value(self, data):
        # ENF11 (api-fuzz) — DRF itère n'importe quel objet pour une relation
        # multiple : `{}` valait « liste vide » (= rôle sans restriction
        # d'entités). Le schéma dit « liste d'identifiants » : tout autre type
        # JSON répond 400.
        if hasattr(data, 'get') and 'entites_visibles' in data and (
                not isinstance(data['entites_visibles'], (list, tuple))):
            raise serializers.ValidationError(
                {'entites_visibles': 'Liste d’identifiants attendue.'})
        return super().to_internal_value(data)

    @extend_schema_field(serializers.IntegerField())
    def get_users_count(self, obj):
        return obj.users.count()

    @extend_schema_field(inline_serializer('RoleUtilisateur', {
        'id': serializers.IntegerField(),
        'username': serializers.CharField()}, many=True))
    def get_users(self, obj):
        return [
            {'id': u.id, 'username': u.username}
            for u in obj.users.all()
        ]

    def _request_user(self):
        request = self.context.get('request')
        return getattr(request, 'user', None)

    def validate_permissions(self, value):
        # ODY26 — les codes « app visible » (``app_<clé>_voir``) sont acceptés
        # PAR FORME et non par énumération : les lister dans ALL_PERMISSIONS
        # les injecterait dans DIRECTEUR/ADMIN_PERMISSIONS (qui en dérivent) et
        # y figer la liste d'apps du jour ; les énumérer ici recréerait un 2ᵉ
        # registre d'apps côté backend, interdit par le Groupe ODY (registre
        # unique = ``moduleConfigs`` côté front). Aucun risque d'escalade : ces
        # codes ne donnent AUCUN droit, ils RESTREIGNENT ce que le rôle voit.
        # Les codes inconnus sont déjà refusés par ``CodePermission`` ; ce
        # contrôle (même motif, ``_RE_CODE_PERMISSION``) garde la méthode sûre
        # quand on l'appelle seule.
        invalid = [p for p in value if not _RE_CODE_PERMISSION.fullmatch(p)]
        if invalid:
            raise serializers.ValidationError(
                f"Permissions invalides : {invalid}"
            )
        # ── Anti-escalade (ERR5) ──────────────────────────────────────────
        # Seul un administrateur (porteur de ``roles_gerer``, ou superuser)
        # peut octroyer une permission ÉLEVÉE (roles_gerer / prix_achat_voir /
        # journal_activite_voir / marge_voir / cout_non_qualite_voir /
        # ao_rentabilite_voir — AOF2, l'économie d'un appel d'offres).
        # On bloque l'AJOUT d'une telle permission par
        # un non-admin : sans cela, un Responsable coche ``roles_gerer`` sur son
        # rôle et s'auto-promeut Administrateur. On compare aux permissions
        # déjà posées (PATCH partiel : on ne pénalise pas un rôle qui les avait
        # déjà), pour ne bloquer que les permissions AJOUTÉES.
        user = self._request_user()
        if user is not None and not getattr(user, 'is_admin_role', False):
            existing = set(self.instance.permissions or []) if self.instance \
                else set()
            added_elevated = (set(value) & ELEVATED_PERMISSIONS) - existing
            if added_elevated:
                raise serializers.ValidationError(
                    "Seul un administrateur peut octroyer ces permissions "
                    f"élevées : {sorted(added_elevated)}."
                )
            # ASEC10 — symétrique : un non-administrateur ne RETIRE pas
            # ``roles_gerer`` ni un code élevé d'un rôle (rétrograder un rôle
            # admin personnalisé = dégrader les administrateurs qui le portent).
            removed_elevated = (existing & ELEVATED_PERMISSIONS) - set(value)
            if removed_elevated:
                raise serializers.ValidationError(
                    "Seul un administrateur peut retirer ces permissions "
                    f"élevées : {sorted(removed_elevated)}."
                )
        return value

    def validate(self, attrs):
        # ── Garde des rôles système (ERR5) ────────────────────────────────
        # Un non-administrateur ne peut PAS modifier les permissions (ni
        # renommer) un rôle système (``est_systeme=True``) — Administrateur,
        # Directeur, etc. Sans cela un Responsable édite le rôle système qui le
        # porte (ou un autre) pour s'octroyer des droits.
        user = self._request_user()
        if self.instance is not None and self.instance.est_systeme \
                and user is not None \
                and not getattr(user, 'is_admin_role', False):
            touches_perms = 'permissions' in attrs and \
                sorted(attrs['permissions'] or []) != \
                sorted(self.instance.permissions or [])
            touches_nom = 'nom' in attrs and \
                attrs['nom'] != self.instance.nom
            if touches_perms or touches_nom:
                raise serializers.ValidationError(
                    "Seul un administrateur peut modifier un rôle système."
                )
        # ── ASEC9 / D-ASEC-1 — codes non octroyables à certains rôles système
        # (ex. ``encaisser`` jamais à Commercial terrain / Technicien /
        # Technicien responsable / Admin RH), même par un administrateur.
        if self.instance is not None and self.instance.est_systeme \
                and 'permissions' in attrs:
            interdits = codes_non_octroyables(
                attrs.get('nom', self.instance.nom), attrs['permissions'])
            if interdits:
                raise serializers.ValidationError({
                    'permissions': [
                        f"Code non octroyable à ce rôle : {interdits}."],
                })
        return attrs

    def validate_entites_visibles(self, value):
        """NTADM3 — le périmètre ne peut porter que des entités de LA société
        de l'acteur.

        ``ModelSerializer`` dérive un ``PrimaryKeyRelatedField`` sur TOUTES
        les entités : sans ce contrôle, un id d'une AUTRE société serait
        accepté (fuite multi-tenant). Liste vide = aucune restriction, le
        rôle voit toutes les entités (comportement historique)."""
        user = self._request_user()
        company = getattr(user, 'company', None)
        if company is None:
            return value
        etrangeres = [e.code for e in value if e.company_id != company.id]
        if etrangeres:
            raise serializers.ValidationError(
                "Ces entités n'appartiennent pas à votre entreprise : "
                f"{sorted(etrangeres)}.")
        return value

    def validate_nom(self, value):
        if not value.strip():
            raise serializers.ValidationError("Le nom ne peut pas être vide.")
        return value.strip()
