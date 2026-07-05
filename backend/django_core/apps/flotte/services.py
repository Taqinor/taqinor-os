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

    XFLT19 — À la clôture, si ``montant_devis`` est renseigné, calcule
    l'écart facture (``cout_total``) vs devis en % (``ecart_facture_devis_pct``,
    signé — positif si la facture dépasse le devis) et le journalise (posé
    en base, jamais juste loggé — consultable après coup). Un écart absolu
    > ``ParametreApprobationOR.ecart_alerte_pct`` (défaut 10 %) est un
    warning NON bloquant (la clôture réussit toujours).

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

    if ordre.montant_devis and float(ordre.montant_devis) > 0:
        # cout_total n'est (re)dérivé qu'à ordre.save() — le calculer ici
        # depuis les deux postes bruts pour ne pas lire une valeur figée
        # avant la sauvegarde.
        cout_total_actuel = (
            float(ordre.cout_main_oeuvre or 0)
            + float(ordre.cout_pieces or 0))
        ecart = (
            (cout_total_actuel - float(ordre.montant_devis))
            / float(ordre.montant_devis) * 100)
        ordre.ecart_facture_devis_pct = round(ecart, 2)

    ordre.save()

    echeance_close = None
    if cloturer_echeance and ordre.echeance_id is not None:
        echeance = ordre.echeance
        if echeance.statut != EcheanceEntretien.Statut.FAIT:
            echeance.statut = EcheanceEntretien.Statut.FAIT
            echeance.save(update_fields=['statut'])
            echeance_close = echeance

    return ordre, echeance_close


def ecart_facture_devis_alerte(ordre):
    """XFLT19 — ``True`` si l'écart facture/devis de l'OR dépasse le seuil
    d'alerte de la société (défaut 10 %, ``ParametreApprobationOR``).
    Lecture seule ; ``None``/``False`` si ``ecart_facture_devis_pct`` n'est
    pas calculé (pas de devis saisi, ou OR pas encore clôturé)."""
    from .models import ParametreApprobationOR

    if ordre.ecart_facture_devis_pct is None:
        return False
    seuil = float(ParametreApprobationOR.pour(ordre.company).ecart_alerte_pct)
    return abs(float(ordre.ecart_facture_devis_pct)) > seuil


def approuver_ordre_reparation(ordre, user):
    """XFLT19 — Approuve le devis de réparation (statut → ``approuve``).

    Pose ``approuve_par``/``date_approbation`` côté serveur. Lève
    ``ValueError`` si l'OR n'est pas au statut ``devis_recu``."""
    from django.utils import timezone

    from .models import OrdreReparation

    if ordre.statut != OrdreReparation.Statut.DEVIS_RECU:
        raise ValueError(
            "Seul un OR au statut « devis reçu » peut être approuvé.")

    ordre.statut = OrdreReparation.Statut.APPROUVE
    ordre.approuve_par = user
    ordre.date_approbation = timezone.now()
    ordre.save(update_fields=[
        'statut', 'approuve_par', 'date_approbation'])
    return ordre


def transition_statut_or_autorisee(ordre, nouveau_statut):
    """XFLT19 — ``(ok: bool, message: str)`` — vérifie que le passage en
    ``en_cours`` respecte le seuil d'approbation société.

    Un OR dont ``montant_devis`` dépasse
    ``ParametreApprobationOR.seuil_approbation`` ne peut passer en
    ``en_cours`` que depuis le statut ``approuve`` (l'action ``approuver/``
    doit avoir été appelée par un rôle gestionnaire au préalable). Sous le
    seuil, ou sans devis saisi, la transition est toujours libre (aucune
    régression sur la chaîne existante ouvert→en_cours→clôturé). Lecture
    seule.
    """
    from .models import OrdreReparation, ParametreApprobationOR

    if nouveau_statut != OrdreReparation.Statut.EN_COURS:
        return True, ''
    if not ordre.montant_devis:
        return True, ''

    seuil = float(ParametreApprobationOR.pour(ordre.company).seuil_approbation)
    if float(ordre.montant_devis) <= seuil:
        return True, ''
    if ordre.statut == OrdreReparation.Statut.APPROUVE:
        return True, ''

    return False, (
        f"Ce devis ({float(ordre.montant_devis):.2f} MAD) dépasse le seuil "
        f"d'approbation ({seuil:.2f} MAD) : il doit être approuvé par un "
        "gestionnaire avant de passer en cours.")


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


# ── XFLT24 — Géofencing sur les données télématiques (purement local) ────────
#
# Évalue les ``ReleveTelematique`` (FLOTTE27) déjà en base — manuels ou issus
# du fournisseur — contre les ``ZoneGeographique`` de la société : PUREMENT
# LOCAL (distance haversine en Python), aucun appel réseau, aucune dépendance
# nouvelle. Ne dépend PAS de ``telematique_active()`` pour ÉVALUER (un relevé
# saisi à la main déclenche l'alerte comme un relevé télématique — la gate
# FLOTTE27 ne bloque QUE la synchronisation fournisseur, jamais la lecture des
# relevés déjà ingérés) — reste néanmoins un NO-OP total si la télématique
# n'a produit aucun relevé (aucun relevé à évaluer, aucune alerte).

def _releve_dans_zone(releve, zone):
    """XFLT24 — True si ``releve`` (position GPS) tombe dans le cercle
    ``zone`` (centre + rayon). Lecture seule ; ``None`` si coordonnées
    absentes de l'un des deux côtés (jamais d'exception)."""
    if releve.position_lat is None or releve.position_lng is None:
        return False
    distance_km = _distance_haversine_km(
        releve.position_lat, releve.position_lng,
        zone.centre_lat, zone.centre_lng)
    if distance_km is None:
        return False
    return (distance_km * 1000.0) <= float(zone.rayon_metres)


