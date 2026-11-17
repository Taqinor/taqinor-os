"""Lire, éditer et supprimer une tâche (reference/api.md §3.2, §4 ; donnees.md invariants 1, 6, 7, 9, 15, 27).

- `liste_taches` : la requête des listes paginées (À trier, En réserve, filtres, ✓+ d'une fiche ERP) ;
- `reverifier_lien` : la fiche revérifie son lien ERP (invariant 23) sans toucher à `lock_version` ;
- `modifier_tache` : le PATCH à verrou. Il REFUSE `jour_prevu`, `heure_debut`, `moment` et
  `quelque_jour` (invariant 15 : seul `planifier()` les écrit) ; chaque identifiant reçu est revérifié
  « même société ET même propriétaire » (invariant 9) ; un prérequis ne boucle jamais (invariant 6) ;
  un geste annulable est rendu ;
- `supprimer_tache` : suppression douce de la tâche ET de ses sous-tâches dans UN geste (min-20).

Rien n'est lu du corps pour la société ni le propriétaire : tout passe par `taches_de(user)`.
"""
import datetime
from dataclasses import dataclass

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import F, Max, Q
from django.http import Http404
from django.utils import timezone
from rest_framework import serializers

from apps.taches.choix import CibleLiable, LienEtat, Priorite, Source, StatutRappel, StatutTache
from apps.taches.confidentialite import ECRAN, nom_pour
from apps.taches.models.rythme import ReglagesRythme
from apps.taches.models.taches import ElementChecklist, EtiquetteTache, Tache
from apps.taches.moteur.gabarits import format_jour
from apps.taches.moteur.recurrence import prochaine_occurrence
from apps.taches.selectors.base import (
    TACHE_CONFIDENTIELLE, etiquettes_de, filtrer_q, jours_travailles_de, projets_de, rappels_de, sections_de,
    taches_de,
)
from apps.taches.selectors.liens import cible_visible, libelle_de_cible
from apps.taches.services.creation import creer_taches
from apps.taches.services.gestes import (
    enregistrer_geste, op_champ, op_creation, op_suppression_douce, op_suppression_dure,
)
from apps.taches.services.planification import (
    MESSAGE_CONFLIT, planifier, _actuel as etat_minimal, _avertissements as avertissements_du_jour,
)
from apps.taches.services.rappels import _hors_fenetre as hors_fenetre
from apps.taches.services.rappels import annuler_rappels, recalculer_ancres
from core.verrou_optimiste import CHAMP_VERSION, CODE_CONFLIT_VERSION, ConflitVersion

OUVERTES = (StatutTache.A_FAIRE, StatutTache.EN_ATTENTE)
PAS_RANG = 1024
MAX_MAILLONS = 50
HORIZON_OUVRES = 400
VUES = ('boite', 'quelque_jour')
PERIODES = ('aujourdhui', 'semaine', 'retard')
TRIS = ('rang', 'echeance', 'priorite')
GROUPES = ('projet',)

MESSAGE_TITRE_VIDE = 'Le titre est vide une fois la date et le projet retirés.'
MESSAGE_TITRE_LONG = '280 caractères au plus.'
MESSAGE_PROJET_INEXISTANT = 'Projet inexistant.'
MESSAGE_VALEUR_INCONNUE = 'Valeur inconnue.'
MESSAGE_ESTIMATION = 'Entre 5 et 960 minutes.'
MESSAGE_HEURE_SANS_ECHEANCE = 'Une heure demande une échéance.'
MESSAGE_NON_MODIFIABLE = 'Non modifiable ici.'
MESSAGE_LIEN_INTROUVABLE = 'Élément introuvable ou hors de ta portée.'
MESSAGE_LIEN_TYPE = "Ce type d'élément ne peut pas être lié à une tâche."


@dataclass(frozen=True)
class ResultatEcriture:
    tache: object
    geste: object = None
    avertissements: tuple = ()
    suivante: object = None


# --- Lire ---------------------------------------------------------------------------------------

def tache_du_compte(user, pk, *, verrou=False):
    """La tâche vivante de `user` (sinon 404 : un id étranger répond comme un id inconnu)."""
    try:
        pk = int(pk)
    except (TypeError, ValueError):
        raise Http404('Introuvable.')
    qs = taches_de(user).select_for_update() if verrou else taches_de(user)
    tache = qs.filter(pk=pk).first()
    if tache is None:
        raise Http404('Introuvable.')
    return tache


def _entier(params, nom):
    valeur = params.get(nom)
    if valeur in (None, ''):
        return None
    try:
        return int(valeur)
    except (TypeError, ValueError):
        raise serializers.ValidationError({nom: [MESSAGE_VALEUR_INCONNUE]})


