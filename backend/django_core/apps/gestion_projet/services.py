"""Services (écritures/orchestration) de la Gestion de projet.

Point d'entrée des écritures internes au module. ``company`` est toujours
dérivée du ``projet`` (jamais lue d'un corps de requête) ; aucun import
cross-app (on reste dans ``gestion_projet``).
"""
from datetime import timedelta
from decimal import ROUND_HALF_UP as _ROUND_HALF_UP
from decimal import Decimal

from django.db import models, transaction

from .models import (
    AffectationRessource,
    BaselinePlanning,
    BaselineTache,
    DependanceTache,
    JourFerie,
    PhaseProjet,
    Projet,
    RecurrenceTache,
    RessourceProfil,
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


def copier_semaine_precedente_timesheets(ressource, *, semaine_source,
                                         semaine_cible, admin=False):
    """Copie les timesheets BROUILLON d'une semaine SOURCE vers une semaine
    CIBLE, décalées du même nombre de jours (XPRJ6 — bouton « copier la
    semaine précédente » de la grille hebdomadaire).

    ``semaine_source``/``semaine_cible`` sont les débuts (dates) de deux
    fenêtres de 7 jours inclusives. Chaque ``Timesheet`` de ``ressource`` sur
    la fenêtre source est dupliquée avec sa date décalée, son ``cout`` refigé
    (``cout_timesheet``), en statut BROUILLON — JAMAIS le statut source
    (soumise/approuvée) : une copie est toujours une nouvelle saisie à
    resoumettre. Respecte le verrou de période (``verifier_periode_ouverte``)
    sur chaque date CIBLE : une ligne dont la période cible est verrouillée est
    SAUTÉE (jamais une exception qui interromprait les autres lignes).

    N'écrit RIEN si ``semaine_source == semaine_cible`` (éviterait un
    auto-doublon immédiat) — renvoie un rapport vide. AUCUN doublon si
    ré-exécutée deux fois de suite sur la MÊME cible pour la MÊME ligne
    (projet/tâche/jour) : une timesheet déjà présente ce jour-là pour ce
    couple est SAUTÉE (jamais une seconde copie).

    Renvoie ``{'nb_copiees': int, 'nb_sautees': int, 'copiees': [...],
    'sautees': [...]}`` — chaque entrée sautée porte le motif (``'existe_deja'``
    ou ``'periode_verrouillee'``).
    """
    from .models import Timesheet

    decalage_jours = (semaine_cible - semaine_source).days
    if decalage_jours == 0:
        return {'nb_copiees': 0, 'nb_sautees': 0, 'copiees': [], 'sautees': []}

    fin_source = semaine_source + timedelta(days=6)
    sources = list(Timesheet.objects.filter(
        ressource=ressource, company=ressource.company,
        date__gte=semaine_source, date__lte=fin_source,
    ).select_related('projet', 'tache', 'phase').order_by('date', 'id'))

    fin_cible = semaine_cible + timedelta(days=6)
    existantes_cible = set(
        Timesheet.objects.filter(
            ressource=ressource, company=ressource.company,
            date__gte=semaine_cible, date__lte=fin_cible,
        ).values_list('projet_id', 'tache_id', 'date'))

    copiees = []
    sautees = []
    for source in sources:
        nouvelle_date = source.date + timedelta(days=decalage_jours)
        cle = (source.projet_id, source.tache_id, nouvelle_date)
        if cle in existantes_cible:
            sautees.append({
                'timesheet_source': source.id, 'motif': 'existe_deja'})
            continue
        try:
            verifier_periode_ouverte(
                ressource.company, nouvelle_date, admin=admin)
        except PeriodeVerrouilleeError:
            sautees.append({
                'timesheet_source': source.id,
                'motif': 'periode_verrouillee'})
            continue
        nouvelle = Timesheet.objects.create(
            company=ressource.company,
            projet=source.projet,
            tache=source.tache,
            phase=source.phase,
            ressource=ressource,
            date=nouvelle_date,
            heures=source.heures,
            cout=cout_timesheet(ressource, source.heures),
            commentaire=source.commentaire,
            facturable=source.facturable,
            type_activite=source.type_activite,
            taux_facturation=source.taux_facturation,
            statut=Timesheet.Statut.BROUILLON,
        )
        existantes_cible.add(cle)
        copiees.append({
            'timesheet_source': source.id, 'timesheet_creee': nouvelle.id})

    return {
        'nb_copiees': len(copiees),
        'nb_sautees': len(sautees),
        'copiees': copiees,
        'sautees': sautees,
    }


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
def _avertissement_politique_facturation(projet, chemin_attendu):
    """Avertissement NON BLOQUANT (ZPRJ10) sur une incohérence de politique.

    ``chemin_attendu`` est la politique que l'action de facturation appelée
    représente (``Projet.PolitiqueFacturation.REGIE`` pour le T&M,
    ``...SITUATIONS`` pour les situations BTP). Si la politique DÉCLARÉE du
    projet diverge, renvoie un message d'avertissement — jamais une exception
    ni un blocage : la politique reste purement déclarative (règle #4, couche
    séparée des statuts devis/BC/facture).
    """
    if projet.politique_facturation == chemin_attendu:
        return None
    return (
        f"Politique de facturation déclarée du projet : "
        f"« {projet.get_politique_facturation_display()} » — cette action "
        f"facture pourtant en mode « "
        f"{dict(Projet.PolitiqueFacturation.choices)[chemin_attendu]} ». "
        f"Vérifiez que c'est intentionnel."
    )


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
        'avertissement_politique': _avertissement_politique_facturation(
            projet, Projet.PolitiqueFacturation.REGIE),
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

    Conservé pour compatibilité (utilisé quand un ``pas_minutes`` explicite
    est passé, ex. override de requête) — le chemin PAR DÉFAUT passe
    désormais par ``arrondir_duree`` (ZPRJ1, réglage par société).
    """
    import math
    if minutes <= 0:
        return Decimal('0')
    pas = max(1, int(pas_minutes))
    paliers = math.ceil(minutes / pas)
    minutes_arrondies = paliers * pas
    return (Decimal(minutes_arrondies) / Decimal('60')).quantize(Decimal('0.01'))


# ── Réglages société temps (ZPRJ1) ───────────────────────────────────────────
def get_or_create_reglage_temps(company):
    """Réglage temps SINGLETON de ``company`` (get_or_create, ZPRJ1).

    Jamais créé plusieurs fois pour une même société (``OneToOneField``) :
    un premier appel le crée avec les valeurs par défaut (arrondi 15 min au
    pas supérieur, saisie en heures, 8 h/jour), les appels suivants renvoient
    la même ligne. ``company`` est TOUJOURS l'appelant — jamais lue d'un
    corps de requête.
    """
    from .models import ReglageTemps

    reglage, _ = ReglageTemps.objects.get_or_create(company=company)
    return reglage


def arrondir_duree(company, heures):
    """Arrondit une durée en HEURES selon le réglage temps de ``company``
    (ZPRJ1) — remplace la constante en dur consommée par XPRJ5 (chrono) et,
    demain, la grille hebdomadaire XPRJ6.

    Applique ``arrondi_minutes`` (pas, en minutes) et ``mode_arrondi``
    (inférieur/supérieur/proche) du ``ReglageTemps`` de la société — get_or_
    create, jamais d'erreur si le réglage n'existe pas encore. Cas limites :
    ``heures=0`` → ``Decimal('0')`` (jamais un pas complet à partir de rien) ;
    une durée déjà EXACTEMENT sur un palier n'est jamais modifiée, quel que
    soit le mode ; ``+1 minute`` au-delà d'un palier bascule le résultat
    selon le mode (inférieur reste sur le palier en dessous, supérieur monte
    au palier au-dessus, proche choisit le plus proche — égalité stricte
    arrondie au SUPÉRIEUR). Renvoie un ``Decimal`` à 2 décimales.
    """
    import math

    reglage = get_or_create_reglage_temps(company)
    pas_minutes = max(1, int(reglage.arrondi_minutes or 15))
    mode = reglage.mode_arrondi or 'superieur'

    minutes = Decimal(str(heures or 0)) * Decimal('60')
    if minutes <= 0:
        return Decimal('0.00')

    pas = Decimal(pas_minutes)
    if mode == 'inferieur':
        paliers = math.floor(minutes / pas)
        # Une durée non nulle mais sous le premier palier arrondit à 0 pour le
        # mode « inférieur » (comportement voulu : jamais négatif, jamais un
        # palier créé à partir de rien) — cohérent avec l'existant XPRJ5.
        minutes_arrondies = Decimal(paliers) * pas
    elif mode == 'proche':
        minutes_arrondies = (minutes / pas).to_integral_value(
            rounding=_ROUND_HALF_UP) * pas
    else:  # 'superieur' (défaut) — comportement historique XPRJ5 conservé.
        paliers = math.ceil(minutes / pas)
        minutes_arrondies = Decimal(paliers) * pas

    return (minutes_arrondies / Decimal('60')).quantize(Decimal('0.01'))


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
def arreter_chrono(user, *, pas_minutes=None):
    """Arrête le chrono actif de ``user`` et crée la ``Timesheet`` brouillon.

    Lève ``ChronoError`` si aucun chrono actif. La durée est ``maintenant −
    demarre_a``. Par DÉFAUT (``pas_minutes=None``), l'arrondi suit le réglage
    de la société (``services.arrondir_duree`` — ZPRJ1, pas/mode
    paramétrables via ``reglages-temps/``) ; un ``pas_minutes`` explicite
    (override de requête) garde l'ancien comportement (arrondi au SUPÉRIEUR
    de ce pas, compatibilité XPRJ5). La ressource est celle liée à
    l'utilisateur (``RessourceProfil.user``) — lève ``ChronoError`` si
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
    if pas_minutes is not None:
        heures = _arrondir_duree_heures(minutes_ecoulees, pas_minutes)
    else:
        heures = arrondir_duree(
            chrono.company, Decimal(str(minutes_ecoulees)) / Decimal('60'))

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

    ARC7 — ``Projet.code`` (``unique_together = [('company', 'code')]``) n'est
    PAS un champ ``reference`` : ``core.numbering.next_reference`` filtre
    littéralement sur ``reference__startswith``, donc il ne s'applique pas tel
    quel à ce modèle. On réutilise ses helpers de bucket (``_bucket_prefix``/
    ``_period_segment`` — même radical ``PRJ-<année>-``, reset annuel, déjà
    ré-exportés par le shim ``apps/ventes/utils/references.py``) pour rester
    à l'octet près du même algorithme plus-haut-utilisé+1, et on ajoute la
    protection race-safe qui manquait : verrouille la ligne ``Company``
    (``select_for_update``) le temps du calcul pour sérialiser les créations
    concurrentes — même patron que ``prochain_numero_situation`` ci-dessous
    (verrou sur la ligne ancre faute de ligne ``Projet`` existante à
    verrouiller pour une CRÉATION). Doit être appelé dans une transaction
    atomique par l'appelant (``creer_projet_depuis_devis`` l'est via
    ``@transaction.atomic``).
    """
    import re

    from authentication.models import Company
    from core.numbering import _bucket_prefix

    Company.objects.select_for_update().get(pk=company.pk)
    prefix = _bucket_prefix('PRJ', 'yearly')
    refs = Projet.objects.filter(
        company=company, code__startswith=prefix).values_list(
            'code', flat=True)
    highest = 0
    suffix_re = re.compile(r'-(\d+)$')
    for ref in refs:
        m = suffix_re.search(ref)
        if m:
            highest = max(highest, int(m.group(1)))
    return f'{prefix}-{highest + 1:04d}'


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

    ARC37 — émet AUSSI ``core.events.projet_status_change`` sur le bus
    (double émission ASSUMÉE et documentée pendant la transition : le chemin
    automation EXISTANT reste inchangé, le bus s'ajoute pour ouvrir un
    abonné DÉCOUPLÉ — ``notifications`` — sans jamais importer
    ``apps.automation`` depuis un abonné cross-app).
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

    try:
        from core.events import projet_status_change

        projet_status_change.send(
            sender=None, projet=projet, company=projet.company, user=user,
            ancien_statut=ancien_statut, nouveau_statut=nouveau_statut)
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


# ── Export/import du plan de tâches (XPRJ24) ─────────────────────────────────
EXPORT_TACHES_ENTETES = [
    'code_wbs', 'libelle', 'parent_wbs', 'date_debut_prevue',
    'date_fin_prevue', 'charge_estimee', 'statut', 'assigne',
    'dependances_fs',
]


def exporter_taches(projet):
    """Lignes du plan de tâches (WBS) prêtes pour un export xlsx (XPRJ24).

    Une ligne par ``Tache`` : ``code_wbs``, libellé, ``parent_wbs`` (code WBS
    du parent, vide si racine), dates, charge, statut, assigné (nom de la
    ressource), et ``dependances_fs`` (codes WBS des PRÉDÉCESSEURS FS de
    cette tâche, séparés par ``;`` — seul le type FS est exporté/réimporté,
    le cas courant du module). Round-trip STABLE : réimporter ce jeu de
    lignes reconstruit le même arbre (même hiérarchie + mêmes dépendances).
    Tout est scopé société via le projet. Lecture seule.
    """
    from .models import DependanceTache

    taches = list(
        Tache.objects.filter(projet=projet, company=projet.company)
        .select_related('parent', 'assigne').order_by('ordre', 'id'))
    par_id = {t.id: t for t in taches}

    deps_par_successeur = {}
    for dep in DependanceTache.objects.filter(
            successeur__in=taches, type_dependance='fs'):
        deps_par_successeur.setdefault(dep.successeur_id, []).append(
            dep.predecesseur_id)

    lignes = []
    for t in taches:
        parent_wbs = par_id[t.parent_id].code_wbs if t.parent_id else ''
        deps_codes = [
            par_id[pid].code_wbs for pid in deps_par_successeur.get(t.id, [])
            if pid in par_id
        ]
        lignes.append({
            'code_wbs': t.code_wbs,
            'libelle': t.libelle,
            'parent_wbs': parent_wbs,
            'date_debut_prevue': (
                t.date_debut_prevue.isoformat()
                if t.date_debut_prevue else ''),
            'date_fin_prevue': (
                t.date_fin_prevue.isoformat() if t.date_fin_prevue else ''),
            'charge_estimee': (
                str(t.charge_estimee) if t.charge_estimee is not None
                else ''),
            'statut': t.statut,
            'assigne': t.assigne.nom if t.assigne_id else '',
            'dependances_fs': ';'.join(deps_codes),
        })
    return lignes


class ImportTachesError(Exception):
    """Erreur métier lors de l'import du plan de tâches."""


