"""Sélecteurs LECTURE SEULE du catalogue lus depuis les devis (co-achat,
compatibilités panneau/batterie ↔ onduleur, classement d'un produit par nom,
« utilisé dans » les devis) — sortis de ``apps/ventes/selectors.py`` par
SPL147 (déplacement pur, corps inchangés ; propriétaire : stock).

Les autres apps continuent de lire ces fonctions par la FAÇADE
``apps.ventes.selectors`` (ré-export en fin de fichier) ; ce module est PLAT :
aucun import de ``.selectors`` en tête (cycle).
"""


def frequence_co_achat(company, produit_id, *, limite=10):
    """NTCPQ19 — Fréquence de CO-ACHAT d'un produit dans les devis ACCEPTÉS.

    Point d'entrée cross-app en LECTURE (sans importer
    ``apps.ventes.models``) : renvoie ``[(produit_id, nb_devis), ...]`` trié par
    fréquence décroissante — les produits apparaissant dans les mêmes devis
    acceptés de la SOCIÉTÉ que ``produit_id``, hors lui-même. Lecture pure,
    jamais de prix d'achat ni de marge."""
    from collections import Counter
    from .models import Devis, LigneDevis
    from .selectors import devis_en_jeu

    # ADEV45 — seule la version EN JEU d'une installation compte : une V1
    # remplacée par sa révision ne double pas la co-occurrence.
    devis_ids = devis_en_jeu(Devis.objects.filter(
        company=company, statut=Devis.Statut.ACCEPTE,
        lignes__produit_id=produit_id)).values_list('id', flat=True)
    devis_ids = set(devis_ids)
    if not devis_ids:
        return []
    paires = list(LigneDevis.objects.filter(
        devis_id__in=devis_ids).exclude(
            produit_id=produit_id).exclude(
                produit_id=None).values_list('devis_id', 'produit_id'))
    compteur = Counter({pid: 0 for _, pid in paires})
    vus = set()
    for devis_id, pid in paires:
        if (devis_id, pid) in vus:
            continue  # une même paire ne compte qu'une fois par devis
        vus.add((devis_id, pid))
        compteur[pid] += 1
    return compteur.most_common(limite)


# ═══════════════════════════════════════════════════════════════════════════
# PVCOMPAT (fondateur 20/08/2026) — COMPATIBILITÉ DEUX À DEUX, point d'entrée
# cross-app.
#
# Le CALCUL vit dans ``apps.ventes.compatibilites`` (il tient au moteur
# électrique et au catalogue solaire, donc au domaine Ventes) ; l'ÉCRAN, lui,
# est la fiche produit du STOCK. Les trois fonctions ci-dessous sont la façade
# LICITE de ce calcul : `apps.stock` (et tout autre appelant) les appelle sans
# jamais importer `apps.ventes.compatibilites` ni, à plus forte raison, les
# modèles de ventes — exactement la règle cross-app de CLAUDE.md.
#
# Import FONCTION-LOCAL : ce module est chargé très tôt (les modèles y font des
# appels différés), et `compatibilites` tire `solar_design` + le noyau
# `core.electrique`. Le différer garde ce fichier sans dépendance au chargement.
# ═══════════════════════════════════════════════════════════════════════════
def compatibilites_du_produit(produit, company):
    """PVCOMPAT — la fiche « Compatibilités » d'un produit du stock.

    Forme CONTRACTUELLE committée dans
    ``apps/stock/contract_samples/produit_compatibilites.json`` :
    ``{produit, fiche_incomplete, installable, bilan, familles}``. Lecture
    seule, aucun prix (ni de vente, ni d'achat) ne traverse cette fonction.
    """
    from .compatibilites import compatibilites_du_produit as _impl
    return _impl(produit, company)


def verdict_panneau_onduleur(panneau, onduleur):
    """PVCOMPAT — ``{statut, raisons, …}`` pour un couple panneau/onduleur.

    ``statut`` ∈ ``compatible`` / ``reserve`` / ``incompatible`` / ``inconnu``,
    avec la TAXONOMIE du noyau ``core.electrique`` (bloquant → incompatible,
    alerte → réserve) et jamais un faux OK sur une fiche incomplète.
    """
    from .compatibilites import verdict_panneau_onduleur as _impl
    return _impl(panneau, onduleur)


def verdict_batterie_onduleur(batterie, onduleur):
    """PVCOMPAT — ``{statut, raisons, …}`` pour un couple batterie/onduleur.

    Délègue à la règle batterie UNIQUE du dépôt
    (``services._batterie_compatible``) : l'écran et la composition ne peuvent
    pas diverger.
    """
    from .compatibilites import verdict_batterie_onduleur as _impl
    return _impl(batterie, onduleur)


