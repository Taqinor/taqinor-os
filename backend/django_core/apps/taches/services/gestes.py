"""Annuler côté serveur — l'UNIQUE mécanisme d'annulation (reference/donnees.md §2.15, §4, A7).

Une écriture annulable décrit ce qu'elle a fait par des OPÉRATIONS (construites par `op_champ`,
`op_creation`, `op_suppression_douce`, `op_suppression_dure`) puis les enregistre en un geste
(`enregistrer_geste`). `annuler_geste` défait ces opérations, de la dernière à la première :

- il ne lit JAMAIS un état envoyé par le navigateur (invariant 21) : seulement le geste stocké ;
- il ne restaure QUE les champs de la liste blanche du §4 (un autre champ est ignoré) ;
- « modifiée depuis » : la valeur courante n'est plus celle que le geste a écrite → l'objet va dans
  `conflits`, inchangé (200 partiel) ; un objet disparu → `conflits` aussi ;
- toute clé étrangère restaurée est revérifiée « même société ET même propriétaire » ;
- le geste d'un autre compte, ou de plus de 7 jours, répond `Http404` ; un geste déjà annulé rend
  `deja: true` sans rien toucher (idempotent).

Les champs d'un même objet sont restaurés ensemble : un seul conflit suffit à laisser l'objet entier
tel quel (jamais un état à moitié restauré, qui violerait `taches_heure_sans_jour_ck`).
"""
import datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist
from django.db import IntegrityError, models, transaction
from django.http import Http404
from django.utils import timezone

from apps.taches.choix import CibleLiable
from apps.taches.models.erp import SuggestionTache
from apps.taches.models.gestes import GesteAnnulable
from apps.taches.models.journee import LignePlanJour, PlanJour
from apps.taches.models.projets import Projet, RevueProjet, Section
from apps.taches.models.rythme import IncitationCoach, Preference, ReglagesRythme
from apps.taches.models.taches import (
    ElementChecklist,
    Etiquette,
    EtiquetteTache,
    Rappel,
    RegleRecurrence,
    Tache,
)
from apps.taches.selectors.base import etiquettes_de, gestes_de, projets_de, sections_de, taches_de

DUREE_ANNULABLE = datetime.timedelta(days=7)

#: Types de geste (reference/donnees.md §4).
TYPES = frozenset({
    'creation', 'modification', 'planification', 'deplacement', 'terminaison', 'reouverture',
    'suppression', 'restauration', 'conversion', 'lien_activite', 'lot', 'decalage',
    'instanciation', 'plan_du_jour', 'bilan_du_soir', 'allegement', 'retour_absence', 'decision',
    'rappel', 'preference', 'rythme', 'suggestion', 'revue', 'essentiel',
})

#: Champs restaurables par objet (§4) ; `lien` est le couple (content_type, object_id) d'une tâche.
LISTE_BLANCHE = {
    'tache': frozenset({
        'titre', 'notes', 'statut', 'fait_le', 'annule_le', 'priorite', 'jour_prevu', 'moment',
        'heure_debut', 'echeance', 'echeance_heure', 'quelque_jour', 'estimation_minutes', 'projet',
        'section', 'reports', 'reports_tranches', 'premier_jour_prevu', 'rang_projet', 'rang_jour',
        'triee_le', 'en_attente_de', 'bloquee_par', 'jalon', 'confidentiel', 'lien'}),
    'projet': frozenset({
        'nom', 'objectif', 'icone', 'couleur', 'priorite', 'statut', 'statut_depuis', 'date_debut',
        'echeance', 'termine_le', 'issue', 'bilan', 'risque', 'domaine', 'planification_le', 'rang',
        'confidentiel', 'affichage'}),
    'section': frozenset({'nom', 'rang', 'date_debut', 'date_fin'}),
    'element_checklist': frozenset({'libelle', 'fait', 'fait_le', 'rang'}),
    'plan_jour': frozenset({'planifie_le', 'cloture_le', 'allege_le', 'reflexion', 'objectif_du_jour'}),
    'rappel': frozenset({'statut', 'jour', 'heure'}),
    'preference': frozenset({'valeur'}),
    'reglages_rythme': frozenset({
        'mode', 'palier', 'palier_source', 'bloc_debut', 'refus_montee', 'blocs_a_sauter',
        'baisse_refusee', 'essai_restant', 'tenir_reference', 'tenir_fixee_le',
        'tenir_silence_jusquau', 'pauses_sollicitations'}),
    'suggestion_tache': frozenset({'statut', 'tache', 'decidee_le'}),
    'incitation_coach': frozenset({'reponse', 'repondu_le'}),
}
#: Objets dont seules la création et la suppression s'annulent.
SANS_CHAMP = frozenset({'etiquette_tache', 'ligne_plan_jour', 'revue_projet'})