def _parse_date_iso(value):
    if not value:
        return None
    from datetime import date as _date
    try:
        return _date.fromisoformat(str(value).strip())
    except ValueError:
        return None


def _parse_decimal(value):
    if value in (None, ''):
        return None
    try:
        return Decimal(str(value).strip())
    except Exception:
        return None


@transaction.atomic
def importer_taches(projet, lignes, *, confirm=False):
    """Importe un plan de tâches (WBS) depuis des lignes (CSV/xlsx) (XPRJ24).

    Chaque ligne suit ``EXPORT_TACHES_ENTETES`` (``code_wbs`` obligatoire et
    UNIQUE dans le fichier — clé d'identité du round-trip). DEUX PASSES :
    1) crée/rattache toutes les tâches par ``code_wbs`` (hiérarchie
       ``parent_wbs`` résolue APRÈS que toutes les tâches existent, pour
       accepter un ordre de lignes arbitraire) ;
    2) recrée les dépendances FS depuis ``dependances_fs``.

    ``confirm=False`` (DÉFAUT) : DRY-RUN — valide toutes les lignes, renvoie
    le rapport d'ERREURS, N'ÉCRIT RIEN. ``confirm=True`` : écrit dans une
    TRANSACTION ATOMIQUE (tout ou rien) — une erreur de validation est
    rapportée SANS écrire une seule ligne, même en confirm.

    Renvoie ``{'erreurs': [...], 'nb_lignes': N, 'nb_creees': N, 'nb_deps': N}``.
    """
    from .models import DependanceTache

    erreurs = []
    codes_vus = set()
    for i, ligne in enumerate(lignes, start=1):
        code = (ligne.get('code_wbs') or '').strip()
        libelle = (ligne.get('libelle') or '').strip()
        if not code:
            erreurs.append(f'Ligne {i} : code_wbs obligatoire.')
            continue
        if code in codes_vus:
            erreurs.append(f'Ligne {i} : code_wbs « {code} » en double.')
            continue
        codes_vus.add(code)
        if not libelle:
            erreurs.append(f'Ligne {i} ({code}) : libelle obligatoire.')
        statut = (ligne.get('statut') or Tache.Statut.A_FAIRE).strip()
        if statut not in Tache.Statut.values:
            erreurs.append(
                f'Ligne {i} ({code}) : statut « {statut} » inconnu.')
        parent_wbs = (ligne.get('parent_wbs') or '').strip()
        if parent_wbs and parent_wbs not in {
                (r.get('code_wbs') or '').strip() for r in lignes}:
            erreurs.append(
                f'Ligne {i} ({code}) : parent_wbs « {parent_wbs} » introuvable '
                'dans le fichier.')
        for dep_code in _split_deps(ligne.get('dependances_fs')):
            if dep_code not in {
                    (r.get('code_wbs') or '').strip() for r in lignes}:
                erreurs.append(
                    f'Ligne {i} ({code}) : dépendance « {dep_code} » '
                    'introuvable dans le fichier.')

    if erreurs:
        return {
            'erreurs': erreurs, 'nb_lignes': len(lignes),
            'nb_creees': 0, 'nb_deps': 0,
        }

    if not confirm:
        return {
            'erreurs': [], 'nb_lignes': len(lignes),
            'nb_creees': 0, 'nb_deps': 0,
        }

    # Résolution des ressources par nom (best-effort : nom introuvable →
    # assigné laissé vide, jamais bloquant).
    from .models import RessourceProfil
    ressources_par_nom = {
        r.nom: r for r in RessourceProfil.objects.filter(
            company=projet.company)
    }

    # Passe 1 : crée/rattache toutes les tâches (sans parent pour l'instant).
    taches_par_code = {}
    for ligne in lignes:
        code = ligne['code_wbs'].strip()
        taches_par_code[code] = Tache.objects.create(
            company=projet.company,
            projet=projet,
            code_wbs=code,
            libelle=ligne['libelle'].strip(),
            date_debut_prevue=_parse_date_iso(ligne.get('date_debut_prevue')),
            date_fin_prevue=_parse_date_iso(ligne.get('date_fin_prevue')),
            charge_estimee=_parse_decimal(ligne.get('charge_estimee')),
            statut=(ligne.get('statut') or Tache.Statut.A_FAIRE).strip(),
            assigne=ressources_par_nom.get(
                (ligne.get('assigne') or '').strip()),
        )

    # Passe 1bis : rattache la hiérarchie parent (toutes les tâches existent).
    for ligne in lignes:
        parent_wbs = (ligne.get('parent_wbs') or '').strip()
        if parent_wbs:
            tache = taches_par_code[ligne['code_wbs'].strip()]
            tache.parent = taches_par_code[parent_wbs]
            tache.save(update_fields=['parent'])

    # Passe 2 : recrée les dépendances FS.
    nb_deps = 0
    for ligne in lignes:
        successeur = taches_par_code[ligne['code_wbs'].strip()]
        for dep_code in _split_deps(ligne.get('dependances_fs')):
            predecesseur = taches_par_code[dep_code]
            DependanceTache.objects.create(
                company=projet.company,
                predecesseur=predecesseur,
                successeur=successeur,
                type_dependance='fs',
            )
            nb_deps += 1

    return {
        'erreurs': [], 'nb_lignes': len(lignes),
        'nb_creees': len(taches_par_code), 'nb_deps': nb_deps,
    }


