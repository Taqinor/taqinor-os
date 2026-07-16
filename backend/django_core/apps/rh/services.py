"""Services RH (écritures/orchestration) — congés & soldes.

Centralise la LOGIQUE métier testable des congés :

* ``acquisition_mensuelle`` / ``droit_annuel`` — droit à congés payés (Maroc) :
  ~1,5 jour ouvrable par mois de service (18 j/an) + bonus d'ancienneté
  (1,5 j par tranche de 5 ans).
* ``calculer_jours_demande`` — durée décomptée d'une demande (jours ouvrés hors
  fériés/week-end si le type le requiert, sinon jours calendaires).
* ``valider_demande`` / ``refuser_demande`` — transitions du workflow FG163, avec
  mise à jour atomique du compteur ``pris`` du ``SoldeConge`` quand le type
  d'absence déduit le solde.

Tout est cadré société : les fonctions reçoivent des objets déjà scopés par la
vue ; elles ne lisent jamais la société du corps de requête.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from . import holidays


# Droit légal marocain : 1,5 jour ouvrable acquis par mois de service.
ACQUISITION_PAR_MOIS = Decimal('1.5')
# Bonus d'ancienneté : +1,5 jour par tranche de 5 ans révolus.
BONUS_PAR_TRANCHE = Decimal('1.5')
TRANCHE_ANNEES = 5


def bonus_anciennete(annees_service):
    """Jours de congé supplémentaires liés à l'ancienneté (Maroc).

    +1,5 jour ouvrable par tranche de 5 années de service révolues. ``< 5`` ans
    → 0 ; 5–9 → 1,5 ; 10–14 → 3 ; etc.
    """
    try:
        annees = int(annees_service)
    except (TypeError, ValueError):
        return Decimal('0')
    if annees < TRANCHE_ANNEES:
        return Decimal('0')
    tranches = annees // TRANCHE_ANNEES
    return BONUS_PAR_TRANCHE * tranches


def acquisition_mensuelle(annees_service=0):
    """Jours acquis pour UN mois de service plein (base 1,5 + part ancienneté).

    Le bonus d'ancienneté annuel est réparti sur 12 mois pour rester homogène
    avec une acquisition mois par mois.
    """
    base = ACQUISITION_PAR_MOIS
    part_bonus = bonus_anciennete(annees_service) / Decimal('12')
    return (base + part_bonus).quantize(Decimal('0.01'))


def droit_annuel(annees_service=0):
    """Droit annuel théorique = 12 × base + bonus d'ancienneté.

    12 mois × 1,5 = 18 jours, plus le bonus d'ancienneté de l'année.
    """
    return (ACQUISITION_PAR_MOIS * 12 + bonus_anciennete(annees_service)) \
        .quantize(Decimal('0.01'))


def feries_periode(company, date_debut, date_fin):
    """ZRH1 — fériés (fixes ET mobiles société) d'une période, cross-app-safe.

    Réutilise ``notifications.calendar_utils.feries_entre`` (jamais
    ``notifications.models`` importé directement dans ``rh``) pour ajouter
    les fêtes MOBILES hégiriennes (Aïd el-Fitr, Aïd el-Adha, 1er Moharram,
    Mawlid…) et tout férié société saisi dans ``notifications.Holiday`` au
    décompte, en plus de la table FIXE ``holidays.JOURS_FERIES_FIXES_MA``.
    Renvoie une liste de ``date`` (vide si rien de configuré, ou dates
    invalides).
    """
    if date_debut is None or date_fin is None:
        return []
    from apps.notifications.calendar_utils import feries_entre
    return feries_entre(company, date_debut, date_fin)


def annees_service(date_embauche, reference=None):
    """Années de service pleines à ``reference`` (aujourd'hui par défaut).

    ``None`` si ``date_embauche`` est absente (ancienneté non calculable).
    """
    if date_embauche is None:
        return 0
    ref = reference or timezone.localdate()
    annees = ref.year - date_embauche.year
    if (ref.month, ref.day) < (date_embauche.month, date_embauche.day):
        annees -= 1
    return max(annees, 0)


@transaction.atomic
def accruer_conges_mensuel(dossier, *, annee, mois, apply=False):
    """ZRH2 — acquisition mensuelle automatique pour UN employé/mois.

    Odoo « Accrual Time Off » : crédite ``SoldeConge.acquis`` du droit du mois
    (``acquisition_mensuelle``, ancienneté dérivée de ``date_embauche``) pour
    l'année ``annee``, SANS jamais dépasser 12 crédits/an (garde
    ``mois_acquis``). Idempotent : un second appel pour le MÊME mois ne
    crédite pas deux fois. ``apply=False`` (dry-run) ne modifie rien et
    renvoie le montant qui SERAIT crédité. Renvoie un dict
    ``{'credite': Decimal, 'deja_acquis': bool}``.
    """
    from .models import SoldeConge

    if apply:
        solde, _ = SoldeConge.objects.select_for_update().get_or_create(
            company=dossier.company, employe=dossier, annee=annee)
    else:
        # Dry-run : ne JAMAIS créer la ligne SoldeConge (elle ne doit
        # exister qu'après une acquisition réellement appliquée).
        solde = SoldeConge.objects.filter(
            company=dossier.company, employe=dossier, annee=annee).first()
    mois_acquis = solde.mois_acquis if solde else 0
    if mois_acquis >= 12 or mois_acquis >= mois:
        # Déjà crédité pour ce mois (ou l'année est déjà pleinement créditée).
        return {'credite': Decimal('0'), 'deja_acquis': True}

    service = annees_service(dossier.date_embauche)
    montant = acquisition_mensuelle(service)
    if apply:
        solde.acquis = (solde.acquis or Decimal('0')) + montant
        solde.mois_acquis = mois
        solde.save(update_fields=[
            'acquis', 'mois_acquis', 'date_modification'])
    return {'credite': montant, 'deja_acquis': False}


@transaction.atomic
def reporter_solde_janvier(dossier, *, annee_precedente, annee_cible,
                           plafond=None, apply=False):
    """ZRH2 — report janvier : transfère le ``disponible`` restant de
    ``annee_precedente`` vers ``report`` de ``annee_cible`` (Odoo « Time Off
    accrual carry-over »).

    Idempotent (``report_applique`` sur le solde CIBLE) : un second appel ne
    re-crédite pas. ``plafond`` borne le montant reporté (``None`` =
    illimité, comportement par défaut). ``apply=False`` ne modifie rien.
    Renvoie un dict ``{'reporte': Decimal, 'deja_applique': bool}``.
    """
    from .models import SoldeConge

    if apply:
        cible, _ = SoldeConge.objects.select_for_update().get_or_create(
            company=dossier.company, employe=dossier, annee=annee_cible)
    else:
        # Dry-run : ne JAMAIS créer la ligne SoldeConge cible (elle ne doit
        # exister qu'après un report réellement appliqué) — même correctif que
        # `accruer_conges_mensuel` ci-dessus.
        cible = SoldeConge.objects.filter(
            company=dossier.company, employe=dossier,
            annee=annee_cible).first()
    if cible is not None and cible.report_applique:
        return {'reporte': Decimal('0'), 'deja_applique': True}

    precedent = SoldeConge.objects.filter(
        company=dossier.company, employe=dossier,
        annee=annee_precedente).first()
    disponible = precedent.disponible if precedent else Decimal('0')
    if disponible < 0:
        disponible = Decimal('0')
    montant = disponible
    if plafond is not None and montant > plafond:
        montant = Decimal(str(plafond))

    if apply:
        cible.report = (cible.report or Decimal('0')) + montant
        cible.report_applique = True
        cible.save(update_fields=[
            'report', 'report_applique', 'date_modification'])
    return {'reporte': montant, 'deja_applique': False}


def jour_bloque_conflit(employe, date_debut, date_fin):
    """ZRH4 — jour bloqué du DÉPARTEMENT de ``employe`` chevauchant la plage.

    Renvoie le premier ``JourBloqueConge`` en conflit (ou ``None``) : un
    blocage SANS département lié couvre TOUTE la société ; sinon il ne
    s'applique qu'aux départements qu'il liste. Un employé sans département
    n'est concerné QUE par les blocages société entière (sans département).
    """
    from django.db.models import Q

    from .models import JourBloqueConge

    qs = JourBloqueConge.objects.filter(
        company=employe.company, date_debut__lte=date_fin,
        date_fin__gte=date_debut)
    if employe.departement_id:
        qs = qs.filter(
            Q(departements__isnull=True) |
            Q(departements__id=employe.departement_id))
    else:
        qs = qs.filter(departements__isnull=True)
    return qs.distinct().first()


def calculer_jours_demande(type_absence, date_debut, date_fin,
                           extra_holidays=None,
                           demi_journee_debut=False, demi_journee_fin=False):
    """Durée décomptée d'une demande de congé (FG163).

    Si ``type_absence.decompte_jours_ouvres`` est vrai, ne compte que les jours
    ouvrés (hors week-end et fériés, cf. ``holidays.working_days`` / FG5) ;
    sinon, compte les jours calendaires. Renvoie un ``Decimal`` (0 si la plage
    est invalide).

    XRH3 — ``demi_journee_debut``/``demi_journee_fin`` retranchent chacune
    0,5 j du total (une demande d'1 jour avec les deux drapeaux reste bornée
    à 0 minimum — jamais négative). Un flag sur une plage de 0 jour (date
    invalide) n'a aucun effet.
    """
    if type_absence is not None and type_absence.decompte_jours_ouvres:
        n = holidays.working_days(date_debut, date_fin, extra_holidays)
    else:
        n = holidays.calendar_days(date_debut, date_fin)
    jours = Decimal(n)
    if n > 0:
        if demi_journee_debut:
            jours -= Decimal('0.5')
        if demi_journee_fin:
            jours -= Decimal('0.5')
        if jours < 0:
            jours = Decimal('0')
    return jours


# ─────────────────────────────────────────────────────────────────────────
# Heures supplémentaires & calcul majoré (FG168) — code du travail marocain.
# Durée normale : 44 h/semaine ≈ 8 h/jour (seuil par défaut). Au-delà, les
# heures sont supplémentaires et majorées :
#   +25 %  HS de JOUR un jour ouvrable ;
#   +50 %  HS de NUIT un jour ouvrable, OU HS de JOUR un jour de repos/férié ;
#   +100 % HS de NUIT un jour de repos/férié.
# ─────────────────────────────────────────────────────────────────────────
SEUIL_JOURNALIER_DEFAUT = Decimal('8')
TAUX_HS_25 = Decimal('0.25')
TAUX_HS_50 = Decimal('0.50')
TAUX_HS_100 = Decimal('1.00')

_CENT = Decimal('0.01')


def _d(value, defaut='0'):
    """Convertit ``value`` en ``Decimal`` (``defaut`` si None/invalide)."""
    if value is None:
        return Decimal(defaut)
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (TypeError, ValueError, ArithmeticError):
        return Decimal(defaut)


def calculer_majoration(heures_travaillees, heures_nuit=0,
                        seuil_journalier=None, jour_repos_ferie=False,
                        taux_horaire=None):
    """Répartit les heures d'une journée en normales / HS par tranche de taux.

    Règle marocaine (cf. ``HeuresSupp``) :

    * Un jour de REPOS hebdomadaire ou FÉRIÉ : TOUTES les heures travaillées sont
      supplémentaires (seuil 0) — majorées 50 % le jour, 100 % la nuit.
    * Un jour ouvrable : seules les heures au-delà du ``seuil_journalier``
      (défaut 8 h) sont supplémentaires — majorées 25 % le jour, 50 % la nuit.

    ``heures_nuit`` est la part de la journée effectuée entre 21 h et 6 h ; les
    HS de nuit sont prioritairement imputées à la tranche nuit (la majoration la
    plus forte s'applique d'abord aux heures de nuit). Renvoie un ``dict`` :
    ``{'heures_normales', 'hs_25', 'hs_50', 'hs_100', 'total_hs',
       'montant_majore'}`` (montant ``None`` si ``taux_horaire`` absent).
    """
    total = _d(heures_travaillees)
    if total < 0:
        total = Decimal('0')
    nuit = _d(heures_nuit)
    if nuit < 0:
        nuit = Decimal('0')
    if nuit > total:
        nuit = total

    if jour_repos_ferie:
        # Jour de repos/férié : tout est supplémentaire — pas d'heures normales.
        seuil = Decimal('0')
    else:
        seuil = _d(seuil_journalier, str(SEUIL_JOURNALIER_DEFAUT)) \
            if seuil_journalier is not None else SEUIL_JOURNALIER_DEFAUT
        if seuil < 0:
            seuil = Decimal('0')

    heures_sup = max(Decimal('0'), total - seuil)
    heures_normales = total - heures_sup

    # Les heures supplémentaires se composent d'abord des heures de NUIT (taux le
    # plus fort), puis des heures de JOUR, dans la limite des HS disponibles.
    hs_nuit = min(nuit, heures_sup)
    hs_jour = heures_sup - hs_nuit

    hs_25 = Decimal('0')
    hs_50 = Decimal('0')
    hs_100 = Decimal('0')
    if jour_repos_ferie:
        # Repos/férié : jour → 50 %, nuit → 100 %.
        hs_50 = hs_jour
        hs_100 = hs_nuit
    else:
        # Jour ouvrable : jour → 25 %, nuit → 50 %.
        hs_25 = hs_jour
        hs_50 = hs_nuit

    montant = None
    taux = _d(taux_horaire, '0') if taux_horaire is not None else None
    if taux is not None:
        # Montant des SEULES majorations (la base est déjà payée par le salaire)
        # + le coût horaire des heures supplémentaires elles-mêmes.
        base_hs = (hs_25 + hs_50 + hs_100) * taux
        majoration = (hs_25 * TAUX_HS_25 + hs_50 * TAUX_HS_50
                      + hs_100 * TAUX_HS_100) * taux
        montant = (base_hs + majoration).quantize(_CENT)

    return {
        'heures_normales': heures_normales.quantize(_CENT),
        'hs_25': hs_25.quantize(_CENT),
        'hs_50': hs_50.quantize(_CENT),
        'hs_100': hs_100.quantize(_CENT),
        'total_hs': (hs_25 + hs_50 + hs_100).quantize(_CENT),
        'montant_majore': montant,
    }


def appliquer_majoration(heures_supp, derive_seuil_from_horaire=False):
    """Calcule et POSE les décomptes majorés sur une instance ``HeuresSupp``.

    Utilise ``calculer_majoration`` avec le ``taux_horaire`` de l'entrée (ou, à
    défaut, le ``cout_horaire`` interne du dossier employé). Renseigne
    ``heures_normales``, ``hs_25``, ``hs_50``, ``hs_100``, ``taux_horaire`` et
    ``montant_majore`` sur l'objet (non sauvegardé — l'appelant ``save()``).

    XRH8 — si ``derive_seuil_from_horaire`` est vrai (l'appelant n'a PAS fourni
    explicitement ``seuil_journalier`` dans la requête), le seuil journalier
    est dérivé de l'horaire ACTIF de l'employé à la date de l'entrée
    (``selectors.horaire_actif``) : un horaire Ramadan à 6 h/j abaisse le
    seuil sur sa fenêtre de validité ; hors fenêtre (ou sans horaire assigné),
    le seuil par défaut du modèle (8 h) reste inchangé — retour automatique.
    """
    if derive_seuil_from_horaire and heures_supp.employe_id:
        from . import selectors
        horaire = selectors.horaire_actif(heures_supp.employe, heures_supp.date)
        if horaire is not None:
            heures_supp.seuil_journalier = horaire.heures_jour_defaut
    taux = heures_supp.taux_horaire
    if taux is None and heures_supp.employe_id:
        taux = heures_supp.employe.cout_horaire
    res = calculer_majoration(
        heures_supp.heures_travaillees,
        heures_nuit=heures_supp.heures_nuit,
        seuil_journalier=heures_supp.seuil_journalier,
        jour_repos_ferie=heures_supp.jour_repos_ferie,
        taux_horaire=taux,
    )
    heures_supp.heures_normales = res['heures_normales']
    heures_supp.hs_25 = res['hs_25']
    heures_supp.hs_50 = res['hs_50']
    heures_supp.hs_100 = res['hs_100']
    heures_supp.taux_horaire = taux
    heures_supp.montant_majore = res['montant_majore']
    return heures_supp


# ─────────────────────────────────────────────────────────────────────────
# Planning d'équipes / roster (FG169) — affectation hebdo + conflit de congés.
# ─────────────────────────────────────────────────────────────────────────
def lundi_de_la_semaine(jour):
    """Renvoie le lundi (début de semaine ISO) de la semaine contenant ``jour``.

    Sert à grouper les lignes de roster par semaine (``semaine_du``). Renvoie
    ``None`` si ``jour`` est absent.
    """
    if jour is None:
        return None
    from datetime import timedelta
    return jour - timedelta(days=jour.weekday())


def detecter_conflit_conge(company, employe_id, jour):
    """Vrai si l'employé est en congé/absence VALIDÉE le ``jour`` d'affectation.

    Réutilise le sélecteur congés ``selectors.employe_absent_le`` (FG165) : on
    n'affecte pas un technicien au roster un jour où il a une demande de congé
    validée. Toujours scopé société ; ``False`` si la société/employé manque.
    """
    from . import selectors
    return selectors.employe_absent_le(company, employe_id, jour)


def appliquer_roster(affectation):
    """Pose ``semaine_du`` et ``conflit_conge`` sur une ``AffectationRoster``.

    ``semaine_du`` = lundi de la semaine de ``date`` ; ``conflit_conge`` est
    recalculé via ``detecter_conflit_conge`` (congé validé couvrant le jour).
    L'objet n'est pas sauvegardé — l'appelant ``save()``.
    """
    affectation.semaine_du = lundi_de_la_semaine(affectation.date)
    affectation.conflit_conge = detecter_conflit_conge(
        affectation.company, affectation.employe_id, affectation.date)
    return affectation


def _solde_de_lannee(demande):
    """``SoldeConge`` (créé si besoin) de l'employé pour l'année de début."""
    from .models import SoldeConge
    annee = demande.date_debut.year
    solde, _ = SoldeConge.objects.get_or_create(
        company=demande.company, employe=demande.employe, annee=annee)
    return solde


@transaction.atomic
def valider_demande(demande, decide_par=None):
    """Valide une demande SOUMISE et, si le type déduit le solde, met à jour le
    compteur ``pris`` du ``SoldeConge`` de l'année (atomique).

    Idempotent vis-à-vis d'une demande déjà validée : ne re-déduit pas. Lève
    ``ValueError`` si la demande n'est pas dans un état décidable.

    XRH3 — si ``type_absence.jours_max_sans_justificatif`` est renseigné et
    que ``demande.jours`` le DÉPASSE, un ``justificatif`` est OBLIGATOIRE :
    sans lui la validation est refusée (``ValueError`` — 400 explicite côté
    vue). ``None`` (pas de plafond configuré) ne bloque jamais.
    """
    from .models import DemandeConge, SoldeConge
    if demande.statut != DemandeConge.Statut.SOUMISE:
        raise ValueError(
            "Seule une demande soumise peut être validée.")
    plafond = demande.type_absence.jours_max_sans_justificatif
    if (plafond is not None and demande.jours is not None
            and demande.jours > plafond and not demande.justificatif):
        raise ValueError(
            "Justificatif obligatoire : cette absence de "
            f"{demande.jours} j dépasse le seuil de {plafond} j sans "
            "justificatif.")
    # Verrou pessimiste sur le solde pour éviter une double déduction concurrente.
    if demande.type_absence.deduit_solde and demande.jours:
        annee = demande.date_debut.year
        solde, _ = SoldeConge.objects.select_for_update().get_or_create(
            company=demande.company, employe=demande.employe, annee=annee)
        solde.pris = (solde.pris or Decimal('0')) + demande.jours
        solde.save(update_fields=['pris', 'date_modification'])
    demande.statut = DemandeConge.Statut.VALIDEE
    demande.decide_par = decide_par
    demande.date_decision = timezone.now()
    demande.motif_refus = ''
    demande.save(update_fields=[
        'statut', 'decide_par', 'date_decision', 'motif_refus'])

    # XPRJ9 — signale la validation au bus d'événements (core.events) : les
    # abonnés (gestion_projet) créent/étendent l'Indisponibilite planning de la
    # RessourceProfil liée au même utilisateur, SANS que rh importe
    # gestion_projet directement.
    from core.events import conge_approuve
    conge_approuve.send(
        sender=DemandeConge, demande=demande, user=decide_par, annule=False)
    return demande


@transaction.atomic
def refuser_demande(demande, decide_par=None, motif_refus=''):
    """Refuse une demande SOUMISE (aucune déduction de solde)."""
    from .models import DemandeConge
    if demande.statut != DemandeConge.Statut.SOUMISE:
        raise ValueError(
            "Seule une demande soumise peut être refusée.")
    demande.statut = DemandeConge.Statut.REFUSEE
    demande.decide_par = decide_par
    demande.date_decision = timezone.now()
    demande.motif_refus = motif_refus or ''
    demande.save(update_fields=[
        'statut', 'decide_par', 'date_decision', 'motif_refus'])
    return demande


@transaction.atomic
def annuler_demande(demande):
    """Annule une demande. Si elle était VALIDÉE et déduisait le solde, recrédite
    le compteur ``pris`` du ``SoldeConge`` correspondant (atomique)."""
    from .models import DemandeConge, SoldeConge
    etait_validee = demande.statut == DemandeConge.Statut.VALIDEE
    if etait_validee and demande.type_absence.deduit_solde and demande.jours:
        annee = demande.date_debut.year
        try:
            solde = SoldeConge.objects.select_for_update().get(
                company=demande.company, employe=demande.employe, annee=annee)
            solde.pris = max(
                Decimal('0'), (solde.pris or Decimal('0')) - demande.jours)
            solde.save(update_fields=['pris', 'date_modification'])
        except SoldeConge.DoesNotExist:
            pass
    demande.statut = DemandeConge.Statut.ANNULEE
    demande.save(update_fields=['statut'])

    # XPRJ9 — n'émet l'événement d'annulation QUE si la demande était VALIDÉE
    # (une indisponibilité a pu être créée par le bus à ce moment-là) ; annuler
    # une demande encore SOUMISE n'a jamais rien créé côté planning.
    if etait_validee:
        from core.events import conge_approuve
        conge_approuve.send(
            sender=DemandeConge, demande=demande, user=None, annule=True)
    return demande


class EmargementError(Exception):
    """Erreur métier d'un émargement de remise EPI (FG180)."""


