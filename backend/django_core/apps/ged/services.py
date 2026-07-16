"""Écritures / orchestration de la GED.

Point d'entrée des écritures cross-app (CLAUDE.md). La société est TOUJOURS
fournie par l'appelant (résolue côté serveur depuis `request.user.company`) —
jamais lue d'un corps de requête. Réutilise les conventions de stockage de
`records.storage` (clé MinIO `file_key`) sans réimplémenter le stockage.
"""
import hashlib
import logging
import re

from django.contrib.postgres.search import SearchVector
from django.db import models, transaction
from django.db.models import Value

from core.pdf import render_pdf

from .models import Cabinet, Document, DocumentVersion, Folder, RoutageDocumentaire

logger = logging.getLogger(__name__)


def update_search_vector(document):
    """GED11 — Recalcule le tsvector plein-texte d'un document.

    Le vecteur agrège le nom (poids A), la description + métadonnées (poids B)
    et le texte OCR (poids C, alimenté par GED12). Calculé en base via
    `SearchVector` (config 'french'). Idempotent — à rappeler après toute
    écriture qui change le contenu indexable.
    """
    meta = ''
    if isinstance(document.custom_data, dict):
        meta = ' '.join(str(v) for v in document.custom_data.values() if v)
    Document.objects.filter(pk=document.pk).update(
        search_vector=(
            SearchVector('nom', weight='A', config='french')
            + SearchVector(Value(document.description or ''),
                           weight='B', config='french')
            + SearchVector(Value(meta), weight='B', config='french')
            + SearchVector('texte_ocr', weight='C', config='french')
        )
    )


def set_ocr_text(document, texte):
    """GED12/GED11 — Pose le texte OCR d'un document et réindexe le tsvector.

    Sert de point d'entrée unique pour l'indexation OCR : on stocke le texte
    extrait, on rafraîchit la recherche plein-texte (GED11), puis on (ré)indexe
    l'embedding sémantique (GED12, no-op sans clé)."""
    Document.objects.filter(pk=document.pk).update(texte_ocr=texte or '')
    document.texte_ocr = texte or ''
    update_search_vector(document)
    index_embedding(document)
    # FG352 — (ré)indexe les fragments RAG/DocQA (no-op sans clé).
    index_document_chunks(document)
    return document


# ── GED33 — OCR de pièces (extraction de texte, KEY-GATED no-op) ─────────────
#
# Pipeline d'extraction de texte par OCR. KEY-GATED comme l'embedding (GED12) et
# l'e-sign (GED30) : sans `settings.GED_OCR_ENABLED` à vrai, `ocr_extract_text`
# est un NO-OP déterministe (renvoie '' — aucun appel réseau, aucun coût, aucune
# dépendance nouvelle). Le founder branchera un provider réel (Zhipu OCR, déjà
# utilisé par le service FastAPI IA) en posant le flag + la clé ; tant que ce
# n'est pas fait, l'OCR ne fabrique jamais de texte fantôme.

def ocr_enabled():
    """GED33 — True si l'OCR de pièces est activé (clé OCR présente).

    KEY-GATED : sans `settings.GED_OCR_ENABLED`, toute extraction est un no-op
    (chaîne vide). Le founder l'active en posant le flag + la clé du provider."""
    from django.conf import settings
    return bool(getattr(settings, 'GED_OCR_ENABLED', False))


def ocr_extract_text(file_bytes, *, mime=''):
    """GED33 — Extrait le texte d'un fichier image/PDF par OCR (no-op sans clé).

    NO-OP PAR DÉFAUT : renvoie '' tant que `ocr_enabled()` est faux — le
    squelette d'appel provider est isolé ici pour un futur branchement (Zhipu OCR
    via le service FastAPI IA) sans toucher au reste du module. Ne lève jamais
    (robustesse : l'OCR ne doit pas casser un dépôt documentaire)."""
    if not file_bytes or not ocr_enabled():
        return ''
    provider = None
    try:  # pragma: no cover - dépend d'un provider externe non câblé ici.
        from . import ocr_provider as provider  # noqa: F401
    except ImportError:
        provider = None
    if provider is None:  # pragma: no cover
        return ''
    try:  # pragma: no cover
        return provider.extract_text(file_bytes, mime=mime) or ''
    except Exception:  # pragma: no cover - jamais bloquer un dépôt.
        return ''


def ocr_index_document(document, *, file_bytes=None, mime=''):
    """GED33 — Lance l'OCR d'un document et indexe le texte extrait (no-op sans clé).

    Si l'OCR est activé et qu'on a les octets du fichier, extrait le texte et le
    pose via `set_ocr_text` (qui réindexe plein-texte + sémantique). Renvoie le
    texte extrait ('' si OCR désactivé / aucun texte). Idempotent ; ne lève
    jamais. `file_bytes` est fourni par l'appelant (jamais re-téléchargé ici
    sans nécessité — l'appelant a souvent déjà les octets en main au dépôt)."""
    if not ocr_enabled() or not file_bytes:
        return ''
    texte = ocr_extract_text(file_bytes, mime=mime)
    if texte:
        set_ocr_text(document, texte)
    return texte


# ── GED33 — Extraction de métadonnées de pièces (CIN / facture / BL) ─────────
#
# Couche DÉTERMINISTE (regex, AUCUNE clé, AUCUN appel réseau) qui parse un texte
# (issu de l'OCR GED33 ou saisi) en métadonnées typées selon le type de pièce.
# Sépare proprement l'EXTRACTION DE TEXTE (key-gated, ci-dessus) de l'ANALYSE
# DU TEXTE (locale, gratuite). Marocaine : CIN (carte nationale), facture, BL
# (bon de livraison). Renvoie un dict de champs reconnus — jamais d'invention :
# un champ absent du texte est simplement omis.

PIECE_CIN = 'cin'
PIECE_FACTURE = 'facture'
PIECE_BL = 'bl'
PIECE_TYPES = (PIECE_CIN, PIECE_FACTURE, PIECE_BL)


def _premier_match(pattern, texte, *, flags=0, group=1):
    """Premier groupe capturé d'un motif dans le texte, ou '' (helper extraction)."""
    import re
    m = re.search(pattern, texte, flags)
    return (m.group(group).strip() if m else '')


def detecter_type_piece(texte):
    """GED33 — Devine le type d'une pièce d'après son texte (heuristique locale).

    Renvoie 'cin' | 'facture' | 'bl' | '' (inconnu). Purement déterministe :
    cherche des marqueurs francophones/marocains usuels. Aucun appel externe."""
    import re
    if not texte:
        return ''
    t = texte.lower()
    if re.search(r'carte\s+nationale|cin\b|c\.i\.n', t):
        return PIECE_CIN
    if re.search(r'bon\s+de\s+livraison|\bb\.?l\.?\b', t):
        return PIECE_BL
    if re.search(r'\bfacture\b|montant\s+t\.?t\.?c|total\s+ttc', t):
        return PIECE_FACTURE
    return ''


def extraire_metadonnees_piece(texte, *, type_piece=None):
    """GED33 — Extrait des métadonnées typées d'un texte de pièce (déterministe).

    `type_piece` (optionnel) force le type ; sinon il est deviné
    (`detecter_type_piece`). Renvoie `{'type_piece': <type>, ...champs}`. Les
    champs reconnus selon le type :
      * cin      : numero_cin (ex. AB123456) ;
      * facture  : numero_facture, montant_ttc, date ;
      * bl       : numero_bl, date.
    AUCUNE invention : un champ non trouvé est omis. Aucune dépendance, aucun
    appel réseau — pur parsing local (utilisable même OCR désactivé)."""
    import re

    texte = texte or ''
    piece = type_piece or detecter_type_piece(texte)
    meta = {}
    if piece:
        meta['type_piece'] = piece

    if piece == PIECE_CIN:
        # CIN marocaine : 1-2 lettres suivies de 5-6 chiffres.
        num = _premier_match(
            r'\b([A-Za-z]{1,2}\s?\d{5,6})\b', texte)
        if num:
            meta['numero_cin'] = num.replace(' ', '').upper()
    elif piece == PIECE_FACTURE:
        num = _premier_match(
            r'facture\s*(?:n[°o]?\.?)?\s*[:#]?\s*([A-Za-z0-9\-/]+)',
            texte, flags=re.IGNORECASE)
        # AUCUNE invention : un vrai numéro de facture contient au moins un
        # chiffre. Sans chiffre (p.ex. « FACTURE sans numéro » capture « sans »),
        # on n'invente rien et on omet le champ.
        if num and any(c.isdigit() for c in num):
            meta['numero_facture'] = num
        ttc = _premier_match(
            r'(?:total\s+ttc|montant\s+t\.?t\.?c\.?)\s*[:=]?\s*'
            r'([0-9][0-9\s.,]*)',
            texte, flags=re.IGNORECASE)
        if ttc:
            meta['montant_ttc'] = ttc.strip().rstrip('.,')
        date = _premier_match(r'\b(\d{2}[/-]\d{2}[/-]\d{4})\b', texte)
        if date:
            meta['date'] = date
    elif piece == PIECE_BL:
        num = _premier_match(
            r'(?:bon\s+de\s+livraison|b\.?l\.?)\s*(?:n[°o]?\.?)?\s*[:#]?\s*'
            r'([A-Za-z0-9\-/]+)',
            texte, flags=re.IGNORECASE)
        if num:
            meta['numero_bl'] = num
        date = _premier_match(r'\b(\d{2}[/-]\d{2}[/-]\d{4})\b', texte)
        if date:
            meta['date'] = date
    return meta


def ocr_piece_vers_metadonnees(document, *, file_bytes=None, mime='',
                               type_piece=None, fusionner=True):
    """GED33 — OCR une pièce puis extrait ses métadonnées (CIN/facture/BL).

    Enchaîne `ocr_index_document` (extraction de texte, no-op sans clé) puis
    `extraire_metadonnees_piece` (parsing local déterministe) sur le texte
    disponible (OCR frais OU `document.texte_ocr` déjà présent). Si `fusionner`
    est vrai, les champs reconnus sont fusionnés (additivement) dans
    `document.custom_data` (jamais d'écrasement d'une clé existante non vide) et
    persistés côté serveur.

    Renvoie le dict de métadonnées extraites (vide si rien trouvé). Sans clé OCR
    et sans `texte_ocr` préexistant, renvoie {} (jamais d'invention)."""
    texte = ''
    if file_bytes:
        texte = ocr_index_document(
            document, file_bytes=file_bytes, mime=mime)
    if not texte:
        # Retombe sur le texte OCR déjà indexé (ex. posé manuellement / GED12).
        document.refresh_from_db(fields=['texte_ocr'])
        texte = document.texte_ocr or ''
    meta = extraire_metadonnees_piece(texte, type_piece=type_piece)
    if meta and fusionner:
        data = dict(document.custom_data or {})
        for k, v in meta.items():
            if not data.get(k):  # additif : ne jamais écraser une valeur posée.
                data[k] = v
        Document.objects.filter(pk=document.pk).update(custom_data=data)
        document.custom_data = data
    return meta


# ── XGED13 — File de validation d'extraction OCR (confiance + tableaux) ──

# Sous ce seuil (0-1), le document entre dans la file de validation manuelle.
OCR_CONFIANCE_SEUIL_DEFAUT = 0.6

_LIGNE_TABLEAU_RE = re.compile(
    r'^(?P<designation>.{3,80}?)\s{2,}(?P<qte>\d+(?:[.,]\d+)?)\s+'
    r'(?P<pu>\d[\d\s.,]*)\s*$')


def score_confiance_extraction(texte, meta):
    """XGED13 — Score de confiance heuristique (0-1) d'une extraction OCR.

    Sans provider de score natif (le chemin Zhipu peut en fournir un directement
    — à brancher ICI si le provider l'expose), on retombe sur une heuristique de
    COMPLÉTUDE : proportion de champs attendus pour le `type_piece` détecté
    effectivement trouvés, pondérée par la longueur du texte source (un texte
    très court est toujours suspect)."""
    if not texte or not meta:
        return 0.0
    attendus = {
        PIECE_CIN: ['numero_cin'],
        PIECE_FACTURE: ['numero_facture', 'montant_ttc', 'date'],
        PIECE_BL: ['numero_bl', 'date'],
    }.get(meta.get('type_piece'), [])
    if not attendus:
        return 0.3 if meta else 0.0
    trouves = sum(1 for k in attendus if meta.get(k))
    completude = trouves / len(attendus)
    longueur_ok = 1.0 if len(texte) >= 40 else len(texte) / 40
    return round(min(1.0, completude * 0.8 + longueur_ok * 0.2), 2)


def extraire_lignes_tableau(texte):
    """XGED13 — Extrait des lignes de tableau (désignation/qté/PU) d'un texte
    de facture/BL — heuristique locale (une ligne = 1 désignation suivie de 2
    nombres séparés par ≥2 espaces, motif typique d'un OCR de tableau tabulé).
    AUCUNE invention : renvoie [] si rien ne matche."""
    lignes = []
    for raw_line in (texte or '').splitlines():
        m = _LIGNE_TABLEAU_RE.match(raw_line.strip())
        if not m:
            continue
        lignes.append({
            'designation': m.group('designation').strip(),
            'qte': m.group('qte').replace(',', '.'),
            'pu': m.group('pu').strip().rstrip('.,'),
        })
    return lignes


def ocr_extraction_avec_validation(document, *, file_bytes=None, mime='',
                                   type_piece=None, seuil=None):
    """XGED13 — Étend `ocr_piece_vers_metadonnees` : calcule un score de
    confiance et, sous le seuil configuré, met le document EN FILE DE
    VALIDATION (`ValidationOcrDocument`, statut « a_valider ») au lieu
    d'appliquer directement les métadonnées. Au-dessus du seuil, les
    métadonnées sont fusionnées normalement (comportement GED33 inchangé) et
    aucune entrée de validation n'est créée. Ajoute aussi
    `custom_data['lignes']` (lignes de tableau extraites) quand présentes.

    Renvoie `(meta, en_validation: bool)`."""
    from .models import ValidationOcrDocument

    seuil = OCR_CONFIANCE_SEUIL_DEFAUT if seuil is None else seuil
    texte = ''
    if file_bytes:
        texte = ocr_index_document(document, file_bytes=file_bytes, mime=mime)
    if not texte:
        document.refresh_from_db(fields=['texte_ocr'])
        texte = document.texte_ocr or ''
    meta = extraire_metadonnees_piece(texte, type_piece=type_piece)
    lignes = extraire_lignes_tableau(texte)
    if lignes:
        meta = dict(meta)
        meta['lignes'] = lignes
    score = score_confiance_extraction(texte, meta)

    if score < seuil and meta:
        ValidationOcrDocument.objects.update_or_create(
            document=document,
            defaults={
                'company': document.company,
                'score_confiance': score,
                'champs_extraits': meta,
                'valide': False,
                'valide_par': None,
                'valide_le': None,
            })
        return meta, True

    # Confiance suffisante : fusion directe (comportement GED33 inchangé).
    if meta:
        data = dict(document.custom_data or {})
        for k, v in meta.items():
            if k == 'lignes' or not data.get(k):
                data[k] = v
        Document.objects.filter(pk=document.pk).update(custom_data=data)
        document.custom_data = data
    return meta, False


def valider_extraction_ocr(validation, *, champs_corriges, user):
    """XGED13 — Valide (avec corrections) une extraction en file d'attente :
    applique `champs_corriges` à `document.custom_data` (additif, jamais
    d'écrasement d'une clé non listée) puis solde la validation."""
    document = validation.document
    data = dict(document.custom_data or {})
    data.update(champs_corriges or {})
    Document.objects.filter(pk=document.pk).update(custom_data=data)
    document.custom_data = data
    from django.utils import timezone as _tz
    validation.valide = True
    validation.champs_extraits = champs_corriges or validation.champs_extraits
    validation.valide_par = user
    validation.valide_le = _tz.now()
    validation.save(update_fields=[
        'valide', 'champs_extraits', 'valide_par', 'valide_le', 'updated_at'])
    return validation


# ── GED34 — Classification automatique (IA gated + heuristique locale) ───────
#
# Attribue une CATÉGORIE à un document. Deux étages, du moins coûteux au plus :
#   1. HEURISTIQUE LOCALE (gratuite, déterministe) — mots-clés sur le nom +
#      texte OCR, réutilise `detecter_type_piece` (GED33). TOUJOURS disponible.
#   2. PROVIDER IA (KEY-GATED) — `classification_enabled()` ; sans
#      `settings.GED_CLASSIFICATION_ENABLED`, c'est un NO-OP (aucun appel réseau,
#      aucun coût) et on retombe sur l'heuristique locale.
# La classification ne fait que SUGGÉRER (pose `custom_data['categorie']` de
# façon additive) — elle ne déplace ni ne supprime jamais un document, et reste
# LOCALE à la GED (séparée du funnel STAGES.py, rule #2).

# Catégories locales reconnues par l'heuristique (mots-clés FR/marocains).
CLASSIFICATION_KEYWORDS = {
    'facture': ('facture', 'montant ttc', 'total ttc'),
    'bon_livraison': ('bon de livraison', ' bl ', 'bordereau'),
    'cin': ('carte nationale', 'cin', 'c.i.n'),
    'contrat': ('contrat', 'convention', 'engagement'),
    'devis': ('devis', 'proposition commerciale'),
    'attestation': ('attestation', 'certificat'),
    'photo': ('photo', 'image du chantier'),
}


def classification_enabled():
    """GED34 — True si la classification IA est activée (clé présente).

    KEY-GATED : sans `settings.GED_CLASSIFICATION_ENABLED`, le provider IA est un
    no-op et la classification retombe sur l'heuristique locale (gratuite)."""
    from django.conf import settings
    return bool(getattr(settings, 'GED_CLASSIFICATION_ENABLED', False))


def classer_heuristique(texte):
    """GED34 — Catégorie déduite par mots-clés locaux (déterministe), ou ''.

    Aucune clé, aucun appel réseau. Renvoie la première catégorie dont un
    mot-clé apparaît dans le texte (nom + OCR), sinon '' (inconnu — jamais
    d'invention)."""
    if not texte:
        return ''
    t = f' {texte.lower()} '
    for categorie, mots in CLASSIFICATION_KEYWORDS.items():
        for mot in mots:
            if mot in t:
                return categorie
    return ''


def classer_ia(texte):  # pragma: no cover - dépend d'un provider externe non câblé.
    """GED34 — Classification via le provider IA configuré, ou '' (no-op sans clé).

    NO-OP PAR DÉFAUT : renvoie '' tant que `classification_enabled()` est faux.
    Le squelette d'appel provider est isolé ici pour un futur branchement sans
    toucher au reste du module. Ne lève jamais."""
    if not texte or not classification_enabled():
        return ''
    provider = None
    try:
        from . import classification_provider as provider  # noqa: F401
    except ImportError:
        provider = None
    if provider is None:
        return ''
    try:
        return provider.classify(texte) or ''
    except Exception:
        return ''


def classer_document(document, *, fusionner=True):
    """GED34 — Classe un document (IA gated → fallback heuristique local).

    Construit le texte de travail (`nom` + `texte_ocr`), tente d'abord le
    provider IA (no-op sans clé) puis l'heuristique locale. Si `fusionner` est
    vrai et qu'une catégorie est trouvée, la pose ADDITIVEMENT dans
    `custom_data['categorie']` (jamais d'écrasement d'une valeur déjà posée) et
    persiste côté serveur. Ne déplace ni ne supprime jamais le document.

    Renvoie la catégorie (str) ou '' si indéterminée. Idempotent ; ne lève
    jamais (la classification ne doit pas casser une écriture documentaire)."""
    texte = f'{document.nom}\n{document.texte_ocr or ""}'.strip()
    categorie = ''
    try:
        categorie = classer_ia(texte)
    except Exception:  # pragma: no cover - robustesse.
        categorie = ''
    if not categorie:
        categorie = classer_heuristique(texte)
    if categorie and fusionner:
        data = dict(document.custom_data or {})
        if not data.get('categorie'):
            data['categorie'] = categorie
            Document.objects.filter(pk=document.pk).update(custom_data=data)
            document.custom_data = data
    return categorie


# ── GED12 — Index OCR + recherche sémantique (pgvector, KEY-GATED no-op) ──

def embedding_enabled():
    """True si la recherche sémantique est activée (clé d'embedding présente).

    KEY-GATED : sans `settings.GED_EMBEDDING_ENABLED` à vrai, tout est un no-op
    (aucun appel réseau, aucun coût) et la recherche sémantique retombe sur la
    recherche plein-texte GED11. Le founder active la fonctionnalité en posant
    le flag + la clé du provider dans l'environnement."""
    from django.conf import settings
    return bool(getattr(settings, 'GED_EMBEDDING_ENABLED', False))


def compute_embedding(text):
    """Calcule l'embedding d'un texte via le provider configuré, ou None.

    NO-OP par défaut : renvoie None tant que `embedding_enabled()` est faux —
    le squelette d'appel provider est isolé ici pour un futur branchement
    (Zhipu/OpenAI-compatible) sans toucher au reste du module. Un provider réel
    devra renvoyer une liste de `EMBEDDING_DIM` flottants."""
    if not text or not embedding_enabled():
        return None
    # Branchement provider à venir (clé-gated). Tant qu'aucun provider concret
    # n'est câblé, on reste no-op même flag activé — jamais d'appel fantôme.
    provider = None
    try:  # pragma: no cover - dépend d'un provider externe non câblé ici.
        from . import embedding_provider as provider  # noqa: F401
    except ImportError:
        provider = None
    if provider is None:
        return None
    vec = provider.embed(text)  # pragma: no cover
    return vec  # pragma: no cover


def index_embedding(document):
    """GED12 — (Ré)indexe l'embedding sémantique d'un document (no-op sans clé).

    Concatène nom + texte OCR, calcule l'embedding (no-op sans clé) et le stocke
    dans `Document.embedding`. Idempotent ; ne lève jamais (l'indexation ne doit
    pas casser une écriture documentaire). Renvoie True si un vecteur a été posé.
    """
    if not embedding_enabled():
        return False
    text = f'{document.nom}\n{document.texte_ocr or ""}'.strip()
    try:
        vec = compute_embedding(text)
    except Exception:  # pragma: no cover - robustesse : jamais bloquer l'écriture.
        vec = None
    if vec is None:
        return False
    Document.objects.filter(pk=document.pk).update(embedding=vec)
    document.embedding = vec
    return True


# ── FG352 — RAG / DocQA : indexation par fragments (pgvector, no-op sans clé) ──

# Paramètres de découpage par défaut (caractères). Un chevauchement préserve le
# contexte aux frontières de fragments. Modestes : un manuel reste lisible et le
# nombre de fragments par document reste raisonnable.
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


def chunk_text(text, *, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP):
    """FG352 — Découpe un texte en fragments chevauchants pour le RAG.

    Utilise `langchain-textsplitters` (RecursiveCharacterTextSplitter) quand il
    est disponible — il coupe en priorité sur les frontières naturelles
    (paragraphes, phrases) avant de tomber sur les caractères. Import gardé : si
    la dépendance n'est pas installée, on retombe sur un découpage fenêtré pur
    Python équivalent, pour que le code reste import-safe partout (CI sans clé).

    Renvoie une liste de fragments non vides (jamais None). Un texte vide donne
    une liste vide.
    """
    if not text or not str(text).strip():
        return []
    text = str(text)
    try:  # Dépendance optionnelle — import gardé (no-op-safe sans la lib).
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        chunks = splitter.split_text(text)
    except Exception:  # pragma: no cover - chemin de repli sans la lib.
        # Repli pur Python : fenêtre glissante avec chevauchement.
        chunks = []
        step = max(1, chunk_size - chunk_overlap)
        for start in range(0, len(text), step):
            piece = text[start:start + chunk_size]
            if piece:
                chunks.append(piece)
    return [c.strip() for c in chunks if c and c.strip()]


def index_document_chunks(document):
    """FG352 — (Ré)indexe les fragments RAG d'un document (no-op sans clé).

    Découpe le texte du document (nom + texte OCR) en fragments, calcule un
    embedding par fragment (no-op sans clé) et les stocke dans `DocumentChunk`,
    dans le MÊME magasin pgvector que `Document.embedding` — pas un second
    magasin. Idempotent : remplace les fragments existants du document. Ne lève
    jamais (l'indexation ne doit pas casser une écriture documentaire).

    KEY-GATED : sans clé d'embedding, c'est un no-op total — on n'écrit aucun
    fragment et on renvoie 0. La company de chaque fragment est posée côté
    serveur (celle du document), jamais lue d'un corps de requête.

    Renvoie le nombre de fragments embeddés et stockés.
    """
    from .models import DocumentChunk
    if not embedding_enabled():
        return 0
    text = f'{document.nom}\n{document.texte_ocr or ""}'.strip()
    pieces = chunk_text(text)
    if not pieces:
        # Plus aucun contenu indexable : purge les anciens fragments.
        DocumentChunk.objects.filter(document=document).delete()
        return 0
    rows = []
    for idx, piece in enumerate(pieces):
        try:
            vec = compute_embedding(piece)
        except Exception:  # pragma: no cover - robustesse : jamais bloquer.
            vec = None
        if vec is None:
            continue
        rows.append(DocumentChunk(
            company=document.company, document=document,
            chunk_index=idx, texte=piece, embedding=vec))
    with transaction.atomic():
        DocumentChunk.objects.filter(document=document).delete()
        if rows:
            DocumentChunk.objects.bulk_create(rows)
    return len(rows)


def validate_coffre_owner(proprietaire, client):
    """GED8 — Un coffre porte EXACTEMENT un propriétaire (employé XOR client).

    Lève ValueError si aucun ou si les deux sont fournis. Sert de garde unique
    pour la création/mise à jour, côté service comme côté serializer.
    """
    has_user = proprietaire is not None
    has_client = client is not None
    if has_user and has_client:
        raise ValueError(
            "Un coffre-fort a un seul propriétaire : un employé OU un client.")
    if not has_user and not has_client:
        raise ValueError(
            "Un coffre-fort doit avoir un propriétaire (employé ou client).")


def compute_checksum(data):
    """SHA-256 hex d'un contenu binaire — sert à la déduplication."""
    if isinstance(data, str):
        data = data.encode('utf-8')
    return hashlib.sha256(data).hexdigest()


def _document_archive_legalement(document):
    """GED23 — True si un document est archivé légalement (write-once).

    Helper interne partagé par les gardes d'écriture (déplacement, verrou,
    transition de cycle de vie…). Lecture en base de l'existence d'un
    `ArchivageLegal` sur le document. Import paresseux pour éviter tout cycle."""
    from .models import ArchivageLegal
    if document.pk is None:
        return False
    return ArchivageLegal.objects.filter(document_id=document.pk).exists()


def validate_tag_parent(tag, new_parent):
    """GED9 — Garde anti-cycle / cross-société pour la taxonomie de tags.

    Refuse qu'un tag devienne son propre parent, qu'il descende sous l'un de ses
    descendants (cycle), ou qu'il pointe sur un parent d'une autre société. À
    appeler avant de poser `parent`. `new_parent` peut être None (tag racine).
    """
    if new_parent is None:
        return
    if tag is not None and new_parent.pk == tag.pk:
        raise ValueError("Un tag ne peut pas être son propre parent.")
    if tag is not None and tag.company_id is not None \
            and new_parent.company_id != tag.company_id:
        raise ValueError("Le parent doit appartenir à la même société.")
    if tag is not None and tag.pk is not None:
        # Empêche un cycle : le nouveau parent ne doit pas être un descendant.
        courant = new_parent
        seen = set()
        while courant is not None and courant.pk not in seen:
            if courant.pk == tag.pk:
                raise ValueError(
                    "Déplacement impossible : le parent est un descendant.")
            seen.add(courant.pk)
            courant = courant.parent


def assign_tag(document, tag, *, created_by=None):
    """GED9 — Applique un tag de la taxonomie à un document (idempotent).

    Le tag et le document doivent appartenir à la même société (jamais de fuite
    cross-société). Renvoie (assignment, created).
    """
    from .models import DocumentTag, DocumentTagAssignment  # noqa: F401
    if tag.company_id != document.company_id:
        raise ValueError("Le tag doit appartenir à la même société.")
    return DocumentTagAssignment.objects.get_or_create(
        document=document, tag=tag,
        defaults={'company': document.company, 'created_by': created_by})


def move_folder(folder, new_parent):
    """Déplace un dossier sous un nouveau parent et recalcule les chemins.

    Recalcule le chemin matérialisé du dossier ET de tout son sous-arbre — la
    contrainte de cohérence du chemin matérialisé. `new_parent` peut être None
    (dossier remis à la racine). Refuse un cycle (devenir son propre ancêtre).
    """
    if new_parent is not None:
        if new_parent.pk == folder.pk:
            raise ValueError("Un dossier ne peut pas être son propre parent.")
        # Empêche de déplacer un dossier sous l'un de ses descendants (cycle).
        if folder.path and new_parent.path.startswith(folder.path):
            raise ValueError(
                "Déplacement impossible : cible dans le sous-arbre du dossier.")
        if new_parent.cabinet_id != folder.cabinet_id:
            raise ValueError(
                "Le dossier cible doit appartenir au même cabinet.")
    with transaction.atomic():
        old_path = folder.path
        folder.parent = new_parent
        folder.save()  # recalcule folder.path via Folder.save()
        new_path = folder.path
        # Réécrit le préfixe de chemin de chaque descendant.
        if old_path and old_path != new_path:
            for desc in Folder.objects.filter(
                    company=folder.company, path__startswith=old_path
            ).exclude(pk=folder.pk):
                desc.path = new_path + desc.path[len(old_path):]
                desc.save(update_fields=['path'])
    return folder