MODELES = {
    'tache': Tache, 'projet': Projet, 'section': Section, 'element_checklist': ElementChecklist,
    'etiquette_tache': EtiquetteTache, 'ligne_plan_jour': LignePlanJour, 'revue_projet': RevueProjet,
    'plan_jour': PlanJour, 'rappel': Rappel, 'preference': Preference,
    'reglages_rythme': ReglagesRythme, 'suggestion_tache': SuggestionTache,
    'incitation_coach': IncitationCoach,
}
#: Chemin du propriétaire d'un objet qui n'en porte pas lui-même.
CHEMIN_PROPRIETAIRE = {
    'section': 'projet__proprietaire',
    'element_checklist': 'tache__proprietaire',
    'etiquette_tache': 'tache__proprietaire',
    'ligne_plan_jour': 'plan__proprietaire',
}
#: Colonnes jamais reprises d'une opération (forcées par le service ou interdites, §4 « Jamais »).
JAMAIS = frozenset({
    'id', 'pk', 'company', 'company_id', 'proprietaire', 'proprietaire_id', 'created_at',
    'updated_at', 'lock_version', 'client_id', 'source', 'parent', 'parent_id', 'content_type',
    'content_type_id', 'object_id', 'activite_origine', 'activite_origine_id', 'is_deleted',
    'deleted_at', 'deleted_by', 'deleted_by_id'})

CONFLIT_MODIFIEE = 'modifiee_depuis'
CONFLIT_INTROUVABLE = 'introuvable'
CONFLIT_NOM_PRIS = 'nom_pris'


class _Refus(Exception):
    """Une clé étrangère ou un lien ne passe pas la revérification : l'objet reste inchangé."""


# --- Construire les opérations ------------------------------------------------------------

def _en_json(valeur):
    if isinstance(valeur, models.Model):
        return valeur.pk
    if isinstance(valeur, (datetime.datetime, datetime.date, datetime.time)):
        return valeur.isoformat()
    if isinstance(valeur, Decimal):
        return str(valeur)
    if isinstance(valeur, (list, tuple)):
        return [_en_json(v) for v in valeur]
    if isinstance(valeur, dict):
        return {str(k): _en_json(v) for k, v in valeur.items()}
    return valeur


def _lien_de(tache):
    """`{"cible": "crm.lead", "id": 12}` ou `None`, depuis les colonnes brutes de la tâche."""
    if tache.content_type_id is None or tache.object_id is None:
        return None
    ct = ContentType.objects.get_for_id(tache.content_type_id)
    return {'cible': f'{ct.app_label}.{ct.model}', 'id': tache.object_id}


def _valeur(instance, champ):
    if champ == 'lien':
        return _lien_de(instance)
    field = instance._meta.get_field(champ)
    return getattr(instance, field.attname)


def _verifier_objet(objet, champ=None):
    if objet not in MODELES:
        raise ValueError(f'objet annulable inconnu : {objet!r}')
    if champ is not None and champ not in LISTE_BLANCHE.get(objet, ()):
        raise ValueError(f'champ non restaurable : {objet}.{champ}')


def op_champ(objet, instance, champ, avant):
    """Opération « champ » : `avant` = la valeur d'avant l'écriture ; `apres` est LU sur `instance`
    (déjà modifiée). Un champ hors liste blanche est une erreur de programmation (ValueError)."""
    _verifier_objet(objet, champ)
    return {'op': 'champ', 'objet': objet, 'id': instance.pk, 'champ': champ,
            'avant': _en_json(avant), 'apres': _en_json(_valeur(instance, champ))}


def op_creation(objet, instance):
    """Opération « création » ; inverse : `soft_delete(record=False)` ou suppression dure."""
    _verifier_objet(objet)
    return {'op': 'creation', 'objet': objet, 'id': instance.pk}


def op_suppression_douce(objet, instance):
    """Opération « suppression douce » (Projet, Tache) ; inverse : `restore()`."""
    _verifier_objet(objet)
    return {'op': 'suppression_douce', 'objet': objet, 'id': instance.pk}


