"""Services (écritures / orchestration) du module « Veille appels d'offres ».

FRONTIÈRE INTER-APPS (import-linter) — une AUTRE app qui a besoin d'écrire
dans ce module ou d'orchestrer une action passe par une fonction de CE fichier
(jamais en important ``apps.veille_ao.models``/``.views`` directement).

VAO10 — les règles d'exclusion. Le principe qui gouverne tout ce fichier :
**aucun filtrage muet**. Quand une règle écarte un avis, l'avis GARDE la trace
de la règle qui l'a écarté, et la règle compte ses applications. Un utilisateur
doit toujours pouvoir répondre à « pourquoi je ne vois pas cet avis ? » et
faire marche arrière en un geste (désactiver la règle).

VAO14 — ``changer_statut_avis`` est le **SEUL** point de mutation du statut
d'un avis, dans tout le dépôt. Une garde d'introspection le vérifie
(``tests/test_statuts.py``) : aucun autre fichier du module n'a le droit
d'écrire ``avis.statut``.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .hashing import empreinte_avis
from .models import (
    AvisMarche, DeclencheurCollecte, ExecutionCollecte, Informateur,
    PorteeExclusion, RegleExclusion, SourceVeille, StatutAvis, TypeSource,
    TYPES_COLLECTABLES, VerdictExecution,
)
from .scoring import normaliser

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────
# VAO14 — le SEUL point de mutation du statut d'un avis.
# ─────────────────────────────────────────────────────────────────────────

#: Table de transitions DÉCLARATIVE. Elle se lit, elle ne se déduit pas.
#: Un avis « nouveau » se trie (retenu ou ignoré) ; un avis « retenu » se
#: convertit en appel d'offres ; **tout** avis peut expirer.
#: Volontairement STRICTE : élargir un chemin est un choix explicite, pas un
#: effet de bord. Un statut vers LUI-MÊME n'est pas une transition — il est
#: refusé, pour qu'un appelant distrait ne réécrive pas un historique plat.
#: ``ignore`` → ``retenu`` est OUVERT (VAO30) : la marche arrière doit être
#: triviale. « Ignorer » est un geste rapide, fait le matin sur une liste ;
#: s'en dédire une heure plus tard ne doit pas demander de recréer l'avis à la
#: main — c'est exactement le même principe qu'une règle d'exclusion qu'on
#: désactive (VAO10). Le chatter garde la trace des deux gestes.
TRANSITIONS_AVIS = {
    StatutAvis.NOUVEAU: (StatutAvis.RETENU, StatutAvis.IGNORE,
                         StatutAvis.EXPIRE),
    StatutAvis.RETENU: (StatutAvis.CONVERTI, StatutAvis.EXPIRE),
    StatutAvis.IGNORE: (StatutAvis.RETENU, StatutAvis.EXPIRE),
    StatutAvis.CONVERTI: (StatutAvis.EXPIRE,),
    StatutAvis.EXPIRE: (),
}

#: Motif écrit au chatter quand c'est le SYSTÈME qui expire un avis.
MOTIF_EXPIRATION_AUTOMATIQUE = 'Date limite de remise dépassée.'


def transitions_possibles(statut):
    """Les statuts atteignables depuis ``statut`` (jamais une devinette)."""
    return TRANSITIONS_AVIS.get(statut, ())


def _journaliser_statut(avis, ancien, nouveau, user, motif):
    """Trace la transition au chatter générique ``records`` (ARC8).

    JAMAIS une classe ``*Activity`` maison : ``veille_ao.avismarche`` est
    déclaré dans ``platform.record_targets`` (VAO13), ce qui suffit à ouvrir
    ``records.Activity`` sur ce modèle. L'utilisateur agissant et la société
    sont posés CÔTÉ SERVEUR, jamais lus d'une requête.
    """
    from apps.records.models import Activity
    from apps.records.services import log_activity

    libelles = dict(StatutAvis.choices)
    log_activity(
        avis, Activity.Kind.MODIFICATION, user=user,
        field='statut', field_label='Statut',
        old_value=libelles.get(ancien, ancien),
        new_value=libelles.get(nouveau, nouveau),
        body=motif or '', company=avis.company)


def changer_statut_avis(avis, nouveau, user=None, motif='',
                        champs_supplementaires=None):
    """LE point de mutation du statut d'un avis — il n'y en a pas d'autre.

    Refuse en **400 avec un message en français** toute transition absente de
    ``TRANSITIONS_AVIS``, et écrit à chaque transition réussie une activité
    ``records`` (qui, quand, pourquoi).

    ``champs_supplementaires`` permet à un appelant d'écrire, DANS LA MÊME
    sauvegarde, les champs qui accompagnent la transition (la règle qui a
    filtré l'avis, l'identifiant de l'appel d'offres créé) — sans jamais
    ouvrir une seconde porte sur le statut lui-même.

    **Aucun signal ``core/events.py`` n'est déclaré ni émis** : le dépôt fait
    rougir la CI sur tout signal sans abonné réel, et rien ici n'a besoin d'un
    abonné cross-app.
    """
    libelles = dict(StatutAvis.choices)
    if nouveau not in libelles:
        raise ValidationError(
            {'statut': [f'Statut inconnu : « {nouveau} ».']})

    ancien = avis.statut
    autorises = transitions_possibles(ancien)
    if nouveau not in autorises:
        atteignables = ', '.join(
            f'« {libelles[s]} »' for s in autorises) or 'aucun'
        raise ValidationError({'statut': [
            f'Transition interdite : « {libelles.get(ancien, ancien)} » → '
            f'« {libelles[nouveau]} ». Statuts atteignables : '
            f'{atteignables}.']})

    champs = dict(champs_supplementaires or {})
    if 'statut' in champs:
        raise ValidationError({'statut': [
            'Le statut ne se pose pas par un champ supplémentaire : il passe '
            'par ce service et par lui seul.']})

    avis.statut = nouveau
    for nom, valeur in champs.items():
        setattr(avis, nom, valeur)
    avis.save(update_fields=['statut', *champs, 'updated_at'])

    _journaliser_statut(avis, ancien, nouveau, user, motif)
    return avis


def expirer_avis_depasses(queryset, maintenant=None, user=None):
    """Fait expirer les avis ouverts dont la date limite est passée.

    Passe par ``changer_statut_avis`` comme tout le monde : l'expiration
    automatique n'est PAS une exception au point de passage unique, elle en
    est simplement l'appelant SYSTÈME (``user=None``). Chaque bascule laisse
    donc sa trace au chatter, avec son motif.
    """
    bascules = 0
    for avis in queryset.depasses(maintenant):
        changer_statut_avis(avis, StatutAvis.EXPIRE, user=user,
                            motif=MOTIF_EXPIRATION_AUTOMATIQUE)
        bascules += 1
    return bascules


def _valeur_de_l_avis(avis, portee):
    """Le champ de l'avis que cette portée compare."""
    if portee == PorteeExclusion.ACHETEUR:
        return avis.acheteur or ''
    if portee == PorteeExclusion.LIBELLE:
        return avis.objet or ''
    if portee == PorteeExclusion.CATEGORIE:
        return avis.categorie or ''
    if portee == PorteeExclusion.REGION:
        return avis.region or ''
    return ''


