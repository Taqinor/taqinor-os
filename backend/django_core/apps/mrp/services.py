"""Services (écritures/orchestration) de l'app `mrp` (Groupe NTMFG)."""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
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
    """NTMFG8/10 — démarre une opération (`a_faire`/`en_pause` -> `en_cours`).
    Pose `demarree_le` UNE seule fois (idempotent : rappeler sur une
    opération déjà en cours ne réinitialise pas l'horodatage). Si le poste
    est sous-traité (NTMFG10), confie les composants réservés de l'OF au
    sous-traitant (best-effort, ne bloque jamais le démarrage)."""
    from .models import OperationOF

    if operation.statut == OperationOF.Statut.TERMINEE:
        raise ValueError('Cette opération est déjà terminée.')
    if operation.statut == OperationOF.Statut.EN_COURS:
        return operation
    deja_demarree = operation.demarree_le is not None
    if operation.demarree_le is None:
        operation.demarree_le = timezone.now()
    operation.statut = OperationOF.Statut.EN_COURS
    operation.save(update_fields=['statut', 'demarree_le'])
    if not deja_demarree:
        transferer_composants_sous_traitance(operation, user=user)
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
                       motif_rebut='', cout_faconnage=0, user=None):
    """NTMFG8/10 — termine une opération : ferme une pause ouverte s'il y en a
    une, calcule le temps ACTIF réel (temps écoulé depuis `demarree_le` MOINS
    les pauses), enregistre quantité bonne/rebut. Un rebut > 0 exige un motif
    et poste un `MouvementStock` SORTIE typé rebut (XMFG11) sur le produit
    fabriqué de l'OF — INDÉPENDANT du backflush de clôture (NTMFG4), qui
    continue à produire `OrdreFabrication.quantite` (simplification
    documentée : la réconciliation fine quantité-planifiée vs quantité-bonne-
    réelle reste un TODO explicite, hors du périmètre de ce ticket). Si le
    poste est sous-traité (NTMFG10), rapatrie les composants confiés et
    enregistre `cout_faconnage` (interne, jamais client-facing)."""
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
        operation.cout_faconnage = _dec(cout_faconnage)
        operation.statut = OperationOF.Statut.TERMINEE
        operation.save(update_fields=[
            'terminee_le', 'temps_reel_min', 'quantite_bonne',
            'quantite_rebut', 'motif_rebut', 'cout_faconnage', 'statut'])

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

        rapatrier_composants_sous_traitance(operation, user=user)
    return operation


# ── NTMFG10 — Sous-traitance d'opération générique ───────────────────────

def _est_operation_sous_traitee(operation):
    from .models import PosteDeCharge

    poste = operation.poste_charge
    return (poste.type_poste == PosteDeCharge.TypePoste.SOUS_TRAITE
            and poste.sous_traitant_id is not None)


def transferer_composants_sous_traitance(operation, user=None):
    """NTMFG10 — à l'entrée dans une opération sur un poste sous-traité
    (`PosteDeCharge.type_poste=sous_traite` + `sous_traitant` renseigné),
    confie les composants RÉSERVÉS de l'OF (NTMFG6) au sous-traitant : un
    `TransfertStock` du dépôt principal vers l'emplacement dédié « chez
    {sous-traitant} » (pattern XMFG16, réutilise
    `stock.services.get_or_create_emplacement_soustraitant`). No-op si le
    poste n'est pas sous-traité. BEST-EFFORT : une ligne en stock
    insuffisant est ignorée (jamais bloquant pour le démarrage MES)."""
    if not _est_operation_sous_traitee(operation):
        return []
    from apps.stock.services import (
        ensure_emplacements, get_or_create_emplacement_soustraitant, transfer_stock,
    )

    of = operation.ordre_fabrication
    poste = operation.poste_charge
    principal = ensure_emplacements(of.company)
    destination = get_or_create_emplacement_soustraitant(
        of.company, poste.sous_traitant.nom)
    transferts = []
    for reservation in of.reservations.filter(consomme=False):
        try:
            quantite = int(reservation.quantite)
        except (TypeError, ValueError):
            continue
        if quantite <= 0:
            continue
        try:
            transferts.append(transfer_stock(
                company=of.company, user=user, produit_id=reservation.produit_id,
                source_id=principal.id, destination_id=destination.id,
                quantite=quantite,
                note=f'Sous-traitance OF-{of.id} — {poste.nom}'))
        except ValueError:
            continue
    return transferts


