"""Sélecteurs (lectures) des Ressources humaines.

Lectures cadrées société : chaque sélecteur exige la ``company`` de l'appelant
et ne renvoie jamais de données hors de sa société.
"""
from datetime import timedelta

from django.utils import timezone

from .models import (
    AccidentTravail,
    AffectationRoster,
    AvanceSalaire,
    Certification,
    Departement,
    DemandeConge,
    DocumentEmploye,
    DossierEmploye,
    DotationEpi,
    FeuilleTemps,
    Habilitation,
    HeuresSupp,
    HoraireTravail,
    IncidentPresence,
    InscriptionFormation,
    PermisConduire,
    Poste,
    PresenceChantier,
    PresquAccident,
    PrimeAttribuee,
    Remuneration,
    SessionFormation,
    VisiteMedicale,
)


def dossier_employe_for_user(company, user_id):
    """XFSM2 — ``DossierEmploye`` scopé société relié à un compte utilisateur,
    ou ``None`` si aucun dossier n'est relié (ex. compte sans fiche RH). Point
    d'entrée de lecture pour les autres modules (ex. installations, pour
    vérifier une habilitation avant affectation) sans importer ``rh.models``."""
    if user_id is None:
        return None
    return DossierEmploye.objects.filter(
        company=company, user_id=user_id).first()


def dossier_appartient_societe(company, dossier_id):
    """Vrai si le dossier ``dossier_id`` appartient à ``company`` (cross-app).

    Point d'entrée de lecture pour les autres modules (paie) : permet de valider
    qu'un ``rh.DossierEmploye`` référencé appartient bien à la société de
    l'appelant, sans importer ``rh.models`` côté appelant. Toujours scopé
    société ; renvoie ``False`` si la société est absente ou le dossier
    introuvable/hors société.
    """
    if company is None or dossier_id is None:
        return False
    return DossierEmploye.objects.filter(
        company=company, pk=dossier_id).exists()


def horaire_actif(employe, le=None):
    """Horaire de travail effectif d'un employé à une date (XRH8).

    Résout l'horaire APPLICABLE à ``le`` (par défaut aujourd'hui) :

    * si ``employe.horaire`` est un horaire TEMPORAIRE (``date_debut``/
      ``date_fin`` renseignées) et que ``le`` tombe dans sa fenêtre de
      validité (bornes incluses) → cet horaire s'applique (ex. Ramadan) ;
    * sinon, si ``employe.horaire`` est PERMANENT (``date_debut`` ET
      ``date_fin`` tous deux vides) → il s'applique toujours ;
    * sinon (horaire temporaire hors fenêtre, ou aucun horaire assigné,
      ou horaire inactif) → ``None`` : l'appelant retombe sur le seuil par
      défaut (8 h/j, ``services.SEUIL_JOURNALIER_DEFAUT``) — RETOUR
      AUTOMATIQUE au standard une fois la fenêtre Ramadan/saisonnière passée.

    Sélecteur PUR : ``le`` est un paramètre (déterministe, testable), jamais
    lu de ``timezone.now()`` en dur.
    """
    if employe is None or employe.horaire_id is None:
        return None
    horaire = employe.horaire
    if not horaire.actif:
        return None
    if le is None:
        le = timezone.localdate()
    if horaire.date_debut is None and horaire.date_fin is None:
        return horaire
    debut_ok = horaire.date_debut is None or le >= horaire.date_debut
    fin_ok = horaire.date_fin is None or le <= horaire.date_fin
    if debut_ok and fin_ok:
        return horaire
    return None


def horaires_actifs_societe(company):
    """Horaires de travail actifs de la société (référentiel, XRH8)."""
    if company is None:
        return HoraireTravail.objects.none()
    return HoraireTravail.objects.filter(company=company, actif=True)


def dossiers_actifs(company):
    """Dossiers employés ACTIFS de la société (cross-app, pour la paie).

    Lecture cadrée société utilisée par la paie pour itérer les collaborateurs
    en activité (génération de période, import d'éléments variables). Jamais lu
    du corps de requête ; renvoie un queryset vide si la société est absente.
    """
    if company is None:
        return DossierEmploye.objects.none()
    return DossierEmploye.objects.filter(
        company=company, statut=DossierEmploye.Statut.ACTIF
    ).order_by('nom', 'prenom')


def documents_expirant_bientot(company, within_days=30):
    """Documents employé de la société qui expirent dans ``within_days`` jours.

    FG159 — alerte d'expiration du coffre documents : ne retient que les
    documents POURVUS d'une ``date_expiration`` (les documents sans échéance,
    ex. diplômes, sont ignorés), dont l'expiration tombe entre aujourd'hui et
    aujourd'hui + ``within_days`` inclus. Exclut les documents déjà expirés
    (échéance passée). Toujours scopé société (jamais lu du corps de requête).
    Trié par échéance la plus proche d'abord.
    """
    if company is None:
        return DocumentEmploye.objects.none()
    try:
        within_days = int(within_days)
    except (TypeError, ValueError):
        within_days = 30
    if within_days < 0:
        within_days = 0
    today = timezone.localdate()
    limite = today + timedelta(days=within_days)
    return (
        DocumentEmploye.objects
        .filter(
            company=company,
            date_expiration__isnull=False,
            date_expiration__gte=today,
            date_expiration__lte=limite,
        )
        .select_related('employe', 'attachment')
        .order_by('date_expiration', 'id')
    )


def absences_equipe(company, date_debut, date_fin):
    """Calendrier d'absences d'équipe (FG165) — demandes VALIDÉES chevauchant la
    plage [``date_debut``, ``date_fin``].

    Lecture cadrée société : ne renvoie que les congés/absences VALIDÉS dont la
    période recoupe la fenêtre demandée (deux intervalles se chevauchent si
    ``debut <= fin_fenetre`` ET ``fin >= debut_fenetre``). Trié par date de début.
    Sert d'agenda d'équipe et de base au verrou de dispatch terrain.
    """
    if company is None or date_debut is None or date_fin is None:
        return DemandeConge.objects.none()
    return (
        DemandeConge.objects
        .filter(
            company=company,
            statut=DemandeConge.Statut.VALIDEE,
            date_debut__lte=date_fin,
            date_fin__gte=date_debut,
        )
        .select_related('employe', 'type_absence')
        .order_by('date_debut', 'id')
    )


def employe_absent_le(company, employe_id, jour):
    """Vrai si l'employé est en congé/absence VALIDÉE le ``jour`` donné (FG165).

    Brique du dispatch terrain : un technicien absent ce jour-là n'est PAS
    assignable. Toujours scopé société ; ``False`` si la société/employé manque.
    """
    if company is None or employe_id is None or jour is None:
        return False
    return DemandeConge.objects.filter(
        company=company,
        employe_id=employe_id,
        statut=DemandeConge.Statut.VALIDEE,
        date_debut__lte=jour,
        date_fin__gte=jour,
    ).exists()


def date_embauche_employe(company, employe_id):
    """Date d'embauche d'un employé (cross-app, pour la paie).

    Sélecteur cadrée société : la paie utilise cette fonction pour calculer
    l'ancienneté sans jamais importer ``rh.models`` directement. Renvoie la
    ``date_embauche`` du dossier (peut être ``None`` si non renseignée) ou
    ``None`` si le dossier est introuvable ou hors société.
    """
    if company is None or employe_id is None:
        return None
    try:
        dossier = DossierEmploye.objects.get(company=company, pk=employe_id)
        return dossier.date_embauche
    except DossierEmploye.DoesNotExist:
        return None


def sortie_employe(company, employe_id):
    """Date/motif de sortie d'un employé (cross-app, pour la paie XPAI1).

    Sélecteur cadré société : la paie l'utilise pour générer le solde de tout
    compte (STC) sans jamais importer ``rh.models`` directement. Renvoie
    ``(date_sortie, motif_sortie)`` — les deux peuvent être ``None``/vides si
    le dossier n'a pas encore de date de sortie renseignée — ou
    ``(None, None)`` si le dossier est introuvable ou hors société.
    """
    if company is None or employe_id is None:
        return None, None
    try:
        dossier = DossierEmploye.objects.get(company=company, pk=employe_id)
        return dossier.date_sortie, dossier.motif_sortie
    except DossierEmploye.DoesNotExist:
        return None, None


def pointages_par_user_jour(company, debut, fin):
    """Durée POINTÉE (FG166) par UTILISATEUR et par JOUR sur [debut, fin] (XPRJ8).

    Sélecteur cross-app fin (frontière CLAUDE.md) : les autres modules (ex.
    ``gestion_projet`` — rapprochement pointages ↔ temps projet) appellent CE
    sélecteur au lieu d'importer ``rh.models.Pointage`` directement. Ne
    considère que les employés reliés à un compte utilisateur (``employe.
    user_id``) — un pointage sans compte ERP n'a aucun homologue « temps
    projet » à rapprocher. Une ligne ``Pointage`` compte pour
    ``duree_minutes`` (arrivée + départ posés) ; une ligne incomplète
    (arrivée seule, ``heure_depart`` absente) compte pour 0 minute (pas de durée
    calculable).

    Toujours scopé société. Renvoie un dict ``{(user_id, date): minutes}`` —
    clé absente = aucun pointage ce jour-là pour cet utilisateur.
    """
    from datetime import date as _date

    from .models import Pointage

    if company is None or debut is None or fin is None:
        return {}

    pointages = Pointage.objects.filter(
        company=company,
        employe__user__isnull=False,
        heure_arrivee__date__gte=debut,
        heure_arrivee__date__lte=fin,
    ).select_related('employe')

    par_user_jour = {}
    for p in pointages:
        if p.heure_arrivee is None or p.heure_depart is None:
            continue
        user_id = p.employe.user_id
        jour = p.heure_arrivee.date() if isinstance(
            p.heure_arrivee, _date) else p.heure_arrivee.date()
        cle = (user_id, jour)
        par_user_jour[cle] = par_user_jour.get(cle, 0) + (
            p.duree_minutes or 0)
    return par_user_jour


def labour_hours_for_installation(installation_id, company=None):
    """Heures de main-d'œuvre imputées à une installation (job-costing, FG167).

    Sélecteur cross-app : les autres modules (ventes job-costing, installations)
    appellent ce sélecteur SANS jamais importer ``rh.models`` directement. Renvoie
    le total des heures et le coût total (si valorisé) pour une installation donnée.

    Retourne un dict :
    ``{
        'total_heures': Decimal,         # 0 si aucune ligne
        'total_cout': Decimal | None,    # None si aucune ligne n'a de taux
        'count': int,
    }``

    ``company`` est recommandé pour garantir l'isolation multi-tenant ; quand
    absent on agrège toutes les sociétés (réservé au reporting global).
    """
    from decimal import Decimal
    from django.db.models import Sum

    qs = FeuilleTemps.objects.filter(installation_id=installation_id)
    if company is not None:
        qs = qs.filter(company=company)

    agg = qs.aggregate(total_heures=Sum('heures'))
    total_heures = agg['total_heures'] or Decimal('0')
    count = qs.count()

    # Coût agrégé : somme des (heures × taux) pour les lignes où taux non NULL.
    cout_lines = qs.filter(
        taux_horaire__isnull=False).only('heures', 'taux_horaire')
    total_cout = None
    if cout_lines.exists():
        total_cout = sum(
            (ft.heures * ft.taux_horaire for ft in cout_lines),
            Decimal('0'),
        )

    return {
        'total_heures': total_heures,
        'total_cout': total_cout,
        'count': count,
    }


def fiche_identite_employe(company, employe_id):
    """Identité + poste actuel d'un employé, pour la fiche carrière (XPAI26).

    Sélecteur cross-app : la paie lit CE sélecteur (jamais ``rh.models``
    direct) pour construire la fiche historique de carrière/salaire (registre
    d'inspection du travail). Renvoie un dict ``{'matricule', 'nom', 'prenom',
    'poste', 'date_embauche', 'type_contrat', 'date_sortie'}`` ou ``None`` si
    le dossier est introuvable/hors société.
    """
    if company is None or employe_id is None:
        return None
    try:
        dossier = DossierEmploye.objects.select_related(
            'poste_ref').get(company=company, pk=employe_id)
    except DossierEmploye.DoesNotExist:
        return None
    poste = (dossier.poste_ref.intitule if dossier.poste_ref_id
             else dossier.poste)
    return {
        'matricule': dossier.matricule,
        'nom': dossier.nom,
        'prenom': dossier.prenom,
        'poste': poste or '',
        'date_embauche': dossier.date_embauche,
        'type_contrat': dossier.get_type_contrat_display(),
        'date_sortie': dossier.date_sortie,
    }


def labour_hours_par_installation_pour_employe(
        company, employe_id, date_debut, date_fin):
    """Heures ``FeuilleTemps`` d'un employé sur une période, par installation.

    Sélecteur cross-app (XPAI17) : la paie appelle CE sélecteur pour ventiler
    le coût employeur d'un bulletin au prorata des heures réellement imputées
    à chaque chantier (``installations.Installation``, référencé en
    ``installation_id`` — jamais importé directement). Renvoie une liste de
    dicts ``{'installation_id', 'total_heures'}`` (Decimal), triée par
    ``installation_id``, EXCLUANT les lignes à 0 heure. Liste vide si aucune
    heure imputée sur la période (repli attendu vers une clé % fixe côté paie).
    """
    from decimal import Decimal

    from django.db.models import Sum

    qs = (
        FeuilleTemps.objects
        .filter(company=company, employe_id=employe_id,
                date__gte=date_debut, date__lte=date_fin)
        .values('installation_id')
        .annotate(total_heures=Sum('heures'))
        .order_by('installation_id')
    )
    return [
        {'installation_id': row['installation_id'],
         'total_heures': row['total_heures'] or Decimal('0')}
        for row in qs if (row['total_heures'] or Decimal('0')) > 0
    ]


