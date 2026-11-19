"""Services de la journée (reference/regles.md « La journée » ; api.md §2, §3.1, §4 `journee/*`).

- `aujourdhui(...)` : LE contrat de la journée (api.md §2) ; `badge(...)`, `ailleurs(...)`, `vu(...)` ;
- la carte du moment (regles.md « La carte du moment ») : UNE carte, la première vraie dans l'ordre
  de `CarteDuMoment` ;
- étape de nuit `clore_jour_precedent` (appelée par `nocturne.executer`).

Les règles viennent des modules purs (`moteur/classement.py`, `moteur/rythme.py`,
`moteur/gabarits.py`) ; les lectures, de `selectors/journee.py`.
"""
import datetime
import logging
from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.utils import timezone

from apps.taches.choix import (
    CanalIncitation, CarteDuMoment, ClePreference, Decision, MotifRevoir, SectionJournee, StatutSuggestion,
    StatutTache, TypeIncitationEcran)
from apps.taches.models.erp import SuggestionTache
from apps.taches.models.journee import PlanJour
from apps.taches.models.rythme import IncitationCoach, ReglagesRythme
from apps.taches.moteur import classement, gabarits
from apps.taches.moteur.rythme import RETOUR_JOURS_TRAVAILLES, statut_jour
from apps.taches.moteur.sollicitations import HEURE_RELANCE_DEFAUT, HEURE_SOIR_DEFAUT
from apps.taches.selectors import journee as sel
from apps.taches.selectors.base import jours_travailles_de, prochain_jour_travaille, taches_de
from apps.taches.serializers import journee as formes_journee
from apps.taches.serializers.formes import charger_items, charger_taches, tache_ecrite
from apps.taches.services import rythme as service_rythme
from apps.taches.services.gestes import enregistrer_geste, op_champ, op_creation, op_suppression_dure
from apps.taches.services.planification import creer_ligne, planifier, remplacer_ligne, valeurs_ligne
from apps.taches.services.rappels import annuler_rappels

logger = logging.getLogger(__name__)

TACHE = classement.TACHE
ACTIVITE = classement.ACTIVITE
MIDI = datetime.time(12, 0)
#: Une carte `retour` reste valable une semaine (contrat `vu.json`).
DUREE_CARTE_RETOUR = datetime.timedelta(days=7)
#: Suggestions visibles 7 jours (spec-6a §3.7).
DUREE_SUGGESTION = datetime.timedelta(days=7)
#: Propositions du rythme servies le matin (carte `rythme`) ; un constat ne l'est que s'il pose une QUESTION
#: (`_rythme_du_matin`, R3-005, choix C-17 : une statistique sans geste — C5 — n'apparaît jamais le matin, elle
#: vit dans Mon rythme et, une fois, au bilan du soir, regles.md §6.9).
TYPES_RYTHME = (TypeIncitationEcran.PROPOSITION_PALIER, TypeIncitationEcran.DERIVE_TENIR,
                TypeIncitationEcran.GARDE_TAILLE)
#: Cartes « de conseil » (C-17) : au plus UNE par jour — répondue (écartée, suivie) aujourd'hui, plus aucune
#: jusqu'au lendemain, ni au rechargement ni sur un autre appareil. Les cartes liées à l'heure (`retour`,
#: `bilan_hier`, `garder`, `alleger`, `faire_bilan`) n'en sont pas.
TYPES_CONSEIL = TYPES_RYTHME + (TypeIncitationEcran.CONSTAT, TypeIncitationEcran.PAUSE,
                                TypeIncitationEcran.REVELATION)
#: Compteurs « Ailleurs dans l'ERP » : clé du contrat → `kind` des files publiques (spec-6a §3.5).
KINDS_AILLEURS = {
    'chantiers': 'chantier_assigne', 'tickets': 'ticket_transfere', 'da_a_commander': 'da_approuvee_a_commander',
    'leads_chauds': 'lead_chaud', 'rappels': 'rappel', 'devis_expirant': 'devis_expire', 'relances': 'relance',
}
LIEN_AILLEURS = '/activites'


# --- Le contexte d'une journée (lu une fois) -----------------------------------------------------

@dataclass
class Contexte:
    """Tout ce qu'`aujourdhui/` lit, en une passe."""
    user: object
    jour: datetime.date
    maintenant: datetime.datetime
    journee: object
    obligations: object
    preferences: dict
    objectif: dict
    compte: int
    detail: dict
    capacite: tuple
    cartes: list
    assistant: bool = False
    rendez_vous: tuple = ()
    agendas: dict = field(default_factory=dict)
    rendez_vous_minutes: int = 0
    #: Activités ERP closes par lui ce jour (`sel.activites_closes_du_jour`) : comptées dans `compte`
    #: et jugées faites sur leur ligne de plan (`sel.ligne_faite`), d'une seule lecture.
    closes: tuple = ()
    #: Le jour est-il un jour court DIT (`Preference.jours_courts`) : le bilan le dit (textes.md §4.3).
    jour_court: bool = False

    @property
    def reglages(self):
        return self.journee.reglages

    @property
    def plan(self):
        return self.journee.plan


def _cartes_ouvertes(user, jour):
    """Cartes à réponse d'écran encore ouvertes au jour `jour`, la carte `retour` du jour même répondue (elle dit
    la « Reprise ») et les cartes de conseil RÉPONDUES ce jour (`TYPES_CONSEIL`, R3-005 : elles éteignent le conseil
    du jour) — une requête. Seules les non répondues sont jamais servies."""
    debut, fin = sel.bornes_du_jour(jour)
    vivantes = Q(expire_le__isnull=True) | Q(expire_le__gte=jour)
    repondue_ce_jour = Q(type__in=TYPES_CONSEIL, repondu_le__gte=debut, repondu_le__lt=fin)
    return list(IncitationCoach.objects.filter(
        company_id=user.company_id, proprietaire=user, canal=CanalIncitation.ECRAN, jour__lte=jour)
        .filter(vivantes).filter(Q(reponse='') | Q(jour=jour, type=TypeIncitationEcran.RETOUR) | repondue_ce_jour)
        .order_by('jour', 'pk'))


def conseil_deja_donne(ctx):
    """Une carte de conseil (`TYPES_CONSEIL`) a-t-elle été répondue AUJOURD'HUI ? (R3-005, choix C-17)."""
    debut, fin = sel.bornes_du_jour(ctx.jour)
    return any(c.type in TYPES_CONSEIL and c.repondu_le is not None and debut <= c.repondu_le < fin
               for c in ctx.cartes)


def _jour_court(preferences, jour):
    return jour.weekday() in service_rythme.jours_courts(preferences.get(ClePreference.JOURS_COURTS))


