"""Lectures du module ``apps.datarooms`` (groupe NTDOC, P2).

Toute lecture est bornée à une société. La GED n'est JAMAIS lue en important
``ged.models`` : on passe par ``apps.ged.selectors`` (imports fonction-locaux,
qui évitent aussi les cycles au chargement des apps).
"""
from .models import AccesSalleDonnees, SalleDeDonnees, SalleDeDonneesDocument


def salles_for_company(company):
    """Salles de données d'une société (QuerySet)."""
    return SalleDeDonnees.objects.filter(company=company)


def documents_de_salle(salle, *, visibles_seulement=False):
    """Lignes d'appartenance d'une salle, dans l'ordre d'affichage.

    ``visibles_seulement`` filtre ce qui est réellement exposé aux viewers."""
    qs = SalleDeDonneesDocument.objects.filter(
        salle=salle).select_related('document')
    if visibles_seulement:
        qs = qs.filter(visible=True)
    return qs


def documents_ged_disponibles(company):
    """Documents GED de la société, candidats à l'ajout dans une salle.

    Passe par ``ged.selectors`` — jamais d'import de ``ged.models``."""
    from apps.ged.selectors import documents_for_company
    return documents_for_company(company)


def version_courante(document):
    """Version courante d'un document GED (ou None), via ``ged.selectors``."""
    from apps.ged.selectors import latest_version
    return latest_version(document)


def acces_de_salle(salle, *, actifs_seulement=False):
    """NTDOC12 — Accès viewer d'une salle (QuerySet).

    ``actifs_seulement`` ne filtre QUE ce qui est décidable en base (non
    révoqué) : l'expiration, elle, est évaluée à la lecture par
    ``AccesSalleDonnees.est_expire`` — jamais figée en base."""
    qs = AccesSalleDonnees.objects.filter(salle=salle)
    if actifs_seulement:
        qs = qs.filter(revoque=False)
    return qs


def acces_for_company(company):
    """NTDOC12 — Accès viewer d'une société (QuerySet), pour la gestion."""
    return AccesSalleDonnees.objects.filter(company=company)


def salles_pour_source(company, source_type, source_id):
    """NTDOC15 — Salles issues d'un objet métier (lien RETOUR de sa fiche).

    Point d'entrée LECTURE SEULE pour qu'une autre app affiche « cet objet a
    N salles de données » sans importer ``datarooms.models``."""
    if not source_type or not source_id:
        return SalleDeDonnees.objects.none()
    return SalleDeDonnees.objects.filter(
        company=company, source_type=source_type, source_id=source_id)
