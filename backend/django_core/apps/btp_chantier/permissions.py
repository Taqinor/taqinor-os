"""NTCON26 — permissions FINES par action du vertical BTP/EPC.

``btp_voir``/``btp_gerer`` (WIR169) gardent le module en lecture/écriture, mais
ils ne distinguent PAS les gestes engageants : avec ``btp_gerer``, le même
compte peut lever une réserve, répondre à un RFI, approuver un visa, approuver
un avenant qui engage le budget et FINALISER un décompte général définitif. Sur
un chantier réel ces six gestes appartiennent à des personnes différentes
(conducteur de travaux, MOE, direction). Ce module ajoute les six codes fins
demandés par NTCON26, enforced EN PLUS du filtre société et de la garde
lecture/écriture existante — jamais à sa place.

Nommage : le plan écrit les clés en pointé (``btp.reserve.creer`` …) ; le
registre du dépôt (``roles.ALL_PERMISSIONS``) est en SOULIGNÉ sans exception
(``btp_voir``, ``qhse_gerer``, ``douane_responsable``…) et la table
``roles.PERMISSION_MODULE`` ainsi que ``CustomUser._role_grants_write``
raisonnent sur ce format. On garde donc la convention du dépôt, code pour code :

    btp.reserve.creer     → btp_reserve_creer
    btp.reserve.lever     → btp_reserve_lever
    btp.rfi.repondre      → btp_rfi_repondre
    btp.visa.approuver    → btp_visa_approuver
    btp.avenant.approuver → btp_avenant_approuver
    btp.dgd.finaliser     → btp_dgd_finaliser

Repli LÉGACY conservé : ``core.permissions._user_has_or_legacy`` fait passer un
compte hérité SANS ``Role`` fin (palier Responsable) — on ne retire jamais un
accès existant. Un rôle FIN, lui, doit porter le code : c'est exactement le cas
d'acceptation NTCON26 (un rôle sans ``btp_visa_approuver`` reçoit 403 sur
l'approbation même s'il lit le chantier).
"""
from __future__ import annotations

from rest_framework.permissions import BasePermission

from core.permissions import _user_has_or_legacy

#: Codes fins NTCON26 — inscrits au catalogue ``roles.ALL_PERMISSIONS``.
PERM_RESERVE_CREER = 'btp_reserve_creer'
PERM_RESERVE_LEVER = 'btp_reserve_lever'
PERM_RFI_REPONDRE = 'btp_rfi_repondre'
PERM_VISA_APPROUVER = 'btp_visa_approuver'
PERM_AVENANT_APPROUVER = 'btp_avenant_approuver'
PERM_DGD_FINALISER = 'btp_dgd_finaliser'

#: Ordre stable — consommé par les tests et par le catalogue de rôles.
PERMISSIONS_FINES_BTP = (
    PERM_RESERVE_CREER,
    PERM_RESERVE_LEVER,
    PERM_RFI_REPONDRE,
    PERM_VISA_APPROUVER,
    PERM_AVENANT_APPROUVER,
    PERM_DGD_FINALISER,
)


class _PermissionFineBtp(BasePermission):
    """Base : exige le code ``code`` (repli légacy conservé)."""

    code = None
    message = "Permission BTP insuffisante pour cette action."

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False
        # NTPRT5 — un compte PORTAIL externe n'atteint jamais une route interne.
        if getattr(user, 'portee', 'interne') != 'interne':
            return False
        return _user_has_or_legacy(user, self.code)


class PeutCreerReserve(_PermissionFineBtp):
    """``btp.reserve.creer`` — poser une réserve sur un plan (NTCON1)."""
    code = PERM_RESERVE_CREER
    message = "Permission « btp.reserve.creer » requise pour poser une réserve."


class PeutLeverReserve(_PermissionFineBtp):
    """``btp.reserve.lever`` — lever/contester une réserve (NTCON2)."""
    code = PERM_RESERVE_LEVER
    message = "Permission « btp.reserve.lever » requise pour lever une réserve."


class PeutRepondreRfi(_PermissionFineBtp):
    """``btp.rfi.repondre`` — répondre/clore un RFI (NTCON3)."""
    code = PERM_RFI_REPONDRE
    message = "Permission « btp.rfi.repondre » requise pour répondre à un RFI."


class PeutApprouverVisa(_PermissionFineBtp):
    """``btp.visa.approuver`` — décider d'un visa, approbation OU refus.

    Le refus est la DÉCISION MIROIR de l'approbation : garder seulement
    ``approuver`` laisserait un compte non revuseur bloquer un document en le
    refusant — un trou équivalent en sens inverse.
    """
    code = PERM_VISA_APPROUVER
    message = (
        "Permission « btp.visa.approuver » requise pour décider d'un visa.")


class PeutApprouverAvenant(_PermissionFineBtp):
    """``btp.avenant.approuver`` — approuver/refuser un avenant (NTCON7/8)."""
    code = PERM_AVENANT_APPROUVER
    message = (
        "Permission « btp.avenant.approuver » requise pour décider d'un "
        "avenant.")


class PeutFinaliserDgd(_PermissionFineBtp):
    """``btp.dgd.finaliser`` — finaliser un décompte général (NTCON9).

    Le DÉVERROUILLAGE (NTCON10), qui annule l'effet de la finalisation, est
    déjà réservé au palier ADMINISTRATEUR par sa propre garde
    (``DecompteGeneralViewSet.deverrouiller``) — strictement plus restrictif
    que ce code : rien à y ajouter.
    """
    code = PERM_DGD_FINALISER
    message = (
        "Permission « btp.dgd.finaliser » requise pour finaliser un décompte "
        "général.")
