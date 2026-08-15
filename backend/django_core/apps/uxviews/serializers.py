from typing import Optional

from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from .models import FavoriUtilisateur, SavedView, UxParametres


class SavedViewSerializer(serializers.ModelSerializer):
    owner_nom = serializers.SerializerMethodField()
    # NTUX2 — le frontend ne connaît le rôle courant que par son NOM
    # (`state.auth.role_nom`, cf. authSlice.js — aucun id numérique de
    # `roles.Role` n'est exposé côté client) : on dénormalise le nom ici pour
    # que l'écran puisse matcher « ma vue par défaut de rôle » sans requête
    # supplémentaire.
    role_nom = serializers.SerializerMethodField()

    class Meta:
        model = SavedView
        fields = [
            'id', 'ecran', 'nom', 'configuration', 'visibilite',
            'est_defaut_role', 'role', 'role_nom', 'owner', 'owner_nom',
            'created_at', 'updated_at',
        ]
        # `owner`/`company`/`est_defaut_role` sont posés côté serveur — jamais
        # depuis le corps de requête (CLAUDE.md — multi-tenant, jamais accepté
        # côté client). `est_defaut_role` ne bascule QUE via l'action dédiée
        # `definir-par-defaut-role` (garde-fou Directeur/Admin + un seul défaut
        # actif par rôle+écran).
        read_only_fields = ['id', 'owner', 'est_defaut_role', 'created_at', 'updated_at']

    def get_owner_nom(self, obj):
        owner = obj.owner
        if not owner:
            return None
        full = f'{getattr(owner, "first_name", "")} {getattr(owner, "last_name", "")}'.strip()
        return full or getattr(owner, 'username', None) or getattr(owner, 'email', None)

    def get_role_nom(self, obj):
        return obj.role.nom if obj.role_id else None


class FavoriUtilisateurSerializer(serializers.ModelSerializer):
    """NTUX12 — un favori épinglé.

    La cible est exprimée par `modele` (`'<app_label>.<model>'`, ex.
    `'installations.installation'`) + `object_id`, JAMAIS par l'identifiant
    numérique de `ContentType` : celui-ci n'est pas stable d'un environnement à
    l'autre et le frontend ne le connaît pas (c'est aussi la clé sur laquelle
    l'import de NTUX35 résoudra ses lignes).
    """

    # Écriture seule : la valeur de LECTURE est réinjectée par
    # `to_representation` depuis `cle_modele` (le modèle ne porte pas d'attribut
    # `modele`, c'est `content_type` qui est écrit en base).
    modele = serializers.CharField(
        write_only=True, help_text="Modèle cible, ex. « crm.lead ».")
    # Libellé résolu à la lecture depuis la cible (jamais stocké) ; `None` si la
    # cible a été supprimée entre-temps — l'écran affiche alors un favori mort
    # plutôt que de mentir (le nettoyage est NTUX30).
    libelle = serializers.SerializerMethodField()

    class Meta:
        model = FavoriUtilisateur
        fields = ['id', 'modele', 'object_id', 'libelle', 'ordre',
                  'owner', 'created_at', 'updated_at']
        # `owner`/`company` sont posés côté serveur — jamais depuis le corps.
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at']

    def get_libelle(self, obj) -> Optional[str]:
        cible = obj.cible
        return str(cible) if cible is not None else None

    def validate_modele(self, value):
        try:
            app_label, model = str(value).strip().lower().split('.')
        except ValueError:
            raise serializers.ValidationError(
                "Format attendu « app.modele », ex. « crm.lead ».")
        content_type = ContentType.objects.filter(
            app_label=app_label, model=model).first()
        if content_type is None:
            raise serializers.ValidationError(f'Modèle inconnu : « {value} ».')
        # Mémorisé pour `create`/`update` (le champ `modele` n'existe pas sur le
        # modèle : c'est `content_type` qui est écrit).
        self._content_type = content_type
        return f'{app_label}.{model}'

    def _appliquer_content_type(self, validated_data):
        validated_data.pop('modele', None)
        content_type = getattr(self, '_content_type', None)
        if content_type is not None:
            validated_data['content_type'] = content_type
        return validated_data

    def create(self, validated_data):
        validated_data = self._appliquer_content_type(validated_data)
        # Épingler deux fois le même enregistrement est un NO-OP (on renvoie le
        # favori existant), jamais une 500 sur la contrainte d'unicité.
        existant = FavoriUtilisateur.objects.filter(
            company=validated_data.get('company'),
            owner=validated_data.get('owner'),
            content_type=validated_data.get('content_type'),
            object_id=validated_data.get('object_id'),
        ).first()
        if existant is not None:
            return existant
        return super().create(validated_data)

    def update(self, instance, validated_data):
        return super().update(instance, self._appliquer_content_type(validated_data))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['modele'] = instance.cle_modele
        return data


class UxParametresSerializer(serializers.ModelSerializer):
    """NTUX27 — réglages UX de la société.

    `company` n'est JAMAIS lue du corps : la vue résout les réglages depuis
    `request.user.company`.
    """

    class Meta:
        model = UxParametres
        fields = [
            'id', 'duree_hover_peek_ms', 'duree_undo_toast_s',
            'permettre_vues_partagees_equipe', 'roles_autorises_definir_defaut',
            'max_vues_par_utilisateur', 'max_favoris_par_utilisateur',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_roles_autorises_definir_defaut(self, value):
        """Un rôle d'une AUTRE société n'a rien à faire ici (les ids de rôle
        sont devinables — sans ce garde, on ouvrirait une référence croisée)."""
        company = self.context.get('company')
        if company is not None:
            etrangers = [role for role in value if role.company_id != company.id]
            if etrangers:
                raise serializers.ValidationError(
                    "Un rôle d'une autre société ne peut pas être autorisé.")
        return value
