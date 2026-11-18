"""Services du pont avec l'ERP (conception/spec-6a-erp.md ; reference/donnees.md invariants 23, 30).

- `lier_activite` : une tâche liée à une activité ERP OUVERTE de l'utilisateur ; la tâche garde
  `activite_origine`, l'activité n'est PAS close (invariant 30) ; 409 `deja_lie` si elle a déjà sa
  tâche (levé par `creer_taches`).
- `convertir_activites` : ses à-faire personnels deviennent des tâches, la source est close par
  `records.services.cloturer_a_faire_personnel` ; 200 partiel, une raison par refus ; UN geste.

- `reverifier_liens` (TCH75) : étape de nuit appelée par `nocturne.executer` (TCH37) : l'état et le
  libellé du lien de chaque tâche ouverte, tels que son propriétaire les voit.

Activités lues par les SEULES portes de `records` (`selectors.py`, `services.py`).

- `proposer_suggestion` · `retirer_suggestion` (TCH71) : appelés par les abonnés de `receivers.py`
  (regles.md §9) ; destinataire STRICT (le responsable du lead, lu par `crm.selectors.get_company_lead`)
  et, avec `suggestions_societe`, l'administrateur, mêmes contrôles ; anti-doublon par la clé.
- `suggestions_de` · `accepter_suggestion` · `refuser_suggestion` (TCH72) : les routes `suggestions/`
  (≤ 20, < 7 jours), « Ajouter » (titre éditable, par `creer_taches`) et « Pas utile », annulables.
"""
import logging

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.utils import timezone

from apps.records.selectors import a_faire_personnels_de, activite_ouverte_de
from apps.records.services import cloturer_a_faire_personnel
from apps.taches.choix import CibleLiable, LienEtat, Source, StatutSuggestion, StatutTache
from apps.taches.models.erp import SuggestionTache
from apps.taches.models.rythme import ReglagesRythme
from apps.taches.models.taches import Tache
from apps.taches.selectors.base import gestes_de, taches_de
from apps.taches.selectors.liens import libelle_de_cible
from apps.taches.services.creation import creer_taches
from apps.taches.services.gestes import enregistrer_geste, op_champ
from core.conflit_etat import ConflitEtat

logger = logging.getLogger(__name__)

#: Raisons d'un refus de conversion (reference/api.md §4, textes.md « Refus de conversion »).
INTROUVABLE = 'introuvable'
ASSIGNEE_A_UN_COLLEGUE = 'assignee_a_un_collegue'
DEJA_CONVERTIE = 'deja_convertie'
CLOSE = 'close'
#: Au plus 200 à-faire par envoi (spec-6a §5).
PLAFOND_CONVERSION = 200
#: Titre d'un à-faire sans résumé ni note (le nom que l'ERP lui donne, textes.md « Bandeau »).
TITRE_A_FAIRE = 'À-faire personnel'
LONGUEUR_TITRE = 280
#: Tâches dont la nuit revérifie le lien (invariant 23 : « les tâches ouvertes »).
OUVERTES = (StatutTache.A_FAIRE, StatutTache.EN_ATTENTE)
#: `suggestions/` sert au plus 20 suggestions (api.md §3.2).
PLAFOND_SUGGESTIONS = 20
#: Texte du geste « Pas utile » (le libellé du bouton, textes.md §2.5 ; aucun toast dédié).
MESSAGE_PAS_UTILE = 'Pas utile'


# --- Lier une tâche à une activité ------------------------------------------------------------

def _lien_de_l_activite(user, activite):
    """(`{"cible","id"}`, libellé) de la cible de l'activité si elle est liable ET visible par
    `user` (invariant 23), sinon (None, None) : la tâche naît alors sans lien."""
    content_type = activite.content_type
    if content_type is None or activite.object_id is None:
        return None, None
    cible = f'{content_type.app_label}.{content_type.model}'
    if cible not in CibleLiable.values:
        return None, None
    libelle = libelle_de_cible(user, cible, activite.object_id)
    if libelle is None:
        return None, None
    return {'cible': cible, 'id': activite.object_id}, libelle