def _hors_plage_horaire(releve, zone):
    """XFLT24 — True si l'horodatage de ``releve`` tombe HORS la plage
    ``[heure_debut_autorisee, heure_fin_autorisee]`` de ``zone``. Renvoie
    ``False`` si la zone ne définit aucune plage (aucune contrainte
    horaire) — comportement permissif par défaut."""
    if zone.heure_debut_autorisee is None or zone.heure_fin_autorisee is None:
        return False
    heure = releve.horodatage.time()
    return not (zone.heure_debut_autorisee <= heure <= zone.heure_fin_autorisee)


def _alerter_zone(releve, zone, motif):
    """XFLT24 — Diffuse une alerte géofencing best-effort (jamais ne lève).

    Notifie via ``apps.notifications.services.notify`` (import LOCAL — la
    flotte ne dépend jamais des modèles d'une autre app) le conducteur
    actuellement affecté au véhicule de l'actif concerné, s'il existe."""
    try:
        from apps.notifications.services import notify
    except Exception:
        return None

    user = None
    try:
        actif = releve.actif_flotte
        if actif is not None and actif.vehicule_id is not None:
            from .selectors import conducteur_actuel_du_vehicule
            conducteur = conducteur_actuel_du_vehicule(
                releve.company, actif.vehicule_id)
            user = conducteur.user if conducteur is not None else None
    except Exception:
        user = None
    if user is None:
        return None

    try:
        return notify(
            user=user,
            event_type='flotte_zone_alerte',
            title=f'Géofencing : {zone.nom}',
            body=(
                f'{releve.actif_flotte.label} — {motif} '
                f'(« {zone.nom} », {releve.horodatage:%Y-%m-%d %H:%M}).'
            ),
            link='/flotte/releves-telematiques',
            company=releve.company,
        )
    except Exception:
        return None


def evaluer_geofencing(company, *, releves=None, alerter=True):
    """XFLT24 — Évalue le géofencing sur les relevés télématiques d'une société.

    Pour chaque ``ReleveTelematique`` de ``company`` (ou le sous-ensemble
    fourni via ``releves``, un itérable de ``ReleveTelematique`` DÉJÀ scopé
    société — jamais revalidé ici), teste sa position contre CHAQUE
    ``ZoneGeographique`` active de la société :

    * s'il tombe dans une zone ``interdite`` → alerte « entrée en zone
      interdite » ;
    * si la zone porte une plage horaire autorisée et que l'horodatage du
      relevé tombe hors cette plage → alerte « mouvement hors plage
      horaire autorisée ».

    Un relevé hors de toute zone (ou dans une zone ``depot``/``chantier``
    sans dépassement horaire) ne déclenche RIEN. Chaque alerte est diffusée
    au mieux (``alerter=True``) via ``notifications.notify`` — un échec de
    notification n'interrompt jamais l'évaluation.

    PUREMENT LOCAL : aucun appel réseau, aucune dépendance nouvelle. Multi-
    tenant : tout est scopé ``company`` côté serveur.

    Retourne la liste des alertes détectées, chacune un dict ``{'releve_id',
    'zone_id', 'zone_nom', 'motif'}``.
    """
    from .models import ReleveTelematique, ZoneGeographique

    if releves is None:
        releves = ReleveTelematique.objects.filter(
            company=company).select_related('actif_flotte')

    zones = list(ZoneGeographique.objects.filter(
        company=company, actif=True))
    if not zones:
        return []

    alertes = []
    for releve in releves:
        for zone in zones:
            if not _releve_dans_zone(releve, zone):
                continue

            motif = None
            if zone.type_zone == ZoneGeographique.TypeZone.INTERDITE:
                motif = 'entrée détectée en zone interdite'
            elif _hors_plage_horaire(releve, zone):
                motif = 'mouvement hors plage horaire autorisée'

            if motif is None:
                continue

            alertes.append({
                'releve_id': releve.id,
                'zone_id': zone.id,
                'zone_nom': zone.nom,
                'motif': motif,
            })
            if alerter:
                _alerter_zone(releve, zone, motif)

    return alertes


# ── XFLT25 — Codes défaut moteur (DTC) sur les relevés télématiques ──────────
#
# Un code critique déclenche une alerte + un ``SignalementVehicule`` (XFLT5)
# gravité critique, IDEMPOTENT : pas de doublon ouvert pour le même
# (code, véhicule). Key-gated comme toute la télématique (FLOTTE27) — la
# saisie MANUELLE du code reste toujours possible, gate ou pas.

# Préfixes DTC par défaut (norme OBD-II générique) si la société n'a pas
# encore édité son propre référentiel ``code_dtc``. P0xxx = moteur/chaîne
# cinématique générique = criticité par défaut la plus haute (sécurité).
_CRITICITE_DTC_DEFAUT = {
    'P0': 'critique',
    'P1': 'moyenne',
    'P2': 'moyenne',
    'P3': 'moyenne',
    'B0': 'moyenne',   # carrosserie
    'C0': 'moyenne',   # châssis
    'U0': 'faible',    # réseau/communication
}


