"""Services (écritures/orchestration) du module ``apps.innovation``.

Le chatter (« historique ») réutilise ``apps.records.services.log_activity``
(ARC8, générique) — jamais un modèle ``*Activity`` maison. Le marquage
(NTIDE13) réutilise ``apps.records.models.Tag``/``TaggedItem`` (FG9,
générique). Ces deux mécanismes sont des primitives PLATEFORME existantes :
aucune nouvelle table n'est créée pour les porter.
"""
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import Idee, VoteIdee

# ── Machine à états (NTIDE5) ────────────────────────────────────────────────

# {statut_cible: {statuts_de_depart_autorises}}
_TRANSITIONS = {
    Idee.Statut.EXAMINEE: {Idee.Statut.OUVERT},
    Idee.Statut.RETENUE: {Idee.Statut.EXAMINEE},
    Idee.Statut.REALISEE: {Idee.Statut.RETENUE},
    # Fermeture optionnelle depuis n'importe quel statut ACTIF (pas déjà
    # réalisée/fermée — ces deux-là sont terminales).
    Idee.Statut.FERMEE: set(Idee.STATUTS_ACTIFS),
}


class TransitionInvalide(ValueError):
    """Levée quand la transition demandée n'est pas légale depuis le statut
    courant de l'idée."""


class ReouvertureInterdite(ValueError):
    """Levée quand l'auteur tente de ré-ouvrir une idée qui n'est pas dans un
    statut ré-ouvrable, ou quand un tiers (pas l'auteur) tente l'action
    (NTIDE17)."""


# NTIDE17 — l'auteur peut ré-ouvrir sa propre idée FERMÉE ou EXAMINÉE (retour
# à OUVERT, avant tout examen approfondi) ; verrouillé dès que l'idée a été
# RETENUE (ou RÉALISÉE) — l'auteur ne défait jamais une décision déjà prise
# par le palier Directeur/Responsable.
REOUVRIR_DEPUIS = frozenset({Idee.Statut.FERMEE, Idee.Statut.EXAMINEE})


def transitionner(idee, *, target, user, note=''):
    """Applique une transition de statut si elle est légale, journalise le
    changement dans le chatter générique (``records.Activity``, ARC8).

    Lève ``TransitionInvalide`` si le statut courant n'autorise pas
    ``target``. ``note`` (optionnelle) est jointe au journal (utilisée par
    l'action ``fermer``, NTIDE5, qui accepte une note de fermeture)."""
    autorises = _TRANSITIONS.get(target)
    if autorises is None or idee.statut not in autorises:
        raise TransitionInvalide(
            f"Transition invalide depuis « {idee.get_statut_display()} » "
            f"vers « {Idee.Statut(target).label} ».")

    old = idee.statut
    idee.statut = target
    idee.save(update_fields=['statut', 'updated_at'])

    from apps.records.models import Activity
    from apps.records.services import log_activity
    log_activity(
        idee, Activity.Kind.MODIFICATION, user=user, field='statut',
        field_label='Statut', old_value=old, new_value=target,
        body=note or '', company=idee.company)
    return idee


def reouvrir(idee, user):
    """NTIDE17 — l'AUTEUR (et uniquement l'auteur) ré-ouvre sa propre idée
    depuis FERMÉE ou EXAMINÉE vers OUVERT. Verrouillé dès RETENUE/RÉALISÉE.
    Journalise la transition dans le chatter générique (ARC8), comme les
    transitions du palier Directeur/Responsable (``transitionner``)."""
    if idee.auteur_id != user.id:
        raise ReouvertureInterdite(
            "Seul l'auteur peut ré-ouvrir son idée.")
    if idee.statut not in REOUVRIR_DEPUIS:
        raise ReouvertureInterdite(
            f"Ré-ouverture impossible depuis « {idee.get_statut_display()} » "
            '(verrouillée après « Retenue »).')

    old = idee.statut
    idee.statut = Idee.Statut.OUVERT
    idee.save(update_fields=['statut', 'updated_at'])

    from apps.records.models import Activity
    from apps.records.services import log_activity
    log_activity(
        idee, Activity.Kind.MODIFICATION, user=user, field='statut',
        field_label='Statut', old_value=old, new_value=Idee.Statut.OUVERT,
        body="Ré-ouverte par l'auteur.", company=idee.company)
    return idee


