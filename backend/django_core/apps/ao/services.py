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


# ── AOF173 — Qui reprend ce texte normalisé ? ──────────────────────────────

def dossiers_impactes_par_section(section):
    """Les dossiers d'AO dont le mémoire REPREND cette section (AOF173).

    La réponse n'est pas une estimation : elle rejoue la MÊME règle
    déclarative que le rendu (``fabrique.rendus.memoire.sections_a_inclure``).
    Réimplémenter le filtre ici le ferait diverger — et l'écran
    d'avertissement dirait « aucun dossier » pendant que douze mémoires
    changeraient.

    Une section INACTIVE n'entre dans aucun mémoire ; une section SANS
    condition d'inclusion entre dans TOUS (aucun contexte à construire, donc
    aucune requête inutile pour le cas le plus fréquent).
    """
    from .fabrique.rendus.memoire import contexte_memoire, sections_a_inclure
    from .models import AppelOffre

    if not section.actif:
        return []
    dossiers = AppelOffre.objects.filter(
        company=section.company).order_by('-id')
    conditions = section.conditions_inclusion or {}
    impactes = []
    for appel_offre in dossiers:
        if conditions:
            retenues = sections_a_inclure(appel_offre.company,
                                          contexte_memoire(appel_offre))
            if section.pk not in {s.pk for s in retenues}:
                continue
        impactes.append({
            'id': appel_offre.pk,
            'reference': appel_offre.reference,
            'objet': appel_offre.objet,
            'statut': appel_offre.statut,
        })
    return impactes


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
        # AOF146 — le contrôleur de cohérence croisée est une PORTE : une
        # passe FRAÎCHE est exécutée ici, et le refus CITE le code de règle
        # fautif (un rapport qu'on lit après coup n'aurait rien empêché).
        from .fabrique.coherence import passer_controle

        passe = passer_controle(dossier)
        if passe['bloquants']:
            raise ValidationError({'controles': [
                f'{item["code_regle"]} — {item["message"]}'
                for item in passe['bloquants']
            ]})

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


# ── AOF136 — Checklist partenaire : les 7 blocs en lignes d'état ──────────
#
# La checklist réelle de remise, telle que remplie par le co-traitant. Chaque
# point devient une ligne SUIVIE (case + responsable + commentaire) ; un point
# obligatoire ouvert ferme la porte du dépôt (``raisons_de_non_depot``).

CHECKLIST_PARTENAIRE = (
    # 1 — CPS
    ('cps', 'CPS_BLANCS', 'Remplir tous les blancs du CPS'),
    ('cps', 'CPS_PARAPHE', 'Parapher CHAQUE page du CPS'),
    ('cps', 'CPS_MENTION',
     'Porter la mention manuscrite « lu et accepté » et signer'),
    # 2 — Acte d'engagement
    ('acte_engagement', 'ACTE_CHIFFRES_LETTRES',
     "Montant porté EN CHIFFRES ET EN LETTRES, identiques"),
    ('acte_engagement', 'ACTE_RIB', 'RIB complet du soumissionnaire'),
    ('acte_engagement', 'ACTE_VALIDITE',
     "Durée de validité de l'offre conforme au règlement"),
    # 3 — Bordereau des prix
    ('bordereau', 'BORDEREAU_INTACT',
     'NE MODIFIER AUCUN PRIX NI AUCUNE QUANTITÉ du bordereau transmis'),
    ('bordereau', 'BORDEREAU_SIGNE',
     'Bordereau paraphé et signé à la dernière page'),
    # 4 — Lettre de soumission
    ('lettre_soumission', 'LETTRE_MONTANTS',
     'Montants de la lettre identiques à ceux du bordereau'),
    ('lettre_soumission', 'LETTRE_CLAUSE_RESERVE',
     'Reporter la clause de réserve à l\'identique'),
    # 5 — Mémoire technique
    ('memoire', 'MEMOIRE_SIGNATURE',
     'Bloc signature du mémoire renseigné et signé'),
    ('memoire', 'MEMOIRE_ATTESTATIONS',
     'Attestations de bonne exécution jointes au mémoire'),
    # 6 — Dossier administratif
    ('administratif', 'ADM_DECLARATION',
     "Déclaration sur l'honneur signée"),
    ('administratif', 'ADM_POUVOIRS', 'Pouvoirs du signataire'),
    ('administratif', 'ADM_FISCALE',
     'Attestation fiscale de moins d\'un an'),
    ('administratif', 'ADM_CNSS', 'Attestation CNSS de moins de trois mois'),
    ('administratif', 'ADM_RC', 'Registre de commerce — modèle J'),
    ('administratif', 'ADM_RIB', 'RIB de la société'),
    ('administratif', 'ADM_ASSURANCE_RC',
     'Assurance responsabilité civile en cours de validité'),
    ('administratif', 'ADM_DECENNALE',
     'Assurance décennale étanchéité en cours de validité'),
    ('administratif', 'ADM_CAUTION', 'Caution provisoire constituée'),
    # 7 — Vérifications téléphoniques avant dépôt
    ('verifications', 'VERIF_PROROGATION',
     'Prorogation éventuelle confirmée PAR ÉCRIT'),
    ('verifications', 'VERIF_ATTESTATION_VISITE',
     'Attestation de visite des lieux obtenue'),
    ('verifications', 'VERIF_PLIS',
     'Plis séparés ou pli unique : confirmé auprès de l\'acheteur'),
)


