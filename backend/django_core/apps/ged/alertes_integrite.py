"""ACEL62 — alerte ERP quand le contrôle nocturne trouve une archive légale
altérée ou introuvable (C-ACEL-003).

Hors de `services.py` (fichier-mur) : `verifier_integrite_archives` n'y fait
que choisir les archives à signaler (résultat changé depuis le contrôle
précédent) ; ici, une notification `SECURITY_ALERT` par archive et par
administrateur actif, plus une ligne au résumé des problèmes."""


class ArchiveLegaleCompromise(Exception):
    """Motif consigné au résumé des problèmes (jamais levé)."""


def alerter_archives_compromises(company, archivages):
    """Notifie chaque administrateur actif, archive par archive ; best-effort."""
    from apps.notifications.services import notify_many
    from apps.notifications.types_evenements import EventType
    from apps.reporting.journal_problemes import consigner_echec_tache
    from authentication.models import CustomUser

    from .models import CONTROLE_RESULTAT_ALTERE

    admins = list(CustomUser.admins_actifs_qs(company))
    for archivage, resultat in archivages:
        etat = 'altérée' if resultat == CONTROLE_RESULTAT_ALTERE else 'introuvable'
        notify_many(
            admins, EventType.SECURITY_ALERT,
            f'Archive légale {etat} : « {archivage.document.nom} »',
            body=('Le contrôle d\'intégrité nocturne a trouvé cette archive '
                  f'{etat}. Consultez son dossier de preuve.'),
            company=company)
    noms = ', '.join(a.document.nom for a, _ in archivages[:5])
    consigner_echec_tache('ged.verifier_integrite_archives', ArchiveLegaleCompromise(
        f'{len(archivages)} archive(s) légale(s) altérée(s) ou introuvable(s) : {noms}'))