def rapatrier_composants_sous_traitance(operation, user=None):
    """NTMFG10 — à la clôture d'une opération sous-traitée, rapatrie (best-
    effort) les composants encore « chez {sous-traitant} » vers le dépôt
    principal — symétrique de `transferer_composants_sous_traitance`. No-op
    si le poste n'est pas sous-traité."""
    if not _est_operation_sous_traitee(operation):
        return []
    from apps.stock.services import (
        ensure_emplacements, get_or_create_emplacement_soustraitant, transfer_stock,
    )

    of = operation.ordre_fabrication
    poste = operation.poste_charge
    principal = ensure_emplacements(of.company)
    source = get_or_create_emplacement_soustraitant(of.company, poste.sous_traitant.nom)
    transferts = []
    for reservation in of.reservations.filter(consomme=False):
        try:
            quantite = int(reservation.quantite)
        except (TypeError, ValueError):
            continue
        if quantite <= 0:
            continue
        try:
            transferts.append(transfer_stock(
                company=of.company, user=user, produit_id=reservation.produit_id,
                source_id=source.id, destination_id=principal.id,
                quantite=quantite,
                note=f'Retour sous-traitance OF-{of.id} — {poste.nom}'))
        except ValueError:
            continue
    return transferts


def cout_operation_sous_traitee(operation):
    """NTMFG10 — coût INTERNE d'une opération sous-traitée : Σ(quantité
    réservée × coût d'achat courant du composant) + `cout_faconnage`.
    JAMAIS client-facing (même règle que `Produit.prix_achat`, DC28)."""
    from apps.stock.services import cout_achat_courant

    of = operation.ordre_fabrication
    cout_composants = Decimal('0')
    for reservation in of.reservations.select_related('produit').all():
        if reservation.produit is None:
            continue
        prix = cout_achat_courant(reservation.produit) or Decimal('0')
        cout_composants += _dec(prix) * _dec(reservation.quantite)
    return cout_composants + _dec(operation.cout_faconnage)


# ── NTMFG11 — Coût de revient standard vs réel (référence entreprise) ────

def calculer_cout_matiere_standard(gamme):
    """NTMFG11 — coût matière standard POUR 1 UNITÉ : Σ(quantité composant
    pour 1 unité × `stock.services.cout_achat_courant`). 0 si la gamme n'a
    pas de `kit_source` (pas de nomenclature connue)."""
    if not gamme.kit_source_id:
        return Decimal('0')
    from apps.stock.selectors import get_produit_scoped
    from apps.stock.services import cout_achat_courant, exploser_kit_par_id

    lignes = exploser_kit_par_id(gamme.company_id, gamme.kit_source_id, 1) or []
    total = Decimal('0')
    for ligne in lignes:
        produit = get_produit_scoped(gamme.company_id, ligne['produit_id'])
        if produit is None:
            continue
        prix = cout_achat_courant(produit) or Decimal('0')
        total += _dec(prix) * _dec(ligne['quantite'])
    return total


def calculer_cout_main_oeuvre_standard(gamme):
    """NTMFG11 — coût main-d'œuvre standard POUR 1 UNITÉ : Σ(temps standard
    de chaque opération pour 1 unité ÷ 60 × coût horaire de son poste)."""
    total = Decimal('0')
    for operation in gamme.operations.select_related('poste_charge').all():
        temps_h = temps_operation_min(operation, 1) / Decimal('60')
        total += temps_h * _dec(operation.poste_charge.cout_horaire)
    return total


def figer_cout_standard(company, produit, gamme, *, cout_indirect_pct=0,
                        date_effective=None, user=None):
    """NTMFG11 — calcule et FIGE une nouvelle version de coût standard pour
    `produit` (roll-up nomenclature + gamme). Ne modifie JAMAIS une version
    existante — la version suivante est `max(version existante) + 1`."""
    from .models import CoutStandard

    date_effective = date_effective or timezone.localdate()
    derniere = (
        CoutStandard.objects.filter(company=company, produit=produit)
        .order_by('-version').first())
    version = (derniere.version + 1) if derniere else 1
    return CoutStandard.objects.create(
        company=company, produit=produit, version=version,
        cout_matiere=calculer_cout_matiere_standard(gamme),
        cout_main_oeuvre=calculer_cout_main_oeuvre_standard(gamme),
        cout_indirect_pct=_dec(cout_indirect_pct),
        date_effective=date_effective)