def seeder_checklist_partenaire(dossier):
    """Crée les points de checklist manquants d'un dossier (idempotent).

    ADDITIF : un point déjà pointé (case, responsable, commentaire) n'est
    JAMAIS réécrit. Renvoie ``(crees, existants)``.
    """
    from .models import LigneChecklistPartenaire

    crees = existants = 0
    for ordre, (bloc, code, libelle) in enumerate(CHECKLIST_PARTENAIRE):
        if LigneChecklistPartenaire.objects.filter(
                dossier=dossier, code=code).exists():
            existants += 1
            continue
        LigneChecklistPartenaire.objects.create(
            company=dossier.company, dossier=dossier, bloc=bloc, code=code,
            libelle=libelle, ordre=ordre)
        crees += 1
    return crees, existants


def pointer_checklist(ligne, *, faite=True, responsable=None, commentaire=None,
                      user=None):
    """Pointe (ou dépointe) un point de checklist — le responsable est TRACÉ.

    Le responsable est posé côté serveur : soit celui explicitement désigné,
    soit l'utilisateur qui pointe. Un point sans responsable ne dit pas QUI
    répond de lui, et c'est précisément ce qu'une checklist papier ne dit pas.
    """
    from django.utils import timezone

    ligne.faite = bool(faite)
    ligne.responsable_utilisateur = (
        responsable or user or ligne.responsable_utilisateur)
    if commentaire is not None:
        ligne.commentaire = commentaire
    ligne.date_faite = timezone.now() if ligne.faite else None
    ligne.save(update_fields=[
        'faite', 'responsable_utilisateur', 'commentaire', 'date_faite',
        'updated_at'])
    _journaliser_checklist(ligne, user)
    return ligne


def _journaliser_checklist(ligne, user):
    """Trace le pointage au chatter générique ``records`` (best-effort)."""
    from apps.records.models import Activity
    from apps.records.services import log_activity

    log_activity(
        ligne.dossier, Activity.Kind.MODIFICATION, user=user,
        field='checklist', field_label=f'Checklist — {ligne.libelle}',
        old_value='', new_value='fait' if ligne.faite else 'ouvert',
        body=ligne.commentaire or '', company=ligne.company)


def points_checklist_ouverts(dossier):
    """Les points OBLIGATOIRES encore ouverts (queryset)."""
    return dossier.lignes_checklist.filter(obligatoire=True, faite=False)


# ── AOF137 — Pièces administratives : péremption MÉCANISÉE ────────────────
#
# La date qui compte est celle de la REMISE DES PLIS, jamais celle du jour :
# une attestation valable aujourd'hui mais expirée à l'ouverture fait rejeter
# le pli. Contrôler « à aujourd'hui » produirait un dossier vert qui sera
# rouge le jour J.

#: Sévérité des contrôles de pièces administratives.
SEVERITE_BLOQUANT = 'bloquant'
SEVERITE_AVERTISSEMENT = 'avertissement'


def controler_pieces_administratives(dossier, *, a_la_date=None):
    """Contrôle les pièces d'un dossier À LA DATE DE REMISE DES PLIS.

    Renvoie une liste de dicts ``{code, severite, message, piece_id}``.
    ``a_la_date`` permet de rejouer un contrôle à une date donnée (tests,
    simulation d'une prorogation) ; par défaut c'est la date de référence du
    dossier (ouverture des plis, sinon date limite de remise).
    """
    reference = a_la_date or dossier.date_reference_controle
    controles = []
    if reference is None:
        controles.append({
            'code': 'AO_DATE_REFERENCE_ABSENTE',
            'severite': SEVERITE_AVERTISSEMENT,
            'message': (
                "Ni date d'ouverture des plis ni date limite de remise : la "
                'péremption des pièces administratives ne peut pas être '
                'contrôlée.'),
            'piece_id': None,
        })
        return controles
    for piece in dossier.pieces_administratives.filter(actif=True):
        if piece.est_expiree_a(reference):
            controles.append({
                'code': 'AO_PIECE_ADMIN_EXPIREE',
                'severite': SEVERITE_BLOQUANT,
                'message': (
                    f'{piece.get_type_piece_display()} '
                    f'« {piece.libelle} » : émise le {piece.date_emission}, '
                    f'expirée le {piece.date_expiration} — donc EXPIRÉE à la '
                    f'date de remise des plis ({reference}).'),
                'piece_id': piece.pk,
            })
            continue
        restants = piece.jours_restants_a(reference)
        if restants is not None and restants <= (piece.rappel_jours or 0):
            controles.append({
                'code': 'AO_PIECE_ADMIN_BIENTOT_EXPIREE',
                'severite': SEVERITE_AVERTISSEMENT,
                'message': (
                    f'{piece.get_type_piece_display()} '
                    f'« {piece.libelle} » expire le {piece.date_expiration}, '
                    f'soit {restants} jour(s) avant la remise des plis '
                    f'({reference}) : à renouveler.'),
                'piece_id': piece.pk,
            })
    return controles


