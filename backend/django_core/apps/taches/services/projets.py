"""Écritures des projets, de leurs étapes et de la revue (reference/api.md §3.3, §4 ; spec-4 §3).

Chaque écriture enregistre UN geste annulable (`enregistrer_geste`) quand elle en a un à rendre ; les
champs qu'elle touche sont ceux de la liste blanche du §4 de donnees.md. Toute lecture passe par les
sélecteurs du compte (société ET propriétaire) ; un id reçu d'un autre compte répond comme un id inconnu
(`Http404`). `company` et propriétaire ne sont JAMAIS lus du corps.

- `terminer_projet` est l'UNIQUE clôture (invariant 17) : l'écran « Terminer » et la décision « Terminer »
  de la revue passent par elle.
- Une tâche ne change de jour que par `planifier()` (invariant 15) : `decaler_projet` l'appelle.
"""
import datetime
from bisect import bisect_right
from dataclasses import dataclass, field
from types import SimpleNamespace

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.http import Http404
from django.utils import timezone
from rest_framework import serializers

from apps.taches.choix import DecisionRevue, Source, StatutProjet, StatutRappel, StatutTache
from apps.taches.confidentialite import nom_pour
from apps.taches.entrees import MESSAGE_DATE, introuvable, jour_dans_bornes, refus_etat
from apps.taches.models.projets import ModeleProjet, Projet, RevueProjet, Section
from apps.taches.models.taches import Tache
from apps.taches.moteur.decalage import decaler, figer_modele, instancier
from apps.taches.saisie.normalisation import cle_nom
from apps.taches.selectors.base import jours_travailles_de, projets_de, rappels_de, sections_de, taches_de
from apps.taches.selectors.projets import (
    CLE_CONFIDENTIEL, CLE_NON_REPRISES, elements_a_figer, modele_confidentiel, modele_de, modeles_de,
)
from apps.taches.services.creation import PAS_RANG, _rang_projet_neuf, couleur_d_office, creer_taches
from apps.taches.services.gestes import (
    enregistrer_geste, op_champ, op_creation, op_suppression_douce, op_suppression_dure,
)
from apps.taches.services.planification import MESSAGE_CONFLIT, planifier
from apps.taches.services.rappels import annuler_rappels, recalculer_ancres
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
    """Un nom déjà pris est un refus d'ÉTAT (409, le corps garde `{"nom": […]}`) : le schéma ne peut pas dire
    quels noms existent, et un 400 sur un corps conforme rougissait l'api-fuzz (r2)."""
    return refus_etat({'nom': [f'Un projet « {nom} » existe déjà.']})


def _etape_prise(nom):
    return refus_etat({'nom': [f'Une étape « {nom} » existe déjà.']})


def _geste(user, type_, message, ops):
    return enregistrer_geste(user, type_, message, ops) if ops else None


# --- Créer, modifier -----------------------------------------------------------------------------

def creer_projet(user, *, nom, priorite=0, couleur=None, icone='', objectif='', domaine=''):
    """Crée un projet neuf (couleur d'office, rang au milieu de sa priorité) ; nom pris → 400."""
    with transaction.atomic():
        projet = _projet_neuf(user, nom=nom, priorite=priorite, couleur=couleur, icone=icone, objectif=objectif,
                              domaine=domaine)
        geste = enregistrer_geste(user, 'creation', 'Projet créé', [op_creation('projet', projet)])
    return ResultatProjet(projet, geste=geste)