def criticite_dtc(company, code):
    """XFLT25 — Criticité d'un code DTC pour ``company`` (lecture seule).

    Cherche d'abord une entrée ÉDITABLE du référentiel société
    (``ReferentielFlotte`` domaine ``code_dtc``) dont ``code`` est un préfixe
    du code fourni (préfixe le plus long qui matche l'emporte — ex. ``P03``
    l'emporte sur ``P0``) ; à défaut, retombe sur le référentiel générique
    OBD-II par défaut (``_CRITICITE_DTC_DEFAUT``). Retourne ``'faible'`` si
    rien ne correspond (comportement permissif par défaut). Ne lève jamais.
    """
    from .models import ReferentielFlotte

    code = (code or '').strip().upper()
    if not code:
        return 'faible'

    entrees = list(ReferentielFlotte.objects.filter(
        company=company, domaine=ReferentielFlotte.Domaine.CODE_DTC,
        actif=True))
    meilleure = None
    for entree in entrees:
        prefixe = (entree.code or '').strip().upper()
        if prefixe and code.startswith(prefixe):
            if meilleure is None or len(prefixe) > len(meilleure.code):
                meilleure = entree
    if meilleure is not None:
        return (meilleure.libelle or 'faible').strip().lower()

    for prefixe, criticite in _CRITICITE_DTC_DEFAUT.items():
        if code.startswith(prefixe):
            return criticite
    return 'faible'


def traiter_codes_defaut(releve):
    """XFLT25 — Traite les ``codes_defaut`` d'un ``ReleveTelematique`` :
    déclenche une alerte + un ``SignalementVehicule`` gravité CRITIQUE pour
    chaque code critique (idempotent : pas de doublon ouvert pour le même
    couple (code, actif)).

    Un code non critique (moyenne/faible) ne fait rien de plus que ce que la
    saisie a déjà posé (aucun signalement) — seul le CRITIQUE agit. Key-gated
    implicitement par l'ingestion normale de la télématique : la saisie
    MANUELLE fonctionne toujours (ne dépend pas de ``telematique_active``).

    Retourne la liste des ``SignalementVehicule`` créés (vide si aucun code
    critique ou si tous ont déjà un signalement ouvert).
    """
    from .models import SignalementVehicule

    codes = releve.codes_defaut or []
    if not codes:
        return []

    crees = []
    for code in codes:
        if criticite_dtc(releve.company, code) != 'critique':
            continue

        # Idempotence : pas de doublon OUVERT pour le même code+véhicule.
        deja_ouvert = SignalementVehicule.objects.filter(
            company=releve.company,
            actif_flotte=releve.actif_flotte,
            statut__in=[SignalementVehicule.Statut.OUVERT,
                        SignalementVehicule.Statut.EN_COURS],
            description__contains=f'DTC {code}',
        ).exists()
        if deja_ouvert:
            continue

        signalement = SignalementVehicule.objects.create(
            company=releve.company,
            actif_flotte=releve.actif_flotte,
            description=(
                f'Code défaut moteur critique DTC {code} détecté '
                f'({releve.horodatage:%Y-%m-%d %H:%M}).'
            ),
            gravite=SignalementVehicule.Gravite.CRITIQUE,
        )
        crees.append(signalement)

        try:
            from apps.notifications.services import notify
            from .selectors import conducteur_actuel_du_vehicule
            actif = releve.actif_flotte
            user = None
            if actif is not None and actif.vehicule_id is not None:
                conducteur = conducteur_actuel_du_vehicule(
                    releve.company, actif.vehicule_id)
                user = conducteur.user if conducteur is not None else None
            if user is not None:
                notify(
                    user=user,
                    event_type='flotte_dtc_critique',
                    title=f'DTC critique : {code}',
                    body=(
                        f'{actif.label} — code défaut moteur critique '
                        f'{code} détecté.'),
                    link='/flotte/releves-telematiques',
                    company=releve.company,
                )
        except Exception:
            pass

    return crees


# ── XFLT28 — Rappels constructeur (recall) ──────────────────────────────────

def rapprocher_rappel(rappel):
    """XFLT28 — Rapproche un ``RappelConstructeur`` contre le parc de VIN de
    la société et crée un ``SignalementVehicule`` (XFLT5) PAR véhicule
    touché.

    Compare ``rappel.vin_concernes`` (liste de VIN, saisie constructeur —
    peut couvrir bien plus que le parc de la société) aux ``Vehicule.vin``
    (XFLT4) de la MÊME société : un VIN vide ne matche jamais (évite les
    faux positifs entre véhicules sans VIN renseigné). Chaque véhicule
    touché reçoit un signalement gravité MOYENNE portant la référence de la
    campagne — tous groupables via cette référence commune (recherche par
    description) pour un traitement en un seul ``OrdreReparation``.

    IDEMPOTENT : un véhicule déjà signalé pour la MÊME campagne (signalement
    ouvert ou en cours portant la référence) n'est pas re-signalé.

    Retourne ``{'crees': [<SignalementVehicule>, …], 'nb_vin_matches': int}``.
    """
    from .models import ActifFlotte, SignalementVehicule, Vehicule

    vins_campagne = {
        (vin or '').strip().upper()
        for vin in (rappel.vin_concernes or [])
        if (vin or '').strip()
    }
    if not vins_campagne:
        return {'crees': [], 'nb_vin_matches': 0}

    vehicules_touches = Vehicule.objects.filter(
        company=rappel.company, vin__in=vins_campagne)

    crees = []
    for vehicule in vehicules_touches:
        actif = ActifFlotte.objects.filter(
            company=rappel.company, vehicule=vehicule).first()
        if actif is None:
            continue

        marqueur = f'Rappel constructeur {rappel.reference_campagne}'
        deja_signale = SignalementVehicule.objects.filter(
            company=rappel.company, actif_flotte=actif,
            statut__in=[SignalementVehicule.Statut.OUVERT,
                        SignalementVehicule.Statut.EN_COURS],
            description__contains=marqueur,
        ).exists()
        if deja_signale:
            continue

        signalement = SignalementVehicule.objects.create(
            company=rappel.company,
            actif_flotte=actif,
            description=(
                f'{marqueur} ({rappel.constructeur}) — VIN {vehicule.vin} : '
                f'{rappel.description}'.strip(' :')
            ),
            gravite=SignalementVehicule.Gravite.MOYENNE,
        )
        crees.append(signalement)

    return {'crees': crees, 'nb_vin_matches': vehicules_touches.count()}