def regle_mord(regle, avis):
    """Cette règle écarte-t-elle cet avis ?

    La catégorie est comparée à l'IDENTIQUE (c'est une valeur fermée) ; les
    trois autres portées sont des recherches de sous-chaîne normalisées
    (casse, accents et espaces neutralisés).
    """
    cible = normaliser(_valeur_de_l_avis(avis, regle.portee))
    aiguille = normaliser(regle.valeur)
    if not aiguille or not cible:
        return False
    if regle.portee == PorteeExclusion.CATEGORIE:
        return cible == aiguille
    return aiguille in cible


def regles_actives(company):
    """Les règles actives d'UNE société (jamais tous les tenants)."""
    return list(RegleExclusion.objects.filter(company=company).actives())


def regle_correspondante(avis, regles=None):
    """La PREMIÈRE règle active qui écarte cet avis, ou ``None``.

    Lecture pure : ne modifie ni l'avis ni la règle.
    """
    if regles is None:
        regles = regles_actives(avis.company)
    for regle in regles:
        if regle_mord(regle, avis):
            return regle
    return None


def appliquer_regles_exclusion(avis, regles=None, user=None):
    """Marque l'avis ``ignore`` s'il est capté par une règle active.

    Renvoie la règle appliquée, ou ``None`` si aucune ne mord.

    Trois garanties non négociables :
      * la bascule passe par ``changer_statut_avis`` (VAO14) comme toutes les
        autres — l'exclusion automatique n'a pas sa propre porte ;
      * l'avis ENREGISTRE quelle règle l'a filtré (jamais un filtrage muet),
        et le motif de la règle part au chatter ;
      * la règle incrémente son compteur d'application de façon atomique
        (``F()``), jamais par lecture-modification-écriture.

    Un avis déjà ignoré n'est pas re-basculé : la table de transitions refuse
    ``ignore`` → ``ignore``, et une re-collecte ne doit pas empiler des
    activités identiques au chatter.
    """
    regle = regle_correspondante(avis, regles)
    if regle is None:
        return None
    if avis.statut == StatutAvis.IGNORE:
        return regle

    changer_statut_avis(
        avis, StatutAvis.IGNORE, user=user,
        motif=f'Règle d\'exclusion : {regle.motif}',
        champs_supplementaires={'regle_exclusion': regle})
    RegleExclusion.objects.filter(pk=regle.pk).update(
        compteur_application=F('compteur_application') + 1)
    regle.refresh_from_db(fields=['compteur_application'])
    return regle


def proposer_regle_pour_avis(avis, portee=PorteeExclusion.ACHETEUR):
    """Propose une règle à partir d'un avis — **sans jamais la créer**.

    « Ignorer » doit APPRENDRE, mais l'apprentissage ne se fait pas en
    douce : l'écran propose, l'utilisateur décide. Cette fonction rend un
    brouillon (portée, valeur, motif suggéré) et n'écrit rien en base.

    ``existe_deja`` dit si une règle identique est déjà enregistrée, pour que
    l'écran propose de la RÉACTIVER plutôt que d'en créer une jumelle.
    """
    valeur = (_valeur_de_l_avis(avis, portee) or '').strip()
    libelle_portee = PorteeExclusion(portee).label
    existante = RegleExclusion.objects.filter(
        company=avis.company, portee=portee, valeur=valeur).first()
    return {
        'portee': portee,
        'portee_libelle': libelle_portee,
        'valeur': valeur,
        'motif_suggere': (
            f'Ignoré depuis un avis — {libelle_portee.lower()} « {valeur} »'
            if valeur else ''),
        'existe_deja': existante is not None,
        'regle_existante_id': existante.pk if existante else None,
        'regle_existante_active': (
            existante.actif if existante is not None else None),
    }


def avis_ignores_par(regle):
    """Les avis que CETTE règle a écartés (pour l'écran de la règle)."""
    return AvisMarche.objects.filter(
        company=regle.company, regle_exclusion=regle)


# ─────────────────────────────────────────────────────────────────────────
# VAO11 — dédoublonnage à DEUX niveaux : le cœur de fiabilité du groupe.
# ─────────────────────────────────────────────────────────────────────────

