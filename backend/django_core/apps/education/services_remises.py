"""NTEDU7 — remises fratrie/bourse.

Module dédié (plutôt qu'ajouté à ``services.py``) pour que ``services.
_apres_validation_inscription`` puisse s'y brancher par un import local
optionnel (``try/except ImportError``) sans dépendance dure entre NTEDU3 et
NTEDU7."""
from decimal import Decimal


def detecter_remise_fratrie(eleve, annee_scolaire, *, taux=None):
    """NTEDU7 — si ``eleve`` est le 2e enfant (ou plus) ACTIVEMENT inscrit de
    sa famille, propose une remise fratrie en ``brouillon`` — jamais
    auto-appliquée sans validation (``Remise.statut='brouillon'`` par
    défaut). No-op si une remise fratrie ``brouillon``/``approuvee`` existe
    déjà pour cette famille sur cette année scolaire (idempotent)."""
    from .models import Remise

    famille = eleve.famille
    enfants_actifs = list(famille.enfants_actifs)
    if len(enfants_actifs) < 2:
        return None

    deja = Remise.objects.filter(
        famille=famille, type=Remise.Type.FRATRIE,
        valable_annee_scolaire=annee_scolaire,
        statut__in=[Remise.Statut.BROUILLON, Remise.Statut.APPROUVEE],
    ).first()
    if deja is not None:
        return deja

    taux_defaut = _taux_fratrie_par_defaut(eleve.company)
    return Remise.objects.create(
        company=eleve.company,
        famille=famille,
        type=Remise.Type.FRATRIE,
        mode=Remise.Mode.POURCENTAGE,
        valeur=taux if taux is not None else taux_defaut,
        motif=(
            f"Détection automatique : {len(enfants_actifs)} enfants "
            f"inscrits actifs dans la famille {famille.nom}."),
        valable_annee_scolaire=annee_scolaire,
        statut=Remise.Statut.BROUILLON,
    )


def _taux_fratrie_par_defaut(company):
    """Taux paramétrable par société — 10% par défaut tant qu'aucun réglage
    dédié n'existe (le paramétrage fin vit dans ``parametres``, hors
    périmètre de cette tâche)."""
    return Decimal('10')


def montant_remises_approuvees(eleve, annee_scolaire, montant_base):
    """Somme des remises ``approuvee`` (jamais ``brouillon``) applicables à
    ``eleve`` (directement ou via sa famille) pour ``annee_scolaire`` —
    consommé par NTEDU8 lors de la génération de l'échéancier."""
    from .models import Remise

    remises = Remise.objects.filter(
        valable_annee_scolaire=annee_scolaire, statut=Remise.Statut.APPROUVEE,
    ).filter(_q_famille_ou_eleve(eleve))

    total = Decimal('0')
    for remise in remises:
        if remise.mode == Remise.Mode.POURCENTAGE:
            total += montant_base * (remise.valeur / Decimal('100'))
        else:
            total += remise.valeur
    return total, list(remises)


def _q_famille_ou_eleve(eleve):
    from django.db.models import Q

    return Q(eleve=eleve) | Q(famille=eleve.famille)