def heures_supp_pour_paie(company, date_debut, date_fin, employe_id=None):
    """Heures supplémentaires majorées d'une période (FG168, entrée de paie).

    Sélecteur cross-app : la paie lit les HS d'une période SANS importer
    ``rh.models`` — elle obtient, par employé, les totaux d'heures
    supplémentaires par tranche de taux et le montant majoré déjà valorisé.
    Toujours scopé société ; renvoie une liste vide si la société est absente.

    Renvoie une liste de dicts (un par employé ayant des HS sur la période) :
    ``{
        'employe_id': int,
        'hs_25': Decimal, 'hs_50': Decimal, 'hs_100': Decimal,
        'total_hs': Decimal,
        'montant_majore': Decimal,   # 0 si aucune ligne valorisée
    }``
    """
    from decimal import Decimal
    if company is None or date_debut is None or date_fin is None:
        return []
    qs = HeuresSupp.objects.filter(
        company=company, date__gte=date_debut, date__lte=date_fin)
    if employe_id is not None:
        qs = qs.filter(employe_id=employe_id)
    agg = {}
    for hs in qs.only(
            'employe_id', 'hs_25', 'hs_50', 'hs_100', 'montant_majore'):
        row = agg.setdefault(hs.employe_id, {
            'employe_id': hs.employe_id,
            'hs_25': Decimal('0'), 'hs_50': Decimal('0'),
            'hs_100': Decimal('0'), 'total_hs': Decimal('0'),
            'montant_majore': Decimal('0'),
        })
        row['hs_25'] += hs.hs_25 or Decimal('0')
        row['hs_50'] += hs.hs_50 or Decimal('0')
        row['hs_100'] += hs.hs_100 or Decimal('0')
        row['total_hs'] += (hs.hs_25 or Decimal('0')) \
            + (hs.hs_50 or Decimal('0')) + (hs.hs_100 or Decimal('0'))
        row['montant_majore'] += hs.montant_majore or Decimal('0')
    return [agg[k] for k in sorted(agg)]


def absences_non_remunerees_pour_paie(company, date_debut, date_fin,
                                      employe_id=None):
    """Absences VALIDÉES non rémunérées d'une période (YHIRE1, entrée de paie).

    Sélecteur cross-app : la paie importe les jours d'absence NON rémunérés
    (``TypeAbsence.remunere = False`` — sans solde, injustifiée…) SANS jamais
    importer ``rh.models`` directement. Une demande de congé REMUNÉRÉE
    (congé payé, maladie indemnisée…) n'a AUCUN impact sur le net : elle est
    délibérément exclue ici (le salarié est payé comme présent).

    Une demande qui chevauche la fenêtre sans y être entièrement contenue est
    IGNORÉE (bornée strictement à ``[date_debut, date_fin]``) — l'import RH
    fonctionne par période de paie mensuelle et une demande à cheval sur deux
    mois est un cas rare traité manuellement.

    Renvoie une liste de dicts (une par demande) : ``{'employe_id',
    'demande_id', 'type_absence_code', 'type_absence_libelle', 'jours',
    'deduit_solde'}``.
    """
    if company is None or date_debut is None or date_fin is None:
        return []
    qs = DemandeConge.objects.filter(
        company=company,
        statut=DemandeConge.Statut.VALIDEE,
        type_absence__remunere=False,
        date_debut__gte=date_debut,
        date_fin__lte=date_fin,
    ).select_related('type_absence')
    if employe_id is not None:
        qs = qs.filter(employe_id=employe_id)
    return [
        {
            'employe_id': demande.employe_id,
            'demande_id': demande.id,
            'type_absence_code': demande.type_absence.code,
            'type_absence_libelle': demande.type_absence.libelle,
            'jours': demande.jours,
            'deduit_solde': demande.type_absence.deduit_solde,
        }
        for demande in qs.order_by('employe_id', 'date_debut')
    ]


def primes_validees_pour_paie(company, annee, mois, employe_id=None):
    """Primes/indemnités VALIDÉES d'un mois (YHIRE1, entrée de paie, FG193).

    Sélecteur cross-app : la paie importe les primes ``PrimeAttribuee`` au
    statut ``validee`` (PAYÉE reste exclue — déjà versée hors bulletin, elle
    ne doit pas re-générer une ligne) de la ``(annee, mois)`` SANS jamais
    importer ``rh.models`` directement.

    Renvoie une liste de dicts (une par prime) : ``{'employe_id',
    'prime_id', 'type_prime_libelle', 'montant', 'motif'}``.
    """
    if company is None or annee is None or mois is None:
        return []
    qs = PrimeAttribuee.objects.filter(
        company=company, annee=annee, mois=mois,
        statut=PrimeAttribuee.Statut.VALIDEE,
    ).select_related('type_prime')
    if employe_id is not None:
        qs = qs.filter(employe_id=employe_id)
    return [
        {
            'employe_id': prime.employe_id,
            'prime_id': prime.id,
            'type_prime_libelle': prime.type_prime.libelle,
            'montant': prime.montant,
            'motif': prime.motif,
        }
        for prime in qs.order_by('employe_id', 'id')
    ]


# Facteurs (numérateur, dénominateur) de normalisation vers un montant
# MENSUEL (YHIRE6). L'horaire est approximé via la norme paie standard
# (191 h/mois) faute d'un taux horaire contractuel dédié sur ``Remuneration``
# — write-up assumé, cohérent avec ``ProfilPaie.heures_travail_mensuel`` par
# défaut.
_FACTEUR_MENSUALISATION = {
    Remuneration.Periodicite.MENSUEL: (1, 1),
    Remuneration.Periodicite.ANNUEL: (1, 12),
    Remuneration.Periodicite.JOURNALIER: (26, 1),
    Remuneration.Periodicite.HORAIRE: (191, 1),
}


def remuneration_en_vigueur(company, employe_id, le_jour=None):
    """Rémunération EN VIGUEUR d'un employé à une date (YHIRE6, FG157).

    La ligne ``Remuneration`` dont ``date_effet`` est la plus récente ≤
    ``le_jour`` (aujourd'hui par défaut). Sélecteur cross-app : la paie lit
    la rémunération de référence SANS jamais importer ``rh.models``
    directement — donnée SENSIBLE (paie), à gater ``salaires_voir`` côté
    appelant.

    Renvoie ``{'montant_mensuel', 'montant', 'devise', 'periodicite',
    'date_effet'}`` normalisé en équivalent MENSUEL (pour comparaison directe
    à ``ProfilPaie.salaire_base``), ou ``None`` si aucune ligne n'est en
    vigueur à cette date.
    """
    from decimal import Decimal
    if company is None or employe_id is None:
        return None
    jour = le_jour or timezone.localdate()
    ligne = (
        Remuneration.objects
        .filter(company=company, employe_id=employe_id, date_effet__lte=jour)
        .order_by('-date_effet', '-date_creation')
        .first()
    )
    if ligne is None:
        return None
    numerateur, denominateur = _FACTEUR_MENSUALISATION.get(
        ligne.periodicite, (1, 1))
    montant_mensuel = (
        Decimal(ligne.montant) * Decimal(numerateur) / Decimal(denominateur))
    return {
        'montant_mensuel': montant_mensuel.quantize(Decimal('0.01')),
        'montant': ligne.montant,
        'devise': ligne.devise,
        'periodicite': ligne.periodicite,
        'date_effet': ligne.date_effet,
    }


def departements_par_employe(company, employe_ids):
    """Mappe ``employe_id -> {'departement_id', 'departement_nom'}`` (ZPAI1).

    Sélecteur cross-app : la paie lit le département d'un groupe d'employés
    (rapport d'analyse par département) SANS jamais importer ``rh.models``
    directement. Un employé sans département (ou hors ``employe_ids``) est
    absent du dict renvoyé — l'appelant traite ça comme « non affecté ».
    """
    if company is None or not employe_ids:
        return {}
    qs = (
        DossierEmploye.objects
        .filter(company=company, id__in=list(employe_ids))
        .select_related('departement')
    )
    return {
        d.id: {
            'departement_id': d.departement_id,
            'departement_nom': d.departement.nom if d.departement_id else '',
        }
        for d in qs
    }


def employes_assignables(company, jour):
    """IDs des employés ACTIFS assignables au dispatch terrain le ``jour`` (FG165).

    Exclut tout employé ayant une demande de congé VALIDÉE couvrant ``jour`` :
    un technicien en congé ne peut pas être affecté à une intervention ce
    jour-là. Renvoie un queryset de ``DossierEmploye`` (scopé société), trié.
    """
    if company is None or jour is None:
        return DossierEmploye.objects.none()
    absents = DemandeConge.objects.filter(
        company=company,
        statut=DemandeConge.Statut.VALIDEE,
        date_debut__lte=jour,
        date_fin__gte=jour,
    ).values_list('employe_id', flat=True)
    return (
        DossierEmploye.objects
        .filter(company=company, statut=DossierEmploye.Statut.ACTIF)
        .exclude(id__in=absents)
        .order_by('nom', 'prenom')
    )


def absents_non_justifies(company, jour):
    """ZRH6 — employés ATTENDUS le ``jour`` sans pointage NI congé validé.

    Odoo « Absence management » : signale l'employé actif assignable ce
    jour-là (``employes_assignables``) qui n'a NI pointé d'arrivée NI de
    congé validé le couvrant (réutilise ``employe_absent_le``). Renvoie une
    liste de dicts ``{employe_id, matricule, nom}``. Toujours scopé société.
    """
    from .models import Pointage

    if company is None or jour is None:
        return []
    attendus = employes_assignables(company, jour)
    ont_pointe = set(
        Pointage.objects.filter(
            company=company, heure_arrivee__date=jour,
        ).values_list('employe_id', flat=True))

    resultats = []
    for employe in attendus:
        if employe.id in ont_pointe:
            continue
        if employe_absent_le(company, employe.id, jour):
            continue  # déjà exclu par employes_assignables, garde défensive.
        resultats.append({
            'employe_id': employe.id,
            'matricule': employe.matricule,
            'nom': f'{employe.nom} {employe.prenom}',
        })
    return resultats


def roster_semaine(company, lundi):
    """Affectations roster (FG169) d'une semaine donnée (du lundi au dimanche).

    Lecture cadrée société : renvoie toutes les lignes de roster dont la ``date``
    tombe dans la semaine commençant le ``lundi`` fourni (7 jours inclus). Trié
    par jour puis équipe. Queryset vide si la société ou le lundi manque.
    """
    if company is None or lundi is None:
        return AffectationRoster.objects.none()
    fin = lundi + timedelta(days=6)
    return (
        AffectationRoster.objects
        .filter(company=company, date__gte=lundi, date__lte=fin)
        .select_related('employe')
        .order_by('date', 'equipe', 'employe_id')
    )


def conflits_roster(company, date_debut=None, date_fin=None):
    """Affectations roster (FG169) en CONFLIT de congé sur une plage.

    Lecture cadrée société : ne retient que les lignes ``conflit_conge=True``
    (technicien affecté alors qu'il a une demande de congé VALIDÉE couvrant ce
    jour). ``date_debut``/``date_fin`` bornent la plage si fournis. Sert d'alerte
    de dispatch (un planificateur revoit ces affectations). Trié par date.
    """
    if company is None:
        return AffectationRoster.objects.none()
    qs = AffectationRoster.objects.filter(company=company, conflit_conge=True)
    if date_debut is not None:
        qs = qs.filter(date__gte=date_debut)
    if date_fin is not None:
        qs = qs.filter(date__lte=date_fin)
    return qs.select_related('employe').order_by('date', 'equipe', 'employe_id')


def presences_installation(company, installation_id, date_debut=None,
                           date_fin=None, presents_seulement=False):
    """Présences chantier (FG170) d'une installation, optionnellement bornées.

    Lecture cadrée société : qui était présent sur le chantier
    ``installation_id`` (preuve litige + base facturation). ``date_debut`` /
    ``date_fin`` bornent la plage si fournis ; ``presents_seulement`` exclut les
    lignes ``ABSENT``. Trié par jour puis employé. Queryset vide si la société
    ou l'installation manque.
    """
    if company is None or installation_id is None:
        return PresenceChantier.objects.none()
    qs = PresenceChantier.objects.filter(
        company=company, installation_id=installation_id)
    if date_debut is not None:
        qs = qs.filter(date__gte=date_debut)
    if date_fin is not None:
        qs = qs.filter(date__lte=date_fin)
    if presents_seulement:
        qs = qs.exclude(statut=PresenceChantier.Statut.ABSENT)
    return qs.select_related('employe').order_by('date', 'employe_id')


def effectif_present_le(company, installation_id, jour):
    """Nombre d'employés effectivement présents sur un chantier un jour donné
    (FG170) — exclut les ABSENT. Brique de facturation/litige cadrée société ;
    renvoie 0 si la société/installation manque."""
    if company is None or installation_id is None or jour is None:
        return 0
    return PresenceChantier.objects.filter(
        company=company, installation_id=installation_id, date=jour,
    ).exclude(statut=PresenceChantier.Statut.ABSENT).count()


def compteur_incidents(company, date_debut=None, date_fin=None,
                       employe_id=None, inclure_justifies=False):
    """Compteur d'incidents de présence par employé (FG171, pilotage RH).

    Agrège les ``IncidentPresence`` (retards / absences injustifiées / départs
    anticipés) par employé sur une période. Par défaut, n'INCLUT PAS les
    incidents régularisés (``justifie=True``) — ce qui compte côté disciplinaire
    est l'injustifié ; passer ``inclure_justifies=True`` rétablit le total brut.
    Toujours scopé société. Renvoie une liste de dicts triée par employé :

    ``{
        'employe_id': int,
        'retards': int, 'absences': int, 'departs_anticipes': int,
        'total': int,
        'minutes_retard_total': int,
    }``
    """
    if company is None:
        return []
    qs = IncidentPresence.objects.filter(company=company)
    if not inclure_justifies:
        qs = qs.filter(justifie=False)
    if date_debut is not None:
        qs = qs.filter(date__gte=date_debut)
    if date_fin is not None:
        qs = qs.filter(date__lte=date_fin)
    if employe_id is not None:
        qs = qs.filter(employe_id=employe_id)
    agg = {}
    for inc in qs.only(
            'employe_id', 'type_incident', 'minutes_retard'):
        row = agg.setdefault(inc.employe_id, {
            'employe_id': inc.employe_id,
            'retards': 0, 'absences': 0, 'departs_anticipes': 0,
            'total': 0, 'minutes_retard_total': 0,
        })
        if inc.type_incident == IncidentPresence.TypeIncident.RETARD:
            row['retards'] += 1
        elif inc.type_incident == \
                IncidentPresence.TypeIncident.ABSENCE_INJUSTIFIEE:
            row['absences'] += 1
        elif inc.type_incident == \
                IncidentPresence.TypeIncident.DEPART_ANTICIPE:
            row['departs_anticipes'] += 1
        row['total'] += 1
        row['minutes_retard_total'] += inc.minutes_retard or 0
    return [agg[k] for k in sorted(agg)]