# ── NTMFG14 — Maintenance préventive des postes de charge ────────────────

def _usage_minutes_depuis_reset(poste, today=None):
    """NTMFG14 — cumul des minutes RÉELLES (NTMFG8, opérations terminées) de
    CE poste depuis la dernière réinitialisation du compteur
    (`PosteDeCharge.usage_reinitialise_le`), ou depuis sa création si le
    compteur n'a jamais été réinitialisé."""
    from .models import OperationOF

    depuis = poste.usage_reinitialise_le or poste.created_at
    total = (
        OperationOF.objects
        .filter(poste_charge=poste, statut='terminee', terminee_le__gte=depuis)
        .aggregate(total=Sum('temps_reel_min'))['total'] or 0)
    return _dec(total)


def generer_echeances_poste(plan, today=None):
    """NTMFG14 — génère (idempotent) la PROCHAINE échéance d'un plan actif,
    par intervalle de jours et/ou par heures d'usage cumulées depuis la
    dernière réinitialisation du compteur (NTMFG8). Ne crée jamais de
    doublon : no-op tant qu'une échéance `a_faire`/`planifie` est déjà
    ouverte pour ce plan. Renvoie l'échéance créée, ou `None`."""
    from .models import EcheanceEntretienPoste

    today = today or timezone.localdate()
    if not plan.actif:
        return None
    ouverte = plan.echeances.filter(
        statut__in=[EcheanceEntretienPoste.Statut.A_FAIRE,
                    EcheanceEntretienPoste.Statut.PLANIFIE]).exists()
    if ouverte:
        return None

    doit_generer = False
    if plan.intervalle_jours:
        derniere = plan.echeances.order_by('-date_prevue').first()
        if derniere is None:
            doit_generer = True
        else:
            base = derniere.date_realisee or derniere.date_prevue
            if today >= base + timedelta(days=int(plan.intervalle_jours)):
                doit_generer = True
    if not doit_generer and plan.intervalle_heures_usage:
        usage_heures = _usage_minutes_depuis_reset(
            plan.poste_charge, today) / Decimal('60')
        if usage_heures >= _dec(plan.intervalle_heures_usage):
            doit_generer = True

    if not doit_generer:
        return None
    return EcheanceEntretienPoste.objects.create(plan=plan, date_prevue=today)


def generer_echeances_entretien(company, today=None):
    """NTMFG14 — génère les échéances dues pour TOUS les plans actifs de
    `company` (appelé par la commande de gestion ou manuellement). Renvoie
    la liste des échéances créées."""
    from .models import PlanEntretienPoste

    today = today or timezone.localdate()
    creees = []
    for plan in PlanEntretienPoste.objects.filter(
            poste_charge__company=company, actif=True):
        echeance = generer_echeances_poste(plan, today=today)
        if echeance is not None:
            creees.append(echeance)
    return creees


def cloturer_echeance_entretien(echeance, *, date_realisee=None, note=''):
    """NTMFG14 — clôture une échéance (`fait`) et remet À ZÉRO le compteur
    d'usage du poste (`PosteDeCharge.usage_reinitialise_le`) quand le plan
    est basé sur les heures d'usage — la prochaine échéance ne se
    redéclenchera qu'après un nouveau cumul complet."""
    from .models import EcheanceEntretienPoste

    with transaction.atomic():
        echeance.statut = EcheanceEntretienPoste.Statut.FAIT
        echeance.date_realisee = date_realisee or timezone.localdate()
        echeance.note = note or ''
        echeance.save(update_fields=['statut', 'date_realisee', 'note'])
        if echeance.plan.intervalle_heures_usage:
            poste = echeance.plan.poste_charge
            poste.usage_reinitialise_le = timezone.now()
            poste.save(update_fields=['usage_reinitialise_le'])
    return echeance


# ── NTMFG32 — Rappel proactif J-7 d'échéance d'entretien de poste ────────

