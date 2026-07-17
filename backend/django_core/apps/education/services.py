"""Services métier de l'app éducation (``apps.education``).

Toute logique qui touche plusieurs modèles (numérotation, workflow
d'inscription, remises, échéancier, notifications) vit ici — jamais dans les
viewsets/serializers. Les intégrations cross-app (``ged``, ``notifications``,
``ventes``, ``core.events``) passent par des imports LOCAUX à la fonction qui
en a besoin, jamais un import module-level (évite les cycles + respecte la
frontière cross-app : lecture via ``selectors.py``, écriture via
``services.py`` de l'app CIBLE).
"""
from django.db import transaction
from django.utils import timezone


# =============================================================================
# NTEDU2 — numérotation dossier élève (jamais un count()+1).
# =============================================================================

def attribuer_numero_dossier(eleve):
    """Pose ``eleve.numero_dossier`` (anti-collision, plus-haut-utilisé+1 par
    société) via le service de numérotation de fondation ``core.numbering``.
    No-op si déjà posé (idempotent)."""
    if eleve.numero_dossier:
        return eleve
    from core.numbering import next_reference

    from .models import Eleve

    eleve.numero_dossier = next_reference(
        Eleve, 'ELV', eleve.company, padding=5, period='none',
        field='numero_dossier')
    eleve.save(update_fields=['numero_dossier'])
    return eleve


# =============================================================================
# NTEDU3 — workflow d'inscription (validation/affectation/liste d'attente).
# =============================================================================

def _classe_est_pleine(classe):
    return classe is not None and classe.effectif >= classe.capacite_max


def recalculer_liste_attente(classe):
    """NTEDU5 — recalcule ``position_liste_attente`` (FIFO par
    ``date_demande``) de toutes les inscriptions ``liste_attente`` d'une
    classe. TOUJOURS appelé après toute variation (nouvelle mise en liste,
    promotion, désinscription) — jamais une position figée côté client."""
    from .models import Inscription

    qs = Inscription.objects.filter(
        classe_demandee=classe, statut=Inscription.Statut.LISTE_ATTENTE,
    ).order_by('date_demande', 'id')
    for position, inscription in enumerate(qs, start=1):
        if inscription.position_liste_attente != position:
            inscription.position_liste_attente = position
            inscription.save(update_fields=['position_liste_attente'])


@transaction.atomic
def affecter_classe(inscription, classe, *, user=None):
    """NTEDU3 — affecte (ou tente d'affecter) une inscription à ``classe``.
    Si la classe est pleine, bascule automatiquement en ``liste_attente``
    avec une position recalculée (NTEDU5) — jamais un refus silencieux."""
    from .models import Inscription

    if _classe_est_pleine(classe):
        inscription.classe_demandee = classe
        inscription.classe_affectee = None
        inscription.statut = Inscription.Statut.LISTE_ATTENTE
        inscription.save(
            update_fields=['classe_demandee', 'classe_affectee', 'statut'])
        recalculer_liste_attente(classe)
        return inscription

    inscription.classe_demandee = classe
    inscription.classe_affectee = classe
    inscription.statut = Inscription.Statut.VALIDEE
    inscription.date_decision = timezone.now().date()
    if user is not None:
        inscription.decide_par = user
    inscription.save(update_fields=[
        'classe_demandee', 'classe_affectee', 'statut', 'date_decision',
        'decide_par'])
    return inscription


@transaction.atomic
def valider_inscription(inscription, *, user=None):
    """NTEDU3 — valide une inscription : affecte la classe demandée (ou
    liste d'attente si pleine), met à jour le statut de l'élève, détecte une
    remise fratrie potentielle (NTEDU7) et génère l'échéancier de scolarité
    (NTEDU8) — SANS intervention manuelle supplémentaire."""
    from .models import Eleve, Inscription

    classe = inscription.classe_demandee
    affecter_classe(inscription, classe, user=user)
    inscription.refresh_from_db()

    if inscription.statut == Inscription.Statut.VALIDEE:
        eleve = inscription.eleve
        eleve.classe = inscription.classe_affectee
        eleve.statut = Eleve.Statut.INSCRIT
        eleve.save(update_fields=['classe', 'statut'])
        _apres_validation_inscription(eleve, inscription.annee_scolaire)

    return inscription


def _apres_validation_inscription(eleve, annee_scolaire):
    """Point d'extension appelé après toute validation d'inscription.
    NTEDU7 (détection remise fratrie) et NTEDU8 (génération de l'échéancier)
    s'y branchent chacun par un import local — no-op tant qu'ils ne sont pas
    encore posés (permet à NTEDU3/NTEDU4/NTEDU5 de fonctionner seuls)."""
    try:
        from .services_remises import detecter_remise_fratrie
    except ImportError:  # pragma: no cover - module pas encore posé
        pass
    else:
        detecter_remise_fratrie(eleve, annee_scolaire)

    try:
        from .services_echeancier import generer_echeancier
    except ImportError:  # pragma: no cover - module pas encore posé
        pass
    else:
        generer_echeancier(eleve, annee_scolaire)


@transaction.atomic
def refuser_inscription(inscription, *, user=None):
    from .models import Inscription

    inscription.statut = Inscription.Statut.REFUSEE
    inscription.date_decision = timezone.now().date()
    if user is not None:
        inscription.decide_par = user
    inscription.save(update_fields=['statut', 'date_decision', 'decide_par'])
    return inscription


