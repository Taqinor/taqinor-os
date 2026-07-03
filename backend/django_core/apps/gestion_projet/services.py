"""Services (écritures/orchestration) de la Gestion de projet.

Point d'entrée des écritures internes au module. ``company`` est toujours
dérivée du ``projet`` (jamais lue d'un corps de requête) ; aucun import
cross-app (on reste dans ``gestion_projet``).
"""
from datetime import timedelta
from decimal import Decimal

from django.db import models, transaction

from .models import (
    BaselinePlanning,
    BaselineTache,
    DependanceTache,
    JourFerie,
    PhaseProjet,
    Projet,
    RecurrenceTache,
    Tache,
)


# ── Suivi des temps (PROJ24) ─────────────────────────────────────────────────
def cout_timesheet(ressource, heures):
    """Coût INTERNE d'une saisie de temps = ``heures`` × coût horaire interne.

    ``cout_horaire`` est porté par la ``RessourceProfil`` ; absent ou nul → 0.
    Renvoie un ``Decimal`` arrondi à 2 décimales. Donnée 100 % INTERNE de
    pilotage (jamais exposée au client final).
    """
    if ressource is None or heures is None:
        return Decimal('0.00')
    cout_horaire = ressource.cout_horaire or Decimal('0')
    return (Decimal(heures) * cout_horaire).quantize(Decimal('0.01'))


# ── Cycle de vie & verrouillage de période (XPRJ1) ───────────────────────────
class TimesheetTransitionError(Exception):
    """Transition de statut illégale sur une ``Timesheet``."""


class PeriodeVerrouilleeError(Exception):
    """Écriture refusée : la période (mois) de la timesheet est verrouillée."""


def mois_de(date_val):
    """1er jour du mois d'une date (clé de ``PeriodeVerrouilleeTemps.mois``)."""
    return date_val.replace(day=1)


def periode_verrouillee(company, date_val):
    """``True`` si le mois de ``date_val`` est verrouillé pour cette société."""
    from .models import PeriodeVerrouilleeTemps
    if date_val is None:
        return False
    return PeriodeVerrouilleeTemps.objects.filter(
        company=company, mois=mois_de(date_val)).exists()


def verifier_periode_ouverte(company, date_val, *, admin=False):
    """Lève ``PeriodeVerrouilleeError`` si la période est verrouillée.

    Un utilisateur ADMIN (``admin=True``) contourne le verrou (déverrouillage
    implicite d'usage — la donnée reste verrouillée pour les autres tant que la
    ligne ``PeriodeVerrouilleeTemps`` n'est pas supprimée).
    """
    if admin:
        return
    if periode_verrouillee(company, date_val):
        raise PeriodeVerrouilleeError(
            f"La période {mois_de(date_val):%Y-%m} est verrouillée : "
            "aucune création/édition/suppression de feuille de temps.")


def soumettre_timesheet(timesheet):
    """brouillon → soumise."""
    from .models import Timesheet
    if timesheet.statut != Timesheet.Statut.BROUILLON:
        raise TimesheetTransitionError(
            "Seule une feuille de temps en brouillon peut être soumise.")
    timesheet.statut = Timesheet.Statut.SOUMISE
    timesheet.save(update_fields=['statut'])
    return timesheet


def approuver_timesheet(timesheet, approbateur):
    """soumise → approuvee (``approuve_par``/``date_approbation`` posés serveur)."""
    from django.utils import timezone

    from .models import Timesheet
    if timesheet.statut != Timesheet.Statut.SOUMISE:
        raise TimesheetTransitionError(
            "Seule une feuille de temps soumise peut être approuvée.")
    timesheet.statut = Timesheet.Statut.APPROUVEE
    timesheet.approuve_par = approbateur
    timesheet.date_approbation = timezone.now()
    timesheet.motif_rejet = ''
    timesheet.save(update_fields=[
        'statut', 'approuve_par', 'date_approbation', 'motif_rejet'])
    return timesheet


# ── Facturation en régie (T&M) depuis les temps approuvés (XPRJ3) ───────────
class FacturationRegieError(Exception):
    """Erreur métier au déclenchement de la facturation en régie."""


@transaction.atomic
def facturer_temps_projet(projet, *, debut, fin, user):
    """Facture en régie (T&M) les temps APPROUVÉS + facturables d'une période.

    Sélectionne les ``Timesheet`` du projet dont ``statut == approuvee``,
    ``facturable == True``, ``facture_id`` est NUL (pas déjà facturées) et
    ``date`` dans ``[debut, fin]`` (bornes inclusives) ; groupe par
    (tâche, type d'activité) pour le libellé ; calcule le montant HT total en
    ``heures × taux_facturation`` (une ligne sans ``taux_facturation`` compte
    pour 0 — jamais un coût INTERNE qui n'a pas vocation à être facturé au
    client). Lève ``FacturationRegieError`` si aucune ligne facturable.

    Le CLIENT est résolu depuis ``projet.client_id`` via un sélecteur
    ``crm.selectors`` (frontière cross-app, import fonction-local — jamais
    ``crm.models``) ; sans client résolvable, lève ``FacturationRegieError``.
    L'écriture de la ``Facture`` BROUILLON passe EXCLUSIVEMENT par
    ``apps.ventes.services.creer_facture_regie`` (jamais ``ventes.models``),
    numérotée via ``apps/ventes/utils/references.py`` (jamais ``count()+1``).

    Après création, CHAQUE timesheet incluse est marquée ``facture_id`` (dans
    la même transaction) — un RE-RUN sur la même période ne re-sélectionne donc
    RIEN (idempotent, 0 ligne re-facturée). Renvoie un dict
    ``{facture, montant_ht, nb_lignes, groupes}``.
    """
    from .models import Timesheet

    qs = Timesheet.objects.filter(
        company=projet.company, projet=projet,
        statut=Timesheet.Statut.APPROUVEE, facturable=True,
        facture_id__isnull=True, date__gte=debut, date__lte=fin,
    ).select_related('tache')

    lignes = list(qs)
    if not lignes:
        raise FacturationRegieError(
            "Aucune feuille de temps approuvée et facturable, non encore "
            "facturée, sur cette période.")

    from apps.crm import selectors as crm_selectors
    client = None
    if projet.client_id:
        client = crm_selectors.get_company_client(
            projet.company, projet.client_id)
    if client is None:
        raise FacturationRegieError(
            "Impossible de résoudre le client du projet (client_id absent ou "
            "introuvable) — facturation en régie impossible.")

    groupes = {}
    montant_ht = Decimal('0.00')
    for ts in lignes:
        cle = (ts.tache_id, ts.type_activite)
        heures = ts.heures or Decimal('0')
        taux = ts.taux_facturation or Decimal('0')
        montant_ligne = (heures * taux).quantize(Decimal('0.01'))
        montant_ht += montant_ligne
        g = groupes.setdefault(cle, {
            'tache_id': ts.tache_id,
            'tache_libelle': ts.tache.libelle if ts.tache_id else '',
            'type_activite': ts.type_activite,
            'heures': Decimal('0'),
            'montant': Decimal('0.00'),
        })
        g['heures'] += heures
        g['montant'] += montant_ligne

    groupes_tries = sorted(
        groupes.values(),
        key=lambda g: (g['tache_id'] or 0, g['type_activite']))
    libelle_lignes = '; '.join(
        f"{g['tache_libelle'] or 'sans tâche'} "
        f"({g['type_activite']}, {g['heures']} h)"
        for g in groupes_tries
    )
    libelle = (
        f'Régie (T&M) — projet {projet.code} [{debut:%d/%m/%Y}–{fin:%d/%m/%Y}] : '
        f'{libelle_lignes}')[:255]

    from apps.ventes import services as ventes_services
    facture = ventes_services.creer_facture_regie(
        company=projet.company, client=client, user=user,
        libelle=libelle, montant_ht=montant_ht)

    Timesheet.objects.filter(
        id__in=[ts.id for ts in lignes]).update(facture_id=facture.id)

    return {
        'facture': facture,
        'montant_ht': montant_ht,
        'nb_lignes': len(lignes),
        'groupes': groupes_tries,
    }


