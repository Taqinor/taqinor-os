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

from core.champs_stricts import QUANTITE_MAX

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

#: ICE : vide (non renseigné) ou exactement 15 chiffres (``validate_ice`` du
#: serializer fournisseur / ``validate_ice_format``) — le schéma publiait une
#: chaîne libre de 20 caractères.
ICE_15_CHIFFRES = {'ice': {'pattern': r'^(?:\d{15})?$', 'maxLength': 15}}

#: CI #997 fuzz — composant de kit (``KitComposantSerializer``) : un produit OU
#: un sous-kit (``validate`` XOR, XMFG17), taux de perte dans [0 ; 100[.
PRODUIT_XOR_SOUS_KIT = {'anyOf': [
    {'required': ['produit'], 'properties': {
        'produit': {'type': 'integer'}, 'composant_kit': {'nullable': True, 'enum': [None]}}},
    {'required': ['composant_kit'], 'properties': {
        'composant_kit': {'type': 'integer'}, 'produit': {'nullable': True, 'enum': [None]}}},
]}
MOTIF_TAUX_0_100 = r'^(?:\d{1,2}(?:\.\d{1,2})?|\.\d{1,2})$'

#: CI #997 fuzz — mouvement libre (``MouvementStockViewSet.perform_create``) :
#: le transfert a sa route (refusé ici) ; ENTREE/SORTIE > 0, AJUSTEMENT = un
#: niveau visé ≥ 0.
TYPE_MOUVEMENT_LIBRE = {'type': 'string', 'enum': ['entree', 'sortie', 'ajustement']}
QUANTITE_SELON_TYPE = {'anyOf': [
    {'properties': {'type_mouvement': {'enum': ['entree', 'sortie']}, 'quantite': {'minimum': 1}}},
    {'properties': {'type_mouvement': {'enum': ['ajustement']}, 'quantite': {'minimum': 0}}},
]}

#: CI #997 fuzz — édition de prix en masse (``apply_product_bulk``) : mode
#: percent (> -100 %) ou fixed (> 0), bornés à 99 999 999,99 ; les autres
#: actions ignorent mode/valeur.
MOTIF_VARIATION_PCT = r'^(?:-(?:[1-9]\d?|0)(?:\.\d{1,2})?|(?:[1-9]\d{0,7}|0)(?:\.\d{1,2})?)$'
MOTIF_PRIX_FIXE = r'^(?:[1-9]\d{0,7}(?:\.\d{1,2})?|0\.(?:0[1-9]|[1-9]\d?))$'
PRIX_EN_MASSE = {'anyOf': [
    {'required': ['mode', 'valeur'], 'properties': {
        'action': {'enum': ['set_price']}, 'mode': {'enum': ['percent']},
        'valeur': {'type': 'string', 'pattern': MOTIF_VARIATION_PCT}}},
    {'required': ['mode', 'valeur'], 'properties': {
        'action': {'enum': ['set_price']}, 'mode': {'enum': ['fixed']},
        'valeur': {'type': 'string', 'pattern': MOTIF_PRIX_FIXE}}},
    {'properties': {'action': {'enum': ['set_warranty', 'set_category', 'set_brand']}}},
]}

#: CI #997 fuzz (2) — l'écran d'édition en masse envoie garanties et catégorie
#: en TEXTE (saisie brute, ``String(id)``, ``""``) : ``_params_bulk`` les lit
#: (``entier_ou_400``) ; publiés entier OU chaîne de chiffres (vide = rien).
GARANTIE_EN_MASSE = {'nullable': True, 'anyOf': [
    {'type': 'integer', 'minimum': 0, 'maximum': 2147483647},
    {'type': 'string', 'pattern': r'^(?:\d{1,9})?$'}]}
CATEGORIE_EN_MASSE = {'nullable': True, 'anyOf': [
    {'type': 'integer', 'maximum': 2147483647},
    {'type': 'string', 'pattern': r'^(?:\d{1,9}|null)?$'}]}

#: CI #997 fuzz (2) — champs JSON de la fiche produit : leur FORME, telle que
#: ``ProduitSerializer.validate_courbe_pompe`` / ``validate_courbe_source`` /
#: ``validate_paliers_prix_vente`` / ``validate_custom_data`` l'appliquent
#: (publiés « valeur quelconque », toute forme passait pour conforme).
#: ``seuil_min`` >= 0 et < ``seuil_max`` : la borne basse n'est PAS publiée en
#: ``minimum`` (le générateur pousserait seuil_min à 1 = seuil_max « 1 »,
#: couple que la règle croisée refuse) — elle est dite en description.
_NOMBRE_OU_TEXTE = {'description': 'Nombre >= 0, strictement inférieur à seuil_max.',
                    'anyOf': [{'type': 'number'}, {'type': 'string', 'pattern': r'^\d+(?:[.,]\d+)?$'}]}
_STRICT_POSITIF = {'anyOf': [
    {'type': 'number', 'minimum': 0, 'exclusiveMinimum': True},
    {'type': 'string', 'pattern': r'^(?:0*[1-9]\d*(?:[.,]\d+)?|0*[.,]\d*[1-9]\d*)$'}]}