def lier_activite(user, *, activite_id, titre='', jour_prevu=None):
    """Crée la tâche liée à l'activité `activite_id` (ouverte, assignée à `user`) → `ResultatCreation`.

    `Http404` si l'activité n'est pas une activité ouverte de `user` (refus = introuvable) — toute
    activité ouverte, sans échéance ou reportée comprises (`records.selectors.activite_ouverte_de`) ;
    `ConflitEtat` 409 `deja_lie` si une tâche vivante la porte déjà. L'activité reste ouverte."""
    activite = activite_ouverte_de(user, activite_id)
    if activite is None:
        raise Http404('Introuvable.')
    lien, _libelle = _lien_de_l_activite(user, activite)
    ligne = {'titre': (titre or '').strip() or (activite.summary or '').strip(), 'jour_prevu': jour_prevu}
    # `creer_taches` pose le libellé du lien à la liaison (même porte `selectors/liens`).
    return creer_taches(user, [ligne], source=Source.ACTIVITE, porte='lien_activite', lien=lien,
                        activite=activite)


# --- Convertir les à-faire personnels ---------------------------------------------------------

def _raison(user, activite, deja_converties):
    """Raison du refus de convertir `activite` (None = convertible), dans l'ordre d'api.md §4."""
    if activite is None:
        return INTROUVABLE
    if activite.assigned_to_id not in (None, user.pk):
        return ASSIGNEE_A_UN_COLLEGUE
    if activite.pk in deja_converties:
        return DEJA_CONVERTIE
    if activite.done:
        return CLOSE
    return None


def _ligne_de(activite):
    """La LIGNE d'une conversion : résumé (sinon note) en titre, note en notes, échéance en jour."""
    titre = (activite.summary or '').strip() or (activite.note or '').strip().split('\n')[0].strip()
    return {'titre': (titre or TITRE_A_FAIRE)[:LONGUEUR_TITRE], 'notes': activite.note or '',
            'jour_prevu': activite.due_date}


def _candidates(user, ids, toutes):
    """(ids demandés dans l'ordre, `{id: activité}` des à-faire de `user` parmi eux)."""
    if toutes:
        ouvertes = (a_faire_personnels_de(user).filter(done=False)
                    .filter(Q(assigned_to_id=user.pk) | Q(assigned_to__isnull=True))
                    .order_by('pk')[:PLAFOND_CONVERSION])
        par_id = {activite.pk: activite for activite in ouvertes}
        return list(par_id), par_id
    demandes = list(dict.fromkeys(ids))[:PLAFOND_CONVERSION]
    return demandes, {activite.pk: activite for activite in a_faire_personnels_de(user, ids=demandes)}


def _convertir_une(user, activite):
    """La tâche née de `activite` et le geste de sa création, la source close ; `None` si une
    tâche vivante la porte déjà (course perdue) ; `ObjectDoesNotExist` si la clôture est refusée."""
    try:
        with transaction.atomic():
            resultat = creer_taches(user, [_ligne_de(activite)], source=Source.ACTIVITE,
                                    porte='conversion', activite=activite)
            cloturer_a_faire_personnel(activite, user)
    except ConflitEtat:
        return None, None
    return resultat.creees[0], resultat.geste


def _un_seul_geste(user, gestes):
    """Les gestes d'une conversion réunis en UN (un seul « Annuler ») ; `None` sans création."""
    gestes = [geste for geste in gestes if geste is not None]
    if not gestes:
        return None
    operations = [operation for geste in gestes for operation in geste.operations]
    message = gestes[0].message if len(gestes) == 1 else f'{len(gestes)} tâches créées'
    gestes_de(user).filter(pk__in=[geste.pk for geste in gestes]).delete()
    return enregistrer_geste(user, 'conversion', message, operations)


def convertir_activites(user, *, ids=(), toutes=False):
    """Convertit les à-faire personnels `ids` (ou tous les ouverts si `toutes`) de `user` →
    `{"converties": [{activite_id, tache_id}], "refusees": [{activite_id, raison}], "geste_id"}`
    (`convertir_activite.json`). Une transaction ; chaque à-faire réussit ou échoue seul."""
    demandes, par_id = _candidates(user, ids, toutes)
    deja = set(Tache.objects.filter(company_id=user.company_id, activite_origine_id__in=list(par_id))
               .values_list('activite_origine_id', flat=True))
    converties, refusees, gestes = [], [], []
    with transaction.atomic():
        for activite_id in demandes:
            activite = par_id.get(activite_id)
            raison = _raison(user, activite, deja)
            if raison is None:
                try:
                    tache, geste = _convertir_une(user, activite)
                except ObjectDoesNotExist:
                    tache, geste, raison = None, None, INTROUVABLE
                else:
                    raison = DEJA_CONVERTIE if tache is None else None
            if raison is not None:
                refusees.append({'activite_id': activite_id, 'raison': raison})
                continue
            converties.append({'activite_id': activite_id, 'tache_id': tache.pk})
            gestes.append(geste)
        geste = _un_seul_geste(user, gestes)
    return {'converties': converties, 'refusees': refusees, 'geste_id': geste.pk if geste else None}