#: Les champs qu'une rectification a le droit de mettre à jour sur un avis
#: déjà connu. Le STATUT n'y est PAS : un avis que l'utilisateur a retenu ou
#: ignoré ne doit jamais être ramené à « nouveau » par une re-collecte.
CHAMPS_RECTIFIABLES = (
    'ref_consultation', 'org_acronyme', 'reference_avis', 'objet',
    'acheteur', 'lieu', 'region', 'procedure', 'categorie', 'lot',
    'date_publication', 'date_limite_remise', 'date_ouverture',
    'montant_estime', 'caution_provisoire', 'url_detail',
    # VAO27 — l'informateur est rectifiable : un avis d'abord collecté puis
    # signalé à la main doit pouvoir GAGNER son tuyau. Il n'est jamais EFFACÉ
    # par une re-collecte, qui ne le porte simplement pas.
    'informateur',
)


def calculer_empreinte(donnees):
    """L'empreinte de niveau 2 d'un dictionnaire d'avis."""
    reference = (donnees.get('reference_avis')
                 or donnees.get('ref_consultation') or '')
    return empreinte_avis(
        reference, donnees.get('acheteur') or '',
        donnees.get('date_limite_remise'))


def trouver_avis_existant(company, source, donnees):
    """Le SAS a-t-il déjà cet avis ? Renvoie ``(avis, niveau)``.

    ``niveau`` vaut 1 (identité de portail), 2 (empreinte) ou 0 (inconnu).
    """
    ref = (donnees.get('ref_consultation') or '').strip()
    if ref:
        existant = AvisMarche.objects.filter(
            company=company, source=source, ref_consultation=ref,
            org_acronyme=(donnees.get('org_acronyme') or '')).first()
        if existant is not None:
            return existant, 1

    empreinte = calculer_empreinte(donnees)
    if empreinte:
        # Le filet de niveau 2 traverse les SOURCES à dessein : c'est ainsi
        # qu'un avis saisi à la main fusionne avec le même avis collecté
        # ensuite, au lieu de doubler.
        existant = AvisMarche.objects.filter(
            company=company, empreinte=empreinte).first()
        if existant is not None:
            return existant, 2

    return None, 0


def _journaliser_rectification(avis, changements, niveau):
    """Trace la rectification DANS l'avis — une fusion silencieuse est un
    bug qu'on ne peut plus expliquer trois mois plus tard.
    """
    brutes = dict(avis.donnees_brutes or {})
    historique = list(brutes.get('rectifications') or [])
    historique.append({
        'date': timezone.now().isoformat(),
        'niveau_dedoublonnage': niveau,
        'changements': changements,
    })
    brutes['rectifications'] = historique
    avis.donnees_brutes = brutes
    logger.info(
        'veille_ao: avis %s rectifié (niveau %s) — champs modifiés : %s',
        avis.pk, niveau, ', '.join(sorted(changements)) or 'aucun')


@transaction.atomic
def enregistrer_avis(company, source, donnees):
    """Enregistre UN avis dans le sas, sans jamais créer de doublon.

    Renvoie ``(avis, cree, niveau)`` :
      * ``cree=True`` → un avis neuf a été inséré (``niveau=0``) ;
      * ``cree=False`` → un avis déjà connu a été MIS À JOUR, et ``niveau``
        dit lequel des deux filets l'a reconnu (1 = identité de portail,
        2 = empreinte).

    Une collision de niveau 2 sans collision de niveau 1 — l'avis rectifié
    qui ressort avec un NOUVEL identifiant — met à jour l'existant et
    journalise la rectification, elle ne duplique pas.
    """
    champs = {k: v for k, v in donnees.items()
              if k in CHAMPS_RECTIFIABLES}
    existant, niveau = trouver_avis_existant(company, source, donnees)

    if existant is None:
        avis = AvisMarche(company=company, source=source, **champs)
        avis.empreinte = calculer_empreinte(donnees)
        avis.save()
        return avis, True, 0

    changements = []
    for nom, valeur in champs.items():
        if getattr(existant, nom) != valeur:
            setattr(existant, nom, valeur)
            changements.append(nom)

    nouvelle_empreinte = calculer_empreinte(donnees)
    if nouvelle_empreinte and existant.empreinte != nouvelle_empreinte:
        existant.empreinte = nouvelle_empreinte
        changements.append('empreinte')

    if changements:
        _journaliser_rectification(existant, changements, niveau)
        existant.save()
    return existant, False, niveau


# ─────────────────────────────────────────────────────────────────────────
# VAO21 — le service de collecte : la SEULE fonction du module qui touche la
# base pour le compte d'une source. Le lecteur (réseau ou non) est branché,
# jamais codé ici.
# ─────────────────────────────────────────────────────────────────────────

#: Verdicts d'une collecte. Les trois cas sont DISTINCTS et ne se confondent
#: jamais (VAO20/VAO24) : « réussie, 0 nouveauté » est normal, « réussie mais
#: structure inattendue » est une anomalie à signaler, « échouée » est une
#: erreur. Un collecteur qui casse sans le dire est PIRE que pas de
#: collecteur : c'est ainsi qu'on rate un AO en se croyant couvert.
VERDICT_SUCCES = VerdictExecution.SUCCES.value
VERDICT_ANOMALIE = VerdictExecution.ANOMALIE.value
VERDICT_ECHEC = VerdictExecution.ECHEC.value


def rapport_vide(source=None):
    """Le gabarit d'un compte-rendu de collecte (jamais un dict improvisé)."""
    return {
        'source_id': getattr(source, 'pk', None),
        'source': getattr(source, 'libelle', ''),
        'mots_cles': [],
        'examines': 0,
        'nouveaux': 0,
        'mis_a_jour': 0,
        'auto_ignores': 0,
        'erreurs': [],
        'verdict': VERDICT_SUCCES,
        'message': '',
    }