@transaction.atomic
def emarger_dotation(dotation, *, signataire_nom, role_signataire=None,
                     signataire=None, ip_adresse='', user_agent='',
                     methode=None, mention=''):
    """Enregistre l'émargement signé d'une remise d'EPI (FG180).

    Crée un ``EmargementEpi`` portant le nom dactylographié (``signataire_nom``,
    fait foi — loi 53-05), le rôle (employé bénéficiaire / remettant / témoin),
    l'utilisateur agissant éventuel (``signataire``, NULL pour un employé sans
    compte qui émarge sur place) et les preuves (``ip_adresse`` ≤ 45,
    ``user_agent``, ``methode`` typed/draw, ``mention``). La société est posée
    côté serveur (celle de la dotation) — jamais lue du corps de requête.

    Marque ensuite la dotation ACCUSÉE (``accuse_remise = True`` +
    ``date_accuse`` = maintenant) : l'accusé de réception prouve la remise de
    l'EPI, pièce exigible en cas de contrôle CNSS / accident du travail. Une
    dotation déjà émargée peut l'être à nouveau (p. ex. un témoin supplémentaire)
    sans erreur — ``date_accuse`` n'est posée qu'au premier accusé.

    Le nom du signataire est requis (loi 53-05) ; vide → ``EmargementError``.

    Renvoie un dict ``{'emargement', 'deja_accusee'}`` : l'émargement créé et un
    booléen indiquant si la dotation était DÉJÀ accusée avant cet appel.
    """
    from .models import EmargementEpi

    nom = (signataire_nom or '').strip()
    if not nom:
        raise EmargementError(
            "Le nom du signataire est requis (loi 53-05).")

    if role_signataire is None:
        role_signataire = EmargementEpi.RoleSignataire.EMPLOYE
    if methode is None:
        methode = EmargementEpi.Methode.TYPED

    emargement = EmargementEpi.objects.create(
        company=dotation.company,
        dotation=dotation,
        signataire_nom=nom,
        signataire=signataire,
        role_signataire=role_signataire,
        ip_adresse=(ip_adresse or '')[:45],
        user_agent=user_agent or '',
        methode=methode,
        mention=mention or '',
    )

    deja_accusee = bool(dotation.accuse_remise)
    if not deja_accusee:
        dotation.accuse_remise = True
        dotation.date_accuse = timezone.now()
        dotation.save(update_fields=[
            'accuse_remise', 'date_accuse', 'date_modification'])

    return {'emargement': emargement, 'deja_accusee': deja_accusee}


def creer_dotation_epi(*, company, epi, employe, quantite, user=None,
                       bloquer_si_insuffisant=False, **extra_fields):
    """YHIRE13 — crée une ``DotationEpi`` et décrémente le stock si ``epi``
    est lié à un produit (``EpiCatalogue.produit_id``).

    Catalogue non lié (``produit_id`` vide) = comportement STRICTEMENT
    inchangé (aucun effet stock). Le mouvement de stock (typé SORTIE, motif
    dotation) est créé via ``apps.stock.services`` — jamais d'import direct
    de ``apps.stock.models``. Lève ``ValueError`` si le stock est insuffisant
    ET que ``bloquer_si_insuffisant`` est vrai (sinon la dotation se fait
    quand même, warn par défaut).
    """
    from .models import DotationEpi

    dotation = DotationEpi.objects.create(
        company=company, epi=epi, employe=employe, quantite=quantite,
        **extra_fields)

    if epi.produit_id:
        from apps.stock import services as stock_services
        stock_services.decrementer_stock_dotation_epi(
            company=company, produit_id=epi.produit_id, quantite=quantite,
            reference=f'DotationEPI#{dotation.id}', user=user,
            bloquer_si_insuffisant=bloquer_si_insuffisant)

    return dotation


class RestitutionEpiError(Exception):
    """Erreur métier lors de la restitution d'une dotation EPI (YHIRE13)."""


def restituer_dotation_epi(dotation, *, user=None):
    """YHIRE13 — restitue une ``DotationEpi`` : réintègre le stock si l'EPI
    est lié à un produit, marque ``restituee``. Une dotation déjà restituée
    lève ``RestitutionEpiError`` (jamais restituée deux fois — pas de double
    réintégration de stock)."""
    if dotation.restituee:
        raise RestitutionEpiError('Cette dotation a déjà été restituée.')

    if dotation.epi.produit_id:
        from apps.stock import services as stock_services
        stock_services.reintegrer_stock_restitution_epi(
            company=dotation.company, produit_id=dotation.epi.produit_id,
            quantite=dotation.quantite,
            reference=f'RestitutionEPI#{dotation.id}', user=user)

    dotation.restituee = True
    dotation.date_restitution = timezone.now()
    dotation.save(update_fields=[
        'restituee', 'date_restitution', 'date_modification'])
    return dotation


def creer_accident_travail(serializer, company):
    """Crée un AccidentTravail (FG181) avec une référence race-safe.

    Pose ``company`` côté serveur et génère ``reference`` (``AT-YYYYMM-NNNN``)
    de façon collision-proof via ``apps.ventes.utils.references`` (plus-haut-
    utilisé+1 par société/mois, savepoint + retry) — JAMAIS ``count()+1``.
    L'import est function-local : il franchit la frontière inter-app
    (utilitaire partagé déjà réutilisé par compta/installations) sans créer de
    cycle d'import au chargement.
    """
    from apps.ventes.utils.references import create_with_reference

    from .models import AccidentTravail

    return create_with_reference(
        AccidentTravail, 'AT', company,
        lambda reference: serializer.save(
            company=company, reference=reference),
    )


def creer_presqu_accident(serializer, company, declare_par=None):
    """Crée un PresquAccident (FG182) avec une référence race-safe.

    Pose ``company`` ET ``declare_par`` (l'utilisateur qui remonte) côté serveur
    et génère ``reference`` (``NM-YYYYMM-NNNN``) de façon collision-proof via
    ``apps.ventes.utils.references`` (plus-haut-utilisé+1 par société/mois,
    savepoint + retry) — JAMAIS ``count()+1``. L'import est function-local : il
    franchit la frontière inter-app (utilitaire partagé déjà réutilisé par
    compta/installations) sans créer de cycle d'import au chargement.
    """
    from apps.ventes.utils.references import create_with_reference

    from .models import PresquAccident

    return create_with_reference(
        PresquAccident, 'NM', company,
        lambda reference: serializer.save(
            company=company, reference=reference, declare_par=declare_par),
    )


