"""apps.promotions.services — pont ORM ↔ moteur pur (NTRET12) + coupons à
code unique (NTRET13) + cartes cadeaux (NTRET15).

``engine.py`` ne connaît aucun modèle Django ; ce module charge les
``ReglexPromotion`` actives d'une société, les convertit en structures
``engine.Regle`` neutres, et expose ``evaluer_panier`` — le SEUL point
d'entrée qu'``apps/pos/services.py`` appelle (import fonction-local, jamais
l'inverse — règle de modularité cross-app, CLAUDE.md).
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from . import engine
from .models import ReglexPromotion


def _regle_to_engine(r):
    """Convertit UNE ``ReglexPromotion`` ORM en ``engine.Regle`` neutre."""
    return engine.Regle(
        id=r.id,
        type_regle=r.type_regle,
        priorite=r.priorite,
        cumulable=r.cumulable,
        categorie_id=r.categorie_id,
        produit_id=r.produit_id,
        montant_min_panier=r.montant_min_panier,
        remise_pct=r.remise_pct,
        remise_montant=r.remise_montant,
        n_achete=r.n_achete,
        m_paye=r.m_paye,
        heure_debut=r.heure_debut,
        heure_fin=r.heure_fin,
        jours_semaine=r.jours_semaine or [],
        date_debut=r.date_debut,
        date_fin=r.date_fin,
    )


def _regles_actives(company, *, maintenant=None):
    """Règles actives d'une société, converties en ``engine.Regle`` neutres."""
    qs = ReglexPromotion.objects.filter(company=company, actif=True)
    return [_regle_to_engine(r) for r in qs]


def _lignes_panier(lignes):
    """Convertit des lignes de panier (ex. ``pos.LigneVenteComptoir``, ou
    tout objet portant les mêmes attributs) en ``engine.LignePanier``
    neutres — AUCUN import direct du modèle source ici : l'appelant fournit
    des objets déjà chargés, ce module ne lit que des attributs génériques
    (duck-typing), jamais un modèle spécifique d'une autre app."""
    out = []
    for ligne in lignes:
        produit = getattr(ligne, 'produit', None)
        out.append(engine.LignePanier(
            produit_id=getattr(ligne, 'produit_id', None),
            categorie_id=getattr(produit, 'categorie_id', None),
            quantite=Decimal(str(getattr(ligne, 'quantite', 0) or 0)),
            prix_unitaire_ttc=Decimal(
                str(getattr(ligne, 'prix_unitaire_ttc', 0) or 0)),
        ))
    return out


def evaluer_panier(company, lignes, *, maintenant=None):
    """Évalue les promotions actives de ``company`` contre ``lignes`` (une
    liste de lignes de panier — duck-typées, cf. ``_lignes_panier``).
    Renvoie une liste de ``engine.RemiseAppliquee``. Best-effort côté
    appelant : cette fonction ne lève jamais pour un panier vide/sans
    règle (renvoie simplement ``[]``)."""
    lignes_panier = _lignes_panier(lignes)
    if not lignes_panier:
        return []
    regles = _regles_actives(company, maintenant=maintenant)
    if not regles:
        return []
    return engine.evaluer_promotions(lignes_panier, regles, maintenant=maintenant)


def total_remises_panier(company, lignes, *, maintenant=None):
    """Somme des remises retenues (MAD) — helper pratique pour l'écran
    caisse et pour ``apps.pos.services``."""
    return sum(
        (r.montant for r in evaluer_panier(company, lignes, maintenant=maintenant)),
        Decimal('0'))


# ── NTRET13 — Coupons à code unique ─────────────────────────────────────────
# Distinct de ``compta.CodePromotion`` (campagne marketing générique) — un
# CouponUnique porte une limite d'usage stricte (1×/client ou N× global) et
# est lié à UNE ``ReglexPromotion`` (NTRET12) pour le calcul de la remise.

class CouponError(Exception):
    """Erreur métier sur l'utilisation d'un coupon à code unique (NTRET13)."""


def valider_coupon(company, code, *, client=None):
    """Vérifie qu'un coupon est utilisable MAINTENANT (existe, actif, pas
    expiré, sous sa limite d'usage) — LECTURE SEULE, ne le consomme pas."""
    from .models import CouponUnique, CouponUtilisation

    code = (code or '').strip().upper()
    if not code:
        raise CouponError('Code coupon requis.')
    coupon = CouponUnique.objects.filter(
        company=company, code=code).select_related('regle').first()
    if coupon is None or not coupon.actif:
        raise CouponError('Coupon introuvable ou inactif.')
    if coupon.date_expiration and timezone.localdate() > coupon.date_expiration:
        raise CouponError('Ce coupon a expiré.')

    if coupon.mode_limite == CouponUnique.ModeLimite.UNIQUE_PAR_CLIENT:
        if client is None:
            raise CouponError(
                'Un client est requis pour ce coupon (1 utilisation par client).')
        if CouponUtilisation.objects.filter(coupon=coupon, client=client).exists():
            raise CouponError('Ce client a déjà utilisé ce coupon.')
    else:
        if coupon.utilisations.count() >= coupon.limite_usage:
            raise CouponError("Ce coupon a atteint sa limite d'utilisation.")
    return coupon


