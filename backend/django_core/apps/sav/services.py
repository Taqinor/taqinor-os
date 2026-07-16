"""
Helpers SAV — arithmétique de garantie (sans dépendance externe).

`add_months` ajoute un nombre de mois à une date en restant dans la stdlib
(calendar), avec recadrage du jour pour les fins de mois (ex. 31 jan + 1 mois
→ 28/29 fév). Sert au calcul des dates de fin de garantie des équipements.
"""
from django.utils import timezone

from .dateutils import add_months  # noqa: F401  (ré-export rétrocompat)


# ── Point d'entrée cross-app : ajout au parc installé (sav.Equipement) ───────
# Les autres apps (installations) poussent un équipement dans le parc à travers
# ce service plutôt qu'en important `apps.sav.models` directement (voir CLAUDE.md,
# règle de modularité). Comportement identique à la création inline d'origine.

def create_equipement_from_serial(*, company, produit, installation,
                                  numero_serie, date_pose, created_by):
    """Crée un Equipement au parc, recalcule ses garanties et le sauve. Renvoie
    l'équipement créé. Écriture identique au bloc inline d'origine."""
    from .models import Equipement
    equip = Equipement.objects.create(
        company=company, produit=produit, installation=installation,
        numero_serie=numero_serie, date_pose=date_pose, created_by=created_by)
    equip.recompute_garanties()
    equip.save(update_fields=[
        'date_fin_garantie', 'date_fin_garantie_production'])
    return equip


def ensure_equipement_for_bom_line(*, company, produit, installation,
                                   date_pose, created_by):
    """FG70 — garantit qu'AU MOINS UN Equipement (sans n° de série) existe au
    parc pour la paire (chantier, produit). IDEMPOTENT : si un équipement de ce
    produit existe déjà pour ce chantier (avec ou sans série), ne crée rien et
    renvoie ``(equipement_existant, False)``. Sinon crée un équipement
    serial-less daté de ``date_pose`` (garanties recalculées) et renvoie
    ``(equipement, True)``.

    Sert au balayage de la nomenclature gelée (`Installation.bom`) à la
    réception : la couverture de garantie ne dépend plus d'un technicien qui
    pense à saisir chaque n° de série. Le n° de série reste optionnel et peut
    être renseigné plus tard sur l'équipement créé."""
    from .models import Equipement
    existing = (Equipement.objects
                .filter(company=company, installation=installation,
                        produit=produit)
                .first())
    if existing is not None:
        return existing, False
    equip = create_equipement_from_serial(
        company=company, produit=produit, installation=installation,
        numero_serie=None, date_pose=date_pose, created_by=created_by)
    return equip, True


def sweep_bom_to_parc(*, installation, company, date_pose, created_by,
                      resolve_produit):
    """FG70 — balaye la nomenclature gelée du chantier (`installation.bom`) et
    garantit un Equipement de parc (sans n° de série) par ligne de BoM ayant un
    produit catalogue. IDEMPOTENT et ADDITIF : ne duplique jamais un équipement
    déjà présent pour une paire (chantier, produit) — un re-passage à
    « Réceptionné » ne crée rien de neuf.

    ``resolve_produit(produit_id)`` est fourni par l'appelant (installations)
    pour résoudre le produit catalogue scopé société sans coupler les apps. Les
    lignes sans ``produit_id``, ou dont le produit est introuvable, sont
    ignorées (on ne crée pas d'équipement pour une ligne libre).

    Renvoie un dict-résumé pour la note de remise / la section PDF :
      {'crees': int, 'existants': int, 'lignes': [
          {'designation': str, 'cree': bool}, ...]}.
    """
    bom = getattr(installation, 'bom', None) or []
    crees = 0
    existants = 0
    lignes = []
    seen = set()
    for ligne in bom:
        produit_id = (ligne or {}).get('produit_id')
        if not produit_id:
            continue
        # Plusieurs lignes peuvent référencer le même produit : on ne crée
        # qu'un seul équipement par produit (idempotence intra-balayage).
        if produit_id in seen:
            continue
        produit = resolve_produit(produit_id)
        if produit is None:
            continue
        seen.add(produit_id)
        _equip, created = ensure_equipement_for_bom_line(
            company=company, produit=produit, installation=installation,
            date_pose=date_pose, created_by=created_by)
        designation = (ligne.get('designation')
                       or getattr(produit, 'nom', '') or '')
        lignes.append({'designation': designation, 'cree': created})
        if created:
            crees += 1
        else:
            existants += 1
    return {'crees': crees, 'existants': existants, 'lignes': lignes}


def _technicien_indisponible(company, user, jour):
    """XSAV9 — Vrai si `user` a un dossier RH avec une absence VALIDÉE ce
    jour-là (lu via les selectors rh — jamais un import direct des modèles
    rh). Sans dossier RH rattaché à l'utilisateur, ou si le module rh est
    indisponible/erreur, on considère l'utilisateur DISPONIBLE (repli sûr —
    l'affectation auto ne doit jamais bloquer faute de données RH)."""
    try:
        from apps.rh.selectors import employe_absent_le
        from apps.rh.models import DossierEmploye
        dossier = DossierEmploye.objects.filter(
            company=company, user=user).first()
        if dossier is None:
            return False
        return employe_absent_le(company, dossier.id, jour)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        return False


def assign_technicien_auto(*, company, jour=None):
    """XSAV9 — Choisit le technicien actif le MOINS chargé (nb de tickets
    ouverts assignés) pour une affectation automatique, en excluant les
    indisponibilités RH (lues via les selectors rh — jamais un import direct
    des modèles rh) quand elles sont disponibles.

    Renvoie l'utilisateur choisi, ou None si aucun technicien actif éligible
    (repli : le ticket reste sans affectation — comportement OFF inchangé).
    Un technicien = tout utilisateur ACTIF de la société ayant déjà été
    assigné à au moins un ticket (participe au pool de charge) — ce périmètre
    évite d'affecter un compte administratif jamais destiné au terrain.
    """
    from django.contrib.auth import get_user_model
    from django.db.models import Count, Q
    from .models import Ticket

    User = get_user_model()
    jour = jour or timezone.localdate()

    candidats = list(
        User.objects.filter(
            company=company, is_active=True,
            tickets_techniques__isnull=False,
        ).distinct()
        .annotate(
            nb_ouverts=Count(
                'tickets_techniques',
                filter=Q(
                    tickets_techniques__statut__in=Ticket.OPEN_STATUTS,
                    tickets_techniques__annule=False),
            ),
        )
        .order_by('nb_ouverts', 'id'))

    for user in candidats:
        if not _technicien_indisponible(company, user, jour):
            return user
    return None