def _projet_neuf(user, *, nom, priorite=0, couleur=None, icone='', objectif='', domaine='', confidentiel=False):
    """Le projet neuf (couleur d'office, rang au milieu de sa priorité), SANS geste : l'appelant en rend un.
    Nom pris → 400, aussi quand deux envois se croisent (la contrainte est relue)."""
    if projets_de(user).filter(nom_cle=cle_nom(nom)).exists():
        raise _nom_pris(nom)
    try:
        with transaction.atomic():
            return Projet.objects.create(
                company_id=user.company_id, proprietaire=user, nom=nom, priorite=priorite,
                couleur=couleur or couleur_d_office(user), icone=icone, objectif=objectif,
                domaine=domaine, confidentiel=confidentiel, rang=_rang_projet_neuf(user, priorite))
    except IntegrityError:  # deux envois qui se croisent : le second voit la contrainte
        raise _nom_pris(nom)


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
        raise introuvable({'projet_cible_id': ['Projet inexistant.']})  # id qui ne désigne rien : 404
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


# --- Étapes (sections) ---------------------------------------------------------------------------

def _section_du_compte(user, pk, *, verrou=False):
    sections = sections_de(user)
    section = (sections.select_for_update() if verrou else sections).select_related('projet').filter(pk=pk).first()
    if section is None:
        raise Http404(MESSAGE_INTROUVABLE)
    return section


def creer_section(user, *, projet_id, nom, date_debut=None, date_fin=None):
    """Ajoute une étape à la fin du projet ; nom repris dans ce projet → 400."""
    with transaction.atomic():
        projet = projets_de(user).select_for_update().filter(pk=projet_id).first()
        if projet is None:  # la ressource parente manque : 404, corps inchangé (règle d'IdInconnu404Mixin)
            raise introuvable({'projet_id': ['Projet inexistant.']})
        if Section.objects.filter(projet=projet, nom_cle=cle_nom(nom)).exists():
            raise _etape_prise(nom)
        dernier = Section.objects.filter(projet=projet).aggregate(m=Max('rang'))['m']
        try:
            with transaction.atomic():
                section = Section.objects.create(
                    company_id=user.company_id, projet=projet, nom=nom, rang=(dernier or 0) + PAS_RANG,
                    date_debut=date_debut, date_fin=date_fin)
        except IntegrityError:
            raise _etape_prise(nom)
        geste = enregistrer_geste(user, 'creation', 'Étape ajoutée', [op_creation('section', section)])
    return section, geste


def modifier_section(user, section_id, donnees):
    """Renomme une étape ou change ses dates (champs reçus seuls)."""
    with transaction.atomic():
        section = _section_du_compte(user, section_id, verrou=True)
        valeurs = dict(donnees)
        if 'nom' in valeurs and cle_nom(valeurs['nom']) != section.nom_cle \
                and Section.objects.filter(projet=section.projet, nom_cle=cle_nom(valeurs['nom'])).exists():
            raise _etape_prise(valeurs['nom'])
        ops = []
        _ecrire('section', section, valeurs, ops)
        geste = _geste(user, 'modification', 'Étape modifiée', ops)
    return section, geste


def supprimer_section(user, section_id):
    """Supprime l'étape ; ses tâches passent « Sans étape » (annulable : elles y retournent)."""
    with transaction.atomic():
        section = _section_du_compte(user, section_id, verrou=True)
        ops = []
        for tache in taches_de(user).select_for_update().filter(section=section):
            _ecrire('tache', tache, {'section': None}, ops)
        valeurs = {'projet': section.projet_id, 'nom': section.nom, 'rang': section.rang,
                   'date_debut': section.date_debut, 'date_fin': section.date_fin}
        ops.append(op_suppression_dure('section', section, valeurs))
        section.delete()
        return enregistrer_geste(user, 'suppression', 'Étape supprimée', ops)


def reordonner_section(user, section_id, *, avant_id=None, apres_id=None):
    """Place l'étape dans l'ordre de son projet. Aucun geste."""
    with transaction.atomic():
        section = _section_du_compte(user, section_id, verrou=True)
        ordre = list(Section.objects.filter(projet=section.projet).exclude(pk=section.pk)
                     .order_by('rang', 'id').values_list('pk', 'rang'))
        _ecrire_rangs(Section, _rangs_apres_insertion(ordre, section.pk, avant_id, apres_id))