def montant_remise_coupon(coupon, lignes, *, maintenant=None):
    """Montant de la remise (MAD) qu'appliquerait la règle liée au coupon
    sur ``lignes`` — LECTURE SEULE, aucune consommation. Réutilise
    ``engine.evaluer_promotions`` avec une liste d'UNE seule règle (le
    comportement cumulable/non-cumulable de la règle unique est trivial :
    elle est toujours retenue si elle s'applique)."""
    lignes_panier = _lignes_panier(lignes)
    if not lignes_panier:
        return Decimal('0')
    remises = engine.evaluer_promotions(
        lignes_panier, [_regle_to_engine(coupon.regle)], maintenant=maintenant)
    return sum((r.montant for r in remises), Decimal('0'))


@transaction.atomic
def consommer_coupon(company, code, lignes, *, client=None, maintenant=None):
    """Valide PUIS consomme un coupon : journalise l'utilisation
    (``CouponUtilisation`` — porte la contrainte 1×/client au niveau DB),
    pose ``utilise_par``/``utilise_le`` à la PREMIÈRE utilisation seulement
    (jamais réécrits ensuite). Renvoie ``(coupon, montant_remise)``."""
    from .models import CouponUtilisation

    coupon = valider_coupon(company, code, client=client)
    CouponUtilisation.objects.create(company=company, coupon=coupon, client=client)
    if coupon.utilise_le is None:
        coupon.utilise_par = client
        coupon.utilise_le = timezone.now()
        coupon.save(update_fields=['utilise_par', 'utilise_le'])
    montant = montant_remise_coupon(coupon, lignes, maintenant=maintenant)
    return coupon, montant


# ── NTRET15 — Cartes cadeaux ─────────────────────────────────────────────────

class CarteCadeauError(Exception):
    """Erreur métier sur une carte cadeau (NTRET15)."""


def _normaliser_code(code):
    return (code or '').strip().upper()


def verifier_carte_cadeau(company, code, *, montant=None):
    """Vérifie qu'une carte cadeau est UTILISABLE maintenant (existe, non
    épuisée, non expirée) et, si ``montant`` est fourni, que le solde le
    couvre. LECTURE SEULE — ne débite jamais."""
    from .models import CarteCadeau

    code = _normaliser_code(code)
    if not code:
        raise CarteCadeauError('Code de carte cadeau requis.')
    carte = CarteCadeau.objects.filter(company=company, code=code).first()
    if carte is None:
        raise CarteCadeauError('Carte cadeau introuvable.')
    if not carte.est_utilisable():
        raise CarteCadeauError(
            f'Carte cadeau {carte.get_statut_display().lower()} — non utilisable.')
    if montant is not None and Decimal(str(montant)) > carte.solde:
        raise CarteCadeauError(
            f'Solde insuffisant sur la carte cadeau ({carte.solde} MAD disponibles).')
    return carte


@transaction.atomic
def debiter_carte_cadeau(company, code, montant):
    """Débite une carte cadeau (NTRET15) — JAMAIS en négatif, plusieurs
    passages possibles jusqu'à épuisement. ``select_for_update`` verrouille
    la ligne pour empêcher une double-dépense concurrente (deux caisses qui
    débitent la même carte en même temps)."""
    from .models import CarteCadeau

    montant = Decimal(str(montant))
    code = _normaliser_code(code)
    carte = CarteCadeau.objects.select_for_update().filter(
        company=company, code=code).first()
    if carte is None:
        raise CarteCadeauError('Carte cadeau introuvable.')
    if not carte.est_utilisable():
        raise CarteCadeauError(
            f'Carte cadeau {carte.get_statut_display().lower()} — non utilisable.')
    if montant > carte.solde:
        raise CarteCadeauError('Solde insuffisant sur la carte cadeau.')

    carte.solde = carte.solde - montant
    if carte.solde <= 0:
        carte.solde = Decimal('0')
        carte.statut = CarteCadeau.Statut.EPUISEE
    carte.save(update_fields=['solde', 'statut'])
    return carte


def emettre_carte_cadeau(company, montant_initial, *, code=None, date_expiration=None):
    """Émet une nouvelle carte cadeau (NTRET15) — le solde de départ =
    ``montant_initial``. ``code`` : physique (carte pré-imprimée saisie),
    sinon généré automatiquement (unique, alphanumérique)."""
    from .models import CarteCadeau

    montant_initial = Decimal(str(montant_initial))
    if montant_initial <= 0:
        raise CarteCadeauError('Le montant initial doit être positif.')
    kwargs = {
        'company': company, 'montant_initial': montant_initial,
        'solde': montant_initial, 'date_expiration': date_expiration,
    }
    code = _normaliser_code(code)
    if code:
        kwargs['code'] = code
    return CarteCadeau.objects.create(**kwargs)
