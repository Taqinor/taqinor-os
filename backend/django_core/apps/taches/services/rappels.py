"""Rappels posés par l'utilisateur (reference/donnees.md §2.13, invariant 19 ; regles.md « Les
sollicitations », rappels posés).

- Un rappel est à l'heure MURALE (`jour`, `heure`) ; ancré (`jour_prevu` ou `echeance` + un décalage
  de −7 à 0 jour), son `jour` suit l'ancre : recalculé quand elle bouge, `annule` quand elle s'efface.
- Au plus 5 rappels en attente par tâche, 100 par compte (vérifiés sous verrou).
- Tâche close, abandonnée ou supprimée → ses rappels en attente passent `annule`.
- Posé hors de la fenêtre de la société, il sonnera quand même : le drapeau `hors_fenetre` le dit.

L'envoi (rappels dus, groupés par minute, `manque` au-delà de 2 h) est le balayage (TCH98).
"""
import datetime
from dataclasses import dataclass

from django.db import transaction
from django.http import Http404
from django.utils import timezone
from rest_framework import serializers

from apps.notifications.selectors import fenetre_notifications
from apps.taches.choix import AncreRappel, SourceRappel, StatutRappel, StatutTache
from apps.taches.entrees import MESSAGE_DATE, jour_dans_bornes
from apps.taches.models.rythme import ReglagesRythme
from apps.taches.models.taches import Rappel
from apps.taches.moteur.gabarits import format_duree, format_heure, format_jour
from apps.taches.selectors.base import rappels_de, taches_de
from apps.taches.services.gestes import enregistrer_geste, op_champ, op_creation

MAX_PAR_TACHE = 5
MAX_PAR_COMPTE = 100
DECALAGE_MIN, DECALAGE_MAX = -7, 0
STATUTS_CLOS = (StatutTache.FAIT, StatutTache.ANNULE)


@dataclass(frozen=True)
class ResultatRappel:
    rappel: object
    hors_fenetre: bool
    question_titres: bool
    geste: object = None


def _heure(valeur):
    if isinstance(valeur, datetime.time):
        return valeur.replace(second=0, microsecond=0)
    try:
        return datetime.time.fromisoformat(str(valeur)).replace(second=0, microsecond=0)
    except ValueError:
        raise serializers.ValidationError({'heure': ['Heure attendue (HH:MM).']})


def _jour(valeur):
    if valeur is None or isinstance(valeur, datetime.date):
        return valeur
    try:
        jour = datetime.date.fromisoformat(str(valeur))
    except ValueError:
        raise serializers.ValidationError({'jour': [MESSAGE_DATE]})
    if not jour_dans_bornes(jour):
        raise serializers.ValidationError({'jour': [MESSAGE_DATE]})
    return jour


def _jour_du_rappel(tache, jour, ancre, decalage_jours):
    """Le jour du rappel : donné, ou ancre + décalage (−7 à 0)."""
    if ancre not in AncreRappel.values:
        raise serializers.ValidationError({'ancre': ['Valeur inconnue.']})
    if not ancre:
        if jour is None:
            raise serializers.ValidationError({'jour': ['Requis.']})
        return jour
    if not DECALAGE_MIN <= int(decalage_jours) <= DECALAGE_MAX:
        raise serializers.ValidationError({'decalage_jours': ['Entre -7 et 0.']})
    base = getattr(tache, ancre)
    if base is None:
        raise serializers.ValidationError({'ancre': ["Cette date n'est pas posée sur la tâche."]})
    return base + datetime.timedelta(days=int(decalage_jours))


def est_hors_fenetre(company, jour, heure):
    """Vrai si la fenêtre des messages de la société est fermée à ce moment-là."""
    instant = timezone.make_aware(datetime.datetime.combine(jour, heure))
    return not fenetre_notifications(company, instant).ouverte


def _verrouiller_tache(acteur, tache):
    t = taches_de(acteur).select_for_update().filter(pk=getattr(tache, 'pk', tache)).first()
    if t is None:
        raise Http404('Introuvable.')
    if t.statut in STATUTS_CLOS:
        raise serializers.ValidationError({'rappel': ['Cette tâche est close.']})
    return t


def _verifier_plafonds(acteur, t):
    """≤ 5 en attente par tâche, ≤ 100 par compte. Le verrou des réglages du compte sérialise deux
    poses simultanées du même compte (la tâche, elle, est déjà verrouillée)."""
    reglages = (ReglagesRythme.objects.select_for_update()
                .filter(company_id=acteur.company_id, proprietaire=acteur).first())
    en_attente = rappels_de(acteur).filter(statut=StatutRappel.EN_ATTENTE)
    if en_attente.filter(tache=t).count() >= MAX_PAR_TACHE:
        raise serializers.ValidationError({'rappel': [f'{MAX_PAR_TACHE} rappels au plus par tâche.']})
    if en_attente.count() >= MAX_PAR_COMPTE:
        raise serializers.ValidationError({'rappel': [f'{MAX_PAR_COMPTE} rappels en attente au plus.']})
    return reglages


def _consigner(acteur, ops, collecte, message):
    if collecte is not None:
        collecte.extend(ops)
        return None
    return enregistrer_geste(acteur, 'rappel', message, ops)