# ── XFLT30 — Ventilation d'une facture fournisseur sur plusieurs véhicules ───

def ventiler_cout_fournisseur(company, *, montant_total, actif_flotte_ids,
                              date, categorie=None, fournisseur='',
                              fournisseur_id_ref=None, reference_piece='',
                              repartitions=None, notes=''):
    """XFLT30 — Répartit une facture fournisseur en N ``CoutVehicule``
    (XFLT3), une ligne PAR actif, toutes portant la MÊME ``reference_piece``
    (réconciliation compta).

    Deux modes de répartition :

    * ``repartitions`` fourni (dict ``{actif_flotte_id: montant}``) : montants
      SAISIS explicitement — DOIVENT sommer exactement à ``montant_total``
      (sinon ``ValueError``, jamais de facture silencieusement mal répartie) ;
    * ``repartitions`` absent : répartition ÉGALE sur ``actif_flotte_ids`` —
      le montant est divisé et ARRONDI au centime, le reliquat (dû à
      l'arrondi) est ajouté à la DERNIÈRE ligne pour que la somme des lignes
      créées soit TOUJOURS exactement égale à ``montant_total`` (jamais de
      centime perdu ou en trop).

    Chaque actif de ``actif_flotte_ids`` doit appartenir à ``company`` (les
    autres sont IGNORÉS silencieusement plutôt que de faire échouer toute la
    ventilation — un id invalide isolé ne doit pas bloquer le reste).

    L'écriture comptable éventuelle (rapprochement, immobilisation…) reste du
    ressort de ``apps.compta`` (qui lira ce ledger via sélecteur) — CETTE
    fonction n'écrit JAMAIS hors de ``CoutVehicule`` (cross-app, voir
    CLAUDE.md).

    Retourne la liste des ``CoutVehicule`` créés (même ordre que
    ``actif_flotte_ids``, actifs invalides omis).
    """
    from .models import ActifFlotte, CoutVehicule

    if categorie is None:
        categorie = CoutVehicule.Categorie.AUTRE

    actifs_valides = list(
        ActifFlotte.objects.filter(company=company, id__in=actif_flotte_ids))
    actifs_par_id = {actif.id: actif for actif in actifs_valides}
    # Préserve l'ordre demandé par l'appelant (actifs invalides omis).
    ordre = [aid for aid in actif_flotte_ids if aid in actifs_par_id]
    if not ordre:
        return []

    if repartitions is not None:
        montants = [_arrondi_centime(repartitions[aid]) for aid in ordre]
        total_saisi = sum(montants)
        if _arrondi_centime(total_saisi) != _arrondi_centime(montant_total):
            raise ValueError(
                'La somme des montants saisis '
                f'({total_saisi}) ne correspond pas au montant total '
                f'({montant_total}).')
    else:
        n = len(ordre)
        part = _arrondi_centime(montant_total) / n
        montants = [_arrondi_centime(part) for _ in range(n)]
        # Reliquat d'arrondi (peut être positif ou négatif) ajouté à la
        # DERNIÈRE ligne : garantit une somme EXACTE au centime près.
        reliquat = _arrondi_centime(montant_total) - _arrondi_centime(
            sum(montants))
        montants[-1] = _arrondi_centime(montants[-1] + reliquat)

    crees = []
    for actif_id, montant in zip(ordre, montants):
        cout = CoutVehicule.objects.create(
            company=company,
            actif_flotte=actifs_par_id[actif_id],
            categorie=categorie,
            date=date,
            montant=montant,
            fournisseur=fournisseur,
            fournisseur_id_ref=fournisseur_id_ref,
            reference_piece=reference_piece,
            notes=notes,
        )
        crees.append(cout)

    return crees


def _arrondi_centime(valeur):
    """XFLT30 — Arrondit ``valeur`` au centime (2 décimales), type ``Decimal``
    préservé si fourni. Lecture seule, aucun effet de bord."""
    import decimal
    return decimal.Decimal(str(valeur)).quantize(
        decimal.Decimal('0.01'), rounding=decimal.ROUND_HALF_UP)


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
    # ZCTR11 — enrichissement fiscal du catalogue : pré-remplis SANS écraser
    # une saisie existante (même règle que les champs ci-dessus).
    'valeur_residuelle': 'valeur_residuelle',
    'pct_charges_non_deductibles': 'pct_charges_non_deductibles',
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


# ── XFLT16 — Cession / sortie de parc ───────────────────────────────────────────

