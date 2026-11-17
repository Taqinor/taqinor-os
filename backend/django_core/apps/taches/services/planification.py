"""Le SEUL chemin d'un jour (reference/donnees.md §5 « Signatures fixées », invariants 4, 14, 15).

`planifier()` est l'unique écriture de `jour_prevu`, `heure_debut`, `moment` et `quelque_jour` d'une
tâche (le PATCH les refuse ; seul `annuler_geste` restaure l'état d'avant). C'est aussi le seul
endroit qui compte un REPORT (`reports += 1` par `F()`, sous `select_for_update()`) :

- un report ⇔ l'ancien `jour_prevu` ≤ J ET le nouveau est plus tard ou « En réserve » ;
- jamais : futur → futur, avancer, premier jour posé, `compter_report=False` (Alléger, retour
  d'absence, décaler, instancier, création).

Heure murale (invariant 14) : jour et heure sont stockés tels quels, jamais un instant UTC.
`collecte` (une liste) reçoit les opérations sans créer de geste : l'appelant (lot, rituels,
alléger, retour, décaler, instancier, création) enregistre UN geste pour tout son travail.
"""
import datetime
from dataclasses import dataclass

from django.db import transaction
from django.db.models import F
from django.http import Http404
from django.utils import timezone
from rest_framework import serializers

from apps.taches.choix import Moment
from apps.taches.moteur.gabarits import format_heure, format_jour
from apps.taches.saisie.grammaire import moment_de
from apps.taches.selectors.base import jours_travailles_de, taches_de
from apps.taches.services.gestes import enregistrer_geste, op_champ
from core.verrou_optimiste import CHAMP_VERSION, CODE_CONFLIT_VERSION, ConflitVersion

MESSAGE_CONFLIT = "Cet enregistrement a été modifié par quelqu'un d'autre depuis son ouverture."
MESSAGE_HEURE_SANS_JOUR = 'Une heure demande un jour prévu.'
MESSAGE_VALEUR_INCONNUE = 'Valeur inconnue.'

#: Colonnes écrites par `planifier` (toutes dans la liste blanche de l'annulation, §4).
CHAMPS_ECRITS = ('jour_prevu', 'moment', 'heure_debut', 'quelque_jour', 'premier_jour_prevu',
                 'triee_le', 'rang_jour')

AVERTISSEMENT_APRES_ECHEANCE = 'prevue_apres_echeance'
AVERTISSEMENT_JOUR_NON_TRAVAILLE = 'jour_non_travaille'


@dataclass(frozen=True)
class ResultatPlanification:
    tache: object
    avertissements: list
    geste: object = None


def _en_date(valeur, champ):
    if valeur is None or isinstance(valeur, datetime.date):
        return valeur
    try:
        return datetime.date.fromisoformat(str(valeur))
    except ValueError:
        raise serializers.ValidationError({champ: ['Date attendue (AAAA-MM-JJ).']})


def _en_heure(valeur):
    if valeur is None or isinstance(valeur, datetime.time):
        return valeur
    try:
        return datetime.time.fromisoformat(str(valeur))
    except ValueError:
        raise serializers.ValidationError({'heure_debut': ['Heure attendue (HH:MM).']})


def _normaliser(jour_prevu, moment, heure_debut, quelque_jour):
    """(jour, moment, heure) cohérents : « En réserve » n'a ni jour ni heure ; une heure exige un
    jour et dérive le moment (invariant 15) ; sans jour, pas de moment."""
    jour, heure = _en_date(jour_prevu, 'jour_prevu'), _en_heure(heure_debut)
    if quelque_jour:
        return None, '', None
    if heure is not None and jour is None:
        raise serializers.ValidationError({'heure_debut': [MESSAGE_HEURE_SANS_JOUR]})
    if heure is not None:
        return jour, moment_de(heure), heure
    moment = moment or ''
    if moment not in Moment.values:
        raise serializers.ValidationError({'moment': [MESSAGE_VALEUR_INCONNUE]})
    return jour, (moment if jour is not None else ''), None


def _actuel(tache):
    """État courant MINIMAL servi dans le 409 (sans titre ni notes) ; la vue le remplace par la
    forme TACHE complète (`exc.tache` porte l'instance relue)."""
    def iso(v):
        return v.isoformat() if v is not None else None
    return {'type': 'tache', 'id': tache.pk, 'statut': tache.statut,
            'jour_prevu': iso(tache.jour_prevu), 'moment': tache.moment,
            'heure_debut': tache.heure_debut.strftime('%H:%M') if tache.heure_debut else None,
            'quelque_jour': tache.quelque_jour, 'reports': tache.reports,
            CHAMP_VERSION: tache.lock_version, 'updated_at': iso(tache.updated_at)}