# ── Votes (NTIDE2) ──────────────────────────────────────────────────────────


class VoteInterdit(ValueError):
    """Levée quand le vote est refusé (auteur de sa propre idée, doublon)."""


@transaction.atomic
def voter(idee, user):
    """Crée un vote pour ``idee`` au nom de ``user`` et incrémente le compteur
    dénormalisé. L'auteur d'une idée ne peut pas voter pour la sienne
    (« Voter ← auteurs en lecture », NTIDE5). Refuse un doublon (unique
    ``(idee, votant)``, NTIDE2)."""
    from django.db.models import F

    if idee.auteur_id and idee.auteur_id == user.id:
        raise VoteInterdit('Vous ne pouvez pas voter pour votre propre idée.')
    try:
        vote = VoteIdee.objects.create(
            company=idee.company, idee=idee, votant=user)
    except IntegrityError as exc:
        raise VoteInterdit('Vous avez déjà voté pour cette idée.') from exc
    Idee.objects.filter(pk=idee.pk).update(votes_count=F('votes_count') + 1)
    idee.refresh_from_db(fields=['votes_count'])
    _maybe_notify_seuil_votes(idee)
    return vote


# ── Notification de seuil de votes (NTIDE16) ────────────────────────────────


def _maybe_notify_seuil_votes(idee):
    """Notifie l'auteur (in-app + email, préférences utilisateur respectées
    par ``notify()``) quand l'idée ATTEINT — exactement, pas dépasse — le
    seuil configuré (``InnovationSettings.seuil_votes_notification``, défaut
    3) : une seule notification par idée, jamais répétée à chaque vote
    suivant. No-op silencieux si l'idée n'a pas d'auteur (idée importée/
    créée en admin) ou si le seuil est désactivé (0)."""
    if not idee.auteur_id:
        return
    from .models import InnovationSettings

    reglages, _ = InnovationSettings.objects.get_or_create(company=idee.company)
    seuil = reglages.seuil_votes_notification
    if seuil <= 0 or idee.votes_count != seuil:
        return

    from apps.notifications.models import EventType
    from apps.notifications.services import notify

    notify(
        idee.auteur, EventType.IDEA_VOTE,
        f'Votre idée « {idee.titre} » a atteint {seuil} votes',
        body=f'Elle totalise maintenant {idee.votes_count} vote(s).',
        link=f'/innovation/idees/{idee.id}', company=idee.company)


@transaction.atomic
def retirer_vote(vote):
    """Supprime un vote et décrémente le compteur dénormalisé (jamais sous
    zéro)."""
    from django.db.models import F

    idee_id = vote.idee_id
    vote.delete()
    Idee.objects.filter(pk=idee_id, votes_count__gt=0).update(
        votes_count=F('votes_count') - 1)


# ── Marquage en masse (NTIDE13) — réutilise records.Tag/TaggedItem (FG9) ────


def _content_type_idee():
    from django.contrib.contenttypes.models import ContentType
    return ContentType.objects.get_for_model(Idee)


def bulk_add_tag(company, ids, tag_nom):
    """Applique le tag ``tag_nom`` (créé si besoin, scopé société) à chaque
    idée de ``ids``. Réutilise ``records.Tag``/``TaggedItem`` — jamais un
    champ ``tags`` maison sur ``Idee``."""
    from apps.records.models import Tag, TaggedItem

    tag, _ = Tag.objects.get_or_create(company=company, nom=tag_nom)
    ct = _content_type_idee()
    ids = list(Idee.objects.filter(company=company, id__in=ids)
               .values_list('id', flat=True))
    created = 0
    for object_id in ids:
        _, was_created = TaggedItem.objects.get_or_create(
            tag=tag, content_type=ct, object_id=object_id)
        created += int(was_created)
    return {'tag': tag.nom, 'idees': len(ids), 'nouveaux': created}


def bulk_remove_tag(company, ids, tag_nom):
    """Retire le tag ``tag_nom`` de chaque idée de ``ids`` (no-op silencieux
    si le tag ou l'association n'existe pas)."""
    from apps.records.models import Tag, TaggedItem

    tag = Tag.objects.filter(company=company, nom=tag_nom).first()
    if tag is None:
        return {'tag': tag_nom, 'idees': 0, 'retires': 0}
    ct = _content_type_idee()
    ids = list(Idee.objects.filter(company=company, id__in=ids)
               .values_list('id', flat=True))
    retires, _ = TaggedItem.objects.filter(
        tag=tag, content_type=ct, object_id__in=ids).delete()
    return {'tag': tag.nom, 'idees': len(ids), 'retires': retires}