# --- Planifier le projet -------------------------------------------------------------------------

def _etapes_du_plan(user, projet, sections, ops):
    """`{nom d'étape: id}` : les étapes du plan, reprises si elles existent, créées sinon."""
    ids = {}
    dernier = Section.objects.filter(projet=projet).aggregate(m=Max('rang'))['m'] or 0
    for bloc in sections:
        nom = bloc.get('nom')
        if not nom or nom in ids:
            continue
        section = Section.objects.filter(projet=projet, nom_cle=cle_nom(nom)).first()
        if section is None:
            dernier += PAS_RANG
            section = Section.objects.create(company_id=user.company_id, projet=projet, nom=nom, rang=dernier)
            ops.append(op_creation('section', section))
        ids[nom] = section.pk
    return ids


def _lignes_du_plan(projet, donnees, etapes, jour):
    """Les LIGNES de `creer_taches` : les tâches de chaque étape, puis les premières actions."""
    lignes, parents = [], []
    for bloc in donnees.get('sections', ()):
        for tache in bloc.get('taches', ()):
            lignes.append({'titre': tache['titre'], 'projet_id': projet.pk, 'section_id': etapes.get(bloc.get('nom')),
                           'jalon': bool(tache.get('jalon'))})
            parents.append(tache.get('sous_taches') or [])
    quand = {'aujourdhui': jour, 'demain': jour + datetime.timedelta(days=1)}
    for action in donnees.get('actions', ()):
        lignes.append({'titre': action['titre'], 'projet_id': projet.pk,
                       'jour_prevu': quand.get(action.get('quand'))})
        parents.append([])
    return lignes, parents


def _creer_le_plan(user, projet, lignes, parents, assistant):
    """Crée tâches puis sous-tâches (même transaction, aucun geste propre : l'appelant en rend UN)."""
    source = Source.ASSISTANT if assistant else Source.MANUEL
    creees = creer_taches(user, lignes, source=source, porte='modele').creees if lignes else []
    tout = list(creees)
    for tache, titres in zip(creees, parents):
        if titres:
            tout += creer_taches(user, [{'titre': t} for t in titres], source=source, porte='modele',
                                 parent=tache).creees
    return tout


def planifier_projet(user, projet_id, donnees, *, version, assistant=False):
    """« Planifier le projet » : objectif, échéance, priorité, risque, étapes, tâches, jalons, premières
    actions — tout ou rien, UN geste (`creation`). `lock_version` périmée → 409. `planification_le` posé."""
    jour = timezone.localdate()
    with transaction.atomic():
        projet = _verrouiller_projet(user, projet_id, version)
        ops = []
        valeurs = {c: donnees[c] for c in ('priorite', 'objectif', 'echeance', 'risque') if c in donnees}
        valeurs['planification_le'] = timezone.now()
        _ecrire('projet', projet, valeurs, ops)
        etapes = _etapes_du_plan(user, projet, donnees.get('sections', ()), ops)
        lignes, parents = _lignes_du_plan(projet, donnees, etapes, jour)
        creees = _creer_le_plan(user, projet, lignes, parents, assistant)
        ops.extend(op_creation('tache', t) for t in creees)
        n = len(creees)
        geste = enregistrer_geste(user, 'creation', f'{n} tâches créées' if n > 1 else 'Ajoutée', ops)
    return ResultatProjet(projet, geste=geste, creees=creees)


# --- Décaler les dates ---------------------------------------------------------------------------

def _dates_du_projet(projet, sections, taches):
    dates = [projet.date_debut, projet.echeance]
    for section in sections:
        dates += [section.date_debut, section.date_fin]
    for tache in taches:
        if tache.statut in OUVERTS:
            dates += [tache.jour_prevu, tache.echeance]
    return [d for d in dates if d is not None]


