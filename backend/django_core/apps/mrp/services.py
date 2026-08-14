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


# ── NTMFG4 — Consommation & production de stock (backflush industriel) ──

def _composants_of(of):
    """NTMFG4 — nomenclature résolue pour CET OF (produit_id, quantité TOTALE
    pour `of.quantite` unités), depuis `of.gamme.kit_source` — lecture seule
    via `stock.services.exploser_kit_par_id` (ID-only, jamais d'import du
    modèle `stock.KitProduit`). Renvoie `[]` si l'OF n'a pas de gamme ou que
    sa gamme n'a pas de nomenclature source."""
    if not of.gamme_id or not of.gamme.kit_source_id:
        return []
    from apps.stock.services import exploser_kit_par_id

    lignes = exploser_kit_par_id(of.company_id, of.gamme.kit_source_id, of.quantite) or []
    return [{'produit_id': ligne['produit_id'], 'quantite': ligne['quantite']}
            for ligne in lignes]


def cloturer_of(of, user=None):
    """NTMFG4 — clôture un OF : consomme les composants et produit le
    composite (backflush), EXACTEMENT une fois (idempotence
    `stock_mouvemente`, même garde que XMFG1). Un OF avec un
    `kit_ordre_assemblage` lié ne mouvemente RIEN ici — le mouvement reste
    porté par cet ordre d'assemblage kitting (XMFG1), jamais de double
    mouvement. Un OF sans nomenclature (pas de gamme, ou gamme sans
    `kit_source`) ne mouvemente rien non plus (suivi pur, pas de crash)."""
    from types import SimpleNamespace

    from .models import OrdreFabrication

    with transaction.atomic():
        # select_for_update — même garde de course que XMFG1 (`OrdreAssemblage`).
        locked = OrdreFabrication.objects.select_for_update().get(pk=of.pk)
        if locked.kit_ordre_assemblage_id is None and not locked.stock_mouvemente:
            composants = _composants_of(locked)
            if composants:
                from apps.stock.services import consommer_et_produire_assemblage

                lignes = [
                    SimpleNamespace(
                        produit=SimpleNamespace(id=c['produit_id']),
                        quantite=_dec(c['quantite']))
                    for c in composants
                ]
                consommer_et_produire_assemblage(
                    company=locked.company,
                    kit=SimpleNamespace(id=locked.gamme.kit_source_id),
                    composants=lignes,
                    produit_compose=SimpleNamespace(id=locked.produit_id),
                    quantite_produite=locked.quantite,
                    reference=f'OF-{locked.id}',
                    user=user,
                    per_unit=False,
                )
            locked.stock_mouvemente = True
        locked.statut = OrdreFabrication.Statut.TERMINE
        locked.save(update_fields=['stock_mouvemente', 'statut'])
    return locked


def confirmer_of(of, user=None):
    """NTMFG3/6 — confirme un OF brouillon : instancie ses opérations depuis
    la gamme, calcule les dates prévues (capacité poste), sème les
    réservations de composants (NTMFG6), passe le statut à `planifie`.
    Idempotent (rappeler sur un OF déjà planifié ne recrée/rejoue rien)."""
    from .models import OrdreFabrication

    with transaction.atomic():
        planifier_of(of)
        reserver_composants_of(of)
        if of.statut == OrdreFabrication.Statut.BROUILLON:
            of.statut = OrdreFabrication.Statut.PLANIFIE
            of.save(update_fields=['statut'])
    return of


# ── NTMFG6 — Réservation de composants sur l'Ordre de Fabrication ────────

def reserver_composants_of(of):
    """NTMFG6 — sème les `ReservationOF` depuis la nomenclature résolue de
    l'OF (même source que le backflush NTMFG4, `_composants_of`). Idempotent :
    ne recrée rien si l'OF a déjà des réservations."""
    from .models import ReservationOF

    if of.reservations.exists():
        return list(of.reservations.all())
    composants = _composants_of(of)
    return [
        ReservationOF.objects.create(
            ordre_fabrication=of, produit_id=c['produit_id'],
            quantite=_dec(c['quantite']))
        for c in composants
    ]


def liberer_reservations_of(of):
    """NTMFG6 — libère (supprime) les réservations NON encore consommées de
    cet OF (annulation). Les réservations déjà `consomme=True` (backflush
    passé) sont conservées comme trace historique."""
    from .models import ReservationOF

    return ReservationOF.objects.filter(
        ordre_fabrication=of, consomme=False).delete()[0]


