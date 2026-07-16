"""Services du registre des assurances & sinistres d'entreprise (NTASS).

Point d'entrée des ORCHESTRATIONS d'écriture (chatter auto-log, échéancier de
primes, propositions d'écritures comptables via ``compta.services`` — jamais
un import direct de ``compta.models``)."""
from .models import PoliceActivity

# ── NTASS3 — Chatter PoliceAssurance ────────────────────────────────────────

#: Champs de ``PoliceAssurance`` dont la transition est auto-loggée (NTASS3).
CHAMPS_SUIVIS_POLICE = {
    'statut': 'Statut',
    'date_echeance': "Date d'échéance",
    'prime_annuelle_ht': 'Prime annuelle HT',
}


def log_police_creation(police, user):
    """Journalise la création d'une police (entrée ``creation``)."""
    return PoliceActivity.objects.create(
        company=police.company, police=police,
        kind=PoliceActivity.Kind.CREATION, user=user)


def log_police_transition(police, champ, champ_label, ancienne_valeur,
                          nouvelle_valeur, user):
    """Journalise un changement de champ suivi (NTASS3)."""
    return PoliceActivity.objects.create(
        company=police.company, police=police,
        kind=PoliceActivity.Kind.MODIFICATION,
        champ=champ, champ_label=champ_label,
        ancienne_valeur='' if ancienne_valeur is None else str(ancienne_valeur),
        nouvelle_valeur='' if nouvelle_valeur is None else str(nouvelle_valeur),
        user=user)


def log_police_transitions_auto(police, valeurs_avant, user):
    """Compare l'état AVANT (``valeurs_avant``, dict champ→valeur capturé avant
    la sauvegarde) à l'état COURANT de ``police`` et loggue une entrée par
    champ suivi (``CHAMPS_SUIVIS_POLICE``) dont la valeur a changé."""
    entrees = []
    for champ, label in CHAMPS_SUIVIS_POLICE.items():
        avant = valeurs_avant.get(champ)
        apres = getattr(police, champ)
        if avant != apres:
            entrees.append(log_police_transition(
                police, champ, label, avant, apres, user))
    return entrees


def log_police_note(police, user, body):
    """Ajoute une note manuelle au chatter d'une police (NTASS3)."""
    return PoliceActivity.objects.create(
        company=police.company, police=police,
        kind=PoliceActivity.Kind.NOTE, description=body, user=user)