def stats_presqu_accidents(company, date_debut=None, date_fin=None,
                           statut=None):
    """Synthèse des presqu'accidents par gravité potentielle (FG182).

    Compte les ``PresquAccident`` (near-miss) de la société, ventilés par
    ``gravite_potentielle`` (faible / moyenne / élevée) — la lecture clé du
    pilotage HSE proactif (combien d'événements à risque, et à quel point ils
    auraient pu mal tourner). Bornes optionnelles ``date_debut`` / ``date_fin``
    (sur ``date_constat``) et filtre ``statut`` (ouvert / traité). Toujours scopé
    société. Renvoie un dict :

    ``{
        'total': int,
        'ouverts': int,
        'par_gravite': {'faible': int, 'moyenne': int, 'elevee': int},
    }``

    Les trois clés de gravité sont toujours présentes (à 0 par défaut) pour un
    affichage stable côté UI.
    """
    par_gravite = {
        code: 0 for code, _ in PresquAccident.GravitePotentielle.choices}
    base = {'total': 0, 'ouverts': 0, 'par_gravite': par_gravite}
    if company is None:
        return base
    qs = PresquAccident.objects.filter(company=company)
    if date_debut is not None:
        qs = qs.filter(date_constat__gte=date_debut)
    if date_fin is not None:
        qs = qs.filter(date_constat__lte=date_fin)
    if statut:
        qs = qs.filter(statut=statut)
    total = 0
    ouverts = 0
    for pa in qs.only('gravite_potentielle', 'statut'):
        total += 1
        if pa.gravite_potentielle in par_gravite:
            par_gravite[pa.gravite_potentielle] += 1
        if pa.statut == PresquAccident.Statut.OUVERT:
            ouverts += 1
    base['total'] = total
    base['ouverts'] = ouverts
    return base


def poste_appartient_societe(company, poste_id):
    """Vrai si le ``rh.Poste`` ``poste_id`` appartient à ``company`` (cross-app).

    DC17 — point d'entrée de lecture pour les modules qui référencent le
    référentiel de postes (FG160) par STRING-FK (ex. ``authentication.CustomUser
    .poste_ref``) sans importer ``rh.models`` : permet de valider qu'un Poste
    assigné est bien de la société de l'appelant. Toujours scopé société ;
    ``False`` si la société est absente ou le poste introuvable/hors société.
    """
    if company is None or poste_id is None:
        return False
    return Poste.objects.filter(company=company, pk=poste_id).exists()


def habilitations_expirantes(company, within_days=30, inclure_expirees=True,
                             employe_id=None):
    """Habilitations électriques (FG173) qui expirent bientôt ou sont expirées.

    Lecture cadrée société : retient les titres ACTIFS dont la ``date_validite``
    est renseignée et tombe au plus tard dans ``within_days`` jours
    (aujourd'hui + ``within_days`` inclus). Par défaut ``inclure_expirees`` est
    vrai : les titres déjà échus (échéance passée) sont également renvoyés, car
    une habilitation expirée est exactement ce qui doit alerter avant un
    chantier PV ; passer ``inclure_expirees=False`` ne garde que les échéances
    encore à venir dans la fenêtre. Les titres sans échéance (``date_validite``
    NULL) ou inactifs sont exclus. ``employe_id`` restreint à un employé.
    Toujours scopé société ; trié par échéance la plus proche d'abord.
    """
    if company is None:
        return Habilitation.objects.none()
    try:
        within_days = int(within_days)
    except (TypeError, ValueError):
        within_days = 30
    if within_days < 0:
        within_days = 0
    today = timezone.localdate()
    limite = today + timedelta(days=within_days)
    qs = Habilitation.objects.filter(
        company=company,
        actif=True,
        date_validite__isnull=False,
        date_validite__lte=limite,
    )
    if not inclure_expirees:
        qs = qs.filter(date_validite__gte=today)
    if employe_id is not None:
        qs = qs.filter(employe_id=employe_id)
    return qs.select_related('employe').order_by('date_validite', 'id')


def employe_a_habilitation_valide(company, employe_id, type_habilitation,
                                  today=None):
    """Vrai si l'employé détient un titre ``type_habilitation`` VALIDE (FG173).

    Brique d'affectation chantier PV : un technicien sans l'habilitation
    requise (ou dont le titre est expiré/inactif) ne devrait pas être assigné.
    Un titre est valide s'il est actif ET (sans échéance OU échéance non
    dépassée). Toujours scopé société ; ``False`` si la société/employé manque.
    ``today`` est injectable (défaut = date du jour) pour des évaluations
    déterministes (FG176).
    """
    if company is None or employe_id is None or not type_habilitation:
        return False
    today = today or timezone.localdate()
    from django.db.models import Q
    return Habilitation.objects.filter(
        company=company,
        employe_id=employe_id,
        type_habilitation=type_habilitation,
        actif=True,
    ).filter(
        Q(date_validite__isnull=True) | Q(date_validite__gte=today)
    ).exists()


def certifications_expirantes(company, within_days=30, inclure_expirees=True,
                              employe_id=None):
    """Certifications spécifiques (FG174) qui expirent bientôt ou sont expirées.

    Famille DISTINCTE des habilitations électriques (FG173). Lecture cadrée
    société : retient les certifications ACTIVES dont la ``date_validite`` est
    renseignée et tombe au plus tard dans ``within_days`` jours (aujourd'hui +
    ``within_days`` inclus). Par défaut ``inclure_expirees`` est vrai : les
    certifications déjà échues sont également renvoyées, car une certification
    expirée (hauteur, harnais, CACES, SST…) est exactement ce qui doit alerter
    avant un chantier PV ; passer ``inclure_expirees=False`` ne garde que les
    échéances encore à venir dans la fenêtre. Les certifications sans échéance
    (``date_validite`` NULL) ou inactives sont exclues. ``employe_id`` restreint
    à un employé. Toujours scopé société ; trié par échéance la plus proche.
    """
    if company is None:
        return Certification.objects.none()
    try:
        within_days = int(within_days)
    except (TypeError, ValueError):
        within_days = 30
    if within_days < 0:
        within_days = 0
    today = timezone.localdate()
    limite = today + timedelta(days=within_days)
    qs = Certification.objects.filter(
        company=company,
        actif=True,
        date_validite__isnull=False,
        date_validite__lte=limite,
    )
    if not inclure_expirees:
        qs = qs.filter(date_validite__gte=today)
    if employe_id is not None:
        qs = qs.filter(employe_id=employe_id)
    return qs.select_related('employe').order_by('date_validite', 'id')


def visites_medicales_expirantes(company, within_days=30, inclure_expirees=True,
                                 employe_id=None):
    """Visites médicales du travail (FG177) à renouveler bientôt ou échues.

    Famille DISTINCTE des habilitations (FG173) et certifications (FG174).
    Lecture cadrée société : retient les visites ACTIVES dont la
    ``prochaine_visite`` (échéance de renouvellement) est renseignée et tombe au
    plus tard dans ``within_days`` jours (aujourd'hui + ``within_days`` inclus).
    Par défaut ``inclure_expirees`` est vrai : les visites déjà échues sont
    également renvoyées, car une visite médicale périmée est exactement ce qui
    doit alerter avant un chantier ; passer ``inclure_expirees=False`` ne garde
    que les échéances encore à venir dans la fenêtre. Les visites sans prochaine
    échéance (``prochaine_visite`` NULL) ou inactives sont exclues.
    ``employe_id`` restreint à un employé. Toujours scopé société ; trié par
    échéance la plus proche d'abord.
    """
    if company is None:
        return VisiteMedicale.objects.none()
    try:
        within_days = int(within_days)
    except (TypeError, ValueError):
        within_days = 30
    if within_days < 0:
        within_days = 0
    today = timezone.localdate()
    limite = today + timedelta(days=within_days)
    qs = VisiteMedicale.objects.filter(
        company=company,
        actif=True,
        prochaine_visite__isnull=False,
        prochaine_visite__lte=limite,
    )
    if not inclure_expirees:
        qs = qs.filter(prochaine_visite__gte=today)
    if employe_id is not None:
        qs = qs.filter(employe_id=employe_id)
    return qs.select_related('employe').order_by('prochaine_visite', 'id')


def dotations_epi_a_renouveler(company, within_days=30, inclure_expirees=True,
                               employe_id=None):
    """Dotations EPI (FG178) dont le renouvellement approche ou est dépassé.

    Famille DISTINCTE des titres réglementaires : ici l'équipement de protection
    (casque, harnais, gants isolants, chaussures…) attribué nominativement.
    Lecture cadrée société : retient les dotations dont la
    ``date_renouvellement`` (échéance) est renseignée et tombe au plus tard dans
    ``within_days`` jours (aujourd'hui + ``within_days`` inclus). Par défaut
    ``inclure_expirees`` est vrai : les dotations déjà échues sont aussi
    renvoyées, car un EPI à remplacer est exactement ce qui doit alerter avant un
    chantier ; passer ``inclure_expirees=False`` ne garde que les échéances à
    venir. Les dotations sans échéance (``date_renouvellement`` NULL) sont
    exclues. ``employe_id`` restreint à un employé. Toujours scopé société ;
    trié par échéance la plus proche d'abord.
    """
    if company is None:
        return DotationEpi.objects.none()
    try:
        within_days = int(within_days)
    except (TypeError, ValueError):
        within_days = 30
    if within_days < 0:
        within_days = 0
    today = timezone.localdate()
    limite = today + timedelta(days=within_days)
    qs = DotationEpi.objects.filter(
        company=company,
        date_renouvellement__isnull=False,
        date_renouvellement__lte=limite,
    )
    if not inclure_expirees:
        qs = qs.filter(date_renouvellement__gte=today)
    if employe_id is not None:
        qs = qs.filter(employe_id=employe_id)
    return (qs.select_related('employe', 'epi')
            .order_by('date_renouvellement', 'id'))


def epi_a_remplacer_ou_controler(company, within_days=30, today=None,
                                 employe_id=None):
    """Dotations EPI à durée de vie : péremption OU recontrôle à venir (FG179).

    Famille DISTINCTE du simple renouvellement (``date_renouvellement``,
    FG178) : ici les EPI à DURÉE DE VIE limitée (harnais antichute, gants
    isolants…) dont la ``date_peremption`` (remplacement obligatoire) OU la
    ``date_prochain_controle`` (recontrôle périodique) — toutes deux dérivées
    de la dotation et des durées du catalogue — tombent au plus tard dans
    ``within_days`` jours (aujourd'hui + ``within_days`` inclus). Les échéances
    DÉJÀ dépassées sont incluses : un EPI périmé ou en retard de contrôle est
    exactement ce qui doit alerter avant un chantier.

    Sélecteur PUR : la date de référence est le paramètre ``today`` (par défaut
    ``timezone.localdate()``), ce qui rend le résultat déterministe/testable.
    Les dotations sans aucune des deux échéances (EPI sans durée de vie) sont
    exclues. ``employe_id`` restreint à un employé. Toujours scopé société ;
    renvoie un queryset vide si la société est absente. Trié par l'échéance la
    plus proche des deux d'abord.
    """
    if company is None:
        return DotationEpi.objects.none()
    try:
        within_days = int(within_days)
    except (TypeError, ValueError):
        within_days = 30
    if within_days < 0:
        within_days = 0
    if today is None:
        today = timezone.localdate()
    from django.db.models import Q
    limite = today + timedelta(days=within_days)
    qs = DotationEpi.objects.filter(
        Q(date_peremption__isnull=False, date_peremption__lte=limite)
        | Q(date_prochain_controle__isnull=False,
            date_prochain_controle__lte=limite),
        company=company,
    )
    if employe_id is not None:
        qs = qs.filter(employe_id=employe_id)
    return (qs.select_related('employe', 'epi')
            .order_by('date_peremption', 'date_prochain_controle', 'id'))


