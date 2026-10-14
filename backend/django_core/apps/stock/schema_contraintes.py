"""ENF11 (achats) — contraintes de requête que le schéma OpenAPI doit DIRE.

Constat (api-fuzz, ``/api/django/achats/``) : une création est refusée en 400
alors que le corps généré respecte le schéma publié, parce que ce schéma
ignore des règles que les serializers appliquent déjà :

* **liste non vide** — ``lignes`` d'un BCF / d'une réception / d'un retour doit
  porter au moins une ligne (``validate_lignes``). drf-spectacular n'émet
  ``minItems`` ni pour ``Serializer(many=True)`` ni pour ``allow_empty=False``
  (seul ``ListField(min_length=…)`` l'est) ;
* **quantité strictement positive** (``validate_quantite``) : le schéma
  annonçait tout l'intervalle d'un entier 32 bits, négatifs compris ;
* **montant strictement positif** (``validate_montant``) : un ``DecimalField``
  est publié en chaîne ``^-?\\d{0,12}(?:\\.\\d{0,2})?$`` — qui admet la chaîne
  vide, « - » ou « . », illisibles pour le serveur ;
* **ligne de BCF** : un ``produit`` OU une ``designation`` libre
  (``validate`` de la ligne, XPUR16).

Plutôt que d'ajouter ces déclarations dans ``serializers.py`` (fichier-mur de
plus de 2 800 lignes), un crochet ``POSTPROCESSING_HOOKS`` les pose sur les
composants de REQUÊTE concernés. Il est **déclaratif et sans effet à
l'exécution** : aucune validation n'est ajoutée ni retirée, les règles
ci-dessous sont celles que le code applique déjà — le contrat publié cesse
seulement de mentir par omission. Un composant absent du document (module
désactivé) est simplement ignoré.
"""
from __future__ import annotations

import re

#: Un schéma de chaîne décimale « fait de chiffres » : au moins un chiffre de
#: chaque côté du séparateur quand il y en a un (la regex de drf-spectacular en
#: admettait zéro).
_MOTIF_DECIMAL = re.compile(r'\\d\{[01],(\d+)\}')

LIGNES_NON_VIDE = {'lignes': {'minItems': 1}}
QUANTITE_POSITIVE = {'quantite': {'minimum': 1}}

#: Une ligne de BCF désigne un produit OU porte une désignation libre.
PRODUIT_OU_DESIGNATION = {
    'anyOf': [
        {'type': 'object', 'required': ['produit'],
         'properties': {'produit': {'type': 'integer'}}},
        {'type': 'object', 'required': ['designation'],
         'properties': {'designation': {'type': 'string', 'pattern': r'\S'}}},
    ],
}

#: ``lim_phases`` (fiche limiteur) : 1, 3 ou vide (``validate_lim_phases``).
PHASES_LIMITEUR = {'type': 'integer', 'enum': [1, 3, None], 'nullable': True,
                   'description': 'Limiteur — 1 ou 3 phases (vide = non publié).'}

#: Rendement en % borné à [1 ; 100] avec UNE décimale
#: (``MinValueValidator(1)`` / ``MaxValueValidator(100)``, ``decimal_places=1``).
MOTIF_POURCENTAGE_1_100 = r'^(?:[1-9]\d?(?:\.\d?)?|100(?:\.0?)?)$'

