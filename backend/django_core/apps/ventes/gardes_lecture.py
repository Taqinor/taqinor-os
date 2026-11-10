"""ERR-ASEC11-LISTE-FACTURES — garde de LECTURE du module Ventes, hors de
``views/`` pour que ``recouvrement`` (lu par les tâches planifiées, donc par
crm) la lise sans importer la couche vue (contrats import-linter)."""
from apps.roles.permissions import is_portal_user
from authentication.permissions import LectureDuModule


class LectureVentes(LectureDuModule):
    """ERR-ASEC11-LISTE-FACTURES (C-ASEC-004, clause ASEC11 « la liste des
    factures → 403 » pour Commercial terrain et Admin RH), ADVS23 pour les
    devis (C-ADVS-041) — LECTURE d'un document du module Ventes.

    APFS108 (D-APFS-4) — rebasée sur ``LectureDuModule`` avec le module FIGÉ
    ``ventes`` : compte interne ET, pour un rôle fin non administrateur, au
    moins un code du module ``ventes`` (ou un octroi de lecture de la vue).
    Inchangés : superuser, palier administrateur, comptes hérités sans rôle
    fin."""

    message = 'Accès réservé aux rôles du module Ventes.'
    module_fige = 'ventes'


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


def lecteur_sans_code_ventes(user):
    """APFS108/APFS109 — rôle fin non administrateur sans aucun code
    ``ventes`` (entré par un octroi de lecture, ``installation_voir``)."""
    from authentication.permissions import codes_du_module

    if (getattr(user, 'is_superuser', False)
            or getattr(user, 'is_admin_role', False)
            or not getattr(user, 'role_id', None)):
        return False
    return not (codes_du_module('ventes')
                & set(user.role.permissions or []))


#: APFS109 — comment chaque vue « dossier / recette » rejoint SON chantier :
#: ``('chantier', <champ chantier>)`` ou ``('devis', <champ devis_id>)``.
CHEMINS_DU_CHANTIER = {
    'RegulatoryDossierViewSet': ('devis', 'devis_id'),
    'DossierChecklistItemViewSet': ('devis', 'dossier__devis_id'),
    'DossierExchangeViewSet': ('devis', 'dossier__devis_id'),
    'SubventionDossierViewSet': ('devis', 'devis_id'),
    'Regularisation8221ViewSet': ('devis', 'devis_id'),
    'CommissioningTestViewSet': ('chantier', 'chantier'),
    'IVCurveCaptureViewSet': ('chantier', 'recette__chantier'),
    'AsBuiltPackViewSet': ('chantier', 'chantier'),
    'AttestationConformiteViewSet': ('chantier', 'chantier'),
    'TestPerformanceReceptionViewSet': ('chantier', 'chantier'),
    'AttestationREViewSet': ('chantier', 'chantier'),
}


class BorneAuChantierMixin:
    """APFS109 (D-APFS-4) — un lecteur entré par l'octroi
    ``installation_voir`` (sans code ``ventes``) ne voit que les objets de
    SES chantiers (``apps.installations.selectors.chantiers_visibles``)."""

    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(getattr(self, 'request', None), 'user', None)
        if user is None or not lecteur_sans_code_ventes(user):
            return qs
        from apps.installations.selectors import chantiers_visibles

        genre, champ = CHEMINS_DU_CHANTIER[type(self).__name__]
        visibles = chantiers_visibles(user)
        if genre == 'chantier':
            return qs.filter(**{f'{champ}__in': visibles})
        return qs.filter(**{f'{champ}__in': visibles.values('devis_id')})
