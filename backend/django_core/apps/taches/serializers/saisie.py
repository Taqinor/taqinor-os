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
from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from apps.taches.choix import (
    AncreRappel, CibleLiable, Couleur, Frequence, ModeRecurrence, Moment, Priorite, StatutTache,
)
from apps.taches.confidentialite import ASSISTANT, ECRAN, nom_pour
from apps.taches.entrees import (
    MOTIF_ANNEE_BORNEE, MOTIF_SEMAINE, Choix, ChoixEntier, DateBornee, HeureStricte, MotifPublie, champ_heure,
)
from apps.taches.saisie.analyseur import analyser
from apps.taches.saisie.collage import (
    MAX_LIGNES, MESSAGE_TROP_DE_LIGNES, decouper_collage, erreurs_limites, marquer_doublons,
)
from apps.taches.saisie.grammaire import ProjetConnu
from apps.taches.selectors.base import (
    TACHE_CONFIDENTIELLE, etiquettes_de, projets_de, sections_de, taches_de,
)
from apps.taches.selectors.journee import lignes_de_taches_du_jour, progression_courante
from apps.taches.serializers.formes import (
    ItemSerializer, ProjetSerializer, TacheEcriteSerializer, TacheSerializer, charger_taches, contexte,
    projet_court, tache_ecrite,
)
from apps.taches.serializers.corps import DATE, ENTIER, CorpsTaches, absent, parmi, present, valeur
from apps.taches.services.etiquettes import MAX_IDS, MAX_Q, MESSAGE_NOM_ETIQUETTE_LONG, MESSAGE_NOM_VUE_LONG
from apps.taches.services.taches import (
    ACTIONS_LOT, CHOIX_TRANCHER, GESTES_ECHO, GROUPES, LISTES, MAX_LOT, MESSAGE_ATTENTE_LONGUE, MESSAGE_ATTENTE_VIDE,
    MESSAGE_ESTIMATION, MESSAGE_LIBELLE_LONG, MESSAGE_LIBELLE_VIDE, MESSAGE_LIEN_INTROUVABLE, MESSAGE_LIEN_TYPE,
    MESSAGE_LOT_LONG, MESSAGE_TITRE_VIDE, MESSAGE_VALEUR_INCONNUE, PERIODES, RANGS_DU_MOIS, TRIS, est_ouvre_de,
    verifier_lien,
)
from core.champs_stricts import (
    MOTIF_NON_BLANC_SANS_NUL, MOTIF_SANS_NUL, BooleenStrict, ChaineStricte, EntierStrict,
)
from core.conflit_etat import ConflitEtat

OUVERTES = (StatutTache.A_FAIRE, StatutTache.EN_ATTENTE)
#: Un collage venu du Copilote tient en 2 000 caractères (api.md §4).
MAX_CARACTERES_ASSISTANT = 2_000
MESSAGE_AUTRE_COMPTE = "Une action d'un autre compte a été retirée de la file."
MESSAGE_TROP_DE_CARACTERES_ASSISTANT = '2 000 caractères au plus.'
MESSAGE_PROJET_INEXISTANT = 'Projet inexistant.'
MESSAGE_REQUIS = 'Requis.'
#: `deja_faite` : la ligne était cochée « ✓ » / « [x] » à l'origine (décochée d'office) ; `doublon_projet` :
#: le nom du projet de la tâche dont la ligne est le doublon (« Déjà dans « {projet} » »), par `nom_pour`.
CLES_APERCU = ('index', 'collage', 'tache_id', 'titre', 'cochee', 'deja_faite', 'doublon_de', 'doublon_projet',
               'etape_de', 'alertes', 'jetons', 'champs')
#: Clés de la sortie de `saisie/` ajoutées à la ligne SEULEMENT quand elles portent quelque chose.
CLES_APERCU_FACULTATIVES = ('doublon_de_ligne', 'projet_suggere', 'erreurs')


def _facultatif(champ, **options):
    return champ(required=False, **options)


_INCONNU = {'invalid': MESSAGE_VALEUR_INCONNUE, 'invalid_choice': MESSAGE_VALEUR_INCONNUE}
#: Plus grand entier d'une colonne `IntegerField` (au-delà : 500 « integer out of range »).
ENTIER_32_MAX = 2 ** 31 - 1
#: Jours du mois permis à une règle mensuelle (`-1` = le dernier) : `services.taches.CONTROLES_REGLE`.
JOURS_DU_MOIS = (-1, *range(1, 32))


