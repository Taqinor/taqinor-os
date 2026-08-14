"""Services du module « ai_governance » — copilotes IA NO-OP-safe (Groupe NTAI).

Tout ce qui vit ici respecte trois invariants :

  1. **Key-gated / NO-OP-safe** — sans fournisseur LLM configuré (``GROQ_API_KEY``
     ou équivalent), AUCUN appel réseau n'est fait et l'appelant reçoit une
     erreur métier explicite (503 douce côté vue) ; jamais une 500.
  2. **Jamais d'écriture implicite** — ces services PROPOSENT un brouillon.
     L'application de la proposition reste une action utilisateur explicite,
     par les endpoints métier existants.
  3. **Confidentialité des données internes** — les faits envoyés au
     fournisseur externe sont construits par une ALLOWLIST explicite de champs,
     jamais par sérialisation d'un objet entier : un champ interne ajouté plus
     tard au modèle ne peut pas fuiter tout seul.

Note NTAI5 : les prompts par défaut vivent en constantes de module. Quand la
bibliothèque de prompts éditables (``PromptTemplate`` + ``render_prompt``)
sera posée, ces constantes deviendront le « défaut code » sur lequel elle
retombe — le corps des fonctions ci-dessous ne change pas.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from core.ai.registry import get_provider, is_capability_configured


class AiCopiloteUnavailable(Exception):
    """Levée quand un copilote ne peut pas produire de brouillon.

    ``configured=False`` → aucune clé LLM/STT (503 douce côté vue, aucun appel
    réseau) ; ``configured=True`` → entrée invalide ou refus fournisseur (400).
    """

    def __init__(self, message, *, configured=True):
        super().__init__(message)
        self.configured = configured


# ─────────────────────────────────────────────────────────────────────────────
# NTAI13 — Génération de description produit (catalogue)
# ─────────────────────────────────────────────────────────────────────────────
#
# GARDE DE CONFIDENTIALITÉ (règle du dépôt) : ``Produit.prix_achat`` est une
# donnée INTERNE (elle alimente l'indicateur de marge du générateur de devis)
# et ne doit JAMAIS quitter le système, a fortiori vers un fournisseur LLM
# externe. Même motif que ``core.ai.services.CAMPAIGN_PROMPT_FORBIDDEN_TERMS``
# (XMKT34), mais renforcé : au lieu de filtrer une chaîne déjà construite, on
# construit le prompt à partir d'une ALLOWLIST de champs (aucun prix, ni
# d'achat ni de vente) et on VÉRIFIE ensuite l'absence des termes interdits.

#: Champs de ``Produit`` autorisés dans le prompt de description. Toute donnée
#: hors de cette liste (prix d'achat, prix de vente, marge, stock, fournisseur)
#: est structurellement absente du prompt.
PRODUIT_DESCRIPTION_ALLOWED_FIELDS = ('nom', 'marque', 'categorie', 'garantie')

#: Termes dont la présence dans le prompt construit signale une fuite de donnée
#: commerciale interne (garde de dernier recours, testée).
PRODUIT_DESCRIPTION_FORBIDDEN_TERMS = (
    'prix_achat', 'prix d\'achat', 'prix achat', 'marge',
    'coût interne', 'cout interne', 'prix_vente',
)

#: Prompt système par défaut (futur « défaut code » de NTAI5, clé
#: ``ai.description_produit``).
PRODUIT_DESCRIPTION_SYSTEM = (
    "Tu es un rédacteur catalogue pour un installateur solaire au Maroc. "
    "À partir des seules caractéristiques fournies, rédige en français : "
    "(1) une description commerciale de 3 à 5 phrases, factuelle et concrète ; "
    "(2) sur une dernière ligne préfixée « COURT : », une variante d'une seule "
    "phrase. N'invente aucune caractéristique technique, aucun prix, aucun "
    "délai et aucune certification qui ne figure pas ci-dessous."
)


def produit_description_facts(produit) -> dict:
    """Faits envoyables au LLM pour ``produit`` — ALLOWLIST stricte.

    Ne lit QUE :data:`PRODUIT_DESCRIPTION_ALLOWED_FIELDS`. ``prix_achat`` (et
    tout autre champ interne) n'est jamais lu, donc jamais transmis.
    """
    categorie = getattr(produit, 'categorie', None)
    raw = {
        'nom': getattr(produit, 'nom', '') or '',
        'marque': getattr(produit, 'marque', '') or '',
        'categorie': getattr(categorie, 'nom', '') or '',
        'garantie': getattr(produit, 'garantie', '') or '',
    }
    return {
        cle: str(raw.get(cle) or '').strip()
        for cle in PRODUIT_DESCRIPTION_ALLOWED_FIELDS
    }


def build_description_produit_prompt(facts: dict) -> str:
    """Construit le prompt utilisateur à partir des faits allowlistés.

    Lève ``ValueError`` si un terme interdit (prix d'achat, marge…) apparaît
    dans le texte produit — garde de dernier recours contre une régression qui
    élargirait l'allowlist sans y penser.
    """
    labels = {
        'nom': 'Désignation',
        'marque': 'Marque',
        'categorie': 'Catégorie',
        'garantie': 'Garantie',
    }
    lignes = [
        f'{labels[cle]} : {facts[cle]}'
        for cle in PRODUIT_DESCRIPTION_ALLOWED_FIELDS
        if facts.get(cle)
    ]
    prompt = 'Caractéristiques du produit :\n' + '\n'.join(lignes)
    lowered = prompt.lower()
    fuite = [t for t in PRODUIT_DESCRIPTION_FORBIDDEN_TERMS if t in lowered]
    if fuite:
        raise ValueError(
            f'Donnée interne interdite dans le prompt produit : {sorted(fuite)}')
    return prompt


def _split_description(texte: str) -> tuple[str, str]:
    """Sépare la description longue de la variante courte (« COURT : … »)."""
    longue, courte = [], ''
    for ligne in (texte or '').splitlines():
        nu = ligne.strip()
        if nu.upper().startswith('COURT'):
            _, _, reste = nu.partition(':')
            courte = reste.strip()
            continue
        if nu:
            longue.append(nu)
    return '\n'.join(longue).strip(), courte


def generer_description_produit(*, company, produit_id, max_tokens=400) -> dict:
    """NTAI13 — Propose une description commerciale FR + une variante courte.

    N'ÉCRIT RIEN : renvoie un brouillon que l'utilisateur valide (puis applique
    via l'endpoint produit existant). ``prix_achat`` n'est jamais transmis au
    fournisseur (voir :func:`produit_description_facts`).

    Lève :class:`AiCopiloteUnavailable` si le produit est introuvable dans la
    société (``configured=True`` → 400) ou si aucune clé LLM n'est configurée
    (``configured=False`` → 503, aucun appel réseau).
    """
    from apps.stock.selectors import get_produit_scoped

    try:
        produit = get_produit_scoped(company, produit_id)
    except (TypeError, ValueError):
        produit = None
    if produit is None:
        raise AiCopiloteUnavailable('Produit introuvable.')

    facts = produit_description_facts(produit)
    if not facts.get('nom'):
        raise AiCopiloteUnavailable(
            'Le produit doit avoir une désignation pour être décrit.')

    if not is_capability_configured('llm'):
        raise AiCopiloteUnavailable(
            "Aucun fournisseur LLM n'est configuré (clé absente) — "
            'rédaction manuelle requise.', configured=False)

    prompt = build_description_produit_prompt(facts)
    res = get_provider('llm').complete(
        prompt=prompt, system=PRODUIT_DESCRIPTION_SYSTEM, max_tokens=max_tokens)
    if not res.ok or not (res.data or {}).get('text'):
        raise AiCopiloteUnavailable(
            "Le fournisseur n'a pas produit de description exploitable.")

    description, description_courte = _split_description(res.data['text'])
    return {
        'produit_id': produit.id,
        'description': description,
        'description_courte': description_courte,
        # Contrat explicite pour l'UI : rien n'a été enregistré.
        'applique': False,
        'source': res.provider,
    }


# ─────────────────────────────────────────────────────────────────────────────
# NTAI11 — Rédaction assistée de réponse / relance (câblage draft_reply)
# ─────────────────────────────────────────────────────────────────────────────
#
# Câble le ``draft_reply`` EXISTANT de la fondation (``core.ai.services``) sur
# n'importe quelle fiche du chatter générique : la relance CRM et la réponse
# SAV réutilisent CE endpoint au lieu d'en recopier un chacune.
#
# GARANTIE D'ENVOI : ce service ne fait QUE générer du texte. Aucun mail, SMS
# ou message WhatsApp n'est émis ici — l'envoi reste un geste explicite de
# l'utilisateur via les endpoints d'envoi existants (testé : boîte d'envoi
# vide après un appel).

#: Canaux acceptés — miroir de ``core.ai.services.REPLY_CHANNELS``.
REDACTION_CANAUX = ('email', 'whatsapp', 'sms')

#: Longueur max de la consigne libre (``intention``) reprise dans le prompt :
#: borne le coût et la surface d'injection d'un champ saisi par l'utilisateur.
REDACTION_INTENTION_MAX = 300

#: Nombre d'entrées de fil reprises (les plus récentes).
REDACTION_FIL_LIMITE = 40

#: Consigne de ton/longueur par canal (futur « défaut code » de NTAI5, clés
#: ``ai.rediger.<canal>``).
REDACTION_CONSIGNE_CANAL = {
    'email': 'Ton professionnel, 120 à 180 mots, avec une formule de politesse.',
    'whatsapp': 'Ton direct et cordial, 40 mots maximum, sans en-tête ni signature.',
    'sms': 'Ton neutre, 160 caractères maximum, une seule phrase utile.',
}


def _activity_texte(act) -> str:
    """Texte lisible d'une entrée de chatter/activité (jamais vide → '')."""
    if act.body:
        return str(act.body).strip()
    if act.note:
        return str(act.note).strip()
    if act.kind == 'modification' and (act.field_label or act.field):
        libelle = act.field_label or act.field
        return f'{libelle} : {act.old_value or "—"} → {act.new_value or "—"}'
    return str(act.summary or '').strip()


def aplatir_fil(*, company, content_type, object_id,
                limit=REDACTION_FIL_LIMITE) -> list[dict]:
    """Met à plat le chatter + les activités d'une cible, du plus ANCIEN au
    plus récent, au format attendu par ``core.ai.services.format_thread``.

    Scopé société : seules les entrées de ``company`` sont lues.
    """
    from apps.records.models import Activity

    qs = (Activity.objects
          .filter(content_type=content_type, object_id=object_id,
                  company=company)
          .select_related('created_by')
          .order_by('-created_at', '-id')[:limit])
    entrees = []
    for act in reversed(list(qs)):
        texte = _activity_texte(act)
        if not texte:
            continue
        auteur = getattr(act.created_by, 'username', '') or ''
        entrees.append({
            'auteur': auteur,
            'date': act.created_at.strftime('%Y-%m-%d %H:%M') if act.created_at else '',
            'texte': texte,
            'canal': 'note' if act.kind == 'note' else '',
        })
    return entrees


def rediger_brouillon(*, company, content_type, object_id, canal='email',
                      intention='', max_tokens=400) -> dict:
    """NTAI11 — Propose un brouillon FR de réponse/relance sur une fiche.

    ``content_type`` est un libellé ``'app.model'`` validé contre les cibles
    autorisées du chatter générique (``records.serializers.resolve_target`` —
    vérifie AUSSI l'appartenance à la société). ``canal`` règle le ton/format.

    N'ENVOIE JAMAIS : renvoie un brouillon éditable (``envoye: False``).
    """
    from apps.records.serializers import resolve_target
    from core.ai.services import draft_reply

    canal = str(canal or 'email').strip().lower()
    if canal not in REDACTION_CANAUX:
        raise AiCopiloteUnavailable(
            f'Canal inconnu — attendu : {", ".join(REDACTION_CANAUX)}.')

    try:
        ct, cible = resolve_target(content_type, object_id, company)
    except ValueError as exc:
        raise AiCopiloteUnavailable(str(exc))

    if not is_capability_configured('llm'):
        raise AiCopiloteUnavailable(
            "Aucun fournisseur LLM n'est configuré (clé absente) — "
            'rédaction manuelle requise.', configured=False)

    fil = aplatir_fil(company=company, content_type=ct, object_id=cible.pk)
    contexte = f'{ct.app_label}.{ct.model} « {str(cible)[:120]} »'
    consigne = REDACTION_CONSIGNE_CANAL.get(canal, '')
    intention = str(intention or '').strip()[:REDACTION_INTENTION_MAX]
    instruction = ' '.join(p for p in (intention, consigne) if p)

    res = draft_reply(fil, channel=canal, context=contexte,
                      instruction=instruction, max_tokens=max_tokens)
    if not res.configured:
        raise AiCopiloteUnavailable(
            "Aucun fournisseur LLM n'est configuré (clé absente) — "
            'rédaction manuelle requise.', configured=False)
    if not res.available:
        raise AiCopiloteUnavailable(
            "Le fournisseur n'a pas produit de brouillon exploitable.")

    return {
        'content_type': f'{ct.app_label}.{ct.model}',
        'object_id': cible.pk,
        'canal': canal,
        'brouillon': res.draft,
        'entrees_fil': len(fil),
        # Contrat explicite : RIEN n'a été envoyé ni enregistré.
        'envoye': False,
        'source': res.source,
    }


# ─────────────────────────────────────────────────────────────────────────────
# NTAI12 — Compte rendu d'intervention DICTÉ (voix → CR structuré SAV)
# ─────────────────────────────────────────────────────────────────────────────
#
# Reprend les garde-fous du flux OCR existant (XSAL8 ``scan_carte_visite``) :
# taille bornée, octets magiques vérifiés, débit limité côté vue, et surtout
# AUCUNE PERSISTANCE de l'audio — les octets ne vivent qu'en mémoire le temps
# de la transcription (jamais de MinIO, jamais de pièce jointe).
#
# Ce service NE CHANGE JAMAIS le statut du ticket : le moteur SAV existant
# reste seul maître des transitions. Il rend un CR structuré à valider.

#: Taille max d'un mémo vocal (mémo de chantier de quelques minutes).
CR_AUDIO_MAX_BYTES = 20 * 1024 * 1024  # 20 Mo

#: Octets magiques des conteneurs audio courants d'un téléphone de chantier.
#: Même motif que ``crm.services._CARTE_VISITE_MAGIC`` — aucune dépendance
#: nouvelle, aucune confiance dans le ``Content-Type`` déclaré par le client.
CR_AUDIO_MAGIC = {
    'audio/ogg': lambda h: h[:4] == b'OggS',
    'audio/wav': lambda h: h[:4] == b'RIFF' and h[8:12] == b'WAVE',
    'audio/mpeg': lambda h: h[:3] == b'ID3' or (
        len(h) >= 2 and h[0] == 0xFF and (h[1] & 0xE0) == 0xE0),
    'audio/mp4': lambda h: h[4:8] == b'ftyp',
    'audio/flac': lambda h: h[:4] == b'fLaC',
    'audio/webm': lambda h: h[:4] == b'\x1a\x45\xdf\xa3',
}

#: Sections du compte rendu structuré (ordre stable, contrat de l'UI).
CR_SECTIONS = ('diagnostic', 'travaux', 'pieces', 'recommandations')

#: Prompt système par défaut (futur « défaut code » de NTAI5, clé
#: ``ai.cr_intervention``).
CR_SYSTEM = (
    "Tu es un technicien SAV solaire au Maroc. À partir du mémo vocal "
    "transcrit ci-dessous, produis UNIQUEMENT un objet JSON avec exactement "
    'les clés "diagnostic", "travaux", "pieces", "recommandations" (valeurs = '
    "chaînes en français). N'invente rien : si le mémo ne dit rien d'une "
    "section, mets une chaîne vide. Aucun texte hors du JSON."
)


def _detect_audio_mime(entete: bytes) -> str | None:
    """MIME déduit des octets magiques, ou ``None`` si non reconnu."""
    for mime, test in CR_AUDIO_MAGIC.items():
        try:
            if test(entete):
                return mime
        except IndexError:  # pragma: no cover - entête trop court
            continue
    return None


def _parse_cr_json(texte: str) -> dict:
    """Extrait le CR structuré d'une sortie LLM (tolère un JSON entouré).

    Renvoie toujours les 4 sections (chaînes, éventuellement vides). Si aucun
    JSON exploitable n'est présent, le texte brut atterrit dans ``diagnostic``
    — jamais d'exception, jamais de section inventée.
    """
    brut = (texte or '').strip()
    charge = None
    match = re.search(r'\{.*\}', brut, re.DOTALL)
    if match:
        try:
            charge = json.loads(match.group(0))
        except (ValueError, TypeError):
            charge = None
    if not isinstance(charge, dict):
        return {'diagnostic': brut, 'travaux': '', 'pieces': '',
                'recommandations': ''}
    return {
        section: str(charge.get(section) or '').strip()
        for section in CR_SECTIONS
    }


def cr_intervention_depuis_audio(*, company, file_bytes, ticket_id=None,
                                 max_tokens=600) -> dict:
    """NTAI12 — Transcrit un mémo vocal puis le structure en CR d'intervention.

    Renvoie ``{transcript, cr: {diagnostic, travaux, pieces, recommandations},
    ticket_id, applique: False}``. NE PERSISTE PAS l'audio et N'ÉCRIT RIEN sur
    le ticket (statut inclus) : le CR est un pré-remplissage à valider.

    Lève :class:`AiCopiloteUnavailable` : fichier absent/trop gros/format non
    reconnu ou ticket hors société (400) ; aucune clé STT (503, aucun appel
    réseau).
    """
    from apps.sav.selectors import ticket_scoped
    from core.ai.services import transcribe_audio

    if not file_bytes:
        raise AiCopiloteUnavailable('Aucun fichier audio fourni.')
    if len(file_bytes) > CR_AUDIO_MAX_BYTES:
        raise AiCopiloteUnavailable('Mémo vocal trop volumineux (max 20 Mo).')

    mime = _detect_audio_mime(file_bytes[:12])
    if mime is None:
        raise AiCopiloteUnavailable(
            'Format audio non reconnu (OGG, WAV, MP3, M4A, FLAC ou WebM).')

    ticket = None
    if ticket_id not in (None, ''):
        try:
            ticket = ticket_scoped(company, ticket_id)
        except (TypeError, ValueError):
            ticket = None
        if ticket is None:
            raise AiCopiloteUnavailable('Ticket introuvable.')

    res = transcribe_audio(content=file_bytes, mime_type=mime, language='fr')
    if not res.configured:
        raise AiCopiloteUnavailable(
            "Aucun fournisseur de transcription n'est configuré (clé "
            'absente) — saisie manuelle requise.', configured=False)
    transcript = str((res.data or {}).get('text') or '').strip()
    if not res.ok or not transcript:
        raise AiCopiloteUnavailable(
            "La transcription n'a produit aucun texte exploitable.")

    cr = {section: '' for section in CR_SECTIONS}
    structure = False
    if is_capability_configured('llm'):
        llm = get_provider('llm').complete(
            prompt=transcript, system=CR_SYSTEM, max_tokens=max_tokens)
        if llm.ok and (llm.data or {}).get('text'):
            cr = _parse_cr_json(llm.data['text'])
            structure = True
    if not structure:
        # Dégradation : sans LLM, le technicien reçoit quand même sa dictée
        # transcrite, à répartir lui-même dans les sections.
        cr['diagnostic'] = transcript

    return {
        'ticket_id': getattr(ticket, 'id', None),
        'transcript': transcript,
        'cr': cr,
        'structure': structure,
        # Contrat explicite : rien n'est enregistré, aucun statut changé.
        'applique': False,
        'source': res.provider,
    }


# ─────────────────────────────────────────────────────────────────────────────
# NTAI36 — Brouillon de rapport d'activité périodique
# ─────────────────────────────────────────────────────────────────────────────
#
# RÈGLE STRUCTURANTE : les CHIFFRES sont calculés par le SERVEUR (via les
# sélecteurs de lecture existants), le LLM ne fait que les METTRE EN PHRASES.
# Un garde-fou vérifie ensuite que le narratif ne contient AUCUN nombre absent
# des métriques calculées — un rapport qui invente un chiffre est REFUSÉ, pas
# publié avec une note de bas de page.

#: Modules couverts (chacun adossé à un sélecteur de lecture EXISTANT).
RAPPORT_MODULES = ('commercial', 'facturation')

#: Prompt système par défaut (futur « défaut code » de NTAI5, clé
#: ``ai.rapport_periode``).
RAPPORT_SYSTEM = (
    "Tu es analyste d'activité pour un installateur solaire au Maroc. Rédige "
    "en français un court narratif (4 à 6 phrases) commentant les métriques "
    "fournies. INTERDICTION ABSOLUE d'introduire un chiffre qui ne figure pas "
    "dans la liste : ne calcule rien, n'extrapole rien, ne compare à aucune "
    "période absente. Reprends les nombres tels quels."
)

#: Séparateurs de milliers tolérés (espace fine/insécable incluses).
_ESPACES = ' ' + chr(9) + chr(0x00A0) + chr(0x202F) + chr(0x2009)

#: Nombres d'un texte, séparateurs de milliers compris.
_NOMBRE_RE = re.compile(r'\d+(?:[' + _ESPACES + r']\d{3})*(?:[.,]\d+)?')

#: Table de suppression des espaces avant comparaison numérique.
_SANS_ESPACES = {ord(c): None for c in _ESPACES}

#: Un jour — passage d'une borne de fin EXCLUSIVE à INCLUSIVE.
_UN_JOUR = timedelta(days=1)


def _normaliser_nombre(valeur) -> str | None:
    """Forme canonique comparable d'un nombre ('1 234,50' -> '1234.5')."""
    brut = str(valeur).strip().translate(_SANS_ESPACES).replace(',', '.')
    try:
        dec = Decimal(brut)
    except (InvalidOperation, ValueError, TypeError):
        return None
    texte = f'{dec:f}'
    if '.' in texte:
        texte = texte.rstrip('0').rstrip('.')
    return texte or '0'


def _formes_autorisees(valeur) -> set:
    """Formes acceptables d'une métrique (exacte, tronquée, arrondie).

    Un narratif qui dit « environ 1 235 » pour 1234,56 reste légitime ; un
    narratif qui sort un 999 de nulle part ne l'est pas.
    """
    formes = set()
    canonique = _normaliser_nombre(valeur)
    if canonique is None:
        return formes
    formes.add(canonique)
    try:
        dec = Decimal(canonique)
    except (InvalidOperation, ValueError):
        return formes
    formes.add(_normaliser_nombre(int(dec)))
    formes.add(_normaliser_nombre(int(dec.to_integral_value())))
    return {f for f in formes if f}


def nombres_hors_source(texte: str, valeurs) -> list:
    """Nombres du narratif ABSENTS des valeurs calculées serveur.

    Liste vide = narratif entièrement adossé aux chiffres du serveur.
    """
    autorises = set()
    for valeur in valeurs:
        autorises |= _formes_autorisees(valeur)
    intrus = []
    for brut in _NOMBRE_RE.findall(texte or ''):
        canonique = _normaliser_nombre(brut)
        if canonique is not None and canonique not in autorises:
            intrus.append(brut.strip())
    return intrus


def _bornes_periode(periode: str) -> tuple:
    """('2026-07') → (date(2026, 7, 1), date(2026, 8, 1)) — fin EXCLUE."""
    try:
        annee_txt, mois_txt = str(periode).strip().split('-', 1)
        annee, mois = int(annee_txt), int(mois_txt)
        debut = date(annee, mois, 1)
    except (ValueError, TypeError):
        raise AiCopiloteUnavailable(
            'Période invalide — format attendu AAAA-MM (ex. 2026-07).')
    fin = date(annee + 1, 1, 1) if mois == 12 else date(annee, mois + 1, 1)
    return debut, fin


def metriques_periode(*, company, module, periode) -> list[dict]:
    """Métriques CALCULÉES SERVEUR d'un module sur une période mensuelle.

    Chaque entrée : ``{'cle', 'label', 'valeur', 'unite'}``. Lecture seule,
    scopée société, via les sélecteurs EXISTANTS des apps métier (jamais leurs
    modèles — règle cross-app). Aucun ``prix_achat`` n'entre ici.
    """
    debut, fin = _bornes_periode(periode)

    if module == 'commercial':
        from apps.crm.selectors import attribution_leads

        # `fin` est INCLUSIVE côté attribution_leads → dernier jour du mois.
        rapport = attribution_leads(company, debut, fin - _UN_JOUR)
        lignes = rapport.get('par_source') or []
        nb_leads = sum(int(li.get('nb_leads') or 0) for li in lignes)
        nb_signes = sum(int(li.get('nb_signes') or 0) for li in lignes)
        ca_signe = sum(
            (Decimal(str(li.get('ca_signe') or 0)) for li in lignes),
            Decimal('0'))
        taux = (Decimal(nb_signes) * 100 / Decimal(nb_leads)
                if nb_leads else Decimal('0'))
        return [
            {'cle': 'nb_leads', 'label': 'Leads créés',
             'valeur': nb_leads, 'unite': ''},
            {'cle': 'nb_signes', 'label': 'Leads signés',
             'valeur': nb_signes, 'unite': ''},
            {'cle': 'taux_conversion_pct', 'label': 'Taux de conversion',
             'valeur': round(float(taux), 1), 'unite': '%'},
            {'cle': 'ca_signe', 'label': 'CA signé',
             'valeur': ca_signe, 'unite': 'MAD'},
        ]

    if module == 'facturation':
        from apps.ventes.selectors import analyse_facturation

        lignes = analyse_facturation(company, debut, fin)
        nb_factures = sum(int(li.get('nb_factures') or 0) for li in lignes)
        total_ht = sum(
            (Decimal(str(li.get('total_ht') or 0)) for li in lignes),
            Decimal('0'))
        total_ttc = sum(
            (Decimal(str(li.get('total_ttc') or 0)) for li in lignes),
            Decimal('0'))
        return [
            {'cle': 'nb_factures', 'label': 'Factures émises',
             'valeur': nb_factures, 'unite': ''},
            {'cle': 'total_ht', 'label': 'Total HT facturé',
             'valeur': total_ht, 'unite': 'MAD'},
            {'cle': 'total_ttc', 'label': 'Total TTC facturé',
             'valeur': total_ttc, 'unite': 'MAD'},
        ]

    raise AiCopiloteUnavailable(
        f'Module inconnu — attendu : {", ".join(RAPPORT_MODULES)}.')


def build_rapport_prompt(module, periode, metriques) -> str:
    """Prompt utilisateur : uniquement les métriques calculées serveur."""
    lignes = [
        f"- {m['label']} : {m['valeur']}{(' ' + m['unite']) if m['unite'] else ''}"
        for m in metriques
    ]
    return (f'Module : {module}\nPériode : {periode}\n'
            'Métriques (les SEULS chiffres autorisés) :\n' + '\n'.join(lignes))


def rapport_periode(*, company, module, periode, max_tokens=400) -> dict:
    """NTAI36 — Brouillon de rapport d'activité périodique, chiffres serveur.

    Renvoie ``{module, periode, metriques, narratif, envoye: False}``. Le
    narratif est REFUSÉ (400) s'il contient un nombre absent des métriques.
    Sans clé LLM : 503 douce — les métriques restent lisibles via l'écran de
    reporting existant.
    """
    module = str(module or '').strip().lower()
    if module not in RAPPORT_MODULES:
        raise AiCopiloteUnavailable(
            f'Module inconnu — attendu : {", ".join(RAPPORT_MODULES)}.')

    metriques = metriques_periode(
        company=company, module=module, periode=periode)

    if not is_capability_configured('llm'):
        raise AiCopiloteUnavailable(
            "Aucun fournisseur LLM n'est configuré (clé absente) — les "
            'métriques restent consultables dans le reporting.',
            configured=False)

    prompt = build_rapport_prompt(module, periode, metriques)
    res = get_provider('llm').complete(
        prompt=prompt, system=RAPPORT_SYSTEM, max_tokens=max_tokens)
    if not res.ok or not (res.data or {}).get('text'):
        raise AiCopiloteUnavailable(
            "Le fournisseur n'a pas produit de narratif exploitable.")

    narratif = str(res.data['text']).strip()
    # Garde « aucun nombre inventé » : le millésime et le mois de la période
    # sont légitimes (« en juillet 2026 »), tout le reste doit venir du serveur.
    debut, _fin = _bornes_periode(periode)
    autorisees = [m['valeur'] for m in metriques] + [debut.year, debut.month]
    intrus = nombres_hors_source(narratif, autorisees)
    if intrus:
        raise AiCopiloteUnavailable(
            'Narratif refusé — chiffres absents des métriques calculées : '
            f'{", ".join(intrus[:5])}.')

    return {
        'module': module,
        'periode': periode,
        'metriques': [
            {**m, 'valeur': str(m['valeur'])} for m in metriques
        ],
        'narratif': narratif,
        # Contrat explicite : brouillon éditable, jamais diffusé tout seul.
        'envoye': False,
        'source': res.provider,
    }


# ─────────────────────────────────────────────────────────────────────────────
# NTAI35 — Assistant de configuration (« Setup Copilot »)
# ─────────────────────────────────────────────────────────────────────────────
#
# GUIDAGE SEUL : cet assistant ne modifie AUCUN paramètre. Il répond à une
# question de paramétrage et renvoie des liens profonds vers les écrans
# Paramètres RÉELLEMENT montés (voir ``config_index`` — un test vérifie que
# chaque lien existe dans le routeur de la SPA).
#
# Sans clé LLM, la réponse dégrade sur la FAQ statique de l'index (le résumé de
# l'écran le plus pertinent) : l'utilisateur obtient toujours son lien.

#: Prompt système par défaut (futur « défaut code » de NTAI5, clé
#: ``ai.assistant_config``).
ASSISTANT_CONFIG_SYSTEM = (
    "Tu es l'assistant de paramétrage d'un ERP. Réponds en français, en 2 à 3 "
    "phrases, en t'appuyant EXCLUSIVEMENT sur les écrans fournis ci-dessous. "
    "N'invente aucun écran, aucun chemin, aucune option. Si les écrans ne "
    "répondent pas à la question, dis-le simplement. Ne propose jamais de "
    "modifier un réglage à la place de l'utilisateur."
)


def assistant_config(*, question, role=None, max_tokens=300) -> dict:
    """NTAI35 — Répond à une question de paramétrage + liens profonds.

    Renvoie ``{question, reponse, ecrans: [{titre, lien, resume}], source}``
    où ``source`` vaut ``'llm'`` (réponse rédigée) ou ``'faq'`` (repli
    statique, sans clé). N'ÉCRIT JAMAIS.
    """
    from .config_index import rechercher_ecrans

    question = str(question or '').strip()
    if not question:
        raise AiCopiloteUnavailable('Question requise.')

    ecrans = rechercher_ecrans(question, role=role)
    charge = [
        {'titre': e['titre'], 'lien': e['lien'], 'resume': e['resume']}
        for e in ecrans
    ]
    if not charge:
        return {
            'question': question,
            'reponse': ("Aucun écran de paramétrage ne correspond à cette "
                        'question. Reformulez avec le réglage cherché (TVA, '
                        'notifications, alertes, export…).'),
            'ecrans': [],
            'source': 'faq',
            # Contrat explicite : guidage seul, aucune modification.
            'modifie': False,
        }

    if not is_capability_configured('llm'):
        # Repli FAQ statique : le résumé de l'écran le plus pertinent.
        return {
            'question': question,
            'reponse': charge[0]['resume'],
            'ecrans': charge,
            'source': 'faq',
            'modifie': False,
        }

    contexte = '\n'.join(
        f"- {e['titre']} ({e['lien']}) : {e['resume']}" for e in charge)
    res = get_provider('llm').complete(
        prompt=f'Question : {question}\n\nÉcrans disponibles :\n{contexte}',
        system=ASSISTANT_CONFIG_SYSTEM, max_tokens=max_tokens)
    if res.ok and (res.data or {}).get('text'):
        return {
            'question': question,
            'reponse': str(res.data['text']).strip(),
            'ecrans': charge,
            'source': 'llm',
            'modifie': False,
        }
    # Le fournisseur a échoué : on rend quand même la FAQ, jamais une erreur.
    return {
        'question': question,
        'reponse': charge[0]['resume'],
        'ecrans': charge,
        'source': 'faq',
        'modifie': False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# NTAI17 — File de traitement document AI (classification + extraction)
# ─────────────────────────────────────────────────────────────────────────────
#
# Une pièce déposée dans la GED crée un JOB (``DocumentAiJob``) que la tâche
# Celery traite HORS REQUÊTE. Deux étages, du moins coûteux au plus :
#
#   1. CLASSIFICATION — réutilise ``ged.services.classer_document`` (GED34) :
#      heuristique locale gratuite, puis provider IA s'il est configuré. On ne
#      recode PAS un second classifieur.
#   2. EXTRACTION — le gabarit ``core.ai.schemas`` correspondant à la catégorie
#      détectée, via ``core.ai.extract_document``. KEY-GATED : sans provider OCR
#      actif, on ne lit MÊME PAS les octets du stockage (aucun appel réseau,
#      aucun coût) et le job finit « traité » avec ``extraction_disponible``
#      à faux.
#
# RIEN N'EST ÉCRIT dans un modèle métier : le résultat attend une validation
# humaine (NTAI18). Cross-app : les lectures GED passent par ses
# ``selectors``/``services``, jamais par ses modèles.

#: Catégorie GED34 → nom de gabarit ``core.ai.schemas``. Une catégorie absente
#: (ou dont le gabarit n'existe pas encore, ex. « facture » tant que NTAI16
#: n'a pas posé ``facture_fournisseur``) donne une extraction vide, jamais une
#: erreur : la classification seule reste utile.
CATEGORIE_VERS_SCHEMA = {
    'cin': 'cin',
    'contrat': 'contrat',
    'bon_livraison': 'bon_livraison',
    'facture': 'facture_fournisseur',
    'cv': 'cv',
    'carte_visite': 'carte_visite',
}


def document_jobs_enabled() -> bool:
    """NTAI17 — True si la file de traitement documentaire est activée.

    KEY-GATED, **OFF par défaut** (``AI_DOCUMENT_JOBS_ENABLED``) : sans clé IA
    configurée, empiler des jobs que rien ne peut traiter n'apporte rien. Quand
    le flag est éteint, aucun job n'est créé et le dépôt d'une pièce GED reste
    byte-identique à ce qu'il était.
    """
    from django.conf import settings
    return bool(getattr(settings, 'AI_DOCUMENT_JOBS_ENABLED', False))


def schema_pour_categorie(categorie: str) -> str:
    """Gabarit d'extraction pour ``categorie``, ou '' si aucun n'est disponible.

    Consulte ``core.ai.schemas.available_schemas()`` À L'EXÉCUTION : le jour où
    un nouveau gabarit est ajouté (NTAI15/NTAI16), la file l'utilise sans
    modification ici.
    """
    from core.ai.schemas import available_schemas

    nom = CATEGORIE_VERS_SCHEMA.get((categorie or '').strip().lower(), '')
    return nom if nom in available_schemas() else ''


def creer_document_ai_job(document):
    """NTAI17 — Crée le job « en attente » d'une pièce GED (ou None).

    Renvoie None (sans lever) quand la file est éteinte ou quand la pièce n'a
    pas de société (le scoping serait impossible). Si un job est DÉJÀ en
    attente pour cette pièce, il est renvoyé tel quel : l'appel est IDEMPOTENT
    sur un double enregistrement.
    """
    from .models import DocumentAiJob

    if not document_jobs_enabled():
        return None
    company_id = getattr(document, 'company_id', None)
    if not company_id:
        return None
    deja = DocumentAiJob.objects.filter(
        company_id=company_id, document=document,
        statut=DocumentAiJob.STATUT_EN_ATTENTE).first()
    if deja is not None:
        return deja
    return DocumentAiJob.objects.create(
        company_id=company_id, document=document,
        statut=DocumentAiJob.STATUT_EN_ATTENTE)


def _octets_du_document(document):
    """(contenu, mime) de la dernière version stockée, ou ``(None, '')``.

    Passe par les ``selectors`` de la GED (jamais ses modèles) puis par le
    stockage objet partagé. Ne lève jamais."""
    try:
        from apps.ged import selectors as ged_selectors
        from apps.records.storage import fetch_attachment
    except Exception:  # noqa: BLE001 - app absente/mal chargée : no-op.
        return None, ''
    try:
        version = ged_selectors.latest_version(document)
    except Exception:  # noqa: BLE001
        return None, ''
    if version is None or not getattr(version, 'file_key', ''):
        return None, ''
    try:
        data, _erreur = fetch_attachment(version.file_key)
    except Exception:  # noqa: BLE001 - stockage indisponible : no-op propre.
        return None, ''
    return data, (getattr(version, 'mime', '') or '')


def traiter_document_ai_job(job):
    """NTAI17 — Classe puis extrait, et remplit ``resultat_json``.

    BEST-EFFORT : toute exception est CAPTURÉE dans ``statut='erreur'`` +
    ``message`` ; la fonction ne lève jamais. Renvoie le job mis à jour.
    """
    from django.utils import timezone

    from .models import DocumentAiJob

    resultat = {
        'categorie': '',
        'schema': '',
        'champs': {},
        'extraction_disponible': False,
        # Contrat explicite : le résultat est une PROPOSITION ; l'application
        # aux modèles métier reste une action humaine (NTAI18).
        'applique': False,
    }
    try:
        from apps.ged import services as ged_services

        document = job.document
        categorie = ged_services.classer_document(document) or ''
        resultat['categorie'] = categorie
        schema = schema_pour_categorie(categorie)
        resultat['schema'] = schema

        confiance = 0.0
        if schema and is_capability_configured('ocr'):
            from core.ai.services import extract_document

            contenu, mime = _octets_du_document(document)
            if contenu:
                res = extract_document(
                    content=contenu, mime_type=mime or 'application/pdf',
                    schema=schema)
                if res.configured:
                    resultat['extraction_disponible'] = True
                if res.ok:
                    donnees = dict(res.data or {})
                    confiance = float(donnees.pop('confiance', 0.0) or 0.0)
                    resultat['champs'] = donnees
        job.categorie = categorie
        job.schema = schema
        job.confiance = confiance
        job.resultat_json = resultat
        job.statut = DocumentAiJob.STATUT_TRAITE
        job.message = ''
    except Exception as exc:  # noqa: BLE001 - un échec ne casse jamais la GED.
        job.statut = DocumentAiJob.STATUT_ERREUR
        job.message = str(exc)[:500]
        job.resultat_json = resultat
    job.traite_le = timezone.now()
    job.save(update_fields=[
        'categorie', 'schema', 'confiance', 'resultat_json', 'statut',
        'message', 'traite_le', 'updated_at'])
    return job


# ─────────────────────────────────────────────────────────────────────────────
# NTAI18 — Boucle de correction humaine des extractions (feedback → qualité)
# ─────────────────────────────────────────────────────────────────────────────
#
# La revue est le SEUL chemin par lequel une extraction devient une donnée de
# confiance : l'utilisateur valide ou corrige CHAMP PAR CHAMP, et chaque écart
# est journalisé (``ExtractionCorrection``). On obtient gratuitement deux
# choses : le taux de correction RÉEL par gabarit (donc la qualité mesurée, pas
# supposée) et un « jeu d'or » de cas vrais pour évaluer un futur modèle.
#
# Toujours AUCUNE écriture métier : la valeur retenue est appliquée au RÉSULTAT
# du job (la proposition), jamais à une facture, un contrat ou un stock.


def enregistrer_corrections(job, corrections, *, user=None):
    """NTAI18 — Journalise la revue humaine d'une extraction et l'applique.

    ``corrections`` est une liste de ``{'champ': ..., 'valeur_corrigee': ...}``.
    Pour chaque entrée : la valeur PROPOSÉE est relue dans le résultat du job,
    l'écart est enregistré, puis la valeur RETENUE remplace la proposée dans
    ``resultat_json['champs']``.

    Lève ``AiCopiloteUnavailable`` (→ 400) si la charge est vide ou mal formée.
    Renvoie ``{'job', 'corrections': [...], 'champs': {...}}``.
    """
    from .models import ExtractionCorrection

    if not isinstance(corrections, (list, tuple)) or not corrections:
        raise AiCopiloteUnavailable(
            'Fournissez au moins une correction '
            '{champ, valeur_corrigee}.')

    resultat = dict(job.resultat_json or {})
    champs = dict(resultat.get('champs') or {})
    lignes = []
    for entree in corrections:
        if not isinstance(entree, dict):
            raise AiCopiloteUnavailable(
                'Chaque correction doit être un objet '
                '{champ, valeur_corrigee}.')
        champ = str(entree.get('champ') or '').strip()
        if not champ:
            raise AiCopiloteUnavailable('Le nom du champ est requis.')
        valeur_corrigee = entree.get('valeur_corrigee')
        valeur_corrigee = ('' if valeur_corrigee is None
                           else str(valeur_corrigee))
        valeur_ia = champs.get(champ)
        valeur_ia = '' if valeur_ia is None else str(valeur_ia)

        lignes.append(ExtractionCorrection(
            company_id=job.company_id, job=job, champ=champ,
            valeur_ia=valeur_ia, valeur_corrigee=valeur_corrigee,
            corrige_par=user if getattr(user, 'pk', None) else None))
        champs[champ] = valeur_corrigee

    creees = ExtractionCorrection.objects.bulk_create(lignes)
    resultat['champs'] = champs
    # Marque la revue humaine ; ``applique`` reste FAUX — la proposition n'est
    # toujours pas écrite dans un modèle métier (ce n'est pas le rôle de la GED).
    resultat['revu_par_humain'] = True
    job.resultat_json = resultat
    job.save(update_fields=['resultat_json', 'updated_at'])
    return {
        'job': job.pk,
        'champs': champs,
        'corrections': [
            {'champ': c.champ, 'valeur_ia': c.valeur_ia,
             'valeur_corrigee': c.valeur_corrigee,
             'modifie': (c.valeur_ia or '') != (c.valeur_corrigee or '')}
            for c in creees
        ],
    }


def taux_correction_par_schema(company) -> list:
    """NTAI18 — Qualité mesurée de chaque gabarit d'extraction, par société.

    Pour chaque schéma : combien de champs ont été REVUS, combien ont été
    réellement MODIFIÉS, et le taux qui en découle. Purement en lecture, scopé
    société, aucun appel LLM.
    """
    from .models import DocumentAiJob, ExtractionCorrection

    par_schema = {}
    jobs = dict(
        DocumentAiJob.objects.filter(company=company)
        .values_list('pk', 'schema'))
    for job_pk, schema in jobs.items():
        par_schema.setdefault(schema or '(aucun)',
                              {'revus': 0, 'corriges': 0})
    corrections = ExtractionCorrection.objects.filter(
        company=company).values_list('job_id', 'valeur_ia', 'valeur_corrigee')
    for job_id, valeur_ia, valeur_corrigee in corrections:
        cle = jobs.get(job_id) or '(aucun)'
        stats = par_schema.setdefault(cle, {'revus': 0, 'corriges': 0})
        stats['revus'] += 1
        if (valeur_ia or '') != (valeur_corrigee or ''):
            stats['corriges'] += 1

    sortie = []
    for schema in sorted(par_schema):
        stats = par_schema[schema]
        revus = stats['revus']
        sortie.append({
            'schema': schema,
            'champs_revus': revus,
            'champs_corriges': stats['corriges'],
            'taux_correction': (round(stats['corriges'] / revus, 4)
                                if revus else 0.0),
        })
    return sortie


# ─────────────────────────────────────────────────────────────────────────────
# NTAI25 — Recherche sémantique GLOBALE avec citations (« Ask your ERP »)
# ─────────────────────────────────────────────────────────────────────────────
#
# DISTINCT de l'agent NL→SQL existant : celui-là interroge des AGRÉGATS (« combien
# de devis signés en juin ? »), celui-ci répond sur des FICHES/DOCUMENTS (« quels
# clients ont un litige ouvert et un contrat qui expire ? ») en CITANT chaque
# source réelle.
#
# GARDE NTAI4 : le LLM ne voit QUE les fiches remontées par l'index (NTAI24,
# scopé société) et doit citer sous la forme fermée ``[app.model#id]``. Toute
# citation qui ne figure pas dans ces résultats est RETIRÉE de la réponse et
# rapportée dans ``citations_ecartees`` — jamais rendue à l'utilisateur, jamais
# transformée en lien mort.

#: Nombre de fiches injectées dans le contexte : assez pour répondre, assez peu
#: pour rester lisible et borné en coût.
RECHERCHE_GLOBALE_LIMITE = 8

#: Forme FERMÉE d'une citation — c'est ce que la garde sait vérifier.
CITATION_RE = re.compile(r'\[([a-z_]+\.[a-z_]+)#(\d+)\]')

RECHERCHE_GLOBALE_SYSTEM = (
    "Tu réponds en français à une question sur les données d'une entreprise, "
    'en te fondant EXCLUSIVEMENT sur les fiches fournies ci-dessous. '
    'Cite chaque fiche utilisée sous la forme exacte [app.model#id] '
    "(par exemple [crm.lead#12]), juste après l'information qu'elle appuie. "
    "N'invente aucune fiche, aucun chiffre et aucune citation : si les fiches "
    'ne permettent pas de répondre, dis-le simplement.'
)


def _contexte_citations(resultats) -> str:
    """Contexte injecté au LLM : une ligne par fiche, avec sa citation exacte."""
    lignes = []
    for fiche in resultats:
        reference = f"[{fiche['content_type']}#{fiche['object_id']}]"
        lignes.append(
            f"{reference} {fiche['titre']} — {fiche['extrait']}".strip())
    return '\n'.join(lignes)


def filtrer_citations(reponse, resultats):
    """NTAI4 — Retire de ``reponse`` toute citation absente des ``resultats``.

    Renvoie ``(texte_nettoye, citations_utilisees, citations_ecartees)``. Une
    citation inventée est SUPPRIMÉE du texte : l'utilisateur ne peut pas cliquer
    sur une fiche qui n'existe pas.
    """
    connues = {
        f"{f['content_type']}#{f['object_id']}": f for f in resultats
    }
    utilisees, ecartees = [], []

    def _remplacer(match):
        cle = f'{match.group(1)}#{match.group(2)}'
        fiche = connues.get(cle)
        if fiche is None:
            if cle not in ecartees:
                ecartees.append(cle)
            return ''
        if fiche not in utilisees:
            utilisees.append(fiche)
        return match.group(0)

    texte = CITATION_RE.sub(_remplacer, str(reponse or ''))
    # Nettoie les espaces doublés laissés par une citation retirée.
    texte = re.sub(r'[ \t]{2,}', ' ', texte).strip()
    return texte, utilisees, ecartees


def recherche_globale(*, company, question, limit=RECHERCHE_GLOBALE_LIMITE,
                      max_tokens=600) -> dict:
    """NTAI25 — Répond à ``question`` sur les fiches de ``company``, avec sources.

    Renvoie ``{question, reponse, citations, resultats, source,
    citations_ecartees}`` où ``source`` vaut ``'llm'`` (réponse rédigée) ou
    ``'recherche'`` (repli : la liste des fiches trouvées, sans rédaction —
    c'est ce qui se passe sans clé LLM). N'ÉCRIT JAMAIS.
    """
    from core.ai.search import rechercher

    question = str(question or '').strip()
    if not question:
        raise AiCopiloteUnavailable('Question requise.')

    resultats = rechercher(company, question, limit=limit)
    if not resultats:
        return {
            'question': question,
            'reponse': ('Aucune fiche ne correspond à cette question dans '
                        'vos données.'),
            'citations': [],
            'resultats': [],
            'source': 'recherche',
            'citations_ecartees': [],
        }

    if not is_capability_configured('llm'):
        # Repli : la recherche existante rend ses fiches telles quelles.
        return {
            'question': question,
            'reponse': ('Recherche par mots-clés : '
                        f'{len(resultats)} fiche(s) trouvée(s).'),
            'citations': resultats,
            'resultats': resultats,
            'source': 'recherche',
            'citations_ecartees': [],
        }

    res = get_provider('llm').complete(
        prompt=(f'Question : {question}\n\nFiches disponibles :\n'
                f'{_contexte_citations(resultats)}'),
        system=RECHERCHE_GLOBALE_SYSTEM, max_tokens=max_tokens)
    if not res.ok or not (res.data or {}).get('text'):
        # Le fournisseur a échoué : on rend les fiches, jamais une erreur.
        return {
            'question': question,
            'reponse': ('Recherche par mots-clés : '
                        f'{len(resultats)} fiche(s) trouvée(s).'),
            'citations': resultats,
            'resultats': resultats,
            'source': 'recherche',
            'citations_ecartees': [],
        }

    texte, utilisees, ecartees = filtrer_citations(
        res.data['text'], resultats)
    return {
        'question': question,
        'reponse': texte,
        'citations': utilisees,
        'resultats': resultats,
        'source': 'llm',
        'citations_ecartees': ecartees,
    }