def op_suppression_dure(objet, instance, valeurs):
    """Opération « suppression dure » ; inverse : recréation au même `pk` depuis `valeurs`."""
    _verifier_objet(objet)
    return {'op': 'suppression_dure', 'objet': objet, 'id': instance.pk,
            'valeurs': _en_json(dict(valeurs or {}))}


def enregistrer_geste(user, type, message, operations):
    """Enregistre le geste annulable de `user` (le texte du toast, ≤ 200 caractères)."""
    if type not in TYPES:
        raise ValueError(f'type de geste inconnu : {type!r}')
    return GesteAnnulable.objects.create(
        company_id=user.company_id, proprietaire=user, type=type,
        message=str(message or '')[:200], operations=list(operations or []))


# --- Retrouver un objet du compte ---------------------------------------------------------

def _lignes_du_compte(objet, user, *, morts=False):
    modele = MODELES[objet]
    if getattr(user, 'company_id', None) is None or getattr(user, 'pk', None) is None:
        return modele.objects.none()
    gestionnaire = modele.all_objects if morts and hasattr(modele, 'all_objects') else modele.objects
    chemin = CHEMIN_PROPRIETAIRE.get(objet, 'proprietaire')
    return gestionnaire.filter(company_id=user.company_id, **{chemin: user})


def _instance(user, objet, pk, *, morts=False):
    try:
        pk = int(pk)
    except (TypeError, ValueError):
        return None
    return _lignes_du_compte(objet, user, morts=morts).select_for_update().filter(pk=pk).first()


def _portee_fk(user, modele):
    """Lignes que `user` peut désigner par une clé étrangère vers `modele` (None = jamais)."""
    selecteurs = {Tache: taches_de, Projet: projets_de, Section: sections_de, Etiquette: etiquettes_de}
    if modele in selecteurs:
        return selecteurs[modele](user)
    if modele in (PlanJour, RegleRecurrence):
        return modele.objects.filter(company_id=user.company_id, proprietaire=user)
    return None


def _fk_permise(user, field, pk):
    if pk is None:
        return field.null
    portee = _portee_fk(user, field.related_model)
    return portee is not None and portee.filter(pk=pk).exists()


# --- Défaire -------------------------------------------------------------------------------

def _depuis_json(field, valeur):
    if valeur is None:
        return None
    if field.is_relation:
        return int(valeur)
    if isinstance(field, models.JSONField):
        return valeur
    return field.to_python(valeur)


def _egal(instance, champ, apres):
    courant = _valeur(instance, champ)
    if champ == 'lien':
        return courant == apres
    try:
        return courant == _depuis_json(instance._meta.get_field(champ), apres)
    except (TypeError, ValueError, ArithmeticError):
        return False


def _poser_lien(user, tache, lien):
    if lien is None:
        tache.content_type, tache.object_id = None, None
        tache.lien_etat, tache.lien_libelle = '', ''
        return ['content_type', 'object_id', 'lien_etat', 'lien_libelle']
    # Revérifié par la porte unique de visibilité (portée CRM/ventes du compte, invariant 23) :
    # un lien sorti de sa portée depuis le geste n'est jamais reposé.
    from apps.taches.selectors.liens import cible_visible, identifiant
    if not isinstance(lien, dict) or lien.get('cible') not in CibleLiable.values:
        raise _Refus()
    objet_id = identifiant(lien.get('id'))
    if objet_id is None or not cible_visible(user, lien['cible'], objet_id):
        raise _Refus()
    app_label, modele = lien['cible'].split('.', 1)
    ct = ContentType.objects.get_by_natural_key(app_label, modele)
    tache.content_type, tache.object_id = ct, objet_id
    tache.lien_etat, tache.lien_libelle, tache.lien_verifie_le = 'ok', '', timezone.now()
    return ['content_type', 'object_id', 'lien_etat', 'lien_libelle', 'lien_verifie_le']


def _poser(user, instance, avant):
    """Pose les valeurs d'avant ; rend les colonnes à écrire. Lève `_Refus` (FK ou lien)."""
    ecrites = []
    for champ, valeur in avant.items():
        if champ == 'lien':
            ecrites += _poser_lien(user, instance, valeur)
            continue
        field = instance._meta.get_field(champ)
        valeur = _depuis_json(field, valeur)
        if field.is_relation and not _fk_permise(user, field, valeur):
            raise _Refus()
        setattr(instance, field.attname, valeur)
        ecrites.append(field.name)
    if any(f.name == 'updated_at' for f in instance._meta.concrete_fields):
        ecrites.append('updated_at')
    return ecrites