# ── NTMFG7 — Ordonnancement à capacité finie : replanification ──────────

def _parse_date(brut):
    if brut is None:
        return None
    if hasattr(brut, 'isoformat') and not isinstance(brut, str):
        return brut
    from datetime import datetime as _dt
    try:
        return _dt.strptime(str(brut), '%Y-%m-%d').date()
    except ValueError:
        raise ValueError(f'Date invalide : {brut!r} (attendu AAAA-MM-JJ).')


def replanifier_operation(operation, *, nouvelle_date=None, nouveau_poste_id=None,
                          company=None):
    """NTMFG7 — déplace une `OperationOF` (drag & drop Gantt) : nouvelle date
    planifiée et/ou nouveau poste, contrôle de capacité NON BLOQUANT (renvoie
    un avertissement texte si le jour cible dépasse la capacité du poste,
    mais applique quand même le déplacement). Renvoie `(operation,
    avertissement_ou_None)`."""
    from .models import OperationOF, PosteDeCharge

    champs = []
    if nouvelle_date is not None:
        operation.date_planifiee = _parse_date(nouvelle_date)
        champs.append('date_planifiee')
    if nouveau_poste_id is not None:
        poste = PosteDeCharge.objects.filter(
            id=nouveau_poste_id, company=company).first()
        if poste is None:
            raise ValueError('Poste de charge inconnu pour cette société.')
        operation.poste_charge = poste
        champs.append('poste_charge')
    if champs:
        operation.save(update_fields=champs)

    avertissement = None
    if operation.date_planifiee is not None:
        poste = operation.poste_charge
        capacite_min = _dec(poste.capacite_heures_jour) * 60
        statuts_en_charge = ['planifie', 'lance']
        autres = (
            OperationOF.objects
            .filter(
                poste_charge=poste, date_planifiee=operation.date_planifiee,
                ordre_fabrication__statut__in=statuts_en_charge)
            .exclude(id=operation.id)
            .select_related('operation_gamme', 'ordre_fabrication'))
        total = sum(
            (temps_operation_min(op.operation_gamme, op.ordre_fabrication.quantite)
             if op.operation_gamme_id else Decimal('0'))
            for op in autres)
        temps_cette_op = (
            temps_operation_min(
                operation.operation_gamme, operation.ordre_fabrication.quantite)
            if operation.operation_gamme_id else Decimal('0'))
        total += temps_cette_op
        if capacite_min > 0 and total > capacite_min:
            avertissement = (
                f'Surcharge du poste « {poste.nom} » le '
                f'{operation.date_planifiee.isoformat()} : '
                f'{total} min planifiées pour {capacite_min} min de capacité.')
    return operation, avertissement


def annuler_of(of, user=None, motif=''):
    """NTMFG6 — annule un OF : libère ses réservations, passe le statut à
    `annule`. Refuse si le stock a déjà été mouvementé (NTMFG4) — comme
    XMFG4, une annulation ne défait jamais un backflush déjà posé."""
    from .models import OrdreFabrication

    with transaction.atomic():
        locked = OrdreFabrication.objects.select_for_update().get(pk=of.pk)
        if locked.stock_mouvemente:
            raise ValueError(
                "Impossible d'annuler un OF dont le stock a déjà été "
                "mouvementé.")
        liberer_reservations_of(locked)
        locked.statut = OrdreFabrication.Statut.ANNULE
        locked.save(update_fields=['statut'])
    return locked


# ── NTMFG8 — Terminal atelier MES : démarrer/pauser/reprendre/terminer ──

def demarrer_operation(operation, user=None):
    """NTMFG8 — démarre une opération (`a_faire`/`en_pause` -> `en_cours`).
    Pose `demarree_le` UNE seule fois (idempotent : rappeler sur une
    opération déjà en cours ne réinitialise pas l'horodatage)."""
    from .models import OperationOF

    if operation.statut == OperationOF.Statut.TERMINEE:
        raise ValueError('Cette opération est déjà terminée.')
    if operation.statut == OperationOF.Statut.EN_COURS:
        return operation
    if operation.demarree_le is None:
        operation.demarree_le = timezone.now()
    operation.statut = OperationOF.Statut.EN_COURS
    operation.save(update_fields=['statut', 'demarree_le'])
    return operation


