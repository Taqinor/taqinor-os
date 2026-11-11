"""APUB14 — tableaux de bord et requêtes enregistrées : seul le propriétaire
modifie ou supprime ; un objet société (sans propriétaire) exige le palier
administrateur (patron ``apps/uxviews``). Sorti de ``core/views.py`` (fichier
≥ 2 000 lignes, C20)."""
from rest_framework.exceptions import PermissionDenied


def exiger_proprietaire(user, instance, quoi):
    if not ((instance.owner_id == user.id) if instance.owner_id else user.is_admin_role):
        raise PermissionDenied(f'Vous ne pouvez modifier que vos propres {quoi}.')


class ProprietaireSeulMixin:
    """``perform_update`` / ``perform_destroy`` gardés ; la mise à jour
    n'accepte jamais ``company``/``owner`` du corps (company imposée)."""

    proprietaire_quoi = 'objets'

    def perform_update(self, serializer):
        exiger_proprietaire(self.request.user, serializer.instance, self.proprietaire_quoi)
        serializer.save(company=self.request.user.company)

    def perform_destroy(self, instance):
        exiger_proprietaire(self.request.user, instance, self.proprietaire_quoi)
        super().perform_destroy(instance)