def create_corrective_ticket(*, company, client, installation, description,
                             created_by):
    """F16 — crée un ticket SAV correctif (référence sans collision via
    l'utilitaire commun). Renvoie le ticket créé. Identique au bloc inline."""
    from apps.ventes.utils.references import create_with_reference
    from .models import Ticket

    def _create(ref):
        return Ticket.objects.create(
            company=company, reference=ref, client=client,
            installation=installation, type=Ticket.Type.CORRECTIF,
            description=description, created_by=created_by)
    return create_with_reference(Ticket, 'SAV', company, _create)


def create_ticket_from_projet_tache(*, company, client, description):
    """ZPRJ11 — crée un ticket SAV CORRECTIF depuis une tâche de projet.

    Fonction FINE appelée depuis ``apps.gestion_projet.services`` (frontière
    cross-app : gestion_projet ne connaît QUE cette fonction, jamais
    ``sav.models``). ``client`` doit être un ``crm.Client`` déjà résolu par
    l'appelant (ex. via ``crm.selectors.get_company_client`` depuis
    ``Projet.client_id``). Référence via l'utilitaire commun (jamais
    ``count()+1``). Renvoie le ``Ticket`` créé."""
    from apps.ventes.utils.references import create_with_reference
    from .models import Ticket

    def _create(ref):
        return Ticket.objects.create(
            company=company, reference=ref, client=client,
            type=Ticket.Type.CORRECTIF, description=description)
    return create_with_reference(Ticket, 'SAV', company, _create)


# ── XSAV16 — Journal d'immobilisation (downtime) + disponibilité % ──────────

class DowntimeOverlapError(Exception):
    """XSAV16 — Levée quand une nouvelle fenêtre de downtime chevauche une
    fenêtre existante du MÊME équipement (une immobilisation double compterait
    la disponibilité %)."""


def ouvrir_downtime(*, company, equipement, debut, ticket=None, motif='',
                    created_by=None):
    """XSAV16 — Ouvre une immobilisation pour ``equipement`` à partir de
    ``debut``. Refuse tout chevauchement avec une fenêtre existante du même
    équipement : une fenêtre EN COURS (fin=None) chevauche toujours toute
    nouvelle ouverture (on ne peut pas ouvrir une seconde panne pendant que la
    première n'est pas close) ; une fenêtre déjà close chevauche si
    ``debut`` tombe dans son intervalle [debut, fin]. Lève
    ``DowntimeOverlapError`` en cas de chevauchement — jamais une seconde
    fenêtre concurrente créée par erreur."""
    from .models import EquipementDowntime

    en_cours = EquipementDowntime.objects.filter(
        equipement=equipement, fin__isnull=True).exists()
    if en_cours:
        raise DowntimeOverlapError(
            'Une immobilisation est déjà en cours pour cet équipement.')

    chevauche = EquipementDowntime.objects.filter(
        equipement=equipement, debut__lte=debut, fin__gte=debut).exists()
    if chevauche:
        raise DowntimeOverlapError(
            'Cette période chevauche une immobilisation existante.')

    return EquipementDowntime.objects.create(
        company=company, equipement=equipement, debut=debut,
        ticket=ticket, motif=motif or '', created_by=created_by)


def disponibilite_equipement(equipement, *, debut_periode, fin_periode):
    """XSAV16 — Disponibilité % d'un équipement sur ``[debut_periode,
    fin_periode]`` (bornes datetime timezone-aware, inclusives).

    Calcule le temps cumulé d'immobilisation qui INTERSECTE la période
    demandée (une fenêtre en cours utilise ``fin_periode`` comme borne haute
    provisoire), puis renvoie :
      {'duree_periode_heures': float, 'duree_downtime_heures': float,
       'disponibilite_pct': float}
    ``disponibilite_pct`` = 100 si la période est nulle/négative (repli sûr,
    aucune division par zéro)."""
    from django.db.models import Q
    from .models import EquipementDowntime

    duree_periode = (fin_periode - debut_periode).total_seconds() / 3600
    if duree_periode <= 0:
        return {
            'duree_periode_heures': 0.0, 'duree_downtime_heures': 0.0,
            'disponibilite_pct': 100.0,
        }

    qs = EquipementDowntime.objects.filter(
        equipement=equipement, debut__lte=fin_periode,
    ).filter(Q(fin__gte=debut_periode) | Q(fin__isnull=True))

    downtime_heures = 0.0
    for dt in qs:
        fin = dt.fin or fin_periode
        seg_debut = max(dt.debut, debut_periode)
        seg_fin = min(fin, fin_periode)
        if seg_fin > seg_debut:
            downtime_heures += (seg_fin - seg_debut).total_seconds() / 3600

    downtime_heures = min(downtime_heures, duree_periode)
    disponibilite_pct = round(
        (1 - downtime_heures / duree_periode) * 100, 2)
    return {
        'duree_periode_heures': round(duree_periode, 2),
        'duree_downtime_heures': round(downtime_heures, 2),
        'disponibilite_pct': disponibilite_pct,
    }


# ── XSAV17 — Relevés compteur (heures / kWh) + entretien conditionnel ────────

class ReleveDecroissantError(Exception):
    """XSAV17 — Levée quand un relevé est INFÉRIEUR au dernier relevé du même
    équipement (le compteur est cumulatif, jamais décroissant)."""


