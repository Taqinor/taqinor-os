from typing import Optional

from rest_framework import serializers

from .models import ElementSupprime


class ElementSupprimeSerializer(serializers.ModelSerializer):
    """Journal de corbeille — LECTURE SEULE de bout en bout.

    Une entrée n'est jamais créée ni éditée depuis l'API : elle naît de
    l'événement `record_soft_deleted` et se ferme par l'action `restaurer/`.
    """

    supprime_par_nom = serializers.SerializerMethodField()
    # Clé du modèle cible (ex. `crm.lead`) : permet à l'écran de router vers le
    # détail sans exposer l'id de `ContentType`.
    modele = serializers.SerializerMethodField()

    class Meta:
        model = ElementSupprime
        fields = [
            'id', 'modele', 'object_id', 'type_libelle', 'libelle_snapshot',
            'donnees_snapshot', 'supprime_par', 'supprime_par_nom',
            'supprime_le', 'expire_le', 'restaure_le',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_supprime_par_nom(self, obj) -> Optional[str]:
        user = obj.supprime_par
        if not user:
            return None
        full = f'{getattr(user, "first_name", "")} {getattr(user, "last_name", "")}'.strip()
        return full or getattr(user, 'username', None) or getattr(user, 'email', None)

    def get_modele(self, obj) -> str:
        return obj.cle_modele