def echeances_rh(company, within_days=30, today=None):
    """Moteur d'échéances RH unifié (FG175) — alertes d'expiration agrégées.

    Réunit en UNE seule liste normalisée les titres/documents d'un employé qui
    arrivent à expiration (ou sont déjà expirés) dans la fenêtre ``within_days`` :

    * habilitations électriques (FG173, ``Habilitation.date_validite``) ;
    * certifications spécifiques (FG174, ``Certification.date_validite``) ;
    * documents employé pourvus d'une échéance (FG159,
      ``DocumentEmploye.date_expiration``) ;
    * visites médicales du travail (FG177,
      ``VisiteMedicale.prochaine_visite``) ;
    * dotations EPI à renouveler (FG178,
      ``DotationEpi.date_renouvellement``) ;
    * EPI à durée de vie limitée (FG179) : péremption/remplacement
      (``DotationEpi.date_peremption``) et recontrôle périodique
      (``DotationEpi.date_prochain_controle``).

    Comme les sélecteurs sous-jacents par famille, on INCLUT les échéances déjà
    dépassées (une habilitation/certification/doc/visite expiré est précisément
    ce qui doit alerter avant un chantier PV) ; on retient donc toute échéance
    ``<=`` aujourd'hui + ``within_days``. Pour les titres réglementaires
    (habilitations, certifications) et les visites médicales on ne garde que les
    lignes ACTIVES ; les documents n'ont pas de drapeau d'activité.

    Sélecteur PUR (pas d'I/O temps réel) : la date de référence est le paramètre
    ``today`` (par défaut ``timezone.localdate()``), ce qui rend le résultat
    déterministe et testable. Toujours scopé société (jamais lu du corps de
    requête) ; renvoie ``[]`` si la société est absente.

    Renvoie une liste de dicts triée par échéance la plus proche (puis type,
    employé) :

    ``{
        'type': 'habilitation' | 'certification' | 'document'
                | 'visite_medicale' | 'dotation_epi'
                | 'epi_peremption' | 'epi_controle' | 'fin_essai'
                | 'declaration_entree',
        'employe_id': int,
        'employe': str,                 # « MATRICULE — Nom Prénom »
        'libelle': str,                 # libellé lisible du titre/document
        'date_validite': date,          # échéance
        'jours_restants': int,          # négatif si déjà expiré
    }``

    XRH1 — la famille ``fin_essai`` alerte AVANT ``DossierEmploye.essai_date_fin``
    (une période d'essai qui arrive à son terme doit être confirmée ou rompue
    à temps) ; confirmer l'essai (``employes/{id}/confirmer-essai``) efface la
    date et retire l'employé de cette famille.

    XRH5 — la famille ``declaration_entree`` alerte tout embauché DONT LA
    ``date_embauche`` EST CONNUE et dont ``declaration_entree_statut =
    a_faire`` (due dès ``date_embauche``, jamais hors fenêtre — mais un
    dossier sans ``date_embauche`` renseignée n'a pas d'échéance calculable
    et est exclu) ; marquer déclaré retire l'employé de cette famille.
    """
    if company is None:
        return []
    try:
        within_days = int(within_days)
    except (TypeError, ValueError):
        within_days = 30
    if within_days < 0:
        within_days = 0
    if today is None:
        today = timezone.localdate()
    limite = today + timedelta(days=within_days)

    rows = []

    def _employe_label(emp):
        return f'{emp.matricule} — {emp.nom} {emp.prenom}'.strip()

    habilitations = (
        Habilitation.objects
        .filter(company=company, actif=True,
                date_validite__isnull=False, date_validite__lte=limite)
        .select_related('employe')
    )
    for hab in habilitations:
        rows.append({
            'type': 'habilitation',
            'employe_id': hab.employe_id,
            'employe': _employe_label(hab.employe),
            'libelle': hab.get_type_habilitation_display(),
            'date_validite': hab.date_validite,
            'jours_restants': (hab.date_validite - today).days,
        })

    certifications = (
        Certification.objects
        .filter(company=company, actif=True,
                date_validite__isnull=False, date_validite__lte=limite)
        .select_related('employe')
    )
    for cert in certifications:
        rows.append({
            'type': 'certification',
            'employe_id': cert.employe_id,
            'employe': _employe_label(cert.employe),
            'libelle': cert.get_type_certification_display(),
            'date_validite': cert.date_validite,
            'jours_restants': (cert.date_validite - today).days,
        })

    documents = (
        DocumentEmploye.objects
        .filter(company=company,
                date_expiration__isnull=False, date_expiration__lte=limite)
        .select_related('employe')
    )
    for doc in documents:
        rows.append({
            'type': 'document',
            'employe_id': doc.employe_id,
            'employe': _employe_label(doc.employe),
            'libelle': doc.get_type_document_display(),
            'date_validite': doc.date_expiration,
            'jours_restants': (doc.date_expiration - today).days,
        })

    visites = (
        VisiteMedicale.objects
        .filter(company=company, actif=True,
                prochaine_visite__isnull=False, prochaine_visite__lte=limite)
        .select_related('employe')
    )
    for vis in visites:
        rows.append({
            'type': 'visite_medicale',
            'employe_id': vis.employe_id,
            'employe': _employe_label(vis.employe),
            'libelle': f'Visite médicale ({vis.get_aptitude_display()})',
            'date_validite': vis.prochaine_visite,
            'jours_restants': (vis.prochaine_visite - today).days,
        })

    dotations = (
        DotationEpi.objects
        .filter(company=company,
                date_renouvellement__isnull=False,
                date_renouvellement__lte=limite)
        .select_related('employe', 'epi')
    )
    for dot in dotations:
        rows.append({
            'type': 'dotation_epi',
            'employe_id': dot.employe_id,
            'employe': _employe_label(dot.employe),
            'libelle': f'EPI à renouveler ({dot.epi.designation})',
            'date_validite': dot.date_renouvellement,
            'jours_restants': (dot.date_renouvellement - today).days,
        })

    # EPI à durée de vie limitée (FG179) : péremption (remplacement
    # obligatoire) et recontrôle périodique, dérivés de la dotation. Familles
    # DISTINCTES du simple renouvellement ci-dessus.
    perimables = (
        DotationEpi.objects
        .filter(company=company,
                date_peremption__isnull=False, date_peremption__lte=limite)
        .select_related('employe', 'epi')
    )
    for dot in perimables:
        rows.append({
            'type': 'epi_peremption',
            'employe_id': dot.employe_id,
            'employe': _employe_label(dot.employe),
            'libelle': f'EPI à remplacer ({dot.epi.designation})',
            'date_validite': dot.date_peremption,
            'jours_restants': (dot.date_peremption - today).days,
        })

    a_controler = (
        DotationEpi.objects
        .filter(company=company,
                date_prochain_controle__isnull=False,
                date_prochain_controle__lte=limite)
        .select_related('employe', 'epi')
    )
    for dot in a_controler:
        rows.append({
            'type': 'epi_controle',
            'employe_id': dot.employe_id,
            'employe': _employe_label(dot.employe),
            'libelle': f'EPI à recontrôler ({dot.epi.designation})',
            'date_validite': dot.date_prochain_controle,
            'jours_restants': (dot.date_prochain_controle - today).days,
        })

    # XRH1 — période d'essai en cours dont la fin approche (ou est dépassée).
    essais = (
        DossierEmploye.objects
        .filter(company=company,
                essai_date_fin__isnull=False, essai_date_fin__lte=limite)
    )
    for emp in essais:
        rows.append({
            'type': 'fin_essai',
            'employe_id': emp.id,
            'employe': _employe_label(emp),
            'libelle': "Fin de période d'essai",
            'date_validite': emp.essai_date_fin,
            'jours_restants': (emp.essai_date_fin - today).days,
        })

    # XRH5 — déclaration d'entrée CNSS/AMO non faite. Due dès l'embauche : la
    # « date_validite » est ``date_embauche``. Un dossier SANS date d'embauche
    # renseignée n'a pas d'échéance calculable et est exclu (pas de « due
    # aujourd'hui » fabriquée) — seuls les embauchés dont la date est connue
    # entrent dans cette famille.
    a_declarer = (
        DossierEmploye.objects
        .filter(
            company=company,
            date_embauche__isnull=False,
            declaration_entree_statut=(
                DossierEmploye.DeclarationEntreeStatut.A_FAIRE))
    )
    for emp in a_declarer:
        echeance = emp.date_embauche
        if echeance > limite:
            continue
        rows.append({
            'type': 'declaration_entree',
            'employe_id': emp.id,
            'employe': _employe_label(emp),
            'libelle': "Déclaration d'entrée CNSS/AMO",
            'date_validite': echeance,
            'jours_restants': (echeance - today).days,
        })

    rows.sort(key=lambda r: (r['date_validite'], r['type'], r['employe_id']))
    return rows


# Constantes des taux HSE normalisés (conventions internationales BIT/INRS).
# Taux de fréquence = accidents avec arrêt × 1 000 000 / heures travaillées.
# Taux de gravité   = journées d'arrêt × 1 000 / heures travaillées.
_TF_BASE = 1_000_000
_TG_BASE = 1_000


def tableau_bord_hse(company, within_days=30, today=None):
    """Tableau de bord HSE (FG185) — agrégation lecture seule des indicateurs.

    Réunit en UN seul dict les indicateurs de pilotage Hygiène-Sécurité-
    Environnement de la société, calculés à partir des modèles HSE du module RH
    UNIQUEMENT (aucun import d'une autre app business-core). Tout est dérivé par
    agrégation — aucun nouveau modèle, aucune écriture.

    Indicateurs renvoyés :

    * ``taux_frequence`` — taux de fréquence des accidents du travail
      (FG181, ``AccidentTravail``) = nombre d'accidents AVEC arrêt de travail
      (``arret_travail=True``) × 1 000 000, divisé par le total d'heures
      travaillées de la période (somme des ``FeuilleTemps.heures``, FG167).
      ``None`` si aucune heure travaillée n'est connue (division par zéro
      gardée) — un taux n'a pas de sens sans base d'heures.
    * ``taux_gravite`` — taux de gravité = somme des journées d'arrêt
      (``nb_jours_arret``) × 1 000, divisée par le même total d'heures
      travaillées. ``None`` si aucune heure travaillée (gardé).
    * ``heures_travaillees`` — base de calcul des deux taux (float),
      somme des ``FeuilleTemps.heures`` de la période.
    * ``accidents_total`` / ``accidents_avec_arret`` / ``jours_arret_total`` —
      compteurs bruts d'accidents du travail de la période.
    * ``presqu_accidents_total`` — nombre de presqu'accidents (near-miss,
      FG182, ``PresquAccident``) de la période.
    * ``alertes`` — comptes de titres/EPI/visites qui expirent dans la fenêtre
      ``within_days`` (ou déjà expirés) : ``habilitations`` (FG173),
      ``certifications`` (FG174), ``visites_medicales`` (FG177),
      ``epi`` (dotations à renouveler/à remplacer/à recontrôler, FG178/FG179,
      lignes distinctes décomptées), et ``total`` (somme).
    * ``incidents_par_chantier`` — liste ``[{chantier_id, nombre}]`` des
      presqu'accidents (seuls événements HSE porteurs d'un ``chantier_id``)
      regroupés par chantier, triés du plus grand au plus petit ; les
      presqu'accidents sans chantier sont regroupés sous ``chantier_id=''``.

    Sélecteur PUR (déterministe/testable) : la date de référence est le
    paramètre ``today`` (défaut ``timezone.localdate()``). ``within_days`` borne
    la période d'agrégation des accidents/presqu'accidents/heures (les
    ``within_days`` derniers jours, aujourd'hui inclus) ET la fenêtre d'alerte
    des échéances (les ``within_days`` prochains jours). Toujours scopé société
    (jamais lu du corps de requête) ; renvoie une structure entièrement à zéro
    (jamais de division par zéro) si la société est absente ou vide.
    """
    try:
        within_days = int(within_days)
    except (TypeError, ValueError):
        within_days = 30
    if within_days < 0:
        within_days = 0
    if today is None:
        today = timezone.localdate()
    debut = today - timedelta(days=within_days)
    limite_alerte = today + timedelta(days=within_days)

    vide = {
        'taux_frequence': None,
        'taux_gravite': None,
        'heures_travaillees': 0.0,
        'accidents_total': 0,
        'accidents_avec_arret': 0,
        'jours_arret_total': 0,
        'presqu_accidents_total': 0,
        'alertes': {
            'habilitations': 0,
            'certifications': 0,
            'visites_medicales': 0,
            'epi': 0,
            'total': 0,
        },
        'incidents_par_chantier': [],
        'periode_jours': within_days,
    }
    if company is None:
        return vide

    from django.db.models import Count, Sum

    # --- Accidents du travail de la période (FG181). -----------------------
    accidents = AccidentTravail.objects.filter(
        company=company, date_accident__gte=debut, date_accident__lte=today)
    acc_agg = accidents.aggregate(
        total=Count('id'),
        avec_arret=Count('id', filter=_q_arret()),
        jours=Sum('nb_jours_arret', filter=_q_arret()),
    )
    accidents_total = acc_agg['total'] or 0
    accidents_avec_arret = acc_agg['avec_arret'] or 0
    jours_arret_total = acc_agg['jours'] or 0

    # --- Heures travaillées de la période (FG167) = base des taux. ---------
    heures_agg = FeuilleTemps.objects.filter(
        company=company, date__gte=debut, date__lte=today
    ).aggregate(total=Sum('heures'))
    heures = heures_agg['total'] or 0
    heures = float(heures)

    # Taux normalisés — division par zéro GARDÉE (None si aucune heure).
    if heures > 0:
        taux_frequence = round(accidents_avec_arret * _TF_BASE / heures, 2)
        taux_gravite = round(jours_arret_total * _TG_BASE / heures, 2)
    else:
        taux_frequence = None
        taux_gravite = None

    # --- Presqu'accidents (near-miss, FG182). ------------------------------
    presqu = PresquAccident.objects.filter(
        company=company, date_constat__gte=debut, date_constat__lte=today)
    presqu_total = presqu.count()

    # Incidents HSE par chantier : le presqu'accident est le seul événement HSE
    # porteur d'un ``chantier_id`` (l'accident du travail n'a qu'un ``lieu``).
    par_chantier = (
        presqu.values('chantier_id')
        .annotate(nombre=Count('id'))
        .order_by('-nombre', 'chantier_id')
    )
    incidents_par_chantier = [
        {'chantier_id': r['chantier_id'] or '', 'nombre': r['nombre']}
        for r in par_chantier
    ]

    # --- Alertes d'expiration dans la fenêtre (réutilise les sélecteurs). --
    hab_alertes = Habilitation.objects.filter(
        company=company, actif=True,
        date_validite__isnull=False, date_validite__lte=limite_alerte
    ).count()
    cert_alertes = Certification.objects.filter(
        company=company, actif=True,
        date_validite__isnull=False, date_validite__lte=limite_alerte
    ).count()
    vis_alertes = VisiteMedicale.objects.filter(
        company=company, actif=True,
        prochaine_visite__isnull=False,
        prochaine_visite__lte=limite_alerte
    ).count()
    # EPI : renouvellement (FG178) + péremption/recontrôle (FG179). Une dotation
    # peut cumuler plusieurs échéances ; on décompte les LIGNES distinctes en
    # alerte (au moins une de leurs échéances tombe dans la fenêtre).
    epi_alertes = DotationEpi.objects.filter(
        _q_epi_echeance(limite_alerte), company=company
    ).distinct().count()
    alertes_total = hab_alertes + cert_alertes + vis_alertes + epi_alertes

    return {
        'taux_frequence': taux_frequence,
        'taux_gravite': taux_gravite,
        'heures_travaillees': round(heures, 2),
        'accidents_total': accidents_total,
        'accidents_avec_arret': accidents_avec_arret,
        'jours_arret_total': int(jours_arret_total),
        'presqu_accidents_total': presqu_total,
        'alertes': {
            'habilitations': hab_alertes,
            'certifications': cert_alertes,
            'visites_medicales': vis_alertes,
            'epi': epi_alertes,
            'total': alertes_total,
        },
        'incidents_par_chantier': incidents_par_chantier,
        'periode_jours': within_days,
    }


def _q_arret():
    """Filtre ORM : accidents AVEC arrêt de travail déclaré (FG185)."""
    from django.db.models import Q
    return Q(arret_travail=True)


def _q_epi_echeance(limite):
    """Filtre ORM : dotations EPI dont une échéance tombe dans la fenêtre.

    Couvre le renouvellement (FG178, ``date_renouvellement``) ET la péremption /
    le recontrôle à durée de vie (FG179, ``date_peremption`` /
    ``date_prochain_controle``) — toute échéance ``<= limite`` met la dotation
    en alerte.
    """
    from django.db.models import Q
    return (
        Q(date_renouvellement__isnull=False,
          date_renouvellement__lte=limite)
        | Q(date_peremption__isnull=False, date_peremption__lte=limite)
        | Q(date_prochain_controle__isnull=False,
            date_prochain_controle__lte=limite)
    )


