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


# --- Mise en forme d'un fil d'activité (partagé FG353/FG354) -----------------

def format_thread(messages: list[dict], *, limit: int = 40) -> str:
    """Met un fil d'activité à plat en texte lisible pour un prompt LLM.

    ``messages`` : liste de dicts génériques fournie par l'app appelante
    (crm/installations/sav via ses selectors) — core n'importe AUCUN modèle.
    Clés reconnues (toutes optionnelles) :

      * ``auteur`` — qui a écrit / agi ;
      * ``date`` — horodatage (str ou datetime, rendu tel quel) ;
      * ``texte`` ou ``message`` ou ``contenu`` — le corps de l'entrée ;
      * ``canal`` — 'email' | 'whatsapp' | 'note' | 'appel'… (facultatif).

    Ne garde que les ``limit`` entrées les plus récentes (les dernières de la
    liste) pour borner la taille du prompt. Une entrée vide est ignorée."""
    lines: list[str] = []
    for entry in (messages or [])[-limit:]:
        if not isinstance(entry, dict):
            entry = {'texte': str(entry)}
        body = (entry.get('texte') or entry.get('message')
                or entry.get('contenu') or '')
        body = str(body).strip()
        if not body:
            continue
        author = str(entry.get('auteur') or entry.get('author') or '').strip()
        when = str(entry.get('date') or '').strip()
        canal = str(entry.get('canal') or '').strip()
        prefix_parts = [p for p in (when, author, canal) if p]
        prefix = ' · '.join(prefix_parts)
        lines.append(f"[{prefix}] {body}" if prefix else body)
    return '\n'.join(lines)


# --- FG353 — Résumé automatique d'un fil (lead/chantier/ticket) --------------

@dataclass
class ThreadSummary:
    """Synthèse d'un fil d'activité (résumé + points clés)."""

    ok: bool = False
    configured: bool = False
    summary: str = ''
    source: str = 'noop'

    @property
    def available(self) -> bool:
        """True si une vraie synthèse a été produite (LLM configuré)."""
        return self.ok and bool(self.summary)


def summarize_thread(messages: list[dict], *, context: str = '',
                     max_tokens: int = 400) -> ThreadSummary:
    """Synthétise en un clic un fil d'activité (lead / chantier / ticket).

    ``messages`` : entrées génériques (voir :func:`format_thread`) — core
    n'importe aucun modèle métier ; l'app appelante passe le fil depuis sa
    couche selectors. ``context`` ajoute un cadre court (ex. « Lead solaire
    résidentiel, étape Devis envoyé »).

    NO-OP-safe : SANS clé LLM, ne fait AUCUN appel réseau et renvoie une
    ``ThreadSummary`` ``configured=False`` (l'UI affiche « synthèse non
    disponible » et l'utilisateur lit le fil à la main). Avec un LLM configuré,
    ``summary`` porte la synthèse française."""
    provider = get_provider('llm')
    if getattr(provider, 'key', 'noop') == 'noop':
        return ThreadSummary(ok=False, configured=False, summary='', source='noop')

    thread = format_thread(messages)
    if not thread:
        # Rien à résumer — pas d'appel réseau inutile.
        return ThreadSummary(ok=True, configured=True, summary='',
                             source=provider.key)
    system = (
        "Tu es un assistant CRM. Résume en français, de façon concise et "
        "factuelle, le fil d'activité ci-dessous : situation actuelle, points "
        "importants et éventuels points à traiter. N'invente rien."
    )
    prompt = thread if not context else f"Contexte : {context}\n\n{thread}"
    res = provider.complete(prompt=prompt, system=system, max_tokens=max_tokens)
    if res.ok and res.data.get('text'):
        return ThreadSummary(ok=True, configured=True,
                             summary=res.data['text'].strip(),
                             source=res.provider)
    return ThreadSummary(ok=False, configured=True, summary='',
                         source=res.provider)


# --- FG354 — Brouillon de réponse email / WhatsApp --------------------------

# Canaux supportés (libellés FR) — borne la consigne de format au LLM.
REPLY_CHANNELS = {
    'email': 'e-mail',
    'whatsapp': 'message WhatsApp',
    'sms': 'SMS',
}


@dataclass
class ReplyDraft:
    """Brouillon de réponse SUGGÉRÉ (jamais envoyé automatiquement)."""

    ok: bool = False
    configured: bool = False
    draft: str = ''
    channel: str = 'email'
    source: str = 'noop'

    @property
    def available(self) -> bool:
        return self.ok and bool(self.draft)