CHAMPS_JSON_PRODUIT = {
    # Objet ; ses séries (débits STRICTEMENT croissants, HMT non croissante,
    # mêmes longueurs, >= 2 points) ne s'expriment pas en JSON Schema : la
    # règle est dite en description et par l'exemple (seule valeur générée).
    'courbe_pompe': {
        'type': 'object', 'nullable': True,
        'description': ('{"debits_m3h": [...], "hmt_m": [...]} : >= 2 points, débits '
                        'STRICTEMENT croissants, HMT non croissante, mêmes longueurs, valeurs >= 0.'),
        'example': {'debits_m3h': [0, 12], 'hmt_m': [91, 85]}},
    'courbe_source': {
        'type': 'object', 'nullable': True, 'additionalProperties': False,
        'properties': {'document': {'type': 'string', 'nullable': True},
                       'date': {'type': 'string', 'format': 'date', 'nullable': True},
                       'page': {'type': 'integer', 'nullable': True}},
        'example': {'document': '', 'date': None, 'page': None}},
    'paliers_prix_vente': {
        'type': 'array', 'nullable': True,
        'description': 'Paliers triés, sans recouvrement (seuil_max exclu ≤ seuil_min suivant).',
        'items': {'type': 'object', 'additionalProperties': False, 'required': ['prix_vente_ttc'],
                  'properties': {'seuil_min': _NOMBRE_OU_TEXTE,
                                 'seuil_max': {'nullable': True, 'anyOf': [
                                     *_STRICT_POSITIF['anyOf'], {'type': 'string', 'enum': ['']}]},
                                 'prix_vente_ttc': _STRICT_POSITIF}},
        'example': [{'seuil_min': 0, 'seuil_max': None, 'prix_vente_ttc': 1000}]},
    'custom_data': {'type': 'object', 'nullable': True, 'additionalProperties': True},
}

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
    'FournisseurRequest': {'proprietes': ICE_15_CHIFFRES},
    'PatchedFournisseurRequest': {'proprietes': ICE_15_CHIFFRES},
    # CI #997 fuzz — `prix_achat` : la fiche produit l'envoie en NOMBRE JSON
    # (``parseFloat``), que le serveur accepte déjà (≤ 2 décimales).
    'PrixFournisseurRequest': {'nombre_accepte': ['prix_achat']},
    'PatchedPrixFournisseurRequest': {'nombre_accepte': ['prix_achat']},
    # CI #997 fuzz — décimaux nullables : ``""`` est lu « non renseigné ».
    'AccordRFAFournisseurRequest': {'vide_accepte': ['taux_pct', 'montant_fixe']},
    'PatchedAccordRFAFournisseurRequest': {'vide_accepte': ['taux_pct', 'montant_fixe']},
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
    'MouvementStockRequest': {'remplacer': {'type_mouvement': TYPE_MOUVEMENT_LIBRE},
                              'proprietes': {'quantite': {'maximum': QUANTITE_MAX}},
                              'racine': QUANTITE_SELON_TYPE},
    'KitProduitComposantRequest': {'montants_positifs': ['quantite'],
                                   'motifs': {'taux_perte_pct': MOTIF_TAUX_0_100},
                                   'racine': PRODUIT_XOR_SOUS_KIT},
    'ProduitRequest': {'remplacer': CHAMPS_JSON_PRODUIT},
    'PatchedProduitRequest': {'remplacer': CHAMPS_JSON_PRODUIT},
    'ProduitBulkCorpsRequest': {'racine': PRIX_EN_MASSE, 'remplacer': {
        'garantie_mois': GARANTIE_EN_MASSE, 'garantie_production_mois': GARANTIE_EN_MASSE,
        'categorie_id': CATEGORIE_EN_MASSE}},
    'ScannerMouvementCorpsRequest': {'proprietes': QUANTITE_POSITIVE},
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


def _chaine_ou_nombre(propriete: dict) -> dict:
    """Décimal-chaîne -> « chaîne OU nombre JSON » de même précision (bornes
    et pas tirés du motif : un nombre à 3 décimales reste refusé)."""
    tailles = [int(n) for n in _MOTIF_DECIMAL.findall(propriete['pattern'])]
    entiers = tailles[0] if tailles else 12
    decimales = tailles[1] if len(tailles) > 1 else 2
    pas = 10 ** -decimales
    maxi = round(10 ** entiers - pas, decimales)
    chaine = {k: v for k, v in propriete.items() if k not in ('description', 'nullable')}
    nombre = {'type': 'number', 'multipleOf': pas, 'maximum': maxi,
              'minimum': -maxi if propriete['pattern'].startswith('^-?') else 0}
    autres = {k: v for k, v in propriete.items() if k in ('description', 'nullable')}
    return {**autres, 'anyOf': [chaine, nombre]}


def _branche_chaine(propriete: dict) -> dict:
    """La branche qui porte le motif d'un décimal : la propriété elle-même, ou
    la branche chaîne d'un ``anyOf`` chaîne|nombre (``DecimalSouple``)."""
    return next((b for b in propriete.get('anyOf', ()) if 'pattern' in b), propriete)


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
        for champ, motif in (regles.get('motifs') or {}).items():
            if isinstance(proprietes.get(champ), dict):
                _branche_chaine(proprietes[champ])['pattern'] = motif
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
        for champ in regles.get('nombre_accepte') or ():
            propriete = proprietes.get(champ)
            if isinstance(propriete, dict) and propriete.get('pattern'):
                proprietes[champ] = _chaine_ou_nombre(propriete)
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
        # CI #997 fuzz (2) — ASTK196 : un TRANSFERT scanné nomme au moins un
        # casier (source ou destination) ; les autres gestes, sans condition.
        libres = [t for t in TYPES_MOUVEMENT_SCANNABLES if t != 'transfert']
        composant['anyOf'] = [{'properties': {'type_mouvement': {'enum': libres}}}] + [
            {'required': [casier], 'properties': {
                'type_mouvement': {'enum': ['transfert']}, casier: {'type': 'integer'}}}
            for casier in ('bin_source', 'bin_destination')]