@extend_schema_serializer(component_name='TachesLigneRegleNeuve')
class RegleNeuveSerializer(CorpsTaches):
    """Une règle de récurrence NEUVE portée par une ligne (`services.creation._regle_neuve`)."""

    frequence = Choix(choices=list(Frequence.values), error_messages={
        'required': MESSAGE_VALEUR_INCONNUE, 'null': MESSAGE_VALEUR_INCONNUE, **_INCONNU})
    mode = Choix(choices=list(ModeRecurrence.values), required=False, allow_null=True,
                 error_messages=_INCONNU)
    intervalle = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=99,
                                          error_messages={**_INCONNU, 'min_value': MESSAGE_VALEUR_INCONNUE,
                                                          'max_value': MESSAGE_VALEUR_INCONNUE})
    jours_semaine = ChaineStricte(required=False, allow_null=True, trim_whitespace=False,
                                  validators=[MotifPublie(MOTIF_SEMAINE, MESSAGE_VALEUR_INCONNUE)],
                                  error_messages=_INCONNU)
    jour_du_mois = serializers.IntegerField(required=False, allow_null=True, error_messages=_INCONNU)
    rang_dans_mois = serializers.IntegerField(required=False, allow_null=True, error_messages=_INCONNU)
    date_debut = DateBornee(required=False, allow_null=True)
    date_fin = DateBornee(required=False, allow_null=True)

    regles_croisees = ((valeur('jour_du_mois', None, *JOURS_DU_MOIS),),
                       (valeur('rang_dans_mois', None, *RANGS_DU_MOIS),))

    def validate_jour_du_mois(self, jour):
        if jour is not None and jour not in JOURS_DU_MOIS:
            raise serializers.ValidationError(MESSAGE_VALEUR_INCONNUE)
        return jour

    def validate_rang_dans_mois(self, rang):
        if rang is not None and rang not in RANGS_DU_MOIS:
            raise serializers.ValidationError(MESSAGE_VALEUR_INCONNUE)
        return rang


def _entier_json(valeur):
    return isinstance(valeur, int) and not isinstance(valeur, bool)


class RecurrenceLigneField(serializers.JSONField):
    """`recurrence` d'une ligne : l'id d'une règle existante (entier) ou une règle neuve (objet), ou nul."""

    def to_internal_value(self, donnee):
        if _entier_json(donnee):
            return donnee
        if not isinstance(donnee, dict):
            raise serializers.ValidationError(MESSAGE_VALEUR_INCONNUE)
        regle = RegleNeuveSerializer(data=donnee)
        regle.is_valid(raise_exception=True)
        return {**donnee, **regle.validated_data}


class RegleModifieeField(serializers.JSONField):
    """`recurrence` d'un PATCH de tâche : `null` (détacher) ou un objet de règle, champs facultatifs (la règle
    existante garde les autres ; une règle neuve exige `frequence`, jugé par `services.taches`)."""

    def to_internal_value(self, donnee):
        if not isinstance(donnee, dict):
            raise serializers.ValidationError(MESSAGE_VALEUR_INCONNUE)
        regle = RegleNeuveSerializer(data=donnee, partial=True)
        regle.is_valid(raise_exception=True)
        return {**donnee, **regle.validated_data}


class _RegleModifieePubliee(OpenApiSerializerFieldExtension):
    target_class = 'apps.taches.serializers.saisie.RegleModifieeField'

    def map_serializer_field(self, auto_schema, direction):
        if direction != 'request':
            return auto_schema._map_serializer_field(self.target, direction, bypass_extensions=True)
        return {'allOf': [auto_schema.resolve_serializer(RegleNeuveSerializer, direction).ref], 'nullable': True}


class EtiquetteLigneField(serializers.JSONField):
    """Une étiquette d'une ligne : un id (entier) ou `{"nom"}` (créée si elle n'existe pas)."""

    def to_internal_value(self, donnee):
        if _entier_json(donnee):
            return donnee
        if isinstance(donnee, dict) and isinstance(donnee.get('nom', ''), str):
            return donnee
        raise serializers.ValidationError(MESSAGE_VALEUR_INCONNUE)


class _RecurrenceLignePubliee(OpenApiSerializerFieldExtension):
    target_class = 'apps.taches.serializers.saisie.RecurrenceLigneField'

    def map_serializer_field(self, auto_schema, direction):
        if direction != 'request':
            return auto_schema._map_serializer_field(self.target, direction, bypass_extensions=True)
        regle = auto_schema.resolve_serializer(RegleNeuveSerializer, direction).ref
        return {'anyOf': [{'type': 'integer'}, regle], 'nullable': True}


class _EtiquetteLignePubliee(OpenApiSerializerFieldExtension):
    target_class = 'apps.taches.serializers.saisie.EtiquetteLigneField'

    def map_serializer_field(self, auto_schema, direction):
        if direction != 'request':
            return auto_schema._map_serializer_field(self.target, direction, bypass_extensions=True)
        return {'anyOf': [{'type': 'integer'},
                          {'type': 'object', 'properties': {'nom': {'type': 'string', 'pattern': MOTIF_SANS_NUL}}}]}