# --- Nuit -------------------------------------------------------------------------------------

def _verdict(user, cible, object_id):
    """(`lien_etat`, libellé) d'un lien vu par son propriétaire `user` (spec-6a §3.2) : objet absent
    de la société → `introuvable` ; archivé ou supprimé → `archive` ; présent mais hors de la
    portée de `user` → `inaccessible` ; sinon `ok` et le libellé du moment. Libellé vide hors `ok`."""
    from apps.records.serializers import resolve_target

    if cible not in CibleLiable.values or getattr(user, 'company', None) is None:
        return LienEtat.INTROUVABLE, ''
    try:
        _type, objet = resolve_target(cible, object_id, user.company)
    except ValueError:  # `CibleIntrouvable` en est une sous-classe
        return LienEtat.INTROUVABLE, ''
    if getattr(objet, 'is_archived', False) or getattr(objet, 'is_deleted', False):
        return LienEtat.ARCHIVE, ''
    libelle = libelle_de_cible(user, cible, object_id)
    if libelle is None:
        return LienEtat.INACCESSIBLE, ''
    return LienEtat.OK, libelle


def reverifier_liens(company_id, jour, *, maintenant=None):
    """Nuit du `jour` : revérifie le lien ERP des tâches OUVERTES de la société (`lien_etat`,
    `lien_libelle`, `lien_verifie_le` ; invariant 23). Un lien `efface` (lead effacé) le reste. Écrit
    sans toucher `lock_version` ni `updated_at` (aucun conflit pour une fiche ouverte) → nombre de
    tâches revérifiées."""
    maintenant = maintenant or timezone.now()
    taches = list(
        Tache.objects.filter(company_id=company_id, statut__in=OUVERTES, content_type__isnull=False,
                             object_id__isnull=False)
        .exclude(lien_etat=LienEtat.EFFACE)
        .select_related('content_type', 'proprietaire', 'proprietaire__company'))
    verdicts, revues = {}, []
    for tache in taches:
        cle = (tache.proprietaire_id, tache.content_type_id, tache.object_id)
        if cle not in verdicts:
            verdicts[cle] = _verdict_isole(tache)
        if verdicts[cle] is None:
            continue  # revue F2 #2 : ce lien reste tel quel, les autres comptes sont revérifiés
        tache.lien_etat, tache.lien_libelle = verdicts[cle]
        tache.lien_verifie_le = maintenant
        revues.append(tache)
    Tache.objects.bulk_update(revues, ['lien_etat', 'lien_libelle', 'lien_verifie_le'], batch_size=500)
    return len(revues)


# --- Suggestions venues de l'ERP (TCH71, regles.md §9) ----------------------------------------

def _responsable(company_id, lead_id):
    """Id du responsable (`owner`) du lead `lead_id` de la société, lu par la porte de `crm`."""
    from apps.crm.selectors import get_company_lead
    lead = get_company_lead(company_id, lead_id)
    return getattr(lead, 'owner_id', None)


def _destinataire_admis(user, reglages, famille, cible, cible_id):
    """Conditions de regles.md §9 : compte actif interne, `taches_voir`, module actif, une
    `ReglagesRythme` (IR14), famille allumée, ET cible visible par lui (A3 ; sinon rien, sans trace)."""
    from apps.taches.auth_jeton import DROIT, MODULE, _compte_interne_actif
    from core.feature_flags import module_actif

    if reglages is None or famille not in (reglages.familles_suggestions or []):
        return False
    if not _compte_interne_actif(user) or not user.has_erp_permission(DROIT):
        return False
    if not module_actif(user.company, MODULE):
        return False
    return libelle_de_cible(user, cible, cible_id) is not None


def _destinataires(company_id, famille, lead_id, cible, cible_id):
    """Le responsable du lead (sinon personne) et les administrateurs qui ont choisi
    `suggestions_societe` ; chacun passe les mêmes contrôles."""
    from django.contrib.auth import get_user_model

    responsable = _responsable(company_id, lead_id)
    reglages = {r.proprietaire_id: r for r in ReglagesRythme.objects.filter(company_id=company_id).filter(
        Q(proprietaire_id=responsable) | Q(suggestions_societe=True))}
    ids = set(reglages) & ({responsable} | {pk for pk, r in reglages.items() if r.suggestions_societe})
    comptes = (get_user_model().objects.filter(pk__in=ids, company_id=company_id)
               .select_related('company', 'role').order_by('pk'))
    return [user for user in comptes
            if (user.pk == responsable or user.is_admin_role)
            and _destinataire_admis(user, reglages[user.pk], famille, cible, cible_id)]


