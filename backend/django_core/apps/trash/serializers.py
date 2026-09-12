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
    # NTUX26 — avertissement best-effort pour l'assistant de restauration en
    # masse (jamais bloquant, jamais une vérité absolue) : `None` sauf quand
    # `donnees_snapshot` porte CONVENTIONNELLEMENT une clé `responsable_id`/
    # `assigned_to_id` (l'émetteur `record_soft_deleted` de l'app cible décide
    # librement de ce qu'il snapshote — `apps.trash` n'importe aucun modèle
    # métier) ET que ce responsable n'existe plus ou a été désactivé depuis.
    avertissement_restauration = serializers.SerializerMethodField()

    class Meta:
        model = ElementSupprime
        fields = [
            'id', 'modele', 'object_id', 'type_libelle', 'libelle_snapshot',
            'donnees_snapshot', 'supprime_par', 'supprime_par_nom',
            'supprime_le', 'expire_le', 'restaure_le',
            'avertissement_restauration',
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

    def get_avertissement_restauration(self, obj) -> Optional[str]:
        if obj.restaure_le is not None:
            return None
        snapshot = obj.donnees_snapshot or {}
        responsable_id = snapshot.get('responsable_id') or snapshot.get('assigned_to_id')
        if not responsable_id:
            return None
        try:
            from django.contrib.auth import get_user_model
            responsable = get_user_model().objects.filter(pk=responsable_id).first()
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            return None
        if responsable is None:
            return "Le responsable d'origine n'existe plus."
        if not responsable.is_active:
            return "Le responsable d'origine a été désactivé."
        return None
