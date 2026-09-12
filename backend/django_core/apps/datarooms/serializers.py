"""Serializers du module ``apps.datarooms`` (groupe NTDOC, P2).

RAPPEL multi-tenant : ``company`` n'est JAMAIS exposée en écriture — elle est
posée côté serveur par ``CompanyScopedModelViewSet.perform_create``.
"""
from rest_framework import serializers

from core.mixins import SameCompanyFKSerializerMixin

from .models import AccesSalleDonnees, SalleDeDonnees, SalleDeDonneesDocument


class SalleDeDonneesDocumentSerializer(SameCompanyFKSerializerMixin,
                                       serializers.ModelSerializer):
    """Une ligne d'appartenance document ↔ salle.

    AUD601 — ``document`` est une FK CROSS-APP vers un modèle scopé société :
    elle est validée même-société de façon déclarative (sans quoi un id de la
    société voisine passerait, DRF acceptant n'importe quelle clé primaire)."""

    same_company_fields = ('document',)

    document_nom = serializers.SerializerMethodField()
    statut_libelle = serializers.SerializerMethodField()

    class Meta:
        model = SalleDeDonneesDocument
        fields = [
            'id', 'salle', 'document', 'document_nom', 'ordre', 'visible',
            'statut_libelle', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_document_nom(self, obj) -> str:
        return getattr(obj.document, 'nom', '') or ''

    def get_statut_libelle(self, obj) -> str:
        return 'Visible' if obj.visible else 'Masqué'

    def validate(self, attrs):
        """Salle et document doivent appartenir à la MÊME société.

        Complète la garde déclarative ``same_company_fields`` : celle-ci borne
        le document à la société de l'APPELANT, celle-ci le borne à la société
        de la SALLE (les deux coïncident en pratique, mais un service appelé
        hors requête n'a pas d'appelant)."""
        salle = attrs.get('salle') or getattr(self.instance, 'salle', None)
        document = attrs.get('document') or getattr(
            self.instance, 'document', None)
        if salle is not None and document is not None:
            if salle.company_id != getattr(document, 'company_id', None):
                raise serializers.ValidationError(
                    "Ce document n'appartient pas à la société de la salle.")
        return attrs


class SalleDeDonneesSerializer(SameCompanyFKSerializerMixin,
                               serializers.ModelSerializer):
    """Fiche d'une salle de données.

    AUD601 — ``dossier_source`` est une FK cross-app (``ged.Folder``) scopée
    société : validée même-société de façon déclarative."""

    same_company_fields = ('dossier_source',)

    statut_libelle = serializers.CharField(
        source='get_statut_display', read_only=True)
    nombre_documents = serializers.SerializerMethodField()
    source_label = serializers.SerializerMethodField()
    source_url = serializers.SerializerMethodField()

    class Meta:
        model = SalleDeDonnees
        fields = [
            'id', 'nom', 'description', 'dossier_source', 'deal_type',
            'statut', 'statut_libelle', 'expires_at', 'nombre_documents',
            'source_type', 'source_id', 'source_label', 'source_url',
            'fermee_le', 'created_at', 'updated_at',
        ]
        # `statut` ne change que par l'action de fermeture (NTDOC16) : un PATCH
        # brut ne doit jamais court-circuiter la révocation des accès.
        read_only_fields = [
            'statut', 'fermee_le', 'created_at', 'updated_at']

    def get_nombre_documents(self, obj) -> int:
        return obj.documents.count()

    def _carte_source(self, obj):
        """NTDOC15 — fiche-carte de l'objet d'origine, résolue une seule fois."""
        if not obj.source_type or not obj.source_id:
            return None
        cache = getattr(self, '_cache_source', None)
        if cache is None:
            cache = self._cache_source = {}
        cle = (obj.source_type, obj.source_id, obj.company_id)
        if cle not in cache:
            from .services import carte_source
            cache[cle] = carte_source(
                obj.company, obj.source_type, obj.source_id)
        return cache[cle]

    def get_source_label(self, obj) -> str:
        carte = self._carte_source(obj)
        return (carte or {}).get('label') or ''

    def get_source_url(self, obj) -> str:
        carte = self._carte_source(obj)
        return (carte or {}).get('url') or ''


class AccesSalleDonneesSerializer(serializers.ModelSerializer):
    """NTDOC12 — Accès d'un viewer nommé (côté GESTION, jamais public).

    Le ``token`` est en lecture seule : il est généré côté serveur et sert à
    composer le lien à envoyer au viewer. ``revoque`` ne se pose que par
    l'action dédiée (``revoquer/``) pour que la révocation reste explicite."""

    salle_nom = serializers.SerializerMethodField()
    lien_public = serializers.SerializerMethodField()
    actif = serializers.SerializerMethodField()

    class Meta:
        model = AccesSalleDonnees
        fields = [
            'id', 'salle', 'salle_nom', 'nom', 'email', 'token',
            'lien_public', 'expires_at', 'revoque', 'actif',
            'derniere_consultation', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'token', 'revoque', 'derniere_consultation',
            'created_at', 'updated_at',
        ]

    def get_salle_nom(self, obj) -> str:
        return getattr(obj.salle, 'nom', '') or ''

    def get_lien_public(self, obj) -> str:
        from .services import lien_public_acces
        return lien_public_acces(obj)

    def get_actif(self, obj) -> bool:
        return obj.est_actif()

    def validate_salle(self, value):
        """La salle doit appartenir à la société de l'appelant."""
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.pk:
            raise serializers.ValidationError(
                "Cette salle n'appartient pas à votre société.")
        return value