def _split_deps(raw):
    if not raw:
        return []
    return [c.strip() for c in str(raw).split(';') if c.strip()]


# ── Journal des modifications de tâches et jalons (XPRJ26) ──────────────────
# Champs sensibles suivis pour chaque type de cible : au-delà (libellé,
# description...) rien n'est journalisé — seules les valeurs qui pèsent sur le
# PLANNING/l'audit sont tracées, pour ne pas noyer l'historique.
TACHE_CHAMPS_SUIVIS = (
    'statut', 'date_debut_prevue', 'date_fin_prevue', 'charge_estimee',
    'assigne_id',
)
JALON_CHAMPS_SUIVIS = ('date_prevue', 'statut', 'facturation_pct')


def _valeur_str(valeur):
    """Représentation texte stable d'une valeur de champ pour le journal.

    ``None`` → chaîne vide. Un ``Decimal`` a ses zéros décimaux de fin
    retirés (p.ex. ``Decimal('30.00')`` -> ``'30'``, ``Decimal('12.50')`` ->
    ``'12.5'``) SANS jamais basculer en notation scientifique (contrairement à
    ``Decimal.normalize()``, qui donnerait ``'3E+1'``) : ``facturation_pct``
    (``DecimalField(decimal_places=2)``) revient de la base avec 2 décimales
    fixes même quand la valeur saisie n'en avait aucune — sans ce nettoyage,
    une valeur INCHANGÉE en base (mais reformattée) semblerait avoir changé de
    forme dans le journal. Le reste est converti tel quel (dates et
    énumérations ont déjà un ``str()`` lisible).
    """
    if valeur is None:
        return ''
    if isinstance(valeur, Decimal):
        texte = format(valeur, 'f')
        if '.' in texte:
            texte = texte.rstrip('0').rstrip('.')
        return texte or '0'
    return str(valeur)