@transaction.atomic
def soumettre_ouverture(ouverture, *, demandeur):
    """YHIRE14 — soumet une ouverture BROUILLON à approbation.

    Seule une ouverture en ``brouillon`` peut être soumise. Pose
    ``demandeur`` (celui qui soumet — jamais lu du corps de requête) et
    ``date_soumission``. Lève ``ValueError`` sinon.
    """
    from .models import OuverturePoste

    if ouverture.statut != OuverturePoste.Statut.BROUILLON:
        raise ValueError(
            'Seule une ouverture en brouillon peut être soumise à '
            'approbation.')
    ouverture.statut = OuverturePoste.Statut.EN_APPROBATION
    ouverture.demandeur = demandeur
    ouverture.date_soumission = timezone.now()
    ouverture.save(update_fields=[
        'statut', 'demandeur', 'date_soumission', 'date_modification'])
    return ouverture


def approuver_ouverture(ouverture, *, approbateur):
    """YHIRE14 — approuve une ouverture EN_APPROBATION -> OUVERT.

    SoD (séparation des tâches) : l'approbateur ne peut JAMAIS être le
    demandeur — auto-approbation refusée (``ValueError``). Lève aussi
    ``ValueError`` si l'ouverture n'est pas dans l'état décidable.
    """
    from .models import OuverturePoste

    if ouverture.statut != OuverturePoste.Statut.EN_APPROBATION:
        raise ValueError(
            "Seule une ouverture en attente d'approbation peut être "
            'approuvée.')
    if ouverture.demandeur_id and ouverture.demandeur_id == getattr(
            approbateur, 'id', None):
        raise ValueError(
            'Le demandeur ne peut pas approuver sa propre réquisition '
            '(séparation des tâches).')
    ouverture.statut = OuverturePoste.Statut.OUVERT
    ouverture.approbateur = approbateur
    ouverture.date_decision = timezone.now()
    ouverture.motif_refus = ''
    if not ouverture.date_ouverture:
        ouverture.date_ouverture = timezone.now().date()
    ouverture.save(update_fields=[
        'statut', 'approbateur', 'date_decision', 'motif_refus',
        'date_ouverture', 'date_modification'])
    return ouverture


def refuser_ouverture(ouverture, *, approbateur, motif_refus=''):
    """YHIRE14 — refuse une ouverture EN_APPROBATION (reste non ouverte).

    Même garde SoD que ``approuver_ouverture``. Le statut refusé n'a pas de
    valeur dédiée dans le cycle (spécification) : on ramène l'ouverture en
    ``brouillon`` pour permettre une resoumission après correction, le motif
    étant conservé pour traçabilité.
    """
    from .models import OuverturePoste

    if ouverture.statut != OuverturePoste.Statut.EN_APPROBATION:
        raise ValueError(
            "Seule une ouverture en attente d'approbation peut être "
            'refusée.')
    if ouverture.demandeur_id and ouverture.demandeur_id == getattr(
            approbateur, 'id', None):
        raise ValueError(
            'Le demandeur ne peut pas refuser sa propre réquisition '
            '(séparation des tâches).')
    ouverture.statut = OuverturePoste.Statut.BROUILLON
    ouverture.approbateur = approbateur
    ouverture.date_decision = timezone.now()
    ouverture.motif_refus = motif_refus or ''
    ouverture.save(update_fields=[
        'statut', 'approbateur', 'date_decision', 'motif_refus',
        'date_modification'])
    return ouverture


def embaucher(candidature, matricule=None, **dossier_kwargs):
    """Convertit une candidature EMBAUCHÉE en ``DossierEmploye`` (FG189 — ATS).

    Quand un candidat est retenu, on crée son dossier employé (même société que
    la candidature) à partir des données déjà saisies (``nom``, ``email``,
    ``telephone`` et le ``poste_ref`` / ``departement`` de l'ouverture), enrichi
    des ``dossier_kwargs`` fournis (ex. ``type_contrat``, ``date_embauche``,
    ``poste``…). On passe l'``etape`` de la candidature à ``embauche`` et on lie
    le dossier via ``employe_cree``. Si l'ouverture atteint son
    ``nombre_postes`` de candidats embauchés, elle bascule en ``pourvu``.

    IDEMPOTENT : si la candidature porte déjà un ``employe_cree``, on renvoie ce
    dossier sans en créer un second. Les champs requis de ``DossierEmploye``
    (``company``, ``matricule``, ``nom``, ``prenom``) sont garantis : la société
    est celle de la candidature (jamais lue du corps), ``matricule`` est fourni
    ou dérivé (``CAND-<id>``), ``nom`` / ``prenom`` proviennent de la
    candidature (le ``nom`` complet est éclaté en prénom + nom à défaut de
    précision). Transaction atomique. Entièrement additif.
    """
    from .models import Candidature, DossierEmploye, OuverturePoste

    # Idempotence : ne jamais recréer un dossier déjà lié.
    if candidature.employe_cree_id:
        dossier = candidature.employe_cree
        if candidature.etape != Candidature.Etape.EMBAUCHE:
            candidature.etape = Candidature.Etape.EMBAUCHE
            candidature.save(update_fields=['etape', 'date_modification'])
        return dossier

    company = candidature.company
    ouverture = candidature.ouverture

    # Éclate le nom complet en prénom + nom (les deux requis, non vides).
    parts = (candidature.nom or '').strip().split()
    if len(parts) >= 2:
        prenom = parts[0]
        nom = ' '.join(parts[1:])
    else:
        prenom = parts[0] if parts else 'Candidat'
        nom = parts[0] if parts else 'Candidat'

    if not matricule:
        matricule = f'CAND-{candidature.id}'

    champs = {
        'company': company,
        'matricule': matricule,
        'nom': nom,
        'prenom': prenom,
        'email': candidature.email or '',
        'telephone': candidature.telephone or '',
        'statut': DossierEmploye.Statut.EMBAUCHE,
    }
    if ouverture is not None:
        if ouverture.poste_ref_id:
            champs['poste_ref_id'] = ouverture.poste_ref_id
        if ouverture.departement_id:
            champs['departement_id'] = ouverture.departement_id
        if ouverture.intitule:
            champs['poste'] = ouverture.intitule[:120]
    # Les kwargs explicites priment sur les valeurs dérivées.
    champs.update(dossier_kwargs)

    dossier = DossierEmploye.objects.create(**champs)

    candidature.employe_cree = dossier
    candidature.etape = Candidature.Etape.EMBAUCHE
    candidature.save(
        update_fields=['employe_cree', 'etape', 'date_modification'])

    # Bascule l'ouverture en POURVU si le nombre d'embauchés est atteint.
    if ouverture is not None and \
            ouverture.statut == OuverturePoste.Statut.OUVERT:
        nb_embauches = ouverture.candidatures.filter(
            etape=Candidature.Etape.EMBAUCHE,
            employe_cree__isnull=False).count()
        if nb_embauches >= ouverture.nombre_postes:
            ouverture.statut = OuverturePoste.Statut.POURVU
            ouverture.save(update_fields=['statut', 'date_modification'])

    # XRH4 — instancie automatiquement la checklist d'intégration du modèle
    # applicable (le plus spécifique au poste/département du dossier créé,
    # sinon le modèle par défaut de la société s'il existe). Best-effort :
    # l'absence de tout modèle ne bloque jamais l'embauche.
    instancier_integration(dossier)

    return dossier


def _modele_integration_applicable(dossier):
    """Modèle d'intégration le plus spécifique pour ``dossier`` (XRH4).

    Priorité : (poste_ref ET departement) > poste_ref seul > departement seul
    > modèle par défaut (les deux vides). ``None`` si aucun modèle actif.
    """
    from .models import ModeleIntegration

    base = ModeleIntegration.objects.filter(
        company=dossier.company, actif=True)
    if dossier.poste_ref_id and dossier.departement_id:
        exact = base.filter(
            poste_ref_id=dossier.poste_ref_id,
            departement_id=dossier.departement_id).first()
        if exact:
            return exact
    if dossier.poste_ref_id:
        match = base.filter(
            poste_ref_id=dossier.poste_ref_id, departement__isnull=True
        ).first()
        if match:
            return match
    if dossier.departement_id:
        match = base.filter(
            departement_id=dossier.departement_id, poste_ref__isnull=True
        ).first()
        if match:
            return match
    return base.filter(poste_ref__isnull=True, departement__isnull=True).first()


# XRH5 — item BLOQUANT toujours présent dans une checklist d'intégration
# instanciée : la déclaration d'entrée CNSS/AMO (suivi de conformité). Ajouté
# systématiquement (en fin de liste) si aucune ligne du modèle ne le porte
# déjà (comparaison insensible à la casse sur le libellé).
_LIBELLE_DECLARATION_ENTREE = "Déclaration d'entrée CNSS/AMO"


@transaction.atomic
def instancier_integration(dossier, modele=None):
    """Crée les ``ElementIntegrationEmploye`` du modèle applicable (XRH4).

    Si ``modele`` n'est pas fourni, résout le modèle le plus spécifique via
    ``_modele_integration_applicable`` (poste+département > poste > département
    > défaut). Aucun modèle applicable → crée uniquement l'item bloquant XRH5
    (déclaration d'entrée), sans lever d'erreur : l'onboarding sans checklist
    configurée reste valide. N'instancie PAS deux fois pour le même dossier
    (idempotent : si des lignes existent déjà, les renvoie telles quelles
    sans dupliquer).
    """
    from .models import ElementIntegrationEmploye

    existantes = list(
        ElementIntegrationEmploye.objects.filter(employe=dossier))
    if existantes:
        return existantes

    if modele is None:
        modele = _modele_integration_applicable(dossier)

    lignes = []
    ordre = 0
    if modele is not None:
        for element in modele.elements.all():
            lignes.append(ElementIntegrationEmploye(
                company=dossier.company, employe=dossier,
                libelle=element.libelle, ordre=element.ordre))
            ordre = max(ordre, element.ordre)

    # XRH5 — item bloquant toujours ajouté s'il n'y figure pas déjà.
    deja_present = any(
        ligne.libelle.strip().lower() == _LIBELLE_DECLARATION_ENTREE.lower()
        for ligne in lignes)
    if not deja_present:
        lignes.append(ElementIntegrationEmploye(
            company=dossier.company, employe=dossier,
            libelle=_LIBELLE_DECLARATION_ENTREE, ordre=ordre + 1))

    if not lignes:
        return []
    return ElementIntegrationEmploye.objects.bulk_create(lignes)


def _modele_evaluation_applicable(campagne, employe):
    """ZRH7 — modèle d'évaluation le plus spécifique pour ``employe`` dans
    ``campagne`` : priorité au modèle EXPLICITE de la campagne s'il est ciblé
    (poste/département) ou par défaut, sinon un modèle du département de
    l'employé, sinon le modèle par défaut de la société. ``None`` si aucun.
    """
    if campagne.modele_id:
        return campagne.modele
    from .models import ModeleEvaluation

    base = ModeleEvaluation.objects.filter(
        company=campagne.company, actif=True)
    if employe.poste_ref_id and employe.departement_id:
        exact = base.filter(
            poste_ref_id=employe.poste_ref_id,
            departement_id=employe.departement_id).first()
        if exact:
            return exact
    if employe.poste_ref_id:
        match = base.filter(
            poste_ref_id=employe.poste_ref_id, departement__isnull=True
        ).first()
        if match:
            return match
    if employe.departement_id:
        match = base.filter(
            departement_id=employe.departement_id, poste_ref__isnull=True
        ).first()
        if match:
            return match
    return base.filter(poste_ref__isnull=True, departement__isnull=True).first()


def instancier_reponses_evaluation(campagne, employe):
    """ZRH7 — instancie ``EvaluationEmploye.reponses`` depuis le modèle
    applicable (campagne > département/poste employé > défaut société).

    Renvoie une liste de dicts ``{libelle, type, cible, reponse: ''}`` (une
    par question du modèle), ou ``[]`` si aucun modèle applicable — la
    campagne SANS modèle reste un entretien à synthèse libre, comportement
    historique inchangé.
    """
    modele = _modele_evaluation_applicable(campagne, employe)
    if modele is None:
        return []
    reponses = []
    for question in modele.questions or []:
        reponses.append({
            'libelle': question.get('libelle', ''),
            'type': question.get('type', 'texte'),
            'cible': question.get('cible', 'manager'),
            'reponse': '',
        })
    return reponses


def controler_permis_affectation(company, employe_id, *, le=None):
    """Contrôle le permis d'un conducteur avant affectation véhicule (FG198).

    Renvoie ``True`` si le conducteur (scopé société) détient un permis VALIDE
    à la date ``le`` (par défaut la date de début d'affectation ou aujourd'hui),
    via ``selectors.peut_conduire`` (FG197). Renvoie ``False`` sinon — la vue
    refuse alors l'affectation côté serveur. Lecture seule, sans effet de bord ;
    cadre société (jamais d'accès hors ``company``).
    """
    from . import selectors

    return selectors.peut_conduire(company, employe_id, le=le)


# ── XRH9 — guichet de demandes RH self-service ──────────────────────────────

# Mappe le type stocké sur ``DemandeRH`` vers le type attendu par le renderer
# PAIE34 (``apps.paie.builders.ATTESTATION_TYPES``).
_TYPE_ATTESTATION_PAIE = {
    'attestation_travail': 'travail',
    'attestation_salaire': 'salaire',
    'attestation_domiciliation': 'domiciliation',
}


class DemandeRHError(Exception):
    """Erreur métier lors du traitement d'une ``DemandeRH``."""


