"""Le balayage de chaque minute `taches.balayer` (reference/api.md §9 ; reference/regles.md « Les
sollicitations », « Activation par étapes et coupe-circuit ») : le SEUL envoi de l'app.

`executer(maintenant=None)` parcourt les sociétés à balayer (`sweeps.societes_a_balayer()` : société
active, module actif, coupe-circuit `ReglagesSociete.balayage_actif` relu À CHAQUE passage — invariant
39 ; coupée : RIEN, ni rappel ni sollicitation, et rien n'est marqué), puis, par société :

1. **Rappels posés** (hors plafond, à l'heure demandée même hors fenêtre) : dus = `jour < J` ou
   (`jour = J` ∧ `heure ≤` maintenant) ; retard > 2 h → `manque`, jamais envoyé (pas de rafale après
   une coupure) ; un compte sans le droit du module (`views.base.a_le_droit`, relu à chaque passage,
   invariant 28) n'en reçoit aucun ; les autres sont GROUPÉS par minute et par compte : pris par
   `UPDATE … WHERE statut='en_attente'` puis `notify(TACHES_RAPPEL)` dans la même transaction.
2. **Sollicitations** (`moteur/sollicitations.py` décide de tout : tick, sauts, priorité, plafond) :
   pour chaque compte actif, interne, ayant une `ReglagesRythme` et le droit du module ; le marqueur
   `IncitationCoach` (canal `push`) est pris par `get_or_create` puis
   `notify(…, respect_quiet_hours=False, badge=…)` dans la même transaction — `notify` ne diffère donc
   jamais une sollicitation : la fenêtre de la société est contrôlée ICI, avant (sautée, jamais
   différée — invariant 22).

Rejouer le balayage n'envoie rien de plus. Le corps d'une notification ne porte un titre que si
`titres_notifications` ET l'objet n'est pas confidentiel (`confidentialite.nom_pour`, usage
`notification`) ; par défaut, aucun titre (textes.md §3). Une société en échec est journalisée et
n'arrête pas les suivantes.
"""
import datetime
import logging
from dataclasses import dataclass, replace

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.notifications.services import notify
from apps.notifications.types_evenements import EventType
from apps.taches import confidentialite
from apps.taches.choix import CanalIncitation, ClePreference, ModeRythme, StatutProjet, StatutRappel, StatutTache
from apps.taches.models.presence import ReglagesSociete
from apps.taches.models.rythme import IncitationCoach, ReglagesRythme
from apps.taches.models.taches import Rappel
from apps.taches.moteur import sollicitations as regles
from apps.taches.moteur.gabarits import format_heure_dite, texte
from apps.taches.selectors import journee as sel
from apps.taches.selectors.base import _conges, _en_conge, jours_travailles_de, projets_de
from apps.taches.selectors.projets import bilan_de_semaine
from apps.taches.services import journee as service_journee
from apps.taches.services import rythme as service_rythme
from apps.taches.views.base import a_le_droit

logger = logging.getLogger(__name__)

#: Un rappel en retard de plus de 2 h est `manque`, jamais envoyé (regles.md « Les sollicitations »).
RETARD_MANQUE = datetime.timedelta(hours=2)
#: Un projet négligé ne fait l'objet que d'une relance par 7 jours (IR13).
NEGLIGE_UNE_FOIS_PAR = datetime.timedelta(days=7)
CANAL_MESSAGES = 'whatsapp'  # la fenêtre des MESSAGES de la société (`notifications.selectors`)
LIEN_AUJOURDHUI = '/taches/aujourdhui'
#: Le test des notifications mène à l'écran Mon iPhone (textes.md §3 : « test → Mon iPhone »).
LIEN_MON_IPHONE = '/taches/reglages/iphone'
LIENS = {regles.PLAN_MATIN: LIEN_AUJOURDHUI, regles.RELANCE: LIEN_AUJOURDHUI,
         regles.BILAN_SOIR: f'{LIEN_AUJOURDHUI}?ouvrir=bilan', regles.REVUE_SEMAINE: '/taches/revue'}
