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
from django.db.models import Case, Count, F, IntegerField, Max, Q, Value, When
from django.db.models.functions import Lower
from django.http import Http404
from django.utils import timezone
from rest_framework import serializers

from apps.taches.choix import (
    CibleLiable, Frequence, LienEtat, ModeRecurrence, Priorite, Source, StatutRappel, StatutTache,
)
from apps.taches.confidentialite import ECRAN, nom_pour
from apps.taches.entrees import MESSAGE_DATE, jour_dans_bornes
from apps.taches.models.projets import Projet
from apps.taches.models.rythme import ReglagesRythme
from apps.taches.models.taches import ElementChecklist, EtiquetteTache, RegleRecurrence, Tache
from apps.taches.moteur.gabarits import format_heure, format_jour
from apps.taches.moteur.recurrence import prochaine_occurrence
from apps.taches.selectors.base import (
    TACHE_CONFIDENTIELLE, etiquettes_de, filtrer_q, gestes_de, jours_travailles_de, projets_de, rappels_de,
    sections_de, taches_de,
)
from apps.taches.selectors.base import normalise_sql
from apps.taches.selectors.liens import cible_visible, libelle_de_cible
from apps.taches.serializers.formes import charger_items
from apps.taches.services.creation import creer_taches
from apps.taches.services.gestes import (
    detacher_d_un_parent_supprime, enregistrer_geste, op_champ, op_creation, op_suppression_douce,
    op_suppression_dure,
)
from apps.taches.services.planification import (
    MESSAGE_CONFLIT, planifier, etat_minimal, avertissements_du_jour,
)
from apps.taches.services.rappels import est_hors_fenetre
from apps.taches.services.rappels import annuler_rappels, recalculer_ancres
from core.verrou_optimiste import CHAMP_VERSION, CODE_CONFLIT_VERSION, ConflitVersion

OUVERTES = (StatutTache.A_FAIRE, StatutTache.EN_ATTENTE)
PAS_RANG = 1024
MAX_MAILLONS = 50
HORIZON_OUVRES = 400
VUES = ('boite', 'quelque_jour')
PERIODES = ('aujourdhui', 'semaine', 'retard')
#: `fait_le` : la plus récemment faite d'abord (« Faites (n) » d'un projet : `?projet=&statut=fait&tri=fait_le`).
TRIS = ('rang', 'echeance', 'priorite', 'fait_le')
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
             'echeance': (F('echeance').asc(nulls_last=True), 'id'),
             'fait_le': (F('fait_le').desc(nulls_last=True), '-id')}[tri]
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


def _lien_courant(tache):
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
    avant = _lien_courant(tache)
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
    if _lien_courant(tache) != avant:
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
        if 'recurrence' in donnees:
            _regle_de_la_tache(edition, donnees['recurrence'], aujourdhui)
        geste = None
        if edition.ecrire:
            tache.save(update_fields=_colonnes(edition.ecrire))
        ops = edition.operations()
        if ops:
            geste = enregistrer_geste(user, 'modification', 'Modifiée', ops)
    return ResultatEcriture(tache, geste, tuple(avertissements_du_jour(user, tache, aujourdhui)))


def avertissement_hors_fenetre(resultat):
    """L'avertissement `hors_fenetre` d'un rappel posé hors des heures de travail de la société : il
    sonnera quand même (textes.md §2.5). `resultat` = `ResultatRappel`."""
    if not resultat.hors_fenetre:
        return ()
    heure = format_heure(resultat.rappel.heure)
    return ({'code': 'hors_fenetre', 'message': f'Hors des heures de travail : il sonnera quand même à {heure}.'},)


def rappel_a_la_creation(user, tache):
    """`(rappel, question_titres)` d'une tâche qui vient d'être créée avec un rappel : le plus proche en
    attente (+ `hors_fenetre`), et vrai tant que le compte n'a pas répondu à la question de l'écran
    verrouillé (A17-T4). `(None, False)` sans rappel."""
    rappel = (rappels_de(user).filter(tache=tache, statut=StatutRappel.EN_ATTENTE)
              .order_by('jour', 'heure', 'pk').first())
    if rappel is None:
        return None, False
    rappel.hors_fenetre = est_hors_fenetre(user.company, rappel.jour, rappel.heure)
    reglages = ReglagesRythme.objects.filter(company_id=user.company_id, proprietaire=user).first()
    return rappel, reglages is None or reglages.titres_notifications_demande_le is None


# --- Supprimer ----------------------------------------------------------------------------------