def _booleen(params, nom):
    return str(params.get(nom, '')).lower() in ('1', 'true', 'vrai', 'oui')


def _choix(params, nom, permis):
    valeur = params.get(nom)
    if valeur in (None, ''):
        return None
    if valeur not in permis:
        raise serializers.ValidationError({nom: [MESSAGE_VALEUR_INCONNUE]})
    return valeur


def _statuts(params):
    """Statuts listés : `statut=` précis, sinon les ouvertes (+ les faites avec `inclure_faites`)."""
    statut = _choix(params, 'statut', StatutTache.values)
    if statut is not None:
        return (statut,)
    if _booleen(params, 'ouvertes') or not _booleen(params, 'inclure_faites'):
        return OUVERTES
    return (*OUVERTES, StatutTache.FAIT)


def _filtrer_vue(qs, vue):
    if vue == 'boite':  # invariant 1 : À trier
        return qs.filter(projet__isnull=True, triee_le__isnull=True)
    if vue == 'quelque_jour':
        return qs.filter(quelque_jour=True)
    return qs


def _filtrer_periode(qs, periode, aujourdhui):
    if periode == 'aujourdhui':
        return qs.filter(jour_prevu=aujourdhui)
    if periode == 'semaine':
        return qs.filter(jour_prevu__gte=aujourdhui, jour_prevu__lte=aujourdhui + datetime.timedelta(days=6))
    if periode == 'retard':
        return qs.filter(Q(jour_prevu__lt=aujourdhui) | Q(echeance__lt=aujourdhui))
    return qs


def _filtrer_lien(qs, params):
    cible = _choix(params, 'cible', ('crm.lead', 'crm.client', 'ventes.devis'))
    identifiant = _entier(params, 'cible_id')
    if cible is None:
        return qs.filter(parent__isnull=True)
    app_label, modele = cible.split('.', 1)
    qs = qs.filter(content_type=ContentType.objects.get_by_natural_key(app_label, modele))
    return qs.filter(object_id=identifiant) if identifiant is not None else qs


def _ordre(qs, params):
    tri = _choix(params, 'tri', TRIS) or 'rang'
    groupe = _choix(params, 'groupe', GROUPES)
    ordre = {'rang': ('rang_projet', 'id'), 'priorite': ('-priorite', 'id'),
             'echeance': (F('echeance').asc(nulls_last=True), 'id')}[tri]
    return qs.order_by('projet__rang', *ordre) if groupe == 'projet' else qs.order_by(*ordre)


def liste_taches(user, params, *, assistant=False, aujourdhui=None):
    """Le queryset des listes (`GET taches/`) ; 400 nommé sur un paramètre inconnu ou illisible.

    `vue=boite` : À trier ; `vue=quelque_jour` : En réserve ; `cible` + `cible_id` + `ouvertes` : les
    tâches liées à une fiche ERP (✓+). Un compte ne lit jamais que SES tâches."""
    aujourdhui = aujourdhui or timezone.localdate()
    qs = taches_de(user).filter(statut__in=_statuts(params))
    qs = _filtrer_lien(_filtrer_vue(qs, _choix(params, 'vue', VUES)), params)
    qs = _filtrer_periode(qs, _choix(params, 'periode', PERIODES), aujourdhui)
    for nom, champ in (('projet', 'projet_id'), ('section', 'section_id')):
        valeur = _entier(params, nom)
        if valeur is not None:
            qs = qs.filter(**{champ: valeur})
    etiquette = _entier(params, 'etiquette')
    if etiquette is not None:
        qs = qs.filter(etiquettetache__etiquette_id=etiquette, etiquettetache__etiquette__proprietaire=user)
    priorite = _entier(params, 'priorite_min')
    if priorite is not None:
        qs = qs.filter(priorite__gte=priorite)
    qs = filtrer_q(qs, params.get('q'), assistant=assistant)
    if assistant:
        qs = qs.exclude(TACHE_CONFIDENTIELLE)
    return _ordre(qs, params)


def reverifier_lien(user, tache):
    """Revérifie le lien ERP de `tache` (invariant 23) : libellé et état relus par la porte de l'app cible.
    Écrit SEULEMENT si quelque chose a changé, par `update()` : lire une fiche ne bouge pas `lock_version`."""
    if tache.content_type_id is None or tache.object_id is None:
        return tache
    cible = f'{tache.content_type.app_label}.{tache.content_type.model}'
    libelle = libelle_de_cible(user, cible, tache.object_id)
    if libelle is not None:
        etat = LienEtat.OK
    else:
        etat = LienEtat.EFFACE if tache.lien_etat == LienEtat.EFFACE else LienEtat.INTROUVABLE
        libelle = ''
    if (etat, libelle) == (tache.lien_etat, tache.lien_libelle) and tache.lien_verifie_le is not None:
        return tache
    maintenant = timezone.now()
    Tache.objects.filter(pk=tache.pk).update(lien_etat=etat, lien_libelle=libelle, lien_verifie_le=maintenant)
    tache.lien_etat, tache.lien_libelle, tache.lien_verifie_le = etat, libelle, maintenant
    return tache