EVENEMENTS = {regles.PLAN_MATIN: EventType.TACHES_PLAN_DU_JOUR, regles.RELANCE: EventType.TACHES_RELANCE,
              regles.BILAN_SOIR: EventType.TACHES_BILAN_SOIR, regles.REVUE_SEMAINE: EventType.TACHES_BILAN_SOIR}
#: Heures des sollicitations : (champ de `PrefsSollicitation`, clé de `Preference`, défaut).
HEURES = (('heure_matin', ClePreference.HEURE_MATIN, regles.HEURE_MATIN_DEFAUT),
          ('relance_jour', ClePreference.RELANCE_JOUR, regles.HEURE_RELANCE_DEFAUT),
          ('heure_soir', ClePreference.HEURE_SOIR, regles.HEURE_SOIR_DEFAUT),
          ('heure_limite', ClePreference.HEURE_LIMITE, regles.HEURE_LIMITE_DEFAUT))
FERMEE = regles.Fenetre(datetime.time(0, 0), datetime.time(0, 0))
CHARGEMENT_RAPPEL = ('tache', 'tache__projet', 'tache__parent', 'tache__parent__projet')


@dataclass(frozen=True)
class Message:
    """Ce qu'une sollicitation envoie : gabarit, variables (des nombres), objets nommables."""
    cle: str
    nombres: dict
    objets: dict
    heure: object = None


# --- Le passage -------------------------------------------------------------------------------------

def executer(maintenant=None):
    """Un passage du balayage → `{"societes", "rappels", "manques", "sollicitations"}` (compteurs)."""
    from apps.taches.sweeps import societes_a_balayer  # sweeps importe ce module (tâche Celery)
    maintenant = timezone.localtime(maintenant) if maintenant is not None else timezone.localtime()
    bilan = {'societes': 0, 'rappels': 0, 'manques': 0, 'sollicitations': 0}
    for company_id in societes_a_balayer():
        try:
            resultat = _balayer_societe(company_id, maintenant)
        except Exception:  # noqa: BLE001 — une société en échec n'arrête pas le balayage (journalisée)
            logger.exception('taches.balayer : société %s en échec (%s)', company_id, maintenant.isoformat())
            continue
        bilan['societes'] += 1
        for cle, valeur in resultat.items():
            bilan[cle] += valeur
    return bilan


def _balayer_societe(company_id, maintenant):
    manques, rappels = _rappels_dus(company_id, maintenant)
    envoyees = 0
    comptes = (ReglagesRythme.objects.filter(company_id=company_id, proprietaire__is_active=True,
                                             proprietaire__portee='interne')
               .select_related('proprietaire', 'proprietaire__company', 'proprietaire__role')
               .order_by('proprietaire_id'))
    fenetres = {}
    for reglages in comptes:
        if not a_le_droit(reglages.proprietaire):  # rôle vidé de `taches_voir` : plus rien (inv. 28)
            continue
        company = reglages.proprietaire.company
        if company.pk not in fenetres:
            fenetres[company.pk] = fenetre_messages(company, maintenant.date())
        envoyees += _solliciter(reglages, maintenant, fenetres[company.pk])
    return {'manques': manques, 'rappels': rappels, 'sollicitations': envoyees}


def fenetre_messages(company, jour):
    """La fenêtre des messages de la société ce jour (`crm.horaires`, celle que `notify` applique),
    fermée un jour non ouvré."""
    from apps.crm import horaires  # module pur, lu comme le fait notifications.selectors
    plage = horaires.fenetre_du_jour(jour, company, canal=CANAL_MESSAGES)
    return regles.Fenetre(plage[0], plage[1]) if plage else FERMEE


# --- 1. Rappels posés ----------------------------------------------------------------------------------

def _instant_q(instant):
    """Rappels à l'heure murale ≤ `instant` (jour antérieur, ou même jour et heure ≤)."""
    return Q(jour__lt=instant.date()) | Q(jour=instant.date(), heure__lte=instant.time())