def objectif_du_jour(reglages, jour, preferences, plan=None):
    """Forme OBJECTIF `{nb, source, mode, zone}` du jour `jour` — la SEULE servie : `aujourdhui/`,
    `journee/proposition/`, « Garder ces N », le bilan et la nuit. `nb` vient de LA règle
    (`services.rythme.objectif_du_jour`, celle de l'en-tête du Copilote et d'un objectif dit) : un jour
    court vaut `max(1, N − 1)` (regles.md §6.3). `preferences` : `sel.preferences_de`, déjà lues.
    `plan` : le `PlanJour` du jour déjà lu ; VALIDÉ, il fixe le nombre du jour
    (`services.rythme.objectif_du_plan_valide`, regles.md §6.5 point 6)."""
    forme = sel.objectif_en_vigueur(reglages)
    fixe = service_rythme.objectif_du_plan_valide(plan)
    if fixe is not None:
        forme['nb'] = fixe
        return forme
    courts = service_rythme.jours_courts(preferences.get(ClePreference.JOURS_COURTS))
    forme['nb'] = service_rythme.objectif_du_jour(sel.etat_rythme(reglages), jour, courts)
    return forme


def _lire_contexte(user, jour, maintenant, *, assistant=False, cache_seul=False):
    """Lit la journée, les obligations, l'objectif, la capacité et les cartes de `user`. `cache_seul`
    (le balayage) : les agendas externes ne sont lus que du cache, jamais du réseau."""
    reglages = sel.reglages_de(user)
    travailles = sel.travailles_autour(user, jour)
    journee = sel.lire_journee(user, jour, charger=charger_items, reglages=reglages, travailles=travailles)
    obligations = sel.obligations_du_jour(user, jour) if journee.erp else sel.Obligations()
    preferences = sel.preferences_de(user)
    closes = tuple(sel.activites_closes_du_jour(user, jour))
    compte, detail = sel.compte_faites(user, jour, closes)
    capacite = sel.capacite_du_jour(user, jour, reglages, preferences, travailles)
    rendez_vous, agendas = sel.rendez_vous_pour(user, jour, jour, cache_seul=cache_seul)
    return Contexte(user=user, jour=jour, maintenant=maintenant, journee=journee, obligations=obligations,
                    preferences=preferences, objectif=objectif_du_jour(reglages, jour, preferences, journee.plan),
                    compte=compte,
                    detail=detail, capacite=capacite, cartes=_cartes_ouvertes(user, jour), assistant=assistant,
                    rendez_vous=rendez_vous, agendas=agendas,
                    rendez_vous_minutes=sel.minutes_de_rendez_vous(user, jour, rendez_vous), closes=closes,
                    jour_court=_jour_court(preferences, jour))


def _gardees_ouvertes(ctx):
    """Tâches ouvertes gardées (Essentiel, Prévu, Ce soir) : le « gardées ouvertes » de N."""
    return sum(1 for cle in sel.gardes_ouverts(ctx.journee) if cle[0] == TACHE)


def reprise(ctx):
    return any(c.type == TypeIncitationEcran.RETOUR and c.jour == ctx.jour for c in ctx.cartes)


def progression(ctx):
    return sel.progression_du_jour(ctx.journee, faites=ctx.compte, detail=ctx.detail, capacite=ctx.capacite,
                                   rendez_vous_minutes=ctx.rendez_vous_minutes, reprise=reprise(ctx),
                                   closes=ctx.closes)


def proposer(ctx, *, exclure=(), inclure=()):
    """`classement.proposer_plan` sur la journée lue (N = objectif − faites − gardées ouvertes)."""
    journee = ctx.journee
    disponible = classement.temps_disponible(ctx.capacite[0], ctx.rendez_vous_minutes)
    taches = [item for item in journee.items.values() if item.type == TACHE]
    return classement.proposer_plan(
        taches, journee.jour, journee.travailles, ctx.objectif['nb'], ctx.compte, _gardees_ouvertes(ctx),
        exclure=exclure, inclure=inclure, plan=journee.plan_pur, disponible_minutes=disponible)


# --- La carte du moment (regles.md « La carte du moment ») ---------------------------------------

def _heure_pref(preferences, cle, defaut):
    valeur = preferences.get(cle)
    if isinstance(valeur, str):
        try:
            return datetime.time.fromisoformat(valeur)
        except ValueError:
            logger.warning('taches : préférence %s illisible (%r)', cle, valeur)
    return defaut


def _gabarit(incitation):
    """(type de gabarit, clé du texte, clé des boutons) d'une carte à réponse."""
    type_, cle = incitation.type, incitation.cle
    if type_ == TypeIncitationEcran.PROPOSITION_PALIER:
        return 'carte', f'palier.{cle}', f'palier.{cle}'
    if type_ == TypeIncitationEcran.DERIVE_TENIR:
        return 'carte', f'derive.{cle}', f'derive.{cle}'
    if type_ == TypeIncitationEcran.CONSTAT:
        # C5 = information : [OK] seul (textes.md §4.2), la seule réponse que `repondre/` admet pour lui
        information = cle in service_rythme.CONSTATS_INFORMATION
        return 'constat', cle, 'constat.information' if information else 'constat'
    return 'carte', str(type_), str(type_)


def proposition(incitation, *, nom_pour=None):
    """Forme PROPOSITION d'une carte (texte et boutons des gabarits) ; None si son texte ne peut pas
    être rendu (donnée manquante : jamais un texte à trous)."""
    type_gabarit, cle_texte, cle_boutons = _gabarit(incitation)
    donnees = dict(incitation.donnees or {})
    try:
        texte = gabarits.texte(type_gabarit, cle_texte, donnees, nom_pour=nom_pour)
        boutons = gabarits.boutons(cle_boutons, donnees)
    except (KeyError, ValueError, TypeError):
        logger.warning('taches : carte %s/%s illisible', incitation.type, incitation.cle, exc_info=True)
        return None
    if not texte:
        return None
    return formes_journee.proposition_forme(incitation, texte, boutons)


def _carte(type_, *, proposition_=None, donnees=None):
    return {'type': str(type_), 'proposition': proposition_, 'donnees': dict(donnees or {})}


def _rythme_du_matin(incitation):
    """Une proposition du rythme (`TYPES_RYTHME`), ou un constat qui pose une QUESTION (C7 « Les revoir
    maintenant ? ») ; jamais un constat d'information (C5) — R3-005, choix C-17."""
    if incitation.type in TYPES_RYTHME:
        return True
    return (incitation.type == TypeIncitationEcran.CONSTAT
            and incitation.cle not in service_rythme.CONSTATS_INFORMATION)


