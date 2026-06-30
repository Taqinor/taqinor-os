"""Sérialiseurs des Réclamations & litiges.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). ``created_by`` est posé côté serveur.
"""
from rest_framework import serializers

from .models import Reclamation, ReclamationActivity


class ReclamationActivitySerializer(serializers.ModelSerializer):
    """Entrée du chatter (changement de statut automatique ou note manuelle).

    Tous les champs sont en lecture seule côté API : les entrées sont créées
    exclusivement côté serveur (transitions de statut, action ``noter``).
    """
    type_display = serializers.CharField(
        source='get_type_display', read_only=True)
    auteur_nom = serializers.SerializerMethodField()

    class Meta:
        model = ReclamationActivity
        fields = [
            'id', 'reclamation', 'type', 'type_display', 'old_value',
            'new_value', 'message', 'auteur', 'auteur_nom', 'date_creation',
        ]
        read_only_fields = fields

    def get_auteur_nom(self, obj):
        return getattr(obj.auteur, 'username', None)


class ReclamationSerializer(serializers.ModelSerializer):
    type_reclamation_display = serializers.CharField(
        source='get_type_reclamation_display', read_only=True)
    gravite_display = serializers.CharField(
        source='get_gravite_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    # LITIGE4 — aperçus QHSE (NCR + audit fin de chantier) résolus côté serveur
    # via apps.qhse.selectors (import fonction-local). Lecture seule ; le
    # rattachement se pose en écriture via ``ncr_id`` / ``audit_id``.
    ncr = serializers.SerializerMethodField()
    audit = serializers.SerializerMethodField()

    class Meta:
        model = Reclamation
        fields = [
            'id', 'reference', 'type_reclamation', 'type_reclamation_display',
            'gravite', 'gravite_display', 'objet', 'description',
            'source_type', 'source_id', 'montant_conteste', 'statut',
            'statut_display', 'bloque_relances', 'ncr_id', 'audit_id',
            'ncr', 'audit',
            # LITIGE5 — concurrent gagnant + motif sur deal perdu (étend FG242).
            'concurrent_nom', 'concurrent_prix', 'concurrent_devise',
            'motif_perte',
            'created_by', 'date_creation',
        ]
        # ``statut`` ne se modifie pas par PATCH direct : le cycle de vie passe
        # par les actions de transition (prendre_en_charge/resoudre/rejeter)
        # qui appliquent la machine à états et journalisent le chatter.
        # ``bloque_relances`` est modifiable par PATCH (le gestionnaire peut
        # désactiver la suspension si nécessaire).
        read_only_fields = ['created_by', 'date_creation', 'statut']

    def get_ncr(self, obj):
        """Aperçu de la non-conformité QHSE liée (ou None), scopé société.

        Lecture cross-app via le sélecteur QHSE (import fonction-local) — jamais
        un import de modèle. La société vient de l'objet (posée côté serveur).
        """
        if not obj.ncr_id:
            return None
        from apps.qhse.selectors import ncr_apercu
        return ncr_apercu(obj.ncr_id, obj.company_id and obj.company)

    def get_audit(self, obj):
        """Aperçu de l'audit fin de chantier QHSE lié (ou None), scopé société."""
        if not obj.audit_id:
            return None
        from apps.qhse.selectors import audit_apercu
        return audit_apercu(obj.audit_id, obj.company_id and obj.company)
