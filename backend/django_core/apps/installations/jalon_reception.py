"""AARG46 — retour arrière d'un chantier réceptionné : symétrique de
``services.notifier_reception_solde_a_facturer`` (YSERV7). Module à part :
``services.py`` est un mur (≥ 2 000 lignes)."""


def defaire_reception(installation, canon_old, canon_new):
    """Retour de RÉCEPTIONNÉ vers un statut antérieur ⇒ jalon RÉCEPTION non
    atteint, ici et au portail : plus de solde « à facturer » ni de jalon
    client « atteint ». Une nouvelle réception le réatteint (même ligne,
    AUD321). RÉCEPTIONNÉ → CLÔTURÉ (en avant) : rien.

    Rend vrai si un jalon a été défait."""
    from apps.portail import services as portail_services

    from .models import Installation, JalonProjet

    ordre = Installation.STATUT_ORDER
    if (canon_old != Installation.Statut.RECEPTIONNE
            or canon_new not in ordre[:ordre.index(canon_old)]):
        return False
    jalon = JalonProjet.objects.filter(
        installation=installation, phase=JalonProjet.Phase.RECEPTION,
        atteint=True).first()
    if jalon is None:
        return False
    jalon.atteint = False
    jalon.save(update_fields=['atteint'])
    portail_services.upsert_jalon_chantier(
        installation.company, installation.id, jalon.phase, jalon.libelle)
    return True
