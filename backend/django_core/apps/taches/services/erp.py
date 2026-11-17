"""Services du pont avec l'ERP (conception/spec-6a-erp.md ; reference/donnees.md invariants 23, 30).

- `lier_activite` : une tâche liée à une activité ERP OUVERTE de l'utilisateur ; la tâche garde
  `activite_origine`, l'activité n'est PAS close (invariant 30) ; 409 `deja_lie` si elle a déjà sa
  tâche (levé par `creer_taches`).
- `convertir_activites` : ses à-faire personnels deviennent des tâches, la source est close par
  `records.services.cloturer_a_faire_personnel` ; 200 partiel, une raison par refus ; UN geste.

- `reverifier_liens` (TCH75) : étape de nuit appelée par `nocturne.executer` (TCH37) : l'état et le
  libellé du lien de chaque tâche ouverte, tels que son propriétaire les voit.

Activités lues par les SEULES portes de `records` (`selectors.py`, `services.py`) ; les suggestions
arrivent avec TCH71-TCH72.
"""
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.utils import timezone

from apps.records.selectors import a_faire_personnels_de, activite_ouverte_de
from apps.records.services import cloturer_a_faire_personnel
from apps.taches.choix import CibleLiable, LienEtat, Source, StatutTache
from apps.taches.models.taches import Tache
from apps.taches.selectors.base import gestes_de
from apps.taches.selectors.liens import libelle_de_cible
from apps.taches.services.creation import creer_taches
from apps.taches.services.gestes import enregistrer_geste
from core.conflit_etat import ConflitEtat

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
    verdicts = {}
    for tache in taches:
        cle = (tache.proprietaire_id, tache.content_type_id, tache.object_id)
        if cle not in verdicts:
            cible = f'{tache.content_type.app_label}.{tache.content_type.model}'
            verdicts[cle] = _verdict(tache.proprietaire, cible, tache.object_id)
        tache.lien_etat, tache.lien_libelle = verdicts[cle]
        tache.lien_verifie_le = maintenant
    Tache.objects.bulk_update(taches, ['lien_etat', 'lien_libelle', 'lien_verifie_le'], batch_size=500)
    return len(taches)
