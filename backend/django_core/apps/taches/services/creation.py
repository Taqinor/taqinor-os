"""Le SEUL créateur de tâches (reference/donnees.md §5 « Signatures fixées », invariants 1, 5, 9, 29, 32).

`creer_taches(user, lignes, *, source, porte, …)` crée en UNE transaction (tout ou rien) une tâche par
LIGNE (`api.md` §4, déjà validée par la vue) :

- idempotence par `client_id` : lu d'abord parmi TOUTES les tâches (supprimées comprises, `all_objects`),
  puis, si deux envois se croisent, l'`IntegrityError` de `taches_tache_cli_uniq` est relue : la ligne
  va dans `deja_creees`, jamais en double ;
- tout identifiant reçu (projet, étape, parent, étiquette, récurrence, activité, lien ERP) est revérifié
  « même société ET même propriétaire » (invariant 9) ;
- `triee_le` = maintenant dès qu'un projet, un jour ou « En réserve » est reconnu (invariant 1) ; un
  rappel posé sans jour donne son jour à la tâche ;
- `rang_projet` = dernier du projet (ou des tâches sans projet) + 1 024 (invariant 32) ;
- le jour passe par `planifier()` (jamais écrit ici), sans report ;
- `ReglagesRythme` NAÎT ici, à la première tâche créée (invariant 29) ;
- un geste annulable est rendu (sauf portes `recurrence` et `modele`, dont l'appelant inclut les
  créations dans SON geste avec `op_creation`).

`couleur_d_office(user)` est la seule règle de couleur d'un projet neuf (aussi pour `POST projets/`).
"""
import datetime
from collections import Counter
from dataclasses import dataclass, field

from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.http import Http404
from django.utils import timezone
from rest_framework import serializers

from apps.notifications.calendar_utils import jours_ouvres_entre
from apps.taches.choix import (
    CibleLiable,
    Couleur,
    Frequence,
    ModeRecurrence,
    Priorite,
    Source,
    StatutProjet,
    StatutTache,
)
from apps.taches.models.projets import Projet, Section
from apps.taches.models.rythme import ReglagesRythme
from apps.taches.models.taches import ElementChecklist, Etiquette, EtiquetteTache, RegleRecurrence, Tache
from apps.taches.moteur.gabarits import format_jour
from apps.taches.moteur.recurrence import premiere_occurrence
from apps.taches.saisie.normalisation import cle_nom
from apps.taches.selectors.base import etiquettes_de, projets_de, sections_de, taches_de
from apps.taches.services import revelations
from apps.taches.services.gestes import enregistrer_geste, op_creation
from apps.taches.services.planification import planifier
from apps.taches.services.rappels import poser_rappel
from core.conflit_etat import ConflitEtat

PORTES = frozenset({'ecran', 'saisie', 'capture', 'assistant', 'suggestion', 'conversion', 'recurrence',
                    'modele', 'lien_activite'})
#: Portes dont l'appelant enregistre lui-même le geste (terminer → suivante ; instancier un modèle).
PORTES_SANS_GESTE = frozenset({'recurrence', 'modele'})
TYPE_GESTE = {'conversion': 'conversion', 'lien_activite': 'lien_activite', 'suggestion': 'suggestion'}
PAS_RANG = 1024
PRIORITE_PROJET_NE = 2  # « Moyenne » : projet né par `#` ou par un collage (A16-M3, A17-M3)
HORIZON_OUVRES = 400
OUVERTS = (StatutTache.A_FAIRE, StatutTache.EN_ATTENTE)

MESSAGE_TITRE_VIDE = 'Le titre est vide une fois la date et le projet retirés.'
MESSAGE_PROJET_INEXISTANT = 'Projet inexistant.'
MESSAGE_LIEN_INTROUVABLE = 'Élément introuvable ou hors de ta portée.'
MESSAGE_LIEN_TYPE = "Ce type d'élément ne peut pas être lié à une tâche."
MESSAGE_DEJA_LIE = 'Cette activité a déjà sa tâche.'  # textes.md §2.16, 409 `deja_lie`


@dataclass(frozen=True)
class ResultatCreation:
    creees: list
    projets_crees: list
    deja_creees: list
    geste: object = None


