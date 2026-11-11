"""AARG46 — retour arrière d'un chantier réceptionné : symétrique de
``services.notifier_reception_solde_a_facturer`` (YSERV7). Module à part :
``services.py`` est un mur (≥ 2 000 lignes)."""

# ACSV113 — clé interne de ``custom_data`` (jamais écrivable par le PATCH).
CLE_RECEPTION_DEFAITE = 'date_reception_defaite'


def defaire_jalons_quittes(installation, canon_old, canon_new):
    """Recul de statut ⇒ les jalons des statuts QUITTÉS vers l'arrière ne sont
    plus atteints, ici et au portail (AARG46 : RÉCEPTION, plus de solde « à
    facturer » ; ACSV3 : POSE quittant « Installé », APPRO quittant « Matériel
    commandé »). Un nouveau passage les réatteint (même ligne, AUD321) ; un
    pas en avant (RÉCEPTIONNÉ → CLÔTURÉ) ne défait rien.

    Rend vrai si un jalon a été défait."""
    from apps.portail import services as portail_services

    from .models import Installation, JalonProjet

    Statut, Phase = Installation.Statut, JalonProjet.Phase
    table = {Statut.RECEPTIONNE: Phase.RECEPTION, Statut.INSTALLE: Phase.POSE,
             Statut.MATERIEL_COMMANDE: Phase.APPRO}
    ordre = Installation.STATUT_ORDER
    if canon_old not in ordre or canon_new not in ordre:
        return False
    quittes = ordre[ordre.index(canon_new) + 1:ordre.index(canon_old) + 1]
    if Statut.RECEPTIONNE in quittes:
        _defaire_dates_reception(installation)
    jalons = list(JalonProjet.objects.filter(
        installation=installation, atteint=True,
        phase__in=[table[s] for s in quittes if s in table]))
    for jalon in jalons:
        jalon.atteint = False
        jalon.save(update_fields=['atteint'])
        portail_services.upsert_jalon_chantier(
            installation.company, installation.id, jalon.phase, jalon.libelle)
    return bool(jalons)


def _defaire_dates_reception(installation):
    """ACSV31 — recul depuis « Réceptionné » : ``date_reception`` et
    ``date_reception_definitive`` remises à nul (le diff du chatter les trace),
    l'ancienne réception gardée dans ``custom_data[CLE_RECEPTION_DEFAITE]``
    pour recaler le parc à la prochaine réception (``_apply_reception_handover``)."""
    from . import activity
    ancienne = installation.date_reception
    if ancienne is None and installation.date_reception_definitive is None:
        return
    if ancienne is not None:
        installation.custom_data = {**(installation.custom_data or {}),
                                    CLE_RECEPTION_DEFAITE: ancienne.isoformat()}
        activity.log_note(installation, None, f'Réception du {ancienne:%d/%m/%Y} défaite.')
    installation.date_reception = installation.date_reception_definitive = None
    installation.save(update_fields=['date_reception', 'date_reception_definitive', 'custom_data'])