def _rappels_dus(company_id, maintenant):
    """(manqués, notifications de rappel envoyées) pour la société."""
    en_attente = Rappel.objects.filter(company_id=company_id, statut=StatutRappel.EN_ATTENTE)
    limite = maintenant - RETARD_MANQUE
    trop_tard = en_attente.filter(Q(jour__lt=limite.date()) | Q(jour=limite.date(), heure__lt=limite.time()))
    manques = trop_tard.update(statut=StatutRappel.MANQUE, updated_at=timezone.now())
    groupes = {}
    for pk, proprietaire_id, jour, heure in (en_attente.filter(_instant_q(maintenant))
                                             .filter(proprietaire__is_active=True)
                                             .order_by('jour', 'heure', 'pk')
                                             .values_list('pk', 'proprietaire_id', 'jour', 'heure')):
        groupes.setdefault((proprietaire_id, jour, heure.replace(second=0, microsecond=0)), []).append(pk)
    admis = _comptes_admis({proprietaire_id for proprietaire_id, _jour, _heure in groupes})
    envoyes = sum(_envoyer_rappels(ids, maintenant) for (proprietaire_id, _jour, _heure), ids in groupes.items()
                  if proprietaire_id in admis)
    return manques, envoyes


def _comptes_admis(ids):
    """Les comptes de `ids` qui ont le droit du module à cet instant (`a_le_droit`, la garde des
    routes), en UNE requête ; aucune si rien n'est dû. Un rappel d'un compte sans le droit reste en
    attente : jamais pris, il devient `manque` après 2 h (aucune rafale si le droit revient)."""
    if not ids:
        return set()
    from django.contrib.auth import get_user_model
    return {user.pk for user in get_user_model().objects.filter(pk__in=ids).select_related('role')
            if a_le_droit(user)}


def _envoyer_rappels(ids, maintenant):
    """Un groupe (compte, minute) : pris par `UPDATE … WHERE statut='en_attente'`, puis UNE notification
    dans la même transaction ; rien si un autre passage l'a déjà pris."""
    with transaction.atomic():
        pris = list(Rappel.objects.select_for_update(skip_locked=True, of=('self',))
                    .filter(pk__in=ids, statut=StatutRappel.EN_ATTENTE)
                    .select_related(*CHARGEMENT_RAPPEL, 'proprietaire').order_by('pk'))
        if not pris:
            return 0
        n = Rappel.objects.filter(pk__in=[r.pk for r in pris], statut=StatutRappel.EN_ATTENTE).update(
            statut=StatutRappel.ENVOYE, envoye_le=maintenant, updated_at=timezone.now())
        if n == 0:
            return 0
        premier, user = pris[0], pris[0].proprietaire
        reglages = sel.reglages_de(user)
        variables = {'heure': format_heure_dite(premier.heure), 'n': n, 'titre': premier.tache,
                     'avec_titres': bool(reglages and reglages.titres_notifications)}
        corps = texte('notification', 'rappel', variables, _variante(maintenant), _nommer(reglages))
        lien = f'{LIEN_AUJOURDHUI}?tache={premier.tache_id}' if n == 1 else LIEN_AUJOURDHUI
        notify(user, EventType.TACHES_RAPPEL, texte('notification', 'titre.rappel', {}), body=corps,
               link=lien, company=user.company, badge=sel.compter_journee(user, maintenant.date()))
    return 1


def _nommer(reglages):
    """`nom_pour` de la confidentialité, avec la `ReglagesRythme` déjà lue (titres_notifications)."""
    return lambda objet, usage: confidentialite.nom_pour(objet, usage, reglages)


def _variante(maintenant):
    return regles.variante(maintenant.date().toordinal())


# --- 2. Sollicitations -------------------------------------------------------------------------------

def _heure(valeur, defaut):
    """`"HH:MM"` → heure ; `"off"` → `None` (type éteint) ; illisible ou absent → le défaut."""
    if valeur == 'off':
        return None
    if isinstance(valeur, str):
        try:
            return datetime.time.fromisoformat(valeur)
        except ValueError:
            logger.warning('taches.balayer : heure dite illisible (%r), défaut gardé', valeur)
    return defaut


def _revue(valeur):
    if valeur in ('auto', 'off') or (isinstance(valeur, int) and not isinstance(valeur, bool) and 0 <= valeur <= 6):
        return valeur
    return 'auto'


