"""CIQ214 — conditions C&I d'un devis (retenue de garantie, pénalités de
retard, caution) : la forme PUBLIÉE et la validation, une seule source.

CI #997 (2) (api-fuzz « rejected schema-compliant request », ``PUT devis``
``caution: [null, null]``) — les trois champs étaient publiés en JSON libre
(``{"nullable": true}``) alors que le sérialiseur exige des objets précis :
une liste conforme au schéma recevait 400. Le schéma dit désormais la forme
exacte, et le serveur n'accepte que cette forme (plus de ``""`` lu « vide »,
plus de ``liberation: null`` ni de nature numérique convertie en texte, plus
de caractère nul que la colonne JSON refuse en 500).

Formes normalisées inchangées (enregistrer → rouvrir → enregistrer sans
toucher = en-tête identique, test CIQ214). Les motifs se lisent comme le
validateur du schéma (regex Rust de jsonschema-rs) : motif ancré lu par
``re.fullmatch`` ; « non blanc » = ``core.champs_stricts.non_blanc``.
"""
import re
from decimal import Decimal

from rest_framework import serializers

from core.champs_stricts import (
    MOTIF_NON_BLANC_SANS_NUL, MOTIF_SANS_NUL, non_blanc,
)

from apps.ventes.utils.echeancier import schema_echeancier

#: Pourcentage écrit en texte : ``]0 ; 100]``, virgule ou point décimal.
MOTIF_POURCENT_POSITIF = (
    r'^(?:100(?:[.,]0+)?|[1-9]\d?(?:[.,]\d+)?|0?[.,]\d*[1-9]\d*)$')

_POURCENT = {'anyOf': [
    {'type': 'number', 'minimum': 0, 'exclusiveMinimum': True,
     'maximum': 100},
    {'type': 'string', 'pattern': MOTIF_POURCENT_POSITIF}]}
_TEXTE_OU_NOMBRE = {'nullable': True, 'anyOf': [
    {'type': 'string', 'pattern': MOTIF_SANS_NUL}, {'type': 'number'}]}
#: ``{}`` vaut « non demandé » (comme ``null``).
_VIDE = {'type': 'object', 'maxProperties': 0}


def _objet(requis, proprietes):
    return {'nullable': True, 'anyOf': [_VIDE, {
        'type': 'object', 'required': list(requis),
        'properties': proprietes}]}


#: Bornes d'argent de l'en-tête (ATOT21, contraintes ``ck_devis_*``) : la
#: chaîne que le serveur ACCEPTE, exactement (décimal 2 places, ``-0``
#: compris) — ``"150"`` pour la remise ou ``"-1"`` pour l'acompte étaient
#: publiés conformes puis refusés (400 / 500 ``CheckViolation``).
def _zero_negatif(entiers):
    return r'-(?:0{1,%d}(?:\.0{0,2})?|\.0{1,2})' % entiers


MOTIF_REMISE = (r'^(?:100(?:\.0{0,2})?|0?\d{1,2}(?:\.\d{0,2})?|\.\d{1,2}|'
                + _zero_negatif(3) + ')$')
MOTIF_ACOMPTE = (r'^(?:\d{1,10}(?:\.\d{0,2})?|\.\d{1,2}|'
                 + _zero_negatif(10) + ')$')


def _decimal_borne(motif, maximum, nullable=False):
    branches = [{'type': 'string', 'format': 'decimal', 'pattern': motif},
                {'type': 'number', 'minimum': 0, 'maximum': maximum}]
    for branche in branches if nullable else ():
        branche['nullable'] = True
    return {'anyOf': branches, **({'nullable': True} if nullable else {})}


