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

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .hashing import empreinte_avis
from .models import AvisMarche, PorteeExclusion, RegleExclusion, StatutAvis
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
TRANSITIONS_AVIS = {
    StatutAvis.NOUVEAU: (StatutAvis.RETENU, StatutAvis.IGNORE,
                         StatutAvis.EXPIRE),
    StatutAvis.RETENU: (StatutAvis.CONVERTI, StatutAvis.EXPIRE),
    StatutAvis.IGNORE: (StatutAvis.EXPIRE,),
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
            {'statut': f'Statut inconnu : « {nouveau} ».'})

    ancien = avis.statut
    autorises = transitions_possibles(ancien)
    if nouveau not in autorises:
        atteignables = ', '.join(
            f'« {libelles[s]} »' for s in autorises) or 'aucun'
        raise ValidationError({'statut': (
            f'Transition interdite : « {libelles.get(ancien, ancien)} » → '
            f'« {libelles[nouveau]} ». Statuts atteignables : '
            f'{atteignables}.')})

    champs = dict(champs_supplementaires or {})
    if 'statut' in champs:
        raise ValidationError({'statut': (
            'Le statut ne se pose pas par un champ supplémentaire : il passe '
            'par ce service et par lui seul.')})

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
VERDICT_SUCCES = 'succes'
VERDICT_ANOMALIE = 'anomalie'
VERDICT_ECHEC = 'echec'


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


def collecter(source, company, *, user=None, lecteur=None):
    """Collecte UNE source et rend un compte-rendu structuré.

    Enchaîne : mots-clés actifs → lecteur → dédoublonnage (VAO11) → scoring
    (VAO9) → règles d'exclusion (VAO10) → écriture. **Ne lève pas** sur une
    panne de lecteur : elle la RANGE dans le compte-rendu avec le verdict
    ``echec``, pour que le journal d'exécution (VAO24) puisse la raconter.

    Le ``lecteur`` est injectable (tests, et futur branchement du collecteur
    portail) ; par défaut il est résolu par le registre ``lecteurs.py``. Ce
    service ne connaît AUCUNE URL et n'importe AUCUN client HTTP : c'est ce
    qui le rend testable hors ligne et ce qui laisse la règle #5 entièrement
    du côté du lecteur.
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


def collecter_toutes_les_sources(company, *, user=None, lecteur=None):
    """Collecte toutes les sources COLLECTABLES d'une société.

    ``SourceVeilleQuerySet.collectables()`` est le seul filtre : une source
    désactivée n'est jamais interrogée, et personne n'a à s'en souvenir.
    Rend la liste des comptes-rendus, un par source — jamais un total agrégé
    qui masquerait une source en panne au milieu de trois sources vertes.
    """
    from .models import SourceVeille

    sources = SourceVeille.objects.filter(company=company).collectables()
    return [collecter(source, company, user=user, lecteur=lecteur)
            for source in sources]
