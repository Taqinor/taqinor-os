"""Services du module Appels d'offres (``apps.ao``).

AOF1 — le CORPS des services AO vit désormais ICI (il vivait encore interleavé
dans ``apps.compta.services`` malgré la sortie ODX11 des modèles).
``apps.compta.services`` porte maintenant un shim de ré-export **INVERSE**
(``from apps.ao.services import …``) pour ne casser aucun import historique.

``ao`` ne lit crm/ventes QUE via leurs selectors/services ou par référence
opaque — jamais leurs ``models`` (le lead reste un ``lead_id`` opaque).
"""
import hashlib
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from core import events
from core.numbering import create_with_reference

from .models import AppelOffre, EcheanceAO, PlanSource, ResultatAO

#: AOF5 — préfixe de NOTRE numérotation d'appels d'offres (``AO-YYYYMM-0001``).
#: La référence de l'acheteur vit dans ``AppelOffre.reference_acheteur`` et
#: n'entre JAMAIS dans cette séquence.
PREFIXE_REFERENCE_AO = 'AO'


# ── AOF5 — Numérotation des appels d'offres ────────────────────────────────

def creer_appel_offre_avec_reference(company, save_fn):
    """Crée un ``AppelOffre`` en lui attribuant une référence libre.

    Délègue à ``core.numbering.create_with_reference`` : plus-haut-numéro-
    utilisé + 1 par société et par mois, dans un savepoint, avec réessai sur
    une course. JAMAIS ``count() + 1`` ni un ``max + 1`` recalculé localement —
    ce motif a déjà coûté une collision de références en production (une
    suppression fait rétrécir le compte alors que le plus haut numéro utilisé,
    lui, reste).

    ``save_fn`` reçoit la référence générée et doit effectuer la création
    réelle (``serializer.save(...)`` ou ``AppelOffre.objects.create(...)``)
    puis retourner l'instance.
    """
    return create_with_reference(
        AppelOffre, PREFIXE_REFERENCE_AO, company, save_fn)


# ── AOF13 — Table de transitions DÉCLARATIVE + service de changement ───────
#
# La table est la seule description du cycle : aucune règle de statut n'est
# écrite « en dur » dans une vue ou un serializer. Les six valeurs historiques
# sont conservées ; ``en_preparation`` (le fourre-tout d'avant) reste un point
# de sortie vers CHACUNE des nouvelles étapes pour que les lignes déjà en base
# ne se retrouvent jamais coincées.

_S = AppelOffre.Statut

TRANSITIONS_AO = {
    _S.IDENTIFIE: (_S.ANALYSE_CPS, _S.EN_PREPARATION, _S.ABANDONNE),
    _S.ANALYSE_CPS: (_S.RELEVE, _S.ABANDONNE),
    _S.RELEVE: (_S.ETUDE, _S.ABANDONNE),
    _S.ETUDE: (_S.CHIFFRAGE, _S.ABANDONNE),
    _S.CHIFFRAGE: (_S.DOSSIER, _S.ABANDONNE),
    _S.DOSSIER: (_S.PRET_A_DEPOSER, _S.ABANDONNE),
    _S.PRET_A_DEPOSER: (_S.DEPOSE, _S.ABANDONNE),
    # Statut HISTORIQUE : rejoint n'importe quelle étape du nouveau cycle.
    _S.EN_PREPARATION: (
        _S.ANALYSE_CPS, _S.RELEVE, _S.ETUDE, _S.CHIFFRAGE, _S.DOSSIER,
        _S.PRET_A_DEPOSER, _S.DEPOSE, _S.ABANDONNE,
    ),
    _S.DEPOSE: (_S.GAGNE, _S.PERDU, _S.ABANDONNE),
    # États terminaux : plus aucune transition (l'issue d'un marché ne se
    # réécrit pas — un nouveau dossier serait un nouvel AO).
    _S.GAGNE: (),
    _S.PERDU: (),
    _S.ABANDONNE: (),
}

#: Statut → signal M6 à émettre EN SORTIE du service. Deux entrées, deux
#: abonnés réels (``apps/crm/receivers.py``) — on ne déclare jamais un signal
#: « pour plus tard » (``core.event_coverage`` le refuserait).
_SIGNAUX_PAR_STATUT = {
    _S.DEPOSE: events.ao_depose,
    _S.GAGNE: events.ao_gagne,
}


