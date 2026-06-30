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
                           extra_holidays=None):
    """Durée décomptée d'une demande de congé (FG163).

    Si ``type_absence.decompte_jours_ouvres`` est vrai, ne compte que les jours
    ouvrés (hors week-end et fériés, cf. ``holidays.working_days`` / FG5) ;
    sinon, compte les jours calendaires. Renvoie un ``Decimal`` (0 si la plage
    est invalide).
    """
    if type_absence is not None and type_absence.decompte_jours_ouvres:
        n = holidays.working_days(date_debut, date_fin, extra_holidays)
    else:
        n = holidays.calendar_days(date_debut, date_fin)
    return Decimal(n)


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


def appliquer_majoration(heures_supp):
    """Calcule et POSE les décomptes majorés sur une instance ``HeuresSupp``.

    Utilise ``calculer_majoration`` avec le ``taux_horaire`` de l'entrée (ou, à
    défaut, le ``cout_horaire`` interne du dossier employé). Renseigne
    ``heures_normales``, ``hs_25``, ``hs_50``, ``hs_100``, ``taux_horaire`` et
    ``montant_majore`` sur l'objet (non sauvegardé — l'appelant ``save()``).
    """
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
    """
    from .models import DemandeConge, SoldeConge
    if demande.statut != DemandeConge.Statut.SOUMISE:
        raise ValueError(
            "Seule une demande soumise peut être validée.")
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
    if demande.statut == DemandeConge.Statut.VALIDEE \
            and demande.type_absence.deduit_solde and demande.jours:
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

    return dossier
