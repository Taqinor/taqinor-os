"""FG267 — Packs documentaires réglementaires par régime (loi 82-21).

Donne, pour un régime de raccordement (``regime_8221``), la LISTE DES PIÈCES
réglementaires à constituer pour le dossier ONEE/distributeur/ANRE. Les codes de
régime sont EXACTEMENT ceux de ``apps.installations.regime`` /
``Installation.Regime8221`` — on ne les redéfinit pas, on les MAPPE :

  * ``declaration_bt``        — déclaration basse tension (< seuil)
  * ``accord_raccordement``   — accord de raccordement (BT/MT au-dessus du seuil)
  * ``autorisation_anre``     — autorisation ANRE (grandes puissances)
  * ``non_concerne``          — hors champ loi 82-21 (autoconsommation isolée…)

Cœur PUR (fonction sans Django) : c'est de la donnée de RÉFÉRENCE réutilisée par
le suivi de dossier (FG268+) et par tout générateur de déclaration (FG272). On
ne touche pas l'app installations (couche découplée) : le régime arrive ici sous
forme de simple chaîne. Aucun prix, aucun changement de statut de devis.
"""
from __future__ import annotations

# Pièce documentaire : code stable + libellé FR + indicateur « obligatoire ».
# ``required=True`` = pièce sans laquelle le dossier ne peut pas être déposé.
_PIECE = lambda code, label, required=True: {  # noqa: E731
    'code': code, 'label': label, 'required': required}

# Pièces COMMUNES à tout dossier de raccordement.
_COMMON_PIECES = [
    _PIECE('cni_client', "Pièce d'identité / RC du client"),
    _PIECE('contrat_onee', "Contrat / référence ONEE du point de livraison"),
    _PIECE('plan_situation', "Plan de situation du site"),
    _PIECE('schema_unifilaire', "Schéma unifilaire de l'installation"),
    _PIECE('fiches_techniques',
           "Fiches techniques modules & onduleur(s)"),
]

# Pièces SPÉCIFIQUES par régime, ajoutées aux pièces communes.
_REGIME_PIECES = {
    'declaration_bt': [
        _PIECE('formulaire_declaration_bt',
               "Formulaire de déclaration basse tension"),
        _PIECE('attestation_conformite',
               "Attestation de conformité électrique"),
    ],
    'accord_raccordement': [
        _PIECE('demande_accord_raccordement',
               "Demande d'accord de raccordement"),
        _PIECE('etude_raccordement',
               "Étude de raccordement (dimensionnement réseau)"),
        _PIECE('attestation_conformite',
               "Attestation de conformité électrique"),
        _PIECE('convention_raccordement',
               "Convention de raccordement signée"),
    ],
    'autorisation_anre': [
        _PIECE('demande_autorisation_anre',
               "Demande d'autorisation ANRE"),
        _PIECE('etude_impact_reseau',
               "Étude d'impact réseau / d'injection"),
        _PIECE('convention_raccordement',
               "Convention de raccordement signée"),
        _PIECE('attestation_conformite',
               "Attestation de conformité électrique"),
        _PIECE('garanties_financieres',
               "Garanties financières du projet", False),
    ],
    'non_concerne': [],
}

# Régimes connus (alignés sur Installation.Regime8221).
KNOWN_REGIMES = tuple(_REGIME_PIECES.keys())


def required_documents(regime_8221):
    """FG267 — liste des pièces du pack documentaire pour un régime donné.

    Renvoie une liste de dicts ``{code, label, required}`` : pièces COMMUNES
    suivies des pièces SPÉCIFIQUES au régime, sans doublon de code (le dernier
    libellé l'emporte en cas de collision). Un régime inconnu ou ``non_concerne``
    renvoie une liste possiblement vide (jamais d'exception).
    """
    if regime_8221 is None:
        # Aucun régime sélectionné : rien à déposer.
        return []
    regime = regime_8221.strip()
    if regime == 'non_concerne':
        # Hors champ 82-21 : pas de dossier réglementaire à déposer.
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
        'autorisation_anre': "Autorisation ANRE",
        'non_concerne': "Non concerné (hors loi 82-21)",
    }
    return labels.get((regime_8221 or '').strip(), regime_8221 or '—')


def document_pack(regime_8221):
    """FG267 — pack documentaire complet (régime + libellé + pièces).

    Sortie JSON-sérialisable pratique pour un endpoint ou un générateur ::

        {regime, regime_label, pieces: [...], required_count, total_count}
    """
    pieces = required_documents(regime_8221)
    required_count = sum(1 for p in pieces if p.get('required'))
    return {
        'regime': (regime_8221 or '').strip(),
        'regime_label': regime_label(regime_8221),
        'pieces': pieces,
        'required_count': required_count,
        'total_count': len(pieces),
    }