def transitions_possibles(statut):
    """Statuts atteignables depuis ``statut`` (tuple, éventuellement vide)."""
    return TRANSITIONS_AO.get(statut, ())


def changer_statut_ao(appel_offre, nouveau_statut, *, user=None, motif=''):
    """SEUL point de mutation du statut d'un appel d'offres (AOF13).

    Valide la transition contre ``TRANSITIONS_AO``, écrit le statut, journalise
    au chatter générique ``records`` (ARC8 — jamais une classe ``*Activity``
    maison) puis émet l'événement M6 correspondant s'il y en a un.

    Args:
        appel_offre: l'instance ``AppelOffre`` à faire avancer.
        nouveau_statut: valeur cible (clé de ``AppelOffre.Statut``).
        user: l'utilisateur qui décide (posé côté serveur, jamais lu du corps).
        motif: commentaire libre journalisé au chatter.

    Returns:
        L'instance mise à jour.

    Raises:
        ValidationError: transition inconnue ou interdite (message FR), à
        traduire en 400 par l'appelant HTTP.
    """
    ancien_statut = appel_offre.statut
    if nouveau_statut == ancien_statut:
        return appel_offre
    valides = dict(_S.choices)
    if nouveau_statut not in valides:
        raise ValidationError({'statut': f"Statut inconnu : « {nouveau_statut} »."})
    autorises = transitions_possibles(ancien_statut)
    if nouveau_statut not in autorises:
        libelles = ', '.join(f'« {valides[s]} »' for s in autorises) or 'aucun'
        raise ValidationError({'statut': (
            f"Transition interdite : « {valides[ancien_statut]} » → "
            f"« {valides[nouveau_statut]} ». Statuts atteignables : "
            f"{libelles}."
        )})

    appel_offre.statut = nouveau_statut
    setattr(appel_offre, AppelOffre.ATTR_STATUT_AUTORISE, True)
    try:
        appel_offre.save(update_fields=['statut', 'updated_at'])
    finally:
        setattr(appel_offre, AppelOffre.ATTR_STATUT_AUTORISE, False)

    _journaliser_statut(appel_offre, ancien_statut, nouveau_statut, user, motif)
    emettre_changement_statut_automation(
        appel_offre, ancien_statut=ancien_statut, user=user)

    signal = _SIGNAUX_PAR_STATUT.get(nouveau_statut)
    if signal is not None:
        signal.send(
            sender='ao.AppelOffre', appel_offre=appel_offre,
            company=appel_offre.company, user=user,
            ancien_statut=ancien_statut)
    return appel_offre


def _journaliser_statut(appel_offre, ancien, nouveau, user, motif):
    """Trace le changement au chatter générique ``records`` (best-effort)."""
    from apps.records.models import Activity
    from apps.records.services import log_activity

    libelles = dict(_S.choices)
    log_activity(
        appel_offre, Activity.Kind.MODIFICATION, user=user,
        field='statut', field_label='Statut',
        old_value=libelles.get(ancien, ancien),
        new_value=libelles.get(nouveau, nouveau),
        body=motif or '', company=appel_offre.company)


def emettre_changement_statut_automation(appel_offre, *, ancien_statut,
                                         user=None):
    """AOF15/ARC34 — évalue les règles no-code ``RECORD_STATE_CHANGE``.

    Même précédent que ``contrats.services`` et ``gestion_projet.services`` :
    appel direct à ``apps.automation.engine.evaluate()`` par un import
    FONCTION-LOCAL, émission depuis le SERVICE (jamais depuis un modèle). Le
    couple ``(ao.appeloffre, statut)`` est déclaré automatisable dans
    ``apps/ao/platform.py`` (``automation_state_fields``) — la surface est donc
    RÉELLEMENT câblée, jamais seulement annoncée (règle d'honnêteté ARC41). Le
    statut visé est le statut de DOMAINE de l'AO, jamais une étape STAGES.py.
    Best-effort : aucune erreur ne remonte, la transition est déjà actée.
    """
    if appel_offre.statut == ancien_statut:
        return
    try:
        from apps.automation.engine import evaluate
        from apps.automation.models import TriggerType

        evaluate(
            TriggerType.RECORD_STATE_CHANGE, appel_offre, appel_offre.company,
            context={
                'model': 'ao.appeloffre', 'field': 'statut',
                'old_value': ancien_statut, 'new_value': appel_offre.statut,
            },
            user=user)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        pass