# --- Éditer -------------------------------------------------------------------------------------

def verrouiller(user, pk, version):
    """La tâche de `user` relue SOUS VERROU ; la version envoyée est comparée sous ce verrou (409
    `conflit_version` : la vue remplace `actuel` par la forme TACHE complète de `exc.tache`)."""
    tache = tache_du_compte(user, pk, verrou=True)
    if version is not None and tache.lock_version != int(version):
        exc = ConflitVersion({'detail': MESSAGE_CONFLIT, 'code': CODE_CONFLIT_VERSION,
                              CHAMP_VERSION: tache.lock_version, 'actuel': etat_minimal(tache)})
        exc.tache = tache
        raise exc
    return tache


class _Edition:
    """Ce qu'un PATCH change : les valeurs d'avant (pour les opérations d'annulation), les colonnes à
    écrire et les opérations déjà prêtes (étiquettes, rappels, sous-tâches)."""

    def __init__(self, user, tache):
        self.user, self.tache = user, tache
        self.avant, self.ecrire, self.ops = {}, set(), []

    def poser(self, champ, valeur, *, annulable=True):
        """Pose `champ` s'il change ; `champ` d'une clé étrangère se donne sans `_id`."""
        colonne = f'{champ}_id' if champ in ('projet', 'section', 'bloquee_par') else champ
        courant = getattr(self.tache, colonne)
        if courant == valeur:
            return False
        if annulable:
            self.avant.setdefault(champ, courant)
        setattr(self.tache, colonne, valeur)
        self.ecrire.add(champ)
        return True

    def operations(self):
        return [op_champ('tache', self.tache, champ, avant) for champ, avant in self.avant.items()] + self.ops


def _titre(valeur):
    titre = str(valeur or '').strip()
    if not titre:
        raise serializers.ValidationError({'titre': [MESSAGE_TITRE_VIDE]})
    if len(titre) > 280:
        raise serializers.ValidationError({'titre': [MESSAGE_TITRE_LONG]})
    return titre


def _bornes(donnees):
    """Valeurs simples revérifiées (priorité, estimation, durée)."""
    if donnees.get('priorite') is not None and donnees['priorite'] not in Priorite.values:
        raise serializers.ValidationError({'priorite': [MESSAGE_VALEUR_INCONNUE]})
    estimation = donnees.get('estimation_minutes')
    if estimation is not None and not 5 <= estimation <= 960:
        raise serializers.ValidationError({'estimation_minutes': [MESSAGE_ESTIMATION]})


def _simples(edition, donnees):
    _bornes(donnees)
    if 'titre' in donnees:
        edition.poser('titre', _titre(donnees['titre']))
    for champ in ('notes', 'priorite', 'jalon', 'confidentiel'):
        if donnees.get(champ) is not None:
            edition.poser(champ, donnees[champ])
    if 'estimation_minutes' in donnees:
        edition.poser('estimation_minutes', donnees['estimation_minutes'])
    if 'duree_reelle_minutes' in donnees:  # hors liste blanche d'annulation (donnees.md §4)
        edition.poser('duree_reelle_minutes', donnees['duree_reelle_minutes'], annulable=False)


def _echeance(edition, donnees):
    """Échéance et heure d'échéance ; les rappels ancrés sur l'échéance suivent (invariant 19)."""
    tache = edition.tache
    if 'echeance' in donnees:
        if edition.poser('echeance', donnees['echeance']):
            edition.ops += recalculer_ancres(tache)
        if tache.echeance is None:
            edition.poser('echeance_heure', None)
    if 'echeance_heure' in donnees and donnees['echeance_heure'] is not None:
        if tache.echeance is None:
            raise serializers.ValidationError({'echeance_heure': [MESSAGE_HEURE_SANS_ECHEANCE]})
        edition.poser('echeance_heure', donnees['echeance_heure'])
    elif 'echeance_heure' in donnees:
        edition.poser('echeance_heure', None)


def _projet(user, projet_id):
    projet = projets_de(user).filter(pk=projet_id).first()
    if projet is None:
        raise serializers.ValidationError({'projet_id': [MESSAGE_PROJET_INEXISTANT]})
    return projet