def _prochain_ouvre(user, dates, delta):
    """`prochain_ouvre(d)` : `d` s'il est travaillé, sinon le prochain jour travaillé (une seule lecture)."""
    bas = min(dates) + datetime.timedelta(days=min(delta, 0))
    haut = max(dates) + datetime.timedelta(days=max(delta, 0) + HORIZON_OUVRES)
    return _prochain_ouvre_entre(user, bas, haut)


def _prochain_ouvre_entre(user, bas, haut):
    """`prochain_ouvre(d)` sur la fenêtre `[bas, haut]` (un seul calendrier lu pour tout le projet)."""
    travailles = sorted(jours_travailles_de(user, bas, haut))

    def prochain(jour):
        place = bisect_right(travailles, jour - datetime.timedelta(days=1))
        return travailles[place] if place < len(travailles) else jour
    return prochain


def _appliquer_decalage(user, projet, sections, taches, changements):
    """Écrit les changements : dates du projet et des étapes, `echeance` des tâches, puis les jours par
    `planifier()` (sans report). Rend les opérations du geste."""
    ops, par_objet = [], {}
    for c in changements:
        par_objet.setdefault((c['objet'], c['id']), {})[c['champ']] = datetime.date.fromisoformat(c['apres'])
    for projet_cible in (projet, *sections):
        objet = 'projet' if isinstance(projet_cible, Projet) else 'section'
        _ecrire(objet, projet_cible, par_objet.get((objet, projet_cible.pk), {}), ops)
    for tache in taches:
        valeurs = par_objet.get(('tache', tache.pk), {})
        if 'echeance' in valeurs and _ecrire('tache', tache, {'echeance': valeurs['echeance']}, ops):
            recalculer_ancres(tache, ops)
        if 'jour_prevu' in valeurs:
            planifier(tache, acteur=user, jour_prevu=valeurs['jour_prevu'], moment=tache.moment,
                      heure_debut=tache.heure_debut, compter_report=False, collecte=ops)
    return ops


class DecalageRefuse(Exception):
    """400 de `decaler/` : `refus` (sous `delta_jours`), l'aperçu titré qu'il AURAIT appliqué
    (`changements`) et les ids des tâches qui passeraient avant aujourd'hui (`avant_aujourdhui`)."""

    def __init__(self, refus, changements, avant_aujourdhui):
        super().__init__(refus)
        self.refus, self.changements, self.avant_aujourdhui = refus, changements, list(avant_aujourdhui)


def _titrer_changements(changements, projet, sections, taches, usage):
    """Chaque ligne de `decalage` reçoit le `titre` de son objet par `nom_pour` (confidentialité
    respectée ; le nom d'une étape d'un projet confidentiel devient « Étape » hors de l'écran, comme
    dans la santé). Les tâches du projet sont déjà lues : projet et parent posés en mémoire, sans requête."""
    par_id = {t.pk: t for t in taches}
    for tache in taches:
        tache.projet = projet
        if tache.parent_id in par_id:
            tache.parent = par_id[tache.parent_id]
    etapes = {s.pk: s for s in sections}
    masquer = usage != 'ecran' and projet.confidentiel

    def titre(ligne):
        if ligne['objet'] == 'tache':
            return nom_pour(par_id[ligne['id']], usage)
        if ligne['objet'] == 'section':
            return 'Étape' if masquer else etapes[ligne['id']].nom
        return nom_pour(projet, usage)
    return [{**ligne, 'titre': titre(ligne)} for ligne in changements]


