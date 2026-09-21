"""CAD-B — Moteur du TEMPS de la cadence : les règles que `services.py` et
`selectors.py` appliquent, écrites une seule fois et hors des fichiers chauds.

Module PUR au sens des horaires : il ne crée rien, n'écrit rien, ne connaît
aucune vue ni aucun sérialiseur. Il répond à des questions de DATES posées par
le moteur de cadence :

  * `echeance_jamais_echue` (CAD22) — une touche ne naît jamais déjà en
    retard ;
  * `nee_en_retard` (CAD22) — la touche a-t-elle été CRÉÉE après son échéance
    (auquel cas personne n'a jamais eu la chance de la faire à l'heure) ?

La règle du groupe reste entière : ni le NOMBRE, ni l'ORDRE, ni le J+N des
touches ne changent ici — seule change la DATE à laquelle une touche
matérialisée tombe quand cette date serait déjà passée.

Convention de temps : datetimes AWARE partout, raisonnement local
Africa/Casablanca via `apps.crm.horaires` (jamais un `datetime(...)` nu).
"""
from __future__ import annotations

from django.utils import timezone

from . import horaires


# ── CAD-B ── CAD22 ──────────────────────────────────────────────────────────

def echeance_jamais_echue(echeance, *, company, dimanche=False,
                          canal='appel', maintenant=None):
    """CAD22 — l'échéance d'une touche qui NAÎT, jamais dans le passé.

    Les touches naissent dans l'ordre du PROTOCOLE, et leur échéance calculée
    depuis l'ancre était écrite telle quelle : après l'appel du dimanche —
    posé au premier dimanche atteignant J+5, donc entre J+5 et J+11 selon le
    jour d'arrivée — la touche J+7 naissait avec une date DÉJÀ passée. Elle ne
    pouvait alors jamais être « à l'heure » (grain JOUR,
    `selectors._a_lheure`) et le tableau d'adhérence comptait un manquement
    que personne n'avait commis.

    Règle : si l'échéance calculée est antérieure à `maintenant`, la touche
    est posée au PROCHAIN créneau joignable — le dimanche suivant pour une
    touche `dimanche_ok` (le seul rendez-vous dominical du protocole reste un
    dimanche), la prochaine ouverture du canal sinon. Le J+N du protocole
    n'est pas touché : c'est la date de CETTE touche, née en retard, qui est
    ramenée dans le présent.

    Rend l'échéance inchangée quand elle est future (cas normal), ou `None`
    tel quel.
    """
    if echeance is None:
        return echeance
    maintenant = maintenant if maintenant is not None else timezone.now()
    if echeance >= maintenant:
        return echeance
    if dimanche:
        return horaires.prochain_dimanche(maintenant)
    return horaires.prochain_creneau_appel(maintenant, company, canal=canal)


def nee_en_retard(etape):
    """CAD22 — cette touche a-t-elle été CRÉÉE après son échéance ?

    Garde-fou d'adhérence : une touche née en retard n'a jamais donné à la
    commerciale la chance de la faire à l'heure ; la compter comme un
    manquement accuse quelqu'un à tort.

    Ne vaut que pour les touches MATÉRIALISÉES par la cadence réactive —
    celles qui portent leur ancre `cadence_depart` (CKP2). Sur une ligne
    d'avant CKP2, tout le plan était créé d'un bloc à l'initialisation :
    `created_at` n'y dit rien de la naissance d'une touche en particulier, et
    s'en servir inventerait une excuse plutôt que de constater un fait.
    """
    due_at = getattr(etape, 'due_at', None)
    cree_le = getattr(etape, 'created_at', None)
    if due_at is None or cree_le is None:
        return False
    if getattr(etape, 'cadence_depart', None) is None:
        return False
    return cree_le > due_at
