"""Sérialiseurs de la Base de connaissances.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). ``auteur`` est posé côté serveur.
"""
from rest_framework import serializers

from .models import (
    KbArticle,
    KbArticleAcl,
    KbArticleLien,
    KbArticleVersion,
    KbLecture,
    KbLectureObligatoire,
)


class KbArticleSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    auteur_nom = serializers.CharField(
        source='auteur.get_full_name', read_only=True)

    class Meta:
        model = KbArticle
        fields = [
            'id', 'titre', 'corps', 'corps_format', 'categorie', 'tags',
            'statut', 'statut_display', 'auteur', 'auteur_nom', 'parent',
            'ordre', 'visibilite', 'est_gabarit', 'date_creation',
            'date_modification',
        ]
        read_only_fields = [
            'auteur', 'date_creation', 'date_modification']

    def validate_parent(self, parent):
        """XKB8 — le parent doit être même-société et ne jamais créer de cycle.

        Un cycle survient si ``parent`` est l'article courant lui-même, ou si
        l'article courant figure dans la chaîne d'ancêtres du ``parent``
        proposé (déplacer un article sous l'un de ses propres descendants).
        """
        if parent is None:
            return parent
        request = self.context.get('request')
        if request is not None and parent.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "L'article parent doit appartenir à votre société.")
        if self.instance is not None:
            if parent.id == self.instance.id:
                raise serializers.ValidationError(
                    "Un article ne peut pas être son propre parent.")
            # Remonte la chaîne d'ancêtres du parent proposé : si l'article
            # courant y figure, c'est un cycle (déplacement sous un
            # descendant). Borné pour ne jamais boucler sur des données
            # corrompues.
            cursor = parent
            for _ in range(1000):
                if cursor is None:
                    break
                if cursor.id == self.instance.id:
                    raise serializers.ValidationError(
                        "Ce déplacement créerait un cycle dans l'arborescence.")
                cursor = cursor.parent
        return parent


class KbArticleVersionSerializer(serializers.ModelSerializer):
    """Lecture seule : les versions sont des instantanés posés côté serveur."""
    auteur_nom = serializers.CharField(
        source='auteur.get_full_name', read_only=True)

    class Meta:
        model = KbArticleVersion
        fields = [
            'id', 'article', 'version', 'titre', 'contenu', 'auteur',
            'auteur_nom', 'date_creation',
        ]
        read_only_fields = fields


class KbArticleLienSerializer(serializers.ModelSerializer):
    """Lien article → objet métier d'une autre app (référence lâche typée).

    ``company`` n'est jamais exposée : elle est posée côté serveur. L'``article``
    reçu est validé comme appartenant à la société de l'utilisateur.
    """
    type_cible_display = serializers.CharField(
        source='get_type_cible_display', read_only=True)

    class Meta:
        model = KbArticleLien
        fields = [
            'id', 'article', 'type_cible', 'type_cible_display', 'cible_id',
            'libelle', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_article(self, article):
        """L'article rattaché doit appartenir à la société de l'utilisateur."""
        request = self.context.get('request')
        if request is not None and article.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Cet article n'appartient pas à votre société.")
        return article

    def validate(self, attrs):
        # XKB11 — quand la cible est un autre ARTICLE, ``cible_id`` doit
        # référencer un KbArticle EXISTANT de la MÊME société (jamais une
        # référence flottante ni cross-tenant, contrairement aux cibles
        # d'autres apps qui restent lâches par design).
        type_cible = attrs.get(
            'type_cible', getattr(self.instance, 'type_cible', None))
        cible_id = attrs.get(
            'cible_id', getattr(self.instance, 'cible_id', None))
        if type_cible == KbArticleLien.TypeCible.ARTICLE and cible_id:
            request = self.context.get('request')
            company_id = (
                request.user.company_id if request is not None else None)
            if not KbArticle.objects.filter(
                    id=cible_id, company_id=company_id).exists():
                raise serializers.ValidationError(
                    {'cible_id': "Article cible introuvable dans votre société."})
        return attrs


class KbArticleAclSerializer(serializers.ModelSerializer):
    """Droit d'accès sur un article : par-RÔLE (KB7) OU par-UTILISATEUR (XKB9).

    ``company`` n'est jamais exposée : elle est posée côté serveur. L'``article``
    reçu est validé comme appartenant à la société de l'utilisateur. Le ``role``
    est le palier canonique faisant autorité (``menu_tier``). Exactement un de
    ``role``/``utilisateur`` doit être renseigné.
    """
    role_display = serializers.CharField(
        source='get_role_display', read_only=True)
    niveau_display = serializers.CharField(
        source='get_niveau_display', read_only=True)
    utilisateur_nom = serializers.CharField(
        source='utilisateur.get_full_name', read_only=True)

    class Meta:
        model = KbArticleAcl
        fields = [
            'id', 'article', 'role', 'role_display', 'utilisateur',
            'utilisateur_nom', 'niveau', 'niveau_display', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_article(self, article):
        """L'article ciblé doit appartenir à la société de l'utilisateur."""
        request = self.context.get('request')
        if request is not None and article.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Cet article n'appartient pas à votre société.")
        return article

    def validate(self, attrs):
        role = attrs.get('role', getattr(self.instance, 'role', ''))
        utilisateur = attrs.get(
            'utilisateur', getattr(self.instance, 'utilisateur', None))
        if bool(role) == bool(utilisateur):
            raise serializers.ValidationError(
                "Renseignez soit un rôle, soit un utilisateur "
                "(jamais les deux, jamais aucun).")
        return attrs


class KbLectureSerializer(serializers.ModelSerializer):
    """Lecture d'article (lecture seule : posée côté serveur via marquer-lu)."""
    utilisateur_nom = serializers.CharField(
        source='utilisateur.get_full_name', read_only=True)

    class Meta:
        model = KbLecture
        fields = [
            'id', 'article', 'utilisateur', 'utilisateur_nom', 'lu_le',
        ]
        read_only_fields = fields


class KbLectureObligatoireSerializer(serializers.ModelSerializer):
    """XKB7 — Assignation de lecture obligatoire (article ↔ utilisateur/rôle).

    ``company`` n'est jamais exposée : posée côté serveur. L'``article`` reçu
    est validé comme appartenant à la société de l'utilisateur. Exactement un
    de ``utilisateur``/``role_cible`` doit être renseigné.
    """
    utilisateur_nom = serializers.CharField(
        source='utilisateur.get_full_name', read_only=True)

    class Meta:
        model = KbLectureObligatoire
        fields = [
            'id', 'article', 'utilisateur', 'utilisateur_nom', 'role_cible',
            'echeance', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_article(self, article):
        request = self.context.get('request')
        if request is not None and article.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Cet article n'appartient pas à votre société.")
        return article

    def validate(self, attrs):
        utilisateur = attrs.get(
            'utilisateur', getattr(self.instance, 'utilisateur', None))
        role_cible = attrs.get(
            'role_cible', getattr(self.instance, 'role_cible', ''))
        if bool(utilisateur) == bool(role_cible):
            raise serializers.ValidationError(
                "Renseignez soit un utilisateur, soit un palier de rôle "
                "(jamais les deux, jamais aucun).")
        return attrs