def decaler_projet(user, projet_id, delta, *, apercu=True, usage='ecran'):
    """Décale de `delta` jours les dates du projet, de ses étapes et de ses tâches ouvertes. `apercu` : rien
    n'est écrit. Refus (une tâche passerait avant aujourd'hui) → `DecalageRefuse` (400, aperçu compris).
    Rend `(changements titrés, geste ou None)`."""
    jour = timezone.localdate()
    with transaction.atomic():
        projet = _verrouiller_projet(user, projet_id)
        sections = list(sections_de(user).filter(projet=projet))
        taches = list(taches_de(user).select_for_update().filter(projet=projet).order_by('id'))
        dates = _dates_du_projet(projet, sections, taches)
        if not dates:
            return [], None
        resultat = decaler(delta, jour, projet, sections, taches, _prochain_ouvre(user, dates, delta))
        if resultat.refus:
            raise DecalageRefuse(resultat.refus, _titrer_changements(resultat.apercu, projet, sections, taches,
                                                                     usage), resultat.avant_aujourdhui)
        changements = _titrer_changements(resultat.changements, projet, sections, taches, usage)
        if apercu or not changements:
            return changements, None
        ops = _appliquer_decalage(user, projet, sections, taches, changements)
        return changements, _geste(user, 'decalage', 'Dates décalées', ops)


# --- Dupliquer, modèles --------------------------------------------------------------------------

MESSAGE_MODELE_PRIS = 'Un modèle « {nom} » existe déjà.'


@dataclass
class ResultatInstance:
    """Ce que rend « instancier » : le plan daté (`apercu` : titre, étapes, tâches, rien d'écrit) et, quand
    `apercu` est faux, le projet créé."""
    plan: dict
    resultat: ResultatProjet = None


def _modele_pris(nom):
    return refus_etat({'nom': [MESSAGE_MODELE_PRIS.format(nom=nom)]})


def _decalages(contenu):
    """Tous les décalages (jours) d'un contenu de modèle, sans les `None`."""
    valeurs = [s.get(c) for s in contenu.get('sections', ()) for c in ('decalage_debut', 'decalage_fin')]
    valeurs += [t.get(c) for t in contenu.get('taches', ()) for c in ('decalage_jour', 'decalage_echeance')]
    return [v for v in valeurs if v is not None]


def _tel_quel(jour):
    return jour


def _hors_plage(champ):
    return serializers.ValidationError({champ: [MESSAGE_DATE]})


def _ecarts_dans_la_plage(date_lancement, decalages):
    """Vrai si `date_lancement` + chaque décalage reste dans la plage acceptée (`entrees.jour_dans_bornes`) —
    jugé AVANT de lire le calendrier : un écart démesuré ne lit jamais des millions de jours."""
    try:
        extremes = [date_lancement + datetime.timedelta(days=d) for d in (min(decalages), max(decalages))]
    except OverflowError:
        return False
    return all(jour_dans_bornes(jour) for jour in extremes)


def _dates_du_plan(plan):
    dates = [s[c] for s in plan['sections'] for c in ('date_debut', 'date_fin')]
    dates += [t[c] for t in plan['taches'] for c in ('jour_prevu', 'echeance')]
    return [datetime.date.fromisoformat(d) for d in dates if d is not None]


def _plan_date(user, contenu, nom, date_lancement, champ):
    """Le plan du moteur `instancier` : chaque date = `date_lancement` + décalage, rectifiée sur un jour
    travaillé du compte (un seul calendrier lu). Une date du plan hors de la plage acceptée (un écart du modèle la
    fait sortir, avant ou après rectification) → 400 sous `champ`, jamais 500 (revue F4 #4)."""
    decalages = _decalages(contenu)
    if decalages:
        if not _ecarts_dans_la_plage(date_lancement, decalages):
            raise _hors_plage(champ)
        bas = date_lancement + datetime.timedelta(days=min(0, min(decalages)))
        haut = date_lancement + datetime.timedelta(days=max(0, max(decalages)) + HORIZON_OUVRES)
        prochain = _prochain_ouvre_entre(user, bas, haut)
    else:  # aucune date à rectifier : le calendrier n'est pas lu
        prochain = _tel_quel
    plan = instancier(contenu, nom, date_lancement, prochain)
    if not all(jour_dans_bornes(jour) for jour in _dates_du_plan(plan)):
        raise _hors_plage(champ)
    return plan


