"""QA-COHERENCE — le registre des règles d'invariants métier.

POURQUOI. Toute la QA automatique du dépôt attrape des PLANTAGES ; un chiffre
faux mais plausible (couverture 28 % au lieu de 37 %, conso = factures ÷ 1,20,
facture qui dépasse son devis…) passe au travers. Sur 30 bugs de « chiffres
faux » historiques, 0 ont été vus par l'automatisation (docs/decisions/COUV-HOR/
audit-qa-complet.md). Ce registre porte des INVARIANTS GÉNÉRIQUES — vrais pour
toute donnée légitime, faux seulement quand quelque chose a dérivé — que le
moteur (``moteur.run_audit``) évalue chaque nuit sur les données réelles.

CONTRAT D'UNE RÈGLE. Une règle est une fonction PURE ``check(obj, ctx)`` qui
LIT (jamais n'écrit) et rend une liste de :class:`Violation`. Elle déclare :

* ``id`` — identifiant stable (clé de l'empreinte, du ``--rules`` de la
  commande et des notifications) ;
* ``libelle`` — une phrase française ;
* ``gravite`` — ``critique`` / ``avertissement`` / ``info`` ;
* ``actif_par_defaut`` — une règle bruyante reste enregistrée mais OFF ;
* ``portee`` — le type d'objet examiné (``devis``, ``facture``) ou
  ``societe`` pour une règle qui interroge la société en bloc (une requête au
  lieu d'une par objet) et rend ses violations directement ;
* ``besoin_rendu`` — la règle lit les données du document construit par le
  moteur de devis (``ctx.donnees_devis``) ; le moteur ne construit alors ces
  données qu'une fois par devis, dans une transaction ANNULÉE.

TOLÉRANCES : toutes ici, dans :data:`TOLERANCES` — jamais un nombre magique
dans une règle.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Callable

GRAVITE_CRITIQUE = 'critique'
GRAVITE_AVERTISSEMENT = 'avertissement'
GRAVITE_INFO = 'info'
GRAVITES = (GRAVITE_CRITIQUE, GRAVITE_AVERTISSEMENT, GRAVITE_INFO)

PORTEE_DEVIS = 'devis'
PORTEE_FACTURE = 'facture'
PORTEE_SOCIETE = 'societe'
PORTEES = (PORTEE_DEVIS, PORTEE_FACTURE, PORTEE_SOCIETE)

# ── Tolérances explicites (une seule table) ─────────────────────────────────
TOLERANCES = {
    # Chaîne HT → remise → TVA → TTC : chaque étage est arrondi au centime,
    # l'écart admis entre un étage stocké et son recalcul est d'UN centime
    # (+ epsilon flottant pour les montants du document construit).
    'centime': 0.011,
    # Facture à montants FIGÉS (tranche d'échéancier) : HT, TVA et TTC sont
    # chacun arrondis indépendamment (``utils.echeancier.next_tranche``) et le
    # solde absorbe les écarts des tranches précédentes — quelques centimes
    # possibles, jamais plus.
    'facture_figee_mad': 0.05,
    # Σ factures actives − Σ avoirs actifs vs total TTC de l'option retenue du
    # devis : la somme des tranches retombe au centime sur le total ; 1 MAD
    # couvre les arrondis cumulés sans masquer une vraie surfacturation.
    'facturation_devis_mad': 1.00,
    # ── Règles « chiffres de l'étude » (portées du prototype COUV-HOR) ──
    'I2_plafond_pts': 1,            # −N % ≤ couverture + 1 pt (tranche haute)
    'I2_plancher_marge_pts': 2,     # −N % ≥ couverture × (1 − part fixe) − 2
    # Couverture ET −N % sont imprimés en ENTIERS : leur écart réel diffère de
    # l'écart imprimé d'au plus 1 pt. Sans cette marge, 11 devis de prod
    # (30/09/2026, −67 % pour 70 %…) sortaient de 0,1-0,4 pt : faux positifs.
    'I2_arrondi_imprime_pts': 1,
    'I4_kwh': 12,                   # conso == Σ factures / 1,20 (± 12 kWh)
    'I4_prix_plat': 1.20,           # prix de repli (MAD/kWh) signé par le bug
    'I5_ratio': 0.10,               # facture actuelle imprimée / factures réelles
    'I6_payback_ratio': 0.30,       # retour imprimé vs prix / économie annuelle
    'I6_eco_vs_facture': 1.001,     # économie annuelle ≤ facture actuelle
    'I7_kwc_ratio': 0.02,           # kWc du bloc horaire vs kWc du devis
    'I10_ratio': 0.03,              # total graphe mensuel vs carte option
}


@dataclass
class Violation:
    """Une violation d'invariant, structurée (jamais une simple chaîne)."""

    regle: str
    gravite: str
    object_type: str
    object_id: int
    reference: str
    company_id: int
    message: str
    valeurs: dict = field(default_factory=dict)
    attendu: object = None
    # Valeurs qui IDENTIFIENT la violation (ex. l'option, la figure) — elles
    # entrent dans l'empreinte ; les MESURES (qui bougent à l'arrondi près)
    # n'y entrent pas, sinon chaque nuit créerait une « nouvelle » alerte.
    cle: dict = field(default_factory=dict)

    @property
    def empreinte(self) -> str:
        brut = json.dumps(
            [self.regle, self.object_type, self.object_id, self.cle],
            sort_keys=True, default=str, ensure_ascii=True)
        return hashlib.sha256(brut.encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class Regle:
    id: str
    libelle: str
    gravite: str
    portee: str
    check: Callable
    actif_par_defaut: bool = True
    besoin_rendu: bool = False

    def violation(self, obj, message, *, valeurs=None, attendu=None, cle=None,
                  object_type=None, object_id=None, reference=None,
                  company_id=None):
        """Fabrique une :class:`Violation` de CETTE règle pour ``obj``."""
        return Violation(
            regle=self.id, gravite=self.gravite,
            object_type=object_type or self.portee,
            object_id=object_id if object_id is not None else obj.pk,
            reference=(reference if reference is not None
                       else (getattr(obj, 'reference', '') or '')),
            company_id=(company_id if company_id is not None
                        else getattr(obj, 'company_id', None)),
            message=message, valeurs=dict(valeurs or {}), attendu=attendu,
            cle=dict(cle or {}))


REGISTRE: dict[str, Regle] = {}


def regle(id, libelle, *, gravite, portee, actif_par_defaut=True,
          besoin_rendu=False):
    """Décorateur d'enregistrement. La fonction décorée reçoit
    ``(regle, obj, ctx)`` et rend une liste de :class:`Violation`."""
    if gravite not in GRAVITES:
        raise ValueError(f'gravité inconnue : {gravite}')
    if portee not in PORTEES:
        raise ValueError(f'portée inconnue : {portee}')

    def _enregistrer(fn):
        if id in REGISTRE:
            raise ValueError(f'règle déjà enregistrée : {id}')
        REGISTRE[id] = Regle(
            id=id, libelle=libelle, gravite=gravite, portee=portee,
            check=fn, actif_par_defaut=actif_par_defaut,
            besoin_rendu=besoin_rendu)
        return fn
    return _enregistrer


def regles_selectionnees(ids=None):
    """Les règles à exécuter : ``ids`` explicites (même désactivées par
    défaut), sinon toutes celles actives par défaut. Un id inconnu lève
    ``KeyError`` — une faute de frappe ne doit jamais auditer « rien »."""
    charger_regles()
    if ids:
        inconnus = [i for i in ids if i not in REGISTRE]
        if inconnus:
            raise KeyError(', '.join(inconnus))
        return [REGISTRE[i] for i in ids]
    return [r for r in REGISTRE.values() if r.actif_par_defaut]


def charger_regles():
    """Importe les modules de règles (l'import les enregistre)."""
    from . import (regles_documents, regles_etude, regles_crm,  # noqa: F401
                   regles_securite)