def classer_produit_nom(nom):
    """STKCAT21 — le RÔLE de composition déduit des MOTS-CLÉS d'un nom, ou
    ``None``.

    Point d'entrée cross-app SANCTIONNÉ du classifieur par mots-clés : c'est
    par ici que ``apps.stock`` (le sérialiseur produit) lit la classification
    ventes, sans jamais importer ``apps.ventes.domain.catalogue`` — frontière
    inter-app, CLAUDE.md.

    Enveloppe MINCE de ``domain.catalogue.classer_produit`` : même entrée, même
    sortie, aucune règle en plus. C'est le REPLI PERMANENT de
    ``core.product_roles.role_effectif`` (rang 3, derrière le rôle déclaré sur
    la fiche et la famille de la catégorie) — il n'est jamais retiré. Pure
    lecture : ne requête rien, n'écrit rien.
    """
    from .domain.catalogue import classer_produit
    return classer_produit(nom)


def devis_utilisant_produit(user, produit_id, limit=20):
    """STKCAT25 — les devis RÉCENTS qui chiffrent ce produit, vus PAR ``user``.

    Frontière cross-app : ``apps.stock`` (onglet « Utilisé dans » de la fiche
    produit) lit les devis PAR ICI — jamais un import de ``apps.ventes.models``
    depuis une autre app.

    LA VISIBILITÉ EST CELLE DE LA LISTE ``/ventes/devis``, REJOUÉE À
    L'IDENTIQUE — jamais une copie allégée. Le chemin suit pas à pas
    ``DevisViewSet.get_queryset`` (``apps/ventes/views/devis.py``) et RÉUTILISE
    ses helpers, sans en réécrire un seul :

      1. ``company_qs`` (core.mixins)   — société (superuser sans société :
         tout ; compte sans société : rien) ;
      2. portail NTPRT10                — un compte externe ne voit QUE les
         devis de SON client, BROUILLON exclu (AUD143) ; une portée autre que
         « client », ou sans rattachement, ne voit RIEN (jamais tout) ;
      3. ``scope_queryset(created_by)`` — portée interne (Feature F).

    Sans ce rejeu, un commercial dont la portée masque un devis dans /ventes le
    verrait réapparaître par la fiche produit du Stock : la même donnée par une
    autre porte.

    Renvoie une liste de dicts ``{id, reference, client_nom, statut, date,
    total_ttc}``, du plus récent au plus ancien, bornée à ``limit``.
    ``total_ttc`` est un prix de VENTE en TEXTE décimal (jamais un flottant) ;
    ``date`` est la date de création en ISO. AUCUN prix d'achat, AUCUNE marge
    n'entre dans cette charge utile. Forme contractuelle :
    ``apps/stock/contract_samples/produit_utilise_dans.json``.
    """
    from apps.roles.permissions import is_portal_user, portal_scope_id
    from core.scoping import scope_queryset

    from .models import Devis
    # QJR655 — LA règle de portée société (core.mixins), celle de
    # TenantMixin : il n'existe pas DEUX règles société.
    from core.mixins import company_qs

    if user is None or not getattr(user, 'is_authenticated', False):
        return []
    if not produit_id:
        return []
    try:
        limite = int(limit)
    except (TypeError, ValueError):
        limite = 0
    if limite <= 0:
        return []

    qs = company_qs(Devis.objects.all(), user)
    if is_portal_user(user):
        scope = portal_scope_id(user)
        if getattr(user, 'portee', None) != 'portail_client' or scope is None:
            return []
        qs = qs.filter(client_id=scope).exclude(statut=Devis.Statut.BROUILLON)
    else:
        qs = scope_queryset(qs, user, ['created_by'])
        # NTADM3 — même périmètre d'entités que DevisViewSet (EntiteScopeMixin) ;
        # renvoie qs inchangé pour un rôle sans périmètre.
        from core.entite_scoping import scope_entite_queryset
        qs = scope_entite_queryset(qs, user)

    qs = (qs.filter(lignes__produit_id=produit_id)
            .select_related('client')
            .prefetch_related('lignes')
            .distinct()
            .order_by('-date_creation', '-id'))

    lignes = []
    for devis in qs[:limite]:
        client = devis.client
        lignes.append({
            'id': devis.id,
            'reference': devis.reference or '',
            'client_nom': (getattr(client, 'nom', '') or '') if client else '',
            'statut': devis.statut or '',
            'date': (devis.date_creation.date().isoformat()
                     if devis.date_creation else ''),
            'total_ttc': str(devis.total_ttc),
        })
    return lignes