def _attendus(etape, blanche):
    """(valeur attendue, valeur d'avant) par champ permis : la PLUS RÉCENTE `apres` contrôle le
    conflit, la PLUS ANCIENNE `avant` est restaurée (les opérations arrivent de la fin)."""
    attendu, avant = {}, {}
    for op in etape['champs']:
        champ = op.get('champ')
        if champ not in blanche:
            continue  # invariant 21 : hors liste blanche, ignoré
        attendu.setdefault(champ, op.get('apres'))
        avant[champ] = op.get('avant')
    return attendu, avant


def _restaurer_champs(user, etape, bilan):
    objet, pk = etape['objet'], etape['id']
    blanche = LISTE_BLANCHE.get(objet)
    if blanche is None:
        return
    attendu, avant = _attendus(etape, blanche)
    if not avant:
        return
    instance = _instance(user, objet, pk)
    if instance is None:
        return bilan.conflit(objet, pk, CONFLIT_INTROUVABLE)
    try:
        if not all(_egal(instance, champ, valeur) for champ, valeur in attendu.items()):
            return bilan.conflit(objet, pk, CONFLIT_MODIFIEE)
        ecrites = _poser(user, instance, avant)
    except (_Refus, FieldDoesNotExist, TypeError, ValueError):
        return bilan.conflit(objet, pk, CONFLIT_INTROUVABLE)
    try:
        with transaction.atomic():
            instance.save(update_fields=ecrites)
    except IntegrityError:  # nom repris par un autre projet, étape ou étiquette depuis le geste
        return bilan.conflit(objet, pk, CONFLIT_NOM_PRIS if 'nom' in ecrites else CONFLIT_MODIFIEE)
    bilan.restauree(objet, pk)


def _encore_utilise(objet, instance):
    """Un projet, une étape ou une tâche qui a reçu d'autres tâches vivantes depuis le geste."""
    if objet == 'projet':
        return Tache.objects.filter(projet=instance).exists()
    if objet == 'section':
        return Tache.objects.filter(section=instance).exists()
    if objet == 'tache':
        return Tache.objects.filter(parent=instance).exists()
    return False


def _defaire_creation(user, op, bilan):
    objet, pk = op.get('objet'), op.get('id')
    if objet not in MODELES:
        return
    instance = _instance(user, objet, pk)
    if instance is None:
        return bilan.conflit(objet, pk, CONFLIT_INTROUVABLE)
    if _encore_utilise(objet, instance):
        return bilan.conflit(objet, pk, CONFLIT_MODIFIEE)
    if hasattr(instance, 'soft_delete'):
        instance.soft_delete(user, record=False)
    else:
        instance.delete()
    bilan.restauree(objet, pk)


def _sortir_d_un_projet_supprime(tache):
    """N7 : une tâche restaurée seule dont le projet reste supprimé revient dans À trier."""
    if tache.projet_id and not Projet.objects.filter(pk=tache.projet_id).exists():
        tache.projet_id, tache.section_id, tache.triee_le = None, None, None
        tache.save(update_fields=['projet', 'section', 'triee_le', 'updated_at'])


def detacher_d_un_parent_supprime(tache):
    """Une sous-tâche restaurée dont le parent reste supprimé redevient une tâche ordinaire (sinon la
    purge du parent l'emporterait en cascade) ; même règle que N7 pour le projet."""
    if tache.parent_id and not Tache.objects.filter(pk=tache.parent_id).exists():
        tache.parent_id = None
        tache.save(update_fields=['parent', 'updated_at'])


def _detacher_les_restaurees(user, bilan):
    """Passe finale : le parent n'est jugé « resté supprimé » qu'une fois TOUT le geste défait (les
    opérations se défont à l'envers : une sous-tâche passe avant son parent)."""
    pks = [r['id'] for r in bilan.restaurees if r['objet'] == 'tache']
    for tache in taches_de(user).filter(pk__in=pks, parent__isnull=False):
        detacher_d_un_parent_supprime(tache)


def _defaire_suppression_douce(user, op, bilan):
    objet, pk = op.get('objet'), op.get('id')
    if objet not in ('tache', 'projet'):
        return
    instance = _instance(user, objet, pk, morts=True)
    if instance is None:
        return bilan.conflit(objet, pk, CONFLIT_INTROUVABLE)
    if not instance.is_deleted:
        return bilan.conflit(objet, pk, CONFLIT_MODIFIEE)
    try:
        with transaction.atomic():
            if objet == 'tache':
                _sortir_d_un_projet_supprime(instance)
            instance.restore()
    except IntegrityError:
        return bilan.conflit(objet, pk, CONFLIT_NOM_PRIS)
    bilan.restauree(objet, pk)


