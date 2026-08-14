"""NTWMS38 — Garde hazmat du rangement guidé.

``casier_accepte_produit`` est le point de vérité UNIQUE : le put-away
(NTWMS2) et l'écran de suggestion l'appellent, personne ne re-code la règle.
"""


def classes_autorisees_casier(company, bin_id):
    """Ensemble des classes de danger explicitement autorisées sur ce casier."""
    from .models import CompatibiliteHazmatCasier
    return set(CompatibiliteHazmatCasier.objects
               .filter(company=company, bin_id=bin_id)
               .values_list('classe_danger', flat=True))


def casier_accepte_produit(company, bin_id, produit):
    """Vrai si ce casier peut recevoir ce produit.

    * produit NON dangereux (``classe_danger`` = AUCUNE ou vide) : toujours
      accepté — c'est le comportement historique, inchangé ;
    * produit dangereux : accepté UNIQUEMENT si le casier porte explicitement
      sa classe. Un casier « nu » n'est jamais présumé compatible.
    """
    from .models import Produit

    classe = (getattr(produit, 'classe_danger', '') or '').strip()
    if not classe or classe == Produit.ClasseDanger.AUCUNE:
        return True
    if bin_id is None:
        return False
    return classe in classes_autorisees_casier(company, bin_id)


def casiers_compatibles_ids(company, produit, bin_ids):
    """Sous-liste de ``bin_ids`` compatible avec ce produit (ordre préservé)."""
    return [bid for bid in (bin_ids or [])
            if casier_accepte_produit(company, bid, produit)]


def suggerer_bin_hazmat_safe(company, produit, emplacement_id, quantite):
    """Suggestion de rangement FILTRÉE par la compatibilité hazmat.

    Enveloppe ``installations.selectors.suggerer_bin_putaway`` (FG320/ZSTK9,
    lu par selector — jamais un modèle importé) : si le casier proposé n'est
    pas compatible, on parcourt les casiers de l'emplacement par ordre de
    parcours et on retient le premier qui l'est. Aucun casier compatible →
    ``None`` (le magasinier range librement, jamais un casier interdit
    suggéré par défaut).
    """
    from apps.installations.selectors import suggerer_bin_putaway

    from .models import Produit as ProduitModel

    if not hasattr(produit, 'classe_danger'):
        # Un ID a été passé : on RÉSOUT le produit, sinon `classe_danger`
        # serait lu comme absent et une batterie lithium passerait pour
        # inoffensive (le bug exact que cette garde existe pour éviter).
        produit = ProduitModel.objects.filter(
            id=produit, company=company).first()
        if produit is None:
            return None
    produit_id = produit.id
    bin_loc = suggerer_bin_putaway(
        company, produit_id, emplacement_id, quantite or 0)
    if bin_loc is None:
        return None
    if casier_accepte_produit(company, bin_loc.id, produit):
        return bin_loc

    from apps.installations.models import BinLocation
    candidats = BinLocation.objects.filter(company=company, archived=False)
    if emplacement_id:
        candidats = candidats.filter(emplacement_id=emplacement_id)
    for candidat in candidats.order_by('ordre', 'code'):
        if casier_accepte_produit(company, candidat.id, produit):
            return candidat
    return None