def traiter_demande_rh(demande, *, traitant, peut_voir_salaires):
    """Traite une ``DemandeRH`` : génère le PDF et le lie à la demande.

    ``traitant`` est l'utilisateur qui traite (posé côté serveur).
    ``peut_voir_salaires`` (bool, résolu côté vue via ``salaires_voir``) — une
    attestation de SALAIRE ne peut être délivrée par un traitant qui ne porte
    pas cette permission : lève ``DemandeRHError``. Le PDF est produit en
    RÉUTILISANT le renderer paie existant via le thin wrapper
    ``apps.paie.services.generer_attestation_pdf_pour_dossier`` — aucun code
    PDF n'est dupliqué ici. Le PDF généré est stocké comme ``records.
    Attachment`` rattaché à la demande. Idempotent au sens où un second appel
    régénère et remplace simplement le PDF (la demande reste ``traitee``).
    """
    from django.contrib.contenttypes.models import ContentType
    from django.core.files.base import ContentFile

    from apps.paie import services as paie_services
    from apps.records.models import Attachment
    from apps.records.storage import store_attachment

    if demande.type == 'attestation_salaire' and not peut_voir_salaires:
        raise DemandeRHError(
            "Attestation de salaire refusée : permission "
            "'salaires_voir' requise.")

    type_paie = _TYPE_ATTESTATION_PAIE.get(demande.type)
    if type_paie is None:
        raise DemandeRHError(
            f"Type de demande {demande.type!r} non pris en charge pour "
            "une génération automatique.")

    pdf_bytes = paie_services.generer_attestation_pdf_pour_dossier(
        demande.employe, type_paie)

    filename = f'{demande.type}_{demande.employe_id}.pdf'
    upload = ContentFile(pdf_bytes, name=filename)
    upload.size = len(pdf_bytes)
    meta, err = store_attachment(upload)
    if err:
        raise DemandeRHError(err)

    attachment = Attachment.objects.create(
        company=demande.company,
        content_type=ContentType.objects.get_for_model(demande),
        object_id=demande.id,
        file_key=meta['file_key'],
        filename=meta['filename'],
        size=meta['size'],
        mime=meta['mime'],
        uploaded_by=traitant,
    )
    demande.attachment = attachment
    demande.statut = 'traitee'
    demande.traite_par = traitant
    demande.traite_le = timezone.now()
    demande.save(update_fields=[
        'attachment', 'statut', 'traite_par', 'traite_le',
        'date_modification'])
    return demande


def refuser_demande_rh(demande, *, traitant, motif_refus=''):
    """Refuse une ``DemandeRH`` (motif optionnel, traitant posé serveur)."""
    demande.statut = 'refusee'
    demande.motif_refus = motif_refus
    demande.traite_par = traitant
    demande.traite_le = timezone.now()
    demande.save(update_fields=[
        'statut', 'motif_refus', 'traite_par', 'traite_le',
        'date_modification'])
    return demande


# ── XRH10 — kiosque de pointage partagé (PIN/QR, tablette dépôt) ───────────

def emettre_device_kiosque(company, label=''):
    """Émet un nouveau ``DeviceKiosque`` : renvoie (instance, token_en_clair).

    Le token en clair n'est JAMAIS stocké — seul son HASH (``token_hash``)
    l'est. Il n'est renvoyé qu'une fois, à l'émission.
    """
    from .models import DeviceKiosque, generate_device_token, hash_device_token

    raw = generate_device_token()
    device = DeviceKiosque.objects.create(
        company=company, label=label, token_hash=hash_device_token(raw))
    return device, raw


def resoudre_device_kiosque(raw_token):
    """Résout un token de device kiosque en clair → ``DeviceKiosque`` actif.

    Renvoie ``None`` si le token est inconnu, révoqué (``actif=False``), ou
    vide. Comparaison par empreinte HMAC-SHA256 (déterministe, O(1)).
    """
    from .models import DeviceKiosque, hash_device_token

    if not raw_token:
        return None
    token_hash = hash_device_token(raw_token)
    return DeviceKiosque.objects.filter(
        token_hash=token_hash, actif=True).select_related('company').first()


class KiosqueError(Exception):
    """Erreur métier du pointage kiosque (PIN inconnu…)."""


def pointer_via_kiosque(device, pin):
    """Pointe arrivée/départ pour l'employé du PIN (XRH10).

    Bascule automatiquement : si le dernier pointage OUVERT (arrivée sans
    départ) du jour existe, ferme-le (départ) ; sinon ouvre une arrivée.
    Renvoie ``(dossier, pointage, sens)`` avec ``sens`` ∈ {arrivee, depart}.
    Lève ``KiosqueError`` si le PIN est inconnu dans la société du device
    (l'appelant doit répondre 404 neutre — jamais préciser la raison).
    """
    from .models import DossierEmploye, Pointage

    pin = (pin or '').strip()
    if not pin:
        raise KiosqueError('PIN manquant.')
    dossier = DossierEmploye.objects.filter(
        company=device.company, code_pointage=pin).first()
    if dossier is None:
        raise KiosqueError('PIN inconnu.')

    now = timezone.now()
    ouvert = (
        Pointage.objects
        .filter(company=device.company, employe=dossier,
                heure_arrivee__date=now.date(), heure_depart__isnull=True)
        .order_by('-heure_arrivee')
        .first())
    if ouvert is not None:
        ouvert.heure_depart = now
        ouvert.type_pointage = Pointage.TypePointage.COMPLET
        ouvert.save(update_fields=['heure_depart', 'type_pointage'])
        device.derniere_utilisation = now
        device.save(update_fields=['derniere_utilisation'])
        return dossier, ouvert, 'depart'

    pointage = Pointage.objects.create(
        company=device.company, employe=dossier,
        type_pointage=Pointage.TypePointage.ARRIVEE, heure_arrivee=now)
    device.derniere_utilisation = now
    device.save(update_fields=['derniere_utilisation'])
    return dossier, pointage, 'arrivee'


# ── XRH12 — géofence de pointage chantier (optionnelle) ────────────────────

def _haversine_metres(lat1, lng1, lat2, lng2):
    """Distance approximative (mètres) entre deux points GPS (Haversine).

    Implémentation locale volontaire (pas d'import de
    ``apps.installations.selectors._haversine_km``, privée et non exportée) —
    même formule que le calcul F6 réutilisé ailleurs dans l'ERP.
    """
    from math import asin, cos, radians, sin, sqrt

    lat1, lng1, lat2, lng2 = (
        radians(float(v)) for v in (lat1, lng1, lat2, lng2))
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return 2 * 6371000.0 * asin(sqrt(a))


def controler_geofence_presence(presence, gps_lat, gps_lng):
    """Contrôle optionnel du géofence à l'émargement d'une présence chantier.

    Résout ``geofence_metres`` (``ReglageRH``, désactivé/``None`` par défaut)
    et les coordonnées de référence du chantier via le selector
    ``apps.installations.selectors.installation_gps_map`` (cross-app en
    LECTURE SEULE, jamais d'import de ``installations.models``). Hors rayon →
    ``presence.hors_zone=True`` + un ``IncidentPresence`` (FG171) créé — JAMAIS
    bloquant (le pointage passe toujours). Sans géofence configuré, sans GPS
    fourni, ou sans coordonnée de référence du chantier : aucun contrôle
    (silencieux). Stocke aussi les coordonnées reçues sur la présence.
    """
    from apps.installations import selectors as installations_selectors

    from .models import IncidentPresence, ReglageRH

    if gps_lat is not None:
        presence.gps_lat = gps_lat
    if gps_lng is not None:
        presence.gps_lng = gps_lng

    reglage = ReglageRH.objects.filter(company=presence.company).first()
    geofence_metres = reglage.geofence_metres if reglage else None
    if not geofence_metres or gps_lat is None or gps_lng is None:
        presence.hors_zone = False
        return presence

    gps_map = installations_selectors.installation_gps_map(
        [presence.installation_id])
    ref_lat, ref_lng = gps_map.get(presence.installation_id, (None, None))
    if ref_lat is None or ref_lng is None:
        presence.hors_zone = False
        return presence

    distance_m = _haversine_metres(gps_lat, gps_lng, ref_lat, ref_lng)
    presence.hors_zone = distance_m > geofence_metres
    if presence.hors_zone:
        IncidentPresence.objects.create(
            company=presence.company,
            employe=presence.employe,
            type_incident=IncidentPresence.TypeIncident.RETARD,
            date=presence.date,
            note=(
                f'Émargement hors zone (géofence {geofence_metres} m, '
                f'≈{int(distance_m)} m du chantier).'),
        )
    return presence


# ── ZRH5 — clôture automatique des pointages oubliés ───────────────────────

def clore_pointages_ouverts(company, *, apply=False):
    """ZRH5 — clôture les pointages OUVERTS (arrivée sans départ) au-delà du
    seuil société (« Automatic check-out » Odoo).

    Seuil désactivé (``ReglageRH.pointage_auto_depart_apres_h`` NULL) → no-op
    (liste vide). Un pointage ouvert depuis > seuil est clôturé UNE fois :
    ``heure_depart = heure_arrivee + seuil``, ``depart_auto = True`` (jamais
    écrasé si déjà fermé — la requête ne cible que
    ``heure_depart__isnull=True``), et un ``IncidentPresence`` « départ
    automatique » est créé pour traçabilité. ``apply=False`` (dry-run) ne
    modifie rien. Renvoie la liste des pointages (dry-run) ou clôturés
    (apply), pour rapport.
    """
    from datetime import timedelta

    from .models import IncidentPresence, Pointage, ReglageRH

    reglage = ReglageRH.objects.filter(company=company).first()
    seuil_h = reglage.pointage_auto_depart_apres_h if reglage else None
    if not seuil_h:
        return []

    seuil = timedelta(hours=seuil_h)
    limite = timezone.now() - seuil
    ouverts = Pointage.objects.filter(
        company=company, heure_depart__isnull=True,
        heure_arrivee__isnull=False, heure_arrivee__lte=limite,
    ).select_related('employe')

    traites = []
    for pointage in ouverts:
        depart_calcule = pointage.heure_arrivee + seuil
        traites.append(pointage)
        if apply:
            pointage.heure_depart = depart_calcule
            pointage.depart_auto = True
            pointage.save(update_fields=[
                'heure_depart', 'depart_auto', 'date_modification'])
            IncidentPresence.objects.create(
                company=company, employe=pointage.employe,
                type_incident=IncidentPresence.TypeIncident.DEPART_ANTICIPE,
                date=pointage.heure_arrivee.date(),
                motif='Départ automatique (pointage oublié)',
                note=f'Clôturé après {seuil_h} h sans départ pointé.')
    return traites


# ── XRH13 — import de pointages externes (pointeuse biométrique, CSV) ──────

def importer_pointages_csv(company, rows):
    """Importe des lignes CSV (device_user_id, horodatage, sens) → Pointage.

    ``rows`` est une liste de dicts (issue de ``csv.DictReader``) avec les
    clés ``device_user_id``, ``horodatage`` (ISO 8601 ou ``YYYY-MM-DD
    HH:MM:SS``) et ``sens`` (``in``/``out``). Mappe via ``EmployeDeviceMap``
    (société scopée) → crée les ``Pointage`` correspondants. IDEMPOTENT par
    ``(employe, horodatage)`` : une ligne déjà importée n'est jamais dupliquée.
    Une ligne SANS mapping connu est RAPPORTÉE en erreur (jamais silencieusement
    ignorée). Renvoie un résumé ``{crees, doublons, erreurs}``.
    """
    from datetime import datetime

    from django.db.models import Q
    from django.utils import timezone as dj_timezone

    from .models import EmployeDeviceMap, Pointage

    device_ids = {
        (row.get('device_user_id') or '').strip() for row in rows}
    device_ids.discard('')
    mapping = {
        m.device_user_id: m.employe
        for m in EmployeDeviceMap.objects.filter(
            company=company, device_user_id__in=device_ids)
        .select_related('employe')
    }

    crees, doublons, erreurs = [], [], []
    for i, row in enumerate(rows, start=1):
        device_user_id = (row.get('device_user_id') or '').strip()
        horodatage_raw = (row.get('horodatage') or '').strip()
        sens = (row.get('sens') or '').strip().lower()

        employe = mapping.get(device_user_id)
        if employe is None:
            erreurs.append({
                'ligne': i, 'device_user_id': device_user_id,
                'motif': 'Aucun mappage employé pour cet ID pointeuse.'})
            continue

        horodatage = None
        for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S'):
            try:
                horodatage = datetime.strptime(horodatage_raw, fmt)
                break
            except ValueError:
                continue
        if horodatage is None:
            erreurs.append({
                'ligne': i, 'device_user_id': device_user_id,
                'motif': f'Horodatage invalide : {horodatage_raw!r}.'})
            continue
        if dj_timezone.is_naive(horodatage):
            horodatage = dj_timezone.make_aware(horodatage)

        type_pointage = (
            Pointage.TypePointage.DEPART if sens == 'out'
            else Pointage.TypePointage.ARRIVEE)
        # Idempotent par (employe, horodatage) — cherche un pointage existant
        # sur la même seconde, quel que soit le champ arrivée/départ touché.
        deja = Pointage.objects.filter(
            company=company, employe=employe
        ).filter(
            Q(heure_arrivee=horodatage) | Q(heure_depart=horodatage)
        ).exists()
        if deja:
            doublons.append({'ligne': i, 'device_user_id': device_user_id})
            continue

        if type_pointage == Pointage.TypePointage.DEPART:
            Pointage.objects.create(
                company=company, employe=employe,
                type_pointage=Pointage.TypePointage.DEPART,
                heure_depart=horodatage)
        else:
            Pointage.objects.create(
                company=company, employe=employe,
                type_pointage=Pointage.TypePointage.ARRIVEE,
                heure_arrivee=horodatage)
        crees.append({'ligne': i, 'device_user_id': device_user_id})

    return {'crees': crees, 'doublons': doublons, 'erreurs': erreurs}


# ── XRH14 — fermetures collectives / congés imposés ─────────────────────────

def _motif_fermeture(fermeture):
    return f'[Fermeture collective #{fermeture.id}] {fermeture.libelle}'


