"""NTEDU21/NTEDU22 — Emploi du temps par classe : détection de conflit de
créneau et matérialisation hebdomadaire des séances.

Module dédié (comme ``services_remises``/``services_echeancier``/
``services_cantine``) : logique propre à l'emploi du temps, isolée du reste
de ``services.py``."""
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