def pieces_administratives_a_renouveler(company, *, a_la_date=None):
    """Pièces dont l'expiration tombe dans leur fenêtre de rappel (J-N)."""
    from django.utils import timezone

    from .models import PieceAdministrative

    reference = a_la_date or timezone.localdate()
    a_renouveler = []
    for piece in PieceAdministrative.objects.filter(
            company=company, actif=True):
        restants = piece.jours_restants_a(reference)
        if restants is None:
            continue
        if restants <= (piece.rappel_jours or 0):
            a_renouveler.append(piece)
    return a_renouveler


def rattacher_piece_administrative(piece, dossier, *, user=None):
    """Rattache une pièce EXISTANTE à un dossier — sans dupliquer le fichier.

    C'est le point d'AOF137 : la même attestation fiscale sert deux appels
    d'offres, en un seul octet stocké.
    """
    if piece.company_id != dossier.company_id:
        raise ValidationError({'dossier': (
            "Une pièce administrative ne se rattache qu'à un dossier de la "
            'MÊME société.')})
    piece.dossiers.add(dossier)
    _journaliser_piece_administrative(piece, dossier, user)
    return piece


def _journaliser_piece_administrative(piece, dossier, user):
    """Trace le rattachement au chatter générique ``records`` (best-effort)."""
    from apps.records.models import Activity
    from apps.records.services import log_activity

    log_activity(
        dossier, Activity.Kind.MODIFICATION, user=user,
        field='piece_administrative',
        field_label='Pièce administrative rattachée',
        old_value='', new_value=str(piece), company=dossier.company)


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


# ── AOF140 — Planches : indices AUTOMATIQUES et citations vérifiables ─────
#
# L'indice n'est JAMAIS saisi : il s'incrémente sur CHANGEMENT D'EMPREINTE.
# Générer un indice supérieur archive le précédent ; la base interdit deux
# planches actives de même code (``uniq_planche_active_par_code``).

def indice_suivant(indice):
    """``A`` → ``B`` … ``Z`` → ``AA`` (numérotation bijective base 26)."""
    if not indice:
        return 'A'
    lettres = list(indice.upper())
    position = len(lettres) - 1
    while position >= 0:
        if lettres[position] != 'Z':
            lettres[position] = chr(ord(lettres[position]) + 1)
            return ''.join(lettres)
        lettres[position] = 'A'
        position -= 1
    return 'A' + ''.join(lettres)


def planche_active(appel_offre, code_document):
    """La planche ACTIVE d'un code, ou None."""
    from .models import PlancheAO

    return PlancheAO.objects.filter(
        company=appel_offre.company, appel_offre=appel_offre,
        code_document=code_document,
        statut=PlancheAO.Statut.ACTIVE).first()


def generer_indice_planche(appel_offre, code_document, *, empreinte,
                           motif='', variante=None, toiture=None,
                           cartouche=None, bandeau_engagement=None,
                           user=None):
    """Produit l'indice COURANT d'une planche (AOF140).

    * empreinte INCHANGÉE → la planche active est rendue telle quelle
      (``creee=False``) : on ne fabrique pas un indice pour rien ;
    * empreinte DIFFÉRENTE → la planche active est ARCHIVÉE et un indice
      supérieur est créé.

    Renvoie ``(planche, creee)``. L'indice n'est jamais lu d'un paramètre.
    """
    from django.db import transaction

    from .models import PlancheAO

    with transaction.atomic():
        courante = planche_active(appel_offre, code_document)
        if courante is not None and courante.empreinte == (empreinte or ''):
            return courante, False
        nouvel_indice = indice_suivant(courante.indice) if courante else 'A'
        if courante is not None:
            courante.statut = PlancheAO.Statut.ARCHIVEE
            courante.save(update_fields=['statut', 'updated_at'])
        planche = PlancheAO.objects.create(
            company=appel_offre.company, appel_offre=appel_offre,
            toiture=toiture, variante=variante,
            code_document=code_document, indice=nouvel_indice,
            empreinte=empreinte or '', motif_revision=motif or '',
            cartouche=cartouche or donnees_cartouche(
                appel_offre, code_document, nouvel_indice),
            bandeau_engagement=bandeau_engagement or donnees_bandeau(variante))
    _journaliser_planche(planche, courante, user)
    return planche, True


def donnees_cartouche(appel_offre, code_document, indice):
    """Le cartouche comme DONNÉES — jamais écrit à la main sur le dessin.

    AOF144 — une planche est une pièce CLIENT : son cartouche ne porte que le
    SOUMISSIONNAIRE, jamais le bureau d'exécution.
    """
    from .fabrique.identite import identite_client

    return {
        'code_document': code_document,
        'indice': indice,
        'objet': appel_offre.objet,
        'maitre_ouvrage': appel_offre.maitre_ouvrage or appel_offre.acheteur,
        'soumissionnaire': identite_client(appel_offre)['raison_sociale'],
        'reference_marche': appel_offre.reference_acheteur
        or appel_offre.reference,
    }