@transaction.atomic
def appliquer_fermeture(fermeture):
    """Applique une ``PeriodeFermeture`` : génère une ``DemandeConge`` VALIDÉE
    par employé concerné (IDEMPOTENT — ré-appliquer ne duplique pas).

    ``departements`` (M2M) restreint aux employés de ces départements ; vide =
    toute la société. Un employé qui a DÉJÀ une demande générée par CETTE
    fermeture (marquée via ``motif``) est sauté. Renvoie la liste des
    ``DemandeConge`` créées (nouvelles seulement).
    """
    from .models import DemandeConge, DossierEmploye

    employes_qs = DossierEmploye.objects.filter(
        company=fermeture.company, statut=DossierEmploye.Statut.ACTIF)
    departements = list(fermeture.departements.all())
    if departements:
        employes_qs = employes_qs.filter(departement__in=departements)

    motif = _motif_fermeture(fermeture)
    deja_generes = set(
        DemandeConge.objects.filter(
            company=fermeture.company, motif=motif)
        .values_list('employe_id', flat=True))

    creees = []
    for employe in employes_qs:
        if employe.id in deja_generes:
            continue
        jours = calculer_jours_demande(
            fermeture.type_absence, fermeture.date_debut, fermeture.date_fin)
        demande = DemandeConge.objects.create(
            company=fermeture.company,
            employe=employe,
            type_absence=fermeture.type_absence,
            date_debut=fermeture.date_debut,
            date_fin=fermeture.date_fin,
            jours=jours,
            motif=motif,
        )
        valider_demande(demande)
        creees.append(demande)

    fermeture.appliquee = True
    fermeture.appliquee_le = timezone.now()
    fermeture.save(update_fields=['appliquee', 'appliquee_le'])
    return creees


# ── XRH18 — chatter candidature + détection de doublons ────────────────────

def _normalize_phone(value):
    """Téléphone normalisé pour comparaison (chiffres, indicatif MA réduit) —
    équivalent local (pas d'import cross-app) du normaliseur CRM."""
    import re

    digits = re.sub(r'\D', '', str(value or ''))
    if not digits:
        return ''
    if digits.startswith('00'):
        digits = digits[2:]
    if digits.startswith('212'):
        digits = digits[3:]
    return digits.lstrip('0')


def _normalize_email(value):
    return str(value or '').strip().lower()


def candidatures_doublons(company, *, telephone=None, email=None,
                          exclude_pk=None):
    """XRH18 — candidatures de la société partageant un téléphone OU un
    email normalisé (pattern CRM ``check-duplicates``). Saisie libre
    acceptée. ``exclude_pk`` retire la candidature en cours d'édition.
    """
    from .models import Candidature

    phone = _normalize_phone(telephone)
    mail = _normalize_email(email)
    if not phone and not mail:
        return []
    qs = Candidature.objects.filter(company=company)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    doublons = []
    for other in qs:
        if phone and _normalize_phone(other.telephone) == phone:
            doublons.append(other)
        elif mail and _normalize_email(other.email) == mail:
            doublons.append(other)
    return doublons


@transaction.atomic
def fusionner_candidatures(cible, source, *, auteur=None):
    """XRH18 — fusionne ``source`` DANS ``cible`` : la cible absorbe le CV
    (si elle n'en a pas déjà un), la note (concaténée) et les activités
    (déplacées) ; la source est marquée REJETÉE-doublon. Ne perd jamais
    l'historique. Idempotent au sens où ``source`` déjà rejetée-doublon ne
    re-déplace rien de plus.
    """
    from .models import Candidature, CandidatureActivity

    if cible.pk == source.pk:
        raise ValueError('Impossible de fusionner une candidature avec elle-même.')

    if not cible.cv_fichier and source.cv_fichier:
        cible.cv_fichier = source.cv_fichier
    if source.note:
        cible.note = (
            f'{cible.note}\n[Fusionné depuis #{source.id}] {source.note}'
            if cible.note else source.note)
    cible.save(update_fields=['cv_fichier', 'note', 'date_modification'])

    CandidatureActivity.objects.filter(candidature=source).update(
        candidature=cible)

    source.etape = Candidature.Etape.REJETE
    source.note = (
        f'{source.note}\n[Fusionnée dans #{cible.id}]'
        if source.note else f'[Fusionnée dans #{cible.id}]')
    source.save(update_fields=['etape', 'note', 'date_modification'])

    CandidatureActivity.objects.create(
        company=cible.company, candidature=cible, type='note', auteur=auteur,
        message=f'Fusion : candidature #{source.id} absorbée.')
    return cible


# ── XRH19 — emails candidats automatiques par étape ─────────────────────────

def envoyer_email_transition(candidature, *, date_entretien=None):
    """XRH19 — envoie (ou console-logue) l'email du gabarit ACTIF pour la
    nouvelle étape de la candidature, si elle en a un ET que
    ``candidature.emails_auto`` n'a pas été désactivé. Substitue les
    placeholders sûrs ``{nom}``/``{poste}``/``{date_entretien}``. Journalise
    dans le chatter (XRH18). JAMAIS d'exception si la clé/infra email
    manque — best-effort, silencieux (comme les autres envois de l'ERP).
    Renvoie ``True`` si un email a été envoyé (ou console-loggué), ``False``
    sinon (pas de gabarit / opt-out / email candidat manquant).
    """
    from .models import CandidatureActivity, GabaritEmailRecrutement

    if not candidature.emails_auto or not candidature.email:
        return False

    gabarit = (
        GabaritEmailRecrutement.objects
        .filter(company=candidature.company, etape=candidature.etape,
                actif=True)
        .first())
    if gabarit is None:
        return False

    poste = (
        candidature.ouverture.intitule if candidature.ouverture_id else '')
    placeholders = {
        'nom': candidature.nom,
        'poste': poste,
        'date_entretien': str(date_entretien) if date_entretien else '',
    }
    objet = gabarit.objet.format(**placeholders)
    corps = gabarit.corps.format(**placeholders)

    try:
        from django.conf import settings
        from django.core.mail import send_mail

        from_email = getattr(
            settings, 'DEFAULT_FROM_EMAIL', 'noreply@erp.local')
        send_mail(
            objet, corps, from_email, [candidature.email],
            fail_silently=True)
    except Exception:  # noqa: BLE001 — best-effort, jamais d'exception.
        return False

    CandidatureActivity.objects.create(
        company=candidature.company, candidature=candidature,
        type=CandidatureActivity.Kind.NOTE,
        message=f'Email automatique envoyé ({gabarit.get_etape_display()}) : '
                f'{objet}')
    return True


# ── XRH20 — promesse d'embauche / lettre d'offre PDF + e-sign interne ──────

class PromesseSignatureError(Exception):
    """Erreur métier lors de la signature d'une promesse d'embauche."""


@transaction.atomic
def signer_promesse_embauche(promesse, *, signataire_nom, ip_adresse='',
                             user_agent=''):
    """XRH20 — signe une ``PromesseEmbauche`` par NOM TAPÉ (loi 53-05).

    Lève ``PromesseSignatureError`` si le jeton a expiré ou si la promesse
    est DÉJÀ signée (immuable — jamais de re-signature). Fige la signature
    (nom, IP, user-agent, horodatage serveur), passe ``statut=signee`` et
    journalise l'acceptation dans le chatter de la candidature (XRH18).
    """
    from .models import CandidatureActivity

    if promesse.statut == promesse.Statut.SIGNEE:
        raise PromesseSignatureError('Cette promesse est déjà signée.')
    if not promesse.is_valid:
        raise PromesseSignatureError('Ce lien de signature a expiré.')

    nom = (signataire_nom or '').strip()
    if not nom:
        raise PromesseSignatureError('Le nom du signataire est requis.')

    promesse.signataire_nom = nom
    promesse.date_signature = timezone.now()
    promesse.ip_adresse = (ip_adresse or '')[:45]
    promesse.user_agent = user_agent or ''
    promesse.statut = promesse.Statut.SIGNEE
    promesse.save(update_fields=[
        'signataire_nom', 'date_signature', 'ip_adresse', 'user_agent',
        'statut'])

    CandidatureActivity.objects.create(
        company=promesse.company, candidature=promesse.candidature,
        type=CandidatureActivity.Kind.NOTE,
        message=(
            f'Offre acceptée — signée électroniquement par {nom} '
            f'le {promesse.date_signature:%d/%m/%Y %H:%M}.'))
    return promesse


# ── XRH21 — vivier de candidats (talent pool) ───────────────────────────────

@transaction.atomic
def rattacher_depuis_vivier(candidature_vivier, ouverture):
    """XRH21 — clone une candidature du vivier vers une NOUVELLE
    ``OuverturePoste`` (même société). Le CV et l'historique (chatter) sont
    conservés ; la nouvelle candidature démarre à l'étape ``reçu`` avec un
    lien ``vivier_origine`` vers l'originale. Renvoie la nouvelle candidature.
    """
    from .models import Candidature, CandidatureActivity

    if ouverture.company_id != candidature_vivier.company_id:
        raise ValueError('Ouverture et candidature doivent être de la même société.')

    nouvelle = Candidature.objects.create(
        company=candidature_vivier.company,
        ouverture=ouverture,
        nom=candidature_vivier.nom,
        email=candidature_vivier.email,
        telephone=candidature_vivier.telephone,
        cv_fichier=candidature_vivier.cv_fichier,
        source=candidature_vivier.source,
        etape=Candidature.Etape.RECU,
        vivier_origine=candidature_vivier,
    )
    CandidatureActivity.objects.create(
        company=nouvelle.company, candidature=nouvelle,
        type=CandidatureActivity.Kind.NOTE,
        message=(
            f'Rattaché depuis le vivier (candidature originale '
            f'#{candidature_vivier.id}).'))
    return nouvelle


# ── XRH23 — parsing de CV par OCR (key-gated) ───────────────────────────────

class CvParsingUnavailable(Exception):
    """Levée quand aucun fournisseur OCR n'est configuré (503 douce)."""


_CV_MIME_TYPES = {
    'pdf': 'application/pdf',
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
}


def parser_cv(candidature):
    """XRH23 — OCR le ``cv_fichier`` de la candidature et PRÉ-REMPLIT
    uniquement les champs VIDES (``nom``/``email``/``telephone``), sans
    jamais écraser une valeur déjà saisie. Suggère aussi des ``tags_vivier``
    (compétences détectées) — toujours en complément, jamais en remplacement
    de tags déjà présents.

    Lève :class:`CvParsingUnavailable` si aucun ``cv_fichier`` n'est attaché
    ou si aucun fournisseur OCR n'est configuré (``ZHIPU_API_KEY`` absent) —
    l'appelant (vue) traduit en 503 douce, sans exception non gérée.

    Renvoie un dict ``{champs_remplis: [...], tags_suggeres: [...],
    donnees_brutes: {...}}``. Entièrement additif, transaction atomique sur
    la sauvegarde des champs remplis.
    """
    from core.ai.services import extract_document

    if not candidature.cv_fichier:
        raise CvParsingUnavailable('Aucun CV attaché à cette candidature.')

    nom_fichier = candidature.cv_fichier.name or ''
    ext = nom_fichier.rsplit('.', 1)[-1].lower() if '.' in nom_fichier else ''
    mime_type = _CV_MIME_TYPES.get(ext, 'application/octet-stream')

    try:
        candidature.cv_fichier.open('rb')
        content = candidature.cv_fichier.read()
    finally:
        candidature.cv_fichier.close()

    result = extract_document(
        content=content, mime_type=mime_type, schema='cv')
    if not result.configured:
        raise CvParsingUnavailable(
            "Aucun fournisseur OCR n'est configuré (clé absente) — "
            'saisie manuelle requise.')

    data = result.data or {}
    champs_remplis = []
    update_fields = []

    with transaction.atomic():
        if not candidature.nom and data.get('nom'):
            prenom = str(data.get('prenom') or '').strip()
            nom = str(data.get('nom') or '').strip()
            candidature.nom = f'{prenom} {nom}'.strip() if prenom else nom
            champs_remplis.append('nom')
            update_fields.append('nom')
        if not candidature.email and data.get('email'):
            candidature.email = str(data['email']).strip()
            champs_remplis.append('email')
            update_fields.append('email')
        if not candidature.telephone and data.get('telephone'):
            candidature.telephone = str(data['telephone']).strip()
            champs_remplis.append('telephone')
            update_fields.append('telephone')

        competences = data.get('competences') or []
        if isinstance(competences, str):
            competences = [c.strip() for c in competences.split(',')
                           if c.strip()]
        tags_suggeres = [str(c).strip() for c in competences if str(c).strip()]

        if update_fields:
            update_fields.append('date_modification')
            candidature.save(update_fields=update_fields)

    return {
        'champs_remplis': champs_remplis,
        'tags_suggeres': tags_suggeres,
        'donnees_brutes': data,
    }


# ── XRH24 — rétention & anonymisation des candidats (loi 09-08) ────────────

_ANONYMISE_NOM = 'Candidat anonymisé'


def candidatures_purgeables(company, *, retention_mois=None, now=None):
    """XRH24 — candidatures REJETÉES éligibles à l'anonymisation.

    Une candidature est éligible si : ``etape == rejete``, ``vivier`` est
    ``False`` (jamais le vivier actif — même rejetée, un candidat au vivier
    est délibérément conservé) et sa dernière activité (``date_modification``,
    date du passage à ``rejete`` en pratique) dépasse ``retention_mois`` (le
    réglage société ``ReglageRH.retention_candidatures_mois``, défaut 24, si
    non fourni). Un candidat déjà anonymisé (``nom`` déjà marqué) est exclu —
    idempotence. Jamais les embauchés (``etape == embauche`` exclue de fait
    par le filtre ``rejete``).
    """
    from .models import Candidature, ReglageRH, _ajouter_mois

    now = now or timezone.now()
    if retention_mois is None:
        reglage = ReglageRH.objects.filter(company=company).first()
        retention_mois = (
            reglage.retention_candidatures_mois if reglage else 24)

    # Recule de ``retention_mois`` SANS dépendance externe (pas de dateutil),
    # en réutilisant l'arithmétique de dates déjà éprouvée des EPI (FG179).
    seuil_date = _ajouter_mois(now.date(), -int(retention_mois))
    seuil = timezone.make_aware(
        timezone.datetime.combine(seuil_date, timezone.datetime.min.time()))
    return Candidature.objects.filter(
        company=company,
        etape=Candidature.Etape.REJETE,
        vivier=False,
        date_modification__lt=seuil,
    ).exclude(nom=_ANONYMISE_NOM)