def _rang_dans(user, projet):
    dernier = taches_de(user).filter(projet=projet).aggregate(m=Max('rang_projet'))['m']
    return (dernier or 0) + PAS_RANG


def _suivre_le_parent(edition, tache):
    """Invariant 7 : les sous-tâches vivantes suivent le projet et l'étape de leur parent."""
    for enfant in taches_de(edition.user).filter(parent=tache):
        avant = {'projet': enfant.projet_id, 'section': enfant.section_id}
        enfant.projet_id, enfant.section_id = tache.projet_id, tache.section_id
        enfant.save(update_fields=['projet', 'section', 'updated_at'])
        edition.ops += [op_champ('tache', enfant, champ, valeur) for champ, valeur in avant.items()
                        if getattr(enfant, f'{champ}_id') != valeur]


def _projet_et_section(edition, donnees):
    """`projet_id` et `section_id` ; une sous-tâche garde ceux de son parent (400 sinon)."""
    tache, user = edition.tache, edition.user
    if 'projet_id' not in donnees and 'section_id' not in donnees:
        return
    for champ in ('projet_id', 'section_id'):
        if champ in donnees and tache.parent_id is not None:
            raise serializers.ValidationError({champ: [MESSAGE_NON_MODIFIABLE]})
    if 'projet_id' in donnees:
        projet = _projet(user, donnees['projet_id']) if donnees['projet_id'] is not None else None
        if edition.poser('projet', projet.pk if projet else None):
            edition.poser('section', None)
            edition.poser('rang_projet', _rang_dans(user, projet))
            if projet is not None and tache.triee_le is None:
                edition.poser('triee_le', timezone.now())
    if donnees.get('section_id') is not None:
        section = (sections_de(user).filter(pk=donnees['section_id'], projet_id=tache.projet_id).first()
                   if tache.projet_id else None)
        if section is None:
            raise Http404('Introuvable.')
        edition.poser('section', section.pk)
    elif 'section_id' in donnees:
        edition.poser('section', None)
    if {'projet', 'section'} & edition.ecrire:
        _suivre_le_parent(edition, tache)


def _boucle(user, tache, candidat):
    """Vrai si suivre les prérequis de `candidat` ramène à `tache` (≤ 50 maillons : au-delà, refus)."""
    courant, vus = candidat, 0
    while courant is not None:
        if courant.pk == tache.pk or vus >= MAX_MAILLONS:
            return True
        courant = taches_de(user).filter(pk=courant.bloquee_par_id).first() if courant.bloquee_par_id else None
        vus += 1
    return False


def _prerequis(edition, donnees, usage):
    if 'bloquee_par_id' not in donnees:
        return
    candidat_id = donnees['bloquee_par_id']
    candidat = tache_du_compte(edition.user, candidat_id) if candidat_id is not None else None
    if candidat is not None and _boucle(edition.user, edition.tache, candidat):
        raise serializers.ValidationError({'bloquee_par_id': [
            f'Boucle : « {nom_pour(candidat, usage)} » attend déjà « {nom_pour(edition.tache, usage)} ».']})
    edition.poser('bloquee_par', candidat.pk if candidat else None)


def _etiquettes(edition, ids):
    """Remplace l'ensemble des étiquettes (ids du compte, sinon 404) ; création et retrait annulables."""
    user, tache = edition.user, edition.tache
    voulues = set(ids)
    connues = set(etiquettes_de(user).filter(pk__in=voulues).values_list('pk', flat=True))
    if connues != voulues:
        raise Http404('Introuvable.')
    actuelles = {lien.etiquette_id: lien for lien in EtiquetteTache.objects.filter(tache=tache)}
    for pk in sorted(voulues - set(actuelles)):
        lien = EtiquetteTache.objects.create(company_id=user.company_id, tache=tache, etiquette_id=pk)
        edition.ops.append(op_creation('etiquette_tache', lien))
    for pk in sorted(set(actuelles) - voulues):
        lien = actuelles[pk]
        edition.ops.append(op_suppression_dure('etiquette_tache', lien, {'tache': tache.pk, 'etiquette': pk}))
        lien.delete()


def lien_courant(tache):
    """`{"cible", "id"}` du lien ERP stocké, ou `None`."""
    if tache.content_type_id is None or tache.object_id is None:
        return None
    ct = ContentType.objects.get_for_id(tache.content_type_id)
    return {'cible': f'{ct.app_label}.{ct.model}', 'id': tache.object_id}


def verifier_lien(user, lien):
    """400 sur `lien` si la cible n'est pas liable ou pas visible (refus = introuvable)."""
    if lien.get('cible') not in CibleLiable.values:
        raise serializers.ValidationError({'lien': [MESSAGE_LIEN_TYPE]})
    if not cible_visible(user, lien['cible'], lien.get('id')):
        raise serializers.ValidationError({'lien': [MESSAGE_LIEN_INTROUVABLE]})