def enregistrer_releve_compteur(*, company, equipement, type_releve, valeur,
                                date_releve, created_by=None):
    """XSAV17 — Enregistre un relevé de compteur et, si un seuil
    (`Equipement.entretien_toutes_les_heures`) est configuré et franchi
    depuis le dernier entretien généré, matérialise EXACTEMENT UN ticket
    préventif (idempotent : `dernier_entretien_compteur_valeur` avance
    aussitôt qu'un ticket est généré, donc un second relevé au-dessus du
    même seuil — avant le prochain entretien — n'en recrée pas un second).

    Refuse (``ReleveDecroissantError``) un relevé strictement inférieur au
    dernier relevé DU MÊME TYPE pour cet équipement — le compteur est
    cumulatif, jamais décroissant. Renvoie ``(releve, ticket_ou_None)``.
    """
    from decimal import Decimal
    from .models import ReleveCompteurEquipement

    valeur = Decimal(str(valeur))
    dernier = (ReleveCompteurEquipement.objects
               .filter(equipement=equipement, type=type_releve)
               .order_by('-valeur').first())
    if dernier is not None and valeur < dernier.valeur:
        raise ReleveDecroissantError(
            'Ce relevé est inférieur au dernier relevé enregistré '
            f'({dernier.valeur}) — le compteur ne peut pas reculer.')

    releve = ReleveCompteurEquipement.objects.create(
        company=company, equipement=equipement, type=type_releve,
        valeur=valeur, date=date_releve, created_by=created_by)

    seuil = equipement.entretien_toutes_les_heures
    ticket = None
    # ZMFG12 — un équipement au rebut ne génère plus de ticket préventif par
    # franchissement de seuil (le parc « au rebut » est en fin de vie).
    if seuil and not equipement.mis_au_rebut:
        reference_base = equipement.dernier_entretien_compteur_valeur or Decimal('0')
        if valeur - reference_base >= seuil:
            ticket = _generer_ticket_preventif_compteur(
                company, equipement, type_releve, valeur, created_by)
            equipement.dernier_entretien_compteur_valeur = valeur
            equipement.save(
                update_fields=['dernier_entretien_compteur_valeur'])
    return releve, ticket


def _generer_ticket_preventif_compteur(company, equipement, type_releve,
                                       valeur, created_by):
    """XSAV17 — Matérialise le ticket préventif de franchissement de seuil."""
    from apps.ventes.utils.references import create_with_reference
    from .models import Ticket

    installation = equipement.installation
    client = getattr(installation, 'client', None)
    label = 'heures' if type_releve == 'heures' else 'kWh'
    description = (
        f'Entretien préventif dû (seuil de {label} franchi — '
        f'compteur à {valeur} {label}).')

    def _create(ref):
        return Ticket.objects.create(
            reference=ref, company=company, client=client,
            installation=installation, equipement=equipement,
            type=Ticket.Type.PREVENTIF, statut=Ticket.Statut.NOUVEAU,
            date_ouverture=timezone.localdate(), description=description,
            created_by=created_by)
    return create_with_reference(Ticket, 'SAV', company, _create)


# ── YSUBS1 — Sélection des contrats de maintenance dus à facturation ────────
# (helper de sélection pour le beat quotidien de facturation récurrente de
# ``apps.contrats.scheduled`` — jamais l'inverse, ``sav`` ne dépend PAS de
# ``contrats``.)

def contrats_maintenance_dus_facturation(company, today=None):
    """Contrats de maintenance ACTIFS dont la facturation récurrente est due
    aujourd'hui (ou en retard) — YSUBS1. Lecture seule, scopée société.

    Réutilise ``ContratMaintenance.facturation_due`` (FG40, déjà idempotent :
    vrai seulement si ``facturation_active`` et la prochaine échéance calculée
    depuis ``derniere_facturation``/``date_debut`` est atteinte)."""
    from .models import ContratMaintenance

    return [
        c for c in ContratMaintenance.objects.filter(
            company=company, actif=True, facturation_active=True)
        if c.facturation_due(today=today)
    ]


def facturer_contrat_maintenance_beat(contrat, *, user=None):
    """Facture UN ``ContratMaintenance`` dû, pour le beat quotidien — YSUBS1.

    Même effet que l'action ``facturer`` de ``ContratMaintenanceViewSet``
    (``maintenance.py``) : émet la ``Facture`` via
    ``apps.ventes.services.creer_facture_contrat`` puis avance
    ``derniere_facturation``, et journalise le cycle dans
    ``apps.contrats.services.enregistrer_cycle`` (best-effort, jamais
    bloquant). Renvoie la ``Facture`` créée ; lève ``ValueError`` si la
    facturation échoue (prix manquant…) — l'appelant (le beat) capture
    l'exception PAR contrat pour ne jamais bloquer les suivants.

    XCTR16 — si le contrat renseigne ``tarif_usage``, ajoute une ligne
    dédiée « facturation à l'usage » (voir ``calculer_ligne_usage_contrat``)
    APRÈS la création de la facture (best-effort, ne bloque jamais l'émission
    de la facture forfaitaire elle-même)."""
    from django.utils import timezone as _timezone

    from apps.ventes.services import creer_facture_contrat

    periode = _timezone.localdate().strftime('%Y-%m')
    try:
        facture = creer_facture_contrat(
            contrat=contrat, user=user, company=contrat.company)
    except ValueError:
        _journaliser_cycle_maintenance_beat(
            contrat.company, contrat.pk, periode, statut_echec=True)
        raise

    motif_usage = ''
    if contrat.tarif_usage is not None:
        motif_usage = _ajouter_ligne_usage_contrat(contrat, facture)

    _journaliser_cycle_maintenance_beat(
        contrat.company, contrat.pk, periode, statut_echec=False,
        facture_id=facture.id, motif=motif_usage)
    return facture


# ── XCTR16 — Facturation à l'usage depuis le monitoring ─────────────────────

def calculer_ligne_usage_contrat(contrat, periode_debut, periode_fin):
    """Calcule la ligne de facturation à l'usage d'un ``ContratMaintenance``
    sur ``[periode_debut, periode_fin)`` (borne de fin exclusive).

    Renvoie ``(montant_ht, description)`` quand une lecture d'usage existe
    (``max(0, usage − franchise) × tarif`` — jamais négatif), ou
    ``(None, motif)`` quand la ligne doit être OMISE : contrat sans
    ``tarif_usage``/``installation``, ou aucune lecture disponible sur la
    période (le motif est destiné au journal XCTR5, jamais une exception —
    l'absence de lecture est un cas attendu, pas une erreur)."""
    from decimal import Decimal

    if contrat.tarif_usage is None:
        return None, 'Pas de tarif à l\'usage sur ce contrat.'
    if contrat.installation_id is None:
        return None, 'Contrat sans installation liée — usage non calculable.'

    from apps.monitoring.selectors import usage_kwh_periode

    usage = usage_kwh_periode(
        contrat.company, contrat.installation, periode_debut, periode_fin)
    if usage is None:
        return None, (
            f"Aucun relevé de production sur la période {periode_debut}"
            f"–{periode_fin} — ligne d'usage omise.")

    franchise = contrat.franchise_incluse or Decimal('0')
    facturable = max(Decimal('0'), usage - franchise)
    montant = (facturable * contrat.tarif_usage).quantize(Decimal('0.01'))
    unite = contrat.get_unite_usage_display() if contrat.unite_usage else 'kWh'
    description = (
        f'Facturation à l\'usage — {usage} {unite} relevés, '
        f'franchise {franchise} {unite}, {facturable} {unite} facturés '
        f'à {contrat.tarif_usage} MAD/{unite}.')
    return montant, description


