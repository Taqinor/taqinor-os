"""Corps de requête et réponses des routes `projets/`, `sections/` et `revue/` (reference/api.md §3.3, §4).

Deux familles : des sérialiseurs de VALIDATION (le corps reçu, messages de `textes.md` §2.16 — tutoiement,
sous le champ fautif) et des CONSTRUCTEURS de réponse, qui rendent EXACTEMENT les clés des échantillons de
`contract_samples/` (`projets_liste`, `projet_ecrit`, `projet_vue`, `planification`, `planification_apercu`,
`decalage`, `revue_projets`, `revue_decision`). Les formes PROJET et ITEM viennent de `serializers/formes.py`,
jamais recopiées ; ce que ces formes ne calculent pas seules (santé, compteurs…) vient de
`selectors/projets.etat_projets` par `contexte(calculs=…)`.
"""
from django.db.models import F
from rest_framework import serializers

from apps.taches.choix import Couleur, IssueProjet, Priorite, StatutProjet, StatutTache
from apps.taches.saisie.collage import MAX_LIGNES, MESSAGE_TROP_DE_LIGNES, erreurs_limites
from apps.taches.saisie.plan import decouper_plan
from apps.taches.selectors import projets as lecture
from apps.taches.selectors.base import sections_de, taches_de
from apps.taches.serializers.formes import (
    AFFICHAGE_DEFAUT, ItemSerializer, ProjetSerializer, TacheSerializer, charger_items, charger_taches, contexte,
)

REQUIS = 'Requis.'
VALEUR_INCONNUE = 'Valeur inconnue.'
CLE_INCONNUE = 'Clé inconnue.'
PASSE_PAR_TERMINER = 'Passe par « Terminer ».'
ATTEINT_OU_ABANDONNE = 'Atteint ou abandonné ?'
DATES_INVERSEES = 'La date de fin précède la date de début.'
VUES = ('liste', 'tableau', 'chronologie')
ISSUES = tuple(valeur for valeur in IssueProjet.values if valeur)  # atteint, abandonne
MAX_TACHES_DU_PLAN = MAX_LIGNES


def _messages(longueur=None, **plus):
    messages = {'required': REQUIS, 'null': REQUIS, 'blank': REQUIS, 'invalid_choice': VALEUR_INCONNUE, **plus}
    if longueur is not None:
        messages['max_length'] = f'{longueur} caractères au plus.'
    return messages


def _texte(longueur, **options):
    return serializers.CharField(max_length=longueur, error_messages=_messages(longueur), **options)


def _version():
    return serializers.IntegerField(min_value=0, error_messages=_messages(min_value='Valeur inconnue.'))


# --- Corps reçus ---------------------------------------------------------------------------------

class ProjetCreationSerializer(serializers.Serializer):
    """POST projets/ — seul `nom` est exigé (couleur d'office, priorité 0)."""

    nom = _texte(120)
    priorite = serializers.ChoiceField(choices=Priorite.values, required=False, default=Priorite.AUCUNE,
                                       error_messages=_messages())
    couleur = serializers.ChoiceField(choices=Couleur.values, required=False, error_messages=_messages())
    icone = _texte(8, required=False, allow_blank=True)
    objectif = serializers.CharField(required=False, allow_blank=True, error_messages=_messages())
    domaine = _texte(40, required=False, allow_blank=True)


class ProjetModificationSerializer(serializers.Serializer):
    """PATCH projets/{id}/ — tout champ facultatif sauf `lock_version` ; `termine` passe par « Terminer »."""

    nom = _texte(120, required=False)
    objectif = serializers.CharField(required=False, allow_blank=True, error_messages=_messages())
    icone = _texte(8, required=False, allow_blank=True)
    couleur = serializers.ChoiceField(choices=Couleur.values, required=False, error_messages=_messages())
    priorite = serializers.ChoiceField(choices=Priorite.values, required=False, error_messages=_messages())
    statut = serializers.ChoiceField(choices=StatutProjet.values, required=False, error_messages=_messages())
    date_debut = serializers.DateField(required=False, allow_null=True)
    echeance = serializers.DateField(required=False, allow_null=True)
    domaine = _texte(40, required=False, allow_blank=True)
    confidentiel = serializers.BooleanField(required=False)
    affichage = serializers.DictField(required=False)
    risque = _texte(280, required=False, allow_blank=True)
    lock_version = _version()

    def validate_statut(self, valeur):
        if valeur == StatutProjet.TERMINE:
            raise serializers.ValidationError(PASSE_PAR_TERMINER)
        return valeur

    def validate_affichage(self, valeur):
        if set(valeur) - set(AFFICHAGE_DEFAUT):
            raise serializers.ValidationError(CLE_INCONNUE)
        if 'vue' in valeur and valeur['vue'] not in VUES:
            raise serializers.ValidationError(VALEUR_INCONNUE)
        if 'montrer_faites' in valeur and not isinstance(valeur['montrer_faites'], bool):
            raise serializers.ValidationError(VALEUR_INCONNUE)
        for cle in ('tri', 'groupe'):
            if cle in valeur and not (isinstance(valeur[cle], str) and 0 < len(valeur[cle]) <= 20):
                raise serializers.ValidationError(VALEUR_INCONNUE)
        return valeur


