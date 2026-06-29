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
