"""Purges et rétention (reference/donnees.md §8).

Étape de nuit appelée par `nocturne.executer` (TCH37) ; remplie par TCH75.
"""


def purger(company_id, jour):
    """Nuit du `jour` : rétentions de donnees.md §8 pour la société (PlanJour 400 j, LignePlanJour et
    IncitationCoach 90 j, Rappel clos 30 j, GesteAnnulable 7 j, SuggestionTache 30 j, tâche ou projet
    supprimé 30 j puis suppression dure). Livrée vide par TCH37, remplie par TCH75."""
    return None
