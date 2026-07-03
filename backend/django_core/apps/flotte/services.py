"""Services (WRITE / orchestration) du module Gestion de flotte.

Point d'entrée des ÉCRITURES cross-app vers la flotte : les autres apps n'écrivent
jamais les modèles flotte directement, elles passent par ces fonctions. La société
est toujours posée côté serveur, jamais lue du corps de requête (multi-tenant).
"""
import datetime


def normaliser_categorie_permis(categorie):
    """FLOTTE9 — Normalise une catégorie de permis pour comparaison.

    Met en majuscules et retire les espaces : ``" ce "`` → ``"CE"``. Une valeur
    vide / ``None`` revient à la chaîne vide (aucune catégorie)."""
    if not categorie:
        return ''
    return ''.join(str(categorie).split()).upper()


def controle_permis(conducteur, vehicule, today=None):
    """FLOTTE9 — Contrôle « permis valide / catégorie » à l'affectation.

    Vérifie qu'un ``Conducteur`` peut légalement conduire un ``Vehicule``. Le
    contrôle est **piloté par l'exigence du véhicule** : il ne se déclenche que
    si le véhicule exige une catégorie de permis
    (``Vehicule.categorie_permis_requise`` non vide). Tant qu'aucune catégorie
    n'est requise, l'affectation est libre (un véhicule sans exigence — p. ex.
    un utilitaire léger sans contrainte saisie — n'impose rien), ce qui préserve
    le comportement historique de FLOTTE8.

    Quand une catégorie EST requise :

    1. **Permis renseigné** — le conducteur doit porter un numéro et une
       catégorie ; sinon → ``permis_manquant``.
    2. **Permis valide (non expiré)** — si ``date_expiration`` est renseignée et
       antérieure à ``today`` → ``permis_expire``.
    3. **Catégorie adaptée** — la catégorie requise doit figurer parmi celles du
       conducteur (un permis « B, CE » couvre « CE ») ; sinon →
       ``categorie_inadaptee``.

    Lecture seule : ne modifie rien, retourne ``(ok, code, message)`` —
    ``ok=True`` et ``code=''`` quand tout est conforme (ou quand le véhicule
    n'exige rien). Aucune exception levée : l'appelant (sérialiseur / service
    d'écriture) décide de rejeter ou de soft-warn selon le drapeau ``force``.
    """
    if today is None:
        today = datetime.date.today()

    requise = normaliser_categorie_permis(vehicule.categorie_permis_requise)
    if not requise:
        # Le véhicule n'impose aucune catégorie → rien à contrôler.
        return (True, '', '')

    numero = (conducteur.numero_permis or '').strip()
    categorie_cond = normaliser_categorie_permis(conducteur.categorie_permis)

    if not numero or not categorie_cond:
        return (
            False,
            'permis_manquant',
            "Le conducteur ne porte pas de permis valide "
            f"(catégorie {requise} requise par le véhicule).",
        )

    if conducteur.date_expiration is not None \
            and conducteur.date_expiration < today:
        return (
            False,
            'permis_expire',
            "Le permis du conducteur est expiré "
            f"(expiré le {conducteur.date_expiration.isoformat()}).",
        )

    # Catégories portées par le conducteur (« B, CE » → {'B', 'CE'}).
    portees = {
        normaliser_categorie_permis(part)
        for part in str(conducteur.categorie_permis).replace(';', ',').split(',')
    }
    portees.discard('')
    if requise not in portees:
        return (
            False,
            'categorie_inadaptee',
            f"La catégorie du permis ({categorie_cond}) ne couvre pas la "
            f"catégorie requise par le véhicule ({requise}).",
        )

    return (True, '', '')


# ── FLOTTE10 — Détection de conflit de réservation de véhicule ────────────────

def reservations_en_conflit(company, vehicule, debut, fin, exclude_pk=None):
    """FLOTTE10 — Réservations ACTIVES d'un véhicule qui chevauchent [debut, fin).

    Une réservation est « active » tant que son statut occupe le véhicule
    (``demandee`` ou ``confirmee``) — les réservations ``annulee`` sont ignorées,
    elles peuvent légitimement se superposer à de nouvelles.

    Deux plages [a1,a2) et [b1,b2) se chevauchent si ``a1 < b2`` ET ``b1 < a2``.
    Un retour à l'heure exacte où une autre commence (``a2 == b1``) n'est donc
    PAS un conflit (bornes demi-ouvertes). Le créneau passé est scopé société et
    par véhicule. ``exclude_pk`` permet d'exclure la réservation en cours d'édition.

    Retourne un queryset (potentiellement vide). Lecture seule.
    """
    from .models import ReservationVehicule

    vehicule_id = getattr(vehicule, 'id', vehicule)
    qs = ReservationVehicule.objects.filter(
        company=company,
        vehicule_id=vehicule_id,
        statut__in=ReservationVehicule.STATUTS_ACTIFS,
        debut__lt=fin,
        fin__gt=debut,
    )
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs


# ── FLOTTE12 — Cohérence du kilométrage au carnet de carburant ────────────────

def kilometrage_incoherent(company, vehicule, kilometrage, date_plein,
                           exclude_pk=None):
    """FLOTTE12 — Indique si ``kilometrage`` est incohérent pour ce véhicule.

    Règle simple : le kilométrage relevé à une date doit être >= au plus grand
    kilométrage déjà enregistré à une date antérieure ou égale, et <= au plus
    petit kilométrage enregistré à une date postérieure ou égale (le compteur ne
    recule jamais). Retourne ``(incoherent: bool, message: str)``. Lecture seule.

    NB : la détection fine d'anomalie/fraude (sauts aberrants) relève de FLOTTE14
    — ici on garde le carnet cohérent (compteur monotone croissant).
    """
    from .models import PleinCarburant

    vehicule_id = getattr(vehicule, 'id', vehicule)
    base = PleinCarburant.objects.filter(
        company=company, vehicule_id=vehicule_id)
    if exclude_pk is not None:
        base = base.exclude(pk=exclude_pk)

    # Plus haut km à une date <= date_plein.
    avant = (
        base.filter(date_plein__lte=date_plein)
        .order_by('-kilometrage')
        .values_list('kilometrage', flat=True)
        .first()
    )
    if avant is not None and kilometrage < avant:
        return (
            True,
            "Le kilométrage saisi est inférieur à un relevé antérieur "
            f"({avant} km) — le compteur ne peut pas reculer.",
        )

    # Plus bas km à une date >= date_plein.
    apres = (
        base.filter(date_plein__gte=date_plein)
        .order_by('kilometrage')
        .values_list('kilometrage', flat=True)
        .first()
    )
    if apres is not None and kilometrage > apres:
        return (
            True,
            "Le kilométrage saisi est supérieur à un relevé postérieur "
            f"({apres} km) — le compteur ne peut pas reculer.",
        )

    return (False, '')