def _jour(texte):
    return datetime.date.fromisoformat(texte) if texte else None


def _etapes_du_modele(user, projet, etapes, ops):
    """Les étapes du plan, créées dans l'ordre du modèle ; rend leurs ids par index."""
    ids = []
    for rang, etape in enumerate(etapes, start=1):
        section = Section.objects.create(
            company_id=user.company_id, projet=projet, nom=etape['nom'], rang=rang * PAS_RANG,
            date_debut=_jour(etape['date_debut']), date_fin=_jour(etape['date_fin']))
        ops.append(op_creation('section', section))
        ids.append(section.pk)
    return ids


def _ligne_du_modele(tache, projet, section_id):
    ligne = {'titre': tache['titre'], 'projet_id': projet.pk, 'priorite': tache['priorite'],
             'jalon': tache['jalon'], 'jour_prevu': tache['jour_prevu'], 'echeance': tache['echeance'],
             'checklist': tache['checklist']}
    if section_id is not None:
        ligne['section_id'] = section_id
    if 'notes' in tache:
        ligne['notes'] = tache['notes']
    return ligne


def _taches_du_modele(user, projet, taches, etapes_ids):
    """Crée les tâches (puis leurs sous-tâches) du plan, dans l'ordre du modèle ; rend `[tâche ou None]` par
    index. Chaque sous-tâche reprend le projet et l'étape de son parent. Les prérequis (`bloquee_par_index`)
    se posent une fois toutes les tâches nées."""
    creees = [None] * len(taches)
    hautes = [i for i, t in enumerate(taches) if t['parent_index'] is None]
    lignes = []
    for i in hautes:
        index = taches[i]['section_index']
        lignes.append(_ligne_du_modele(taches[i], projet, etapes_ids[index] if index is not None else None))
    if lignes:
        for i, tache in zip(hautes, creer_taches(user, lignes, source=Source.MODELE, porte='modele').creees):
            creees[i] = tache
    for i in hautes:
        enfants = [j for j, t in enumerate(taches) if t['parent_index'] == i]
        if enfants and creees[i] is not None:
            nees = creer_taches(user, [_ligne_du_modele(taches[j], projet, None) for j in enfants],
                                source=Source.MODELE, porte='modele', parent=creees[i]).creees
            for j, tache in zip(enfants, nees):
                creees[j] = tache
    for i, t in enumerate(taches):
        cible = t['bloquee_par_index']
        if cible is not None and creees[i] is not None and creees[cible] is not None and cible != i:
            Tache.objects.filter(pk=creees[i].pk).update(bloquee_par_id=creees[cible].pk)
    return creees


def _creer_depuis_le_plan(user, plan, *, confidentiel):
    """Le projet, ses étapes et ses tâches du `plan` (même transaction), UN geste `creation` (« Annuler » =
    suppression douce du projet créé)."""
    with transaction.atomic():
        ops = []
        projet = _projet_neuf(user, nom=plan['projet']['nom'], priorite=plan['projet']['priorite'],
                              objectif=plan['projet']['objectif'], confidentiel=confidentiel)
        ops.append(op_creation('projet', projet))
        etapes_ids = _etapes_du_modele(user, projet, plan['sections'], ops)
        creees = [t for t in _taches_du_modele(user, projet, plan['taches'], etapes_ids) if t is not None]
        ops.extend(op_creation('tache', t) for t in creees)
        geste = enregistrer_geste(user, 'creation', 'Projet créé', ops)
    return ResultatProjet(projet, geste=geste, creees=creees)