# Garde d'affectation par habilitation (FG176) — type d'intervention → titres
# d'habilitation requis. Carte volontairement conservatrice (clés = familles de
# chantier ; valeurs = codes ``Habilitation.TypeHabilitation``) : un appelant
# (l'affectation côté installations, un autre lane) traduit son type
# d'intervention en titres requis puis appelle ``verifier_habilitation_requise``.
# « Blocage doux » : la garde RAPPORTE seulement ; l'appelant décide d'alerter
# ou de bloquer. La carte reste éditable sans migration (pure constante Python).
INTERVENTION_HABILITATIONS = {
    # Pose/raccordement BT d'une installation PV (le plus courant).
    'pose_pv_bt': ['b1v', 'br'],
    # Intervention/maintenance BT générale.
    'maintenance_bt': ['br'],
    # Consignation BT (mise hors tension avant travaux).
    'consignation_bt': ['bc'],
    # Opérations sur partie HT (poste, raccordement HT).
    'travaux_ht': ['h1v', 'h2v'],
    # Opérations spécifiques sur installation photovoltaïque.
    'operations_pv': ['bp'],
}


def habilitations_requises_pour_intervention(type_intervention):
    """Titres d'habilitation requis pour un ``type_intervention`` (FG176).

    Lecture pure de la carte ``INTERVENTION_HABILITATIONS`` : renvoie la liste
    des codes ``Habilitation.TypeHabilitation`` exigés (copie défensive), ou
    ``[]`` si le type est inconnu/absent. Aucune I/O ni société — la traduction
    type → titres ne dépend pas des données ; l'appelant passe ensuite ces codes
    à ``verifier_habilitation_requise``.
    """
    if not type_intervention:
        return []
    return list(INTERVENTION_HABILITATIONS.get(type_intervention, []))


def _classifier_habilitation(company, employe_id, type_habilitation, today):
    """Classe UN titre requis : ``'valide'`` / ``'expiree'`` / ``'manquante'``.

    Brique interne de la garde FG176, cadrée société. Réutilise la règle de
    validité de ``employe_a_habilitation_valide`` (actif ET non expiré). Quand le
    titre n'est pas valide, on distingue :

    * ``'expiree'`` — l'employé DÉTIENT bien ce titre (une ligne existe) mais il
      est inactif ou son échéance est dépassée (à recycler/renouveler) ;
    * ``'manquante'`` — aucune ligne pour ce titre (jamais obtenu).

    Cette distinction alimente les listes ``expirees`` vs ``manquantes`` du
    rapport. ``today`` est injecté pour rester déterministe/testable.
    """
    if company is None or employe_id is None or not type_habilitation:
        return 'manquante'
    if employe_a_habilitation_valide(company, employe_id, type_habilitation,
                                     today=today):
        return 'valide'
    detenu = Habilitation.objects.filter(
        company=company,
        employe_id=employe_id,
        type_habilitation=type_habilitation,
    ).exists()
    return 'expiree' if detenu else 'manquante'


def verifier_habilitation_requise(company, employe, type_requis, today=None):
    """Garde d'affectation par habilitation (FG176) — BLOCAGE DOUX.

    Étant donné un employé et un (ou plusieurs) titre(s) d'habilitation requis,
    indique si l'employé est AUTORISÉ — c.-à-d. détient chaque titre exigé,
    actif et non expiré (même règle que ``employe_a_habilitation_valide``). La
    garde se contente de RAPPORTER : l'appelant (l'affectation côté
    ``installations``, un autre lane) décide d'alerter ou de bloquer. Aucune
    écriture, aucune transition d'état.

    Paramètres
    * ``company`` — société de l'appelant (jamais lue du corps de requête) ;
    * ``employe`` — un ``DossierEmploye`` ou son ``id`` ;
    * ``type_requis`` — un code ``Habilitation.TypeHabilitation`` OU un itérable
      de codes (tous exigés). Les entrées vides/falsy sont ignorées ;
    * ``today`` — date de référence injectable (déterminisme/tests).

    Renvoie un dict :
    ``{
        'autorise': bool,        # True seulement si aucune manquante ni expirée
        'manquantes': [str],     # titres jamais obtenus (codes), triés
        'expirees': [str],       # titres détenus mais expirés/inactifs, triés
        'message': str,          # résumé lisible (français)
    }``

    Si la société ou l'employé manque, ou si ``type_requis`` est vide, renvoie un
    rapport NON autorisé avec un message explicite (on ne « valide » jamais par
    défaut une affectation que l'on ne peut pas vérifier).
    """
    if today is None:
        today = timezone.localdate()

    # Normalise ``type_requis`` en liste de codes non vides, sans doublon, ordre
    # stable. Une chaîne unique n'est PAS itérée caractère par caractère.
    if isinstance(type_requis, str):
        requis = [type_requis] if type_requis else []
    elif type_requis is None:
        requis = []
    else:
        requis = [t for t in type_requis if t]
    vus = set()
    requis = [t for t in requis if not (t in vus or vus.add(t))]

    employe_id = getattr(employe, 'pk', employe)

    if company is None or employe_id is None:
        return {
            'autorise': False,
            'manquantes': [],
            'expirees': [],
            'message': 'Vérification impossible : société ou employé manquant.',
        }
    if not requis:
        return {
            'autorise': False,
            'manquantes': [],
            'expirees': [],
            'message': 'Aucune habilitation requise précisée.',
        }

    manquantes = []
    expirees = []
    for type_habilitation in requis:
        statut = _classifier_habilitation(
            company, employe_id, type_habilitation, today)
        if statut == 'manquante':
            manquantes.append(type_habilitation)
        elif statut == 'expiree':
            expirees.append(type_habilitation)

    manquantes.sort()
    expirees.sort()
    autorise = not manquantes and not expirees

    if autorise:
        message = 'Habilitation(s) requise(s) présente(s) et valide(s).'
    else:
        parties = []
        if manquantes:
            parties.append(
                'manquante(s) : ' + ', '.join(manquantes))
        if expirees:
            parties.append(
                'expirée(s)/inactive(s) : ' + ', '.join(expirees))
        message = 'Habilitation non conforme — ' + ' ; '.join(parties) + '.'

    return {
        'autorise': autorise,
        'manquantes': manquantes,
        'expirees': expirees,
        'message': message,
    }


def registre_formation_employe(company, employe_id, today=None):
    """Registre de formation d'un employé (FG188) — historique des sessions.

    Agrège l'HISTORIQUE DE FORMATION d'un employé : toutes ses inscriptions
    (``InscriptionFormation``) avec le détail de la session liée (intitulé,
    type, organisme, dates, lieu, statut, compétence visée), sa présence et
    son résultat. La lecture est cadrée société : seules les inscriptions de
    ``company`` sont renvoyées, triées de la session la plus récente à la plus
    ancienne. ``today`` (optionnel) sert au compteur des sessions réalisées et
    n'est jamais inventé côté serveur.

    Renvoie un dict ``{employe, lignes, total, total_realisees}`` :
    ``lignes`` est une liste de dicts prête à sérialiser ; ``total`` le nombre
    d'inscriptions ; ``total_realisees`` celles dont la session est réalisée.
    Un employé d'une autre société (ou inconnu) renvoie un registre vide.
    """
    if today is None:
        today = timezone.localdate()

    inscriptions = (
        InscriptionFormation.objects
        .filter(company=company, participant_id=employe_id)
        .select_related('session', 'session__competence_visee')
        .order_by('-session__date_debut', '-session__date_creation', 'id')
    )

    lignes = []
    total_realisees = 0
    for inscr in inscriptions:
        session = inscr.session
        realisee = session.statut == SessionFormation.Statut.REALISEE
        if realisee:
            total_realisees += 1
        competence = session.competence_visee
        lignes.append({
            'inscription_id': inscr.id,
            'session_id': session.id,
            'intitule': session.intitule,
            'type': session.type,
            'type_display': session.get_type_display(),
            'organisme': session.organisme,
            'date_debut': session.date_debut,
            'date_fin': session.date_fin,
            'lieu': session.lieu,
            'cout': session.cout,
            'statut': session.statut,
            'statut_display': session.get_statut_display(),
            'realisee': realisee,
            'competence_visee': competence.id if competence else None,
            'competence_visee_libelle': competence.libelle if competence else '',
            'present': inscr.present,
            'resultat': inscr.resultat,
            'resultat_display': inscr.get_resultat_display(),
            'note': inscr.note,
        })

    return {
        'employe': employe_id,
        'lignes': lignes,
        'total': len(lignes),
        'total_realisees': total_realisees,
    }


def avances_a_deduire(company, annee, mois, employe_id=None):
    """Avances sur salaire APPROUVÉES à récupérer pour une période (FG195).

    Renvoie les avances de la société à déduire pour le mois (``annee``,
    ``mois``) — celles dont la déduction est planifiée à ce mois et qui ne sont
    pas encore déduites/refusées. Sert à l'intégration avec l'export paie
    (FG192 : alimentation des retenues mensuelles) et au module paie (PAIE28),
    qui les consomment via ce sélecteur — jamais par import croisé de models.
    Scopé société : ne renvoie jamais d'avance hors de ``company``.
    """
    qs = AvanceSalaire.objects.filter(
        company=company,
        statut=AvanceSalaire.Statut.APPROUVEE,
        annee_deduction=annee,
        mois_deduction=mois,
    ).select_related('employe')
    if employe_id:
        qs = qs.filter(employe_id=employe_id)
    return [
        {
            'id': av.id,
            'employe': av.employe_id,
            'matricule': av.employe.matricule if av.employe_id else '',
            'montant': av.montant,
            'date_demande': av.date_demande.isoformat()
            if av.date_demande else None,
        }
        for av in qs
    ]


def peut_conduire(company, employe_id, *, le=None, categorie=None):
    """Vrai si l'employé a un permis VALIDE pour conduire (FG197/FG198).

    Un employé « peut conduire » s'il détient au moins un permis (scopé
    société) dont la ``date_expiration`` est nulle (pas d'échéance) ou ≥ ``le``
    (par défaut aujourd'hui). Si ``categorie`` est fournie, seul un permis de
    cette catégorie compte. Sert de garde à l'affectation conducteur↔véhicule
    (FG198) ; scopé société (jamais d'accès hors ``company``).
    """
    from django.db.models import Q

    jour = le or timezone.localdate()
    qs = PermisConduire.objects.filter(
        company=company, employe_id=employe_id)
    if categorie:
        qs = qs.filter(categorie=categorie)
    return qs.filter(
        Q(date_expiration__isnull=True)
        | Q(date_expiration__gte=jour)
    ).exists()


def permis_expirant_bientot(company, within_days=30):
    """Permis de conduire de la société expirant dans ``within_days`` jours.

    Exclut les permis sans échéance et ceux déjà expirés. Scopé société.
    """
    try:
        within = int(within_days)
    except (TypeError, ValueError):
        within = 30
    today = timezone.localdate()
    limite = today + timedelta(days=within)
    return PermisConduire.objects.filter(
        company=company,
        date_expiration__isnull=False,
        date_expiration__gte=today,
        date_expiration__lte=limite,
    ).select_related('employe').order_by('date_expiration')


def _masse_salariale_mensuelle(company):
    """Masse salariale MENSUELLE estimée (FG200, GATED — donnée interne).

    Somme, pour chaque employé ACTIF, de sa rémunération de base en vigueur
    (la plus récente par ``date_effet``) normalisée en mensuel : un montant
    annuel ÷ 12, un horaire × 173 h, un journalier × 22 j, un mensuel tel quel.
    Donnée INTERNE (paie) : ne quitte JAMAIS une sortie client — elle n'est
    renvoyée qu'au sein de l'API RH admin-gated. Scopé société.
    """
    from decimal import Decimal

    from .models import Remuneration

    facteurs = {
        Remuneration.Periodicite.MENSUEL: Decimal('1'),
        Remuneration.Periodicite.ANNUEL: Decimal('1') / Decimal('12'),
        Remuneration.Periodicite.HORAIRE: Decimal('173'),
        Remuneration.Periodicite.JOURNALIER: Decimal('22'),
    }
    actifs = DossierEmploye.objects.filter(
        company=company, statut=DossierEmploye.Statut.ACTIF)
    total = Decimal('0')
    for emp in actifs:
        rem = (Remuneration.objects
               .filter(company=company, employe=emp)
               .order_by('-date_effet', '-date_creation')
               .first())
        if rem is None:
            continue
        facteur = facteurs.get(rem.periodicite, Decimal('1'))
        total += (rem.montant or Decimal('0')) * facteur
    return total


def motifs_depart(company, debut, fin):
    """XRH25 — répartition des motifs de départ sur ``[debut, fin]``.

    Agrège les ``EntretienSortie.motif_principal`` des employés SORTIS de la
    société dont ``date_sortie`` tombe dans la période (bornes incluses).
    Renvoie un dict ``{motif: nb}`` (motifs sans entretien de sortie renseigné
    ne sont PAS comptés — distinct du ``DossierEmploye.motif_sortie`` coarse,
    toujours disponible via le cockpit ``par_statut``). Lecture seule, société
    scopée.
    """
    from .models import EntretienSortie

    entretiens = EntretienSortie.objects.filter(
        company=company,
        employe__date_sortie__gte=debut,
        employe__date_sortie__lte=fin,
    ).exclude(motif_principal='')

    counts = {}
    for entretien in entretiens:
        counts[entretien.motif_principal] = (
            counts.get(entretien.motif_principal, 0) + 1)
    return counts


