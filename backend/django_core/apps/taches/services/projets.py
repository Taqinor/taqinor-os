"""Écritures des projets, de leurs étapes et de la revue (reference/api.md §3.3, §4 ; spec-4 §3).

Chaque écriture enregistre UN geste annulable (`enregistrer_geste`) quand elle en a un à rendre ; les
champs qu'elle touche sont ceux de la liste blanche du §4 de donnees.md. Toute lecture passe par les
sélecteurs du compte (société ET propriétaire) ; un id reçu d'un autre compte répond comme un id inconnu
(`Http404`). `company` et propriétaire ne sont JAMAIS lus du corps.

- `terminer_projet` est l'UNIQUE clôture (invariant 17) : l'écran « Terminer » et la décision « Terminer »
  de la revue passent par elle.
- Une tâche ne change de jour que par `planifier()` (invariant 15) : `decaler_projet` l'appelle.
"""
from dataclasses import dataclass, field

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.http import Http404
from django.utils import timezone
from rest_framework import serializers

from apps.taches.choix import StatutProjet, StatutRappel, StatutTache
from apps.taches.models.projets import Projet
from apps.taches.models.taches import Tache
from apps.taches.saisie.normalisation import cle_nom
from apps.taches.selectors.base import projets_de, rappels_de, taches_de
from apps.taches.services.creation import PAS_RANG, _rang_projet_neuf, couleur_d_office
from apps.taches.services.gestes import enregistrer_geste, op_champ, op_creation, op_suppression_douce
from apps.taches.services.planification import MESSAGE_CONFLIT
from apps.taches.services.rappels import annuler_rappels
from core.conflit_etat import ConflitEtat
from core.verrou_optimiste import CHAMP_VERSION, CODE_CONFLIT_VERSION, ConflitVersion

OUVERTS = (StatutTache.A_FAIRE, StatutTache.EN_ATTENTE)
CODE_NOM_PRIS = 'nom_pris'
MESSAGE_NOM_PRIS = 'Un projet actif porte déjà ce nom.'
MESSAGE_REQUIS = 'Requis.'
MESSAGE_INTROUVABLE = 'Introuvable.'
HORIZON_OUVRES = 400


@dataclass
class ResultatProjet:
    """Ce que rend une écriture de projet : le projet et les compteurs de `projet_ecrit.json`."""
    projet: Projet
    deplacees: int = 0
    restaurees: int = 0
    supprimees: int = 0
    geste: object = None
    creees: list = field(default_factory=list)


# --- Outils communs ------------------------------------------------------------------------------

def _champ_simple(instance, champ):
    return getattr(instance, instance._meta.get_field(champ).attname)


def _ecrire(objet, instance, valeurs, collecte):
    """Pose `valeurs` (`{champ: valeur}` ; une clé étrangère par son id) sur `instance`, l'enregistre et
    ajoute à `collecte` une opération par champ qui a changé."""
    avant = {champ: _champ_simple(instance, champ) for champ in valeurs}
    changes = [champ for champ, valeur in valeurs.items() if avant[champ] != valeur]
    if not changes:
        return False
    for champ in changes:
        setattr(instance, instance._meta.get_field(champ).attname, valeurs[champ])
    colonnes = list(changes)
    if any(f.name == 'updated_at' for f in instance._meta.concrete_fields):
        colonnes.append('updated_at')
    instance.save(update_fields=colonnes)
    collecte.extend(op_champ(objet, instance, champ, avant[champ]) for champ in changes)
    return True


def _verrouiller_projet(user, pk, version=None):
    """Le projet vivant `pk` de `user`, relu sous verrou ; `version` périmée → 409 `conflit_version`."""
    projet = projets_de(user).select_for_update().filter(pk=pk).first()
    if projet is None:
        raise Http404(MESSAGE_INTROUVABLE)
    if version is not None and projet.lock_version != int(version):
        exc = ConflitVersion({'detail': MESSAGE_CONFLIT, 'code': CODE_CONFLIT_VERSION,
                              CHAMP_VERSION: projet.lock_version, 'actuel': {'id': projet.pk}})
        exc.projet = projet  # la vue remplace `actuel` par la forme PROJET complète
        raise exc
    return projet