def rejeter_timesheet(timesheet, approbateur, motif=''):
    """soumise → rejetee (``approuve_par``/``date_approbation`` posés serveur)."""
    from django.utils import timezone

    from .models import Timesheet
    if timesheet.statut != Timesheet.Statut.SOUMISE:
        raise TimesheetTransitionError(
            "Seule une feuille de temps soumise peut être rejetée.")
    timesheet.statut = Timesheet.Statut.REJETEE
    timesheet.approuve_par = approbateur
    timesheet.date_approbation = timezone.now()
    timesheet.motif_rejet = motif or ''
    timesheet.save(update_fields=[
        'statut', 'approuve_par', 'date_approbation', 'motif_rejet'])
    return timesheet


# ── Jalons de facturation liés à l'avancement (PROJ27) ───────────────────────
class FacturationJalonError(Exception):
    """Erreur métier au déclenchement de la facturation d'un jalon."""


def declencher_facturation_jalon(jalon):
    """Déclenche la facturation liée à un jalon ATTEINT (PROJ27).

    Un jalon n'est facturable que s'il est ATTEINT (``statut == atteint``) et
    porte un ``facturation_pct`` > 0 — sinon ``FacturationJalonError``. Le
    montant théorique est ``facturation_pct`` % du ``budget_total`` du projet
    (donnée INTERNE de pilotage).

    L'écriture de la FACTURE client passe EXCLUSIVEMENT par ``ventes`` via son
    ``services`` (frontière cross-app, CLAUDE.md ; import fonction-local) — ce
    module n'importe JAMAIS les modèles/vues de ``ventes``. Aujourd'hui
    ``ventes.services`` n'expose pas d'entrée « facturer un jalon de projet » :
    on DÉGRADE proprement en renvoyant une PROPOSITION (aucune écriture
    cross-app), avec ``facture_creee=False`` et une note. Le jour où
    ``ventes.services`` exposera ``facturer_jalon_projet``, on l'appellera ici.

    Renvoie un dict ``{jalon_id, facturation_pct, montant, facture_creee, note}``.
    """
    from .models import Jalon

    if jalon.statut != Jalon.Statut.ATTEINT:
        raise FacturationJalonError(
            'Le jalon doit être atteint pour déclencher la facturation.')
    pct = jalon.facturation_pct or Decimal('0')
    if pct <= 0:
        raise FacturationJalonError(
            "Le jalon ne porte aucun pourcentage de facturation.")

    base = jalon.projet.budget_total or Decimal('0')
    montant = (base * pct / Decimal('100')).quantize(Decimal('0.01'))

    # Route vers ventes.services si une entrée dédiée existe ; sinon dégrade.
    facture_creee = False
    note = ''
    try:
        from apps.ventes import services as ventes_services
        facturer = getattr(
            ventes_services, 'facturer_jalon_projet', None)
    except Exception:  # pragma: no cover - ventes toujours importable
        facturer = None
    if callable(facturer):  # pragma: no cover - pas d'entrée ventes aujourd'hui
        facturer(jalon=jalon, montant=montant)
        facture_creee = True
        note = 'Facture déclenchée via ventes.services.'
    else:
        note = (
            "Aucune entrée ventes.services.facturer_jalon_projet — proposition "
            "seule (aucune facture créée).")

    return {
        'jalon_id': jalon.id,
        'facturation_pct': pct,
        'montant': montant,
        'facture_creee': facture_creee,
        'note': note,
    }


# ── Documents & plans versionnés (PROJ33) ────────────────────────────────────
@transaction.atomic
def deposer_version_document(document, fichier, commentaire='', auteur=None):
    """Dépose une NOUVELLE version d'un ``DocumentProjet`` (PROJ33).

    Le numéro de version est posé CÔTÉ SERVEUR : ``document.derniere_version`` +
    1 (jamais lu du corps de requête) — les versions ne s'écrasent jamais. Le
    cache ``document.derniere_version`` est avancé dans la même transaction
    atomique. ``company`` est toujours celle du ``document`` (jamais lue d'un
    corps) ; ``auteur`` est posé côté serveur. Renvoie la ``VersionDocument``
    créée.
    """
    from .models import DocumentProjet, VersionDocument

    if not isinstance(document, DocumentProjet):  # pragma: no cover - garde-fou
        raise TypeError('document doit être une instance de DocumentProjet.')
    # Verrou ligne pour sérialiser des dépôts concurrents sur le même document.
    document = DocumentProjet.objects.select_for_update().get(pk=document.pk)
    prochaine = (document.derniere_version or 0) + 1
    version = VersionDocument.objects.create(
        company=document.company,
        document=document,
        version=prochaine,
        fichier=fichier,
        commentaire=commentaire or '',
        auteur=auteur,
    )
    document.derniere_version = prochaine
    document.save(update_fields=['derniere_version'])
    return version


# ── Templates de projet par type d'installation (PROJ35) ─────────────────────
class ModeleProjetError(Exception):
    """Erreur métier à l'instanciation d'un modèle de projet."""