#: composant de requête -> {'proprietes': {champ: fragment fusionné},
#: 'racine': fragment fusionné à la racine du composant}.
CONTRAINTES = {
    'BonCommandeFournisseurRequest': {'proprietes': LIGNES_NON_VIDE},
    'PatchedBonCommandeFournisseurRequest': {'proprietes': LIGNES_NON_VIDE},
    'LigneBonCommandeFournisseurRequest': {
        'proprietes': QUANTITE_POSITIVE, 'racine': PRODUIT_OU_DESIGNATION},
    'PatchedLigneBonCommandeFournisseurRequest': {
        'proprietes': QUANTITE_POSITIVE},
    'ReceptionFournisseurRequest': {'proprietes': LIGNES_NON_VIDE},
    'PatchedReceptionFournisseurRequest': {'proprietes': LIGNES_NON_VIDE},
    'LigneReceptionFournisseurRequest': {'proprietes': QUANTITE_POSITIVE},
    'PatchedLigneReceptionFournisseurRequest': {
        'proprietes': QUANTITE_POSITIVE},
    'RetourFournisseurRequest': {'proprietes': LIGNES_NON_VIDE},
    'PatchedRetourFournisseurRequest': {'proprietes': LIGNES_NON_VIDE},
    'LigneRetourFournisseurRequest': {'proprietes': QUANTITE_POSITIVE},
    'PatchedLigneRetourFournisseurRequest': {'proprietes': QUANTITE_POSITIVE},
    'PaiementFournisseurRequest': {'montants_positifs': ['montant']},
    'PatchedPaiementFournisseurRequest': {'montants_positifs': ['montant']},
    # ERR-ENF11-FUZZ-STOCK (CI #997) — fiche technique : les bornes que les
    # validateurs du modèle appliquent et qu'une chaîne décimale ne porte pas.
    # Rendements 1–100 % (1 décimale), C-rate ≥ 0,01, `lim_phases` = 1 ou 3.
    'FicheTechniqueRequest': {
        'pourcentages_1_100': ['ond_rendement_max_pct', 'ond_rendement_cec_pct'],
        'montants_positifs': ['bat_c_rate_charge', 'bat_c_rate_decharge'],
        'remplacer': {'lim_phases': PHASES_LIMITEUR}},
    'PatchedFicheTechniqueRequest': {
        'pourcentages_1_100': ['ond_rendement_max_pct', 'ond_rendement_cec_pct'],
        'montants_positifs': ['bat_c_rate_charge', 'bat_c_rate_decharge'],
        'remplacer': {'lim_phases': PHASES_LIMITEUR}},
    'PrixFournisseurRequest': {},
    'PatchedPrixFournisseurRequest': {},
    'TrancheEcheancierRequest': {},
    # ERR-ENF11-FUZZ-STOCK — montants / facteurs strictement positifs et
    # quantités réellement lues (un corps sans ``quantite`` : « Quantité
    # invalide. »), règles que les services appliquent déjà.
    'AcompteFournisseurRequest': {'montants_positifs': ['montant']},
    'PatchedAcompteFournisseurRequest': {'montants_positifs': ['montant']},
    'ConditionnementProduitRequest': {'montants_positifs': ['facteur']},
    'PatchedConditionnementProduitRequest': {'montants_positifs': ['facteur']},
    'BlocageQualiteRequest': {
        'proprietes': QUANTITE_POSITIVE, 'requis': ['quantite']},
    'DepotConsignationRequest': {
        'proprietes': {'quantite_deposee': {'minimum': 1}},
        'requis': ['quantite_deposee']},
    'MouvementRebutRequest': {
        'proprietes': QUANTITE_POSITIVE, 'requis': ['quantite']},
    'TransfertStockRequest': {'proprietes': QUANTITE_POSITIVE},
    'TransfertDemanderCorpsRequest': {'proprietes': QUANTITE_POSITIVE},
    'ProduitRebutCorpsRequest': {'proprietes': QUANTITE_POSITIVE},
    # Un mouvement libre ne déclare pas un rebut (motif obligatoire : la
    # déclaration de rebut) ; le scanner ne rend que ses trois gestes.
    'MouvementStockRequest': {'remplacer': {'type_mouvement': {
        'type': 'string',
        'enum': ['entree', 'sortie', 'transfert', 'ajustement']}}},
    'ScannerMouvementCorpsRequest': {'proprietes': QUANTITE_POSITIVE},
    # ``poids_kg: ""`` est lu comme « non renseigné » (décimal nullable DRF).
    'UniteLogistiqueRequest': {'vide_accepte': ['poids_kg']},
    'PatchedUniteLogistiqueRequest': {'vide_accepte': ['poids_kg']},
    # Fusion de BCF : au moins deux identifiants, DISTINCTS (deux fois le même
    # est un seul BCF, donc « au moins deux » n'est pas atteint).
    'BcfFusionnerCorpsRequest': {
        'proprietes': {'bons_commande': {'uniqueItems': True}},
        'elements': {'bons_commande': {'minimum': 1, 'maximum': 2147483647}}},
}