def supprimer_tache(user, pk):
    """`DELETE taches/{id}/` : la tâche et ses sous-tâches vivantes disparaissent dans UN geste
    (`soft_delete(record=False)`) ; leurs rappels en attente sont annulés (invariant 19)."""
    with transaction.atomic():
        tache = tache_du_compte(user, pk, verrou=True)
        ops = []
        _supprimer_dans(user, tache, ops)
        return enregistrer_geste(user, 'suppression', 'Supprimée', ops)


def _supprimer_dans(user, tache, ops):
    """Supprime `tache` et ses sous-tâches vivantes ; leurs rappels en attente sont annulés."""
    for t in [tache, *taches_de(user).select_for_update().filter(parent=tache)]:
        annuler_rappels(t, collecte=ops)
        t.soft_delete(user, record=False)
        ops.append(op_suppression_douce('tache', t))


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
        suivante = _terminer_dans(user, t, maintenant, aujourdhui, ops)
        message = 'Faite'
        if suivante is not None:
            message += f' · prochaine {format_jour(suivante.jour_prevu, aujourdhui)}'
        geste = enregistrer_geste(user, 'terminaison', message, ops)
    return ResultatEcriture(t, geste, suivante=suivante)


def _terminer_dans(user, t, maintenant, aujourdhui, ops):
    """Ferme `t` comme fait (sous-tâches ouvertes comprises) et rend l'occurrence suivante née, ou `None`."""
    _clore(user, t, StatutTache.FAIT, maintenant, ops, enfants=True)
    return _fin_de_serie(user, t, maintenant, aujourdhui, ops, apres_fait=True)


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
        detacher_d_un_parent_supprime(morte)
        ops = []
        for t in groupe:
            t.restore()
            ops.append(op_creation('tache', t))
        message = 'Restaurée dans À trier' if sans_projet else 'Restaurée'
        geste = enregistrer_geste(user, 'restauration', message, ops)
    return ResultatEcriture(tache_du_compte(user, pk), geste)


# --- Réordonner, écho de changement ----------------------------------------------------------------

LISTES = ('jour', 'projet')
GESTES_ECHO = ('renommer', 'abandonner', 'supprimer')
MESSAGE_REQUIS = 'Requis.'


def _liste_a_ordonner(user, t, liste):
    """`(queryset, colonne de rang, clé d'ordre de départ)` de la liste où `t` se range : « jour » = les
    tâches ouvertes du même jour prévu (`rang_jour`), « projet » = ses voisines du même projet, de la même
    étape et du même parent (`rang_projet`, puis `id` : invariant 32)."""
    ouvertes = taches_de(user).filter(statut__in=OUVERTES)
    if liste == 'jour':
        if t.jour_prevu is None:
            raise serializers.ValidationError({'liste': [MESSAGE_VALEUR_INCONNUE]})
        qs = ouvertes.filter(parent__isnull=True, jour_prevu=t.jour_prevu)
        return qs, 'rang_jour', lambda x: (x.rang_jour is None, x.rang_jour or 0,
                                           x.heure_debut or datetime.time.max, -x.priorite, x.pk)
    qs = ouvertes.filter(projet_id=t.projet_id, section_id=t.section_id, parent_id=t.parent_id)
    return qs, 'rang_projet', lambda x: (x.rang_projet is None, x.rang_projet or 0, x.pk)


def _voisin(user, pk, ids, nom):
    """Le voisin `pk` (du compte, sinon 404) qui doit figurer dans la liste ordonnée (sinon 400)."""
    if pk is None:
        return None
    voisin = tache_du_compte(user, pk)
    if voisin.pk not in ids:
        raise serializers.ValidationError({nom: [MESSAGE_VALEUR_INCONNUE]})
    return voisin


def reordonner_tache(user, pk, liste, avant_id=None, apres_id=None):
    """Place `pk` entre ses deux voisins (`avant_id` le précède, `apres_id` le suit) et NUMÉROTE toute la
    liste par pas de 1 024 (invariant 32). Aucun geste ; `lock_version` ne bouge pas."""
    if liste not in LISTES:
        raise serializers.ValidationError({'liste': [MESSAGE_VALEUR_INCONNUE]})
    if avant_id is None and apres_id is None:
        raise serializers.ValidationError({'avant_id': [MESSAGE_REQUIS]})
    with transaction.atomic():
        t = tache_du_compte(user, pk, verrou=True)
        qs, colonne, cle = _liste_a_ordonner(user, t, liste)
        par_id = {x.pk: x for x in qs.select_for_update()}
        par_id.setdefault(t.pk, t)
        ids = [x.pk for x in sorted(par_id.values(), key=cle) if x.pk != t.pk]
        avant, apres = _voisin(user, avant_id, ids, 'avant_id'), _voisin(user, apres_id, ids, 'apres_id')
        ids.insert(ids.index(avant.pk) + 1 if avant is not None else ids.index(apres.pk), t.pk)
        for rang, identifiant in enumerate(ids, start=1):
            setattr(par_id[identifiant], colonne, rang * PAS_RANG)
        Tache.objects.bulk_update(list(par_id.values()), [colonne])  # aucune écriture de `lock_version`


