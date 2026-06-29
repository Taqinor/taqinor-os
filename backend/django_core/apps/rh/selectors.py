"""Sélecteurs (lectures) des Ressources humaines.

Lectures cadrées société : chaque sélecteur exige la ``company`` de l'appelant
et ne renvoie jamais de données hors de sa société.
"""
from datetime import timedelta

from django.utils import timezone

from .models import (
    DemandeConge,
    DocumentEmploye,
    DossierEmploye,
    FeuilleTemps,
    HeuresSupp,
    Poste,
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
