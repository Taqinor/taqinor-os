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
from django.http import Http404
from django.utils import timezone
from drf_spectacular.utils import inline_serializer
from rest_framework import serializers

from apps.taches.choix import StatutTache
from apps.taches.confidentialite import ASSISTANT, ECRAN, nom_pour
from apps.taches.saisie.analyseur import analyser
from apps.taches.saisie.collage import (
    MAX_LIGNES, MESSAGE_TROP_DE_LIGNES, decouper_collage, erreurs_limites, marquer_doublons,
)
from apps.taches.saisie.grammaire import ProjetConnu
from apps.taches.selectors.base import (
    TACHE_CONFIDENTIELLE, etiquettes_de, projets_de, sections_de, taches_de,
)
from apps.taches.selectors.journee import progression_courante
from apps.taches.serializers.formes import (
    ItemSerializer, ProjetSerializer, TacheEcriteSerializer, TacheSerializer, charger_taches, contexte,
    projet_court, tache_ecrite,
)
from apps.taches.services.taches import est_ouvre_de, verifier_lien
from core.conflit_etat import ConflitEtat

OUVERTES = (StatutTache.A_FAIRE, StatutTache.EN_ATTENTE)
#: Un collage venu du Copilote tient en 2 000 caractères (api.md §4).
MAX_CARACTERES_ASSISTANT = 2_000
MESSAGE_AUTRE_COMPTE = "Une action d'un autre compte a été retirée de la file."
MESSAGE_TROP_DE_CARACTERES_ASSISTANT = '2 000 caractères au plus.'
MESSAGE_PROJET_INEXISTANT = 'Projet inexistant.'
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
    est_ouvre = est_ouvre_de(user, aujourdhui)
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


# --- Tâches : création d'une LIGNE, PATCH, TACHE_ECRITE --------------------------------------------

#: `POST taches/` : une LIGNE (+ `parent_id`, `proprietaire_attendu`).
TacheCreationSerializer = type('TacheCreationSerializer', (serializers.Serializer,), {
    **CHAMPS_LIGNE,
    'parent_id': serializers.IntegerField(required=False, allow_null=True),
    'proprietaire_attendu': serializers.IntegerField(required=False),
})

#: Champs que le PATCH renvoie vers « Quand » (`planifier()` est le seul chemin du jour : invariant 15).
CHAMPS_PLANIFICATION = ('jour_prevu', 'moment', 'heure_debut', 'quelque_jour')
MESSAGE_PASSE_PAR_QUAND = 'Passe par « Quand ».'
MESSAGE_NON_MODIFIABLE = 'Non modifiable ici.'


class TachePatchSerializer(serializers.Serializer):
    """Corps de `PATCH taches/{id}/` : tout champ est facultatif SAUF `lock_version`."""

    titre = serializers.CharField(required=False, allow_blank=True, max_length=280,
                                  error_messages={'max_length': '280 caractères au plus.'})
    notes = serializers.CharField(required=False, allow_blank=True)
    priorite = serializers.IntegerField(required=False)
    echeance = serializers.DateField(required=False, allow_null=True)
    echeance_heure = serializers.TimeField(required=False, allow_null=True)
    estimation_minutes = serializers.IntegerField(required=False, allow_null=True)
    duree_reelle_minutes = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    projet_id = serializers.IntegerField(required=False, allow_null=True)
    section_id = serializers.IntegerField(required=False, allow_null=True)
    jalon = serializers.BooleanField(required=False)
    bloquee_par_id = serializers.IntegerField(required=False, allow_null=True)
    confidentiel = serializers.BooleanField(required=False)
    etiquettes = serializers.ListField(required=False, child=serializers.IntegerField(), max_length=50)
    recurrence = serializers.JSONField(required=False, allow_null=True)
    lien = serializers.DictField(required=False, allow_null=True)
    lock_version = serializers.IntegerField(min_value=0, error_messages={'required': MESSAGE_REQUIS})