def _creer(acteur, tache, *, heure, jour, ancre, decalage_jours, source):
    t = _verrouiller_tache(acteur, tache)
    jour = _jour_du_rappel(t, _jour(jour), ancre or '', decalage_jours or 0)
    reglages = _verifier_plafonds(acteur, t)
    rappel = Rappel.objects.create(
        company_id=acteur.company_id, proprietaire=acteur, tache=t, ancre=ancre or '',
        decalage_jours=int(decalage_jours or 0) if ancre else 0, jour=jour, heure=heure,
        source=source)
    question = reglages is None or reglages.titres_notifications_demande_le is None
    return rappel, question


def poser_rappel(tache, *, acteur, heure, jour=None, ancre='', decalage_jours=0,
                 source=SourceRappel.MANUEL, collecte=None):
    """Pose un rappel sur `tache` (à `acteur`) : `jour` + `heure`, ou ancre + décalage + heure.
    `collecte` reçoit l'opération sans créer de geste."""
    heure = _heure(heure)
    with transaction.atomic():
        rappel, question = _creer(acteur, tache, heure=heure, jour=jour, ancre=ancre,
                                  decalage_jours=decalage_jours, source=source)
        message = f'Rappel posé {format_jour(rappel.jour, timezone.localdate())} à {format_heure(heure)}'
        geste = _consigner(acteur, [op_creation('rappel', rappel)], collecte, message)
    return ResultatRappel(rappel, est_hors_fenetre(acteur.company, rappel.jour, rappel.heure), question, geste)


def _rappel_du_compte(acteur, rappel_id):
    try:
        pk = int(rappel_id)
    except (TypeError, ValueError):
        raise Http404('Introuvable.')
    rappel = rappels_de(acteur).select_for_update().filter(pk=pk).first()
    if rappel is None:
        raise Http404('Introuvable.')
    return rappel


def retirer_rappel(acteur, rappel_id):
    """Retire (statut `annule`) un rappel du compte → le geste, ou `None` s'il n'était plus en
    attente (idempotent)."""
    with transaction.atomic():
        rappel = _rappel_du_compte(acteur, rappel_id)
        if rappel.statut != StatutRappel.EN_ATTENTE:
            return None
        rappel.statut = StatutRappel.ANNULE
        rappel.save(update_fields=['statut', 'updated_at'])
        op = op_champ('rappel', rappel, 'statut', StatutRappel.EN_ATTENTE)
        return enregistrer_geste(acteur, 'rappel', 'Rappel retiré', [op])


def repeter_rappel(acteur, rappel_id, *, dans_minutes=None, jour=None, heure=None):
    """« Encore 10 min · 1 h · Demain 9 h » : un NOUVEAU rappel (source `repetition`) sur la même
    tâche, dans `dans_minutes` à partir de maintenant, ou à `jour` + `heure`."""
    maintenant = timezone.localtime()
    if dans_minutes is not None:
        cible = maintenant + datetime.timedelta(minutes=int(dans_minutes))
        jour, heure = cible.date(), cible.time()
        message = f'Rappel dans {format_duree(int(dans_minutes))}'
    else:
        heure = _heure(heure)
        message = f'Rappel posé {format_jour(_jour(jour), maintenant.date())} à {format_heure(heure)}'
    with transaction.atomic():
        source_rappel = _rappel_du_compte(acteur, rappel_id)
        rappel, question = _creer(acteur, source_rappel.tache_id, heure=_heure(heure), jour=jour,
                                  ancre='', decalage_jours=0, source=SourceRappel.REPETITION)
        geste = enregistrer_geste(acteur, 'rappel', message, [op_creation('rappel', rappel)])
    return ResultatRappel(rappel, est_hors_fenetre(acteur.company, rappel.jour, rappel.heure), question, geste)


def _en_attente_de(tache):
    return (Rappel.objects.select_for_update()
            .filter(company_id=tache.company_id, tache_id=tache.pk, statut=StatutRappel.EN_ATTENTE))


def _suivre_l_ancre(tache, rappel):
    base = getattr(tache, rappel.ancre)
    if base is None:
        rappel.statut = StatutRappel.ANNULE
        rappel.save(update_fields=['statut', 'updated_at'])
        return [op_champ('rappel', rappel, 'statut', StatutRappel.EN_ATTENTE)]
    jour, avant = base + datetime.timedelta(days=rappel.decalage_jours), rappel.jour
    if jour == avant:
        return []
    rappel.jour = jour
    rappel.save(update_fields=['jour', 'updated_at'])
    return [op_champ('rappel', rappel, 'jour', avant)]


def recalculer_ancres(tache, collecte=None):
    """L'ancre a bougé : le `jour` de chaque rappel ancré en attente suit ; une ancre effacée
    l'annule. Rend les opérations (ajoutées aussi à `collecte`). `tache` = déjà relue sous verrou
    par l'appelant (`planifier`, PATCH de l'échéance)."""
    ops = []
    with transaction.atomic():
        for rappel in _en_attente_de(tache).exclude(ancre=''):
            ops += _suivre_l_ancre(tache, rappel)
    if collecte is not None:
        collecte.extend(ops)
    return ops


def annuler_rappels(tache, collecte=None):
    """Invariant 19 : tâche close, abandonnée ou supprimée → ses rappels en attente `annule`.
    Rend les opérations (ajoutées aussi à `collecte`)."""
    ops = []
    with transaction.atomic():
        for rappel in _en_attente_de(tache):
            rappel.statut = StatutRappel.ANNULE
            rappel.save(update_fields=['statut', 'updated_at'])
            ops.append(op_champ('rappel', rappel, 'statut', StatutRappel.EN_ATTENTE))
    if collecte is not None:
        collecte.extend(ops)
    return ops