def apercu_changement(user, pk, geste, titre=None, *, usage=ECRAN):
    """L'écho d'un renommage, d'un abandon ou d'une suppression demandés (rien n'est écrit) :
    `{"geste", "avant", "apres"}`. `avant` passe par `nom_pour` : jamais un titre confidentiel à l'assistant."""
    if geste not in GESTES_ECHO:
        raise serializers.ValidationError({'geste': [MESSAGE_VALEUR_INCONNUE]})
    t = tache_du_compte(user, pk)
    apres = _titre(titre) if geste == 'renommer' else None
    return t, {'geste': geste, 'avant': nom_pour(t, usage), 'apres': apres}


# --- Règle de récurrence ----------------------------------------------------------------------------

MESSAGE_FIN_AVANT_DEBUT = 'La date de fin précède la date de début.'
CHAMPS_REGLE = ('frequence', 'intervalle', 'jours_semaine', 'jour_du_mois', 'rang_dans_mois', 'mode',
                'date_debut', 'date_fin')
RANGS_DU_MOIS = (1, 2, 3, 4, -1)


def _date_de_regle(valeur):
    if valeur is None or isinstance(valeur, datetime.date):
        return valeur
    try:
        jour = datetime.date.fromisoformat(str(valeur))
    except ValueError:
        raise ValueError(MESSAGE_DATE)
    if not jour_dans_bornes(jour):
        raise ValueError(MESSAGE_DATE)
    return jour


def _entier_entre(valeur, bas, haut):
    return isinstance(valeur, int) and not isinstance(valeur, bool) and bas <= valeur <= haut


#: champ → la valeur est-elle permise ? (les dates sont lues à part)
CONTROLES_REGLE = {
    'frequence': lambda v: v in Frequence.values,
    'mode': lambda v: v in ModeRecurrence.values,
    'intervalle': lambda v: _entier_entre(v, 1, 99),
    'jours_semaine': lambda v: isinstance(v, str) and len(v) == 7 and set(v) <= {'0', '1'},
    'jour_du_mois': lambda v: v is None or v == -1 or _entier_entre(v, 1, 31),
    'rang_dans_mois': lambda v: v is None or v in RANGS_DU_MOIS,
}


def _controle_regle(champ, valeur):
    """La valeur de `champ` de la règle, ou `ValueError(message)`."""
    if champ in ('date_debut', 'date_fin'):
        return _date_de_regle(valeur)
    if not CONTROLES_REGLE[champ](valeur):
        raise ValueError(MESSAGE_VALEUR_INCONNUE)
    return valeur


def _valeurs_regle(spec, enveloppe=None):
    """Les valeurs REVÉRIFIÉES de `spec` (dict) pour une règle ; 400 sous le champ fautif
    (`{"<champ>": […]}`, ou `{"<enveloppe>": {"<champ>": […]}}`)."""
    if not isinstance(spec, dict):
        raise serializers.ValidationError({enveloppe or 'recurrence': [MESSAGE_VALEUR_INCONNUE]})
    valeurs, erreurs = {}, {}
    for champ in CHAMPS_REGLE:
        if champ not in spec:
            continue
        try:
            valeurs[champ] = _controle_regle(champ, spec[champ])
        except ValueError as exc:
            erreurs[champ] = [str(exc)]
    debut, fin = valeurs.get('date_debut'), valeurs.get('date_fin')
    if not erreurs and debut and fin and fin < debut:
        erreurs['date_fin'] = [MESSAGE_FIN_AVANT_DEBUT]
    if erreurs:
        raise serializers.ValidationError({enveloppe: erreurs} if enveloppe else erreurs)
    return valeurs


def _regle_du_compte(user, pk, *, verrou=False):
    qs = RegleRecurrence.objects.filter(company_id=user.company_id, proprietaire=user)
    regle = (qs.select_for_update() if verrou else qs).filter(pk=pk).first()
    if regle is None:
        raise Http404('Introuvable.')
    return regle


def _appliquer_regle(regle, valeurs, enveloppe=None):
    """Pose `valeurs` sur `regle` ; la fin ne précède jamais le début de la règle obtenue."""
    for champ, valeur in valeurs.items():
        setattr(regle, champ, valeur)
    if regle.date_fin is not None and regle.date_fin < regle.date_debut:
        erreur = {'date_fin': [MESSAGE_FIN_AVANT_DEBUT]}
        raise serializers.ValidationError({enveloppe: erreur} if enveloppe else erreur)


