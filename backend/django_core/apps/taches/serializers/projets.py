"""Corps de requête et réponses des routes `projets/`, `sections/` et `revue/` (reference/api.md §3.3, §4).

Deux familles : des sérialiseurs de VALIDATION (le corps reçu, messages de `textes.md` §2.16 — tutoiement,
sous le champ fautif) et des CONSTRUCTEURS de réponse, qui rendent EXACTEMENT les clés des échantillons de
`contract_samples/` (`projets_liste`, `projet_ecrit`, `projet_vue`, `planification`, `planification_apercu`,
`decalage`, `revue_projets`, `revue_decision`). Les formes PROJET et ITEM viennent de `serializers/formes.py`,
jamais recopiées ; ce que ces formes ne calculent pas seules (santé, compteurs…) vient de
`selectors/projets.etat_projets` par `contexte(calculs=…)`.
"""
from rest_framework import serializers

from apps.taches.choix import Couleur, IssueProjet, Priorite, StatutProjet
from apps.taches.saisie.collage import MAX_LIGNES
from apps.taches.serializers.formes import AFFICHAGE_DEFAUT, ProjetSerializer, contexte

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
