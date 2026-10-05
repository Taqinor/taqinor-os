"""CIQ107 — profils de charge de REPLI : archétypes SOURCÉS seulement.

Module PUR : aucun import Django, aucune base lue. La seule entrée-sortie est
la lecture du fichier vendorisé ``donnees/archetypes_charge.json`` (forme :
clé ``donnees_archetypes`` du contrat ``etude_ci_preview.json``), embarqué
par l'image Django (``COPY . /app/``).

Règles (D-CIQ-1, audit W5) :

* un archétype n'existe que s'il est recalculé depuis un fichier PRIMAIRE
  (BDEW G1-G5 via demandlib, NREL ComStock AMY2018) dont la LICENCE a été
  vérifiée ; sinon il n'est pas vendorisé et la catégorie exige un profil
  déclaré ;
* hammam, autre et TOUT industriel n'ont AUCUN archétype ;
* un profil SAISI par la société (``ProfilTypeConsommation`` CAL149, passé
  par l'orchestrateur) passe devant l'archétype ;
* aucun scalaire « part diurne » n'est produit ni servi : on rend une forme
  24 h (Σ = 1) et sa source.
"""

import json
import os
from functools import lru_cache

FICHIER_DONNEES = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'donnees', 'archetypes_charge.json')

TYPES_JOUR = ('ouvre', 'samedi', 'dimanche')
SAISONS = ('hiver', 'ete', 'transition')

MOTIF_PROFIL_DECLARE = 'profil déclaré exigé'

#: Catégories volontairement sans archétype (aucune donnée sourcée) ; tout
#: site industriel passe ``categorie='industriel'`` (ou aucune catégorie).
CATEGORIES_SANS_ARCHETYPE = frozenset({'hammam', 'autre', 'industriel'})

#: Saisons CAL149 lues pour chaque saison du moteur C&I, dans l'ordre.
_SAISONS_SOCIETE = {
    'hiver': ('hiver', 'annuel'),
    'ete': ('ete', 'annuel'),
    'transition': ('printemps', 'automne', 'annuel'),
}
#: Types de jour CAL149 (``ouvre``/``weekend``/``ferie``) lus pour chacun des nôtres.
_JOURS_SOCIETE = {
    'ouvre': ('ouvre',),
    'samedi': ('weekend',),
    'dimanche': ('weekend',),
}


@lru_cache(maxsize=1)
def donnees_archetypes():
    """Le fichier vendorisé, lu une fois (dict, à ne pas muter)."""
    with open(FICHIER_DONNEES, encoding='utf-8') as fh:
        return json.load(fh)


def _archetype_pour(categorie):
    for archetype in donnees_archetypes()['archetypes']:
        if categorie in archetype['categories']:
            return archetype
    return None


def _normaliser(valeurs):
    nombres = [float(v) for v in valeurs]
    if len(nombres) != 24 or any(n < 0 for n in nombres):
        return None
    total = sum(nombres)
    if total <= 0:
        return None
    return [n / total for n in nombres]


def _courbe_societe(courbe, type_jour, saison):
    """La courbe 24 h du profil société pour (type_jour, saison), ou None.

    ``courbe`` suit CAL149 : ``{saison: [24]}`` (forme plate, tous types de
    jour) ou ``{saison: {jour_type: [24]}}`` (CALX258).
    """
    if not isinstance(courbe, dict):
        return None
    for cle_saison in _SAISONS_SOCIETE[saison]:
        valeur = courbe.get(cle_saison)
        if valeur is None:
            continue
        if isinstance(valeur, dict):
            for cle_jour in _JOURS_SOCIETE[type_jour]:
                if valeur.get(cle_jour) is not None:
                    return _normaliser(valeur[cle_jour])
            continue
        return _normaliser(valeur)
    return None


def forme_archetype(categorie, type_jour, saison, *, profil_societe=None):
    """Forme 24 h normalisée (Σ = 1) et sa source, ou ``(None, motif)``.

    ``profil_societe`` : ``{'cle', 'libelle', 'courbe', 'provenance'}`` d'un
    profil CAL149 de la société (familles commercial/industriel), passé par
    l'orchestrateur ; il passe devant l'archétype.
    ``categorie`` : clé ``categorie_commerciale`` du lead ; ``industriel`` (ou
    ``None``) ⇒ aucun archétype, profil déclaré exigé.
    """
    if type_jour not in TYPES_JOUR:
        raise ValueError(f'type de jour inconnu : {type_jour!r}')
    if saison not in SAISONS:
        raise ValueError(f'saison inconnue : {saison!r}')

    if profil_societe:
        forme = _courbe_societe(profil_societe.get('courbe'), type_jour, saison)
        if forme is not None:
            return forme, {
                'type': 'profil_societe',
                'cle': profil_societe.get('cle'),
                'libelle': profil_societe.get('libelle'),
                'provenance': profil_societe.get('provenance'),
                'statut': 'declare',
            }

    if not categorie or categorie in CATEGORIES_SANS_ARCHETYPE:
        return None, f'{MOTIF_PROFIL_DECLARE} : aucun archétype sourcé pour « {categorie} »'

    archetype = _archetype_pour(categorie)
    if archetype is None:
        # Licence non confirmée ou catégorie inconnue : l'archétype n'est pas vendorisé.
        return None, f'{MOTIF_PROFIL_DECLARE} : aucun archétype sourcé pour « {categorie} »'

    forme = list(archetype['forme'][type_jour][saison])
    source = dict(archetype['source'])
    return forme, {
        'type': 'archetype',
        'cle': archetype['cle'],
        'jeu_de_donnees': source['jeu_de_donnees'],
        'url': source['url'],
        'fichier': source['fichier'],
        'date_releve': source['date_releve'],
        'licence': source['licence'],
        'statut': archetype['statut'],
    }