@dataclass
class _Contexte:
    user: object
    source: str
    porte: str
    maintenant: datetime.datetime
    aujourdhui: datetime.date
    parent: object = None
    activite: object = None
    lien: object = None
    par_ligne: bool = False
    creees: list = field(default_factory=list)
    projets_crees: list = field(default_factory=list)
    deja_creees: list = field(default_factory=list)
    ops_contenants: list = field(default_factory=list)
    ops_taches: list = field(default_factory=list)
    projets_par_cle: dict = field(default_factory=dict)
    rangs: dict = field(default_factory=dict)


# --- Couleur et rang d'un projet neuf -------------------------------------------------------

def couleur_d_office(user):
    """Première couleur de la palette absente des projets ACTIFS, sinon la moins utilisée ; égalité →
    ordre de la palette (regles.md « Projet par la saisie », spec-4 §A, IR6)."""
    utilisees = Counter(projets_de(user).filter(statut=StatutProjet.ACTIF).values_list('couleur', flat=True))
    ordre = list(Couleur.values)
    return min(ordre, key=lambda couleur: (utilisees.get(couleur, 0), ordre.index(couleur)))


def _rang_projet_neuf(user, priorite):
    """Au milieu entre le dernier actif de priorité ≥ `priorite` et le suivant (pas 1 024)."""
    actifs = list(projets_de(user).filter(statut=StatutProjet.ACTIF).order_by('rang', 'id')
                  .values_list('rang', 'priorite'))
    if not actifs:
        return 0
    rangs_ok = [i for i, (_rang, prio) in enumerate(actifs) if prio >= priorite]
    if not rangs_ok:
        return actifs[0][0] - PAS_RANG
    dernier = rangs_ok[-1]
    if dernier + 1 == len(actifs):
        return actifs[dernier][0] + PAS_RANG
    return (actifs[dernier][0] + actifs[dernier + 1][0]) // 2


# --- Lecture des valeurs d'une LIGNE ---------------------------------------------------------

def _date(valeur, champ):
    if valeur is None or valeur == '' or isinstance(valeur, datetime.date):
        return valeur or None
    try:
        return datetime.date.fromisoformat(str(valeur))
    except ValueError:
        raise serializers.ValidationError({champ: ['Date attendue (AAAA-MM-JJ).']})


def _heure(valeur, champ):
    if valeur is None or valeur == '' or isinstance(valeur, datetime.time):
        return valeur or None
    try:
        return datetime.time.fromisoformat(str(valeur))
    except ValueError:
        raise serializers.ValidationError({champ: ['Heure attendue (HH:MM).']})


def _entier(valeur):
    try:
        return int(valeur)
    except (TypeError, ValueError):
        raise Http404('Introuvable.')


def _titre(ligne):
    titre = str(ligne.get('titre') or '').strip()
    if not titre:
        raise serializers.ValidationError({'titre': [MESSAGE_TITRE_VIDE]})
    if len(titre) > 280:
        raise serializers.ValidationError({'titre': ['280 caractères au plus.']})
    return titre


def _champs_simples(ligne):
    """Colonnes posées telles quelles (hors jour, projet, liens) : bornes revérifiées."""
    estimation = ligne.get('estimation_minutes')
    if estimation is not None and not 5 <= int(estimation) <= 960:
        raise serializers.ValidationError({'estimation_minutes': ['Entre 5 et 960 minutes.']})
    priorite = int(ligne.get('priorite') or 0)
    if priorite not in Priorite.values:
        raise serializers.ValidationError({'priorite': ['Valeur inconnue.']})
    echeance = _date(ligne.get('echeance'), 'echeance')
    return {
        'titre': _titre(ligne), 'notes': str(ligne.get('notes') or ''), 'priorite': priorite,
        'echeance': echeance,
        'echeance_heure': _heure(ligne.get('echeance_heure'), 'echeance_heure') if echeance else None,
        'estimation_minutes': int(estimation) if estimation is not None else None,
        'jalon': bool(ligne.get('jalon')), 'confidentiel': bool(ligne.get('confidentiel')),
    }