def _instancier(user, contenu, nom, date_lancement, *, apercu, confidentiel, champ):
    """Le plan daté ; sans `apercu`, le projet est créé. Un nom de projet pris → 400, aperçu compris ; une date
    hors plage → 400 sous `champ` (le champ de date de la route)."""
    if projets_de(user).filter(nom_cle=cle_nom(nom)).exists():
        raise _nom_pris(nom)
    plan = _plan_date(user, contenu, nom, date_lancement or timezone.localdate(), champ)
    plan[CLE_NON_REPRISES] = contenu.get(CLE_NON_REPRISES, 0)
    if apercu:
        return ResultatInstance(plan)
    return ResultatInstance(plan, _creer_depuis_le_plan(user, plan, confidentiel=confidentiel))


def _contenu_du_projet(user, projet, *, inclure_notes):
    """Le contenu v1 figé du projet, avec sa confidentialité de CET instant (`CLE_CONFIDENTIEL`, revue F4 #1) :
    le modèle la garde, quoi que devienne ensuite le projet ; et le nombre de tâches confidentielles non reprises
    (`CLE_NON_REPRISES`, revue F4 #14)."""
    sections, taches, listes, non_reprises = elements_a_figer(user, projet)
    pures = [SimpleNamespace(
        id=t.pk, parent_id=t.parent_id, statut=t.statut, section_id=t.section_id, titre=t.titre,
        priorite=t.priorite, jalon=t.jalon, jour_prevu=t.jour_prevu, echeance=t.echeance,
        bloquee_par=t.bloquee_par_id, checklist=listes.get(t.pk, []), notes=t.notes) for t in taches]
    contenu = figer_modele(projet, sections, pures, inclure_notes=inclure_notes)
    contenu[CLE_CONFIDENTIEL] = bool(projet.confidentiel)
    contenu[CLE_NON_REPRISES] = non_reprises
    return contenu


def _projet_a_copier(user, projet_id):
    projet = projets_de(user).filter(pk=projet_id).first()
    if projet is None:
        raise Http404(MESSAGE_INTROUVABLE)
    return projet


def dupliquer_projet(user, projet_id, nom, date_debut=None, *, apercu=True):
    """« Dupliquer » : le projet figé (notes comprises) puis instancié à `date_debut` (aujourd'hui sinon) par le
    même moteur que les modèles. Le double d'un projet confidentiel l'est aussi. `apercu` : rien n'est écrit."""
    projet = _projet_a_copier(user, projet_id)
    contenu = _contenu_du_projet(user, projet, inclure_notes=True)
    return _instancier(user, contenu, nom, date_debut, apercu=apercu, confidentiel=projet.confidentiel,
                       champ='date_debut')


def enregistrer_modele(user, projet_id, nom, *, inclure_notes=False):
    """« Enregistrer comme modèle » : fige le projet (notes seulement si `inclure_notes`) ; nom pris → 400."""
    with transaction.atomic():
        projet = _projet_a_copier(user, projet_id)
        if modeles_de(user).filter(nom__iexact=nom).exists():
            raise _modele_pris(nom)
        contenu = _contenu_du_projet(user, projet, inclure_notes=inclure_notes)
        try:
            with transaction.atomic():
                return ModeleProjet.objects.create(
                    company_id=user.company_id, proprietaire=user, nom=nom, contenu=contenu, cree_depuis=projet)
        except IntegrityError:  # deux envois qui se croisent
            raise _modele_pris(nom)


def _modele_du_compte(user, modele_id):
    modele = modele_de(user, modele_id)
    if modele is None:
        raise Http404(MESSAGE_INTROUVABLE)
    return modele


def renommer_modele(user, modele_id, nom):
    """PATCH d'un modèle : son nom seul ; nom pris → 400."""
    with transaction.atomic():
        modele = _modele_du_compte(user, modele_id)
        if modeles_de(user).filter(nom__iexact=nom).exclude(pk=modele.pk).exists():
            raise _modele_pris(nom)
        modele.nom = nom
        try:
            with transaction.atomic():
                modele.save(update_fields=['nom', 'updated_at'])
        except IntegrityError:
            raise _modele_pris(nom)
    return modele


