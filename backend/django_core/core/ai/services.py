"""Services IA de la fondation — orchestrent un fournisseur + un gabarit.

Tout est NO-OP-safe : sans fournisseur configuré, ces services renvoient un
:class:`~core.ai.providers.AIResult` ``configured=False`` (l'appelant retombe
sur la saisie manuelle). Aucun import d'app métier : les fonctions de mise en
correspondance reçoivent le catalogue/les données du DOMAINE en argument, depuis
la couche ``services.py`` de l'app appelante (stock/crm/installations).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from core.ai.providers import AIResult
from core.ai.registry import get_provider
from core.ai.schemas import get_schema


# --- FG355 — OCR document (CIN / contrat) -----------------------------------

def extract_document(*, content: bytes, mime_type: str, schema: str,
                     hint: str | None = None) -> AIResult:
    """OCR un document selon un gabarit nommé (``'cin'``, ``'contrat'``…).

    Valide le gabarit, délègue au fournisseur OCR sélectionné. NO-OP-safe :
    sans clé, renvoie un résultat ``configured=False`` sans appel réseau.
    """
    # Valide le gabarit tôt (lève KeyError si inconnu) — vrai aussi en NO-OP.
    get_schema(schema)
    return get_provider('ocr').extract(
        content=content, mime_type=mime_type, schema=schema, hint=hint)


# --- FG356 — Appariement lignes OCR ↔ catalogue -----------------------------

def _normalize(text: str) -> str:
    """Minuscule, sans accents, espaces compactés — pour comparer des libellés."""
    text = unicodedata.normalize('NFKD', text or '')
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


@dataclass
class MatchedLine:
    """Une ligne OCR appariée (ou non) à un item du catalogue."""

    designation: str
    quantite: float
    reference: str = ''
    unite: str = ''
    catalogue_id: Any | None = None
    catalogue_label: str | None = None
    score: float = 0.0  # 0.0–1.0 ; >= seuil = apparié

    @property
    def matched(self) -> bool:
        return self.catalogue_id is not None


def match_ocr_lines(ocr_lines: list[dict], catalogue: list[dict],
                    *, threshold: float = 0.6) -> list[MatchedLine]:
    """Apparie des lignes OCR de BL à un catalogue produit.

    ``ocr_lines`` : liste de dicts ``{designation, reference?, quantite?,
    unite?}`` (typiquement ``AIResult.data['lignes']``).
    ``catalogue`` : liste de dicts ``{id, designation, reference?}`` fournie par
    l'app STOCK (sa couche services), jamais importée ici — core reste pur.

    Stratégie : match exact par référence d'abord, sinon similarité de libellé
    (``difflib.SequenceMatcher`` sur libellés normalisés). Retourne une
    :class:`MatchedLine` par ligne OCR (appariée ou non), prête à pré-remplir
    une réception côté stock.
    """
    # Index références → item (normalisées).
    by_ref = {}
    for item in catalogue:
        ref = _normalize(str(item.get('reference') or ''))
        if ref:
            by_ref.setdefault(ref, item)

    norm_catalogue = [
        (item, _normalize(str(item.get('designation') or '')))
        for item in catalogue
    ]

    results: list[MatchedLine] = []
    for line in ocr_lines or []:
        designation = str(line.get('designation') or '')
        ref = str(line.get('reference') or '')
        try:
            qte = float(line.get('quantite') or 0)
        except (TypeError, ValueError):
            qte = 0.0
        ml = MatchedLine(
            designation=designation,
            reference=ref,
            quantite=qte,
            unite=str(line.get('unite') or ''),
        )

        # 1) Match exact par référence.
        ref_norm = _normalize(ref)
        if ref_norm and ref_norm in by_ref:
            item = by_ref[ref_norm]
            ml.catalogue_id = item.get('id')
            ml.catalogue_label = item.get('designation')
            ml.score = 1.0
            results.append(ml)
            continue

        # 2) Similarité de libellé.
        target = _normalize(designation)
        best_item, best_score = None, 0.0
        if target:
            for item, norm in norm_catalogue:
                if not norm:
                    continue
                score = SequenceMatcher(None, target, norm).ratio()
                if score > best_score:
                    best_item, best_score = item, score
        if best_item is not None and best_score >= threshold:
            ml.catalogue_id = best_item.get('id')
            ml.catalogue_label = best_item.get('designation')
            ml.score = round(best_score, 3)
        else:
            ml.score = round(best_score, 3)
        results.append(ml)

    return results


# --- FG357 — Transcription audio (notes terrain) ----------------------------

def transcribe_audio(*, content: bytes, mime_type: str,
                     language: str = 'fr') -> AIResult:
    """Transcrit un mémo audio en texte (STT). NO-OP-safe sans clé."""
    return get_provider('stt').transcribe(
        content=content, mime_type=mime_type, language=language)


# --- FG358 — Contrôle qualité vision sur photo d'installation ----------------

# Liste de contrôle par défaut (FR) — réutilisable côté installations.
DEFAULT_PHOTO_QA_CHECKLIST = [
    'Panneaux alignés et propres',
    'Étiquettes / plaques signalétiques lisibles',
    'Câblage rangé et fixé',
    'Mise à la terre visible',
    'Onduleur correctement monté',
]


def inspect_photo(*, content: bytes, mime_type: str,
                  checklist: list[str] | None = None) -> AIResult:
    """Contrôle qualité vision d'une photo de chantier. NO-OP-safe.

    Sans fournisseur vision, renvoie ``configured=False`` (pas de score) ;
    l'app installations affiche alors « contrôle non disponible »."""
    return get_provider('vision_qa').inspect(
        content=content, mime_type=mime_type,
        checklist=checklist or DEFAULT_PHOTO_QA_CHECKLIST)