def echeances_a_relancer_j7(company, today=None):
    """NTMFG32 — échéances `a_faire` de `company` dont `date_prevue` tombe
    dans les 7 prochains jours (J-7, INCLUS — comprise entre aujourd'hui et
    aujourd'hui+7), jamais encore notifiées (`notifie=False`). Ne remonte
    JAMAIS une échéance déjà en retard (`date_prevue < today`, couverte par
    l'alerte NON bloquante existante `selectors.postes_en_alerte_maintenance`,
    pas ce rappel proactif) — lecture seule."""
    from .models import EcheanceEntretienPoste

    today = today or timezone.localdate()
    seuil = today + timedelta(days=7)
    return (EcheanceEntretienPoste.objects
            .filter(plan__poste_charge__company=company,
                    statut=EcheanceEntretienPoste.Statut.A_FAIRE,
                    notifie=False,
                    date_prevue__gte=today, date_prevue__lte=seuil)
            .select_related('plan__poste_charge'))


def notifier_echeances_j7(company, *, today=None):
    """NTMFG32 — notifie (best-effort, `notifications.notify_many`, réutilise
    `EventType.MAINTENANCE_DUE` — même reprise que `apps.qhse.services`)
    le responsable atelier pour chaque échéance due à J-7
    (`echeances_a_relancer_j7`), puis pose `notifie=True` pour ne JAMAIS la
    renotifier. Renvoie la liste des échéances notifiées."""
    from .models import EcheanceEntretienPoste

    notifiees = []
    for echeance in echeances_a_relancer_j7(company, today=today):
        try:
            from apps.notifications.models import EventType
            from apps.notifications.services import notify_many, resolve_recipients

            poste = echeance.plan.poste_charge
            recipients = resolve_recipients(company, EventType.MAINTENANCE_DUE)
            notify_many(
                recipients, EventType.MAINTENANCE_DUE,
                title=f'Entretien à échéance proche — {poste.nom}',
                body=(f'{echeance.plan.description} : échéance prévue le '
                      f'{echeance.date_prevue.isoformat()} (J-7).'),
                link='/mrp/oee', company=company)
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            continue
        EcheanceEntretienPoste.objects.filter(pk=echeance.pk).update(notifie=True)
        notifiees.append(echeance)
    return notifiees


# ── NTMFG15 — PLM léger : Ordres de Modification (ECO) ───────────────────

def appliquer_eco(eco):
    """NTMFG15 — applique les changements d'un ECO `approuve` (idempotent :
    un ECO déjà `applique` n'est jamais rejoué). Un ECO `gamme`/`les_deux`
    active la VERSION de `Gamme` déjà créée (NTMFG2) désignée par
    `changements['gamme_id']` (les autres versions du même produit repassent
    `actif=False`). Un ECO `nomenclature`/`les_deux` pointe la gamme ACTIVE
    courante du produit vers `changements['kit_source_id']`. Les OF déjà
    LANCÉS gardent leur `gamme` figée — AUCUNE rétroactivité, leur FK
    `OrdreFabrication.gamme` n'est jamais touchée ici."""
    from .models import Gamme, OrdreModification

    if eco.statut == OrdreModification.Statut.APPLIQUE:
        return eco
    if eco.statut != OrdreModification.Statut.APPROUVE:
        raise ValueError('Seul un ECO approuvé peut être appliqué.')

    with transaction.atomic():
        changements = eco.changements or {}

        gamme_id = changements.get('gamme_id')
        if gamme_id and eco.type_eco in (
                OrdreModification.TypeEco.GAMME, OrdreModification.TypeEco.LES_DEUX):
            nouvelle = Gamme.objects.filter(
                id=gamme_id, company=eco.company, produit=eco.produit).first()
            if nouvelle is not None:
                Gamme.objects.filter(
                    company=eco.company, produit=eco.produit
                ).exclude(id=nouvelle.id).update(actif=False)
                if not nouvelle.actif:
                    nouvelle.actif = True
                    nouvelle.save(update_fields=['actif'])

        kit_source_id = changements.get('kit_source_id')
        if kit_source_id and eco.type_eco in (
                OrdreModification.TypeEco.NOMENCLATURE, OrdreModification.TypeEco.LES_DEUX):
            gamme_active = (
                Gamme.objects.filter(
                    company=eco.company, produit=eco.produit, actif=True)
                .order_by('-version').first())
            if gamme_active is not None:
                gamme_active.kit_source_id = kit_source_id
                gamme_active.save(update_fields=['kit_source'])

        eco.statut = OrdreModification.Statut.APPLIQUE
        eco.applique_le = timezone.now()
        eco.save(update_fields=['statut', 'applique_le'])
    return eco