def _carte_proposition(ctx, type_carte, types=None, *, garder=None):
    """La première carte ouverte dont le type est dans `types` (ou que `garder` retient), rendue en PROPOSITION."""
    for incitation in ctx.cartes:
        retenue = garder(incitation) if garder is not None else incitation.type in types
        if retenue and incitation.reponse == '':
            forme = proposition(incitation)
            if forme is not None:
                return _carte(type_carte, proposition_=forme)
    return None


def _carte_retour(ctx, propose):
    cartes = [c for c in ctx.cartes if c.type == TypeIncitationEcran.RETOUR and c.jour == ctx.jour]
    ouvertes = [c for c in cartes if c.reponse == '']
    forme = proposition(ouvertes[0]) if ouvertes else None
    return _carte(CarteDuMoment.RETOUR, proposition_=forme) if forme else None


def _restes_d_hier(user, hier):
    return (sel.taches_de_la_journee(user, hier).filter(statut=StatutTache.A_FAIRE)
            .filter(Q(jour_prevu=hier) | Q(echeance=hier)).exists())


def _carte_bilan_hier(ctx, propose):
    if ctx.maintenant.time() >= MIDI:
        return None
    hier = ctx.jour - datetime.timedelta(days=1)
    plan = sel.plan_du_jour(ctx.user, hier)
    if plan is not None and plan.cloture_le is not None:
        return None
    if not _restes_d_hier(ctx.user, hier):
        return None
    return _carte(CarteDuMoment.BILAN_HIER, donnees={'jour': hier.isoformat()})


def _carte_garder(ctx, propose):
    if ctx.plan is not None and ctx.plan.planifie_le is not None:
        return None
    if not propose.pour_objectif:
        return None
    return _carte(CarteDuMoment.GARDER, donnees={'n': len(propose.pour_objectif), 'objectif': ctx.objectif['nb']})


def _carte_alleger(ctx, propose):
    relance = _heure_pref(ctx.preferences, ClePreference.RELANCE_JOUR, HEURE_RELANCE_DEFAUT)
    nb = ctx.objectif['nb']
    if nb is None or ctx.maintenant.time() < relance:
        return None
    if ctx.plan is not None and ctx.plan.allege_le is not None:
        return None
    if _gardees_ouvertes(ctx) < 1 or 2 * ctx.compte >= nb:
        return None
    return _carte(CarteDuMoment.ALLEGER, donnees={'faites': ctx.compte, 'prevues': progression(ctx)['prevues']})


def _carte_faire_bilan(ctx, propose):
    soir = _heure_pref(ctx.preferences, ClePreference.HEURE_SOIR, HEURE_SOIR_DEFAUT)
    if ctx.maintenant.time() < soir:
        return None
    plan = ctx.plan
    if plan is not None and plan.cloture_le is not None:
        return None
    valide = plan is not None and plan.planifie_le is not None
    return _carte(CarteDuMoment.FAIRE_BILAN) if valide or ctx.compte >= 1 else None


def _carte_rythme(ctx, propose):
    if conseil_deja_donne(ctx):
        return None
    return _carte_proposition(ctx, CarteDuMoment.RYTHME, garder=_rythme_du_matin)


def _carte_pause(ctx, propose):
    if conseil_deja_donne(ctx):
        return None
    return _carte_proposition(ctx, CarteDuMoment.PAUSE, (TypeIncitationEcran.PAUSE,))


def _carte_revelation(ctx, propose):
    """La révélation ouverte la plus récente (I14), rendue par les textes de `serializers/rythme.py`
    (`TEXTES_REVELATION`, un seul bouton « OK ») ; dernière de l'ordre : elle ne passe jamais devant
    une autre carte (regles.md §4.10) ; rien quand un conseil a déjà été répondu aujourd'hui (R3-005)."""
    from apps.taches.serializers.rythme import TEXTES_REVELATION, forme_proposition  # la forme lit le rythme
    if conseil_deja_donne(ctx):
        return None
    ouvertes = [c for c in ctx.cartes if c.type == TypeIncitationEcran.REVELATION and c.reponse == ''
                and c.cle in TEXTES_REVELATION]
    if not ouvertes:
        return None
    return _carte(CarteDuMoment.REVELATION, proposition_=forme_proposition(ouvertes[-1], assistant=ctx.assistant))


#: Ordre de `CarteDuMoment` (regles.md §4.10).
TESTS_CARTES = (_carte_retour, _carte_bilan_hier, _carte_garder, _carte_alleger, _carte_faire_bilan,
                _carte_rythme, _carte_pause, _carte_revelation)


def _carte_du_moment(ctx, propose):
    """UNE carte au plus : la première vraie dans l'ordre (regles.md §4.10)."""
    for test in TESTS_CARTES:
        carte = test(ctx, propose)
        if carte is not None:
            return carte
    return None


# --- `aujourdhui/` ---------------------------------------------------------------------------------

def _boite_a_trier(user):
    """La boîte de réception (invariant 1) : ouvertes, sans parent, sans projet, jamais triées."""
    return taches_de(user).filter(parent__isnull=True, projet__isnull=True, triee_le__isnull=True,
                                  statut__in=sel.OUVERTS).count()


def a_trier(user, jour):
    """Compteurs de « À trier » : boîte (invariant 1), bloquées, suggestions visibles (7 jours), à
    convertir (`records.selectors.nb_a_faire_personnels`)."""
    from apps.records.selectors import nb_a_faire_personnels
    boite = _boite_a_trier(user)
    bloquees = taches_de(user).filter(statut=StatutTache.A_FAIRE).filter(sel.BLOQUEE).count()
    depuis, _ = sel.bornes_du_jour(jour - DUREE_SUGGESTION)
    suggestions = SuggestionTache.objects.filter(company_id=user.company_id, proprietaire=user,
                                                 statut=StatutSuggestion.PROPOSEE, created_at__gte=depuis).count()
    return {'boite_reception': boite, 'bloquees': bloquees, 'suggestions': suggestions,
            'a_convertir': nb_a_faire_personnels(user)}


def _entete(ctx):
    prochain = min((d for d in ctx.journee.travailles if d > ctx.jour), default=None)
    plan = ctx.plan
    return {
        'jour': ctx.jour.isoformat(),
        'maintenant': ctx.maintenant.replace(microsecond=0).isoformat(),
        'jour_ouvre': ctx.jour in ctx.journee.travailles,
        'prochain_jour_ouvre': prochain.isoformat() if prochain else None,
        'objectif': dict(ctx.objectif),
        'progression': progression(ctx),
        'plan': {'planifie_le': _instant(plan.planifie_le if plan else None),
                 'cloture_le': _instant(plan.cloture_le if plan else None),
                 'allege_le': _instant(plan.allege_le if plan else None)},
    }


def _instant(valeur):
    """Instant à l'heure locale, à la seconde (`2026-11-17T08:40:00+01:00`)."""
    if valeur is None:
        return None
    return timezone.localtime(valeur).replace(microsecond=0).isoformat()