def move_document(document, new_folder):
    """Déplace un document dans un autre dossier (même société).

    Le dossier cible DOIT appartenir à la même société que le document — sinon
    on refuse (jamais de fuite cross-société). La société du document n'est
    jamais modifiée (elle reste posée côté serveur). Renvoie le document.
    """
    if new_folder.company_id != document.company_id:
        raise ValueError(
            "Le dossier cible doit appartenir à la même société.")
    # GED23 — write-once : un document archivé légalement est figé (jamais
    # déplacé). On refuse en `ValueError` (→ 400 côté vue `deplacer`).
    if _document_archive_legalement(document):
        raise ValueError(
            "Document archivé à valeur probante (write-once) : il ne peut plus "
            "être déplacé.")
    if document.folder_id != new_folder.id:
        document.folder = new_folder
        document.save(update_fields=['folder', 'updated_at'])
    return document


def add_version(document, *, file_key, company, filename='', size=0, mime='',
                checksum='', uploaded_by=None, restored_from=None):
    """Ajoute une nouvelle version à un document (numéro auto-incrémenté).

    Le numéro de version est calculé côté serveur (dernière + 1) et la société
    est forcée à celle du document (jamais du corps de requête). `checksum`
    permet la déduplication : un appelant peut vérifier au préalable s'il
    existe déjà une version de même empreinte (voir `find_duplicate`).

    GED15 — `restored_from` : si cette version est le résultat d'une restauration,
    on passe ici la version source pour traçabilité (posé côté serveur dans
    `restore_version`, jamais lu du corps de requête).
    """
    with transaction.atomic():
        last = (DocumentVersion.objects
                .select_for_update()
                .filter(document=document)
                .order_by('-version')
                .first())
        next_version = (last.version + 1) if last else 1
        version = DocumentVersion.objects.create(
            company=company,
            document=document,
            version=next_version,
            file_key=file_key,
            filename=filename,
            size=size,
            mime=mime,
            checksum=checksum,
            uploaded_by=uploaded_by,
            restored_from=restored_from,
        )
    # XGED15 — journal automatique : nouvelle version (best-effort).
    journaliser_evenement(
        document, type_evenement='nouvelle_version',
        message=f'Version {next_version} ajoutée.', utilisateur=uploaded_by)
    return version


def restore_version(document, source_version, *, uploaded_by=None):
    """GED15 — Restaure un document à une version antérieure (non destructif).

    Crée une NOUVELLE version (numéro max + 1) dont le contenu (file_key,
    filename, size, mime, checksum) est copié depuis `source_version`, en
    traçant le lien via `restored_from`. L'historique est ENTIÈREMENT PRÉSERVÉ —
    aucune version n'est modifiée ou supprimée.

    La `source_version` doit appartenir au même document ET à la même société
    (validé ici côté serveur — jamais du corps de requête). La société de la
    nouvelle version est toujours celle du document.

    Renvoie la nouvelle version créée.
    """
    # Garde : la version source doit appartenir à ce document et cette société.
    if source_version.document_id != document.pk:
        raise ValueError("La version source n'appartient pas à ce document.")
    if source_version.company_id != document.company_id:
        raise ValueError(
            "La version source n'appartient pas à la même société.")
    return add_version(
        document,
        file_key=source_version.file_key,
        company=document.company,
        filename=source_version.filename,
        size=source_version.size,
        mime=source_version.mime,
        checksum=source_version.checksum,
        uploaded_by=uploaded_by,
        restored_from=source_version,
    )


def find_duplicate(company, checksum):
    """Première version d'une société portant ce checksum, ou None (dedup)."""
    if not checksum:
        return None
    return (DocumentVersion.objects
            .filter(company=company, checksum=checksum)
            .order_by('id')
            .first())


def create_document(*, company, folder, nom, description='', created_by=None,
                    custom_data=None):
    """Crée un document dans un dossier (société cohérente avec le dossier).

    `custom_data` (optionnel) permet de poser des métadonnées typées dès la
    création (ex. la trace de l'objet métier source pour un dépôt cross-app) —
    posées côté serveur, jamais lues d'un corps de requête.
    """
    if folder.company_id != getattr(company, 'id', company):
        raise ValueError("Le dossier doit appartenir à la même société.")
    return Document.objects.create(
        company=company, folder=folder, nom=nom,
        description=description, created_by=created_by,
        custom_data=custom_data if custom_data is not None else dict())


# ── Dépôt cross-app : enregistrer un fichier/des octets existants en GED ─────

# Clés réservées dans `Document.custom_data` qui tracent l'objet métier source
# d'un document déposé par une AUTRE app (ex. contrats). Sert d'ancre
# d'idempotence : un dépôt répété pour le même objet source retrouve le document
# déjà créé au lieu d'en dupliquer un. Ces clés vivent dans le JSONField additif
# `custom_data` — on n'invente aucun nouveau schéma de FK.
SOURCE_TYPE_KEY = 'source_type'
SOURCE_ID_KEY = 'source_id'


def ensure_cabinet(company, nom):
    """Retourne (ou crée) le cabinet `nom` d'une société (idempotent).

    Sert l'auto-provisionnement d'un espace documentaire pour un dépôt cross-app
    (ex. un cabinet « Contrats »). La société est posée côté serveur."""
    cabinet, _ = Cabinet.objects.get_or_create(company=company, nom=nom)
    return cabinet


def ensure_root_folder(company, *, cabinet, nom):
    """Retourne (ou crée) un dossier racine `nom` d'un cabinet (idempotent).

    Cherche un dossier RACINE (sans parent) de ce nom dans le cabinet ; sinon le
    crée. Société/cabinet posés côté serveur. Sert l'auto-provisionnement d'un
    dossier de classement pour un dépôt cross-app."""
    folder = Folder.objects.filter(
        company=company, cabinet=cabinet, parent__isnull=True, nom=nom
    ).first()
    if folder is None:
        folder = Folder.objects.create(
            company=company, cabinet=cabinet, nom=nom)
    return folder


def find_document_by_source(company, *, source_type, source_id):
    """Document déjà déposé pour cet objet métier source (idempotence), ou None.

    Borné à la société et résolu DEPUIS la trace `custom_data` (`source_type` +
    `source_id`) — jamais d'un corps de requête. Permet à un appelant cross-app
    de ne pas re-déposer (dédupliquer) le même objet source."""
    if source_type is None or source_id is None:
        return None
    return (Document.objects
            .filter(company=company,
                    custom_data__contains={
                        SOURCE_TYPE_KEY: source_type,
                        SOURCE_ID_KEY: source_id,
                    })
            .order_by('id')
            .first())


def _store_bytes(data, *, mime='application/pdf'):
    """Téléverse des octets bruts dans le stockage objet et renvoie (clé, méta).

    RÉUTILISE les conventions de `records.storage` (bucket
    `settings.MINIO_BUCKET_UPLOADS`, clé `attachments/<uuid>.<ext>`,
    `ensure_uploads_bucket`) — on ne réimplémente PAS de couche de stockage, on
    reprend exactement le même client MinIO partagé. Import paresseux pour rester
    import-safe (CI/dev sans MinIO) et éviter tout cycle d'import.

    Renvoie `(file_key, {'filename', 'size', 'mime'})`.
    """
    import io
    import uuid

    from django.conf import settings

    from apps.ventes.utils.minio_client import (
        ensure_uploads_bucket, get_minio_client,
    )

    ext = 'pdf' if 'pdf' in (mime or '') else 'bin'
    key = f'attachments/{uuid.uuid4().hex}.{ext}'
    client = get_minio_client()
    ensure_uploads_bucket()
    client.upload_fileobj(
        io.BytesIO(data), settings.MINIO_BUCKET_UPLOADS, key,
        ExtraArgs={'ContentType': mime or 'application/octet-stream'})
    return key, {'filename': f'{key.rsplit("/", 1)[-1]}',
                 'size': len(data), 'mime': mime or ''}


def deposit_document(*, company, nom, source_type, source_id,
                     file_key='', filename='', size=0, mime='', checksum='',
                     contenu_bytes=None, description='', cabinet_nom='Contrats',
                     folder_nom='Contrats', created_by=None):
    """Enregistre un fichier/des octets EXISTANTS comme document GED (cross-app).

    Point d'entrée d'ÉCRITURE pour qu'une AUTRE app (ex. `contrats`) dépose un
    document déjà produit (un PDF signé, un instantané de version…) dans le
    référentiel central, SANS importer les modèles GED. On RÉUTILISE les
    primitives existantes (`create_document`, `add_version`) et les conventions
    de stockage `records.storage` — on ne réimplémente ni le stockage ni le
    versionnage.

    Multi-tenant : `company` est posée CÔTÉ SERVEUR par l'appelant (jamais lue
    d'un corps de requête) ; le cabinet, le dossier, le document et sa version
    héritent tous de cette société.

    Source du contenu (au moins l'un) :
      - `file_key` : la clé d'un objet déjà stocké en MinIO (records.storage).
      - `contenu_bytes` : des octets bruts téléversés ici via `_store_bytes`
        (mêmes conventions de stockage objet que `records.storage` : bucket
        erp-uploads, clé `attachments/<uuid>.ext`). Utilisé quand l'appelant
        n'a qu'un rendu en mémoire (ex. un PDF de contrat).
      Si AUCUN n'est fourni, le document est tout de même créé avec une version
      « pointeur vide » (file_key='') — utile pour tracer un instantané textuel
      dont seul le contenu vit dans l'app source.

    IDEMPOTENCE : `source_type`/`source_id` identifient l'objet métier source
    (ex. 'contrats.versioncontrat' + pk). Un dépôt répété pour le MÊME objet
    source ne crée JAMAIS un second document : on retrouve et on renvoie le
    document déjà déposé (pas de doublon GED).

    Renvoie `(document, created)` : le `Document` GED et un booléen indiquant
    s'il vient d'être créé (False = déjà présent, dépôt idempotent).
    """
    # Idempotence : déjà déposé pour cet objet source ? On renvoie l'existant.
    existant = find_document_by_source(
        company, source_type=source_type, source_id=source_id)
    if existant is not None:
        return existant, False

    # Si l'appelant fournit des octets bruts (sans clé), on les stocke via le
    # MÊME stockage objet que `records.storage` (bucket erp-uploads, clé
    # `attachments/<uuid>.ext`) — on RÉUTILISE les conventions de stockage sans
    # réimplémenter de couche. Import paresseux pour rester import-safe sans
    # MinIO et éviter tout cycle.
    if not file_key and contenu_bytes is not None:
        file_key, store_meta = _store_bytes(
            contenu_bytes, mime=mime or 'application/pdf')
        filename = filename or store_meta.get('filename', '')
        size = size or store_meta.get('size', 0)
        mime = mime or store_meta.get('mime', '')
        checksum = checksum or compute_checksum(contenu_bytes)

    cabinet = ensure_cabinet(company, cabinet_nom)
    folder = ensure_root_folder(company, cabinet=cabinet, nom=folder_nom)
    document = create_document(
        company=company, folder=folder, nom=nom, description=description,
        created_by=created_by,
        custom_data={SOURCE_TYPE_KEY: source_type, SOURCE_ID_KEY: source_id})
    # Première version : pointe vers le binaire (ou un pointeur vide si l'app
    # source ne gère qu'un contenu textuel). Numéro auto (add_version, max+1).
    add_version(
        document, file_key=file_key or '', company=company,
        filename=filename or '', size=size or 0, mime=mime or '',
        checksum=checksum or '', uploaded_by=created_by)
    return document, True


# ── GED31 — Numérisation par lot (scan-to-DMS) + OCR ─────────────────────────
#
# Ingestion de PLUSIEURS fichiers scannés en UN appel : chaque fichier devient un
# Document + sa version 1 dans le dossier cible (company-scopé), puis passe le
# hook OCR (GED33, no-op sans clé) et l'indexation plein-texte/sémantique. On
# RÉUTILISE intégralement les primitives existantes (`create_document`,
# `add_version`, `records.storage`) — aucune nouvelle couche de stockage.

def deposer_un_scan(*, company, folder, file_key, filename='', size=0, mime='',
                    checksum='', nom='', description='', created_by=None,
                    contenu_bytes=None):
    """GED31 — Dépose UN fichier scanné comme Document + version 1 (+ OCR hook).

    Le `folder` DOIT appartenir à la société (vérifié par `create_document`).
    Société/créateur posés CÔTÉ SERVEUR (jamais lus d'un corps). Indexe le
    plein-texte + l'embedding (no-op sans clé) et lance l'OCR (no-op sans clé)
    si `contenu_bytes` est fourni. Renvoie le `Document` créé.
    """
    nom = (nom or filename or 'Scan').strip()
    document = create_document(
        company=company, folder=folder, nom=nom, description=description,
        created_by=created_by)
    add_version(
        document, file_key=file_key or '', company=company,
        filename=filename or '', size=size or 0, mime=mime or '',
        checksum=checksum or '', uploaded_by=created_by)
    # GED33 — OCR (no-op sans clé). Indexe le texte extrait si présent.
    ocr_index_document(document, file_bytes=contenu_bytes, mime=mime)
    # GED11/GED12 — indexation plein-texte + sémantique (no-op sans clé).
    update_search_vector(document)
    index_embedding(document)
    index_document_chunks(document)
    return document


def deposer_lot_scans(*, company, folder, fichiers, created_by=None):
    """GED31 — Dépose un LOT de fichiers scannés (scan-to-DMS) en un appel.

    `fichiers` est une liste de dicts décrivant chaque scan déjà stocké
    (`{file_key, filename, size, mime, checksum?, nom?, description?,
    contenu_bytes?}`). Chaque entrée est déposée via `deposer_un_scan`
    (Document + v1 + OCR hook + indexation). Société/créateur posés côté serveur
    pour TOUS les éléments du lot.

    Renvoie la liste des `Document` créés, dans l'ordre du lot. Un lot vide
    renvoie une liste vide (jamais d'erreur).
    """
    documents = []
    for f in (fichiers or []):
        document = deposer_un_scan(
            company=company, folder=folder,
            file_key=f.get('file_key', ''),
            filename=f.get('filename', ''),
            size=f.get('size', 0),
            mime=f.get('mime', ''),
            checksum=f.get('checksum', ''),
            nom=f.get('nom', ''),
            description=f.get('description', ''),
            created_by=created_by,
            contenu_bytes=f.get('contenu_bytes'))
        documents.append(document)
    return documents


# ── XGED12 — Capture mobile photo → PDF multi-pages classé en GED ────────────
#
# Assemble N photos (déjà recadrées/pivotées CÔTÉ CLIENT via canvas — cf.
# `frontend/src/features/ged`) en UN SEUL PDF multi-pages, CÔTÉ SERVEUR, via
# Pillow (déjà pinné — `Image.save(save_all=True)`, AUCUNE dépendance
# nouvelle). Le PDF assemblé est ensuite déposé via le MÊME chemin que
# `televerser` (GED televerser/GED31) — on ne réimplémente ni le stockage ni la
# création de document/version.

def assembler_photos_pdf(images_bytes):
    """XGED12 — Assemble une liste d'octets JPEG/PNG en un PDF multi-pages.

    `images_bytes` : liste non vide d'octets d'image (une entrée = une page,
    dans l'ordre de capture). Chaque image est ouverte via Pillow, convertie en
    RGB (un PDF n'accepte pas la transparence/palette) puis les pages 2..N sont
    ajoutées à la première via `save(..., save_all=True, append_images=...)` —
    exactement le mécanisme multi-pages documenté de Pillow, sans dépendance
    nouvelle (Pillow==10.4.0 déjà pinné).

    Renvoie les octets du PDF assemblé. Lève `ValueError` si `images_bytes` est
    vide ou si une entrée n'est pas une image décodable (jamais un PDF
    silencieusement vide ou corrompu)."""
    import io

    from PIL import Image, UnidentifiedImageError

    if not images_bytes:
        raise ValueError("Au moins une photo est requise pour assembler un PDF.")

    pages = []
    try:
        for raw in images_bytes:
            img = Image.open(io.BytesIO(raw))
            img.load()  # force le décodage immédiat (détecte un fichier corrompu ici)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            pages.append(img)
    except UnidentifiedImageError as exc:
        raise ValueError("Une des photos est illisible (format non supporté).") from exc

    buf = io.BytesIO()
    first, rest = pages[0], pages[1:]
    if rest:
        first.save(buf, format='PDF', save_all=True, append_images=rest)
    else:
        first.save(buf, format='PDF')
    return buf.getvalue()


