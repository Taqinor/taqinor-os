"""Sérialiseurs de la Base de connaissances.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). ``auteur`` est posé côté serveur.
"""
from rest_framework import serializers

from .models import (
    BlocReutilisable,
    KbArticle,
    KbArticleAcl,
    KbArticleLien,
    KbArticleVersion,
    KbFavori,
    KbLecture,
    KbLectureObligatoire,
    KbParcours,
    KbParcoursArticle,
    KbParcoursAssignation,
    KbRechercheVide,
    PartageArticleKb,
)


class KbArticleSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    auteur_nom = serializers.CharField(
        source='auteur.get_full_name', read_only=True)

    verifie_par_nom = serializers.CharField(
        source='verifie_par.get_full_name', read_only=True)

    has_couverture = serializers.SerializerMethodField()
    proprietes_effectives = serializers.SerializerMethodField()

    class Meta:
        model = KbArticle
        fields = [
            'id', 'titre', 'corps', 'corps_format', 'categorie', 'tags',
            'statut', 'statut_display', 'auteur', 'auteur_nom', 'parent',
            'ordre', 'visibilite', 'est_gabarit', 'verifie_par',
            'verifie_par_nom', 'verifie_jusqua', 'est_verrouille', 'vues',
            'visible_portail', 'consultations_portail_ticket',
            'langue', 'traduction_de', 'traduction_perimee',
            'emoji', 'has_couverture', 'proprietes', 'proprietes_effectives',
            'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'auteur', 'verifie_par', 'verifie_jusqua', 'est_verrouille',
            'vues', 'consultations_portail_ticket', 'traduction_perimee',
            'has_couverture',
            'proprietes_effectives', 'date_creation', 'date_modification']

    def get_has_couverture(self, obj):
        """ZGED10 — expose seulement un booléen : la clé MinIO elle-même
        n'est jamais exposée telle quelle (même motif que ``authentication``
        avatars) ; l'image se récupère via l'action ``couverture``."""
        return bool(obj.couverture_file_key)

    def get_proprietes_effectives(self, obj):
        """ZGED11 — Propriétés RÉSOLUES (celles de l'article + héritées de
        ses ANCÊTRES quand l'article lui-même ne les définit pas)."""
        from . import selectors
        return selectors.proprietes_effectives(obj)

    def validate_proprietes(self, value):
        """ZGED11 — Valide contre les définitions actives du module
        ``kb_article`` de la société (réutilise `customfields`, même motif
        que GED10 pour les documents). Hors requête (écritures de service),
        laisse passer tel quel."""
        request = self.context.get('request')
        if request is None:
            return value
        from apps.customfields.serializers import validate_custom_data
        return validate_custom_data(
            'kb_article', request.user.company, value)

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

    def validate_traduction_de(self, source):
        """XKB18 — la source de traduction doit être même-société et ne
        JAMAIS être elle-même une traduction (une chaîne de traductions de
        traductions n'a pas de sens : toutes les traductions d'un même
        contenu pointent vers la MÊME source racine)."""
        if source is None:
            return source
        request = self.context.get('request')
        if request is not None and source.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "L'article source doit appartenir à votre société.")
        if self.instance is not None and source.id == self.instance.id:
            raise serializers.ValidationError(
                "Un article ne peut pas être la traduction de lui-même.")
        if source.traduction_de_id is not None:
            raise serializers.ValidationError(
                "L'article source est déjà une traduction : "
                "rattachez-vous à sa propre source.")
        return source


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
        # DRF auto-génère un ``UniqueTogetherValidator`` par tuple de
        # ``Meta.unique_together`` du modèle. Pour ``('article', 'role',
        # 'niveau')``, ce validateur compare aussi les lignes par-UTILISATEUR
        # (``role=''`` par défaut) entre elles — une fausse collision : deux
        # ACL nominatives distinctes (rôle vide toutes les deux) sur le même
        # article/niveau se retrouvent traitées comme un doublon de RÔLE alors
        # qu'aucun rôle n'est renseigné. Désactivés ici ; l'unicité réelle
        # (par-rôle et par-utilisateur, XOR) est appliquée explicitement dans
        # ``validate()`` ci-dessous et reste garantie en base par les DEUX
        # contraintes ``unique_together`` du modèle.
        validators = []

    def validate_article(self, article):
        """L'article ciblé doit appartenir à la société de l'utilisateur."""
        request = self.context.get('request')
        if request is not None and article.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Cet article n'appartient pas à votre société.")
        return article

    def validate(self, attrs):
        article = attrs.get('article', getattr(self.instance, 'article', None))
        role = attrs.get('role', getattr(self.instance, 'role', ''))
        utilisateur = attrs.get(
            'utilisateur', getattr(self.instance, 'utilisateur', None))
        niveau = attrs.get('niveau', getattr(self.instance, 'niveau', None))
        if bool(role) == bool(utilisateur):
            raise serializers.ValidationError(
                "Renseignez soit un rôle, soit un utilisateur "
                "(jamais les deux, jamais aucun).")
        if article is not None and niveau is not None:
            if role:
                qs = KbArticleAcl.objects.filter(
                    article=article, role=role, niveau=niveau)
            else:
                qs = KbArticleAcl.objects.filter(
                    article=article, utilisateur=utilisateur, niveau=niveau)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    "Les champs article, "
                    + ('role' if role else 'utilisateur')
                    + ", niveau doivent former un ensemble unique.")
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


