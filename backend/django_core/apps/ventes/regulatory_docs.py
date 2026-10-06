"""FG267 — Packs documentaires réglementaires par régime (loi 82-21).

Donne, pour un régime de raccordement (``regime_8221``), la LISTE DES PIÈCES
réglementaires à constituer pour le dossier déposé chez le distributeur (ONEE
ou SRM régionale). CIQ616 : chaque pièce porte son ÉTAPE et sa SOURCE (article
de la loi 82-21 ou du décret 2.25.100) — forme ``pieces`` du contrat partagé
``contract_samples/dossier_8221.json``. Les codes de régime sont EXACTEMENT
ceux de ``apps.installations.regime`` / ``Installation.Regime8221`` — on ne les
redéfinit pas, on les MAPPE :

  * ``declaration_bt``        — déclaration (BT, sous le seuil sourcé)
  * ``accord_raccordement``   — accord de raccordement (chez le distributeur)
  * ``autorisation_anre``     — autorisation (ministère) ; code historique
    conservé, l'ANRE n'est PAS un guichet (CIQ612/CIQ616)
  * ``non_concerne``          — aucun dossier à déposer (régime non qualifié)
  * ``declaration_hors_reseau`` — AGR603 : installation NON raccordée au réseau.
    Loi 82-21 art. 3 (BO 7400) : l'autoconsommation isolée relève d'une
    DÉCLARATION, quelle que soit la puissance — elle n'est PAS hors loi 82-21.
  * ``a_qualifier``           — CIQ616 : régime inconnu (puissance ou niveau
    inconnu) ; aucune pièce, motif exposé.

Cœur PUR (fonction sans Django) : c'est de la donnée de RÉFÉRENCE réutilisée par
le suivi de dossier (FG268+) et par tout générateur de déclaration (FG272). On
ne touche pas l'app installations (couche découplée) : le régime arrive ici sous
forme de simple chaîne. Aucun prix, aucun changement de statut de devis.
"""
from __future__ import annotations


def _PIECE(code, label, etape, source, obligatoire=True):
    """Pièce documentaire : code stable + libellé FR + étape + source.

    ``obligatoire`` = pièce sans laquelle l'étape ne peut pas être franchie.
    ``required`` reste un alias historique d'``obligatoire`` (FG267, rendu de
    la déclaration FG272)."""
    return {'code': code, 'label': label, 'etape': etape,
            'obligatoire': obligatoire, 'required': obligatoire,
            'source': source}


_ART1 = 'décret 2.25.100 art. 1'
_ART12 = 'décret 2.25.100 art. 12'
_ART15 = 'décret 2.25.100 art. 15 (accord et autorisation seulement)'
_ART9_A_CONFIRMER = 'décret 2.25.100 art. 9 — contenu à confirmer'

_LIBELLE_SCHEMA = "Schéma électrique complet de l'installation"
_LIBELLE_FICHES = "Fiches techniques des équipements (fabricant et modèle)"

# Pièces COMMUNES à tout dossier raccordé au réseau (décret 2.25.100 art. 1).
# Le distributeur est l'ONEE OU la SRM régionale selon la zone : jamais
# « ONEE » seul. Codes historiques conservés (aucune donnée migrée).
_COMMON_PIECES = [
    _PIECE('cni_client', "Identité et registre de commerce du demandeur",
           'depot', _ART1),
    _PIECE('titre_droit_usage',
           "Titre de propriété ou droit d'usage du site", 'depot', _ART1),
    _PIECE('engagement_non_cession',
           "Engagement de non-cession de la production", 'depot', _ART1),
    _PIECE('contrat_onee',
           "Contrat / référence du distributeur (ONEE ou SRM régionale)",
           'depot',
           "référence du point de livraison chez le distributeur — "
           "à confirmer avec le distributeur"),
]

