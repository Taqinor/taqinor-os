"""ERR-ASEC11-LISTE-FACTURES — garde de LECTURE du module Ventes, hors de
``views/`` pour que ``recouvrement`` (lu par les tâches planifiées, donc par
crm) la lise sans importer la couche vue (contrats import-linter)."""
from apps.roles.permissions import is_portal_user
from authentication.permissions import IsAnyRole, codes_du_module


class LectureVentes(IsAnyRole):
    """ERR-ASEC11-LISTE-FACTURES (C-ASEC-004, clause ASEC11 « la liste des
    factures → 403 » pour Commercial terrain et Admin RH), ADVS23 pour les
    devis (C-ADVS-041) — LECTURE d'un document du module Ventes.

    Compte interne (``IsAnyRole``) ET, pour un rôle fin non administrateur, au
    moins un code du module ``ventes`` (même règle de lecture que la branche
    lecture d'``IsResponsableOrAdmin``, sans exiger le palier responsable : un
    Commercial ou un Viewer qui porte ``ventes_voir`` lit toujours ses
    documents). Inchangés : superuser, palier administrateur, comptes hérités
    sans rôle fin."""

    message = 'Accès réservé aux rôles du module Ventes.'

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        user = request.user
        if (getattr(user, 'is_superuser', False)
                or getattr(user, 'is_admin_role', False)):
            return True
        if not getattr(user, 'role_id', None):
            return True
        return bool(codes_du_module('ventes')
                    & set(user.role.permissions or []))


class LectureFactures(LectureVentes):
    """La LECTURE d'une facture (liste, fiche, paiements, relances, e-mails,
    arrondi, KPI). Tous les écrans qui lisent ``/ventes/factures/`` sont des
    écrans Ventes (liste, paiements, relances, tableau de bord) — aucun écran
    d'un rôle sans code ventes n'en dépend."""

    message = 'Accès aux factures réservé aux rôles du module Ventes.'


class LectureVentesHorsPortail(LectureVentes):
    """ADVS23 — ``/proposal`` : la même règle pour un compte interne ; le client
    portail reste jugé par ``IsInternalWriterOrPortalClientOwner``, posée avant."""

    def has_permission(self, request, view):
        return (is_portal_user(request.user)
                or super().has_permission(request, view))
