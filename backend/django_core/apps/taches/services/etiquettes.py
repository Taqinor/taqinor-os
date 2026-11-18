"""Étiquettes et vues enregistrées (reference/api.md §3.2, §4 ; donnees.md §2.5, §2.6, §2.16).

Chaque écriture rend son geste annulable (`enregistrer_geste`) ; toute lecture passe par les sélecteurs du
compte (société ET propriétaire) : l'id d'un collègue répond comme un id inconnu (`Http404`).
`company` et propriétaire ne sont JAMAIS lus du corps.

- Étiquette : `nom` ≤ 40, unique par `nom_cle` (« Magasin » et « magasin » sont la même) ; supprimer
  une étiquette la retire de ses tâches, et l'annulation les lui rend (une opération par lien).
- Vue enregistrée : `filtres` à clés FERMÉES (`CLES_FILTRES`), 30 vues au plus ; une clé ou une valeur
  inconnue → 400 nommé `{"filtres": {"<clé>": ["Valeur inconnue."]}}`.
"""
import datetime

from django.db import IntegrityError, transaction
from django.http import Http404
from rest_framework import serializers

from apps.taches.choix import Couleur, Priorite, StatutTache
from apps.taches.models.taches import Etiquette, EtiquetteTache, VueEnregistree
from apps.taches.saisie.normalisation import cle_nom
from apps.taches.selectors.base import etiquettes_de, projets_de, vues_de
from apps.taches.services.gestes import enregistrer_geste, op_champ, op_creation, op_suppression_dure
from apps.taches.services.taches import GROUPES, PERIODES, TRIS

MESSAGE_INTROUVABLE = 'Introuvable.'
MESSAGE_REQUIS = 'Requis.'
MESSAGE_INCONNU = 'Valeur inconnue.'
MESSAGE_NOM_ETIQUETTE_LONG = '40 caractères au plus.'
MESSAGE_NOM_VUE_LONG = '60 caractères au plus.'
MESSAGE_VUES_PLEINES = '30 au plus.'
MESSAGE_PROJET_INEXISTANT = 'Projet inexistant.'
MESSAGE_ETIQUETTE_INEXISTANTE = 'Étiquette inexistante.'
MAX_VUES = 30
PAS_RANG = 1024
#: Les dix clés d'un filtre enregistré (donnees.md §2.16) ; toute autre est refusée.
CLES_FILTRES = ('q', 'projets', 'etiquettes', 'priorite_min', 'statuts', 'periode', 'echeance', 'tri', 'groupe',
                'inclure_faites')
#: Plafonds des valeurs libres (un filtre n'est pas un fourre-tout).
MAX_Q = 200
MAX_IDS = 100


def _nom(valeur, maximum, message_long):
    if valeur is not None and not isinstance(valeur, str):
        raise serializers.ValidationError({'nom': [MESSAGE_INCONNU]})
    nom = (valeur or '').strip()
    if not nom:
        raise serializers.ValidationError({'nom': [MESSAGE_REQUIS]})
    if len(nom) > maximum:
        raise serializers.ValidationError({'nom': [message_long]})
    return nom


# --- Étiquettes ----------------------------------------------------------------------------------

def _etiquette_prise(nom):
    return serializers.ValidationError({'nom': [f'Une étiquette « {nom} » existe déjà.']})


def _couleur(valeur):
    if valeur not in Couleur.values:
        raise serializers.ValidationError({'couleur': [MESSAGE_INCONNU]})
    return valeur


def _etiquette_du_compte(user, pk, *, verrou=False):
    qs = etiquettes_de(user)
    etiquette = (qs.select_for_update() if verrou else qs).filter(pk=pk).first()
    if etiquette is None:
        raise Http404(MESSAGE_INTROUVABLE)
    return etiquette


def creer_etiquette(user, *, nom, couleur=None):
    """Crée l'étiquette de `user` ; un nom déjà pris (même clé) → 400 ; rend `(etiquette, geste)`."""
    nom = _nom(nom, 40, MESSAGE_NOM_ETIQUETTE_LONG)
    champs = {} if couleur in (None, '') else {'couleur': _couleur(couleur)}
    with transaction.atomic():
        if etiquettes_de(user).filter(nom_cle=cle_nom(nom)).exists():
            raise _etiquette_prise(nom)
        try:
            with transaction.atomic():
                etiquette = Etiquette.objects.create(
                    company_id=user.company_id, proprietaire=user, nom=nom, **champs)
        except IntegrityError:  # deux envois qui se croisent : le second voit la contrainte
            raise _etiquette_prise(nom)
        geste = enregistrer_geste(user, 'creation', 'Étiquette créée', [op_creation('etiquette', etiquette)])
    return etiquette, geste