@transaction.atomic
def instancier_modele(modele, projet):
    """Applique un ``ModeleProjet`` à un ``Projet`` : crée phases + tâches (PROJ35).

    Pour chaque tâche-type du modèle, s'assure que la ``PhaseProjet`` du
    ``type_phase`` correspondant existe (création idempotente, mêmes libellés que
    ``PHASES_STANDARD``) puis crée la ``Tache`` (libellé / code WBS / ordre /
    charge copiés du modèle), rattachée à cette phase. ``company`` est TOUJOURS
    celle du ``projet`` (jamais lue d'un corps) ; le modèle doit appartenir à la
    MÊME société que le projet (sinon ``ModeleProjetError``). Écritures
    atomiques. Renvoie la liste des ``Tache`` créées.

    NB — opération ADDITIVE : elle n'écrase aucune phase/tâche existante (les
    phases sont créées seulement si absentes ; les tâches sont toujours ajoutées).
    """
    from .models import ModeleProjet, PhaseProjet, Tache

    if not isinstance(modele, ModeleProjet):  # pragma: no cover - garde-fou
        raise TypeError('modele doit être une instance de ModeleProjet.')
    if modele.company_id != projet.company_id:
        raise ModeleProjetError(
            'Le modèle et le projet doivent appartenir à la même société.')

    # Libellés standard par type de phase (cohérent avec PHASES_STANDARD).
    libelles_phase = {tp: lib for tp, lib in PHASES_STANDARD}
    ordres_phase = {
        tp: i for i, (tp, _) in enumerate(PHASES_STANDARD, start=1)}

    # Phases déjà présentes sur le projet (par type).
    phases_par_type = {
        p.type_phase: p
        for p in projet.phases.all()
    }

    def _phase_pour(type_phase):
        phase = phases_par_type.get(type_phase)
        if phase is None:
            phase = PhaseProjet.objects.create(
                company=projet.company,
                projet=projet,
                type_phase=type_phase,
                libelle=libelles_phase.get(type_phase, ''),
                ordre=ordres_phase.get(type_phase, 0),
            )
            phases_par_type[type_phase] = phase
        return phase

    creees = []
    for mt in modele.taches.order_by('ordre', 'id'):
        phase = _phase_pour(mt.type_phase)
        tache = Tache.objects.create(
            company=projet.company,
            projet=projet,
            phase=phase,
            code_wbs=mt.code_wbs,
            libelle=mt.libelle,
            ordre=mt.ordre,
            charge_estimee=mt.charge_estimee,
        )
        creees.append(tache)
    return creees


# ── Sous-traitance & clôture + REX (PROJ38) ──────────────────────────────────
class ClotureError(Exception):
    """Erreur métier à la clôture d'un projet."""


@transaction.atomic
def cloturer_projet(projet, *, date_cloture, date_reception=None,
                    points_positifs='', points_amelioration='',
                    recommandations='', auteur=None):
    """Clôture un ``Projet`` + enregistre le RETOUR D'EXPÉRIENCE (PROJ38).

    Crée (ou met à jour) la ``ClotureProjet`` 1–1 du projet avec le REX
    (positifs / améliorations / recommandations) puis fait passer le projet au
    statut TERMINÉ s'il ne l'est pas déjà (transition côté serveur, journalisée
    dans ``ProjetActivity``). Un projet ANNULÉ ne peut pas être clôturé (lève
    ``ClotureError``). ``company`` est TOUJOURS celle du projet ; ``cloture_par``
    est posé côté serveur. Écritures atomiques. Renvoie la ``ClotureProjet``.
    """
    from .models import ClotureProjet, ProjetActivity

    if projet.statut == Projet.Statut.ANNULE:
        raise ClotureError("Un projet annulé ne peut pas être clôturé.")

    cloture, _ = ClotureProjet.objects.update_or_create(
        projet=projet,
        defaults={
            'company': projet.company,
            'date_cloture': date_cloture,
            'date_reception': date_reception,
            'points_positifs': points_positifs or '',
            'points_amelioration': points_amelioration or '',
            'recommandations': recommandations or '',
            'cloture_par': auteur,
        },
    )

    # Transition vers TERMINÉ (journalisée), idempotente.
    if projet.statut != Projet.Statut.TERMINE:
        ancien = projet.statut
        projet.statut = Projet.Statut.TERMINE
        projet.save(update_fields=['statut'])
        ProjetActivity.objects.create(
            company=projet.company,
            projet=projet,
            old_value=ancien,
            new_value=Projet.Statut.TERMINE,
            auteur=auteur,
        )
    return cloture


# Décomposition standard d'un projet d'installation solaire (WBS), dans l'ordre
# de réalisation. PROPRE à ce module — ne réutilise aucune clé de STAGES.py.
PHASES_STANDARD = [
    (PhaseProjet.TypePhase.ETUDE, 'Étude'),
    (PhaseProjet.TypePhase.APPRO, 'Approvisionnement'),
    (PhaseProjet.TypePhase.POSE, 'Pose'),
    (PhaseProjet.TypePhase.MES, 'Mise en service'),
    (PhaseProjet.TypePhase.RECEPTION, 'Réception'),
]


def instancier_phases_standard(projet):
    """Crée les 5 phases standard d'un ``Projet``, dans l'ordre — IDEMPOTENT.

    Une phase n'est créée que si elle n'existe pas déjà (clé
    ``(projet, type_phase)``) : un second appel ne duplique rien et laisse
    intactes les phases déjà présentes (statut/dates/avancement édités). La
    société est toujours celle du ``projet`` (jamais lue d'un corps de requête).
    Renvoie la liste complète des phases du projet, ordonnée par ``ordre``.
    """
    if not isinstance(projet, Projet):  # pragma: no cover - garde-fou
        raise TypeError('projet doit être une instance de Projet.')
    existants = set(
        projet.phases.values_list('type_phase', flat=True))
    a_creer = []
    for ordre, (type_phase, libelle) in enumerate(PHASES_STANDARD, start=1):
        if type_phase in existants:
            continue
        a_creer.append(PhaseProjet(
            company=projet.company,
            projet=projet,
            type_phase=type_phase,
            libelle=libelle,
            ordre=ordre,
        ))
    if a_creer:
        PhaseProjet.objects.bulk_create(a_creer)
    return list(projet.phases.order_by('ordre', 'id'))


# ── Drag-reschedule (PROJ11) ─────────────────────────────────────────────────

class RescheduleError(Exception):
    """Erreur métier de re-planification (ex. dates incohérentes, cycle)."""


def _duree_jours(tache):
    """Durée d'une tâche en jours (≥ 1) à partir de ses dates prévues.

    Si la tâche n'a pas encore de dates, retombe sur ``charge_estimee`` arrondie
    au jour supérieur (≥ 1), sinon 1 — même convention que le CPM (``cpm.py``).
    """
    deb = tache.date_debut_prevue
    fin = tache.date_fin_prevue
    if deb is not None and fin is not None:
        return max(1, (fin - deb).days)
    charge = tache.charge_estimee
    if charge is not None and charge > 0:
        import math
        return max(1, int(math.ceil(float(charge))))
    return 1


def _contrainte_debut_min(type_dep, lag, pred_debut, pred_fin, duree_succ):
    """Début AU PLUS TÔT du successeur imposé par UNE arête (en date).

    Renvoie la date de DÉBUT minimale du successeur pour respecter l'arête
    ``type_dep`` (+ ``lag`` jours) sachant le début/fin du prédécesseur et la
    durée du successeur. Mêmes règles que le CPM, transposées en calendrier.
    """
    lag_d = timedelta(days=lag)
    dur = timedelta(days=duree_succ)
    if type_dep == DependanceTache.TypeDependance.FS:
        return pred_fin + lag_d                     # début ≥ fin préd. + lag
    if type_dep == DependanceTache.TypeDependance.SS:
        return pred_debut + lag_d                   # début ≥ début préd. + lag
    if type_dep == DependanceTache.TypeDependance.FF:
        return pred_fin + lag_d - dur               # fin ≥ fin préd. + lag
    # SF : fin ≥ début préd. + lag
    return pred_debut + lag_d - dur