@extend_schema_serializer(component_name='TachesLigneRappel')
class RappelLigneSerializer(CorpsTaches):
    """Le rappel d'une ligne : absolu `{jour, heure}` ou ancré `{ancre, decalage_jours, heure}`
    (`services.rappels.poser_rappel`)."""

    jour = DateBornee(required=False, allow_null=True)
    heure = champ_heure(error_messages={'required': MESSAGE_REQUIS, 'null': MESSAGE_REQUIS})
    ancre = Choix(choices=list(AncreRappel.values), required=False, allow_blank=True,
                  allow_null=True, error_messages=_INCONNU)
    decalage_jours = serializers.IntegerField(required=False, allow_null=True, min_value=-7, max_value=0,
                                              error_messages={'min_value': 'Entre -7 et 0.',
                                                              'max_value': 'Entre -7 et 0.'})

    regles_croisees = ((present('jour', DATE), present('ancre', parmi(*(a for a in AncreRappel.values if a)))),)

    def validate(self, donnees):
        if not donnees.get('ancre') and donnees.get('jour') is None:
            raise serializers.ValidationError({'jour': [MESSAGE_REQUIS]})
        return donnees


@extend_schema_serializer(component_name='TachesLigneNouveauProjet')
class NouveauProjetLigneSerializer(CorpsTaches):
    nom = ChaineStricte(max_length=120, error_messages={'required': MESSAGE_REQUIS, 'blank': MESSAGE_REQUIS})
    priorite = ChoixEntier(choices=list(Priorite.values), required=False, error_messages=_INCONNU)


@extend_schema_serializer(component_name='TachesLigneNouvelleSection')
class NouvelleSectionLigneSerializer(CorpsTaches):
    nom = ChaineStricte(max_length=120, error_messages={'required': MESSAGE_REQUIS, 'blank': MESSAGE_REQUIS})


class LienLigneField(serializers.JSONField):
    """`lien` d'une ligne : `{cible, id}`, `cible` ∈ `CibleLiable` (sinon 400 « Ce type d'élément… »
    sous `lien`, le refus de `services.creation._lien_verifie`, rendu ici avant toute écriture)."""

    def to_internal_value(self, donnee):
        if not isinstance(donnee, dict) or donnee.get('cible') not in CibleLiable.values:
            raise serializers.ValidationError(MESSAGE_LIEN_TYPE)
        if not _entier_json(donnee.get('id')):
            raise serializers.ValidationError(MESSAGE_LIEN_INTROUVABLE)
        return donnee


class _LienLignePublie(OpenApiSerializerFieldExtension):
    target_class = 'apps.taches.serializers.saisie.LienLigneField'

    def map_serializer_field(self, auto_schema, direction):
        schema = {'type': 'object', 'required': ['cible', 'id'], 'properties': {
            'cible': {'type': 'string', 'enum': list(CibleLiable.values)}, 'id': {'type': 'integer'}}}
        return {**schema, 'nullable': True} if self.target.allow_null else schema


#: Une LIGNE à créer (api.md §4) : `projet_id` / `nouveau_projet` et `section_id` /
#: `nouvelle_section` exclusifs ; `rappel` absolu `{jour, heure}` ou ancré `{ancre,
#: decalage_jours, heure}` ; `etiquettes` = ids ou `{"nom"}` ; `lien` = `{cible, id}`. Types STRICTS (une
#: chaîne pour un nombre, un nombre pour un texte → 400) : ce que le schéma publie, le serveur l'exige.
CHAMPS_LIGNE = {
    'index': _facultatif(EntierStrict),
    'collage': _facultatif(EntierStrict),
    'client_id': _facultatif(ChaineStricte, max_length=64),
    'titre': ChaineStricte(max_length=280, error_messages={
        'required': MESSAGE_TITRE_VIDE, 'null': MESSAGE_TITRE_VIDE, 'blank': MESSAGE_TITRE_VIDE,
        'max_length': '280 caractères au plus.'}),
    'projet_id': _facultatif(EntierStrict, allow_null=True),
    'nouveau_projet': NouveauProjetLigneSerializer(required=False, allow_null=True),
    'section_id': _facultatif(EntierStrict, allow_null=True),
    'nouvelle_section': NouvelleSectionLigneSerializer(required=False, allow_null=True),
    'priorite': ChoixEntier(choices=list(Priorite.values), required=False, error_messages=_INCONNU),
    'jour_prevu': _facultatif(DateBornee, allow_null=True),
    'moment': Choix(choices=list(Moment.values), required=False, allow_blank=True,
                    error_messages=_INCONNU),
    'heure_debut': champ_heure(required=False, allow_null=True),
    'echeance': _facultatif(DateBornee, allow_null=True),
    'echeance_heure': champ_heure(required=False, allow_null=True),
    'quelque_jour': _facultatif(BooleenStrict),
    'estimation_minutes': EntierStrict(required=False, allow_null=True, min_value=5, max_value=960,
                                       error_messages={'min_value': MESSAGE_ESTIMATION,
                                                       'max_value': MESSAGE_ESTIMATION}),
    'etiquettes': _facultatif(serializers.ListField, child=EtiquetteLigneField()),
    'recurrence': RecurrenceLigneField(required=False, allow_null=True),
    'rappel': RappelLigneSerializer(required=False, allow_null=True),
    'notes': _facultatif(ChaineStricte, allow_blank=True),
    'checklist': _facultatif(serializers.ListField, child=ChaineStricte(max_length=255)),
    'lien': LienLigneField(required=False, allow_null=True),
}