def _premiere_date_de(user, regle, aujourdhui):
    """La première date de la série ≥ aujourd'hui (« Appliquer à l'ouverte »), ou `None` : série arrêtée,
    ou close avant."""
    if not regle.actif:
        return None
    if regle.mode == ModeRecurrence.APRES_FAIT:
        jour = max(regle.date_debut, aujourdhui)
        return None if regle.date_fin is not None and jour > regle.date_fin else jour
    veille = aujourdhui - datetime.timedelta(days=1)
    return prochaine_occurrence(regle, veille, veille, est_ouvre=est_ouvre_de(user, aujourdhui))


def _recaler_l_ouverte(user, ouverte, regle, aujourdhui, ops):
    """L'occurrence ouverte se recale sur la première date de la nouvelle règle ≥ aujourd'hui, sans report
    (`planifier(compter_report=False)`) ; une date déjà prise par une autre occurrence est laissée."""
    jour = _premiere_date_de(user, regle, aujourdhui)
    if jour is None or taches_de(user).filter(recurrence=regle, occurrence_du=jour).exclude(pk=ouverte.pk).exists():
        return
    planifier(ouverte, acteur=user, jour_prevu=jour, moment=ouverte.moment, heure_debut=ouverte.heure_debut,
              compter_report=False, collecte=ops)
    Tache.objects.filter(pk=ouverte.pk).update(occurrence_du=jour)


def _occurrence_de_la_serie(user, regle):
    """L'occurrence OUVERTE de la série (la plus récente), sinon la dernière occurrence ; 404 sans tâche."""
    serie = taches_de(user).filter(recurrence=regle).order_by('-occurrence_du', '-pk')
    ouverte = serie.filter(statut__in=OUVERTES).first()
    tache = ouverte or serie.first()
    if tache is None:
        raise Http404('Introuvable.')
    return tache, ouverte


def modifier_regle(user, regle_id, donnees, *, aujourdhui=None):
    """`PATCH recurrences/{id}/` : modifie la règle (elle vaut pour la SUIVANTE), l'arrête (`actif: false`)
    ou, avec `appliquer_a_l_ouverte`, recale l'occurrence ouverte → `ResultatEcriture` de la série."""
    aujourdhui = aujourdhui or timezone.localdate()
    with transaction.atomic():
        regle = _regle_du_compte(user, regle_id, verrou=True)
        _appliquer_regle(regle, _valeurs_regle(donnees))
        if 'actif' in donnees:
            regle.actif = donnees['actif']
        regle.save()
        tache, ouverte = _occurrence_de_la_serie(user, regle)
        ops = []
        if donnees.get('appliquer_a_l_ouverte') and ouverte is not None:
            _recaler_l_ouverte(user, ouverte, regle, aujourdhui, ops)
        geste = enregistrer_geste(user, 'modification', 'Modifiée', ops) if ops else None
    return ResultatEcriture(tache_du_compte(user, tache.pk), geste)


def _regle_de_la_tache(edition, spec, aujourdhui):
    """`PATCH taches/{id}/ {"recurrence": …}` : `null` détache la règle ; un dict modifie la règle de la
    tâche ou, sans règle, en crée une (`frequence` requise). Hors liste blanche d'annulation (§4)."""
    t, user = edition.tache, edition.user
    if spec is None:
        if t.recurrence_id is not None:
            t.recurrence, t.occurrence_du = None, None
            edition.ecrire |= {'recurrence', 'occurrence_du'}
        return
    valeurs = _valeurs_regle(spec, 'recurrence')
    if t.recurrence_id is not None:
        regle = _regle_du_compte(user, t.recurrence_id, verrou=True)
        _appliquer_regle(regle, valeurs, 'recurrence')
        regle.save()
        return
    if 'frequence' not in valeurs:
        raise serializers.ValidationError({'recurrence': {'frequence': [MESSAGE_REQUIS]}})
    debut = valeurs.get('date_debut') or t.jour_prevu or aujourdhui
    regle = RegleRecurrence(company_id=user.company_id, proprietaire=user, date_debut=debut)
    _appliquer_regle(regle, valeurs, 'recurrence')
    regle.save()
    t.recurrence = regle
    t.occurrence_du = t.jour_prevu or prochaine_occurrence(
        regle, debut - datetime.timedelta(days=1), debut - datetime.timedelta(days=1),
        est_ouvre=est_ouvre_de(user, aujourdhui))
    edition.ecrire |= {'recurrence', 'occurrence_du'}


# --- Lot : une action sur une sélection -------------------------------------------------------------

