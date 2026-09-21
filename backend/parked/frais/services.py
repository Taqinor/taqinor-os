"""Façade de services du module Notes de frais (``apps.frais``) — ODX15.

**La frontière ODX15, en une phrase :** ``apps.frais`` possède la SAISIE et le
RÉFÉRENTIEL (notes, rapports, plafonds, barèmes, indemnités) ; ``apps.compta``
garde le POSTING COMPTABLE — les écritures 6143 (charge) / 4432 (personnel
créditeur) / trésorerie et le verrou de période FG115 restent écrits par
``apps.compta.services``, jamais réimplémentés ici.

Ce module est donc le point d'entrée ``services.py`` que CLAUDE.md exige entre
apps : un appelant (``apps.paie``, une vue, un futur écran) passe par
``apps.frais.services`` sans jamais importer ``apps.compta.models``. Les
fonctions ci-dessous SONT celles de ``apps.compta.services`` (même objet, même
comportement, même transaction) — ré-exportées, pas dupliquées : aucune logique
comptable n'est copiée, donc aucune ne peut diverger.
"""

from apps.compta.services import (  # noqa: F401
    # ── Notes de frais (FG135) ──
    creer_note_frais,
    soumettre_note_frais,
    valider_note_frais,
    rejeter_note_frais,
    rembourser_note_frais,
    # ── Rapports de frais (ZACC6) ──
    creer_rapport_note_frais,
    soumettre_rapport_note_frais,
    valider_rapport_note_frais,
    rembourser_rapport_note_frais,
    # ── Politique de plafonds (XACC27) ──
    plafond_note_frais_pour,
    note_frais_hors_politique,
    note_frais_doublon_possible,
    # ── Justificatifs / OCR (XACC) ──
    extraire_justificatif_note_frais,
    mapper_justificatif_vers_note_frais,
    # ── Refacturation client (XACC28) ──
    refacturer_frais_client,
    # ── Barèmes & indemnités chantier (FG136) ──
    bareme_indemnite_defaut,
    calculer_indemnite,
    creer_indemnite_chantier,
    recalculer_indemnite_chantier,
    soumettre_indemnite_chantier,
    valider_indemnite_chantier,
    rejeter_indemnite_chantier,
    rembourser_indemnite_chantier,
    marquer_indemnite_remboursee_par_paie,
)

__all__ = [
    'creer_note_frais',
    'soumettre_note_frais',
    'valider_note_frais',
    'rejeter_note_frais',
    'rembourser_note_frais',
    'creer_rapport_note_frais',
    'soumettre_rapport_note_frais',
    'valider_rapport_note_frais',
    'rembourser_rapport_note_frais',
    'plafond_note_frais_pour',
    'note_frais_hors_politique',
    'note_frais_doublon_possible',
    'extraire_justificatif_note_frais',
    'mapper_justificatif_vers_note_frais',
    'refacturer_frais_client',
    'bareme_indemnite_defaut',
    'calculer_indemnite',
    'creer_indemnite_chantier',
    'recalculer_indemnite_chantier',
    'soumettre_indemnite_chantier',
    'valider_indemnite_chantier',
    'rejeter_indemnite_chantier',
    'rembourser_indemnite_chantier',
    'marquer_indemnite_remboursee_par_paie',
]