#: Une LIGNE reçue : seules les clés de `CHAMPS_LIGNE` sont lues (une clé inconnue est ignorée). Les
#: champs sont COPIÉS : la construction d'un sérialiseur vide le dict reçu.
LigneEntreeSerializer = type('LigneEntreeSerializer', (serializers.Serializer,), dict(CHAMPS_LIGNE))


@extend_schema_serializer(component_name='TachesIgnorer')
class IgnorerSerializer(serializers.Serializer):
    """Effet du × sur une puce : `{type, source}` (le jeton que l'utilisateur a refusé)."""

    type = ChaineStricte(max_length=24)
    source = ChaineStricte(max_length=280)


#: Corps de `saisie-rapide/` (api.md §4), types STRICTS. `lignes` y est lu ligne par ligne par `valider_lignes`
#: (une erreur par ligne, `{"lignes": {"3": …}}`) : le schéma publie la LIGNE (`views/saisie.SAISIE_RAPIDE`).
CHAMPS_SAISIE = {
    'textes': _facultatif(serializers.ListField, child=ChaineStricte(allow_blank=True, trim_whitespace=False)),
    'texte': _facultatif(ChaineStricte, allow_blank=True, trim_whitespace=False),
    'ids': _facultatif(serializers.ListField, child=EntierStrict(), max_length=200),
    'client_id': _facultatif(ChaineStricte, max_length=64, allow_blank=True),
    'projet_id': _facultatif(EntierStrict, allow_null=True),
    'lien': LienLigneField(required=False, allow_null=True),
    'parent_id': _facultatif(EntierStrict, allow_null=True),
    'proprietaire_attendu': _facultatif(EntierStrict),
    'ignorer': _facultatif(serializers.ListField, child=IgnorerSerializer(), max_length=100),
    'apercu': _facultatif(BooleenStrict),
}
SaisieEntreeSerializer = type('SaisieEntreeSerializer', (serializers.Serializer,), {
    **CHAMPS_SAISIE, 'lignes': _facultatif(serializers.ListField, child=serializers.DictField()),
    '__doc__': 'Corps de `saisie-rapide/` (api.md §4).'})


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


def _projets_des_doublons(user, lignes, assistant):
    """`{tache_id: nom du projet ou None}` des tâches dont une ligne est le doublon (UNE requête) ; le
    nom passe par `nom_pour` (« Projet confidentiel » pour l'assistant)."""
    ids = {ligne['doublon_de'] for ligne in lignes if ligne.get('doublon_de') is not None}
    if not ids:
        return {}
    usage = ASSISTANT if assistant else ECRAN
    return {t.pk: (nom_pour(t.projet, usage) if t.projet_id else None)
            for t in taches_de(user).filter(pk__in=ids).select_related('projet')}


def _forme_ligne(ligne, doublons):
    """La ligne de `saisie_apercu.json` : ses clés, dans l'ordre, + celles de `saisie/` qui portent
    quelque chose (doublon de ligne, projet suggéré, erreurs)."""
    ligne = {**ligne, 'deja_faite': bool(ligne.get('deja_faite')),
             'doublon_projet': doublons.get(ligne.get('doublon_de'))}
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
    doublons = _projets_des_doublons(user, apercu['lignes'], assistant)
    return {'projets_communs': apercu['projets_communs'],
            'lignes': [_forme_ligne(ligne, doublons) for ligne in apercu['lignes']],
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
               'deja_faite': False, 'doublon_de': None, 'doublon_projet': None, 'etape_de': None, 'alertes': [],
               'jetons': [], 'champs': {}, 'projet_suggere': None} for rang, pk in enumerate(demandes)]
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
#: Corps de `POST taches/` : une LIGNE, plus le parent d'une sous-tâche et le compte attendu (file hors ligne).
CHAMPS_CREATION = {
    **CHAMPS_LIGNE,
    'parent_id': EntierStrict(required=False, allow_null=True),
    'proprietaire_attendu': EntierStrict(required=False),
}
TacheCreationSerializer = type('TacheCreationSerializer', (serializers.Serializer,), dict(CHAMPS_CREATION))

#: Champs que le PATCH renvoie vers « Quand » (`planifier()` est le seul chemin du jour : invariant 15).
CHAMPS_PLANIFICATION = ('jour_prevu', 'moment', 'heure_debut', 'quelque_jour')
MESSAGE_PASSE_PAR_QUAND = 'Passe par « Quand ».'
MESSAGE_NON_MODIFIABLE = 'Non modifiable ici.'


