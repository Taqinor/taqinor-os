"""Sélecteurs (lectures) des Ressources humaines.

Lectures cadrées société : chaque sélecteur exige la ``company`` de l'appelant
et ne renvoie jamais de données hors de sa société.
"""
from datetime import timedelta

from django.utils import timezone

from .models import (
    AffectationRoster,
    Certification,
    DemandeConge,
    DocumentEmploye,
    DossierEmploye,
    DotationEpi,
    FeuilleTemps,
    Habilitation,
    HeuresSupp,
    IncidentPresence,
    Poste,
    PresenceChantier,
    VisiteMedicale,
)


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
      ``DotationEpi.date_renouvellement``).

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
                | 'visite_medicale' | 'dotation_epi',
        'employe_id': int,
        'employe': str,                 # « MATRICULE — Nom Prénom »
        'libelle': str,                 # libellé lisible du titre/document
        'date_validite': date,          # échéance
        'jours_restants': int,          # négatif si déjà expiré
    }``
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

    rows.sort(key=lambda r: (r['date_validite'], r['type'], r['employe_id']))
    return rows


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