def _rendez_vous(ctx, rendu):
    """RENDEZ_VOUS du jour (lecture seule, jamais une tâche) : horodatés à leur heure, journée entière
    signalée par `journee_entiere` (le front les range dans « Toute la journée ») ; titrés
    « Rendez-vous » sous l'en-tête assistant (forme RENDEZ_VOUS)."""
    from apps.taches.serializers.formes import RendezVousSerializer
    du_jour = [r for r in ctx.rendez_vous if sel.touche_le_jour(r, ctx.jour)]
    return list(RendezVousSerializer(du_jour, many=True, context=rendu.contexte()).data)


def _propose(ctx, rendu, plan_propose, cles_propose, *, tout):
    raisons = formes_journee.raisons_du_tour(plan_propose)
    disponible = classement.temps_disponible(ctx.capacite[0], ctx.rendez_vous_minutes)
    return {
        'replie': plan_propose.replie,
        'pour_objectif': rendu.items(cles_propose, raisons),
        'reste_nb': plan_propose.reste_nb,
        'charge': {'minutes_estimees': plan_propose.charge.get('minutes_estimees', 0),
                   'disponible_minutes': disponible, 'surcharge': bool(plan_propose.charge.get('surcharge'))},
        'suite_par_projet': formes_journee.suite_par_projet(rendu, plan_propose, raisons) if tout else None,
    }


def _forme_aujourdhui(ctx, *, tout=False):
    """Le contrat de la journée (api.md §2), clés dans l'ordre vertical."""
    journee = ctx.journee
    plan_propose = proposer(ctx)
    rendu = formes_journee.Rendu(journee, assistant=ctx.assistant, peut_cloturer=ctx.obligations.peut_cloturer,
                                 agendas=ctx.agendas)
    ordre = (SectionJournee.ESSENTIEL, SectionJournee.JOURNEE, SectionJournee.CE_SOIR)
    propose = [(TACHE, item.id) for item, _ in plan_propose.pour_objectif]
    replies = (SectionJournee.A_DECIDER, SectionJournee.EN_ATTENTE, SectionJournee.FAITES)
    listes, tronque = formes_journee.plafonner(
        [journee.sections.get(s, []) for s in ordre] + [propose] + [journee.sections.get(s, []) for s in replies])
    forme = _entete(ctx)
    forme['carte_du_moment'] = _carte_du_moment(ctx, plan_propose)
    forme['essentiel'] = rendu.items(listes[0])
    forme['obligations'] = list(ctx.obligations.lignes)
    forme['rendez_vous'] = _rendez_vous(ctx, rendu)
    forme['journee'] = rendu.items(listes[1])
    forme['ce_soir'] = rendu.items(listes[2])
    forme['propose'] = _propose(ctx, rendu, plan_propose, listes[3], tout=tout)
    forme['a_decider'] = rendu.items(listes[4])
    forme['en_attente'] = rendu.items(listes[5])
    forme['faites'] = rendu.items(listes[6])
    forme['a_trier'] = a_trier(ctx.user, ctx.jour)
    forme['tronque'] = tronque
    return forme


def aujourdhui(user, jour, maintenant, *, tout=False, assistant=False):
    """GET aujourdhui/ : la journée de `user` (jour `jour`, heure murale `maintenant`)."""
    return _forme_aujourdhui(_lire_contexte(user, jour, maintenant, assistant=assistant), tout=tout)


def badge(user, jour):
    """GET badge/ : `{n, jour, a_trier}` — `n` par `compter_journee`, la seule définition (invariant 11) ;
    `a_trier` = `a_trier.boite_reception` d'`aujourdhui/` (une requête de plus : la pastille de l'onglet
    « À trier » n'a plus à lire toute la journée)."""
    return {'n': sel.compter_journee(user, jour), 'jour': jour.isoformat(), 'a_trier': _boite_a_trier(user)}


# --- « Ailleurs dans l'ERP » -----------------------------------------------------------------------

def _file_commerciale(user):
    if not user.has_erp_permission('crm_voir'):
        return []
    from apps.crm.selectors import ma_file_commercial_items
    return ma_file_commercial_items(user.company, user)


def _affectations_chantiers(user):
    from apps.installations.selectors import affectations_pour
    return affectations_pour(user)


def _affectations_sav(user):
    from apps.sav.selectors import affectations_pour
    return affectations_pour(user)


SOURCES_AILLEURS = (('crm', _file_commerciale), ('installations', _affectations_chantiers),
                    ('sav', _affectations_sav))


def _items_ailleurs(user):
    """Items des files publiques : `crm.selectors.ma_file_commercial_items` (si `crm_voir`), puis
    `affectations_pour` d'`installations` et de `sav` — une source en échec ne compte rien."""
    items = []
    for nom, lire in SOURCES_AILLEURS:
        try:
            items.extend(lire(user))
        except Exception:  # noqa: BLE001 — une source ERP en échec ne casse jamais la journée
            logger.warning('taches : source %s illisible pour « Ailleurs »', nom, exc_info=True)
    return items


def _mentions(user):
    """Mentions non lues (`notifications.selectors.mentions_non_lues`, la porte que lit `ma_file`) ;
    `None` si la source est illisible (famille absente, jamais un 0 inventé)."""
    from apps.notifications.selectors import mentions_non_lues
    try:
        return mentions_non_lues(user, user.company).count()
    except Exception:  # noqa: BLE001 — une source ERP en échec ne casse jamais la journée
        logger.warning('taches : mentions illisibles pour « Ailleurs »', exc_info=True)
        return None


def ailleurs(user):
    """GET aujourdhui/ailleurs/ : compteurs par famille (forme `ailleurs.json`). Les approbations
    (bloc 2 de `ma_file`) n'ont AUCUNE porte publique (`reporting.approbations` n'expose que des
    internes) : la famille est ABSENTE de la réponse, jamais un compteur inventé à 0."""
    kinds = [item.get('kind') for item in _items_ailleurs(user)]
    compteurs = {cle: kinds.count(kind) for cle, kind in KINDS_AILLEURS.items()}
    mentions = _mentions(user)
    if mentions is not None:
        compteurs['mentions'] = mentions
    return {**compteurs, 'lien': LIEN_AILLEURS}


# --- `vu/` : ouverture du jour, carte de retour (regles.md « Retour d'absence ») -----------------

def _derniere_ouverture(user, jour):
    return (PlanJour.objects.filter(company_id=user.company_id, proprietaire=user, jour__lt=jour,
                                    app_ouverte_le__isnull=False)
            .order_by('-jour').values_list('jour', flat=True).first())