def _enregistrer_un_avis(company, source, donnees, mots_cles, regles,
                         user=None):
    """Traite UN avis de bout en bout, dans SA propre transaction.

    Une transaction PAR AVIS, jamais une pour toute la collecte : un avis
    fautif (date illisible, champ manquant) ne doit pas faire perdre les 33
    autres. C'est la raison d'être de ce découpage.

    Renvoie ``(cree, mis_a_jour, auto_ignore)``.
    """
    from .scoring import scorer_avis

    with transaction.atomic():
        avis, cree, _niveau = enregistrer_avis(company, source, donnees)
        scorer_avis(avis, mots_cles)
        avis.save(update_fields=['score', 'mots_cles_declenches',
                                 'updated_at'])
        # VAO10 — les règles d'exclusion s'appliquent APRÈS le scoring et
        # passent par ``changer_statut_avis`` : un avis auto-ignoré garde la
        # trace de la règle qui l'a filtré (jamais un filtrage muet). Un avis
        # déjà trié par un humain n'est PAS re-basculé — la table de
        # transitions refuse ``ignore``→``ignore`` et ``retenu``→``ignore``.
        auto_ignore = False
        if avis.statut == StatutAvis.NOUVEAU:
            auto_ignore = appliquer_regles_exclusion(
                avis, regles, user=user) is not None
    return cree, (not cree), auto_ignore


def collecter(source, company, *, user=None, lecteur=None,
              declencheur=DeclencheurCollecte.PLANIFIE):
    """Collecte UNE source, JOURNALISE l'exécution et rend le compte-rendu.

    Enchaîne : mots-clés actifs → lecteur → dédoublonnage (VAO11) → scoring
    (VAO9) → règles d'exclusion (VAO10) → écriture. **Ne lève pas** sur une
    panne de lecteur : elle la RANGE dans le compte-rendu avec le verdict
    ``echec``.

    VAO24 — une ligne ``ExecutionCollecte`` est écrite à CHAQUE passage, y
    compris (et surtout) sur échec : c'est ici, au point de passage unique,
    que le journal est garanti — pas dans les appelants, où un chemin
    oublierait de le faire un jour.

    Le ``lecteur`` est injectable (tests, et futur branchement du collecteur
    portail) ; par défaut il est résolu par le registre ``lecteurs.py``. Ce
    service ne connaît AUCUNE URL et n'importe AUCUN client HTTP : c'est ce
    qui le rend testable hors ligne et ce qui laisse la règle #5 entièrement
    du côté du lecteur.
    """
    debut = timezone.now()
    rapport = _collecter_sans_journal(source, company, user=user,
                                      lecteur=lecteur)
    rapport['execution_id'] = journaliser_execution(
        company, source, rapport, debut=debut,
        declencheur=declencheur).pk
    return rapport


def journaliser_execution(company, source, rapport, *, debut=None,
                          declencheur=DeclencheurCollecte.PLANIFIE):
    """Écrit la ligne de journal d'UNE exécution (VAO24).

    Le message est TRONQUÉ, jamais rejeté : un journal qui refuse de s'écrire
    parce qu'un message est trop long est un journal qui n'existe pas le jour
    où il compte.
    """
    return ExecutionCollecte.objects.create(
        company=company, source=source,
        debut=debut or timezone.now(), fin=timezone.now(),
        mots_cles_interroges=list(rapport.get('mots_cles') or []),
        examines=rapport.get('examines', 0),
        nouveaux=rapport.get('nouveaux', 0),
        mis_a_jour=rapport.get('mis_a_jour', 0),
        auto_ignores=rapport.get('auto_ignores', 0),
        erreurs=[str(e) for e in (rapport.get('erreurs') or [])][:50],
        verdict=rapport.get('verdict', VERDICT_SUCCES),
        message=(rapport.get('message') or '')[:500],
        declencheur=declencheur)


def _collecter_sans_journal(source, company, *, user=None, lecteur=None):
    """Le corps de la collecte. Séparé pour que le JOURNAL soit inévitable :
    aucun chemin de sortie de ``collecter`` ne peut sauter l'écriture.
    """
    from .lecteurs import LecteurIndisponible, lecteur_pour
    from .scoring import mots_cles_actifs

    rapport = rapport_vide(source)

    if not source.est_collectable_automatiquement:
        rapport['verdict'] = VERDICT_ECHEC
        rapport['message'] = (
            f'Source « {source.libelle} » inactive ou sans URL : rien n\'a '
            'été interrogé.')
        rapport['erreurs'].append(rapport['message'])
        return rapport

    mots = mots_cles_actifs(company)
    rapport['mots_cles'] = [m.libelle for m in mots]
    if not mots:
        # Interroger un portail SANS mot-clé restrictif est interdit par le
        # fichier de risque (requête restreinte, < 10 requêtes/jour) : on
        # s'arrête ici plutôt que de laisser le lecteur décider.
        rapport['verdict'] = VERDICT_ECHEC
        rapport['message'] = (
            'Aucun mot-clé actif : une collecte sans mot-clé restrictif est '
            'refusée (balayage complet interdit).')
        rapport['erreurs'].append(rapport['message'])
        return rapport

    if lecteur is None:
        try:
            lecteur = lecteur_pour(source)
        except LecteurIndisponible as erreur:
            rapport['verdict'] = VERDICT_ECHEC
            rapport['message'] = str(erreur)
            rapport['erreurs'].append(str(erreur))
            return rapport

    try:
        lignes = list(lecteur(source, mots))
    except Exception as erreur:  # noqa: BLE001 — toute panne = ÉCHEC FRANC
        logger.exception('veille_ao: lecture de la source %s échouée',
                         source.pk)
        rapport['verdict'] = VERDICT_ECHEC
        rapport['message'] = f'Lecture de la source impossible : {erreur}'
        rapport['erreurs'].append(rapport['message'])
        return rapport

    regles = regles_actives(company)
    for donnees in lignes:
        rapport['examines'] += 1
        try:
            cree, maj, auto_ignore = _enregistrer_un_avis(
                company, source, dict(donnees or {}), mots, regles, user=user)
        except Exception as erreur:  # noqa: BLE001 — un avis fautif ne perd
            # pas la collecte : il est journalisé et les autres passent.
            logger.warning('veille_ao: avis ignoré (source %s) — %s',
                           source.pk, erreur)
            rapport['erreurs'].append(str(erreur))
            continue
        if cree:
            rapport['nouveaux'] += 1
        elif maj:
            rapport['mis_a_jour'] += 1
        if auto_ignore:
            rapport['auto_ignores'] += 1

    if rapport['erreurs']:
        # Des lignes sont passées, d'autres non : ce n'est ni un succès plein
        # ni un échec — c'est une ANOMALIE, et elle doit se voir.
        rapport['verdict'] = VERDICT_ANOMALIE
        rapport['message'] = (
            f'{len(rapport["erreurs"])} ligne(s) rejetée(s) sur '
            f'{rapport["examines"]} examinée(s).')
    else:
        rapport['message'] = (
            f'{rapport["nouveaux"]} nouveau(x), '
            f'{rapport["mis_a_jour"]} mis à jour sur '
            f'{rapport["examines"]} examiné(s).')

    if rapport['verdict'] != VERDICT_ECHEC:
        source.derniere_collecte_reussie = timezone.now()
        source.save(update_fields=['derniere_collecte_reussie', 'updated_at'])

    return rapport


