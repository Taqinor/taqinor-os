"""Services du rythme (reference/regles.md « Le rythme », « Les sollicitations »).

Étape de nuit appelée par `nocturne.executer` (TCH37) ; remplie par TCH70. Mon rythme, les
propositions et les préférences arrivent avec TCH66-TCH69.
"""


def etapes_nocturnes(company_id, jour):
    """Nuit du `jour` : jour clos, blocs, propositions, dérive, constats (si « Comprendre mon
    rythme »), révélation `revue`, cartes expirées, push `ignoree`, pauses à 14 (api.md §9). Livrée
    vide par TCH37, remplie par TCH70."""
    return None
