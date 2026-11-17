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
from django.utils import timezone

from apps.taches.choix import (
    CanalIncitation, CarteDuMoment, ClePreference, SectionJournee, StatutSuggestion, StatutTache,
    TypeIncitationEcran)
from apps.taches.models.erp import SuggestionTache
from apps.taches.models.journee import PlanJour
from apps.taches.models.rythme import IncitationCoach
from apps.taches.moteur import classement, gabarits
from apps.taches.moteur.rythme import RETOUR_JOURS_TRAVAILLES
from apps.taches.moteur.sollicitations import HEURE_RELANCE_DEFAUT, HEURE_SOIR_DEFAUT
from apps.taches.selectors import journee as sel
from apps.taches.selectors.base import jours_travailles_de, taches_de
from apps.taches.serializers import journee as formes_journee
from apps.taches.serializers.formes import charger_items

logger = logging.getLogger(__name__)

TACHE = classement.TACHE
ACTIVITE = classement.ACTIVITE
MIDI = datetime.time(12, 0)
#: Une carte `retour` reste valable une semaine (contrat `vu.json`).
DUREE_CARTE_RETOUR = datetime.timedelta(days=7)
#: Suggestions visibles 7 jours (spec-6a §3.7).
DUREE_SUGGESTION = datetime.timedelta(days=7)
TYPES_RYTHME = (TypeIncitationEcran.PROPOSITION_PALIER, TypeIncitationEcran.DERIVE_TENIR,
                TypeIncitationEcran.GARDE_TAILLE, TypeIncitationEcran.CONSTAT)
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

    @property
    def reglages(self):
        return self.journee.reglages

    @property
    def plan(self):
        return self.journee.plan


def _cartes_ouvertes(user, jour):
    """Cartes à réponse d'écran encore ouvertes au jour `jour` (et la carte `retour` du jour, même
    répondue : elle dit la « Reprise ») — une requête."""
    vivantes = Q(expire_le__isnull=True) | Q(expire_le__gte=jour)
    return list(IncitationCoach.objects.filter(
        company_id=user.company_id, proprietaire=user, canal=CanalIncitation.ECRAN, jour__lte=jour)
        .filter(vivantes).filter(Q(reponse='') | Q(jour=jour, type=TypeIncitationEcran.RETOUR))
        .order_by('jour', 'pk'))


def lire_contexte(user, jour, maintenant, *, assistant=False):
    """Lit la journée, les obligations, l'objectif, la capacité et les cartes de `user`."""
    reglages = sel.reglages_de(user)
    travailles = sel.travailles_autour(user, jour)
    journee = sel.lire_journee(user, jour, charger=charger_items, reglages=reglages, travailles=travailles)
    obligations = sel.obligations_du_jour(user, jour) if journee.erp else sel.Obligations()
    preferences = sel.preferences_de(user)
    compte, detail = sel.compte_faites(user, jour)
    capacite = sel.capacite_du_jour(user, jour, reglages, preferences, travailles)
    return Contexte(user=user, jour=jour, maintenant=maintenant, journee=journee, obligations=obligations,
                    preferences=preferences, objectif=sel.objectif_du_jour(reglages), compte=compte,
                    detail=detail, capacite=capacite, cartes=_cartes_ouvertes(user, jour), assistant=assistant)


def _gardees_ouvertes(ctx):
    """Tâches ouvertes gardées (Essentiel, Prévu, Ce soir) : le « gardées ouvertes » de N."""
    return sum(1 for cle in sel.gardes_ouverts(ctx.journee) if cle[0] == TACHE)


def reprise(ctx):
    return any(c.type == TypeIncitationEcran.RETOUR and c.jour == ctx.jour for c in ctx.cartes)


def progression(ctx):
    return sel.progression_du_jour(ctx.journee, faites=ctx.compte, detail=ctx.detail, capacite=ctx.capacite,
                                   rendez_vous_minutes=ctx.rendez_vous_minutes, reprise=reprise(ctx))


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
        return 'constat', cle, 'constat'
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