def _fin_de_conge(preferences, derniere, jour):
    for periode in preferences.get(ClePreference.CONGES) or ():
        try:
            au = datetime.date.fromisoformat((periode or {}).get('au'))
        except (TypeError, ValueError, AttributeError):
            continue
        if au < jour and (derniere is None or derniere <= au):
            return True
    return False


def _est_un_retour(user, jour, derniere, preferences):
    if _fin_de_conge(preferences, derniere, jour):
        return True
    if derniere is None or (jour - derniere).days < 2:
        return False
    entre = jours_travailles_de(user, derniere + datetime.timedelta(days=1), jour - datetime.timedelta(days=1))
    return len(entre) >= RETOUR_JOURS_TRAVAILLES


def _carte_retour_creee(user, jour, derniere, maintenant):
    """Crée la carte `retour` du jour (une fois : `taches_incit_uniq`) si des tâches attendaient ; ses
    `donnees.ids` sont ces tâches (« Les remettre dans Proposé » les lit, `services.rythme`)."""
    debut = (derniere or jour) + datetime.timedelta(days=1)
    ids = list(sel.taches_de_la_journee(user, jour)
               .filter(statut=StatutTache.A_FAIRE, jour_prevu__gte=debut, jour_prevu__lt=jour)
               .order_by('pk').values_list('pk', flat=True))
    if not ids:
        return
    jours = (jour - derniere).days if derniere is not None else 0
    IncitationCoach.objects.get_or_create(
        company_id=user.company_id, proprietaire=user, type=TypeIncitationEcran.RETOUR, jour=jour, cle='',
        defaults={'canal': CanalIncitation.ECRAN, 'donnees': {'jours': jours, 'taches': len(ids), 'ids': ids},
                  'montre_le': maintenant, 'expire_le': jour + DUREE_CARTE_RETOUR})


def vu(user, jour, maintenant):
    """POST vu/ : pose `app_ouverte_le`, marque ouverts les push du jour, crée la carte de retour ;
    RIEN sans `ReglagesRythme` (invariant 29). Rend la carte de retour du jour (ou nulle)."""
    if sel.reglages_de(user) is None:
        return {'carte_du_moment': None}
    preferences = sel.preferences_de(user)
    with transaction.atomic():
        derniere = _derniere_ouverture(user, jour)
        plan, _ = PlanJour.objects.get_or_create(company_id=user.company_id, proprietaire=user, jour=jour)
        if plan.app_ouverte_le is None:
            plan.app_ouverte_le = maintenant
            plan.save(update_fields=['app_ouverte_le', 'updated_at'])
        IncitationCoach.objects.filter(company_id=user.company_id, proprietaire=user, jour=jour,
                                       canal=CanalIncitation.PUSH, ouvert_le__isnull=True) \
            .update(ouvert_le=maintenant)
        if _est_un_retour(user, jour, derniere, preferences):
            _carte_retour_creee(user, jour, derniere, maintenant)
    ouverte = IncitationCoach.objects.filter(
        company_id=user.company_id, proprietaire=user, type=TypeIncitationEcran.RETOUR, jour=jour,
        reponse='').first()
    forme = proposition(ouverte) if ouverte is not None else None
    return {'carte_du_moment': _carte(CarteDuMoment.RETOUR, proposition_=forme) if forme else None}


# --- `journee/proposition/` (regles.md « Pool de Proposé », TCH57) --------------------------------

def proposition_du_jour(user, jour, maintenant, *, exclure=(), inclure=(), tout=False, assistant=False):
    """GET journee/proposition/ : Proposé par projets, sans écriture ; un id étranger dans
    `exclure`/`inclure` est simplement ignoré (invariant 9, exception de lecture)."""
    ctx = _lire_contexte(user, jour, maintenant, assistant=assistant)
    plan_propose = proposer(ctx, exclure=exclure, inclure=inclure)
    rendu = formes_journee.Rendu(ctx.journee, assistant=assistant, peut_cloturer=ctx.obligations.peut_cloturer)
    raisons = formes_journee.raisons_du_tour(plan_propose)
    cles = [(TACHE, item.id) for item, _ in plan_propose.pour_objectif]
    lignes = [{'item': forme, 'deja_prevue': ctx.journee.items[cle].jour_prevu is not None, 'cochee': True}
              for cle, forme in zip(cles, rendu.items(cles, raisons))]
    rythme = _carte_proposition(ctx, CarteDuMoment.RYTHME, garder=_rythme_du_matin)
    capacite, source = ctx.capacite
    return {
        'jour': jour.isoformat(), 'objectif': dict(ctx.objectif),
        'capacite': {'minutes': capacite, 'source': source, 'rendez_vous_minutes': ctx.rendez_vous_minutes,
                     'disponible_minutes': classement.temps_disponible(capacite, ctx.rendez_vous_minutes)},
        'a_decider': rendu.items(ctx.journee.sections.get(SectionJournee.A_DECIDER, [])),
        'proposition': lignes, 'charge': dict(plan_propose.charge),
        'rythme': rythme['proposition'] if rythme else None,
        'suite_par_projet': formes_journee.suite_par_projet(rendu, plan_propose, raisons) if tout else None,
    }


# --- Le plan du jour : « Garder ces N » et ★ (regles.md « Garder ces N », TCH57) -----------------

MESSAGE_ESSENTIELS = '3 au plus.'
MESSAGE_MODE = 'Valeur inconnue.'
MODE_EXPRESS = 'express'


class Refus(Exception):
    """Corps refusé : `erreurs` = {champ: [message]} (la vue répond 400)."""

    def __init__(self, erreurs):
        super().__init__(erreurs)
        self.erreurs = erreurs


class RefusEtat(Refus):
    """Refus d'ÉTAT : le corps est bien formé, c'est l'état (l'heure, les ★ déjà posées) qui s'y oppose — la vue
    répond 409, même corps `{champ: [message]}` (api-fuzz r2 : un 400 sur un corps conforme au schéma)."""


def _plan_verrouille(user, jour, ops):
    """Le `PlanJour` du jour sous verrou (créé si absent : une opération de création)."""
    plan, cree = PlanJour.objects.get_or_create(company_id=user.company_id, proprietaire=user, jour=jour)
    plan = PlanJour.objects.select_for_update().get(pk=plan.pk)
    if cree:
        ops.append(op_creation('plan_jour', plan))
    return plan, cree


def _valider_plan(plan, cree, maintenant, objectif, ops):
    """Première validation : `planifie_le` = maintenant, `objectif_du_jour` = l'objectif en vigueur."""
    if plan.planifie_le is not None:
        return
    avant = {'planifie_le': plan.planifie_le, 'objectif_du_jour': plan.objectif_du_jour}
    plan.planifie_le = maintenant
    plan.objectif_du_jour = objectif if objectif is not None else plan.objectif_du_jour
    plan.save(update_fields=['planifie_le', 'objectif_du_jour', 'updated_at'])
    if not cree:
        ops.extend(op_champ('plan_jour', plan, champ, valeur) for champ, valeur in avant.items()
                   if getattr(plan, champ) != valeur)