SCHEMAS = {
    'remise_globale': _decimal_borne(MOTIF_REMISE, 100),
    # QJR21 — ``EcheancierValidationMixin`` : null, ``""``, ou une liste de
    # tranches OBJETS ; CI #997 (4) — dont ``pct_or_montant`` est obligatoire
    # (source unique : ``utils.echeancier``, jumelle du refus 400).
    'echeancier': schema_echeancier(),
    'acompte_montant': _decimal_borne(
        MOTIF_ACOMPTE, 9999999999.99, nullable=True),
    'retenue_garantie': _objet(('taux_pct',), {
        'taux_pct': _POURCENT,
        'liberation': {'type': 'string', 'enum': ['reception_definitive']}}),
    'penalites_retard_livraison': _objet(
        ('taux_pct_par_semaine', 'plafond_pct'),
        {'taux_pct_par_semaine': _POURCENT, 'plafond_pct': _POURCENT}),
    'caution': _objet(('nature',), {
        'nature': {'type': 'string', 'pattern': MOTIF_NON_BLANC_SANS_NUL},
        'montant_ou_pct': _TEXTE_OU_NOMBRE, 'plafond': _TEXTE_OU_NOMBRE}),
}


def publier(fields):
    """Pose la forme publiée de chaque champ de ``SCHEMAS`` présent dans
    ``fields`` (conditions C&I + bornes d'argent de l'en-tête)."""
    from drf_spectacular.drainage import set_override
    for nom, schema in SCHEMAS.items():
        if nom in fields:
            set_override(fields[nom], 'field', schema)


def _nombre(valeur):
    return isinstance(valeur, (int, float)) and not isinstance(valeur, bool)


def pourcentage(champ, brut):
    """``]0 ; 100]`` en nombre ou en texte publié, rendu en ``float``."""
    if not (_nombre(brut) or (
            isinstance(brut, str)
            and re.fullmatch(MOTIF_POURCENT_POSITIF, brut))):
        raise serializers.ValidationError(
            f"« {champ} » : un pourcentage numérique est attendu.")
    valeur = Decimal(str(brut).strip().replace(',', '.'))
    if not valeur.is_finite() or valeur <= 0 or valeur > 100:
        raise serializers.ValidationError(
            f"« {champ} » doit être compris entre 0 et 100 %.")
    return float(valeur)


def _vide(value):
    return value is None or (isinstance(value, dict) and not value)


def retenue(value):
    if _vide(value):
        return None
    if not isinstance(value, dict):
        raise serializers.ValidationError(
            "Retenue de garantie : un objet {taux_pct, liberation} est "
            "attendu.")
    liberation = value.get('liberation', 'reception_definitive')
    if liberation != 'reception_definitive':
        raise serializers.ValidationError(
            "« retenue_garantie.liberation » : seule la réception "
            "définitive libère la retenue (reception_definitive).")
    return {'taux_pct': pourcentage('retenue_garantie.taux_pct',
                                    value.get('taux_pct')),
            'liberation': liberation}


def penalites(value):
    if _vide(value):
        return None
    if not isinstance(value, dict):
        raise serializers.ValidationError(
            "Pénalités de retard : un objet {taux_pct_par_semaine, "
            "plafond_pct} est attendu.")
    for cle, libelle in (('taux_pct_par_semaine', 'le taux par semaine'),
                         ('plafond_pct', 'le plafond')):
        if value.get(cle) in (None, ''):
            raise serializers.ValidationError(
                f"Pénalités de retard : {libelle} "
                f"(penalites_retard_livraison.{cle}) est obligatoire — "
                "taux et plafond vont ensemble.")
    return {cle: pourcentage(f'penalites_retard_livraison.{cle}',
                             value.get(cle))
            for cle in ('taux_pct_par_semaine', 'plafond_pct')}


def caution(value):
    if _vide(value):
        return None
    nature = value.get('nature') if isinstance(value, dict) else None
    if not isinstance(nature, str) or '\x00' in nature or not non_blanc(
            nature):
        raise serializers.ValidationError(
            "Caution : la nature (caution.nature) est obligatoire.")
    for cle in ('montant_ou_pct', 'plafond'):
        brut = value.get(cle)
        if not (brut is None or _nombre(brut) or (
                isinstance(brut, str) and '\x00' not in brut)):
            raise serializers.ValidationError(
                f"« caution.{cle} » : un texte ou un nombre est attendu.")
    return {'nature': nature.strip(),
            'montant_ou_pct': value.get('montant_ou_pct'),
            'plafond': value.get('plafond')}