@transaction.atomic
def reprogrammer_tache(tache, nouvelle_date_debut, nouvelle_date_fin=None):
    """Déplace une tâche (drag) et POUSSE ses successeurs en cascade.

    Pose le nouveau créneau de ``tache`` (``date_debut_prevue`` /
    ``date_fin_prevue``) puis propage en aval : chaque successeur dont le créneau
    actuel VIOLE désormais sa contrainte (FS/SS/FF/SF + lag) est décalé au plus
    tôt admissible, en CONSERVANT sa durée. La propagation ne fait que POUSSER
    (jamais tirer une tâche plus tôt) : un successeur déjà assez tard n'est pas
    touché. Toutes les écritures sont dans une transaction atomique.

    ``nouvelle_date_fin`` est optionnelle : si absente, on conserve la durée
    courante de la tâche (ou 1 jour à défaut). Renvoie la liste ORDONNÉE des
    tâches modifiées (la tâche déplacée d'abord, puis les successeurs décalés).

    Garde-fous : ``nouvelle_date_fin`` doit être ≥ ``nouvelle_date_debut`` ; un
    cycle dans le sous-graphe aval lève ``RescheduleError`` (sécurité, au-delà
    des cycles directs déjà refusés à l'écriture).
    """
    if nouvelle_date_debut is None:
        raise RescheduleError('La nouvelle date de début est obligatoire.')
    if nouvelle_date_fin is None:
        duree = _duree_jours(tache)
        nouvelle_date_fin = nouvelle_date_debut + timedelta(days=duree)
    if nouvelle_date_fin < nouvelle_date_debut:
        raise RescheduleError(
            'La date de fin ne peut pas précéder la date de début.')

    projet = tache.projet
    company = tache.company

    # Charge tout le graphe du projet en mémoire (scopé société).
    taches = {
        t.id: t for t in Tache.objects.filter(
            projet=projet, company=company)
    }
    deps = list(DependanceTache.objects.filter(
        predecesseur__projet=projet, company=company))
    succ_par_pred = {}   # pred_id -> [dep]
    pred_par_succ = {}   # succ_id -> [dep]
    for dep in deps:
        succ_par_pred.setdefault(dep.predecesseur_id, []).append(dep)
        pred_par_succ.setdefault(dep.successeur_id, []).append(dep)

    # Pose le nouveau créneau de la tâche déplacée.
    tache.date_debut_prevue = nouvelle_date_debut
    tache.date_fin_prevue = nouvelle_date_fin
    taches[tache.id].date_debut_prevue = nouvelle_date_debut
    taches[tache.id].date_fin_prevue = nouvelle_date_fin

    modifies = {tache.id: tache}
    ordre_modifies = [tache.id]

    # Propagation BFS en aval avec garde anti-boucle (au plus N² relâches).
    file = [tache.id]
    max_iter = (len(taches) + 1) ** 2 + 1
    iters = 0
    while file:
        iters += 1
        if iters > max_iter:
            raise RescheduleError(
                'Cycle détecté dans le sous-graphe des successeurs.')
        courant = file.pop(0)
        cur = taches[courant]
        if cur.date_debut_prevue is None or cur.date_fin_prevue is None:
            continue
        for dep in succ_par_pred.get(courant, ()):
            succ = taches[dep.successeur_id]
            dur_succ = _duree_jours(succ)
            debut_min = _contrainte_debut_min(
                dep.type_dependance, dep.lag,
                cur.date_debut_prevue, cur.date_fin_prevue, dur_succ)
            debut_actuel = succ.date_debut_prevue
            # Ne POUSSE que si le créneau actuel viole la contrainte (ou est
            # absent) ; ne tire jamais un successeur plus tôt.
            if debut_actuel is not None and debut_actuel >= debut_min:
                continue
            succ.date_debut_prevue = debut_min
            succ.date_fin_prevue = debut_min + timedelta(days=dur_succ)
            if succ.id not in modifies:
                modifies[succ.id] = succ
                ordre_modifies.append(succ.id)
            file.append(succ.id)

    for t in modifies.values():
        t.save(update_fields=['date_debut_prevue', 'date_fin_prevue'])

    return [taches[i] for i in ordre_modifies]


# ── Situations de travaux — décomptes progressifs BTP (XPRJ4) ───────────────
class SituationTravauxError(Exception):
    """Erreur métier sur une situation de travaux."""


def prochain_numero_situation(projet):
    """Numéro de situation SUIVANT pour ce projet (jamais ``count()+1``).

    Verrouille la ligne ``Projet`` (``select_for_update``) le temps du calcul
    pour sérialiser des créations concurrentes de situations sur le MÊME
    projet, puis prend le plus haut ``numero`` déjà UTILISÉ + 1 (les trous —
    situation supprimée — ne créent jamais de collision). Doit être appelé
    dans une transaction atomique par l'appelant (``creer_situation``).
    """
    from .models import Projet, SituationTravaux

    Projet.objects.select_for_update().get(pk=projet.pk)
    plus_haut = SituationTravaux.objects.filter(
        projet=projet).aggregate(
            models.Max('numero'))['numero__max'] or 0
    return plus_haut + 1


@transaction.atomic
def creer_situation(projet, *, periode, retenue_garantie_pct=None,
                    contrat_id=None):
    """Crée une nouvelle ``SituationTravaux`` BROUILLON pour ``projet``.

    Le ``numero`` est posé côté serveur (savepoint + verrou de ligne, jamais
    ``count()+1`` — voir ``prochain_numero_situation``). ``company`` est
    TOUJOURS celle du ``projet``. Renvoie la ``SituationTravaux`` créée (sans
    lignes — ``LigneSituation`` sont ajoutées séparément, voir
    ``ajouter_ligne_situation``).
    """
    from .models import SituationTravaux

    numero = prochain_numero_situation(projet)
    return SituationTravaux.objects.create(
        company=projet.company,
        projet=projet,
        numero=numero,
        periode=periode,
        retenue_garantie_pct=retenue_garantie_pct,
        contrat_id=contrat_id,
    )


def _situation_precedente_montant_cumule(situation, libelle):
    """``montant_cumule`` de la ligne de MÊME libellé à la situation N-1.

    0 si ``situation`` est la n°1 du projet, ou si aucune ligne de ce libellé
    n'existe encore à la situation précédente (nouveau lot introduit en cours
    de chantier).
    """
    from .models import LigneSituation, SituationTravaux

    precedente = SituationTravaux.objects.filter(
        projet_id=situation.projet_id, numero__lt=situation.numero,
    ).order_by('-numero').first()
    if precedente is None:
        return Decimal('0')
    ligne_prec = LigneSituation.objects.filter(
        situation=precedente, libelle=libelle).first()
    if ligne_prec is None:
        return Decimal('0')
    return ligne_prec.montant_cumule or Decimal('0')


