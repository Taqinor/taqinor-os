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

from apps.taches.choix import Couleur, DecisionRevue, IssueProjet, Priorite, StatutProjet, StatutTache
from apps.taches.confidentialite import nom_pour
from apps.taches.saisie.collage import MAX_LIGNES, MESSAGE_TROP_DE_LIGNES, erreurs_limites
from apps.taches.saisie.plan import decouper_plan
from apps.taches.selectors import journee as journee_lue
from apps.taches.selectors import projets as lecture
from apps.taches.selectors.base import sections_de, taches_de
from apps.taches.serializers.formes import (
    AFFICHAGE_DEFAUT, ItemSerializer, ProjetSerializer, TacheSerializer, charger_items, charger_taches, contexte,
)
from apps.taches.serializers.journee import nom_du_projet, texte_explication

REQUIS = 'Requis.'
VALEUR_INCONNUE = 'Valeur inconnue.'
CLE_INCONNUE = 'Clé inconnue.'
PASSE_PAR_TERMINER = 'Passe par « Terminer ».'
ATTEINT_OU_ABANDONNE = 'Atteint ou abandonné ?'
DATES_INVERSEES = 'La date de fin précède la date de début.'
VUES = ('liste', 'tableau', 'chronologie')
ISSUES = tuple(valeur for valeur in IssueProjet.values if valeur)  # atteint, abandonne


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
        if nombre > MAX_LIGNES:
            raise serializers.ValidationError({'sections': [MESSAGE_TROP_DE_LIGNES.format(n=nombre)]})
        return donnees


class DecalerSerializer(serializers.Serializer):
    """POST projets/{id}/decaler/ — `{delta_jours, apercu}` (sans `apercu`, rien n'est écrit)."""

    delta_jours = serializers.IntegerField(min_value=-3650, max_value=3650, error_messages=_messages(
        min_value=VALEUR_INCONNUE, max_value=VALEUR_INCONNUE))
    apercu = serializers.BooleanField(required=False, default=True)


class RevueDecisionSerializer(serializers.Serializer):
    """PUT revue/projets/{projet_id}/ — la décision d'une carte (`terminer` exige `issue`)."""

    semaine = serializers.DateField(error_messages=_messages())
    intention = _texte(200, required=False, allow_blank=True)
    prochaine_action_id = serializers.IntegerField(required=False, allow_null=True)
    decision = serializers.ChoiceField(choices=[c for c in DecisionRevue.values if c], error_messages=_messages())
    focus = serializers.BooleanField(required=False, default=False)
    issue = serializers.ChoiceField(choices=ISSUES, required=False,
                                    allow_null=True, allow_blank=True, error_messages=_messages())

    def validate(self, donnees):
        if donnees['decision'] == DecisionRevue.TERMINER and not donnees.get('issue'):
            raise serializers.ValidationError({'issue': [ATTEINT_OU_ABANDONNE]})
        return donnees


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


def poser_calculs_d_items(user, taches, etat, ctx):
    """`explication`, `essentielle`, `prevue_au_plan` des ITEM de `taches` servis hors de la journée
    (vue d'un projet, revue) : le MÊME calcul que la journée (`texte_explication` sur l'`ItemPur`, jours
    travaillés et projets « de la semaine » lus par `etat_projets`), et les lignes du plan de J lues en UNE
    requête. Écrit dans `ctx['calculs']` ; les calculs déjà posés (santé du projet) sont gardés."""
    usage = 'assistant' if ctx['assistant'] else 'ecran'
    lignes = journee_lue.lignes_de_taches_du_jour(user, etat.jour)
    for tache in taches:
        ligne = lignes.get(tache.pk)
        item = journee_lue.item_de_tache(tache, etat.focus)
        ctx['calculs'][('tache', tache.pk)] = {
            **ctx['calculs'].get(('tache', tache.pk), {}),
            'explication': texte_explication(item, tache, nom_du_projet(tache, usage, ctx['reglages']), etat.jour,
                                             etat.travailles_journee),
            'essentielle': bool(ligne and ligne.essentielle),
            'prevue_au_plan': bool(ligne and ligne.prevue_au_plan)}


def _item(user, pk, ctx, chargees, etat):
    """L'ITEM de la tâche `pk` (déjà chargée, sinon lue avec ses calculs) ou `None`."""
    if pk is None:
        return None
    tache = chargees.get(pk)
    if tache is None:
        tache = charger_items(taches_de(user).filter(pk=pk)).first()
        if tache is not None:
            poser_calculs_d_items(user, [tache], etat, ctx)
    return ItemSerializer(tache, context=ctx).data if tache is not None else None