def journaliser_modification_tache(tache, anciennes_valeurs, *, auteur):
    """Journalise les champs sensibles modifiés d'une ``Tache`` (XPRJ26).

    ``anciennes_valeurs`` est un dict ``{champ: valeur_avant}`` capturé par
    l'appelant AVANT la sauvegarde (voir ``views.TacheViewSet.perform_update``).
    Une entrée ``ProjetActivity`` (``cible_type='tache'``, ``cible_id=tache.id``)
    est créée PAR CHAMP réellement changé parmi ``TACHE_CHAMPS_SUIVIS`` — aucune
    entrée si rien de suivi n'a changé. ``company``/``auteur`` posés côté
    serveur. N'écrit RIEN d'autre (comportement de sauvegarde inchangé).
    """
    from .models import ProjetActivity

    for champ in TACHE_CHAMPS_SUIVIS:
        if champ not in anciennes_valeurs:
            continue
        avant = anciennes_valeurs[champ]
        apres = getattr(tache, champ)
        if avant == apres:
            continue
        ProjetActivity.objects.create(
            company=tache.company,
            projet=tache.projet,
            cible_type=ProjetActivity.CibleType.TACHE,
            cible_id=tache.id,
            champ=champ,
            old_value=_valeur_str(avant),
            new_value=_valeur_str(apres),
            auteur=auteur,
        )


def journaliser_modification_jalon(jalon, anciennes_valeurs, *, auteur):
    """Journalise les champs sensibles modifiés d'un ``Jalon`` (XPRJ26).

    Même contrat que ``journaliser_modification_tache`` (voir sa docstring),
    pour ``JALON_CHAMPS_SUIVIS``. ``cible_type='jalon'``, ``cible_id=jalon.id``.
    """
    from .models import ProjetActivity

    for champ in JALON_CHAMPS_SUIVIS:
        if champ not in anciennes_valeurs:
            continue
        avant = anciennes_valeurs[champ]
        apres = getattr(jalon, champ)
        if avant == apres:
            continue
        ProjetActivity.objects.create(
            company=jalon.company,
            projet=jalon.projet,
            cible_type=ProjetActivity.CibleType.JALON,
            cible_id=jalon.id,
            champ=champ,
            old_value=_valeur_str(avant),
            new_value=_valeur_str(apres),
            auteur=auteur,
        )


# ── Génération IA d'un plan de tâches depuis le devis (XPRJ29) ──────────────
class PlanTachesIAError(Exception):
    """Erreur métier lors de la génération/matérialisation du plan IA."""


class PlanTachesIAIndisponible(PlanTachesIAError):
    """Levée quand le service IA (FastAPI, key-gated) est indisponible."""


def _fastapi_internal_url():
    """URL interne du service FastAPI IA (même convention que ``apps.chat``/
    ``apps.crm.intake_photo``)."""
    import os

    from django.conf import settings

    base = (getattr(settings, 'FASTAPI_INTERNAL_URL', '')
            or os.environ.get('FASTAPI_INTERNAL_URL', '')
            or 'http://fastapi_ia:8001/api/fastapi')
    return base.rstrip('/') + '/projets/generer-plan'


def _service_token_for(user):
    """Jeton JWT court pour relayer l'auth vers FastAPI (même motif que
    ``apps.crm.intake_photo._service_token_for``)."""
    if user is None:
        return ''
    try:
        from rest_framework_simplejwt.tokens import AccessToken
        return str(AccessToken.for_user(user))
    except Exception:  # pragma: no cover - défensif
        return ''


