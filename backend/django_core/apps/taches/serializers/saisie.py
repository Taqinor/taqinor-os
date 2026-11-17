"""Corps reçus et réponses de la saisie (reference/api.md §3.2, §4 ; `saisie_apercu.json`,
`saisie_rapide.json`).

Entrées : `CHAMPS_LIGNE` (le format d'une LIGNE à créer, déclaré ICI une fois : le schéma OpenAPI et
la validation à l'exécution lisent les mêmes champs), `SaisieEntreeSerializer` (le corps de
`saisie-rapide/`), `valider_lignes` (une erreur par ligne : `{"lignes": {"3": {"titre": […]}}}`).

Sorties : `apercu_saisie` (analyse et collage → forme de `saisie_apercu.json`, rien n'est écrit),
`apercu_ids` (« Range ma liste » : un projet proposé à des tâches existantes) et
`reponse_creation` (forme de `saisie_rapide.json`). L'analyse et le collage sont déjà écrits et
testés dans `saisie/` : ce module les BRANCHE, il ne les réécrit pas. Un texte collé ou dicté est
une DONNÉE, jamais une consigne.
"""
import datetime

from django.http import Http404
from django.utils import timezone
from drf_spectacular.utils import inline_serializer
from rest_framework import serializers

from apps.taches.choix import CibleLiable, StatutTache
from apps.taches.saisie.analyseur import analyser
from apps.taches.saisie.collage import (
    MAX_LIGNES, MESSAGE_TROP_DE_LIGNES, decouper_collage, erreurs_limites, marquer_doublons,
)
from apps.taches.saisie.grammaire import ProjetConnu
from apps.taches.selectors.base import (
    TACHE_CONFIDENTIELLE, etiquettes_de, jours_travailles_de, projets_de, sections_de, taches_de,
)
from apps.taches.selectors.liens import cible_visible
from apps.taches.serializers.formes import (
    TacheSerializer, charger_taches, contexte, projet_court,
)
from core.conflit_etat import ConflitEtat

OUVERTES = (StatutTache.A_FAIRE, StatutTache.EN_ATTENTE)
#: Un collage venu du Copilote tient en 2 000 caractères (api.md §4).
MAX_CARACTERES_ASSISTANT = 2_000
HORIZON_OUVRES = 400
MESSAGE_AUTRE_COMPTE = "Une action d'un autre compte a été retirée de la file."
MESSAGE_TROP_DE_CARACTERES_ASSISTANT = '2 000 caractères au plus.'
MESSAGE_PROJET_INEXISTANT = 'Projet inexistant.'
MESSAGE_LIEN_INTROUVABLE = 'Élément introuvable ou hors de ta portée.'
MESSAGE_LIEN_TYPE = "Ce type d'élément ne peut pas être lié à une tâche."
MESSAGE_REQUIS = 'Requis.'
CLES_APERCU = ('index', 'collage', 'tache_id', 'titre', 'cochee', 'doublon_de', 'etape_de', 'alertes',
               'jetons', 'champs')
#: Clés de la sortie de `saisie/` ajoutées à la ligne SEULEMENT quand elles portent quelque chose.
CLES_APERCU_FACULTATIVES = ('doublon_de_ligne', 'projet_suggere', 'erreurs')


def _facultatif(champ, **options):
    return champ(required=False, **options)


