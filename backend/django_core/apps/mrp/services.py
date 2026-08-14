"""Services (écritures/orchestration) de l'app `mrp` (Groupe NTMFG)."""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone


def _dec(value):
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001 — valeur non numérique -> 0, jamais de crash.
        return Decimal('0')


def temps_operation_min(operation_gamme, quantite):
    """NTMFG2 — temps prévu d'UNE opération pour `quantite` pièces :
    préparation + (temps unitaire × quantité), borné en bas par le temps
    minimum par lot (ex. changement d'outillage) s'il est renseigné."""
    quantite = _dec(quantite)
    prepa = _dec(operation_gamme.temps_prepa_min)
    unitaire = _dec(operation_gamme.temps_unitaire_min) * quantite
    minimum_lot = _dec(operation_gamme.temps_min_par_lot)
    return max(prepa + unitaire, minimum_lot)


def temps_total_gamme(gamme, quantite):
    """NTMFG2 — temps total prévu de toute la gamme pour `quantite` pièces
    (somme des temps d'opération). Renvoie un `Decimal` (minutes)."""
    total = Decimal('0')
    for operation in gamme.operations.all():
        total += temps_operation_min(operation, quantite)
    return total


# ── NTMFG3 — Ordre de Fabrication capacitaire ────────────────────────────

def _jour_ouvre_suivant(jour):
    """Jour ouvré suivant (lun-ven — calendrier standard marocain par
    défaut). `jour` est un `datetime.date`."""
    suivant = jour + timedelta(days=1)
    while suivant.weekday() >= 5:  # 5=samedi, 6=dimanche.
        suivant += timedelta(days=1)
    return suivant


def instancier_operations_of(of):
    """NTMFG3 — instancie les `OperationOF` depuis la gamme liée (idempotent :
    ne recrée rien si l'OF a déjà ses opérations). Renvoie la liste des
    opérations (existantes ou nouvellement créées)."""
    from .models import OperationOF

    existantes = list(of.operations.all())
    if existantes:
        return existantes
    if not of.gamme_id:
        return []
    created = []
    for og in of.gamme.operations.select_related('poste_charge').order_by('ordre', 'id'):
        created.append(OperationOF.objects.create(
            ordre_fabrication=of, operation_gamme=og,
            poste_charge=og.poste_charge, ordre=og.ordre, libelle=og.libelle))
    return created


def _debut_jour(jour):
    """Combine une `date` en `datetime` aware à minuit (fuseau courant)."""
    naive = timezone.datetime.combine(jour, timezone.datetime.min.time())
    return timezone.make_aware(naive) if timezone.is_naive(naive) else naive


def _fin_jour(jour):
    """Combine une `date` en `datetime` aware en fin de journée."""
    naive = timezone.datetime.combine(
        jour, timezone.datetime.max.time().replace(microsecond=0))
    return timezone.make_aware(naive) if timezone.is_naive(naive) else naive


def planifier_of(of, *, date_debut=None):
    """NTMFG3 — instancie les opérations (si besoin) puis calcule leurs dates
    prévues par un day-bucket scheduler à capacité finie : une opération
    démarre le jour courant du poste ; si son temps prévu dépasse la
    capacité restante du jour courant de CE poste (pour CET OF), elle
    bascule au jour ouvré suivant. Pose `OrdreFabrication.date_debut/fin
    _planifiee`. Idempotent en dates (peut être rappelé)."""
    operations = instancier_operations_of(of)
    if not operations:
        return of

    debut = date_debut or timezone.now()
    premiere_date = debut.date()
    jour_courant = premiere_date
    minutes_utilisees = {}  # poste_id -> minutes déjà planifiées le jour courant.
    jour_par_poste = {}     # poste_id -> jour courant de CE poste.

    for op in operations:
        poste_id = op.poste_charge_id
        capacite_min = _dec(op.poste_charge.capacite_heures_jour) * 60
        temps = (temps_operation_min(op.operation_gamme, of.quantite)
                 if op.operation_gamme_id else Decimal('0'))
        jour_poste = jour_par_poste.get(poste_id, premiere_date)
        utilise = minutes_utilisees.get(poste_id, Decimal('0'))
        if utilise > 0 and utilise + temps > capacite_min:
            jour_poste = _jour_ouvre_suivant(jour_poste)
            utilise = Decimal('0')
        op.date_planifiee = jour_poste
        op.save(update_fields=['date_planifiee'])
        jour_par_poste[poste_id] = jour_poste
        minutes_utilisees[poste_id] = utilise + temps
        if jour_poste > jour_courant:
            jour_courant = jour_poste

    of.date_debut_planifiee = _debut_jour(premiere_date)
    of.date_fin_planifiee = _fin_jour(jour_courant)
    of.save(update_fields=['date_debut_planifiee', 'date_fin_planifiee'])
    return of


def confirmer_of(of, user=None):
    """NTMFG3 — confirme un OF brouillon : instancie ses opérations depuis la
    gamme, calcule les dates prévues (capacité poste), passe le statut à
    `planifie`. Idempotent (rappeler sur un OF déjà planifié ne recrée rien)."""
    from .models import OrdreFabrication

    with transaction.atomic():
        planifier_of(of)
        if of.statut == OrdreFabrication.Statut.BROUILLON:
            of.statut = OrdreFabrication.Statut.PLANIFIE
            of.save(update_fields=['statut'])
    return of
