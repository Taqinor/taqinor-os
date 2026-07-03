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