def _champs_recrees(user, modele, valeurs):
    champs = {}
    for nom, valeur in (valeurs or {}).items():
        if nom in JAMAIS:
            continue
        field = modele._meta.get_field(nom)  # FieldDoesNotExist : refus
        if field.many_to_many or field.one_to_many:
            raise _Refus()
        valeur = _depuis_json(field, valeur)
        if field.is_relation and not _fk_permise(user, field, valeur):
            raise _Refus()
        champs[field.attname] = valeur
    return champs


def _defaire_suppression_dure(user, op, bilan):
    objet, pk = op.get('objet'), op.get('id')
    modele = MODELES.get(objet)
    if modele is None or objet in ('tache', 'projet'):
        return
    if modele._base_manager.filter(pk=pk).exists():
        return bilan.conflit(objet, pk, CONFLIT_MODIFIEE)
    try:
        instance = modele(pk=int(pk), company_id=user.company_id,
                          **_champs_recrees(user, modele, op.get('valeurs')))
        if any(f.name == 'proprietaire' for f in modele._meta.concrete_fields):
            instance.proprietaire = user
        with transaction.atomic():
            instance.save(force_insert=True)
    except (_Refus, FieldDoesNotExist, IntegrityError, TypeError, ValueError):
        return bilan.conflit(objet, pk, CONFLIT_INTROUVABLE)
    bilan.restauree(objet, pk)


class _Bilan:
    def __init__(self):
        self.restaurees, self.conflits, self._vus = [], [], set()

    def restauree(self, objet, pk):
        if ('r', objet, pk) not in self._vus:
            self._vus.add(('r', objet, pk))
            self.restaurees.append({'objet': objet, 'id': pk})

    def conflit(self, objet, pk, raison):
        if ('c', objet, pk) not in self._vus:
            self._vus.add(('c', objet, pk))
            self.conflits.append({'objet': objet, 'id': pk, 'raison': raison})

    def rendu(self):
        return {'restaurees': self.restaurees, 'conflits': self.conflits, 'deja': False}


def _etapes(operations):
    """Les opérations à défaire, de la dernière à la première ; les champs d'un même objet en une
    étape. Un projet supprimé est restauré AVANT ses tâches (elles y retournent, invariant 27)."""
    etapes, groupes, projets = [], {}, []
    for op in reversed(operations if isinstance(operations, list) else []):
        if not isinstance(op, dict):
            continue
        if op.get('op') == 'champ':
            cle = (op.get('objet'), op.get('id'))
            if cle not in groupes:
                groupes[cle] = {'op': 'champs', 'objet': cle[0], 'id': cle[1], 'champs': []}
                etapes.append(groupes[cle])
            groupes[cle]['champs'].append(op)
        elif op.get('op') == 'suppression_douce' and op.get('objet') == 'projet':
            projets.append(op)
        else:
            etapes.append(op)
    return projets + etapes


_DEFAIRE = {
    'champs': _restaurer_champs,
    'creation': _defaire_creation,
    'suppression_douce': _defaire_suppression_douce,
    'suppression_dure': _defaire_suppression_dure,
}


def _rouvrir_sources_converties(user, operations, bilan):
    """Annuler une conversion (« conversion » d'à-faire ERP en tâches) rouvre l'à-faire SOURCE de chaque
    tâche dont la création vient d'être défaite, par `records.services.rouvrir_a_faire_personnel` (lu par
    `records.selectors.a_faire_personnels_de` : jamais l'à-faire d'un autre créateur). Une tâche restée en
    place (conflit) garde sa source close ; un à-faire que `records` refuse de rouvrir va dans `conflits`
    (`objet` = `activite`)."""
    from apps.records.selectors import a_faire_personnels_de
    from apps.records.services import rouvrir_a_faire_personnel

    retirees = {r['id'] for r in bilan.restaurees if r['objet'] == 'tache'}
    creees = [op.get('id') for op in operations if isinstance(op, dict) and op.get('op') == 'creation'
              and op.get('objet') == 'tache' and op.get('id') in retirees]
    sources = list(Tache.all_objects.filter(company_id=user.company_id, proprietaire=user, pk__in=creees,
                                            is_deleted=True, activite_origine_id__isnull=False)
                   .values_list('activite_origine_id', flat=True))
    for activite in a_faire_personnels_de(user, ids=sources):
        try:
            rouvrir_a_faire_personnel(activite, user)
        except activite.DoesNotExist:
            bilan.conflit('activite', activite.pk, CONFLIT_INTROUVABLE)