def _lien(edition, lien):
    """Pose ou retire le lien ERP (cible ∈ `CibleLiable` ET visible : sinon 400 sur `lien`)."""
    tache = edition.tache
    avant = lien_courant(tache)
    if lien is None:
        tache.content_type, tache.object_id = None, None
        tache.lien_etat, tache.lien_libelle, tache.lien_verifie_le = '', '', None
    else:
        verifier_lien(edition.user, lien)
        app_label, modele = lien['cible'].split('.', 1)
        tache.content_type = ContentType.objects.get_by_natural_key(app_label, modele)
        tache.object_id = lien['id']
        tache.lien_etat, tache.lien_verifie_le = LienEtat.OK, timezone.now()
        tache.lien_libelle = libelle_de_cible(edition.user, lien['cible'], lien['id']) or ''
    if lien_courant(tache) != avant:
        edition.avant['lien'] = avant
        edition.ecrire |= {'content_type', 'object_id', 'lien_etat', 'lien_libelle', 'lien_verifie_le'}


def _colonnes(ecrire):
    """Colonnes réelles à écrire pour les noms de `Edition.ecrire`."""
    colonnes = {f'{c}_id' if c in ('projet', 'section', 'bloquee_par') else c for c in ecrire}
    return sorted(colonnes | {'updated_at'})


def modifier_tache(user, pk, donnees, *, version, aujourdhui=None, usage=ECRAN):
    """`PATCH taches/{id}/` : applique `donnees` (déjà typées) sous verrou → `ResultatEcriture`.
    409 `conflit_version` si `version` n'est plus celle de la base ; rien n'est écrit sur un refus."""
    aujourdhui = aujourdhui or timezone.localdate()
    with transaction.atomic():
        tache = verrouiller(user, pk, version)
        edition = _Edition(user, tache)
        _simples(edition, donnees)
        _echeance(edition, donnees)
        _projet_et_section(edition, donnees)
        _prerequis(edition, donnees, usage)
        if 'lien' in donnees:
            _lien(edition, donnees['lien'])
        if 'etiquettes' in donnees:
            _etiquettes(edition, donnees['etiquettes'])
        geste = None
        if edition.ecrire:
            tache.save(update_fields=_colonnes(edition.ecrire))
        ops = edition.operations()
        if ops:
            geste = enregistrer_geste(user, 'modification', 'Modifiée', ops)
    return ResultatEcriture(tache, geste, tuple(avertissements_du_jour(user, tache, aujourdhui)))


def rappel_a_la_creation(user, tache):
    """`(rappel, question_titres)` d'une tâche qui vient d'être créée avec un rappel : le plus proche en
    attente (+ `hors_fenetre`), et vrai tant que le compte n'a pas répondu à la question de l'écran
    verrouillé (A17-T4). `(None, False)` sans rappel."""
    rappel = (rappels_de(user).filter(tache=tache, statut=StatutRappel.EN_ATTENTE)
              .order_by('jour', 'heure', 'pk').first())
    if rappel is None:
        return None, False
    rappel.hors_fenetre = hors_fenetre(user.company, rappel.jour, rappel.heure)
    reglages = ReglagesRythme.objects.filter(company_id=user.company_id, proprietaire=user).first()
    return rappel, reglages is None or reglages.titres_notifications_demande_le is None


# --- Supprimer ----------------------------------------------------------------------------------

def supprimer_tache(user, pk):
    """`DELETE taches/{id}/` : la tâche et ses sous-tâches vivantes disparaissent dans UN geste
    (`soft_delete(record=False)`) ; leurs rappels en attente sont annulés (invariant 19)."""
    with transaction.atomic():
        tache = tache_du_compte(user, pk, verrou=True)
        concernees = [tache, *taches_de(user).select_for_update().filter(parent=tache)]
        ops = []
        for t in concernees:
            annuler_rappels(t, collecte=ops)
            t.soft_delete(user, record=False)
            ops.append(op_suppression_douce('tache', t))
        return enregistrer_geste(user, 'suppression', 'Supprimée', ops)


# --- Actions d'état : terminer, rouvrir, sauter, trancher, attendre, reçu, restaurer ---------------