def collecter_toutes_les_sources(company, *, user=None, lecteur=None,
                                 declencheur=DeclencheurCollecte.PLANIFIE):
    """Collecte toutes les sources COLLECTABLES d'une société.

    ``SourceVeilleQuerySet.collectables()`` est le seul filtre : une source
    désactivée n'est jamais interrogée, et personne n'a à s'en souvenir.
    Rend la liste des comptes-rendus, un par source — jamais un total agrégé
    qui masquerait une source en panne au milieu de trois sources vertes.

    L'alarme de silence (VAO24) est évaluée UNE fois, à la fin du passage :
    c'est le moment où l'on sait si la veille a ramené quelque chose.
    """
    sources = SourceVeille.objects.filter(company=company).collectables()
    rapports = [collecter(source, company, user=user, lecteur=lecteur,
                          declencheur=declencheur)
                for source in sources]
    signaler_alarme_si_besoin(company)
    notifier_nouveaux_avis(company, rapports)
    return rapports


# ─────────────────────────────────────────────────────────────────────────
# VAO24 — L'ALARME DE COLLECTE SILENCIEUSE.
#
# La tâche la plus importante du groupe, et la raison est un scénario RÉEL,
# pas une hypothèse : le portail change, la collecte renvoie vide, l'écran
# reste calme — et on se croit couvert pendant des semaines. Un dispositif de
# veille qui casse sans le dire est PIRE que pas de dispositif du tout,
# puisqu'il fabrique une fausse tranquillité.
# ─────────────────────────────────────────────────────────────────────────

#: Nombre d'échecs consécutifs qui déclenchent l'alarme.
ECHECS_CONSECUTIFS_ALARME = 2
#: Nombre de JOURS consécutifs sans le moindre résultat qui la déclenchent.
JOURS_MUETS_ALARME = 2


def _jours_muets(company, jours=JOURS_MUETS_ALARME):
    """Les N derniers jours où la veille a tourné ont-ils TOUS été muets ?

    « Muet » = une exécution réussie qui n'a RIEN examiné, sur tous les
    mots-clés. On raisonne en JOURS CALENDAIRES de collecte (pas en « N
    dernières exécutions ») parce que la collecte est quotidienne : deux
    exécutions vides le même matin ne font pas deux jours de silence.
    """
    recentes = ExecutionCollecte.objects.filter(
        company=company).reussies().recentes()[:50]
    par_jour = {}
    for execution in recentes:
        jour = timezone.localtime(execution.debut).date()
        par_jour.setdefault(jour, []).append(execution)
        if len(par_jour) > jours:
            break
    journees = sorted(par_jour, reverse=True)[:jours]
    if len(journees) < jours:
        return False
    return all(all(e.examines == 0 for e in par_jour[j]) for j in journees)


def _echecs_consecutifs(company, combien=ECHECS_CONSECUTIFS_ALARME):
    """Les ``combien`` dernières exécutions sont-elles TOUTES en échec ?"""
    dernieres = list(ExecutionCollecte.objects.filter(
        company=company).recentes()[:combien])
    if len(dernieres) < combien:
        return False
    return all(e.verdict == VERDICT_ECHEC for e in dernieres)


def evaluer_alarme(company):
    """``(active, message)`` — l'alarme de silence de CETTE société.

    Le message est en français et ACTIONNABLE : il dit ce qui s'est passé et
    ce qu'il faut aller vérifier. Un « alerte » nu ne fait rien bouger.
    """
    if _echecs_consecutifs(company):
        return True, (
            f'La collecte a échoué {ECHECS_CONSECUTIFS_ALARME} fois de suite. '
            'La veille ne ramène plus rien — vérifiez la source et le journal '
            "d'exécution.")
    if _jours_muets(company):
        return True, (
            f'Aucun avis remonté depuis {JOURS_MUETS_ALARME} jours, sur tous '
            'les mots-clés. La veille ne ramène plus rien — vérifiez les '
            'mots-clés et la source.')
    return False, ''