#: Une LIGNE à créer (api.md §4) : `projet_id` / `nouveau_projet` et `section_id` /
#: `nouvelle_section` exclusifs ; `rappel` absolu `{jour, heure}` ou ancré `{ancre,
#: decalage_jours, heure}` ; `etiquettes` = ids ou `{"nom"}` ; `lien` = `{cible, id}`.
CHAMPS_LIGNE = {
    'index': _facultatif(serializers.IntegerField),
    'collage': _facultatif(serializers.IntegerField),
    'client_id': _facultatif(serializers.CharField, max_length=64),
    # `allow_blank` : un titre vide est refusé par `creer_taches` avec SON message (textes.md §2.16).
    'titre': _facultatif(serializers.CharField, max_length=280, allow_blank=True,
                         error_messages={'max_length': '280 caractères au plus.'}),
    'projet_id': _facultatif(serializers.IntegerField, allow_null=True),
    'nouveau_projet': inline_serializer('TachesLigneNouveauProjet', {
        'nom': serializers.CharField(max_length=120),
        'priorite': serializers.IntegerField(required=False),
    }, required=False, allow_null=True),
    'section_id': _facultatif(serializers.IntegerField, allow_null=True),
    'nouvelle_section': inline_serializer('TachesLigneNouvelleSection', {
        'nom': serializers.CharField(max_length=120),
    }, required=False, allow_null=True),
    'priorite': _facultatif(serializers.IntegerField),
    'jour_prevu': _facultatif(serializers.DateField, allow_null=True),
    'moment': _facultatif(serializers.CharField, allow_blank=True),
    'heure_debut': _facultatif(serializers.CharField, allow_null=True),
    'echeance': _facultatif(serializers.DateField, allow_null=True),
    'echeance_heure': _facultatif(serializers.CharField, allow_null=True),
    'quelque_jour': _facultatif(serializers.BooleanField),
    'estimation_minutes': _facultatif(serializers.IntegerField, allow_null=True),
    'etiquettes': _facultatif(serializers.ListField, child=serializers.JSONField()),
    'recurrence': _facultatif(serializers.JSONField, allow_null=True),
    'rappel': _facultatif(serializers.JSONField, allow_null=True),
    'notes': _facultatif(serializers.CharField, allow_blank=True),
    'checklist': _facultatif(serializers.ListField, child=serializers.CharField()),
    'lien': inline_serializer('TachesLigneLien', {
        'cible': serializers.CharField(), 'id': serializers.IntegerField(),
    }, required=False, allow_null=True),
}


#: Une LIGNE reçue : seules les clés de `CHAMPS_LIGNE` sont lues (une clé inconnue est ignorée). Les
#: champs sont COPIÉS : la construction d'un sérialiseur vide le dict reçu.
LigneEntreeSerializer = type('LigneEntreeSerializer', (serializers.Serializer,), dict(CHAMPS_LIGNE))


class IgnorerSerializer(serializers.Serializer):
    """Effet du × sur une puce : `{type, source}` (le jeton que l'utilisateur a refusé)."""

    type = serializers.CharField(max_length=24)
    source = serializers.CharField(max_length=280)


class SaisieEntreeSerializer(serializers.Serializer):
    """Corps de `saisie-rapide/` (api.md §4)."""

    textes = _facultatif(serializers.ListField, child=serializers.CharField(
        allow_blank=True, trim_whitespace=False))
    texte = _facultatif(serializers.CharField, allow_blank=True, trim_whitespace=False)
    ids = _facultatif(serializers.ListField, child=serializers.IntegerField(), max_length=200)
    client_id = _facultatif(serializers.CharField, max_length=64, allow_blank=True)
    projet_id = _facultatif(serializers.IntegerField, allow_null=True)
    lien = _facultatif(serializers.DictField, allow_null=True)
    parent_id = _facultatif(serializers.IntegerField, allow_null=True)
    proprietaire_attendu = _facultatif(serializers.IntegerField)
    ignorer = _facultatif(serializers.ListField, child=IgnorerSerializer(), max_length=100)
    lignes = _facultatif(serializers.ListField, child=serializers.DictField())
    apercu = _facultatif(serializers.BooleanField)


# --- Garde-fous communs ----------------------------------------------------------------------

def verifier_proprietaire(user, attendu):
    """409 `autre_compte` : la file hors ligne d'un AUTRE compte est jetée (invariant 31)."""
    if attendu is not None and attendu != user.pk:
        raise ConflitEtat({'detail': MESSAGE_AUTRE_COMPTE, 'code': 'autre_compte'})


def valider_lignes(lignes):
    """Les LIGNES validées (liste de dicts) ; sinon 400 `{"lignes": {"<index>": {champ: […]}}}`."""
    if len(lignes) > MAX_LIGNES:
        raise serializers.ValidationError(
            {'lignes': [MESSAGE_TROP_DE_LIGNES.format(n=len(lignes))]})
    valides, erreurs = [], {}
    for rang, brute in enumerate(lignes):
        entree = LigneEntreeSerializer(data=brute)
        if entree.is_valid():
            valides.append(dict(entree.validated_data))
            continue
        index = brute.get('index', rang) if isinstance(brute, dict) else rang
        erreurs[str(index)] = entree.errors
    if erreurs:
        raise serializers.ValidationError({'lignes': erreurs})
    return valides