@transaction.atomic
def ajouter_ligne_situation(situation, *, libelle, montant_marche_ht,
                            avancement_cumule_pct):
    """Ajoute (ou remplace) une ``LigneSituation`` avec montants CALCULÉS.

    ``montant_cumule`` = ``montant_marche_ht`` × ``avancement_cumule_pct`` / 100
    (arrondi 2 décimales) ; ``montant_cumule_anterieur`` = le ``montant_cumule``
    de la MÊME ligne (même libellé) à la situation N-1 du projet (0 si absente
    ou n°1) ; ``montant_periode`` = cumulé − antérieur. Une ``SituationTravaux``
    déjà VALIDÉE/FACTURÉE ne peut plus recevoir de nouvelle ligne (lève
    ``SituationTravauxError``).
    """
    from .models import LigneSituation, SituationTravaux

    if situation.statut != SituationTravaux.Statut.BROUILLON:
        raise SituationTravauxError(
            "Seule une situation en brouillon peut recevoir des lignes.")

    montant_marche_ht = Decimal(montant_marche_ht)
    avancement_cumule_pct = Decimal(avancement_cumule_pct)
    montant_cumule = (
        montant_marche_ht * avancement_cumule_pct / Decimal('100')
    ).quantize(Decimal('0.01'))
    montant_cumule_anterieur = _situation_precedente_montant_cumule(
        situation, libelle)
    montant_periode = montant_cumule - montant_cumule_anterieur

    return LigneSituation.objects.create(
        company=situation.company,
        situation=situation,
        libelle=libelle,
        montant_marche_ht=montant_marche_ht,
        avancement_cumule_pct=avancement_cumule_pct,
        montant_cumule_anterieur=montant_cumule_anterieur,
        montant_periode=montant_periode,
        montant_cumule=montant_cumule,
    )


@transaction.atomic
def valider_situation(situation, *, user):
    """Valide une ``SituationTravaux`` BROUILLON et génère la facture d'acompte.

    Passe la situation à VALIDÉE puis FACTURÉE (une seule facture générée —
    idempotent : un second appel sur une situation déjà VALIDÉE/FACTURÉE lève
    ``SituationTravauxError``, jamais de double facturation). Le montant
    facturé est la SOMME des ``montant_periode`` des lignes (± retenue de
    garantie déduite, tracée sur ``retenue_garantie_pct``). Le CLIENT est
    résolu depuis ``projet.client_id`` via ``crm.selectors`` (frontière
    cross-app, import fonction-local). L'écriture de la ``Facture`` passe
    EXCLUSIVEMENT par ``ventes.services.creer_facture_acompte_situation``.
    Renvoie la ``SituationTravaux`` mise à jour.
    """
    from django.utils import timezone

    from .models import SituationTravaux

    if situation.statut != SituationTravaux.Statut.BROUILLON:
        raise SituationTravauxError(
            "Seule une situation en brouillon peut être validée.")

    lignes = list(situation.lignes.all())
    if not lignes:
        raise SituationTravauxError(
            "La situation ne porte aucune ligne — rien à facturer.")

    montant_periode_total = sum(
        (ligne.montant_periode or Decimal('0')) for ligne in lignes)

    projet = situation.projet
    from apps.crm import selectors as crm_selectors
    client = None
    if projet.client_id:
        client = crm_selectors.get_company_client(
            projet.company, projet.client_id)
    if client is None:
        raise SituationTravauxError(
            "Impossible de résoudre le client du projet — validation "
            "impossible.")

    libelle = (
        f'Situation n°{situation.numero} — projet {projet.code} '
        f'[{situation.periode:%m/%Y}]')[:255]

    from apps.ventes import services as ventes_services
    facture = ventes_services.creer_facture_acompte_situation(
        company=projet.company, client=client, user=user, libelle=libelle,
        montant_periode_ht=montant_periode_total,
        retenue_garantie_pct=situation.retenue_garantie_pct)

    situation.statut = SituationTravaux.Statut.FACTUREE
    situation.facture_id = facture.id
    situation.date_validation = timezone.now()
    situation.save(update_fields=[
        'statut', 'facture_id', 'date_validation'])
    return situation


# ── Congés RH approuvés → indisponibilités planning (XPRJ9) ──────────────────
def _marqueur_conge_rh(demande):
    """Marqueur STABLE identifiant la demande RH source (idempotence).

    Stocké dans ``Indisponibilite.motif`` (aucune référence lâche dédiée sur ce
    modèle historique — additif minimal) : permet de retrouver/mettre à jour la
    MÊME indisponibilité sur une re-validation, sans jamais dupliquer.
    """
    return f'conge_rh:{demande.id}'


def synchroniser_indisponibilite_conge(demande, *, annule=False):
    """Synchronise l'``Indisponibilite`` planning à partir d'une ``DemandeConge``.

    Appelé par ``receivers.py`` (abonné à l'événement ``conge_approuve`` du bus
    ``core/events.py``) — JAMAIS appelé directement par ``rh`` (découplage M6).

    Résout la ``RessourceProfil`` liée au MÊME utilisateur que
    ``demande.employe.user`` (dans la société du profil ressource déduite du
    lien utilisateur — jamais lue du corps de requête). Un employé sans compte
    utilisateur, ou un utilisateur sans profil ressource dans ce module, est
    ignoré PROPREMENT (retourne ``None``, aucune exception).

    * ``annule=False`` (validation) : ``update_or_create`` sur le marqueur
      ``_marqueur_conge_rh`` — IDEMPOTENT : une re-validation ne duplique
      jamais, elle met juste à jour les dates si elles ont changé.
    * ``annule=True`` : supprime l'indisponibilité correspondante si elle
      existe encore (aucune erreur si déjà absente).

    Renvoie l'``Indisponibilite`` créée/mise à jour (validation) ou ``None``
    (annulation, ou dégradation propre).
    """
    from .models import Indisponibilite, RessourceProfil

    employe = getattr(demande, 'employe', None)
    user_id = getattr(employe, 'user_id', None) if employe else None
    if not user_id:
        return None

    ressource = RessourceProfil.objects.filter(user_id=user_id).first()
    if ressource is None:
        return None

    marqueur = _marqueur_conge_rh(demande)

    if annule:
        Indisponibilite.objects.filter(
            company=ressource.company, ressource=ressource,
            motif=marqueur).delete()
        return None

    indispo, _ = Indisponibilite.objects.update_or_create(
        company=ressource.company, ressource=ressource, motif=marqueur,
        defaults={
            'type_indispo': Indisponibilite.TypeIndispo.CONGE,
            'date_debut': demande.date_debut,
            'date_fin': demande.date_fin,
        },
    )
    return indispo