# ── AOF15 — Échéancier DÉRIVÉ du projet et du CPS ──────────────────────────
#
# L'échéancier n'est jamais saisi à la main : il se DÉRIVE des dates du projet
# (remise des plis, ouverture, fin de validité) et des ``ExigenceCPS`` qui les
# paramètrent. La génération est IDEMPOTENTE — rejouer ne duplique rien — et
# une PROROGATION (validité rallongée, ouverture repoussée) DÉCALE l'échéance
# existante au lieu d'en créer une seconde : sans cela un dossier prorogé deux
# fois afficherait trois dates de validité concurrentes, et l'utilisateur
# apprendrait à ignorer le bandeau de rappel.

#: Libellés STABLES : ils servent de clé d'idempotence avec le type
#: d'échéance. Les changer casserait la déduplication d'un dossier existant.
LIBELLE_REMISE_PLIS = 'Remise des plis'
LIBELLE_OUVERTURE = 'Ouverture des plis'
LIBELLE_VALIDITE = "Fin de validité de l'offre"
LIBELLE_CAUTION = 'Échéance de la caution {type}'

#: Rappel par défaut (jours avant) par type d'échéance.
RAPPELS_PAR_DEFAUT = {
    EcheanceAO.TypeEcheance.REMISE_PLIS: 7,
    EcheanceAO.TypeEcheance.OUVERTURE: 1,
    EcheanceAO.TypeEcheance.VALIDITE: 15,
}
#: Rappel des échéances de caution (AOF16).
RAPPEL_CAUTION_JOURS = 15


def jours_validite_effectifs(appel_offre):
    """Durée de validité RÉELLEMENT applicable, en jours (AOF15).

    La clause ``VALIDITE_OFFRE`` du CPS (``ExigenceCPS``) PRIME sur la valeur
    portée par le projet : c'est le règlement de consultation qui fait foi, et
    une prorogation écrite se saisit comme une clause. À défaut de clause, on
    retombe sur ``AppelOffre.validite_offre_jours``.
    """
    from .models import ExigenceCPS

    clause = appel_offre.exigences_cps.filter(
        type_exigence=ExigenceCPS.TypeExigence.VALIDITE_OFFRE,
        valeur_num__isnull=False,
    ).order_by('-updated_at').first()
    if clause is not None:
        return int(clause.valeur_num)
    return appel_offre.validite_offre_jours or 0


def date_fin_validite_effective(appel_offre):
    """Fin de validité DÉRIVÉE (jamais stockée) — clause CPS prioritaire."""
    base = appel_offre.date_ouverture_plis or appel_offre.date_limite
    jours = jours_validite_effectifs(appel_offre)
    if base is None or not jours:
        return None
    return base + timedelta(days=jours)


def echeances_attendues(appel_offre):
    """Les échéances que le projet IMPLIQUE aujourd'hui (calcul pur).

    Renvoie une liste de dicts ``{type_echeance, libelle, date_echeance,
    rappel_jours}``. Une date absente ne produit AUCUNE échéance — une date
    inventée serait pire qu'une date manquante.
    """
    types = EcheanceAO.TypeEcheance
    candidats = (
        (types.REMISE_PLIS, LIBELLE_REMISE_PLIS, appel_offre.date_limite),
        (types.OUVERTURE, LIBELLE_OUVERTURE, appel_offre.date_ouverture_plis),
        (types.VALIDITE, LIBELLE_VALIDITE,
         date_fin_validite_effective(appel_offre)),
    )
    attendues = []
    for type_echeance, libelle, date_echeance in candidats:
        if date_echeance is None:
            continue
        attendues.append({
            'type_echeance': type_echeance,
            'libelle': libelle,
            'date_echeance': date_echeance,
            'rappel_jours': RAPPELS_PAR_DEFAUT[type_echeance],
        })
    # AOF16 — l'échéance de CHAQUE caution rejoint l'échéancier : une caution
    # périmée le jour de l'ouverture fait rejeter le pli.
    for caution in appel_offre.cautions.exclude(date_echeance=None):
        attendues.append({
            'type_echeance': types.AUTRE,
            'libelle': LIBELLE_CAUTION.format(
                type=caution.get_type_caution_display().lower()),
            'date_echeance': caution.date_echeance,
            'rappel_jours': RAPPEL_CAUTION_JOURS,
        })
    return attendues


