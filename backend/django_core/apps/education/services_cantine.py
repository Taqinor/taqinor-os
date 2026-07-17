"""NTEDU25/NTEDU26 — Cantine : menus, inscriptions, alerte allergie et
facturation proratisée dans l'échéancier.

Module dédié (comme ``services_remises``/``services_echeancier``) : pas de
dépendance dure entre NTEDU8 et NTEDU25/26 (imports locaux). Aucune donnée
médicale structurée — ``Eleve.allergies`` reste un texte libre déclaratif,
comparaison SIMPLE substring (jamais de NLP)."""
from django.db.models import Q

_JOURS_LABELS = [
    'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']


# =============================================================================
# NTEDU25 — menu du jour + alerte allergie.
# =============================================================================

def eleves_cantine_du_jour(company, date):
    """NTEDU25 — élèves inscrits à la cantine CE jour (jour de semaine
    présent dans ``jours_semaine`` de leur inscription active), avec une
    alerte allergie si le menu du jour contient un allergène présent
    (comparaison texte SIMPLE, pas de NLP) dans ``Eleve.allergies``. Renvoie
    une liste de ``{'eleve': Eleve, 'alerte_allergie': bool}``."""
    from .models import InscriptionCantine, MenuCantine

    jour_label = _JOURS_LABELS[date.weekday()]
    inscriptions = InscriptionCantine.objects.filter(
        company=company, actif=True, date_debut__lte=date,
    ).filter(
        Q(date_fin__isnull=True) | Q(date_fin__gte=date),
    ).select_related('eleve')
    menu = MenuCantine.objects.filter(company=company, date=date).first()
    allergenes = [
        str(a).strip().lower() for a in ((menu.allergenes if menu else None) or [])
        if str(a).strip()]

    resultats = []
    for inscription in inscriptions:
        if jour_label not in (inscription.jours_semaine or []):
            continue
        eleve = inscription.eleve
        alerte = False
        if allergenes and eleve.allergies:
            eleve_allergies = eleve.allergies.lower()
            alerte = any(a in eleve_allergies for a in allergenes)
        resultats.append({'eleve': eleve, 'alerte_allergie': alerte})
    return resultats
