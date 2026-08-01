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

from .models import (
    AppelOffre, EcheanceAO, PlanSource, ResultatAO, StatutCote,
)

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


# ── AOF32 — Le résultat d'ouverture des plis ───────────────────────────────
#
# ``ResultatAO`` existait et n'était JAMAIS écrit : l'app s'arrêtait au dépôt
# alors que la valeur récurrente est en AVAL. C'est cette donnée qui alimente
# la bibliothèque de prix et le KPI de taux de réussite — lequel est CALCULÉ
# (``taux_reussite_ao``), jamais saisi.

#: Issue du résultat → statut d'AO correspondant. ``infructueux``/``annule``
#: ne changent PAS le statut : le dossier n'est ni gagné ni perdu, il est sans
#: suite du fait de l'acheteur.
_ISSUE_VERS_STATUT = {
    ResultatAO.Issue.GAGNE: AppelOffre.Statut.GAGNE,
    ResultatAO.Issue.PERDU: AppelOffre.Statut.PERDU,
}


def enregistrer_resultat_ao(appel_offre, *, issue, user=None, **donnees):
    """Enregistre le résultat d'ouverture des plis et FAIT SUIVRE le statut.

    La transition ``depose → gagne|perdu`` passe par
    ``changer_statut_ao`` — JAMAIS par une mutation directe : c'est lui qui
    valide la transition, journalise au chatter et émet ``ao_gagne``.

    IDEMPOTENT : un second appel met à jour le résultat existant (un AO n'a
    qu'un résultat, contrainte ``OneToOne``).

    Args:
        issue: valeur de ``ResultatAO.Issue``.
        **donnees: champs de ``ResultatAO`` (date_ouverture, nombre_plis,
            classement, notre_rang, attributaire, notre_prix, prix_gagnant,
            motif, date_resultat).

    Raises:
        ValidationError: issue inconnue, ou transition de statut interdite
        depuis l'état courant du dossier.
    """
    valides = dict(ResultatAO.Issue.choices)
    if issue not in valides:
        raise ValidationError({'issue': f"Issue inconnue : « {issue} »."})

    resultat, _ = ResultatAO.objects.update_or_create(
        company=appel_offre.company, appel_offre=appel_offre,
        defaults={'issue': issue, **donnees})

    statut_cible = _ISSUE_VERS_STATUT.get(issue)
    if statut_cible is not None and appel_offre.statut != statut_cible:
        changer_statut_ao(
            appel_offre, statut_cible, user=user,
            motif=(donnees.get('motif') or "Résultat d'ouverture des plis"))
    return resultat


# ── AOF28 — Publier une variante exige une PREUVE ──────────────────────────

def publier_variante(variante):
    """Fait passer une variante à ``publiable`` — ou REFUSE avec les motifs.

    C'est la seule façon d'écrire « capacité prouvée optimale » à un maître
    d'ouvrage sans risque : la donnée doit le démontrer.

    Raises:
        ValidationError: la preuve ne tient pas (motifs en français).
    """
    raisons = variante.raisons_de_non_publiabilite()
    if raisons:
        raise ValidationError({'preuve': raisons})
    variante.statut = variante.Statut.PUBLIABLE
    variante.save(update_fields=['statut', 'updated_at'])
    return variante


def retenir_variante(variante):
    """Désigne LA variante retenue d'une toiture (une seule à la fois)."""
    from .models import VarianteCalepinage

    VarianteCalepinage.objects.filter(
        toiture_id=variante.toiture_id, est_retenue=True,
    ).exclude(pk=variante.pk).update(est_retenue=False)
    variante.est_retenue = True
    variante.save(update_fields=['est_retenue', 'updated_at'])
    return variante


# ── AOF26/AOF27 — Kits et presets ──────────────────────────────────────────

def appliquer_preset(preset, toiture, *, user=None):
    """Applique un preset à une toiture EN UN APPEL, et TRACE l'application.

    On écrit à la fois le lien (``preset_applique``) et un INSTANTANÉ des
    paramètres (``parametres_calepinage``) : sans l'instantané, éditer un
    preset six mois plus tard réécrirait l'histoire d'un calepinage déjà
    publié — et le plan remis au maître d'ouvrage ne serait plus reproductible.
    """
    toiture.preset_applique = preset
    toiture.parametres_calepinage = dict(preset.parametres or {})
    toiture.save(update_fields=[
        'preset_applique', 'parametres_calepinage', 'updated_at'])

    from apps.records.models import Activity
    from apps.records.services import log_activity

    log_activity(
        toiture.batiment.appel_offre, Activity.Kind.MODIFICATION, user=user,
        field='preset_applique',
        field_label=f'Toiture {toiture.code_document or toiture.pk}',
        old_value='', new_value=preset.nom,
        body='Preset de calepinage appliqué.', company=toiture.company)
    return toiture