def _verrouiller(acteur, tache, version):
    """La tâche de `acteur` relue SOUS VERROU (404 si elle n'est pas à lui ou plus vivante) ; la
    version envoyée est comparée sous ce verrou (409 `conflit_version`)."""
    pk = getattr(tache, 'pk', tache)
    t = taches_de(acteur).select_for_update().filter(pk=pk).first()
    if t is None:
        raise Http404('Introuvable.')
    if version is not None and t.lock_version != int(version):
        exc = ConflitVersion({'detail': MESSAGE_CONFLIT, 'code': CODE_CONFLIT_VERSION,
                              CHAMP_VERSION: t.lock_version, 'actuel': _actuel(t)})
        exc.tache = t
        raise exc
    return t


def _compte_un_report(ancien, nouveau, quelque_jour, aujourdhui):
    """Invariant 4 : l'ancien jour est passé ou aujourd'hui ET le nouveau est plus tard (ou En
    réserve). Un premier jour posé, avancer, futur → futur : jamais."""
    if ancien is None or ancien > aujourdhui:
        return False
    if quelque_jour:
        return True
    return nouveau is not None and nouveau > ancien


def _ecrire(t, jour, moment, heure, quelque_jour, maintenant, report):
    change_de_jour = t.jour_prevu != jour
    t.jour_prevu, t.moment, t.heure_debut, t.quelque_jour = jour, moment, heure, quelque_jour
    if jour is not None and t.premier_jour_prevu is None:
        t.premier_jour_prevu = jour
    if t.triee_le is None:
        t.triee_le = maintenant
    if change_de_jour:
        t.rang_jour = None  # l'ordre d'une section du jour ne suit pas la tâche ailleurs
    champs = list(CHAMPS_ECRITS) + ['updated_at']
    if report:
        t.reports = F('reports') + 1
        champs.append('reports')
    t.save(update_fields=champs)
    if report:
        t.refresh_from_db(fields=['reports'])


def _message(t, avant, aujourdhui, report):
    if t.quelque_jour:
        return 'En réserve'
    if t.jour_prevu is None:
        return 'Sans jour'
    if t.heure_debut is not None and t.heure_debut != avant['heure_debut']:
        return f'Placée à {format_heure(t.heure_debut)}'
    if t.jour_prevu == aujourdhui:
        return "Mise à aujourd'hui"
    jour = format_jour(t.jour_prevu, aujourdhui)
    return f'Reportée à {jour}' if report else f'Prévue {jour}'


def _avertissements(acteur, t, aujourdhui):
    sortie = []
    if t.jour_prevu is None:
        return sortie
    if t.echeance is not None and t.jour_prevu > t.echeance:
        sortie.append({'code': AVERTISSEMENT_APRES_ECHEANCE, 'message': "Prévue après l'échéance."})
    if t.jour_prevu not in jours_travailles_de(acteur, t.jour_prevu, t.jour_prevu):
        jour = format_jour(t.jour_prevu, aujourdhui)
        sortie.append({'code': AVERTISSEMENT_JOUR_NON_TRAVAILLE,
                       'message': f"{jour[:1].upper()}{jour[1:]} n'est pas un jour travaillé."})
    return sortie


def _apres_le_jour(t, collecte):
    """Ce qui suit le jour posé, dans la même transaction (rappels ancrés : TCH35)."""


def planifier(tache, *, acteur, jour_prevu, moment='', heure_debut=None, quelque_jour=False,
              compter_report=True, version=None, collecte=None):
    """Pose le jour, l'heure, le moment ou « En réserve » de `tache` (à `acteur`) → résultat
    (tâche relue, avertissements, geste ou `None` quand `collecte` est fournie)."""
    jour, moment, heure = _normaliser(jour_prevu, moment, heure_debut, quelque_jour)
    quelque_jour = bool(quelque_jour)
    aujourdhui, maintenant = timezone.localdate(), timezone.now()
    with transaction.atomic():
        t = _verrouiller(acteur, tache, version)
        avant = {champ: getattr(t, champ) for champ in CHAMPS_ECRITS + ('reports',)}
        report = compter_report and _compte_un_report(t.jour_prevu, jour, quelque_jour, aujourdhui)
        _ecrire(t, jour, moment, heure, quelque_jour, maintenant, report)
        ops = [op_champ('tache', t, champ, valeur) for champ, valeur in avant.items()
               if getattr(t, champ) != valeur]
        ops += _apres_le_jour(t, collecte) or []
        geste = None
        if collecte is not None:
            collecte.extend(ops)
        elif ops:
            geste = enregistrer_geste(acteur, 'planification', _message(t, avant, aujourdhui, report), ops)
    return ResultatPlanification(t, _avertissements(acteur, t, aujourdhui), geste)