ACTIONS_LOT = ('deplacer', 'planifier', 'prioriser', 'etiqueter', 'terminer', 'supprimer', 'garder_sans_projet')
MAX_LOT = 200
MESSAGE_LOT_LONG = '200 au plus.'
RAISON_INTROUVABLE = 'introuvable'
RAISON_SOUS_TACHE = 'sous_tache'
RAISON_CLOSE = 'close'
#: Le message du geste d'un lot : (singulier, pluriel) du participe, `{n}` devant.
MOTS_LOT = {
    'deplacer': ('déplacée', 'déplacées'), 'prioriser': ('priorisée', 'priorisées'),
    'etiqueter': ('étiquetée', 'étiquetées'), 'terminer': ('faite', 'faites'),
    'supprimer': ('supprimée', 'supprimées'), 'garder_sans_projet': ('gardée sans projet', 'gardées sans projet'),
}


def _cible_de_deplacement(user, valeurs):
    """`(valeurs communes, par tâche)` d'un `deplacer`, projets REVÉRIFIÉS (400 « Projet inexistant. »
    sous `valeurs`) ; une étape ne se vérifie qu'avec son projet, tâche par tâche."""
    commun = {cle: valeurs[cle] for cle in ('projet_id', 'section_id') if cle in valeurs}
    if 'projet_id' not in commun and 'par_tache' not in valeurs:
        raise serializers.ValidationError({'valeurs': {'projet_id': [MESSAGE_REQUIS]}})
    par_tache = {}
    for cle, cible in (valeurs.get('par_tache') or {}).items():
        try:
            par_tache[int(cle)] = {c: cible[c] for c in ('projet_id', 'section_id') if c in cible}
        except (TypeError, ValueError, AttributeError):
            raise serializers.ValidationError({'valeurs': {'par_tache': [MESSAGE_VALEUR_INCONNUE]}})
    try:
        for projet_id in {c['projet_id'] for c in (commun, *par_tache.values()) if c.get('projet_id') is not None}:
            _projet(user, projet_id)
    except serializers.ValidationError as exc:
        raise serializers.ValidationError({'valeurs': exc.detail})
    return {'commun': commun, 'par_tache': par_tache}


def _ids_etiquettes(user, valeurs, cle):
    ids = valeurs.get(cle) or []
    if not isinstance(ids, list) or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids):
        raise serializers.ValidationError({'valeurs': {cle: [MESSAGE_VALEUR_INCONNUE]}})
    if set(ids) != set(etiquettes_de(user).filter(pk__in=ids).values_list('pk', flat=True)):
        raise Http404('Introuvable.')
    return set(ids)


def _valeurs_du_lot(user, action, valeurs):
    """Les `valeurs` d'une action, revérifiées une fois pour toute la sélection."""
    if action == 'deplacer':
        return _cible_de_deplacement(user, valeurs)
    if action == 'planifier':
        if not valeurs.get('quelque_jour') and valeurs.get('jour_prevu') is None:
            raise serializers.ValidationError({'valeurs': {'jour_prevu': [MESSAGE_REQUIS]}})
        try:
            jour = _date_de_regle(valeurs.get('jour_prevu'))
        except ValueError as exc:
            raise serializers.ValidationError({'valeurs': {'jour_prevu': [str(exc)]}})
        return {'jour_prevu': jour, 'quelque_jour': bool(valeurs.get('quelque_jour'))}
    if action == 'prioriser':
        if valeurs.get('priorite') not in Priorite.values:
            raise serializers.ValidationError({'valeurs': {'priorite': [MESSAGE_VALEUR_INCONNUE]}})
        return {'priorite': valeurs['priorite']}
    if action == 'etiqueter':
        return {'ajouter': _ids_etiquettes(user, valeurs, 'ajouter'),
                'retirer': _ids_etiquettes(user, valeurs, 'retirer')}
    return {}


def _enregistrer(edition):
    if edition.ecrire:
        edition.tache.save(update_fields=_colonnes(edition.ecrire))
    return edition.operations()


def _lot_deplacer(user, t, v, ctx, ops):
    if t.parent_id is not None:
        return RAISON_SOUS_TACHE
    edition = _Edition(user, t)
    try:
        _projet_et_section(edition, v['par_tache'].get(t.pk) or v['commun'])
    except Http404:
        return RAISON_INTROUVABLE
    ops.extend(_enregistrer(edition))
    return None


def _lot_planifier(user, t, v, ctx, ops):
    if t.parent_id is not None:
        return RAISON_SOUS_TACHE
    if t.statut not in OUVERTES:
        return RAISON_CLOSE
    planifier(t, acteur=user, jour_prevu=v['jour_prevu'], quelque_jour=v['quelque_jour'], collecte=ops)
    return None


