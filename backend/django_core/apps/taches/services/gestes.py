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
    from apps.records.serializers import resolve_target
    if not isinstance(lien, dict) or lien.get('cible') not in CibleLiable.values:
        raise _Refus()
    try:
        ct, _cible = resolve_target(lien.get('cible'), lien.get('id'), user.company, user=user)
    except (ValueError, AttributeError):
        raise _Refus()
    tache.content_type, tache.object_id = ct, lien.get('id')
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
        for etape in _etapes(geste.operations):
            defaire = _DEFAIRE.get(etape.get('op'))
            if defaire is not None:
                defaire(user, etape, bilan)
        geste.annule_le = timezone.now()
        geste.save(update_fields=['annule_le', 'updated_at'])
    return bilan.rendu()