# ── Rappels des temps manquants (XPRJ7) ──────────────────────────────────────
def rappeler_temps_manquants(company, debut, fin):
    """Notifie CHAQUE ressource en retard de saisie sur [debut, fin] (XPRJ7).

    Délègue la détection à ``selectors.temps_manquants`` puis diffuse UNE
    notification interne par ressource via ``apps.notifications.services.
    notify`` (import fonction-local — frontière cross-app ; événement générique
    ``DIGEST``, réutilisé tel quel par d'autres rappels périodiques du repo).

    IDEMPOTENT : une notification déjà émise AUJOURD'HUI pour cette ressource +
    cette fenêtre exacte (marqueur dans ``Notification.link``) n'est jamais
    re-diffusée — relancer la commande plusieurs fois le même jour ne spamme
    pas. Best-effort par ressource : un échec de notification n'interrompt pas
    les suivantes. Renvoie ``{nb_en_retard, nb_notifies, nb_deja_notifies}``.
    """
    from django.utils import timezone

    from . import selectors

    data = selectors.temps_manquants(company, debut, fin)
    lignes = data['lignes']
    if not lignes:
        return {'nb_en_retard': 0, 'nb_notifies': 0, 'nb_deja_notifies': 0}

    from apps.notifications.models import EventType, Notification
    from apps.notifications.services import notify

    today = timezone.localdate()
    nb_notifies = 0
    nb_deja_notifies = 0
    for ligne in lignes:
        marqueur = (
            f'gestion_projet:rappel_timesheet:{ligne["ressource_id"]}:'
            f'{debut}:{fin}:{today}')
        deja_notifie = Notification.objects.filter(
            company=company, recipient_id=ligne['user_id'],
            event_type=EventType.DIGEST, link=marqueur,
            created_at__date=today,
        ).exists()
        if deja_notifie:
            nb_deja_notifies += 1
            continue
        try:
            from authentication.models import CustomUser
            user = CustomUser.objects.filter(id=ligne['user_id']).first()
            if user is None:
                continue
            nb_manquants = len(ligne['jours_manquants'])
            notify(
                user, EventType.DIGEST,
                title='Feuilles de temps manquantes',
                body=(
                    f'{nb_manquants} jour(s) sans saisie de temps entre '
                    f'{debut} et {fin}.'),
                link=marqueur,
                company=company,
            )
            nb_notifies += 1
        except Exception:  # pragma: no cover - défensif, best-effort
            continue

    return {
        'nb_en_retard': len(lignes),
        'nb_notifies': nb_notifies,
        'nb_deja_notifies': nb_deja_notifies,
    }


# ── Chrono start/stop sur tâche (XPRJ5) ──────────────────────────────────────
class ChronoError(Exception):
    """Erreur métier sur le chrono start/stop d'une tâche."""


def _arrondir_duree_heures(minutes, pas_minutes=15):
    """Arrondit une durée (en minutes) au ``pas_minutes`` SUPÉRIEUR, en heures.

    Ex. ``pas_minutes=15`` (quart d'heure) : 1 minute → 15 min (0.25 h) ;
    16 minutes → 30 min (0.50 h) ; 0 minute → 0 h. Renvoie un ``Decimal``.
    """
    import math
    if minutes <= 0:
        return Decimal('0')
    pas = max(1, int(pas_minutes))
    paliers = math.ceil(minutes / pas)
    minutes_arrondies = paliers * pas
    return (Decimal(minutes_arrondies) / Decimal('60')).quantize(Decimal('0.01'))


@transaction.atomic
def demarrer_chrono(tache, user):
    """Démarre un chrono sur ``tache`` pour ``user`` (XPRJ5).

    Un seul chrono actif par utilisateur : démarrer un NOUVEAU chrono arrête
    (silencieusement, sans créer de timesheet) l'ancien s'il existe — le
    START/STOP explicite reste la seule voie qui crée une timesheet. ``company``
    est TOUJOURS celle de la ``tache``. Renvoie le ``ChronoEnCours`` créé.
    """
    from django.utils import timezone

    from .models import ChronoEnCours

    ChronoEnCours.objects.filter(user=user).delete()
    return ChronoEnCours.objects.create(
        company=tache.company,
        user=user,
        tache=tache,
        demarre_a=timezone.now(),
    )


@transaction.atomic
def arreter_chrono(user, *, pas_minutes=15):
    """Arrête le chrono actif de ``user`` et crée la ``Timesheet`` brouillon.

    Lève ``ChronoError`` si aucun chrono actif. La durée est
    ``maintenant − demarre_a``, arrondie au quart d'heure SUPÉRIEUR
    (``pas_minutes``, paramétrable — défaut 15 min). La ressource est celle
    liée à l'utilisateur (``RessourceProfil.user``) — lève ``ChronoError`` si
    l'utilisateur n'a AUCUN profil ressource (message explicite). Supprime le
    ``ChronoEnCours`` après création. Renvoie la ``Timesheet`` créée.
    """
    from django.utils import timezone

    from .models import ChronoEnCours, RessourceProfil, Timesheet

    chrono = ChronoEnCours.objects.filter(user=user).first()
    if chrono is None:
        raise ChronoError("Aucun chrono actif pour cet utilisateur.")

    ressource = RessourceProfil.objects.filter(
        company=chrono.company, user=user).first()
    if ressource is None:
        raise ChronoError(
            "Aucun profil ressource lié à cet utilisateur — impossible de "
            "créer la feuille de temps.")

    maintenant = timezone.now()
    minutes_ecoulees = max(
        0, (maintenant - chrono.demarre_a).total_seconds() / 60)
    heures = _arrondir_duree_heures(minutes_ecoulees, pas_minutes)

    timesheet = Timesheet.objects.create(
        company=chrono.company,
        projet=chrono.tache.projet,
        tache=chrono.tache,
        ressource=ressource,
        date=maintenant.date(),
        heures=heures,
        cout=cout_timesheet(ressource, heures),
        saisi_par=user,
    )
    chrono.delete()
    return timesheet


# ── Baseline de planning (PROJ13) ────────────────────────────────────────────

@transaction.atomic
def creer_baseline(projet, libelle='', auteur=None):
    """Crée une BASELINE figée du planning courant d'un ``Projet``.

    Capture, pour CHAQUE tâche du projet, son créneau prévu
    (``date_debut_prevue`` / ``date_fin_prevue``) et sa ``charge_estimee`` dans
    des lignes ``BaselineTache`` (libellé/code WBS figés pour survivre à une
    suppression de tâche). ``company`` est toujours celle du ``projet`` (jamais
    lue d'un corps de requête) ; ``auteur`` est posé côté serveur. Écritures
    atomiques. Renvoie la ``BaselinePlanning`` créée.
    """
    if not isinstance(projet, Projet):  # pragma: no cover - garde-fou
        raise TypeError('projet doit être une instance de Projet.')
    baseline = BaselinePlanning.objects.create(
        company=projet.company,
        projet=projet,
        libelle=libelle or '',
        auteur=auteur,
    )
    taches = Tache.objects.filter(projet=projet, company=projet.company)
    lignes = [
        BaselineTache(
            company=projet.company,
            baseline=baseline,
            tache=t,
            tache_libelle=t.libelle,
            tache_code_wbs=t.code_wbs,
            date_debut_prevue=t.date_debut_prevue,
            date_fin_prevue=t.date_fin_prevue,
            charge_estimee=t.charge_estimee,
        )
        for t in taches
    ]
    if lignes:
        BaselineTache.objects.bulk_create(lignes)
    return baseline


# ── Tâches récurrentes (XPRJ13) ──────────────────────────────────────────────

def _prochaine_echeance_suivante(echeance, regle, intervalle):
    """Avance ``echeance`` d'un pas de la règle (hebdomadaire/mensuelle)."""
    if regle == RecurrenceTache.Regle.HEBDOMADAIRE:
        return echeance + timedelta(weeks=intervalle)
    # Mensuelle : avance de ``intervalle`` mois, en clampant le jour si le
    # mois cible est plus court (ex. 31 janvier + 1 mois → 28/29 février).
    mois_total = echeance.month - 1 + intervalle
    annee = echeance.year + mois_total // 12
    mois = mois_total % 12 + 1
    import calendar
    dernier_jour = calendar.monthrange(annee, mois)[1]
    jour = min(echeance.day, dernier_jour)
    return echeance.replace(year=annee, month=mois, day=jour)