# ── FLOTTE16 — Génération d'échéances d'entretien dues + alertes ───────────────

def _cible_echeance_depuis_criteres(criteres):
    """Extrait la cible ``(due_le, due_km, due_heures)`` d'une échéance DUE.

    À partir des ``criteres`` calculés par
    ``selectors.plan_entretien_echeance`` (déjà filtrés sur ``statut == 'due'``
    en amont), renvoie la prochaine échéance par dimension : la date ISO
    (``jours``) est convertie en ``datetime.date``, le km et les heures restent
    des entiers. Une dimension absente vaut ``None``. Lecture seule, pas d'effet
    de bord."""
    due_le = None
    due_km = None
    due_heures = None
    for critere in criteres:
        if critere.get('statut') != 'due':
            continue
        dimension = critere.get('dimension')
        prochaine = critere.get('prochaine_echeance')
        if dimension == 'jours' and prochaine:
            try:
                due_le = datetime.date.fromisoformat(str(prochaine))
            except (ValueError, TypeError):
                due_le = None
        elif dimension == 'km' and prochaine is not None:
            due_km = int(prochaine)
        elif dimension == 'heures' and prochaine is not None:
            due_heures = int(prochaine)
    return due_le, due_km, due_heures


def _destinataire_alerte(plan):
    """Utilisateur ERP à alerter pour un plan : conducteur actif du véhicule.

    Best-effort : résout le conducteur actuellement affecté au véhicule ciblé
    (si l'actif est un véhicule) et renvoie son utilisateur ERP lié, sinon
    ``None``. Aucune exception propagée. Lecture seule."""
    try:
        actif = plan.actif_flotte
        if actif is None or actif.vehicule_id is None:
            return None
        from .selectors import conducteur_actuel_du_vehicule
        conducteur = conducteur_actuel_du_vehicule(
            plan.company, actif.vehicule_id)
        return conducteur.user if conducteur is not None else None
    except Exception:
        return None


def _alerter_echeance(echeance, plan):
    """FLOTTE16 — Diffuse une alerte « entretien dû » (best-effort, jamais lève).

    Notifie via le service partagé ``apps.notifications.services.notify``
    (import LOCAL — la flotte ne dépend jamais des modèles d'une autre app) le
    destinataire le plus pertinent disponible : l'utilisateur ERP lié à l'actif
    via son affectation conducteur active ; à défaut, on n'alerte personne. La
    notification réutilise l'événement métier ``maintenance_due``.

    Tolérant : toute exception est avalée — une alerte ratée ne doit jamais
    interrompre la génération ni casser une transaction d'écriture.
    """
    try:
        from apps.notifications.services import notify
    except Exception:
        return None

    user = _destinataire_alerte(plan)
    if user is None:
        return None

    cibles = []
    if echeance.due_le is not None:
        cibles.append(f"avant le {echeance.due_le.isoformat()}")
    if echeance.due_km is not None:
        cibles.append(f"à {echeance.due_km} km")
    if echeance.due_heures is not None:
        cibles.append(f"à {echeance.due_heures} h")
    detail = ' / '.join(cibles) if cibles else 'dès que possible'
    try:
        return notify(
            user=user,
            event_type='maintenance_due',
            title=f"Entretien dû : {echeance.type_entretien}",
            body=(
                f"L'actif {echeance.actif_flotte.label} doit passer en "
                f"entretien « {echeance.type_entretien} » ({detail})."
            ),
            link='/flotte/echeances-entretien',
            company=echeance.company,
        )
    except Exception:
        return None


