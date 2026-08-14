"""apps.promotions.engine — moteur PUR d'évaluation des règles promo panier
(NTRET12).

AUCUNE dépendance ORM : ce module ne connaît ni Django ni la base de données,
il ne reçoit et ne renvoie que des structures Python simples (dataclasses).
Testable isolément (``python -m pytest`` sans settings Django, ou
``python -m compileall``) — le pont ORM ↔ moteur vit dans ``services.py``.

Types de règle (``Regle.type_regle``) :
  * ``remise_pourcentage_produit`` — remise % sur les lignes d'un
    produit/catégorie ciblé (ou tout le panier si aucun ciblage).
  * ``remise_montant_panier`` — remise en montant fixe sur le total du
    panier (plafonnée au total, jamais négative).
  * ``n_pour_m`` — N articles achetés, seulement M payés (ex. 3 pour 2) :
    les unités les MOINS chères du groupe sont offertes.
  * ``plage_horaire`` — happy hour : remise % qui ne s'applique QUE dans la
    fenêtre heure_debut–heure_fin, les jours de semaine configurés.

Règles CUMULABLES : toutes s'additionnent. Règles NON cumulables : elles se
neutralisent entre elles — seule celle de plus haute priorité (plus petit
``priorite``), puis à égalité la plus avantageuse, est retenue.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional


def _q2(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


@dataclass
class LignePanier:
    """Une ligne de panier — structure minimale et neutre, découplée de tout
    modèle ORM (``VenteComptoir``/``LigneVenteComptoir`` ou autre)."""
    produit_id: Optional[int]
    categorie_id: Optional[int]
    quantite: Decimal
    prix_unitaire_ttc: Decimal

    @property
    def total_ttc(self) -> Decimal:
        return _q2(Decimal(str(self.quantite)) * Decimal(str(self.prix_unitaire_ttc)))


@dataclass
class Regle:
    """Une règle de promotion, découplée du modèle ORM ``ReglexPromotion``
    (``services.py`` fait la conversion)."""
    id: object
    type_regle: str
    priorite: int = 100
    cumulable: bool = False
    categorie_id: Optional[int] = None
    produit_id: Optional[int] = None
    montant_min_panier: Optional[Decimal] = None
    remise_pct: Optional[Decimal] = None
    remise_montant: Optional[Decimal] = None
    n_achete: Optional[int] = None
    m_paye: Optional[int] = None
    heure_debut: Optional[datetime.time] = None
    heure_fin: Optional[datetime.time] = None
    jours_semaine: list = field(default_factory=list)  # 0=lundi … 6=dimanche
    date_debut: Optional[datetime.date] = None
    date_fin: Optional[datetime.date] = None


@dataclass
class RemiseAppliquee:
    regle_id: object
    libelle: str
    montant: Decimal


def _regle_active_maintenant(regle: Regle, maintenant: datetime.datetime) -> bool:
    if regle.date_debut and maintenant.date() < regle.date_debut:
        return False
    if regle.date_fin and maintenant.date() > regle.date_fin:
        return False
    if regle.type_regle == 'plage_horaire':
        if regle.jours_semaine and maintenant.weekday() not in regle.jours_semaine:
            return False
        if regle.heure_debut and regle.heure_fin:
            heure = maintenant.time()
            if not (regle.heure_debut <= heure <= regle.heure_fin):
                return False
    return True


def _lignes_concernees(regle: Regle, lignes: list[LignePanier]) -> list[LignePanier]:
    if regle.produit_id:
        return [ligne for ligne in lignes if ligne.produit_id == regle.produit_id]
    if regle.categorie_id:
        return [ligne for ligne in lignes if ligne.categorie_id == regle.categorie_id]
    return list(lignes)


def _evaluer_n_pour_m(regle: Regle, concernees: list[LignePanier]) -> Optional[Decimal]:
    if not regle.n_achete or not regle.m_paye or regle.n_achete <= regle.m_paye:
        return None
    unites = []
    for ligne in concernees:
        prix = Decimal(str(ligne.prix_unitaire_ttc))
        try:
            qte = int(ligne.quantite)
        except (TypeError, ValueError):
            qte = 0
        unites.extend([prix] * qte)
    if len(unites) < regle.n_achete:
        return None
    unites.sort(reverse=True)
    gratuites_par_groupe = regle.n_achete - regle.m_paye
    montant = Decimal('0')
    for i in range(0, len(unites) - regle.n_achete + 1, regle.n_achete):
        groupe = unites[i:i + regle.n_achete]
        offertes = sorted(groupe)[:gratuites_par_groupe]
        montant += sum(offertes, Decimal('0'))
    return montant if montant > 0 else None


def _evaluer_regle(regle: Regle, lignes: list[LignePanier],
                   total_panier: Decimal) -> Optional[RemiseAppliquee]:
    if regle.montant_min_panier and total_panier < Decimal(str(regle.montant_min_panier)):
        return None

    concernees = _lignes_concernees(regle, lignes)
    if not concernees:
        return None

    if regle.type_regle in ('remise_pourcentage_produit', 'plage_horaire'):
        if not regle.remise_pct:
            return None
        montant = sum(
            (ligne.total_ttc * Decimal(str(regle.remise_pct)) / 100 for ligne in concernees),
            Decimal('0'))
        if montant <= 0:
            return None
        libelle = (
            f'Happy hour -{regle.remise_pct}%' if regle.type_regle == 'plage_horaire'
            else f'Remise {regle.remise_pct}%')
        return RemiseAppliquee(regle.id, libelle, _q2(montant))

    if regle.type_regle == 'remise_montant_panier':
        if not regle.remise_montant:
            return None
        montant = min(Decimal(str(regle.remise_montant)), total_panier)
        if montant <= 0:
            return None
        return RemiseAppliquee(regle.id, f'Remise {regle.remise_montant} MAD', _q2(montant))

    if regle.type_regle == 'n_pour_m':
        montant = _evaluer_n_pour_m(regle, concernees)
        if montant is None:
            return None
        return RemiseAppliquee(
            regle.id, f'{regle.n_achete} pour {regle.m_paye}', _q2(montant))

    return None


def evaluer_promotions(lignes: list[LignePanier], regles: list[Regle], *,
                       maintenant: Optional[datetime.datetime] = None,
                       ) -> list[RemiseAppliquee]:
    """Évalue toutes les règles ACTIVES contre le panier à l'instant
    ``maintenant`` (défaut = now). Renvoie les remises RETENUES : les règles
    cumulables s'additionnent toutes ; parmi les règles NON cumulables,
    seule celle de plus haute priorité (plus petit ``priorite``), puis à
    égalité la remise la plus avantageuse, est retenue — les autres se
    neutralisent (jamais appliquées ensemble)."""
    maintenant = maintenant or datetime.datetime.now()
    total_panier = sum((ligne.total_ttc for ligne in lignes), Decimal('0'))

    applicables: list[tuple[Regle, RemiseAppliquee]] = []
    for regle in regles:
        if not _regle_active_maintenant(regle, maintenant):
            continue
        remise = _evaluer_regle(regle, lignes, total_panier)
        if remise is not None:
            applicables.append((regle, remise))

    cumulables = [(r, rem) for r, rem in applicables if r.cumulable]
    non_cumulables = [(r, rem) for r, rem in applicables if not r.cumulable]

    retenues = [rem for _, rem in cumulables]
    if non_cumulables:
        meilleure = min(
            non_cumulables, key=lambda pair: (pair[0].priorite, -pair[1].montant))
        retenues.append(meilleure[1])

    return retenues


def total_remises(lignes: list[LignePanier], regles: list[Regle], *,
                  maintenant: Optional[datetime.datetime] = None) -> Decimal:
    """Somme des remises retenues (helper pratique pour l'appelant)."""
    return sum(
        (r.montant for r in evaluer_promotions(lignes, regles, maintenant=maintenant)),
        Decimal('0'))
