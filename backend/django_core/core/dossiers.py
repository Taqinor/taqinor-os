"""NTWFL18 — chatter et alerte d'échéance du dossier transverse.

Deux responsabilités, toutes deux PURES de tout import métier (``core`` reste
une couche de fondation, contrat import-linter
``core-foundation-is-a-base-layer``) :

1. **Le chatter** (``core.DossierActivity``) — les entrées AUTOMATIQUES
   (changement de statut, rattachement/détachement d'un objet) et les NOTES
   manuelles. L'auteur et la société viennent TOUJOURS du serveur.

2. **L'alerte d'échéance dépassée** — un balayage journalier
   (``notifier_echeances_depassees``) émet ``core.events
   .dossier_echeance_depassee`` pour chaque dossier en retard, UNE SEULE FOIS
   par jour grâce au marqueur ``Dossier.dernier_rappel_echeance_le`` (même
   discipline anti-double-notification que NTWFL5 sur les étapes BPM).
   ``core`` ne connaît aucun canal de notification : il émet sur le bus, et
   c'est ``apps.notifications`` qui décide quoi en faire.

Le « maintenant » est TOUJOURS passé explicitement par l'appelant
(déterminisme testable — même discipline que ``core.workflow``).
"""
from django.db import transaction

from .dates import aujourd_hui_local
from .models import Dossier, DossierActivity

__all__ = [
    'journaliser_creation',
    'journaliser_changement',
    'journaliser_lien',
    'noter',
    'historique',
    'dossiers_echeance_depassee',
    'marquer_rappel_echeance',
    'notifier_echeances_depassees',
]


def _texte(valeur):
    """Rend une valeur affichable dans le chatter (jamais ``None``)."""
    return '' if valeur is None else str(valeur)


def journaliser_creation(dossier, user=None):
    """Première entrée du chatter : le dossier vient d'être ouvert."""
    return DossierActivity.objects.create(
        company=dossier.company, dossier=dossier,
        kind=DossierActivity.KIND_CREATION,
        new_value=dossier.titre, user=user)


def journaliser_changement(dossier, champ, libelle, ancienne, nouvelle,
                           user=None):
    """Entrée AUTOMATIQUE « ancienne → nouvelle » pour un champ suivi.

    Retourne ``None`` si rien n'a bougé : le chatter ne se remplit jamais de
    non-évènements."""
    if _texte(ancienne) == _texte(nouvelle):
        return None
    return DossierActivity.objects.create(
        company=dossier.company, dossier=dossier,
        kind=DossierActivity.KIND_MODIFICATION,
        field=champ, field_label=libelle,
        old_value=_texte(ancienne), new_value=_texte(nouvelle), user=user)


def journaliser_lien(dossier, cle_modele, object_id, *, action='rattache',
                     libelle='', user=None):
    """Entrée AUTOMATIQUE au rattachement/détachement d'un objet métier.

    ``cle_modele`` est la chaîne ``app_label.model`` de la cible : aucun
    import d'app domaine, même pour écrire la ligne de chatter."""
    cible = f'{cle_modele}#{object_id}'
    if libelle:
        cible = f'{cible} — {libelle}'
    detache = action == 'detache'
    return DossierActivity.objects.create(
        company=dossier.company, dossier=dossier,
        kind=DossierActivity.KIND_LIEN,
        field='liens', field_label='Objets liés',
        old_value=cible if detache else '',
        new_value='' if detache else cible,
        user=user)


def noter(dossier, body, user=None):
    """Note MANUELLE (texte libre) ajoutée au chatter."""
    contenu = (body or '').strip()
    if not contenu:
        return None
    return DossierActivity.objects.create(
        company=dossier.company, dossier=dossier,
        kind=DossierActivity.KIND_NOTE, body=contenu, user=user)


def historique(dossier):
    """Le chatter du dossier, du plus récent au plus ancien."""
    return dossier.activites.select_related('user').all()


def dossiers_echeance_depassee(company, aujourd_hui=None):
    """Dossiers ENCORE OUVERTS dont l'échéance est strictement dépassée.

    ``aujourd_hui`` est passé par l'appelant ; à défaut, la date LOCALE
    (Casablanca) — jamais ``date.today()`` du serveur."""
    jour = aujourd_hui or aujourd_hui_local()
    return (Dossier.objects
            .filter(company=company, echeance__lt=jour)
            .exclude(statut__in=Dossier.STATUTS_FERMES)
            .select_related('proprietaire')
            .order_by('echeance', 'id'))


def marquer_rappel_echeance(dossier, aujourd_hui):
    """Pose le marqueur anti-double-alerte du jour (NTWFL5 à la journée)."""
    dossier.dernier_rappel_echeance_le = aujourd_hui
    dossier.save(update_fields=['dernier_rappel_echeance_le', 'updated_at'])
    return dossier


def _emettre_echeance_depassee(dossier):
    """Émission best-effort : une notification cassée ne bloque jamais le
    balayage des dossiers suivants."""
    try:
        from .events import dossier_echeance_depassee
        dossier_echeance_depassee.send(
            sender='core.dossiers', dossier=dossier,
            company=dossier.company, proprietaire=dossier.proprietaire)
    except Exception:  # pragma: no cover - défensif, jamais bloquant
        pass


def notifier_echeances_depassees(company, aujourd_hui=None):
    """Balayage JOURNALIER des échéances dépassées d'une société.

    Émet ``core.events.dossier_echeance_depassee`` pour chaque dossier en
    retard qui n'a pas DÉJÀ été alerté aujourd'hui, puis pose le marqueur.
    Retourne la liste des dossiers effectivement alertés — rejouer le
    balayage le même jour n'émet plus rien.
    """
    jour = aujourd_hui or aujourd_hui_local()
    alertes = []
    for dossier in dossiers_echeance_depassee(company, jour):
        if dossier.dernier_rappel_echeance_le == jour:
            continue
        with transaction.atomic():
            marquer_rappel_echeance(dossier, jour)
        _emettre_echeance_depassee(dossier)
        alertes.append(dossier)
    return alertes