def generer_echeancier_ao(appel_offre):
    """Génère/MET À JOUR l'échéancier d'un AO — IDEMPOTENT (AOF15).

    Clé d'idempotence : ``(company, appel_offre, type_echeance, libelle)`` —
    le libellé entre dans la clé parce que plusieurs cautions partagent le
    type ``AUTRE``. Rejouer sur un dossier inchangé ne crée rien ; rejouer
    après une PROROGATION met à jour la date de l'échéance existante (et donc
    décale son rappel) au lieu d'en ajouter une nouvelle. Aucune I/O réseau
    ici : le service calcule et écrit, l'envoi éventuel appartient à la tâche
    planifiée.

    Returns:
        ``{'creees': int, 'mises_a_jour': int, 'inchangees': int}``.
    """
    resume = {'creees': 0, 'mises_a_jour': 0, 'inchangees': 0}
    for attendue in echeances_attendues(appel_offre):
        existante = EcheanceAO.objects.filter(
            company=appel_offre.company, appel_offre=appel_offre,
            type_echeance=attendue['type_echeance'],
            libelle=attendue['libelle'],
        ).first()
        if existante is None:
            EcheanceAO.objects.create(
                company=appel_offre.company, appel_offre=appel_offre,
                **attendue)
            resume['creees'] += 1
            continue
        if existante.date_echeance == attendue['date_echeance']:
            resume['inchangees'] += 1
            continue
        existante.date_echeance = attendue['date_echeance']
        # Une prorogation ROUVRE l'échéance : une date repoussée redevient
        # « à traiter », sinon le rappel décalé ne serait jamais émis.
        existante.traitee = False
        existante.save(update_fields=[
            'date_echeance', 'traitee', 'updated_at'])
        resume['mises_a_jour'] += 1
    return resume


# ── AOF16 — Les DEUX régimes de cautionnement ──────────────────────────────
#
# Constat marché : le cautionnement DÉFINITIF est un TAUX du montant initial
# (3 % au Maroc) ; le PROVISOIRE est un MONTANT ABSOLU fixé par le CPS
# (10 000 / 25 000 / 30 000 / 50 000 DH). Le provisoire n'est donc JAMAIS
# dérivé du montant de l'offre — il se saisit. Et le taux du définitif est LU
# dans ``ExigenceCPS`` : c'est une clause du marché, pas une loi du produit.
# Le figer en constante produirait un jour une caution non conforme.

def taux_caution_definitive(appel_offre):
    """Taux (%) du cautionnement définitif, LU dans les clauses du CPS.

    Raises:
        ValidationError: aucune clause ``CAUTION_DEFINITIVE_TAUX`` saisie. On
        refuse d'inventer un taux — mieux vaut un blocage explicite qu'une
        caution calculée sur une hypothèse.
    """
    from .models import ExigenceCPS

    clause = appel_offre.exigences_cps.filter(
        type_exigence=ExigenceCPS.TypeExigence.CAUTION_DEFINITIVE_TAUX,
        valeur_num__isnull=False,
    ).order_by('-updated_at').first()
    if clause is None:
        raise ValidationError({'caution': (
            "Le taux du cautionnement définitif n'est pas saisi dans les "
            "clauses du CPS de cet appel d'offres : il se lit dans le marché, "
            "il ne se devine pas."
        )})
    return clause.valeur_num