def _client_id(ligne, client_id, rang, nombre):
    """`client_id` de la ligne, sinon celui de l'envoi (`:<n>` par ligne d'un envoi multi-lignes).
    Une base trop longue est coupée, JAMAIS le suffixe `:<n>` (sinon `:1` et `:10` se confondraient)."""
    propre = ligne.get('client_id')
    if propre:
        return str(propre)[:64]
    if not client_id:
        return None
    if nombre == 1:
        return str(client_id)[:64]
    suffixe = f':{ligne.get("index", rang)}'
    return (str(client_id)[:max(0, 64 - len(suffixe))] + suffixe)[:64]


# --- Identifiants reçus, revérifiés (invariant 9) ---------------------------------------------

def _parent_verifie(user, parent):
    if parent is None:
        return None
    trouve = (taches_de(user).select_related('projet', 'section')
              .filter(pk=_entier(getattr(parent, 'pk', parent))).first())
    if trouve is None or trouve.parent_id is not None:  # un niveau de sous-tâche seulement
        raise Http404('Introuvable.')
    return trouve


def _activite_verifiee(user, activite, nombre):
    """L'activité ERP à convertir ou à lier : de la société, assignée au compte (ou à-faire personnel
    sans assigné qu'il a créé), pas encore liée à une tâche vivante (409 `deja_lie`). L'à-faire
    personnel d'un collègue (XKB4 : invisible au compte, même assigné) est introuvable."""
    if activite is None:
        return None
    if nombre != 1:
        raise ValueError("creer_taches : une activité ne se lie qu'à une seule ligne.")
    a_lui = (activite.assigned_to_id == user.pk
             or (activite.assigned_to_id is None and activite.created_by_id == user.pk))
    prive_d_autrui = activite.personnelle and activite.created_by_id != user.pk
    if activite.company_id != user.company_id or not a_lui or prive_d_autrui:
        raise Http404('Introuvable.')
    if Tache.objects.filter(company_id=user.company_id, activite_origine_id=activite.pk).exists():
        raise ConflitEtat({'detail': MESSAGE_DEJA_LIE, 'code': 'deja_lie'})
    return activite


def _lien_verifie(user, lien):
    """(ContentType, id, libellé) d'une cible ∈ `CibleLiable` VISIBLE par `user` (invariant 23), par la
    porte unique `selectors/liens` (`cible_visible` = un libellé existe) ; refus = introuvable. Le libellé
    est posé à la liaison (comme `lier_activite`), la nuit le revérifie ensuite."""
    if not isinstance(lien, dict) or lien.get('cible') not in CibleLiable.values:
        raise serializers.ValidationError({'lien': [MESSAGE_LIEN_TYPE]})
    try:
        objet_id = int(lien.get('id'))
    except (TypeError, ValueError):
        raise serializers.ValidationError({'lien': [MESSAGE_LIEN_INTROUVABLE]})
    from apps.taches.selectors.liens import libelle_de_cible
    libelle = libelle_de_cible(user, lien['cible'], objet_id)
    if libelle is None:
        raise serializers.ValidationError({'lien': [MESSAGE_LIEN_INTROUVABLE]})
    app_label, modele = lien['cible'].split('.', 1)
    return ContentType.objects.get_by_natural_key(app_label, modele), objet_id, libelle


def _projet_existant(user, projet_id):
    try:
        pk = int(projet_id)
    except (TypeError, ValueError):
        pk = None
    projet = projets_de(user).filter(pk=pk).first() if pk is not None else None
    if projet is None:
        raise serializers.ValidationError({'projet_id': [MESSAGE_PROJET_INEXISTANT]})
    return projet


def _nouveau_projet(ctx, spec):
    """« Nouveau projet : X » : retrouvé par sa clé s'il existe déjà (même envoi ou base), sinon créé
    priorité Moyenne, couleur d'office, rang au milieu de sa priorité."""
    nom = str((spec or {}).get('nom') or '').strip()[:120]
    if not nom:
        raise serializers.ValidationError({'nouveau_projet': ['Requis.']})
    cle = cle_nom(nom)
    if cle in ctx.projets_par_cle:
        return ctx.projets_par_cle[cle]
    user = ctx.user
    projet = projets_de(user).filter(nom_cle=cle).first()
    if projet is None:
        priorite = int(spec.get('priorite', PRIORITE_PROJET_NE))
        projet, cree = Projet.objects.get_or_create(
            company_id=user.company_id, proprietaire=user, nom_cle=cle, is_deleted=False,
            defaults={'nom': nom, 'priorite': priorite, 'couleur': couleur_d_office(user),
                      'rang': _rang_projet_neuf(user, priorite)})
        if cree:
            ctx.projets_crees.append(projet)
            ctx.ops_contenants.append(op_creation('projet', projet))
    ctx.projets_par_cle[cle] = projet
    return projet


