"""Services de la journée (reference/regles.md « La journée »).

Étape de nuit appelée par `nocturne.executer` (TCH37) ; remplie par TCH58. Les services du jour
(Garder ces N, ★, Alléger, Bilan) arrivent avec TCH56-TCH58.
"""


def clore_jour_precedent(company_id, jour):
    """Nuit du `jour` : clôt le `PlanJour` de la veille (statut du jour, compteurs) sans toucher aux
    tâches (regles.md « Passage à minuit »). Livrée vide par TCH37, remplie par TCH58."""
    return None