def preset_par_defaut(company, portee):
    """Le preset par défaut d'une portée, ou ``None``."""
    from .models import PresetCalepinage

    return PresetCalepinage.objects.filter(
        company=company, portee=portee, par_defaut=True).first()


def seeder_presets(company):
    """Crée les presets de référence manquants. ADDITIF et rejouable."""
    from .models import (
        PRESET_CONSERVATEUR_NOM, PRESET_CONSERVATEUR_PARAMETRES,
        PRESET_REFERENCE_NOM, PRESET_REFERENCE_PARAMETRES, PresetCalepinage,
    )

    gabarits = (
        (PRESET_REFERENCE_NOM, PRESET_REFERENCE_PARAMETRES, True,
         'Jeu de référence relevé sur un chantier réel (07/2026) : rives '
         '0,35 m, allée minimale 0,60 m, dégagements 0,30/0,50 m.'),
        (PRESET_CONSERVATEUR_NOM, PRESET_CONSERVATEUR_PARAMETRES, False,
         "Anciens défauts conservateurs (1,50/0,50/0,50), conservés à titre "
         "d'information."),
    )
    crees = 0
    for nom, parametres, par_defaut, description in gabarits:
        _, cree = PresetCalepinage.objects.get_or_create(
            company=company, nom=nom,
            defaults={
                'portee': PresetCalepinage.Portee.AO,
                'parametres': dict(parametres),
                'par_defaut': par_defaut,
                'description': description,
            })
        crees += int(cree)
    return crees


# ── AOF25 — Trancher une question APPLIQUE la décision ─────────────────────
#
# Une question tranchée qui ne modifie rien ne sert à rien : la décision doit
# retomber sur l'objet concerné (obstacle écarté/confirmé, cote requalifiée) ET
# périmer les variantes de calepinage qui s'appuyaient sur l'ancien état.

#: Actions applicables au moment de trancher une question.
ACTIONS_QUESTION = (
    'ecarter_obstacle', 'confirmer_obstacle', 'requalifier_cote', 'aucune',
)


def trancher_question(question, *, decision, action='aucune',
                      statut_cote=None, provenance=None, user=None):
    """Tranche une question et APPLIQUE sa décision (AOF25).

    Args:
        question: la ``QuestionAO`` à trancher.
        decision: la décision retenue, en clair (journalisée).
        action: ``ecarter_obstacle`` | ``confirmer_obstacle`` |
            ``requalifier_cote`` | ``aucune``.
        statut_cote: nouveau statut des cotes de la chaîne liée
            (``requalifier_cote``).
        provenance: nouvelle provenance de l'obstacle (``confirmer_obstacle``).

    Returns:
        ``(question, variantes_perimees)``.

    Raises:
        ValidationError: action inconnue, ou objet lié manquant pour l'action.
    """
    if action not in ACTIONS_QUESTION:
        raise ValidationError({'action': (
            f"Action inconnue : « {action} ». Attendu l'une de "
            f"{', '.join(ACTIONS_QUESTION)}."
        )})

    toitures = set()
    if action in ('ecarter_obstacle', 'confirmer_obstacle'):
        if question.obstacle_id is None:
            raise ValidationError({'obstacle': (
                "Cette action exige une question rattachée à un obstacle."
            )})
        obstacle = question.obstacle
        toitures.add(obstacle.toiture_id)
        if action == 'ecarter_obstacle':
            ecarter_obstacle(obstacle, motif=decision, user=user)
        else:
            requalifier_provenance(
                obstacle, provenance or obstacle.Provenance.MESURE,
                user=user, motif=decision)
    elif action == 'requalifier_cote':
        if question.chaine_id is None:
            raise ValidationError({'chaine': (
                "Cette action exige une question rattachée à une chaîne de "
                "cotes."
            )})
        chaine = question.chaine
        toitures.add(chaine.toiture_id)
        _requalifier_cotes(chaine, statut_cote or StatutCote.MESURE)

    question.decision = decision
    question.statut = question.Statut.TRANCHEE
    question.date_decision = timezone.now().date()
    question.save(update_fields=[
        'decision', 'statut', 'date_decision', 'updated_at'])

    perimees = 0
    for toiture_id in toitures:
        perimees += perimer_variantes_de_toiture(toiture_id)

    from apps.records.models import Activity
    from apps.records.services import log_activity

    log_activity(
        question.serie.appel_offre, Activity.Kind.MODIFICATION, user=user,
        field='question', field_label=f'Question {question.repere or ""}',
        old_value=question.texte[:80], new_value=decision[:80],
        body=(
            f'Impact prévisionnel {question.impact_min_modules}→'
            f'{question.impact_max_modules} modules ; action « {action} » ; '
            f'{perimees} variante(s) périmée(s).'
        ),
        company=question.company)
    return question, perimees


