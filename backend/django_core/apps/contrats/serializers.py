"""Sérialiseurs de la Gestion des contrats.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). ``created_by`` est également posé côté
serveur.
"""
from rest_framework import serializers

from .models import Contrat, ContratLien, ModeleContrat, PartieContrat


class ContratSerializer(serializers.ModelSerializer):
    """Sérialiseur d'un ``Contrat``.

    ``sav_contrat_maintenance_id`` est un lien LÂCHE (id seul) vers un contrat
    de maintenance SAV (``sav.ContratMaintenance``) : il est STOCKÉ tel quel,
    sans validation cross-app — l'app ``sav`` n'expose pas de ``selectors.py``
    aujourd'hui, donc on ne vérifie pas l'existence/la société de la cible et on
    n'importe JAMAIS ``apps.sav``. Quand un sélecteur SAV de lecture existera,
    l'enrichissement/validation pourra s'y brancher (même schéma que les
    ``ContratLien`` enrichis dans ``selectors.py``).
    """
    type_contrat_display = serializers.CharField(
        source='get_type_contrat_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    confidentialite_display = serializers.CharField(
        source='get_confidentialite_display', read_only=True)

    class Meta:
        model = Contrat
        fields = [
            'id', 'reference', 'type_contrat', 'type_contrat_display',
            'objet', 'statut', 'statut_display', 'client_id',
            'sav_contrat_maintenance_id', 'date_debut',
            'date_fin', 'montant', 'devise',
            'confidentialite', 'confidentialite_display',
            'created_by', 'date_creation',
        ]
        read_only_fields = ['created_by', 'date_creation']


class PartieContratSerializer(serializers.ModelSerializer):
    type_partie_display = serializers.CharField(
        source='get_type_partie_display', read_only=True)

    class Meta:
        model = PartieContrat
        fields = [
            'id', 'contrat', 'type_partie', 'type_partie_display', 'nom',
            'fonction', 'email', 'telephone', 'ordre',
        ]

    def validate_contrat(self, contrat):
        """Le contrat rattaché doit appartenir à la société de l'utilisateur.

        Empêche d'attacher une partie à un contrat d'une autre société (la
        société de la partie elle-même est posée côté serveur par le
        ``TenantMixin``).
        """
        request = self.context.get('request')
        if request is not None and contrat.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Ce contrat n'appartient pas à votre société.")
        return contrat


class ContratLienSerializer(serializers.ModelSerializer):
    """Lien contrat → document métier d'une autre app (référence lâche typée).

    ``company`` n'est jamais exposée : elle est posée côté serveur. Le
    ``contrat`` reçu est validé comme appartenant à la société de l'utilisateur.
    """
    type_cible_display = serializers.CharField(
        source='get_type_cible_display', read_only=True)

    class Meta:
        model = ContratLien
        fields = [
            'id', 'contrat', 'type_cible', 'type_cible_display', 'cible_id',
            'libelle', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_contrat(self, contrat):
        """Le contrat rattaché doit appartenir à la société de l'utilisateur."""
        request = self.context.get('request')
        if request is not None and contrat.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Ce contrat n'appartient pas à votre société.")
        return contrat


class ModeleContratSerializer(serializers.ModelSerializer):
    """Sérialiseur d'un ``ModeleContrat`` (bibliothèque de gabarits — CONTRAT7).

    ``company`` n'est jamais exposée en écriture : elle est posée côté serveur.
    Champs d'affichage (_display) sont en lecture seule.
    """
    type_contrat_defaut_display = serializers.CharField(
        source='get_type_contrat_defaut_display', read_only=True)
    confidentialite_defaut_display = serializers.CharField(
        source='get_confidentialite_defaut_display', read_only=True)

    class Meta:
        model = ModeleContrat
        fields = [
            'id', 'nom', 'categorie',
            'type_contrat_defaut', 'type_contrat_defaut_display',
            'corps', 'clauses',
            'devise_defaut',
            'confidentialite_defaut', 'confidentialite_defaut_display',
            'actif', 'ordre', 'date_creation',
        ]
        read_only_fields = ['date_creation']


class InstancierContratSerializer(serializers.Serializer):
    """Corps de la requête POST /modeles/<id>/instancier/.

    Permet de surcharger les valeurs par défaut du gabarit au moment de
    l'instanciation. Tous les champs sont facultatifs : les valeurs manquantes
    sont héritées du gabarit.
    """
    objet = serializers.CharField(max_length=255, required=False, allow_blank=True)
    reference = serializers.CharField(max_length=50, required=False, allow_blank=True)
