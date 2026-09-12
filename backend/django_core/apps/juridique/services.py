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
# NTJUR2 — Machine à états PROCÉDURALE du dossier juridique
#
# Clés PROPRES au module (jamais ``STAGES.py``, règle #2 ; jamais le cycle
# Devis/Facture, règle #4). Le champ ``statut`` est en lecture seule au
# sérialiseur : il n'avance QUE par ``changer_statut`` (garde AUD515).
# ───────────────────────────────────────────────────────────────────────────


class TransitionError(Exception):
    """Transition de statut illégale (message FR destiné à l'utilisateur)."""


def _statuts():
    from .models import DossierJuridique

    return DossierJuridique.Statut


def statut_transitions():
    """Table des transitions LÉGALES : statut courant → statuts atteignables.

    Un statut ``clos_*`` est TERMINAL : il n'ouvre sur rien (un dossier clos
    ne repart pas — un nouvel épisode est un nouveau dossier).
    """
    s = _statuts()
    clos = (s.CLOS_GAGNE, s.CLOS_PERDU, s.CLOS_TRANSACTION,
            s.CLOS_DESISTEMENT)
    return {
        s.OUVERT: (s.INSTRUCTION, *clos),
        s.INSTRUCTION: (s.AUDIENCE_PROGRAMMEE, s.EN_DELIBERE, *clos),
        s.AUDIENCE_PROGRAMMEE: (s.EN_DELIBERE, s.INSTRUCTION, *clos),
        s.EN_DELIBERE: (s.JUGEMENT_RENDU, *clos),
        s.JUGEMENT_RENDU: (s.APPEL, s.EXECUTION, *clos),
        s.APPEL: (s.INSTRUCTION, s.AUDIENCE_PROGRAMMEE, s.EN_DELIBERE,
                  s.JUGEMENT_RENDU, *clos),
        s.EXECUTION: clos,
        s.CLOS_GAGNE: (),
        s.CLOS_PERDU: (),
        s.CLOS_TRANSACTION: (),
        s.CLOS_DESISTEMENT: (),
    }


def statuts_suivants(dossier):
    """Statuts légalement atteignables depuis l'état courant (lecture seule)."""
    return list(statut_transitions().get(dossier.statut, ()))


@transaction.atomic
def changer_statut(dossier_juridique, nouveau_statut, *, user=None, motif=''):
    """Applique une transition de statut GARDÉE (NTJUR2).

    Refuse toute transition hors de la table (``TransitionError`` → 400 côté
    vue) et laisse alors le dossier STRICTEMENT inchangé. Journalise le
    changement dans le chatter GÉNÉRIQUE ``records.Activity`` (ARC8 — jamais
    un énième modèle ``*Activity`` maison), auteur et société côté serveur.

    Le premier paramètre est nommé ``dossier_juridique`` à dessein : c'est ce
    qui range ``DossierJuridique`` parmi les modèles GOUVERNÉS de
    ``scripts/check_machine_etats_statut_readonly.py`` (AUD515), qui interdit
    dès lors tout sérialiseur laissant ``statut`` writable.
    """
    from apps.records import services as records_services
    from apps.records.models import Activity

    dossier = dossier_juridique
    ancien = dossier.statut
    legaux = statut_transitions().get(ancien, ())
    if nouveau_statut not in {str(v) for v in legaux}:
        raise TransitionError(
            f"Transition impossible depuis « "
            f"{dossier.get_statut_display()} » vers « {nouveau_statut} ».")
    dossier.statut = nouveau_statut
    dossier.save(update_fields=['statut', 'updated_at'])
    records_services.log_activity(
        dossier, Activity.Kind.MODIFICATION, user=user, field='statut',
        field_label='Statut', old_value=ancien, new_value=nouveau_statut,
        body=motif or '', company=dossier.company)
    return dossier


@transaction.atomic
def clore_dossier(dossier, statut_final, *, user=None, motif=''):
    """Clôt un dossier et PROPOSE (sans jamais l'appliquer) la reprise de sa
    provision — NTJUR15.

    Aucune écriture comptable n'est postée ici : la clôture ne fait que lever
    la bannière (``reprise_provision_proposee``) quand le dossier porte une
    ``provision_comptable_id``. Un dossier sans provision ne propose RIEN.
    """
    from .models import DossierJuridique

    valides = {str(s) for s in DossierJuridique.STATUTS_CLOS}
    if statut_final not in valides:
        raise TransitionError(
            "Statut de clôture invalide : choisissez gagné, perdu, "
            "transaction ou désistement.")
    dossier = changer_statut(dossier, statut_final, user=user, motif=motif)
    # NTJUR26 — la bannière n'est plus levée en dur ici : la clôture ÉMET un
    # événement, et l'abonné (``apps/juridique/receivers.py``) la lève. Le
    # seam est ainsi ouvert à ``apps.compta`` sans que ``juridique`` l'importe.
    emettre_dossier_clos(dossier, user=user)
    return dossier