def _envoyes_du_jour(user, jour):
    """Types push déjà partis ce jour (le journal du plafond)."""
    return list(IncitationCoach.objects.filter(
        company_id=user.company_id, proprietaire=user, canal=CanalIncitation.PUSH, jour=jour,
        montre_le__isnull=False).values_list('type', flat=True))


def _prefs_de_base(reglages, maintenant, envoyes):
    """Ce que `due` lit sans lire la journée : heures dites, jours travaillés, congé, pauses, plafond."""
    user, jour = reglages.proprietaire, maintenant.date()
    preferences = sel.preferences_de(user)
    heures = {champ: _heure(preferences.get(cle), defaut) for champ, cle, defaut in HEURES}
    dimanche = jour + datetime.timedelta(days=6 - jour.weekday())
    travailles = jours_travailles_de(user, jour, dimanche)
    return regles.PrefsSollicitation(
        heure_matin=heures['heure_matin'], relance_jour=heures['relance_jour'], heure_soir=heures['heure_soir'],
        heure_limite=heures['heure_limite'] or regles.HEURE_LIMITE_DEFAUT,
        revue_semaine=_revue(preferences.get(ClePreference.REVUE_SEMAINE, 'auto')),
        dernier_jour_travaille_semaine=jour in travailles and max(travailles) == jour,
        jour_travaille=jour in travailles,
        en_conge=_en_conge(jour, _conges(preferences.get(ClePreference.CONGES))),
        pauses=tuple(p.get('type') if isinstance(p, dict) else p for p in reglages.pauses_sollicitations or ()),
        plafond_atteint=regles.plafond_atteint(envoyes))


def _solliciter(reglages, maintenant, fenetre):
    """0 ou 1 sollicitation envoyée à ce compte à ce tick (`moteur/sollicitations.py` décide)."""
    jour = maintenant.date()
    envoyes = _envoyes_du_jour(reglages.proprietaire, jour)
    base = _prefs_de_base(reglages, maintenant, envoyes)
    # Types dans leur tick et non sautés (compte, fenêtre, heure limite, plafond), leur condition
    # d'envoi supposée vraie : la journée n'est lue que pour eux.
    optimiste = replace(base, plan_valide=False, nb_jour_et_propose=1, nb_faites=1,
                        motif_relance=regles.MOTIF_ECHEANCE)
    candidats = [t for t in regles.ORDRE_PRIORITE if regles.due(t, maintenant, optimiste, fenetre)]
    if not candidats or candidats[0] in envoyes:
        return 0
    lecture = _lire(reglages, maintenant, candidats)
    prefs = replace(base, **lecture.conditions)
    # Un type déjà parti à ce tick reste « dû » pour le départage : l'autre reste sauté, jamais différé.
    dus = [t for t in candidats if t in envoyes or regles.due(t, maintenant, prefs, fenetre)]
    retenu, _sautes = regles.departager(dus)
    if retenu is None or retenu in envoyes:
        return 0
    return _envoyer(reglages, retenu, _message(retenu, lecture, prefs), maintenant, lecture)


@dataclass
class Lecture:
    """La journée du compte lue une fois pour la sollicitation du tick (jamais un titre stocké)."""
    ctx: object
    mode: str
    objectif: object
    zone: object
    gardees: list
    proposees: list
    echeances: list
    essentiel_ouvert: object
    neglige: object
    conditions: dict


def _essentiels(ctx):
    """(nombre d'essentiels choisis, première tâche essentielle encore ouverte ou `None`)."""
    lignes = [ligne for ligne in ctx.journee.lignes if ligne.essentielle]
    ouvertes = [ctx.journee.objets.get((service_journee.TACHE, ligne.tache_id)) for ligne in lignes
                if ligne.tache_id is not None]
    ouvertes = [t for t in ouvertes if t is not None and t.statut != StatutTache.FAIT]
    return len(lignes), (ouvertes[0] if ouvertes else None)


def _projet_neglige(user, jour):
    """Le projet prioritaire négligé (`services.rythme`), au plus une relance par projet et par 7 jours."""
    projet_id = service_rythme._projet_neglige(user, jour)
    if projet_id is None:
        return None
    deja = IncitationCoach.objects.filter(
        company_id=user.company_id, proprietaire=user, type=regles.RELANCE, canal=CanalIncitation.PUSH,
        jour__gt=jour - NEGLIGE_UNE_FOIS_PAR, donnees__projet_id=projet_id).exists()
    return None if deja else projets_de(user).filter(pk=projet_id).first()