#: `lock_version` d'une occurrence au sortir de `creer_taches` (insertion 0, puis `planifier` 1) : au-delà,
#: quelqu'un l'a touchée et « Rouvrir » ne la supprime plus (regles.md « La récurrence »).
VERSION_OCCURRENCE_NEUVE = 1
CHOIX_TRANCHER = ('aujourdhui', 'garder', 'jour', 'un_jour', 'abandonner')
MESSAGE_ATTENTE_VIDE = 'Dis de qui ou de quoi tu attends.'
MESSAGE_ATTENTE_LONGUE = '200 caractères au plus.'
MESSAGE_PAS_RECURRENTE = 'Cette tâche ne se répète pas.'
MESSAGE_JOUR_REQUIS = 'Requis.'
FENETRE_SUPPRESSION_GROUPEE = datetime.timedelta(seconds=5)
CHAMPS_STATUT = ('statut', 'fait_le', 'annule_le', 'triee_le')


def est_ouvre_de(user, aujourdhui):
    """`est_ouvre(date)` des séries « jours ouvrés » : les jours TRAVAILLÉS du compte sur 400 jours
    (au-delà : lundi-vendredi)."""
    fin = aujourdhui + datetime.timedelta(days=HORIZON_OUVRES)
    travailles = jours_travailles_de(user, aujourdhui, fin)
    return lambda jour: (jour in travailles) if jour <= fin else jour.weekday() < 5


def _poser_statut(t, statut, maintenant, ops):
    """Pose `statut` (`fait` ⇔ `fait_le`, `annule` ⇔ `annule_le` : invariant 16) et ajoute les opérations ;
    clore une tâche la sort d'À trier (`triee_le`, invariant 1)."""
    avant = {champ: getattr(t, champ) for champ in CHAMPS_STATUT}
    t.statut = statut
    t.fait_le = maintenant if statut == StatutTache.FAIT else None
    t.annule_le = maintenant if statut == StatutTache.ANNULE else None
    if t.triee_le is None and statut in (StatutTache.FAIT, StatutTache.ANNULE):
        t.triee_le = maintenant
    t.save(update_fields=[*CHAMPS_STATUT, 'updated_at'])
    ops.extend(op_champ('tache', t, champ, valeur) for champ, valeur in avant.items()
               if getattr(t, champ) != valeur)


def _ligne_de_la_suivante(t, jour, etiquettes, checklist):
    return {'titre': t.titre, 'notes': t.notes, 'priorite': t.priorite, 'jalon': t.jalon,
            'confidentiel': t.confidentiel, 'estimation_minutes': t.estimation_minutes,
            'projet_id': t.projet_id, 'section_id': t.section_id, 'jour_prevu': jour,
            'heure_debut': t.heure_debut, 'recurrence': t.recurrence_id, 'occurrence_du': jour,
            'etiquettes': etiquettes, 'checklist': checklist}


def _occurrence_suivante(user, t, maintenant, aujourdhui, *, apres_fait):
    """L'occurrence qui naît quand `t` est close (terminer ou sauter) : une seule ouverte par règle
    (invariant 5). Rend la tâche née, ou `None` (série arrêtée ou close : la règle s'éteint)."""
    regle = t.recurrence if t.recurrence_id else None
    if regle is None or not regle.actif:
        return None
    jour = prochaine_occurrence(
        regle, t.occurrence_du, aujourdhui, fait_le=timezone.localtime(maintenant) if apres_fait else None,
        est_ouvre=est_ouvre_de(user, aujourdhui))
    if jour is None:
        regle.actif = False
        regle.save(update_fields=['actif', 'updated_at'])
        return None
    etiquettes = list(EtiquetteTache.objects.filter(tache=t).values_list('etiquette_id', flat=True))
    checklist = list(ElementChecklist.objects.filter(tache=t).order_by('rang', 'pk').values_list('libelle', flat=True))
    resultat = creer_taches(user, [_ligne_de_la_suivante(t, jour, etiquettes, checklist)],
                            source=Source.RECURRENCE, porte='recurrence')
    return resultat.creees[0]


def _clore(user, t, statut, maintenant, ops, *, enfants):
    """Ferme `t` (et, si `enfants`, ses sous-tâches ouvertes : invariant 7) ; ses rappels en attente
    sont annulés (invariant 19)."""
    _poser_statut(t, statut, maintenant, ops)
    annuler_rappels(t, collecte=ops)
    if enfants:
        for enfant in taches_de(user).select_for_update().filter(parent=t, statut__in=OUVERTES):
            _poser_statut(enfant, statut, maintenant, ops)
            annuler_rappels(enfant, collecte=ops)


def _fin_de_serie(user, t, maintenant, aujourdhui, ops, *, apres_fait):
    suivante = _occurrence_suivante(user, t, maintenant, aujourdhui, apres_fait=apres_fait)
    if suivante is not None:
        ops.append(op_creation('tache', suivante))
    return suivante