def emettre_dossier_clos(dossier, *, user=None):
    """Émet ``core.events.dossier_juridique_clos`` (NTJUR26).

    Bus de signaux SYNCHRONE : les abonnés s'exécutent dans la transaction de
    la clôture, donc l'instance rendue à l'appelant porte déjà l'effet de la
    bannière. Aucun abonné ne poste d'écriture comptable — ils ne peuvent que
    PROPOSER (patron « propose → confirme »).
    """
    from core import events

    events.dossier_juridique_clos.send(
        sender=dossier.__class__,
        dossier=dossier,
        company=dossier.company,
        resultat=dossier.statut,
        montant_final=dossier.montant_en_jeu,
        user=user,
    )
    return dossier


# ───────────────────────────────────────────────────────────────────────────
# NTJUR4 / NTJUR5 / NTJUR11 — échéancier procédural et honoraires
# ───────────────────────────────────────────────────────────────────────────


def calculer_date_limite(company, date_declenchement, duree_jours):
    """Date limite d'un délai procédural, en jours OUVRÉS (NTJUR4).

    Réutilise ``apps.notifications.calendar_utils.ajouter_jours_ouvres``
    (import fonction-local) : week-ends ET jours fériés de la société sont
    sautés — un férié dans la fenêtre décale donc la date limite. Aucune
    logique de calendrier n'est réécrite ici.
    """
    from apps.notifications import calendar_utils

    return calendar_utils.ajouter_jours_ouvres(
        date_declenchement, int(duree_jours or 0), company)


@transaction.atomic
def reporter_audience(audience, nouvelle_date, *, heure=None,
                      juridiction_salle=None, motif=''):
    """Reporte une audience : l'ancienne devient ``reportee``, une NOUVELLE
    ligne est créée (NTJUR5) — jamais de suppression, jamais d'écrasement.

    Renvoie la nouvelle audience. Refuse de reporter une audience déjà tenue
    ou annulée (son histoire est close).
    """
    from .models import Audience

    if audience.statut in (Audience.Statut.TENUE, Audience.Statut.ANNULEE):
        raise TransitionError(
            "Une audience déjà tenue ou annulée ne peut plus être reportée.")
    if not nouvelle_date:
        raise TransitionError("Indiquez la nouvelle date d'audience.")
    nouvelle = Audience.objects.create(
        company=audience.company,
        dossier=audience.dossier,
        date_audience=nouvelle_date,
        heure=heure if heure is not None else audience.heure,
        juridiction_salle=(juridiction_salle
                           if juridiction_salle is not None
                           else audience.juridiction_salle),
        type_audience=audience.type_audience,
        statut=Audience.Statut.PROGRAMMEE,
        reporte_depuis=audience,
    )
    audience.statut = Audience.Statut.REPORTEE
    if motif:
        audience.resultat = (
            f'{audience.resultat}\nReport : {motif}'.strip())
    audience.save(update_fields=['statut', 'resultat', 'updated_at'])
    return nouvelle


def creer_note_honoraires(mandat, **champs):
    """Crée une note d'honoraires avec une référence anti-collision (NTJUR11).

    Référence ``NHJ-AAAAMM-NNNN`` via ``core.numbering`` — jamais
    ``count() + 1``.
    """
    from core.numbering import create_with_reference

    from .models import NoteHonoraires

    champs.pop('company', None)
    champs.pop('reference', None)

    def _save(reference):
        return NoteHonoraires.objects.create(
            company=mandat.company, mandat=mandat, reference=reference,
            **champs)

    return create_with_reference(
        NoteHonoraires, 'NHJ', mandat.company, _save)


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


@transaction.atomic
def reprendre_provision_dossier(dossier, *, montant=None, user=None):
    """Reprend la provision d'un dossier CLOS — NTJUR15, jamais automatique.

    Appelée uniquement depuis l'action confirmée ``reprendre-provision``.
    L'écriture inverse reste la responsabilité de
    ``apps.compta.services.reprendre_provision`` (import FONCTION-LOCAL :
    aucun modèle ``compta`` n'est importé ici — l'instance est résolue par
    ``apps.compta.selectors.provision_par_id``).

    Marque ``reprise_provision_traitee`` : la bannière ne revient pas au
    rechargement suivant.
    """
    from django.core.exceptions import ValidationError

    from apps.compta import selectors as compta_selectors
    from apps.compta import services as compta_services

    if not dossier.provision_comptable_id:
        raise ProvisionError("Ce dossier ne porte aucune provision à reprendre.")
    if dossier.reprise_provision_traitee:
        raise ProvisionError(
            "La reprise de provision de ce dossier a déjà été traitée.")
    provision = compta_selectors.provision_par_id(
        dossier.company, dossier.provision_comptable_id)
    if provision is None:
        raise ProvisionError(
            "La provision comptable liée est introuvable dans votre société.")
    try:
        provision = compta_services.reprendre_provision(
            provision, montant=montant, user=user)
    except ValidationError as exc:
        raise ProvisionError(
            ' '.join(getattr(exc, 'messages', [str(exc)])))
    dossier.reprise_provision_traitee = True
    dossier.save(update_fields=['reprise_provision_traitee', 'updated_at'])
    return provision


def abandonner_reprise_provision(dossier):
    """NTJUR15 — décision explicite de NE PAS reprendre la provision.

    Éteint la bannière sans passer la moindre écriture : « traitée » veut dire
    « une décision a été prise », pas « une écriture a été postée ».
    """
    if not dossier.reprise_provision_traitee:
        dossier.reprise_provision_traitee = True
        dossier.save(update_fields=['reprise_provision_traitee',
                                    'updated_at'])
    return dossier


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