def donnees_bandeau(variante):
    """Le bandeau d'engagement comme DONNÉES (vide sans variante)."""
    if variante is None:
        return {}
    return {
        'modules_engages': variante.total_modules,
        'puissance_kwc': str(variante.puissance_kwc or ''),
        'variante': variante.nom,
        'methode': (variante.preuve or {}).get('methode', ''),
    }


def _journaliser_planche(planche, precedente, user):
    """Trace la révision au chatter générique ``records`` (best-effort)."""
    from apps.records.models import Activity
    from apps.records.services import log_activity

    log_activity(
        planche.appel_offre, Activity.Kind.MODIFICATION, user=user,
        field='planche', field_label=f'Planche {planche.code_document}',
        old_value=precedente.reference_complete if precedente else '',
        new_value=planche.reference_complete,
        body=planche.motif_revision or '', company=planche.company)


def citations_perimees(appel_offre):
    """Citations de planche pointant un indice qui n'est PLUS actif (AOF140).

    Renvoie une liste de dicts ``{citation_id, code_document, indice_cite,
    indice_actif, message}``. Liste vide = le mémoire cite juste.
    """
    from .models import CitationPlanche

    perimees = []
    for citation in CitationPlanche.objects.filter(
            company=appel_offre.company, appel_offre=appel_offre):
        active = planche_active(appel_offre, citation.code_document)
        indice_actif = active.indice if active else None
        if indice_actif is not None and citation.indice_cite == indice_actif:
            continue
        if indice_actif is None:
            message = (
                f'La planche « {citation.code_document} » citée '
                f'({citation.emplacement or "mémoire"}) n\'existe pas ou '
                f'n\'a plus de version active.')
        else:
            message = (
                f'La planche « {citation.code_document} » est citée à '
                f'l\'indice {citation.indice_cite or "(aucun)"} alors que '
                f'l\'indice courant est {indice_actif} '
                f'({citation.emplacement or "mémoire"}).')
        perimees.append({
            'citation_id': citation.pk,
            'code_document': citation.code_document,
            'indice_cite': citation.indice_cite,
            'indice_actif': indice_actif,
            'message': message,
        })
    return perimees


def totaux_bordereau(bordereau):
    """AOF120 — les totaux du bordereau, RECALCULÉS côté serveur.

    Aucun total n'est stocké : une colonne recopiée diverge dès la première
    ligne modifiée, et c'est le total qui part chez le maître d'ouvrage.
    """
    return {
        'sous_total_ht': bordereau.sous_total_ht,
        'remise_globale_pct': bordereau.remise_globale_pct,
        'montant_remise_globale': bordereau.montant_remise_globale,
        'total_ht': bordereau.total_ht,
        'tva_par_taux': {str(taux): montant
                         for taux, montant in bordereau.tva_par_taux.items()},
        'total_tva': bordereau.total_tva,
        'total_ttc': bordereau.total_ttc,
    }


def raisons_bordereau_non_remettable(bordereau):
    """Motifs, en français, qui interdisent de remettre ce bordereau (AOF120).

    Liste vide = remettable. Deux familles : la clause de réserve manquante
    sur un marché à prix unitaires, et une quantité annoncée « issue du
    calepinage » sans variante citée.
    """
    raisons = list(bordereau.raisons_de_non_conformite())
    for ligne in bordereau.lignes.all():
        raisons.extend(ligne.raisons_de_non_tracabilite())
    return raisons


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


# ── AOF141 — Bascule d'équipement : UNE transaction, ou RIEN ───────────────
#
# ``fabrique/bascule_rapport.py`` DÉCRIT ce contrat depuis AOF142 sans que
# personne ne l'applique : « l'application atomique de la bascule est le rôle
# de ``services.basculer_equipement`` ». Le défaut réel qu'il combat est une
# bascule PARTIELLE — le dossier du 27/07 a changé de batterie, le montant a
# cascadé, et la fiche technique annexée comme la justification d'un texte
# sont restées sur l'ancien matériel. Une bascule à moitié faite est PIRE que
# pas de bascule : le pli part avec deux vérités contradictoires.
#
# D'où la règle de ce module : les six gestes (snapshot figé, grandeurs
# dérivées, fiche annexée ajoutée, ancienne retirée, chaînage ``remplace``,
# péremption des artefacts) tiennent dans UNE ``transaction.atomic()``. Si
# l'un échoue, AUCUN n'est écrit — pas de dossier à demi basculé.
#
# Aucun PRIX n'entre ni ne sort d'ici : un équipement d'AO alimente des pièces
# remises au maître d'ouvrage. Les dicts ``ancien``/``nouveau`` remis au
# rapport ne portent DÉLIBÉRÉMENT aucune clé de prix (le détecteur de prix
# resté en arrière est donc muet par construction, plutôt que nourri d'un coût
# qui n'a rien à faire là).