def _lot_prioriser(user, t, v, ctx, ops):
    edition = _Edition(user, t)
    edition.poser('priorite', v['priorite'])
    ops.extend(_enregistrer(edition))
    return None


def _lot_etiqueter(user, t, v, ctx, ops):
    edition = _Edition(user, t)
    actuelles = {lien.etiquette_id: lien for lien in EtiquetteTache.objects.filter(tache=t)}
    for pk in sorted(v['ajouter'] - set(actuelles)):
        lien = EtiquetteTache.objects.create(company_id=user.company_id, tache=t, etiquette_id=pk)
        edition.ops.append(op_creation('etiquette_tache', lien))
    for pk in sorted(v['retirer'] & set(actuelles)):
        edition.ops.append(op_suppression_dure('etiquette_tache', actuelles[pk], {'tache': t.pk, 'etiquette': pk}))
        actuelles[pk].delete()
    ops.extend(edition.ops)
    return None


def _lot_terminer(user, t, v, ctx, ops):
    if t.statut != StatutTache.FAIT:
        _terminer_dans(user, t, ctx['maintenant'], ctx['aujourdhui'], ops)
    return None


def _lot_supprimer(user, t, v, ctx, ops):
    _supprimer_dans(user, t, ops)
    return None


def _lot_garder_sans_projet(user, t, v, ctx, ops):
    edition = _Edition(user, t)
    edition.poser('triee_le', ctx['maintenant'])
    ops.extend(_enregistrer(edition))
    return None


TRAITEMENTS_LOT = {
    'deplacer': _lot_deplacer, 'planifier': _lot_planifier, 'prioriser': _lot_prioriser,
    'etiqueter': _lot_etiqueter, 'terminer': _lot_terminer, 'supprimer': _lot_supprimer,
    'garder_sans_projet': _lot_garder_sans_projet,
}


def _message_lot(action, n, valeurs, aujourdhui):
    if action == 'planifier':
        if valeurs['quelque_jour']:
            return f'{n} en réserve'
        return f'{n} prévue{"s" if n > 1 else ""} {format_jour(valeurs["jour_prevu"], aujourdhui)}'
    singulier, pluriel = MOTS_LOT[action]
    return f'{n} {pluriel if n > 1 else singulier}'


def _ids_du_lot(ids):
    ids = list(dict.fromkeys(ids or ()))
    if not ids:
        raise serializers.ValidationError({'ids': [MESSAGE_REQUIS]})
    if len(ids) > MAX_LOT:
        raise serializers.ValidationError({'ids': [MESSAGE_LOT_LONG]})
    return ids


def _traiter_le_lot(user, action, ids, valeurs, ctx):
    """`(appliquées, refusées, opérations)` : chaque tâche relue sous verrou, puis refusée avec sa raison
    (`introuvable` : inconnue ou d'un autre compte ; `sous_tache` ; `close`) ou appliquée."""
    par_id = {t.pk: t for t in taches_de(user).select_for_update().filter(pk__in=ids)}
    ops, appliquees, refusees = [], [], []
    for pk in ids:
        t = par_id.get(pk)
        if t is not None:
            t.refresh_from_db()
        raison = RAISON_INTROUVABLE if t is None else (
            None if t.is_deleted else TRAITEMENTS_LOT[action](user, t, valeurs, ctx, ops))
        if raison is None:
            appliquees.append(pk)
        else:
            refusees.append({'id': pk, 'raison': raison})
    return appliquees, refusees, ops


def lot_taches(user, ids, action, valeurs=None, *, maintenant=None, aujourdhui=None):
    """`POST taches/lot/` : applique `action` à `ids` (≤ 200) en UN geste → `{"appliquees", "refusees",
    "geste_id"}` (`lot.json`). Un id étranger est refusé `introuvable` ; une tâche refusée ne bloque pas
    les autres. Les arguments sont revérifiés AVANT d'écrire quoi que ce soit."""
    if action not in ACTIONS_LOT:
        raise serializers.ValidationError({'action': [MESSAGE_VALEUR_INCONNUE]})
    ids = _ids_du_lot(ids)
    valeurs = _valeurs_du_lot(user, action, valeurs or {})
    ctx = {'maintenant': maintenant or timezone.now(), 'aujourdhui': aujourdhui or timezone.localdate()}
    with transaction.atomic():
        appliquees, refusees, ops = _traiter_le_lot(user, action, ids, valeurs, ctx)
        geste = None
        if appliquees and ops:
            message = _message_lot(action, len(appliquees), valeurs, ctx['aujourdhui'])
            geste = enregistrer_geste(user, 'lot', message, ops)
    return {'appliquees': appliquees, 'refusees': refusees, 'geste_id': geste.pk if geste is not None else None}


# --- Check-list --------------------------------------------------------------------------------------