def _ajouter_ligne_usage_contrat(contrat, facture):
    """Ajoute (best-effort) la ligne d'usage calculée sur la ``Facture``
    récurrente déjà émise, via le hook cross-app générique déjà exposé par
    ``ventes`` (``ajouter_lignes_frais_refactures`` — même mécanisme que
    ``apps.compta`` pour les frais refacturés, aucun nouveau couplage).
    Renvoie le motif (chaîne vide si une ligne a bien été ajoutée) destiné au
    journal XCTR5."""
    periode_debut = facture.periode_service_debut
    periode_fin = facture.periode_service_fin
    if periode_debut is None or periode_fin is None:
        return 'Période de service absente sur la facture — usage non calculé.'

    montant, description = calculer_ligne_usage_contrat(
        contrat, periode_debut, periode_fin)
    if montant is None:
        return description

    from apps.ventes.services import ajouter_lignes_frais_refactures

    ajouter_lignes_frais_refactures(
        facture=facture,
        lignes=[{'designation': description, 'montant_ht': montant}],
    )
    return ''


def _journaliser_cycle_maintenance_beat(company, contrat_id, periode, *,
                                        statut_echec, facture_id=None,
                                        motif=''):
    """Journalise un cycle de facturation SAV dans le journal contrats —
    XCTR5/YSUBS1. Même patron que
    ``maintenance.ContratMaintenanceViewSet._journaliser_cycle_best_effort``
    (frontière cross-app : import fonction-local, best-effort).

    XCTR16 — ``motif`` trace la ligne d'usage omise (aucune lecture
    disponible) même quand la facture forfaitaire, elle, a bien été générée
    (le statut reste ``GENERE`` — seule la ligne d'usage est absente)."""
    try:
        from apps.contrats import services as contrats_services
        from apps.contrats.models import CycleFacturationLog

        statut = (
            CycleFacturationLog.Statut.ECHEC if statut_echec
            else CycleFacturationLog.Statut.GENERE)
        contrats_services.enregistrer_cycle(
            company,
            source_type=CycleFacturationLog.SourceType.SAV_MAINTENANCE,
            source_id=contrat_id,
            periode=periode,
            statut=statut,
            facture_id=facture_id,
            motif=motif or '',
        )
    except Exception:  # pragma: no cover - défensif (best-effort)
        pass


def creer_intervention_depuis_installation(
        *, company, installation_id, description, ncr_reference=None):
    """XQHS23 — fonction FINE appelée par QHSE pour ouvrir une intervention
    corrective depuis une non-conformité (pont NCR → SAV, sens inverse de
    ``qhse.services.creer_ncr_depuis_ticket``). QHSE ne lit/écrit jamais
    ``sav.models`` directement — cette fonction est le seul point d'entrée.

    Le ``client`` est dérivé de l'``Installation`` (via le sélecteur LECTURE
    SEULE ``installations.selectors.installation_scoped`` — jamais un import
    direct du modèle). Lève ``ValueError`` si l'installation est introuvable
    dans la société.

    Idempotent : si un ticket correctif porte déjà le marqueur
    ``[NCR:<ncr_reference>]`` pour la même installation, le ticket existant
    est réutilisé plutôt que dupliqué. Renvoie ``(ticket, created)``."""
    from apps.installations.selectors import installation_scoped
    from apps.ventes.utils.references import create_with_reference
    from .models import Ticket

    installation = installation_scoped(company, installation_id)
    if installation is None:
        raise ValueError("Installation introuvable dans votre société.")

    marqueur = f'[NCR:{ncr_reference}]' if ncr_reference else None
    if marqueur:
        existant = Ticket.objects.filter(
            company=company, installation_id=installation_id,
            description__startswith=marqueur).first()
        if existant is not None:
            return existant, False

    full_description = f'{marqueur} {description}' if marqueur else description

    def _create(ref):
        return Ticket.objects.create(
            company=company, reference=ref, client=installation.client,
            installation=installation, type=Ticket.Type.CORRECTIF,
            description=full_description)
    ticket = create_with_reference(Ticket, 'SAV', company, _create)
    return ticket, True


# ── XMFG10 — Pièces retirées / récupérées sur ticket SAV ─────────────────────

class OperationDestinationIncoherenteError(ValueError):
    """ZMFG8 — une pièce en ``recyclage`` doit avoir ``destination`` =
    ``stock_occasion`` (cohérence avec le restock XMFG10)."""