def valider_patch(donnees):
    """Le PATCH validé ; sinon 400 nommé : `lock_version` requis, un champ du jour renvoyé vers « Quand »,
    tout autre champ inconnu « Non modifiable ici. »."""
    if not isinstance(donnees, dict):
        raise serializers.ValidationError({'detail': ['Corps attendu : un objet.']})
    entree = TachePatchSerializer(data=donnees)
    entree.is_valid()
    erreurs = dict(entree.errors)
    for cle in donnees:
        if cle in CHAMPS_PLANIFICATION:
            erreurs[cle] = [MESSAGE_PASSE_PAR_QUAND]
        elif cle not in entree.fields:
            erreurs[cle] = [MESSAGE_NON_MODIFIABLE]
    if erreurs:
        raise serializers.ValidationError(erreurs)
    return dict(entree.validated_data)


def lire_corps(classe, donnees):
    """Le corps validé d'une action (`{}` si absent) ; 400 nommé sinon."""
    entree = classe(data=donnees if donnees is not None else {})
    entree.is_valid(raise_exception=True)
    return dict(entree.validated_data)


class ProprietaireEntreeSerializer(serializers.Serializer):
    """Corps facultatif de `terminer/` et `rouvrir/` : le compte qui a mis l'op en file (invariant 31)."""

    proprietaire_attendu = serializers.IntegerField(required=False)


class PlanifierEntreeSerializer(ProprietaireEntreeSerializer):
    """Corps de `planifier/` : le jour, l'heure, le moment ou « En réserve » ; `lock_version` requis."""

    jour_prevu = serializers.DateField(required=False, allow_null=True)
    moment = serializers.CharField(required=False, allow_blank=True)
    heure_debut = serializers.CharField(required=False, allow_null=True)
    quelque_jour = serializers.BooleanField(required=False)
    lock_version = serializers.IntegerField(min_value=0, error_messages={'required': MESSAGE_REQUIS})


class TrancherEntreeSerializer(serializers.Serializer):
    choix = serializers.CharField(error_messages={'required': MESSAGE_REQUIS})
    jour = serializers.DateField(required=False, allow_null=True)


class AttendreEntreeSerializer(serializers.Serializer):
    en_attente_de = serializers.CharField(required=False, allow_blank=True, default='')


class ReordonnerEntreeSerializer(serializers.Serializer):
    """Corps de `reordonner/` : la place entre deux voisins (`avant_id` précède, `apres_id` suit)."""

    liste = serializers.CharField(error_messages={'required': MESSAGE_REQUIS})
    avant_id = serializers.IntegerField(required=False, allow_null=True)
    apres_id = serializers.IntegerField(required=False, allow_null=True)


class ChangementEntreeSerializer(serializers.Serializer):
    geste = serializers.CharField(error_messages={'required': MESSAGE_REQUIS})
    titre = serializers.CharField(required=False, allow_blank=True)


class RappelEntreeSerializer(serializers.Serializer):
    """Corps de `rappels/` : `{jour, heure}` ou `{ancre, decalage_jours, heure}`."""

    jour = serializers.DateField(required=False)
    heure = serializers.CharField(error_messages={'required': MESSAGE_REQUIS})
    ancre = serializers.CharField(required=False, allow_blank=True)
    decalage_jours = serializers.IntegerField(required=False)


class RepeterEntreeSerializer(serializers.Serializer):
    """Corps de `repeter/` : `{dans_minutes}` ou `{jour, heure}`."""

    dans_minutes = serializers.IntegerField(required=False, min_value=1)
    jour = serializers.DateField(required=False)
    heure = serializers.CharField(required=False)

    def validate(self, donnees):
        if 'dans_minutes' not in donnees and not ('jour' in donnees and 'heure' in donnees):
            raise serializers.ValidationError({'dans_minutes': [MESSAGE_REQUIS]})
        return donnees


class RecurrenceEntreeSerializer(serializers.Serializer):
    """Corps de `PATCH recurrences/{id}/` : tout est facultatif ; `actif: false` arrête la série."""

    frequence = serializers.CharField(required=False)
    intervalle = serializers.IntegerField(required=False)
    jours_semaine = serializers.CharField(required=False)
    jour_du_mois = serializers.IntegerField(required=False, allow_null=True)
    rang_dans_mois = serializers.IntegerField(required=False, allow_null=True)
    mode = serializers.CharField(required=False)
    date_debut = serializers.DateField(required=False)
    date_fin = serializers.DateField(required=False, allow_null=True)
    actif = serializers.BooleanField(required=False)
    appliquer_a_l_ouverte = serializers.BooleanField(required=False)