@extend_schema_serializer(component_name='TachesCorpsTachePatch')
class TachePatchSerializer(CorpsTaches):
    """Corps de `PATCH taches/{id}/` : tout champ est facultatif SAUF `lock_version` (règle croisée : un PATCH
    publie ses champs facultatifs). Bornes et listes de `services.taches._bornes` / `_titre`, publiées ici."""

    titre = ChaineStricte(required=False, max_length=280, error_messages={
        'blank': MESSAGE_TITRE_VIDE, 'null': MESSAGE_TITRE_VIDE, 'max_length': '280 caractères au plus.'})
    notes = ChaineStricte(required=False, allow_blank=True)
    priorite = ChoixEntier(choices=list(Priorite.values), required=False, error_messages=_INCONNU)
    echeance = DateBornee(required=False, allow_null=True)
    echeance_heure = HeureStricte(required=False, allow_null=True)
    estimation_minutes = EntierStrict(required=False, allow_null=True, min_value=5, max_value=960,
                                      error_messages={'min_value': MESSAGE_ESTIMATION,
                                                      'max_value': MESSAGE_ESTIMATION})
    duree_reelle_minutes = EntierStrict(required=False, allow_null=True, min_value=0, max_value=ENTIER_32_MAX)
    projet_id = EntierStrict(required=False, allow_null=True)
    section_id = EntierStrict(required=False, allow_null=True)
    jalon = BooleenStrict(required=False)
    bloquee_par_id = EntierStrict(required=False, allow_null=True)
    confidentiel = BooleenStrict(required=False)
    etiquettes = serializers.ListField(required=False, child=EntierStrict(), max_length=50)
    recurrence = RegleModifieeField(required=False, allow_null=True)
    lien = LienLigneField(required=False, allow_null=True)
    lock_version = EntierStrict(min_value=0, error_messages={'required': MESSAGE_REQUIS})

    regles_croisees = ((present('lock_version', ENTIER),),)


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


#: Messages des refus d'un corps d'action : une valeur hors de sa liste, un champ manquant.
_CHOIX = {'required': MESSAGE_REQUIS, 'null': MESSAGE_REQUIS, 'blank': MESSAGE_REQUIS,
          'invalid_choice': MESSAGE_VALEUR_INCONNUE}
#: api-fuzz (r2) — chaque corps ci-dessous EST le schéma publié de sa route (`@extend_schema(request=…)`) :
#: listes fermées en `enum`, textes non blancs, bornes et règles croisées (`CorpsTaches.regles_croisees`) sont
#: dites au schéma par la même déclaration qui les applique.
_NON_BLANC = {'type': 'string', 'minLength': 1, 'pattern': MOTIF_NON_BLANC_SANS_NUL}
#: « Encore … » d'un rappel : une année au plus (au-delà, le calcul de la nouvelle heure déborde).
DANS_MINUTES_MAX = 366 * 24 * 60


def _choix(valeurs, **options):
    return Choix(choices=list(valeurs), error_messages=dict(_CHOIX), **options)


@extend_schema_serializer(component_name='TachesCorpsProprietaireAttendu')
class ProprietaireEntreeSerializer(CorpsTaches):
    """Corps facultatif de `terminer/` et `rouvrir/` : le compte qui a mis l'op en file (invariant 31)."""

    proprietaire_attendu = EntierStrict(required=False)


@extend_schema_serializer(component_name='TachesCorpsPlanifier')
class PlanifierEntreeSerializer(ProprietaireEntreeSerializer):
    """Corps de `planifier/` : le jour, l'heure, le moment ou « Plus tard » ; `lock_version` requis. Une heure
    demande un jour, sauf « Plus tard » (`services.planification._normaliser`, publié en règle croisée)."""

    jour_prevu = DateBornee(required=False, allow_null=True)
    moment = _choix(Moment.values, required=False, allow_blank=True)
    heure_debut = champ_heure(required=False, allow_null=True)
    quelque_jour = BooleenStrict(required=False)
    lock_version = EntierStrict(min_value=0, error_messages={'required': MESSAGE_REQUIS})

    regles_croisees = ((present('quelque_jour', parmi(True)), absent('heure_debut'),
                        valeur('heure_debut', None), present('jour_prevu', DATE)),)


@extend_schema_serializer(component_name='TachesCorpsTrancher')
class TrancherEntreeSerializer(CorpsTaches):
    choix = _choix(CHOIX_TRANCHER)
    jour = DateBornee(required=False, allow_null=True)

    regles_croisees = ((valeur('choix', *(c for c in CHOIX_TRANCHER if c != 'jour')), present('jour', DATE)),)


@extend_schema_serializer(component_name='TachesCorpsTacheAttendre')
class AttendreEntreeSerializer(CorpsTaches):
    en_attente_de = ChaineStricte(max_length=200, error_messages={
        'required': MESSAGE_ATTENTE_VIDE, 'null': MESSAGE_ATTENTE_VIDE, 'blank': MESSAGE_ATTENTE_VIDE,
        'max_length': MESSAGE_ATTENTE_LONGUE})