def _section(ctx, projet, ligne):
    user = ctx.user
    if ligne.get('section_id') is not None:
        section = (sections_de(user).filter(pk=_entier(ligne['section_id']), projet=projet).first()
                   if projet is not None else None)
        if section is None:
            raise Http404('Introuvable.')
        return section
    nom = str((ligne.get('nouvelle_section') or {}).get('nom') or '').strip()[:120]
    if not nom or projet is None:
        return None
    dernier = Section.objects.filter(projet=projet).aggregate(m=Max('rang'))['m']
    section, cree = Section.objects.get_or_create(
        company_id=user.company_id, projet=projet, nom_cle=cle_nom(nom),
        defaults={'nom': nom, 'rang': (dernier or 0) + PAS_RANG})
    if cree:
        ctx.ops_contenants.append(op_creation('section', section))
    return section


def _projet_et_section(ctx, ligne):
    if ctx.parent is not None:  # invariant 7 : projet et étape du parent
        return ctx.parent.projet, ctx.parent.section
    projet = None
    if ligne.get('projet_id') is not None:
        projet = _projet_existant(ctx.user, ligne['projet_id'])
    elif ligne.get('nouveau_projet'):
        projet = _nouveau_projet(ctx, ligne['nouveau_projet'])
    return projet, _section(ctx, projet, ligne)


# --- Récurrence (invariant 5) -----------------------------------------------------------------

def _est_ouvre_de(user, debut):
    ouvres = jours_ouvres_entre(user.company, debut, debut + datetime.timedelta(days=HORIZON_OUVRES))
    return ouvres.__contains__


def _regle_existante(user, regle_id):
    regle = RegleRecurrence.objects.filter(
        company_id=user.company_id, proprietaire=user, pk=_entier(regle_id), actif=True).first()
    if regle is None:
        raise Http404('Introuvable.')
    if taches_de(user).filter(recurrence=regle, statut__in=OUVERTS).exists():
        raise serializers.ValidationError({'recurrence': ['Une occurrence de cette série est déjà ouverte.']})
    return regle


def _regle_neuve(ctx, spec, jour):
    frequence = spec.get('frequence')
    mode = spec.get('mode') or ModeRecurrence.CALENDRIER
    if frequence not in Frequence.values or mode not in ModeRecurrence.values:
        raise serializers.ValidationError({'recurrence': ['Valeur inconnue.']})
    # Revue F2 #8 : revérifiée comme au PATCH (400 sous le champ, jamais un 500 au calcul de l'occurrence) ;
    # import local, `services.taches` important ce module. `None` = la valeur par défaut, comme ci-dessous.
    from apps.taches.services.taches import _valeurs_regle
    _valeurs_regle({champ: valeur for champ, valeur in spec.items() if valeur is not None}, 'recurrence')
    debut = _date(spec.get('date_debut'), 'recurrence') or jour or ctx.aujourdhui
    return RegleRecurrence.objects.create(
        company_id=ctx.user.company_id, proprietaire=ctx.user, frequence=frequence,
        intervalle=max(1, int(spec.get('intervalle') or 1)),
        jours_semaine=str(spec.get('jours_semaine') or '0000000')[:7],
        jour_du_mois=spec.get('jour_du_mois'), rang_dans_mois=spec.get('rang_dans_mois'),
        mode=mode, date_debut=debut, date_fin=_date(spec.get('date_fin'), 'recurrence'))


def _recurrence(ctx, ligne, jour):
    """(règle, occurrence_du) : une règle NEUVE (dict) a pour première occurrence cette tâche ; une
    règle existante (id, porte `recurrence`) reçoit l'occurrence `occurrence_du` de la ligne."""
    spec = ligne.get('recurrence')
    if spec is None:
        return None, None
    if not isinstance(spec, dict):
        regle = _regle_existante(ctx.user, spec)
        return regle, _date(ligne.get('occurrence_du'), 'occurrence_du') or jour
    regle = _regle_neuve(ctx, spec, jour)
    return regle, premiere_occurrence(regle, _est_ouvre_de(ctx.user, regle.date_debut))