def generer_echeances_entretien(company, alerter=True):
    """FLOTTE16 — Génère les échéances d'entretien DUES depuis les plans actifs.

    Pour chaque ``PlanEntretien`` actif de la société (scopé), calcule son
    statut courant via ``selectors.plans_entretien_status`` ; lorsqu'un plan est
    ``due``, matérialise une ``EcheanceEntretien`` (statut ``a_faire``) si — et
    seulement si — il n'existe pas déjà une échéance OUVERTE
    (``a_faire`` / ``planifie``) pour ce plan. La génération est donc
    IDEMPOTENTE : un second passage ne duplique aucune échéance ouverte ; une
    nouvelle échéance ne renaît qu'une fois la précédente marquée ``fait``.

    Si ``alerter=True``, une alerte best-effort est diffusée pour CHAQUE échéance
    nouvellement créée via ``apps.notifications.services.notify`` (événement
    ``maintenance_due``) — un échec d'alerte n'interrompt jamais la génération.

    Multi-tenant : ``company`` est toujours posée côté serveur ; la société de
    l'échéance créée est celle du plan source. Retourne un dict scopé société ::

        {'company_id', 'nb_plans_due', 'nb_creees', 'nb_existantes',
         'echeances': [<EcheanceEntretien>, …]}  # uniquement les nouvelles

    Aucune écriture hors ``EcheanceEntretien`` ; l'opération est sûre à relancer.
    """
    from .models import EcheanceEntretien
    from .selectors import plans_de_la_societe, plans_entretien_status

    status = plans_entretien_status(company, actif_only=True, statut='due')
    plans_due = status['plans']

    # Index des plans actifs par id (pour récupérer l'instance ORM complète).
    plans_par_id = {
        plan.id: plan
        for plan in plans_de_la_societe(company, actif_only=True)
    }

    # Plans ayant DÉJÀ une échéance ouverte (a_faire/planifie) → on ne re-crée pas.
    plans_avec_ouverte = set(
        EcheanceEntretien.objects
        .filter(company=company,
                statut__in=EcheanceEntretien.STATUTS_OUVERTS)
        .values_list('plan_id', flat=True)
    )

    creees = []
    nb_existantes = 0
    for ligne in plans_due:
        plan_id = ligne['plan_id']
        plan = plans_par_id.get(plan_id)
        if plan is None:
            continue
        if plan_id in plans_avec_ouverte:
            nb_existantes += 1
            continue

        due_le, due_km, due_heures = _cible_echeance_depuis_criteres(
            ligne.get('criteres', []))
        echeance = EcheanceEntretien.objects.create(
            company=company,
            plan=plan,
            actif_flotte=plan.actif_flotte,
            type_entretien=plan.type_entretien,
            due_le=due_le,
            due_km=due_km,
            due_heures=due_heures,
            statut=EcheanceEntretien.Statut.A_FAIRE,
        )
        creees.append(echeance)
        # Empêche un doublon si plusieurs lignes du même plan apparaissaient.
        plans_avec_ouverte.add(plan_id)
        if alerter:
            _alerter_echeance(echeance, plan)

    return {
        'company_id': company.id,
        'nb_plans_due': len(plans_due),
        'nb_creees': len(creees),
        'nb_existantes': nb_existantes,
        'echeances': creees,
    }


# ── FLOTTE17 — Clôture d'un ordre de réparation (et de l'échéance liée) ────────

def cloturer_ordre_reparation(ordre, date_cloture=None,
                              cloturer_echeance=True):
    """FLOTTE17 — Clôture un ``OrdreReparation`` et, en option, son échéance liée.

    Pose ``statut='cloture'`` sur l'OR et renseigne ``date_cloture`` (date du jour
    si absente). Quand ``cloturer_echeance=True`` et qu'une ``EcheanceEntretien``
    est rattachée à l'OR, cette échéance est marquée ``fait`` (sauf si elle l'est
    déjà) — l'entretien curatif solde l'échéance préventive d'origine.

    Idempotent : ré-appeler sur un OR déjà clôturé ne change rien (la date de
    clôture existante est conservée). Multi-tenant : aucune société n'est lue du
    corps de requête ; l'OR porte déjà sa société côté serveur.

    Retourne ``(ordre, echeance_clôturée|None)``.
    """
    from .models import EcheanceEntretien

    if date_cloture is None:
        date_cloture = ordre.date_cloture or datetime.date.today()

    deja_cloture = ordre.statut == ordre.Statut.CLOTURE
    ordre.statut = ordre.Statut.CLOTURE
    if ordre.date_cloture is None or not deja_cloture:
        ordre.date_cloture = date_cloture
    ordre.save()

    echeance_close = None
    if cloturer_echeance and ordre.echeance_id is not None:
        echeance = ordre.echeance
        if echeance.statut != EcheanceEntretien.Statut.FAIT:
            echeance.statut = EcheanceEntretien.Statut.FAIT
            echeance.save(update_fields=['statut'])
            echeance_close = echeance

    return ordre, echeance_close


# ── FLOTTE27 — Point d'intégration télématique (KEY-GATED no-op) ──────────────

def telematique_active():
    """FLOTTE27 — True si l'intégration télématique est activée (gated, off).

    KEY-GATED : sans ``settings.TELEMATIQUE_ENABLED`` à vrai, tout l'aspect
    fournisseur est un NO-OP (aucun appel réseau, aucune dépendance, aucun coût).
    Le founder active la fonctionnalité en posant le drapeau + la clé du
    fournisseur dans l'environnement. Tant que le flag est faux, ``synchroniser_
    releves`` ne fait rien et l'ingestion MANUELLE des relevés reste la seule
    voie (et elle marche toujours).

    Pour rester réellement no-op même drapeau activé tant qu'aucun fournisseur
    concret n'est câblé, on exige AUSSI qu'un module fournisseur soit importable
    (``telematique_provider``) — sinon on reste off. On ne lève jamais.
    """
    from django.conf import settings
    if not bool(getattr(settings, 'TELEMATIQUE_ENABLED', False)):
        return False
    # Drapeau activé : un fournisseur concret doit être câblé pour sortir du
    # no-op. Import GARDÉ — tant qu'aucun module fournisseur n'existe, on reste
    # off (jamais d'appel fantôme, aucune dépendance dure introduite ici).
    try:  # pragma: no cover - dépend d'un provider externe non câblé ici.
        from . import telematique_provider as provider  # noqa: F401
    except ImportError:
        return False
    return provider is not None  # pragma: no cover


def synchroniser_releves(company, *, actif_flotte=None, depuis=None):
    """FLOTTE27 — Synchronise les relevés télématiques depuis le fournisseur.

    POINT D'INTÉGRATION : tire les relevés (odomètre, position, carburant,
    heures moteur) d'un fournisseur GPS/télématique externe et les enregistre
    comme ``ReleveTelematique`` de la société.

    NO-OP par défaut : tant que ``telematique_active()`` est faux (aucun
    fournisseur configuré), cette fonction ne fait RIEN — aucun appel réseau,
    aucune dépendance, aucun coût — et renvoie ``0`` (nombre de relevés
    importés). Le squelette d'appel fournisseur est isolé ici pour un futur
    branchement sans toucher au reste du module ; l'ingestion MANUELLE d'un
    ``ReleveTelematique`` (``source='manuel'``) ne dépend jamais de ce chemin.

    Multi-tenant : ``company`` est toujours posée côté serveur ; tout relevé
    importé hériterait de cette société (jamais lue d'un corps de requête).
    ``actif_flotte`` (optionnel) restreint la synchro à un actif ; ``depuis``
    (optionnel) borne la fenêtre temporelle. Ne lève jamais — une synchro
    indisponible renvoie simplement ``0``.

    Retourne le nombre de relevés nouvellement importés (``0`` en mode no-op).
    """
    if not telematique_active():
        # Aucun fournisseur configuré → no-op total : on ne touche rien.
        return 0
    # Branchement fournisseur à venir (clé-gated). Tant qu'aucun fournisseur
    # concret n'est câblé, ``telematique_active`` renvoie déjà False ; ce bloc
    # n'est donc jamais atteint en l'état (no-op garanti). Laissé en squelette
    # pour le futur branchement.
    from . import telematique_provider as provider  # pragma: no cover
    releves = provider.fetch_releves(  # pragma: no cover
        company, actif_flotte=actif_flotte, depuis=depuis)
    return len(releves or [])  # pragma: no cover