def deriver_caution_definitive(appel_offre, *, montant_marche=None,
                               banque='', date_echeance=None):
    """Crée/MET À JOUR la caution DÉFINITIVE, dérivée du taux du CPS (AOF16).

    ``montant_marche`` par défaut : le montant HT de NOTRE offre. Le résultat
    est arrondi au centime. IDEMPOTENT : un second appel met à jour la caution
    définitive existante au lieu d'en créer une seconde.

    La caution PROVISOIRE n'est jamais touchée ici : son montant est absolu et
    saisi (cf. la clause ``CAUTION_PROVISOIRE`` du CPS).
    """
    from .models import CautionSoumission

    taux = taux_caution_definitive(appel_offre)
    base = montant_marche
    if base is None:
        base = appel_offre.montant_offre_ht or Decimal('0.00')
    montant = (Decimal(base) * Decimal(taux) / Decimal('100')).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)

    caution = appel_offre.cautions.filter(
        type_caution=CautionSoumission.TypeCaution.DEFINITIVE).first()
    if caution is None:
        return CautionSoumission.objects.create(
            company=appel_offre.company, appel_offre=appel_offre,
            type_caution=CautionSoumission.TypeCaution.DEFINITIVE,
            montant=montant, banque=banque, date_echeance=date_echeance)
    caution.montant = montant
    champs = ['montant', 'updated_at']
    if banque:
        caution.banque = banque
        champs.append('banque')
    if date_echeance is not None:
        caution.date_echeance = date_echeance
        champs.append('date_echeance')
    caution.save(update_fields=champs)
    return caution


def cautions_expirant_avant_ouverture(appel_offre):
    """Cautions dont l'échéance tombe AVANT l'ouverture des plis (AOF16)."""
    return [
        caution for caution in appel_offre.cautions.all()
        if caution.expire_avant_ouverture
    ]


# ── AOF22 — Obstacles : provenance, dégagement dérivé, écartement ──────────

def enregistrer_obstacle(obstacle):
    """Applique la règle de dégagement PUIS écrit (AOF22).

    Point de passage unique : tout changement de provenance ou de nature doit
    repasser par ici, sinon un obstacle requalifié garderait le dégagement de
    son ancienne provenance — l'erreur est silencieuse et coûte des modules.
    """
    obstacle.appliquer_degagement()
    obstacle.save()
    return obstacle


def requalifier_provenance(obstacle, provenance, *, user=None, motif=''):
    """Change la provenance d'un obstacle et RECALCULE son dégagement."""
    ancienne = obstacle.provenance
    if provenance == ancienne:
        return obstacle
    obstacle.provenance = provenance
    obstacle.appliquer_degagement()
    obstacle.save(update_fields=[
        'provenance', 'degagement_m', 'regle_degagement', 'updated_at'])
    _journaliser_obstacle(
        obstacle, 'provenance', ancienne, provenance, user, motif)
    return obstacle


def ecarter_obstacle(obstacle, *, motif, user=None):
    """Écarte un obstacle SANS le supprimer (AOF22).

    La géométrie reste en base : le retour arrière est un one-liner et
    l'échelle de décomposition peut chiffrer ce que la décision rapporte. Un
    obstacle mesuré n'est JAMAIS supprimé.
    """
    ancienne = obstacle.provenance
    obstacle.provenance = obstacle.Provenance.ECARTE
    obstacle.actif = False
    obstacle.decision = motif
    obstacle.appliquer_degagement()
    obstacle.save(update_fields=[
        'provenance', 'actif', 'decision', 'degagement_m',
        'regle_degagement', 'updated_at'])
    _journaliser_obstacle(
        obstacle, 'provenance', ancienne, obstacle.provenance, user, motif)
    return obstacle


def reintegrer_obstacle(obstacle, provenance, *, user=None, motif=''):
    """Retour arrière : un obstacle écarté redevient actif (AOF22)."""
    ancienne = obstacle.provenance
    obstacle.provenance = provenance
    obstacle.actif = True
    obstacle.appliquer_degagement()
    obstacle.save(update_fields=[
        'provenance', 'actif', 'degagement_m', 'regle_degagement',
        'updated_at'])
    _journaliser_obstacle(
        obstacle, 'provenance', ancienne, provenance, user, motif)
    return obstacle


def _journaliser_obstacle(obstacle, champ, ancien, nouveau, user, motif):
    from apps.records.models import Activity
    from apps.records.services import log_activity

    log_activity(
        obstacle.toiture.batiment.appel_offre, Activity.Kind.MODIFICATION,
        user=user, field=champ,
        field_label=f'Obstacle {obstacle.repere or obstacle.pk} — {champ}',
        old_value=str(ancien), new_value=str(nouveau), body=motif or '',
        company=obstacle.company)


# ── AOF21 — Pièces du DCE reçues : additifs et re-vérification ─────────────