@transaction.atomic
def generer_taches_recurrentes(company, *, aujourd_hui=None):
    """Génère la PROCHAINE ``Tache`` de chaque récurrence ACTIVE à échéance.

    IDEMPOTENT : chaque appel avance ``prochaine_echeance`` immédiatement
    après avoir créé la tâche, donc un re-run le même jour ne crée jamais deux
    occurrences pour la même échéance. Respecte ``date_fin`` et
    ``nb_occurrences`` (désactive la récurrence une fois atteinte). Renvoie la
    liste des ``Tache`` créées.
    """
    if aujourd_hui is None:
        from datetime import date as _date
        aujourd_hui = _date.today()

    crees = []
    recurrences = RecurrenceTache.objects.select_for_update().filter(
        company=company, actif=True, prochaine_echeance__lte=aujourd_hui)
    for rec in recurrences:
        # Une récurrence peut avoir plusieurs échéances en retard (ex. cron
        # arrêté un moment) : on rattrape TOUTES les échéances passées, une
        # tâche par échéance, jamais deux pour la même échéance (avance
        # systématique avant la prochaine itération).
        while rec.actif and rec.prochaine_echeance <= aujourd_hui:
            if rec.date_fin is not None \
                    and rec.prochaine_echeance > rec.date_fin:
                rec.actif = False
                rec.save(update_fields=['actif'])
                break
            if rec.nb_occurrences is not None \
                    and rec.nb_generees >= rec.nb_occurrences:
                rec.actif = False
                rec.save(update_fields=['actif'])
                break

            tache = Tache.objects.create(
                company=rec.company,
                projet=rec.projet,
                phase=rec.phase,
                libelle=rec.libelle,
                charge_estimee=rec.charge_estimee,
                assigne=rec.assigne,
                date_debut_prevue=rec.prochaine_echeance,
                date_fin_prevue=rec.prochaine_echeance,
            )
            crees.append(tache)

            rec.nb_generees += 1
            rec.prochaine_echeance = _prochaine_echeance_suivante(
                rec.prochaine_echeance, rec.regle, rec.intervalle)
            if rec.date_fin is not None \
                    and rec.prochaine_echeance > rec.date_fin:
                rec.actif = False
            if rec.nb_occurrences is not None \
                    and rec.nb_generees >= rec.nb_occurrences:
                rec.actif = False
            rec.save(update_fields=[
                'nb_generees', 'prochaine_echeance', 'actif'])
    return crees


# ── Jours fériés marocains pré-remplis (XPRJ20) ──────────────────────────────
def seeder_feries_calendrier(calendrier, annee):
    """Pré-remplit ``JourFerie`` depuis le référentiel UNIQUE ``core.calendar``.

    Source EXCLUSIVE : ``core.calendar.MOROCCAN_FIXED_HOLIDAYS`` (fixes) +
    ``MOROCCAN_MOVABLE_HOLIDAYS`` (mobiles, hégiriens) de l'année demandée —
    JAMAIS une nouvelle liste de dates codée en dur ici (règle DC26/FG5).
    IDEMPOTENT : ``unique (calendrier, date)`` respecté (``get_or_create``,
    aucun doublon même en re-run). Pour une année SANS jeu de fêtes mobiles
    codé (``MOROCCAN_MOVABLE_HOLIDAYS`` n'a pas cette année), les fêtes
    mobiles (Aïd al-Fitr, Aïd al-Adha, Nouvel An hégirien, Aïd al-Mawlid)
    restent à saisir MANUELLEMENT — signalé dans le résultat.

    Renvoie ``{'crees': [...], 'nb_deja_presents': N, 'fetes_mobiles_manquantes': bool}``.
    """
    from core.calendar import MOROCCAN_MOVABLE_HOLIDAYS, moroccan_holidays

    company = calendrier.company
    dates_feriees = moroccan_holidays(annee)

    # Libellés : fixes via un mapping mois/jour → libellé, mobiles via le
    # dict de l'année (déjà date → libellé).
    from core.calendar import MOROCCAN_FIXED_HOLIDAYS
    libelles_fixes = {
        _date_du_mois_jour(annee, mois, jour): libelle
        for (mois, jour), libelle in MOROCCAN_FIXED_HOLIDAYS.items()
    }
    libelles_mobiles = MOROCCAN_MOVABLE_HOLIDAYS.get(annee, {})

    crees = []
    nb_deja = 0
    for d in sorted(dates_feriees):
        libelle = libelles_fixes.get(d) or libelles_mobiles.get(d, '')
        _, created = JourFerie.objects.get_or_create(
            company=company, calendrier=calendrier, date=d,
            defaults={'libelle': libelle})
        if created:
            crees.append(d)
        else:
            nb_deja += 1

    return {
        'crees': crees,
        'nb_deja_presents': nb_deja,
        'fetes_mobiles_manquantes': annee not in MOROCCAN_MOVABLE_HOLIDAYS,
    }


def _date_du_mois_jour(annee, mois, jour):
    from datetime import date as _date
    return _date(annee, mois, jour)


# ── Créer un projet depuis un devis accepté (XPRJ21) ─────────────────────────
class DevisVersProjetError(Exception):
    """Erreur métier lors de la création d'un projet depuis un devis."""


def _prochain_code_projet(company):
    """Code ``Projet`` sûr : plus haut suffixe utilisé + 1 (JAMAIS count()+1).

    Radical ``PRJ-<année>-`` (reset annuel), même politique anti-collision que
    ``apps/ventes/utils/references.py`` (pas de dépendance croisée : logique
    dupliquée localement, modèle différent).
    """
    import re
    from django.utils import timezone

    annee = timezone.now().strftime('%Y')
    prefix = f'PRJ-{annee}-'
    refs = Projet.objects.filter(
        company=company, code__startswith=prefix).values_list(
            'code', flat=True)
    highest = 0
    suffix_re = re.compile(r'-(\d+)$')
    for ref in refs:
        m = suffix_re.search(ref)
        if m:
            highest = max(highest, int(m.group(1)))
    return f'{prefix}{highest + 1:04d}'