#: Colonnes d'un `PlanJour` qu'aucun geste n'écrit (la nuit, `vu/`) : non vides = le plan a vécu.
PLAN_ECRIT_AILLEURS = ('app_ouverte_le', 'capacite_minutes', 'capacite_source', 'statut_jour', 'compte_rythme',
                       'micro_comptees', 'essentiels_choisis', 'essentiels_faits', 'plan_prevues', 'plan_faites',
                       'minutes_prevues', 'minutes_faites', 'taille_mediane_min')


def _ids_crees(operations, objet):
    return {op.get('id') for op in operations if isinstance(op, dict) and op.get('op') == 'creation'
            and op.get('objet') == objet}


def _plans_gardes(user, geste):
    """Revue F2 #3 : les `PlanJour` créés par `geste` qui ont reçu DEPUIS d'autres écritures — une
    ligne d'un autre geste (★, bilan), un geste plus récent qui les nomme (bilan du soir, alléger), un
    compteur de la nuit ou `vu/`. Les défaire supprimerait (CASCADE) ce que ces écritures ont posé :
    ils restent tels quels, avec leurs lignes, et vont dans `conflits` (`modifiee_depuis`)."""
    operations = geste.operations if isinstance(geste.operations, list) else []
    crees = _ids_crees(operations, 'plan_jour')
    if not crees:
        return set()
    lignes_du_geste = _ids_crees(operations, 'ligne_plan_jour')
    plus_recents = (gestes_de(user).filter(created_at__gte=geste.created_at, annule_le__isnull=True)
                    .exclude(pk=geste.pk))
    gardes = set()
    for plan in _lignes_du_compte('plan_jour', user).filter(pk__in=crees):
        if (any(getattr(plan, champ) != plan._meta.get_field(champ).get_default() for champ in PLAN_ECRIT_AILLEURS)
                or LignePlanJour.objects.filter(plan=plan).exclude(pk__in=lignes_du_geste).exists()
                or plus_recents.filter(operations__contains=[{'objet': 'plan_jour', 'id': plan.pk}]).exists()):
            gardes.add(plan.pk)
    return gardes


def _etapes_hors_plans_gardes(user, geste, bilan):
    """Les étapes du geste, sans celles qui toucheraient un plan gardé (`_plans_gardes`)."""
    gardes = _plans_gardes(user, geste)
    lignes = set(LignePlanJour.objects.filter(plan_id__in=gardes).values_list('pk', flat=True)) if gardes else set()
    for pk in sorted(gardes):
        bilan.conflit('plan_jour', pk, CONFLIT_MODIFIEE)
    for etape in _etapes(geste.operations):
        if (etape.get('objet') == 'plan_jour' and etape.get('id') in gardes
                or etape.get('objet') == 'ligne_plan_jour' and etape.get('op') == 'creation'
                and etape.get('id') in lignes):
            continue
        yield etape


def annuler_geste(user, geste_id):
    """Défait le geste `geste_id` de `user` → `{"restaurees", "conflits", "deja"}`
    (`geste_annuler.json`). `Http404` hors propriétaire, inconnu ou de plus de 7 jours."""
    try:
        geste_id = int(geste_id)
    except (TypeError, ValueError):
        raise Http404('Introuvable.')
    limite = timezone.now() - DUREE_ANNULABLE
    with transaction.atomic():
        geste = (gestes_de(user).select_for_update()
                 .filter(pk=geste_id, created_at__gte=limite).first())
        if geste is None:
            raise Http404('Introuvable.')
        if geste.annule_le is not None:
            return {'restaurees': [], 'conflits': [], 'deja': True}
        bilan = _Bilan()
        for etape in _etapes_hors_plans_gardes(user, geste, bilan):
            defaire = _DEFAIRE.get(etape.get('op'))
            if defaire is not None:
                defaire(user, etape, bilan)
        _detacher_les_restaurees(user, bilan)
        if geste.type == 'conversion':
            _rouvrir_sources_converties(user, geste.operations, bilan)
        geste.annule_le = timezone.now()
        geste.save(update_fields=['annule_le', 'updated_at'])
    return bilan.rendu()
