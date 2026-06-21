"""Permissions de la messagerie interne.

`IsConversationMember` : un utilisateur ne peut lire/écrire dans une conversation
que s'il en est membre (ET de la même société). Cross-tenant → 404 (via le
scoping du queryset) ; non-membre d'une conversation de sa société → 403.
"""
from rest_framework.permissions import BasePermission


def is_member(user, conversation):
    """Vrai si `user` appartient à `conversation` (même société comprise)."""
    if user is None or not getattr(user, 'pk', None):
        return False
    if getattr(conversation, 'company_id', None) != getattr(
            user, 'company_id', None):
        # Une société différente : on ne révèle même pas l'existence.
        return False
    return conversation.members.filter(user=user).exists()


class IsConversationMember(BasePermission):
    """Contrôle l'appartenance au niveau objet (Conversation ou Message).

    Le scoping société est déjà appliqué par le queryset (cross-tenant = 404) ;
    cette permission renvoie 403 pour un membre de la société qui n'appartient
    pas à la conversation."""

    message = "Vous n'êtes pas membre de cette conversation."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        conversation = getattr(obj, 'conversation', None) or obj
        return is_member(request.user, conversation)