def _identifiant(valeur, champ):
    """Identifiant ENTIER, ou un 400 motivé — jamais une erreur 500 de l'ORM.

    ``Produit.objects.filter(id='abc')`` lève une ``ValueError`` que DRF ne
    rattrape pas : un corps de requête fautif rendrait un 500 muet là où la
    faute est côté client.
    """
    try:
        return int(valeur)
    except (TypeError, ValueError) as exc:
        raise ValidationError({champ: (
            f'Identifiant « {valeur} » invalide : un entier est attendu.'
        )}) from exc


def _fiches_annexees(appel_offre):
    """Les fiches techniques ANNEXÉES aujourd'hui, au format ``annexes``.

    Format d'entrée de ``fabrique/annexes.py`` : une fiche cite l'équipement
    qu'elle documente par sa RÉFÉRENCE constructeur.
    """
    from .models import EquipementAO

    return [
        {'reference_equipement': equipement.reference_constructeur,
         'titre': equipement.designation,
         'attachment': equipement.fiche_technique_id}
        for equipement in EquipementAO.objects.filter(
            company=appel_offre.company, appel_offre=appel_offre,
            actif=True).exclude(fiche_technique__isnull=True)
    ]


def _textes_libres_du_dossier(appel_offre):
    """Textes libres du dossier où une référence peut être restée en arrière.

    Les deux gisements RÉELS du défaut : les désignations du bordereau (qui
    nomment le matériel) et les textes normalisés du mémoire (où une
    justification se fige à la main). Chacun est cité avec son emplacement,
    pour que le rapport dise OÙ regarder et pas seulement QUE quelque chose
    cloche.
    """
    from .models import LigneBordereau, SectionMemoire

    textes = []
    for ligne in LigneBordereau.objects.filter(
            company=appel_offre.company,
            bordereau__appel_offre=appel_offre).select_related('bordereau'):
        textes.append({
            'emplacement': f'bordereau ligne {ligne.numero}',
            'texte': ligne.designation or '',
        })
    for section in SectionMemoire.objects.filter(
            company=appel_offre.company, actif=True):
        textes.append({
            'emplacement': f'mémoire §{section.code}',
            'texte': section.corps or '',
        })
    return textes


def _perimer_artefacts_du_dossier(appel_offre):
    """PÉRIME les artefacts que la bascule vient de rendre faux (AOF146).

    Rien n'est recodé : l'empreinte de dossier et la passe de cohérence
    EXISTENT (``fabrique/coherence.py``). L'empreinte inclut les équipements
    actifs, donc une bascule la fait bouger mécaniquement — toute pièce
    produite sous l'empreinte antérieure devient PÉRIMÉE, et la passe
    rejouée l'inscrit en base (règle ``AO_ARTEFACT_PERIME``) au lieu de
    laisser un fichier frère attendre d'être déposé à la place du bon.

    Renvoie la liste des pièces périmées (vide si le dossier n'existe pas
    encore : un AO sans dossier de dépôt n'a aucun artefact à périmer).
    """
    from .fabrique.coherence import empreinte_dossier, passer_controle

    dossier = getattr(appel_offre, 'dossier_ao', None)
    if dossier is None:
        return []
    courante = empreinte_dossier(dossier)
    perimees = [
        {'code': piece.code, 'libelle': piece.libelle,
         'empreinte_source': piece.empreinte_source,
         'empreinte_courante': courante}
        for piece in dossier.pieces.all()
        if piece.empreinte_source and piece.empreinte_source != courante
    ]
    passer_controle(dossier)
    return perimees