def enregistrer_additif(appel_offre, *, piece_modifiee, reference='',
                        version='', date_reception=None, user=None):
    """Enregistre un ADDITIF et marque « à revérifier » ce qui en dérive.

    Le cas coûteux est l'erratum reçu APRÈS le téléchargement du dossier : il
    change des clauses DÉJÀ relevées. Sans ce marquage, l'équipe continue de
    travailler sur des valeurs périmées et ne s'en aperçoit qu'à l'ouverture
    des plis.

    Renvoie le couple ``(additif, nombre_d_exigences_marquees)``.
    """
    from .models import PieceConsultation

    additif = PieceConsultation.objects.create(
        company=appel_offre.company, appel_offre=appel_offre,
        type_piece=PieceConsultation.TypePiece.ADDITIF,
        reference=reference, version=version,
        date_reception=date_reception or timezone.now().date(),
        modifie=piece_modifiee)

    marquees = 0
    if piece_modifiee is not None:
        marquees = piece_modifiee.exigences.filter(
            a_reverifier=False).update(a_reverifier=True)

    from apps.records.models import Activity
    from apps.records.services import log_activity

    log_activity(
        appel_offre, Activity.Kind.NOTE, user=user,
        body=(
            f'Additif reçu ({reference or "sans référence"}) — '
            f'{marquees} clause(s) du CPS marquée(s) « à revérifier ».'
        ),
        company=appel_offre.company)
    return additif, marquees


def exigences_a_reverifier(appel_offre):
    """Clauses marquées à relire après un additif (AOF21)."""
    return appel_offre.exigences_cps.filter(a_reverifier=True)


# ── AOF20 — Supports de plan : upload, calibration, empreinte ──────────────

def empreinte_fichier(contenu):
    """SHA-256 hexadécimal d'un contenu binaire (AOF20)."""
    return hashlib.sha256(contenu).hexdigest()


def attacher_fichier_plan_source(plan_source, fichier, *, user=None):
    """Attache un fichier à un ``PlanSource`` VIA ``records.Attachment``.

    Le binaire ne touche JAMAIS ``apps/ao`` : il part dans le stockage objet
    par ``records.storage.store_attachment`` (clé préfixée par société), et
    seul l'``Attachment`` est référencé — **jamais un** ``FileField`` (garde
    ARC26).

    L'empreinte SHA-256 sert à reconnaître un même plan reçu deux fois
    (erratum, re-téléchargement du dossier) : le second ``PlanSource``
    RÉUTILISE l'``Attachment`` déjà stocké de la même société au lieu d'en
    téléverser un doublon.

    Raises:
        ValidationError: format refusé ou fichier trop volumineux (message du
        stockage, en français).
    """
    from django.contrib.contenttypes.models import ContentType

    from apps.records.models import Attachment
    from apps.records.storage import store_attachment

    contenu = fichier.read()
    fichier.seek(0)
    empreinte = empreinte_fichier(contenu)

    jumeau = PlanSource.objects.filter(
        company=plan_source.company, empreinte_sha256=empreinte,
        attachment__isnull=False,
    ).exclude(pk=plan_source.pk).first()
    if jumeau is not None:
        attachement = jumeau.attachment
    else:
        infos, erreur = store_attachment(
            fichier, company=plan_source.company)
        if erreur:
            raise ValidationError({'fichier': erreur})
        attachement = Attachment.objects.create(
            company=plan_source.company,
            content_type=ContentType.objects.get_for_model(PlanSource),
            object_id=plan_source.pk,
            uploaded_by=user, **infos)

    plan_source.attachment = attachement
    plan_source.empreinte_sha256 = empreinte
    plan_source.save(update_fields=[
        'attachment', 'empreinte_sha256', 'updated_at'])
    return plan_source


def recalibrer_plan_source(plan_source, *, point_a_px=None, point_b_px=None,
                           distance_reelle_m=None):
    """Met à jour la calibration ET recalcule l'échelle (AOF20).

    C'est le SEUL chemin de modification d'un point de calibration : une
    échelle laissée figée après un déplacement de point fausserait toutes les
    cotes déduites du plan, silencieusement.
    """
    champs = []
    if point_a_px is not None:
        plan_source.calib_point_a_px = list(point_a_px)
        champs.append('calib_point_a_px')
    if point_b_px is not None:
        plan_source.calib_point_b_px = list(point_b_px)
        champs.append('calib_point_b_px')
    if distance_reelle_m is not None:
        plan_source.calib_distance_reelle_m = Decimal(str(distance_reelle_m))
        champs.append('calib_distance_reelle_m')
    plan_source.recalculer_echelle()
    champs += ['echelle_m_par_px', 'etat', 'updated_at']
    plan_source.save(update_fields=champs)
    return plan_source