def _motifs(mode, objectif, zone, compte, choisis, echeances, neglige):
    """Les motifs de relance présents (regles.md « Priorité de la relance »)."""
    motifs = []
    if echeances:
        motifs.append(regles.MOTIF_ECHEANCE)
    if (mode == ModeRythme.POUSSER and objectif is not None and compte < objectif / 2
            and (choisis == 0 or compte == 0)):
        motifs.append(regles.MOTIF_DERIVE)
    if mode == ModeRythme.TENIR and zone is not None and compte >= zone[1]:
        motifs.append(regles.MOTIF_DERIVE)
    if neglige is not None:
        motifs.append(regles.MOTIF_NEGLIGE)
    return motifs


def _lire(reglages, maintenant, candidats):
    """La journée du compte (`services.journee`) et les conditions d'envoi des types candidats."""
    user, jour = reglages.proprietaire, maintenant.date()
    ctx = service_journee._lire_contexte(user, jour, maintenant)
    propose = service_journee.proposer(ctx)
    objets = ctx.journee.objets
    gardees = [objets[cle] for cle in sel.gardes_ouverts(ctx.journee) if cle[0] == service_journee.TACHE]
    proposees = [objets[(service_journee.TACHE, item.id)] for item, _raison in propose.pour_objectif]
    echeances = sorted((t for (type_, _pk), t in objets.items() if type_ == service_journee.TACHE
                        and t.statut == StatutTache.A_FAIRE and t.echeance == jour), key=lambda t: t.pk)
    choisis, essentiel_ouvert = _essentiels(ctx)
    neglige = _projet_neglige(user, jour) if regles.RELANCE in candidats else None
    mode, objectif, zone = ctx.objectif['mode'], ctx.objectif['nb'], ctx.objectif['zone']
    motifs = _motifs(mode, objectif, zone, ctx.compte, choisis, echeances, neglige)
    conditions = {'plan_valide': ctx.plan is not None and ctx.plan.planifie_le is not None,
                  'nb_jour_et_propose': len(gardees) + len(proposees), 'nb_faites': ctx.compte,
                  'motif_relance': regles.choisir_relance(motifs)}
    return Lecture(ctx=ctx, mode=mode, objectif=objectif, zone=zone, gardees=gardees, proposees=proposees,
                   echeances=echeances, essentiel_ouvert=essentiel_ouvert, neglige=neglige, conditions=conditions)


# --- Le message de chaque type (textes.md §3) ----------------------------------------------------------

def _message_matin(lecture):
    prevues, en_tete = len(lecture.gardees), (lecture.gardees or lecture.proposees or [None])[0]
    if lecture.mode == ModeRythme.POUSSER and lecture.gardees:
        return Message('matin.pousser_gardees', {'prevues': prevues, 'objectif': lecture.objectif},
                       {'titre': en_tete})
    if lecture.mode == ModeRythme.POUSSER:
        return Message('matin.pousser_proposees', {'proposees': len(lecture.proposees),
                                                   'objectif': lecture.objectif}, {'titre': en_tete})
    if lecture.mode == ModeRythme.TENIR and lecture.zone is not None:
        return Message('matin.tenir', {'prevues': prevues, 'bas': lecture.zone[0], 'haut': lecture.zone[1]},
                       {'titre': en_tete})
    return Message('matin.libre', {'prevues': prevues}, {'titre': en_tete})


def _message_relance(lecture):
    motif, faites = lecture.conditions['motif_relance'], lecture.ctx.compte
    if motif == regles.MOTIF_ECHEANCE:
        n = len(lecture.echeances)
        return Message('relance.echeance', {'n': n, 'n_autres': n - 1}, {'titre': lecture.echeances[0]})
    if motif == regles.MOTIF_NEGLIGE:
        return Message('relance.neglige', {'projet_id': lecture.neglige.pk}, {'projet': lecture.neglige})
    if lecture.mode == ModeRythme.TENIR:
        return Message('relance.derive_tenir',
                       {'faites': faites, 'bas': lecture.zone[0], 'haut': lecture.zone[1]}, {})
    nombres = {'faites': faites, 'objectif': lecture.objectif}
    if lecture.essentiel_ouvert is not None:
        return Message('relance.derive_pousser_essentiel', nombres, {'titre': lecture.essentiel_ouvert})
    return Message('relance.derive_pousser_sans_essentiel', nombres, {})