def supprimer_modele(user, modele_id):
    """Supprime le modèle (définitivement : aucun geste annulable) ; les projets qui en sont nés restent."""
    with transaction.atomic():
        _modele_du_compte(user, modele_id).delete()


def instancier_modele(user, modele_id, nom, date_lancement=None, *, apercu=True):
    """« Utiliser un modèle » : `date_lancement` (aujourd'hui sinon) + décalages, rectifiée sur un jour
    travaillé. `apercu` d'abord (rien n'écrit), puis sans `apercu` : le projet est créé (un geste)."""
    modele = _modele_du_compte(user, modele_id)
    return _instancier(user, modele.contenu, nom, date_lancement, apercu=apercu,
                       confidentiel=modele_confidentiel(modele), champ='date_lancement')


# --- Revue de la semaine -------------------------------------------------------------------------

def _autre_focus(user, projet, semaine):
    """Le projet déjà « de la semaine » (autre que `projet`), ou `None` (invariant 25)."""
    revue = (RevueProjet.objects.filter(company_id=user.company_id, proprietaire=user, semaine=semaine, focus=True)
             .exclude(projet=projet).select_related('projet').first())
    return revue.projet if revue is not None else None


def _prochaine_action_du_projet(user, projet, action_id):
    if action_id is None:
        return None
    tache = taches_de(user).filter(pk=action_id, projet=projet).first()
    if tache is None:
        raise Http404(MESSAGE_INTROUVABLE)
    return tache


def _enregistrer_revue(user, projet, semaine, donnees, ops):
    """Crée ou met à jour la `RevueProjet` de la semaine ; une création est annulable."""
    action = _prochaine_action_du_projet(user, projet, donnees.get('prochaine_action_id'))
    revue = RevueProjet.objects.select_for_update().filter(
        company_id=user.company_id, proprietaire=user, projet=projet, semaine=semaine).first()
    fin = semaine + datetime.timedelta(days=6)
    faites = taches_de(user).filter(projet=projet, statut=StatutTache.FAIT,
                                    fait_le__date__range=(semaine, fin)).count()
    champs = {'intention': donnees.get('intention', ''), 'prochaine_action': action,
              'decision': donnees['decision'], 'focus': bool(donnees.get('focus')), 'faites_semaine': faites}
    if revue is None:
        revue = RevueProjet.objects.create(company_id=user.company_id, proprietaire=user, projet=projet,
                                           semaine=semaine, **champs)
        ops.append(op_creation('revue_projet', revue))
    else:
        for champ, valeur in champs.items():
            setattr(revue, champ, valeur)
        revue.save()
    return revue


def decider_revue(user, projet_id, donnees):
    """La décision d'une carte de revue : `garder` ne touche à rien, `pause` met le projet en pause,
    `terminer` passe par `terminer_projet` (exige `issue`), `passe` saute. Un seul projet « de la semaine »."""
    semaine = donnees['semaine'] - datetime.timedelta(days=donnees['semaine'].weekday())
    with transaction.atomic():
        projet = _verrouiller_projet(user, projet_id)
        autre = _autre_focus(user, projet, semaine) if donnees.get('focus') else None
        if autre is not None:
            raise serializers.ValidationError({'focus': [f'Déjà « {autre.nom} » cette semaine.']})
        ops = []
        revue = _enregistrer_revue(user, projet, semaine, donnees, ops)
        geste = None
        if donnees['decision'] == DecisionRevue.PAUSE and projet.statut == StatutProjet.ACTIF:
            _ecrire('projet', projet, {'statut': StatutProjet.EN_PAUSE, 'statut_depuis': timezone.now()}, ops)
        elif donnees['decision'] == DecisionRevue.TERMINER:
            geste = terminer_projet(user, projet.pk, issue=donnees['issue'], taches_ouvertes='boite').geste
            projet.refresh_from_db()
        geste = geste or _geste(user, 'revue', 'Revue enregistrée', ops)
    return revue, projet, geste