def retirer_piece(*, company, ticket, produit, quantite, numero_serie,
                  destination, user, operation=None):
    """Trace une pièce RETIRÉE du ticket (`PieceRetiree`) et applique les
    effets de bord de sa `destination` :

      * ``stock_occasion`` → ré-incrémente le stock (MouvementStock ENTRÉE,
        UNE seule fois via `restockee`) ;
      * ``retour_fournisseur`` → propose/crée un `WarrantyClaim` (FG83) lié
        à l'équipement si `numero_serie` matche un équipement de la société ;
      * ``rebut`` → aucun mouvement de stock.

    ``operation`` (ZMFG8) — ``retrait`` (défaut) ou ``recyclage`` ; lève
    ``OperationDestinationIncoherenteError`` si ``recyclage`` est demandé
    sans ``destination='stock_occasion'`` (garde de cohérence, aucun
    nouveau mouvement de stock au-delà de celui déjà déclenché par
    `stock_occasion`).

    Si `numero_serie` correspond à un `sav.Equipement` existant (société
    scoped), il est marqué REMPLACÉ. Renvoie la `PieceRetiree` créée."""
    from .models import Equipement, PieceRetiree, WarrantyClaim

    operation = operation or PieceRetiree.Operation.RETRAIT
    if (operation == PieceRetiree.Operation.RECYCLAGE
            and destination != PieceRetiree.Destination.STOCK_OCCASION):
        raise OperationDestinationIncoherenteError(
            "Une pièce en recyclage doit avoir une destination "
            "'stock_occasion'.")

    equipement_remplace = None
    if numero_serie:
        equipement_remplace = Equipement.objects.filter(
            company=company, numero_serie=numero_serie).first()
        if equipement_remplace is not None:
            equipement_remplace.statut = Equipement.Statut.REMPLACE
            equipement_remplace.remplace_par_ticket = ticket
            equipement_remplace.save(
                update_fields=['statut', 'remplace_par_ticket'])
            # ARC37 — sav devient émetteur du bus : émet EXACTEMENT une fois
            # (une seule bascule REMPLACE par appel, garantie par le
            # ``if equipement_remplace is not None`` ci-dessus). Best-effort :
            # jamais bloquant pour le retrait de pièce déjà acté.
            try:
                from core.events import equipement_remplace as \
                    equipement_remplace_signal

                equipement_remplace_signal.send(
                    sender=None, equipement=equipement_remplace,
                    ticket=ticket, company=company, user=user)
            except Exception:  # pragma: no cover - défensif (best-effort)
                pass

    piece = PieceRetiree.objects.create(
        company=company, ticket=ticket, produit=produit, quantite=quantite,
        numero_serie=numero_serie or '', destination=destination,
        operation=operation,
        equipement_remplace=equipement_remplace, created_by=user)

    if destination == PieceRetiree.Destination.STOCK_OCCASION:
        if not piece.restockee:
            from apps.stock.services import (
                mouvement_type_entree, record_stock_movement,
            )
            produit.refresh_from_db()
            qte_avant = produit.quantite_stock
            qte_apres = qte_avant + quantite
            record_stock_movement(
                company=company, produit=produit,
                type_mouvement=mouvement_type_entree(),
                quantite=quantite, quantite_avant=qte_avant,
                quantite_apres=qte_apres, reference=ticket.reference,
                note=f'Retrait pièce SAV {ticket.reference} (stock occasion)',
                created_by=user)
            piece.restockee = True
            piece.save(update_fields=['restockee'])
    elif destination == PieceRetiree.Destination.RETOUR_FOURNISSEUR:
        if equipement_remplace is not None:
            claim = WarrantyClaim.objects.create(
                company=company, equipement=equipement_remplace,
                ticket=ticket, created_by=user,
                description=(
                    'RMA proposé automatiquement — pièce retirée '
                    f'(ticket {ticket.reference}).'))
            piece.warranty_claim = claim
            piece.save(update_fields=['warranty_claim'])

    return piece


# ── XPOS9 — Capture n° de série à la vente comptoir → garantie SAV auto ─────

class SerieDejaEnregistreeError(Exception):
    """Le n° de série est déjà rattaché à un équipement de la société."""


def creer_equipement_depuis_vente_pos(*, company, produit, client,
                                      numero_serie, date_vente, created_by):
    """XPOS9 — pendant « vente au détail » de `create_equipement_from_serial`
    (le pendant chantier existant, FG70) : crée l'Equipement SAV garanti pour
    un produit sérialisé vendu au comptoir SANS chantier (`installation=None`,
    `client_vente=client`), garantie courant depuis `date_vente`.

    No-op côté appelant si `produit.suivi_serie` est faux ou `numero_serie`
    est vide — c'est à l'appelant (`apps.pos.services`) de ne PAS invoquer
    cette fonction dans ce cas (flag additif, comportement inchangé par
    défaut). Lève `SerieDejaEnregistreeError` si la série existe déjà dans la
    société (contrainte `uniq_equipement_serie_par_societe`).

    Si la série est déjà enregistrée au registre entrepôt (`SerieEntrepot`,
    FG323), la marque SORTI (best-effort, jamais bloquant) via
    `installations.services.marquer_serie_entrepot_sortie`."""
    from .models import Equipement

    serie = (numero_serie or '').strip()
    if not serie:
        raise ValueError('numero_serie requis.')
    if Equipement.objects.filter(
            company=company, numero_serie=serie).exists():
        raise SerieDejaEnregistreeError(
            f'Le n° de série {serie} est déjà enregistré dans votre société.')

    equip = Equipement.objects.create(
        company=company, produit=produit, installation=None,
        client_vente=client, numero_serie=serie, date_pose=date_vente,
        created_by=created_by)
    equip.recompute_garanties()
    equip.save(update_fields=[
        'date_fin_garantie', 'date_fin_garantie_production'])

    try:
        from apps.installations.services import marquer_serie_entrepot_sortie
        marquer_serie_entrepot_sortie(
            company=company, produit_id=produit.id, numero_serie=serie)
    except Exception:  # pragma: no cover - défensif (best-effort)
        pass

    return equip


# ── XFSM15 — Suivi des récidives (callbacks / retour sur panne) ────────────

def suggerer_recidive(*, company, installation_id, exclure_ticket_id=None,
                      a_la_date=None):
    """XFSM15 — suggère une récidive à la création d'un ticket : cherche la
    dernière intervention TERMINÉE/VALIDÉE du MÊME chantier dans la fenêtre
    paramétrable (`SavSlaSettings.recidive_fenetre_jours`, défaut 30 jours).

    Lit `installations.Intervention` UNIQUEMENT via
    `installations.selectors.intervention_recente_pour_chantier` (jamais un
    import direct de `installations.models` — règle de modularité). Renvoie
    ``(intervention_id, motif)`` ou ``(None, '')`` si rien ne matche."""
    from .models import SavSlaSettings

    if not installation_id:
        return None, ''
    sla = SavSlaSettings.get(company)
    fenetre = sla.recidive_fenetre_jours
    if not fenetre:
        return None, ''

    from apps.installations.selectors import intervention_recente_pour_chantier
    interv = intervention_recente_pour_chantier(
        company, installation_id, depuis_jours=fenetre, avant=a_la_date,
        exclure_ticket_id=exclure_ticket_id)
    if interv is None:
        return None, ''
    type_label = interv.get_type_intervention_display()
    motif = (
        f'Intervention #{interv.id} ({type_label}) réalisée le '
        f'{interv.date_realisee} sur le même chantier (< {fenetre} j).')
    return interv.id, motif


# ── XSAV26 — WhatsApp entrant → ticket SAV (gated BSP) ──────────────────────