def basculer_equipement(equipement, nouveau_produit, *, user=None,
                        fiche_technique=None, motif=''):
    """AOF141 — remplace un équipement engagé par un autre produit, EN UNE FOIS.

    ``nouveau_produit`` : identifiant (ou objet portant un ``pk``) d'un produit
    du catalogue de la MÊME société — lu par ``apps.stock.selectors`` via
    ``snapshot_produit``, jamais par un import de ``apps.stock.models``.
    ``fiche_technique`` : ``records.Attachment`` de la fiche du NOUVEAU
    matériel ; l'ancienne est retirée de l'annexe dans le même geste.

    Les six gestes, dans UNE transaction :

    1. le NOUVEAU snapshot est FIGÉ depuis le produit cible (désignation,
       marque, référence, caractéristiques) — jamais recalculé ensuite ;
    2. les grandeurs DÉRIVÉES qui en dépendent sont recalculées (la quantité
       de modules se redérive des variantes retenues, elle ne se saisit pas) ;
    3. la nouvelle fiche technique est ANNEXÉE ;
    4. l'ancienne est RETIRÉE — le même appel fait les deux moitiés, parce que
       c'est leur séparation qui produit le dossier à deux fiches ;
    5. ``remplace`` chaîne le nouvel équipement à son prédécesseur, désactivé ;
    6. les artefacts documentaires impactés sont PÉRIMÉS.

    Renvoie ``{'equipement', 'ancien', 'rapport', 'artefacts_perimes'}``. Le
    rapport est celui d'AOF142 : ce qui a changé ET les textes qui portent
    ENCORE l'ancienne référence — ils ne sont pas réécrits d'office, ils sont
    NOMMÉS avec leur extrait.
    """
    from django.db import transaction

    from .fabrique import annexes
    from .fabrique.bascule_rapport import rapport_bascule
    from .models import EquipementAO, VarianteCalepinage

    appel_offre = equipement.appel_offre
    company = equipement.company
    if not equipement.actif:
        raise ValidationError({'equipement': (
            "Cet équipement n'est plus actif : il a déjà été basculé. "
            "Basculer un équipement retiré créerait une deuxième chaîne de "
            "remplacement et le dossier ne saurait plus quel matériel il "
            "engage.")})
    produit_id = getattr(nouveau_produit, 'pk', nouveau_produit)
    if produit_id in (None, ''):
        raise ValidationError({'produit': (
            "Aucun produit cible : une bascule doit NOMMER le matériel qui "
            "remplace l'ancien.")})
    produit_id = _identifiant(produit_id, 'produit')
    if equipement.produit_id and equipement.produit_id == produit_id:
        raise ValidationError({'produit': (
            "L'équipement porte déjà ce produit : la bascule n'aurait rien à "
            "figer et laisserait une chaîne de remplacement vide.")})
    instantane = snapshot_produit(company, produit_id)
    if not instantane:
        raise ValidationError({'produit': (
            "Produit introuvable dans le catalogue de cette société : le "
            "snapshot serait vide, donc le dossier engagerait un matériel "
            "sans désignation.")})

    attachement = None
    if fiche_technique not in (None, ''):
        from apps.records.models import Attachment

        attachement = Attachment.objects.filter(
            pk=_identifiant(getattr(fiche_technique, 'pk', fiche_technique),
                            'fiche_technique'),
            company=company).first()
        if attachement is None:
            raise ValidationError({'fiche_technique': (
                "Fiche technique introuvable pour cette société.")})

    ancien_snapshot = {
        'designation': equipement.designation,
        'reference': equipement.reference_constructeur,
        'marque': equipement.marque,
        'unite': equipement.unite,
        'caracteristiques': dict(equipement.caracteristiques or {}),
    }
    nouveau_snapshot = {
        'designation': instantane.get('designation', ''),
        'reference': instantane.get('reference_constructeur', ''),
        'marque': instantane.get('marque', ''),
        'unite': equipement.unite,
        'caracteristiques': dict(instantane.get('caracteristiques') or {}),
    }

    with transaction.atomic():
        nouveau = engager_equipement(
            appel_offre, role=equipement.role, produit_id=produit_id,
            quantite=equipement.quantite, batiment=equipement.batiment,
            user=user, unite=equipement.unite, remplace=equipement,
            fiche_technique=attachement)
        emplacements = [f'équipement {equipement.role} (snapshot figé)']

        # 3 + 4 — les DEUX moitiés de l'annexe dans le MÊME appel.
        nouvelle_fiche = None
        if attachement is not None:
            nouvelle_fiche = {
                'reference_equipement': nouveau.reference_constructeur,
                'titre': nouveau.designation,
                'attachment': attachement.pk,
            }
        try:
            restantes = annexes.appliquer_bascule(
                _fiches_annexees(appel_offre),
                ancienne_reference=equipement.reference_constructeur,
                nouvelle_fiche=nouvelle_fiche)
        except ValueError as exc:
            # Une fiche qui ne cite aucun équipement serait orpheline dès son
            # ajout : on REFUSE la bascule entière plutôt que d'annexer un
            # document que rien ne rattache au matériel fourni.
            raise ValidationError({'fiche_technique': str(exc)}) from exc
        annexees = {str(fiche.get('reference_equipement'))
                    for fiche in restantes}

        # 5 — le prédécesseur sort du dossier, et sa fiche sort de l'annexe.
        champs = ['actif', 'updated_at']
        equipement.actif = False
        if str(equipement.reference_constructeur) not in annexees:
            equipement.fiche_technique = None
            champs.insert(1, 'fiche_technique')
        equipement.save(update_fields=champs)
        emplacements.append('annexe des fiches techniques')

        # 2 — grandeurs DÉRIVÉES. L'alignement n'est joué QUE s'il existe une
        # variante retenue : sans variante, le total dérivé vaut zéro et
        # écraserait une quantité légitime par un chiffre faux.
        if nouveau.role == EquipementAO.Role.MODULE and \
                VarianteCalepinage.objects.filter(
                    company=company, appel_offre=appel_offre,
                    est_retenue=True).exists():
            aligner_quantite_modules(appel_offre, user=user)
            nouveau.refresh_from_db()
            emplacements.append('quantité de modules (dérivée du calepinage)')

        # 6 — péremption des artefacts que la bascule vient de rendre faux.
        perimes = _perimer_artefacts_du_dossier(appel_offre)
        emplacements.extend(f'pièce {piece["code"]}' for piece in perimes)

        rapport = rapport_bascule(
            ancien_snapshot, nouveau_snapshot,
            emplacements_modifies=emplacements,
            textes=_textes_libres_du_dossier(appel_offre))
        _journaliser_bascule(equipement, nouveau, user, motif)

    return {
        'equipement': nouveau,
        'ancien': equipement,
        'rapport': rapport,
        'artefacts_perimes': perimes,
    }