# ── FLOTTE28 — Construction de trajets depuis les relevés télématiques ─────────

def _distance_haversine_km(lat1, lng1, lat2, lng2):
    """Distance à vol d'oiseau (km) entre deux points GPS (formule de Haversine).

    Retourne ``None`` si l'une des coordonnées est absente. Lecture seule, pas
    d'effet de bord. Sert d'estimation de distance d'un trajet à défaut d'un
    odomètre fiable sur les relevés."""
    if None in (lat1, lng1, lat2, lng2):
        return None
    import math
    rayon = 6371.0  # rayon moyen de la Terre en km.
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlambda = math.radians(float(lng2) - float(lng1))
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return round(2 * rayon * math.asin(math.sqrt(a)), 3)


def construire_trajets_telematiques(company, actif_flotte, *,
                                    pause_minutes=15):
    """FLOTTE28 — Construit des trajets depuis les relevés télématiques d'un actif.

    Agrège les ``ReleveTelematique`` (FLOTTE27) consécutifs d'un actif (triés par
    horodatage) en ``TrajetTelematique`` : un trajet regroupe les relevés tant
    que l'écart entre deux relevés successifs reste sous ``pause_minutes`` ; un
    écart plus grand CLÔT le trajet en cours et en démarre un nouveau. La
    distance du trajet est ESTIMÉE par l'écart d'odomètre des relevés bornes si
    disponible, sinon par la distance Haversine entre positions de départ et
    d'arrivée. Un trajet d'un seul relevé (immobile) est ignoré.

    IDEMPOTENT : on ne (re)construit que les trajets dont le relevé de départ
    n'est pas déjà borne d'un trajet existant de l'actif — un second passage ne
    duplique rien. Multi-tenant : ``company`` est posée côté serveur ; l'actif
    fourni doit appartenir à la société (vérifié). Ne lève pas sur données vides.

    Retourne la liste des ``TrajetTelematique`` nouvellement créés.
    """
    from .models import ReleveTelematique, TrajetTelematique

    actif_id = getattr(actif_flotte, 'id', actif_flotte)
    # Garde-fou société : ne construit que pour un actif de la société.
    from .models import ActifFlotte
    if not ActifFlotte.objects.filter(
            company=company, id=actif_id).exists():
        return []

    releves = list(
        ReleveTelematique.objects
        .filter(company=company, actif_flotte_id=actif_id)
        .order_by('horodatage', 'id'))
    if len(releves) < 2:
        return []

    # Relevés déjà utilisés comme départ d'un trajet existant (idempotence).
    deja_depart = set(
        TrajetTelematique.objects
        .filter(company=company, actif_flotte_id=actif_id,
                releve_depart__isnull=False)
        .values_list('releve_depart_id', flat=True))

    # Découpe en segments selon la pause.
    seuil = datetime.timedelta(minutes=pause_minutes)
    groupes = []
    courant = [releves[0]]
    for precedent, suivant in zip(releves, releves[1:]):
        if (suivant.horodatage - precedent.horodatage) <= seuil:
            courant.append(suivant)
        else:
            groupes.append(courant)
            courant = [suivant]
    groupes.append(courant)

    crees = []
    for groupe in groupes:
        if len(groupe) < 2:
            continue  # actif immobile : pas de trajet.
        depart = groupe[0]
        arrivee = groupe[-1]
        if depart.id in deja_depart:
            continue  # déjà construit.

        # Distance : écart d'odomètre si exploitable, sinon Haversine.
        distance = None
        if depart.odometre is not None and arrivee.odometre is not None \
                and arrivee.odometre >= depart.odometre:
            distance = arrivee.odometre - depart.odometre
        else:
            distance = _distance_haversine_km(
                depart.position_lat, depart.position_lng,
                arrivee.position_lat, arrivee.position_lng)

        trajet = TrajetTelematique.objects.create(
            company=company,
            actif_flotte_id=actif_id,
            debut=depart.horodatage,
            fin=arrivee.horodatage,
            depart_lat=depart.position_lat,
            depart_lng=depart.position_lng,
            arrivee_lat=arrivee.position_lat,
            arrivee_lng=arrivee.position_lng,
            distance_km=distance,
            releve_depart=depart,
            releve_arrivee=arrivee,
        )
        crees.append(trajet)
        deja_depart.add(depart.id)

    return crees


# ── FLOTTE32 — Décision sur une demande de véhicule (pool) ─────────────────────