def ceder_vehicule(vehicule, *, date_cession, prix_cession, acheteur='',
                   user=None):
    """XFLT16 — Cède (vend) un véhicule ``statut='a_vendre'`` (XFLT4).

    Exige le statut ``a_vendre`` (lève ``ValueError`` sinon). Le gain/perte
    de cession est calculé :

    * si le véhicule est rattaché à une ``compta.Immobilisation``
      (``Vehicule.immobilisation``) : DÉLÉGUÉ à
      ``apps.compta.services.calculer_cession`` + ``enregistrer_cession`` +
      ``poster_cession`` (jamais recalculé en doublon — la cession
      comptable existe déjà côté compta, FG120) ;
    * sinon (véhicule non immobilisé) : gain/perte simple =
      ``prix_cession - Vehicule.valeur`` (repli local, aucune écriture
      comptable à générer puisqu'il n'y a pas d'immobilisation).

    Pose ``date_cession``/``prix_cession``/``acheteur``, passe le statut à
    ``vendu`` (via ``changer_statut_vehicule``, journalisé). L'historique du
    véhicule (coûts, OR, affectations) reste intact — seuls les KPI actifs
    du tableau de bord (FLOTTE35) et les alertes d'échéances l'excluent
    désormais (filtre sur le statut, voir ``selectors``).

    Retourne ``{'vehicule', 'resultat_cession', 'source'}`` où ``source``
    vaut ``'compta'`` ou ``'local'``.
    """
    from .models import Vehicule
    from .services import changer_statut_vehicule

    if vehicule.statut != Vehicule.Statut.A_VENDRE:
        raise ValueError(
            "Le véhicule doit être au statut « à vendre » avant cession.")

    resultat_cession = None
    source = 'local'
    if vehicule.immobilisation_id is not None:
        from apps.compta.services import enregistrer_cession, poster_cession

        cession = enregistrer_cession(
            vehicule.immobilisation, date_cession=date_cession,
            prix_cession=prix_cession, user=user)
        poster_cession(cession, user=user)
        resultat_cession = float(cession.resultat_cession)
        source = 'compta'
    else:
        valeur_actuelle = float(vehicule.valeur or 0)
        resultat_cession = float(prix_cession or 0) - valeur_actuelle

    vehicule.date_cession = date_cession
    vehicule.prix_cession = prix_cession
    vehicule.acheteur = acheteur
    vehicule.save(update_fields=['date_cession', 'prix_cession', 'acheteur'])

    vehicule = changer_statut_vehicule(
        vehicule, Vehicule.Statut.VENDU, user=user)

    return {
        'vehicule': vehicule,
        'resultat_cession': round(resultat_cession, 2),
        'source': source,
    }


# ── XFLT17 — Charte véhicule + signatures sur l'état des lieux ─────────────────

def signer_etat_des_lieux(etat_des_lieux, *, role, nom):
    """XFLT17 — Appose une e-signature (nom saisi + horodatage serveur) sur
    l'état des lieux, loi 53-05 (comme le flux devis existant — pas de
    signature graphique).

    ``role`` vaut ``'conducteur'`` ou ``'responsable'``. Idempotent par
    rôle : une signature déjà posée pour ce rôle n'est jamais écrasée
    silencieusement (lève ``ValueError`` si déjà signée). ``nom`` est
    tronqué à 150 caractères (borne du champ). Retourne l'objet mis à jour.
    """
    from django.utils import timezone

    champs_valides = {'conducteur', 'responsable'}
    if role not in champs_valides:
        raise ValueError("Rôle de signature invalide.")

    champ_nom = f'signature_{role}'
    champ_horodatage = f'signature_{role}_horodatage'

    if getattr(etat_des_lieux, champ_nom):
        raise ValueError(
            f"L'état des lieux est déjà signé par le {role}.")

    setattr(etat_des_lieux, champ_nom, str(nom or '')[:150])
    setattr(etat_des_lieux, champ_horodatage, timezone.now())
    etat_des_lieux.save(update_fields=[champ_nom, champ_horodatage])
    return etat_des_lieux


def charte_courante(company):
    """XFLT17 — Version courante (la plus récente) de la charte véhicule de
    la société, ou ``None`` si aucune n'est publiée. Lecture seule."""
    from .models import CharteVehicule

    return CharteVehicule.objects.filter(
        company=company).order_by('-version').first()


def accuse_charte_manquant(conducteur):
    """XFLT17 — ``True`` si le conducteur n'a PAS accusé réception de la
    version courante de la charte véhicule (aucune charte publiée = jamais
    de warning). Lecture seule, sert à l'avertissement non bloquant à la
    première affectation."""
    from .models import AccuseCharte

    charte = charte_courante(conducteur.company)
    if charte is None:
        return False

    return not AccuseCharte.objects.filter(
        company=conducteur.company, conducteur=conducteur,
        version=charte.version,
    ).exists()


# ── XFLT18 — Budget flotte annuel vs réalisé ────────────────────────────────────

def verifier_depassements_budget(company, annee):
    """XFLT18 — Notifie (best-effort, IDEMPOTENT) les dépassements de budget
    flotte > 100 % pour une année.

    Calcule la variance via ``selectors.variance_budget_flotte`` ; pour
    chaque catégorie en dépassement (``niveau='rouge'``) dont la ligne
    ``BudgetFlotte`` n'a pas déjà ``notifie_depassement=True``, notifie les
    responsables/admins de la société (``apps.notifications.services.
    notify_many``, best-effort — jamais levé) puis marque la ligne comme
    notifiée. Un second appel sur la même période ne renvoie AUCUNE
    notification supplémentaire tant que le dépassement reste inchangé.

    Retourne la liste des catégories nouvellement notifiées (codes).
    """
    from .models import BudgetFlotte
    from .selectors import variance_budget_flotte

    variance = variance_budget_flotte(company, annee)
    notifiees = []

    for ligne in variance['categories']:
        if ligne['niveau'] != 'rouge':
            continue

        budget = BudgetFlotte.objects.filter(
            company=company, annee=annee, categorie=ligne['categorie'],
        ).first()
        if budget is None or budget.notifie_depassement:
            continue

        try:
            from django.contrib.auth import get_user_model

            from apps.notifications.models import EventType
            from apps.notifications.services import notify_many

            User = get_user_model()
            destinataires = User.objects.filter(
                company=company, is_active=True,
                role_legacy__in=['responsable', 'admin'])
            notify_many(
                destinataires, EventType.FLOTTE_BUDGET_DEPASSEMENT,
                title=f"Budget flotte dépassé : {ligne['categorie_display']}",
                body=(
                    f"Le budget {ligne['categorie_display']} {annee} est "
                    f"dépassé : {ligne['realise']} MAD réalisés pour "
                    f"{ligne['budgete']} MAD budgétés ({ligne['pct']} %)."
                ),
                company=company,
            )
        except Exception:
            pass

        budget.notifie_depassement = True
        budget.save(update_fields=['notifie_depassement'])
        notifiees.append(ligne['categorie'])

    return notifiees


