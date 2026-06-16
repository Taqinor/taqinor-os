"""
Parc installé (système installé) — matérialisation à la réception du chantier
(N7) et helpers de classification des composants.

Principe (additif, réutilise l'existant) : le chantier RÉCEPTIONNÉ (mise en
service ou clôturé) EST le système installé. Il porte déjà client / site / GPS /
kWc / type / installateur / date de mise en service / liens devis. À la
réception on :

  1. pose `date_reception` une seule fois (première transition vers un état
     terminal) ;
  2. AUTO-CRÉE un `sav.Equipement` par produit « composant » des lignes du
     devis d'origine (panneau / onduleur / batterie / pompe / variateur …),
     s'il n'existe pas déjà un équipement de ce produit sur le chantier.

Idempotent : ré-exécuter ne crée jamais de doublon. Aucun planificateur — c'est
déclenché au fil de l'eau, sur le chemin de changement de statut.
"""

# Mots-clés de classification des composants — ALIGNÉS avec
# quote_engine/builder.py (panneau / onduleur / batterie) + pompage (pompe /
# variateur). Un produit dont la désignation OU le nom contient l'un de ces
# mots est un composant matériel du parc installé.
COMPONENT_KEYWORDS = (
    'panneau', 'panneaux',
    'onduleur',
    'batterie',
    'pompe',
    'variateur',
)


def is_component(designation, produit_nom=''):
    """Vrai si la ligne désigne un composant matériel à suivre au parc."""
    blob = f"{designation or ''} {produit_nom or ''}".lower()
    return any(kw in blob for kw in COMPONENT_KEYWORDS)


def _component_produits_from_devis(devis):
    """Produits distincts (composants) des lignes du devis, dans l'ordre.

    Réutilise la classification alignée avec le moteur de devis : on ne crée un
    équipement que pour les lignes matérielles (panneau / onduleur / batterie /
    pompe / variateur), jamais pour la pose, l'étude, les frais, etc.
    """
    produits = []
    seen = set()
    if devis is None:
        return produits
    for ligne in devis.lignes.select_related('produit').all():
        produit = ligne.produit
        if produit is None or produit.id in seen:
            continue
        if not is_component(ligne.designation, getattr(produit, 'nom', '')):
            continue
        seen.add(produit.id)
        produits.append(produit)
    return produits


def ensure_equipements(installation, user=None):
    """Crée les sav.Equipement manquants pour les composants du chantier.

    IDEMPOTENT : un seul équipement par (chantier, produit). La date de pose
    utilisée est la mise en service du chantier (sinon la pose réelle, sinon la
    date de réception) ; les horloges de garantie sont recalculées comme partout
    (date_pose + Produit.garantie_mois). Retourne la liste des équipements créés.
    """
    from apps.sav.models import Equipement

    devis = installation.devis
    produits = _component_produits_from_devis(devis)
    if not produits:
        return []

    existing = set(
        Equipement.objects.filter(installation=installation)
        .values_list('produit_id', flat=True))

    date_pose = (
        installation.date_mise_en_service
        or installation.date_pose_reelle
        or installation.date_reception)

    created = []
    for produit in produits:
        if produit.id in existing:
            continue
        eq = Equipement(
            company=installation.company,
            produit=produit,
            installation=installation,
            date_pose=date_pose,
            created_by=user,
        )
        eq.recompute_garanties()
        eq.save()
        created.append(eq)
    return created


def mark_received(installation, user=None, today=None):
    """Matérialise le système installé quand le chantier est réceptionné (N7).

    À appeler quand le statut devient « mise en service » ou « clôturé ». Pose
    `date_reception` la première fois, garde `parc_actif` à True, puis auto-crée
    les équipements manquants. IDEMPOTENT et sans effet si le chantier n'est pas
    dans un état réceptionné. Retourne la liste des équipements créés.
    """
    from django.utils import timezone
    from .models import Installation

    if installation.statut not in Installation.RECEIVED_STATUTS:
        return []

    # Recharge depuis la base : les dates posées via l'API arrivent en chaîne
    # dans l'instance en mémoire ; refresh_from_db garantit de vrais objets date
    # pour le calcul des garanties (date_pose + Produit.garantie_mois).
    installation.refresh_from_db()

    today = today or timezone.localdate()
    update_fields = []
    if installation.date_reception is None:
        installation.date_reception = (
            installation.date_mise_en_service or today)
        update_fields.append('date_reception')
    if not installation.parc_actif:
        installation.parc_actif = True
        update_fields.append('parc_actif')
    if update_fields:
        installation.save(update_fields=update_fields)

    return ensure_equipements(installation, user=user)