def terminer_tache(user, pk, *, maintenant=None, aujourdhui=None):
    """Coche `pk` : fait, sous-tâches ouvertes faites, rappels annulés, occurrence suivante née (série) —
    en UN geste annulable. Déjà faite : rien ne bouge (idempotent)."""
    maintenant, aujourdhui = maintenant or timezone.now(), aujourdhui or timezone.localdate()
    with transaction.atomic():
        t = tache_du_compte(user, pk, verrou=True)
        if t.statut == StatutTache.FAIT:
            return ResultatEcriture(t)
        ops = []
        _clore(user, t, StatutTache.FAIT, maintenant, ops, enfants=True)
        suivante = _fin_de_serie(user, t, maintenant, aujourdhui, ops, apres_fait=True)
        message = 'Faite'
        if suivante is not None:
            message += f' · prochaine {format_jour(suivante.jour_prevu, aujourdhui)}'
        geste = enregistrer_geste(user, 'terminaison', message, ops)
    return ResultatEcriture(t, geste, suivante=suivante)


def sauter_occurrence(user, pk, *, maintenant=None, aujourdhui=None):
    """Saute l'occurrence ouverte d'une série : elle est abandonnée et la suivante naît (400 si la tâche
    ne se répète pas). Déjà close : rien ne bouge."""
    maintenant, aujourdhui = maintenant or timezone.now(), aujourdhui or timezone.localdate()
    with transaction.atomic():
        t = tache_du_compte(user, pk, verrou=True)
        if t.recurrence_id is None:
            raise serializers.ValidationError({'recurrence': [MESSAGE_PAS_RECURRENTE]})
        if t.statut not in OUVERTES:
            return ResultatEcriture(t)
        ops = []
        _clore(user, t, StatutTache.ANNULE, maintenant, ops, enfants=False)
        suivante = _fin_de_serie(user, t, maintenant, aujourdhui, ops, apres_fait=False)
        message = 'Sautée'
        if suivante is not None:
            message += f' · prochaine {format_jour(suivante.jour_prevu, aujourdhui)}'
        geste = enregistrer_geste(user, 'terminaison', message, ops)
    return ResultatEcriture(t, geste, suivante=suivante)


def _supprimer_la_suivante(user, t, ops):
    """Rouvrir supprime l'occurrence née de la clôture si personne n'y a touché (invariant 5)."""
    if t.recurrence_id is None or t.occurrence_du is None:
        return
    suivante = (taches_de(user).select_for_update()
                .filter(recurrence_id=t.recurrence_id, statut__in=OUVERTES, occurrence_du__gt=t.occurrence_du)
                .order_by('occurrence_du').first())
    if suivante is not None and suivante.lock_version <= VERSION_OCCURRENCE_NEUVE:
        suivante.soft_delete(user, record=False)
        ops.append(op_suppression_douce('tache', suivante))


def rouvrir_tache(user, pk, *, maintenant=None):
    """Décoche : `fait_le` et `annule_le` repartent à nul ; l'occurrence suivante intacte disparaît."""
    maintenant = maintenant or timezone.now()
    with transaction.atomic():
        t = tache_du_compte(user, pk, verrou=True)
        if t.statut in OUVERTES:
            return ResultatEcriture(t)
        ops = []
        _poser_statut(t, StatutTache.A_FAIRE, maintenant, ops)
        _supprimer_la_suivante(user, t, ops)
        geste = enregistrer_geste(user, 'reouverture', 'Rouverte', ops)
    return ResultatEcriture(t, geste)


def _attente(valeur):
    texte = str(valeur or '').strip()
    if not texte:
        raise serializers.ValidationError({'en_attente_de': [MESSAGE_ATTENTE_VIDE]})
    if len(texte) > 200:
        raise serializers.ValidationError({'en_attente_de': [MESSAGE_ATTENTE_LONGUE]})
    return texte


def attendre_tache(user, pk, texte):
    """« En attente de… » quelqu'un ou quelque chose (une autre tâche passe par `PATCH bloquee_par_id`)."""
    texte = _attente(texte)
    with transaction.atomic():
        t = tache_du_compte(user, pk, verrou=True)
        if t.statut not in OUVERTES:
            raise serializers.ValidationError({'statut': [MESSAGE_VALEUR_INCONNUE]})
        avant = {'statut': t.statut, 'en_attente_de': t.en_attente_de}
        t.statut, t.en_attente_de = StatutTache.EN_ATTENTE, texte
        t.save(update_fields=['statut', 'en_attente_de', 'updated_at'])
        ops = [op_champ('tache', t, champ, valeur) for champ, valeur in avant.items()
               if getattr(t, champ) != valeur]
        geste = enregistrer_geste(user, 'modification', f'En attente de : {texte}', ops) if ops else None
    return ResultatEcriture(t, geste)


