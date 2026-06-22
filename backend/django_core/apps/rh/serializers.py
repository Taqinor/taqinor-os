"""Sérialiseurs des Ressources humaines.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). Tous les FK reçus sont validés comme
appartenant à la société de l'utilisateur.
"""
from rest_framework import serializers

from .models import (
    Departement,
    DocumentEmploye,
    DossierEmploye,
    Remuneration,
)


def _meme_societe(serializer, value, label):
    """Garde-fou : un FK doit appartenir à la société de l'utilisateur."""
    request = serializer.context.get('request')
    if value is not None and request is not None:
        if value.company_id != request.user.company_id:
            raise serializers.ValidationError(f'{label} inconnu.')
    return value


class DepartementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Departement
        fields = ['id', 'nom', 'code', 'actif', 'date_creation']
        read_only_fields = ['date_creation']


class DossierEmployeSerializer(serializers.ModelSerializer):
    type_contrat_display = serializers.CharField(
        source='get_type_contrat_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    situation_familiale_display = serializers.CharField(
        source='get_situation_familiale_display', read_only=True)

    class Meta:
        model = DossierEmploye
        fields = [
            'id', 'user', 'matricule', 'nom', 'prenom', 'cin',
            'cnss', 'cimr', 'amo', 'situation_familiale',
            'situation_familiale_display', 'nombre_enfants', 'telephone',
            'email', 'poste', 'departement', 'date_embauche', 'type_contrat',
            'type_contrat_display', 'contrat_date_debut', 'contrat_date_fin',
            'statut', 'statut_display', 'cout_horaire',
            'rib',
            # FG158 — coordonnées perso étendues + contact d'urgence (internes).
            'adresse_perso', 'telephone_perso', 'email_perso',
            'urgence_nom', 'urgence_lien', 'urgence_telephone',
            'groupe_sanguin',
            'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_departement(self, value):
        return _meme_societe(self, value, 'Département')


class RemunerationSerializer(serializers.ModelSerializer):
    """Rémunération de base (FG157). ``employe`` doit appartenir à la société de
    l'utilisateur ; ``company`` est posée côté serveur."""
    periodicite_display = serializers.CharField(
        source='get_periodicite_display', read_only=True)

    class Meta:
        model = Remuneration
        fields = [
            'id', 'employe', 'montant', 'devise', 'periodicite',
            'periodicite_display', 'date_effet', 'motif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')


class DocumentEmployeSerializer(serializers.ModelSerializer):
    """Document du coffre employé (FG159) — qualifie une ``records.Attachment``.

    Lecture seule sur les métadonnées de la pièce jointe (nom/taille/mime/URL de
    téléchargement même origine) : le FICHIER lui-même reste dans MinIO via
    ``records.Attachment`` — ce sérialiseur n'expose que ce qui décrit le
    document. ``company`` et ``attachment`` sont posés côté serveur (jamais lus
    du corps) : la pièce jointe est créée par la vue à partir du fichier uploadé.
    """
    type_document_display = serializers.CharField(
        source='get_type_document_display', read_only=True)
    filename = serializers.CharField(
        source='attachment.filename', read_only=True)
    size = serializers.IntegerField(
        source='attachment.size', read_only=True)
    mime = serializers.CharField(
        source='attachment.mime', read_only=True)
    url = serializers.SerializerMethodField()

    class Meta:
        model = DocumentEmploye
        fields = [
            'id', 'employe', 'type_document', 'type_document_display',
            'date_expiration', 'note',
            'filename', 'size', 'mime', 'url',
            'date_creation',
        ]
        read_only_fields = [
            'id', 'type_document_display', 'filename', 'size', 'mime', 'url',
            'date_creation',
        ]

    def get_url(self, obj):
        # Même proxy Django (même origine, authentifié par cookie) que toute
        # autre pièce jointe records — on ne sert jamais l'URL MinIO interne.
        if obj.attachment_id:
            return (f'/api/django/records/attachments/'
                    f'{obj.attachment_id}/download/')
        return None

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')