def router_whatsapp_entrant_vers_ticket(*, company, expediteur, texte):
    """XSAV26 — route un message WhatsApp entrant vers le SAV quand
    l'expéditeur matche un ``crm.Client`` existant (via
    ``crm.selectors.find_client_by_phone``, normalisation
    ``normalize_ma_phone``) :

      * si le client n'a AUCUN ticket ouvert (statuts ``OPEN_STATUTS``), crée
        un ticket correctif dont la description démarre par le message ;
      * sinon, ajoute le texte en note chatter du ticket ouvert le plus
        récent.

    Renvoie ``('ticket_cree', ticket)`` / ``('note_ajoutee', ticket)`` quand
    un client a matché, ou ``(None, None)`` si l'expéditeur ne correspond à
    aucun client de la société (l'appelant route alors vers le lead comme
    avant — comportement inchangé, XSAV26 ne touche jamais ce chemin)."""
    from apps.crm.selectors import find_client_by_phone
    from apps.ventes.utils.references import create_with_reference
    from . import activity
    from .models import Ticket

    client = find_client_by_phone(company, expediteur)
    if client is None:
        return None, None

    ticket = (
        Ticket.objects
        .filter(company=company, client=client, statut__in=Ticket.OPEN_STATUTS,
                annule=False)
        .order_by('-date_creation')
        .first())
    if ticket is not None:
        activity.log_note(
            ticket, None, f'WhatsApp de {expediteur} : {texte}'.strip())
        return 'note_ajoutee', ticket

    def _create(ref):
        return Ticket.objects.create(
            company=company, reference=ref, client=client,
            type=Ticket.Type.CORRECTIF,
            description=f'[WhatsApp] {texte}'.strip())
    ticket = create_with_reference(Ticket, 'SAV', company, _create)
    # XSAV24 — la trace de création (CREATION) est posée automatiquement par
    # le récepteur `post_save` de `receivers.py` (voir
    # `_log_creation_on_ticket_created`), plus besoin de l'appel explicite ici.
    return 'ticket_cree', ticket


# ── XSAV27 — Prêt / échange anticipé d'équipement (loaner) ─────────────────

class PretEquipementError(Exception):
    """Erreur métier sur un prêt d'équipement (statut incohérent, stock…)."""


def creer_pret_equipement(*, company, ticket, produit, numero_serie,
                          date_sortie, date_retour_prevue, user):
    """XSAV27 — crée un `PretEquipement` et sort IMMÉDIATEMENT l'unité du
    stock (MouvementStock SORTIE, idempotent via `stock_sorti`). Lève
    `PretEquipementError` si le stock est insuffisant (jamais négatif —
    même garde que `TicketViewSet.pieces`)."""
    from apps.stock.services import mouvement_type_sortie, record_stock_movement
    from .models import PretEquipement

    produit.refresh_from_db()
    if produit.quantite_stock < 1:
        raise PretEquipementError(
            f'Stock insuffisant pour prêter {produit.nom} '
            f'({produit.quantite_stock} en main).')

    pret = PretEquipement.objects.create(
        company=company, ticket=ticket, produit=produit,
        numero_serie=numero_serie or '', date_sortie=date_sortie,
        date_retour_prevue=date_retour_prevue, created_by=user)

    qte_avant = produit.quantite_stock
    qte_apres = qte_avant - 1
    record_stock_movement(
        company=company, produit=produit,
        type_mouvement=mouvement_type_sortie(),
        quantite=1, quantite_avant=qte_avant, quantite_apres=qte_apres,
        reference=ticket.reference,
        note=f'Prêt équipement SAV {ticket.reference}', created_by=user)
    pret.stock_sorti = True
    pret.save(update_fields=['stock_sorti'])
    return pret


def retourner_pret_equipement(*, pret, date_retour_reelle, user):
    """XSAV27 — clôt un prêt EN_COURS : réintègre le stock (MouvementStock
    ENTRÉE, idempotent via `stock_reintegre`) et marque RETOURNE.
    Idempotent : un second appel sur un prêt déjà retourné ne fait rien
    (renvoie le prêt tel quel)."""
    from .models import PretEquipement

    if pret.statut == PretEquipement.Statut.RETOURNE:
        return pret

    if pret.stock_sorti and not pret.stock_reintegre:
        from apps.stock.services import (
            mouvement_type_entree, record_stock_movement,
        )
        produit = pret.produit
        produit.refresh_from_db()
        qte_avant = produit.quantite_stock
        qte_apres = qte_avant + 1
        record_stock_movement(
            company=pret.company, produit=produit,
            type_mouvement=mouvement_type_entree(),
            quantite=1, quantite_avant=qte_avant, quantite_apres=qte_apres,
            reference=pret.ticket.reference,
            note=f'Retour prêt équipement SAV {pret.ticket.reference}',
            created_by=user)
        pret.stock_reintegre = True

    pret.statut = PretEquipement.Statut.RETOURNE
    pret.date_retour_reelle = date_retour_reelle
    pret.save(update_fields=[
        'statut', 'date_retour_reelle', 'stock_reintegre'])
    return pret


def prets_en_retard(company):
    """XSAV27 — liste des prêts EN_COURS dont `date_retour_prevue` est
    dépassée aujourd'hui. Utilisé par le scan d'alerte (idempotent via
    `alerte_depassement_notifiee`)."""
    from .models import PretEquipement

    today = timezone.localdate()
    return list(PretEquipement.objects.filter(
        company=company, statut=PretEquipement.Statut.EN_COURS,
        date_retour_prevue__isnull=False,
        date_retour_prevue__lt=today))


# ── XSAV28 — Triage IA du ticket + brouillon de réponse (clé-gated) ─────────
# Key-gated (GROQ_API_KEY, même clé que XQHS25 — pas de nouvelle dépendance
# externe/payante ajoutée ici). Sans clé, `ia_disponible()` est False et
# `suggerer_triage_ticket` renvoie `{'disponible': False}` — jamais
# d'exception, jamais de no-op cassant. TOUJOURS une proposition éditable,
# JAMAIS auto-appliquée (pattern propose→confirm, groupe AG).

import json  # noqa: E402
import os  # noqa: E402

import requests  # noqa: E402

_GROQ_CHAT_URL = 'https://api.groq.com/openai/v1/chat/completions'
_GROQ_MODEL_DEFAUT = 'llama-3.1-8b-instant'


def _groq_api_key():
    return os.environ.get('GROQ_API_KEY', '') or ''


def ia_disponible():
    """True si une clé IA (GROQ) est configurée. Sert de garde côté vue/
    front (masque les boutons IA quand False)."""
    return bool(_groq_api_key())