@transaction.atomic
def anonymiser_candidature(candidature):
    """XRH24 — anonymise UNE candidature rejetée hors-vivier (irréversible) :
    ``nom`` → « Candidat anonymisé », ``email``/``telephone`` vidés, le
    ``cv_fichier`` est supprimé du storage (et le champ vidé), ``note``
    purgée. La LIGNE survit (jamais de suppression) — les comptages/stats
    XRH22 restent corrects. ``tags_vivier`` est également vidé (donnée
    personnelle librement saisie)."""
    if candidature.cv_fichier:
        candidature.cv_fichier.delete(save=False)

    candidature.nom = _ANONYMISE_NOM
    candidature.email = ''
    candidature.telephone = ''
    candidature.note = ''
    candidature.tags_vivier = ''
    candidature.cv_fichier = None
    candidature.save(update_fields=[
        'nom', 'email', 'telephone', 'note', 'tags_vivier', 'cv_fichier',
        'date_modification'])
    return candidature


def purger_candidatures(company, *, retention_mois=None, now=None,
                        apply=False):
    """XRH24 — purge (DRY-RUN par défaut) les candidatures rejetées hors
    vivier au-delà de la rétention société.

    ``apply=False`` (défaut) : ne modifie RIEN, renvoie seulement le compte et
    les ids éligibles. ``apply=True`` : anonymise réellement chaque
    candidature éligible (:func:`anonymiser_candidature`). Jamais les
    embauchés ni le vivier actif (filtrés en amont par
    :func:`candidatures_purgeables`). Renvoie
    ``{'company_id', 'dry_run', 'eligibles', 'anonymisees', 'ids'}``.
    """
    candidats = list(candidatures_purgeables(
        company, retention_mois=retention_mois, now=now))
    ids = [c.id for c in candidats]
    anonymisees = 0
    if apply:
        for candidature in candidats:
            anonymiser_candidature(candidature)
            anonymisees += 1

    return {
        'company_id': company.id,
        'dry_run': not apply,
        'eligibles': len(candidats),
        'anonymisees': anonymisees,
        'ids': ids,
    }


# ── XRH26 — auto-évaluation + issues d'évaluation structurées ──────────────