def recevoir_tache(user, pk):
    """« Reçu » : la tâche en attente redevient à faire (`en_attente_de` vidé)."""
    with transaction.atomic():
        t = tache_du_compte(user, pk, verrou=True)
        if t.statut != StatutTache.EN_ATTENTE:
            return ResultatEcriture(t)
        avant = {'statut': t.statut, 'en_attente_de': t.en_attente_de}
        t.statut, t.en_attente_de = StatutTache.A_FAIRE, ''
        t.save(update_fields=['statut', 'en_attente_de', 'updated_at'])
        ops = [op_champ('tache', t, champ, valeur) for champ, valeur in avant.items()]
        geste = enregistrer_geste(user, 'modification', 'Reçue', ops)
    return ResultatEcriture(t, geste)


def _jour_a_poser(t, choix, jour, aujourdhui):
    """`(jour_prevu, quelque_jour)` d'une décision de `trancher` (regles.md §4.3)."""
    if choix == 'aujourdhui':
        return aujourdhui, False
    if choix == 'garder':
        return (t.jour_prevu if t.jour_prevu is not None and t.jour_prevu >= aujourdhui else aujourdhui), False
    if choix == 'jour':
        if jour is None:
            raise serializers.ValidationError({'jour': [MESSAGE_JOUR_REQUIS]})
        return jour, False
    return None, True


def _message_tranche(choix, t, aujourdhui):
    if choix == 'aujourdhui':
        return "Mise à aujourd'hui"
    if choix == 'un_jour':
        return 'En réserve'
    return f'Prévue {format_jour(t.jour_prevu, aujourdhui)}'


def trancher_tache(user, pk, choix, jour=None, *, maintenant=None, aujourdhui=None):
    """« À revoir » : `aujourdhui`, `garder`, `jour` (une date), `un_jour` (En réserve) ou `abandonner`.
    `aujourdhui`, `garder` et `jour` posent `reports_tranches = reports` : la question ne revient que
    3 reports plus tard (invariant 4). Un seul geste."""
    if choix not in CHOIX_TRANCHER:
        raise serializers.ValidationError({'choix': [MESSAGE_VALEUR_INCONNUE]})
    maintenant, aujourdhui = maintenant or timezone.now(), aujourdhui or timezone.localdate()
    with transaction.atomic():
        t = tache_du_compte(user, pk, verrou=True)
        ops = []
        if choix == 'abandonner':
            _clore(user, t, StatutTache.ANNULE, maintenant, ops, enfants=False)
            return ResultatEcriture(t, enregistrer_geste(user, 'decision', 'Abandonnée', ops))
        jour_a_poser, reserve = _jour_a_poser(t, choix, jour, aujourdhui)
        t = planifier(t, acteur=user, jour_prevu=jour_a_poser, quelque_jour=reserve, collecte=ops).tache
        if choix != 'un_jour' and t.reports_tranches != t.reports:
            avant = t.reports_tranches
            t.reports_tranches = t.reports
            t.save(update_fields=['reports_tranches', 'updated_at'])
            ops.append(op_champ('tache', t, 'reports_tranches', avant))
        geste = enregistrer_geste(user, 'decision', _message_tranche(choix, t, aujourdhui), ops) if ops else None
    return ResultatEcriture(t, geste, tuple(avertissements_du_jour(user, t, aujourdhui)))


def restaurer_tache(user, pk):
    """Restaure une tâche supprimée (et les sous-tâches supprimées avec elle). Si son projet reste
    supprimé, elle revient dans À trier (invariant 27)."""
    with transaction.atomic():
        morte = (Tache.all_objects.select_for_update()
                 .filter(company_id=user.company_id, proprietaire=user, pk=pk, is_deleted=True).first())
        if morte is None:
            raise Http404('Introuvable.')
        groupe = [morte, *Tache.all_objects.select_for_update().filter(
            company_id=user.company_id, proprietaire=user, parent=morte, is_deleted=True,
            deleted_at__gte=morte.deleted_at - FENETRE_SUPPRESSION_GROUPEE,
            deleted_at__lte=morte.deleted_at + FENETRE_SUPPRESSION_GROUPEE)]
        sans_projet = bool(morte.projet_id) and not projets_de(user).filter(pk=morte.projet_id).exists()
        if sans_projet:
            Tache.all_objects.filter(pk__in=[t.pk for t in groupe]).update(projet=None, section=None, triee_le=None)
        ops = []
        for t in groupe:
            t.restore()
            ops.append(op_creation('tache', t))
        message = 'Restaurée dans À trier' if sans_projet else 'Restaurée'
        geste = enregistrer_geste(user, 'restauration', message, ops)
    return ResultatEcriture(tache_du_compte(user, pk), geste)