def _carte_proposition(ctx, type_carte, types):
    for incitation in ctx.cartes:
        if incitation.type in types and incitation.reponse == '':
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
    return _carte_proposition(ctx, CarteDuMoment.RYTHME, TYPES_RYTHME)


def _carte_pause(ctx, propose):
    return _carte_proposition(ctx, CarteDuMoment.PAUSE, (TypeIncitationEcran.PAUSE,))


#: Ordre de `CarteDuMoment`. `revelation` : ses textes (textes.md §2.18) n'ont pas encore de gabarit
#: (`moteur/gabarits.py`) — la carte reste absente tant qu'il manque (jamais un texte inventé).
TESTS_CARTES = (_carte_retour, _carte_bilan_hier, _carte_garder, _carte_alleger, _carte_faire_bilan,
                _carte_rythme, _carte_pause)


def carte_du_moment(ctx, propose):
    """UNE carte au plus : la première vraie dans l'ordre (regles.md §4.10)."""
    for test in TESTS_CARTES:
        carte = test(ctx, propose)
        if carte is not None:
            return carte
    return None


# --- `aujourdhui/` ---------------------------------------------------------------------------------

def a_trier(user, jour):
    """Compteurs de « À trier » : boîte (invariant 1), bloquées, suggestions visibles (7 jours), à
    convertir (`records.selectors.nb_a_faire_personnels`)."""
    from apps.records.selectors import nb_a_faire_personnels
    boite = taches_de(user).filter(parent__isnull=True, projet__isnull=True, triee_le__isnull=True,
                                   statut__in=sel.OUVERTS).count()
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
    from apps.taches.serializers.formes import RendezVousSerializer
    horodates = [r for r in ctx.rendez_vous if not r.journee_entiere]
    return list(RendezVousSerializer(horodates, many=True, context=rendu.contexte()).data)


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


def forme_aujourdhui(ctx, *, tout=False):
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
    forme['carte_du_moment'] = carte_du_moment(ctx, plan_propose)
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
    return forme_aujourdhui(lire_contexte(user, jour, maintenant, assistant=assistant), tout=tout)


def badge(user, jour):
    """GET badge/ : `{n, jour}` — `compter_journee`, la seule définition (invariant 11)."""
    return {'n': sel.compter_journee(user, jour), 'jour': jour.isoformat()}


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


def ailleurs(user):
    """GET aujourdhui/ailleurs/ : compteurs par famille (forme `ailleurs.json`). Les approbations et
    les mentions (blocs 2-3 de `ma_file`) n'ont pas de porte publique lisible d'ici : 0."""
    kinds = [item.get('kind') for item in _items_ailleurs(user)]
    compteurs = {cle: kinds.count(kind) for cle, kind in KINDS_AILLEURS.items()}
    return {**compteurs, 'approbations': 0, 'mentions': 0, 'lien': LIEN_AILLEURS}


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
    """Crée la carte `retour` du jour (une fois : `taches_incit_uniq`) si des tâches attendaient."""
    debut = (derniere or jour) + datetime.timedelta(days=1)
    attendues = (sel.taches_de_la_journee(user, jour)
                 .filter(statut=StatutTache.A_FAIRE, jour_prevu__gte=debut, jour_prevu__lt=jour).count())
    if attendues == 0:
        return
    jours = (jour - derniere).days if derniere is not None else 0
    IncitationCoach.objects.get_or_create(
        company_id=user.company_id, proprietaire=user, type=TypeIncitationEcran.RETOUR, jour=jour, cle='',
        defaults={'canal': CanalIncitation.ECRAN, 'donnees': {'jours': jours, 'taches': attendues},
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


def clore_jour_precedent(company_id, jour):
    """Nuit du `jour` : clôt le `PlanJour` de la veille (statut du jour, compteurs) sans toucher aux
    tâches (regles.md « Passage à minuit »). Livrée vide par TCH37, remplie par TCH58."""
    return None