def draft_reply(messages: list[dict], *, channel: str = 'email',
                context: str = '', instruction: str = '',
                max_tokens: int = 400) -> ReplyDraft:
    """Propose un brouillon de réponse FR éditable à partir d'un fil.

    ``channel`` ∈ :data:`REPLY_CHANNELS` (``'email'``/``'whatsapp'``/``'sms'``)
    règle uniquement le TON/FORMAT. ``instruction`` permet d'orienter la réponse
    (ex. « propose un créneau de visite »). ``messages`` : voir
    :func:`format_thread` — aucun modèle métier importé.

    GARANTIE : cette fonction ne fait QUE générer du texte ; elle n'envoie
    JAMAIS rien. L'envoi reste une action manuelle explicite de l'utilisateur.

    NO-OP-safe : sans clé LLM, aucun appel réseau, renvoie ``configured=False``
    (l'UI masque la suggestion ; l'utilisateur rédige à la main)."""
    chan_label = REPLY_CHANNELS.get(channel, REPLY_CHANNELS['email'])
    provider = get_provider('llm')
    if getattr(provider, 'key', 'noop') == 'noop':
        return ReplyDraft(ok=False, configured=False, draft='',
                          channel=channel, source='noop')

    thread = format_thread(messages)
    system = (
        f"Tu es un commercial solaire au Maroc. Rédige en français un brouillon "
        f"de {chan_label} poli et professionnel répondant au dernier message du "
        "fil. Reste concret et bref. Ne promets aucun prix ni délai non confirmé."
    )
    parts = []
    if context:
        parts.append(f"Contexte : {context}")
    if instruction:
        parts.append(f"Consigne : {instruction}")
    parts.append(f"Fil :\n{thread}" if thread else "Fil : (vide)")
    prompt = '\n\n'.join(parts)
    res = provider.complete(prompt=prompt, system=system, max_tokens=max_tokens)
    if res.ok and res.data.get('text'):
        return ReplyDraft(ok=True, configured=True,
                          draft=res.data['text'].strip(),
                          channel=channel, source=res.provider)
    return ReplyDraft(ok=False, configured=True, draft='',
                      channel=channel, source=res.provider)


# --- XMKT34 — Génération IA de contenu de campagne (FR/AR), gated -----------
#
# Même patron NO-OP-safe que FG354 (``draft_reply``) : une SUGGESTION éditable
# de sujet + corps, JAMAIS auto-envoyée — l'utilisateur relit/édite/envoie
# lui-même. Sans clé LLM configurée, ``configured=False`` et l'appelant
# (apps.compta.views) masque le bouton « Générer avec l'IA » (no-op complet,
# aucun appel réseau). GARDE STRICTE : le prompt construit ne doit JAMAIS
# contenir de donnée interne (prix_achat, marge) — testé par
# ``build_campaign_prompt`` + une liste de mots-clés interdits.

#: Champs interdits dans le prompt de génération de campagne (fuite de donnée
#: commerciale interne — jamais envoyés à un fournisseur externe).
CAMPAIGN_PROMPT_FORBIDDEN_TERMS = ('prix_achat', 'marge', 'coût interne')


@dataclass
class CampaignContentDraft:
    """Objet + corps de campagne SUGGÉRÉS (jamais auto-envoyés)."""

    ok: bool = False
    configured: bool = False
    objet: str = ''
    corps: str = ''
    langue: str = 'fr'
    source: str = 'noop'

    @property
    def available(self) -> bool:
        return self.ok and bool(self.corps)