def cockpit_rh(company, *, inclure_masse_salariale=False, departement_id=None):
    """Cockpit RH — effectifs & coûts (FG200), agrégation scopée société.

    Renvoie un tableau de bord en lecture :

    * ``effectif_total`` — nombre d'employés non sortis ;
    * ``par_statut`` / ``par_contrat`` / ``par_departement`` — répartitions ;
    * ``pyramide_anciennete`` — tranches d'ancienneté (<1 an, 1-3, 3-5, 5-10,
      10+ ans) sur la base de ``date_embauche`` ;
    * ``turnover`` — entrées/sorties sur les 12 derniers mois + taux ;
    * ``alertes`` — CDD à échéance (30 j), documents/permis/visites à expirer ;
    * ``masse_salariale_mensuelle`` — UNIQUEMENT si ``inclure_masse_salariale``
      (GATED : donnée interne paie, jamais côté client).

    XRH27 — ``departement_id`` filtre le cockpit à CE département ET TOUS ses
    descendants (arbre de hiérarchie), via :func:`departements_descendants`.

    Tout est cadré société (jamais d'accès hors ``company``).
    """
    from datetime import date

    today = timezone.localdate()
    base = DossierEmploye.objects.filter(company=company)
    if departement_id:
        ids = departements_descendants(company, departement_id)
        base = base.filter(departement_id__in=ids)
    non_sortis = base.exclude(statut=DossierEmploye.Statut.SORTI)

    # Répartitions par statut / contrat.
    par_statut = {}
    for emp in base:
        par_statut[emp.statut] = par_statut.get(emp.statut, 0) + 1
    par_contrat = {}
    for emp in non_sortis:
        par_contrat[emp.type_contrat] = \
            par_contrat.get(emp.type_contrat, 0) + 1

    # Répartition par département (effectif non-sorti).
    par_departement = []
    for dep in Departement.objects.filter(company=company):
        n = non_sortis.filter(departement=dep).count()
        par_departement.append({
            'departement': dep.id, 'nom': dep.nom, 'effectif': n})
    sans_dep = non_sortis.filter(departement__isnull=True).count()
    if sans_dep:
        par_departement.append({
            'departement': None, 'nom': 'Sans département',
            'effectif': sans_dep})

    # Pyramide d'ancienneté.
    tranches = {'<1': 0, '1-3': 0, '3-5': 0, '5-10': 0, '10+': 0}
    for emp in non_sortis:
        if not emp.date_embauche:
            continue
        annees = (today - emp.date_embauche).days / 365.25
        if annees < 1:
            tranches['<1'] += 1
        elif annees < 3:
            tranches['1-3'] += 1
        elif annees < 5:
            tranches['3-5'] += 1
        elif annees < 10:
            tranches['5-10'] += 1
        else:
            tranches['10+'] += 1

    # Turnover sur 12 mois glissants.
    debut_periode = date(today.year - 1, today.month, 1)
    entrees = base.filter(date_embauche__gte=debut_periode).count()
    sorties = base.filter(
        statut=DossierEmploye.Statut.SORTI,
        date_sortie__gte=debut_periode).count()
    effectif_total = non_sortis.count()
    taux_turnover = round(
        (sorties / effectif_total * 100), 1) if effectif_total else 0.0

    # Alertes.
    dans_30 = today + timedelta(days=30)
    cdd_echeance = base.filter(
        type_contrat=DossierEmploye.TypeContrat.CDD,
        contrat_date_fin__isnull=False,
        contrat_date_fin__gte=today,
        contrat_date_fin__lte=dans_30,
    ).count()
    alertes = {
        'cdd_a_echeance': cdd_echeance,
        'documents_a_expirer': documents_expirant_bientot(
            company, within_days=30).count(),
        'permis_a_expirer': permis_expirant_bientot(
            company, within_days=30).count(),
        'visites_medicales_a_renouveler': visites_medicales_expirantes(
            company, within_days=30, inclure_expirees=False).count(),
    }

    result = {
        'effectif_total': effectif_total,
        'par_statut': par_statut,
        'par_contrat': par_contrat,
        'par_departement': par_departement,
        'pyramide_anciennete': tranches,
        'turnover': {
            'entrees_12m': entrees,
            'sorties_12m': sorties,
            'taux_pct': taux_turnover,
            # XRH25 — répartition des motifs de départ (12 mois glissants),
            # depuis les entretiens de sortie structurés (distincts du
            # ``motif_sortie`` coarse posé à l'offboarding FG161).
            'motifs_depart': motifs_depart(
                company, debut_periode, today),
        },
        'alertes': alertes,
    }
    if inclure_masse_salariale:
        result['masse_salariale_mensuelle'] = _masse_salariale_mensuelle(
            company)
    return result


def jours_fermeture_exclus(company, employe, date_debut, date_fin):
    """XRH14 — jours de ``date_debut``→``date_fin`` déjà couverts par une
    fermeture collective (chevauchant le département de l'employé, ou toute
    la société si la fermeture n'a pas de département). Renvoie l'ensemble
    des dates (``set`` de ``date``) à EXCLURE du décompte d'une nouvelle
    demande de congé qui chevauche cette période — évite le double-décompte.
    Lecture seule, société scopée.
    """
    from datetime import timedelta

    from .models import PeriodeFermeture

    fermetures = (
        PeriodeFermeture.objects
        .filter(company=company, date_debut__lte=date_fin,
                date_fin__gte=date_debut)
        .prefetch_related('departements'))

    exclues = set()
    for fermeture in fermetures:
        departements = list(fermeture.departements.all())
        if departements and employe.departement_id not in [
                d.id for d in departements]:
            continue
        debut = max(fermeture.date_debut, date_debut)
        fin = min(fermeture.date_fin, date_fin)
        jour = debut
        while jour <= fin:
            exclues.add(jour)
            jour += timedelta(days=1)
    return exclues


def ecarts_competences(employe):
    """XRH15 — écart requis-vs-actuel pour un employé, au poste de référence.

    Compare le profil requis de ``employe.poste_ref``
    (``CompetenceRequise``) au niveau réel de l'employé
    (``CompetenceEmploye``, 0 si jamais évalué). Renvoie une liste de dicts
    ``{competence_id, competence_libelle, niveau_requis, niveau_actuel,
    ecart}`` pour chaque compétence MANQUANTE ou INSUFFISANTE (niveau_actuel
    < niveau_requis) — les compétences déjà couvertes sont omises. Liste vide
    si l'employé n'a pas de ``poste_ref``. Lecture seule.
    """
    from .models import CompetenceEmploye, CompetenceRequise

    if not employe.poste_ref_id:
        return []

    requises = (
        CompetenceRequise.objects
        .filter(company=employe.company, poste=employe.poste_ref)
        .select_related('competence'))
    niveaux_actuels = dict(
        CompetenceEmploye.objects
        .filter(company=employe.company, employe=employe)
        .values_list('competence_id', 'niveau'))

    ecarts = []
    for requise in requises:
        actuel = niveaux_actuels.get(requise.competence_id, 0)
        if actuel < requise.niveau_requis:
            ecarts.append({
                'competence_id': requise.competence_id,
                'competence_libelle': requise.competence.libelle,
                'niveau_requis': requise.niveau_requis,
                'niveau_actuel': actuel,
                'ecart': requise.niveau_requis - actuel,
            })
    return ecarts


def candidats_internes(company, poste_id):
    """XRH15 — classe les employés d'un poste par COUVERTURE de son profil
    requis (décroissante). Couverture = proportion (0..1) des compétences
    requises satisfaites (``niveau_actuel >= niveau_requis``). Un poste sans
    profil requis renvoie une liste vide. Lecture seule, société scopée.
    """
    from .models import CompetenceEmploye, CompetenceRequise, DossierEmploye

    requises = list(
        CompetenceRequise.objects.filter(company=company, poste_id=poste_id))
    if not requises:
        return []

    employes = DossierEmploye.objects.filter(
        company=company, statut=DossierEmploye.Statut.ACTIF)
    resultats = []
    for employe in employes:
        competence_ids = [r.competence_id for r in requises]
        niveaux_actuels = dict(
            CompetenceEmploye.objects
            .filter(company=company, employe=employe,
                    competence_id__in=competence_ids)
            .values_list('competence_id', 'niveau'))
        satisfaites = sum(
            1 for r in requises
            if niveaux_actuels.get(r.competence_id, 0) >= r.niveau_requis)
        couverture = satisfaites / len(requises)
        resultats.append({
            'employe_id': employe.id,
            'employe_nom': f'{employe.nom} {employe.prenom}',
            'couverture_pct': round(couverture * 100, 1),
        })
    resultats.sort(key=lambda r: r['couverture_pct'], reverse=True)
    return resultats


def compa_ratio(employe):
    """XRH16 — compa-ratio de l'employé : salaire actuel vs milieu de bande
    de son poste (``GrilleSalariale`` la plus récente, ``date_effet``).

    Renvoie ``None`` si l'employé n'a pas de ``poste_ref``, pas de bande
    salariale connue, ou pas de ``Remuneration`` (salaire actuel). Sinon un
    dict ``{salaire_actuel, salaire_min, salaire_max, milieu_bande,
    compa_ratio_pct, statut}`` où ``statut`` ∈ {sous_bande, dans_bande,
    sur_bande}. Donnée SENSIBLE (paie) — gatée ``salaires_voir`` côté vue,
    JAMAIS dans un PDF ni une sortie client.
    """
    from .models import GrilleSalariale, Remuneration

    if not employe.poste_ref_id:
        return None

    grille = (
        GrilleSalariale.objects
        .filter(company=employe.company, poste=employe.poste_ref)
        .order_by('-date_effet')
        .first())
    if grille is None:
        return None

    remuneration = (
        Remuneration.objects
        .filter(company=employe.company, employe=employe)
        .order_by('-date_effet')
        .first())
    if remuneration is None:
        return None

    salaire_actuel = remuneration.montant
    milieu_bande = (grille.salaire_min + grille.salaire_max) / 2
    if milieu_bande == 0:
        return None
    ratio_pct = round(float(salaire_actuel / milieu_bande) * 100, 1)

    if salaire_actuel < grille.salaire_min:
        statut = 'sous_bande'
    elif salaire_actuel > grille.salaire_max:
        statut = 'sur_bande'
    else:
        statut = 'dans_bande'

    return {
        'salaire_actuel': salaire_actuel,
        'salaire_min': grille.salaire_min,
        'salaire_max': grille.salaire_max,
        'milieu_bande': milieu_bande,
        'compa_ratio_pct': ratio_pct,
        'statut': statut,
    }


def comparatif_candidats(company, ouverture_id):
    """XRH17 — compare les candidats d'une MÊME ouverture par la moyenne de
    leurs notes d'entretien (toutes notes, tous entretiens confondus).
    Classé décroissant. Un candidat sans note reçoit ``moyenne=None`` (en
    fin de liste). Lecture seule, société scopée.
    """
    from .models import Candidature, NoteEntretien

    candidatures = Candidature.objects.filter(
        company=company, ouverture_id=ouverture_id)

    resultats = []
    for candidature in candidatures:
        notes = NoteEntretien.objects.filter(
            company=company, entretien__candidature=candidature)
        moyennes = [
            n.moyenne_criteres for n in notes
            if n.moyenne_criteres is not None]
        moyenne = sum(moyennes) / len(moyennes) if moyennes else None
        resultats.append({
            'candidature_id': candidature.id,
            'nom': candidature.nom,
            'moyenne': round(moyenne, 2) if moyenne is not None else None,
            'nb_notes': len(moyennes),
        })
    resultats.sort(
        key=lambda r: (r['moyenne'] is None, -(r['moyenne'] or 0)))
    return resultats


def stats_recrutement(company, debut=None, fin=None):
    """XRH22 — analytics recrutement : délai d'embauche, entonnoir, sources.

    Filtre les ``Candidature`` de la société sur ``date_candidature`` dans
    ``[debut, fin]`` (bornes incluses, optionnelles — période complète si
    absentes). Renvoie un dict :

    * ``delai_embauche_moyen_jours`` — moyenne (candidat EMBAUCHÉ dans la
      période) de ``date_modification - date_candidature`` (proxy de la date
      d'embauche : le passage à l'étape ``embauche`` touche
      ``date_modification``). ``None`` si aucun embauché avec les deux dates.
    * ``entonnoir`` — dict ``{etape: nb_candidatures_ayant_atteint_ou_dépassé
      cette étape}`` sur l'ordre reçu→présélection→entretien→offre→embauché
      (une candidature à l'étape ``offre`` compte dans reçu/présélection/
      entretien/offre). ``rejete`` compté séparément, hors entonnoir.
    * ``candidatures_par_ouverture`` — liste ``{ouverture_id, intitule, nb}``.
    * ``sources`` — liste ``{source, candidatures, embauches,
      taux_embauche_pct}`` triée par taux d'embauche décroissant (division par
      zéro gardée : ``0.0`` si aucune candidature pour la source).

    Lecture seule, société scopée, pas de migration.
    """
    from .models import Candidature

    qs = Candidature.objects.filter(company=company)
    if debut:
        qs = qs.filter(date_candidature__gte=debut)
    if fin:
        qs = qs.filter(date_candidature__lte=fin)
    candidatures = list(qs.select_related('ouverture'))

    # Délai d'embauche moyen (jours) sur les candidats embauchés de la
    # période disposant des deux dates.
    delais = []
    for c in candidatures:
        if (c.etape == Candidature.Etape.EMBAUCHE
                and c.date_candidature and c.date_modification):
            delta = c.date_modification.date() - c.date_candidature
            delais.append(delta.days)
    delai_moyen = round(sum(delais) / len(delais), 1) if delais else None

    # Entonnoir : ordre des étapes et rang de chacune.
    ordre_etapes = [
        Candidature.Etape.RECU,
        Candidature.Etape.PRESELECTION,
        Candidature.Etape.ENTRETIEN,
        Candidature.Etape.OFFRE,
        Candidature.Etape.EMBAUCHE,
    ]
    rang = {etape: i for i, etape in enumerate(ordre_etapes)}
    entonnoir = {etape: 0 for etape in ordre_etapes}
    nb_rejetes = 0
    for c in candidatures:
        if c.etape == Candidature.Etape.REJETE:
            nb_rejetes += 1
            continue
        rang_candidat = rang.get(c.etape)
        if rang_candidat is None:
            continue
        for etape in ordre_etapes:
            if rang[etape] <= rang_candidat:
                entonnoir[etape] += 1
    entonnoir['rejete'] = nb_rejetes

    # Candidatures par ouverture.
    par_ouverture = {}
    for c in candidatures:
        key = c.ouverture_id
        if key not in par_ouverture:
            par_ouverture[key] = {
                'ouverture_id': key,
                'intitule': c.ouverture.intitule if c.ouverture_id else '',
                'nb': 0,
            }
        par_ouverture[key]['nb'] += 1
    candidatures_par_ouverture = sorted(
        par_ouverture.values(), key=lambda r: r['nb'], reverse=True)

    # Efficacité par source.
    par_source = {}
    for c in candidatures:
        source = c.source or ''
        if source not in par_source:
            par_source[source] = {'candidatures': 0, 'embauches': 0}
        par_source[source]['candidatures'] += 1
        if c.etape == Candidature.Etape.EMBAUCHE:
            par_source[source]['embauches'] += 1

    sources = []
    for source, data in par_source.items():
        nb_cand = data['candidatures']
        taux = round(
            (data['embauches'] / nb_cand) * 100, 1) if nb_cand else 0.0
        sources.append({
            'source': source,
            'candidatures': nb_cand,
            'embauches': data['embauches'],
            'taux_embauche_pct': taux,
        })
    sources.sort(key=lambda r: r['taux_embauche_pct'], reverse=True)

    return {
        'delai_embauche_moyen_jours': delai_moyen,
        'entonnoir': entonnoir,
        'candidatures_par_ouverture': candidatures_par_ouverture,
        'sources': sources,
    }