def signaler_alarme_si_besoin(company):
    """Notifie le directeur si l'alarme vient de s'allumer. Idempotent.

    Une alarme qui crie tous les matins est une alarme qu'on apprend à
    ignorer : le drapeau ``alarme_notifiee`` porté par la DERNIÈRE exécution
    garantit une seule notification par épisode de silence.
    """
    active, message = evaluer_alarme(company)
    derniere = ExecutionCollecte.objects.filter(
        company=company).recentes().first()
    if derniere is None:
        return None
    if not active:
        return None
    if derniere.alarme_notifiee:
        return None

    _notifier(company, 'veille_ao_alarme_silence',
              'Veille appels d\'offres : plus rien ne remonte', message,
              lien='/veille-ao/avis')
    ExecutionCollecte.objects.filter(pk=derniere.pk).update(
        alarme_notifiee=True)
    return message


def sante(company):
    """VAO24/VAO35/VAO37 — l'état de la veille en UN appel agrégé.

    Un seul calcul côté serveur, consommé identiquement par le bandeau de
    santé et par l'écran de paramètres : deux calculs séparés finiraient par
    diverger, et c'est précisément un désaccord entre écrans qui ferait
    douter de l'ensemble.
    """
    from django.conf import settings

    maintenant = timezone.now()
    derniere_reussie = ExecutionCollecte.objects.filter(
        company=company).reussies().recentes().first()
    horodatage = derniere_reussie.fin or derniere_reussie.debut \
        if derniere_reussie else None
    if horodatage is None:
        # Repli : une source peut porter une réussite antérieure au journal.
        horodatage = SourceVeille.objects.filter(
            company=company, derniere_collecte_reussie__isnull=False
        ).order_by('-derniere_collecte_reussie').values_list(
            'derniere_collecte_reussie', flat=True).first()

    # « Hier » se lit au jour CALENDAIRE LOCAL, pas en « il y a 24 h »
    # glissantes. La requête est bornée à une fenêtre de 3 jours (jamais un
    # balayage du journal entier) puis affinée en Python, parce que la
    # frontière de journée dépend du fuseau et non de la colonne stockée.
    hier = (timezone.localtime(maintenant) - timedelta(days=1)).date()
    fenetre = ExecutionCollecte.objects.filter(
        company=company,
        debut__gte=maintenant - timedelta(days=3),
        debut__lte=maintenant + timedelta(days=1))
    examines_hier = sum(
        e.examines for e in fenetre
        if timezone.localtime(e.debut).date() == hier)

    active, message = evaluer_alarme(company)
    derniere = ExecutionCollecte.objects.filter(
        company=company).recentes().first()

    return {
        'derniere_collecte_reussie': horodatage,
        'age_heures': (
            round((maintenant - horodatage).total_seconds() / 3600, 1)
            if horodatage else None),
        'avis_examines_hier': examines_hier,
        'alarme_active': active,
        'alarme_message': message,
        'collecte_active': bool(
            getattr(settings, 'VEILLE_AO_COLLECTE_ACTIVE', False)),
        'dernier_verdict': derniere.verdict if derniere else '',
        'dernier_message': derniere.message if derniere else '',
        'sources_collectables': SourceVeille.objects.filter(
            company=company).collectables().count(),
        'avis_nouveaux': AvisMarche.objects.filter(
            company=company, statut=StatutAvis.NOUVEAU).count(),
    }


# ─────────────────────────────────────────────────────────────────────────
# VAO25 — la notification quotidienne : utile, en français, NON bruyante.
# ─────────────────────────────────────────────────────────────────────────

#: Fenêtre d'urgence mise en avant dans la notification (jours).
FENETRE_URGENCE_JOURS = 15


def _notifier(company, event_type, titre, corps, lien=''):
    """Envoi via ``apps.notifications`` — JAMAIS un envoi réseau d'ici.

    Destinataires : les porteurs de ``veille_ao_voir`` de cette société. Le
    service de collecte n'ouvre aucune connexion lui-même : il demande, la
    plateforme livre (et respecte les préférences, les heures calmes et les
    canaux de chacun).
    """
    from apps.notifications.services import notify_many

    destinataires = destinataires_veille(company)
    if not destinataires:
        return []
    return notify_many(destinataires, event_type, titre, body=corps,
                       link=lien, company=company)


def destinataires_veille(company):
    """Les utilisateurs actifs de la société qui PEUVENT lire la veille.

    Paramétrable au sens fort : la permission EST le paramètre. Donner ou
    retirer ``veille_ao_voir`` à un rôle change les destinataires, sans liste
    codée en dur ni réglage parallèle à maintenir.

    Le test d'appartenance passe par ``core.permissions._user_has_or_legacy``
    — la MÊME fonction que ``ScopedPermission`` applique aux routes. Les
    destinataires sont donc, par construction, exactement ceux qui peuvent
    ouvrir l'écran : on ne notifie jamais quelqu'un à propos d'une page qu'il
    recevrait en 403, et on n'oublie jamais un compte hérité sans rôle fin.
    """
    from django.contrib.auth import get_user_model

    from core.permissions import _user_has_or_legacy

    utilisateurs = get_user_model().objects.filter(
        company=company, is_active=True).select_related('role')
    return [u for u in utilisateurs
            if _user_has_or_legacy(u, 'veille_ao_voir')]


def notifier_nouveaux_avis(company, rapports):
    """« 3 nouveaux avis solaires — dont 1 à échéance J-12 ».

    **Rien à dire = rien à envoyer.** Une notification quotidienne vide
    apprend à ignorer les notifications — et le jour où elle compte, personne
    ne la lit. Renvoie le nombre de notifications émises (0 si silence).
    """
    nouveaux = sum(r.get('nouveaux', 0) for r in (rapports or []))
    if nouveaux <= 0:
        return 0

    limite = timezone.now() + timedelta(days=FENETRE_URGENCE_JOURS)
    urgents = AvisMarche.objects.filter(
        company=company, statut=StatutAvis.NOUVEAU,
        date_limite_remise__isnull=False,
        date_limite_remise__lte=limite,
        date_limite_remise__gte=timezone.now()).order_by(
            'date_limite_remise')

    libelle = ('1 nouvel avis' if nouveaux == 1
               else f'{nouveaux} nouveaux avis')
    titre = f'Veille appels d\'offres : {libelle}'
    premier = urgents.first()
    if premier is not None:
        jours = max((premier.date_limite_remise - timezone.now()).days, 0)
        corps = f'{libelle} — dont 1 à échéance J-{jours}.'
    else:
        corps = f'{libelle} à trier dans le sas.'

    envoyees = _notifier(company, 'veille_ao_nouveaux_avis', titre, corps,
                         lien='/veille-ao/avis?statut=nouveau')
    return len(envoyees)