#: « `avant_id` ou `apres_id` » (un voisin au moins, non nul) : publié en règle croisée.
_UN_VOISIN = ((present('avant_id', ENTIER), present('apres_id', ENTIER)),)


@extend_schema_serializer(component_name='TachesCorpsReordonner')
class ReordonnerEntreeSerializer(CorpsTaches):
    """Corps de `reordonner/` : la place entre deux voisins (`avant_id` précède, `apres_id` suit)."""

    liste = _choix(LISTES)
    avant_id = EntierStrict(required=False, allow_null=True)
    apres_id = EntierStrict(required=False, allow_null=True)

    regles_croisees = _UN_VOISIN


@extend_schema_serializer(component_name='TachesCorpsTacheChangementApercu')
class ChangementEntreeSerializer(CorpsTaches):
    geste = _choix(GESTES_ECHO)
    titre = ChaineStricte(required=False, allow_blank=True)

    regles_croisees = ((valeur('geste', *(g for g in GESTES_ECHO if g != 'renommer')),
                        present('titre', {**_NON_BLANC, 'maxLength': 280})),)


@extend_schema_serializer(component_name='TachesCorpsRappel')
class RappelEntreeSerializer(CorpsTaches):
    """Corps de `rappels/` : `{jour, heure}` ou `{ancre, decalage_jours, heure}`."""

    jour = DateBornee(required=False)
    heure = champ_heure(error_messages={'required': MESSAGE_REQUIS, 'null': MESSAGE_REQUIS})
    ancre = _choix(AncreRappel.values, required=False, allow_blank=True)
    decalage_jours = EntierStrict(required=False, min_value=-7, max_value=0, error_messages={
        'min_value': 'Entre -7 et 0.', 'max_value': 'Entre -7 et 0.'})

    regles_croisees = ((present('jour', DATE),
                        present('ancre', parmi(*(a for a in AncreRappel.values if a)))),)


@extend_schema_serializer(component_name='TachesCorpsRepeter')
class RepeterEntreeSerializer(CorpsTaches):
    """Corps de `repeter/` : `{dans_minutes}` ou `{jour, heure}`."""

    dans_minutes = EntierStrict(required=False, min_value=1, max_value=DANS_MINUTES_MAX)
    jour = DateBornee(required=False)
    heure = champ_heure(required=False)

    regles_croisees = ((present('dans_minutes', ENTIER), {'required': ['jour', 'heure']}),)

    def validate(self, donnees):
        if 'dans_minutes' not in donnees and not ('jour' in donnees and 'heure' in donnees):
            raise serializers.ValidationError({'dans_minutes': [MESSAGE_REQUIS]})
        return donnees


@extend_schema_serializer(component_name='TachesCorpsRecurrence')
class RecurrenceEntreeSerializer(CorpsTaches):
    """Corps de `PATCH recurrences/{id}/` : tout est facultatif ; `actif: false` arrête la série. Les listes et
    les bornes sont celles de `services.taches.CONTROLES_REGLE`."""

    frequence = _choix(Frequence.values, required=False)
    intervalle = EntierStrict(required=False, min_value=1, max_value=99, error_messages={
        'min_value': MESSAGE_VALEUR_INCONNUE, 'max_value': MESSAGE_VALEUR_INCONNUE})
    jours_semaine = ChaineStricte(required=False, trim_whitespace=False,
                                  validators=[MotifPublie(MOTIF_SEMAINE, MESSAGE_VALEUR_INCONNUE)],
                                  error_messages={'invalid': MESSAGE_VALEUR_INCONNUE})
    jour_du_mois = EntierStrict(required=False, allow_null=True)
    rang_dans_mois = EntierStrict(required=False, allow_null=True)
    mode = _choix(ModeRecurrence.values, required=False)
    date_debut = DateBornee(required=False)
    date_fin = DateBornee(required=False, allow_null=True)
    actif = BooleenStrict(required=False)
    appliquer_a_l_ouverte = BooleenStrict(required=False)

    regles_croisees = ((valeur('jour_du_mois', None, *JOURS_DU_MOIS),),
                       (valeur('rang_dans_mois', None, *RANGS_DU_MOIS),))

    def validate_jour_du_mois(self, jour):
        if jour is not None and jour not in JOURS_DU_MOIS:
            raise serializers.ValidationError(MESSAGE_VALEUR_INCONNUE)
        return jour

    def validate_rang_dans_mois(self, rang):
        if rang is not None and rang not in RANGS_DU_MOIS:
            raise serializers.ValidationError(MESSAGE_VALEUR_INCONNUE)
        return rang


def _action(action, valeurs=None):
    branche = {'properties': {'action': parmi(action)}}
    if valeurs is not None:
        branche['required'] = ['valeurs']
        branche['properties']['valeurs'] = valeurs
    return branche


