"""NTEDU25/NTEDU26 — Cantine : menus, inscriptions, alerte allergie et
facturation proratisée dans l'échéancier.

Module dédié (comme ``services_remises``/``services_echeancier``) : pas de
dépendance dure entre NTEDU8 et NTEDU25/26 (imports locaux). Aucune donnée
médicale structurée — ``Eleve.allergies`` reste un texte libre déclaratif,
comparaison SIMPLE substring (jamais de NLP)."""
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Q

JOURS_SEMAINE_PLEIN = 5
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


# =============================================================================
# NTEDU26 — facturation cantine proratisée dans l'échéancier.
# =============================================================================

def inscription_cantine_active(eleve, annee_scolaire):
    """InscriptionCantine ACTIVE de ``eleve`` qui chevauche la période de
    ``annee_scolaire`` — la plus récente si plusieurs (cas normalement
    unique)."""
    from .models import InscriptionCantine

    return InscriptionCantine.objects.filter(
        eleve=eleve, actif=True, date_debut__lte=annee_scolaire.date_fin,
    ).filter(
        Q(date_fin__isnull=True) | Q(date_fin__gte=annee_scolaire.date_debut),
    ).order_by('-date_debut').first()


def montant_cantine_mensuel(eleve, annee_scolaire):
    """NTEDU26 — montant mensuel cantine PRORATISÉ (``cantine_mensuelle ×
    jours_semaine/5`` — règle simple du plan) si ``eleve`` a une inscription
    cantine active pour cette année scolaire, sinon ``Decimal('0')``. Une
    inscription 2 jours/semaine facture 2/5 du tarif mensuel plein, JAMAIS le
    tarif complet."""
    from .models import GrilleTarifaire

    inscription = inscription_cantine_active(eleve, annee_scolaire)
    if inscription is None or eleve.classe is None:
        return Decimal('0')

    grille = GrilleTarifaire.objects.filter(
        annee_scolaire=annee_scolaire, niveau=eleve.classe.niveau,
        active=True).first()
    if grille is None or not grille.cantine_mensuelle:
        return Decimal('0')

    jours = len(inscription.jours_semaine or [])
    if jours <= 0:
        return Decimal('0')
    ratio = Decimal(min(jours, JOURS_SEMAINE_PLEIN)) / Decimal(JOURS_SEMAINE_PLEIN)
    return (grille.cantine_mensuelle * ratio).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)


def resynchroniser_lignes_futures_cantine(eleve):
    """NTEDU26 — recalcule la composante cantine des lignes d'échéance
    FUTURES (statut ``a_venir`` UNIQUEMENT) de TOUS les échéanciers de
    ``eleve`` — à appeler à la création/mise à jour/désactivation d'une
    ``InscriptionCantine``. JAMAIS rétroactif : une ligne déjà ``facturee``/
    ``payee``/``en_retard`` garde son montant historique même si
    l'inscription change en cours d'année (retirer un élève de la cantine ne
    modifie jamais la facture déjà émise, seulement les mois suivants)."""
    from .models import EcheancierScolarite, LigneEcheance

    for echeancier in EcheancierScolarite.objects.filter(eleve=eleve):
        nouveau_cantine = montant_cantine_mensuel(eleve, echeancier.annee_scolaire)
        lignes = echeancier.lignes.filter(statut=LigneEcheance.Statut.A_VENIR)
        montant_total_delta = Decimal('0')
        for ligne in lignes:
            if ligne.cantine_montant == nouveau_cantine:
                continue
            montant_total_delta += nouveau_cantine - ligne.cantine_montant
            ligne.montant = ligne.montant - ligne.cantine_montant + nouveau_cantine
            ligne.cantine_montant = nouveau_cantine
            ligne.save(update_fields=['montant', 'cantine_montant'])
        if montant_total_delta:
            echeancier.montant_total = echeancier.montant_total + montant_total_delta
            echeancier.save(update_fields=['montant_total'])