# Pièces techniques du dossier de demande (décret 2.25.100 art. 12).
_ART12_PIECES = [
    _PIECE('schema_unifilaire', _LIBELLE_SCHEMA, 'depot', _ART12),
    _PIECE('plan_situation', "Plan de situation du site", 'depot', _ART12),
    _PIECE('coordonnees_gps', "Coordonnées GPS du site", 'depot', _ART12),
    _PIECE('fiches_techniques', _LIBELLE_FICHES, 'depot', _ART12),
    _PIECE('planning_travaux', "Planning de réalisation", 'depot', _ART12),
    _PIECE('conso_3_ans', "Consommation des trois dernières années",
           'depot', _ART12),
    _PIECE('etude_impact', "Étude d'impact", 'depot',
           "selon la législation en vigueur — à confirmer "
           "(décret 2.25.100 art. 12)", obligatoire=False),
]

# Pièces exigées pour EXPLOITER (décret 2.25.100 art. 15) : accord et
# autorisation seulement — la déclaration (art. 9) n'exige pas l'assurance.
_EXPLOITATION_PIECES = [
    _PIECE('certificat_organisme_agree', "Certificat d'un organisme agréé",
           'exploitation', _ART15),
    _PIECE('preuve_propriete', "Preuve de propriété de l'installation",
           'exploitation', _ART15),
    _PIECE('attestation_assurance', "Attestation d'assurance",
           'exploitation',
           "décret 2.25.100 art. 15 (accord et autorisation seulement ; la "
           "déclaration, art. 9, ne l'exige pas)"),
]

# Autres autorisations propres au site (décret 2.25.100 art. 26).
_ART26_PIECE = _PIECE(
    'autres_autorisations', "Autres autorisations requises du site",
    'travaux', "décret 2.25.100 art. 26 (à la charge du client)",
    obligatoire=False)

_CONVENTION_PIECE = _PIECE(
    'convention_raccordement', "Convention de raccordement signée",
    'convention', "décret 2.25.100 art. 14")

# Pièces SPÉCIFIQUES par régime, ajoutées aux pièces communes. Aucune pièce
# MT de découplage tant que les prescriptions du distributeur ne sont pas
# lues (tâche manuelle) — jamais une pièce inventée.
_REGIME_PIECES = {
    'declaration_bt': [
        _PIECE('formulaire_declaration_bt', "Formulaire de déclaration",
               'depot', "décret 2.25.100 art. 9"),
        _PIECE('schema_unifilaire', _LIBELLE_SCHEMA, 'depot',
               _ART9_A_CONFIRMER),
        _PIECE('fiches_techniques', _LIBELLE_FICHES, 'depot',
               _ART9_A_CONFIRMER),
        _ART26_PIECE,
    ],
    'accord_raccordement': [
        _PIECE('demande_accord_raccordement',
               "Demande d'accord de raccordement", 'depot',
               "loi 82-21 art. 4 ; décret 2.25.100 art. 11"),
        *_ART12_PIECES,
        _PIECE('etude_raccordement',
               "Paiement des frais de l'étude du distributeur", 'etude',
               "décret 2.25.100 art. 27"),
        _PIECE('reglages_etude',
               "Réglages imposés par l'étude du distributeur", 'etude',
               "décret 2.25.100 art. 27"),
        _CONVENTION_PIECE,
        _ART26_PIECE,
        *_EXPLOITATION_PIECES,
    ],
    'autorisation_anre': [
        _PIECE('demande_autorisation_anre',
               "Demande d'autorisation (ministère)", 'depot',
               "loi 82-21 art. 2-6 ; décret 2.25.100 art. 5, 18"),
        *_ART12_PIECES,
        _CONVENTION_PIECE,
        _ART26_PIECE,
        *_EXPLOITATION_PIECES,
    ],
    'non_concerne': [],
    # AGR603 — hors réseau : les pièces sont fixées par voie réglementaire
    # (décret 2.25.100, non lu) ; jamais de pièce du distributeur (aucun point
    # de livraison), jamais une pièce inventée → liste vide + motif exposé.
    'declaration_hors_reseau': [],
    # CIQ616 — régime à qualifier : aucune pièce tant que le régime n'est pas
    # connu (CIQ613/CIQ618), motif exposé.
    'a_qualifier': [],
}

# AGR603 / CIQ616 — régimes dont la liste de pièces est volontairement vide,
# avec le motif exposé par ``document_pack`` (jamais une pièce inventée).
_MOTIF_SANS_PIECES = {
    'declaration_hors_reseau': (
        "Pièces fixées par voie réglementaire (décret 2.25.100, non lu)"),
    'a_qualifier': "Régime à qualifier (puissance ou niveau inconnu)",
}