def _nom_pris(nom):
    return serializers.ValidationError({'nom': [f'Un projet « {nom} » existe déjà.']})


def _geste(user, type_, message, ops):
    return enregistrer_geste(user, type_, message, ops) if ops else None


# --- Créer, modifier -----------------------------------------------------------------------------

def creer_projet(user, *, nom, priorite=0, couleur=None, icone='', objectif='', domaine=''):
    """Crée un projet neuf (couleur d'office, rang au milieu de sa priorité) ; nom pris → 400."""
    cle = cle_nom(nom)
    with transaction.atomic():
        if projets_de(user).filter(nom_cle=cle).exists():
            raise _nom_pris(nom)
        try:
            with transaction.atomic():
                projet = Projet.objects.create(
                    company_id=user.company_id, proprietaire=user, nom=nom, priorite=priorite,
                    couleur=couleur or couleur_d_office(user), icone=icone, objectif=objectif,
                    domaine=domaine, rang=_rang_projet_neuf(user, priorite))
        except IntegrityError:  # deux envois qui se croisent : le second voit la contrainte
            raise _nom_pris(nom)
        geste = enregistrer_geste(user, 'creation', 'Projet créé', [op_creation('projet', projet)])
    return ResultatProjet(projet, geste=geste)


def _statut_de(projet, statut):
    """Valeurs à poser pour un changement de statut par PATCH (sortir de `termine` = rouvrir)."""
    valeurs = {'statut': statut, 'statut_depuis': timezone.now()}
    if projet.statut == StatutProjet.TERMINE:
        valeurs.update(termine_le=None, issue='')
    return valeurs


def modifier_projet(user, projet_id, donnees, *, version):
    """PATCH d'un projet : les champs reçus seuls, sous verrou ; `lock_version` périmée → 409."""
    donnees = dict(donnees)
    with transaction.atomic():
        projet = _verrouiller_projet(user, projet_id, version)
        valeurs = {c: v for c, v in donnees.items() if c not in ('statut', 'affichage')}
        if 'statut' in donnees and donnees['statut'] != projet.statut:
            valeurs.update(_statut_de(projet, donnees['statut']))
        if 'affichage' in donnees:
            valeurs['affichage'] = {**(projet.affichage or {}), **donnees['affichage']}
        if 'nom' in valeurs and cle_nom(valeurs['nom']) != projet.nom_cle \
                and projets_de(user).filter(nom_cle=cle_nom(valeurs['nom'])).exclude(pk=projet.pk).exists():
            raise _nom_pris(valeurs['nom'])
        try:
            with transaction.atomic():
                _ecrire('projet', projet, valeurs, [])
        except IntegrityError:
            raise _nom_pris(valeurs.get('nom', projet.nom))
    return projet


# --- Supprimer, restaurer ------------------------------------------------------------------------

def _annuler_les_rappels(user, taches, ops):
    """Invariant 19 : ses rappels en attente passent `annule` (une opération annulable chacun)."""
    ids = set(rappels_de(user).filter(tache__in=taches, statut=StatutRappel.EN_ATTENTE)
              .values_list('tache_id', flat=True))
    for tache in taches:
        if tache.pk in ids:
            annuler_rappels(tache, ops)


def supprimer_projet(user, projet_id):
    """Supprime le projet ET ses tâches vivantes en UN geste (invariant 27) ; `supprimees` = leur nombre."""
    with transaction.atomic():
        projet = _verrouiller_projet(user, projet_id)
        taches = list(taches_de(user).select_for_update().filter(projet=projet))
        ops = []
        _annuler_les_rappels(user, taches, ops)
        projet.soft_delete(user, record=False)
        ops.extend(op_suppression_douce('tache', t) for t in taches)
        Tache.all_objects.filter(pk__in=[t.pk for t in taches]).update(
            is_deleted=True, deleted_at=projet.deleted_at, deleted_by=user, updated_at=projet.deleted_at)
        ops.append(op_suppression_douce('projet', projet))
        geste = enregistrer_geste(user, 'suppression', 'Projet supprimé', ops)
    return ResultatProjet(projet, supprimees=len(taches), geste=geste)