def _reproposer_si_retiree(suggestion):
    """Vrai si `suggestion`, RETIRÉE PAR LE SYSTÈME (son événement a été annulé : `retirer_suggestion`), redevient
    proposée, comme neuve (visible 7 jours à compter de maintenant), parce que l'événement se reproduit (revue F4 #13,
    décision d'orchestrateur). Écriture conditionnelle sur `statut=retiree` : deux émissions qui se croisent n'en
    reproposent qu'une, et une suggestion refusée ou acceptée n'est jamais touchée."""
    maintenant = timezone.now()
    return bool(SuggestionTache.objects.filter(pk=suggestion.pk, statut=StatutSuggestion.RETIREE).update(
        statut=StatutSuggestion.PROPOSEE, decidee_le=None, tache=None, created_at=maintenant, updated_at=maintenant))


def proposer_suggestion(company_id, *, famille, cle, titre, lead_id, cible, cible_id):
    """Propose la suggestion `cle` à chaque destinataire admis → nombre de suggestions créées ou reproposées.

    Anti-doublon : `get_or_create` sur (`company`, `proprietaire`, `cle`) — contrainte
    `taches_sugg_cle_uniq`. Une suggestion existante n'est reproposée que si le SYSTÈME l'avait retirée
    (`retiree` : l'événement avait été annulé et se reproduit) ; refusée par l'utilisateur (« Pas utile »),
    acceptée (tâche créée) ou encore proposée : jamais reproposée, jamais en double (regles.md §9)."""
    app_label, modele = cible.split('.', 1)
    content_type = ContentType.objects.get_by_natural_key(app_label, modele)
    creees = 0
    for user in _destinataires(company_id, famille, lead_id, cible, cible_id):
        suggestion, creee = SuggestionTache.objects.get_or_create(
            company_id=company_id, proprietaire=user, cle=cle,
            defaults={'famille': famille, 'titre_propose': titre, 'content_type': content_type,
                      'object_id': cible_id, 'lead_ref': lead_id})
        creees += int(creee or _reproposer_si_retiree(suggestion))
    return creees


def retirer_suggestion(company_id, cle):
    """Les suggestions ENCORE proposées de la clé `cle` passent `retiree` → nombre retiré."""
    maintenant = timezone.now()
    return (SuggestionTache.objects.filter(company_id=company_id, cle=cle, statut=StatutSuggestion.PROPOSEE)
            .update(statut=StatutSuggestion.RETIREE, decidee_le=maintenant, updated_at=maintenant))


# --- Routes des suggestions (TCH72, api.md §3.2, §4) --------------------------------------------

def suggestions_de(user, jour):
    """Les suggestions PROPOSÉES de `user` nées depuis 7 jours (même borne que le compteur d'À trier),
    les plus récentes d'abord, au plus 20 (`suggestions.json`)."""
    from apps.taches.selectors.journee import bornes_du_jour
    from apps.taches.services.journee import DUREE_SUGGESTION

    depuis, _ = bornes_du_jour(jour - DUREE_SUGGESTION)
    return list(SuggestionTache.objects
                .filter(company_id=user.company_id, proprietaire=user, statut=StatutSuggestion.PROPOSEE,
                        created_at__gte=depuis)
                .select_related('content_type').order_by('-created_at', '-pk')[:PLAFOND_SUGGESTIONS])


def _suggestion_de(user, suggestion_id):
    """La suggestion `suggestion_id` de `user`, verrouillée ; `Http404` pour celle d'un autre."""
    # Sans `select_related` : FOR UPDATE refuse le côté nul d'une jointure externe (content_type).
    suggestion = (SuggestionTache.objects.select_for_update()
                  .filter(company_id=user.company_id, proprietaire=user, pk=suggestion_id).first())
    if suggestion is None:
        raise Http404('Introuvable.')
    return suggestion