MESSAGE_LIBELLE_VIDE = 'Requis.'
MESSAGE_LIBELLE_LONG = '255 caractères au plus.'


def _libelle(valeur):
    texte = str(valeur or '').strip()
    if not texte:
        raise serializers.ValidationError({'libelle': [MESSAGE_LIBELLE_VIDE]})
    if len(texte) > 255:
        raise serializers.ValidationError({'libelle': [MESSAGE_LIBELLE_LONG]})
    return texte


def _element_du_compte(user, pk, *, verrou=False):
    qs = ElementChecklist.objects.filter(
        company_id=user.company_id, tache__proprietaire=user, tache__is_deleted=False, pk=pk)
    element = (qs.select_for_update() if verrou else qs).select_related('tache').first()
    if element is None:
        raise Http404('Introuvable.')
    return element


def ajouter_element(user, tache_id, libelle):
    """`POST checklist/` : un point en fin de liste (rang + 1 024) ; la tâche doit être au compte (404)."""
    texte = _libelle(libelle)
    with transaction.atomic():
        tache = tache_du_compte(user, tache_id, verrou=True)
        dernier = ElementChecklist.objects.filter(tache=tache).aggregate(m=Max('rang'))['m']
        element = ElementChecklist.objects.create(
            company_id=user.company_id, tache=tache, libelle=texte, rang=(dernier or 0) + PAS_RANG)
        geste = enregistrer_geste(user, 'modification', 'Ajoutée', [op_creation('element_checklist', element)])
    return ResultatEcriture(tache, geste)


def modifier_element(user, pk, donnees, *, maintenant=None):
    """`PATCH checklist/{id}/ {"libelle"?, "fait"?}` : `fait_le` suit `fait`."""
    maintenant = maintenant or timezone.now()
    with transaction.atomic():
        element = _element_du_compte(user, pk, verrou=True)
        avant = {champ: getattr(element, champ) for champ in ('libelle', 'fait', 'fait_le')}
        if 'libelle' in donnees:
            element.libelle = _libelle(donnees['libelle'])
        if donnees.get('fait') is not None and donnees['fait'] != element.fait:
            element.fait, element.fait_le = donnees['fait'], maintenant if donnees['fait'] else None
        ops = [op_champ('element_checklist', element, champ, valeur) for champ, valeur in avant.items()
               if getattr(element, champ) != valeur]
        geste = None
        if ops:
            element.save(update_fields=['libelle', 'fait', 'fait_le', 'updated_at'])
            geste = enregistrer_geste(user, 'modification', 'Modifiée', ops)
    return ResultatEcriture(element.tache, geste)


def retirer_element(user, pk):
    """`DELETE checklist/{id}/` : suppression dure, annulable (le point revient au même rang)."""
    with transaction.atomic():
        element = _element_du_compte(user, pk, verrou=True)
        valeurs = {'tache': element.tache_id, 'libelle': element.libelle, 'fait': element.fait,
                   'fait_le': element.fait_le, 'rang': element.rang}
        op = op_suppression_dure('element_checklist', element, valeurs)
        tache = element.tache
        element.delete()
        geste = enregistrer_geste(user, 'modification', 'Retirée', [op])
    return ResultatEcriture(tache, geste)


def reordonner_element(user, pk, avant_id=None, apres_id=None):
    """`POST checklist/{id}/reordonner/` : le point se place entre ses voisins (`avant_id` le précède,
    `apres_id` le suit) et la check-list est NUMÉROTÉE par pas de 1 024 ; aucun geste."""
    if avant_id is None and apres_id is None:
        raise serializers.ValidationError({'avant_id': [MESSAGE_REQUIS]})
    with transaction.atomic():
        element = _element_du_compte(user, pk, verrou=True)
        par_id = {e.pk: e for e in ElementChecklist.objects.select_for_update().filter(tache=element.tache)}
        ids = [e.pk for e in sorted(par_id.values(), key=lambda e: (e.rang, e.pk)) if e.pk != element.pk]
        for nom, voisin in (('avant_id', avant_id), ('apres_id', apres_id)):
            if voisin is not None:
                _element_du_compte(user, voisin)  # d'un autre compte : 404
                if voisin not in ids:
                    raise serializers.ValidationError({nom: [MESSAGE_VALEUR_INCONNUE]})
        ids.insert(ids.index(avant_id) + 1 if avant_id is not None else ids.index(apres_id), element.pk)
        for rang, identifiant in enumerate(ids, start=1):
            par_id[identifiant].rang = rang * PAS_RANG
        ElementChecklist.objects.bulk_update(list(par_id.values()), ['rang'])


# --- Recherche, supprimées récemment, derniers gestes ------------------------------------------------