def modifier_etiquette(user, pk, donnees):
    """PATCH : renomme et/ou recolore ; rend `(etiquette, geste)` (geste `None` si rien n'a changé)."""
    with transaction.atomic():
        etiquette = _etiquette_du_compte(user, pk, verrou=True)
        valeurs = {}
        if 'nom' in donnees:
            valeurs['nom'] = _nom(donnees['nom'], 40, MESSAGE_NOM_ETIQUETTE_LONG)
        if 'couleur' in donnees:
            valeurs['couleur'] = _couleur(donnees['couleur'])
        changes = {c: v for c, v in valeurs.items() if getattr(etiquette, c) != v}
        if 'nom' in changes and etiquettes_de(user).filter(nom_cle=cle_nom(changes['nom'])).exclude(
                pk=etiquette.pk).exists():
            raise _etiquette_prise(changes['nom'])
        if not changes:
            return etiquette, None
        avant = {c: getattr(etiquette, c) for c in changes}
        for champ, valeur in changes.items():
            setattr(etiquette, champ, valeur)
        try:
            with transaction.atomic():
                etiquette.save(update_fields=[*changes, 'updated_at'])
        except IntegrityError:
            raise _etiquette_prise(changes.get('nom', etiquette.nom))
        geste = enregistrer_geste(user, 'modification', 'Étiquette modifiée',
                                  [op_champ('etiquette', etiquette, c, avant[c]) for c in changes])
    return etiquette, geste


def supprimer_etiquette(user, pk):
    """DELETE : l'étiquette est retirée de ses tâches (une opération annulable par lien, puis la
    sienne : l'annulation la recrée AVANT de rendre les liens) ; rend le geste."""
    with transaction.atomic():
        etiquette = _etiquette_du_compte(user, pk, verrou=True)
        liens = list(EtiquetteTache.objects.filter(etiquette=etiquette))
        ops = [op_suppression_dure('etiquette_tache', lien, {'tache': lien.tache_id, 'etiquette': etiquette.pk})
               for lien in liens]
        ops.append(op_suppression_dure('etiquette', etiquette, {'nom': etiquette.nom, 'couleur': etiquette.couleur}))
        EtiquetteTache.objects.filter(etiquette=etiquette).delete()
        etiquette.delete()
        return enregistrer_geste(user, 'suppression', 'Étiquette supprimée', ops)


# --- Vues enregistrées ---------------------------------------------------------------------------

def _entier_strict(valeur):
    return isinstance(valeur, int) and not isinstance(valeur, bool)


def _ids_du_compte(valeur, selecteur, user, message):
    """Liste d'ids tous connus du compte (sans doublon)."""
    if not isinstance(valeur, list) or len(valeur) > MAX_IDS or not all(_entier_strict(v) for v in valeur):
        raise ValueError(MESSAGE_INCONNU)
    ids = list(dict.fromkeys(valeur))
    if len(ids) != selecteur(user).filter(pk__in=ids).count():
        raise ValueError(message)
    return ids


def _texte_borne(valeur):
    if not isinstance(valeur, str) or len(valeur) > MAX_Q:
        raise ValueError(MESSAGE_INCONNU)
    return valeur.strip()


def _choix_ferme(permis):
    def lire(valeur):
        if valeur not in permis:
            raise ValueError(MESSAGE_INCONNU)
        return valeur
    return lire


def _date_iso(valeur):
    try:
        return datetime.date.fromisoformat(valeur).isoformat()
    except (TypeError, ValueError):
        raise ValueError(MESSAGE_INCONNU)


def _booleen(valeur):
    if not isinstance(valeur, bool):
        raise ValueError(MESSAGE_INCONNU)
    return valeur


def _priorite(valeur):
    if not _entier_strict(valeur) or valeur not in Priorite.values:
        raise ValueError(MESSAGE_INCONNU)
    return valeur


def _statuts(valeur):
    if not isinstance(valeur, list) or not valeur or not all(v in StatutTache.values for v in valeur):
        raise ValueError(MESSAGE_INCONNU)
    return list(dict.fromkeys(valeur))