def _decider(suggestion, statut, tache=None):
    """Pose la décision ; rend les opérations annulables (statut, tâche, `decidee_le`)."""
    avant = {'statut': suggestion.statut, 'tache': suggestion.tache_id, 'decidee_le': suggestion.decidee_le}
    suggestion.statut, suggestion.tache, suggestion.decidee_le = statut, tache, timezone.now()
    suggestion.save(update_fields=['statut', 'tache', 'decidee_le', 'updated_at'])
    return [op_champ('suggestion_tache', suggestion, champ, valeur) for champ, valeur in avant.items()]


def _lien_encore_a_portee(user, suggestion):
    """`{"cible","id"}` de la cible de `suggestion` si `user` la lit ENCORE (porte unique `libelle_de_cible`, droits
    du moment), sinon `None` : la tâche naît alors sans lien, comme celle d'une activité dont la cible n'est pas
    visible (`_lien_de_l_activite`). Une cible sortie de sa portée (droit retiré, objet supprimé) ne fait donc plus
    échouer « Ajouter » à chaque fois, et rien d'elle n'est servi (revue F4 #12)."""
    if suggestion.content_type_id is None or suggestion.object_id is None:
        return None
    content_type = ContentType.objects.get_for_id(suggestion.content_type_id)
    cible = f'{content_type.app_label}.{content_type.model}'
    if libelle_de_cible(user, cible, suggestion.object_id) is None:
        return None
    return {'cible': cible, 'id': suggestion.object_id}


def accepter_suggestion(user, suggestion_id, *, titre='', jour_prevu=None):
    """« Ajouter » → (id de la tâche née, geste) : `creer_taches(source='suggestion', lien=cible)` avec
    le titre édité, sinon `titre_propose` (regles.md §9) ; la suggestion passe `acceptee` dans le MÊME
    geste (« Annuler » la rend proposée). Rejeu d'une suggestion déjà acceptée : sa tâche, sans geste
    neuf. Une suggestion refusée ou retirée répond `Http404`."""
    with transaction.atomic():
        suggestion = _suggestion_de(user, suggestion_id)
        if suggestion.statut == StatutSuggestion.ACCEPTEE and taches_de(user).filter(
                pk=suggestion.tache_id).exists():
            return suggestion.tache_id, None
        if suggestion.statut != StatutSuggestion.PROPOSEE:
            raise Http404('Introuvable.')
        ligne = {'titre': (titre or '').strip() or suggestion.titre_propose, 'jour_prevu': jour_prevu}
        resultat = creer_taches(user, [ligne], source=Source.SUGGESTION, porte='suggestion',
                                lien=_lien_encore_a_portee(user, suggestion))
        tache = resultat.creees[0]
        operations = [*resultat.geste.operations, *_decider(suggestion, StatutSuggestion.ACCEPTEE, tache)]
        # UN geste (création + décision) : celui de `creer_taches` est remplacé, comme `_un_seul_geste`.
        gestes_de(user).filter(pk=resultat.geste.pk).delete()
        geste = enregistrer_geste(user, 'suggestion', resultat.geste.message, operations)
    return tache.pk, geste


def refuser_suggestion(user, suggestion_id):
    """« Pas utile » → `{"id","statut":"refusee","geste_id"}` (`suggestion_refusee.json`) ; rejeu d'une
    suggestion déjà refusée : même réponse, sans geste neuf ; acceptée ou retirée : `Http404`."""
    with transaction.atomic():
        suggestion = _suggestion_de(user, suggestion_id)
        if suggestion.statut == StatutSuggestion.REFUSEE:
            return {'id': suggestion.pk, 'statut': suggestion.statut, 'geste_id': None}
        if suggestion.statut != StatutSuggestion.PROPOSEE:
            raise Http404('Introuvable.')
        operations = _decider(suggestion, StatutSuggestion.REFUSEE)
        geste = enregistrer_geste(user, 'suggestion', MESSAGE_PAS_UTILE, operations)
    return {'id': suggestion.pk, 'statut': suggestion.statut, 'geste_id': geste.pk}


def _verdict_isole(tache):
    """`_verdict` d'une tâche, ou `None` s'il lève (journal sans donnée personnelle : ids et classe)."""
    cible = f'{tache.content_type.app_label}.{tache.content_type.model}'
    try:
        with transaction.atomic():
            return _verdict(tache.proprietaire, cible, tache.object_id)
    except Exception as erreur:  # noqa: BLE001 — un lien illisible n'arrête pas la nuit des autres comptes
        logger.error('taches.nocturne : lien de la tâche %s (compte %s) non revérifié (%s)',
                     tache.pk, tache.proprietaire_id, type(erreur).__name__)
        return None
