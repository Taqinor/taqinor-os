"""Services (écritures / orchestration) du module ``apps.juridique``.

FRONTIÈRE INTER-APPS — une AUTRE app qui doit écrire ici passe par une
fonction de CE fichier (jamais ``apps.juridique.models`` / ``.views``).

La numérotation des dossiers passe par ``core.numbering`` (race-safe,
plus-haut-utilisé + 1, savepoint + retry) — JAMAIS ``count() + 1``.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone


class ApprobationError(Exception):
    """Transition d'approbation refusée (message FR destiné à l'utilisateur)."""


class ApprobationInterditeError(ApprobationError):
    """NTJUR40 — l'appelant n'a pas le DROIT de décider cette étape (403).

    Distincte d'``ApprobationError`` (règle métier → 400) : ici la transition
    serait légale, c'est l'ACTEUR qui n'est pas le bon.
    """


def creer_dossier(company, *, user=None, **champs):
    """Crée un ``DossierJuridique`` avec une référence anti-collision.

    Référence ``JUR-{annee}-{seq}`` (remise à zéro ANNUELLE, padding 4) —
    ``core.numbering.create_with_reference`` gère la course entre deux
    créations simultanées (le perdant prend simplement le numéro suivant).
    La société est TOUJOURS celle passée par l'appelant (posée côté serveur).
    """
    from core.numbering import create_with_reference

    from .models import DossierJuridique

    champs.pop('company', None)
    champs.pop('reference', None)

    def _save(reference):
        return DossierJuridique.objects.create(
            company=company, reference=reference, created_by=user, **champs)

    return create_with_reference(
        DossierJuridique, 'JUR', company, _save, period='yearly')


@transaction.atomic
def creer_dossier_depuis_reclamation(company, reclamation_id, *, user=None,
                                     **overrides):
    """NTJUR6 — escalade d'une réclamation ``litiges`` en dossier juridique.

    IDEMPOTENT : si la réclamation porte déjà un ``dossier_juridique_id`` qui
    existe encore, ce dossier est RENVOYÉ tel quel — cliquer deux fois sur
    « ouvrir un dossier juridique » ne crée jamais deux dossiers.

    Frontière inter-apps respectée dans les deux sens (imports fonction-locaux
    de ``selectors``/``services``, jamais de ``models``) :
      * LECTURE de la réclamation → ``apps.litiges.selectors.reclamation_scoped``
        (scopé société : un id d'une autre société renvoie ``None``) ;
      * ÉCRITURE du lien retour → ``apps.litiges.services.lier_dossier_juridique``.

    Pré-remplissage HONNÊTE — rien n'est inventé : titre = objet de la
    réclamation, montant en jeu = montant contesté, résumé des faits =
    description. La partie adverse n'est renseignée que si l'appelant la
    fournit, ou si la réclamation pointe explicitement un client
    (``source_type='client'``, résolu via ``apps.crm.selectors.client_label``)
    — sinon elle reste VIDE, à saisir.

    Renvoie ``(dossier, cree)`` — ``cree=False`` quand le dossier existait
    déjà. Renvoie ``(None, False)`` si la réclamation n'existe pas dans cette
    société.
    """
    from apps.litiges import selectors as litiges_selectors
    from apps.litiges import services as litiges_services

    from .models import DossierJuridique

    reclamation = litiges_selectors.reclamation_scoped(company, reclamation_id)
    if reclamation is None:
        return None, False

    if reclamation.dossier_juridique_id:
        existant = DossierJuridique.objects.filter(
            company=company, pk=reclamation.dossier_juridique_id).first()
        if existant is not None:
            return existant, False

    partie_adverse = overrides.pop('partie_adverse_nom', '') or ''
    if not partie_adverse and reclamation.source_type == 'client':
        from apps.crm import selectors as crm_selectors
        partie_adverse = crm_selectors.client_label(
            company, reclamation.source_id) or ''

    champs = {
        'titre': reclamation.objet,
        'nature': DossierJuridique.Nature.CONTENTIEUX,
        'partie_adverse_nom': partie_adverse,
        'montant_en_jeu': reclamation.montant_conteste,
        'resume_faits': reclamation.description or '',
        'date_ouverture': timezone.localdate(),
    }
    champs.update({k: v for k, v in overrides.items() if v is not None})
    dossier = creer_dossier(company, user=user, **champs)
    litiges_services.lier_dossier_juridique(reclamation, dossier.id)
    return dossier, True


# ───────────────────────────────────────────────────────────────────────────
# NTJUR14 — Provision pour risque : PROPOSÉE, jamais auto-comptabilisée
#
# Patron « propose → confirme » du dépôt : AUCUNE écriture comptable ne naît
# d'un changement d'état métier. Ouvrir un dossier à fort montant en jeu, ou le
# faire avancer, ne poste RIEN — seul un appel EXPLICITE et CONFIRMÉ à
# ``proposer_provision`` déclenche ``compta.services.enregistrer_provision``.
# ───────────────────────────────────────────────────────────────────────────


class ProvisionError(Exception):
    """Proposition de provision refusée (message FR pour l'utilisateur)."""


def apercu_provision(dossier, *, montant=None, motif='', date_dotation=None):
    """Aperçu de la dotation PROPOSÉE — lecture seule, n'écrit rien.

    Sert la première moitié du geste « propose → confirme » : l'écran montre
    ce qui SERA comptabilisé avant que quiconque ne confirme.
    """
    from decimal import Decimal

    montant = (Decimal(str(montant)) if montant is not None
               else (dossier.montant_risque_estime or Decimal('0')))
    return {
        'dossier': dossier.id,
        'reference': dossier.reference,
        'nature': 'risques_charges',
        'montant': str(montant),
        'motif': motif or f'Provision pour risque — {dossier.reference}',
        'date_dotation': str(date_dotation or timezone.localdate()),
    }


@transaction.atomic
def proposer_provision(dossier, *, montant, motif='', date_dotation=None,
                       user=None):
    """Comptabilise la provision pour risque d'un dossier (NTJUR14).

    N'est JAMAIS appelée automatiquement : l'appelant (la vue) exige une
    confirmation explicite ET une permission comptable. L'écriture elle-même
    reste la responsabilité de ``apps.compta.services.enregistrer_provision``
    (import FONCTION-LOCAL : ``juridique`` n'importe aucun modèle ``compta``).

    Refuse un montant ≤ 0 et une seconde provision sur le même dossier (une
    dotation en double serait une écriture fausse, pas une commodité).
    """
    from decimal import Decimal

    from apps.compta import services as compta_services

    if dossier.provision_comptable_id:
        raise ProvisionError(
            "Ce dossier porte déjà une provision comptabilisée : passez par "
            "une reprise plutôt que par une seconde dotation.")
    try:
        montant = Decimal(str(montant))
    except (TypeError, ValueError, ArithmeticError):
        raise ProvisionError("Montant de provision invalide.")
    if montant <= 0:
        raise ProvisionError(
            "Le montant de la provision doit être strictement positif.")

    provision = compta_services.enregistrer_provision(
        dossier.company,
        nature='risques_charges',
        date_dotation=date_dotation or timezone.localdate(),
        montant=montant,
        motif=motif or f'Provision pour risque — {dossier.reference}',
        user=user,
    )
    dossier.provision_comptable_id = provision.id
    dossier.save(update_fields=['provision_comptable_id', 'updated_at'])
    return provision


# ───────────────────────────────────────────────────────────────────────────
# NTJUR19 — Workflow d'approbation des engagements de dépenses juridiques
#
# Patron IDENTIQUE à ``contrats.services`` (CONTRAT13/14) : règle la plus
# spécifique → N étapes ordonnées → décisions gardées (ordre + non-rejeu).
# Aucune décision d'étape ne touche JAMAIS ``DossierJuridique.statut``.
# ───────────────────────────────────────────────────────────────────────────


def _premiere_etape_en_attente(mandat):
    """Première étape encore ``en_attente`` (ordre ``niveau``) ou ``None``."""
    from .models import EtapeApprobationJuridique

    return (
        mandat.etapes_approbation
        .filter(statut=EtapeApprobationJuridique.Statut.EN_ATTENTE)
        .order_by('niveau', 'id')
        .first()
    )


def approbation_requise(mandat):
    """Règle d'approbation couvrant ce mandat, ou ``None`` (aucune requise).

    Le SEUIL n'est jamais codé en dur : il vient des
    ``RegleApprobationJuridique`` actives de la société (NTJUR19).
    """
    from . import selectors

    return selectors.resoudre_regle_approbation_mandat(
        mandat.company, mandat.montant_engage,
        nature_dossier=mandat.dossier.nature)


def workflow_complet(mandat):
    """``True`` si le workflow existe ET que toutes ses étapes sont approuvées."""
    from .models import EtapeApprobationJuridique

    etapes = mandat.etapes_approbation.all()
    if not etapes.exists():
        return False
    return not etapes.exclude(
        statut=EtapeApprobationJuridique.Statut.APPROUVE).exists()


@transaction.atomic
def lancer_approbation_mandat(mandat, *, approbateurs=None):
    """Instancie le workflow d'approbation d'un mandat (NTJUR19).

    Crée une ``EtapeApprobationJuridique`` par approbateur requis par la règle
    la plus spécifique, dans l'ordre, et bascule le mandat en
    ``en_approbation``. Refuse si aucune règle ne couvre le montant engagé
    (rien à approuver), si le mandat est déjà actif/clos, ou si un workflow est
    déjà en cours. Renvoie la liste ordonnée des étapes.

    ``approbateurs`` (NTJUR40, optionnel) : liste ORDONNÉE d'utilisateurs
    désignés, un par étape. Être désigné ne donne AUCUN droit par soi-même —
    l'utilisateur doit aussi porter ``juridique_approuver_engagement``.
    """
    from .models import EtapeApprobationJuridique, MandatAvocat

    if mandat.statut in (MandatAvocat.Statut.ACTIF, MandatAvocat.Statut.CLOS):
        raise ApprobationError(
            "Ce mandat est déjà actif ou clos : il n'y a plus rien à "
            "approuver.")
    if mandat.etapes_approbation.exists():
        raise ApprobationError(
            "Un workflow d'approbation est déjà lancé sur ce mandat.")
    regle = approbation_requise(mandat)
    if regle is None:
        raise ApprobationError(
            "Aucune règle d'approbation ne couvre le montant engagé de ce "
            "mandat : il peut être activé directement.")
    nombre = max(1, regle.nombre_approbateurs)
    designes = list(approbateurs or [])
    EtapeApprobationJuridique.objects.bulk_create([
        EtapeApprobationJuridique(
            company=mandat.company, mandat=mandat, regle=regle, niveau=rang,
            niveau_approbation=regle.niveau_approbation,
            approbateur_designe=(
                designes[rang - 1] if rang <= len(designes) else None),
            statut=EtapeApprobationJuridique.Statut.EN_ATTENTE)
        for rang in range(1, nombre + 1)
    ])
    mandat.statut = MandatAvocat.Statut.EN_APPROBATION
    mandat.save(update_fields=['statut', 'updated_at'])
    return list(mandat.etapes_approbation.order_by('niveau', 'id'))


def _decider_etape(etape, *, statut_cible, approbateur=None, commentaire=''):
    """Applique une décision GARDÉE (ordre + non-rejeu) sur une étape."""
    from .models import EtapeApprobationJuridique

    if etape.statut != EtapeApprobationJuridique.Statut.EN_ATTENTE:
        raise ApprobationError("Cette étape d'approbation a déjà été décidée.")
    # NTJUR40 — une étape NOMMÉE n'est décidable que par son désigné (en plus
    # de la permission de rôle, vérifiée côté vue avant d'arriver ici).
    if (etape.approbateur_designe_id
            and approbateur is not None
            and etape.approbateur_designe_id != getattr(
                approbateur, 'pk', None)):
        raise ApprobationInterditeError(
            "Cette étape est réservée à son approbateur désigné.")
    premiere = _premiere_etape_en_attente(etape.mandat)
    if premiere is not None and premiere.pk != etape.pk:
        raise ApprobationError(
            "Une étape d'approbation antérieure est encore en attente.")
    etape.statut = statut_cible
    etape.approbateur = approbateur
    etape.decision_le = timezone.now()
    if commentaire:
        etape.commentaire = commentaire
    etape.save(update_fields=[
        'statut', 'approbateur', 'decision_le', 'commentaire', 'updated_at'])
    return etape


@transaction.atomic
def approuver_etape(etape, *, approbateur=None, commentaire=''):
    """Approuve une étape ; n'ACTIVE jamais le mandat toute seule (NTJUR19).

    L'activation reste un geste explicite (``mandats/{id}/activer``) : le
    workflow ne fait que lever le verrou.
    """
    from .models import EtapeApprobationJuridique

    return _decider_etape(
        etape, statut_cible=EtapeApprobationJuridique.Statut.APPROUVE,
        approbateur=approbateur, commentaire=commentaire)


@transaction.atomic
def rejeter_etape(etape, *, approbateur=None, commentaire=''):
    """Rejette une étape : le mandat retombe en ``brouillon`` (non activable)."""
    from .models import EtapeApprobationJuridique, MandatAvocat

    etape = _decider_etape(
        etape, statut_cible=EtapeApprobationJuridique.Statut.REJETE,
        approbateur=approbateur, commentaire=commentaire)
    mandat = etape.mandat
    if mandat.statut == MandatAvocat.Statut.EN_APPROBATION:
        mandat.statut = MandatAvocat.Statut.BROUILLON
        mandat.save(update_fields=['statut', 'updated_at'])
    return etape


@transaction.atomic
def activer_mandat(mandat):
    """Passe un mandat à ``actif`` — GARDÉ par le workflow d'approbation.

    Un mandat dont le montant engagé est couvert par une règle d'approbation
    ne peut PAS devenir actif tant que toutes les étapes ne sont pas
    approuvées (critère d'acceptation NTJUR19 : un mandat à 150 000 MAD
    au-dessus du seuil reste bloqué). Sans règle couvrante, l'activation est
    directe.
    """
    from .models import MandatAvocat

    if mandat.statut == MandatAvocat.Statut.CLOS:
        raise ApprobationError(
            "Ce mandat est clos : il ne peut plus être activé.")
    if mandat.statut == MandatAvocat.Statut.ACTIF:
        return mandat
    if (approbation_requise(mandat) is not None
            and not workflow_complet(mandat)):
        raise ApprobationError(
            "Ce mandat dépasse le seuil d'engagement juridique : il doit être "
            "approuvé avant activation.")
    mandat.statut = MandatAvocat.Statut.ACTIF
    mandat.save(update_fields=['statut', 'updated_at'])
    return mandat