def _valider_filtres(user, filtres):
    """`filtres` normalisés (clés fermées, valeurs de même nature que les paramètres de `GET taches/`) ;
    une clé ou une valeur inconnue → 400 `{"filtres": {"<clé>": ["Valeur inconnue."]}}`."""
    if not isinstance(filtres, dict):
        raise serializers.ValidationError({'filtres': [MESSAGE_INCONNU]})
    lecteurs = {
        'q': _texte_borne,
        'projets': lambda v: _ids_du_compte(v, projets_de, user, MESSAGE_PROJET_INEXISTANT),
        'etiquettes': lambda v: _ids_du_compte(v, etiquettes_de, user, MESSAGE_ETIQUETTE_INEXISTANTE),
        'priorite_min': _priorite,
        'statuts': _statuts,
        'periode': _choix_ferme(PERIODES),
        'echeance': _date_iso,
        'tri': _choix_ferme(TRIS),
        'groupe': _choix_ferme(GROUPES),
        'inclure_faites': _booleen,
    }
    erreurs, propres = {}, {}
    for cle, valeur in filtres.items():
        if cle not in CLES_FILTRES:
            erreurs[str(cle)[:40]] = [MESSAGE_INCONNU]
            continue
        try:
            propres[cle] = lecteurs[cle](valeur)
        except ValueError as exc:
            erreurs[cle] = [str(exc)]
    if erreurs:
        raise serializers.ValidationError({'filtres': erreurs})
    return propres


def _vue_du_compte(user, pk, *, verrou=False):
    qs = vues_de(user)
    vue = (qs.select_for_update() if verrou else qs).filter(pk=pk).first()
    if vue is None:
        raise Http404(MESSAGE_INTROUVABLE)
    return vue


def _vue_prise(nom):
    return serializers.ValidationError({'nom': [f'Une vue « {nom} » existe déjà.']})


def liste_vues(user):
    """Les vues de `user` (30 au plus), dans l'ordre choisi."""
    return list(vues_de(user).order_by('rang', 'id')[:MAX_VUES])


def creer_vue(user, *, nom, filtres=None, rang=None):
    """Crée une vue enregistrée ; 31e vue ou nom déjà pris → 400 ; rend `(vue, geste)`."""
    nom = _nom(nom, 60, MESSAGE_NOM_VUE_LONG)
    filtres = _valider_filtres(user, {} if filtres is None else filtres)
    with transaction.atomic():
        existantes = list(vues_de(user).select_for_update().values_list('nom', 'rang'))
        if len(existantes) >= MAX_VUES:
            raise serializers.ValidationError({'nom': [MESSAGE_VUES_PLEINES]})
        if any(n == nom for n, _rang in existantes):
            raise _vue_prise(nom)
        if rang is None:
            rang = max((r for _n, r in existantes), default=0) + PAS_RANG
        try:
            with transaction.atomic():
                vue = VueEnregistree.objects.create(
                    company_id=user.company_id, proprietaire=user, nom=nom, filtres=filtres, rang=rang)
        except IntegrityError:
            raise _vue_prise(nom)
        geste = enregistrer_geste(user, 'creation', 'Vue enregistrée', [op_creation('vue_enregistree', vue)])
    return vue, geste


def modifier_vue(user, pk, donnees):
    """PATCH : `nom`, `filtres` et/ou `rang` ; rend `(vue, geste)` (geste `None` si rien n'a changé)."""
    with transaction.atomic():
        vue = _vue_du_compte(user, pk, verrou=True)
        valeurs = {}
        if 'nom' in donnees:
            valeurs['nom'] = _nom(donnees['nom'], 60, MESSAGE_NOM_VUE_LONG)
        if 'filtres' in donnees:
            valeurs['filtres'] = _valider_filtres(user, donnees['filtres'])
        if 'rang' in donnees:
            valeurs['rang'] = donnees['rang']
        changes = {c: v for c, v in valeurs.items() if getattr(vue, c) != v}
        if 'nom' in changes and vues_de(user).filter(nom=changes['nom']).exclude(pk=vue.pk).exists():
            raise _vue_prise(changes['nom'])
        if not changes:
            return vue, None
        avant = {c: getattr(vue, c) for c in changes}
        for champ, valeur in changes.items():
            setattr(vue, champ, valeur)
        try:
            with transaction.atomic():
                vue.save(update_fields=[*changes, 'updated_at'])
        except IntegrityError:
            raise _vue_prise(changes.get('nom', vue.nom))
        geste = enregistrer_geste(user, 'modification', 'Vue modifiée',
                                  [op_champ('vue_enregistree', vue, c, avant[c]) for c in changes])
    return vue, geste


def supprimer_vue(user, pk):
    """DELETE : la vue disparaît (recréée au même id par l'annulation) ; rend le geste."""
    with transaction.atomic():
        vue = _vue_du_compte(user, pk, verrou=True)
        op = op_suppression_dure('vue_enregistree', vue, {'nom': vue.nom, 'filtres': vue.filtres, 'rang': vue.rang})
        vue.delete()
        return enregistrer_geste(user, 'suppression', 'Vue supprimée', [op])
