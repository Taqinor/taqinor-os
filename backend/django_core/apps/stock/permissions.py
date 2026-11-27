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

from types import SimpleNamespace

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
        # Jumeau de 17b278df9 / f3056a536 : une réponse d'erreur n'a rien à masquer, et lire
        # ``request.user`` ici authentifiait hors du gestionnaire d'exceptions de DRF (en-tête
        # ``Authorization`` mal formé → 500 au lieu de 401). Seul l'utilisateur DÉJÀ authentifié
        # (``Request._user``) est lu.
        champs = self.champs_achat_par_action.get(getattr(self, 'action', None))
        if champs and not getattr(response, 'exception', False):
            user = vars(request).get('_user') if hasattr(request, '__dict__') else None
            if cache_montants_achat(SimpleNamespace(user=user)):
                retirer_cles(getattr(response, 'data', None), champs)
        return super().finalize_response(request, response, *args, **kwargs)


# ── D-ACAL-152 (fondateur, 26/11/2026) — prix de VENTE masqués ──────────────
#: LA liste des clés de prix de vente que le stock RETIRE pour un compte sans
#: ``prix_vente_voir`` (``User.can_view_sale_prices`` : Technicien et
#: Technicien responsable par défaut). Champs du produit, puis clés dérivées
#: des actions (étiquette TTC, kits explosés / structure).
PRIX_VENTE_CHAMPS = (
    'prix_vente', 'paliers_prix_vente', 'prix_fixe_ht', 'prix_par_panneau_ht',
    'tarif_location_jour', 'tarif_location_semaine', 'tarif_location_mois',
    'prix_ttc', 'prix_vente_unitaire', 'prix_vente_total',
)
MESSAGE_PRIX_VENTE = "Permission « prix_vente_voir » requise (prix de vente)."