# Régimes connus (alignés sur Installation.Regime8221).
KNOWN_REGIMES = tuple(_REGIME_PIECES.keys())


def required_documents(regime_8221):
    """FG267 — liste des pièces du pack documentaire pour un régime donné.

    Renvoie une liste de dicts ``{code, label, etape, obligatoire, required,
    source}`` : pièces COMMUNES suivies des pièces SPÉCIFIQUES au régime, sans
    doublon de code (le dernier libellé l'emporte en cas de collision). Un
    régime inconnu ou ``non_concerne`` renvoie une liste possiblement vide
    (jamais d'exception).
    """
    if regime_8221 is None:
        # Aucun régime sélectionné : rien à déposer.
        return []
    regime = regime_8221.strip()
    if regime == 'non_concerne':
        # Aucun régime qualifié : pas de dossier réglementaire à déposer.
        return []
    if regime in _MOTIF_SANS_PIECES:
        # AGR603 / CIQ616 — hors réseau ou à qualifier : aucune pièce commune
        # (pas de contrat distributeur), aucune pièce inventée ; le motif est
        # exposé par ``document_pack``.
        return []
    specifics = _REGIME_PIECES.get(regime)
    if specifics is None:
        # Régime inconnu : on retourne au moins les pièces communes (utile en
        # repli) plutôt que de lever.
        specifics = []
    pieces = []
    seen = set()
    for piece in list(_COMMON_PIECES) + list(specifics):
        code = piece['code']
        if code in seen:
            # Écrase la version précédente (le spécifique précise le commun).
            pieces = [p for p in pieces if p['code'] != code]
        seen.add(code)
        pieces.append(dict(piece))
    return pieces


def regime_label(regime_8221):
    """Libellé FR lisible d'un code régime (repli sur le code brut)."""
    labels = {
        'declaration_bt': "Déclaration basse tension",
        'accord_raccordement': "Accord de raccordement",
        'autorisation_anre': "Autorisation (ministère)",
        'non_concerne': "Non concerné (hors loi 82-21)",
        'declaration_hors_reseau':
            "Déclaration hors réseau (loi 82-21, art. 3)",
        'a_qualifier': "À qualifier",
    }
    return labels.get((regime_8221 or '').strip(), regime_8221 or '—')


def document_pack(regime_8221):
    """FG267 — pack documentaire complet (régime + libellé + pièces).

    Sortie JSON-sérialisable pratique pour un endpoint ou un générateur ::

        {regime, regime_label, pieces: [...], required_count, total_count}
    """
    pieces = required_documents(regime_8221)
    required_count = sum(1 for p in pieces if p.get('required'))
    regime = (regime_8221 or '').strip()
    pack = {
        'regime': regime,
        'regime_label': regime_label(regime_8221),
        'pieces': pieces,
        'required_count': required_count,
        'total_count': len(pieces),
    }
    motif = _MOTIF_SANS_PIECES.get(regime)
    if motif:
        # AGR603 — clé ajoutée SEULEMENT quand la liste est vide par motif :
        # les 4 régimes historiques gardent une sortie octet-identique.
        pack['motif_pieces'] = motif
    return pack


def regime_8221_pour_devis(mode, raccordement):
    """AGR603 — régime 82-21 suggéré pour un devis (fonction pure).

    Un devis hors réseau (cas type : AGRICOLE / pompage) relève d'une
    déclaration (loi 82-21, art. 3, BO 7400), QUELLE QUE SOIT la puissance :
    jamais ``accord_raccordement`` ni ``non_concerne``. L'art. 3 ne dépend pas
    du marché : ``mode`` est accepté pour l'appelant mais ne change pas la
    règle. Pour un devis raccordé, aucune suggestion ici (``None``) : le régime
    par puissance relève du noyau (CIQ612), jamais d'une seconde table locale.
    """
    del mode  # la règle art. 3 vaut pour tout marché
    racc = (raccordement or '').strip().lower().replace('-', '_').replace(' ', '_')
    if racc in ('hors_reseau', 'off_grid', 'isole'):
        return 'declaration_hors_reseau'
    return None
