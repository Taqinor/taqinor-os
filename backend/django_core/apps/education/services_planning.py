"""NTEDU21/NTEDU22 — Emploi du temps par classe : détection de conflit de
créneau et matérialisation hebdomadaire des séances.

Module dédié (comme ``services_remises``/``services_echeancier``/
``services_cantine``) : logique propre à l'emploi du temps, isolée du reste
de ``services.py``."""
from datetime import timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError


def _chevauchement(debut1, fin1, debut2, fin2):
    return debut1 < fin2 and debut2 < fin1


def verifier_conflit_creneau(creneau):
    """NTEDU21 — vérifie qu'AUCUN autre créneau ACTIF de la société ne
    chevauche ``creneau`` sur le MÊME jour ET partage sa classe, son
    enseignant (via ``matiere_classe.enseignant``) ou sa salle (si
    renseignée) — rejet EXPLICITE en amont (jamais un 500 — la base ne porte
    aucune contrainte d'exclusion), même patron que ``GrilleTarifaireViewSet.
    _guard_doublon``. Lève une ``ValidationError`` DRF nommant le conflit
    (« classe »/« enseignant »/« salle »)."""
    from .models import CreneauEmploiDuTemps

    qs = CreneauEmploiDuTemps.objects.filter(
        company=creneau.company, jour_semaine=creneau.jour_semaine, actif=True)
    if creneau.pk:
        qs = qs.exclude(pk=creneau.pk)

    enseignant_id = creneau.matiere_classe.enseignant_id
    for autre in qs.select_related('matiere_classe'):
        if not _chevauchement(
                creneau.heure_debut, creneau.heure_fin,
                autre.heure_debut, autre.heure_fin):
            continue
        if autre.classe_id == creneau.classe_id:
            raise ValidationError({'detail': (
                "Conflit de classe : cette classe a déjà un créneau sur ce "
                "jour/horaire.")})
        if enseignant_id and autre.matiere_classe.enseignant_id == enseignant_id:
            raise ValidationError({'detail': (
                "Conflit d'enseignant : cet enseignant est déjà affecté à "
                "une autre classe sur ce jour/horaire.")})
        if creneau.salle and autre.salle == creneau.salle:
            raise ValidationError({'detail': (
                "Conflit de salle : cette salle est déjà occupée sur ce "
                "jour/horaire.")})


def _lundi_semaine_prochaine(today=None):
    """Lundi de la semaine CIVILE suivante (jamais la semaine en cours)."""
    today = today or timezone.localdate()
    jours_avant_lundi = (7 - today.weekday()) % 7 or 7
    return today + timedelta(days=jours_avant_lundi)


def generer_seances_semaine(company, *, semaine_debut=None):
    """NTEDU22 — matérialise les ``Seance`` (NTEDU12) de la semaine à venir à
    partir des ``CreneauEmploiDuTemps`` ACTIFS (récurrence hebdomadaire),
    calendrier scolaire respecté (jours fériés marocains exclus via
    ``core.calendar.is_holiday`` — fondation partagée, aucun modèle
    ``JourFerieEducation`` dupliqué). Idempotent (``get_or_create`` par
    classe/matière/date/heure de début) : rejouer la génération ne duplique
    jamais une séance."""
    from core.calendar import is_holiday

    from .models import CreneauEmploiDuTemps, Seance

    semaine_debut = semaine_debut or _lundi_semaine_prochaine()
    creneaux = CreneauEmploiDuTemps.objects.filter(
        company=company, actif=True).select_related(
        'classe', 'matiere_classe__matiere', 'matiere_classe__enseignant')

    creees = []
    for creneau in creneaux:
        date_seance = semaine_debut + timedelta(days=creneau.jour_semaine)
        if is_holiday(date_seance):
            continue  # NTEDU22 — jour férié : aucune séance générée ce jour-là.
        seance, created = Seance.objects.get_or_create(
            company=company, classe=creneau.classe,
            matiere=creneau.matiere_classe.matiere.nom, date=date_seance,
            heure_debut=creneau.heure_debut,
            defaults={
                'heure_fin': creneau.heure_fin,
                'enseignant': creneau.matiere_classe.enseignant,
                'salle': creneau.salle,
            })
        if created:
            creees.append(seance)
    return creees