def build_campaign_prompt(*, segment_label: str = '', offre: str = '',
                          instruction: str = '', langue: str = 'fr',
                          longueur: str = '') -> str:
    """Construit le prompt de génération de contenu marketing.

    ``segment_label``/``offre`` décrivent le CIBLAGE et l'OFFRE en langage
    naturel (fournis par l'appelant — jamais un objet ORM ni un champ interne
    du catalogue). ``instruction`` porte une consigne libre de réécriture
    (ton/longueur/langue). Ne référence JAMAIS ``prix_achat``/``marge`` — un
    appelant qui les passerait par erreur les verrait apparaître ici, d'où le
    test dédié sur cette fonction (jamais sur un prompt déjà envoyé)."""
    langue_label = {'fr': 'français', 'ar': 'arabe'}.get(langue, 'français')
    parts = [
        "Tu es un rédacteur marketing pour un installateur solaire au Maroc.",
        f"Rédige en {langue_label} un OBJET court et un CORPS de message "
        "pour une campagne marketing (email ou WhatsApp).",
    ]
    if segment_label:
        parts.append(f"Segment ciblé : {segment_label}.")
    if offre:
        parts.append(f"Offre / contexte : {offre}.")
    if longueur:
        parts.append(f"Longueur souhaitée : {longueur}.")
    if instruction:
        parts.append(f"Consigne de réécriture : {instruction}.")
    # Formulation volontairement sans les termes de CAMPAIGN_PROMPT_FORBIDDEN_TERMS :
    # le garde-fou (test) vérifie leur absence LITTÉRALE dans tout prompt construit.
    parts.append(
        "Ne mentionne JAMAIS de données financières internes de l'entreprise — "
        "ces informations ne te sont de toute façon jamais fournies. "
        "Réponds strictement au format :\nOBJET: <objet>\nCORPS: <corps>")
    return '\n'.join(parts)


def draft_campaign_content(*, segment_label: str = '', offre: str = '',
                           instruction: str = '', langue: str = 'fr',
                           longueur: str = '',
                           max_tokens: int = 500) -> CampaignContentDraft:
    """Génère un OBJET + CORPS de campagne suggérés (XMKT34), éditables.

    NO-OP-safe : sans clé LLM configurée (Groq/Zhipu via
    ``settings.AI_PROVIDERS``), ne fait AUCUN appel réseau et renvoie
    ``configured=False`` — l'appelant masque alors le bouton « Générer avec
    l'IA » (aucune trace UI). Le contenu généré reste une SUGGESTION éditable,
    jamais envoyée automatiquement (même garantie que ``draft_reply``,
    FG354)."""
    provider = get_provider('llm')
    if getattr(provider, 'key', 'noop') == 'noop':
        return CampaignContentDraft(
            ok=False, configured=False, objet='', corps='', langue=langue,
            source='noop')

    prompt = build_campaign_prompt(
        segment_label=segment_label, offre=offre, instruction=instruction,
        langue=langue, longueur=longueur)
    system = (
        "Tu rédiges du contenu marketing pour un installateur solaire "
        "marocain. Reste concret, factuel, sans promesse de prix ni de délai "
        "non confirmé. N'invente aucune donnée chiffrée."
    )
    res = provider.complete(prompt=prompt, system=system, max_tokens=max_tokens)
    if not (res.ok and res.data.get('text')):
        return CampaignContentDraft(
            ok=False, configured=True, objet='', corps='', langue=langue,
            source=res.provider)

    text = res.data['text'].strip()
    objet, corps = '', text
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith('OBJET:'):
            objet = stripped.split(':', 1)[1].strip()
        elif stripped.upper().startswith('CORPS:'):
            corps = stripped.split(':', 1)[1].strip()
    if not objet and '\n' in text:
        # Repli : première ligne = objet, reste = corps, si le format demandé
        # n'a pas été respecté par le modèle.
        first, _, rest = text.partition('\n')
        objet, corps = first.strip(), rest.strip() or text
    return CampaignContentDraft(
        ok=True, configured=True, objet=objet, corps=corps, langue=langue,
        source=res.provider)


# --- XMKT37 — Qualification livechat visiteur (site public) -----------------
#
# Prompt de qualification solaire pour un visiteur ANONYME du site public.
# GARDE STRICTE : le prompt système n'expose JAMAIS de donnée interne
# (prix_achat/marges) — il n'a d'ailleurs accès à AUCUNE donnée interne, sa
# seule entrée est le fil de conversation du visiteur (aucun modèle métier
# importé ici, `core` reste pur fondation).

LIVECHAT_QUALIFICATION_SYSTEM_PROMPT = (
    "Tu es l'assistant d'accueil du site TAQINOR (installateur solaire au "
    "Maroc). Réponds en français, de façon brève, chaleureuse et concrète. "
    "Ton seul objectif : qualifier le besoin du visiteur puis recueillir son "
    "nom et un moyen de contact (téléphone ou email) pour qu'un commercial le "
    "recontacte. Pose UNE question à la fois, dans cet ordre si l'info manque : "
    "1) sa ville, 2) le montant approximatif de sa facture d'électricité, "
    "3) le type de projet (résidentiel / professionnel / agricole - pompage), "
    "4) son nom, 5) son téléphone ou email. "
    "N'invente JAMAIS de prix, de délai, de remise ni de disponibilité produit. "
    "Ne mentionne JAMAIS aucune donnée commerciale interne ou confidentielle "
    "de l'entreprise (coûts, chiffres internes, partenaires ou origine des "
    "produits) — ces informations ne te sont de toute façon jamais fournies. "
    "Si le visiteur pose une question hors sujet solaire, réponds brièvement "
    "puis reviens à la qualification."
)