def _taches_du_compte(user, ids):
    """Les tâches `ids` de `user` ; 404 si une seule n'est pas à lui (invariant 9)."""
    ids = set(ids)
    taches = {t.pk: t for t in taches_de(user).filter(pk__in=ids)}
    if set(taches) != ids:
        raise Http404('Introuvable.')
    return taches


def _activites_du_compte(user, ids, jour):
    """Les activités ERP ouvertes `ids` de `user` (`activites_ouvertes_pour`) ; 404 sinon."""
    ids = set(ids)
    if not ids:
        return set()
    from apps.records.selectors import activites_ouvertes_pour
    trouvees = set(activites_ouvertes_pour(user, jusquau=jour).filter(pk__in=ids).values_list('pk', flat=True))
    if trouvees != ids:
        raise Http404('Introuvable.')
    return trouvees


def _poser_au_jour(user, taches, jour, ops):
    """`planifier(J)` pour chaque tâche gardée qui n'est pas déjà du jour (report compté selon
    l'invariant 4 : 0 pour un premier jour posé)."""
    for tache in taches.values():
        if tache.jour_prevu == jour or tache.echeance == jour:
            continue
        planifier(tache, acteur=user, jour_prevu=jour, collecte=ops)


def _lignes_du_plan(user, plan, cles, essentielles, ops):
    """Une ligne `prevue_au_plan` par clé sans ligne (revalider n'ajoute que des lignes, invariant
    18) ; ★ posées sur les tâches `essentielles`."""
    existantes = {(TACHE, lig.tache_id) if lig.tache_id else (ACTIVITE, lig.activite_id): lig
                  for lig in plan.ligneplanjour_set.all()}
    for cle in cles:
        type_, pk = cle
        if cle in existantes:
            ligne = existantes[cle]
            if type_ == TACHE and pk in essentielles and not ligne.essentielle:
                remplacer_ligne(ligne, ops, essentielle=True)
            continue
        champs = {'tache_id': pk} if type_ == TACHE else {'activite_id': pk}
        creer_ligne(plan, ops, prevue_au_plan=True, essentielle=type_ == TACHE and pk in essentielles, **champs)


def _verifier_essentiels(plan, essentielles, champ='essentielles'):
    """« 3 au plus. » sur les ★ qui comptent (`sel.ESSENTIELLE_VIVANTE` : tâche vivante, non abandonnée)."""
    deja = set(plan.ligneplanjour_set.filter(sel.ESSENTIELLE_VIVANTE).values_list('tache_id', flat=True))
    if len(deja | set(essentielles)) > classement.ESSENTIELS_MAX:
        raise RefusEtat({champ: [MESSAGE_ESSENTIELS]})


def planifier_express(user, jour, maintenant, *, lignes, essentielles=(), mode=MODE_EXPRESS, assistant=False):
    """POST journee/planifier/ (« Garder ces N », seul mode `express`, A17-T2) → journee_ecrite."""
    if mode != MODE_EXPRESS:
        raise Refus({'mode': [MESSAGE_MODE]})
    ids_taches = [ligne['id'] for ligne in lignes if ligne['type'] == TACHE]
    ids_activites = [ligne['id'] for ligne in lignes if ligne['type'] == ACTIVITE]
    with transaction.atomic():
        taches = _taches_du_compte(user, set(ids_taches) | set(essentielles))
        _activites_du_compte(user, ids_activites, jour)
        ops = []
        plan, cree = _plan_verrouille(user, jour, ops)
        _verifier_essentiels(plan, essentielles)
        _poser_au_jour(user, {pk: taches[pk] for pk in ids_taches}, jour, ops)
        _valider_plan(plan, cree, maintenant,
                      objectif_du_jour(sel.reglages_de(user), jour, sel.preferences_de(user))['nb'], ops)
        journee = sel.lire_journee(user, jour)
        cles = list(dict.fromkeys(sel.gardes_ouverts(journee) + [(TACHE, pk) for pk in ids_taches]
                                  + [(ACTIVITE, pk) for pk in ids_activites]
                                  + [(TACHE, pk) for pk in essentielles]))
        _lignes_du_plan(user, plan, cles, set(essentielles), ops)
        geste = enregistrer_geste(user, 'plan_du_jour', f'{len(lignes)} gardées', ops)
    return {'aujourdhui': aujourdhui(user, jour, maintenant, assistant=assistant), 'renvoyees': [],
            'geste_id': geste.pk}


def marquer_essentielle(user, tache_id, essentielle, maintenant):
    """POST journee/essentiel/ (★) : ligne `essentielle` du plan de J (`prevue_au_plan` = vrai tant que
    le plan n'est pas validé) ; 4e ★ → 400 « 3 au plus. »."""
    jour = maintenant.date()
    with transaction.atomic():
        tache = _taches_du_compte(user, [tache_id])[tache_id]
        ops = []
        plan, _cree = _plan_verrouille(user, jour, ops)
        ligne = plan.ligneplanjour_set.filter(tache_id=tache.pk).first()
        if essentielle:
            _verifier_essentiels(plan, [tache.pk], champ='essentielle')
        if ligne is not None and ligne.essentielle != essentielle:
            remplacer_ligne(ligne, ops, essentielle=essentielle)
        elif ligne is None and essentielle:
            creer_ligne(plan, ops, tache_id=tache.pk, essentielle=True, prevue_au_plan=plan.planifie_le is None)
        geste = enregistrer_geste(user, 'essentiel', 'Essentielle', ops) if ops else None
    tache = charger_taches(taches_de(user).filter(pk=tache.pk)).get()
    return tache_ecrite(tache, progression=sel.progression_courante(user, jour),
                        geste_id=geste.pk if geste else None)


# --- « Alléger ma journée » (regles.md « Alléger ma journée », TCH58) ------------------------------

def _a_renvoyer(user, jour, garder):
    """Tâches ouvertes à `jour_prevu` = J, sans échéance ≤ J, que l'on ne garde pas."""
    return list(taches_de(user).select_for_update().filter(statut=StatutTache.A_FAIRE, jour_prevu=jour)
                .exclude(pk__in=garder).filter(Q(echeance__isnull=True) | Q(echeance__gt=jour)))