def _effectif_departement(company, departement_id):
    """Effectif NON-SORTI directement rattaché à ce département (hors
    descendants — l'agrégation cumulée se fait dans :func:`arbre_departements`)."""
    return DossierEmploye.objects.filter(
        company=company, departement_id=departement_id
    ).exclude(statut=DossierEmploye.Statut.SORTI).count()


def arbre_departements(company):
    """XRH27 — arbre imbriqué des départements avec effectifs par nœud.

    Renvoie une liste de nœuds RACINE (``parent`` vide), chacun
    ``{id, nom, code, effectif_propre, effectif_cumule, enfants: [...]}`` où
    ``effectif_propre`` = employés non-sortis DIRECTEMENT rattachés à ce
    département, et ``effectif_cumule`` = ``effectif_propre`` + la somme
    cumulée de TOUS les descendants (récursif). Lecture seule, société
    scopée.
    """
    departements = list(Departement.objects.filter(company=company))
    enfants_de = {}
    for d in departements:
        enfants_de.setdefault(d.parent_id, []).append(d)

    def construire(dep):
        enfants = [
            construire(e) for e in enfants_de.get(dep.id, [])]
        effectif_propre = _effectif_departement(company, dep.id)
        effectif_cumule = effectif_propre + sum(
            e['effectif_cumule'] for e in enfants)
        return {
            'id': dep.id,
            'nom': dep.nom,
            'code': dep.code,
            'effectif_propre': effectif_propre,
            'effectif_cumule': effectif_cumule,
            'enfants': enfants,
        }

    racines = enfants_de.get(None, [])
    return [construire(d) for d in racines]


def departements_descendants(company, departement_id):
    """XRH27 — ids du département donné + TOUS ses descendants (récursif).

    Utilisé par le filtre cockpit ``?departement=`` (descendant-inclusif).
    Renvoie ``[]`` si ``departement_id`` est absent/invalide.
    """
    if not departement_id:
        return []
    departements = list(Departement.objects.filter(company=company))
    enfants_de = {}
    for d in departements:
        enfants_de.setdefault(d.parent_id, []).append(d.id)

    resultat = []
    a_visiter = [int(departement_id)]
    while a_visiter:
        courant = a_visiter.pop()
        resultat.append(courant)
        a_visiter.extend(enfants_de.get(courant, []))
    return resultat


def features_risque_attrition(employe, *, today=None, within_days=90):
    """XRH31 — assemble les FEATURES d'un employé pour ``core.attrition_risk``.

    Lit UNIQUEMENT via les selectors/models de ``apps.rh`` (jamais un import
    d'app domaine dans ``core``) : ancienneté (``date_embauche``), incidents
    de présence des ``within_days`` derniers jours (retards/départs anticipés
    hors absences — ``IncidentPresence``), absences injustifiées sur la même
    fenêtre, dernière note d'évaluation (``EvaluationEmploye.note_globale``
    la plus récente), mois depuis la dernière ``Remuneration`` (augmentation),
    nombre de ``Sanction`` (toutes, non filtrées par statut annulé — une
    sanction contestée reste un signal). Renvoie un dict prêt pour
    :func:`core.attrition_risk.attrition_risk`.
    """
    from .models import EvaluationEmploye, IncidentPresence, Remuneration, Sanction

    today = today or timezone.localdate()
    debut = today - timedelta(days=within_days)

    features = {}

    if employe.date_embauche:
        jours = (today - employe.date_embauche).days
        features['seniority_months'] = round(jours / 30.44, 2)

    incidents_qs = IncidentPresence.objects.filter(
        company=employe.company, employe=employe,
        date__gte=debut, date__lte=today, justifie=False)
    features['recent_attendance_incidents'] = incidents_qs.exclude(
        type_incident=IncidentPresence.TypeIncident.ABSENCE_INJUSTIFIEE
    ).count()
    features['unplanned_absences'] = incidents_qs.filter(
        type_incident=IncidentPresence.TypeIncident.ABSENCE_INJUSTIFIEE
    ).count()

    derniere_evaluation = EvaluationEmploye.objects.filter(
        company=employe.company, employe=employe,
        note_globale__isnull=False).order_by('-date_creation').first()
    if derniere_evaluation is not None:
        features['last_evaluation_score'] = float(
            derniere_evaluation.note_globale)

    derniere_remuneration = Remuneration.objects.filter(
        company=employe.company, employe=employe
    ).order_by('-date_effet').first()
    if derniere_remuneration is not None and derniere_remuneration.date_effet:
        jours_depuis = (today - derniere_remuneration.date_effet).days
        features['months_since_last_raise'] = round(jours_depuis / 30.44, 2)

    features['sanctions_count'] = Sanction.objects.filter(
        company=employe.company, employe=employe).count()

    return features


def risque_attrition_employe(employe, *, today=None):
    """XRH31 — score de risque d'attrition d'UN employé (dict prêt UI/API).

    Assemble les features via :func:`features_risque_attrition` puis délègue
    le scoring au moteur pur ``core.attrition_risk``. Renvoie
    ``{employe_id, score, band, factors}``.
    """
    from core.attrition_risk import attrition_risk

    features = features_risque_attrition(employe, today=today)
    resultat = attrition_risk(features)
    return {
        'employe_id': employe.id,
        'score': resultat.score,
        'band': resultat.band,
        'factors': resultat.factors,
    }


def top_risque_attrition(company, *, limite=10, today=None):
    """XRH31 — top-N employés ACTIFS par risque d'attrition décroissant.

    Lecture seule, société scopée. Renvoie une liste triée
    ``[{employe_id, employe_nom, score, band}, ...]`` limitée à ``limite``.
    """
    employes = DossierEmploye.objects.filter(
        company=company, statut=DossierEmploye.Statut.ACTIF)
    resultats = []
    for employe in employes:
        r = risque_attrition_employe(employe, today=today)
        resultats.append({
            'employe_id': employe.id,
            'employe_nom': f'{employe.nom} {employe.prenom}',
            'score': r['score'],
            'band': r['band'],
        })
    resultats.sort(key=lambda r: r['score'], reverse=True)
    return resultats[:limite]


# Seuil minimal de réponses avant d'afficher un score eNPS (anonymat XRH32).
PULSE_SEUIL_ANONYMAT = 5


def score_enps_campagne(company, campagne_id):
    """XRH32 — score eNPS (%promoteurs − %détracteurs) d'une campagne pulse.

    Renvoie ``{nb_reponses, score_enps, masque}`` où ``masque=True`` (et
    ``score_enps=None``) SOUS ``PULSE_SEUIL_ANONYMAT`` réponses — protection
    d'anonymat (une poignée de réponses redeviendrait identifiable). Lecture
    seule, société scopée.
    """
    from .models import ReponsePulse

    reponses = list(ReponsePulse.objects.filter(
        company=company, campagne_id=campagne_id))
    nb = len(reponses)
    if nb < PULSE_SEUIL_ANONYMAT:
        return {'nb_reponses': nb, 'score_enps': None, 'masque': True}

    promoteurs = sum(1 for r in reponses if r.categorie == 'promoteur')
    detracteurs = sum(1 for r in reponses if r.categorie == 'detracteur')
    score = round(((promoteurs - detracteurs) / nb) * 100, 1)
    return {'nb_reponses': nb, 'score_enps': score, 'masque': False}


def rapport_conges(company, annee, employe_id=None, departement_id=None):
    """ZRH3 — rapport congés par type ET par employé (Odoo « Time Off
    Reporting by Type / by Employee »), sur les demandes VALIDÉES de l'année.

    Renvoie un dict :
    ``{'par_type': [{'type_absence_id', 'code', 'libelle', 'jours'}],
       'par_employe': [{'employe_id', 'nom', 'jours', 'par_type': {...},
                        'solde_disponible'}]}``
    ``employe_id``/``departement_id`` filtrent optionnellement. Lecture seule,
    société scopée, jamais lu du corps de requête.
    """
    from decimal import Decimal

    from .models import DemandeConge, SoldeConge

    qs = DemandeConge.objects.filter(
        company=company, statut=DemandeConge.Statut.VALIDEE,
        date_debut__year=annee,
    ).select_related('type_absence', 'employe')
    if employe_id:
        qs = qs.filter(employe_id=employe_id)
    if departement_id:
        qs = qs.filter(employe__departement_id=departement_id)

    par_type = {}
    par_employe = {}
    for demande in qs:
        jours = demande.jours or Decimal('0')
        ta = demande.type_absence
        entry_type = par_type.setdefault(ta.id, {
            'type_absence_id': ta.id, 'code': ta.code,
            'libelle': ta.libelle, 'jours': Decimal('0'),
        })
        entry_type['jours'] += jours

        emp = demande.employe
        entry_emp = par_employe.setdefault(emp.id, {
            'employe_id': emp.id, 'nom': f'{emp.nom} {emp.prenom}',
            'jours': Decimal('0'), 'par_type': {},
        })
        entry_emp['jours'] += jours
        entry_emp['par_type'][ta.code] = \
            entry_emp['par_type'].get(ta.code, Decimal('0')) + jours

    for emp_id, entry in par_employe.items():
        solde = SoldeConge.objects.filter(
            company=company, employe_id=emp_id, annee=annee).first()
        entry['solde_disponible'] = solde.disponible if solde else Decimal('0')

    return {
        'par_type': sorted(
            par_type.values(), key=lambda e: -e['jours']),
        'par_employe': sorted(
            par_employe.values(), key=lambda e: -e['jours']),
    }


def rapport_turnover(company, annee):
    """ZRH11 — rapport de rétention / turnover ANNUEL détaillé.

    DISTINCT du turnover 12 mois glissants du cockpit RH (FG200,
    :func:`cockpit_rh`) — celui-ci reste inchangé. Pour l'année civile
    ``annee`` (1er janvier -> 31 décembre), calcule :

    * ``effectif_debut`` / ``effectif_fin`` — employés déjà embauchés
      (``date_embauche`` <= borne) et pas encore sortis à cette date-là
      (``date_sortie`` absente ou postérieure) ;
    * ``par_mois`` — liste de 12 entrées ``{mois, entrees, sorties}`` ;
    * ``taux_turnover_pct`` — sorties de l'année / effectif moyen
      ((debut+fin)/2), 0 si effectif moyen nul ;
    * ``anciennete_moyenne_ans`` — ancienneté moyenne (en années) des
      employés présents à la fin de l'année (sur ``date_embauche``) ;
    * ``retention_12m_pct`` — parmi les employés embauchés durant l'année
      N-1, la part encore présente (non sortie) 12 mois après leur entrée
      (ou toujours actifs si la fenêtre n'est pas encore écoulée -> exclus
      du dénominateur tant que leurs 12 mois ne sont pas atteints à
      aujourd'hui).

    Lecture seule, société scopée, pas de migration.
    """
    from datetime import date

    from django.utils import timezone as _tz

    debut_annee = date(annee, 1, 1)
    fin_annee = date(annee, 12, 31)
    today = _tz.localdate()

    base = DossierEmploye.objects.filter(company=company)

    def present_a(d):
        # Déjà embauché à la date ``d`` ET pas encore sorti à cette date-là
        # (``date_sortie`` absente ou postérieure à ``d``).
        return base.filter(
            date_embauche__isnull=False, date_embauche__lte=d,
        ).exclude(
            date_sortie__isnull=False, date_sortie__lt=d,
        )

    effectif_debut = present_a(debut_annee).count()
    effectif_fin = present_a(min(fin_annee, today)).count()

    par_mois = []
    total_entrees = 0
    total_sorties = 0
    for m in range(1, 13):
        mois_debut = date(annee, m, 1)
        mois_fin = date(annee, m, 28)
        # Dernier jour du mois (sans dépendance externe).
        if m == 12:
            mois_fin = date(annee, 12, 31)
        else:
            mois_fin = date(annee, m + 1, 1) - timedelta(days=1)
        entrees = base.filter(
            date_embauche__gte=mois_debut, date_embauche__lte=mois_fin
        ).count()
        sorties = base.filter(
            date_sortie__gte=mois_debut, date_sortie__lte=mois_fin
        ).count()
        total_entrees += entrees
        total_sorties += sorties
        par_mois.append({
            'mois': m, 'entrees': entrees, 'sorties': sorties,
        })

    effectif_moyen = (effectif_debut + effectif_fin) / 2
    taux_turnover_pct = (
        round(total_sorties / effectif_moyen * 100, 1)
        if effectif_moyen else 0.0)

    presents_fin = present_a(min(fin_annee, today))
    anciennetes = [
        (min(fin_annee, today) - emp.date_embauche).days / 365.25
        for emp in presents_fin if emp.date_embauche
    ]
    anciennete_moyenne_ans = (
        round(sum(anciennetes) / len(anciennetes), 1)
        if anciennetes else 0.0)

    # Rétention 12 mois des embauchés de l'année N-1 : uniquement ceux dont
    # les 12 mois sont déjà écoulés à aujourd'hui (sinon on ne peut pas
    # encore juger — exclus du dénominateur).
    annee_precedente = annee - 1
    embauches_n1 = base.filter(
        date_embauche__year=annee_precedente, date_embauche__isnull=False)
    jugeables = []
    encore_presents = 0
    for emp in embauches_n1:
        jalon = emp.date_embauche + timedelta(days=365)
        if jalon > today:
            continue
        jugeables.append(emp)
        if not emp.date_sortie or emp.date_sortie > jalon:
            encore_presents += 1
    retention_12m_pct = (
        round(encore_presents / len(jugeables) * 100, 1)
        if jugeables else None)

    return {
        'annee': annee,
        'effectif_debut': effectif_debut,
        'effectif_fin': effectif_fin,
        'par_mois': par_mois,
        'entrees_total': total_entrees,
        'sorties_total': total_sorties,
        'taux_turnover_pct': taux_turnover_pct,
        'anciennete_moyenne_ans': anciennete_moyenne_ans,
        'retention_12m_pct': retention_12m_pct,
    }