class KbRechercheVideSerializer(serializers.ModelSerializer):
    """XKB16 — Recherche sans résultat (lecture seule : posée côté serveur
    par la liste des articles quand ``?search=`` ne renvoie rien)."""
    class Meta:
        model = KbRechercheVide
        fields = ['id', 'terme', 'utilisateur', 'date_creation']
        read_only_fields = fields


class PartageArticleKbSerializer(serializers.ModelSerializer):
    """XKB19 — Partage public d'un article (lien tokenisé, opt-in).

    ``token`` est en LECTURE SEULE (généré côté serveur, ``editable=False``
    sur le modèle) ; ``company``/``created_by`` sont posés côté serveur.
    """
    article_titre = serializers.CharField(
        source='article.titre', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = PartageArticleKb
        fields = [
            'id', 'article', 'article_titre', 'token', 'expires_at', 'actif',
            'consultations', 'is_expired', 'created_by', 'date_creation',
        ]
        read_only_fields = [
            'token', 'consultations', 'created_by', 'date_creation']

    def validate_article(self, article):
        request = self.context.get('request')
        if request is not None and article.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Cet article n'appartient pas à votre société.")
        return article


class KbParcoursSerializer(serializers.ModelSerializer):
    """XKB22 — Parcours de lecture (séquence ordonnée d'articles).

    ``company``/``created_by`` posés côté serveur (jamais du corps de
    requête)."""
    role_cible_display = serializers.CharField(
        source='get_role_cible_display', read_only=True)

    class Meta:
        model = KbParcours
        fields = [
            'id', 'nom', 'description', 'role_cible', 'role_cible_display',
            'metier', 'actif', 'created_by', 'date_creation',
        ]
        read_only_fields = ['created_by', 'date_creation']


class KbParcoursArticleSerializer(serializers.ModelSerializer):
    """XKB22 — Article ordonné d'un parcours. ``company`` posée côté serveur ;
    ``parcours``/``article`` validés même-société."""
    article_titre = serializers.CharField(
        source='article.titre', read_only=True)

    class Meta:
        model = KbParcoursArticle
        fields = ['id', 'parcours', 'article', 'article_titre', 'ordre']

    def validate_parcours(self, parcours):
        request = self.context.get('request')
        if request is not None and parcours.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Ce parcours n'appartient pas à votre société.")
        return parcours

    def validate_article(self, article):
        request = self.context.get('request')
        if request is not None and article.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Cet article n'appartient pas à votre société.")
        return article


class KbParcoursAssignationSerializer(serializers.ModelSerializer):
    """XKB22 — Assignation d'un parcours à un utilisateur précis. ``company``
    posée côté serveur ; ``parcours``/``utilisateur`` validés même-société."""
    utilisateur_nom = serializers.CharField(
        source='utilisateur.get_full_name', read_only=True)
    parcours_nom = serializers.CharField(
        source='parcours.nom', read_only=True)

    class Meta:
        model = KbParcoursAssignation
        fields = [
            'id', 'parcours', 'parcours_nom', 'utilisateur', 'utilisateur_nom',
            'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_parcours(self, parcours):
        request = self.context.get('request')
        if request is not None and parcours.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Ce parcours n'appartient pas à votre société.")
        return parcours

    def validate_utilisateur(self, utilisateur):
        request = self.context.get('request')
        if (request is not None
                and utilisateur.company_id != request.user.company_id):
            raise serializers.ValidationError(
                "Cet utilisateur n'appartient pas à votre société.")
        return utilisateur


class BlocReutilisableSerializer(serializers.ModelSerializer):
    """ZGED12 — Bloc de texte réutilisable (« presse-papiers Knowledge »).

    ``company``/``created_by`` posés côté serveur (jamais du corps de
    requête). La visibilité (personnel vs société) est appliquée côté vue
    (``selectors.blocs_visibles``), pas ici."""
    created_by_nom = serializers.CharField(
        source='created_by.get_full_name', read_only=True)
    portee_display = serializers.CharField(
        source='get_portee_display', read_only=True)

    class Meta:
        model = BlocReutilisable
        fields = [
            'id', 'nom', 'corps', 'portee', 'portee_display', 'created_by',
            'created_by_nom', 'date_creation', 'date_modification',
        ]
        read_only_fields = ['created_by', 'date_creation', 'date_modification']


class KbFavoriSerializer(serializers.ModelSerializer):
    """XKB15 — Favori (article étoilé) : posé côté serveur (utilisateur +
    société), strictement personnel — jamais visible d'un autre utilisateur
    (filtré côté vue, pas ici)."""
    article_titre = serializers.CharField(
        source='article.titre', read_only=True)

    class Meta:
        model = KbFavori
        fields = ['id', 'article', 'article_titre', 'utilisateur',
                  'date_creation']
        read_only_fields = ['utilisateur', 'date_creation']

    def validate_article(self, article):
        request = self.context.get('request')
        if request is not None and article.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Cet article n'appartient pas à votre société.")
        return article