# ── XFLT20 — Registre de remise clés / carte / badge / tag Jawaz ───────────────

def avertissement_accessoires_non_rendus(affectation):
    """XFLT20 — Message d'avertissement si le conducteur d'une affectation
    qui se termine (``date_fin`` renseignée) détient encore des accessoires
    non rendus sur LE VÉHICULE de l'affectation. Lecture seule, non
    bloquant. Retourne ``None`` si rien à signaler."""
    from .selectors import accessoires_non_rendus

    if affectation.date_fin is None:
        return None

    actif = getattr(affectation.vehicule, 'actif_flotte', None)
    if actif is None:
        return None

    non_rendus = [
        a for a in accessoires_non_rendus(
            affectation.company, affectation.conducteur_id)
        if a['actif_flotte_id'] == actif.id
    ]
    if not non_rendus:
        return None

    libelles = ', '.join(a['type_display'] for a in non_rendus)
    return (
        f"Accessoires non rendus par {affectation.conducteur} pour "
        f"{affectation.vehicule} : {libelles}.")


# ── XFLT21 — Journal d'audit flotte ─────────────────────────────────────────────

# Champs suivis sur Vehicule (diffs journalisés) — limité aux champs à
# valeur métier (statut, affectation-adjacents) pour éviter le bruit
# (dates de création, etc.).
_CHAMPS_SUIVIS_VEHICULE = ('statut', 'kilometrage', 'type_fiscal', 'modele_ref_id')
_CHAMPS_SUIVIS_AFFECTATION = ('conducteur_id', 'date_fin', 'actif')


def journaliser_activite(*, company, vehicule, type_objet, objet_id, champ,
                         ancienne_valeur, nouvelle_valeur, user=None):
    """XFLT21 — Crée une entrée ``ActiviteFlotte`` (immuable, jamais mise à
    jour ni supprimée). Les valeurs sont converties en ``str`` (tronquées à
    255 caractères, borne du champ) — aucune validation métier ici, c'est un
    simple journal."""
    from .models import ActiviteFlotte

    return ActiviteFlotte.objects.create(
        company=company, vehicule=vehicule, type_objet=type_objet,
        objet_id=objet_id, champ=champ,
        ancienne_valeur=str(ancienne_valeur if ancienne_valeur is not None
                            else '')[:255],
        nouvelle_valeur=str(nouvelle_valeur if nouvelle_valeur is not None
                            else '')[:255],
        user=user,
    )


def journaliser_diff_vehicule(avant, apres, user=None):
    """XFLT21 — Compare l'état AVANT/APRÈS d'un ``Vehicule`` (dicts de
    valeurs des champs suivis) et journalise chaque changement RÉEL.
    Retourne la liste des entrées créées (peut être vide)."""
    from .models import ActiviteFlotte

    crees = []
    for champ in _CHAMPS_SUIVIS_VEHICULE:
        ancienne = avant.get(champ)
        nouvelle = apres.get(champ)
        if ancienne == nouvelle:
            continue
        crees.append(journaliser_activite(
            company=apres['company'], vehicule=apres['instance'],
            type_objet=ActiviteFlotte.TypeObjet.VEHICULE,
            objet_id=apres['instance'].id, champ=champ,
            ancienne_valeur=ancienne, nouvelle_valeur=nouvelle, user=user))
    return crees


def journaliser_diff_affectation(avant, apres, user=None):
    """XFLT21 — Compare l'état AVANT/APRÈS d'une ``AffectationConducteur``
    (dicts de valeurs des champs suivis) et journalise chaque changement
    RÉEL, rattaché au véhicule de l'affectation. Retourne la liste des
    entrées créées (peut être vide)."""
    from .models import ActiviteFlotte

    crees = []
    for champ in _CHAMPS_SUIVIS_AFFECTATION:
        ancienne = avant.get(champ)
        nouvelle = apres.get(champ)
        if ancienne == nouvelle:
            continue
        crees.append(journaliser_activite(
            company=apres['company'], vehicule=apres['vehicule'],
            type_objet=ActiviteFlotte.TypeObjet.AFFECTATION,
            objet_id=apres['instance'].id, champ=champ,
            ancienne_valeur=ancienne, nouvelle_valeur=nouvelle, user=user))
    return crees


# ── XFLT22 — Import CSV du parc + opérations en masse ───────────────────────────

