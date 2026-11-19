"""NTP2P36 — permission FINE sur la validation d'un dossier fournisseur.

``DossierOnboardingFournisseurViewSet.valider_dossier`` (NTP2P7, action
``valider-dossier``) n'était gardée QUE par le palier grossier hérité
(``IsResponsableOrAdmin``) : tout compte Responsable/Admin pouvait valider ou
rejeter un dossier d'entrée en relation fournisseur. Ce module ajoute le code
fin catalogué par NTP2P36 (``roles.ALL_PERMISSIONS``), EN PLUS de
``IsResponsableOrAdmin`` — jamais à sa place, même patron que
``apps/btp_chantier/permissions.py`` (NTCON26) et
``apps/installations/permissions.py`` (NTP2P36).

Repli LÉGACY conservé via ``core.permissions._user_has_or_legacy`` : un compte
HÉRITÉ sans ``Role`` fin (palier Responsable/Admin via ``role_legacy``) garde
exactement son accès actuel ; un rôle FIN doit désormais porter le code pour
que la case correspondante soit administrable dans l'éditeur de rôles.
"""
from __future__ import annotations

from rest_framework.permissions import BasePermission

from authentication.permissions import HasPermission, IsAdminRole
from core.permissions import _user_has_or_legacy

#: Code fin NTP2P36 — inscrit au catalogue ``roles.ALL_PERMISSIONS``.
PERM_VALIDER_DOSSIER_FOURNISSEUR = 'valider_dossier_fournisseur'


class PeutValiderDossierFournisseur(BasePermission):
    """``valider_dossier_fournisseur`` — valide/rejette un dossier
    d'onboarding fournisseur en attente (NTP2P7, action ``valider-dossier``)."""

    message = (
        "Permission « valider_dossier_fournisseur » requise pour valider un "
        "dossier fournisseur.")

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False
        # NTPRT5 — un compte PORTAIL externe n'atteint jamais une route interne.
        if getattr(user, 'portee', 'interne') != 'interne':
            return False
        return _user_has_or_legacy(user, PERM_VALIDER_DOSSIER_FOURNISSEUR)


class PeutVoirPrixAchat(BasePermission):
    """ASTK10 (D-ASTK-2) — lectures dont l'objet même est un prix ou un
    montant d'ACHAT (PDF interne du BCF, historique des prix, achats hors
    contrat, comptes à payer…) : réservées à ``prix_achat_voir``
    (``user.can_view_buy_prices`` — repli historique pour les comptes légacy
    sans rôle fin, exactement comme le masquage des serializers)."""

    message = "Permission « prix_achat_voir » requise (prix et montants d'achat)."

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False
        if getattr(user, 'portee', 'interne') != 'interne':
            return False
        return bool(getattr(user, 'can_view_buy_prices', False))


#: ADRG44 — suppression d'un référentiel stock : palier administrateur OU la
#: case ``stock_supprimer`` d'un rôle fin (compte hérité : administrateur seul).
PeutSupprimerStock = IsAdminRole | HasPermission('stock_supprimer')


def cache_montants_achat(requete):
    """D-ASTK-2 — vrai quand la réponse à ``requete`` doit perdre ses prix et
    montants d'ACHAT (``PeutVoirPrixAchat`` refuse son utilisateur). Sans
    requête (usage service) : faux, la donnée reste entière."""
    return requete is not None and not PeutVoirPrixAchat().has_permission(requete, None)


def retirer_cles(donnees, champs):
    """Retire ``champs`` de chaque dictionnaire de ``donnees`` (listes et
    dictionnaires imbriqués compris) ; la clé disparaît, jamais mise à 0."""
    if isinstance(donnees, dict):
        for champ in champs:
            donnees.pop(champ, None)
        valeurs = donnees.values()
    elif isinstance(donnees, list):
        valeurs = donnees
    else:
        return donnees
    for valeur in valeurs:
        retirer_cles(valeur, champs)
    return donnees


class MasqueMontantsAchatMixin:
    """ERR-STK-PRIX-ACHAT-SUITE (D-ASTK-2) — retire ``champs_montants_achat``
    de la RÉPONSE quand ``PeutVoirPrixAchat`` refuse l'utilisateur de la
    requête ; l'écriture reste ouverte (aucune donnée perdue en silence).
    Sans requête en contexte (usage service) : réponse inchangée."""

    champs_montants_achat = ()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if cache_montants_achat(self.context.get('request')):
            for champ in self.champs_montants_achat:
                data.pop(champ, None)
        return data


class MasqueAchatRapportsProduitMixin:
    """STK1 (copilote vague 2, D-ASTK-2 / D-W2-Q6) — les rapports INTERNES du
    viewset produit gardés par le seul palier administrateur (``IsAdminRole``)
    servaient leurs valeurs d'achat à un rôle administrateur dont la case
    « voir les prix d'achat » est décochée. Pour ce compte, les clés ci-dessous
    sont RETIRÉES de la réponse (l'écran reste utilisable : quantités,
    fournisseurs, dates) ; un porteur de ``prix_achat_voir`` reçoit tout,
    comme avant. ``previsions-reappro`` n'est pas listée : elle ne rend que
    des quantités et des dates. L'export XLSX de la valorisation suit la même
    règle (``exports_valorisation``)."""

    champs_achat_par_action = {
        'valorisation': ('total', 'valeur', 'cout_moyen'),
        'valorisation_date': ('total', 'valeur', 'cout_moyen'),
        'a_reapprovisionner': ('prix_achat',),
        'rotation': ('valeur_stock',),
        'comparer_fournisseurs': ('prix_achat',),
        'rapport_pertes_view': ('valeur_totale', 'valeur'),
    }

    def finalize_response(self, request, response, *args, **kwargs):
        champs = self.champs_achat_par_action.get(getattr(self, 'action', None))
        if champs and cache_montants_achat(request):
            retirer_cles(getattr(response, 'data', None), champs)
        return super().finalize_response(request, response, *args, **kwargs)