def _chiffres_obligatoires(motif: str) -> str:
    return _MOTIF_DECIMAL.sub(lambda m: '\\d{1,%s}' % m.group(1), motif)


def _motif_decimal_positif(motif: str) -> str:
    """Chaîne décimale STRICTEMENT positive dérivée du motif d'origine."""
    tailles = [int(n) for n in _MOTIF_DECIMAL.findall(motif)]
    entiers = tailles[0] if tailles else 12
    decimales = tailles[1] if len(tailles) > 1 else 2
    positif_entier = r'[1-9]\d{0,%d}(?:\.\d{1,%d})?' % (
        max(entiers - 1, 0), decimales)
    positif_fraction = r'0\.\d{0,%d}[1-9]' % max(decimales - 1, 0)
    return '^(?:%s|%s)$' % (positif_entier, positif_fraction)


def _reparer_decimaux(proprietes: dict) -> None:
    for propriete in proprietes.values():
        if not isinstance(propriete, dict):
            continue
        motif = propriete.get('pattern')
        if propriete.get('format') == 'decimal' and isinstance(motif, str):
            propriete['pattern'] = _chiffres_obligatoires(motif)


def declarer_contraintes_achats(result, generator=None, request=None,
                                public=None, **kwargs):
    """Crochet POSTPROCESSING_HOOKS de drf-spectacular (mute et renvoie)."""
    schemas = (result.get('components') or {}).get('schemas') or {}
    for nom, regles in CONTRAINTES.items():
        composant = schemas.get(nom)
        if not isinstance(composant, dict):
            continue
        proprietes = composant.get('properties') or {}
        _reparer_decimaux(proprietes)
        for champ, fragment in (regles.get('proprietes') or {}).items():
            if isinstance(proprietes.get(champ), dict):
                proprietes[champ] = {**proprietes[champ], **fragment}
        for champ in regles.get('montants_positifs') or ():
            propriete = proprietes.get(champ)
            if isinstance(propriete, dict) and propriete.get('pattern'):
                propriete['pattern'] = _motif_decimal_positif(
                    propriete['pattern'])
        for champ in regles.get('pourcentages_1_100') or ():
            propriete = proprietes.get(champ)
            if isinstance(propriete, dict) and propriete.get('pattern'):
                propriete['pattern'] = MOTIF_POURCENTAGE_1_100
        for champ, remplacement in (regles.get('remplacer') or {}).items():
            if champ in proprietes:
                proprietes[champ] = dict(remplacement)
        for champ in regles.get('vide_accepte') or ():
            propriete = proprietes.get(champ)
            if isinstance(propriete, dict) and 'oneOf' not in propriete:
                nullable = propriete.pop('nullable', False)
                proprietes[champ] = {'nullable': nullable, 'oneOf': [
                    propriete, {'type': 'string', 'enum': ['']}]}
        for champ in regles.get('requis') or ():
            requis = composant.setdefault('required', [])
            if champ not in requis:
                requis.append(champ)
        for champ, fragment in (regles.get('elements') or {}).items():
            elements = (proprietes.get(champ) or {}).get('items')
            if isinstance(elements, dict):
                elements.update(fragment)
        composant.update(regles.get('racine') or {})
    _gestes_scannables(schemas)
    return result


def _gestes_scannables(schemas: dict) -> None:
    """``type_mouvement`` du scanner = ``TYPES_MOUVEMENT_SCANNABLES`` (la
    source unique du service) : publié en énumération, jamais recopié."""
    composant = schemas.get('ScannerMouvementCorpsRequest')
    propriete = ((composant or {}).get('properties') or {}).get('type_mouvement')
    if isinstance(propriete, dict):
        from .services_wms import TYPES_MOUVEMENT_SCANNABLES
        propriete.pop('minLength', None)
        propriete.pop('pattern', None)
        propriete['enum'] = list(TYPES_MOUVEMENT_SCANNABLES)
