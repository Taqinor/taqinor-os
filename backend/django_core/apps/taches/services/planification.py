"""Le SEUL chemin d'un jour (reference/donnees.md §5 « Signatures fixées », invariants 4, 14, 15).

`planifier()` est l'unique écriture de `jour_prevu`, `heure_debut`, `moment` et `quelque_jour` d'une
tâche (le PATCH les refuse ; seul `annuler_geste` restaure l'état d'avant). C'est aussi le seul
endroit qui compte un REPORT (`reports += 1` par `F()`, sous `select_for_update()`) :

- un report ⇔ l'ancien `jour_prevu` ≤ J ET le nouveau est plus tard ou « En réserve » ;
- jamais : futur → futur, avancer, premier jour posé, `compter_report=False` (Alléger, retour
  d'absence, décaler, instancier, création).

C'est donc aussi LA règle de la ligne de plan d'une tâche qui change de jour (`_suivre_les_lignes_du_plan`,
acceptation F2 défaut 6) : tous les chemins (Choisir un jour, Reporter, trancher, lot, décaler un
projet, Planifier ma semaine, placer dans l'agenda, récurrence, retour d'absence, bilan) passent ici.

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
from apps.taches.entrees import MESSAGE_DATE, jour_dans_bornes
from apps.taches.models.journee import LignePlanJour
from apps.taches.moteur.gabarits import format_heure, format_jour
from apps.taches.saisie.grammaire import moment_de
from apps.taches.selectors.base import jours_travailles_de, taches_de
from apps.taches.services.gestes import enregistrer_geste, op_champ, op_creation, op_suppression_dure
from apps.taches.services.rappels import recalculer_ancres
from core.verrou_optimiste import CHAMP_VERSION, CODE_CONFLIT_VERSION, ConflitVersion

MESSAGE_CONFLIT = "Cet enregistrement a été modifié par quelqu'un d'autre depuis son ouverture."
MESSAGE_HEURE_SANS_JOUR = 'Une heure demande un jour prévu.'
MESSAGE_VALEUR_INCONNUE = 'Valeur inconnue.'

#: Colonnes écrites par `planifier` (toutes dans la liste blanche de l'annulation, §4).
CHAMPS_ECRITS = ('jour_prevu', 'moment', 'heure_debut', 'quelque_jour', 'premier_jour_prevu',
                 'triee_le', 'rang_jour')

#: Champs d'une ligne de plan recopiés quand elle change (une ligne n'a pas de champ restaurable, §4).
CHAMPS_LIGNE = ('prevue_au_plan', 'faite', 'reportee', 'essentielle', 'creneau', 'rang')

AVERTISSEMENT_APRES_ECHEANCE = 'prevue_apres_echeance'
AVERTISSEMENT_JOUR_NON_TRAVAILLE = 'jour_non_travaille'
AVERTISSEMENT_ECHEANCE_AUJOURDHUI = 'echeance_aujourdhui'
MESSAGE_ECHEANCE_AUJOURDHUI = "L'échéance reste aujourd'hui."


@dataclass(frozen=True)
class ResultatPlanification:
    tache: object
    avertissements: list
    geste: object = None


def _en_date(valeur, champ):
    if valeur is None or isinstance(valeur, datetime.date):
        return valeur
    try:
        jour = datetime.date.fromisoformat(str(valeur))
    except ValueError:
        raise serializers.ValidationError({champ: [MESSAGE_DATE]})
    if not jour_dans_bornes(jour):
        raise serializers.ValidationError({champ: [MESSAGE_DATE]})
    return jour


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


def etat_minimal(tache):
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
                              CHAMP_VERSION: t.lock_version, 'actuel': etat_minimal(t)})
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


def avertissements_du_jour(acteur, t, aujourdhui):
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


def _avertissement_echeance(t, ancien_jour, aujourdhui):
    """R3-002 (choix C-13) : la tâche quitte le jour d'aujourd'hui (jour posé plus tard, ou retiré) alors que son
    échéance EST aujourd'hui — la règle ne change pas (`classement.gardee_aujourdhui` : l'échéance la garde dans la
    journée), le geste le DIT au lieu de la laisser revenir en silence. Rien pour « En réserve » (elle quitte alors
    la journée, invariant 10) ni quand le jour n'a pas changé."""
    if t.quelque_jour or t.echeance != aujourdhui or t.jour_prevu == aujourdhui or t.jour_prevu == ancien_jour:
        return []
    return [{'code': AVERTISSEMENT_ECHEANCE_AUJOURDHUI, 'message': MESSAGE_ECHEANCE_AUJOURDHUI}]


# --- Les lignes du plan (donnees.md §2.9) ----------------------------------------------------

def valeurs_ligne(ligne):
    return {'plan': ligne.plan_id, 'tache': ligne.tache_id, 'activite_id': ligne.activite_id,
            **{champ: getattr(ligne, champ) for champ in CHAMPS_LIGNE}}


def creer_ligne(plan, ops, *, tache_id=None, activite_id=None, **champs):
    ligne = LignePlanJour.objects.create(company_id=plan.company_id, plan=plan, tache_id=tache_id,
                                         activite_id=activite_id, **champs)
    op = op_creation('ligne_plan_jour', ligne)
    if tache_id is not None:
        op['tache'] = tache_id  # R3-008 : « Derniers gestes » dit le titre de la ★ sans relire une ligne disparue
    ops.append(op)
    return ligne


def remplacer_ligne(ligne, ops, **changements):
    """Une ligne n'a pas de champ restaurable (§4) : la changer = la supprimer (opération dure,
    restaurée à l'identique) et en créer une neuve — l'annulation défait les deux."""
    valeurs = valeurs_ligne(ligne)
    ops.append(op_suppression_dure('ligne_plan_jour', ligne, valeurs))
    plan = ligne.plan
    ligne.delete()
    champs = {champ: valeurs[champ] for champ in CHAMPS_LIGNE}
    champs.update(changements)
    return creer_ligne(plan, ops, tache_id=valeurs['tache'], activite_id=valeurs['activite_id'], **champs)


def _suivre_les_lignes_du_plan(t, ancien, ops):
    """LA règle d'une tâche gardée qui change de jour (regles.md §4.6, §4.9 ; invariant 18) : sa ligne
    du plan du jour qu'elle QUITTE reste une gardée — non tenue, comptée dans « x des y gardées » (seul
    Alléger retire une ligne) — et passe `reportee` comme au bilan ; revenue à ce jour (ou gardée par
    son échéance), elle ne l'est plus. Une requête quand le jour change, aucune sinon."""
    jours = [jour for jour in (ancien, t.jour_prevu) if jour is not None]
    if ancien == t.jour_prevu or not jours:
        return
    lignes = LignePlanJour.objects.filter(company_id=t.company_id, tache_id=t.pk,
                                          plan__jour__in=jours).select_related('plan')
    for ligne in lignes:
        reportee = ligne.plan.jour not in (t.jour_prevu, t.echeance)
        if ligne.reportee != reportee:
            remplacer_ligne(ligne, ops, reportee=reportee)


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
        ops += recalculer_ancres(t)  # rappels ancrés sur le jour prévu (TCH35)
        _suivre_les_lignes_du_plan(t, avant['jour_prevu'], ops)
        geste = None
        if collecte is not None:
            collecte.extend(ops)
        elif ops:
            geste = enregistrer_geste(acteur, 'planification', _message(t, avant, aujourdhui, report), ops)
    avertissements = avertissements_du_jour(acteur, t, aujourdhui) + _avertissement_echeance(
        t, avant['jour_prevu'], aujourdhui)
    return ResultatPlanification(t, avertissements, geste)