def approuver_eco(eco, user=None):
    """NTMFG15 — passe l'ECO en `approuve`. Si `date_effectivite` est déjà
    atteinte (ou absente = immédiat), applique aussitôt (`appliquer_eco`) ;
    sinon reste en attente du sweep périodique (`sweep_ecos_effectivite`)."""
    from .models import OrdreModification

    if eco.statut not in (
            OrdreModification.Statut.BROUILLON, OrdreModification.Statut.EN_REVUE):
        raise ValueError('Seul un ECO brouillon/en revue peut être approuvé.')
    with transaction.atomic():
        eco.statut = OrdreModification.Statut.APPROUVE
        eco.approbateur = user if getattr(user, 'is_authenticated', False) else None
        eco.save(update_fields=['statut', 'approbateur'])
        today = timezone.localdate()
        if eco.date_effectivite is None or eco.date_effectivite <= today:
            appliquer_eco(eco)
    eco.refresh_from_db()
    return eco


def rejeter_eco(eco):
    """NTMFG15 — rejette l'ECO : AUCUN changement n'est appliqué, jamais.
    Refuse si l'ECO est déjà `applique` (un ECO appliqué ne se rejette
    plus — créer un nouvel ECO)."""
    from .models import OrdreModification

    if eco.statut == OrdreModification.Statut.APPLIQUE:
        raise ValueError('Un ECO déjà appliqué ne peut plus être rejeté.')
    eco.statut = OrdreModification.Statut.REJETE
    eco.save(update_fields=['statut'])
    return eco


def sweep_ecos_effectivite(company, today=None):
    """NTMFG15 — balaie les ECO `approuve` de `company` dont la date
    d'effectivité est atteinte et les applique (pattern beat existant :
    commande de gestion appelable manuellement ou par planificateur).
    Renvoie la liste des ECO appliqués."""
    from .models import OrdreModification

    today = today or timezone.localdate()
    appliques = []
    qs = OrdreModification.objects.filter(
        company=company, statut=OrdreModification.Statut.APPROUVE,
        date_effectivite__isnull=False, date_effectivite__lte=today)
    for eco in qs:
        appliquer_eco(eco)
        appliques.append(eco)
    return appliques


# ── NTMFG17 — Kanban de production (pull flow) ───────────────────────────

def declencher_kanban(regle):
    """NTMFG17 — si le stock disponible du produit de `regle` est SOUS le
    seuil de déclenchement, crée un OF BROUILLON de `quantite_lot` unités
    (jamais dupliqué : no-op si un OF brouillon/planifié/lancé est DÉJÀ
    ouvert pour ce produit). Renvoie l'OF créé, ou `None`."""
    from apps.stock.selectors import get_produit_scoped
    from apps.stock.services import available_quantity

    from .models import Gamme, OrdreFabrication

    if not regle.actif:
        return None
    produit = get_produit_scoped(regle.company_id, regle.produit_id)
    if produit is None:
        return None
    dispo = _dec(available_quantity(produit))
    if dispo > _dec(regle.seuil_declenchement):
        return None
    deja_ouvert = OrdreFabrication.objects.filter(
        company=regle.company, produit_id=regle.produit_id,
        statut__in=[
            OrdreFabrication.Statut.BROUILLON, OrdreFabrication.Statut.PLANIFIE,
            OrdreFabrication.Statut.LANCE]).exists()
    if deja_ouvert:
        return None
    gamme = (
        Gamme.objects.filter(
            company=regle.company, produit_id=regle.produit_id, actif=True)
        .order_by('-version').first())
    return OrdreFabrication.objects.create(
        company=regle.company, produit_id=regle.produit_id,
        quantite=regle.quantite_lot, gamme=gamme)


def declencher_kanban_toutes_regles(company):
    """NTMFG17 — balaie toutes les règles kanban ACTIVES de `company` (tâche
    périodique, pattern beat existant — dégrade proprement en déclenchement
    manuel via `mrp/kanban/declencher/` si Celery beat n'est pas déployé).
    Renvoie la liste des OF créés."""
    from .models import ReglesKanbanProduction

    crees = []
    for regle in ReglesKanbanProduction.objects.filter(company=company, actif=True):
        of = declencher_kanban(regle)
        if of is not None:
            crees.append(of)
    return crees


