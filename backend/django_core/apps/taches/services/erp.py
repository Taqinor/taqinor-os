"""Services du pont avec l'ERP (conception/spec-6a-erp.md ; reference/donnees.md invariants 23, 30).

Étape de nuit appelée par `nocturne.executer` (TCH37) ; remplie par TCH75. Convertir et lier une
activité arrivent avec TCH73, les suggestions avec TCH71-TCH72.
"""


def reverifier_liens(company_id, jour):
    """Nuit du `jour` : revérifie le lien ERP des tâches ouvertes de la société (`lien_etat`,
    `lien_libelle`, `lien_verifie_le` ; invariant 23). Livrée vide par TCH37, remplie par TCH75."""
    return None