def decider_demande_vehicule(demande, *, statut, decide_par=None,
                             vehicule=None, motif=''):
    """FLOTTE32 — Approuve / refuse / annule une demande de véhicule (pool).

    Pose le ``statut`` cible (``approuvee`` | ``refusee`` | ``annulee``),
    renseigne ``decide_par`` (utilisateur décideur), ``date_decision`` (maintenant)
    et ``motif_decision``. À l'approbation, ``vehicule`` (un ``Vehicule`` de la
    MÊME société) est attribué ; sur un refus / une annulation, l'attribution est
    remise à ``None``. Vérifie l'appartenance société du décideur et du véhicule.

    Multi-tenant : aucune société n'est lue du corps de requête ; la demande
    porte déjà sa société côté serveur. Retourne la demande mise à jour. Lève
    ``ValueError`` sur un statut cible invalide ou une incohérence de société.
    """
    from django.core.exceptions import ValidationError
    from django.utils import timezone

    from .models import DemandeVehicule

    statuts_decision = {
        DemandeVehicule.Statut.APPROUVEE,
        DemandeVehicule.Statut.REFUSEE,
        DemandeVehicule.Statut.ANNULEE,
    }
    if statut not in statuts_decision:
        raise ValueError("Statut de décision invalide.")

    if decide_par is not None \
            and getattr(decide_par, 'company_id', None) != demande.company_id:
        raise ValueError("Le décideur n'appartient pas à la même société.")

    if statut == DemandeVehicule.Statut.APPROUVEE:
        if vehicule is not None \
                and getattr(vehicule, 'company_id', None) != demande.company_id:
            raise ValueError(
                "Le véhicule attribué n'appartient pas à la même société.")
        demande.vehicule_attribue = vehicule
    else:
        # Refus / annulation : aucune attribution conservée.
        demande.vehicule_attribue = None

    demande.statut = statut
    demande.decide_par = decide_par
    demande.date_decision = timezone.now()
    demande.motif_decision = motif or ''
    try:
        demande.full_clean()
    except ValidationError as exc:
        raise ValueError(str(exc))
    demande.save()
    return demande


# ── XFLT2 — Génération des coûts récurrents de contrat ─────────────────────────

def _contrat_actif_sur_periode(contrat, annee, mois):
    """XFLT2 — Vrai si le ``ContratVehicule`` couvre le mois ``annee-mois``.

    ``date_debut`` doit être <= à la fin du mois cible, et ``date_fin`` (si
    renseignée) doit être >= au début du mois cible. Un contrat sans
    ``date_fin`` (durée indéterminée) reste actif indéfiniment.
    """
    import calendar

    debut_mois = datetime.date(annee, mois, 1)
    dernier_jour = calendar.monthrange(annee, mois)[1]
    fin_mois = datetime.date(annee, mois, dernier_jour)

    if contrat.date_debut is not None and contrat.date_debut > fin_mois:
        return False
    if contrat.date_fin is not None and contrat.date_fin < debut_mois:
        return False
    return True


def generer_couts_contrat(company, period):
    """XFLT2 — Matérialise l'échéance récurrente des contrats véhicule DUS
    pour ``period``.

    ``period`` est une chaîne ``'YYYY-MM'``. Pour chaque ``ContratVehicule``
    (XFLT1) de la société qui COUVRE ce mois (``date_debut``/``date_fin``),
    crée UNE ``EcheanceContrat`` (XFLT2) portant le ``montant_recurrent`` du
    contrat — sauf si une échéance existe déjà pour ce couple
    ``(contrat, period)`` (contrainte ``unique_together`` + vérification
    applicative avant écriture) : la génération est donc IDEMPOTENTE, deux
    exécutions sur la même période ne créent jamais de doublon.

    NOTE (repli XFLT3) : tant que ``CoutVehicule`` (grand livre unifié,
    XFLT3) n'existe pas sur cette branche, la matérialisation utilise le
    modèle propre ``EcheanceContrat``. Le jour où ``CoutVehicule`` existe,
    ce service devra y écrire à la place (catégorie ``contrat``) — voir
    XFLT3 pour le branchement.

    Multi-tenant : ``company`` est toujours posée côté serveur. Retourne un
    dict scopé société ::

        {'company_id', 'period', 'nb_contrats_actifs', 'nb_creees',
         'nb_existantes', 'echeances': [<EcheanceContrat>, …]}  # nouvelles uniquement

    Aucune écriture hors ``EcheanceContrat`` ; l'opération est sûre à relancer.
    """
    from django.db import IntegrityError, transaction

    from .models import ContratVehicule, EcheanceContrat

    try:
        annee, mois = (int(part) for part in period.split('-'))
    except (ValueError, AttributeError):
        raise ValueError(
            "Période invalide : format attendu 'YYYY-MM'.")

    contrats = ContratVehicule.objects.filter(company=company)
    contrats_actifs = [
        c for c in contrats if _contrat_actif_sur_periode(c, annee, mois)
    ]

    deja_generes = set(
        EcheanceContrat.objects
        .filter(company=company, period=period,
                contrat__in=[c.id for c in contrats_actifs])
        .values_list('contrat_id', flat=True)
    )

    date_echeance = datetime.date(annee, mois, 1)
    creees = []
    nb_existantes = 0
    for contrat in contrats_actifs:
        if contrat.id in deja_generes:
            nb_existantes += 1
            continue
        try:
            with transaction.atomic():
                echeance = EcheanceContrat.objects.create(
                    company=company,
                    contrat=contrat,
                    period=period,
                    date_echeance=date_echeance,
                    montant=contrat.montant_recurrent,
                )
        except IntegrityError:
            # Course concurrente sur le même (contrat, period) : une autre
            # exécution a déjà créé la ligne — comportement idempotent.
            nb_existantes += 1
            continue
        creees.append(echeance)

    return {
        'company_id': company.id,
        'period': period,
        'nb_contrats_actifs': len(contrats_actifs),
        'nb_creees': len(creees),
        'nb_existantes': nb_existantes,
        'echeances': creees,
    }


# ── XFLT4 — Cycle de vie du véhicule (transition de statut journalisée) ────────