def _appeler_groq(system_prompt, user_prompt, *, timeout=15):
    """Appel HTTP direct à l'API Groq (compatible OpenAI), sans SDK
    supplémentaire (``requests`` est déjà une dépendance du projet). Renvoie
    le contenu texte de la réponse, ou lève une exception (capturée par
    l'appelant) en cas d'échec réseau/clé/timeout."""
    resp = requests.post(
        _GROQ_CHAT_URL,
        headers={
            'Authorization': f'Bearer {_groq_api_key()}',
            'Content-Type': 'application/json',
        },
        json={
            'model': _GROQ_MODEL_DEFAUT,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            'temperature': 0,
            'response_format': {'type': 'json_object'},
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data['choices'][0]['message']['content']


_TRIAGE_SYSTEM_PROMPT = (
    "Tu es un assistant SAV pour un installateur solaire au Maroc. À partir "
    "de la description d'un ticket entrant (email, portail, WhatsApp) et "
    "d'articles de base de connaissance pertinents (fournis en contexte), "
    "propose un triage structuré. Réponds UNIQUEMENT en JSON valide avec "
    "les clés : \"type_panne_suggere\" (texte court, ex. « Onduleur en "
    "défaut »), \"priorite_suggeree\" (une valeur parmi basse|normale|"
    "haute|urgente), \"resume\" (une phrase résumant le problème), "
    "\"brouillon_reponse\" (un brouillon de première réponse au client, "
    "poli et concis, en français, qui s'appuie sur les articles KB fournis "
    "si pertinents)."
)


def suggerer_triage_ticket(*, company, description):
    """XSAV28 — suggère type de panne / priorité / résumé + brouillon de
    première réponse pour un ticket entrant (email FG373, portail, WhatsApp
    XSAV26). Key-gated : sans ``GROQ_API_KEY``, renvoie
    ``{'disponible': False}`` (jamais d'exception).

    Les articles KB pertinents (``selectors.kb_articles_pertinents``) sont
    injectés en contexte du prompt. TOUJOURS une proposition éditable —
    l'appelant (vue) ne l'applique JAMAIS automatiquement au ticket."""
    if not ia_disponible():
        return {'disponible': False}
    description = (description or '').strip()
    if not description:
        return {'disponible': True, 'suggestion': None,
                'erreur': 'description vide'}

    from .selectors import kb_articles_pertinents
    articles = kb_articles_pertinents(company, description)
    contexte_kb = '\n'.join(
        f"- {a['titre']} : {a['extrait']}" for a in articles)
    user_prompt = description
    if contexte_kb:
        user_prompt = (
            f'{description}\n\nArticles KB pertinents :\n{contexte_kb}')

    try:
        contenu = _appeler_groq(_TRIAGE_SYSTEM_PROMPT, user_prompt)
        suggestion = json.loads(contenu)
    except Exception as exc:  # pragma: no cover - dépend d'un service externe
        return {'disponible': True, 'suggestion': None, 'erreur': str(exc)}

    return {'disponible': True, 'suggestion': suggestion,
            'kb_articles': articles}


# ── ZSAV9 — Suiveurs de ticket (followers) ───────────────────────────────────

def notify_followers(ticket, *, event_type, title, body='', link=None,
                     exclude_user=None):
    """ZSAV9 — Notifie tous les suiveurs (``TicketFollower``) d'un ticket,
    best-effort (``notify()`` est déjà mute-aware par utilisateur), en plus
    du technicien assigné (notifié séparément par les sites d'appel
    existants). ``exclude_user`` évite d'auto-notifier l'auteur de l'action
    (ex. la personne qui vient de poster la note)."""
    from apps.notifications.services import notify

    followers = ticket.followers.select_related('user')
    for follower in followers:
        user = follower.user
        if exclude_user is not None and user.id == getattr(
                exclude_user, 'id', None):
            continue
        try:
            notify(
                user=user, event_type=event_type, title=title, body=body,
                link=link, company=ticket.company)
        except Exception:  # pragma: no cover - best-effort, jamais bloquant
            pass


# ── ARC37 — sav devient émetteur du bus (core.events) ───────────────────────

def emettre_ticket_resolu(ticket, *, company, user=None, ancien_statut):
    """ARC37 — émet ``core.events.ticket_resolu`` sur le FRANCHISSEMENT vers
    RESOLU. Point d'émission UNIQUE appelé par les DEUX sites où la bascule
    RESOLU peut être atteinte : l'action gardée ``resoudre``
    (``apps/sav/views.py``) et l'avancement automatique sur intervention
    terminée (``apps/sav/receivers.py``, YSERV2). Best-effort : une erreur ici
    ne doit jamais remonter (la transition, côté appelant, est déjà actée)."""
    from .models import Ticket

    if ticket.statut != Ticket.Statut.RESOLU or ancien_statut == Ticket.Statut.RESOLU:
        return  # pas une bascule VERS résolu — ne réémet jamais.
    try:
        from core.events import ticket_resolu

        ticket_resolu.send(
            sender=None, ticket=ticket, company=company, user=user,
            ancien_statut=ancien_statut)
    except Exception:  # pragma: no cover - défensif (best-effort)
        pass


def emettre_changement_statut_ticket(ticket, *, company, user=None,
                                     ancien_statut):
    """ARC34 — évalue les règles no-code automation ``RECORD_STATE_CHANGE``
    après une transition de statut RÉUSSIE du ticket. Appelée par l'UNIQUE
    site de transition gardée (``TicketViewSet._appliquer_transition_statut``,
    juste à côté de l'émission ARC37 ``emettre_ticket_resolu`` ci-dessus).

    Frontière : même précédent que ``gestion_projet.services`` (appel direct
    ``apps.automation.engine.evaluate()``, import FONCTION-LOCAL, chemin
    parallèle documenté dans automation/models.py). Le couple (sav.ticket,
    statut) est déclaré automatisable dans ``apps/sav/platform.py``
    (automation_state_fields) ; statut de DOMAINE ``Ticket.Statut``, jamais
    STAGES.py (rule #2). Best-effort : aucune erreur ne remonte (la
    transition, côté appelant, est déjà actée)."""
    if ticket.statut == ancien_statut:
        return  # pas de changement réel — n'émet jamais.
    try:
        from apps.automation.engine import evaluate
        from apps.automation.models import TriggerType

        evaluate(
            TriggerType.RECORD_STATE_CHANGE, ticket, company,
            context={
                'model': 'sav.ticket', 'field': 'statut',
                'old_value': ancien_statut, 'new_value': ticket.statut,
            },
            user=user)
    except Exception:  # pragma: no cover - défensif (best-effort)
        pass


def abonner_suiveurs_globaux(ticket):
    """ZSAV9 — Abonne automatiquement (idempotent) chaque utilisateur listé
    dans ``SavSlaSettings.suivre_tous_tickets_sav`` au ticket nouvellement
    créé. Liste vide (défaut) = no-op, comportement actuel inchangé."""
    from .models import SavSlaSettings, TicketFollower

    sla = SavSlaSettings.get(ticket.company)
    users = list(sla.suivre_tous_tickets_sav.all())
    if not users:
        return
    for user in users:
        TicketFollower.objects.get_or_create(
            company=ticket.company, ticket=ticket, user=user)


# ── XCTR1 — Devis accepté (ligne récurrente) → contrat de maintenance ───────

def creer_contrat_depuis_devis_accepte(*, devis, user=None):
    """XCTR1 — quand un ``ventes.Devis`` contenant AU MOINS UNE ligne dont le
    produit est marqué ``est_recurrent`` passe à accepté, crée IDEMPOTENT un
    ``ContratMaintenance`` pour le client du devis : prix = total TTC des
    lignes récurrentes, périodicité = celle du premier produit récurrent
    trouvé (défaut annuel), ``facturation_active=False`` (comportement
    historique — la facturation récurrente reste un opt-in explicite,
    cf. FG40). Le contrat est lié au devis via une note dans ``notes`` (pas de
    nouvelle FK cross-app).

    Aucune écriture cross-app directe : appelé UNIQUEMENT depuis le receveur
    ``apps/sav/receivers.py`` abonné à ``core.events.devis_accepted``.

    Idempotence : si un ``ContratMaintenance`` référence déjà ce devis dans
    ``notes`` (marqueur ``[devis:<id>]``), ne crée rien (ré-émission du signal,
    double clic) et renvoie ``None``. Un devis SANS ligne récurrente ne crée
    rien non plus (renvoie ``None``).
    """
    from decimal import Decimal

    from .models import ContratMaintenance

    marqueur = f'[devis:{devis.pk}]'
    if ContratMaintenance.objects.filter(
            company=devis.company, notes__contains=marqueur).exists():
        return None

    lignes_recurrentes = [
        ligne for ligne in devis.lignes.select_related('produit').all()
        if getattr(ligne.produit, 'est_recurrent', False)
    ]
    if not lignes_recurrentes:
        return None

    prix = sum((ligne.total_ht * (
        1 + (ligne.taux_tva_effectif or 0) / Decimal('100'))
        for ligne in lignes_recurrentes), Decimal('0'))

    premiere_periodicite = None
    for ligne in lignes_recurrentes:
        periodicite = getattr(ligne.produit, 'periodicite_defaut', None)
        if periodicite:
            premiere_periodicite = periodicite
            break

    kwargs = dict(
        company=devis.company,
        client=devis.client,
        date_debut=devis.date_acceptation or timezone.localdate(),
        prix=prix,
        actif=True,
        facturation_active=False,
        notes=f'Créé automatiquement depuis le devis {marqueur} '
              f'(ligne(s) récurrente(s) — XCTR1).',
    )
    if premiere_periodicite:
        kwargs['periodicite'] = premiere_periodicite

    installation = getattr(devis, 'installation', None)
    if installation is not None:
        kwargs['installation'] = installation

    return ContratMaintenance.objects.create(**kwargs)


# ── ZMFG7 — Alias e-mail par catégorie d'équipement ──────────────────────────

def _extract_to_addresses(message):
    """Extrait les adresses du header ``To`` (brut) d'un ``InboundMessage``
    (``core.email_intake``), en minuscules, sans nom affiché."""
    from email.utils import getaddresses

    to_header = (message.raw_headers or {}).get('To', '')
    if not to_header:
        return []
    return [addr.strip().lower()
            for _, addr in getaddresses([to_header]) if addr]


def categorie_pour_alias(company, message):
    """ZMFG7 — ``CategorieEquipement`` de la société dont ``alias_email``
    correspond à UNE des adresses ``To`` du message, ou ``None`` si aucune
    catégorie ne configure cet alias (route FG373 générique inchangée)."""
    from .models import CategorieEquipement

    adresses = _extract_to_addresses(message)
    if not adresses:
        return None
    return (CategorieEquipement.objects
            .filter(company=company, alias_email__in=adresses)
            .exclude(alias_email__isnull=True)
            .exclude(alias_email='')
            .first())


def creer_ticket_depuis_email_alias(message, company):
    """ZMFG7 — Handler enregistré auprès de ``core.email_intake`` (FG373) :
    si le message entrant est adressé à l'alias e-mail d'une
    ``CategorieEquipement``, crée un ticket CORRECTIF pré-catégorisé
    (catégorie posée sur l'équipement via son alias + équipe responsable de
    la catégorie si posée).

    NO-OP total (ne crée rien) si :
      * aucune catégorie de la société ne configure cet alias (route
        générique FG373 inchangée) ;
      * l'expéditeur ne correspond à AUCUN client existant de la société
        (on ne devine jamais un client — mieux vaut ne rien créer qu'un
        ticket orphelin).

    Idempotent par Message-ID : un même message ne crée jamais deux
    tickets (re-poll IMAP, redélivrance).
    """
    categorie = categorie_pour_alias(company, message)
    if categorie is None:
        return None  # pas d'alias configuré → route générique inchangée.

    from apps.crm.selectors import find_client_by_email
    from apps.ventes.utils.references import create_with_reference
    from .models import Ticket

    client = find_client_by_email(message.from_email, company=company)
    if client is None:
        return None  # expéditeur inconnu → aucun ticket orphelin créé.

    marqueur = f'[email:{message.message_id}]' if message.message_id else None
    if marqueur:
        existant = Ticket.objects.filter(
            company=company, description__startswith=marqueur).first()
        if existant is not None:
            return existant

    sujet = (message.subject or 'Demande reçue par e-mail').strip()
    corps = message.body or ''
    description = f'{marqueur} {sujet}\n\n{corps}' if marqueur else f'{sujet}\n\n{corps}'

    def _create(ref):
        return Ticket.objects.create(
            company=company, reference=ref, client=client,
            type=Ticket.Type.CORRECTIF, statut=Ticket.Statut.NOUVEAU,
            categorie_equipement=categorie,
            equipe=categorie.equipe_responsable,
            date_ouverture=timezone.localdate(),
            description=description[:4000])
    return create_with_reference(Ticket, 'SAV', company, _create)


def register_email_alias_handler():
    """ZMFG7 — Abonne ``creer_ticket_depuis_email_alias`` au bus e-mail
    entrant (``core.email_intake``), câblé depuis ``SavConfig.ready()``.
    ``core`` ne connaît jamais ``apps.sav`` — même patron de découplage que
    les autres handlers du registre (docstring ``core/email_intake.py``)."""
    from core.email_intake import register_handler

    register_handler(creer_ticket_depuis_email_alias)