#: Champs interdits — sert de garde-fou testable : le prompt ne doit JAMAIS
#: contenir ces mots-clés (fuite de donnée interne).
LIVECHAT_FORBIDDEN_TERMS = ('prix_achat', 'marge', 'coût interne', 'fournisseur')


@dataclass
class LivechatQualificationExtract:
    """Champs de qualification extraits d'une conversation livechat."""

    ville: str = ''
    facture_estimee: str = ''
    type_projet: str = ''
    nom: str = ''
    telephone: str = ''
    email: str = ''

    @property
    def has_contact(self) -> bool:
        """True dès que nom + (téléphone OU email) sont capturés — le seuil
        déclenchant la création du Lead (XMKT37)."""
        return bool(self.nom) and bool(self.telephone or self.email)


def qualify_livechat_reply(messages: list[dict], *, instruction: str = '',
                           max_tokens: int = 300) -> ReplyDraft:
    """Prochaine réponse de l'assistant de qualification livechat.

    ``messages`` : fil du visiteur (voir :func:`format_thread` — clés
    ``auteur``/``texte``/``date``). NO-OP-safe : sans LLM configuré, renvoie
    ``configured=False`` — l'appelant (apps.crm.public_chat_views) bascule
    alors en mode capture seule (formulaire de rappel), jamais d'exception.
    """
    provider = get_provider('llm')
    if getattr(provider, 'key', 'noop') == 'noop':
        return ReplyDraft(ok=False, configured=False, draft='',
                          channel='livechat', source='noop')

    thread = format_thread(messages)
    prompt = thread if not instruction else f"Consigne : {instruction}\n\n{thread}"
    res = provider.complete(
        prompt=prompt, system=LIVECHAT_QUALIFICATION_SYSTEM_PROMPT,
        max_tokens=max_tokens)
    if res.ok and res.data.get('text'):
        return ReplyDraft(ok=True, configured=True,
                          draft=res.data['text'].strip(),
                          channel='livechat', source=res.provider)
    return ReplyDraft(ok=False, configured=True, draft='',
                      channel='livechat', source=res.provider)


def extract_livechat_qualification(
        messages: list[dict]) -> LivechatQualificationExtract:
    """Extrait les champs de qualification depuis le texte du VISITEUR.

    Heuristique légère (regex/mots-clés), toujours disponible — aucune
    dépendance LLM : c'est ce qui décide, côté appelant, quand créer le Lead
    (nom + téléphone/email capturés), y compris en mode dégradé sans clé LLM.
    """
    extract = LivechatQualificationExtract()
    visitor_text = ' '.join(
        str(m.get('texte') or m.get('message') or m.get('contenu') or '')
        for m in (messages or [])
        if isinstance(m, dict)
        and str(m.get('auteur') or '').lower() in ('visiteur', 'visitor', '')
    )
    if not visitor_text:
        return extract

    phone_match = re.search(
        r'(?:\+?212|0)[\s.-]?[5-7](?:[\s.-]?\d{2}){4}', visitor_text)
    if phone_match:
        extract.telephone = phone_match.group(0).strip()

    email_match = re.search(
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', visitor_text)
    if email_match:
        extract.email = email_match.group(0).strip()

    # Nom : heuristique légère sur les tournures de présentation courantes en
    # français ("je m'appelle X", "je suis X", "mon nom est X", "c'est X").
    # Capture 1 à 3 mots (prénom [+ nom de famille]) jusqu'à la ponctuation.
    name_match = re.search(
        r"(?:je\s+m['’]appelle|je\s+suis|mon\s+nom\s+est|c['’]est)\s+"
        r"([A-ZÀ-Ý][\wÀ-ÿ'’-]*(?:\s+[A-ZÀ-Ý][\wÀ-ÿ'’-]*){0,2})",
        visitor_text, re.IGNORECASE)
    if name_match:
        extract.nom = name_match.group(1).strip(' ,.;:').title()

    return extract