@transaction.atomic
def desinscrire(inscription):
    """NTEDU5 — retire un élève d'une classe (désinscription) et, si la
    classe était pleine, promeut automatiquement le suivant en liste
    d'attente."""
    from .models import Eleve, Inscription

    classe = inscription.classe_affectee or inscription.classe_demandee
    inscription.statut = Inscription.Statut.REFUSEE
    inscription.classe_affectee = None
    inscription.save(update_fields=['statut', 'classe_affectee'])

    eleve = inscription.eleve
    if eleve.classe_id == getattr(classe, 'id', None):
        eleve.classe = None
        eleve.statut = Eleve.Statut.RADIE
        eleve.save(update_fields=['classe', 'statut'])

    if classe is not None:
        promouvoir_premier_liste_attente(classe)
    return inscription


def promouvoir_premier_liste_attente(classe):
    """NTEDU5 — promeut le 1er de la liste d'attente d'une classe (position
    la plus basse) dès qu'une place se libère, et notifie la famille via
    ``notifications`` (service, jamais un import de modèle)."""
    from .models import Eleve, Inscription

    if _classe_est_pleine(classe):
        return None

    candidate = Inscription.objects.filter(
        classe_demandee=classe, statut=Inscription.Statut.LISTE_ATTENTE,
    ).order_by('position_liste_attente', 'date_demande', 'id').first()
    if candidate is None:
        return None

    candidate.classe_affectee = classe
    candidate.statut = Inscription.Statut.VALIDEE
    candidate.date_decision = timezone.now().date()
    candidate.position_liste_attente = None
    candidate.save(update_fields=[
        'classe_affectee', 'statut', 'date_decision', 'position_liste_attente'])

    eleve = candidate.eleve
    eleve.classe = classe
    eleve.statut = Eleve.Statut.INSCRIT
    eleve.save(update_fields=['classe', 'statut'])

    recalculer_liste_attente(classe)
    _notifier_promotion_liste_attente(candidate)
    return candidate


def _notifier_promotion_liste_attente(inscription):
    """Notifie la famille de la promotion (best-effort, jamais bloquant)."""
    from .models import Famille  # noqa: F401 (documentation du type attendu)

    famille = inscription.eleve.famille
    recipient = famille.parent1_whatsapp or famille.parent1_telephone
    if not recipient:
        return
    try:
        from apps.notifications.services import send_whatsapp_campaign_message
        send_whatsapp_campaign_message(
            inscription.company,
            recipient=recipient,
            body=(
                f"Bonjour {famille.parent1_nom or famille.nom}, une place "
                f"s'est libérée pour {inscription.eleve} en "
                f"{inscription.classe_affectee}. Merci de confirmer "
                "l'inscription auprès de l'administration."),
        )
    except Exception:  # pragma: no cover - défensif, best-effort
        pass


# =============================================================================
# NTEDU4 — réinscription annuelle en masse.
# =============================================================================

def reinscrire_en_masse(*, company, annee_source, annee_cible):
    """NTEDU4 — génère, pour chaque élève actif (statut ``inscrit``/
    ``reinscrit``) de ``annee_source``, une nouvelle ``Inscription`` en
    ``en_attente`` sur ``annee_cible`` avec une classe suggérée (niveau
    supérieur si ``Niveau.ordre+1`` existe). IDEMPOTENT : ne duplique jamais
    une inscription déjà créée pour le même (eleve, annee_cible) — lancer
    l'action deux fois de suite ne crée rien de plus la 2e fois."""
    from .models import Classe, Eleve, Inscription, Niveau

    eleves = Eleve.objects.filter(
        company=company,
        statut__in=[Eleve.Statut.INSCRIT, Eleve.Statut.REINSCRIT],
        classe__annee_scolaire=annee_source,
    ).select_related('classe', 'classe__niveau')

    crees = []
    deja_existantes = 0
    for eleve in eleves:
        if Inscription.objects.filter(
                eleve=eleve, annee_scolaire=annee_cible).exists():
            deja_existantes += 1
            continue

        classe_suggeree = None
        ancienne_classe = eleve.classe
        if ancienne_classe is not None:
            niveau_suivant = Niveau.objects.filter(
                company=company, ordre=ancienne_classe.niveau.ordre + 1,
            ).first()
            if niveau_suivant is not None:
                classe_suggeree = Classe.objects.filter(
                    company=company, annee_scolaire=annee_cible,
                    niveau=niveau_suivant).first()
            if classe_suggeree is None:
                # Pas de niveau supérieur (ex. dernière année du cycle) :
                # on retente le MÊME niveau sur l'année cible (redoublement/
                # défaut raisonnable), jamais un blocage silencieux.
                classe_suggeree = Classe.objects.filter(
                    company=company, annee_scolaire=annee_cible,
                    niveau=ancienne_classe.niveau).first()

        inscription = Inscription.objects.create(
            company=company,
            eleve=eleve,
            annee_scolaire=annee_cible,
            classe_demandee=classe_suggeree,
            statut=Inscription.Statut.EN_ATTENTE,
        )
        crees.append(inscription)

    return {'creees': crees, 'deja_existantes': deja_existantes}


# =============================================================================
# NTEDU15 — permission de saisie des notes (AUTH).
# =============================================================================

def peut_saisir_notes(user, matiere_classe):
    """NTEDU15 — un enseignant ne peut saisir des notes QUE sur les
    classes/matières qui lui sont assignées (``MatiereClasse.enseignant`` ==
    son ``rh.DossierEmploye``, résolu via ``user.dossier_employe`` — JAMAIS
    un import direct de ``apps.rh.models``). Un compte superuser ou palier
    Responsable/Admin (repli légacy, comme ``core.permissions.
    _user_has_or_legacy``) contourne la restriction (administration)."""
    if getattr(user, 'is_superuser', False):
        return True
    if getattr(user, 'is_responsable', False):
        return True
    dossier = getattr(user, 'dossier_employe', None)
    if dossier is None:
        return False
    return matiere_classe.enseignant_id == dossier.id