class TerminerSerializer(serializers.Serializer):
    """POST projets/{id}/terminer/ — `issue` obligatoire ; sort des tâches ouvertes."""

    issue = serializers.ChoiceField(choices=ISSUES,
                                    error_messages={**_messages(), 'required': ATTEINT_OU_ABANDONNE,
                                                    'null': ATTEINT_OU_ABANDONNE, 'blank': ATTEINT_OU_ABANDONNE,
                                                    'invalid_choice': ATTEINT_OU_ABANDONNE})
    bilan = _texte(280, required=False, allow_blank=True)
    taches_ouvertes = serializers.ChoiceField(choices=['boite', 'annuler', 'deplacer'], required=False,
                                              error_messages=_messages())
    projet_cible_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, donnees):
        if donnees.get('taches_ouvertes') == 'deplacer' and donnees.get('projet_cible_id') is None:
            raise serializers.ValidationError({'projet_cible_id': [REQUIS]})
        return donnees


class ReordonnerSerializer(serializers.Serializer):
    """POST …/reordonner/ — la place entre deux voisins (`avant_id` : juste avant lui ; `apres_id` : juste après)."""

    avant_id = serializers.IntegerField(required=False, allow_null=True)
    apres_id = serializers.IntegerField(required=False, allow_null=True)
    liste = serializers.CharField(required=False, allow_blank=True)  # sans objet pour un projet ou une étape


class SectionCreationSerializer(serializers.Serializer):
    """POST sections/ — `{projet_id, nom, date_debut?, date_fin?}`."""

    projet_id = serializers.IntegerField(error_messages=_messages())
    nom = _texte(120)
    date_debut = serializers.DateField(required=False, allow_null=True)
    date_fin = serializers.DateField(required=False, allow_null=True)

    def validate(self, donnees):
        return _dates_ordonnees(donnees)


class SectionModificationSerializer(serializers.Serializer):
    """PATCH sections/{id}/ — renommer, dates."""

    nom = _texte(120, required=False)
    date_debut = serializers.DateField(required=False, allow_null=True)
    date_fin = serializers.DateField(required=False, allow_null=True)

    def validate(self, donnees):
        return _dates_ordonnees(donnees)


def _dates_ordonnees(donnees):
    debut, fin = donnees.get('date_debut'), donnees.get('date_fin')
    if debut is not None and fin is not None and fin < debut:
        raise serializers.ValidationError({'date_fin': [DATES_INVERSEES]})
    return donnees


class ApercuPlanSerializer(serializers.Serializer):
    """POST projets/{id}/planification/apercu/ — `{texte}`, jamais écrit."""

    texte = serializers.CharField(trim_whitespace=False, error_messages=_messages())

    def validate_texte(self, texte):
        erreurs = erreurs_limites(texte)
        if erreurs:
            raise serializers.ValidationError(erreurs['texte'])
        return texte


class _TachePlanSerializer(serializers.Serializer):
    titre = _texte(280)
    jalon = serializers.BooleanField(required=False, default=False)
    sous_taches = serializers.ListField(child=_texte(280), required=False)


class _EtapePlanSerializer(serializers.Serializer):
    nom = _texte(120, required=False, allow_null=True, allow_blank=True)
    taches = _TachePlanSerializer(many=True)


class _ActionPlanSerializer(serializers.Serializer):
    titre = _texte(280)
    quand = serializers.ChoiceField(choices=['aujourdhui', 'demain', 'plus_tard', ''], required=False,
                                    allow_blank=True, error_messages=_messages())


class PlanificationSerializer(serializers.Serializer):
    """POST projets/{id}/planification/ — tout créer, priorité comprise (verrou 409)."""

    priorite = serializers.ChoiceField(choices=Priorite.values, required=False, error_messages=_messages())
    objectif = serializers.CharField(required=False, allow_blank=True, error_messages=_messages())
    echeance = serializers.DateField(required=False, allow_null=True)
    risque = _texte(280, required=False, allow_blank=True)
    sections = _EtapePlanSerializer(many=True, required=False)
    actions = _ActionPlanSerializer(many=True, required=False)
    lock_version = _version()

    def validate(self, donnees):
        nombre = sum(1 + len(t.get('sous_taches', ())) for s in donnees.get('sections', ()) for t in s['taches'])
        nombre += len(donnees.get('actions', ()))
        if nombre > MAX_TACHES_DU_PLAN:
            raise serializers.ValidationError({'sections': [MESSAGE_TROP_DE_LIGNES.format(n=nombre)]})
        return donnees


class DecalerSerializer(serializers.Serializer):
    """POST projets/{id}/decaler/ — `{delta_jours, apercu}` (sans `apercu`, rien n'est écrit)."""

    delta_jours = serializers.IntegerField(min_value=-3650, max_value=3650, error_messages=_messages(
        min_value=VALEUR_INCONNUE, max_value=VALEUR_INCONNUE))
    apercu = serializers.BooleanField(required=False, default=True)