def pauser_operation(operation, user=None):
    """NTMFG8 — met l'opération en pause (`en_cours` -> `en_pause`), ouvre
    une `PauseOperationOF` (fin=None). Refuse si l'opération n'est pas en
    cours (idempotence stricte : jamais deux pauses ouvertes)."""
    from .models import OperationOF, PauseOperationOF

    if operation.statut != OperationOF.Statut.EN_COURS:
        raise ValueError('Seule une opération en cours peut être mise en pause.')
    PauseOperationOF.objects.create(operation=operation, debut=timezone.now())
    operation.statut = OperationOF.Statut.EN_PAUSE
    operation.save(update_fields=['statut'])
    return operation


def reprendre_operation(operation, user=None):
    """NTMFG8 — reprend une opération en pause (`en_pause` -> `en_cours`),
    ferme la pause ouverte (`fin=now()`)."""
    from .models import OperationOF

    if operation.statut != OperationOF.Statut.EN_PAUSE:
        raise ValueError('Cette opération n\'est pas en pause.')
    pause_ouverte = operation.pauses.filter(fin__isnull=True).order_by('-debut').first()
    if pause_ouverte is not None:
        pause_ouverte.fin = timezone.now()
        pause_ouverte.save(update_fields=['fin'])
    operation.statut = OperationOF.Statut.EN_COURS
    operation.save(update_fields=['statut'])
    return operation


def _minutes_pauses(operation):
    total = Decimal('0')
    for pause in operation.pauses.all():
        fin = pause.fin or timezone.now()
        total += _dec((fin - pause.debut).total_seconds()) / Decimal('60')
    return total


def terminer_operation(operation, *, quantite_bonne=0, quantite_rebut=0,
                       motif_rebut='', user=None):
    """NTMFG8 — termine une opération : ferme une pause ouverte s'il y en a
    une, calcule le temps ACTIF réel (temps écoulé depuis `demarree_le` MOINS
    les pauses), enregistre quantité bonne/rebut. Un rebut > 0 exige un motif
    et poste un `MouvementStock` SORTIE typé rebut (XMFG11) sur le produit
    fabriqué de l'OF — INDÉPENDANT du backflush de clôture (NTMFG4), qui
    continue à produire `OrdreFabrication.quantite` (simplification
    documentée : la réconciliation fine quantité-planifiée vs quantité-bonne-
    réelle reste un TODO explicite, hors du périmètre de ce ticket)."""
    from types import SimpleNamespace

    from .models import OperationOF

    if operation.statut == OperationOF.Statut.TERMINEE:
        raise ValueError('Cette opération est déjà terminée.')
    if quantite_rebut and _dec(quantite_rebut) > 0 and not motif_rebut:
        raise ValueError('Un motif est requis pour déclarer un rebut.')

    with transaction.atomic():
        # Ferme une éventuelle pause ouverte (reprise implicite).
        pause_ouverte = operation.pauses.filter(fin__isnull=True).first()
        if pause_ouverte is not None:
            pause_ouverte.fin = timezone.now()
            pause_ouverte.save(update_fields=['fin'])

        operation.terminee_le = timezone.now()
        if operation.demarree_le is not None:
            brut_min = _dec(
                (operation.terminee_le - operation.demarree_le).total_seconds()
            ) / Decimal('60')
            operation.temps_reel_min = max(
                brut_min - _minutes_pauses(operation), Decimal('0'))
        operation.quantite_bonne = _dec(quantite_bonne)
        operation.quantite_rebut = _dec(quantite_rebut)
        operation.motif_rebut = motif_rebut or ''
        operation.statut = OperationOF.Statut.TERMINEE
        operation.save(update_fields=[
            'terminee_le', 'temps_reel_min', 'quantite_bonne',
            'quantite_rebut', 'motif_rebut', 'statut'])

        if operation.quantite_rebut > 0:
            from apps.stock.services import declarer_rebut

            of = operation.ordre_fabrication
            declarer_rebut(
                company=of.company,
                produit=SimpleNamespace(id=of.produit_id),
                quantite=operation.quantite_rebut,
                motif=motif_rebut,
                reference=f'OF-{of.id}-OP-{operation.id}',
                note=f'Rebut atelier — {operation.libelle}',
                user=user)
    return operation