def proposer_plan_taches_ia(devis_data, type_installation, *, user=None):
    """Propose un brouillon de plan de tâches (WBS) via le service IA (XPRJ29).

    ``devis_data`` provient EXCLUSIVEMENT de ``apps.ventes.selectors.
    devis_pour_projet`` (jamais un import de ``ventes.models`` — frontière
    cross-app). Délègue au service FastAPI ``POST /projets/generer-plan``
    (key-gated sur ``GROQ_API_KEY``/provider équivalent). AUCUNE écriture :
    pure proposition JSON, à matérialiser explicitement APRÈS confirmation
    utilisateur via ``materialiser_plan_taches``.

    Lève ``PlanTachesIAIndisponible`` (503 côté vue) si le service IA renvoie
    503 (clé absente) ou est injoignable ; ``PlanTachesIAError`` (400 côté vue)
    si la réponse est invalide (502 FastAPI ou payload inattendu).
    """
    import requests

    url = _fastapi_internal_url()
    token = _service_token_for(user)
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    payload = {
        'devis': {
            'id': devis_data.get('id'),
            'montant_materiel': float(devis_data.get('montant_materiel') or 0),
            'montant_main_oeuvre': float(
                devis_data.get('montant_main_oeuvre') or 0),
            'nb_lignes_materiel': devis_data.get('nb_lignes_materiel') or 0,
            'nb_lignes_main_oeuvre': devis_data.get(
                'nb_lignes_main_oeuvre') or 0,
        },
        'type_installation': type_installation or 'residentiel',
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
    except requests.RequestException as exc:
        raise PlanTachesIAIndisponible(
            "Le service de génération IA est injoignable.") from exc

    if resp.status_code == 503:
        raise PlanTachesIAIndisponible(
            "Le service de génération IA n'est pas configuré (clé LLM "
            "absente).")
    if resp.status_code != 200:
        raise PlanTachesIAError(
            "Le service IA n'a pas pu proposer de plan exploitable.")
    try:
        data = resp.json()
    except ValueError as exc:
        raise PlanTachesIAError(
            "Réponse du service IA illisible.") from exc
    taches = data.get('taches') if isinstance(data, dict) else None
    if not isinstance(taches, list) or not taches:
        raise PlanTachesIAError("Le plan proposé est vide ou invalide.")
    return {'taches': taches}


@transaction.atomic
def materialiser_plan_taches(projet, plan):
    """Matérialise un plan de tâches PROPOSÉ (XPRJ29) — APRÈS confirmation.

    ``plan`` est le dict ``{'taches': [{code, libelle, phase, duree_jours,
    dependances_fs}, ...]}`` renvoyé par ``proposer_plan_taches_ia`` (ou
    modifié par l'utilisateur avant confirmation — aucune re-validation
    contre le LLM, seulement contre la forme attendue). Crée, pour chaque
    tâche : la ``PhaseProjet`` si absente (même logique idempotente
    qu'``instancier_modele``), la ``Tache`` (dates dérivées de
    ``duree_jours`` en jours calendaires depuis ``projet.date_debut`` — ou
    aujourd'hui si absent — de façon SÉQUENTIELLE dans l'ordre des tâches),
    puis les ``DependanceTache`` FS déclarées (codes inconnus ignorés,
    silencieusement — la proposition a déjà été nettoyée côté IA mais on ne
    fait jamais confiance en écriture). ``company`` est TOUJOURS celle du
    ``projet``. Écritures atomiques. Renvoie la liste des ``Tache`` créées.
    """
    from datetime import date as _date
    from datetime import timedelta

    from .models import PhaseProjet

    taches_brutes = (plan or {}).get('taches') or []
    if not isinstance(taches_brutes, list) or not taches_brutes:
        raise PlanTachesIAError("Le plan à matérialiser est vide.")

    libelles_phase = {tp: lib for tp, lib in PHASES_STANDARD}
    ordres_phase = {
        tp: i for i, (tp, _) in enumerate(PHASES_STANDARD, start=1)}
    phases_par_type = {
        p.type_phase: p for p in projet.phases.all()}

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

    types_phase_valides = {tp for tp, _ in PHASES_STANDARD}
    curseur = projet.date_debut or _date.today()
    taches_par_code = {}
    creees = []
    for ordre, brut in enumerate(taches_brutes, start=1):
        if not isinstance(brut, dict):
            continue
        code = str(brut.get('code', '')).strip()
        libelle = str(brut.get('libelle', '')).strip()
        if not libelle:
            continue
        type_phase = str(brut.get('phase', '')).strip().lower()
        if type_phase not in types_phase_valides:
            type_phase = PhaseProjet.TypePhase.ETUDE
        phase = _phase_pour(type_phase)
        try:
            duree = max(1, int(brut.get('duree_jours', 1) or 1))
        except (TypeError, ValueError):
            duree = 1
        date_debut_prevue = curseur
        date_fin_prevue = curseur + timedelta(days=duree - 1)
        curseur = date_fin_prevue + timedelta(days=1)
        tache = Tache.objects.create(
            company=projet.company,
            projet=projet,
            phase=phase,
            libelle=libelle,
            code_wbs=code,
            ordre=ordre,
            date_debut_prevue=date_debut_prevue,
            date_fin_prevue=date_fin_prevue,
        )
        creees.append(tache)
        if code:
            taches_par_code[code] = tache

    for brut in taches_brutes:
        if not isinstance(brut, dict):
            continue
        code = str(brut.get('code', '')).strip()
        successeur = taches_par_code.get(code)
        if successeur is None:
            continue
        for dep_code in (brut.get('dependances_fs') or []):
            predecesseur = taches_par_code.get(str(dep_code).strip())
            if predecesseur is None or predecesseur.id == successeur.id:
                continue
            DependanceTache.objects.create(
                company=projet.company,
                predecesseur=predecesseur,
                successeur=successeur,
                type_dependance=DependanceTache.TypeDependance.FS,
            )

    if not creees:
        raise PlanTachesIAError(
            "Aucune tâche exploitable dans le plan à matérialiser.")
    return creees


# ── Plan de ressources : publication (ZPRJ2) ────────────────────────────────
@transaction.atomic
def publier_affectations(company, *, ids=None, ressource_id=None,
                         debut=None, fin=None, auteur=None):
    """Publie un lot d'``AffectationRessource`` BROUILLON (ZPRJ2).

    Sélectionne soit par ``ids`` (liste d'identifiants) soit par
    ``ressource_id`` + ``debut``/``fin`` (période — bornes INCLUSIVES,
    convention PROJ16/17), scopé ``company``. IDEMPOTENT : une affectation
    déjà ``publie`` est simplement IGNORÉE (jamais republiée, jamais
    renotifiée) — un re-run ne fait rien de plus. Pose ``statut_publication``,
    ``publie_le`` (horodatage serveur) et ``publie_par`` CÔTÉ SERVEUR sur
    chaque affectation nouvellement publiée, puis notifie CHAQUE ressource
    concernée UNE FOIS (regroupe par ressource — pas une notification par
    affectation) via ``apps.notifications.services.notify`` (import
    fonction-local, cross-app, BEST-EFFORT : un échec de notification
    n'interrompt jamais la transaction ni les ressources suivantes). Une
    ressource sans ``user`` lié est publiée normalement mais ignorée
    proprement côté notification (personne à notifier). Renvoie
    ``{'nb_publiees': int, 'nb_deja_publiees': int, 'nb_notifies': int}``.
    """
    from django.utils import timezone

    qs = AffectationRessource.objects.filter(company=company)
    if ids:
        qs = qs.filter(id__in=list(ids))
    elif ressource_id is not None and debut is not None and fin is not None:
        qs = qs.filter(
            ressource_id=ressource_id, date_debut__lte=fin,
            date_fin__gte=debut)
    else:
        return {'nb_publiees': 0, 'nb_deja_publiees': 0, 'nb_notifies': 0}

    affectations = list(qs.select_related('ressource'))
    nb_deja_publiees = sum(
        1 for a in affectations
        if a.statut_publication == AffectationRessource.StatutPublication.PUBLIE)
    a_publier = [
        a for a in affectations
        if a.statut_publication != AffectationRessource.StatutPublication.PUBLIE]

    maintenant = timezone.now()
    ids_a_publier = [a.id for a in a_publier]
    if ids_a_publier:
        AffectationRessource.objects.filter(id__in=ids_a_publier).update(
            statut_publication=AffectationRessource.StatutPublication.PUBLIE,
            publie_le=maintenant,
            publie_par=auteur,
        )

    # Regroupe par ressource pour UNE notification par ressource (pas une par
    # affectation), best-effort — un échec ne casse jamais la publication.
    ressources_a_notifier = {}
    for a in a_publier:
        if a.ressource_id is not None:
            ressources_a_notifier.setdefault(a.ressource_id, a.ressource)

    nb_notifies = 0
    if ressources_a_notifier:
        try:
            from apps.notifications.models import EventType
            from apps.notifications.services import notify
        except Exception:  # pragma: no cover - défensif
            EventType = None
            notify = None

        for ressource in ressources_a_notifier.values():
            if notify is None or ressource.user_id is None:
                continue
            try:
                notify(
                    ressource.user,
                    EventType.DIGEST,
                    title='Planning publié',
                    body='Votre planning a été publié — consultez vos '
                         'créneaux.',
                    link=f'gestion_projet:planning_publie:{ressource.id}:'
                         f'{maintenant.date()}',
                    company=company,
                )
                nb_notifies += 1
            except Exception:  # pragma: no cover - best-effort
                continue

    return {
        'nb_publiees': len(a_publier),
        'nb_deja_publiees': nb_deja_publiees,
        'nb_notifies': nb_notifies,
    }


# ── Copier le plan de ressources de la semaine précédente (ZPRJ3) ──────────
@transaction.atomic
def copier_semaine_precedente(company, *, semaine_source, semaine_cible,
                              ressource_id=None, equipe_id=None):
    """Copie les affectations d'une fenêtre SOURCE vers une fenêtre CIBLE
    décalée de 7 j × N (ZPRJ3) — équivalent « Copy previous week ».

    ``semaine_source``/``semaine_cible`` sont les débuts (dates) des deux
    fenêtres de 7 jours [``semaine_X``, ``semaine_X + 6 jours``]. Duplique
    chaque ``AffectationRessource`` de la société (filtrée par ``ressource_id``
    OU ``equipe_id`` si fourni — sinon toutes) dont la fenêtre est ENTIÈREMENT
    contenue dans la semaine source, en décalant ``date_debut``/``date_fin`` du
    même nombre de jours que l'écart entre les deux débuts de semaine, en
    statut BROUILLON (ZPRJ2 — jamais publié directement).

    SAUTE (sans écrire) toute copie qui tomberait :
      * sur une ``Indisponibilite`` de la ressource (``selectors.
        ressource_disponible_sur_periode``) — les affectations d'équipe/actif
        matériel n'ont pas de ressource individuelle et ne sont jamais
        sautées pour ce motif ;
      * en CONFLIT avec une affectation déjà existante de la même ressource
        sur la fenêtre cible (détection identique à ``selectors.
        conflits_affectation`` — chevauchement calendaire, y compris via
        équipe).

    N'écrit RIEN si ``semaine_source == semaine_cible`` (fenêtre nulle,
    éviterait un auto-doublon immédiat) — renvoie un rapport vide. AUCUN
    doublon si ré-exécutée deux fois de suite sur la MÊME cible : la seconde
    exécution retrouve les affectations déjà copiées sur la fenêtre cible et
    les compte en conflit (donc sautées), jamais dupliquées deux fois.

    Renvoie ``{'nb_copiees': int, 'nb_sautees': int, 'copiees': [...],
    'sautees': [...]}`` — chaque entrée porte l'affectation source (id) et,
    pour les sautées, le motif (``'indisponible'`` ou ``'conflit'``).
    """
    from . import selectors

    decalage_jours = (semaine_cible - semaine_source).days
    if decalage_jours == 0:
        return {
            'nb_copiees': 0, 'nb_sautees': 0, 'copiees': [], 'sautees': [],
        }

    fin_source = semaine_source + timedelta(days=6)

    qs = AffectationRessource.objects.filter(
        company=company,
        date_debut__gte=semaine_source, date_fin__lte=fin_source,
    ).select_related('ressource', 'equipe')
    if ressource_id is not None:
        qs = qs.filter(ressource_id=ressource_id)
    if equipe_id is not None:
        qs = qs.filter(equipe_id=equipe_id)

    # Affectations EXISTANTES sur la fenêtre cible (anti-conflit ET
    # anti-doublon sur ré-exécution), indexées par ressource.
    fin_cible_max = fin_source + timedelta(days=decalage_jours)
    existantes_cible = list(
        AffectationRessource.objects.filter(
            company=company,
            date_debut__lte=fin_cible_max,
            date_fin__gte=semaine_cible,
        ))
    existantes_par_ressource = {}
    for existante in existantes_cible:
        if existante.ressource_id is not None:
            existantes_par_ressource.setdefault(
                existante.ressource_id, []).append(existante)

    copiees = []
    sautees = []
    for source in qs.order_by('date_debut', 'id'):
        nouvelle_debut = source.date_debut + timedelta(days=decalage_jours)
        nouvelle_fin = source.date_fin + timedelta(days=decalage_jours)

        if source.ressource_id is not None:
            # Indisponibilité de la ressource sur la fenêtre cible.
            if not selectors.ressource_disponible_sur_periode(
                    source.ressource, nouvelle_debut, nouvelle_fin):
                sautees.append({
                    'affectation_source': source.id, 'motif': 'indisponible',
                })
                continue
            # Conflit avec une affectation déjà existante de la ressource.
            conflit = False
            for existante in existantes_par_ressource.get(
                    source.ressource_id, []):
                if (nouvelle_debut <= existante.date_fin
                        and nouvelle_fin >= existante.date_debut):
                    conflit = True
                    break
            if conflit:
                sautees.append({
                    'affectation_source': source.id, 'motif': 'conflit',
                })
                continue

        nouvelle = AffectationRessource.objects.create(
            company=company,
            tache=source.tache,
            ressource=source.ressource,
            equipe=source.equipe,
            actif_type=source.actif_type,
            actif_id=source.actif_id,
            date_debut=nouvelle_debut,
            date_fin=nouvelle_fin,
            charge_jours=source.charge_jours,
            quantite=source.quantite,
            note=source.note,
            statut_publication=AffectationRessource.StatutPublication.BROUILLON,
        )
        if source.ressource_id is not None:
            existantes_par_ressource.setdefault(
                source.ressource_id, []).append(nouvelle)
        copiees.append({
            'affectation_source': source.id, 'affectation_creee': nouvelle.id,
        })

    return {
        'nb_copiees': len(copiees),
        'nb_sautees': len(sautees),
        'copiees': copiees,
        'sautees': sautees,
    }


# ── Auto-affectation : appliquer les propositions de nivellement (ZPRJ4) ───
def _taches_sans_affectation(company, debut, fin):
    """Tâches de ``company`` chevauchant [debut, fin] SANS AUCUNE affectation
    directe/équipe/actif (lecture seule, aide interne à ``auto_affecter``).

    Une tâche sans dates prévues n'est jamais considérée (rien à comparer à
    la fenêtre) : ce ciblage reste conservateur (jamais une tâche non datée
    auto-affectée à l'aveugle)."""
    return list(
        Tache.objects.filter(
            company=company,
            date_debut_prevue__isnull=False, date_fin_prevue__isnull=False,
            date_debut_prevue__lte=fin, date_fin_prevue__gte=debut,
        ).exclude(
            id__in=AffectationRessource.objects.filter(
                company=company).values_list('tache_id', flat=True)
        ).select_related('projet'))


def auto_affecter(company, debut, fin, *, confirmer=False):
    """Applique (ou simule) l'auto-affectation des tâches en excès (ZPRJ4).

    Odoo Planning « Auto Plan » — équivalent gestion-projet. Combine deux
    sources de candidats sur [debut, fin] :

    1. les PROPOSITIONS DE DÉPLACEMENT de ``selectors.nivellement_charge``
       (ressources sur-chargées → sous-chargées, anti-conflit déjà garanti
       par le sélecteur) — chaque proposition RÉASSIGNE la ``ressource`` de
       l'``AffectationRessource`` déplacée (jamais un nouveau créneau) ;
    2. les TÂCHES SANS AUCUNE AFFECTATION dans la fenêtre — pour chacune, la
       ressource ACTIVE disponible (``selectors.ressource_disponible_sur_
       periode``) avec le PLUS de marge (``plan_de_charge.disponible_heures``,
       simulée en mémoire au fil des affectations pour rester équitable) reçoit
       une NOUVELLE ``AffectationRessource`` (période = fenêtre de la tâche,
       statut BROUILLON) ; une tâche sans candidat valide (aucune ressource
       disponible/avec marge) est RAPPORTÉE, jamais silencieusement ignorée.

    Mode ``?simuler=1`` (``confirmer=False``, PAR DÉFAUT) : NE MUTE RIEN,
    renvoie le plan proposé. Mode ``?confirm=1`` (``confirmer=True``) :
    applique réellement (déplace/crée), toujours en statut BROUILLON (ZPRJ2 —
    jamais publié directement), transaction atomique.

    Renvoie ``{'simule': bool, 'deplacements': [...], 'creations': [...],
    'non_resolues': [...]}`` — ``deplacements``/``creations`` portent la même
    forme que confirmées ou simulées (``affectation``/``nouvelle_ressource``
    pour un déplacement ; ``tache``/``ressource`` pour une création).
    """
    from . import selectors

    plan = selectors.nivellement_charge(company, debut, fin)
    deplacements = [{
        'affectation': p['affectation'],
        'tache': p['tache'],
        'de_ressource': p['de_ressource'],
        'de_nom': p['de_nom'],
        'vers_ressource': p['vers_ressource'],
        'vers_nom': p['vers_nom'],
        'charge_heures': p['charge_heures'],
    } for p in plan['propositions']]

    # Marge restante simulée par ressource (réutilisée pour les créations de
    # tâches sans affectation, à la suite des déplacements proposés).
    marge_par_ressource = {
        ligne['ressource']: ligne['disponible_heures']
        for ligne in plan['sous_charges']
    }
    # Cache LOCAL à cet appel (jamais persistant entre requêtes) des
    # ``RessourceProfil`` candidates, pour éviter N requêtes redondantes.
    ressources_par_id = {
        r.id: r for r in RessourceProfil.objects.filter(
            company=company, id__in=list(marge_par_ressource.keys()))
    }

    creations = []
    non_resolues = []
    taches_sans_affectation = _taches_sans_affectation(company, debut, fin)
    for tache in taches_sans_affectation:
        candidats = sorted(
            marge_par_ressource.items(), key=lambda kv: -kv[1])
        choisi = None
        for ressource_id, marge in candidats:
            if marge <= 0:
                continue
            ressource = ressources_par_id.get(ressource_id)
            if ressource is None or not ressource.actif:
                continue
            if not selectors.ressource_disponible_sur_periode(
                    ressource, tache.date_debut_prevue,
                    tache.date_fin_prevue):
                continue
            choisi = ressource_id
            break
        if choisi is None:
            non_resolues.append({
                'tache': tache.id, 'tache_libelle': tache.libelle,
                'projet': tache.projet_id,
            })
            continue
        creations.append({
            'tache': tache.id, 'tache_libelle': tache.libelle,
            'ressource': choisi,
            'date_debut': tache.date_debut_prevue.isoformat(),
            'date_fin': tache.date_fin_prevue.isoformat(),
        })
        marge_par_ressource[choisi] = max(
            0.0, marge_par_ressource.get(choisi, 0.0) - 1.0)

    if not confirmer:
        return {
            'simule': True, 'deplacements': deplacements,
            'creations': creations, 'non_resolues': non_resolues,
        }

    with transaction.atomic():
        for d in deplacements:
            AffectationRessource.objects.filter(
                id=d['affectation'], company=company).update(
                    ressource_id=d['vers_ressource'],
                    statut_publication=(
                        AffectationRessource.StatutPublication.BROUILLON),
                )
        for c in creations:
            tache = Tache.objects.get(id=c['tache'], company=company)
            AffectationRessource.objects.create(
                company=company,
                tache=tache,
                ressource_id=c['ressource'],
                date_debut=tache.date_debut_prevue,
                date_fin=tache.date_fin_prevue,
                statut_publication=(
                    AffectationRessource.StatutPublication.BROUILLON),
            )

    return {
        'simule': False, 'deplacements': deplacements,
        'creations': creations, 'non_resolues': non_resolues,
    }


# ── Conversion tâche → ticket SAV (ZPRJ11) ───────────────────────────────────
class ConversionTicketSavError(Exception):
    """Levée quand une tâche est déjà convertie ou sans client résolvable."""


def convertir_tache_en_ticket_sav(tache, *, user=None):
    """Convertit une ``Tache`` en ``sav.Ticket`` (ZPRJ11).

    Le client est résolu depuis ``tache.projet.client_id`` via un sélecteur
    ``crm.selectors`` (frontière cross-app, import fonction-local — jamais
    ``crm.models``). L'écriture du ``Ticket`` passe EXCLUSIVEMENT par
    ``apps.sav.services.create_ticket_from_projet_tache`` (jamais
    ``sav.models`` depuis ``gestion_projet``). Une tâche déjà convertie
    (``ticket_sav_id`` non nul) lève ``ConversionTicketSavError`` — pas de
    double conversion. Trace le lien retour sur la tâche (référence LÂCHE
    ``ticket_sav_id``). Renvoie le ``Ticket`` créé (objet de l'app ``sav``).
    """
    if tache.ticket_sav_id:
        raise ConversionTicketSavError(
            "Cette tâche a déjà été convertie en ticket SAV.")

    projet = tache.projet
    from apps.crm import selectors as crm_selectors
    client = None
    if projet.client_id:
        client = crm_selectors.get_company_client(
            projet.company, projet.client_id)
    if client is None:
        raise ConversionTicketSavError(
            "Impossible de résoudre le client du projet — conversion en "
            "ticket SAV impossible.")

    from apps.sav import services as sav_services
    description = (
        f'{tache.libelle}\n\n{tache.description}'
        if tache.description else tache.libelle)
    ticket = sav_services.create_ticket_from_projet_tache(
        company=tache.company, client=client, description=description)

    tache.ticket_sav_id = ticket.id
    tache.save(update_fields=['ticket_sav_id'])
    return ticket


# ── Création de tâches par e-mail entrant (alias projet) (ZPRJ12) ──────────
def is_email_ingestion_configured():
    """True si une ingestion e-mail entrante est configurée (pattern
    ``apps.ventes.inbound_email.is_inbound_configured``, réutilisé — jamais
    réinventé). Sans configuration, ``ingest_email_projet`` reste un NO-OP
    propre (aucune connexion réseau, jamais d'exception)."""
    from apps.ventes import inbound_email
    return inbound_email.is_inbound_configured()


def ingest_email_projet(company, *, to_alias, subject='', body='',
                        from_email=''):
    """Crée une ``Tache`` depuis un e-mail entrant adressé à l'alias d'un
    projet (ZPRJ12) — pattern d'ingestion réutilisé de
    ``apps.ventes.inbound_email`` (parsing PUR, aucun appel réseau ici : la
    connexion IMAP/webhook reste dans la commande appelante).

    ``to_alias`` est comparé à ``Projet.alias_email`` (scopé société,
    insensible à la casse). Un alias INCONNU (aucun projet ne le porte) est
    IGNORÉ proprement (renvoie None, jamais d'erreur — un alias mal orthographié
    ne doit jamais planter le sweep). Sans ingestion configurée
    (``is_email_ingestion_configured`` False), NE FAIT RIEN et renvoie None
    (no-op propre) — permet d'appeler cette fonction sans risque même hors
    configuration (le contrôle est fait ici, pas seulement dans la commande).

    Renvoie la ``Tache`` créée (``statut=a_faire``, ``libelle`` = objet,
    ``description`` = corps), journalisant l'expéditeur dans la description.
    """
    if not is_email_ingestion_configured():
        return None

    alias = (to_alias or '').strip().lower()
    if not alias:
        return None

    projet = Projet.objects.filter(
        company=company, alias_email__iexact=alias).first()
    if projet is None:
        return None

    libelle = (subject or '(sans objet)')[:200]
    description = body or ''
    if from_email:
        description = f'[e-mail de {from_email}]\n\n{description}'

    return Tache.objects.create(
        company=company, projet=projet, libelle=libelle,
        description=description, statut=Tache.Statut.A_FAIRE)


# ── Conversion à-faire (records.Activity) → tâche projet (XKB4) ────────────
class ConversionActiviteError(Exception):
    """Levée quand une activité personnelle ne peut pas être convertie."""


def creer_tache_depuis_activite(activite, *, projet_id, company=None):
    """Convertit un ``records.Activity`` (typiquement un à-faire personnel,
    XKB4) en ``Tache`` du projet ``projet_id``, en préservant son contenu.

    Reçoit l'instance ``Activity`` déjà chargée par l'appelant (``records``
    ne nous passe jamais son ``models`` — seul cet import fonction-local par
    l'appelant existe, jamais l'inverse) ; on ne lit ici que des attributs
    scalaires (``summary``/``note``/``due_date``), jamais
    ``apps.records.models`` lui-même, pour ne créer aucune dépendance
    circulaire. ``company`` est dérivée de l'activité si non fournie, jamais
    du corps de requête.
    """
    company = company or getattr(activite, 'company', None)
    try:
        projet = Projet.objects.get(pk=projet_id, company=company)
    except Projet.DoesNotExist:
        raise ConversionActiviteError(
            "Projet introuvable pour cette société.")

    libelle = (getattr(activite, 'summary', '') or '(sans titre)')[:200]
    return Tache.objects.create(
        company=projet.company, projet=projet, libelle=libelle,
        description=getattr(activite, 'note', '') or '',
        date_fin_prevue=getattr(activite, 'due_date', None),
        statut=Tache.Statut.A_FAIRE)


# ── ARC22 — chemin de création VIA le master sous-traitant unifié DC34 ──────
def creer_sous_traitant_via_master(
        *, company, user=None, nom, specialite='', contact='', telephone='',
        email='', actif=True):
    """ARC22 — crée un ``SousTraitant`` (carnet projet local) EN CRÉANT AUSSI
    son pendant sur le référentiel unifié DC34 (``stock.Fournisseur``
    type=service + ``SousTraitantProfile``), via ``stock.services.
    create_sous_traitant`` — frontière cross-app respectée : ce module
    n'importe JAMAIS ``apps.stock.models``, uniquement son point d'entrée
    ``services.py`` (import fonction-local, CLAUDE.md).

    C'est le chemin de création RECOMMANDÉ pour tout NOUVEAU sous-traitant
    (corrige la régression PROJ38 constatée par ARC22 : avant cette fonction,
    le carnet ``gestion_projet`` ne posait jamais le lien ``fournisseur``).
    L'ancien chemin de création directe (``SousTraitantViewSet.create``) reste
    disponible SANS lien — additif, aucune rupture de compat.

    ``specialite`` (texte libre du carnet projet) n'a pas de correspondance
    STRICTE avec ``SousTraitantProfile.Metier`` (enum fermé) : le mapping
    (insensible à la casse, repli ``AUTRE`` si aucun métier ne correspond,
    comportement jamais bloquant) est délégué à ``stock.services.
    create_sous_traitant`` (``specialite=``) — la connaissance de l'enum
    ``Metier`` reste côté ``stock``.

    Renvoie le ``SousTraitant`` (carnet local) créé, avec ``fournisseur`` posé.
    """
    from apps.stock import services as stock_services

    from .models import SousTraitant

    fournisseur = stock_services.create_sous_traitant(
        company=company, user=user, nom=nom, specialite=specialite,
        contact_personne=contact or None, email=email or None,
        telephone=telephone or None, actif=actif)

    return SousTraitant.objects.create(
        company=company, nom=nom, specialite=specialite, contact=contact,
        telephone=telephone, email=email, actif=actif,
        fournisseur=fournisseur)