# ─────────────────────────────────────────────────────────────────────────
# VAO27 — LA PORTE MANUELLE : capter en 30 secondes un AO reçu par WhatsApp,
# SMS ou appel — avec sa SOURCE.
#
# C'est la leçon FRDISI, et elle est chère : l'appel d'offres qui a réellement
# occupé le fondateur n'est passé par AUCUN portail. Il est arrivé par un
# partenaire, sur une liste d'invitation, et aucun dispositif de veille —
# gratuit ou payant — ne l'aurait fait remonter. La porte automatique ne peut
# donc jamais être la seule.
# ─────────────────────────────────────────────────────────────────────────

#: Libellés des sources créées à la volée par la saisie manuelle.
LIBELLES_PORTE_HUMAINE = {
    TypeSource.TUYAU_PARTENAIRE: 'Tuyau partenaire',
    TypeSource.SAISIE_MANUELLE: 'Saisie manuelle',
    TypeSource.IMPORT_CSV: 'Import de fichier',
}


def resoudre_source(company, valeur, defaut=TypeSource.TUYAU_PARTENAIRE):
    """Rend la ``SourceVeille`` désignée par ``valeur`` — PK ou TYPE.

    Une saisie faite depuis un chantier ne connaît pas la clé primaire d'une
    source : elle sait seulement « c'est un partenaire qui me l'a dit ». Cette
    fonction accepte donc l'identifiant TECHNIQUE (un entier, pour l'écran
    complet) **ou** le code de TYPE (``tuyau_partenaire``…), et crée la source
    de ce type à la volée si elle n'existe pas encore — idempotent, une seule
    ligne par société et par type.

    Une source d'une AUTRE société est introuvable : rien ne fuit entre
    locataires, même par un identifiant deviné.
    """
    if isinstance(valeur, SourceVeille):
        if valeur.company_id != getattr(company, 'pk', None):
            raise ValidationError(
                {'source': 'Cette source appartient à une autre société.'})
        return valeur

    brut = '' if valeur is None else str(valeur).strip()

    if brut.isdigit():
        source = SourceVeille.objects.filter(
            company=company, pk=int(brut)).first()
        if source is None:
            raise ValidationError({'source': ['Source introuvable.']})
        return source

    type_source = brut or defaut
    if type_source not in {c for c, _ in TypeSource.choices}:
        connus = ', '.join(c for c, _ in TypeSource.choices)
        raise ValidationError({'source': [
            f'Type de source inconnu : « {type_source} ». '
            f'Valeurs acceptées : {connus}.']})

    source, _cree = SourceVeille.objects.get_or_create(
        company=company, code=str(type_source),
        defaults={
            'libelle': LIBELLES_PORTE_HUMAINE.get(
                type_source, TypeSource(type_source).label),
            'type_source': type_source,
            # Une porte HUMAINE est active d'emblée : elle n'interroge rien,
            # elle reçoit. Une source réseau, elle, naît DÉSARMÉE (règle #5).
            'actif': type_source not in TYPES_COLLECTABLES,
        })
    return source


def creer_avis_manuel(company, donnees, user=None):
    """Crée un avis SIGNALÉ par un humain, en quatre champs.

    Le minimum vital, et rien de plus : objet, acheteur, date limite,
    informateur. ``informateur`` est le SEUL champ bloquant (400 en français
    sinon) — savoir QUI l'a signalé est la matière même de la mesure
    d'attribution (VAO31), et c'est la seule information qu'on ne pourra plus
    jamais retrouver après coup.

    **Aucune autre validation ne bloque.** Une saisie faite debout sur un
    chantier, entre deux appels, doit passer : un formulaire qui refuse parce
    qu'une date est incomplète est un formulaire qu'on n'utilise pas, et l'AO
    est perdu.

    L'avis manuel entre dans le MÊME sas et suit le MÊME cycle que les avis
    collectés — dédoublonnage de niveau 2 compris (VAO11) : le même avis saisi
    à la main puis collecté automatiquement FUSIONNE au lieu de doubler.
    """
    donnees = dict(donnees or {})

    informateur = (donnees.pop('informateur', '') or '').strip()
    if not informateur:
        raise ValidationError({'informateur': [
            "Qui vous a signalé cet avis ? L'informateur est obligatoire : "
            "c'est la seule information qu'on ne pourra plus retrouver plus "
            'tard, et celle qui mesure ce que la veille automatique ne voit '
            'pas.']})
    if informateur not in {c for c, _ in Informateur.choices}:
        connus = ', '.join(c for c, _ in Informateur.choices)
        raise ValidationError({'informateur': [
            f'Informateur inconnu : « {informateur} ». '
            f'Valeurs acceptées : {connus}.']})

    source = resoudre_source(company, donnees.pop('source', None))

    if not (donnees.get('objet') or donnees.get('acheteur')):
        raise ValidationError({'objet': [
            "Indiquez au moins l'objet ou l'acheteur — sans l'un des deux, "
            "l'avis serait introuvable dans le sas."]})

    champs = {k: v for k, v in donnees.items() if k in CHAMPS_RECTIFIABLES}
    champs['informateur'] = informateur

    avis, cree, _niveau = enregistrer_avis(company, source, champs)
    if cree:
        from .scoring import scorer_avis

        scorer_avis(avis)
        avis.save(update_fields=['score', 'mots_cles_declenches',
                                 'updated_at'])
    elif informateur and not avis.informateur:
        # Un avis d'abord COLLECTÉ puis signalé à la main garde la trace du
        # tuyau : c'est précisément ce que la mesure d'attribution cherche.
        avis.informateur = informateur
        avis.save(update_fields=['informateur', 'updated_at'])
    return avis, cree