@extend_schema_serializer(component_name='TachesCorpsLot')
class LotEntreeSerializer(CorpsTaches):
    """Corps de `taches/lot/` : `ids` (1 à 200), `action`, `valeurs` selon l'action."""

    ids = serializers.ListField(child=EntierStrict(), allow_empty=False, min_length=1, max_length=MAX_LOT,
                                error_messages={'required': MESSAGE_REQUIS, 'empty': MESSAGE_REQUIS,
                                                'max_length': MESSAGE_LOT_LONG})
    action = _choix(ACTIONS_LOT)
    valeurs = serializers.DictField(required=False)

    regles_croisees = ((
        _action('deplacer', {'anyOf': [{'required': ['projet_id']}, {'required': ['par_tache']}]}),
        _action('planifier', {'anyOf': [
            {'required': ['quelque_jour'], 'properties': {'quelque_jour': {'enum': [True]}}},
            {'required': ['jour_prevu'], 'properties': {'jour_prevu': {
                'type': 'string', 'format': 'date', 'pattern': MOTIF_ANNEE_BORNEE}}}]}),
        _action('prioriser', {'required': ['priorite'], 'properties': {'priorite': {'enum': list(Priorite.values)}}}),
        _action('etiqueter', {'properties': {cle: {'type': 'array', 'items': {'type': 'integer'}}
                                             for cle in ('ajouter', 'retirer')}}),
        *(_action(a) for a in ACTIONS_LOT if a not in ('deplacer', 'planifier', 'prioriser', 'etiqueter')),
    ),)


@extend_schema_serializer(component_name='TachesCorpsChecklist')
class ChecklistEntreeSerializer(CorpsTaches):
    tache_id = EntierStrict(error_messages={'required': MESSAGE_REQUIS})
    libelle = ChaineStricte(max_length=255, error_messages={
        'required': MESSAGE_REQUIS, 'null': MESSAGE_REQUIS, 'blank': MESSAGE_LIBELLE_VIDE,
        'max_length': MESSAGE_LIBELLE_LONG})


@extend_schema_serializer(component_name='TachesCorpsChecklistElement')
class ElementChecklistEntreeSerializer(CorpsTaches):
    libelle = ChaineStricte(required=False, max_length=255, error_messages={
        'blank': MESSAGE_LIBELLE_VIDE, 'max_length': MESSAGE_LIBELLE_LONG})
    fait = BooleenStrict(required=False)


@extend_schema_serializer(component_name='TachesCorpsReordonnerElement')
class ReordonnerElementEntreeSerializer(CorpsTaches):
    """Corps de `checklist/{id}/reordonner/` : les voisins (`liste` est sans objet ici)."""

    liste = ChaineStricte(required=False)
    avant_id = EntierStrict(required=False, allow_null=True)
    apres_id = EntierStrict(required=False, allow_null=True)

    regles_croisees = _UN_VOISIN


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
    calculs = calculs_du_plan(user, [t for t in (instance['tache'], instance['suivante']) if t is not None])
    return TacheEcriteSerializer(instance, context=contexte(assistant=assistant, calculs=calculs)).data


def calculs_du_plan(user, taches, jour=None):
    """`essentielle` / `prevue_au_plan` d'une TACHE servie seule (fiche `GET taches/{id}/`, TACHE_ECRITE) : la
    MÊME source que la journée et la vue d'un projet (`serializers.projets.poser_calculs_d_items`), les lignes du
    plan de J, en UNE requête (`selectors.journee.lignes_de_taches_du_jour`). Sans elle, la fiche servait
    `essentielle: false` pour une ★ de la liste et l'étoile changeait d'avis à l'ouverture (couture L7)."""
    lignes = lignes_de_taches_du_jour(user, jour or timezone.localdate())
    return {('tache', t.pk): {'essentielle': bool(lignes[t.pk].essentielle),
                              'prevue_au_plan': bool(lignes[t.pk].prevue_au_plan)}
            for t in taches if t.pk in lignes}


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


def reponse_gestes(gestes, masques=frozenset(), titres=None):
    """Forme de `gestes.json` : `{"results": […]}` ; `annulable` tant que le geste n'est pas annulé.
    `masques` : ids des gestes d'une tâche confidentielle servis à l'assistant — leur message ne porte pas
    le texte saisi (`services.taches.gestes_confidentiels`), seulement l'état « En attente de… ».
    `titres` : `{id du geste: titre de la tâche}` (`services.gestes.titres_des_gestes`, R2-125), vide sous
    l'en-tête assistant."""
    titres = titres or {}
    return {'results': [{'id': g.pk, 'type': g.type,
                         'message': StatutTache.EN_ATTENTE.label if g.pk in masques else g.message,
                         'titre': titres.get(g.pk),
                         'created_at': _INSTANT.to_representation(g.created_at),
                         'annule_le': _INSTANT.to_representation(g.annule_le) if g.annule_le else None,
                         'annulable': g.annule_le is None} for g in gestes]}


# --- Étiquettes et vues enregistrées (TCH156) ----------------------------------------------------------

_REQUIS = {'required': MESSAGE_REQUIS, 'null': MESSAGE_REQUIS}
MESSAGE_INCONNU = 'Valeur inconnue.'