def employes_par_competence(
        company, competence_id, niveau_min=0, actif=True,
        competence_ids=None):
    """ZRH17 — recherche transverse « qui maîtrise X au niveau >= N ? ».

    Renvoie les ``DossierEmploye`` de la société dont le niveau sur
    ``competence_id`` est >= ``niveau_min``, triés par niveau décroissant.
    ``actif=True`` (défaut) exclut les employés sortis. Si
    ``competence_ids`` (itérable d'IDs) est fourni en plus de
    ``competence_id``, l'INTERSECTION est requise : l'employé doit
    satisfaire ``niveau_min`` sur CHACUNE des compétences (celle passée en
    premier + celles de ``competence_ids``). Lecture seule, société scopée.
    """
    from .models import CompetenceEmploye

    toutes_competences = [competence_id]
    if competence_ids:
        toutes_competences += [
            cid for cid in competence_ids if cid != competence_id]

    base = DossierEmploye.objects.filter(company=company)
    if actif:
        base = base.exclude(statut=DossierEmploye.Statut.SORTI)

    # Niveau de l'employé sur la compétence "primaire" — sert au tri.
    niveaux_primaire = dict(
        CompetenceEmploye.objects
        .filter(
            company=company, competence_id=competence_id,
            niveau__gte=niveau_min)
        .values_list('employe_id', 'niveau'))
    qualifies_ids = set(niveaux_primaire.keys())

    # Intersection : chaque compétence supplémentaire doit aussi être
    # satisfaite par le même employé.
    for autre_id in toutes_competences[1:]:
        satisfait = set(
            CompetenceEmploye.objects
            .filter(
                company=company, competence_id=autre_id,
                niveau__gte=niveau_min)
            .values_list('employe_id', flat=True))
        qualifies_ids &= satisfait

    employes = list(base.filter(id__in=qualifies_ids))
    employes.sort(
        key=lambda e: niveaux_primaire.get(e.id, 0), reverse=True)
    return employes


def rapport_presence(
        company, date_debut, date_fin, employe_id=None,
        departement_id=None):
    """ZRH18 — rapport de présence & heures supp. par employé/département
    sur période (« Attendance reporting » Odoo).

    Pour chaque employé de la société ayant au moins un ``Pointage`` sur
    ``[date_debut, date_fin]`` (bornes incluses sur ``heure_arrivee``) :

    * ``jours_pointes`` — nombre de jours distincts pointés ;
    * ``heures_totales`` — somme des ``duree_minutes`` (arrivée->départ)
      convertie en heures (float, arrondi 2) ;
    * ``heures_supp`` — total HS validées via :func:`heures_supp_pour_paie` ;
    * ``jours_absence`` — nb d'``IncidentPresence`` de type
      ``absence_injustifiee`` NON justifiés sur la période (FG171) ;
    * ``taux_presence_pct`` — jours_pointes / jours ouvrés de la période
      (jours calendaires hors dimanche, approximation simple), borné [0,
      100].

    ``totaux_departement`` agrège les mêmes métriques par département.
    Filtres optionnels ``employe_id`` / ``departement_id`` (et ses
    descendants). Divisions par zéro gardées. Lecture seule, société
    scopée, pas de migration.
    """
    from .models import Pointage

    if company is None or date_debut is None or date_fin is None:
        return {'par_employe': [], 'totaux_departement': []}

    base_emp = DossierEmploye.objects.filter(company=company)
    if departement_id:
        ids = departements_descendants(company, departement_id)
        base_emp = base_emp.filter(departement_id__in=ids)
    if employe_id:
        base_emp = base_emp.filter(id=employe_id)

    jours_ouvres = sum(
        1 for n in range((date_fin - date_debut).days + 1)
        if (date_debut + timedelta(days=n)).weekday() != 6
    ) or 1

    hs_par_employe = {
        row['employe_id']: row['total_hs']
        for row in heures_supp_pour_paie(company, date_debut, date_fin)
    }

    par_employe = []
    for emp in base_emp:
        pointages = Pointage.objects.filter(
            company=company, employe=emp,
            heure_arrivee__date__gte=date_debut,
            heure_arrivee__date__lte=date_fin)
        jours_pointes = pointages.dates('heure_arrivee', 'day').count()
        minutes = sum(
            p.duree_minutes or 0 for p in pointages)
        jours_absence = IncidentPresence.objects.filter(
            company=company, employe=emp,
            type_incident=IncidentPresence.TypeIncident.ABSENCE_INJUSTIFIEE,
            date__gte=date_debut, date__lte=date_fin,
            justifie=False,
        ).count()
        if not jours_pointes and not jours_absence and emp.id not in hs_par_employe:
            continue
        par_employe.append({
            'employe_id': emp.id,
            'nom': f'{emp.nom} {emp.prenom}',
            'departement_id': emp.departement_id,
            'jours_pointes': jours_pointes,
            'heures_totales': round(minutes / 60, 2),
            'heures_supp': float(hs_par_employe.get(emp.id, 0)),
            'jours_absence': jours_absence,
            'taux_presence_pct': round(
                min(jours_pointes / jours_ouvres, 1.0) * 100, 1),
        })

    totaux_par_dep = {}
    for entry in par_employe:
        dep_id = entry['departement_id']
        agg = totaux_par_dep.setdefault(dep_id, {
            'departement_id': dep_id,
            'jours_pointes': 0, 'heures_totales': 0.0,
            'heures_supp': 0.0, 'jours_absence': 0,
        })
        agg['jours_pointes'] += entry['jours_pointes']
        agg['heures_totales'] += entry['heures_totales']
        agg['heures_supp'] += entry['heures_supp']
        agg['jours_absence'] += entry['jours_absence']

    for dep_id, agg in totaux_par_dep.items():
        agg['heures_totales'] = round(agg['heures_totales'], 2)
        agg['heures_supp'] = round(agg['heures_supp'], 2)
        if dep_id is not None:
            dep = Departement.objects.filter(
                company=company, id=dep_id).first()
            agg['departement_nom'] = dep.nom if dep else ''
        else:
            agg['departement_nom'] = 'Sans département'

    return {
        'par_employe': par_employe,
        'totaux_departement': sorted(
            totaux_par_dep.values(),
            key=lambda e: (e['departement_id'] is None, e['departement_nom'])),
    }


_JOURS_SEMAINE = [
    'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche',
]

DEFAULT_LOCALISATION = 'bureau'


def localisation_du_jour(company, jour):
    """ZRH16 — localisation de travail attendue de chaque employé actif de
    la société pour ``jour`` (objet ``date``).

    Pour chaque employé (hors sortis) : lit ``localisation_hebdo`` (JSON
    jour->lieu, clé absente = ``bureau`` par défaut, cf.
    :data:`DEFAULT_LOCALISATION`) pour le jour de semaine de ``jour`` ; si
    l'employé a une demande de congé VALIDÉE couvrant ``jour``, la
    localisation devient ``absent`` (prend le pas sur le réglage). Purement
    informatif — aucun impact paie/pointage. Lecture seule, société scopée.
    """
    from .models import DemandeConge

    nom_jour = _JOURS_SEMAINE[jour.weekday()]
    employes = DossierEmploye.objects.filter(
        company=company).exclude(statut=DossierEmploye.Statut.SORTI)

    en_conge_ids = set(
        DemandeConge.objects.filter(
            company=company, statut=DemandeConge.Statut.VALIDEE,
            date_debut__lte=jour, date_fin__gte=jour,
        ).values_list('employe_id', flat=True))

    resultat = []
    for emp in employes:
        if emp.id in en_conge_ids:
            lieu = 'absent'
        else:
            carte = emp.localisation_hebdo or {}
            lieu = carte.get(nom_jour) or DEFAULT_LOCALISATION
        resultat.append({
            'employe_id': emp.id,
            'nom': f'{emp.nom} {emp.prenom}',
            'jour': nom_jour,
            'localisation': lieu,
        })
    return resultat


def evolution_competences(
        company, *, employe_id=None, competence_id=None, debut=None,
        fin=None):
    """ZRH10 — rapport d'évolution des compétences (« Skills Evolution »
    Odoo) : rejoue les changements de niveau (:class:`HistoriqueCompetence`,
    écrits automatiquement à chaque upsert du niveau — voir
    ``services.enregistrer_niveau_competence``) sur une période, société
    scopée, filtrable par employé/compétence.

    Renvoie une liste de dicts ``{employe_id, employe_nom, competence_id,
    competence_libelle, ancien_niveau, nouveau_niveau, progression (bool),
    source, date}`` triée la plus récente d'abord. ``progression`` distingue
    une PROGRESSION (nouveau > ancien) d'une RÉGRESSION.
    """
    from .models import HistoriqueCompetence

    qs = HistoriqueCompetence.objects.filter(
        company=company).select_related('employe', 'competence')
    if employe_id:
        qs = qs.filter(employe_id=employe_id)
    if competence_id:
        qs = qs.filter(competence_id=competence_id)
    if debut:
        qs = qs.filter(date_creation__date__gte=debut)
    if fin:
        qs = qs.filter(date_creation__date__lte=fin)

    return [
        {
            'employe_id': h.employe_id,
            'employe_nom': f'{h.employe.nom} {h.employe.prenom}',
            'competence_id': h.competence_id,
            'competence_libelle': h.competence.libelle,
            'ancien_niveau': h.ancien_niveau,
            'nouveau_niveau': h.nouveau_niveau,
            'progression': h.nouveau_niveau > h.ancien_niveau,
            'source': h.source,
            'date': h.date_creation,
        }
        for h in qs
    ]


SEUIL_ANONYMAT_360 = 3


def synthese_feedback360(evaluation):
    """ZRH9 — synthèse agrégée des retours SOUMIS d'un feedback 360°.

    Agrège les réponses ``RetourFeedback360.reponses`` (JSON
    ``{question: note}``) des retours SOUMIS de l'évaluation : moyenne par
    critère/question. Les retours INDIVIDUELS ne sont RENVOYÉS
    qu'au-dessus du seuil d'anonymat (:data:`SEUIL_ANONYMAT_360` — au
    moins 3 répondants soumis) ; en-dessous, seule la moyenne agrégée est
    exposée (aucun retour individuel, aucun nom de répondant identifiable
    dans cette synthèse). Lecture seule.
    """
    soumis = list(
        evaluation.retours_360.filter(soumis=True))
    nb_reponses = len(soumis)
    anonymise = nb_reponses < SEUIL_ANONYMAT_360

    moyennes = {}
    compteurs = {}
    for retour in soumis:
        for question, note in (retour.reponses or {}).items():
            try:
                valeur = float(note)
            except (TypeError, ValueError):
                continue
            moyennes[question] = moyennes.get(question, 0.0) + valeur
            compteurs[question] = compteurs.get(question, 0) + 1

    moyennes_par_critere = {
        question: round(total / compteurs[question], 2)
        for question, total in moyennes.items()
    }

    result = {
        'nb_invites': evaluation.retours_360.count(),
        'nb_soumis': nb_reponses,
        'anonymise': anonymise,
        'moyennes_par_critere': moyennes_par_critere,
    }
    if not anonymise:
        result['retours'] = [
            {
                'repondant_id': r.repondant_id,
                'relation': r.relation,
                'reponses': r.reponses,
                'commentaire': r.commentaire,
            }
            for r in soumis
        ]
    return result


def causerie_securite_for_id(company, causerie_id):
    """XQHS27 — lecture fine d'une ``CauserieSecurite`` (FG183) scopée société,
    participants inclus (émargement). Point d'entrée pour un autre module
    (``qhse``, rendu PDF imprimable de la fiche d'émargement) — jamais un
    import direct de ``rh.models`` depuis l'appelant.

    Renvoie ``None`` si l'id n'existe pas ou n'appartient pas à ``company``."""
    from .models import CauserieSecurite

    return (
        CauserieSecurite.objects
        .filter(company=company, pk=causerie_id)
        .select_related('animateur')
        .prefetch_related('participants__participant')
        .first()
    )


def ribs_par_employe(company, employe_ids):
    """Mappe ``employe_id -> rib`` du dossier RH (ARC25, cross-app, lecture seule).

    Sélecteur cross-app : la paie lit le ``rib`` de RÉFÉRENCE porté par la fiche
    RH maître (``DossierEmploye.rib``) pour un groupe d'employés, SANS jamais
    importer ``rh.models`` — afin de CONTRÔLER (jamais fusionner) la cohérence
    avec le ``ProfilPaie.rib`` de paie au moment d'un run de virement. Le RIB est
    renvoyé BRUT (tel que saisi) ; la normalisation de comparaison (espaces)
    reste à la charge de l'appelant.

    Toujours scopé société. Un ``employe_id`` inconnu / hors société / hors
    ``employe_ids`` est absent du dict renvoyé (l'appelant traite ça comme « pas
    de RIB RH de référence »). Renvoie ``{}`` si la société ou la liste manque.
    """
    if company is None or not employe_ids:
        return {}
    qs = (
        DossierEmploye.objects
        .filter(company=company, id__in=list(employe_ids))
        .only('id', 'rib')
    )
    return {d.id: (d.rib or '') for d in qs}


# ── ARC40 — provider KPI pour le reporting fédéré ────────────────────────────

def kpi_effectifs_absences(company):
    """ARC40 — tuiles KPI RH normalisées pour l'endpoint reporting fédéré.

    Déclaré dans ``apps/rh/platform.py`` (surface ``kpi_providers``) et résolu
    par ``apps/reporting/reports.py::kpi_federes`` — le reporting n'importe
    JAMAIS les modèles RH, il appelle ce sélecteur (frontière inter-app).
    Chaque tuile suit la forme normalisée ``{id, label, valeur, unite?}``.
    Lecture seule, scopé société.
    """
    from datetime import date

    from .models import DemandeConge, DossierEmploye

    today = date.today()
    effectif_actif = DossierEmploye.objects.filter(
        company=company, statut=DossierEmploye.Statut.ACTIF).count()
    absences_en_cours = DemandeConge.objects.filter(
        company=company, statut=DemandeConge.Statut.VALIDEE,
        date_debut__lte=today, date_fin__gte=today).count()
    return [
        {'id': 'rh_effectif_actif', 'label': 'Effectif actif',
         'valeur': effectif_actif, 'unite': 'employés'},
        {'id': 'rh_absences_en_cours', 'label': 'Absences en cours (validées)',
         'valeur': absences_en_cours, 'unite': 'employés'},
    ]
