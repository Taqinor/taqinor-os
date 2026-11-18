"""La tâche de nuit `taches.nocturne` (reference/api.md §9 ; reference/donnees.md §8), pour UNE société.

`executer(company_id, jour)` appelle, dans cet ordre, les étapes de la nuit — chacune dans sa propre
transaction : une étape qui lève est journalisée et n'arrête pas les suivantes (sa transaction seule
est défaite). `jour` = date locale du passage (03:00, `Africa/Casablanca`) ; « hier » = `jour` − 1,
calculé par chaque étape. Chaque étape est idempotente : rejouer la nuit ne change rien de plus
(recalcul déterministe, contrainte unique des cartes, purges par date).

Ordre (api.md §9) :
1. `services/journee.clore_jour_precedent` — clôt le `PlanJour` d'hier (TCH58) ; AVANT le rythme, qui
   lit `statut_jour` et `compte_rythme` de ce plan ;
2. `services/rythme.etapes_nocturnes` — rythme, cartes, constats, révélation `revue`, expirations,
   push ignorés, pauses (TCH70) — des cartes d'écran : la nuit n'ENVOIE rien ;
3. `services/erp.reverifier_liens` — revérifie les liens ERP des tâches ouvertes (TCH75) ;
4. `services/purge.purger` — rétentions de donnees.md §8 (TCH75).

Appelée par `sweeps.py` (TCH99), une fois par société active où le module est actif, coupe-circuit
compris (`ReglagesSociete.balayage_actif` ne coupe que l'envoi, `taches.balayer`).
"""
import logging

from django.db import transaction

from apps.taches.services import erp, journee, purge, rythme

logger = logging.getLogger(__name__)

#: (nom, étape) dans l'ordre de la nuit. Chaque étape lit sa fonction AU MOMENT de l'appel : une étape
#: remplie plus tard par sa tâche garde sa place sans toucher ce fichier.
ETAPES = (
    ('clore_jour_precedent', lambda company_id, jour: journee.clore_jour_precedent(company_id, jour)),
    ('etapes_nocturnes', lambda company_id, jour: rythme.etapes_nocturnes(company_id, jour)),
    ('reverifier_liens', lambda company_id, jour: erp.reverifier_liens(company_id, jour)),
    ('purger', lambda company_id, jour: purge.purger(company_id, jour)),
)


def _executer_etape(nom, etape, company_id, jour):
    try:
        with transaction.atomic():
            etape(company_id, jour)
    except Exception:  # noqa: BLE001 — une étape en échec n'arrête pas la nuit (journalisée)
        logger.exception('taches.nocturne : étape %s en échec pour la société %s (%s)', nom, company_id, jour)
        return False
    return True


def executer(company_id, jour):
    """Les étapes de la nuit pour la société `company_id` → `{nom de l'étape: réussie}`, dans l'ordre."""
    return {nom: _executer_etape(nom, etape, company_id, jour) for nom, etape in ETAPES}