def changer_statut_vehicule(vehicule, nouveau_statut, user=None):
    """XFLT4 — Change le statut d'un ``Vehicule`` et journalise la transition.

    Le passage ``commande`` → ``actif`` est BLOQUÉ (``ValueError``) tant que
    la checklist de mise en service n'est pas complète (immatriculation
    faite, plaques, assurance active, carte grise reçue — voir
    ``Vehicule.checklist_mise_en_service_ok``). Tout autre changement de
    statut est libre.

    À chaque transition RÉELLE (statut effectivement différent), une entrée
    ``JournalStatutVehicule`` est créée (ancien→nouveau, utilisateur,
    horodatage serveur-side). Un changement vers le MÊME statut est un no-op
    silencieux (aucune entrée de journal).

    Retourne le véhicule mis à jour. Lève ``ValueError`` sur un statut cible
    invalide ou la checklist incomplète (message FR, utilisable tel quel côté
    API).
    """
    from .models import JournalStatutVehicule, Vehicule

    statuts_valides = {choice for choice, _ in Vehicule.Statut.choices}
    if nouveau_statut not in statuts_valides:
        raise ValueError("Statut de véhicule invalide.")

    ancien_statut = vehicule.statut
    if ancien_statut == nouveau_statut:
        return vehicule

    if ancien_statut == Vehicule.Statut.COMMANDE \
            and nouveau_statut == Vehicule.Statut.ACTIF \
            and not vehicule.checklist_mise_en_service_ok():
        raise ValueError(
            "Impossible de passer le véhicule en actif : la checklist de "
            "mise en service n'est pas complète (immatriculation, plaques, "
            "assurance active, carte grise reçue).")

    vehicule.statut = nouveau_statut
    vehicule.save(update_fields=['statut'])

    JournalStatutVehicule.objects.create(
        company=vehicule.company,
        vehicule=vehicule,
        ancien_statut=ancien_statut,
        nouveau_statut=nouveau_statut,
        user=user,
    )

    return vehicule


# ── XFLT6 — Import relevé carte carburant / Jawaz (CSV) + rapprochement ────────

def _parse_montant_csv(valeur):
    """XFLT6 — Parse un montant CSV (accepte virgule ou point décimal)."""
    if valeur in (None, ''):
        return None
    try:
        return float(str(valeur).strip().replace(',', '.'))
    except (ValueError, TypeError):
        return None


def _parse_date_csv(valeur):
    """XFLT6 — Parse une date CSV au format ISO 'YYYY-MM-DD'."""
    if not valeur:
        return None
    try:
        return datetime.date.fromisoformat(str(valeur).strip())
    except ValueError:
        return None


def importer_releve_carte(carte, contenu_csv):
    """XFLT6 — Importe un relevé de carte carburant / Jawaz (CSV) et
    rapproche les lignes.

    ``contenu_csv`` est le TEXTE du fichier CSV (colonnes attendues, avec
    en-tête, insensible à la casse : ``date``, ``montant``, ``litres``,
    ``station`` ou ``gare``). Aucun appel réseau — import fichier uniquement.

    Pour chaque ligne :

    * une ligne avec ``litres`` renseigné (> 0) crée un ``PleinCarburant``
      (carte carburant, FLOTTE12) rattaché au véhicule de la carte ;
    * une ligne SANS ``litres`` (péage/Jawaz) crée un ``CoutVehicule``
      (XFLT3) catégorie ``peage``, avec ``reference_piece`` taggée
      ``'Jawaz'`` — nécessite un ``actif_flotte`` résolu depuis le véhicule
      de la carte (une carte sans véhicule attribué → ligne « non
      rapprochée », rien n'est créé) ;
    * une ligne DÉJÀ présente (même date + montant ± centime, pour le MÊME
      véhicule) est marquée DOUBLON et ignorée — l'import est donc
      IDEMPOTENT (un ré-import ne crée jamais de doublon) ;
    * une ligne sans véhicule résolu (carte sans ``vehicule``) est comptée
      « non rapprochée » et rien n'est créé.

    Retourne un dict rapport ::

        {'nb_lignes': N, 'crees': N, 'doublons': N, 'non_rapprochees': N,
         'erreurs': [{'ligne': i, 'motif': str}, …]}

    Multi-tenant : la société est celle de ``carte`` (jamais du corps de
    requête).
    """
    import csv
    import io

    from .models import CoutVehicule, PleinCarburant

    company = carte.company
    vehicule = carte.vehicule

    reader = csv.DictReader(io.StringIO(contenu_csv))
    # Normalise les en-têtes (insensible à la casse/espaces).
    if reader.fieldnames:
        reader.fieldnames = [
            (name or '').strip().lower() for name in reader.fieldnames]

    crees = 0
    doublons = 0
    non_rapprochees = 0
    erreurs = []

    for i, row in enumerate(reader, start=1):
        date_ = _parse_date_csv(row.get('date'))
        montant = _parse_montant_csv(row.get('montant'))
        litres = _parse_montant_csv(row.get('litres'))
        station = (row.get('station') or row.get('gare') or '').strip()

        if date_ is None or montant is None:
            erreurs.append({
                'ligne': i,
                'motif': "Date ou montant invalide/manquant.",
            })
            continue

        if vehicule is None:
            non_rapprochees += 1
            continue

        if litres and litres > 0:
            # Rapprochement : plein déjà présent (même véhicule/date/montant
            # ± 0.01) → doublon ignoré.
            deja_present = PleinCarburant.objects.filter(
                company=company, vehicule=vehicule, date_plein=date_,
                prix_total__gte=montant - 0.01,
                prix_total__lte=montant + 0.01,
            ).exists()
            if deja_present:
                doublons += 1
                continue
            PleinCarburant.objects.create(
                company=company, vehicule=vehicule, date_plein=date_,
                kilometrage=vehicule.kilometrage, quantite=litres,
                prix_total=montant, station=station,
            )
            crees += 1
        else:
            actif = getattr(vehicule, 'actif_flotte', None)
            if actif is None:
                non_rapprochees += 1
                continue
            deja_present = CoutVehicule.objects.filter(
                company=company, actif_flotte=actif, categorie='peage',
                date=date_, montant__gte=montant - 0.01,
                montant__lte=montant + 0.01,
            ).exists()
            if deja_present:
                doublons += 1
                continue
            CoutVehicule.objects.create(
                company=company, actif_flotte=actif, categorie='peage',
                date=date_, montant=montant, fournisseur=station,
                reference_piece='Jawaz',
            )
            crees += 1

    return {
        'nb_lignes': crees + doublons + non_rapprochees + len(erreurs),
        'crees': crees,
        'doublons': doublons,
        'non_rapprochees': non_rapprochees,
        'erreurs': erreurs,
    }