def _requalifier_cotes(chaine, statut):
    """Repose le statut de TOUTES les cotes d'une chaîne (AOF25)."""
    segments = [dict(s) for s in (chaine.segments or [])]
    for segment in segments:
        segment['statut'] = str(statut)
    chaine.segments = segments
    chaine.recalculer_fermeture()
    chaine.save(update_fields=[
        'segments', 'residu_m', 'residu_pct', 'verdict', 'updated_at'])
    return chaine


def perimer_variantes_de_toiture(toiture_id):
    """Marque PÉRIMÉES les variantes de calepinage d'une toiture (AOF25/AOF29).

    Résolution PARESSEUSE du modèle : ``VarianteCalepinage`` arrive avec AOF28
    et ce service doit continuer de fonctionner AVANT comme APRÈS, sans import
    conditionnel enfoui dans un appelant. Renvoie le nombre de variantes
    marquées (0 tant que le modèle n'existe pas).
    """
    from django.apps import apps as django_apps

    try:
        modele = django_apps.get_model('ao', 'VarianteCalepinage')
    except LookupError:
        return 0
    return modele.objects.filter(toiture_id=toiture_id).exclude(
        statut='perime').update(statut='perime')


# ── AOF23 — Fermetures de chaînes : la déduction PRIME sur l'annoncé ───────

def recalculer_chaine(chaine):
    """Recalcule la fermeture d'une chaîne PUIS persiste (AOF23)."""
    chaine.recalculer_fermeture()
    chaine.save(update_fields=[
        'residu_m', 'residu_pct', 'verdict', 'updated_at'])
    return chaine


def deduire_segment(chaine, index, *, user=None):
    """Déduit le segment ``index`` de la FERMETURE EXACTE de la chaîne.

    Règle métier gravée : la valeur DÉDUITE prime sur la valeur ANNONCÉE
    (souvent arrondie sur le terrain), et le segment bascule automatiquement en
    ``A_CONFIRMER``. Cas réel : 51,10 − (19,36 + 7,92 + 4,50 + 10,50) = 8,82 m
    déduits contre « ≈ 8,5 » annoncé — l'écart de 0,32 m se PUBLIE.

    La valeur annoncée n'est pas jetée : elle est conservée dans
    ``valeur_annoncee_m`` pour que l'écart reste citable.

    Raises:
        ValidationError: sans mesure totale, aucune déduction n'est possible.
    """
    if chaine.mesure_globale_m is None:
        raise ValidationError({'mesure_globale_m': (
            "Sans mesure totale, aucun segment ne peut être déduit d'une "
            'fermeture.'
        )})
    segments = [dict(s) for s in (chaine.segments or [])]
    if not 0 <= index < len(segments):
        raise ValidationError({'segments': 'Segment inexistant.'})

    autres = Decimal('0.000')
    for position, segment in enumerate(segments):
        if position == index:
            continue
        valeur = segment.get('valeur_m')
        if valeur not in (None, ''):
            autres += Decimal(str(valeur))
    deduit = (Decimal(chaine.mesure_globale_m) - autres).quantize(
        Decimal('0.001'))

    cible = segments[index]
    annoncee = cible.get('valeur_m')
    if annoncee not in (None, '') and Decimal(str(annoncee)) != deduit:
        cible['valeur_annoncee_m'] = float(Decimal(str(annoncee)))
    cible['valeur_m'] = float(deduit)
    cible['deduit'] = True
    # Une valeur déduite n'a JAMAIS été mesurée : elle est à confirmer.
    cible['statut'] = StatutCote.A_CONFIRMER.value
    segments[index] = cible

    chaine.segments = segments
    chaine.recalculer_fermeture()
    chaine.save(update_fields=[
        'segments', 'residu_m', 'residu_pct', 'verdict', 'updated_at'])
    _journaliser_chaine(chaine, cible, annoncee, deduit, user)
    return chaine