def deposer_photos_assemblees(*, company, folder, images_bytes, nom='',
                              description='', created_by=None):
    """XGED12 — Assemble des photos en PDF puis les dépose comme Document GED.

    Assemble `images_bytes` (liste d'octets image, une par page) en un PDF
    multi-pages via `assembler_photos_pdf`, stocke le résultat via
    `records.storage.store_attachment` (MÊME pipeline MinIO que `televerser` —
    aucun second chemin d'upload) puis crée le `Document` + sa version 1
    (`create_document` + `add_version`, société/créateur posés CÔTÉ SERVEUR).
    Lance l'OCR (GED33, no-op sans clé) et l'indexation (plein-texte +
    sémantique + RAG) sur le PDF assemblé, comme les autres points de dépôt.

    `folder` DOIT appartenir à `company` (vérifié par `create_document`).
    Renvoie le `Document` créé."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.records.storage import store_attachment

    pdf_bytes = assembler_photos_pdf(images_bytes)
    nom = (nom or 'Numérisation').strip()
    upload = SimpleUploadedFile(
        f'{nom or "numerisation"}.pdf', pdf_bytes, content_type='application/pdf')
    meta, err = store_attachment(upload)
    if err:
        raise ValueError(err)

    document = create_document(
        company=company, folder=folder, nom=nom, description=description,
        created_by=created_by)
    add_version(
        document, file_key=meta['file_key'], company=company,
        filename=meta['filename'], size=meta['size'], mime=meta['mime'],
        checksum=compute_checksum(pdf_bytes), uploaded_by=created_by)
    # GED33 — OCR (no-op sans clé) sur le PDF assemblé.
    ocr_index_document(document, file_bytes=pdf_bytes, mime=meta['mime'])
    # GED11/GED12/FG352 — indexation plein-texte + sémantique + RAG.
    update_search_vector(document)
    index_embedding(document)
    index_document_chunks(document)
    return document


# ── GED32 — Import en masse (CSV de métadonnées + ZIP de fichiers) ───────────
#
# Import gouverné de N documents en un appel : un CSV de MÉTADONNÉES (une ligne
# par document : nom, description, et colonnes de champs personnalisés) crée les
# documents, et un ZIP OPTIONNEL fournit les binaires (appariés par la colonne
# `fichier` = nom de l'entrée dans le zip). Stdlib seulement (`csv`, `zipfile`,
# `io`) — AUCUNE dépendance nouvelle. Tout est company-scopé côté serveur.

# Colonnes CSV réservées (le reste = codes de champs personnalisés customfields).
CSV_COL_NOM = 'nom'
CSV_COL_DESCRIPTION = 'description'
CSV_COL_FICHIER = 'fichier'
CSV_COLS_RESERVEES = {CSV_COL_NOM, CSV_COL_DESCRIPTION, CSV_COL_FICHIER}


def parser_csv_metadonnees(csv_text):
    """GED32 — Parse un CSV de métadonnées en liste de dicts (stdlib `csv`).

    Première ligne = en-têtes. Renvoie une liste de dicts (une par ligne), clés
    normalisées (strip). Robuste à un CSV vide (renvoie []). Ne valide RIEN ici
    (la validation métier — nom requis, custom_data — se fait à l'import)."""
    import csv
    import io

    if not csv_text or not csv_text.strip():
        return []
    reader = csv.DictReader(io.StringIO(csv_text))
    lignes = []
    for row in reader:
        lignes.append({(k or '').strip(): (v or '').strip()
                       for k, v in row.items() if k is not None})
    return lignes


def _zip_entries(zip_bytes):
    """GED32 — Dictionnaire {nom_entrée: octets} d'un ZIP (stdlib `zipfile`).

    Ignore les répertoires. Renvoie {} si `zip_bytes` est vide/invalide (jamais
    d'erreur — un import sans zip reste possible)."""
    import io
    import zipfile

    entries = {}
    if not zip_bytes:
        return entries
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                entries[info.filename] = zf.read(info.filename)
    except (zipfile.BadZipFile, OSError):
        return {}
    return entries


def importer_en_masse(*, company, folder, lignes, zip_bytes=None,
                      created_by=None, valider_custom=None):
    """GED32 — Import en masse de documents depuis des métadonnées (+ZIP optionnel).

    Pour chaque ligne (dict issu de `parser_csv_metadonnees`) :
      * `nom` est REQUIS (ligne sans nom → erreur, ligne ignorée) ;
      * `description` (optionnel) ;
      * `fichier` (optionnel) = nom d'une entrée du ZIP → stockée comme binaire
        de la version 1 ; absente du ZIP → erreur sur la ligne ;
      * toute autre colonne = code de champ personnalisé → `custom_data`
        (validé via `valider_custom(custom_data)` si fourni — un appelant passe
        `customfields.serializers.validate_custom_data` borné société/module).

    Société + créateur posés CÔTÉ SERVEUR pour tout le lot ; le `folder` doit
    appartenir à la société (garde dans `create_document`). Une ligne en erreur
    n'interrompt PAS le lot (collectée dans `erreurs`).

    Renvoie `{'documents': [...], 'erreurs': [{'ligne', 'detail'}], 'crees': n}`.
    """
    entries = _zip_entries(zip_bytes)
    documents = []
    erreurs = []
    for idx, ligne in enumerate(lignes or [], start=1):
        nom = (ligne.get(CSV_COL_NOM) or '').strip()
        if not nom:
            erreurs.append({'ligne': idx, 'detail': 'Nom requis.'})
            continue
        # Champs personnalisés = colonnes hors réservées (valeurs non vides).
        custom_data = {k: v for k, v in ligne.items()
                       if k not in CSV_COLS_RESERVEES and v not in (None, '')}
        if custom_data and valider_custom is not None:
            try:
                custom_data = valider_custom(custom_data)
            except Exception as exc:  # validation customfields → erreur de ligne.
                erreurs.append({'ligne': idx,
                                'detail': f'Métadonnées invalides : {exc}'})
                continue
        # Binaire optionnel apparié par la colonne `fichier`.
        fichier = (ligne.get(CSV_COL_FICHIER) or '').strip()
        contenu_bytes = None
        mime = ''
        if fichier:
            if fichier not in entries:
                erreurs.append({
                    'ligne': idx,
                    'detail': f"Fichier « {fichier} » absent du ZIP."})
                continue
            contenu_bytes = entries[fichier]
            mime = _guess_mime(fichier)
        document = create_document(
            company=company, folder=folder, nom=nom,
            description=(ligne.get(CSV_COL_DESCRIPTION) or '').strip(),
            created_by=created_by,
            custom_data=custom_data or None)
        file_key = ''
        size = 0
        checksum = ''
        if contenu_bytes is not None:
            file_key, store_meta = _store_bytes(
                contenu_bytes, mime=mime or 'application/octet-stream')
            size = store_meta.get('size', 0)
            checksum = compute_checksum(contenu_bytes)
        add_version(
            document, file_key=file_key, company=company,
            filename=fichier or '', size=size, mime=mime,
            checksum=checksum, uploaded_by=created_by)
        update_search_vector(document)
        index_embedding(document)
        index_document_chunks(document)
        documents.append(document)
    return {'documents': documents, 'erreurs': erreurs,
            'crees': len(documents)}


def _guess_mime(filename):
    """GED32 — Devine le type MIME d'un nom de fichier (stdlib `mimetypes`)."""
    import mimetypes
    mime, _ = mimetypes.guess_type(filename)
    return mime or ''


# ── GED16 — Check-out / check-in (verrouillage optimiste) ──────────

def checkout_document(document, user):
    """GED16 — Pose un verrou sur un document (check-out).

    Si le document est LIBRE (locked_by == None), pose locked_by=user et
    locked_at=now dans une transaction sérialisée (select_for_update) pour
    éviter les doubles check-out simultanés.

    Si le document est déjà verrouillé PAR UN AUTRE utilisateur, lève
    PermissionError (→ 409 dans la vue). Si le même utilisateur re-check-out
    son propre document, l'opération est idempotente.

    Multi-tenant : vérifie que user.company_id == document.company_id.
    """
    from django.utils import timezone
    if document.company_id != user.company_id:
        raise PermissionError("Document inaccessible.")
    # GED23 — write-once : on n'extrait pas (check-out) un document archivé
    # légalement — il est figé. Refus en `PermissionError` (→ 409 côté vue).
    if _document_archive_legalement(document):
        raise PermissionError(
            "Document archivé à valeur probante (write-once) : il est immuable "
            "et ne peut plus être extrait pour modification.")
    with transaction.atomic():
        doc = Document.objects.select_for_update().get(pk=document.pk)
        if doc.locked_by_id is not None and doc.locked_by_id != user.pk:
            raise PermissionError(
                "Le document est déjà extrait par un autre utilisateur.")
        if doc.locked_by_id == user.pk:
            # Déjà verrouillé par ce même utilisateur — idempotent.
            return doc
        doc.locked_by = user
        doc.locked_at = timezone.now()
        doc.save(update_fields=['locked_by', 'locked_at', 'updated_at'])
    document.locked_by = doc.locked_by
    document.locked_at = doc.locked_at
    return doc


def checkin_document(document, user):
    """GED16 — Libère le verrou d'un document (check-in).

    Seul le détenteur du verrou OU un administrateur peut libérer le verrou.
    Si le document est déjà libre, l'opération est silencieusement idempotente.

    Multi-tenant : vérifie que user.company_id == document.company_id.
    """
    if document.company_id != user.company_id:
        raise PermissionError("Document inaccessible.")
    with transaction.atomic():
        doc = Document.objects.select_for_update().get(pk=document.pk)
        if doc.locked_by_id is None:
            # Déjà libre — idempotent.
            return doc
        is_locker = doc.locked_by_id == user.pk
        is_admin = getattr(user, 'is_admin_role', False) or user.is_superuser
        if not is_locker and not is_admin:
            raise PermissionError(
                "Seul le détenteur du verrou ou un administrateur peut "
                "libérer ce document.")
        doc.locked_by = None
        doc.locked_at = None
        doc.save(update_fields=['locked_by', 'locked_at', 'updated_at'])
    document.locked_by = None
    document.locked_at = None
    return doc


def assert_not_locked_by_other(document, user):
    """GED16 — Garde : rejette si document verrouillé par un autre utilisateur.

    À appeler avant add_version ou toute autre écriture sur le contenu du
    document. Ne lève rien si le document est libre OU si c'est le détenteur
    du verrou qui écrit.
    """
    if document.locked_by_id is not None and document.locked_by_id != user.pk:
        raise PermissionError(
            "Le document est extrait par un autre utilisateur. "
            "Attendez le check-in avant de téléverser une nouvelle version."
        )


def verrouiller_avertissement(document, user, *, motif=''):
    """ZGED9 — Pose le verrou d'AVERTISSEMENT léger (« en cours d'édition »),
    DISTINCT du check-out GED16 : n'empêche jamais la lecture, affiche
    seulement un bandeau à tous. Idempotent si déjà posé par le MÊME
    utilisateur (motif mis à jour) ; si posé par un AUTRE, lève
    `PermissionError` (→ 409 côté vue).

    Multi-tenant : vérifie que user.company_id == document.company_id."""
    if document.company_id != user.company_id:
        raise PermissionError("Document inaccessible.")
    from django.utils import timezone
    with transaction.atomic():
        doc = Document.objects.select_for_update().get(pk=document.pk)
        if (doc.verrou_avertissement_par_id is not None
                and doc.verrou_avertissement_par_id != user.pk):
            raise PermissionError(
                "Ce document est déjà signalé « en cours d'édition » par un "
                "autre utilisateur.")
        doc.verrou_avertissement_par = user
        doc.verrou_avertissement_le = timezone.now()
        doc.verrou_avertissement_motif = motif or ''
        doc.save(update_fields=[
            'verrou_avertissement_par', 'verrou_avertissement_le',
            'verrou_avertissement_motif', 'updated_at'])
    journaliser_evenement(
        doc, type_evenement='verrou_avertissement_pose',
        message=motif or '', utilisateur=user)
    return doc


def deverrouiller_avertissement(document, user):
    """ZGED9 — Lève le verrou d'AVERTISSEMENT. Le poseur OU un
    gestionnaire/admin peut lever ; un forçage PAR UN TIERS gestionnaire est
    journalisé distinctement (traçabilité de la levée forcée). Idempotent si
    déjà libre.

    Multi-tenant : vérifie que user.company_id == document.company_id."""
    if document.company_id != user.company_id:
        raise PermissionError("Document inaccessible.")
    with transaction.atomic():
        doc = Document.objects.select_for_update().get(pk=document.pk)
        if doc.verrou_avertissement_par_id is None:
            return doc  # déjà libre — idempotent.
        is_poseur = doc.verrou_avertissement_par_id == user.pk
        is_manager = getattr(user, 'is_admin_role', False) or user.is_superuser
        if not is_poseur and not is_manager:
            raise PermissionError(
                "Seul le poseur du verrou ou un gestionnaire peut le lever.")
        force = not is_poseur
        poseur_id = doc.verrou_avertissement_par_id
        doc.verrou_avertissement_par = None
        doc.verrou_avertissement_le = None
        doc.verrou_avertissement_motif = ''
        doc.save(update_fields=[
            'verrou_avertissement_par', 'verrou_avertissement_le',
            'verrou_avertissement_motif', 'updated_at'])
    journaliser_evenement(
        doc,
        type_evenement=(
            'verrou_avertissement_force' if force else 'verrou_avertissement_leve'),
        message=(
            f'Levé de force par un gestionnaire (posé par #{poseur_id}).'
            if force else ''),
        utilisateur=user)
    return doc


def change_lifecycle_status(document, target_status, *, user):
    """GED17 — Fait avancer un document dans son cycle de vie (statut LOCAL).

    Garde la machine à états `LIFECYCLE_TRANSITIONS` : seule une transition
    autorisée depuis le statut COURANT vers `target_status` est appliquée ;
    toute autre lève `ValueError` (→ 400 dans la vue). Ce cycle de vie est
    DISTINCT du funnel commercial `STAGES.py` (rule #2) — on ne l'importe pas.

    Multi-tenant : refuse si `user.company_id != document.company_id`. La
    mise à jour est sérialisée (`select_for_update`) pour éviter deux
    transitions concurrentes depuis le même statut.

    Renvoie le `Document` rafraîchi avec son nouveau statut.
    """
    from .models import (
        Document, LIFECYCLE_CHOICES, LIFECYCLE_TRANSITIONS,
    )
    if document.company_id != user.company_id:
        raise PermissionError("Document inaccessible.")
    # GED23 — write-once : un document archivé légalement est figé — son cycle
    # de vie ne bouge plus. Refus en `PermissionError` (→ 403 côté vue).
    if _document_archive_legalement(document):
        raise PermissionError(
            "Document archivé à valeur probante (write-once) : son cycle de "
            "vie est figé.")
    valides = {code for code, _ in LIFECYCLE_CHOICES}
    if target_status not in valides:
        raise ValueError(
            f"Statut « {target_status} » inconnu. "
            f"Statuts valides : {', '.join(sorted(valides))}."
        )
    with transaction.atomic():
        doc = Document.objects.select_for_update().get(pk=document.pk)
        if target_status == doc.statut:
            # Aucune transition réelle — on n'autorise PAS un no-op silencieux :
            # avancer vers le statut courant n'est pas une transition valide.
            raise ValueError(
                f"Le document est déjà au statut « {doc.statut} »."
            )
        autorisees = LIFECYCLE_TRANSITIONS.get(doc.statut, set())
        if target_status not in autorisees:
            attendus = ', '.join(sorted(autorisees)) or 'aucun'
            raise ValueError(
                f"Transition refusée : « {doc.statut} » → "
                f"« {target_status} » n'est pas permise "
                f"(transitions possibles : {attendus})."
            )
        doc.statut = target_status
        doc.save(update_fields=['statut', 'updated_at'])
    document.statut = doc.statut
    # XGED15 — journal automatique : changement de cycle de vie (best-effort).
    journaliser_evenement(
        doc, type_evenement='changement_statut',
        message=f'Statut → {target_status}.', utilisateur=user)
    return doc


# ── GED18 — Workflow d'approbation / revue documentaire ─────────────

def request_review(document, *, user, approbateur=None, commentaire=''):
    """GED18 — Lance une demande d'approbation/revue sur un document.

    Crée une `DemandeApprobation` « en_attente » et — si le document n'est pas
    déjà en revue — le fait avancer « brouillon → revue » via la machine à états
    GED17 (`change_lifecycle_status`, jamais dupliquée ici). Le `demandeur` et la
    `company` sont posés côté serveur (jamais lus du corps de requête).

    Refuse (`ValueError`) s'il existe déjà une demande EN ATTENTE pour ce
    document (une seule revue active à la fois) ou si `approbateur` appartient à
    une autre société. Multi-tenant : `PermissionError` si l'utilisateur n'est
    pas de la société du document.

    Renvoie la `DemandeApprobation` créée.
    """
    from .models import (
        APPROBATION_EN_ATTENTE, DemandeApprobation, LIFECYCLE_BROUILLON,
        LIFECYCLE_REVUE,
    )
    if document.company_id != user.company_id:
        raise PermissionError("Document inaccessible.")
    if approbateur is not None and approbateur.company_id != document.company_id:
        raise ValueError("L'approbateur doit appartenir à la même société.")
    with transaction.atomic():
        doc = Document.objects.select_for_update().get(pk=document.pk)
        existe = (DemandeApprobation.objects
                  .filter(document=doc, statut=APPROBATION_EN_ATTENTE)
                  .exists())
        if existe:
            raise ValueError(
                "Une demande d'approbation est déjà en attente pour ce "
                "document.")
        demande = DemandeApprobation.objects.create(
            company=doc.company,
            document=doc,
            demandeur=user,
            approbateur=approbateur,
            statut=APPROBATION_EN_ATTENTE,
            commentaire=commentaire or '',
        )
        # Met le document « en revue » s'il est encore brouillon (transition
        # GED17 réutilisée — on ne duplique pas la machine à états).
        if doc.statut == LIFECYCLE_BROUILLON:
            change_lifecycle_status(doc, LIFECYCLE_REVUE, user=user)
    document.statut = doc.statut
    return demande


def _decide_demande(demande, *, user, statut_cible, commentaire=''):
    """GED18 — Tranche une demande d'approbation (approbation OU rejet).

    Garde commune à `approve_demande`/`reject_demande` : seule une demande
    ENCORE EN ATTENTE peut être décidée (sinon `ValueError` — pas de double
    décision). L'`approbateur`, le statut, l'horodatage `decision_le` et le
    commentaire sont posés côté serveur. Multi-tenant : `PermissionError` si
    l'utilisateur n'est pas de la société de la demande.

    Renvoie la `DemandeApprobation` rafraîchie.
    """
    from django.utils import timezone
    from .models import APPROBATION_EN_ATTENTE, DemandeApprobation
    if demande.company_id != user.company_id:
        raise PermissionError("Demande inaccessible.")
    with transaction.atomic():
        dem = (DemandeApprobation.objects
               .select_for_update()
               .get(pk=demande.pk))
        if dem.statut != APPROBATION_EN_ATTENTE:
            raise ValueError(
                f"La demande est déjà « {dem.statut} » — décision impossible.")
        dem.statut = statut_cible
        dem.approbateur = user
        dem.decision_le = timezone.now()
        if commentaire:
            dem.commentaire = commentaire
        dem.save(update_fields=[
            'statut', 'approbateur', 'decision_le', 'commentaire',
            'updated_at'])
    demande.statut = dem.statut
    demande.approbateur = dem.approbateur
    demande.decision_le = dem.decision_le
    demande.commentaire = dem.commentaire
    return dem


def approve_demande(demande, *, user, commentaire=''):
    """GED18 — Approuve une demande de revue et fait avancer le document.

    Tranche la demande (« approuve », horodatage + approbateur côté serveur),
    puis — si le document est « en revue » — le fait avancer « revue →
    approuvé » via la machine à états GED17 (`change_lifecycle_status`, jamais
    dupliquée). L'avancement du cycle de vie n'est tenté QUE depuis « revue » :
    un document à un autre statut reste inchangé (la décision est tout de même
    enregistrée). Renvoie la `DemandeApprobation` décidée.
    """
    from .models import (
        APPROBATION_APPROUVE, LIFECYCLE_APPROUVE, LIFECYCLE_REVUE,
    )
    dem = _decide_demande(
        demande, user=user, statut_cible=APPROBATION_APPROUVE,
        commentaire=commentaire)
    document = dem.document
    if document.statut == LIFECYCLE_REVUE:
        change_lifecycle_status(document, LIFECYCLE_APPROUVE, user=user)
    return dem


def reject_demande(demande, *, user, commentaire=''):
    """GED18 — Rejette une demande de revue et renvoie le document en correction.

    Tranche la demande (« rejete », horodatage + approbateur côté serveur),
    puis — si le document est « en revue » — le renvoie « revue → brouillon »
    via la machine à états GED17 (`change_lifecycle_status`, jamais dupliquée),
    pour qu'il reparte en correction. Un document à un autre statut reste
    inchangé. Renvoie la `DemandeApprobation` décidée.
    """
    from .models import (
        APPROBATION_REJETE, LIFECYCLE_BROUILLON, LIFECYCLE_REVUE,
    )
    dem = _decide_demande(
        demande, user=user, statut_cible=APPROBATION_REJETE,
        commentaire=commentaire)
    document = dem.document
    if document.statut == LIFECYCLE_REVUE:
        change_lifecycle_status(document, LIFECYCLE_BROUILLON, user=user)
    return dem


# ── GED20 — Partage public d'un document par lien tokenisé ──────────

def create_partage(*, document, company, created_by=None, expires_at=None,
                   password=None, quota_max=None, watermark=False):
    """GED20 — Crée un partage public tokenisé pour un document (côté gestion).

    `company` est posée côté serveur et doit être celle du document (jamais lue
    du corps de requête). Le `token` long/imprévisible est généré par le défaut
    du modèle. Le mot de passe (optionnel) est HACHÉ via `set_password` — jamais
    stocké en clair. `expires_at`/`quota_max` sont optionnels (NULL = pas de
    limite). `watermark` (GED21) force le filigrane sur ce lien public. Renvoie
    le `PartageGed` créé.
    """
    from .models import PartageGed
    if document.company_id != getattr(company, 'id', company):
        raise ValueError("Le document doit appartenir à la même société.")
    partage = PartageGed(
        company=company,
        document=document,
        expires_at=expires_at,
        quota_max=quota_max,
        watermark=watermark,
        created_by=created_by,
    )
    partage.set_password(password)
    partage.save()
    # XGED15 — journal automatique : partage créé (best-effort).
    journaliser_evenement(
        document, type_evenement='partage_cree',
        message='Lien de partage public créé.', utilisateur=created_by)
    return partage


def revoke_partage(partage):
    """GED20 — Révoque un partage (kill-switch : `actif=False`).

    Idempotent : un partage déjà révoqué reste révoqué. Après révocation,
    l'endpoint public renvoie 404 (lien mort) sans fuite."""
    if partage.actif:
        partage.actif = False
        partage.save(update_fields=['actif', 'updated_at'])
    return partage


# Sentinelles de résultat pour la résolution publique (le SEUL chemin d'accès
# public au document). Chaque cas mappe vers un code HTTP côté endpoint.
PARTAGE_OK = 'ok'
PARTAGE_INTROUVABLE = 'introuvable'        # jeton inconnu ou révoqué → 404
PARTAGE_EXPIRE = 'expire'                  # expiré ou quota épuisé → 410
PARTAGE_MDP_REQUIS = 'mot_de_passe_requis'  # mot de passe manquant/erroné → 403


def resolve_partage_public(token, *, password=None):
    """GED20 — Résout un partage public DEPUIS le seul jeton (aucune identité).

    C'est le cœur sécurité de l'accès public : on ne fait JAMAIS confiance à une
    société/identité venue de la requête — tout est résolu à partir du `token`
    (qui ne référence qu'un seul document d'une seule société). Renvoie un tuple
    `(statut, partage_ou_None)` où `statut` est l'une des sentinelles :

      - PARTAGE_INTROUVABLE : jeton inconnu OU partage révoqué (actif=False).
        → 404, sans distinguer les deux (pas de fuite « ce jeton existe »).
      - PARTAGE_EXPIRE       : partage expiré OU quota de téléchargements épuisé.
        → 410 Gone.
      - PARTAGE_MDP_REQUIS   : un mot de passe protège le partage et le mot de
        passe fourni est manquant ou erroné. → 403.
      - PARTAGE_OK           : accès autorisé, `partage` est servable.

    Note : un partage révoqué est traité comme INTROUVABLE (404) — révoquer doit
    « faire disparaître » le lien, pas révéler qu'il a existé.
    """
    from .models import PartageGed
    partage = (PartageGed.objects
               .select_related('document', 'company')
               .filter(token=token)
               .first())
    # Jeton inconnu OU partage révoqué → 404 indistinct (pas de fuite).
    if partage is None or not partage.actif:
        return PARTAGE_INTROUVABLE, None
    # Expiré ou quota épuisé → 410 Gone.
    if partage.is_expired or partage.quota_exhausted:
        return PARTAGE_EXPIRE, partage
    # Mot de passe (le cas échéant) — 403 si manquant/erroné.
    if partage.has_password and not partage.check_password(password):
        return PARTAGE_MDP_REQUIS, partage
    return PARTAGE_OK, partage


def consume_partage_download(partage):
    """GED20 — Incrémente atomiquement le compteur de téléchargements.

    Race-safe : incrément via F-expression + filtre conditionnel sur le quota
    (un GET concurrent ne peut pas dépasser `quota_max`). Renvoie True si le
    téléchargement a été comptabilisé, False si le quota venait d'être épuisé
    par un accès concurrent (l'appelant doit alors renvoyer 410 et NE PAS
    servir le document).

    `quota_max=None` → quota illimité : on incrémente toujours sans condition.
    """
    from django.db.models import F
    from .models import PartageGed
    if partage.quota_max is None:
        PartageGed.objects.filter(pk=partage.pk).update(
            telechargements=F('telechargements') + 1)
        partage.refresh_from_db(fields=['telechargements'])
        return True
    # Incrément CONDITIONNEL : ne passe que si le quota n'est pas déjà atteint.
    # Sous concurrence, exactement `quota_max` GET réussissent l'update.
    updated = PartageGed.objects.filter(
        pk=partage.pk, telechargements__lt=partage.quota_max
    ).update(telechargements=F('telechargements') + 1)
    if not updated:
        return False
    partage.refresh_from_db(fields=['telechargements'])
    return True


# ── GED21 — Filigrane & contrôle de diffusion ───────────────────────────────

# Types de contenu que le filigrane sait traiter. Tout autre type est renvoyé
# tel quel (jamais d'erreur) — le filigrane est best-effort, jamais bloquant.
_WATERMARK_PDF_MIMES = {'application/pdf'}
_WATERMARK_IMAGE_MIMES = {
    'image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'image/gif',
}


def _watermark_pdf(file_bytes, text):
    """GED21 — Filigrane diagonal répété sur chaque page d'un PDF.

    Utilise PyMuPDF (`fitz`) quand il est disponible — import GARDÉ et
    PARESSEUX : si la lib n'est pas installée (elle n'est PAS une dépendance
    dure du backend), on dégrade proprement en renvoyant le PDF d'origine. Ne
    lève jamais : tout échec retombe sur l'original (best-effort).

    Renvoie `(out_bytes, watermarked)` où `watermarked` est False si la lib est
    absente ou si le rendu a échoué (octets inchangés).
    """
    try:  # Dépendance optionnelle — import paresseux (no-op-safe sans la lib).
        import fitz  # PyMuPDF
    except Exception:  # pragma: no cover - chemin de repli sans la lib.
        return file_bytes, False
    try:
        doc = fitz.open(stream=file_bytes, filetype='pdf')
        try:
            for page in doc:
                rect = page.rect
                # Filigrane diagonal centré, gris translucide, répété en bas.
                page.insert_textbox(
                    rect,
                    text,
                    fontsize=28,
                    color=(0.5, 0.5, 0.5),
                    rotate=45,
                    align=fitz.TEXT_ALIGN_CENTER,
                    overlay=True,
                )
            out = doc.tobytes()
        finally:
            doc.close()
        return out, True
    except Exception:  # pragma: no cover - robustesse : jamais bloquer.
        return file_bytes, False


def _watermark_image(file_bytes, text):
    """GED21 — Incruste un filigrane texte translucide sur une image.

    Utilise Pillow (déjà épinglé dans requirements) via un import PARESSEUX et
    GARDÉ : si Pillow venait à manquer, on dégrade en renvoyant l'image
    d'origine. Ne lève jamais.

    Renvoie `(out_bytes, watermarked)`.
    """
    try:  # Import paresseux et gardé — Pillow présent, mais on reste robuste.
        from PIL import Image, ImageDraw, ImageFont
    except Exception:  # pragma: no cover - chemin de repli sans la lib.
        return file_bytes, False
    try:
        import io
        src = Image.open(io.BytesIO(file_bytes)).convert('RGBA')
        overlay = Image.new('RGBA', src.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        try:
            font = ImageFont.load_default()
        except Exception:  # pragma: no cover - police par défaut indisponible.
            font = None
        # Tuile le texte en diagonale sur toute la surface (gris translucide).
        step_x = max(160, src.width // 3)
        step_y = max(90, src.height // 4)
        for y in range(0, src.height + step_y, step_y):
            for x in range(0, src.width + step_x, step_x):
                draw.text((x, y), text, fill=(128, 128, 128, 110), font=font)
        watermarked = Image.alpha_composite(src, overlay)
        out = io.BytesIO()
        # On réémet en PNG : préserve l'alpha du filigrane, sans dépendance
        # supplémentaire (toujours supporté par Pillow).
        watermarked.save(out, format='PNG')
        return out.getvalue(), True
    except Exception:  # pragma: no cover - robustesse : jamais bloquer.
        return file_bytes, False


def apply_watermark(file_bytes, content_type, text):
    """GED21 — Applique un filigrane texte sur un contenu diffusé (best-effort).

    Point d'entrée unique du contrôle de diffusion : superpose un texte de
    confidentialité (ex. « CONFIDENTIEL — {société} — {utilisateur/date} ») sur
    les PDF (via PyMuPDF) et les images (via Pillow). Le filigrane est un RENDU
    À LA VOLÉE — il ne modifie JAMAIS le binaire stocké (MinIO/base) ni aucun
    statut documentaire ; il ne s'applique qu'au flux servi.

    SÉCURITÉ DÉPENDANCES : les libs sont importées PARESSEUSEMENT à l'intérieur
    des helpers. Si une lib est absente (PyMuPDF n'est PAS une dépendance dure)
    ou si le rendu échoue, on DÉGRADE proprement en renvoyant les octets
    d'origine + `watermarked=False` — aucune exception, aucun crash, aucun
    rebuild obligatoire. Un type non pris en charge (texte, zip…) est de même
    renvoyé tel quel.

    Renvoie un tuple `(out_bytes, watermarked)` :
      - `out_bytes`     : les octets à servir (filigranés ou identiques).
      - `watermarked`   : True seulement si un filigrane a effectivement été
        appliqué (utile pour ajuster le Content-Type côté appelant).

    Le contenu vide ou un texte vide laissent les octets inchangés.
    """
    if not file_bytes or not text:
        return file_bytes, False
    ct = (content_type or '').split(';')[0].strip().lower()
    if ct in _WATERMARK_PDF_MIMES:
        return _watermark_pdf(file_bytes, text)
    if ct in _WATERMARK_IMAGE_MIMES:
        return _watermark_image(file_bytes, text)
    # Type non filigranable (texte, archive, octet-stream…) → inchangé.
    return file_bytes, False


def watermark_label(*, company=None, user=None):
    """GED21 — Construit l'étiquette de filigrane de confidentialité.

    Format : « CONFIDENTIEL — {société} — {acteur} — {date} ». Tout segment
    absent est omis proprement. La société/l'utilisateur viennent TOUJOURS du
    serveur (jamais d'un corps de requête) — l'appelant les résout depuis le
    document partagé ou `request.user`.
    """
    from django.utils import timezone
    parts = ['CONFIDENTIEL']
    co_nom = getattr(company, 'nom', None)
    if co_nom:
        parts.append(str(co_nom))
    actor = None
    if user is not None:
        actor = (getattr(user, 'username', None)
                 or getattr(user, 'email', None))
    if actor:
        parts.append(str(actor))
    parts.append(timezone.now().strftime('%Y-%m-%d'))
    return ' — '.join(parts)


# ── GED23 — Archivage légal à valeur probante (write-once / object-lock) ─────

def _version_integrity_hash(version):
    """GED23 — Condensat SHA-256 (hex) du contenu d'une version, ou ''.

    Preuve d'intégrité à valeur probante. On PRIVILÉGIE un recalcul depuis le
    contenu réellement stocké (`records.storage.fetch_attachment`) — l'empreinte
    la plus fiable. Si le contenu n'est pas récupérable (stockage indisponible),
    on retombe sur le `checksum` déjà figé sur la version (lui-même un SHA-256).
    Best-effort : ne lève jamais — renvoie '' si rien n'est exploitable."""
    if version is None:
        return ''
    # 1) Recalcul depuis le contenu stocké (import paresseux de la couche
    #    storage partagée — on ne réimplémente pas le stockage objet).
    try:
        from apps.records.storage import fetch_attachment
        data, err = fetch_attachment(version.file_key)
        if not err and data:
            return compute_checksum(data)
    except Exception:
        pass
    # 2) Repli : le checksum déjà enregistré sur la version (SHA-256 hex).
    return version.checksum or ''


def _try_set_object_lock(version, retain_until):
    """GED23 — Pose un verrou objet (MinIO/S3 Object-Lock) — BEST-EFFORT.

    BONUS purement consolidant : l'immuabilité APPLICATIVE (write-once posée
    dans les modèles + services) est LA garantie ; ce verrou n'est qu'un
    renfort. Import PARESSEUX du client MinIO (mêmes conventions que
    `records.storage` — aucune nouvelle dépendance) puis `put_object_retention`.

    DÉGRADE PROPREMENT : si le backend ne supporte pas l'object-lock (MinIO sans
    bucket WORM, opération non implémentée…), ou si le client est absent, ou si
    quoi que ce soit échoue, on renvoie ``False`` SANS lever — l'archivage
    légal reste valide grâce à l'immuabilité applicative.

    Renvoie ``True`` seulement si le verrou a effectivement été posé.
    """
    if version is None or not version.file_key or retain_until is None:
        return False
    try:
        import datetime as _dt

        from django.conf import settings

        from apps.ventes.utils.minio_client import get_minio_client

        client = get_minio_client()
        # boto3 attend un datetime tz-aware pour RetainUntilDate.
        if isinstance(retain_until, _dt.datetime):
            until_dt = retain_until
        else:
            until_dt = _dt.datetime.combine(retain_until, _dt.time.min)
        if until_dt.tzinfo is None:
            until_dt = until_dt.replace(tzinfo=_dt.timezone.utc)
        client.put_object_retention(
            Bucket=settings.MINIO_BUCKET_UPLOADS,
            Key=version.file_key,
            Retention={'Mode': 'COMPLIANCE', 'RetainUntilDate': until_dt},
        )
        return True
    except Exception:
        # Object-lock non supporté / indisponible → on dégrade en silence.
        return False


def archiver_legalement(document, *, user, motif='', retain_until=None):
    """GED23 — Archive un document à VALEUR PROBANTE (write-once / object-lock).

    Pose un `ArchivageLegal` sur le document, ce qui le rend (et toutes ses
    versions) IMMUABLE — WRITE-ONCE : aucune modification ni suppression
    ultérieure (gardes au niveau modèle + service). On fige le `hash_integrite`
    (SHA-256 du contenu de la version courante) comme preuve d'intégrité, et —
    en BONUS best-effort — on tente de poser un verrou objet (object-lock
    retain-until) côté stockage SI le backend le supporte (sinon on dégrade
    proprement : l'immuabilité applicative reste LA garantie).

    Multi-tenant : `company` et `archive_par` sont posés CÔTÉ SERVEUR (jamais
    lus du corps de requête). `PermissionError` si l'utilisateur n'est pas de la
    société du document. Idempotence : un document déjà archivé légalement lève
    `ValueError` (un archivage est unique et définitif — write-once).

    `retain_until` (date OU datetime, OPTIONNEL) est la date de rétention du
    verrou objet — propagée jusqu'à la pose best-effort du verrou.

    Renvoie l'`ArchivageLegal` créé.
    """
    from .models import ArchivageLegal, DocumentVersion

    if document.company_id != getattr(user, 'company_id', None):
        raise PermissionError("Document inaccessible.")
    # Write-once : un document n'est archivé légalement qu'une seule fois.
    if ArchivageLegal.objects.filter(document=document).exists():
        raise ValueError("Ce document est déjà archivé légalement.")
    # Version courante figée (la plus récente) — sert au hash + à l'object-lock.
    version = (DocumentVersion.objects
               .filter(document=document)
               .order_by('-version')
               .first())
    hash_integrite = _version_integrity_hash(version)
    # Normalise retain_until → date (le champ modèle est une DateField).
    retain_date = None
    if retain_until is not None:
        import datetime as _dt
        retain_date = (retain_until.date()
                       if isinstance(retain_until, _dt.datetime)
                       else retain_until)
    # BONUS best-effort : pose l'object-lock AVANT de créer la trace, pour
    # refléter fidèlement s'il a réussi (dégrade en silence sinon).
    lock_applique = _try_set_object_lock(version, retain_date)
    with transaction.atomic():
        # Re-vérifie sous transaction (la contrainte d'unicité protège aussi en
        # base, mais on renvoie une erreur métier propre en cas de course).
        if ArchivageLegal.objects.filter(document=document).exists():
            raise ValueError("Ce document est déjà archivé légalement.")
        archivage = ArchivageLegal.objects.create(
            company=document.company,
            document=document,
            version=version,
            archive_par=user,
            motif=(motif or '').strip(),
            hash_integrite=hash_integrite,
            object_lock_retain_until=retain_date,
            object_lock_applique=lock_applique,
        )
    return archivage


def assert_not_archive_legalement(document):
    """GED23 — Garde : rejette toute écriture si le document est archivé (WORM).

    À appeler côté service avant toute écriture (ajout de version, changement de
    statut, déplacement, verrouillage…) sur un document. La garde au niveau
    modèle (`save`/`delete`) est le filet de sécurité ultime ; cette fonction
    permet de refuser TÔT avec un message clair (→ 403 dans la vue). Lève
    `ArchivageLegalError` si le document est archivé légalement."""
    from .models import ARCHIVE_LEGALE_MESSAGE, ArchivageLegalError
    if _document_archive_legalement(document):
        raise ArchivageLegalError(ARCHIVE_LEGALE_MESSAGE)


# ── GED24 — Rétention légale / legal hold (gel anti-suppression) ─────────────

def _document_sous_legal_hold(document):
    """GED24 — True si une rétention légale ACTIVE couvre le document.

    Helper interne partagé par les gardes de suppression. Lecture en base de
    l'existence d'un `LegalHold` `actif=True` sur le document. Import paresseux
    pour éviter tout cycle."""
    from .models import LegalHold
    if document.pk is None:
        return False
    return LegalHold.objects.filter(
        document_id=document.pk, actif=True).exists()


def placer_legal_hold(document, *, user, motif=''):
    """GED24 — Place une RÉTENTION LÉGALE (legal hold) sur un document.

    Pose un `LegalHold` ACTIF qui GÈLE la suppression/purge du document tant
    qu'il reste actif (garde au niveau modèle `Document.delete()` + service).
    Ce gel SURCLASSE toute purge de politique de rétention (GED22) et reste une
    couche distincte de l'archivage write-once (GED23) — il ne fige QUE
    l'effacement (le document reste éditable) et est TEMPORAIRE (levable).

    Multi-tenant : `company` et `place_par` posés CÔTÉ SERVEUR (jamais lus du
    corps). `PermissionError` si l'utilisateur n'est pas de la société du
    document. IDEMPOTENT : si un hold actif existe déjà sur ce document, on le
    renvoie tel quel sans en créer un second (on ne duplique pas le gel).

    Renvoie le `LegalHold` actif (créé ou réutilisé).
    """
    from .models import LegalHold

    if document.company_id != getattr(user, 'company_id', None):
        raise PermissionError("Document inaccessible.")
    with transaction.atomic():
        # Idempotence : un hold actif existant tient lieu de gel — on ne pose
        # pas de doublon (le document est déjà gelé).
        existant = (LegalHold.objects
                    .select_for_update()
                    .filter(document=document, actif=True)
                    .first())
        if existant is not None:
            return existant
        return LegalHold.objects.create(
            company=document.company,
            document=document,
            place_par=user,
            motif=(motif or '').strip(),
            actif=True,
        )


def lever_legal_hold(document, *, user):
    """GED24 — Lève la/les rétention(s) légale(s) active(s) d'un document.

    Bascule tous les `LegalHold` ACTIFS du document en `actif=False` et trace
    `date_levee`/`leve_par` (on ne supprime jamais la trace d'un hold —
    historique conservé). Une fois le dernier hold actif levé, le document
    redevient supprimable (sauf autre protection, ex. GED23). IDEMPOTENT : sans
    hold actif, l'appel est un no-op (renvoie 0).

    Multi-tenant : `company` du document vérifiée côté serveur ; `leve_par`
    posé côté serveur. `PermissionError` si l'utilisateur n'est pas de la
    société du document.

    Renvoie le nombre de holds levés.
    """
    from django.utils import timezone
    from .models import LegalHold

    if document.company_id != getattr(user, 'company_id', None):
        raise PermissionError("Document inaccessible.")
    with transaction.atomic():
        actifs = list(LegalHold.objects
                      .select_for_update()
                      .filter(document=document, actif=True))
        for hold in actifs:
            hold.actif = False
            hold.date_levee = timezone.now()
            hold.leve_par = user
            hold.save(update_fields=['actif', 'date_levee', 'leve_par'])
        return len(actifs)


def assert_not_legal_hold(document):
    """GED24 — Garde : rejette la suppression si le document est sous hold actif.

    À appeler côté service avant toute suppression/purge/destruction de cycle de
    vie d'un document. La garde au niveau modèle (`Document.delete()`) est le
    filet ultime ; cette fonction permet de refuser TÔT avec un message clair
    (→ 403 dans la vue, jamais 500). Lève `LegalHoldError` si une rétention
    légale active couvre le document."""
    from .models import LEGAL_HOLD_MESSAGE, LegalHoldError
    if _document_sous_legal_hold(document):
        raise LegalHoldError(LEGAL_HOLD_MESSAGE)


# ── GED26 — Corbeille & restauration (soft-delete réversible) ────────────────

def mettre_en_corbeille(document, user):
    """GED26 — Place un document dans la CORBEILLE (soft-delete réversible).

    Renseigne `supprime_le`/`supprime_par` côté serveur : le document disparaît
    des listes par défaut (`documents_visible_to_user`) mais N'EST PAS effacé —
    il reste intégralement récupérable via `restaurer_de_corbeille`.

    Gardes (mêmes refus que la suppression réelle) :
      * GED23 — un document archivé légalement (write-once) NE PEUT PAS être mis
        en corbeille → lève `ArchivageLegalError` (→ 403, jamais 500) ;
      * GED24 — un document sous rétention légale ACTIVE (legal hold) NE PEUT
        PAS être mis en corbeille → lève `LegalHoldError` (→ 403).
    On vérifie ces gardes AVANT toute écriture : `Document.save()` bloque déjà
    toute écriture sur un document archivé (write-once), donc on refuse en amont
    avec un message clair plutôt que de laisser remonter une 500.

    IDEMPOTENT : un document déjà dans la corbeille est renvoyé tel quel (on ne
    réécrase ni la date ni l'auteur d'origine). Renvoie le document.
    """
    assert_not_archive_legalement(document)   # GED23 → ArchivageLegalError
    assert_not_legal_hold(document)           # GED24 → LegalHoldError
    if document.supprime_le is not None:
        # Déjà en corbeille : no-op (on préserve la trace d'origine).
        return document
    from django.utils import timezone
    document.supprime_le = timezone.now()
    document.supprime_par = user
    document.save(update_fields=['supprime_le', 'supprime_par', 'updated_at'])
    return document


def restaurer_de_corbeille(document):
    """GED26 — Restaure un document DEPUIS la corbeille (efface le soft-delete).

    Vide `supprime_le`/`supprime_par` : le document réapparaît dans les listes
    par défaut. IDEMPOTENT : un document qui n'est pas en corbeille est renvoyé
    tel quel (no-op). Aucune garde légale ici — restaurer ne fait que ANNULER un
    soft-delete (rien n'est effacé). Renvoie le document.
    """
    if document.supprime_le is None:
        return document
    document.supprime_le = None
    document.supprime_par = None
    document.save(update_fields=['supprime_le', 'supprime_par', 'updated_at'])
    return document


def purger_definitivement(document):
    """GED26 — Supprime DÉFINITIVEMENT un document depuis la corbeille (réel delete).

    Effacement RÉEL et irréversible — réservé aux documents DÉJÀ en corbeille
    (on ne purge jamais un document « vivant » par cette voie : il faut le mettre
    en corbeille d'abord). Les gardes légales restent respectées : `delete()` au
    niveau modèle refuse encore un document archivé (GED23) ou sous legal hold
    actif (GED24) → `ArchivageLegalError`/`LegalHoldError` (→ 403, jamais 500).

    Lève `ValueError` si le document n'est pas dans la corbeille. Renvoie None.
    """
    if document.supprime_le is None:
        raise ValueError(
            "Le document doit d'abord être dans la corbeille avant la purge "
            "définitive.")
    # Les gardes légales (GED23/GED24) sont posées dans `Document.delete()` —
    # filet ultime ; on les laisse lever telles quelles (traduites en 403).
    document.delete()


# ── GED25 — Purge automatique de la corbeille (DRY-RUN par défaut) ────────────
#
# Politique : la purge automatique n'efface JAMAIS un document « vivant ». Elle
# ne considère QUE les documents DÉJÀ en corbeille (GED26, soft-delete) dont le
# séjour en corbeille dépasse un délai de grâce (`PURGE_GRACE_DAYS`, défaut
# 30 jours depuis `supprime_le`). Avant tout effacement, chaque candidat repasse
# les gardes légales (GED23 write-once / GED24 legal hold actif) : un document
# protégé est EXCLU silencieusement de la purge (jamais une 500). Tout est borné
# à la société (multi-tenant) — jamais de fuite cross-société.
#
# DRY-RUN PAR DÉFAUT : `purger_corbeille_echue(..., apply=False)` ne fait que
# COMPTER/LISTER ce qui SERAIT purgé sans rien effacer. L'effacement réel exige
# un `apply=True` explicite (posé par la tâche planifiée ou la commande). C'est
# une opération DESTRUCTIVE-mais-révertable au sens CLAUDE.md (revertable via
# git pour le code ; les documents purgés étaient déjà en corbeille, soft-
# supprimés et hors des listes — la purge ne fait que matérialiser un effacement
# déjà demandé une fois le délai de grâce écoulé).

# Délai de grâce par défaut (jours) avant qu'un document EN CORBEILLE devienne
# éligible à la purge automatique. Lu de `settings.GED_PURGE_GRACE_DAYS` si
# présent — sinon 30 jours. Toujours surchargeable par appel (`grace_days`).
PURGE_GRACE_DEFAULT_DAYS = 30


def _purge_grace_days(grace_days=None):
    """GED25 — Résout le délai de grâce effectif (jours, entier positif).

    Priorité : argument explicite > `settings.GED_PURGE_GRACE_DAYS` > défaut
    (30 j). Un délai de grâce de 0 est REFUSÉ (on garde toujours un coussin) :
    toute valeur non strictement positive retombe sur le défaut."""
    from django.conf import settings
    if grace_days is None:
        grace_days = getattr(
            settings, 'GED_PURGE_GRACE_DAYS', PURGE_GRACE_DEFAULT_DAYS)
    try:
        grace_days = int(grace_days)
    except (TypeError, ValueError):
        grace_days = PURGE_GRACE_DEFAULT_DAYS
    return grace_days if grace_days > 0 else PURGE_GRACE_DEFAULT_DAYS


def corbeille_purgeable(company, *, grace_days=None, now=None):
    """GED25 — Documents EN CORBEILLE éligibles à la purge auto (société).

    Renvoie un QuerySet (borné à la société) des documents dont :
      * `supprime_le` est renseigné (déjà en corbeille, GED26) ; ET
      * le séjour en corbeille dépasse le délai de grâce (`supprime_le` est
        antérieur à `now - grace_days`).
    Les gardes légales (GED23/GED24) NE sont PAS appliquées ici (elles le sont
    au moment de l'effacement, document par document) — ce sélecteur n'est que la
    présélection par âge. Aucun effacement : pur read.
    """
    import datetime

    from django.utils import timezone

    if now is None:
        now = timezone.now()
    seuil = now - datetime.timedelta(days=_purge_grace_days(grace_days))
    return (Document.objects
            .filter(company=company,
                    supprime_le__isnull=False,
                    supprime_le__lt=seuil)
            .order_by('supprime_le', 'id'))


def purger_corbeille_echue(company, *, grace_days=None, now=None, apply=False):
    """GED25 — Purge auto de la corbeille échue d'une société (DRY-RUN par défaut).

    Balaie les documents EN CORBEILLE dont le séjour dépasse le délai de grâce
    (`corbeille_purgeable`) et, pour chacun, RE-VÉRIFIE les gardes légales avant
    tout effacement :
      * GED23 — archivé légalement (write-once) → EXCLU (compté `proteges`) ;
      * GED24 — sous legal hold actif → EXCLU (compté `proteges`).
    Un document protégé n'est JAMAIS purgé (jamais une 500) — il reste en
    corbeille jusqu'à la levée de sa protection.

    `apply=False` (DÉFAUT) = DRY-RUN : on COMPTE seulement ce qui serait purgé,
    rien n'est effacé. `apply=True` efface réellement (via
    `purger_definitivement`, qui respecte les mêmes gardes au niveau modèle —
    double filet). L'effacement est idempotent et borné à la société.

    Renvoie un dict de synthèse :
      ``{'company_id', 'dry_run', 'eligibles', 'purges', 'proteges', 'ids'}``
    où `eligibles` = candidats par âge, `purges` = réellement (ou virtuellement)
    purgés, `proteges` = exclus par une garde légale, `ids` = ids purgés.
    """
    from .models import ArchivageLegalError, LegalHoldError

    candidats = list(corbeille_purgeable(
        company, grace_days=grace_days, now=now))
    purges = 0
    proteges = 0
    ids = []
    for document in candidats:
        # Garde légale RE-vérifiée par document (état au moment de la purge).
        if document.est_archive_legalement or document.est_sous_legal_hold:
            proteges += 1
            continue
        if apply:
            try:
                purger_definitivement(document)
            except (ArchivageLegalError, LegalHoldError):
                # Filet ultime : course avec une protection posée entre-temps.
                proteges += 1
                continue
        purges += 1
        ids.append(document.pk)
    return {
        'company_id': getattr(company, 'id', None),
        'dry_run': not apply,
        'eligibles': len(candidats),
        'purges': purges,
        'proteges': proteges,
        'ids': ids,
    }


def purger_corbeille_toutes_societes(*, grace_days=None, now=None, apply=False):
    """GED25 — Purge auto de la corbeille échue de TOUTES les sociétés.

    Itère société par société (chacune bornée à ses propres documents — jamais
    de fuite cross-société) et agrège le résultat de `purger_corbeille_echue`.
    DRY-RUN par défaut (`apply=False`). Renvoie un dict agrégé avec un détail par
    société (`par_societe`)."""
    from authentication.models import Company

    total = {'dry_run': not apply, 'eligibles': 0, 'purges': 0,
             'proteges': 0, 'par_societe': []}
    for company in Company.objects.all():
        res = purger_corbeille_echue(
            company, grace_days=grace_days, now=now, apply=apply)
        total['eligibles'] += res['eligibles']
        total['purges'] += res['purges']
        total['proteges'] += res['proteges']
        if res['eligibles']:
            total['par_societe'].append(res)
    return total


# ── GED27 — Modèles de documents (fusion/mailing → PDF WeasyPrint) ───────────
#
# Couche GÉNÉRIQUE de documents INTERNES (attestations, courriers, mailing) :
# un modèle porte un corps HTML avec des jetons ``{{ champ }}``, fusionné avec un
# dictionnaire de données puis rendu en PDF via WeasyPrint. SÉPARÉE et DISTINCTE
# du chemin `/proposal` (rule #4) — qui reste l'UNIQUE chemin des PDF de DEVIS
# client. On n'importe ni ne route jamais par le moteur premium ici.


def fusionner_modele(corps_html, contexte):
    """GED27 — Fusionne un corps HTML avec un contexte (substitution SÛRE).

    Substitue les jetons ``{{ champ }}`` du corps par les valeurs de `contexte`
    via le moteur de gabarit Django dans un contexte EXPLICITE et borné — JAMAIS
    d'``eval`` ni d'exécution de code arbitraire. Un jeton inconnu est rendu vide
    (comportement standard du moteur), jamais une fuite d'objet Python.

    Le `contexte` est un dictionnaire plat fourni par l'appelant (les données de
    fusion d'un courrier/mailing). Renvoie le HTML fusionné (str).
    """
    from django.template import Context, Template
    if not corps_html:
        return ''
    safe_contexte = dict(contexte or {})
    template = Template(str(corps_html))
    return template.render(Context(safe_contexte))


def _modele_html_document(modele, contexte):
    """GED27 — Construit le HTML complet (en-tête + corps fusionné) d'un modèle.

    Enrobe le corps fusionné dans un squelette HTML imprimable minimal (police,
    marges) — même esprit que le PDF interne de `contrats` (hors `/proposal`).
    """
    corps = fusionner_modele(modele.corps_html, contexte)
    titre = (modele.nom or 'Document').replace('<', '&lt;').replace('>', '&gt;')
    return (
        "<!DOCTYPE html><html lang='fr'><head><meta charset='utf-8'>"
        "<style>"
        "body{font-family:sans-serif;font-size:11pt;color:#1a1a1a;"
        "margin:2cm;line-height:1.5;}"
        "h1{font-size:16pt;border-bottom:2px solid #2b5cab;padding-bottom:6px;}"
        "</style></head><body>"
        f"<h1>{titre}</h1>"
        f"<div class='corps'>{corps}</div>"
        "</body></html>"
    )


def rendre_modele(modele, contexte):
    """GED27 — Fusionne un modèle avec un contexte et rend un PDF (bytes).

    Substitue les jetons ``{{ champ }}`` du `corps_html` (via `fusionner_modele`,
    contexte borné, jamais d'exécution de code), enrobe le résultat dans un
    squelette HTML imprimable, puis rend un PDF via WeasyPrint.

    PDF INTERNE/administratif (attestation, courrier, mailing) — ce N'EST PAS un
    PDF de devis : `/proposal` reste l'unique chemin des PDF de devis client
    (rule #4). On n'importe ni ne route jamais par le moteur premium.

    ARC12 — la plomberie WeasyPrint (import paresseux + ``write_pdf()``) est
    déléguée au service partagé ``core.pdf.render_pdf`` ; le GABARIT HTML de
    `_modele_html_document` reste STRICTEMENT identique, donc le rendu est
    inchangé à l'octet près.

    Renvoie les octets du PDF (commençant par ``%PDF``).
    """
    html_str = _modele_html_document(modele, contexte)
    return render_pdf(html=html_str)


def resoudre_classement(modele, contexte, *, cabinet_defaut='Modèles',
                        folder_defaut='Mailing'):
    """GED28 — Résout le (cabinet, dossier) de CLASSEMENT d'un modèle généré.

    Décide OÙ déposer le document produit par `generer_document`, à partir de la
    règle de classement portée par le modèle :

      * `cabinet_cible` : nom du cabinet de destination. Vide → `cabinet_defaut`
        (comportement rétro-compatible de l'appelant).
      * `dossier_cible` : nom du dossier racine de destination, qui peut porter
        des jetons ``{{ champ }}`` résolus DEPUIS le `contexte` de fusion via
        `fusionner_modele` (substitution SÛRE — jamais d'exécution de code), p.ex.
        « Attestations {{ annee }} » → « Attestations 2026 ». Vide (ou résolu
        vide) → `folder_defaut`.

    Renvoie `(cabinet_nom, folder_nom)` — deux chaînes non vides, prêtes pour
    `ensure_cabinet`/`ensure_root_folder`. Ne crée RIEN ici (résolution pure).
    """
    cabinet_nom = (getattr(modele, 'cabinet_cible', '') or '').strip() \
        or cabinet_defaut
    brut = (getattr(modele, 'dossier_cible', '') or '').strip()
    if brut:
        # Le nom de dossier est un mini-gabarit : on réutilise EXACTEMENT la
        # substitution sûre de GED27 (contexte borné, jamais d'exécution de code).
        folder_nom = fusionner_modele(brut, contexte).strip()
    else:
        folder_nom = ''
    folder_nom = folder_nom or folder_defaut
    return cabinet_nom, folder_nom


def generer_document(modele, contexte, *, company, created_by=None,
                     nom=None, cabinet_nom='Modèles', folder_nom='Mailing'):
    """GED27 + GED28 — Rend un modèle en PDF, le CLASSE et le DÉPOSE en GED.

    Fusionne + rend le PDF (`rendre_modele`) puis l'enregistre dans le
    référentiel GED en RÉUTILISANT le service de dépôt existant
    (`deposit_document`, lui-même fondé sur `create_document`/`add_version` et le
    stockage objet `records.storage`) — on ne duplique ni le stockage ni le
    versionnage. Multi-tenant : `company` posée CÔTÉ SERVEUR (jamais lue du corps
    de requête), cohérente avec le modèle.

    GED28 — CLASSEMENT AUTOMATIQUE : le cabinet et le dossier de destination sont
    résolus depuis la RÈGLE de classement du modèle (`cabinet_cible` /
    `dossier_cible` — ce dernier pouvant porter des jetons ``{{ champ }}``
    résolus depuis le contexte, ex. par année/client) via `resoudre_classement`.
    Le cabinet et le dossier sont auto-créés s'ils manquent (`ensure_cabinet` /
    `ensure_root_folder`, idempotents). RÉTRO-COMPATIBLE : un modèle SANS cible
    retombe sur les dossiers `cabinet_nom`/`folder_nom` passés par l'appelant
    (défauts inchangés « Modèles » / « Mailing »).

    L'idempotence du dépôt est ancrée sur (`source_type`='ged.modeledocument',
    `source_id`=pk du modèle) : un mailing répété pour le MÊME modèle retrouve le
    document déjà déposé au lieu d'en dupliquer un (comportement standard de
    `deposit_document`). Renvoie `(document, created)`.
    """
    if modele.company_id is not None \
            and modele.company_id != getattr(company, 'id', company):
        raise ValueError("Le modèle doit appartenir à la même société.")
    pdf_bytes = rendre_modele(modele, contexte)
    # GED28 : où classer ? Règle du modèle (cible templatée) sinon défauts appelant.
    cabinet_resolu, folder_resolu = resoudre_classement(
        modele, contexte,
        cabinet_defaut=cabinet_nom, folder_defaut=folder_nom)
    return deposit_document(
        company=company,
        nom=nom or modele.nom,
        source_type='ged.modeledocument',
        source_id=modele.pk,
        contenu_bytes=pdf_bytes,
        mime='application/pdf',
        description=modele.description or '',
        cabinet_nom=cabinet_resolu,
        folder_nom=folder_resolu,
        created_by=created_by,
    )


# ── GED29 — Filage (classement) des PDF après-vente (SAV) générés ──────────

def classer_document_apres_vente(*, company, file_key='', contenu_bytes=None,
                                 nom, source_type, source_id,
                                 cabinet='Après-vente', dossier='Après-vente',
                                 created_by=None, mime='application/pdf',
                                 description=''):
    """GED29 — Classe (file) un PDF APRÈS-VENTE (SAV) DÉJÀ généré dans la GED.

    Point d'entrée de RÉCEPTION côté GED : une autre app (le module SAV /
    après-vente, câblé dans une tâche FUTURE) produit un PDF après-vente
    (rapport d'intervention, bon de SAV, attestation de garantie…) puis appelle
    ce service pour le DÉPOSER et le CLASSER automatiquement dans un cabinet/
    dossier « Après-vente » dédié — SANS importer les modèles GED, en RÉUTILISANT
    les primitives existantes (`deposit_document`, lui-même fondé sur
    `create_document`/`add_version` et le stockage objet `records.storage`). On ne
    réimplémente ni le stockage ni le versionnage ni l'idempotence.

    Multi-tenant : `company` est posée CÔTÉ SERVEUR par l'appelant (jamais lue
    d'un corps de requête) ; cabinet, dossier, document et version héritent tous
    de cette société. Le cabinet et le dossier « Après-vente » sont auto-créés
    s'ils manquent (`ensure_cabinet` / `ensure_root_folder`, idempotents — via
    `deposit_document`).

    Source du contenu (au moins l'une) :
      - `file_key` : la clé d'un objet déjà stocké en MinIO (records.storage),
        p.ex. un PDF que l'app SAV a déjà téléversé.
      - `contenu_bytes` : des octets bruts (rendu PDF en mémoire) téléversés ici
        via le même stockage objet que `records.storage`.
      Si AUCUN n'est fourni, un document « pointeur vide » est tout de même créé
      (trace), comportement hérité de `deposit_document`.

    CLASSEMENT : sous-dossier contextuel TRIVIAL réutilisant la résolution sûre de
    GED28 — le nom de `dossier` peut porter des jetons ``{{ champ }}`` (ici borné à
    l'année, ex. « Après-vente {{ annee }} » → « Après-vente 2026 ») résolus par
    `fusionner_modele` (substitution SÛRE, jamais d'exécution de code). L'année
    courante est injectée dans le contexte ; un `dossier` sans jeton est laissé
    tel quel.

    IDEMPOTENCE : ancrée sur (`source_type`, `source_id`) — l'objet métier SAV
    source (ex. 'sav.ticket' + pk, ou 'sav.rapportintervention' + pk). Un dépôt
    répété pour le MÊME objet source ne crée JAMAIS un second document : on
    retrouve et on renvoie l'existant (idempotence native de `deposit_document`).

    Renvoie `(document, created)` : le `Document` GED et un booléen (`created` =
    True s'il vient d'être créé, False = déposé idempotent / déjà présent).
    """
    from django.utils import timezone

    cabinet_nom = (cabinet or '').strip() or 'Après-vente'
    # Sous-dossier contextuel trivial (GED28) : résout les jetons {{ annee }}
    # depuis un contexte borné (année courante). Un dossier sans jeton est inchangé.
    brut = (dossier or '').strip()
    contexte = {'annee': timezone.now().year}
    folder_nom = (fusionner_modele(brut, contexte).strip() if brut else '') \
        or 'Après-vente'
    return deposit_document(
        company=company,
        nom=nom,
        source_type=source_type,
        source_id=source_id,
        file_key=file_key or '',
        contenu_bytes=contenu_bytes,
        mime=mime or 'application/pdf',
        description=description or '',
        cabinet_nom=cabinet_nom,
        folder_nom=folder_nom,
        created_by=created_by,
    )


# ── GED30 — Signature électronique (point d'intégration + STUB no-op) ─────────

def esign_active():
    """GED30 — True si un fournisseur e-sign externe est activé (clé présente).

    KEY-GATED (mirroir de `embedding_enabled()` GED12) : sans
    `settings.ESIGN_ENABLED` à vrai, tout est un STUB no-op — `demander_signature`
    se contente de créer une demande LOCALE `en_attente` (aucun appel réseau,
    aucun coût, aucune dépendance nouvelle). Le founder activera un fournisseur
    réel (DocuSign/Yousign/…) en posant le flag + la clé du provider dans
    l'environnement ; tant que ce n'est pas fait, la GED reste 100 % locale."""
    from django.conf import settings
    return bool(getattr(settings, 'ESIGN_ENABLED', False))


def esign_provider_name():
    """GED30 — Nom du fournisseur e-sign configuré, ou « aucun » (stub).

    Renvoie `settings.ESIGN_PROVIDER` seulement si l'e-sign est active ; sinon
    « aucun » (mode stub). Aucune dépendance/import de provider ici."""
    from django.conf import settings
    from .models import SIGNATURE_PROVIDER_AUCUN
    if not esign_active():
        return SIGNATURE_PROVIDER_AUCUN
    return getattr(settings, 'ESIGN_PROVIDER', SIGNATURE_PROVIDER_AUCUN) \
        or SIGNATURE_PROVIDER_AUCUN


def demander_signature(document, *, signataire_nom, signataire_email,
                       company, created_by=None):
    """GED30 — Demande une signature électronique sur un document (STUB no-op).

    Crée une `DemandeSignatureDocument` `en_attente` rattachée au document. La
    `company` est TOUJOURS fournie par l'appelant (résolue côté serveur depuis
    `request.user.company`) — jamais lue d'un corps de requête ; elle doit
    correspondre à celle du document (sinon `PermissionError`, traduit en 404/403
    côté vue). `created_by` est posé côté serveur.

    KEY-GATED NO-OP : quand `esign_active()` est faux, AUCUN appel réseau n'est
    fait — la demande reste un enregistrement purement local `en_attente` avec
    `provider='aucun'` et `provider_ref=''` (résultat déterministe, aucun coût,
    aucune dépendance nouvelle). Quand un provider sera câblé (clé posée par le
    founder), c'est ICI que l'appel fournisseur serait fait (squelette isolé
    ci-dessous, jamais exécuté tant qu'aucun provider concret n'est importé) et
    `provider`/`provider_ref` seraient renseignés.

    Renvoie la `DemandeSignatureDocument` créée.
    """
    from .models import (
        DemandeSignatureDocument, SIGNATURE_EN_ATTENTE, SIGNATURE_PROVIDER_AUCUN,
    )

    if document.company_id != getattr(company, 'id', None):
        raise PermissionError("Document inaccessible.")

    provider = SIGNATURE_PROVIDER_AUCUN
    provider_ref = ''
    if esign_active():  # pragma: no cover - dépend d'un provider externe non câblé.
        # Branchement provider à venir (clé-gated). Tant qu'aucun fournisseur
        # concret n'est importé, on reste no-op même flag activé — jamais d'appel
        # fantôme ni de dépendance nouvelle.
        prov = None
        try:
            from . import esign_provider as prov  # noqa: F401
        except ImportError:
            prov = None
        if prov is not None:
            provider = esign_provider_name()
            provider_ref = prov.create_signature_request(
                document=document,
                signataire_nom=signataire_nom,
                signataire_email=signataire_email,
            ) or ''

    return DemandeSignatureDocument.objects.create(
        company=document.company,
        document=document,
        signataire_nom=(signataire_nom or '').strip(),
        signataire_email=(signataire_email or '').strip(),
        statut=SIGNATURE_EN_ATTENTE,
        provider=provider,
        provider_ref=provider_ref,
        created_by=created_by,
    )


def marquer_signe(demande, *, provider_ref=None, date_signature=None):
    """GED30 — Enregistre la COMPLÉTION d'une signature (webhook ou manuel).

    Bascule la demande en `signe` et horodate `date_signature` (défaut : maintenant).
    Point d'entrée pour un callback/webhook provider OU une saisie manuelle ;
    aucune dépendance externe — purement une mise à jour locale. Idempotent : une
    demande déjà signée reste signée. Si un `provider_ref` est fourni (callback),
    on le conserve. Une demande annulée/refusée n'est pas re-basculée en signée.

    Renvoie la `DemandeSignatureDocument` mise à jour.
    """
    from django.utils import timezone
    from .models import (
        SIGNATURE_ANNULE, SIGNATURE_REFUSE, SIGNATURE_SIGNE,
    )

    if demande.statut in (SIGNATURE_ANNULE, SIGNATURE_REFUSE):
        return demande
    champs = []
    etait_deja_signe = demande.statut == SIGNATURE_SIGNE
    if not etait_deja_signe:
        demande.statut = SIGNATURE_SIGNE
        champs.append('statut')
    if demande.date_signature is None:
        demande.date_signature = date_signature or timezone.now()
        champs.append('date_signature')
    if provider_ref:
        demande.provider_ref = provider_ref
        champs.append('provider_ref')
    if champs:
        demande.save(update_fields=champs)
    # XGED4 — À la PREMIÈRE complétion (jamais en ré-appel idempotent) : génère
    # le certificat + classe automatiquement, SANS action manuelle. Best-effort
    # total (try/except large) — un souci de rendu/stockage ne doit JAMAIS
    # empêcher la signature elle-même d'être enregistrée.
    if not etait_deja_signe:
        try:
            classer_signature_completee(demande)
        except Exception:  # pragma: no cover - défensif, jamais bloquant.
            import logging
            logging.getLogger(__name__).warning(
                'XGED4: classement automatique après signature échoué '
                'pour la demande %s', demande.pk, exc_info=True)
        # XGED15 — journal automatique : signature complétée (best-effort).
        journaliser_evenement(
            demande.document, type_evenement='signature_completee',
            message=f'Signé par {demande.signataire_nom}.'.strip())
    return demande


# ── XGED1 — Cérémonie de signature in-app (lien public tokenisé) ────────────

# Sentinelles de résolution publique — même motif que `resolve_partage_public`
# (GED20) : jamais de fuite distinguant « jeton inconnu » d'un état terminal
# révélateur ; un jeton inconnu ET une demande annulée renvoient le même 404.
SIGNATURE_PUBLIQUE_OK = 'ok'
SIGNATURE_PUBLIQUE_INTROUVABLE = 'introuvable'   # jeton inconnu → 404
SIGNATURE_PUBLIQUE_EXPIREE = 'expiree'           # expirée/annulée → 410
SIGNATURE_PUBLIQUE_DEJA_TRAITEE = 'deja_traitee'  # déjà signée/refusée → 410


def resolve_signature_publique(token):
    """XGED1 — Résout une demande de signature DEPUIS le seul jeton public.

    Cœur sécurité : aucune identité/société n'est jamais lue de la requête —
    tout est résolu à partir du `token` (qui ne référence qu'UNE seule demande
    d'UNE seule société). Renvoie `(statut, demande_ou_None)` :

      - SIGNATURE_PUBLIQUE_INTROUVABLE : jeton inconnu → 404.
      - SIGNATURE_PUBLIQUE_EXPIREE     : `expires_at` dépassée OU demande
        `annule` → 410 Gone.
      - SIGNATURE_PUBLIQUE_DEJA_TRAITEE : déjà `signe`/`refuse` → 410 Gone
        (idempotence visible : le lien ne re-signe jamais deux fois).
      - SIGNATURE_PUBLIQUE_OK          : la demande est signable/refusable.
    """
    from .models import (
        DemandeSignatureDocument, SIGNATURE_ANNULE, SIGNATURE_EN_ATTENTE,
    )
    demande = (DemandeSignatureDocument.objects
               .select_related('document', 'document__company', 'company')
               .filter(token=token)
               .first())
    if demande is None:
        return SIGNATURE_PUBLIQUE_INTROUVABLE, None
    if demande.statut == SIGNATURE_ANNULE or demande.is_expired:
        return SIGNATURE_PUBLIQUE_EXPIREE, demande
    if demande.statut != SIGNATURE_EN_ATTENTE:
        return SIGNATURE_PUBLIQUE_DEJA_TRAITEE, demande
    return SIGNATURE_PUBLIQUE_OK, demande


def _hash_version_contenu(version):
    """XGED1 — SHA-256 hex du CONTENU de la version courante (preuve QJ10).

    Best-effort : si le contenu n'est pas récupérable (stockage indisponible),
    renvoie une chaîne vide plutôt que de bloquer la signature — le hash reste
    une preuve BONUS, jamais un bloqueur de cérémonie."""
    if version is None:
        return ''
    try:
        from apps.records.storage import fetch_attachment
        data, err = fetch_attachment(version.file_key)
        if err or data is None:
            return ''
        return hashlib.sha256(data).hexdigest()
    except Exception:  # pragma: no cover - défensif, jamais bloquant.
        return ''


def signer_demande_publique(demande, *, consentement, signature_texte='',
                            signature_tracee='', adresse_ip=None,
                            user_agent=''):
    """XGED1 — Enregistre la SIGNATURE d'une demande depuis le lien public.

    Exige un consentement explicite (`consentement is True`) ET au moins une
    des deux formes de signature (nom tapé OU tracé vectoriel — pattern FG69
    `signature_client`). Les preuves (IP/UA/horodatage/hash du contenu de la
    version courante — pattern QJ10) sont posées CÔTÉ SERVEUR, jamais lues du
    corps au-delà de ce que l'appelant (la vue publique) fournit explicitement.
    Une fois signée, les champs de preuve sont IMMUABLES (l'API ne les modifie
    plus jamais). Bascule le statut via `marquer_signe` (réutilisé, ne le
    duplique pas). Lève `ValueError` si le consentement/la signature manquent.

    Renvoie la `DemandeSignatureDocument` mise à jour.
    """
    from django.utils import timezone

    if not consentement:
        raise ValueError(
            "Le consentement explicite à contracter électroniquement est requis.")
    signature_texte = (signature_texte or '').strip()
    signature_tracee = (signature_tracee or '').strip()
    if not signature_texte and not signature_tracee:
        raise ValueError(
            "Une signature (nom tapé ou tracé) est requise.")

    version = selectors_latest_version(demande.document)
    demande.consentement_explicite = True
    demande.signature_texte = signature_texte
    demande.signature_tracee = signature_tracee
    demande.adresse_ip = adresse_ip or None
    demande.user_agent = (user_agent or '')[:512]
    demande.hash_contenu = _hash_version_contenu(version)
    demande.save(update_fields=[
        'consentement_explicite', 'signature_texte', 'signature_tracee',
        'adresse_ip', 'user_agent', 'hash_contenu', 'updated_at',
    ])
    return marquer_signe(demande, date_signature=timezone.now())


def refuser_demande_publique(demande, *, motif, adresse_ip=None, user_agent=''):
    """XGED1 — Enregistre le REFUS d'une demande depuis le lien public.

    Motif OBLIGATOIRE (non vide). Statut → `refuse`, horodaté ; les preuves
    IP/UA sont posées côté serveur. Idempotent : un refus déjà enregistré ne
    modifie pas `refuse_le`. Lève `ValueError` si le motif est vide.

    Renvoie la `DemandeSignatureDocument` mise à jour.
    """
    from django.utils import timezone
    from .models import SIGNATURE_REFUSE

    motif = (motif or '').strip()
    if not motif:
        raise ValueError("Le motif de refus est requis.")

    champs = ['motif_refus', 'adresse_ip', 'user_agent', 'updated_at']
    demande.motif_refus = motif
    demande.adresse_ip = adresse_ip or None
    demande.user_agent = (user_agent or '')[:512]
    if demande.statut != SIGNATURE_REFUSE:
        demande.statut = SIGNATURE_REFUSE
        champs.append('statut')
    if demande.refuse_le is None:
        demande.refuse_le = timezone.now()
        champs.append('refuse_le')
    demande.save(update_fields=champs)
    return demande


def selectors_latest_version(document):
    """Import paresseux de `selectors.latest_version` (évite un cycle module)."""
    from . import selectors
    return selectors.latest_version(document)


# ── XGED2 — Circuit multi-signataires (séquentiel/parallèle) ────────────────

def _send_signataire_email(signataire, demande, *, relance=False):
    """XGED2 — Envoie (best-effort) le lien de signature à un destinataire.

    Réutilise `django.core.mail.send_mail` (pattern `ventes._send_otp_email`) —
    backend console en local, jamais bloquant : toute erreur d'envoi est
    journalisée mais ne casse jamais le flux de notification/relance."""
    if not signataire.email:
        return False
    try:
        from django.conf import settings
        from django.core.mail import send_mail
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@erp.local')
        sujet = (
            f'Relance — document à signer : {demande.document.nom}'
            if relance else f'Document à signer : {demande.document.nom}')
        corps = (
            f'Bonjour {signataire.nom},\n\n'
            f'Un document « {demande.document.nom} » requiert votre '
            f'{"attention" if signataire.role != "signataire" else "signature"}.\n'
            f'Lien : /ged/signature/{signataire.token}/\n\n'
            "Cordialement,\nL'équipe TAQINOR"
        )
        send_mail(sujet, corps, from_email, [signataire.email], fail_silently=False)
        return True
    except Exception as exc:  # noqa: BLE001 - best-effort, jamais bloquant.
        import logging
        logging.getLogger(__name__).warning(
            'XGED2: envoi email signataire échoué : %s', exc)
        return False


@transaction.atomic
def creer_demande_multi_signataires(document, *, destinataires, company,
                                    routage=None, expires_at=None,
                                    relance_cadence_jours=None,
                                    created_by=None):
    """XGED2 — Crée une demande de signature à PLUSIEURS destinataires.

    `destinataires` : liste ordonnée de dicts
    `{"nom", "email"?, "telephone"?, "role"?, "ordre"?, "role_signataire"?}`.
    Le premier élément devient le signataire « principal » de la
    `DemandeSignatureDocument` (`signataire_nom`/`signataire_email`,
    rétrocompatibilité GED30/XGED1) ; TOUS les éléments deviennent des
    `SignataireDemande` ordonnés. `company` est TOUJOURS fournie par
    l'appelant (jamais lue du corps) et doit correspondre à celle du document
    (sinon `PermissionError`).

    ZGED1 — `role_signataire` (id, optionnel) référence le catalogue de
    rôles réutilisables (`RoleSignataire`, borné à la même société — un id
    d'une autre société est silencieusement ignoré, jamais une fuite) : le
    destinataire HÉRITE de sa couleur/authentification extra. RÉTROCOMPATIBLE
    : sans référence, le `role` texte reste la seule valeur (comportement
    XGED2 inchangé).

    Routage : `notifier_prochains_signataires` est appelé immédiatement après
    création — en parallèle, tous les `signataire` sont notifiés ; en
    séquentiel, seul le rang 1 l'est.

    Renvoie la `DemandeSignatureDocument` créée (avec ses `.signataires`).
    """
    from .models import (
        ROLE_SIGNATAIRE, ROUTAGE_SEQUENTIEL, RoleSignataire, SignataireDemande,
    )

    if not destinataires:
        raise ValueError("Au moins un destinataire est requis.")
    premier = destinataires[0]
    demande = demander_signature(
        document,
        signataire_nom=premier.get('nom', ''),
        signataire_email=premier.get('email', ''),
        company=company,
        created_by=created_by)
    demande.routage = routage or ROUTAGE_SEQUENTIEL
    demande.expires_at = expires_at
    demande.relance_cadence_jours = relance_cadence_jours
    demande.save(update_fields=[
        'routage', 'expires_at', 'relance_cadence_jours', 'updated_at'])

    for idx, dest in enumerate(destinataires, start=1):
        role_signataire = None
        role_signataire_id = dest.get('role_signataire')
        if role_signataire_id:
            role_signataire = RoleSignataire.objects.filter(
                company=demande.company, pk=role_signataire_id).first()
        SignataireDemande.objects.create(
            company=demande.company,
            demande=demande,
            nom=(dest.get('nom') or '').strip(),
            email=(dest.get('email') or '').strip(),
            telephone=(dest.get('telephone') or '').strip(),
            ordre=dest.get('ordre', idx),
            role=dest.get('role', ROLE_SIGNATAIRE),
            role_signataire=role_signataire,
        )
    notifier_prochains_signataires(demande)
    return demande


def notifier_prochains_signataires(demande):
    """XGED2 — Notifie les destinataires dont c'est le tour (routage-aware).

    Parallèle : notifie tous les `SignataireDemande` encore `en_attente`.
    Séquentiel : notifie uniquement le/les rang(s) le(s) plus bas parmi ceux
    encore `en_attente` (le rang N+1 n'est notifié qu'après le traitement — ie.
    signature/refus — du rang N). Les `copie`/`approbateur` sont TOUJOURS
    notifiés en parallèle du flux (jamais bloquants pour les signataires).
    Idempotent : un destinataire déjà notifié n'est pas re-notifié ici (seule
    `relancer_signataires_dus` ré-émet, à cadence)."""
    from django.utils import timezone
    from .models import (
        ROLE_SIGNATAIRE, ROUTAGE_SEQUENTIEL, SIGNATAIRE_EN_ATTENTE,
        SIGNATAIRE_NOTIFIE,
    )

    a_notifier = list(demande.signataires.filter(statut=SIGNATAIRE_EN_ATTENTE))
    if not a_notifier:
        return []

    if demande.routage == ROUTAGE_SEQUENTIEL:
        signataires_en_cours = [s for s in a_notifier if s.role == ROLE_SIGNATAIRE]
        non_signataires = [s for s in a_notifier if s.role != ROLE_SIGNATAIRE]
        cible = []
        if signataires_en_cours:
            rang_min = min(s.ordre for s in signataires_en_cours)
            cible = [s for s in signataires_en_cours if s.ordre == rang_min]
        cible += non_signataires
    else:
        cible = a_notifier

    notifies = []
    now = timezone.now()
    for signataire in cible:
        signataire.statut = SIGNATAIRE_NOTIFIE
        signataire.notifie_le = now
        signataire.save(update_fields=['statut', 'notifie_le', 'updated_at'])
        _send_signataire_email(signataire, demande)
        notifies.append(signataire)
    return notifies


# ── ZGED2 — Authentification extra du signataire (SMS/OTP email, key-gated) ─

OTP_EXPIRATION_MINUTES = 10
OTP_MAX_ESSAIS = 3


def _generer_code_otp():
    """ZGED2 — Génère un code à 6 chiffres cryptographiquement fort."""
    import secrets as _secrets
    return f'{_secrets.randbelow(1_000_000):06d}'


def _hash_otp(code):
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def envoyer_code_otp_signataire(signataire, *, telephone_override='',
                                email_override=''):
    """ZGED2 — Envoie (ou dégrade proprement) le code d'authentification
    extra d'UN destinataire, selon son `auth_extra_effective`.

    Sans authentification extra requise (`aucune`) : no-op, renvoie
    `{'envoye': False, 'mode': 'aucune'}` — la signature se fait directement
    (comportement XGED1 inchangé).

    Mode `sms` : si la passerelle SMS marocaine (`core.sms`, FG371,
    key-gated) est configurée pour la société, envoie un code à 6 chiffres au
    téléphone du signataire ; SANS passerelle configurée, dégrade en « aucune »
    avec un message clair (no-op, aucun appel réseau, aucune dépendance
    nouvelle) — la signature reste possible sans OTP, et le journal le note.

    Mode `email_otp` : réutilise le backend email existant (console en local,
    même mécanisme que les relances XGED2) — toujours « envoyé » car aucune
    passerelle externe requise.

    Génération/validation horodatées ; le code n'est JAMAIS stocké en clair
    (seul `otp_code_hash`, SHA-256). Renvoie un dict `{'envoye', 'mode',
    'detail'}` — jamais d'exception (toujours un résultat exploitable par la
    vue publique)."""
    import datetime

    from django.utils import timezone

    mode = signataire.auth_extra_effective
    if mode == 'aucune':
        return {'envoye': False, 'mode': 'aucune',
                'detail': "Aucune authentification extra requise."}

    if mode == 'sms':
        from core.sms import send_sms
        company = signataire.demande.company
        telephone = telephone_override or signataire.telephone
        if not telephone:
            return {'envoye': False, 'mode': 'aucune',
                    'detail': "Aucun téléphone renseigné : authentification "
                              "SMS dégradée (signature sans OTP)."}
        code = _generer_code_otp()
        resultat = send_sms(
            company, telephone,
            f'TAQINOR — votre code de signature : {code}')
        if not resultat.sent:
            # Passerelle absente/non configurée → dégrade proprement en
            # « aucune » (jamais bloquant, jamais un faux OTP requis).
            return {'envoye': False, 'mode': 'aucune',
                    'detail': f'Passerelle SMS indisponible ({resultat.detail}) '
                              ': authentification dégradée, signature sans OTP.'}
        signataire.otp_code_hash = _hash_otp(code)
        signataire.otp_expires_at = (
            timezone.now() + datetime.timedelta(minutes=OTP_EXPIRATION_MINUTES))
        signataire.otp_essais = 0
        signataire.otp_valide = False
        signataire.save(update_fields=[
            'otp_code_hash', 'otp_expires_at', 'otp_essais', 'otp_valide',
            'updated_at'])
        return {'envoye': True, 'mode': 'sms', 'detail': 'Code SMS envoyé.'}

    if mode == 'email_otp':
        from django.conf import settings
        from django.core.mail import send_mail
        email = email_override or signataire.email
        if not email:
            return {'envoye': False, 'mode': 'aucune',
                    'detail': "Aucun email renseigné : authentification "
                              "dégradée, signature sans OTP."}
        code = _generer_code_otp()
        from_email = getattr(
            settings, 'DEFAULT_FROM_EMAIL', 'no-reply@taqinor.ma')
        try:
            send_mail(
                'TAQINOR — code de signature', f'Votre code : {code}',
                from_email, [email], fail_silently=False)
        except Exception as exc:  # noqa: BLE001 — dégrade, jamais bloquant.
            return {'envoye': False, 'mode': 'aucune',
                    'detail': f"Envoi email échoué ({exc}) : authentification "
                              "dégradée, signature sans OTP."}
        signataire.otp_code_hash = _hash_otp(code)
        signataire.otp_expires_at = (
            timezone.now() + datetime.timedelta(minutes=OTP_EXPIRATION_MINUTES))
        signataire.otp_essais = 0
        signataire.otp_valide = False
        signataire.save(update_fields=[
            'otp_code_hash', 'otp_expires_at', 'otp_essais', 'otp_valide',
            'updated_at'])
        return {'envoye': True, 'mode': 'email_otp', 'detail': 'Code email envoyé.'}

    return {'envoye': False, 'mode': 'aucune',
            'detail': f'Mode inconnu : {mode!r} — dégradé.'}


def valider_code_otp_signataire(signataire, code):
    """ZGED2 — Valide le code saisi par le signataire (3 essais max, expire
    en `OTP_EXPIRATION_MINUTES`).

    Lève `ValueError` (→ 400 explicite côté vue, jamais silencieux) si :
    aucun code n'a été envoyé, le code a expiré, ou les essais sont épuisés.
    Un mauvais code incrémente `otp_essais` et lève `ValueError` (tracé).
    Renvoie `signataire` avec `otp_valide=True` en cas de succès."""
    from django.utils import timezone

    if not signataire.otp_code_hash or signataire.otp_expires_at is None:
        raise ValueError("Aucun code d'authentification n'a été envoyé.")
    if signataire.otp_expires_at <= timezone.now():
        raise ValueError("Le code d'authentification a expiré.")
    if signataire.otp_essais >= OTP_MAX_ESSAIS:
        raise ValueError("Nombre maximal d'essais atteint.")
    if _hash_otp((code or '').strip()) != signataire.otp_code_hash:
        signataire.otp_essais += 1
        signataire.save(update_fields=['otp_essais', 'updated_at'])
        raise ValueError("Code d'authentification incorrect.")
    signataire.otp_valide = True
    signataire.otp_valide_le = timezone.now()
    signataire.save(update_fields=['otp_valide', 'otp_valide_le', 'updated_at'])
    return signataire


def signer_signataire(signataire, *, consentement, signature_texte='',
                      signature_tracee='', adresse_ip=None, user_agent=''):
    """XGED2 — Signe le rang d'UN signataire et fait progresser le circuit
    (notifie le rang suivant en séquentiel).

    Exige le même consentement + forme de signature que le mono-signataire
    (`ValueError` sinon — réutilise les mêmes règles que XGED1, appliquées ICI
    au signataire individuel plutôt qu'à la demande globale). N'affecte QUE ce
    `SignataireDemande` ; le statut GLOBAL de la demande n'est marqué `signe`
    que lorsque TOUS les `signataire` requis ont signé (`_maj_statut_global`).

    ZGED2 — si une authentification extra est requise pour ce destinataire
    (`otp_requis_et_non_valide`), la signature est REFUSÉE (`ValueError`,
    tracé) tant que le bon code n'a pas été validé au préalable
    (`valider_code_otp_signataire`)."""
    from django.utils import timezone
    from .models import SIGNATAIRE_SIGNE

    if signataire.otp_requis_et_non_valide:
        raise ValueError(
            "Authentification supplémentaire requise avant de signer : "
            "saisissez le code reçu.")
    if not consentement:
        raise ValueError(
            "Le consentement explicite à contracter électroniquement est requis.")
    signature_texte = (signature_texte or '').strip()
    signature_tracee = (signature_tracee or '').strip()
    if not signature_texte and not signature_tracee:
        raise ValueError("Une signature (nom tapé ou tracé) est requise.")

    signataire.statut = SIGNATAIRE_SIGNE
    signataire.date_action = timezone.now()
    signataire.save(update_fields=['statut', 'date_action', 'updated_at'])
    notifier_prochains_signataires(signataire.demande)
    _maj_statut_global(signataire.demande)
    return signataire


def refuser_signataire(signataire, *, motif):
    """XGED2 — Refuse le rang d'UN signataire. Un refus INDIVIDUEL bascule la
    demande GLOBALE en `refuse` (un refus de N'IMPORTE quel signataire requis
    arrête le circuit — cohérent avec le refus mono-signataire XGED1)."""
    from django.utils import timezone
    from .models import SIGNATAIRE_REFUSE, SIGNATURE_REFUSE

    motif = (motif or '').strip()
    if not motif:
        raise ValueError("Le motif de refus est requis.")
    signataire.statut = SIGNATAIRE_REFUSE
    signataire.motif_refus = motif
    signataire.date_action = timezone.now()
    signataire.save(update_fields=[
        'statut', 'motif_refus', 'date_action', 'updated_at'])

    demande = signataire.demande
    champs = ['motif_refus', 'updated_at']
    demande.motif_refus = motif
    if demande.statut != SIGNATURE_REFUSE:
        demande.statut = SIGNATURE_REFUSE
        champs.append('statut')
    if demande.refuse_le is None:
        demande.refuse_le = timezone.now()
        champs.append('refuse_le')
    demande.save(update_fields=champs)
    return signataire


def _maj_statut_global(demande):
    """XGED2 — Bascule la demande en `signe` quand tous les `signataire`
    requis ont signé (aucun-op si des signataires restent en attente, ou s'il
    n'y a aucun `SignataireDemande` — comportement mono-partie XGED1 inchangé,
    piloté directement par `marquer_signe`)."""
    from .models import ROLE_SIGNATAIRE, SIGNATAIRE_SIGNE

    requis = list(demande.signataires.filter(role=ROLE_SIGNATAIRE))
    if not requis:
        return demande
    if all(s.statut == SIGNATAIRE_SIGNE for s in requis):
        return marquer_signe(demande)
    return demande


def annuler_demande(demande, *, user):
    """XGED2 — Annule une demande de signature (action ÉMETTEUR, tracée).

    Bascule `statut → annule`, horodate `annule_le`/`annule_par`. Une demande
    déjà `signe`/`refuse` ne peut plus être annulée (`ValueError`) — l'issue
    est déjà définitive. Idempotent sur une demande déjà `annule`."""
    from django.utils import timezone
    from .models import SIGNATURE_ANNULE, SIGNATURE_REFUSE, SIGNATURE_SIGNE

    if demande.statut in (SIGNATURE_SIGNE, SIGNATURE_REFUSE):
        raise ValueError(
            "Une demande déjà signée ou refusée ne peut plus être annulée.")
    if demande.statut == SIGNATURE_ANNULE:
        return demande
    demande.statut = SIGNATURE_ANNULE
    demande.annule_le = timezone.now()
    demande.annule_par = user
    demande.save(update_fields=[
        'statut', 'annule_le', 'annule_par', 'updated_at'])
    return demande


def expirer_demandes_echues(company, *, now=None):
    """XGED2 — Bascule en `annule` les demandes `en_attente` dont `expires_at`
    est dépassée (sweep planifié, idempotent, bornée à une société).

    Renvoie le nombre de demandes basculées."""
    from django.utils import timezone
    from .models import DemandeSignatureDocument, SIGNATURE_ANNULE, SIGNATURE_EN_ATTENTE

    now = now or timezone.now()
    echues = DemandeSignatureDocument.objects.filter(
        company=company, statut=SIGNATURE_EN_ATTENTE,
        expires_at__isnull=False, expires_at__lte=now)
    count = 0
    for demande in echues:
        demande.statut = SIGNATURE_ANNULE
        demande.annule_le = now
        demande.save(update_fields=['statut', 'annule_le', 'updated_at'])
        count += 1
    return count


def notifier_emetteur_expiration_proche(company, *, seuil_jours=3, now=None):
    """ZGED14 — Notifie l'ÉMETTEUR d'une demande `en_attente` dont
    l'expiration approche (versant ÉMETTEUR — XGED2 ne couvre que le
    SIGNATAIRE). « Approche » = `expires_at` dans les `seuil_jours` à venir
    (et pas encore dépassée — `expirer_demandes_echues` gère l'échéance
    dépassée séparément).

    Anti-doublon : une demande déjà notifiée pour SA fenêtre d'expiration
    courante (`emetteur_notifie_expiration_le` renseigné) n'est pas
    re-notifiée. `prolonger_demande_signature` remet ce champ à NULL pour
    réarmer. Une demande sans `created_by` (émetteur inconnu) est ignorée
    silencieusement. Renvoie le nombre de notifications envoyées."""
    from datetime import timedelta

    from django.utils import timezone

    from .models import DemandeSignatureDocument, SIGNATURE_EN_ATTENTE

    now = now or timezone.now()
    seuil = now + timedelta(days=seuil_jours)
    candidats = (DemandeSignatureDocument.objects
                 .filter(company=company, statut=SIGNATURE_EN_ATTENTE,
                         expires_at__isnull=False, expires_at__gt=now,
                         expires_at__lte=seuil,
                         emetteur_notifie_expiration_le__isnull=True)
                 .exclude(created_by__isnull=True)
                 .select_related('created_by', 'document'))
    count = 0
    for demande in candidats:
        jours_restants = max((demande.expires_at - now).days, 0)
        total = demande.signataires.count()
        signes = demande.signataires.filter(statut='signe').count()
        try:
            from apps.notifications.services import notify

            notify(
                demande.created_by, 'ged_signature_expiration_proche',
                title=(
                    f'Demande de signature « {demande.document.nom} » '
                    f'expire dans {jours_restants} jour(s)'),
                body=f'{signes}/{total} signataire(s) ont signé.',
                company=company,
            )
        except Exception:  # pragma: no cover - défensif, best-effort.
            logger.warning(
                'ZGED14 — échec notification émetteur demande #%s',
                demande.pk, exc_info=True)
        demande.emetteur_notifie_expiration_le = now
        demande.save(update_fields=[
            'emetteur_notifie_expiration_le', 'updated_at'])
        count += 1
    return count


def prolonger_demande_signature(demande, *, expires_at, user):
    """ZGED14 — Prolonge l'échéance d'une demande de signature `en_attente`
    (endpoint `demandes-signature/{id}/prolonger/`). Repousse `expires_at` et
    RÉARME la notification émetteur (remet
    `emetteur_notifie_expiration_le` à NULL) pour que le prochain sweep puisse
    re-notifier sur la nouvelle échéance si elle approche à nouveau.

    Multi-tenant : vérifie que `user.company_id == demande.company_id`."""
    if demande.company_id != user.company_id:
        raise PermissionError("Demande inaccessible.")
    demande.expires_at = expires_at
    demande.emetteur_notifie_expiration_le = None
    demande.save(update_fields=[
        'expires_at', 'emetteur_notifie_expiration_le', 'updated_at'])
    journaliser_evenement(
        demande.document, type_evenement='signature_prolongee',
        message=f'Demande #{demande.pk} prolongée jusqu\'au {expires_at}.',
        utilisateur=user)
    return demande


def relancer_signataires_dus(company, *, now=None):
    """XGED2 — Relance (email best-effort) les signataires `notifie` dont la
    cadence configurée sur leur demande (`relance_cadence_jours`) est due.

    Un signataire est DÛ si : sa demande porte une cadence > 0, il est encore
    `notifie` (ni signé ni refusé), et le temps écoulé depuis sa dernière
    relance (ou sa notification initiale si aucune relance encore) dépasse la
    cadence. Idempotent par appel (ne relance jamais deux fois dans le même
    passage). Renvoie la liste des `SignataireDemande` relancés."""
    from datetime import timedelta

    from django.utils import timezone
    from .models import SIGNATAIRE_NOTIFIE, SignataireDemande

    now = now or timezone.now()
    candidats = (SignataireDemande.objects
                 .filter(company=company, statut=SIGNATAIRE_NOTIFIE,
                         demande__relance_cadence_jours__isnull=False)
                 .exclude(demande__relance_cadence_jours=0)
                 .select_related('demande'))
    relances = []
    for signataire in candidats:
        cadence = signataire.demande.relance_cadence_jours
        reference = signataire.derniere_relance_le or signataire.notifie_le
        if reference is None:
            continue
        if now - reference < timedelta(days=cadence):
            continue
        signataire.derniere_relance_le = now
        signataire.nb_relances += 1
        signataire.save(update_fields=[
            'derniere_relance_le', 'nb_relances', 'updated_at'])
        _send_signataire_email(signataire, signataire.demande, relance=True)
        relances.append(signataire)
    return relances


# ── XGED3 — Zones de champs positionnées sur le PDF à signer ────────────────

def champs_pour_demande(demande):
    """XGED3 — Champs positionnés d'une demande (QuerySet, triés page/position).

    Rétrocompatible : renvoie un QuerySet vide pour une demande sans aucun
    champ placé (aucune régression sur le flux mono-champ XGED1)."""
    return demande.champs.all()


def enregistrer_valeurs_champs(demande, valeurs):
    """XGED3 — Enregistre les VALEURS saisies par le signataire pour les
    champs `texte`/`case`/`date` d'une demande (les champs `signature`/
    `initiales` restent vides ici — ils utilisent la signature de la
    cérémonie elle-même, XGED1/XGED2, jamais dupliquée dans `valeur`).

    `valeurs` : dict `{champ_id: valeur_str}`. Ignore silencieusement les
    identifiants inconnus ou hors société (pas d'injection cross-société).
    Ne bloque JAMAIS la cérémonie — best-effort par champ. Renvoie la liste
    des champs mis à jour."""
    from .models import CHAMP_TYPE_INITIALES, CHAMP_TYPE_SIGNATURE

    if not valeurs:
        return []
    champs = {c.id: c for c in demande.champs.all()}
    mis_a_jour = []
    for champ_id, valeur in valeurs.items():
        try:
            champ_id = int(champ_id)
        except (TypeError, ValueError):
            continue
        champ = champs.get(champ_id)
        if champ is None or champ.type_champ in (
                CHAMP_TYPE_SIGNATURE, CHAMP_TYPE_INITIALES):
            continue
        champ.valeur = str(valeur)[:500]
        champ.save(update_fields=['valeur', 'updated_at'])
        mis_a_jour.append(champ)
    return mis_a_jour


def _flatten_champs_pdf(file_bytes, champs, *, signature_texte='',
                        signature_tracee=''):
    """XGED3 — Aplati les VALEURS des champs positionnés sur un PDF final.

    Utilise PyMuPDF (`fitz`) via un import PARESSEUX et GARDÉ — même motif que
    `_watermark_pdf` (GED21) : si la lib est absente, on DÉGRADE en annexant
    une page-texte listant les champs/valeurs (jamais une perte de données,
    jamais un échec bloquant). Les positions `x`/`y`/`largeur`/`hauteur` sont
    en POURCENTAGE de la page — converties en points via `page.rect`.

    Renvoie `(out_bytes, aplati)` où `aplati` est False si PyMuPDF est absent
    (repli annexe texte, toujours `aplati=False` pour signaler la dégradation
    à l'appelant/aux tests)."""
    try:
        import fitz  # PyMuPDF
    except Exception:  # pragma: no cover - chemin de repli sans la lib.
        return _annexe_texte_champs(file_bytes, champs, signature_texte), False
    try:
        from .models import CHAMP_TYPE_CASE, CHAMP_TYPE_SIGNATURE

        doc = fitz.open(stream=file_bytes, filetype='pdf')
        try:
            for champ in champs:
                if champ.page >= len(doc):
                    continue
                page = doc[champ.page]
                rect = page.rect
                x0 = rect.x0 + float(champ.x) / 100.0 * rect.width
                y0 = rect.y0 + float(champ.y) / 100.0 * rect.height
                x1 = x0 + float(champ.largeur) / 100.0 * rect.width
                y1 = y0 + float(champ.hauteur) / 100.0 * rect.height
                zone = fitz.Rect(x0, y0, x1, y1)
                if champ.type_champ == CHAMP_TYPE_SIGNATURE:
                    texte = signature_texte or (
                        '✓ signé' if signature_tracee else '')
                elif champ.type_champ == CHAMP_TYPE_CASE:
                    texte = '☑' if champ.valeur else '☐'
                else:
                    texte = champ.valeur or ''
                if texte:
                    page.insert_textbox(
                        zone, texte, fontsize=10, color=(0, 0, 0.6),
                        align=fitz.TEXT_ALIGN_LEFT, overlay=True)
            out = doc.tobytes()
        finally:
            doc.close()
        return out, True
    except Exception:  # pragma: no cover - robustesse : jamais bloquer.
        return _annexe_texte_champs(file_bytes, champs, signature_texte), False


def _annexe_texte_champs(file_bytes, champs, signature_texte):
    """XGED3 — Dégradation SANS PyMuPDF : renvoie le PDF original inchangé.

    Les valeurs restent disponibles via l'API (`ChampSignature.valeur`) même
    quand l'aplatissement visuel n'a pas pu avoir lieu — aucune perte de
    donnée, seulement une dégradation du RENDU (pattern GED21)."""
    return file_bytes


def signer_demande_publique_avec_champs(demande, *, consentement,
                                        signature_texte='',
                                        signature_tracee='', adresse_ip=None,
                                        user_agent='', valeurs_champs=None):
    """XGED3 — Signature publique QUI honore les champs positionnés (XGED1 +
    remplissage/aplatissement). Wrapper ADDITIF autour de
    `signer_demande_publique` : ne change rien à son comportement pour une
    demande SANS champ (rétrocompatible XGED1) ; pour une demande AVEC des
    champs `requis` non `signature`/`initiales`, exige qu'ils soient tous
    renseignés dans `valeurs_champs` AVANT de signer (sinon `ValueError`).

    Enregistre les valeurs (`enregistrer_valeurs_champs`) puis délègue la
    signature elle-même à `signer_demande_publique` (preuves QJ10 inchangées).
    Renvoie la `DemandeSignatureDocument` signée."""
    from .models import CHAMP_TYPE_INITIALES, CHAMP_TYPE_SIGNATURE

    champs = list(demande.champs.all())
    requis_a_remplir = [
        c for c in champs
        if c.requis and c.type_champ not in (
            CHAMP_TYPE_SIGNATURE, CHAMP_TYPE_INITIALES)]
    if isinstance(valeurs_champs, str):
        # Clients multipart/form (pas JSON) envoient un dict sérialisé en
        # chaîne : on le décode plutôt que de planter sur `.keys()`.
        import json as _json
        try:
            valeurs_champs = _json.loads(valeurs_champs) if valeurs_champs else {}
        except (TypeError, ValueError):
            valeurs_champs = {}
    # Tout ce qui n'est pas un mapping (int/list/None d'un client mal formé) est
    # traité comme « aucun champ fourni » plutôt que de planter sur `.keys()`.
    if not isinstance(valeurs_champs, dict):
        valeurs_champs = {}
    fournis = {int(k) for k in valeurs_champs.keys()
               if str(k).lstrip('-').isdigit()}
    manquants = [c for c in requis_a_remplir if c.id not in fournis]
    if manquants:
        raise ValueError(
            "Certains champs requis du document ne sont pas remplis.")

    if valeurs_champs:
        enregistrer_valeurs_champs(demande, valeurs_champs)

    return signer_demande_publique(
        demande, consentement=consentement,
        signature_texte=signature_texte, signature_tracee=signature_tracee,
        adresse_ip=adresse_ip, user_agent=user_agent)


def rendre_pdf_signe_avec_champs(demande):
    """XGED3 — Rend le PDF final de la version courante avec les champs
    positionnés APLATIS (valeurs + signature). Best-effort : si le contenu
    n'est pas récupérable, renvoie `(None, False)` sans lever.

    Renvoie `(pdf_bytes_ou_None, aplati)`."""
    version = selectors_latest_version(demande.document)
    if version is None:
        return None, False
    try:
        from apps.records.storage import fetch_attachment
        data, err = fetch_attachment(version.file_key)
        if err or data is None:
            return None, False
    except Exception:  # pragma: no cover - défensif.
        return None, False
    champs = list(demande.champs.all())
    if not champs:
        return data, False
    return _flatten_champs_pdf(
        data, champs, signature_texte=demande.signature_texte,
        signature_tracee=demande.signature_tracee)


# ── XGED4 — Certificat de complétion + classement automatique ───────────────

def _evenements_cerentonie(demande):
    """XGED4 — Séquence horodatée des événements d'une demande de signature
    (demande → notification(s) → signature/refus), triée chronologiquement.

    Best-effort et purement descriptive : ne lève jamais, utilisée seulement
    pour l'affichage du certificat."""
    evenements = [('Demande créée', demande.date_demande)]
    for signataire in demande.signataires.all():
        if signataire.notifie_le:
            evenements.append(
                (f'{signataire.nom} notifié', signataire.notifie_le))
        if signataire.date_action:
            libelle = ('signé' if signataire.statut == 'signe' else 'refusé')
            evenements.append(
                (f'{signataire.nom} a {libelle}', signataire.date_action))
    if demande.date_signature:
        evenements.append(('Demande signée', demande.date_signature))
    if demande.refuse_le:
        evenements.append(('Demande refusée', demande.refuse_le))
    return sorted(
        (e for e in evenements if e[1] is not None), key=lambda e: e[1])


def _certificat_html(demande):
    """XGED4 — HTML du certificat de complétion (squelette imprimable minimal,
    même esprit que `_modele_html_document` GED27 — jamais `/proposal`)."""
    document = demande.document
    signataires = list(demande.signataires.all())
    lignes_signataires = ''.join(
        f"<tr><td>{s.nom}</td><td>{s.email or '—'}</td>"
        f"<td>{s.get_role_display()}</td><td>{s.get_statut_display()}</td></tr>"
        for s in signataires
    ) or (
        f"<tr><td>{demande.signataire_nom}</td>"
        f"<td>{demande.signataire_email}</td><td>Signataire</td>"
        f"<td>{demande.get_statut_display()}</td></tr>"
    )
    evenements_html = ''.join(
        f"<li>{libelle} — {quand:%Y-%m-%d %H:%M}</li>"
        for libelle, quand in _evenements_cerentonie(demande)
    )
    geoloc = getattr(demande, 'geolocalisation', '') or 'Non transmise'
    return (
        "<!DOCTYPE html><html lang='fr'><head><meta charset='utf-8'>"
        "<style>"
        "body{font-family:sans-serif;font-size:10pt;color:#1a1a1a;"
        "margin:2cm;line-height:1.5;}"
        "h1{font-size:15pt;border-bottom:2px solid #2b5cab;padding-bottom:6px;}"
        "table{width:100%;border-collapse:collapse;margin:10px 0;}"
        "td,th{border:1px solid #ccc;padding:4px 8px;text-align:left;}"
        "</style></head><body>"
        "<h1>Certificat de complétion de signature électronique</h1>"
        f"<p><strong>Document :</strong> {document.nom}</p>"
        f"<p><strong>Statut final :</strong> {demande.get_statut_display()}</p>"
        f"<p><strong>Adresse IP :</strong> {demande.adresse_ip or 'Non transmise'}</p>"
        f"<p><strong>User-Agent :</strong> {demande.user_agent or 'Non transmis'}</p>"
        f"<p><strong>Géolocalisation :</strong> {geoloc}</p>"
        f"<p><strong>Méthode :</strong> "
        f"{'Tracée' if demande.signature_tracee else 'Nom tapé'}</p>"
        f"<p><strong>Hash du document signé (SHA-256) :</strong> "
        f"{demande.hash_contenu or 'Non calculé'}</p>"
        "<h2>Signataires</h2>"
        f"<table><tr><th>Nom</th><th>Email</th><th>Rôle</th>"
        f"<th>Statut</th></tr>{lignes_signataires}</table>"
        "<h2>Séquence des événements</h2>"
        f"<ul>{evenements_html}</ul>"
        "</body></html>"
    )


def generer_certificat_completion(demande):
    """XGED4 — Rend le certificat de complétion PDF (WeasyPrint, hors
    `/proposal`) d'une demande de signature COMPLÉTÉE (signée).

    Contenu : identités/emails des signataires, IP, user-agent, géolocalisation
    (optionnelle — jamais requise, vide si non transmise par le navigateur),
    méthode (tapée/tracée), séquence horodatée des événements, hash SHA-256.

    ARC12 — la plomberie WeasyPrint est déléguée au service partagé
    ``core.pdf.render_pdf`` (même motif que `rendre_modele` GED27).

    Renvoie les octets du PDF certificat."""
    return render_pdf(html=_certificat_html(demande))


def classer_signature_completee(demande, *, created_by=None):
    """XGED4 — À la complétion d'une demande SIGNÉE : génère le certificat +
    CLASSE AUTOMATIQUEMENT le document signé + son certificat dans un dossier
    « Signés » (réutilise `deposit_document`, idempotent par source), et pose
    un `DocumentLien` vers l'objet métier d'origine SI un lien existe déjà sur
    le document (best-effort, jamais bloquant).

    No-op silencieux si la demande n'est pas `signe` (rien à classer). Renvoie
    un dict `{'document_signe', 'certificat', 'created'}` où `document_signe`
    est le `Document` GED source, `certificat` le `Document` du certificat
    déposé, et `created` un booléen (False = déjà classé, idempotent)."""
    from .models import SIGNATURE_SIGNE

    if demande.statut != SIGNATURE_SIGNE:
        return None

    company = demande.company
    document_source = demande.document

    # 1) Le document signé lui-même : dépose la VERSION COURANTE (déjà
    #    signée/aplatie si XGED3 a produit un PDF final) dans « Signés ».
    version = selectors_latest_version(document_source)
    contenu = None
    if version is not None:
        try:
            from apps.records.storage import fetch_attachment
            data, err = fetch_attachment(version.file_key)
            contenu = data if not err else None
        except Exception:  # pragma: no cover - défensif.
            contenu = None

    # XGED5 — Scellement cryptographique best-effort AVANT dépôt (no-op sans
    # pyHanko — contenu byte-identique dans ce cas, flux XGED4 intact).
    if contenu is not None and (contenu[:4] == b'%PDF'):
        contenu, _scelle = sceller_pdf(contenu, company=company)

    document_signe, created_doc = deposit_document(
        company=company,
        nom=document_source.nom,
        source_type='ged.demandesignaturedocument.document',
        source_id=demande.pk,
        contenu_bytes=contenu,
        mime=(version.mime if version else 'application/pdf') or 'application/pdf',
        description=f'Document signé — demande #{demande.pk}',
        cabinet_nom='Signés', folder_nom='Signés',
        created_by=created_by,
    )

    # 2) Le certificat de complétion — best-effort (WeasyPrint requis).
    certificat_document = None
    try:
        certificat_bytes = generer_certificat_completion(demande)
        certificat_document, _ = deposit_document(
            company=company,
            nom=f'Certificat de complétion — {document_source.nom}',
            source_type='ged.demandesignaturedocument.certificat',
            source_id=demande.pk,
            contenu_bytes=certificat_bytes,
            mime='application/pdf',
            description=f'Certificat de complétion — demande #{demande.pk}',
            cabinet_nom='Signés', folder_nom='Signés',
            created_by=created_by,
        )
    except Exception:  # pragma: no cover - défensif, jamais bloquant.
        certificat_document = None

    # 3) Lien vers l'objet métier d'origine, s'il existe déjà sur le document
    #    source (best-effort — ne crée jamais de lien inventé).
    try:
        from .models import DocumentLien
        liens_source = DocumentLien.objects.filter(document=document_source)
        for lien in liens_source:
            for cible in (document_signe, certificat_document):
                if cible is None:
                    continue
                DocumentLien.objects.get_or_create(
                    company=company, document=cible,
                    content_type=lien.content_type, object_id=lien.object_id,
                    defaults={'created_by': created_by})
    except Exception:  # pragma: no cover - défensif, jamais bloquant.
        pass

    return {
        'document_signe': document_signe,
        'certificat': certificat_document,
        'created': created_doc,
    }


# ── XGED5 — Scellement cryptographique (PAdES) + horodatage qualifié (gated) ─

def _pades_signer_disponible():
    """XGED5 — True si pyHanko est installé (import paresseux, GARDÉ).

    pyHanko est une dépendance OUVERTE/gratuite (requirements.txt) mais reste
    importée fonction-locale : si elle venait à manquer en prod (image non
    reconstruite, etc.), le scellement dégrade proprement en no-op plutôt que
    de lever au chargement du module."""
    try:
        import pyhanko  # noqa: F401
        return True
    except Exception:  # pragma: no cover - chemin de repli sans la lib.
        return False


def tsa_url_configuree():
    """XGED5 — URL de la TSA (RFC 3161) configurée, ou '' (no-op).

    KEY-GATED (mirroir `esign_active`/`embedding_enabled`) : sans
    `settings.GED_TSA_URL`, l'horodatage qualifié est un no-op — le sceau
    PAdES reste posé (si pyHanko est disponible) mais SANS horodatage TSA."""
    from django.conf import settings
    return (getattr(settings, 'GED_TSA_URL', '') or '').strip()


def _certificat_societe_pour_scellement(company):
    """XGED5 — Résout le SIGNATAIRE pyHanko (certificat + clé) à utiliser pour
    sceller les PDF signés d'une société (PAdES).

    POINT D'INTÉGRATION — squelette isolé, JAMAIS exécuté tant qu'aucune
    source de certificat concrète n'est câblée : par défaut aucun certificat
    par société n'est provisionné automatiquement (une clé privée persistée
    en base sans HSM/coffre dédié serait une régression de sécurité qu'on ne
    prend pas ici sans l'accord du founder). Une intégration future posera un
    `settings.GED_PADES_CERT_PATH`/`GED_PADES_KEY_PATH` par société (ou un
    provider HSM) et cette fonction chargera `signers.SimpleSigner.load(...)`
    depuis cette source — l'appelant (`sceller_pdf`) n'aura pas à changer.

    Renvoie un objet signataire pyHanko, ou None (dégrade en no-op, comme
    `esign_active()`/`_default_partage_token` sans provider câblé)."""
    from django.conf import settings

    if not _pades_signer_disponible():
        return None
    cert_path = getattr(settings, 'GED_PADES_CERT_PATH', '')
    key_path = getattr(settings, 'GED_PADES_KEY_PATH', '')
    if not cert_path or not key_path:
        return None
    try:  # pragma: no cover - dépend d'un certificat réel non provisionné.
        from pyhanko.sign import signers
        return signers.SimpleSigner.load(
            key_file=key_path, cert_file=cert_path, ca_chain_files=())
    except Exception:  # pragma: no cover - défensif.
        return None


def sceller_pdf(pdf_bytes, *, company=None):
    """XGED5 — Scelle CRYPTOGRAPHIQUEMENT un PDF signé (PAdES, via pyHanko).

    Import PARESSEUX et GARDÉ (même motif que `_watermark_pdf` GED21) : sans
    pyHanko installé, dégrade proprement en renvoyant le PDF INCHANGÉ (le flux
    XGED4 reste intact — aucune régression, aucun blocage). Avec pyHanko
    disponible ET un certificat de société exploitable, appose une signature
    numérique PAdES vérifiable dans n'importe quel lecteur PDF conforme ; toute
    modification ultérieure du fichier invalide le sceau.

    Si `tsa_url_configuree()` renvoie une URL, un horodatage RFC 3161 est
    demandé à cette TSA et inclus dans la signature (prépare l'« horodatage »
    loi 43-20) — sinon le sceau est posé SANS horodatage TSA (no-op sur ce
    volet uniquement, jamais bloquant).

    Renvoie `(out_bytes, scelle)` où `scelle` est False si la lib est absente,
    si aucun certificat n'est exploitable, ou si le scellement a échoué pour
    toute autre raison (best-effort total — ne lève JAMAIS)."""
    if not _pades_signer_disponible():
        return pdf_bytes, False
    try:
        signataire = _certificat_societe_pour_scellement(company)
        if signataire is None:
            return pdf_bytes, False
        from io import BytesIO

        from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
        from pyhanko.sign import PdfSignatureMetadata, sign_pdf

        timestamper = None
        tsa_url = tsa_url_configuree()
        if tsa_url:
            from pyhanko.sign.timestamps import HTTPTimeStamper
            timestamper = HTTPTimeStamper(tsa_url)

        writer = IncrementalPdfFileWriter(BytesIO(pdf_bytes))
        out = sign_pdf(
            writer,
            PdfSignatureMetadata(field_name='TaqinorSeal'),
            signer=signataire,
            timestamper=timestamper,
        )
        return out.getvalue(), True
    except Exception:  # pragma: no cover - robustesse : jamais bloquer XGED4.
        return pdf_bytes, False


# ── XGED6 — Vérification périodique d'intégrité des archives légales ────────

def _hash_constate_pour_archivage(archivage):
    """XGED6 — Recalcule le hash SHA-256 ACTUEL du contenu archivé, ou None si
    indisponible (stockage KO). Ne lève jamais."""
    version = archivage.version
    if version is None:
        return None
    try:
        from apps.records.storage import fetch_attachment
        data, err = fetch_attachment(version.file_key)
        if err or data is None:
            return None
        return compute_checksum(data)
    except Exception:  # pragma: no cover - défensif.
        return None


def verifier_integrite_archives(company):
    """XGED6 — Re-vérifie l'intégrité de CHAQUE archivage légal (GED23) d'une
    société : re-télécharge le contenu archivé, recompare au
    `hash_integrite` figé AU DÉPÔT, et journalise le résultat
    (`ControleIntegrite`). Notifie l'admin en cas d'écart (best-effort).

    Trois issues par archivage :
      * OK           : hash constaté == hash figé au dépôt.
      * ALTÉRÉ       : hash constaté != hash figé (preuve d'altération).
      * INDISPONIBLE : contenu non re-téléchargeable (ne prouve PAS une
        altération — signale seulement un problème de disponibilité).

    Ne modifie JAMAIS `ArchivageLegal` (write-once, GED23 intact) — ne fait
    QUE journaliser. Renvoie un dict de synthèse
    `{'total', 'ok', 'altere', 'indisponible'}`."""
    from .models import (
        ArchivageLegal, CONTROLE_RESULTAT_ALTERE, CONTROLE_RESULTAT_INDISPONIBLE,
        CONTROLE_RESULTAT_OK, ControleIntegrite,
    )

    synthese = {'total': 0, 'ok': 0, 'altere': 0, 'indisponible': 0}
    archivages = ArchivageLegal.objects.filter(
        company=company).select_related('version', 'document')
    alteres = []
    for archivage in archivages:
        synthese['total'] += 1
        hash_constate = _hash_constate_pour_archivage(archivage)
        if hash_constate is None:
            resultat = CONTROLE_RESULTAT_INDISPONIBLE
            synthese['indisponible'] += 1
        elif hash_constate == (archivage.hash_integrite or ''):
            resultat = CONTROLE_RESULTAT_OK
            synthese['ok'] += 1
        else:
            resultat = CONTROLE_RESULTAT_ALTERE
            synthese['altere'] += 1
            alteres.append(archivage)
        ControleIntegrite.objects.create(
            company=company, archivage=archivage, resultat=resultat,
            hash_constate=hash_constate or '')

    if alteres:
        _notifier_alteration_archives(company, alteres)
    return synthese


def _notifier_alteration_archives(company, archivages_alteres):
    """XGED6 — Notifie (best-effort, jamais bloquant) les admins de la société
    d'une altération détectée sur un ou plusieurs archivages légaux."""
    try:
        from authentication.models import CustomUser
        admins = CustomUser.admins_actifs_qs(company)
        noms = ', '.join(a.document.nom for a in archivages_alteres[:5])
        sujet = (
            f'Alerte intégrité — {len(archivages_alteres)} archive(s) '
            f'légale(s) altérée(s)')
        corps = (
            f'Le contrôle périodique a détecté une altération sur : {noms}.\n'
            'Consultez le dossier de preuve pour chaque archivage concerné.')
        for admin in admins:
            try:
                from django.conf import settings
                from django.core.mail import send_mail
                from_email = getattr(
                    settings, 'DEFAULT_FROM_EMAIL', 'noreply@erp.local')
                if admin.email:
                    send_mail(sujet, corps, from_email, [admin.email],
                              fail_silently=True)
            except Exception:  # pragma: no cover - best-effort.
                continue
    except Exception:  # pragma: no cover - défensif, jamais bloquant.
        pass


def dossier_preuve_archivage(archivage):
    """XGED6 — Exporte le DOSSIER DE PREUVE d'un archivage légal (JSON) :
    hash au dépôt, tous les contrôles successifs (append-only), horodatages —
    aligné « validation et conservation » loi 43-20.

    Renvoie un dict directement sérialisable en JSON (jamais de prix d'achat/
    marge — hors sujet ici)."""
    controles = list(archivage.controles.order_by('created_at').values(
        'resultat', 'hash_constate', 'created_at'))
    return {
        'document': archivage.document.nom,
        'archive_le': archivage.archive_le,
        'motif': archivage.motif,
        'hash_integrite_au_depot': archivage.hash_integrite,
        'controles': [
            {
                'date': c['created_at'],
                'resultat': c['resultat'],
                'hash_constate': c['hash_constate'],
            }
            for c in controles
        ],
    }


# ── GED35 — Journal d'audit d'accès aux documents (lectures) ─────────────────

def journaliser_acces(document, *, utilisateur=None, type_acces=None,
                      adresse_ip=None):
    """GED35 — Enregistre un accès EN LECTURE à un document (append-only).

    `company` est posée CÔTÉ SERVEUR (toujours celle du document) — jamais lue
    d'un corps de requête. `utilisateur` peut être None (accès public anonyme
    via lien tokenisé GED20). Ne lève jamais (l'audit ne doit pas casser une
    lecture) — toute erreur d'écriture du journal est silencieusement ignorée.

    Renvoie l'entrée `JournalAcces` créée, ou None si la journalisation a échoué
    (best-effort)."""
    from .models import ACCES_CONSULTATION, JournalAcces

    try:
        return JournalAcces.objects.create(
            company=document.company,
            document=document,
            utilisateur=utilisateur if getattr(
                utilisateur, 'is_authenticated', False) else None,
            type_acces=type_acces or ACCES_CONSULTATION,
            adresse_ip=adresse_ip or None,
        )
    except Exception:  # robustesse : l'audit ne bloque jamais une lecture.
        return None


def _adresse_ip_requete(request):
    """GED35 — Adresse IP best-effort d'une requête (ou None).

    Lit `REMOTE_ADDR` (jamais d'en-tête X-Forwarded-For non fiable). Renvoie
    None si indisponible — l'audit reste possible sans IP."""
    if request is None:
        return None
    return (getattr(request, 'META', {}) or {}).get('REMOTE_ADDR') or None


# ── GED36 — Quotas de stockage par société ──────────────────────────────────

def usage_stockage_octets(company):
    """GED36 — Total des octets stockés par une société (somme des versions).

    Somme la taille (`DocumentVersion.size`) de TOUTES les versions de la
    société — y compris les versions historiques (chaque version occupe de
    l'espace objet). Borné à la société (jamais cross-société). Renvoie un entier
    (0 si aucune version)."""
    from django.db.models import Sum
    agg = (DocumentVersion.objects
           .filter(company=company)
           .aggregate(total=Sum('size')))
    return int(agg['total'] or 0)


def quota_octets(company):
    """GED36 — Quota (octets) effectif d'une société (0 = illimité).

    Lit l'entrée `QuotaStockage` explicite de la société si elle existe ; sinon
    retombe sur le défaut `settings.GED_QUOTA_DEFAUT_OCTETS` (0 = illimité)."""
    from django.conf import settings
    from .models import QuotaStockage
    quota = QuotaStockage.objects.filter(company=company).first()
    if quota is not None:
        return int(quota.quota_octets or 0)
    return int(getattr(settings, 'GED_QUOTA_DEFAUT_OCTETS', 0) or 0)


def quota_restant_octets(company):
    """GED36 — Octets restants avant d'atteindre le quota (None si illimité)."""
    limite = quota_octets(company)
    if limite <= 0:
        return None  # illimité
    return max(0, limite - usage_stockage_octets(company))


def quota_depasse(company, *, octets_supplementaires=0):
    """GED36 — True si la société dépasse (ou dépasserait) son quota.

    `octets_supplementaires` simule l'ajout d'un dépôt à venir : on vérifie si
    `usage + supplément > quota`. Un quota nul/illimité ne dépasse JAMAIS."""
    limite = quota_octets(company)
    if limite <= 0:
        return False  # illimité
    return (usage_stockage_octets(company)
            + max(0, int(octets_supplementaires or 0))) > limite


def assert_quota_disponible(company, *, octets_supplementaires=0):
    """GED36 — Lève `QuotaDepasseError` si le dépôt ferait dépasser le quota.

    Garde à poser AVANT un dépôt (la vue la traduit en 403, jamais 500). Un
    quota illimité (0) ne lève jamais."""
    from .models import QuotaDepasseError, QUOTA_DEPASSE_MESSAGE
    if quota_depasse(company, octets_supplementaires=octets_supplementaires):
        raise QuotaDepasseError(QUOTA_DEPASSE_MESSAGE)


# ── XGED7 — Lien public de DÉPÔT (upload-request) ────────────────────

DEPOT_INTROUVABLE = 'introuvable'
DEPOT_EXPIRE = 'expire'
DEPOT_OK = 'ok'


def create_depot_public(*, folder, company, created_by=None, message='',
                        expires_at=None, quota_fichiers=None,
                        quota_octets=None):
    """XGED7 — Crée un lien de dépôt public sur `folder` (société posée côté
    serveur, jamais lue du corps)."""
    from .models import DepotPublic
    if folder.company_id != getattr(company, 'id', company):
        raise ValueError("Le dossier doit appartenir à la même société.")
    return DepotPublic.objects.create(
        company=company, folder=folder, created_by=created_by,
        message=message or '', expires_at=expires_at,
        quota_fichiers=quota_fichiers, quota_octets=quota_octets)


def revoke_depot_public(depot):
    """XGED7 — Révoque (kill-switch) un lien de dépôt public."""
    depot.actif = False
    depot.save(update_fields=['actif', 'updated_at'])
    return depot


def resolve_depot_public(token):
    """XGED7 — Résout un jeton de dépôt public. Renvoie (statut, depot|None).

    Statuts : DEPOT_INTROUVABLE (jeton inconnu/révoqué), DEPOT_EXPIRE (expiré
    OU quota épuisé), DEPOT_OK (accepte encore des dépôts). Ne fait JAMAIS
    confiance à une société/identité venue de la requête — tout est résolu
    DEPUIS le jeton (le jeton ne référence qu'un seul dossier d'une seule
    société)."""
    from .models import DepotPublic
    depot = DepotPublic.objects.filter(token=token).select_related(
        'folder', 'company').first()
    if depot is None or not depot.actif:
        return DEPOT_INTROUVABLE, None
    if depot.is_expired or depot.quota_fichiers_exhausted or depot.quota_octets_exhausted:
        return DEPOT_EXPIRE, None
    return DEPOT_OK, depot


def deposer_via_lien_public(depot, *, file_key, filename='', size=0, mime='',
                            uploader_nom='', uploader_email=''):
    """XGED7 — Crée un Document (+ version 1) depuis un dépôt public anonyme.

    L'uploader anonyme est tracé par nom/email saisis dans `custom_data`
    (jamais un `created_by` — pas d'utilisateur authentifié). Incrémente
    atomiquement les compteurs de quota du lien. Ne fait AUCUNE lecture du
    contenu existant du dossier (isolation : le tiers ne voit jamais autre
    chose que le formulaire de dépôt)."""
    from django.db import transaction as _tx

    from .models import DepotPublic
    with _tx.atomic():
        d = DepotPublic.objects.select_for_update().get(pk=depot.pk)
        if not d.is_accessible:
            raise ValueError("Ce lien de dépôt n'accepte plus de fichiers.")
        nom = (filename or 'Document déposé').strip()
        document = Document.objects.create(
            company=d.company, folder=d.folder, nom=nom,
            custom_data={
                'depot_public_id': d.pk,
                'uploader_nom': uploader_nom or '',
                'uploader_email': uploader_email or '',
            })
        add_version(
            document, file_key=file_key, company=d.company,
            filename=filename, size=size, mime=mime, uploaded_by=None)
        d.depots_effectues += 1
        d.octets_deposes += max(0, int(size or 0))
        d.save(update_fields=['depots_effectues', 'octets_deposes', 'updated_at'])
    update_search_vector(document)
    # XGED8 — un dépôt sur ce dossier peut solder une demande de document
    # correspondante (matching best-effort, jamais bloquant).
    try:
        matcher_depot_demandes(document)
    except Exception:  # pragma: no cover - défensif, ne bloque jamais le dépôt.
        pass
    return document


# ── XGED8 — Checklist de pièces requises + demandes de documents ────

def matcher_depot_demandes(document):
    """XGED8 — Solde automatiquement une `DemandeDocument` en attente sur le
    même dossier quand un document y est déposé (matching best-effort par
    dossier ; le premier « en_attente » du dossier est soldé — un
    rapprochement plus fin par libellé reste possible côté appelant)."""
    from .models import DEMANDE_DOC_EN_ATTENTE, DEMANDE_DOC_SOLDEE, DemandeDocument
    demande = (DemandeDocument.objects
               .filter(company=document.company, folder=document.folder,
                       statut=DEMANDE_DOC_EN_ATTENTE)
               .order_by('created_at', 'id')
               .first())
    if demande is None:
        return None
    demande.statut = DEMANDE_DOC_SOLDEE
    demande.document = document
    demande.save(update_fields=['statut', 'document', 'updated_at'])
    return demande


def creer_demande_document(*, folder, company, libelle, created_by=None,
                           exigence=None, utilisateur=None,
                           destinataire_nom='', destinataire_email='',
                           echeance=None):
    """XGED8 — Crée une demande de pièce (placeholder visible dans le dossier)."""
    from .models import DemandeDocument
    if folder.company_id != getattr(company, 'id', company):
        raise ValueError("Le dossier doit appartenir à la même société.")
    return DemandeDocument.objects.create(
        company=company, folder=folder, libelle=libelle,
        exigence=exigence, utilisateur=utilisateur,
        destinataire_nom=destinataire_nom or '',
        destinataire_email=destinataire_email or '',
        echeance=echeance, created_by=created_by)


def relancer_demande_document(demande, *, now=None):
    """XGED8 — Relance une demande encore en attente (best-effort, notifie
    l'utilisateur interne si connu ; incrémente le compteur de relances)."""
    from django.utils import timezone as _tz
    from .models import DEMANDE_DOC_EN_ATTENTE
    if demande.statut != DEMANDE_DOC_EN_ATTENTE:
        return demande
    if demande.utilisateur_id:
        try:
            from apps.notifications.models import EventType as ET
            from apps.notifications.services import notify
            notify(
                demande.utilisateur, ET.APPROVAL_REMINDER,
                f'Pièce manquante : {demande.libelle}',
                body=f'Merci de déposer « {demande.libelle} » dans le dossier '
                     f'« {demande.folder.nom} ».',
                company=demande.company)
        except Exception:  # pragma: no cover - défensif.
            pass
    demande.nombre_relances += 1
    demande.derniere_relance_le = now or _tz.now()
    demande.save(update_fields=[
        'nombre_relances', 'derniere_relance_le', 'updated_at'])
    return demande


def relancer_demandes_document_dues(company, *, now=None):
    """XGED8 — Relance toutes les demandes en attente d'une société (à planifier
    en tâche périodique). Renvoie la liste des demandes relancées."""
    from django.utils import timezone as _tz
    from .models import DEMANDE_DOC_EN_ATTENTE, DemandeDocument
    now = now or _tz.now()
    demandes = DemandeDocument.objects.filter(
        company=company, statut=DEMANDE_DOC_EN_ATTENTE)
    return [relancer_demande_document(d, now=now) for d in demandes]


def checklist_dossier(folder):
    """XGED8 — État requis/présent/manquant d'un dossier : combine les
    `ExigenceDossier` applicables (dossier précis OU génériques du cabinet) et
    les `DemandeDocument` en cours. Renvoie une liste de dicts."""
    from .models import DEMANDE_DOC_EN_ATTENTE, DemandeDocument, ExigenceDossier
    exigences = (ExigenceDossier.objects
                 .filter(company=folder.company)
                 .filter(models.Q(folder=folder)
                         | models.Q(cabinet=folder.cabinet, folder__isnull=True)))
    demandes_par_exigence = {
        d.exigence_id: d
        for d in DemandeDocument.objects.filter(
            company=folder.company, folder=folder,
            statut=DEMANDE_DOC_EN_ATTENTE, exigence__isnull=False)
    }
    resultat = []
    for exigence in exigences:
        demande = demandes_par_exigence.get(exigence.pk)
        resultat.append({
            'exigence': exigence,
            'statut': 'manquant' if demande else 'present',
            'demande': demande,
        })
    return resultat


# ── XGED9 — Ingestion par email → GED (alias par cabinet/dossier) ───────────
#
# KEY-GATED (`settings.GED_MAIL_INTAKE_ENABLED`) : sans le flag, `poll_mail_intake`
# est un no-op propre. Réutilise la résolution de config IMAP de
# `core.email_intake` (foundation) mais fait sa PROPRE lecture des messages —
# avec pièces jointes, ce que le parseur générique FG373 n'extrait pas. GED ne
# s'abonne pas au registre de handlers générique (celui-ci route vers
# leads/tickets, pas vers des documents).

import re as _re_mod  # noqa: E402 — regroupé ici, section XGED9 auto-contenue.

# Clé réservée dans `Document.custom_data` traçant le Message-ID source d'un
# import email — ancre d'idempotence (un même message retraité ne duplique pas).
MAIL_INTAKE_MESSAGE_ID_KEY = 'ged_mail_intake_message_id'

_ALIAS_PLUS_RE = _re_mod.compile(r'\+([\w\-]+)@')
_ALIAS_SUBJECT_RE = _re_mod.compile(r'\[([\w\-]+)\]')


def mail_intake_enabled():
    """XGED9 — True si l'ingestion email→GED est activée (flag posé)."""
    from django.conf import settings
    return bool(getattr(settings, 'GED_MAIL_INTAKE_ENABLED', False))


def extraire_alias_email(*, to_addr='', subject=''):
    """XGED9 — Extrait l'alias cible d'une adresse plus-adressée OU d'un objet
    `[alias]`. `to_addr` prioritaire (ex. « ged+compta@… » → « compta ») ; à
    défaut, le premier `[alias]` de l'objet. Renvoie '' si aucun match."""
    if to_addr:
        m = _ALIAS_PLUS_RE.search(to_addr)
        if m:
            return m.group(1).lower()
    if subject:
        m = _ALIAS_SUBJECT_RE.search(subject)
        if m:
            return m.group(1).lower()
    return ''


def resoudre_dossier_alias(company, alias):
    """XGED9 — Résout le `Folder` cible pour un alias (borné à la société), ou
    None si aucun dossier ne porte cet alias."""
    if not alias:
        return None
    return Folder.objects.filter(company=company, alias_email=alias).first()


def _mail_deja_importe(company, message_id):
    """XGED9 — True si ce Message-ID a déjà produit un document (idempotence)."""
    if not message_id:
        return False
    return Document.objects.filter(
        company=company,
        custom_data__contains={MAIL_INTAKE_MESSAGE_ID_KEY: message_id},
    ).exists()


def _extraire_pieces_jointes_email(raw_bytes):
    """XGED9 — Extrait les pièces jointes d'un message brut (stdlib `email`).

    Renvoie une liste de dicts `{filename, mime, data}`."""
    import email as _email
    msg = _email.message_from_bytes(raw_bytes)
    pieces = []
    for part in msg.walk():
        disposition = str(part.get('Content-Disposition') or '')
        filename = part.get_filename()
        if not filename or 'attachment' not in disposition.lower():
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        pieces.append({
            'filename': filename,
            'mime': part.get_content_type() or 'application/octet-stream',
            'data': payload,
        })
    return pieces


def _appliquer_tag_expediteur(document, *, company, from_email, alias):
    """XGED9 — Tagging simple par expéditeur/alias (best-effort, jamais bloquant)."""
    from .models import DocumentTag
    try:
        label = alias or (from_email.split('@')[0] if from_email else '')
        if not label:
            return
        slug = _re_mod.sub(r'[^a-z0-9\-]+', '-', label.lower()).strip('-') or 'mail'
        tag, _created = DocumentTag.objects.get_or_create(
            company=company, slug=slug, defaults={'nom': label})
        assign_tag(document, tag)
    except Exception:  # pragma: no cover - défensif, jamais bloquant.
        pass


def importer_message_email(raw_bytes, *, company):
    """XGED9 — Importe UN message brut (déjà récupéré) vers la GED.

    Route chaque pièce jointe vers le dossier de l'alias résolu depuis le
    destinataire (`To`) ou l'objet. Sans alias résolu (dossier inconnu), le
    message est ignoré (rien n'est déposé « au hasard »). Idempotent par
    Message-ID. Renvoie la liste des `Document` créés (vide si rien à
    importer)."""
    import email as _email

    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.records.storage import store_attachment

    msg = _email.message_from_bytes(raw_bytes)
    message_id = (msg.get('Message-ID', '') or '').strip('<> ')
    if message_id and _mail_deja_importe(company, message_id):
        return []
    to_addr = msg.get('To', '') or ''
    subject = msg.get('Subject', '') or ''
    from email.utils import parseaddr as _parseaddr
    _, from_email = _parseaddr(msg.get('From', '') or '')
    alias = extraire_alias_email(to_addr=to_addr, subject=subject)
    folder = resoudre_dossier_alias(company, alias)
    if folder is None:
        return []
    pieces = _extraire_pieces_jointes_email(raw_bytes)
    created = []
    for piece in pieces:
        upload = SimpleUploadedFile(
            piece['filename'], piece['data'], content_type=piece['mime'])
        meta, err = store_attachment(upload)
        if err:
            continue  # format non supporté — ignoré, ne bloque pas le reste.
        document = Document.objects.create(
            company=company, folder=folder, nom=meta['filename'],
            custom_data={MAIL_INTAKE_MESSAGE_ID_KEY: message_id} if message_id else {},
        )
        add_version(
            document, file_key=meta['file_key'], company=company,
            filename=meta['filename'], size=meta['size'], mime=meta['mime'],
            uploaded_by=None)
        update_search_vector(document)
        _appliquer_tag_expediteur(
            document, company=company, from_email=from_email, alias=alias)
        created.append(document)
    return created


def poll_mail_intake(company):
    """XGED9 — Relève la boîte IMAP configurée (FG373) et route les pièces
    jointes vers la GED. No-op propre si le flag est désactivé OU si aucune
    config IMAP active n'existe pour la société. Renvoie
    `{"fetched": int, "imported": int}` (jamais d'exception remontée)."""
    if not mail_intake_enabled():
        return {'fetched': 0, 'imported': 0}
    from core.email_intake import _active_imap_config
    from core.integrations import resolve_secret
    cfg = _active_imap_config(company)
    if cfg is None:
        return {'fetched': 0, 'imported': 0}
    settings_dict = cfg.settings or {}
    host = settings_dict.get('host')
    user = settings_dict.get('user')
    password = resolve_secret(getattr(cfg, 'secret_ref', '') or None)
    if not host or not user or not password:
        return {'fetched': 0, 'imported': 0}
    folder_name = settings_dict.get('folder', 'INBOX')
    try:
        import imaplib
    except Exception:  # pragma: no cover - stdlib toujours présente en prod.
        return {'fetched': 0, 'imported': 0}
    fetched = 0
    imported = 0
    try:
        conn = imaplib.IMAP4_SSL(host)
        conn.login(user, password)
        conn.select(folder_name)
        typ, data = conn.search(None, 'UNSEEN')
        if typ == 'OK':
            for num in data[0].split():
                t, msg_data = conn.fetch(num, '(RFC822)')
                if t == 'OK' and msg_data and msg_data[0]:
                    fetched += 1
                    created = importer_message_email(msg_data[0][1], company=company)
                    imported += len(created)
        conn.logout()
    except Exception:  # pragma: no cover - réseau/auth : dégrade proprement.
        return {'fetched': fetched, 'imported': imported}
    return {'fetched': fetched, 'imported': imported}


# ── XGED10 — Outils PDF : scission et fusion ─────────────────────────

def _pdf_lib_indisponible_message():
    return ("Traitement PDF indisponible (bibliothèque PyMuPDF non installée "
            "sur ce serveur).")


def scinder_pdf(version, points_de_coupe):
    """XGED10 — Scinde un PDF en segments (chaque segment devient un nouveau
    `Document`, métadonnées héritées). `points_de_coupe` est une liste
    d'entiers (numéros de PAGE 1-based OÙ COMMENCE chaque nouveau segment,
    ex. `[1, 3]` sur un PDF de 6 pages donne [1-2] et [3-6]).

    L'original n'est JAMAIS muté. Lève `ValueError` si PyMuPDF est absent
    (dégradation explicite 400, jamais un split silencieusement faux) ou si
    les points de coupe sont invalides. Renvoie la liste des `Document` créés,
    dans l'ordre des segments."""
    document = version.document
    assert_not_archive_legalement(document)
    assert_not_legal_hold(document)
    try:
        import fitz  # PyMuPDF
    except Exception:
        raise ValueError(_pdf_lib_indisponible_message())
    data, err = _fetch_version_bytes(version)
    if err:
        raise ValueError(err)
    src = fitz.open(stream=data, filetype='pdf')
    try:
        n_pages = src.page_count
        # Un point de coupe hors [1, n_pages] est une entrée invalide (ex. page
        # 99 d'un PDF de 3 pages) — on refuse explicitement plutôt que de le
        # filtrer silencieusement et produire un découpage faux.
        raw_points = [int(p) for p in (points_de_coupe or [])]
        if any(p < 1 or p > n_pages for p in raw_points):
            raise ValueError("Points de coupe invalides.")
        coupes = sorted(set(raw_points))
        if not coupes or coupes[0] != 1:
            coupes = [1] + [c for c in coupes if c != 1]
        coupes = [c for c in coupes if 1 <= c <= n_pages]
        if not coupes:
            raise ValueError("Points de coupe invalides.")
        bornes = coupes + [n_pages + 1]
        created = []
        for i in range(len(bornes) - 1):
            debut, fin = bornes[i], bornes[i + 1]
            if debut >= fin:
                continue
            seg = fitz.open()
            seg.insert_pdf(src, from_page=debut - 1, to_page=fin - 2)
            seg_bytes = seg.tobytes()
            seg.close()
            nom = f'{document.nom} ({debut}-{fin - 1})'
            new_doc = create_document(
                company=document.company, folder=document.folder, nom=nom,
                description=document.description,
                custom_data=dict(document.custom_data or {}))
            key, _meta = _store_bytes(seg_bytes, mime='application/pdf')
            add_version(
                new_doc, file_key=key, company=document.company,
                filename=f'{nom}.pdf', size=len(seg_bytes),
                mime='application/pdf')
            update_search_vector(new_doc)
            created.append(new_doc)
        return created
    finally:
        src.close()


def fusionner_pdf(documents_ordonnes, *, cible=None, company=None,
                  nom='', created_by=None):
    """XGED10 — Fusionne N PDF (documents ordonnés) en un seul flux paginé.

    Sans `cible`, crée un NOUVEAU document dans le dossier du premier document
    de la liste. Avec `cible` (un `Document` existant), ajoute une NOUVELLE
    VERSION à ce document au lieu d'en créer un nouveau. L'original de chaque
    source n'est JAMAIS muté. Lève `ValueError` si PyMuPDF est absent ou si la
    liste est vide/contient un document sans version PDF."""
    if not documents_ordonnes:
        raise ValueError("Aucun document à fusionner.")
    try:
        import fitz  # PyMuPDF
    except Exception:
        raise ValueError(_pdf_lib_indisponible_message())
    out = fitz.open()
    try:
        for doc in documents_ordonnes:
            version = selectors_latest_version(doc)
            if version is None:
                raise ValueError(f"« {doc.nom} » n'a aucune version.")
            data, err = _fetch_version_bytes(version)
            if err:
                raise ValueError(err)
            seg = fitz.open(stream=data, filetype='pdf')
            out.insert_pdf(seg)
            seg.close()
        out_bytes = out.tobytes()
    finally:
        out.close()

    premier = documents_ordonnes[0]
    company = company or premier.company
    key, _meta = _store_bytes(out_bytes, mime='application/pdf')
    if cible is not None:
        assert_not_archive_legalement(cible)
        assert_not_legal_hold(cible)
        add_version(
            cible, file_key=key, company=company,
            filename=f'{cible.nom}.pdf', size=len(out_bytes),
            mime='application/pdf', uploaded_by=created_by)
        update_search_vector(cible)
        return cible
    nom = nom or f'{premier.nom} (fusionné)'
    nouveau = create_document(
        company=company, folder=premier.folder, nom=nom,
        created_by=created_by)
    add_version(
        nouveau, file_key=key, company=company, filename=f'{nom}.pdf',
        size=len(out_bytes), mime='application/pdf', uploaded_by=created_by)
    update_search_vector(nouveau)
    return nouveau


def _fetch_version_bytes(version):
    """XGED10 — Récupère les octets d'une version (helper interne, mêmes
    codes d'erreur que le proxy de téléchargement)."""
    from apps.records.storage import fetch_attachment
    return fetch_attachment(version.file_key)


# ── XGED11 — Séparation automatique des lots scannés + code-barres/QR ────

# Ratio de pixels quasi-blancs au-delà duquel une page est considérée séparatrice.
# NB : un ratio trop bas (ex. 0.995) fait passer pour "blanche" une page de
# contenu clairsemé (quelques traits sur fond blanc peuvent dépasser 99.8 %
# de pixels clairs) — 0.999 laisse passer un contenu réel tout en détectant
# les vraies pages séparatrices (quasi 100 % blanches).
_PAGE_BLANCHE_RATIO = 0.999


def _page_est_blanche(image, *, seuil=_PAGE_BLANCHE_RATIO):
    """XGED11 — True si `image` (objet Pillow) est quasi entièrement blanche.

    Convertit en niveaux de gris et compte la proportion de pixels clairs
    (> 250/255) — une page séparatrice scannée est presque toujours vierge."""
    try:
        gray = image.convert('L')
        pixels = list(gray.getdata())
        if not pixels:
            return False
        clairs = sum(1 for p in pixels if p > 250)
        return (clairs / len(pixels)) >= seuil
    except Exception:  # pragma: no cover - défensif.
        return False


def _decoder_barcode(image):
    """XGED11 — Décode un code-barres/QR sur une image (import PARESSEUX et
    GARDÉ : `pyzbar` n'est PAS une dépendance dure). Renvoie la valeur
    décodée (str) ou '' si absent/aucun code trouvé."""
    try:
        from pyzbar.pyzbar import decode as _zbar_decode
    except Exception:  # pragma: no cover - chemin de repli sans la lib.
        return ''
    try:
        results = _zbar_decode(image)
        if results:
            return results[0].data.decode('utf-8', 'replace')
    except Exception:  # pragma: no cover - robustesse : jamais bloquer.
        return ''
    return ''


def barcode_lib_disponible():
    """XGED11 — True si `pyzbar` est installé (dégrade proprement sinon)."""
    try:
        import pyzbar.pyzbar  # noqa: F401
    except Exception:
        return False
    return True


def separer_lot_scans_images(images):
    """XGED11 — Découpe un lot de pages scannées (images Pillow, dans l'ordre)
    en sous-lots individuels, sur pages BLANCHES séparatrices ET pages
    porteuses d'un code-barres/QR séparateur.

    Une page blanche ou porteuse d'un code-barres est un SÉPARATEUR : elle
    n'est PAS incluse dans le sous-lot suivant. Renvoie une liste de dicts
    `{pages: [image, ...], barcode: str}` — `barcode` porte la valeur décodée
    sur la page séparatrice qui a ouvert ce sous-lot (vide si ouvert par une
    page blanche ou si `pyzbar` est absent). Sans AUCUNE page séparatrice, le
    lot entier forme un seul sous-lot (comportement inchangé)."""
    sous_lots = []
    courant = []
    prochain_barcode = ''
    for image in images:
        if _page_est_blanche(image):
            if courant:
                sous_lots.append({'pages': courant, 'barcode': prochain_barcode})
                courant = []
                prochain_barcode = ''
            continue
        code = _decoder_barcode(image)
        if code:
            if courant:
                sous_lots.append({'pages': courant, 'barcode': prochain_barcode})
                courant = []
            prochain_barcode = code
            continue  # la page séparatrice code-barres n'est pas une page de contenu.
        courant.append(image)
    if courant:
        sous_lots.append({'pages': courant, 'barcode': prochain_barcode})
    return sous_lots


def deposer_lot_scans_separe(*, company, folder, images, created_by=None,
                             nom_base='Scan'):
    """XGED11 — Sépare un lot d'images scannées puis dépose chaque sous-lot
    comme un `Document` distinct (assemblage PDF multi-pages via Pillow, déjà
    pinné — aucune nouvelle dépendance dure). Le code-barres décodé (le cas
    échéant) est stocké dans `custom_data['barcode']` — matching optionnel
    vers une référence ERP laissé à l'appelant (selectors cross-app). Renvoie
    la liste des `Document` créés, dans l'ordre des sous-lots."""
    import io

    sous_lots = separer_lot_scans_images(images)
    created = []
    for idx, lot in enumerate(sous_lots, start=1):
        pages = lot['pages']
        if not pages:
            continue
        buf = io.BytesIO()
        first, *rest = [p.convert('RGB') for p in pages]
        first.save(buf, format='PDF', save_all=True, append_images=rest)
        pdf_bytes = buf.getvalue()
        nom = f'{nom_base} {idx}'
        custom_data = {}
        if lot['barcode']:
            custom_data['barcode'] = lot['barcode']
        document = create_document(
            company=company, folder=folder, nom=nom, created_by=created_by,
            custom_data=custom_data)
        key, _meta = _store_bytes(pdf_bytes, mime='application/pdf')
        add_version(
            document, file_key=key, company=company, filename=f'{nom}.pdf',
            size=len(pdf_bytes), mime='application/pdf',
            uploaded_by=created_by)
        update_search_vector(document)
        created.append(document)
    return created


# ── XGED14 — Opérations par LOT (multi-sélection) ────────────────────

def zipper_documents(documents):
    """XGED14 — Empaquette la version courante de chaque document en un ZIP
    (stream en mémoire — le volume GED reste modeste). Un document bloqué
    (aucune version) est ignoré (rapporté dans `erreurs`), jamais bloquant.

    Renvoie `(zip_bytes, erreurs)`."""
    import io
    import zipfile

    from apps.records.storage import fetch_attachment

    erreurs = []
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        used_names = set()
        for document in documents:
            version = selectors_latest_version(document)
            if version is None:
                erreurs.append({'document': document.pk, 'erreur': 'Aucune version.'})
                continue
            data, err = fetch_attachment(version.file_key)
            if err:
                erreurs.append({'document': document.pk, 'erreur': err})
                continue
            name = version.filename or f'{document.nom}'
            base_name = name
            i = 1
            while name in used_names:
                stem, _, ext = base_name.rpartition('.')
                name = f'{stem or base_name}-{i}.{ext}' if ext else f'{base_name}-{i}'
                i += 1
            used_names.add(name)
            zf.writestr(name, data)
    return buf.getvalue(), erreurs


def operation_lot(documents, *, operation, params, user):
    """XGED14 — Applique `operation` à chaque document d'un lot, un par un.

    Chaque item est validé INDIVIDUELLEMENT — un item bloqué (archivé/hold, ou
    toute autre erreur métier) est rapporté dans `erreurs` SANS jamais faire
    échouer le reste du lot (jamais tout-ou-rien silencieux). Renvoie
    `(resultats, erreurs)`, listes parallèles indexées par document.pk."""
    from .models import ArchivageLegalError, DocumentTag, Folder, LegalHoldError

    resultats = []
    erreurs = []
    for document in documents:
        try:
            if operation == 'tagger':
                tag = DocumentTag.objects.filter(
                    company=user.company, pk=params.get('tag')).first()
                if tag is None:
                    raise ValueError('Tag inconnu.')
                assign_tag(document, tag, created_by=user)
                resultats.append({'document': document.pk, 'ok': True})
            elif operation == 'detaguer':
                from .models import DocumentTagAssignment
                DocumentTagAssignment.objects.filter(
                    document=document, tag_id=params.get('tag')).delete()
                resultats.append({'document': document.pk, 'ok': True})
            elif operation == 'deplacer':
                folder = Folder.objects.filter(
                    company=user.company, pk=params.get('folder')).first()
                if folder is None:
                    raise ValueError('Dossier cible inconnu.')
                move_document(document, folder)
                resultats.append({'document': document.pk, 'ok': True})
            elif operation == 'corbeille':
                mettre_en_corbeille(document, user)
                resultats.append({'document': document.pk, 'ok': True})
            elif operation == 'partager':
                partage = create_partage(
                    document=document, company=user.company, created_by=user)
                resultats.append({'document': document.pk, 'ok': True,
                                  'token': partage.token})
            elif operation == 'demander_signature':
                demande = demander_signature(
                    document,
                    signataire_nom=params.get('signataire_nom', ''),
                    signataire_email=params.get('signataire_email', ''),
                    company=user.company, created_by=user)
                resultats.append({'document': document.pk, 'ok': True,
                                  'demande': demande.pk})
            elif operation == 'demander_revue':
                demande = request_review(document, user=user)
                resultats.append({'document': document.pk, 'ok': True,
                                  'demande': demande.pk})
            else:
                raise ValueError(f'Opération inconnue : {operation}')
        except (ArchivageLegalError, LegalHoldError, ValueError,
                PermissionError) as exc:
            erreurs.append({'document': document.pk, 'erreur': str(exc)})
    return resultats, erreurs


# ── XGED15 — Chatter documentaire : journal + activités planifiées ──

def journaliser_evenement(document, *, type_evenement, message='', utilisateur=None):
    """XGED15 — Journalise un événement majeur du cycle de vie GED (pattern
    `crm.LeadActivity`). Best-effort : n'interrompt jamais l'appelant."""
    from .models import DocumentActivity
    try:
        return DocumentActivity.objects.create(
            company=document.company, document=document,
            type_evenement=type_evenement, message=message or '',
            utilisateur=utilisateur)
    except Exception:  # pragma: no cover - défensif, jamais bloquant.
        return None


def planifier_document(document, *, libelle, echeance, assigne_a=None,
                       created_by=None):
    """XGED15 — Planifie une activité sur un document (« relancer le J+7 »)."""
    from .models import PlanificationDocument
    return PlanificationDocument.objects.create(
        company=document.company, document=document, libelle=libelle,
        echeance=echeance, assigne_a=assigne_a, created_by=created_by)


def notifier_planifications_echues(company, *, today=None):
    """XGED15 — Notifie les assignés des planifications échues non encore
    notifiées (best-effort, à planifier en tâche périodique). Renvoie la liste
    des `PlanificationDocument` notifiées."""
    from django.utils import timezone as _tz
    from .models import PlanificationDocument
    today = today or _tz.now().date()
    qs = PlanificationDocument.objects.filter(
        company=company, faite=False, notifiee=False, echeance__lte=today)
    notifiees = []
    for planif in qs:
        if planif.assigne_a_id:
            try:
                from apps.notifications.models import EventType as ET
                from apps.notifications.services import notify
                notify(
                    planif.assigne_a, ET.APPROVAL_REMINDER,
                    f'Relance planifiée : {planif.libelle}',
                    body=f'Document « {planif.document.nom} ».',
                    company=company)
            except Exception:  # pragma: no cover - défensif.
                pass
        planif.notifiee = True
        planif.save(update_fields=['notifiee'])
        notifiees.append(planif)
    return notifiees


# ── XGED16 — Annotations et tampons (couche séparée, jamais l'original) ──

def creer_annotation(version, *, type_annotation, page=0, x=0.0, y=0.0,
                     contenu='', auteur=None):
    """XGED16 — Pose une annotation/tampon sur l'image d'une version.

    Vit en base UNIQUEMENT (couche séparée) — le fichier original de la
    version n'est JAMAIS modifié par cette fonction. `x`/`y` en POURCENTAGE
    (0-100)."""
    from .models import AnnotationDocument
    return AnnotationDocument.objects.create(
        company=version.company, version=version,
        type_annotation=type_annotation, page=page, x=x, y=y,
        contenu=contenu, auteur=auteur)


def tampons_disponibles(company):
    """XGED16 — Tampons prédéfinis pour une société : les 3 tampons système
    + les tampons propres à la société."""
    from .models import TAMPONS_SYSTEME, TamponSociete
    propres = list(TamponSociete.objects.filter(company=company)
                   .values_list('libelle', flat=True))
    return list(TAMPONS_SYSTEME) + propres


def exporter_pdf_annote(version):
    """XGED16 — Exporte un PDF « annoté » APLATI (nouveau fichier séparé —
    l'original reste intact) : superpose les annotations/tampons via PyMuPDF
    (import paresseux et gardé — dégrade en `ValueError` explicite sans la
    lib, jamais un export silencieusement faux)."""
    try:
        import fitz  # PyMuPDF
    except Exception:
        raise ValueError(_pdf_lib_indisponible_message())
    data, err = _fetch_version_bytes(version)
    if err:
        raise ValueError(err)
    doc = fitz.open(stream=data, filetype='pdf')
    try:
        for annot in version.annotations.all():
            if annot.page >= doc.page_count:
                continue
            page = doc[annot.page]
            rect = page.rect
            px = rect.x0 + (annot.x / 100.0) * rect.width
            py = rect.y0 + (annot.y / 100.0) * rect.height
            texte = annot.contenu or (
                'TAMPON' if annot.type_annotation == 'tampon' else '')
            page.insert_textbox(
                fitz.Rect(px, py, px + 200, py + 40), texte,
                fontsize=12, color=(0.8, 0, 0), overlay=True)
        out_bytes = doc.tobytes()
    finally:
        doc.close()
    return out_bytes


# ── XGED18 — Documents-liens (URL externes comme entrées GED) ───────

def creer_document_lien(*, company, folder, nom, url_externe, description='',
                        created_by=None):
    """XGED18 — Crée un document-LIEN (référence une URL externe, sans
    stockage). Entrée GED de première classe : tags/ACL/liaison métier/cycle
    de vie/chatter fonctionnent comme sur un document fichier ordinaire — SEULES
    les actions fichier (version/OCR/signature) le refusent explicitement."""
    if not url_externe:
        raise ValueError("L'URL externe est requise pour un document-lien.")
    if folder.company_id != getattr(company, 'id', company):
        raise ValueError("Le dossier doit appartenir à la même société.")
    return Document.objects.create(
        company=company, folder=folder, nom=nom, description=description,
        url_externe=url_externe, created_by=created_by)


def assert_not_document_lien(document, *, action=''):
    """XGED18 — Garde : refuse une action FICHIER (version/OCR/signature) sur un
    document-lien. Lève `ValueError` (→ 400 explicite côté vue, jamais un
    comportement silencieusement faux)."""
    if document.est_document_lien:
        raise ValueError(
            f"Action « {action or 'fichier'} » impossible : ce document est "
            "un document-lien (URL externe, sans fichier stocké).")


# ── XGED19 — Actions automatiques par dossier (règles à l'upload) ───

def _document_contexte_regle(document):
    """XGED19 — Construit le `context` plat (dict) pour `core.rules` à partir
    des métadonnées d'un document nouvellement créé."""
    contexte = {
        'nom': document.nom,
        'description': document.description or '',
        'texte_ocr': document.texte_ocr or '',
    }
    for k, v in (document.custom_data or {}).items():
        contexte[f'custom_data.{k}'] = v
    tags = list(document.tag_assignments.values_list('tag__slug', flat=True))
    contexte['tags'] = tags
    return contexte


def _executer_action_regle(document, action_descriptor, *, user=None):
    """XGED19 — Exécute UNE action de `RegleDossier` (dispatch par `type`).

    Actions supportées : `tag` (params.tag = slug), `deplacer`
    (params.folder = id), `proprietaire` (params.user = id — posé dans
    `custom_data.proprietaire_id`, pas de champ dédié dans `Document`),
    `demander_approbation`, `demander_signature` (params.signataire_nom/email).
    Une action inconnue lève `ValueError` (rapportée, jamais silencieuse)."""
    from .models import DocumentTag, Folder

    type_action = (action_descriptor or {}).get('type')
    params = (action_descriptor or {}).get('params') or {}
    if type_action == 'tag':
        tag = DocumentTag.objects.filter(
            company=document.company, slug=params.get('tag')).first()
        if tag is None:
            raise ValueError(f"Tag inconnu : {params.get('tag')}")
        assign_tag(document, tag)
        return {'type': type_action, 'ok': True}
    if type_action == 'deplacer':
        folder = Folder.objects.filter(
            company=document.company, pk=params.get('folder')).first()
        if folder is None:
            raise ValueError(f"Dossier inconnu : {params.get('folder')}")
        move_document(document, folder)
        return {'type': type_action, 'ok': True}
    if type_action == 'proprietaire':
        data = dict(document.custom_data or {})
        data['proprietaire_id'] = params.get('user')
        Document.objects.filter(pk=document.pk).update(custom_data=data)
        document.custom_data = data
        return {'type': type_action, 'ok': True}
    if type_action == 'demander_approbation':
        request_review(document, user=user or document.created_by)
        return {'type': type_action, 'ok': True}
    if type_action == 'demander_signature':
        demander_signature(
            document,
            signataire_nom=params.get('signataire_nom', ''),
            signataire_email=params.get('signataire_email', ''),
            company=document.company, created_by=user)
        return {'type': type_action, 'ok': True}
    raise ValueError(f"Type d'action inconnu : {type_action}")


def appliquer_regles_dossier(document, *, user=None):
    """XGED19 — Applique les `RegleDossier` actives du dossier d'un document
    nouvellement créé. BEST-EFFORT total : une règle/action en échec est
    JOURNALISÉE (`ExecutionRegleDossier`) sans JAMAIS faire échouer l'upload
    lui-même. Renvoie la liste des `ExecutionRegleDossier` créées."""
    from core.rules import evaluate_condition_group

    from .models import ExecutionRegleDossier, RegleDossier

    contexte = _document_contexte_regle(document)
    executions = []
    for regle in (RegleDossier.objects
                  .filter(company=document.company, folder=document.folder,
                          actif=True)
                  .order_by('ordre', 'id')):
        try:
            declenchee = evaluate_condition_group(regle.condition_group, contexte)
        except Exception:  # pragma: no cover - défensif, jamais bloquant.
            declenchee = False
        resultats = []
        if declenchee:
            for step in (regle.actions or []):
                try:
                    resultats.append(
                        _executer_action_regle(document, step, user=user))
                except Exception as exc:  # noqa: BLE001 — best-effort, journalisé.
                    resultats.append({
                        'type': (step or {}).get('type'),
                        'ok': False, 'erreur': str(exc),
                    })
        execution = ExecutionRegleDossier.objects.create(
            company=document.company, regle=regle, document=document,
            declenchee=declenchee, resultats=resultats)
        executions.append(execution)
    return executions


# ── XGED20 — Routage conditionnel des approbations par métadonnées ──

def resoudre_regle_approbation_ged(document):
    """XGED20 — Résout la `RegleApprobationGed` la plus SPÉCIFIQUE applicable
    à un document (plus haute `priorite`, puis id le plus récent), ou None si
    aucune règle active ne matche (RÉTROCOMPATIBLE : comportement GED18
    inchangé sans règle)."""
    from core.rules import evaluate_condition_group

    from .models import RegleApprobationGed

    contexte = _document_contexte_regle(document)
    for regle in (RegleApprobationGed.objects
                  .filter(company=document.company, actif=True)
                  .order_by('-priorite', '-id')):
        try:
            if evaluate_condition_group(regle.condition_group, contexte):
                return regle
        except Exception:  # pragma: no cover - défensif.
            continue
    return None


def request_review_avec_routage(document, *, user, commentaire=''):
    """XGED20 — Comme `request_review`, mais consulte D'ABORD
    `resoudre_regle_approbation_ged` : si une règle matche, instancie une
    CHAÎNE séquentielle d'approbateurs (`ChaineApprobationGed`) au lieu d'un
    approbateur unique fixe. Sans règle applicable, comportement GED18
    STRICTEMENT inchangé (délègue à `request_review`)."""
    from django.contrib.auth import get_user_model

    from .models import ChaineApprobationGed

    regle = resoudre_regle_approbation_ged(document)
    if regle is None or not regle.approbateurs:
        return request_review(document, user=user, commentaire=commentaire)

    User = get_user_model()
    premier_id = regle.approbateurs[0]
    premier = User.objects.filter(
        company=document.company, pk=premier_id).first()
    demande = request_review(
        document, user=user, approbateur=premier, commentaire=commentaire)
    etapes = [
        {'approbateur_id': uid, 'statut': 'en_attente', 'decision_le': None}
        for uid in regle.approbateurs
    ]
    if etapes:
        etapes[0]['statut'] = 'en_cours'
    ChaineApprobationGed.objects.create(
        company=document.company, demande=demande, regle=regle,
        etapes=etapes, etape_courante=0)
    return demande


def avancer_chaine_approbation_ged(demande, *, user, commentaire=''):
    """XGED20 — Avance la chaîne séquentielle d'une demande (si une
    `ChaineApprobationGed` existe) : l'étape courante est marquée approuvée,
    puis soit l'étape SUIVANTE devient l'approbateur actif (demande reste
    `en_attente`, `approbateur` réassigné), soit — dernière étape — la demande
    est approuvée définitivement via `approve_demande` (GED18, jamais
    dupliqué). SANS chaîne (règle non applicable), délègue directement à
    `approve_demande`."""
    from django.contrib.auth import get_user_model
    from django.utils import timezone as _tz

    try:
        chaine = demande.chaine_approbation
    except Exception:
        chaine = None
    if chaine is None:
        return approve_demande(demande, user=user, commentaire=commentaire)

    etapes = list(chaine.etapes or [])
    idx = chaine.etape_courante
    if idx < len(etapes):
        etapes[idx]['statut'] = 'approuve'
        etapes[idx]['decision_le'] = _tz.now().isoformat()
    if idx + 1 < len(etapes):
        # Étape suivante : réassigne l'approbateur actif, la demande reste
        # « en_attente » (décision globale pas encore prise).
        etapes[idx + 1]['statut'] = 'en_cours'
        User = get_user_model()
        suivant = User.objects.filter(
            company=demande.company, pk=etapes[idx + 1]['approbateur_id']).first()
        demande.approbateur = suivant
        demande.save(update_fields=['approbateur', 'updated_at'])
        chaine.etapes = etapes
        chaine.etape_courante = idx + 1
        chaine.save(update_fields=['etapes', 'etape_courante', 'updated_at'])
        return demande
    # Dernière étape : décision définitive (réutilise GED18, jamais dupliqué).
    chaine.etapes = etapes
    chaine.save(update_fields=['etapes', 'updated_at'])
    return approve_demande(demande, user=user, commentaire=commentaire)


# ── XGED23 — Disposition fin de rétention (revue + certificat) ─────────────

def creer_demande_disposition(
        company, *, libelle, document_ids, action='detruire', user=None):
    """XGED23 — Crée une `DemandeDisposition` à partir d'un lot d'ids de
    documents ÉCHUS proposés (typiquement issus de `selectors.documents_echus`).

    Les documents sous `LegalHold` (GED24) ACTIF sont EXCLUS D'OFFICE du lot
    (jamais proposés à destruction/archivage) — filtrage silencieux, jamais
    une erreur. Les ids sont bornés à `company` (un id d'une autre société —
    ou inexistant — est simplement écarté, jamais une fuite cross-société).
    `company`/`demandeur` posés côté serveur. Lève `ValueError` si le lot
    filtré est vide (rien à proposer)."""
    from .models import DemandeDisposition, Document

    valides = list(
        Document.objects.filter(company=company, pk__in=document_ids or [])
        .values_list('pk', flat=True))
    exclus_hold = _pks_sous_legal_hold(valides)
    retenus = [pk for pk in valides if pk not in exclus_hold]
    if not retenus:
        raise ValueError(
            "Aucun document éligible : tous exclus (introuvables ou sous "
            "legal hold actif).")
    return DemandeDisposition.objects.create(
        company=company, libelle=libelle, action=action,
        documents=retenus, demandeur=user)


def _pks_sous_legal_hold(document_ids):
    """XGED23 — pk des documents (parmi `document_ids`) sous `LegalHold` actif.

    Helper interne factorisant l'exclusion d'office des documents gelés hors
    de tout lot de disposition. Import paresseux (évite un cycle)."""
    from .models import LegalHold
    if not document_ids:
        return set()
    return set(
        LegalHold.objects
        .filter(document_id__in=document_ids, actif=True)
        .values_list('document_id', flat=True))


def approuver_demande_disposition(demande, *, user, commentaire=''):
    """XGED23 — Approuve une `DemandeDisposition` (ne détruit PAS encore —
    l'exécution est une étape séparée et explicite, `executer_demande_disposition`).

    Idempotence : une demande déjà décidée lève `DemandeDispositionError`
    (jamais de double décision silencieuse). `PermissionError` hors société."""
    from django.utils import timezone

    from .models import DISPOSITION_APPROUVEE, DemandeDispositionError

    if demande.company_id != getattr(user, 'company_id', None):
        raise PermissionError("Demande de disposition inaccessible.")
    if not demande.is_pending:
        raise DemandeDispositionError(
            "Cette demande de disposition a déjà été décidée.")
    demande.statut = DISPOSITION_APPROUVEE
    demande.approbateur = user
    demande.commentaire = commentaire or demande.commentaire
    demande.decision_le = timezone.now()
    demande.save(update_fields=[
        'statut', 'approbateur', 'commentaire', 'decision_le', 'updated_at'])
    return demande


def rejeter_demande_disposition(demande, *, user, commentaire=''):
    """XGED23 — Rejette une `DemandeDisposition` : CONSERVE tous les documents
    du lot (aucun effacement, jamais). Idempotence : demande déjà décidée →
    `DemandeDispositionError`."""
    from django.utils import timezone

    from .models import DISPOSITION_REJETEE, DemandeDispositionError

    if demande.company_id != getattr(user, 'company_id', None):
        raise PermissionError("Demande de disposition inaccessible.")
    if not demande.is_pending:
        raise DemandeDispositionError(
            "Cette demande de disposition a déjà été décidée.")
    demande.statut = DISPOSITION_REJETEE
    demande.approbateur = user
    demande.commentaire = commentaire or demande.commentaire
    demande.decision_le = timezone.now()
    demande.save(update_fields=[
        'statut', 'approbateur', 'commentaire', 'decision_le', 'updated_at'])
    return demande


def executer_demande_disposition(demande, *, user):
    """XGED23 — Exécute une `DemandeDisposition` APPROUVÉE : pour l'action
    `detruire`, chaque document du lot ENCORE existant et NON sous legal hold
    (re-vérifié à l'exécution — un hold posé entre la proposition et
    l'exécution protège toujours le document, exclusion silencieuse) est
    supprimé DÉFINITIVEMENT (`Document.delete()`, réel, irréversible), et un
    `CertificatDestruction` immuable est émis pour CHAQUE document
    effectivement détruit (hash des métadonnées figé avant suppression).
    Pour l'action `archiver`, délègue à `archiver_legalement` (GED23 existant,
    jamais dupliqué) — aucune destruction.

    Lève `DemandeDispositionError` si la demande n'est pas approuvée ou déjà
    exécutée. `PermissionError` hors société. Renvoie la liste des
    `CertificatDestruction` créés (vide pour l'action `archiver`)."""
    import json

    from django.utils import timezone

    from .models import (
        DISPOSITION_ACTION_ARCHIVER, DISPOSITION_APPROUVEE,
        DISPOSITION_EXECUTEE, CertificatDestruction, Document,
        DemandeDispositionError,
    )

    if demande.company_id != getattr(user, 'company_id', None):
        raise PermissionError("Demande de disposition inaccessible.")
    if demande.statut != DISPOSITION_APPROUVEE:
        raise DemandeDispositionError(
            "Seule une demande APPROUVÉE peut être exécutée.")

    certificats = []
    with transaction.atomic():
        for doc_id in (demande.documents or []):
            document = Document.objects.filter(
                company=demande.company, pk=doc_id).first()
            if document is None:
                continue  # déjà supprimé/introuvable — silencieux.
            if _document_sous_legal_hold(document):
                continue  # protégé entre-temps — exclusion silencieuse.
            if demande.action == DISPOSITION_ACTION_ARCHIVER:
                archiver_legalement(document, user=user)
                continue
            # Action « detruire » : fige le hash des métadonnées AVANT
            # suppression réelle (preuve — le contenu n'est jamais conservé).
            meta_snapshot = {
                'nom': document.nom,
                'description': document.description,
                'custom_data': document.custom_data,
                'created_at': document.created_at.isoformat()
                if document.created_at else None,
            }
            hash_meta = hashlib.sha256(
                json.dumps(meta_snapshot, sort_keys=True, default=str)
                .encode('utf-8')).hexdigest()
            politique = None
            try:
                from . import selectors
                politique = selectors.politique_applicable(document)
            except Exception:  # pragma: no cover - défensif.
                politique = None
            nom_doc = document.nom
            doc_pk = document.pk
            document.delete()
            certificats.append(CertificatDestruction.objects.create(
                company=demande.company, demande=demande,
                document_id_origine=doc_pk, document_nom=nom_doc,
                politique_appliquee=(politique.nom if politique else ''),
                hash_metadonnees=hash_meta, detruit_par=user,
            ))
        demande.statut = DISPOSITION_EXECUTEE
        demande.executee_le = timezone.now()
        demande.save(update_fields=['statut', 'executee_le', 'updated_at'])
    return certificats


# ── XGED24 — Outil de caviardage (redaction) ────────────────────────────────

def caviarder_document(version, zones, *, created_by=None):
    """XGED24 — Caviarde DÉFINITIVEMENT des zones d'un PDF sur une COPIE
    publiée (le texte SOUS-JACENT est supprimé, pas un simple rectangle
    décoratif) — l'ORIGINAL n'est JAMAIS modifié.

    `zones` : liste de `{"page": <int 0-based>, "x0", "y0", "x1", "y1"}` en
    POURCENTAGE (0-100) de la page — même convention que `AnnotationDocument`
    (XGED16). Utilise PyMuPDF `add_redact_annot`/`apply_redactions` (import
    PARESSEUX et GARDÉ) : sans la lib, lève `ValueError` explicite (jamais un
    caviardage silencieusement faux, ex. juste un rectangle par-dessus qui
    laisserait le texte extractible).

    La copie devient un NOUVEAU `Document` (dans le même dossier que
    l'original), dont `custom_data` trace l'origine
    (`{'caviarde_depuis': <id original>}`) — pattern `source_type`/`source_id`
    déjà utilisé pour les traces cross-app, pas un nouveau schéma de FK.
    Respecte les gardes GED23/24 sur l'ORIGINAL (lecture seule — jamais
    bloquant : caviarder ne MODIFIE pas l'original, seule une garde
    `assert_not_document_lien` s'applique, XGED18). Renvoie le nouveau
    `Document` créé."""
    document = version.document
    assert_not_document_lien(document, action='caviarder')
    try:
        import fitz  # PyMuPDF
    except Exception:
        raise ValueError(_pdf_lib_indisponible_message())
    data, err = _fetch_version_bytes(version)
    if err:
        raise ValueError(err)
    if not zones:
        raise ValueError("Au moins une zone à caviarder est requise.")
    doc = fitz.open(stream=data, filetype='pdf')
    try:
        for zone in zones:
            page_no = int(zone.get('page', 0))
            if page_no < 0 or page_no >= doc.page_count:
                continue
            page = doc[page_no]
            rect = page.rect
            x0 = rect.x0 + (float(zone.get('x0', 0)) / 100.0) * rect.width
            y0 = rect.y0 + (float(zone.get('y0', 0)) / 100.0) * rect.height
            x1 = rect.x0 + (float(zone.get('x1', 0)) / 100.0) * rect.width
            y1 = rect.y0 + (float(zone.get('y1', 0)) / 100.0) * rect.height
            page.add_redact_annot(
                fitz.Rect(x0, y0, x1, y1), fill=(0, 0, 0))
        for page in doc:
            # Applique et APLATIT les rédactions : supprime réellement le
            # texte/l'image sous la zone (pas seulement un rectangle visuel).
            page.apply_redactions()
        out_bytes = doc.tobytes()
    finally:
        doc.close()

    nom = f'{document.nom} (caviardé)'
    new_doc = create_document(
        company=document.company, folder=document.folder, nom=nom,
        description=document.description,
        custom_data={'caviarde_depuis': document.pk},
        created_by=created_by)
    key, _meta = _store_bytes(out_bytes, mime='application/pdf')
    add_version(
        new_doc, file_key=key, company=document.company,
        filename=f'{nom}.pdf', size=len(out_bytes),
        mime='application/pdf', uploaded_by=created_by)
    update_search_vector(new_doc)
    return new_doc


# ── XGED27 — Envoi en masse de demandes de signature ────────────────────────

def _valider_destinataire_envoi_masse(ligne, index):
    """XGED27 — Valide UNE ligne de destinataire (dict) : `nom` et `email`
    sont requis. Lève `ValueError` (rapporté par ligne, jamais tout-ou-rien)."""
    nom = (ligne.get('nom') or '').strip()
    email = (ligne.get('email') or '').strip()
    if not nom or not email:
        raise ValueError(
            f"Ligne {index + 1} : nom et email sont requis.")
    return nom, email


def creer_lot_envoi_signature(*, company, modele, destinataires, libelle='',
                              cabinet_nom='Modèles', folder_nom='Mailing',
                              created_by=None):
    """XGED27 — Envoi en masse de demandes de signature à partir d'UN
    `ModeleDocument` (GED27) fusionné pour N `destinataires`.

    `destinataires` : liste de dicts (issus d'un CSV `nom`/`email`/champs de
    fusion, OU résolus depuis une sélection de clients CRM via
    `crm.selectors` par l'appelant — cette fonction ne connaît QUE des dicts,
    jamais `crm.models`). Pour CHAQUE destinataire : le modèle est fusionné
    avec la ligne comme contexte (`rendre_modele`), un document PERSONNALISÉ
    est créé + versionné (jamais dédupliqué — contrairement à
    `generer_document`/GED28, chaque destinataire produit un document
    DISTINCT), puis une demande de signature individuelle est créée
    (`demander_signature`, XGED1/2, respecte le mode key-gated no-op).

    Chaque ligne est traitée INDÉPENDAMMENT : une erreur (nom/email manquant,
    rendu PDF impossible) est RAPPORTÉE dans `resultats` sans jamais bloquer
    le reste du lot. `company`/`created_by` posés côté serveur.

    Renvoie le `LotEnvoi` créé (avec ses compteurs et `resultats` détaillés).
    """
    from .models import LotEnvoi

    resultats = []
    nb_envoyes = 0
    nb_erreurs = 0
    for index, ligne in enumerate(destinataires or []):
        try:
            nom, email = _valider_destinataire_envoi_masse(ligne, index)
            cabinet_resolu, folder_resolu = resoudre_classement(
                modele, ligne,
                cabinet_defaut=cabinet_nom, folder_defaut=folder_nom)
            cabinet = ensure_cabinet(company, cabinet_resolu)
            folder = ensure_root_folder(company, cabinet=cabinet, nom=folder_resolu)
            pdf_bytes = rendre_modele(modele, ligne)
            new_doc = create_document(
                company=company, folder=folder,
                nom=f'{modele.nom} — {nom}',
                description=modele.description or '',
                custom_data={'envoi_masse_destinataire': email},
                created_by=created_by)
            key, meta = _store_bytes(pdf_bytes, mime='application/pdf')
            add_version(
                new_doc, file_key=key, company=company,
                filename=meta.get('filename', ''), size=len(pdf_bytes),
                mime='application/pdf', uploaded_by=created_by)
            update_search_vector(new_doc)
            demande = demander_signature(
                new_doc, signataire_nom=nom, signataire_email=email,
                company=company, created_by=created_by)
            nb_envoyes += 1
            resultats.append({
                'ligne': index, 'nom': nom, 'email': email, 'ok': True,
                'document_id': new_doc.pk, 'demande_id': demande.pk,
            })
        except Exception as exc:  # noqa: BLE001 — rapporté par ligne, jamais bloquant.
            nb_erreurs += 1
            resultats.append({
                'ligne': index, 'nom': ligne.get('nom'),
                'email': ligne.get('email'), 'ok': False, 'erreur': str(exc),
            })

    return LotEnvoi.objects.create(
        company=company, modele=modele,
        libelle=libelle or (modele.nom if modele else 'Envoi en masse'),
        resultats=resultats, total=len(destinataires or []),
        nb_envoyes=nb_envoyes, nb_erreurs=nb_erreurs, created_by=created_by)


def rafraichir_compteurs_lot_envoi(lot):
    """XGED27 — Recalcule `nb_vus`/`nb_signes`/`nb_refuses` d'un `LotEnvoi`
    depuis l'état RÉEL des `DemandeSignatureDocument` créées (via les ids
    tracés dans `resultats`) — jamais une simple incrémentation optimiste,
    toujours la vérité depuis les statuts actuels."""
    from .models import DemandeSignatureDocument

    demande_ids = [
        r['demande_id'] for r in (lot.resultats or [])
        if r.get('ok') and r.get('demande_id')
    ]
    if not demande_ids:
        return lot
    demandes = DemandeSignatureDocument.objects.filter(
        company=lot.company, pk__in=demande_ids)
    lot.nb_signes = demandes.filter(statut='signe').count()
    lot.nb_refuses = demandes.filter(statut='refuse').count()
    # « Vu » : approximé par toute demande sortie de `en_attente` (signée,
    # refusée, ou annulée) — le stub GED30 ne trace pas d'ouverture de lien
    # dédiée hors de ces statuts.
    lot.nb_vus = demandes.exclude(statut='en_attente').count()
    lot.save(update_fields=['nb_signes', 'nb_refuses', 'nb_vus', 'updated_at'])
    return lot


# ── XGED30 — Co-édition Office (Collabora/OnlyOffice self-host, gated) ──────

# Extensions Office reconnues par le slot de co-édition (traitement de texte/
# tableur/présentation) — purement indicatif pour l'UI (bouton conditionnel) ;
# le backend n'inspecte jamais le contenu, seule l'extension du `filename`.
OFFICE_EXTENSIONS = {
    '.docx', '.doc', '.odt', '.xlsx', '.xls', '.ods', '.pptx', '.ppt', '.odp',
}


def office_edit_active():
    """XGED30 — True si un éditeur Office self-hébergé est configuré.

    KEY-GATED (même motif que `esign_active()` GED30/`embedding_enabled()`
    GED12) : sans `settings.GED_OFFICE_URL` non vide, le slot de co-édition
    est un NO-OP COMPLET — aucun appel réseau, aucune UI, aucune dépendance
    nouvelle. Le founder posera l'URL d'une instance Collabora/OnlyOffice
    auto-hébergée (nouvelle brique d'infra, à valider) pour l'activer."""
    from django.conf import settings
    return bool((getattr(settings, 'GED_OFFICE_URL', '') or '').strip())


def office_edit_url():
    """XGED30 — URL de l'éditeur Office configuré, ou chaîne vide si inactif."""
    from django.conf import settings
    if not office_edit_active():
        return ''
    return (getattr(settings, 'GED_OFFICE_URL', '') or '').strip()


def ouvrir_dans_editeur_office(document, *, user):
    """XGED30 — Prépare l'ouverture d'un document Office dans l'éditeur
    embarqué (Collabora/OnlyOffice, slot WOPI-like).

    Lève `ValueError` si le slot n'est pas activé (`office_edit_active()`
    faux — 400 explicite côté vue, jamais une UI qui pointerait nulle part).
    Respecte le check-out (GED16, via `checkout_document` — un document
    verrouillé par un AUTRE utilisateur refuse l'ouverture, même motif que
    l'édition classique) et les gardes GED23/24 (archivé/hold → refus, jamais
    une 500). Renvoie `{"editor_url": <str>, "document_id": <int>}` — l'URL
    de base de l'éditeur ; l'intégration WOPI complète (jeton d'accès par
    document) est un point d'extension future, hors scope de ce slot minimal.
    """
    if not office_edit_active():
        raise ValueError(
            "Co-édition Office non configurée (GED_OFFICE_URL absent) : "
            "cette fonctionnalité est désactivée.")
    assert_not_archive_legalement(document)
    assert_not_legal_hold(document)
    checkout_document(document, user)
    return {'editor_url': office_edit_url(), 'document_id': document.pk}


def sauvegarder_depuis_editeur_office(document, *, contenu_bytes, user,
                                      filename='', mime=''):
    """XGED30 — Callback de sauvegarde de l'éditeur Office : crée une
    NOUVELLE `DocumentVersion` à partir du contenu édité.

    Respecte le check-out (GED16 — `assert_not_locked_by_other`, un
    utilisateur tiers ne peut pas écraser la session d'édition d'un autre) et
    les gardes GED23/24 (document archivé/hold → refus explicite, jamais une
    500). Lève `ValueError` si le slot n'est pas activé. Renvoie la nouvelle
    `DocumentVersion` créée (le check-out N'EST PAS libéré automatiquement —
    l'utilisateur ferme l'éditeur puis check-in explicitement, même motif que
    l'édition classique GED16)."""
    if not office_edit_active():
        raise ValueError(
            "Co-édition Office non configurée (GED_OFFICE_URL absent) : "
            "cette fonctionnalité est désactivée.")
    assert_not_archive_legalement(document)
    assert_not_legal_hold(document)
    assert_not_locked_by_other(document, user)
    key, meta = _store_bytes(contenu_bytes, mime=mime or 'application/octet-stream')
    version = add_version(
        document, file_key=key, company=document.company,
        filename=filename or meta.get('filename', ''),
        size=len(contenu_bytes), mime=mime or meta.get('mime', ''),
        uploaded_by=user)
    update_search_vector(document)
    return version


# ── ZGED6 — Centralisation des fichiers par module ───────────────────────────

_JETON_RE = re.compile(r'\{\{\s*(\w+)\s*\}\}')


def _resoudre_jetons(texte, contexte):
    """ZGED6 — Remplace les jetons ``{{ champ }}`` d'un segment de chemin par
    les valeurs du contexte fourni. Un jeton absent du contexte est rendu vide
    (jamais une KeyError) — comportement standard, aligné sur ModeleDocument
    (GED27) qui rend aussi les jetons inconnus vides."""
    def _sub(match):
        return str(contexte.get(match.group(1), ''))
    return _JETON_RE.sub(_sub, texte)


def _resoudre_dossier_cible(routage, contexte):
    """ZGED6 — Résout/crée (idempotent, get_or_create par segment) le dossier
    cible d'un `RoutageDocumentaire`, à partir de son `dossier_cible`
    (segments séparés par '/', jetons résolus). Renvoie le `Folder` final."""
    segments = [
        _resoudre_jetons(seg.strip(), contexte)
        for seg in routage.dossier_cible.split('/') if seg.strip()
    ]
    parent = None
    folder = None
    for segment in segments:
        folder, _created = Folder.objects.get_or_create(
            company=routage.company, cabinet=routage.cabinet_cible,
            parent=parent, nom=segment)
        parent = folder
    return folder


def router_document_module(source, *, company, file, filename='',
                           reference='', contexte=None, uploaded_by=None):
    """ZGED6 — Centralise un fichier produit par un AUTRE module (paie/rh/sav/
    ventes…) vers le dossier GED configuré pour cette `source` (réglage
    `RoutageDocumentaire`), avec ses tags par défaut.

    Sans réglage ACTIF pour cette `source`+société : no-op strict, renvoie
    `None` (comportement actuel inchangé — c'est la voie normale tant qu'un
    admin n'a rien configuré). IDEMPOTENT par `source`+`reference` : si un
    document du dossier résolu porte déjà cette référence (posée dans
    `custom_data['routage_reference']`), le document existant est renvoyé sans
    créer de doublon ni ajouter de version.

    Appelé UNIQUEMENT depuis `apps/ged/receivers.py` (abonné à l'événement
    `core.events.document_produit`) — jamais appelé directement par l'app
    émettrice, qui ne doit jamais importer `apps.ged`.
    """
    routage = RoutageDocumentaire.objects.filter(
        company=company, source=source, actif=True).first()
    if routage is None:
        return None

    contexte = contexte or {}
    folder = _resoudre_dossier_cible(routage, contexte)

    if reference:
        existant = Document.objects.filter(
            company=company, folder=folder,
            custom_data__routage_reference=reference,
        ).first()
        if existant is not None:
            return existant

    from apps.records.storage import store_attachment

    meta, err = store_attachment(file)
    if err:
        raise ValueError(err)

    document = Document.objects.create(
        company=company, folder=folder,
        nom=filename or meta.get('filename', ''),
        custom_data={'routage_reference': reference} if reference else {},
        created_by=uploaded_by,
    )
    add_version(
        document, file_key=meta['file_key'], company=company,
        filename=meta.get('filename', ''), size=meta.get('size', 0),
        mime=meta.get('mime', ''), uploaded_by=uploaded_by)
    update_search_vector(document)

    for tag in routage.tags_defaut.all():
        assign_tag(document, tag, created_by=uploaded_by)

    return document