def restaurer_projet(user, projet_id):
    """Rend le projet supprimé et les tâches supprimées AVEC lui (même instant) ; nom repris → 409."""
    with transaction.atomic():
        projet = (Projet.all_objects.select_for_update()
                  .filter(company_id=user.company_id, proprietaire=user, pk=projet_id).first())
        if projet is None:
            raise Http404(MESSAGE_INTROUVABLE)
        if not projet.is_deleted:
            return ResultatProjet(projet)
        if projets_de(user).filter(nom_cle=projet.nom_cle).exists():
            raise ConflitEtat({'detail': MESSAGE_NOM_PRIS, 'code': CODE_NOM_PRIS})
        quand = projet.deleted_at
        projet.restore()
        nombre = Tache.all_objects.filter(projet=projet, is_deleted=True, deleted_at=quand).update(
            is_deleted=False, deleted_at=None, deleted_by=None, updated_at=timezone.now())
    return ResultatProjet(projet, restaurees=nombre)


# --- Terminer, rouvrir ---------------------------------------------------------------------------

def _cible_de_deplacement(user, projet, projet_cible_id):
    cible = projets_de(user).filter(pk=projet_cible_id).exclude(pk=projet.pk).first() \
        if projet_cible_id is not None else None
    if cible is None:
        raise serializers.ValidationError({'projet_cible_id': ['Projet inexistant.']})
    return cible


def _tache_suivante_rang(user, projet_cible):
    """Dernier `rang_projet` de la liste (le projet, ou « À trier » sans projet)."""
    return taches_de(user).filter(projet=projet_cible, parent__isnull=True).aggregate(
        m=Max('rang_projet'))['m'] or 0


def _vers_une_liste(user, taches, cible, ops):
    """Remet `taches` dans `cible` (un projet) ou dans « À trier » (`None`), à la fin de sa liste."""
    maintenant = timezone.now()
    rang = _tache_suivante_rang(user, cible)
    for tache in sorted(taches, key=lambda t: (t.rang_projet is None, t.rang_projet, t.pk)):
        valeurs = {'projet': cible.pk if cible else None, 'section': None}
        if tache.parent_id is None:
            rang += PAS_RANG
            valeurs['rang_projet'] = rang
            if cible is not None and tache.triee_le is None:
                valeurs['triee_le'] = maintenant
            if cible is None and tache.jour_prevu is None and not tache.quelque_jour:
                valeurs['triee_le'] = None  # À trier : ni projet, ni jour
        _ecrire('tache', tache, valeurs, ops)


def _abandonner(user, taches, ops):
    maintenant = timezone.now()
    for tache in taches:
        _ecrire('tache', tache, {'statut': StatutTache.ANNULE, 'annule_le': maintenant}, ops)
    _annuler_les_rappels(user, taches, ops)


def _a_traiter(user, projet):
    """(ouvertes, suivent) : les tâches ouvertes du projet, et leurs sous-tâches non ouvertes qui les suivent."""
    ouvertes = list(taches_de(user).select_for_update().filter(projet=projet, statut__in=OUVERTS))
    ids = [t.pk for t in ouvertes if t.parent_id is None]
    suivent = list(taches_de(user).select_for_update().filter(parent__in=ids).exclude(statut__in=OUVERTS))
    return ouvertes, suivent


