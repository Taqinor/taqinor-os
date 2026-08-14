"""apps.promotions.services — pont ORM ↔ moteur pur (NTRET12).

``engine.py`` ne connaît aucun modèle Django ; ce module charge les
``ReglexPromotion`` actives d'une société, les convertit en structures
``engine.Regle`` neutres, et expose ``evaluer_panier`` — le SEUL point
d'entrée qu'``apps/pos/services.py`` appelle (import fonction-local, jamais
l'inverse — règle de modularité cross-app, CLAUDE.md).
"""
from decimal import Decimal

from . import engine
from .models import ReglexPromotion


def _regles_actives(company, *, maintenant=None):
    """Règles actives d'une société, converties en ``engine.Regle`` neutres."""
    qs = ReglexPromotion.objects.filter(company=company, actif=True)
    regles = []
    for r in qs:
        regles.append(engine.Regle(
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
        ))
    return regles


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