def projet_choisi(user, projet_id, *, assistant=False):
    """Le projet imposé à tout l'envoi (`{id, nom, nouveau: False}`) ; 400 « Projet inexistant. »."""
    projet = projets_de(user).filter(pk=projet_id).first()
    if projet is None or (assistant and projet.confidentiel):
        raise serializers.ValidationError({'projet_id': [MESSAGE_PROJET_INEXISTANT]})
    return {'id': projet.pk, 'nom': projet.nom, 'nouveau': False}


def verifier_lien(user, lien):
    """400 sur `lien` si la cible n'est pas liable ou pas visible (refus = introuvable)."""
    if lien.get('cible') not in CibleLiable.values:
        raise serializers.ValidationError({'lien': [MESSAGE_LIEN_TYPE]})
    if not cible_visible(user, lien['cible'], lien.get('id')):
        raise serializers.ValidationError({'lien': [MESSAGE_LIEN_INTROUVABLE]})


# --- Aperçu ------------------------------------------------------------------------------------

def _textes_de(donnees):
    textes = donnees.get('textes')
    if textes is None and donnees.get('texte') is not None:
        textes = [donnees['texte']]
    return textes


def _limites(textes, assistant):
    """400 sur `texte` : plafonds de l'aperçu (200 lignes, 20 000 caractères, 10 collages) ; 2 000
    caractères via le Copilote. Posé AVANT toute analyse : un texte trop long n'est jamais lu."""
    erreurs = erreurs_limites(textes)
    if assistant and not erreurs and sum(len(t) for t in textes) > MAX_CARACTERES_ASSISTANT:
        erreurs = {'texte': [MESSAGE_TROP_DE_CARACTERES_ASSISTANT]}
    if erreurs:
        raise serializers.ValidationError(erreurs)


def _connus(user, assistant):
    """Ce que l'analyseur sait du compte : projets (jamais un projet confidentiel vers l'assistant),
    étapes, étiquettes."""
    projets = projets_de(user)
    if assistant:
        projets = projets.filter(confidentiel=False)
    return {
        'projets': tuple(ProjetConnu(id=p.pk, nom=p.nom, statut=p.statut, rang=p.rang)
                         for p in projets.order_by('rang', 'id')),
        'sections': tuple(sections_de(user).values_list('projet_id', 'pk', 'nom')),
        'etiquettes': tuple(etiquettes_de(user).values_list('pk', 'nom')),
    }


def _taches_ouvertes(user, assistant):
    """`(id, titre)` des tâches ouvertes du compte (doublons) ; jamais une confidentielle pour l'assistant."""
    ouvertes = taches_de(user).filter(statut__in=OUVERTES, parent__isnull=True)
    if assistant:
        ouvertes = ouvertes.exclude(TACHE_CONFIDENTIELLE)
    return tuple(ouvertes.values_list('pk', 'titre'))


def _est_ouvre(user, aujourdhui):
    """`est_ouvre(date)` de la récurrence « jours ouvrés » : les jours TRAVAILLÉS du compte sur 400 jours
    (au-delà : lundi-vendredi)."""
    fin = aujourdhui + datetime.timedelta(days=HORIZON_OUVRES)
    travailles = jours_travailles_de(user, aujourdhui, fin)
    return lambda jour: (jour in travailles) if jour <= fin else jour.weekday() < 5


def _relire_ignorees(lignes, ignorer, base):
    """Le × d'une puce : chaque ligne qui portait un jeton refusé est relue SANS lui (le projet hérité
    d'un titre de groupe ou de la première ligne est gardé)."""
    refus = {(i['type'], i['source']) for i in ignorer}
    for ligne in lignes:
        if not any((j['type'], j['source']) in refus for j in ligne['jetons']):
            continue
        lecture = analyser(ligne['texte'], ignorer=ignorer, **base)
        herite = {cle: val for cle, val in ligne['champs'].items()
                  if cle in ('projet_id', 'nouveau_projet') and not any(
                      j['type'] == 'projet' for j in ligne['jetons'])}
        ligne.update(titre=lecture.titre, jetons=list(lecture.jetons), alertes=list(lecture.alertes),
                     champs={**lecture.champs, **herite})
        ligne.pop('erreurs', None)
        if lecture.erreurs:
            ligne['erreurs'], ligne['cochee'] = lecture.erreurs, False


def _forme_ligne(ligne):
    """La ligne de `saisie_apercu.json` : ses clés, dans l'ordre, + celles de `saisie/` qui portent
    quelque chose (doublon de ligne, projet suggéré, erreurs)."""
    forme = {cle: ligne[cle] for cle in CLES_APERCU}
    forme.update({cle: ligne[cle] for cle in CLES_APERCU_FACULTATIVES
                  if ligne.get(cle) is not None and ligne[cle] != {}})
    return forme