def _journaliser_bascule(ancien, nouveau, user, motif):
    """Trace la bascule au chatter générique ``records`` (jamais une classe maison)."""
    from apps.records.models import Activity
    from apps.records.services import log_activity

    log_activity(
        nouveau.appel_offre, Activity.Kind.MODIFICATION, user=user,
        field='equipement_bascule', field_label="Bascule d'équipement",
        old_value=str(ancien), new_value=str(nouveau),
        body=motif or '', company=nouveau.company)


# ── AOF163 — Point d'entrée VILLA du moteur PARTAGÉ, sans projet AO ────────
#
# Le moteur ``core/calepinage`` a DEUX consommateurs qui ne peuvent pas
# s'importer l'un l'autre : ``apps.ao`` et ``apps.ventes``. Le format
# d'obstacle AO (rectangle + dégagement PAR obstacle + PROVENANCE) est le
# format CANONIQUE : la villa s'y adapte par
# ``core.calepinage.adaptateurs.villa`` (AOF162), jamais l'inverse.
#
# Ces fonctions sont PURES au sens base de données : elles ne lisent et
# n'écrivent AUCUNE ligne AO. Un appel villa ne doit laisser aucune trace dans
# ``apps/ao`` — un ``AppelOffre`` fantôme par simulation de villa serait à la
# fois une fuite de données et un compteur faux (test dédié).


def _entree_calepinage_canonique(*, repere, surface, kits, parametres,
                                 obstacles=(), zones=()):
    """Assemble l'``EntreeCalepinage`` canonique (format AO) — sans ORM.

    ``appliquer_regles`` DÉRIVE le dégagement de chaque obstacle depuis son
    type et sa provenance : le moteur ne devine jamais un dégagement en
    silence, et la villa hérite donc exactement de la même règle que l'AO.
    """
    from core.calepinage.obstacles import appliquer_regles
    from core.calepinage.serialisation import EntreeCalepinage

    return EntreeCalepinage(
        repere=repere, surfaces=(surface,), kits=tuple(kits),
        parametres=parametres,
        obstacles=tuple(appliquer_regles(tuple(obstacles))),
        zones=tuple(zones))


def _preuve_publiable(resultat, politique):
    """``ResultatOptimum`` -> preuve sérialisable (aucun coût, aucun prix)."""
    return {
        'methode': resultat.preuve.methode.value,
        'pas_recherche_m': resultat.preuve.pas_recherche_m,
        'compte_retenu': resultat.preuve.compte_retenu,
        'compte_optimal': resultat.preuve.compte_optimal,
        'borne_superieure': resultat.preuve.borne_superieure,
        'nb_plans_optimaux': resultat.preuve.nb_plans_optimaux,
        'ecart_a_l_optimum': resultat.ecart_a_l_optimum,
        'politique_pas': getattr(politique, 'code', ''),
    }


def calepiner_surface(*, surface, kits, parametres, obstacles=(), zones=(),
                      politique=None, repere='SURFACE'):
    """Calepine UNE enveloppe et ses obstacles — SANS aucun projet AO.

    C'est le point d'entrée PARTAGÉ : la villa (``apps.ventes``, qui lit via
    ``apps.ao.selectors``) et l'AO passent par le MÊME moteur sur le MÊME
    format d'entrée. Aucune ligne n'est créée, aucune n'est lue : la fonction
    ne touche pas l'ORM (elle est appelable hors transaction, hors société).

    Rend un dict ``{'entree', 'resultat', 'preuve', 'rangees', 'tables'}`` où
    ``resultat`` est un ``ResultatCalepinage`` — le MÊME objet que le chemin
    AO, porteur du couple ``(hash_entree, version_moteur)``.
    """
    from core.calepinage.perf import optimiser_economique
    from core.calepinage.poseur import poser_plan
    from core.calepinage.serialisation import ResultatCalepinage

    entree = _entree_calepinage_canonique(
        repere=repere, surface=surface, kits=kits, parametres=parametres,
        obstacles=obstacles, zones=zones)
    calcul = optimiser_economique(entree.surfaces[0], entree.parametres,
                                  entree.obstacles, entree.zones, politique)
    rangees = tuple((y0, entree.parametres.kit(code))
                    for y0, code in calcul.rangees)
    tables = poser_plan(entree.surfaces[0], rangees, entree.obstacles,
                        entree.zones)
    return {
        'entree': entree,
        'resultat': ResultatCalepinage.depuis_resultat(entree, calcul),
        'preuve': _preuve_publiable(calcul, politique),
        'rangees': calcul.rangees,
        'tables': tuple(tables),
    }