# ── NTMFG29 — Paramètres MRP par société ─────────────────────────────────

def parametres_mrp(company):
    """NTMFG29 — réglages MRP de la société (lazy `get_or_create`, pattern
    `scm.services.parametres_scm` — valeurs par défaut n'affectent AUCUNE
    société qui n'a encore rien configuré)."""
    from .models import ParametresMRP

    obj, _created = ParametresMRP.objects.get_or_create(company=company)
    return obj


# ── NTMFG31 — Purge/archivage des OF prototype anciens ───────────────────

def archiver_of_prototype_anciens(company, *, today=None, user=None):
    """NTMFG31 — archive (soft-delete, `core.SoftDeleteModel`) les OF
    `est_prototype=True` CLÔTURÉS (`statut=termine`, `updated_at` sert de
    proxy de date de clôture — même convention que `selectors.analyse_couts`)
    depuis plus de `ParametresMRP.retention_prototype_jours` (NTMFG29,
    défaut 180). Ne touche JAMAIS un OF de production normale
    (`est_prototype=False`, filtré explicitement) ni un OF déjà archivé
    (`objects` masque déjà les archivés — la requête ne les revoit pas,
    donc `soft_delete()` — lui-même idempotent — n'est jamais rejoué).
    Renvoie la liste des OF archivés par cet appel."""
    from .models import OrdreFabrication

    today = today or timezone.localdate()
    parametres = parametres_mrp(company)
    seuil = today - timedelta(days=int(parametres.retention_prototype_jours))

    candidats = OrdreFabrication.objects.filter(
        company=company, est_prototype=True,
        statut=OrdreFabrication.Statut.TERMINE,
        updated_at__date__lte=seuil)
    archives = []
    for of in candidats:
        of.soft_delete(user=user)
        archives.append(of)
    return archives


# ── NTMFG35 — Import CSV/XLSX de gammes opératoires en masse ─────────────

# En-têtes acceptés (normalisés via `apps.dataimport.parsing.normalize_header`)
# → clé canonique. `produit` référence l'ID du produit (résolu company-scopé
# via `stock.selectors.get_produit_scoped`, jamais un import du modèle
# `stock.Produit` — frontière cross-app) ; `poste_charge` référence
# `PosteDeCharge.code`, un champ 100% `mrp` — aucune résolution cross-app.
_GAMMES_IMPORT_FIELD_MAP = {
    'produit': 'produit', 'produit_code': 'produit', 'code_produit': 'produit',
    'ordre': 'ordre',
    'poste_charge': 'poste_charge', 'poste': 'poste_charge',
    'libelle': 'libelle',
    'temps_prepa_min': 'temps_prepa_min', 'temps_preparation_min': 'temps_prepa_min',
    'temps_unitaire_min': 'temps_unitaire_min',
}


def _ligne_gamme_import(row):
    """Normalise les clés d'une ligne brute (`dataimport.parsing.iter_rows`)
    vers les clés canoniques de `_GAMMES_IMPORT_FIELD_MAP`."""
    from apps.dataimport.parsing import normalize_header

    out = {}
    for header, valeur in row.items():
        cle = _GAMMES_IMPORT_FIELD_MAP.get(normalize_header(header))
        if cle:
            out[cle] = valeur
    return out