class LotEntreeSerializer(serializers.Serializer):
    """Corps de `taches/lot/` : `ids` (≤ 200, bornés par le service), `action`, `valeurs` selon l'action."""

    ids = serializers.ListField(child=serializers.IntegerField(), error_messages={'required': MESSAGE_REQUIS})
    action = serializers.CharField(error_messages={'required': MESSAGE_REQUIS})
    valeurs = serializers.DictField(required=False)


class ChecklistEntreeSerializer(serializers.Serializer):
    tache_id = serializers.IntegerField(error_messages={'required': MESSAGE_REQUIS})
    libelle = serializers.CharField(allow_blank=True, error_messages={'required': MESSAGE_REQUIS})


class ElementChecklistEntreeSerializer(serializers.Serializer):
    libelle = serializers.CharField(required=False, allow_blank=True)
    fait = serializers.BooleanField(required=False)


class ReordonnerElementEntreeSerializer(serializers.Serializer):
    """Corps de `checklist/{id}/reordonner/` : les voisins (`liste` est sans objet ici)."""

    liste = serializers.CharField(required=False)
    avant_id = serializers.IntegerField(required=False, allow_null=True)
    apres_id = serializers.IntegerField(required=False, allow_null=True)


def reponse_ecrite(user, tache, *, assistant=False, geste=None, suivante=None, projet_cree=None,
                   rappel=None, question_titres=False, avertissements=()):
    """La TACHE_ECRITE d'une écriture : `tache` relue et chargée (aucune requête par ligne), + `suivante`
    (occurrence née), `rappel` posé, `progression` du jour (`selectors.journee.progression_courante`),
    `geste_id`."""
    pks = [tache.pk] + ([suivante.pk] if suivante is not None else [])
    chargees = {t.pk: t for t in taches_chargees(user, pks)}
    instance = tache_ecrite(
        chargees[tache.pk], suivante=chargees.get(suivante.pk) if suivante is not None else None,
        projet_cree=projet_cree, rappel=rappel, question_titres=question_titres,
        avertissements=avertissements, progression=progression_courante(user, timezone.localdate()),
        geste_id=geste.pk if geste is not None else None)
    return TacheEcriteSerializer(instance, context=contexte(assistant=assistant)).data


# --- Recherche, supprimées récemment, derniers gestes ------------------------------------------------

_INSTANT = serializers.DateTimeField()


def reponse_recherche(projets, taches, *, assistant=False):
    """Forme de `recherche.json` : `projets` (id, nom, couleur, statut, priorité) et `taches` (ITEM)."""
    usage = ASSISTANT if assistant else ECRAN
    return {
        'projets': [{'id': p.pk, 'nom': nom_pour(p, usage), 'couleur': p.couleur, 'statut': p.statut,
                     'priorite': p.priorite} for p in projets],
        'taches': ItemSerializer(taches, many=True, context=contexte(assistant=assistant)).data,
    }


def reponse_supprimees(projets, compteurs, taches, *, assistant=False):
    """Forme de `supprimees.json` : un projet = une ligne (`projet`, `taches_nb`, `deleted_at`), puis les
    tâches supprimées seules (`item`, `deleted_at`). Les compteurs du projet sont CALCULÉS de ses tâches."""
    calculs = {('projet', p.pk): {'compteurs': {'ouvertes': compteurs[p.pk]['ouvertes'],
                                                'faites': compteurs[p.pk]['faites']}} for p in projets}
    ctx = contexte(assistant=assistant, calculs=calculs)
    return {
        'projets': [{'projet': ProjetSerializer(p, context=ctx).data, 'taches_nb': compteurs[p.pk]['total'],
                     'deleted_at': _INSTANT.to_representation(p.deleted_at)} for p in projets],
        'taches': [{'item': ItemSerializer(t, context=ctx).data,
                    'deleted_at': _INSTANT.to_representation(t.deleted_at)} for t in taches],
    }


def reponse_gestes(gestes):
    """Forme de `gestes.json` : `{"results": […]}` ; `annulable` tant que le geste n'est pas annulé."""
    return {'results': [{'id': g.pk, 'type': g.type, 'message': g.message,
                         'created_at': _INSTANT.to_representation(g.created_at),
                         'annule_le': _INSTANT.to_representation(g.annule_le) if g.annule_le else None,
                         'annulable': g.annule_le is None} for g in gestes]}