def proposer_compensation_prorata(chaine):
    """PROPOSE une répartition du résidu au prorata — sans RIEN appliquer.

    Appliquer une compensation en silence transformerait un écart de relevé en
    fausse précision : la proposition est rendue à l'utilisateur, qui décide.
    Renvoie ``{'residu_m', 'segments': [{'index', 'libelle', 'valeur_m',
    'valeur_proposee_m', 'delta_m'}]}`` ou ``None`` si rien à répartir.
    """
    if chaine.residu_m in (None, '') or Decimal(chaine.residu_m) == 0:
        return None
    somme = chaine.somme_segments_m
    if somme == 0:
        return None
    residu = Decimal(chaine.residu_m)
    lignes = []
    for index, segment in enumerate(chaine.segments or []):
        valeur = segment.get('valeur_m')
        if valeur in (None, ''):
            continue
        valeur = Decimal(str(valeur))
        delta = (residu * valeur / somme).quantize(Decimal('0.001'))
        lignes.append({
            'index': index,
            'libelle': segment.get('libelle', ''),
            'valeur_m': float(valeur),
            'valeur_proposee_m': float(valeur + delta),
            'delta_m': float(delta),
        })
    return {'residu_m': float(residu), 'applique': False, 'segments': lignes}


def _journaliser_chaine(chaine, segment, annoncee, deduit, user):
    from apps.records.models import Activity
    from apps.records.services import log_activity

    log_activity(
        chaine.toiture.batiment.appel_offre, Activity.Kind.MODIFICATION,
        user=user, field='segments',
        field_label=f'Chaîne « {chaine.libelle} » — {segment.get("libelle", "")}',
        old_value=('' if annoncee in (None, '') else str(annoncee)),
        new_value=str(deduit),
        body='Cote déduite de la fermeture — à confirmer à l\'exécution.',
        company=chaine.company)


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


# ── AOF115 — Dossier de dépôt : création numérotée + porte de transition ───

def creer_dossier_ao(company, appel_offre=None, save_fn=None, **champs):
    """Crée le ``DossierAO`` d'un appel d'offres avec sa référence ``AODOS``.

    Délègue la numérotation à ``core.numbering.create_with_reference`` (plus
    haut numéro utilisé + 1, savepoint + réessai) — JAMAIS ``count()+1``.
    ``save_fn`` reçoit la référence générée et effectue la création réelle
    (motif ``core.documents.document_viewset``) ; sans elle, l'instance est
    créée ici à partir d'``appel_offre`` et des champs fournis.
    """
    from .models import DossierAO

    def _save(reference):
        if save_fn is not None:
            return save_fn(reference)
        return DossierAO.objects.create(
            company=company, appel_offre=appel_offre, reference=reference,
            **champs)

    return create_with_reference(
        DossierAO, DossierAO.PREFIXE_REFERENCE, company, _save)


def changer_statut_dossier(dossier, nouveau_statut, *, user=None, motif=''):
    """SEUL point de mutation du statut d'un ``DossierAO`` (AOF115).

    Compose le kit ``core.documents.changer_statut`` (table ``TRANSITIONS``
    déclarative + événement ``document_statut_change``) et y AJOUTE la porte
    métier : ``pret_a_deposer`` est REFUSÉ tant qu'une pièce obligatoire
    manque. La complétude est DÉRIVÉE des pièces, jamais d'un drapeau stocké.

    Raises:
        ValidationError: pièce obligatoire manquante (message FR listant les
            pièces fautives), à traduire en 400 par l'appelant HTTP.
        core.documents.TransitionRefusee: transition absente de la table.
    """
    from core.documents import changer_statut

    from .models import DossierAO

    if nouveau_statut == DossierAO.Statut.PRET_A_DEPOSER:
        raisons = dossier.raisons_de_non_depot()
        if raisons:
            raise ValidationError({'statut': raisons})

    ancien = dossier.statut
    changer_statut(dossier, nouveau_statut, user=user)
    _journaliser_dossier(dossier, ancien, nouveau_statut, user, motif)
    return dossier


def _journaliser_dossier(dossier, ancien, nouveau, user, motif):
    """Trace le changement au chatter générique ``records`` (best-effort)."""
    from apps.records.models import Activity
    from apps.records.services import log_activity

    from .models import DossierAO

    libelles = dict(DossierAO.Statut.choices)
    log_activity(
        dossier, Activity.Kind.MODIFICATION, user=user,
        field='statut', field_label='Statut',
        old_value=libelles.get(ancien, ancien),
        new_value=libelles.get(nouveau, nouveau),
        body=motif or '', company=dossier.company)