def terminer_projet(user, projet_id, *, issue, bilan='', taches_ouvertes='', projet_cible_id=None):
    """Clôt le projet (`termine`, `termine_le`, `issue`, `bilan`) et règle le sort de ses tâches ouvertes
    (`boite` : À trier · `annuler` : abandonnées · `deplacer` : vers `projet_cible_id`). Déjà terminé :
    rien à faire. UN geste `terminaison`."""
    with transaction.atomic():
        projet = _verrouiller_projet(user, projet_id)
        if projet.statut == StatutProjet.TERMINE:
            return ResultatProjet(projet)
        ouvertes, suivent = _a_traiter(user, projet)
        if ouvertes and not taches_ouvertes:
            raise serializers.ValidationError({'taches_ouvertes': [MESSAGE_REQUIS]})
        ops, deplacees = [], 0
        if ouvertes and taches_ouvertes == 'annuler':
            _abandonner(user, ouvertes, ops)
        elif ouvertes:
            cible = _cible_de_deplacement(user, projet, projet_cible_id) if taches_ouvertes == 'deplacer' else None
            _vers_une_liste(user, ouvertes + suivent, cible, ops)
            deplacees = len(ouvertes) + len(suivent)
        maintenant = timezone.now()
        _ecrire('projet', projet, {'statut': StatutProjet.TERMINE, 'statut_depuis': maintenant,
                                   'termine_le': maintenant, 'issue': issue, 'bilan': bilan}, ops)
        geste = enregistrer_geste(user, 'terminaison', 'Projet terminé', ops)
    return ResultatProjet(projet, deplacees=deplacees, geste=geste)


def rouvrir_projet(user, projet_id):
    """Terminé ou archivé → actif ; l'issue est vidée, le bilan gardé. Déjà ouvert : rien à faire."""
    with transaction.atomic():
        projet = _verrouiller_projet(user, projet_id)
        if projet.statut not in (StatutProjet.TERMINE, StatutProjet.ARCHIVE):
            return ResultatProjet(projet)
        ops = []
        _ecrire('projet', projet, {'statut': StatutProjet.ACTIF, 'statut_depuis': timezone.now(),
                                   'termine_le': None, 'issue': ''}, ops)
        geste = enregistrer_geste(user, 'reouverture', 'Projet rouvert', ops)
    return ResultatProjet(projet, geste=geste)


# --- Ordre ---------------------------------------------------------------------------------------

def _renumeroter(elements):
    """`{pk: rang}` : `elements` (dans l'ordre voulu) numérotés par pas de 1 024."""
    return {pk: (rang + 1) * PAS_RANG for rang, pk in enumerate(elements)}


def _rangs_apres_insertion(ordre, pk, avant_id, apres_id):
    """`ordre` : `[(pk, rang)]` SANS l'élément déplacé. Rend `{pk: rang}` des lignes à écrire : seul
    l'élément déplacé quand il reste de la place entre ses voisins, sinon toute la liste renumérotée."""
    ids = [i for i, _ in ordre]
    repere = avant_id if avant_id is not None else apres_id
    if repere is None:
        raise serializers.ValidationError({'avant_id': [MESSAGE_REQUIS]})
    if repere not in ids:
        raise Http404(MESSAGE_INTROUVABLE)
    place = ids.index(repere) + (0 if avant_id is not None else 1)
    precedent = ordre[place - 1][1] if place > 0 else None
    suivant = ordre[place][1] if place < len(ordre) else None
    if precedent is None and suivant is None:
        return {pk: 0}
    if precedent is None:
        return {pk: suivant - PAS_RANG}
    if suivant is None:
        return {pk: precedent + PAS_RANG}
    milieu = (precedent + suivant) // 2
    if precedent < milieu < suivant:
        return {pk: milieu}
    return _renumeroter(ids[:place] + [pk] + ids[place:])


def _ecrire_rangs(modele, rangs):
    for pk, rang in rangs.items():
        modele.objects.filter(pk=pk).update(rang=rang)


def reordonner_projet(user, projet_id, *, avant_id=None, apres_id=None):
    """Place le projet juste avant `avant_id` ou juste après `apres_id` (« Mettre en haut » : avant le
    premier). Aucun geste (api.md §0)."""
    with transaction.atomic():
        projet = _verrouiller_projet(user, projet_id)
        ordre = list(projets_de(user).exclude(pk=projet.pk).order_by('rang', 'id').values_list('pk', 'rang'))
        _ecrire_rangs(Projet, _rangs_apres_insertion(ordre, projet.pk, avant_id, apres_id))


def trier_par_priorite(user):
    """Renumérote tous les projets par priorité décroissante, puis rang (une fois, jamais silencieux)."""
    with transaction.atomic():
        projets = list(projets_de(user).select_for_update().order_by('-priorite', 'rang', 'id'))
        _ecrire_rangs(Projet, _renumeroter([p.pk for p in projets]))