# ── XFLT8 — TVA carburant : récupérable vs non déductible ──────────────────────

def classifier_tva_recuperable(vehicule):
    """XFLT8 — Classification PAR DÉFAUT de la récupérabilité TVA d'un plein.

    Règle CGI TVA (Maroc) simplifiée : le gasoil sur un véhicule
    ``type_fiscal='utilitaire'`` est RÉCUPÉRABLE ; le carburant sur un
    véhicule ``type_fiscal='tourisme'`` est NON DÉDUCTIBLE. Sans
    ``type_fiscal`` renseigné (valeur vide, XFLT4), on retombe sur le
    comportement historique : récupérable par défaut (aucune régression pour
    les véhicules déjà saisis avant XFLT8).

    Lecture seule — un ``PleinCarburant.tva_recuperable`` DÉJÀ posé explicitement
    (override founder) n'est jamais recalculé par cette fonction ; elle ne sert
    qu'à proposer une valeur PAR DÉFAUT à la création.
    """
    from .models import Vehicule

    type_fiscal = getattr(vehicule, 'type_fiscal', '') or ''
    if type_fiscal == Vehicule.TypeFiscal.TOURISME:
        return False
    # 'utilitaire' ou vide (type fiscal inconnu) → récupérable par défaut.
    return True


# ── XFLT10 — Périodicité visite technique NARSA auto-calculée ──────────────────

def _ajouter_mois(date_ref, mois):
    """Additionne ``mois`` mois à ``date_ref``, gère le débordement de fin de
    mois (même logique que ``VisiteTechnique.calculer_date_prochaine``)."""
    total = date_ref.month - 1 + int(mois)
    year = date_ref.year + total // 12
    month = total % 12 + 1
    if month == 12:
        last_day = 31
    else:
        last_day = (datetime.date(year, month + 1, 1)
                    - datetime.timedelta(days=1)).day
    day = min(date_ref.day, last_day)
    return datetime.date(year, month, day)


def prochaine_visite_narsa(vehicule, today=None):
    """XFLT10 — Propose la prochaine date de visite technique NARSA.

    Règles marocaines (simplifiées, éditables par le founder à la saisie —
    cette fonction ne fait QUE proposer une valeur par défaut, jamais
    n'écrase une saisie manuelle) :

    - ``type_fiscal='utilitaire'`` (transport/utilitaire) : périodicité
      6 mois dès la mise en circulation.
    - Sinon (véhicule particulier, ``type_fiscal`` vide ou ``'tourisme'``) :
      1re visite à 5 ans, puis tous les 2 ans jusqu'à 10 ans, puis annuelle
      au-delà de 10 ans.

    La date de mise en circulation est lue via le sélecteur flotte
    (``CarteGriseVehicule.date_mise_circulation``, FLOTTE23) — jamais
    dupliquée sur ``Vehicule`` (XFLT4). Retourne ``None`` si aucune date de
    mise en circulation n'est connue (rien à proposer).
    """
    from .selectors import date_mise_circulation_vehicule

    if today is None:
        today = datetime.date.today()

    mise_en_circulation = date_mise_circulation_vehicule(vehicule)
    if mise_en_circulation is None:
        return None

    type_fiscal = getattr(vehicule, 'type_fiscal', '') or ''
    if type_fiscal == 'utilitaire':
        # Utilitaire/transport : périodicité 6 mois depuis la mise en
        # circulation, en avançant par tranches de 6 mois jusqu'à couvrir
        # aujourd'hui (prochaine échéance future).
        proposition = _ajouter_mois(mise_en_circulation, 6)
        while proposition < today:
            proposition = _ajouter_mois(proposition, 6)
        return proposition

    age_ans = (today - mise_en_circulation).days / 365.25
    premiere_visite = _ajouter_mois(mise_en_circulation, 60)  # 5 ans
    if today < premiere_visite:
        return premiere_visite

    if age_ans < 10:
        # Tous les 2 ans après la première visite (5 ans), jusqu'à 10 ans.
        proposition = premiere_visite
        while proposition < today:
            proposition = _ajouter_mois(proposition, 24)
        return proposition

    # Au-delà de 10 ans : annuelle.
    dix_ans = _ajouter_mois(mise_en_circulation, 120)
    proposition = dix_ans
    while proposition < today:
        proposition = _ajouter_mois(proposition, 12)
    return proposition


# ── XFLT11 — Imputation automatique du conducteur sur les infractions ──────────

def conducteur_a_la_date(vehicule, dt):
    """XFLT11 — Conducteur affecté à ``vehicule`` à l'horodatage ``dt``.

    Résout l'affectation dont la période ``[date_debut, date_fin]`` couvre
    ``dt`` (``date_fin`` nullable = affectation en cours, couvre toute date
    ``>= date_debut``). Ne s'applique qu'aux infractions rattachées à un
    ``Vehicule`` (l'historique d'affectation est propre aux véhicules, pas
    aux engins) — retourne ``None`` si ``vehicule`` est ``None`` ou ``dt``
    absent, ou si aucune affectation ne couvre la date (véhicule non
    affecté à ce moment-là). Lecture seule.
    """
    from django.db.models import Q

    from .models import AffectationConducteur

    if vehicule is None or dt is None:
        return None

    qs = AffectationConducteur.objects.filter(
        vehicule=vehicule, date_debut__lte=dt,
    ).filter(
        Q(date_fin__isnull=True) | Q(date_fin__gte=dt)
    ).order_by('-date_debut', '-id')
    affectation = qs.first()
    return affectation.conducteur if affectation is not None else None


# ── XFLT12 — Catalogue de modèles véhicule ──────────────────────────────────────