# ── AOF17 — Lien CRM, sans couplage ────────────────────────────────────────
#
# ``AppelOffre.lead_id`` reste un ENTIER OPAQUE : c'est ce qui tient le contrat
# import-linter ``ao-models-decoupled``. On lit le lead par les SELECTORS du
# CRM (``apps.crm.selectors``) — jamais ``apps.crm.models``.

def resoudre_lead(company, lead_id):
    """Résout le lead d'une société par son id, ou ``None`` (AOF17).

    Un id appartenant à une AUTRE société renvoie ``None`` : c'est la même
    borne que ``crm.selectors.get_company_lead``, donc aucun accès
    cross-tenant n'est possible par un id deviné.
    """
    if not lead_id:
        return None
    from apps.crm.selectors import get_company_lead

    return get_company_lead(company, lead_id)


def rattacher_ao_au_lead(appel_offre, lead_id, *, user=None):
    """Rattache (ou détache) un AO à un lead, en VALIDANT l'appartenance.

    ``lead_id`` vide ⇒ détachement. Un lead d'une autre société est refusé —
    sinon un identifiant deviné suffirait à relier un dossier au CRM d'autrui.
    Le changement est journalisé au chatter générique ``records``.

    Raises:
        ValidationError: le lead n'existe pas dans la société de l'AO.
    """
    ancien = appel_offre.lead_id
    if not lead_id:
        nouveau = None
    else:
        lead = resoudre_lead(appel_offre.company, lead_id)
        if lead is None:
            raise ValidationError({'lead': (
                "Ce lead n'existe pas dans votre société."
            )})
        nouveau = lead.pk
    if ancien == nouveau:
        return appel_offre
    appel_offre.lead_id = nouveau
    appel_offre.save(update_fields=['lead_id', 'updated_at'])

    from apps.records.models import Activity
    from apps.records.services import log_activity

    log_activity(
        appel_offre, Activity.Kind.MODIFICATION, user=user,
        field='lead_id', field_label='Lead lié',
        old_value=str(ancien or ''), new_value=str(nouveau or ''),
        company=appel_offre.company)
    return appel_offre


# ── FG226 — Échéances d'AO dues (rappels) ──────────────────────────────────

def echeances_ao_dues(company, *, a_la_date=None):
    """Liste les échéances d'AO dont le rappel est dû (FG226), NON traitées.

    Une échéance est due quand ``date_echeance - rappel_jours <= a_la_date`` et
    qu'elle n'est pas encore traitée. Calcul pur (aucun envoi réseau) — sert au
    moteur d'alertes et aux tests.
    """
    a_la_date = a_la_date or timezone.now().date()
    dues = []
    qs = EcheanceAO.objects.filter(
        company=company, traitee=False).order_by('date_echeance')
    for ech in qs:
        seuil = ech.date_echeance - timezone.timedelta(days=ech.rappel_jours)
        if seuil <= a_la_date:
            dues.append(ech)
    return dues


# ── FG227 — Taux de réussite des appels d'offres ───────────────────────────

def taux_reussite_ao(company):
    """Taux de réussite gagné/perdu des AO (FG227).

    Compte les résultats par issue et calcule le taux = gagnés / (gagnés +
    perdus). Renvoie un dict d'agrégats. Lecture seule.
    """
    resultats = ResultatAO.objects.filter(company=company)
    gagnes = resultats.filter(issue=ResultatAO.Issue.GAGNE).count()
    perdus = resultats.filter(issue=ResultatAO.Issue.PERDU).count()
    total_decides = gagnes + perdus
    taux = Decimal('0.00')
    if total_decides > 0:
        taux = (Decimal(gagnes) / Decimal(total_decides) * Decimal('100')
                ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return {
        'gagnes': gagnes,
        'perdus': perdus,
        'total_decides': total_decides,
        'total_resultats': resultats.count(),
        'taux_reussite_pct': taux,
    }