# --- Une ligne ------------------------------------------------------------------------------

def _jour_de(ligne):
    """Le jour prévu : celui de la ligne, sinon le jour d'un rappel absolu (invariant 1)."""
    jour = _date(ligne.get('jour_prevu'), 'jour_prevu')
    rappel = ligne.get('rappel')
    if jour is None and isinstance(rappel, dict) and not rappel.get('ancre'):
        jour = _date(rappel.get('jour'), 'rappel')
    return jour


def _rang_suivant(ctx, projet):
    cle = projet.pk if projet is not None else None
    if cle not in ctx.rangs:
        dernier = taches_de(ctx.user).filter(projet=projet).aggregate(m=Max('rang_projet'))['m']
        ctx.rangs[cle] = dernier or 0
    ctx.rangs[cle] += PAS_RANG
    return ctx.rangs[cle]


def _lien_de_la_ligne(ctx, ligne):
    if ligne.get('lien'):
        return _lien_verifie(ctx.user, ligne['lien'])
    return ctx.lien


def _construire(ctx, ligne, cid, projet, section):
    jour = _jour_de(ligne)
    regle, occurrence = _recurrence(ctx, ligne, jour)
    jour = jour or occurrence
    lien = _lien_de_la_ligne(ctx, ligne)
    trie = projet is not None or jour is not None or bool(ligne.get('quelque_jour'))
    tache = Tache(
        company_id=ctx.user.company_id, proprietaire=ctx.user, projet=projet, section=section,
        parent=ctx.parent, client_id=cid, source=ctx.source, rang_projet=_rang_suivant(ctx, projet),
        triee_le=ctx.maintenant if trie else None, activite_origine=ctx.activite,
        recurrence=regle, occurrence_du=occurrence if regle is not None else None,
        **_champs_simples(ligne))
    if lien is not None:
        tache.content_type, tache.object_id, tache.lien_libelle = lien
        tache.lien_etat, tache.lien_verifie_le = 'ok', ctx.maintenant
    return tache, jour


def _tache_existante(user, cid):
    """Toute tâche du compte à ce `client_id`, SUPPRIMÉE comprise (un rejeu ne ressuscite rien)."""
    return Tache.all_objects.filter(company_id=user.company_id, proprietaire=user, client_id=cid).exists()


def _inserer(ctx, ligne, cid, projet, section):
    """La tâche insérée (sous un point de sauvegarde), ou `None` si un envoi concurrent au même
    `client_id` l'a créée entre la lecture et l'insertion (l'`IntegrityError` est relue)."""
    try:
        with transaction.atomic():
            tache, jour = _construire(ctx, ligne, cid, projet, section)
            tache.save(force_insert=True)
    except IntegrityError:
        if cid and _tache_existante(ctx.user, cid):
            return None, None
        if ctx.activite is not None:
            raise ConflitEtat({'detail': MESSAGE_DEJA_LIE, 'code': 'deja_lie'})
        raise
    return tache, jour


def _etiqueter(ctx, tache, etiquettes):
    vues = set()
    for etiquette in etiquettes or ():
        if isinstance(etiquette, dict):
            nom = str(etiquette.get('nom') or '').strip()[:40]
            if not nom:
                continue
            etiquette, _cree = Etiquette.objects.get_or_create(
                company_id=ctx.user.company_id, proprietaire=ctx.user, nom_cle=cle_nom(nom),
                defaults={'nom': nom})
        else:
            etiquette = etiquettes_de(ctx.user).filter(pk=_entier(etiquette)).first()
            if etiquette is None:
                raise Http404('Introuvable.')
        if etiquette.pk not in vues:
            vues.add(etiquette.pk)
            EtiquetteTache.objects.create(company_id=ctx.user.company_id, tache=tache, etiquette=etiquette)


def _checklist(tache, libelles):
    elements = [
        ElementChecklist(company_id=tache.company_id, tache=tache, libelle=str(libelle)[:255],
                         rang=(rang + 1) * PAS_RANG)
        for rang, libelle in enumerate(libelles or ()) if str(libelle).strip()]
    ElementChecklist.objects.bulk_create(elements)