# Champs du véhicule pré-remplis depuis le modèle sélectionné, et le champ
# source correspondant sur ``ModeleVehicule``.
PREFILL_DEPUIS_MODELE = {
    'energie': 'energie',
    'puissance_fiscale': 'puissance_fiscale',
    'valeur': 'valeur_catalogue',
}


def prefill_depuis_modele(vehicule_data, modele):
    """XFLT12 — Pré-remplit les champs vides de ``vehicule_data`` depuis
    ``modele`` (``ModeleVehicule``), SANS écraser une valeur déjà présente.

    ``vehicule_data`` est un dict (typiquement ``serializer.validated_data``
    avant sauvegarde). Un champ est considéré « vide » s'il est absent du
    dict, ``None``, ou chaîne vide. Retourne le dict modifié (mutation in
    place ET retour, pour un usage direct). ``modele=None`` ne change rien.
    """
    if modele is None:
        return vehicule_data
    for champ_vehicule, champ_modele in PREFILL_DEPUIS_MODELE.items():
        valeur_actuelle = vehicule_data.get(champ_vehicule)
        if valeur_actuelle not in (None, ''):
            continue
        valeur_modele = getattr(modele, champ_modele, None)
        if valeur_modele not in (None, ''):
            vehicule_data[champ_vehicule] = valeur_modele
    return vehicule_data


# ── XFLT13 — Inspections périodiques paramétrables (check-lists DVIR) ──────────

def traiter_items_fail(inspection):
    """XFLT13 — Crée un ``SignalementVehicule`` (XFLT5) pour chaque item
    ``resultat='fail'`` de ``inspection.resultats``.

    Un signalement est créé PAR item en échec, gravité ``moyenne`` par
    défaut (``critique`` si l'item porte ``"bloquant": true`` dans le modèle
    d'inspection correspondant — recherché par libellé), description
    reprenant le libellé de l'item + le nom de l'inspection. Idempotent au
    niveau appelant (appelée une seule fois à la création de l'inspection) —
    ne déduplique pas elle-même (chaque appel crée les signalements).
    Retourne la liste des ``SignalementVehicule`` créés.
    """
    from .models import SignalementVehicule

    items_modele = {
        item.get('libelle'): item
        for item in (inspection.modele_inspection.items or [])
    }

    crees = []
    for resultat_item in (inspection.resultats or []):
        if resultat_item.get('resultat') != 'fail':
            continue
        libelle = resultat_item.get('libelle', '')
        item_modele = items_modele.get(libelle, {})
        bloquant = bool(item_modele.get('bloquant'))
        gravite = (SignalementVehicule.Gravite.CRITIQUE if bloquant
                   else SignalementVehicule.Gravite.MOYENNE)
        signalement = SignalementVehicule.objects.create(
            company=inspection.company,
            actif_flotte=inspection.actif_flotte,
            conducteur=inspection.conducteur,
            auteur=inspection.auteur,
            description=(
                f"Inspection « {inspection.modele_inspection.nom} » — "
                f"item en échec : {libelle}"),
            gravite=gravite,
        )
        crees.append(signalement)
    return crees


def taux_completion_inspections_par_conducteur(company, periode=None):
    """XFLT13 — Taux de complétion des items d'inspection, par conducteur.

    Pour chaque conducteur ayant réalisé au moins une inspection sur la
    société (filtrable par ``periode`` = ``(debut, fin)`` inclusif sur
    ``date_inspection``), calcule le taux d'items ``pass`` sur le total
    d'items renseignés à travers toutes ses inspections. Lecture seule.
    Retourne une liste ``[{'conducteur_id', 'conducteur_nom', 'nb_inspections',
    'nb_items', 'nb_pass', 'taux_completion'}, …]`` triée par conducteur.
    """
    from .models import InspectionVehicule

    qs = InspectionVehicule.objects.filter(
        company=company, conducteur__isnull=False,
    ).select_related('conducteur')
    if periode is not None:
        debut, fin = periode
        qs = qs.filter(
            date_inspection__date__gte=debut, date_inspection__date__lte=fin)

    par_conducteur = {}
    for inspection in qs:
        cid = inspection.conducteur_id
        entree = par_conducteur.setdefault(cid, {
            'conducteur_id': cid,
            'conducteur_nom': inspection.conducteur.nom,
            'nb_inspections': 0,
            'nb_items': 0,
            'nb_pass': 0,
        })
        entree['nb_inspections'] += 1
        for item in (inspection.resultats or []):
            entree['nb_items'] += 1
            if item.get('resultat') == 'pass':
                entree['nb_pass'] += 1

    resultats = []
    for entree in par_conducteur.values():
        taux = (entree['nb_pass'] / entree['nb_items'] * 100
                if entree['nb_items'] else 0.0)
        entree['taux_completion'] = round(taux, 1)
        resultats.append(entree)

    resultats.sort(key=lambda e: e['conducteur_nom'])
    return resultats


# ── XFLT14 — Garanties véhicule & pièces ────────────────────────────────────────

def garantie_active_pour(actif_flotte, today=None):
    """XFLT14 — Garantie(s) ACTIVE(S) couvrant ``actif_flotte`` à ``today``.

    Lit le kilométrage courant depuis ``actif_flotte.vehicule.kilometrage``
    (``None`` pour un engin — la garantie km n'est alors jamais évaluée sur
    ce critère). Retourne la liste des ``GarantieFlotte`` de l'actif dont
    ``couvre(today, kilometrage)`` est vrai (peut en retourner plusieurs si
    plusieurs composants sont garantis). Lecture seule.
    """
    from .models import GarantieFlotte

    if today is None:
        today = datetime.date.today()

    vehicule = getattr(actif_flotte, 'vehicule', None)
    kilometrage = getattr(vehicule, 'kilometrage', None) if vehicule else None

    garanties = GarantieFlotte.objects.filter(actif_flotte=actif_flotte)
    return [g for g in garanties if g.couvre(today, kilometrage)]