def _nom(maximum, message_long, **options):
    """Le `nom` d'une étiquette ou d'une vue : une vraie chaîne, non blanche, `maximum` signes (le service rogne et
    revérifie : `services.etiquettes._nom`)."""
    return ChaineStricte(max_length=maximum, error_messages={
        **_REQUIS, 'blank': MESSAGE_REQUIS, 'invalid': MESSAGE_INCONNU, 'max_length': message_long}, **options)


@extend_schema_serializer(component_name='TachesCorpsEtiquette')
class EtiquetteEntreeSerializer(CorpsTaches):
    """Corps de `POST etiquettes/` : `nom` (doublon jugé par le service) et `couleur` (une des couleurs de
    l'application ; vide ou absente : celle d'office)."""

    nom = _nom(40, MESSAGE_NOM_ETIQUETTE_LONG)
    couleur = Choix(choices=list(Couleur.values), required=False, allow_blank=True, allow_null=True,
                    error_messages=_INCONNU)


@extend_schema_serializer(component_name='TachesCorpsEtiquettePatch')
class EtiquettePatchSerializer(CorpsTaches):
    nom = _nom(40, MESSAGE_NOM_ETIQUETTE_LONG, required=False)
    couleur = Choix(choices=list(Couleur.values), required=False,
                    error_messages={**_INCONNU, 'null': MESSAGE_INCONNU})


#: `VueEnregistree.rang` est un `IntegerField` : l'entier signé 32 bits de la base (au-delà, 500 « integer out of
#: range » ; revue F4 #5).
RANG_MIN, RANG_MAX = -2 ** 31, 2 ** 31 - 1


def _rang_de_vue():
    return EntierStrict(required=False, min_value=RANG_MIN, max_value=RANG_MAX, error_messages={
        'invalid': MESSAGE_INCONNU, 'min_value': MESSAGE_INCONNU, 'max_value': MESSAGE_INCONNU})


class FiltresVueField(serializers.JSONField):
    """Les `filtres` d'une vue enregistrée : jugés par `services.etiquettes._valider_filtres` (clés fermées,
    valeurs de même nature que les paramètres de `GET taches/`) ; publiés à l'identique ci-dessous."""


def _ids_publies():
    return {'type': 'array', 'maxItems': MAX_IDS, 'items': {'type': 'integer'}}


class _FiltresVuePublies(OpenApiSerializerFieldExtension):
    target_class = 'apps.taches.serializers.saisie.FiltresVueField'

    def map_serializer_field(self, auto_schema, direction):
        if direction != 'request':
            return auto_schema._map_serializer_field(self.target, direction, bypass_extensions=True)
        booleen = {'type': 'boolean'}
        return {'type': 'object', 'additionalProperties': False, 'properties': {
            'q': {'type': 'string', 'maxLength': MAX_Q, 'pattern': MOTIF_SANS_NUL},
            'projets': _ids_publies(), 'etiquettes': _ids_publies(),
            'priorite_min': {'type': 'integer', **parmi(*Priorite.values)},
            'statuts': {'type': 'array', 'minItems': 1, 'items': {'type': 'string', **parmi(*StatutTache.values)}},
            'periode': {'type': 'string', **parmi(*PERIODES)}, 'tri': {'type': 'string', **parmi(*TRIS)},
            'groupe': {'type': 'string', **parmi(*GROUPES)}, 'echeance': booleen, 'inclure_faites': booleen,
        }}


@extend_schema_serializer(component_name='TachesCorpsVue')
class VueEntreeSerializer(CorpsTaches):
    """Corps de `POST vues/` : `filtres` est jugé (clés fermées) par le service."""

    nom = _nom(60, MESSAGE_NOM_VUE_LONG)
    filtres = FiltresVueField(required=False)
    rang = _rang_de_vue()


@extend_schema_serializer(component_name='TachesCorpsVuePatch')
class VuePatchSerializer(CorpsTaches):
    nom = _nom(60, MESSAGE_NOM_VUE_LONG, required=False)
    filtres = FiltresVueField(required=False)
    rang = _rang_de_vue()


def forme_etiquette(etiquette):
    """Une ligne de `etiquettes.json` : `{id, nom, couleur}`."""
    return {'id': etiquette.pk, 'nom': etiquette.nom, 'couleur': etiquette.couleur}


def reponse_etiquette(etiquette, geste):
    """Écriture d'une étiquette : sa forme + `geste_id` (null si rien n'a changé)."""
    return {**forme_etiquette(etiquette), 'geste_id': geste.pk if geste is not None else None}


def forme_vue(vue):
    """Une vue de `vues.json` : `{id, nom, rang, filtres}`."""
    return {'id': vue.pk, 'nom': vue.nom, 'rang': vue.rang, 'filtres': vue.filtres}


def reponse_vue(vue, geste):
    return {**forme_vue(vue), 'geste_id': geste.pk if geste is not None else None}