def alleger(user, jour, maintenant, *, garder, assistant=False):
    """POST journee/alleger/ : le reste retourne à ses projets SANS report (`compter_report=False`),
    ses lignes de plan (essentielles comprises) sont retirées, `allege_le` posé → Proposé replié et
    vide jusqu'au lendemain. Un seul geste « allegement » annulable."""
    with transaction.atomic():
        _taches_du_compte(user, garder)
        ops = []
        plan, cree = _plan_verrouille(user, jour, ops)
        renvoyees = _a_renvoyer(user, jour, garder)
        for tache in renvoyees:
            planifier(tache, acteur=user, jour_prevu=None, compter_report=False, collecte=ops)
        ids = {t.pk for t in renvoyees}
        for ligne in plan.ligneplanjour_set.filter(tache_id__in=ids):
            ops.append(op_suppression_dure('ligne_plan_jour', ligne, valeurs_ligne(ligne)))
            ligne.delete()
        avant = plan.allege_le
        plan.allege_le = maintenant
        plan.save(update_fields=['allege_le', 'updated_at'])
        if not cree:
            ops.append(op_champ('plan_jour', plan, 'allege_le', avant))
        geste = enregistrer_geste(user, 'allegement', f'{len(ids)} retournées aux projets', ops)
    return {'aujourdhui': aujourdhui(user, jour, maintenant, assistant=assistant),
            'renvoyees': sorted(ids), 'geste_id': geste.pk}


# --- Bilan du soir (regles.md « Bilan du soir », TCH58) --------------------------------------------

MESSAGE_BILAN_FERME = "Le bilan d'hier n'est plus modifiable après midi."
MESSAGE_CHOIX = 'Valeur inconnue.'
CHOIX_BILAN = (Decision.PROCHAIN_JOUR_OUVRE, Decision.JOUR, Decision.UN_JOUR, Decision.ABANDONNER)


def _possible_jusqua(jour):
    """Le bilan d'un jour reste possible jusqu'au lendemain midi (heure murale)."""
    return timezone.make_aware(datetime.datetime.combine(jour + datetime.timedelta(days=1), MIDI))


def _verifier_jour_du_bilan(jour, maintenant):
    """J, ou J − 1 jusqu'à midi ; sinon 400 au champ `jour`."""
    if jour > maintenant.date() or maintenant >= _possible_jusqua(jour):
        raise RefusEtat({'jour': [MESSAGE_BILAN_FERME]})


def _bilan_chiffres(ctx, prog):
    objectif = ctx.plan.objectif_du_jour if ctx.plan and ctx.plan.objectif_du_jour else ctx.objectif['nb']
    mode = ctx.objectif['mode']
    variables = {'mode': mode, 'faites': ctx.compte, 'objectif': objectif, 'ef': prog['essentiel_faites'],
                 'ep': prog['essentiel_prevues'], 'jour_court': ctx.jour_court and objectif is not None}
    if ctx.objectif['zone']:
        variables['bas'], variables['haut'] = ctx.objectif['zone']
    # R3-001 : `texte_gardees` reste une clé du contrat, toujours vide (plus de « x des y gardées »)
    return {'faites': ctx.compte, 'objectif': objectif,
            'objectif_atteint': bool(sel.objectif_atteint(ctx.compte, objectif)),
            'essentiel_faites': prog['essentiel_faites'], 'essentiel_prevues': prog['essentiel_prevues'],
            'plan_tenues': prog['plan_tenues'], 'plan_lignes': prog['plan_lignes'],
            'texte': gabarits.texte('bilan', 'texte', variables), 'texte_gardees': ''}


def _restes_et_a_trancher(journee):
    """(restes, à trancher) : tâches ouvertes d'Essentiel, Prévu, Ce soir ; reportées 3 fois du jour."""
    restes = [cle for cle in sel.gardes_ouverts(journee) if cle[0] == TACHE]
    a_trancher = [cle for cle in journee.sections.get(SectionJournee.A_DECIDER, ())
                  if cle[0] == TACHE and journee.items[cle].jour_prevu == journee.jour
                  and journee.placements[cle].code == MotifRevoir.REPORTEE_3_FOIS]
    return restes, a_trancher


def cloture(user, jour, maintenant, *, assistant=False):
    """GET journee/cloture/ : faites, restes, à trancher (marquées, jamais refusées), activités ERP à
    clore à part, bilan en deux lignes, UN constat au plus."""
    _verifier_jour_du_bilan(jour, maintenant)
    ctx = _lire_contexte(user, jour, maintenant, assistant=assistant)
    journee, prog = ctx.journee, progression(ctx)
    rendu = formes_journee.Rendu(journee, assistant=assistant, peut_cloturer=ctx.obligations.peut_cloturer)
    restes, a_trancher = _restes_et_a_trancher(journee)
    activites = [cle for cle in sel.gardes_ouverts(journee) if cle[0] == ACTIVITE]
    constat = _carte_proposition(ctx, CarteDuMoment.RYTHME, (TypeIncitationEcran.CONSTAT,))
    prochain = min((d for d in journee.travailles if d > jour), default=None)
    return {
        'jour': jour.isoformat(), 'faites': rendu.items(journee.sections.get(SectionJournee.FAITES, [])),
        'restes': rendu.items(restes), 'a_trancher': rendu.items(a_trancher),
        'prochain_jour_ouvre': prochain.isoformat() if prochain else None,
        'bilan': _bilan_chiffres(ctx, prog), 'constat': constat['proposition'] if constat else None,
        'activites_a_clore': rendu.items(activites),
        'possible_jusqua': _possible_jusqua(jour).isoformat(),
    }


def _abandonner(user, tache, maintenant, ops):
    """`abandonner` : statut `annule` + `annule_le` (invariant 16), rappels annulés (invariant 19)."""
    avant = {'statut': tache.statut, 'annule_le': tache.annule_le, 'triee_le': tache.triee_le}
    tache.statut, tache.annule_le = StatutTache.ANNULE, maintenant
    tache.triee_le = tache.triee_le or maintenant
    tache.save(update_fields=['statut', 'annule_le', 'triee_le', 'updated_at'])
    ops.extend(op_champ('tache', tache, champ, valeur) for champ, valeur in avant.items()
               if getattr(tache, champ) != valeur)
    annuler_rappels(tache, collecte=ops)


def _appliquer_choix(user, tache, choix, maintenant, prochain, ops):
    decision = choix['choix']
    if decision == Decision.ABANDONNER:
        return _abandonner(user, tache, maintenant, ops)
    if decision == Decision.UN_JOUR:
        planifier(tache, acteur=user, jour_prevu=None, quelque_jour=True, collecte=ops)
    else:
        jour = choix.get('jour') if decision == Decision.JOUR else prochain
        if jour is None:
            raise Refus({'choix': [MESSAGE_CHOIX]})
        planifier(tache, acteur=user, jour_prevu=jour, collecte=ops)
    return True