def _completer(ctx, tache, ligne, jour):
    """Jour (par `planifier`, sans report), étiquettes, check-list, rappel ; rend la tâche relue."""
    if jour is not None or ligne.get('quelque_jour'):
        tache = planifier(tache, acteur=ctx.user, jour_prevu=jour, moment=ligne.get('moment') or '',
                          heure_debut=ligne.get('heure_debut') if jour is not None else None,
                          quelque_jour=bool(ligne.get('quelque_jour')), compter_report=False,
                          collecte=[]).tache
    _etiqueter(ctx, tache, ligne.get('etiquettes'))
    _checklist(tache, ligne.get('checklist'))
    rappel = ligne.get('rappel')
    if isinstance(rappel, dict):
        poser_rappel(tache, acteur=ctx.user, heure=rappel.get('heure'), jour=rappel.get('jour'),
                     ancre=rappel.get('ancre') or '', decalage_jours=rappel.get('decalage_jours') or 0,
                     collecte=ctx.ops_taches)
    return tache


def _creer_ligne(ctx, ligne, cid):
    if cid and _tache_existante(ctx.user, cid):
        ctx.deja_creees.append(cid)
        return
    projet, section = _projet_et_section(ctx, ligne)
    tache, jour = _inserer(ctx, ligne, cid, projet, section)
    if tache is None:
        ctx.deja_creees.append(cid)
        return
    ctx.ops_taches.append(op_creation('tache', tache))
    ctx.creees.append(_completer(ctx, tache, ligne, jour))


def _par_ligne(ctx, rang, ligne, cid):
    """Une ligne ; à la porte `saisie`, l'erreur est rendue sous `lignes.<index>` (erreurs.json)."""
    try:
        _creer_ligne(ctx, ligne, cid)
    except serializers.ValidationError as exc:
        if ctx.porte != 'saisie' and not ctx.par_ligne:
            raise
        raise serializers.ValidationError({'lignes': {str(ligne.get('index', rang)): exc.detail}})


def _message(ctx):
    if ctx.porte == 'lien_activite':
        return "Tâche liée à l'activité"
    if len(ctx.creees) > 1:
        return f'{len(ctx.creees)} tâches créées'
    jour = ctx.creees[0].jour_prevu
    return f'Ajoutée pour {format_jour(jour, ctx.aujourdhui)}' if jour is not None else 'Ajoutée'


def _geste(ctx):
    if not ctx.creees or ctx.porte in PORTES_SANS_GESTE:
        return None
    return enregistrer_geste(ctx.user, TYPE_GESTE.get(ctx.porte, 'creation'), _message(ctx),
                             ctx.ops_contenants + ctx.ops_taches)


def creer_taches(user, lignes, *, source, porte, client_id=None, lien=None, parent=None, activite=None,
                 par_ligne=False):
    """Crée les tâches de `lignes` pour `user` (une transaction, tout ou rien) → `ResultatCreation`
    (`creees`, `projets_crees`, `deja_creees` = `client_id` déjà vus, `geste`)."""
    if porte not in PORTES or source not in Source.values:
        raise ValueError(f'creer_taches : porte {porte!r} ou source {source!r} inconnue')
    lignes = list(lignes or ())
    ctx = _Contexte(user=user, source=source, porte=porte, maintenant=timezone.now(),
                    aujourdhui=timezone.localdate(), par_ligne=par_ligne)
    with transaction.atomic():
        ctx.parent = _parent_verifie(user, parent)
        ctx.activite = _activite_verifiee(user, activite, len(lignes))
        ctx.lien = _lien_verifie(user, lien) if lien else None
        if lignes:
            # AVANT les lignes : le verrou des plafonds de rappels (`services.rappels`) porte sur
            # cette ligne ; absente, deux premiers envois simultanés dépasseraient 100 rappels.
            ReglagesRythme.objects.get_or_create(company_id=user.company_id, proprietaire=user)
        for rang, ligne in enumerate(lignes):
            _par_ligne(ctx, rang, ligne, _client_id(ligne, client_id, rang, len(lignes)))
        if ctx.creees:
            revelations.apres_creation(user, ctx.creees, ctx.projets_crees, porte=porte)
        geste = _geste(ctx)
    return ResultatCreation(ctx.creees, ctx.projets_crees, ctx.deja_creees, geste)