def cache_prix_vente(requete):
    """D-ACAL-152 — vrai quand la réponse à ``requete`` doit perdre ses prix de
    VENTE. Sans requête ou sans utilisateur (usage service) : faux, la donnée
    reste entière."""
    user = getattr(requete, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    return not getattr(user, 'can_view_sale_prices', True)


def _cache_prix_vente_deja_authentifie(requete):
    """``cache_prix_vente`` pour une RÉPONSE : ne lit que l'utilisateur que DRF a déjà
    authentifié (``Request._user``), jamais ``requete.user`` (qui authentifierait)."""
    user = vars(requete).get('_user') if hasattr(requete, '__dict__') else None
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    return not getattr(user, 'can_view_sale_prices', True)


#: Valeurs qu'un formulaire renvoie pour un prix qu'on ne lui a pas servi.
_PRIX_VIDES = ('', None, [], {})


class MasquePrixVenteMixin:
    """D-ACAL-152 — sérialiseur du stock : sans ``prix_vente_voir``, les clés de
    ``PRIX_VENTE_CHAMPS`` sont RETIRÉES de la représentation (lecture, réponse
    d'écriture, objets imbriqués). L'ÉCRITURE garde son contrat (ASTK20 :
    changer un prix sans ``catalogue_prix_modifier`` = 403) ; seul un prix
    VIDE renvoyé par un formulaire qui ne l'a jamais reçu est lu comme « pas
    de changement » (mise à jour seulement). À placer AVANT les autres bases."""

    def _prix_vente_caches(self):
        return cache_prix_vente(self.context.get('request'))

    def to_internal_value(self, data):
        caches = self.instance is not None and self._prix_vente_caches()
        if caches and hasattr(data, 'copy'):
            data = data.copy()
            for champ in PRIX_VENTE_CHAMPS:
                if champ in data and data.get(champ) in _PRIX_VIDES:
                    data.pop(champ)
        attrs = super().to_internal_value(data)
        if caches:
            self._refuser_prix_vente_modifie(attrs)
        return attrs

    def _refuser_prix_vente_modifie(self, attrs):
        """D-ACAL-165 — qui ne VOIT pas un prix de vente ne l'écrase pas : un
        changement NON vide → 403. Les prix catalogue (``PRIX_CATALOGUE_CHAMPS``
        du sérialiseur) gardent leur 403 « catalogue_prix_modifier » (ASTK20)
        pour qui n'a pas ce code ; ce garde couvre le reste (tarifs de
        location) et le compte qui porterait ``catalogue_prix_modifier`` sans
        ``prix_vente_voir``."""
        user = getattr(self.context.get('request'), 'user', None)
        from .serializers import PRIX_CATALOGUE_CHAMPS as catalogue  # liste unique (ASTK20)
        garde_catalogue = bool(user and user.has_erp_permission('catalogue_prix_modifier'))
        changes = [c for c in PRIX_VENTE_CHAMPS
                   if c in attrs and (garde_catalogue or c not in catalogue)
                   and attrs[c] != getattr(self.instance, c, None)]
        if changes:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(f"{MESSAGE_PRIX_VENTE} — modification refusée ({', '.join(changes)}).")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if self._prix_vente_caches():
            for champ in PRIX_VENTE_CHAMPS:
                data.pop(champ, None)
        return data


class MasquePrixVenteReponseMixin:
    """D-ACAL-152 — viewset du stock : sans ``prix_vente_voir``, les clés de
    ``PRIX_VENTE_CHAMPS`` sont retirées de TOUTE réponse JSON (liste, détail,
    recherche, actions, dictionnaires imbriqués) ; les actions de
    ``actions_reservees_prix_vente`` (une sortie qui n'est QU'un prix, ex.
    l'étiquette prix) répondent 403."""

    actions_reservees_prix_vente = ()
    #: D-ACAL-165 — montants de VENTE propres à une action, sous un autre nom
    #: que ``PRIX_VENTE_CHAMPS`` (ex. le total TTC d'un devis).
    montants_vente_par_action = {}

    def check_permissions(self, request):
        super().check_permissions(request)
        if (getattr(self, 'action', None) in self.actions_reservees_prix_vente
                and cache_prix_vente(request)):
            self.permission_denied(request, message=MESSAGE_PRIX_VENTE)

    def finalize_response(self, request, response, *args, **kwargs):
        # CI #1564 api-fuzz (``stock/produits/0.5/`` → 500) : « .5 » est lu comme un suffixe de
        # format, la négociation répond 404 AVANT l'authentification ; lire ``request.user`` ici
        # la déclenchait hors du gestionnaire d'exceptions de DRF. Seul l'utilisateur DÉJÀ
        # authentifié est lu (toute réponse d'une requête authentifiée garde son masque).
        if _cache_prix_vente_deja_authentifie(request):
            champs = PRIX_VENTE_CHAMPS + tuple(
                self.montants_vente_par_action.get(getattr(self, 'action', None), ()))
            retirer_cles(getattr(response, 'data', None), champs)
        return super().finalize_response(request, response, *args, **kwargs)


class MasquePrixVenteProduitMixin(MasquePrixVenteReponseMixin):
    """D-ACAL-152 — ``ProduitViewSet`` : l'étiquette PRIX de rayon n'existe que
    pour son prix TTC → réservée à ``prix_vente_voir``. D-ACAL-165 — « Utilisé
    dans » : ``total_ttc`` des devis retiré sans le droit ; et (D-ACAL-106,
    « aucun devis ni aucun prix ») un compte qui ne peut pas LIRE les devis
    (``ventes.selectors_assistant.lit_les_devis``) n'en reçoit aucune ligne."""

    actions_reservees_prix_vente = ('etiquettes_prix',)
    montants_vente_par_action = {'utilise_dans': ('total_ttc',)}

    def finalize_response(self, request, response, *args, **kwargs):
        donnees = getattr(response, 'data', None)
        if getattr(self, 'action', None) == 'utilise_dans' and isinstance(donnees, dict) \
                and donnees.get('devis'):
            from apps.ventes.selectors_assistant import lit_les_devis
            if not lit_les_devis(getattr(request, 'user', None)):
                donnees['devis'] = []
        return super().finalize_response(request, response, *args, **kwargs)