def _choix_du_bilan(user, jour, choix, le_reste):
    """{tâche: choix} : les choix nommés (tâches du compte, sinon 404), puis « Tout reporter » sur les
    restes non nommés ; une reportée 3 fois non nommée reste à sa place."""
    if any(c.get('choix') not in CHOIX_BILAN for c in choix):
        raise Refus({'choix': [MESSAGE_CHOIX]})
    taches = _taches_du_compte(user, [c['id'] for c in choix])
    plan_choix = {c['id']: c for c in choix}
    if le_reste:
        restes, _a_trancher = _restes_et_a_trancher(sel.lire_journee(user, jour))
        for _type, pk in restes:
            plan_choix.setdefault(pk, {'id': pk, 'choix': Decision.PROCHAIN_JOUR_OUVRE})
        taches.update(_taches_du_compte(user, [pk for pk in plan_choix if pk not in taches]))
    return [(taches[pk], c) for pk, c in plan_choix.items()]


def _marquer_reportees(plan, ids, ops):
    for ligne in plan.ligneplanjour_set.filter(tache_id__in=ids, reportee=False):
        remplacer_ligne(ligne, ops, reportee=True)


def cloturer(user, jour, maintenant, *, choix=(), le_reste=False, reflexion=''):
    """POST journee/cloturer/ : choix par reste (reports comptés, invariant 4), lignes `reportee`,
    `cloture_le` et `reflexion` ; un geste « bilan_du_soir » annulable."""
    _verifier_jour_du_bilan(jour, maintenant)
    prochain = prochain_jour_travaille(user, jour)
    with transaction.atomic():
        a_traiter = _choix_du_bilan(user, jour, list(choix), le_reste)
        ops = []
        plan, cree = _plan_verrouille(user, jour, ops)
        reportees = [tache.pk for tache, c in a_traiter
                     if _appliquer_choix(user, tache, c, maintenant, prochain, ops)]
        _marquer_reportees(plan, reportees, ops)
        avant = {'cloture_le': plan.cloture_le, 'reflexion': plan.reflexion}
        plan.cloture_le, plan.reflexion = maintenant, (reflexion or '')[:280]
        plan.save(update_fields=['cloture_le', 'reflexion', 'updated_at'])
        if not cree:
            ops.extend(op_champ('plan_jour', plan, champ, valeur) for champ, valeur in avant.items()
                       if getattr(plan, champ) != valeur)
        geste = enregistrer_geste(user, 'bilan_du_soir', 'Bilan enregistré', ops)
    return {'plan': {'jour': jour.isoformat(), 'cloture_le': _instant(plan.cloture_le)}, 'geste_id': geste.pk}


# --- Passage à minuit : la nuit clôt la veille (regles.md « Passage à minuit », TCH58) -------------

def _en_conge(preferences, jour):
    for periode in preferences.get(ClePreference.CONGES) or ():
        try:
            du = datetime.date.fromisoformat((periode or {}).get('du'))
            au = datetime.date.fromisoformat((periode or {}).get('au'))
        except (TypeError, ValueError, AttributeError):
            continue
        if du <= jour <= au:
            return True
    return False


def _minutes_faites(user, jour):
    debut, fin = sel.bornes_du_jour(jour)
    lignes = (taches_de(user).filter(statut=StatutTache.FAIT, fait_le__gte=debut, fait_le__lt=fin,
                                     parent__isnull=True)
              .values_list('duree_reelle_minutes', 'estimation_minutes'))
    return sum((reelle if reelle is not None else (estimee or 0)) for reelle, estimee in lignes)


def _clore_pour(user, hier):
    """Statut et compteurs du `PlanJour` d'hier de `user` — recalcul déterministe, tâches intactes."""
    preferences = sel.preferences_de(user)
    journee = sel.lire_journee(user, hier)
    closes = sel.activites_closes_du_jour(user, hier)
    compte, detail = sel.compte_faites(user, hier, closes)
    capacite = sel.capacite_du_jour(user, hier, journee.reglages, preferences, journee.travailles)
    prog = sel.progression_du_jour(journee, faites=compte, detail=detail, capacite=capacite, closes=closes)
    conge = _en_conge(preferences, hier)
    plan, _cree = PlanJour.objects.get_or_create(company_id=user.company_id, proprietaire=user, jour=hier)
    if journee.reglages is None or journee.reglages.comprendre_mon_rythme:
        # Revue F2 tour 2 #6 : « Comprendre mon rythme » coupé, plus rien n'est calculé ni gardé sur son
        # rythme (donnees.md §8) : ni `statut_jour` ni `compte_rythme` (`micro_comptees` et
        # `taille_mediane_min` ne sont écrits nulle part ici). Le bilan du jour, lui, reste écrit.
        plan.statut_jour = statut_jour(ouvre=hier in journee.travailles or conge, conge=conge, compte=compte,
                                       plan=plan.planifie_le is not None, app=plan.app_ouverte_le is not None)
        plan.compte_rythme = compte
    if plan.objectif_du_jour is None and hier in journee.travailles:
        # Revue F2 tour 2 #4 : tout jour travaillé jugé porte SON objectif (jour court compris), pas
        # seulement ceux où « Garder ces N » l'a posé ; un objectif déjà posé n'est jamais réécrit.
        plan.objectif_du_jour = objectif_du_jour(journee.reglages, hier, preferences)['nb']
    plan.essentiels_choisis, plan.essentiels_faits = prog['essentiel_prevues'], prog['essentiel_faites']
    plan.plan_prevues, plan.plan_faites = prog['plan_lignes'], prog['plan_tenues']
    plan.minutes_prevues, plan.minutes_faites = prog['minutes_prevues'], _minutes_faites(user, hier)
    plan.capacite_minutes, plan.capacite_source = capacite
    plan.save()


def clore_jour_precedent(company_id, jour):
    """Nuit du `jour` : clôt le `PlanJour` de la veille (statut du jour, compteurs) de chaque compte
    actif qui a des `ReglagesRythme` (invariant 29), sans toucher aux tâches (regles.md « Passage à
    minuit »). Rejouer la nuit ne change rien de plus. Appelée par `nocturne.executer` (TCH37)."""
    hier = jour - datetime.timedelta(days=1)
    reglages = (ReglagesRythme.objects.filter(company_id=company_id, proprietaire__is_active=True)
                .select_related('proprietaire', 'proprietaire__company'))
    for ligne in reglages:
        # Revue F2 #2 : un compte en échec (savepoint défait) n'arrête pas les autres ; journal sans donnée
        # personnelle (id du compte et classe de l'erreur).
        try:
            with transaction.atomic():
                _clore_pour(ligne.proprietaire, hier)
        except Exception as erreur:  # noqa: BLE001
            logger.error('taches.nocturne : clôture de la veille en échec pour le compte %s (%s)',
                         ligne.proprietaire_id, type(erreur).__name__)