def apercu_saisie(user, donnees, *, assistant=False, aujourdhui=None, maintenant=None):
    """Aperçu d'un ou plusieurs collages (`saisie_apercu.json`) ; rien n'est écrit.

    `aujourdhui` et `maintenant` sont fournis par l'appelant (la vue lit l'horloge, les tests la fixent).
    """
    textes = _textes_de(donnees)
    _limites(textes, assistant)
    aujourdhui = aujourdhui or timezone.localdate()
    maintenant = maintenant or timezone.localtime()
    connus = _connus(user, assistant)
    imposer = (projet_choisi(user, donnees['projet_id'], assistant=assistant)
               if donnees.get('projet_id') is not None else None)
    if donnees.get('lien'):
        verifier_lien(user, donnees['lien'])
    est_ouvre = _est_ouvre(user, aujourdhui)
    apercu = decouper_collage(
        textes, aujourdhui, maintenant, projets=connus['projets'], sections=connus['sections'],
        etiquettes=connus['etiquettes'], taches_ouvertes=_taches_ouvertes(user, assistant),
        est_ouvre=est_ouvre, projet_impose=imposer)
    if donnees.get('ignorer'):
        base = {'aujourdhui': aujourdhui, 'maintenant': maintenant, 'projets': connus['projets'],
                'sections': connus['sections'], 'etiquettes': connus['etiquettes'], 'est_ouvre': est_ouvre}
        _relire_ignorees(apercu['lignes'], donnees['ignorer'], base)
    return {'projets_communs': apercu['projets_communs'],
            'lignes': [_forme_ligne(ligne) for ligne in apercu['lignes']],
            'projets_nouveaux': apercu['projets_nouveaux']}


def apercu_ids(user, ids, *, assistant=False):
    """« Range ma liste » : pour chaque tâche À TRIER demandée, le projet suggéré par les mots du titre
    (`champs.projet_id`), sinon rien. L'id d'un autre compte (ou confidentiel pour l'assistant) répond
    comme un id inconnu (404). Le projet n'est posé que par `taches/lot/` `deplacer`."""
    demandes = list(dict.fromkeys(ids))
    taches = taches_de(user).filter(pk__in=demandes, parent__isnull=True, statut__in=OUVERTES)
    if assistant:
        taches = taches.exclude(TACHE_CONFIDENTIELLE)
    par_id = {t.pk: t for t in taches}
    if len(par_id) != len(demandes):
        raise Http404('Introuvable.')
    projets = _connus(user, assistant)['projets']
    lignes = [{'index': rang, 'collage': 0, 'tache_id': pk, 'titre': par_id[pk].titre, 'cochee': True,
               'doublon_de': None, 'etape_de': None, 'alertes': [], 'jetons': [], 'champs': {},
               'projet_suggere': None} for rang, pk in enumerate(demandes)]
    marquer_doublons(lignes, (), projets)
    for ligne in lignes:
        suggere = ligne['projet_suggere']
        ligne['cochee'] = suggere is not None
        if suggere is not None:
            ligne['champs'] = {'projet_id': suggere['id']}
    return {'projets_communs': [],
            'lignes': [{cle: ligne[cle] for cle in CLES_APERCU} for ligne in lignes],
            'projets_nouveaux': []}


# --- Création ------------------------------------------------------------------------------------

def taches_chargees(user, ids):
    """Les tâches `ids` du compte, chargées pour la forme TACHE (aucune requête par ligne), dans
    l'ordre de `ids`."""
    par_id = {t.pk: t for t in charger_taches(taches_de(user).filter(pk__in=ids))}
    return [par_id[pk] for pk in ids if pk in par_id]


def reponse_creation(user, resultat, *, assistant=False):
    """Forme de `saisie_rapide.json` : `creees` (TACHE), `projets_crees`, `deja_creees`, `geste_id`."""
    ctx = contexte(assistant=assistant)
    taches = taches_chargees(user, [t.pk for t in resultat.creees])
    return {
        'creees': TacheSerializer(taches, many=True, context=ctx).data,
        'projets_crees': [projet_court(p, assistant=assistant) for p in resultat.projets_crees],
        'deja_creees': list(resultat.deja_creees),
        'geste_id': resultat.geste.pk if resultat.geste is not None else None,
    }