@transaction.atomic
def creer_projet_depuis_devis(devis_data, *, company, user=None):
    """Crée un ``Projet`` + ``ProjetLien`` + ``BudgetProjet`` v1 depuis un
    devis ACCEPTÉ (XPRJ21) — action UTILISATEUR EXPLICITE uniquement (JAMAIS
    automatique sur ``devis_accepted`` : le chantier auto existe déjà côté
    ``installations``).

    ``devis_data`` provient EXCLUSIVEMENT de
    ``apps.ventes.selectors.devis_pour_projet`` (jamais un import de
    ``ventes.models``). Refuse (``DevisVersProjetError``) si un ``ProjetLien``
    pointant déjà ce devis existe pour la société (re-run → « déjà lié »). Le
    ``code`` du projet est généré via une numérotation SÛRE (plus haut
    suffixe utilisé + 1, jamais ``count()+1``).

    Renvoie ``{'projet': Projet, 'lien': ProjetLien, 'budget': BudgetProjet}``.
    """
    from .models import BudgetProjet, LigneBudgetProjet, ProjetLien

    devis_id = devis_data['id']
    deja_lie = ProjetLien.objects.filter(
        company=company, type_cible=ProjetLien.TypeCible.DEVIS,
        cible_id=devis_id).exists()
    if deja_lie:
        raise DevisVersProjetError(
            f'Le devis {devis_data["reference"]} est déjà lié à un projet.')

    projet = Projet.objects.create(
        company=company,
        code=_prochain_code_projet(company),
        nom=f'Projet — devis {devis_data["reference"]}',
        client_id=devis_data['client_id'],
        budget_total=(
            devis_data['montant_materiel']
            + devis_data['montant_main_oeuvre']),
    )

    lien = ProjetLien.objects.create(
        company=company,
        projet=projet,
        type_cible=ProjetLien.TypeCible.DEVIS,
        cible_id=devis_id,
        libelle=devis_data['reference'],
    )

    budget = BudgetProjet.objects.create(
        company=company, projet=projet, version=1,
        statut=BudgetProjet.Statut.BROUILLON,
    )
    if devis_data['montant_materiel']:
        LigneBudgetProjet.objects.create(
            company=company, budget=budget,
            categorie=LigneBudgetProjet.Categorie.MATERIEL,
            libelle='Matériel (depuis devis)',
            montant_prevu=devis_data['montant_materiel'],
        )
    if devis_data['montant_main_oeuvre']:
        LigneBudgetProjet.objects.create(
            company=company, budget=budget,
            categorie=LigneBudgetProjet.Categorie.MAIN_OEUVRE,
            libelle="Main-d'œuvre (depuis devis)",
            montant_prevu=devis_data['montant_main_oeuvre'],
        )

    return {'projet': projet, 'lien': lien, 'budget': budget}


# ── Alertes automatiques de retard planning (XPRJ22) ─────────────────────────
def alertes_retards_projets(company, *, seuil_jours=None):
    """Notifie le ``responsable`` des projets ACTIFS en retard/à risque (XPRJ22).

    Balaie ``selectors.retards_projet`` (PROJ14) sur chaque projet ACTIF
    (exclut TERMINE/ANNULE) de la société et notifie son ``responsable`` via
    ``apps.notifications.services.notify`` (import fonction-local — frontière
    cross-app ; événement dédié ``EventType.PROJET_RETARD``, XPRJ22).

    IDEMPOTENT : UNE notification par (projet, élément, jour) — un marqueur
    unique dans ``Notification.link`` empêche tout spam en re-run le même
    jour. Un projet SANS responsable est ignoré silencieusement (pas de
    destinataire). Best-effort par élément : un échec n'interrompt pas les
    suivants. Renvoie ``{nb_projets_scannes, nb_alertes_envoyees,
    nb_deja_notifiees}``.
    """
    from django.utils import timezone

    from . import selectors

    from apps.notifications.models import EventType, Notification
    from apps.notifications.services import notify

    today = timezone.localdate()
    projets = Projet.objects.filter(company=company).exclude(
        statut__in=[Projet.Statut.TERMINE, Projet.Statut.ANNULE]
    ).select_related('responsable')

    nb_envoyees = 0
    nb_deja = 0
    for projet in projets:
        if projet.responsable_id is None:
            continue
        data = selectors.retards_projet(projet, seuil_jours=seuil_jours)
        elements = (
            [('tache', t) for t in data['taches_en_retard']]
            + [('tache', t) for t in data['taches_a_risque']]
            + [('jalon', j) for j in data['jalons_en_retard']]
            + [('jalon', j) for j in data['jalons_a_risque']]
        )
        for type_elem, item in elements:
            marqueur = (
                f'gestion_projet:alerte_retard:{projet.id}:'
                f'{type_elem}:{item["id"]}:{today}')
            deja_notifiee = Notification.objects.filter(
                company=company, recipient_id=projet.responsable_id,
                event_type=EventType.PROJET_RETARD, link=marqueur,
                created_at__date=today,
            ).exists()
            if deja_notifiee:
                nb_deja += 1
                continue
            try:
                notify(
                    projet.responsable, EventType.PROJET_RETARD,
                    title=f'Retard planning — {projet.code}',
                    body=(
                        f'{type_elem.capitalize()} « {item["libelle"]} » '
                        f'({item["retard_jours"]} j).'),
                    link=marqueur,
                    company=company,
                )
                nb_envoyees += 1
            except Exception:  # pragma: no cover - défensif, best-effort
                continue

    return {
        'nb_projets_scannes': projets.count(),
        'nb_alertes_envoyees': nb_envoyees,
        'nb_deja_notifiees': nb_deja,
    }


# ── Notifications client aux étapes du projet (XPRJ23) ───────────────────────
def notifier_transition_projet(
        projet, *, ancien_statut, nouveau_statut, user=None):
    """Émet ``TriggerType.PROJET_STATUS_CHANGE`` vers le moteur automation.

    NE crée AUCUN modèle de notification parallèle : délègue au moteur
    no-code EXISTANT (``apps.automation`` N72/N73, import fonction-local —
    frontière cross-app). Config ``{'statut': …}`` avec les enums PROPRES à
    gestion_projet (jamais ``STAGES.py``, règle #2). Best-effort ABSOLU :
    toute exception est avalée ici (le moteur est déjà best-effort en
    interne) — la transition de statut qui a appelé cette fonction n'est
    JAMAIS bloquée. Variables ``{nom_projet}``/``{date}`` disponibles dans le
    corps des modèles de message (substitution côté automation).
    """
    if ancien_statut == nouveau_statut:
        return
    try:
        from apps.automation.engine import evaluate
        from apps.automation.models import TriggerType

        evaluate(
            TriggerType.PROJET_STATUS_CHANGE, projet, projet.company,
            context={
                'new_statut': nouveau_statut,
                'old_statut': ancien_statut,
                'nom_projet': projet.nom,
                'date': _date_du_jour().isoformat(),
            },
            user=user,
        )
    except Exception:  # pragma: no cover - défensif, ne bloque jamais
        pass


def notifier_transition_phase(
        phase, *, ancien_statut, nouveau_statut, user=None):
    """Émet ``TriggerType.PROJET_PHASE_CHANGE`` vers le moteur automation.

    Même politique que ``notifier_transition_projet`` : moteur EXISTANT,
    aucun modèle parallèle, best-effort ABSOLU (n'interrompt jamais la
    transition de phase). Variables ``{nom_projet}``/``{date}`` disponibles.
    """
    if ancien_statut == nouveau_statut:
        return
    try:
        from apps.automation.engine import evaluate
        from apps.automation.models import TriggerType

        evaluate(
            TriggerType.PROJET_PHASE_CHANGE, phase, phase.company,
            context={
                'new_statut': nouveau_statut,
                'old_statut': ancien_statut,
                'nom_projet': phase.projet.nom,
                'date': _date_du_jour().isoformat(),
            },
            user=user,
        )
    except Exception:  # pragma: no cover - défensif, ne bloque jamais
        pass


def _date_du_jour():
    from datetime import date as _date
    return _date.today()