def _sections_de_la_vue(user, projet, taches, ctx, pures):
    """Les étapes du projet (avec leurs ITEM et leur compte `{ouvertes, faites}`, calculé de TOUTES ses
    tâches même quand les faites ne sont pas servies) et les ITEM « sans étape »."""
    par_etape = {}
    for tache in taches:
        par_etape.setdefault(tache.section_id, []).append(tache)
    comptes = lecture.compteurs_par_etape(pures)
    etapes = [{'id': s.pk, 'nom': s.nom, 'rang': s.rang, 'date_debut': _iso(s.date_debut),
               'date_fin': _iso(s.date_fin),
               'taches': ItemSerializer(par_etape.get(s.pk, []), many=True, context=ctx).data,
               'compteurs': comptes.get(s.pk, {'ouvertes': 0, 'faites': 0})}
              for s in sections_de(user).filter(projet=projet).order_by('rang', 'id')]
    sans = comptes.get(None, {'ouvertes': 0, 'faites': 0})
    return etapes, ItemSerializer(par_etape.get(None, []), many=True, context=ctx).data, sans


def vue_du_projet(user, projet, etat, ctx, jour):
    """`projet_vue.json` : en-tête PROJET, avancement, prochain jalon, prochaine action, étapes, tâches sans
    étape, nombre de faites, burn-up. Les tâches faites ne sont servies que si `affichage.montrer_faites`."""
    pures = etat.taches_de(projet.pk)
    montrer = bool((projet.affichage or {}).get('montrer_faites'))
    statuts = lecture.OUVERTS + ((StatutTache.FAIT,) if montrer else ())
    taches = list(charger_items(taches_de(user).filter(projet=projet, parent__isnull=True, statut__in=statuts)
                                .order_by(F('rang_projet').asc(nulls_last=True), 'id')))
    chargees = {t.pk: t for t in taches}
    poser_calculs_d_items(user, taches, etat, ctx)
    etapes, sans_etape, sans_compteurs = _sections_de_la_vue(user, projet, taches, ctx, pures)
    points, legende = lecture.burnup_de(pures, jour)
    return {
        'projet': forme_projet(projet, ctx), 'avancement': lecture.avancement_de(pures),
        'prochain_jalon': _item(user, lecture.prochain_jalon_id(pures), ctx, chargees, etat),
        'prochaine_action': _item(user, lecture.prochaine_action_id(pures), ctx, chargees, etat),
        'sections': etapes, 'sans_section': sans_etape, 'sans_section_compteurs': sans_compteurs,
        'faites_nb': etat.calculs[('projet', projet.pk)]['compteurs']['faites'],
        'burnup': points, 'burnup_legende': legende,
    }


def _titre(tache, ctx):
    return nom_pour(tache, 'assistant' if ctx['assistant'] else 'ecran', ctx['reglages'])


def _carte_de_revue(carte, ctx, prochaines):
    revue = carte.revue
    return {
        'projet': forme_projet(carte.projet, ctx),
        'faites_semaine': [{'id': t.pk, 'titre': _titre(t, ctx)} for t in carte.faites[:3]],
        'faites_nb': len(carte.faites),
        'bloquees': [{'id': t.pk, 'titre': _titre(t, ctx),
                      'attend': {'id': t.bloquee_par_id, 'titre': _titre(t.bloquee_par, ctx)}} for t in carte.bloquees],
        'prochaine_action': _item_de_revue(carte.prochaine_id, ctx, prochaines),
        'revue': {'intention': revue.intention if revue else '', 'decision': revue.decision if revue else '',
                  'focus': revue.focus if revue else False},
    }


def _item_de_revue(pk, ctx, prochaines):
    tache = prochaines.get(pk)
    return ItemSerializer(tache, context=ctx).data if tache is not None else None


def revue_des_projets(user, etat, ctx, lundi):
    """`revue_projets.json` : bilan de la semaine (ou Semaine courte), projet « de la semaine » et une carte
    par projet actif."""
    cartes = lecture.cartes_de_revue(user, etat, lundi)
    ids = [c.prochaine_id for c in cartes if c.prochaine_id is not None]
    prochaines = {t.pk: t for t in charger_items(taches_de(user).filter(pk__in=ids))}
    poser_calculs_d_items(user, list(prochaines.values()), etat, ctx)
    mode = etat.reglages.mode if etat.reglages else 'pousser'
    courte, bilan = lecture.bilan_de_semaine(user, lundi, mode)
    focus = next((c.projet.pk for c in cartes if c.revue is not None and c.revue.focus), None)
    return {'semaine': lundi.isoformat(), 'semaine_courte': courte, 'bilan_semaine': bilan,
            'focus_projet_id': focus, 'cartes': [_carte_de_revue(c, ctx, prochaines) for c in cartes]}


def decision_rendue(revue, projet, geste, ctx):
    """`revue_decision.json` : la revue enregistrée, le projet après la décision et le geste."""
    return {'revue': {'semaine': revue.semaine.isoformat(), 'intention': revue.intention,
                      'decision': revue.decision, 'focus': revue.focus,
                      'prochaine_action_id': revue.prochaine_action_id},
            'projet': forme_projet(projet, ctx), 'geste_id': geste.pk if geste is not None else None}