def calepiner_villa(area, *, ordre='lnglat', kit=None, retrait_m=None,
                    pas_recherche_m=0.01):
    """Calepine une toiture VILLA (``AreaRecord`` du lecteur de cartes).

    ``ordre`` est EXPLICITE et jamais deviné : le lecteur de cartes sérialise
    en ``[lng, lat]`` (GeoJSON) tandis que le lead CRM stocke ``[lat, lng]`` —
    une confusion produit une toiture retournée, plausible et fausse.

    Aucune ligne AO n'est créée ni lue : une villa n'a pas de projet AO.
    Rend le même dict que ``calepiner_surface`` + ``projection``,
    ``politique`` et ``panneaux`` (structure compatible avec l'écran existant,
    pour ne rien casser côté front).
    """
    from core.calepinage.adaptateurs.villa import (
        RETRAIT_VILLA_M, vers_entree, vers_panneaux,
    )
    from core.calepinage.types import KIT_VILLA_720

    kit = kit or KIT_VILLA_720
    entree, projection, politique = vers_entree(
        area, ordre=ordre, kit=kit,
        retrait_m=RETRAIT_VILLA_M if retrait_m is None else retrait_m,
        pas_recherche_m=pas_recherche_m)
    sortie = calepiner_surface(
        surface=entree.surfaces[0], kits=entree.kits,
        parametres=entree.parametres, obstacles=entree.obstacles,
        zones=entree.zones, politique=politique, repere=entree.repere)
    sortie['projection'] = projection
    sortie['politique'] = politique
    sortie['panneaux'] = vers_panneaux(sortie['tables'], projection, kit)
    return sortie


# ── AOF169 — l'AMONT du tunnel : créer une affaire depuis un AVIS publié ───
#
# **Aucun scraping, jamais** (règle #5 du dépôt). La source d'un avis est un
# FICHIER importé ou une saisie manuelle : aucun appel réseau vers le portail
# national des marchés publics — ni vers aucun autre portail — n'existe dans
# ``apps/ao``, et un test de grep l'impose sur tout le paquet (le nom de
# domaine est lui-même un motif interdit, il n'est donc écrit nulle part).
# La collecte AUTOMATIQUE est traitée dans une app SÉPARÉE
# (``apps/veille_ao``, Groupe VAO), sous gate intégral de la règle #5.
#
# Cette fonction est le POINT DE CONTACT UNIQUE de l'amont : l'import de
# fichier, la saisie manuelle et — le jour où il existera — le sas de veille
# passent tous par elle. C'est ce qui garantit qu'il n'y aura jamais deux
# chemins de création d'affaire avec deux règles de déduplication différentes.

#: Champs d'avis reportables sur un AO EXISTANT lors d'un ré-import.
#: ``reference`` (NOTRE numérotation) et ``statut`` n'en sont PAS : un avis
#: rectifié ne renumérote pas un dossier et ne le fait pas reculer d'étape.
CHAMPS_AVIS = (
    'objet', 'acheteur', 'maitre_ouvrage', 'lot', 'montant_estime',
    'caution_provisoire', 'date_limite', 'date_ouverture_plis',
    'mode_passation', 'type_marche',
)


def creer_appel_offre_depuis_avis(company, avis, *, user=None):
    """Crée — ou met à jour — l'affaire correspondant à un avis publié.

    Déduplication par ``reference_acheteur`` DANS LA SOCIÉTÉ : deux acheteurs
    différents peuvent parfaitement publier la même référence, et deux sociétés
    du même ERP ne partagent jamais leurs dossiers.

    Rend ``(appel_offre, cree)``. La création passe par
    ``creer_appel_offre_avec_reference`` (donc ``core.numbering``) : NOTRE
    référence ``AO-YYYYMM-0001`` reste générée par la plateforme, jamais
    recopiée depuis l'avis — la référence de l'acheteur vit dans son propre
    champ, et les confondre rendrait impossible de retrouver un dossier depuis
    l'avis publié.
    """
    reference_acheteur = (avis or {}).get('reference_acheteur') or ''
    reference_acheteur = str(reference_acheteur).strip()
    if not reference_acheteur:
        raise ValidationError(
            {'reference_acheteur': "La référence de l'acheteur est "
                                   'obligatoire : elle déduplique les avis.'})

    # Une valeur ABSENTE de l'avis laisse le défaut du modèle (``montant_estime``
    # et ``caution_provisoire`` sont NON NULS) : on ne pousse jamais un ``None``
    # dans un champ qui n'en accepte pas.
    valeurs = {champ: avis[champ] for champ in CHAMPS_AVIS
               if champ in avis and avis[champ] is not None}

    existant = AppelOffre.objects.filter(
        company=company, reference_acheteur=reference_acheteur).first()
    if existant is not None:
        modifies = []
        for champ, valeur in valeurs.items():
            # Un avis rectifié qui ne redit PAS une valeur ne doit pas
            # l'effacer : seules les valeurs réellement portées écrasent.
            if valeur in (None, ''):
                continue
            if getattr(existant, champ) != valeur:
                setattr(existant, champ, valeur)
                modifies.append(champ)
        if modifies:
            existant.save(update_fields=modifies)
        return (existant, False)

    def _creer(reference):
        return AppelOffre.objects.create(
            company=company, reference=reference,
            reference_acheteur=reference_acheteur,
            statut=AppelOffre.Statut.IDENTIFIE, **valeurs)

    return (creer_appel_offre_avec_reference(company, _creer), True)
