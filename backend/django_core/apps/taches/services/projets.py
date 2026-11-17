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
from django.http import Http404
from django.utils import timezone
from rest_framework import serializers

from apps.taches.choix import StatutProjet, StatutRappel, StatutTache
from apps.taches.models.projets import Projet
from apps.taches.models.taches import Tache
from apps.taches.saisie.normalisation import cle_nom
from apps.taches.selectors.base import projets_de, rappels_de, taches_de
from apps.taches.services.creation import _rang_projet_neuf, couleur_d_office
from apps.taches.services.gestes import enregistrer_geste, op_champ, op_creation, op_suppression_douce
from apps.taches.services.planification import MESSAGE_CONFLIT
from apps.taches.services.rappels import annuler_rappels
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