# ── AOF118 — Équipements engagés : SNAPSHOT figé du catalogue ──────────────
#
# Le catalogue est re-seedé régulièrement. Un dossier DÉPOSÉ ne doit jamais
# voir sa désignation bouger sous lui : on COPIE ce que le catalogue disait au
# moment de l'engagement, une fois, et on n'y revient plus.
#
# Les attributs du produit sont lus par ``apps.stock.selectors`` UNIQUEMENT —
# jamais par un import de ``apps.stock.models`` (contrat import-linter
# ``ao-models-decoupled`` + règle de frontière cross-app).

#: Caractéristiques du catalogue reportées dans le snapshot. Le COÛT
#: (``prix_achat``) en est DÉLIBÉRÉMENT absent : il ne sort jamais d'un
#: équipement d'AO, qui alimente des pièces remises au maître d'ouvrage.
CARACTERISTIQUES_SNAPSHOT = (
    'garantie', 'garantie_mois', 'garantie_production_mois',
    'pompe_cv', 'hmt_m', 'debit_m3j', 'tension_v', 'pompe_kw',
)


def snapshot_produit(company, produit_id):
    """Instantané FIGÉ d'un produit du catalogue (lecture via selectors).

    Renvoie un dict ``{designation, marque, reference_constructeur,
    caracteristiques}``. Produit introuvable → dict vide (l'appelant garde ses
    valeurs saisies à la main : un équipement hors catalogue reste légitime).
    """
    from apps.stock import selectors as stock_selectors

    produit = stock_selectors.get_produit_scoped(company, produit_id)
    if produit is None:
        return {}
    caracteristiques = {}
    for champ in CARACTERISTIQUES_SNAPSHOT:
        valeur = getattr(produit, champ, None)
        if valeur in (None, ''):
            continue
        caracteristiques[champ] = str(valeur)
    if getattr(produit, 'description', None):
        caracteristiques['description'] = produit.description
    return {
        'designation': produit.nom,
        'marque': produit.marque or '',
        'reference_constructeur': produit.sku or '',
        'caracteristiques': caracteristiques,
    }


def engager_equipement(appel_offre, *, role, produit_id=None, quantite=None,
                       batiment=None, caracteristiques=None, user=None,
                       **champs):
    """Engage un équipement dans le dossier en FIGEANT son snapshot (AOF118).

    Le snapshot est pris UNE fois, à l'engagement. Un re-seed du catalogue
    (prix, archivage, fiche) ne le touche plus : c'est ce qui rend un dossier
    déposé opposable.
    """
    from django.utils import timezone

    from .models import EquipementAO

    company = appel_offre.company
    donnees = dict(champs)
    if produit_id:
        donnees.update(snapshot_produit(company, produit_id))
    if caracteristiques:
        fusion = dict(donnees.get('caracteristiques') or {})
        fusion.update(caracteristiques)
        donnees['caracteristiques'] = fusion
    donnees.setdefault('designation', '')
    equipement = EquipementAO.objects.create(
        company=company, appel_offre=appel_offre, batiment=batiment,
        role=role, produit_id=produit_id or None,
        quantite=quantite if quantite is not None else Decimal('0.000'),
        snapshot_le=timezone.now(), **donnees)
    _journaliser_equipement(equipement, user)
    return equipement


def _journaliser_equipement(equipement, user):
    """Trace l'engagement au chatter générique ``records`` (best-effort)."""
    from apps.records.models import Activity
    from apps.records.services import log_activity

    log_activity(
        equipement.appel_offre, Activity.Kind.MODIFICATION, user=user,
        field='equipement', field_label='Équipement engagé',
        old_value='', new_value=str(equipement),
        company=equipement.company)


def aligner_quantite_modules(appel_offre, *, user=None):
    """Aligne la quantité de MODULES sur les variantes RETENUES (AOF118).

    La quantité de modules du dossier n'est pas une saisie : c'est la somme
    des engagements portés par les variantes retenues de chaque toiture. Un
    écart entre les deux est précisément ce que le contrôleur de cohérence
    (AOF146) doit voir.

    Renvoie ``(quantite_alignee, equipements_touches)``.
    """
    from .models import EquipementAO, VarianteCalepinage

    total = 0
    retenues = VarianteCalepinage.objects.filter(
        company=appel_offre.company, appel_offre=appel_offre,
        est_retenue=True)
    for variante in retenues:
        total += int(variante.total_modules or 0)
    touches = 0
    for equipement in EquipementAO.objects.filter(
            company=appel_offre.company, appel_offre=appel_offre,
            role=EquipementAO.Role.MODULE, actif=True):
        if equipement.quantite == Decimal(total):
            continue
        equipement.quantite = Decimal(total)
        equipement.save(update_fields=['quantite', 'updated_at'])
        touches += 1
    return Decimal(total), touches