# ─────────────────────────────────────────────────────────────────────────
# VAO30 — « RETENIR » : l'UNIQUE point de contact cross-app de tout le groupe.
#
# La conversion passe par ``apps.ao.services.creer_appel_offre_depuis_avis``
# — le point de contact que l'app cible EXPOSE dans son ``services.py``
# (AOF169), déjà emprunté par l'import de fichier et la saisie manuelle d'AO.
# Aucun modèle ni aucune vue d'``apps.ao`` n'est importé ici : le lien
# retourne un ENTIER opaque (``appel_offre_id``), ce qui garde le contrat
# import-linter vert et la chaîne de migrations d'``apps.ao`` mono-écrivain.
#
# La référence de NOTRE dossier (AO-YYYYMM-0001) est générée par la
# plateforme (``core.numbering``) à l'intérieur de ce service — jamais un
# ``count()+1``, le dépôt a déjà payé une collision en production.
# ─────────────────────────────────────────────────────────────────────────

#: Les champs d'un avis que l'affaire reprend. Les NOMS sont ceux du contrat
#: d'``apps.ao`` (``date_limite``, ``date_ouverture_plis``), pas les nôtres :
#: c'est la fonction d'accueil qui fixe le vocabulaire, pas l'appelant.
def _avis_vers_affaire(avis):
    """Traduit un avis du sas vers le dictionnaire attendu par ``apps.ao``."""
    reference = (avis.reference_avis or avis.ref_consultation or '').strip()
    if not reference:
        # Un avis capté par WhatsApp n'a souvent AUCUNE référence publiée
        # (c'est le cas FRDISI : une consultation privée sur invitation).
        # Refuser la conversion ici viderait le groupe de son sens ; on pose
        # donc une référence interne STABLE et traçable, qui déduplique tout
        # aussi bien qu'une référence d'acheteur.
        reference = f'VEILLE-{avis.pk}'

    donnees = {
        'reference_acheteur': reference,
        'objet': avis.objet or '',
        'acheteur': avis.acheteur or '',
        'lot': avis.lot or '',
        'date_limite': avis.date_limite_remise,
        'date_ouverture_plis': avis.date_ouverture,
    }
    if avis.montant_estime is not None:
        donnees['montant_estime'] = avis.montant_estime
    if avis.caution_provisoire is not None:
        donnees['caution_provisoire'] = avis.caution_provisoire
    return {k: v for k, v in donnees.items() if v not in (None, '')}


def retenir_avis(avis, user=None, motif=''):
    """Retient un avis et crée l'affaire correspondante. IDEMPOTENT.

    Re-cliquer ne crée pas de doublon : si l'avis porte déjà un
    ``appel_offre_id``, on rend ce lien tel quel sans rien créer ni muter.

    Un avis IGNORÉ peut être retenu (marche arrière triviale, VAO10) ; un avis
    EXPIRÉ ne bouge plus, et le service de transition le dit en français.

    Rend ``(avis, appel_offre_id, cree)``.
    """
    if avis.appel_offre_id:
        return avis, avis.appel_offre_id, False

    # La transition se VALIDE AVANT la moindre écriture cross-app. Sans cette
    # garde, un avis EXPIRÉ traversait la fonction, faisait créer l'affaire,
    # et n'échouait qu'au passage en CONVERTI : le refus laissait derrière lui
    # un appel d'offres ORPHELIN, créé pour une conversion qui n'a pas eu
    # lieu. On refuse d'abord, on écrit ensuite.
    if avis.statut not in (StatutAvis.NOUVEAU, StatutAvis.IGNORE,
                           StatutAvis.RETENU):
        libelles = dict(StatutAvis.choices)
        raise ValidationError({'statut': [
            f'Transition interdite : un avis « {libelles.get(avis.statut, avis.statut)} » '
            'ne se retient plus.']})

    # Tout ou rien : si la conversion échoue en cours de route, aucune affaire
    # ne survit à l'échec.
    with transaction.atomic():
        if avis.statut in (StatutAvis.NOUVEAU, StatutAvis.IGNORE):
            changer_statut_avis(
                avis, StatutAvis.RETENU, user=user,
                motif=motif or 'Retenu pour chiffrage.')

        # L'UNIQUE appel cross-app du groupe — par le ``services.py`` de l'app
        # cible, jamais par ses modèles.
        from apps.ao.services import creer_appel_offre_depuis_avis

        appel_offre, cree = creer_appel_offre_depuis_avis(
            avis.company, _avis_vers_affaire(avis), user=user)

        changer_statut_avis(
            avis, StatutAvis.CONVERTI, user=user,
            motif=(f"Converti en appel d'offres {appel_offre.reference}."),
            champs_supplementaires={'appel_offre_id': appel_offre.pk})
    return avis, appel_offre.pk, cree


def ignorer_avis(avis, user=None, motif=''):
    """Ignore un avis et PROPOSE la règle d'exclusion — sans jamais la créer.

    « Ignorer » doit APPRENDRE (VAO10), mais l'apprentissage ne se fait pas en
    douce : le service rend un brouillon de règle, l'écran le propose, et
    l'utilisateur décide. Rend ``(avis, proposition)``.
    """
    changer_statut_avis(avis, StatutAvis.IGNORE, user=user,
                        motif=motif or 'Ignoré manuellement.')
    return avis, proposer_regle_pour_avis(avis)