def _message_soir(lecture):
    nombres = {'faites': lecture.ctx.compte, 'restes': len(lecture.gardees)}
    if lecture.mode == ModeRythme.LIBRE or lecture.objectif is None:
        return Message('soir.libre', nombres, {})
    return Message('soir.pousser', {**nombres, 'objectif': lecture.objectif}, {})


def _message_revue(lecture):
    user, jour = lecture.ctx.user, lecture.ctx.jour
    courte, bilan = bilan_de_semaine(user, sel.lundi_de(jour), lecture.mode)
    if courte:
        return Message('revue.courte', {}, {})
    donnees = (bilan or {}).get('donnees') or {}
    projets = projets_de(user).filter(statut=StatutProjet.ACTIF).count()
    return Message('revue', {'faites': donnees.get('faites', 0), 'jours': donnees.get('jours', 0),
                             'projets': projets}, {})


MESSAGES = {regles.PLAN_MATIN: _message_matin, regles.RELANCE: _message_relance,
            regles.BILAN_SOIR: _message_soir, regles.REVUE_SEMAINE: _message_revue}


def _message(type_, lecture, prefs):
    message = MESSAGES[type_](lecture)
    return replace(message, heure=format_heure_dite(prefs.relance_jour)) if type_ == regles.RELANCE else message


def _envoyer(reglages, type_, message, maintenant, lecture):
    """Marqueur `IncitationCoach` (`get_or_create`) + `notify` dans la même transaction → 1, ou 0 si un
    autre passage l'a déjà pris. La fenêtre est déjà contrôlée : `respect_quiet_hours=False`."""
    user, jour = reglages.proprietaire, maintenant.date()
    variables = {**message.nombres, **message.objets, 'heure': message.heure,
                 'avec_titres': bool(reglages.titres_notifications)}
    titre = texte('notification', f'titre.{type_}', variables)
    corps = texte('notification', message.cle, variables, _variante(maintenant), _nommer(reglages))
    badge = sel.compter_journee(user, jour, journee=lecture.ctx.journee)
    with transaction.atomic():
        _marqueur, cree = IncitationCoach.objects.get_or_create(
            company=user.company, proprietaire=user, type=type_, jour=jour, cle='',
            defaults={'canal': CanalIncitation.PUSH, 'donnees': dict(message.nombres), 'montre_le': maintenant})
        if not cree:
            return 0
        notify(user, EVENEMENTS[type_], titre, body=corps, link=LIENS[type_], company=user.company,
               respect_quiet_hours=False, badge=badge)
    return 1


# --- 3. Le test des notifications -------------------------------------------------------------------------

def envoyer_test(user):
    """`POST mon-iphone/test-notification/` : UNE notification `TACHES_RAPPEL` au seul compte `user`
    (titre et corps du gabarit `test`, lien Mon iPhone) → 1, ou 0 si le coupe-circuit de la société est
    allumé (« aucune notification de Tâches », textes.md §3 ; relu à chaque appel, absent = actif).

    Hors plafond (regles.md « Les sollicitations ») : aucun marqueur `IncitationCoach`, donc ni plafond
    consommé, ni pause, ni décroissance. L'appui est un geste du compte : la notification part tout de
    suite, jamais différée à l'ouverture de la société (`respect_quiet_hours=False`). Aucun titre de
    tâche (regles.md §8) : le texte est celui du gabarit, rien n'est lu de la journée."""
    if ReglagesSociete.objects.filter(company_id=user.company_id, balayage_actif=False).exists():
        return 0
    notify(user, EventType.TACHES_RAPPEL, texte('notification', 'titre.test', {}),
           body=texte('notification', 'test', {}), link=LIEN_MON_IPHONE, company=user.company,
           respect_quiet_hours=False)
    return 1