BULK_STATUT_CIBLES = frozenset({
    Idee.Statut.EXAMINEE, Idee.Statut.RETENUE, Idee.Statut.REALISEE,
    Idee.Statut.FERMEE,
})


def bulk_set_statut(company, ids, target, user):
    """Applique la transition ``target`` à chaque idée de ``ids`` qui
    l'autorise depuis son statut courant ; ignore silencieusement celles qui
    ne l'autorisent pas (retournées dans ``ignorees``)."""
    if target not in BULK_STATUT_CIBLES:
        raise ValidationError('Statut cible invalide pour une action en masse.')
    idees = Idee.objects.filter(company=company, id__in=ids)
    appliquees, ignorees = [], []
    for idee in idees:
        try:
            transitionner(idee, target=target, user=user)
        except TransitionInvalide:
            ignorees.append(idee.id)
        else:
            appliquees.append(idee.id)
    return {'appliquees': appliquees, 'ignorees': ignorees}


# ── Tag automatique de campagne (NTIDE28) ───────────────────────────────────


def maybe_apply_campagne_tag(idee, user):
    """NTIDE28 — si ``user`` matche le segment d'une campagne ACTIVE portant
    un ``tag_auto`` (``selectors.campagne_active_pour_utilisateur``, même
    règle que le bandeau d'incitation NTIDE27), applique ce tag à ``idee``
    automatiquement. Réutilise ``bulk_add_tag`` (``records.Tag``/
    ``TaggedItem``) — le tag reste ensuite modifiable manuellement comme
    n'importe quel autre (pas verrouillé). No-op silencieux si aucune
    campagne ne matche, ou si elle n'a pas de ``tag_auto``."""
    from . import selectors

    campagne = selectors.campagne_active_pour_utilisateur(user)
    if campagne is None or not campagne.tag_auto:
        return
    bulk_add_tag(idee.company, [idee.id], campagne.tag_auto)


# ── Notification de lancement de campagne (NTIDE31) ─────────────────────────


def notifier_campagne_lancee(campagne):
    """NTIDE31 — quand une campagne passe brouillon → active (détecté côté
    vue, ``CampagneInnovationViewSet.perform_update``), notifie CHAQUE
    utilisateur du segment ciblé (``selectors.users_for_campaign`` — même
    règle que le bandeau d'incitation NTIDE27/le tag auto NTIDE28) : in-app
    systématique + email OPT-IN — l'arbitrage canal/préférence reste dans
    ``notify()``/``NotificationPreference`` (``notify_many``, best-effort
    par destinataire), jamais dupliqué ici. Tag
    ``EventType.INNOVATION_CAMPAIGN``. No-op silencieux si le segment ne
    cible personne."""
    from apps.notifications.models import EventType
    from apps.notifications.services import notify_many

    from . import selectors

    utilisateurs = selectors.users_for_campaign(campagne.company, campagne)
    titre = f"Nouvelle campagne d'innovation : {campagne.nom}"
    corps = campagne.message_incitation or campagne.description or ''
    notify_many(
        utilisateurs, EventType.INNOVATION_CAMPAIGN, titre, body=corps,
        link='/innovation/proposer', company=campagne.company)


BULK_ACTIONS = frozenset({'set_statut', 'add_tag', 'remove_tag'})


def apply_bulk_action(*, company, user, ids, op, params):
    """Point d'entrée unique des actions en masse (NTIDE13). ``op`` in
    ``BULK_ACTIONS`` (l'export est géré séparément côté vue : il renvoie un
    fichier, pas un JSON)."""
    if op == 'set_statut':
        target = params.get('statut')
        return bulk_set_statut(company, ids, target, user)
    if op == 'add_tag':
        tag_nom = (params.get('tag') or '').strip()
        if not tag_nom:
            raise ValidationError('Tag requis.')
        return bulk_add_tag(company, ids, tag_nom)
    if op == 'remove_tag':
        tag_nom = (params.get('tag') or '').strip()
        if not tag_nom:
            raise ValidationError('Tag requis.')
        return bulk_remove_tag(company, ids, tag_nom)
    raise ValidationError('Action en masse inconnue.')
