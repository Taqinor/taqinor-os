"""Gabarits d'extraction OCR (FG355/FG356) — purs, sans dépendance.

Chaque gabarit décrit les CHAMPS attendus d'un type de document. Un vrai
fournisseur OCR (Zhipu vision) consomme ce gabarit pour structurer sa sortie ;
le NO-OP les ignore. Définir les gabarits ici (fondation) garde la connaissance
métier « quels champs sur une CIN/un contrat/un BL » côté code, versionnée et
testable, sans coupler à un fournisseur.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OCRField:
    """Un champ attendu dans un document OCR-isé."""

    key: str
    label: str  # libellé FR pour l'UI
    required: bool = False


@dataclass(frozen=True)
class OCRSchema:
    """Gabarit d'un type de document : nom + champs attendus."""

    name: str
    label: str
    fields: tuple[OCRField, ...]

    def field_keys(self) -> list[str]:
        return [f.key for f in self.fields]

    def required_keys(self) -> list[str]:
        return [f.key for f in self.fields if f.required]


# FG355 — Carte d'identité nationale (CIN) marocaine.
CIN_SCHEMA = OCRSchema(
    name='cin',
    label="Carte d'identité nationale",
    fields=(
        OCRField('numero_cin', 'Numéro CIN', required=True),
        OCRField('nom', 'Nom', required=True),
        OCRField('prenom', 'Prénom', required=True),
        OCRField('date_naissance', 'Date de naissance'),
        OCRField('lieu_naissance', 'Lieu de naissance'),
        OCRField('date_validite', 'Date de validité'),
        OCRField('adresse', 'Adresse'),
        OCRField('sexe', 'Sexe'),
    ),
)

# FG355 — Contrat / pièce signée.
CONTRAT_SCHEMA = OCRSchema(
    name='contrat',
    label='Contrat / pièce',
    fields=(
        OCRField('reference', 'Référence', required=True),
        OCRField('date_document', 'Date du document'),
        OCRField('parties', 'Parties'),
        OCRField('montant_total', 'Montant total'),
        OCRField('objet', 'Objet'),
        OCRField('signataires', 'Signataires'),
    ),
)

# FG356 — Bon de livraison (lignes produits → réception stock).
BON_LIVRAISON_SCHEMA = OCRSchema(
    name='bon_livraison',
    label='Bon de livraison',
    fields=(
        OCRField('numero_bl', 'Numéro de BL'),
        OCRField('fournisseur', 'Fournisseur'),
        OCRField('date_livraison', 'Date de livraison'),
        # `lignes` : liste de {designation, reference, quantite, unite}.
        OCRField('lignes', 'Lignes', required=True),
    ),
)

# XRH23 — CV candidat (RH/ATS) : identité + parcours pour pré-remplissage.
CV_SCHEMA = OCRSchema(
    name='cv',
    label='CV candidat',
    fields=(
        OCRField('nom', 'Nom'),
        OCRField('prenom', 'Prénom'),
        OCRField('email', 'E-mail'),
        OCRField('telephone', 'Téléphone'),
        OCRField('diplome', 'Diplôme'),
        # `competences` : liste de str (mots-clés courts) — suggère les tags
        # vivier (XRH21 ``tags_vivier``), jamais écrit tel quel sans revue.
        OCRField('competences', 'Compétences'),
    ),
)

# XSAL8 — Carte de visite (salon/chantier) → pré-remplissage lead express.
CARTE_VISITE_SCHEMA = OCRSchema(
    name='carte_visite',
    label='Carte de visite',
    fields=(
        OCRField('nom', 'Nom'),
        OCRField('prenom', 'Prénom'),
        OCRField('societe', 'Société'),
        OCRField('telephone', 'Téléphone'),
        OCRField('email', 'E-mail'),
    ),
)

_SCHEMAS = {
    s.name: s for s in
    (CIN_SCHEMA, CONTRAT_SCHEMA, BON_LIVRAISON_SCHEMA, CV_SCHEMA,
     CARTE_VISITE_SCHEMA)
}


def get_schema(name: str) -> OCRSchema:
    """Retourne le gabarit nommé. Lève ``KeyError`` si inconnu."""
    return _SCHEMAS[name]


def available_schemas() -> list[str]:
    return sorted(_SCHEMAS.keys())