def _porteurs_salaires_voir(company):
    """Utilisateurs actifs de la société portant la permission
    ``salaires_voir`` (JSONField liste de codes sur ``roles.Role``)."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.filter(
        company=company, is_active=True,
        role__permissions__contains=['salaires_voir'])


@transaction.atomic
def traiter_issue_evaluation(evaluation):
    """XRH26 — effets de bord de l'``issue`` posée À LA VALIDATION d'un
    entretien d'évaluation :

    * ``issue == 'formation'`` — crée un ``BesoinFormation`` lié à
      l'employé évalué (thème = ``issue_details`` si renseigné, sinon un
      libellé générique), priorité moyenne, statut ``identifie``.
    * ``issue == 'augmentation_proposee'`` — notifie (best-effort, via
      ``apps.notifications.services.notify``) chaque porteur actif de
      ``salaires_voir`` — SANS JAMAIS inclure de montant dans le corps de la
      notification (juste le nom de l'employé concerné).

    Idempotence pragmatique : appelée uniquement au moment de la validation
    (vue), jamais automatiquement en boucle. Aucune exception ne remonte côté
    notification (best-effort) ; la création du besoin de formation reste,
    elle, dans la transaction (erreur = rollback propre).
    """
    from .models import BesoinFormation, EvaluationEmploye

    if evaluation.issue == EvaluationEmploye.Issue.FORMATION:
        theme = evaluation.issue_details.strip() or (
            f"Formation suite à l'évaluation {evaluation.campagne.intitule}")
        BesoinFormation.objects.create(
            company=evaluation.company,
            employe=evaluation.employe,
            theme=theme[:200],
            priorite=BesoinFormation.Priorite.MOYENNE,
            statut=BesoinFormation.Statut.IDENTIFIE,
        )

    if evaluation.issue == EvaluationEmploye.Issue.AUGMENTATION_PROPOSEE:
        try:
            from apps.notifications.models import EventType
            from apps.notifications.services import notify_many

            employe_nom = f'{evaluation.employe.nom} {evaluation.employe.prenom}'
            notify_many(
                _porteurs_salaires_voir(evaluation.company),
                EventType.APPROVAL_REQUESTED,
                title='Augmentation proposée',
                body=(
                    f'Une augmentation a été proposée pour {employe_nom} '
                    "suite à son entretien d'évaluation."),
            )
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant.
            pass


# ── XRH32 — baromètre interne eNPS anonyme (pulse) ──────────────────────────

class DejaVoteError(Exception):
    """Levée quand l'utilisateur a déjà participé à cette campagne pulse."""


@transaction.atomic
def repondre_pulse(campagne, user, *, score, commentaire=''):
    """XRH32 — enregistre une réponse ANONYME à une campagne pulse.

    Deux écritures dans LA MÊME transaction, JAMAIS reliées entre elles :
      1. ``ParticipationPulse(campagne, user)`` — la contrainte d'unicité EST
         le garde-fou anti-double-vote ; si elle existe déjà,
         :class:`DejaVoteError` est levée AVANT toute écriture de réponse
         (aucune deuxième ``ReponsePulse`` n'est créée pour ce vote refusé).
      2. ``ReponsePulse(campagne, score, commentaire)`` — SANS AUCUNE
         référence à ``user`` : structurellement impossible de relier cette
         ligne au votant.

    Renvoie la ``ReponsePulse`` créée.
    """
    from .models import (
        ParticipationPulse, ReponsePulse, hash_participation_token,
    )

    if ParticipationPulse.objects.filter(
            campagne=campagne, user=user).exists():
        raise DejaVoteError('Vous avez déjà répondu à cette campagne.')

    ParticipationPulse.objects.create(
        company=campagne.company, campagne=campagne, user=user,
        token_hash=hash_participation_token(user.id, campagne.id))

    return ReponsePulse.objects.create(
        company=campagne.company, campagne=campagne,
        score=score, commentaire=commentaire or '')


# ── YHIRE2 — orchestration de sortie (employe_sorti) ───────────────────────

@transaction.atomic
def sortir_employe(dossier, *, date_sortie, motif, notes_avances=''):
    """YHIRE2 — orchestre la sortie d'un ``DossierEmploye`` : jusqu'ici,
    passer ``statut`` à SORTI était un simple PATCH sans aucun effet — la
    checklist de restitution restait à saisir à la main, le compte
    utilisateur lié restait ACTIF et le profil de paie n'était jamais coupé
    (un sorti pouvait encore recevoir un bulletin normal).

    Dans UNE transaction :

    1. pose ``statut=SORTI`` + ``date_sortie`` + ``motif_sortie`` ;
    2. GÉNÈRE les ``ElementSortie`` (FG161) depuis les affectations OUVERTES
       réelles :
       - une ligne EPI par ``DotationEpi`` de l'employé non encore restituée
         (``restituee=False``) ;
       - une ligne VÉHICULE par ``AffectationVehicule`` ACTIVE, close à
         ``date_sortie`` (``statut=TERMINEE``, ``date_fin=date_sortie``) ;
       - une note (ligne AUTRE) listant les ``AvanceSalaire`` non soldées
         (statut demandée/approuvée) si elles existent ;
    3. désactive le compte utilisateur lié (``user.is_active=False``,
       horodaté sur le dossier via le chatter XRH6) ;
    4. émet ``employe_sorti`` sur le bus d'événements (``core.events``) —
       ``paie`` s'y abonne (``apps/paie/receivers.py``) pour couper
       ``ProfilPaie.actif``, SANS que ``rh`` importe jamais ``apps.paie``.

    Idempotent : ré-appeler sur un dossier DÉJÀ ``SORTI`` ne RE-génère pas la
    checklist ni ne ré-émet l'événement (lève ``ValueError``) — évite un
    doublon d'``ElementSortie``/de désactivation si l'action est rejouée.

    ``dossier``/``motif`` sont déjà scopés/validés par l'appelant (vue) ;
    aucune lecture de société depuis le corps de requête.
    """
    from .models import (
        AffectationVehicule, AvanceSalaire, DossierEmploye, DotationEpi,
        ElementSortie,
    )

    if dossier.statut == DossierEmploye.Statut.SORTI:
        raise ValueError('Ce dossier est déjà marqué sorti.')

    dossier.statut = DossierEmploye.Statut.SORTI
    dossier.date_sortie = date_sortie
    dossier.motif_sortie = motif
    dossier.save(update_fields=['statut', 'date_sortie', 'motif_sortie'])

    # (b) EPI non restitués → une ligne de checklist par dotation ouverte.
    dotations_ouvertes = DotationEpi.objects.filter(
        company=dossier.company, employe=dossier, restituee=False)
    for dotation in dotations_ouvertes:
        ElementSortie.objects.create(
            company=dossier.company,
            employe=dossier,
            libelle=f'EPI — {dotation.epi.designation}'[:160],
            type_element=ElementSortie.TypeElement.EPI,
        )

    # Véhicules affectés ACTIFS → clôturés à la date de sortie + checklist.
    affectations_ouvertes = AffectationVehicule.objects.filter(
        company=dossier.company, employe=dossier,
        statut=AffectationVehicule.Statut.ACTIVE)
    for affectation in affectations_ouvertes:
        ElementSortie.objects.create(
            company=dossier.company,
            employe=dossier,
            libelle=f'Véhicule #{affectation.vehicule_id}'[:160],
            type_element=ElementSortie.TypeElement.VEHICULE,
        )
        affectation.statut = AffectationVehicule.Statut.TERMINEE
        affectation.date_fin = date_sortie
        affectation.save(update_fields=['statut', 'date_fin', 'date_modification'])

    # YHIRE11 — Affectations flotte OUVERTES du sortant (conducteur flotte
    # lié à ce dossier, ``flotte.Conducteur.employe_id``) → note informative
    # listant les véhicules encore ouverts. Distinct de l'``AffectationVehicule``
    # RH ci-dessus (qui référence ``flotte.Vehicule`` par un string-FK
    # indépendant) : un conducteur flotte peut avoir des affectations propres
    # que le module RH ne connaissait pas jusqu'ici. Lecture cross-app UNIQUEMENT
    # via le sélecteur flotte (jamais un import de ``apps.flotte.models``).
    try:
        from apps.flotte.selectors import affectations_ouvertes_pour_employe
        affectations_flotte = affectations_ouvertes_pour_employe(
            dossier.company, dossier.pk)
    except Exception:
        affectations_flotte = []
    if affectations_flotte:
        vehicules_labels = ', '.join(
            a['vehicule_label'] for a in affectations_flotte)
        ElementSortie.objects.create(
            company=dossier.company,
            employe=dossier,
            libelle='Véhicules flotte encore ouverts'[:160],
            type_element=ElementSortie.TypeElement.VEHICULE,
            note=(
                f'{len(affectations_flotte)} affectation(s) flotte '
                f'ouverte(s) : {vehicules_labels}'[:255]),
        )

    # Avances non soldées → note informative (pas de mouvement financier ici,
    # le solde reste porté par le module concerné — RH ou paie).
    avances_ouvertes = AvanceSalaire.objects.filter(
        company=dossier.company, employe=dossier,
        statut__in=[
            AvanceSalaire.Statut.DEMANDEE, AvanceSalaire.Statut.APPROUVEE])
    if avances_ouvertes.exists():
        total = sum((a.montant or 0) for a in avances_ouvertes)
        note = (
            f'{avances_ouvertes.count()} avance(s) non soldée(s) '
            f'(total {total}).')
        if notes_avances:
            note = f'{note} {notes_avances}'.strip()
        ElementSortie.objects.create(
            company=dossier.company,
            employe=dossier,
            libelle='Avances sur salaire non soldées'[:160],
            type_element=ElementSortie.TypeElement.AUTRE,
            note=note[:255],
        )

    # (c) Compte utilisateur lié désactivé — journalisé.
    if dossier.user_id and dossier.user.is_active:
        dossier.user.is_active = False
        dossier.user.save(update_fields=['is_active'])

    # (d) Bus d'événements — paie s'abonne dans son propre apps.py ready(),
    # rh n'importe jamais apps.paie.
    from core.events import employe_sorti
    employe_sorti.send(
        sender=DossierEmploye, dossier=dossier, user=dossier.user,
        motif=motif)

    return dossier


# ── YHIRE7 — propagation des effets des sanctions disciplinaires ──────────

# Code stable du TypeAbsence de mise à pied (seedé par ``seed_types_absence``,
# NON rémunéré, NE déduit PAS le solde de congés — compteur distinct d'une
# sanction). Un motif reprenant le n° de sanction sert de clé d'idempotence.
_CODE_TYPE_ABSENCE_MISE_A_PIED = 'MAP'


def _motif_absence_mise_a_pied(sanction):
    """Clé stable (dans ``motif``) reliant une ``DemandeConge`` générée à SA
    sanction d'origine — sert de garde d'idempotence (une sanction ne génère
    jamais deux absences)."""
    return f'Mise à pied — Sanction #{sanction.pk}'


@transaction.atomic
def propager_effets_sanction_notification(sanction):
    """YHIRE7(a) — à la NOTIFICATION d'une sanction (statut NOTIFIEE), propage
    son effet métier :

    * ``MISE_A_PIED`` avec ``duree_jours`` > 0 — crée (idempotent : une seule
      fois par sanction, clé = motif stable) une ``DemandeConge`` déjà
      VALIDÉE du type ``TypeAbsence`` seedé « Mise à pied » (non rémunéré, ne
      déduit pas le solde de congés), couvrant
      ``date_notification`` → ``date_notification + duree_jours - 1`` (ou
      ``date_faits`` si la notification est absente). Le bulletin de paie
      exclut cette période via l'import RH→paie (YHIRE1, absence non
      rémunérée).
    * tout autre type de sanction — aucun effet (no-op silencieux).

    Ne lève JAMAIS d'exception si le type d'absence n'est pas seedé pour la
    société (défensif — journalise et ne bloque pas la création/notification
    de la sanction).
    """
    from datetime import timedelta

    from .models import DemandeConge, Sanction, TypeAbsence

    if sanction.type_sanction != Sanction.TypeSanction.MISE_A_PIED:
        return None
    if not sanction.duree_jours:
        return None

    motif = _motif_absence_mise_a_pied(sanction)
    if DemandeConge.objects.filter(
            company=sanction.company, employe=sanction.employe,
            motif=motif).exists():
        return None  # déjà propagé (idempotence)

    type_absence = TypeAbsence.objects.filter(
        company=sanction.company, code=_CODE_TYPE_ABSENCE_MISE_A_PIED).first()
    if type_absence is None:
        return None  # type non seedé pour cette société — no-op défensif

    date_debut = sanction.date_notification or sanction.date_faits
    if date_debut is None:
        return None
    date_fin = date_debut + timedelta(days=sanction.duree_jours - 1)

    return DemandeConge.objects.create(
        company=sanction.company,
        employe=sanction.employe,
        type_absence=type_absence,
        date_debut=date_debut,
        date_fin=date_fin,
        jours=Decimal(sanction.duree_jours),
        statut=DemandeConge.Statut.VALIDEE,
        date_decision=timezone.now(),
        motif=motif,
    )


@transaction.atomic
def propager_effets_sanction_annulation(sanction):
    """YHIRE7(a) — à l'ANNULATION d'une sanction (contestation gagnée),
    retire l'effet propagé : annule la ``DemandeConge`` de mise à pied liée
    (créée par ``propager_effets_sanction_notification``) si elle existe et
    n'est pas déjà annulée. No-op si aucune absence n'avait été générée."""
    from .models import DemandeConge

    motif = _motif_absence_mise_a_pied(sanction)
    demande = DemandeConge.objects.filter(
        company=sanction.company, employe=sanction.employe,
        motif=motif).exclude(statut=DemandeConge.Statut.ANNULEE).first()
    if demande is None:
        return None
    return annuler_demande(demande)


class SortieNonConfirmeeError(Exception):
    """YHIRE7(b) — levée quand une sanction LICENCIEMENT propose la sortie
    sans confirmation explicite (jamais automatique silencieux)."""


def proposer_sortie_pour_licenciement(
        sanction, *, confirmer=False, date_sortie=None):
    """YHIRE7(b) — une sanction ``LICENCIEMENT`` PROPOSE la sortie de
    l'employé (``sortir_employe``, YHIRE2) — JAMAIS automatique et silencieux :
    sans ``confirmer=True`` explicite, lève :class:`SortieNonConfirmeeError`
    (l'appelant — la vue — répond avec les infos pré-remplies pour que
    l'utilisateur confirme).

    Avec confirmation, appelle ``sortir_employe`` avec
    ``motif=DossierEmploye.MotifSortie.LICENCIEMENT`` et
    ``date_sortie`` (par défaut ``date_notification`` de la sanction, sinon
    aujourd'hui). Un dossier déjà SORTI lève ``ValueError`` (propagé tel
    quel — même garde d'idempotence que ``sortir_employe``).
    """
    from .models import DossierEmploye, Sanction

    if sanction.type_sanction != Sanction.TypeSanction.LICENCIEMENT:
        return None
    if not confirmer:
        raise SortieNonConfirmeeError(
            'Confirmation explicite requise pour déclencher la sortie '
            "suite à un licenciement (jamais automatique).")
    effective_date = (
        date_sortie or sanction.date_notification or timezone.localdate())
    return sortir_employe(
        sanction.employe, date_sortie=effective_date,
        motif=DossierEmploye.MotifSortie.LICENCIEMENT)


# ── YHIRE10 — accident du travail avec arrêt → absence (présence) ─────────

# Code stable du TypeAbsence dédié (seedé par ``seed_types_absence``). La
# rémunération de cette absence dépend du réglage société (l'indemnisation
# IJ CNSS reste le périmètre XPAI14 ; on câble ici SEULEMENT la présence —
# roster + import paie via le flag ``remunere`` du type).
_CODE_TYPE_ABSENCE_ACCIDENT_TRAVAIL = 'AT'


def _motif_absence_accident_travail(accident):
    """Clé stable reliant la ``DemandeConge`` générée à SON accident
    d'origine — garde d'idempotence (jamais deux absences pour un même AT ;
    une prolongation ÉTEND la même ligne au lieu d'en créer une seconde)."""
    return f'Accident du travail — {accident.reference}'


@transaction.atomic
def synchroniser_absence_accident_travail(accident):
    """YHIRE10 — synchronise l'absence de présence liée à un
    ``AccidentTravail`` avec arrêt, appelée à la création ET à chaque mise à
    jour de l'accident (idempotent) :

    * ``arret_travail=True`` et ``nb_jours_arret > 0`` — crée (1er appel) ou
      ÉTEND (appel suivant : mêmes dates recalculées depuis
      ``date_accident``/``nb_jours_arret``, jamais de doublon — clé stable
      par ``reference``) une ``DemandeConge`` déjà VALIDÉE du type
      ``TypeAbsence`` seedé « Accident du travail », couvrant
      ``date_accident`` → ``date_accident + nb_jours_arret - 1`` ;
    * ``arret_travail=False`` (ou ``nb_jours_arret=0``) — ANNULE l'absence
      précédemment générée si elle existe (arrêt supprimé/retiré) ;
    * type non seedé pour la société — no-op défensif (journalisé nulle
      part, appel silencieux : ne bloque jamais la déclaration de l'AT).

    Renvoie la ``DemandeConge`` active, ou ``None`` si aucun effet.
    """
    from datetime import timedelta

    from .models import DemandeConge, TypeAbsence

    motif = _motif_absence_accident_travail(accident)
    existante = DemandeConge.objects.filter(
        company=accident.company, employe=accident.employe,
        motif=motif).exclude(statut=DemandeConge.Statut.ANNULEE).first()

    if not accident.arret_travail or not accident.nb_jours_arret:
        if existante is not None:
            annuler_demande(existante)
        return None

    type_absence = TypeAbsence.objects.filter(
        company=accident.company,
        code=_CODE_TYPE_ABSENCE_ACCIDENT_TRAVAIL).first()
    if type_absence is None:
        return None  # type non seedé pour cette société — no-op défensif

    date_debut = accident.date_accident
    date_fin = date_debut + timedelta(days=accident.nb_jours_arret - 1)

    if existante is not None:
        # Prolongation/ajustement : ÉTEND la même ligne (jamais de doublon).
        existante.date_debut = date_debut
        existante.date_fin = date_fin
        existante.jours = Decimal(accident.nb_jours_arret)
        existante.type_absence = type_absence
        existante.save(update_fields=[
            'date_debut', 'date_fin', 'jours', 'type_absence'])
        return existante

    return DemandeConge.objects.create(
        company=accident.company,
        employe=accident.employe,
        type_absence=type_absence,
        date_debut=date_debut,
        date_fin=date_fin,
        jours=Decimal(accident.nb_jours_arret),
        statut=DemandeConge.Statut.VALIDEE,
        date_decision=timezone.now(),
        motif=motif,
    )


def comptes_actifs_employes_sortis(company):
    """YHIRE2 — rapport de sécurité PERMANENT : comptes utilisateur restés
    ACTIFS alors que leur dossier employé est SORTI. Doit toujours être VIDE
    en fonctionnement normal (un dossier sorti désactive son compte via
    ``sortir_employe`` — cette liste ne détecte que les cas hors chemin,
    ex. données historiques ou sortie faite avant ce câblage).

    Sélecteur pur, scopé société. Renvoie une liste de dicts
    ``{'employe_id', 'matricule', 'nom', 'prenom', 'user_id', 'username'}``.
    """
    from .models import DossierEmploye

    qs = (
        DossierEmploye.objects
        .filter(
            company=company, statut=DossierEmploye.Statut.SORTI,
            user__isnull=False, user__is_active=True)
        .select_related('user'))
    return [
        {
            'employe_id': d.pk,
            'matricule': d.matricule,
            'nom': d.nom,
            'prenom': d.prenom,
            'user_id': d.user_id,
            'username': getattr(d.user, 'username', ''),
        }
        for d in qs
    ]


# ── XRH34 — eLearning léger : quiz + certification ─────────────────────────

def _ajouter_mois(une_date, mois):
    """Ajoute ``mois`` mois calendaires à ``une_date`` (stdlib uniquement,
    aucune dépendance externe) — cale le jour sur le dernier jour du mois
    cible s'il déborde (ex. 31 janvier + 1 mois → 28/29 février)."""
    import calendar

    total = une_date.month - 1 + mois
    annee = une_date.year + total // 12
    moiscible = total % 12 + 1
    jour = min(une_date.day, calendar.monthrange(annee, moiscible)[1])
    return une_date.replace(year=annee, month=moiscible, day=jour)


def _est_reponse_correcte(question, reponse):
    """Compare une réponse brute (int ou liste d'ints) aux bonnes réponses
    d'UNE question — vrai UNIQUEMENT si l'ensemble complet correspond
    (aucune bonne réponse manquante, aucune fausse en plus)."""
    bonnes = set(question.get('bonnes_reponses') or [])
    if isinstance(reponse, (list, tuple, set)):
        donnees = set(reponse)
    elif reponse is None:
        donnees = set()
    else:
        donnees = {reponse}
    return donnees == bonnes


def corriger_tentative_quiz(quiz, reponses):
    """XRH34 — corrige une tentative CÔTÉ SERVEUR : ``reponses`` est une
    liste parallèle à ``quiz.questions`` (index de choix, ou liste d'index
    pour une question à choix multiple). Renvoie ``(score_pourcent, reussi)``.

    Les bonnes réponses NE SONT JAMAIS renvoyées à l'appelant — seul le
    score agrégé l'est. Un quiz sans question renvoie ``(0, False)``
    (jamais de division par zéro).
    """
    questions = quiz.questions or []
    if not questions:
        return 0, False
    reponses = list(reponses or [])
    correctes = 0
    for i, question in enumerate(questions):
        reponse = reponses[i] if i < len(reponses) else None
        if _est_reponse_correcte(question, reponse):
            correctes += 1
    score = round(100 * correctes / len(questions))
    reussi = score >= quiz.score_reussite
    return score, reussi


@transaction.atomic
def passer_tentative_quiz(quiz, employe, *, reponses, session=None):
    """XRH34 — enregistre + corrige une ``TentativeQuiz`` et, en cas de
    réussite, applique TOUS les effets de certification :

    * upsert du niveau ``CompetenceEmploye`` (niveau CONFIRMÉ) si
      ``quiz.competence`` est défini (même chemin que
      ``SessionFormationViewSet.marquer_realisee``, FG187) ;
    * si ``session`` est fournie ET que le quiz y est explicitement lié
      (même valeur transmise ici), upsert
      ``InscriptionFormation.resultat = REUSSI`` du participant ;
    * si ``quiz.habilitation_type`` est défini ET ``quiz.validite_mois``
      renseigné : prolonge (ou crée) l'``Habilitation`` de l'employé pour ce
      type — nouvelle échéance = ``max(aujourd'hui, échéance actuelle) +
      validite_mois``.

    Un ÉCHEC (score < seuil) N'A AUCUN EFFET (aucune mise à jour de
    compétence/inscription/habilitation) — seule la tentative est
    enregistrée avec son score.
    """
    from .models import (
        CompetenceEmploye, Habilitation, InscriptionFormation, TentativeQuiz,
    )

    score, reussi = corriger_tentative_quiz(quiz, reponses)
    tentative = TentativeQuiz.objects.create(
        company=quiz.company, quiz=quiz, employe=employe, session=session,
        reponses=reponses, score=score, reussi=reussi)

    if not reussi:
        return tentative

    if quiz.competence_id:
        # ZRH10 — passe par le point d'entrée unique : historise le
        # changement de niveau (source='quiz') si le niveau change réellement.
        enregistrer_niveau_competence(
            employe, quiz.competence_id, CompetenceEmploye.Niveau.CONFIRME,
            company=quiz.company, evalue_le=timezone.now(), source='quiz')

    if session is not None:
        InscriptionFormation.objects.update_or_create(
            session=session, participant=employe,
            defaults={'company': quiz.company,
                      'resultat': InscriptionFormation.Resultat.REUSSI},
        )

    if quiz.habilitation_type and quiz.validite_mois:
        today = timezone.localdate()
        habilitation = Habilitation.objects.filter(
            employe=employe, type_habilitation=quiz.habilitation_type).first()
        base = today
        if habilitation is not None and habilitation.date_validite and \
                habilitation.date_validite > today:
            base = habilitation.date_validite
        nouvelle_echeance = _ajouter_mois(base, quiz.validite_mois)
        if habilitation is None:
            Habilitation.objects.create(
                company=quiz.company, employe=employe,
                type_habilitation=quiz.habilitation_type,
                date_obtention=today, date_validite=nouvelle_echeance,
                actif=True,
            )
        else:
            habilitation.date_validite = nouvelle_echeance
            habilitation.actif = True
            habilitation.save(update_fields=[
                'date_validite', 'actif', 'date_modification'])

    return tentative


def generer_besoin_recertification(habilitation):
    """XRH34 — à l'expiration d'une habilitation LIÉE à un quiz (un
    ``QuizFormation`` actif existe pour ce ``type_habilitation`` et cette
    société), crée IDEMPOTENT un ``BesoinFormation`` de re-certification.

    Idempotence : clé stable dans ``theme`` (type d'habilitation + employé) —
    un ``BesoinFormation`` ``identifie``/``planifie`` déjà ouvert pour cette
    re-certification n'est jamais dupliqué (re-run = 0 doublon). Une fois le
    besoin ``satisfait`` (nouvelle réussite prolongeant l'habilitation), un
    futur cycle d'expiration peut en re-créer un NOUVEAU.

    No-op si aucun quiz actif ne couvre ce type d'habilitation pour la
    société (pas de fausse alerte pour un titre sans quiz associé), ou si
    l'habilitation n'est pas expirée.
    """
    from .models import BesoinFormation, QuizFormation

    if habilitation.valide:
        return None
    quiz_couvrant = QuizFormation.objects.filter(
        company=habilitation.company, actif=True,
        habilitation_type=habilitation.type_habilitation).exists()
    if not quiz_couvrant:
        return None

    theme = (
        f'Re-certification — {habilitation.get_type_habilitation_display()} '
        f'— {habilitation.employe.matricule}')
    deja_ouvert = BesoinFormation.objects.filter(
        company=habilitation.company, employe=habilitation.employe,
        theme=theme,
        statut__in=[
            BesoinFormation.Statut.IDENTIFIE, BesoinFormation.Statut.PLANIFIE],
    ).exists()
    if deja_ouvert:
        return None

    return BesoinFormation.objects.create(
        company=habilitation.company,
        employe=habilitation.employe,
        theme=theme[:200],
        priorite=BesoinFormation.Priorite.HAUTE,
        obligation_reglementaire=True,
        type_obligation=BesoinFormation.TypeObligation.AUTRE,
    )


@transaction.atomic
def valider_allocation(demande, decide_par=None):
    """ZRH13 — valide une ``DemandeAllocation`` SOUMISE et CRÉDITE le
    ``SoldeConge.acquis`` de l'année (année de création de la demande) du
    nombre de jours demandés (verrou pessimiste pour éviter un double
    crédit concurrent). Lève ``ValueError`` si la demande n'est pas
    décidable. Idempotent vis-à-vis d'une demande déjà validée (ne
    re-crédite pas)."""
    from .models import DemandeAllocation, SoldeConge

    if demande.statut != DemandeAllocation.Statut.SOUMISE:
        raise ValueError("Seule une demande soumise peut être validée.")

    annee = demande.date_creation.year if demande.date_creation \
        else timezone.now().year
    solde, _ = SoldeConge.objects.select_for_update().get_or_create(
        company=demande.company, employe=demande.employe, annee=annee)
    solde.acquis = (solde.acquis or Decimal('0')) + demande.jours
    solde.save(update_fields=['acquis', 'date_modification'])

    demande.statut = DemandeAllocation.Statut.VALIDEE
    demande.decide_par = decide_par
    demande.date_decision = timezone.now()
    demande.save(update_fields=['statut', 'decide_par', 'date_decision'])
    return demande


@transaction.atomic
def refuser_allocation(demande, decide_par=None):
    """ZRH13 — refuse une ``DemandeAllocation`` SOUMISE (aucun crédit de
    solde). Lève ``ValueError`` si la demande n'est pas décidable."""
    from .models import DemandeAllocation

    if demande.statut != DemandeAllocation.Statut.SOUMISE:
        raise ValueError("Seule une demande soumise peut être refusée.")
    demande.statut = DemandeAllocation.Statut.REFUSEE
    demande.decide_par = decide_par
    demande.date_decision = timezone.now()
    demande.save(update_fields=['statut', 'decide_par', 'date_decision'])
    return demande


@transaction.atomic
def enregistrer_niveau_competence(
        employe, competence_id, niveau, *, company=None, evalue_par=None,
        evalue_le=None, source='manuelle'):
    """ZRH10 — point d'entrée UNIQUE pour écrire le niveau d'une
    ``CompetenceEmploye`` : upsert le niveau ET, si le niveau CHANGE
    (création avec niveau > 0, ou changement réel sur une ligne existante),
    écrit une ligne ``HistoriqueCompetence`` (ancien -> nouveau, horodatée,
    ``source`` ∈ {manuelle, quiz, formation}).

    Appelé par les TROIS chemins d'écriture du niveau : la matrice manuelle
    (``CompetenceEmployeViewSet``), la session de formation réalisée (FG187,
    ``marquer_realisee``) et la réussite de quiz (XRH34,
    ``passer_tentative_quiz``) — aucun n'écrit plus ``CompetenceEmploye``
    directement, ils passent tous par ici, garantissant qu'AUCUN changement
    de niveau n'échappe à l'historique.

    Renvoie l'instance ``CompetenceEmploye`` à jour.
    """
    from .models import CompetenceEmploye, HistoriqueCompetence

    company = company or employe.company
    if evalue_le is None:
        evalue_le = timezone.now()

    existante = CompetenceEmploye.objects.filter(
        company=company, employe=employe,
        competence_id=competence_id).first()
    ancien_niveau = existante.niveau if existante else 0

    obj, _created = CompetenceEmploye.objects.update_or_create(
        company=company, employe=employe, competence_id=competence_id,
        defaults={
            'niveau': niveau,
            'evalue_le': evalue_le,
            'evalue_par': evalue_par,
        },
    )

    if niveau != ancien_niveau:
        HistoriqueCompetence.objects.create(
            company=company, employe=employe, competence_id=competence_id,
            ancien_niveau=ancien_niveau, nouveau_niveau=niveau,
            source=source,
        )
    return obj


# ── ZRH8 — Plans d'appréciation automatiques (jalons d'ancienneté) ─────────

def campagne_annuelle_par_defaut(company, annee):
    """ZRH8 — Renvoie la campagne annuelle par défaut de ``company``/``annee``,
    la créant si elle n'existe pas déjà (idempotent, ``get_or_create``).

    Utilisée par ``planifier_appreciations`` quand un ``PlanAppreciation`` ne
    porte pas de ``campagne_cible`` explicite. Le libellé est stable
    (« Appréciations automatiques <année> ») pour que deux appels sur la même
    année retombent sur la MÊME campagne (jamais un doublon).
    """
    from .models import CampagneEvaluation

    campagne, _created = CampagneEvaluation.objects.get_or_create(
        company=company, annee=annee,
        intitule=f'Appréciations automatiques {annee}',
        defaults={'statut': CampagneEvaluation.Statut.OUVERTE},
    )
    return campagne


def _mois_entre(date_debut, date_fin):
    """ZRH8 — Nombre de mois PLEINS entre deux dates (``date_fin`` > ou =
    ``date_debut``), en tenant compte du jour du mois (un jalon n'est
    « franchi » que le jour anniversaire, pas avant). Lecture seule."""
    mois = ((date_fin.year - date_debut.year) * 12
            + (date_fin.month - date_debut.month))
    if date_fin.day < date_debut.day:
        mois -= 1
    return max(mois, 0)


def planifier_appreciations_pour_societe(company, *, aujourd_hui=None,
                                         apply=False):
    """ZRH8 — Planifie les évaluations dues (jalons d'ancienneté franchis)
    pour TOUS les ``DossierEmploye`` ACTIFS de ``company``, selon les
    ``PlanAppreciation`` actifs de la société.

    Pour chaque employé actif et chaque plan actif : calcule son ancienneté
    en mois pleins (``date_embauche`` -> ``aujourd_hui``, défaut aujourd'hui)
    et, pour CHAQUE jalon du plan déjà FRANCHI (ancienneté >= jalon), crée une
    ``EvaluationEmploye`` "planifiée" — SAUF si une évaluation existe déjà
    pour ce jalon (clé d'idempotence : ``synthese`` porte une marque stable
    ``"[ZRH8:jalon=<n>]"`` — un jalon donné ne génère donc JAMAIS de doublon,
    même rejoué). L'évaluateur posé est le MANAGER de l'employé s'il en
    existe un identifiable (le dernier ``evaluateur`` d'une évaluation
    antérieure de cet employé), sinon ``None`` (aucune évaluation n'est
    inventée). La campagne cible est celle du plan (``campagne_cible``) ou,
    à défaut, la campagne annuelle par défaut de l'année courante.

    Dry-run PAR DÉFAUT (``apply=False``) : ne calcule et ne rapporte que ce
    qui SERAIT créé, sans rien écrire. ``apply=True`` committe réellement.

    Un employé dont l'ancienneté n'atteint aucun jalon ne génère rien.
    Multi-tenant : tout est scopé à ``company`` (jamais lu du corps de
    requête).

    Retourne ``{'a_creer': [...], 'nb_a_creer': int, 'nb_deja': int}`` où
    chaque entrée de ``a_creer`` est ``{'employe_id', 'jalon', 'plan_id'}``
    (dry-run) ou l'``EvaluationEmploye`` créée (``apply=True``).
    """
    from .models import DossierEmploye, EvaluationEmploye, PlanAppreciation

    if aujourd_hui is None:
        aujourd_hui = timezone.localdate()

    plans = PlanAppreciation.objects.filter(company=company, actif=True)
    if not plans:
        return {'a_creer': [], 'nb_a_creer': 0, 'nb_deja': 0}

    dossiers = DossierEmploye.objects.filter(
        company=company, statut=DossierEmploye.Statut.ACTIF,
        date_embauche__isnull=False)

    a_creer = []
    nb_deja = 0
    # Un employé qui franchit PLUSIEURS jalons du même plan dans le même
    # passage (ex. 3 ET 12 mois à la fois) obtient UNE SEULE
    # ``EvaluationEmploye`` par (campagne, employe) — contrainte unique,
    # toutes les marques de jalon coexistent dans ``synthese``
    # (test_deux_jalons_franchis_meme_campagne_pas_de_doublon_ligne). Sans ce
    # suivi, chaque jalon franchi comptait pour +1 dans ``nb_a_creer``/
    # ``a_creer`` même quand il retombait sur la MÊME ligne déjà comptée —
    # bug réel : un employé embauché il y a exactement 12 mois avec les
    # jalons [3, 12, 24] franchit 3 ET 12 à la fois, gonflant nb_a_creer à 2
    # pour une seule évaluation réellement (à créer/déjà créée).
    lignes_comptees = set()  # {(campagne_id ou None, employe_id)}

    for plan in plans:
        jalons = plan.mois_apres_embauche or []
        if not jalons:
            continue
        for dossier in dossiers:
            anciennete_mois = _mois_entre(dossier.date_embauche, aujourd_hui)
            for jalon in jalons:
                if anciennete_mois < jalon:
                    continue  # jalon pas encore franchi.

                marque = f'[ZRH8:jalon={jalon}]'
                deja = EvaluationEmploye.objects.filter(
                    company=company, employe=dossier,
                    synthese__contains=marque).exists()
                if deja:
                    nb_deja += 1
                    continue

                if apply:
                    campagne = (
                        plan.campagne_cible
                        or campagne_annuelle_par_defaut(
                            company, aujourd_hui.year))
                    # Le dernier évaluateur connu de cet employé sert de
                    # proxy « manager » (aucun organigramme dédié n'existe
                    # encore dans ce module) — None si aucun antécédent.
                    derniere_eval = (
                        EvaluationEmploye.objects
                        .filter(company=company, employe=dossier)
                        .exclude(evaluateur__isnull=True)
                        .order_by('-date_creation')
                        .first())
                    evaluateur = (
                        derniere_eval.evaluateur if derniere_eval else None)

                    evaluation, created = (
                        EvaluationEmploye.objects.get_or_create(
                            company=company, campagne=campagne,
                            employe=dossier,
                            defaults={
                                'evaluateur': evaluateur,
                                'statut': EvaluationEmploye.Statut.PLANIFIE,
                                'synthese': marque,
                            },
                        ))
                    if not created and marque not in (evaluation.synthese or ''):
                        # Une évaluation existe déjà pour (campagne, employe)
                        # (contrainte unique) mais sans la marque de CE
                        # jalon — on l'ajoute pour rester idempotent sans
                        # dupliquer la ligne.
                        evaluation.synthese = (
                            f'{evaluation.synthese} {marque}'.strip())
                        evaluation.save(update_fields=['synthese'])
                    ligne_key = (campagne.id, dossier.pk)
                    if ligne_key not in lignes_comptees:
                        lignes_comptees.add(ligne_key)
                        a_creer.append(evaluation)
                else:
                    # Dry-run : la clé de regroupement DOIT rester purement
                    # en lecture (aucune écriture en dry-run — contrat du
                    # docstring). ``campagne_cible`` s'il est posé, sinon un
                    # marqueur stable par année (même campagne annuelle par
                    # défaut qu'``apply`` résoudrait, sans la créer ici).
                    campagne_key = (
                        plan.campagne_cible_id
                        if plan.campagne_cible_id
                        else f'defaut-{aujourd_hui.year}')
                    ligne_key = (campagne_key, dossier.pk)
                    if ligne_key not in lignes_comptees:
                        lignes_comptees.add(ligne_key)
                        a_creer.append({
                            'employe_id': dossier.pk,
                            'jalon': jalon,
                            'plan_id': plan.pk,
                        })

    return {
        'a_creer': a_creer,
        'nb_a_creer': len(a_creer),
        'nb_deja': nb_deja,
    }


# ── ARC13 — import générique (framework `apps.dataimport`) ─────────────────

def _parse_date_import(valeur):
    """Normalise une valeur de date issue d'un import (str ISO/FR ou objet
    date/datetime déjà résolu par openpyxl) ; ``None`` si vide/invalide."""
    import datetime as _dt

    if valeur is None or valeur == '':
        return None
    if isinstance(valeur, _dt.datetime):
        return valeur.date()
    if isinstance(valeur, _dt.date):
        return valeur
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return _dt.datetime.strptime(str(valeur).strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def creer_dossier_employe_import(company, ligne):
    """ARC13 — Crée (ou saute si doublon) UN dossier employé depuis une ligne
    d'import CSV/XLSX (dict de colonnes déjà nettoyées), via
    ``apps.rh.services`` — jamais le modèle ``DossierEmploye`` directement
    (contrat du framework ``apps.dataimport``, même motif que
    ``creer_vehicule_import`` XFLT22).

    Colonnes attendues : ``matricule`` (obligatoire, clé d'idempotence),
    ``nom`` (obligatoire), ``prenom``, ``email``, ``telephone``, ``cin``,
    ``poste``, ``date_embauche``, ``type_contrat``. Idempotent sur
    ``(company, matricule)`` (même contrainte d'unicité que le modèle) : une
    ligne dont le matricule existe déjà pour la société est SAUTÉE (retourne
    ``'doublon'``), jamais mise à jour ni dupliquée. Retourne
    ``('cree'|'doublon'|'erreur', message|None)``.
    """
    from .models import DossierEmploye

    matricule = str(ligne.get('matricule', '') or '').strip()
    if not matricule:
        return 'erreur', 'Matricule manquant.'
    nom = str(ligne.get('nom', '') or '').strip()
    if not nom:
        return 'erreur', 'Nom manquant.'

    if DossierEmploye.objects.filter(
            company=company, matricule=matricule).exists():
        return 'doublon', None

    type_brut = str(ligne.get('type_contrat', '') or '').strip().lower()
    types_valides = {c for c, _ in DossierEmploye.TypeContrat.choices}
    type_contrat = type_brut if type_brut in types_valides \
        else DossierEmploye.TypeContrat.CDI

    try:
        DossierEmploye.objects.create(
            company=company,
            matricule=matricule,
            nom=nom,
            prenom=str(ligne.get('prenom', '') or '').strip(),
            email=str(ligne.get('email', '') or '').strip(),
            telephone=str(ligne.get('telephone', '') or '').strip(),
            cin=str(ligne.get('cin', '') or '').strip(),
            poste=str(ligne.get('poste', '') or '').strip(),
            date_embauche=_parse_date_import(ligne.get('date_embauche')),
            type_contrat=type_contrat,
        )
    except Exception as exc:  # pragma: no cover - défensif, erreur inattendue
        return 'erreur', str(exc)

    return 'cree', None