class VueProjetSerializer(serializers.Serializer):
    """GET projets/{id}/vue/?vue= — la vue demandée (les trois servent le même contenu)."""

    vue = serializers.ChoiceField(choices=VUES, required=False, error_messages=_messages())


# --- Réponses ------------------------------------------------------------------------------------

def _iso(valeur):
    return valeur.isoformat() if valeur is not None else None


def contexte_de(etat, *, assistant):
    """Le contexte des formes PROJET et ITEM pour l'état calculé `etat`."""
    return contexte(assistant=assistant, reglages=etat.reglages, calculs=etat.calculs)


def forme_projet(projet, ctx):
    """La forme PROJET d'un projet."""
    return ProjetSerializer(projet, context=ctx).data


def geste_de(resultat):
    return resultat.geste.pk if getattr(resultat, 'geste', None) is not None else None


def projet_ecrit(resultat, ctx):
    """`projet_ecrit.json` : le projet et ce que l'écriture a déplacé, rendu, supprimé."""
    return {'projet': forme_projet(resultat.projet, ctx), 'deplacees': resultat.deplacees,
            'restaurees': resultat.restaurees, 'supprimees': resultat.supprimees, 'geste_id': geste_de(resultat)}


def section_ecrite(section, geste):
    """La réponse de `sections/` : l'étape écrite et son geste."""
    return {'id': section.pk, 'projet_id': section.projet_id, 'nom': section.nom, 'rang': section.rang,
            'date_debut': _iso(section.date_debut), 'date_fin': _iso(section.date_fin),
            'geste_id': geste.pk if geste is not None else None}


def apercu_du_plan(texte):
    """`planification_apercu.json` : la liste collée lue (étapes, tâches, jalons, sous-tâches), rien d'écrit."""
    return decouper_plan(texte)


def planification_rendue(user, resultat, ctx):
    """`planification.json` : le projet, les tâches créées (forme TACHE) et le geste."""
    ids = [t.pk for t in resultat.creees]
    creees = {t.pk: t for t in charger_taches(taches_de(user).filter(pk__in=ids))}
    return {'projet': forme_projet(resultat.projet, ctx),
            'creees': TacheSerializer([creees[i] for i in ids], many=True, context=ctx).data,
            'geste_id': geste_de(resultat)}


def decalage_rendu(changements, geste):
    return {'changements': changements, 'geste_id': geste.pk if geste is not None else None}


def _item(user, pk, ctx, chargees):
    """L'ITEM de la tâche `pk` (déjà chargée, sinon lue) ou `None`."""
    if pk is None:
        return None
    tache = chargees.get(pk) or charger_items(taches_de(user).filter(pk=pk)).first()
    return ItemSerializer(tache, context=ctx).data if tache is not None else None


def _sections_de_la_vue(user, projet, taches, ctx):
    """Les étapes du projet (avec leurs ITEM) et les ITEM « sans étape »."""
    par_etape = {}
    for tache in taches:
        par_etape.setdefault(tache.section_id, []).append(tache)
    etapes = [{'id': s.pk, 'nom': s.nom, 'rang': s.rang, 'date_debut': _iso(s.date_debut),
               'date_fin': _iso(s.date_fin),
               'taches': ItemSerializer(par_etape.get(s.pk, []), many=True, context=ctx).data}
              for s in sections_de(user).filter(projet=projet).order_by('rang', 'id')]
    return etapes, ItemSerializer(par_etape.get(None, []), many=True, context=ctx).data


def vue_du_projet(user, projet, etat, ctx, jour):
    """`projet_vue.json` : en-tête PROJET, avancement, prochain jalon, prochaine action, étapes, tâches sans
    étape, nombre de faites, burn-up. Les tâches faites ne sont servies que si `affichage.montrer_faites`."""
    pures = etat.taches_de(projet.pk)
    montrer = bool((projet.affichage or {}).get('montrer_faites'))
    statuts = lecture.OUVERTS + ((StatutTache.FAIT,) if montrer else ())
    taches = list(charger_items(taches_de(user).filter(projet=projet, parent__isnull=True, statut__in=statuts)
                                .order_by(F('rang_projet').asc(nulls_last=True), 'id')))
    chargees = {t.pk: t for t in taches}
    etapes, sans_etape = _sections_de_la_vue(user, projet, taches, ctx)
    points, legende = lecture.burnup_de(pures, jour)
    return {
        'projet': forme_projet(projet, ctx), 'avancement': lecture.avancement_de(pures),
        'prochain_jalon': _item(user, lecture.prochain_jalon_id(pures), ctx, chargees),
        'prochaine_action': _item(user, lecture.prochaine_action_id(pures), ctx, chargees),
        'sections': etapes, 'sans_section': sans_etape,
        'faites_nb': etat.calculs[('projet', projet.pk)]['compteurs']['faites'],
        'burnup': points, 'burnup_legende': legende,
    }
