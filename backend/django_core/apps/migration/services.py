"""Services d'orchestration du groupe NTMIG.

Toute écriture de données métier est DÉLÉGUÉE à ``apps.dataimport`` (dry-run /
commit / ExternalRef / ImportJob) ou aux ``services.py`` des apps cibles —
jamais un import direct de leurs modèles, jamais un second importateur, jamais
un second journal.

NTMIG5 — la garde « pas de succès sans reconcile » : un lot ne devient
``reconcilie`` (et un projet ``termine``) que si son dernier rapport est
``conforme`` OU s'il porte une dérogation explicite, motivée et attribuée.
"""
from django.utils import timezone

from .models import LotMigration, ProjetMigration


class ReconcileBloque(ValueError):
    """Clôture refusée : réconciliation non conforme et non dérogée.

    Porte la liste des ``ecarts`` bloquants pour que l'appelant (endpoint,
    écran) puisse les afficher au lieu d'un simple « échec ».
    """

    def __init__(self, message, ecarts=None):
        super().__init__(message)
        self.ecarts = ecarts or []


def deroger_reconcile(lot, motif, user):
    """Enregistre une dérogation explicite — bool + motif + qui + quand.

    C'est la SEULE porte de sortie d'un lot non conforme : elle exige un motif
    non vide et laisse une trace attribuée (jamais une dérogation anonyme ni
    silencieuse). Écrit uniquement les champs de dérogation (``update_fields``)
    pour ne rien écraser d'autre sur le lot.
    """
    if not motif or not motif.strip():
        raise ValueError('Une dérogation exige un motif explicite.')
    lot.derogation_reconcile = True
    lot.derogation_motif = motif.strip()
    lot.derogation_par = user if getattr(user, 'pk', None) else None
    lot.derogation_at = timezone.now()
    lot.save(update_fields=[
        'derogation_reconcile', 'derogation_motif', 'derogation_par',
        'derogation_at', 'updated_at'])
    return lot


def ecarts_bloquants(lot):
    """Écarts qui EMPÊCHENT de clôturer ``lot`` — ``[]`` s'il est clôturable.

    Ordre de décision : un rapport conforme libère ; sinon une dérogation
    libère ; sinon on renvoie les écarts (ou l'absence même de rapport, qui
    est l'écart le plus grave : « migration réussie » jamais affirmée sans
    preuve).
    """
    rapport = lot.rapports.order_by('-created_at').first()
    if rapport is not None and rapport.conforme:
        return []
    if lot.derogation_reconcile:
        return []
    if rapport is None:
        return [{'type': 'sans_rapport',
                 'detail': 'Aucun rapport de réconciliation pour ce lot.'}]
    return list(rapport.ecarts) or [{
        'type': 'non_conforme',
        'detail': 'Rapport de réconciliation non conforme.'}]


def marquer_lot_termine(lot, user=None):
    """Passe un lot en ``reconcilie`` — refuse sinon (``ReconcileBloque``).

    Un lot dont le rapport n'est pas conforme et qui n'est pas dérogé RESTE
    ``charge`` : jamais ``reconcilie``, jamais ``termine``.
    """
    bloquants = ecarts_bloquants(lot)
    if bloquants:
        raise ReconcileBloque(
            "Le lot n'est pas réconcilié : rapport non conforme et aucune "
            "dérogation motivée.", ecarts=bloquants)
    if lot.statut != LotMigration.Statut.RECONCILIE:
        lot.statut = LotMigration.Statut.RECONCILIE
        lot.save(update_fields=['statut', 'updated_at'])
    return lot


def terminer_projet(projet, user=None):
    """Clôture un projet — refuse tant qu'un lot n'est pas conforme/dérogé.

    Vérifie TOUS les lots AVANT d'en marquer un seul : une clôture refusée ne
    laisse jamais un projet à moitié clôturé. L'erreur porte, par lot, la
    liste des écarts bloquants (rendue telle quelle en 400 par l'endpoint).
    """
    lots = list(projet.lots.all())
    bloquants = []
    for lot in lots:
        ecarts = ecarts_bloquants(lot)
        if ecarts:
            bloquants.append({
                'lot': lot.pk, 'entite': lot.entite, 'ecarts': ecarts})
    if bloquants:
        raise ReconcileBloque(
            'Des lots ne sont pas réconciliés ni dérogés : clôture refusée.',
            ecarts=bloquants)

    for lot in lots:
        marquer_lot_termine(lot, user=user)
    projet.statut = ProjetMigration.Statut.TERMINE
    projet.date_fin = timezone.now()
    projet.save(update_fields=['statut', 'date_fin', 'updated_at'])
    return projet