LIMITE_RECHERCHE_DEFAUT = 25
LIMITE_RECHERCHE_MAX = 100
FENETRE_CORBEILLE = datetime.timedelta(days=30)
FENETRE_GESTES = datetime.timedelta(days=7)
PLAFOND_LISTE = 200


def _limite(params):
    brut = params.get('limite')
    if brut in (None, ''):
        return LIMITE_RECHERCHE_DEFAUT
    try:
        limite = int(brut)
    except (TypeError, ValueError):
        limite = 0
    if not 1 <= limite <= LIMITE_RECHERCHE_MAX:
        raise serializers.ValidationError({'limite': [MESSAGE_VALEUR_INCONNUE]})
    return limite


def _projets_trouves(user, termes, limite, assistant):
    """Les projets du compte dont le nom porte TOUS les mots (sans accents si la base le permet) ; jamais un
    projet confidentiel pour l'assistant."""
    from apps.stock.selectors import recherche_sans_accents_disponible
    sans_accents = recherche_sans_accents_disponible()
    qs = projets_de(user).alias(_nom_q=normalise_sql(Lower('nom'), sans_accents))
    if assistant:
        qs = qs.filter(confidentiel=False)
    for terme in termes:
        qs = qs.filter(_nom_q__contains=normalise_sql(Value(terme.lower()), sans_accents))
    return list(qs.order_by('rang', 'id')[:limite])


def rechercher(user, params, *, assistant=False):
    """`GET recherche/?q=&limite=` → `(projets, taches)` : les projets et les tâches qui portent TOUS les mots
    (`q` est requis ; `limite` = 25 par défaut, 100 au plus, pour CHAQUE liste). Les tâches ouvertes
    passent avant les closes ; l'assistant ne reçoit ni note ni objet confidentiel."""
    q = str(params.get('q') or '').strip()
    if not q:
        raise serializers.ValidationError({'q': [MESSAGE_REQUIS]})
    limite = _limite(params)
    projets = _projets_trouves(user, q.split(), limite, assistant)
    ouverte_d_abord = Case(When(statut__in=OUVERTES, then=0), default=1, output_field=IntegerField())
    taches = (filtrer_q(taches_de(user), q, assistant=assistant)
              .order_by(ouverte_d_abord, '-updated_at', 'id'))
    return projets, charger_items(taches)[:limite]


def _compteurs_par_projet(user, projets):
    """`{projet_id: {"ouvertes", "faites", "total"}}` des tâches supprimées de chaque projet (une requête)."""
    compteurs = {p.pk: {'ouvertes': 0, 'faites': 0, 'total': 0} for p in projets}
    lignes = (Tache.all_objects.filter(company_id=user.company_id, proprietaire=user, is_deleted=True,
                                       projet__in=projets).values('projet_id', 'statut').annotate(n=Count('pk')))
    for ligne in lignes:
        compteur = compteurs[ligne['projet_id']]
        compteur['total'] += ligne['n']
        if ligne['statut'] in OUVERTES:
            compteur['ouvertes'] += ligne['n']
        elif ligne['statut'] == StatutTache.FAIT:
            compteur['faites'] += ligne['n']
    return compteurs


def supprimees_recentes(user, *, maintenant=None):
    """`GET supprimees/` : ce que le compte a supprimé depuis moins de 30 jours. Un projet supprimé = UNE ligne
    (ses tâches n'y sont pas répétées), une sous-tâche supprimée avec son parent n'a pas sa ligne. Plus
    récent d'abord, 200 lignes au plus par liste. → `(projets, compteurs, taches)`."""
    depuis = (maintenant or timezone.now()) - FENETRE_CORBEILLE
    commun = {'company_id': user.company_id, 'proprietaire': user, 'is_deleted': True}
    projets = list(Projet.all_objects.filter(**commun, deleted_at__gte=depuis)
                   .order_by('-deleted_at', '-pk')[:PLAFOND_LISTE])
    projets_morts = Projet.all_objects.filter(**commun).values('pk')
    taches = (Tache.all_objects.filter(**commun, deleted_at__gte=depuis)
              .exclude(projet__in=projets_morts).exclude(parent__is_deleted=True)
              .order_by('-deleted_at', '-pk'))
    return projets, _compteurs_par_projet(user, projets), charger_items(taches)[:PLAFOND_LISTE]


def derniers_gestes(user, *, maintenant=None):
    """`GET gestes/` : les gestes annulables des 7 derniers jours, le plus récent d'abord (200 au plus)."""
    depuis = (maintenant or timezone.now()) - FENETRE_GESTES
    return list(gestes_de(user).filter(created_at__gte=depuis).order_by('-created_at', '-pk')[:PLAFOND_LISTE])