def importer_gammes_csv(company, rows, *, user=None, filename=''):
    """NTMFG35 — importe en masse des OPÉRATIONS de gamme depuis des lignes
    déjà parsées (`apps.dataimport.parsing.iter_rows`, réutilisé tel quel —
    jamais un parseur ad-hoc). Colonnes attendues : produit(id)/ordre/
    poste_charge(code)/libelle/temps_prepa_min/temps_unitaire_min.

    Validation LIGNE PAR LIGNE — un produit ou un poste de charge inconnu
    pour la société rejette CETTE ligne (motif précis), jamais tout le
    fichier. Pour chaque ligne valide, la `Gamme` ACTIVE du produit est
    résolue (ou créée en version 1 si aucune n'existe) et son
    `OperationGamme` à cet `ordre` est créé, ou MIS À JOUR s'il existe déjà
    (idempotent : ré-importer le même fichier ne duplique jamais).

    Bookkeeping via `apps.dataimport.ImportJob`/`ImportJobRow` (moteur
    générique réutilisé tel quel, jamais réécrit) — le rapport d'erreurs
    téléchargeable se lit ensuite via
    `apps.dataimport.services.erreurs_csv_rows(job)`. Renvoie
    ``{job_id, total_lignes, created_count, updated_count, error_count,
    erreurs: [{ligne, motif}]}``."""
    from apps.dataimport.models import ImportJob, ImportJobRow
    from apps.stock.selectors import get_produit_scoped

    from .models import Gamme, OperationGamme, PosteDeCharge

    created_count = 0
    updated_count = 0
    erreurs = []
    gammes_par_produit = {}  # produit_id -> Gamme (évite un re-lookup par ligne).

    for i, row in enumerate(rows, 1):
        f = _ligne_gamme_import(row)
        motif = None

        produit = None
        try:
            produit_id = int(f.get('produit') or 0)
        except (TypeError, ValueError):
            produit_id = 0
        if produit_id:
            produit = get_produit_scoped(company, produit_id)
        if produit is None:
            motif = 'Produit inconnu pour cette société.'

        poste = None
        if motif is None:
            code_poste = (f.get('poste_charge') or '').strip()
            poste = PosteDeCharge.objects.filter(
                company=company, code=code_poste).first()
            if poste is None:
                motif = f'Poste de charge inconnu pour cette société : « {code_poste} ».'

        libelle = (f.get('libelle') or '').strip()
        if motif is None and not libelle:
            motif = 'Libellé manquant.'

        try:
            ordre = int(f.get('ordre') or 0) or 1
        except (TypeError, ValueError):
            ordre = 1
        temps_prepa = _dec(f.get('temps_prepa_min') or 0)
        temps_unitaire = _dec(f.get('temps_unitaire_min') or 0)

        if motif is not None:
            erreurs.append({'ligne': i, 'motif': motif})
            continue

        try:
            gamme = gammes_par_produit.get(produit.id)
            if gamme is None:
                gamme = (Gamme.objects
                         .filter(company=company, produit=produit, actif=True)
                         .order_by('-version').first())
                if gamme is None:
                    gamme = Gamme.objects.create(
                        company=company, produit=produit,
                        nom=f'Gamme {produit.nom}', version=1)
                gammes_par_produit[produit.id] = gamme

            existante = OperationGamme.objects.filter(
                gamme=gamme, ordre=ordre).first()
            if existante is not None:
                existante.poste_charge = poste
                existante.libelle = libelle
                existante.temps_prepa_min = temps_prepa
                existante.temps_unitaire_min = temps_unitaire
                existante.save(update_fields=[
                    'poste_charge', 'libelle', 'temps_prepa_min',
                    'temps_unitaire_min'])
                updated_count += 1
            else:
                OperationGamme.objects.create(
                    company=company, gamme=gamme, ordre=ordre,
                    poste_charge=poste, libelle=libelle,
                    temps_prepa_min=temps_prepa,
                    temps_unitaire_min=temps_unitaire)
                created_count += 1
        except Exception as exc:  # noqa: BLE001 — une ligne KO n'arrête pas les autres.
            erreurs.append({'ligne': i, 'motif': f'Erreur inattendue : {exc}'})

    job = ImportJob.objects.create(
        company=company, target='mrp_gammes', fichier_nom=filename or '',
        mode='creer', statut=(
            ImportJob.Statut.OK if not erreurs
            else (ImportJob.Statut.PARTIEL if (created_count or updated_count)
                  else ImportJob.Statut.ECHEC)),
        total_lignes=len(rows), created_count=created_count,
        updated_count=updated_count, error_count=len(erreurs),
        created_by=user if getattr(user, 'is_authenticated', False) else None)
    for erreur in erreurs:
        brute = rows[erreur['ligne'] - 1]
        # JSON-safe (une cellule XLSX peut renvoyer un `datetime`/`float`
        # brut, jamais garanti sérialisable tel quel sur un `JSONField`).
        donnees = {str(k): ('' if v is None else str(v)) for k, v in brute.items()}
        ImportJobRow.objects.create(
            job=job, ligne=erreur['ligne'], statut=ImportJobRow.Statut.ERREUR,
            motif=erreur['motif'], donnees=donnees)

    return {
        'job_id': job.id,
        'total_lignes': len(rows),
        'created_count': created_count,
        'updated_count': updated_count,
        'error_count': len(erreurs),
        'erreurs': erreurs,
    }