def creer_vehicule_import(company, ligne):
    """XFLT22 — Crée (ou saute si doublon) UN véhicule depuis une ligne
    d'import CSV (dict de colonnes déjà nettoyées), via ``apps.flotte.
    services`` — jamais les models directement (contrat du framework
    ``apps.dataimport``).

    Colonnes attendues : ``immatriculation`` (obligatoire, clé d'idempotence),
    ``marque``, ``modele``, ``energie``, ``kilometrage``, ``puissance_fiscale``
    (``cv``). Idempotent sur ``immatriculation`` : une ligne déjà présente pour
    la société est SAUTÉE (retourne ``'doublon'``), jamais mise à jour ni
    dupliquée. Retourne ``('cree'|'doublon'|'erreur', message|None)``.
    """
    from .models import Vehicule

    immatriculation = str(ligne.get('immatriculation', '')).strip()
    if not immatriculation:
        return 'erreur', "Immatriculation manquante."

    if Vehicule.objects.filter(
            company=company, immatriculation=immatriculation).exists():
        return 'doublon', None

    def _to_int(valeur):
        try:
            return int(float(str(valeur).strip().replace(',', '.')))
        except (ValueError, TypeError):
            return None

    energie_brute = str(ligne.get('energie', '') or '').strip().lower()
    energies_valides = {c for c, _ in Vehicule.Energie.choices}
    energie = energie_brute if energie_brute in energies_valides \
        else Vehicule.Energie.DIESEL

    try:
        Vehicule.objects.create(
            company=company,
            immatriculation=immatriculation,
            marque=str(ligne.get('marque', '') or '').strip(),
            modele=str(ligne.get('modele', '') or '').strip(),
            energie=energie,
            kilometrage=_to_int(ligne.get('kilometrage')) or 0,
            puissance_fiscale=_to_int(
                ligne.get('cv') or ligne.get('puissance_fiscale')),
        )
    except Exception as exc:  # noqa: BLE001 — ligne isolée, jamais bloquant
        return 'erreur', str(exc)

    return 'cree', None


def importer_vehicules_csv(company, lignes, *, dry_run=False):
    """XFLT22 — Importe une liste de lignes véhicule (dry-run ou commit).

    ``lignes`` est une liste de dicts (déjà parsés — bornes anti-DoS gérées
    par le framework ``apps.dataimport`` appelant). En ``dry_run=True``,
    simule (détection de doublon incluse) SANS écrire (utilise une
    transaction annulée). Retourne ``{'crees', 'doublons', 'erreurs':
    [{'ligne', 'message'}, …]}``.
    """
    from django.db import transaction

    crees = 0
    doublons = 0
    erreurs = []

    if dry_run:
        with transaction.atomic():
            for index, ligne in enumerate(lignes, start=1):
                statut, message = creer_vehicule_import(company, ligne)
                if statut == 'cree':
                    crees += 1
                elif statut == 'doublon':
                    doublons += 1
                else:
                    erreurs.append({'ligne': index, 'message': message})
            transaction.set_rollback(True)
    else:
        for index, ligne in enumerate(lignes, start=1):
            statut, message = creer_vehicule_import(company, ligne)
            if statut == 'cree':
                crees += 1
            elif statut == 'doublon':
                doublons += 1
            else:
                erreurs.append({'ligne': index, 'message': message})

    return {'crees': crees, 'doublons': doublons, 'erreurs': erreurs}


def reaffecter_conducteurs_masse(company, reaffectations, *, date_debut,
                                 user=None):
    """XFLT22 — Réaffectation conducteur en masse (clôt les affectations
    courantes et ouvre les nouvelles).

    ``reaffectations`` est une liste de ``{'vehicule_id', 'conducteur_id'}``.
    Pour chaque ligne : contrôle permis (FLOTTE9, ``controle_permis`` — un
    échec est LISTÉ dans ``echecs`` sans bloquer le lot), clôture
    l'affectation ``actif=True`` courante du véhicule (``date_fin`` = veille
    de ``date_debut``, ``actif=False``) puis crée la nouvelle affectation.
    Retourne ``{'reussies': [...], 'echecs': [{'vehicule_id',
    'conducteur_id', 'message'}, …]}``.
    """
    import datetime as _dt

    from .models import AffectationConducteur, Conducteur, Vehicule

    reussies = []
    echecs = []

    for ligne in reaffectations:
        vehicule_id = ligne.get('vehicule_id')
        conducteur_id = ligne.get('conducteur_id')

        vehicule = Vehicule.objects.filter(
            company=company, id=vehicule_id).first()
        conducteur = Conducteur.objects.filter(
            company=company, id=conducteur_id).first()
        if vehicule is None or conducteur is None:
            echecs.append({
                'vehicule_id': vehicule_id, 'conducteur_id': conducteur_id,
                'message': "Véhicule ou conducteur introuvable.",
            })
            continue

        ok, _code, message = controle_permis(conducteur, vehicule)
        if not ok:
            echecs.append({
                'vehicule_id': vehicule_id, 'conducteur_id': conducteur_id,
                'message': message,
            })
            continue

        AffectationConducteur.objects.filter(
            company=company, vehicule=vehicule, actif=True,
        ).update(
            actif=False,
            date_fin=date_debut - _dt.timedelta(days=1))

        nouvelle = AffectationConducteur.objects.create(
            company=company, vehicule=vehicule, conducteur=conducteur,
            date_debut=date_debut, actif=True)
        reussies.append(nouvelle)

    return {'reussies': reussies, 'echecs': echecs}