# --- FG359 — Prochaine meilleure action (heuristique + IA optionnelle) -------

@dataclass
class NextBestAction:
    """Action recommandée pour un enregistrement (lead/chantier/facture)."""

    action: str           # clé machine : 'relancer', 'planifier', 'facturer'…
    label: str            # libellé FR pour l'UI
    priority: int = 0     # plus haut = plus urgent
    reason: str = ''      # justification courte (FR)
    source: str = 'heuristique'  # 'heuristique' | nom du fournisseur IA
    meta: dict = field(default_factory=dict)


# Catalogue des actions connues (libellés FR).
_ACTION_LABELS = {
    'relancer': 'Relancer le client',
    'planifier': 'Planifier une intervention',
    'facturer': 'Émettre la facture',
    'envoyer_devis': 'Envoyer le devis',
    'qualifier': 'Qualifier le lead',
    'cloturer': 'Clôturer',
    'rien': 'Aucune action prioritaire',
}


def recommend_next_action(facts: dict) -> NextBestAction:
    """Recommande la prochaine action depuis des FAITS normalisés.

    Heuristique pure (toujours disponible, gratuite). ``facts`` est un dict
    fourni par l'app appelante (crm/installations/ventes via ses selectors) —
    core n'importe aucun modèle. Clés reconnues (toutes optionnelles) :

      * ``kind`` — 'lead' | 'chantier' | 'facture' ;
      * ``stage`` — étape de pipeline (clé STAGES) ;
      * ``days_since_contact`` — jours depuis le dernier contact ;
      * ``has_open_quote`` — devis envoyé non répondu ;
      * ``quote_accepted`` — devis accepté (→ planifier) ;
      * ``work_done`` — travaux terminés (→ facturer) ;
      * ``invoice_unpaid`` — facture impayée (→ relancer paiement).

    Un vrai LLM peut ENRICHIR via :func:`recommend_next_action_ai`, mais le
    défaut est cette heuristique déterministe."""
    kind = facts.get('kind')

    # Facture impayée → relancer le paiement (priorité haute).
    if facts.get('invoice_unpaid'):
        return NextBestAction('relancer', 'Relancer le paiement', priority=90,
                              reason='Facture impayée', source='heuristique')
    # Travaux terminés mais pas facturés → facturer.
    if facts.get('work_done') and not facts.get('invoiced'):
        return NextBestAction('facturer', _ACTION_LABELS['facturer'], priority=85,
                              reason='Travaux terminés, à facturer',
                              source='heuristique')
    # Devis accepté → planifier l'intervention.
    if facts.get('quote_accepted'):
        return NextBestAction('planifier', _ACTION_LABELS['planifier'], priority=80,
                              reason='Devis accepté', source='heuristique')
    # Devis envoyé non répondu depuis > 3 j → relancer.
    days = facts.get('days_since_contact')
    if facts.get('has_open_quote') and isinstance(days, (int, float)) and days >= 3:
        return NextBestAction('relancer', _ACTION_LABELS['relancer'],
                              priority=70,
                              reason=f'Devis en attente depuis {int(days)} j',
                              source='heuristique')
    # Lead sans devis → envoyer un devis ou qualifier.
    if kind == 'lead':
        if facts.get('qualified'):
            return NextBestAction('envoyer_devis', _ACTION_LABELS['envoyer_devis'],
                                  priority=60, reason='Lead qualifié sans devis',
                                  source='heuristique')
        return NextBestAction('qualifier', _ACTION_LABELS['qualifier'],
                              priority=50, reason='Lead à qualifier',
                              source='heuristique')
    # Contact ancien → relancer.
    if isinstance(days, (int, float)) and days >= 14:
        return NextBestAction('relancer', _ACTION_LABELS['relancer'], priority=40,
                              reason=f'Sans contact depuis {int(days)} j',
                              source='heuristique')

    return NextBestAction('rien', _ACTION_LABELS['rien'], priority=0,
                          reason='Rien d\'urgent', source='heuristique')


def recommend_next_action_ai(facts: dict, *, context: str = '') -> NextBestAction:
    """Recommandation enrichie par IA si une clé LLM est présente, sinon
    heuristique. NO-OP-safe : sans LLM, renvoie exactement
    :func:`recommend_next_action`.

    Quand un LLM est configuré, on l'utilise pour formuler une RAISON plus riche
    en français, mais l'ACTION machine reste celle de l'heuristique (sûr,
    déterministe, jamais d'action inventée hors catalogue)."""
    base = recommend_next_action(facts)
    provider = get_provider('llm')
    if getattr(provider, 'key', 'noop') == 'noop':
        return base
    prompt = (
        f"Action recommandée : {base.label}.\n"
        f"Faits : {facts}.\nContexte : {context}\n"
        "Rédige en une phrase française la justification de cette action."
    )
    res = provider.complete(prompt=prompt, max_tokens=120)
    if res.ok and res.data.get('text'):
        base.reason = res.data['text'].strip()
        base.source = res.provider
    return base