def rollout_plan_entretien(company, plan_modele, actif_flotte_ids):
    """XFLT22 — Duplique ``plan_modele`` (un ``PlanEntretien`` existant) sur
    une sélection d'autres actifs.

    Copie ``type_entretien``/les critères d'intervalle/les seuils d'alerte
    sur chaque actif de ``actif_flotte_ids`` (de la MÊME société). Un actif
    déjà couvert par un plan du même ``type_entretien`` est SAUTÉ (jamais de
    doublon). Retourne ``{'crees': [...], 'ignores': [<actif_flotte_id>, …]}``.
    """
    from .models import ActifFlotte, PlanEntretien

    crees = []
    ignores = []

    for actif_id in actif_flotte_ids:
        actif = ActifFlotte.objects.filter(
            company=company, id=actif_id).first()
        if actif is None:
            ignores.append(actif_id)
            continue

        deja_present = PlanEntretien.objects.filter(
            company=company, actif_flotte=actif,
            type_entretien=plan_modele.type_entretien,
        ).exists()
        if deja_present:
            ignores.append(actif_id)
            continue

        nouveau = PlanEntretien.objects.create(
            company=company, actif_flotte=actif,
            type_entretien=plan_modele.type_entretien,
            intervalle_km=plan_modele.intervalle_km,
            intervalle_jours=plan_modele.intervalle_jours,
            intervalle_heures=plan_modele.intervalle_heures,
            seuil_alerte_km=plan_modele.seuil_alerte_km,
            seuil_alerte_jours=plan_modele.seuil_alerte_jours,
            seuil_alerte_heures=plan_modele.seuil_alerte_heures,
        )
        crees.append(nouveau)

    return {'crees': crees, 'ignores': ignores}


# ── XFLT23 — OCR reçu carburant → pré-remplissage du plein (KEY-GATED) ────────
#
# Réutilise le SERVICE OCR existant (``backend/fastapi_ia``, ``ZHIPU_API_KEY``)
# comme point d'intégration : le squelette d'appel provider est isolé ici, à
# l'image de ``apps.ged.services.ocr_extract_text`` (GED33). Tant qu'aucune
# clé/flag n'est posé, l'extraction est un NO-OP DÉTERMINISTE : aucun appel
# réseau, aucune dépendance, aucun coût. La création du ``PleinCarburant`` à
# partir des champs extraits reste TOUJOURS du ressort de l'utilisateur (jamais
# de création automatique) — cette fonction ne fait QUE lire/retourner les
# champs, jamais écrire.

def ocr_pleins_active():
    """XFLT23 — True si l'OCR de reçu carburant est activé (clé configurée).

    KEY-GATED : sans ``settings.FLOTTE_OCR_PLEINS_ENABLED`` à vrai (posé par le
    founder aux côtés de ``ZHIPU_API_KEY``), toute extraction reste un no-op.
    Ne lève jamais.
    """
    from django.conf import settings
    return bool(getattr(settings, 'FLOTTE_OCR_PLEINS_ENABLED', False))


def extraire_recu_carburant(file_bytes, *, mime=''):
    """XFLT23 — Extrait les champs d'un reçu de station (photo) par OCR.

    NO-OP tant que ``ocr_pleins_active()`` est faux : lève ``RuntimeError``
    (l'appelant — la vue — traduit ceci en 503 avec un message FR clair,
    « OCR indisponible (configuration manquante) »). Ceci est un
    comportement DÉLIBÉRÉMENT différent de GED33 (qui renvoie une chaîne
    vide) car ici l'appelant a besoin de distinguer "aucune donnée" de
    "fonctionnalité indisponible" pour renvoyer le bon code HTTP.

    Quand activé, délègue à un module fournisseur isolé
    (``flotte_ocr_provider``, non câblé dans ce dépôt) qui appelle le service
    OCR ``backend/fastapi_ia`` (Zhipu AI) et renvoie un dict de champs bruts.
    Le mapping vers les champs ``PleinCarburant`` est fait par
    ``mapper_recu_vers_plein``. Ne lève jamais au-delà du RuntimeError
    "indisponible" ci-dessus — toute erreur provider est avalée et renvoie un
    dict vide (aucun champ extrait, jamais de crash de l'écran de saisie).
    """
    if not ocr_pleins_active():
        raise RuntimeError('OCR indisponible (configuration manquante).')
    if not file_bytes:
        return {}
    try:  # pragma: no cover - dépend d'un provider externe non câblé ici.
        from . import flotte_ocr_provider as provider  # noqa: F401
    except ImportError:  # pragma: no cover
        return {}
    try:  # pragma: no cover
        return provider.extraire_recu(file_bytes, mime=mime) or {}
    except Exception:  # pragma: no cover - jamais casser l'écran de saisie.
        return {}


def mapper_recu_vers_plein(champs_bruts):
    """XFLT23 — Normalise les champs bruts OCR vers les clés du formulaire
    ``PleinCarburant`` (lecture seule, aucun effet de bord).

    ``champs_bruts`` est le dict renvoyé par le provider OCR (ou un mock en
    test) : accepte les clés ``date``/``litres``/``prix_unitaire``/
    ``montant``/``station`` (FR, tel que documenté côté spec XFLT23) et
    projette vers ``date_plein``/``quantite``/``prix_total``/``station`` —
    les clés du formulaire ``PleinCarburant``. Une clé absente est simplement
    omise du résultat (l'utilisateur complète le reste à la main). Ne lève
    jamais : une valeur mal formée est ignorée plutôt que de faire échouer le
    pré-remplissage.
    """
    if not champs_bruts:
        return {}
    resultat = {}
    if champs_bruts.get('date'):
        resultat['date_plein'] = champs_bruts['date']
    if champs_bruts.get('litres') is not None:
        resultat['quantite'] = champs_bruts['litres']
    if champs_bruts.get('station'):
        resultat['station'] = champs_bruts['station']
    montant = champs_bruts.get('montant')
    if montant is not None:
        resultat['prix_total'] = montant
    elif (champs_bruts.get('litres') is not None
            and champs_bruts.get('prix_unitaire') is not None):
        try:
            resultat['prix_total'] = round(
                float(champs_bruts['litres'])
                * float(champs_bruts['prix_unitaire']), 2)
        except (TypeError, ValueError):
            pass
    if champs_bruts.get('prix_unitaire') is not None:
        resultat['prix_unitaire'] = champs_bruts['prix_unitaire']
    return resultat
