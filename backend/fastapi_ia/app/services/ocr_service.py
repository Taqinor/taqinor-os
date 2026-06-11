"""
Service OCR — Z.AI (Zhipu AI).
- Images : glm-4.5v avec streaming (seul mode qui retourne du contenu)
- PDF    : pypdf pour l'extraction + glm-4.7 pour la structuration
Clé ZHIPU_API_KEY depuis les variables d'environnement.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
from typing import Any

from app.core.config import ZHIPU_API_KEY

logger = logging.getLogger(__name__)

OCR_TIMEOUT_SECONDS = 115      # timeout global (nginx = 120s)
_STRUCTURE_TIMEOUT = 50        # timeout spécifique pour l'appel GLM de structuration
_ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
_VISION_MODEL = "glm-4.5v"   # vision — fonctionne uniquement en streaming
_TEXT_MODEL = "glm-4.7"      # texte seul — fonctionne en mode normal

_EXTRACT_PROMPT = """\
Analyse ce document et extrais toutes les informations.
Reponds UNIQUEMENT avec un objet JSON valide, sans texte avant ni apres.

Format attendu :
{
  "texte_brut": "tout le texte brut du document en preservant la mise en page",
  "type_document": "facture|devis|bon_commande|bon_livraison|autre",
  "confiance": <float 0.0-1.0>,
  "donnees_structurees": {
    "numero": null,
    "date": null,
    "fournisseur": null,
    "client": null,
    "montant_ht": null,
    "taux_tva": null,
    "montant_tva": null,
    "montant_ttc": null,
    "conditions_paiement": null,
    "iban": null,
    "lignes": []
  }
}

Regles :
- Les montants sont des nombres (pas de chaines), null si absent.
- Les dates au format YYYY-MM-DD, null si absente.
- confiance reflète la lisibilite et completude (1.0 = parfait).
- lignes : [{"description":"","quantite":null,"prix_unitaire":null,"montant":null}]
"""

_STRUCTURE_PROMPT = """\
Voici le texte extrait d'un document commercial. \
Identifie le type et structure les donnees.
Reponds UNIQUEMENT avec un objet JSON valide.

Format attendu :
{
  "type_document": "facture|devis|bon_commande|bon_livraison|autre",
  "confiance": <float 0.0-1.0>,
  "donnees_structurees": {
    "numero": null,
    "date": null,
    "fournisseur": null,
    "client": null,
    "montant_ht": null,
    "taux_tva": null,
    "montant_tva": null,
    "montant_ttc": null,
    "conditions_paiement": null,
    "iban": null,
    "lignes": []
  }
}

Texte du document :
"""

_STOCK_PROMPT = """\
Analyse ce document fournisseur : bon de livraison, bon de sortie, bordereau, ou facture fournisseur.
Ce document peut etre un scan ou une photo d'un document papier, parfois de mauvaise qualite, froisse ou incline.
Reponds UNIQUEMENT avec un objet JSON valide, sans aucun texte avant ni apres.

Format attendu :
{
  "type_document": "bon_livraison|facture_fournisseur|autre",
  "mouvement_suggere": "entree",
  "fournisseur": "Nom exact de la societe fournisseur ou null",
  "reference_document": "Numero BL, TD, bon de sortie ou facture ou null",
  "date": "YYYY-MM-DD ou null",
  "confiance": <float 0.0-1.0>,
  "lignes": [
    {
      "reference": "Code article / REF / SKU tel qu'il apparait dans le document ou null",
      "nom": "Designation complete du produit en francais",
      "categorie_suggeree": "Nom court de la famille du produit en francais (2-3 mots). OBLIGATOIRE, ne jamais null.",
      "quantite": <nombre entier positif>,
      "prix_unitaire_ht": <float ou null>,
      "tva": <taux TVA en % (ex: 10, 20) ou null si absent>
    }
  ]
}

Regles importantes :
- Extrais ABSOLUMENT TOUTES les lignes produits visibles, meme partiellement lisibles.
- Pour la quantite : utilise de preference la colonne LIVRE / LIVREE / QTE LIVREE / DELIVRE.
  Si seulement une colonne existe (COMMANDEE, QTE...), utilise-la.
- mouvement_suggere est toujours "entree" (marchandises recues du fournisseur vers nous).
- Les documents "bon de sortie" (TD/OUT, BS, BL) d'un fournisseur sont traites comme bon_livraison.
- fournisseur = la societe qui EMET la facture (le vendeur), pas le client destinataire.
  Sur une facture : le fournisseur est en haut a gauche (logo, nom societe emettrice) ou en bas (mentions legales RC/ICE).
  Le nom dans le cadre adresse (ex: "TAQINOR SOLUTIONS", "Vendu a", "Client :") est le CLIENT, pas le fournisseur.
  Ne jamais mettre le nom du client/acheteur comme fournisseur.
- reference = code article interne ou SKU alphanumérique du fournisseur (ex: "REF-001", "CS-715W").
  NE PAS utiliser le code douanier / code SH / code HS (nombre de 6 à 10 chiffres, ex: 85414020) comme reference.
  Si la seule valeur numerique disponible est un code douanier, mettre reference = null.
- quantite et prix_unitaire sont des nombres (entiers ou decimaux), null si absents.
- Si le document contient du texte arabe ou melange arabe/francais, traduis les designations en francais.
- confiance : 1.0 = document parfaitement lisible, 0.3 = scan difficile mais donnees extraites.
- Ignore les tampons, signatures et annotations manuscrites non pertinentes.
- categorie_suggeree : OBLIGATOIRE, ne jamais null. Nom court de la famille du produit en francais (2-3 mots max).
"""

_DOC_TYPE_CONTEXT: dict[str, str] = {
    "facture_achat": "Ce document est une FACTURE D'ACHAT fournisseur. Extrayez les prix HT et la TVA par ligne.",
    "bon_livraison": "Ce document est un BON DE LIVRAISON fournisseur. Les prix peuvent etre absents.",
    "bon_sortie": "Ce document est un BON DE SORTIE ou livraison CLIENT. Mettez mouvement_suggere = sortie.",
}


def _build_stock_prompt(doc_type: str) -> str:
    ctx = _DOC_TYPE_CONTEXT.get(doc_type, "")
    if ctx:
        return f"CONTEXTE : {ctx}\n\n" + _STOCK_PROMPT
    return _STOCK_PROMPT


def _build_stock_structure_prompt(doc_type: str) -> str:
    ctx = _DOC_TYPE_CONTEXT.get(doc_type, "")
    if ctx:
        return f"CONTEXTE : {ctx}\n\n" + _STOCK_STRUCTURE_PROMPT
    return _STOCK_STRUCTURE_PROMPT


_STOCK_STRUCTURE_PROMPT = """\
Voici le texte extrait d'un document fournisseur (facture, bon de livraison, bon de sortie).
ATTENTION : l'extraction PDF peut placer les donnees dans le desordre (valeurs avant en-tetes de colonnes).
Identifie le type et structure les donnees produits.
Reponds UNIQUEMENT avec un objet JSON valide.

Aide pour les factures avec colonnes "Designation | TVA | P.U. HT | Qte | Total HT" :
- Apres la designation du produit, les valeurs suivent l'ordre : TVA% prix_unitaire quantite total_ht
- Exemple : "Panneau Solar 715W ... 10% 909,09091 16 14 545,45"
  → reference="Panneau_Solar_715W", nom="Panneau Solar 715W", prix_unitaire_ht=909.09, tva=10, quantite=16

Format attendu :
{
  "type_document": "bon_livraison|facture_fournisseur|autre",
  "mouvement_suggere": "entree",
  "fournisseur": "Nom de la societe fournisseur ou null",
  "reference_document": "Numero BL, TD, bon de sortie ou facture ou null",
  "date": "YYYY-MM-DD ou null",
  "confiance": <float 0.0-1.0>,
  "lignes": [
    {
      "reference": "Code article / REF / SKU ou null",
      "nom": "Designation complete du produit en francais",
      "categorie_suggeree": "Nom court de la famille du produit en francais (2-3 mots). OBLIGATOIRE, ne jamais null.",
      "quantite": <nombre entier positif>,
      "prix_unitaire_ht": <float HT ou null>,
      "tva": <taux TVA en % (ex: 10, 20) ou null>
    }
  ]
}

Regles :
- Extrais TOUTES les lignes produits, meme si l'ordre du texte semble incohérent.
- Pour la quantite : prefere la colonne LIVRE / LIVREE / QTE LIVREE plutot que COMMANDEE.
- mouvement_suggere est toujours "entree".
- Les "bon de sortie" (TD/OUT, BS) d'un fournisseur sont traites comme bon_livraison.
- fournisseur = la societe qui EMET le document (le vendeur/expediteur), pas le destinataire.
  Le destinataire (zone "Vendu a", "Client", "A l'attention de", cadre adresse central) est notre propre entreprise : NE PAS le mettre comme fournisseur.
  Le fournisseur est l'entite avec logo en haut a gauche, ou avec RC/ICE/IF en bas de page.
- Si une designation commence par un code_article alphanumérique (ex: "Canadian_Solar_715w_n_type_Bifacial"),
  utilise-le comme reference et le reste comme nom.
- NE PAS utiliser le code douanier / SH / HS (nombre pur de 6 a 10 chiffres, ex: 85414020) comme reference.
  Le code douanier est une colonne separee de la designation. reference = null si pas de code interne.

Texte du document :
"""


def _get_media_type(filename: str, data: bytes) -> str:
    """Détecte le type MIME réel à partir des magic bytes."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] in (b"II*\x00", b"MM\x00*"):
        return "image/tiff"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "webp": "image/webp",
        "tiff": "image/tiff", "tif": "image/tiff",
    }.get(ext, "image/jpeg")


def _tiff_to_png(tiff_bytes: bytes) -> bytes:
    """Convertit un TIFF en PNG via Pillow."""
    from PIL import Image
    img = Image.open(io.BytesIO(tiff_bytes))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _compress_for_vision(img_bytes: bytes, max_side: int = 1280) -> tuple[bytes, str]:
    """
    Redimensionne et compresse une image pour l'API vision.
    Retourne (jpeg_bytes, 'image/jpeg').
    Réduit typiquement de 2-5 Mo → 200-400 Ko.
    """
    from PIL import Image
    img = Image.open(io.BytesIO(img_bytes))
    w, h = img.size
    if max(w, h) > max_side:
        ratio = max_side / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=88, optimize=True)
    compressed = buf.getvalue()
    logger.debug(
        "Image compressed: %d Ko → %d Ko",
        len(img_bytes) // 1024,
        len(compressed) // 1024,
    )
    return compressed, "image/jpeg"


def _parse_json(text: str) -> dict:
    """Parse une réponse JSON, tolère du texte parasite autour."""
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def _make_client():
    from openai import AsyncOpenAI
    return AsyncOpenAI(api_key=ZHIPU_API_KEY, base_url=_ZHIPU_BASE_URL)


async def _stream_response(client, model: str, messages: list) -> str:
    """
    Appel streaming — seul mode fiable pour glm-4.5v.
    Concatène les chunks et retourne le texte complet.
    """
    stream = await client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=2048,
        stream=True,
    )
    chunks: list[str] = []
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            chunks.append(delta)
    return "".join(chunks)


class OCRService:

    def __init__(self) -> None:
        self._api_key: str = ZHIPU_API_KEY

    def _check_api_key(self) -> None:
        if not self._api_key:
            raise RuntimeError(
                "ZHIPU_API_KEY non configuree. "
                "Ajoutez ZHIPU_API_KEY=xxxx dans le fichier .env."
            )

    # ── Images ────────────────────────────────────────────────────────────────

    async def process_image(
        self, image_bytes: bytes, filename: str = ""
    ) -> dict[str, Any]:
        try:
            return await asyncio.wait_for(
                self._process_image_internal(image_bytes, filename),
                timeout=OCR_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            return self._timeout_result()
        except RuntimeError as e:
            return self._error_result(str(e))
        except Exception as e:
            logger.error("OCR image error: %s", e)
            return self._error_result("Erreur inattendue lors de l'analyse.")

    async def _process_image_internal(
        self, image_bytes: bytes, filename: str
    ) -> dict[str, Any]:
        self._check_api_key()

        media_type = _get_media_type(filename, image_bytes)

        # glm-4.5v ne supporte pas TIFF → convertir en PNG
        if media_type == "image/tiff":
            image_bytes = _tiff_to_png(image_bytes)
            media_type = "image/png"

        b64 = base64.standard_b64encode(image_bytes).decode()
        data_url = f"data:{media_type};base64,{b64}"

        client = _make_client()
        raw_text = await _stream_response(
            client,
            _VISION_MODEL,
            [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": _EXTRACT_PROMPT},
                ],
            }],
        )

        parsed = _parse_json(raw_text)
        # parsed.get("texte_brut") peut être "" (image vide) — ne pas
        # substituer raw_text dans ce cas, seulement si la clé est absente
        texte = parsed.get("texte_brut") if "texte_brut" in parsed else raw_text
        return {
            "texte_brut": texte,
            "confiance": float(parsed.get("confiance", 0.75)),
            "blocs": [],
            "type_document": parsed.get("type_document", "autre"),
            "donnees_structurees": parsed.get("donnees_structurees", {}),
        }

    # ── PDF ───────────────────────────────────────────────────────────────────

    async def process_pdf(self, pdf_bytes: bytes) -> dict[str, Any]:
        try:
            return await asyncio.wait_for(
                self._process_pdf_internal(pdf_bytes),
                timeout=OCR_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            return {**self._timeout_result(), "nb_pages": 0, "pages": []}
        except RuntimeError as e:
            return {**self._error_result(str(e)), "nb_pages": 0, "pages": []}
        except Exception as e:
            logger.error("OCR pdf error: %s", e)
            return {
                **self._error_result("Erreur inattendue lors de l'analyse PDF."),
                "nb_pages": 0,
                "pages": [],
            }

    async def _process_pdf_internal(self, pdf_bytes: bytes) -> dict[str, Any]:
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        pages_text: list[dict] = []
        full_text = ""

        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            pages_text.append({"page": i + 1, "texte": text})
            full_text += f"\n--- Page {i + 1} ---\n{text}"

        extracted = full_text.strip()

        structured: dict = {}
        if extracted and self._api_key:
            try:
                structured = await asyncio.wait_for(
                    self._structure_text(extracted),
                    timeout=_STRUCTURE_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.warning("GLM structuring timed out after %ss — returning raw text", _STRUCTURE_TIMEOUT)
            except Exception as e:
                logger.warning("GLM structuring failed for PDF: %s", e)

        return {
            "texte_complet": extracted,
            "nb_pages": len(reader.pages),
            "pages": pages_text,
            "type_document": structured.get("type_document", "autre"),
            "confiance": float(
                structured.get("confiance", 0.5 if extracted else 0.0)
            ),
            "donnees_structurees": structured.get("donnees_structurees", {}),
        }

    async def _structure_text(self, text: str) -> dict:
        """Utilise glm-4.7 (texte) pour structurer un texte déjà extrait."""
        client = _make_client()
        response = await client.chat.completions.create(
            model=_TEXT_MODEL,
            messages=[{
                "role": "user",
                "content": _STRUCTURE_PROMPT + text[:4000],
            }],
            max_tokens=1024,
        )
        raw = response.choices[0].message.content or ""
        return _parse_json(raw)

    # ── Stock document (bon de livraison / facture fournisseur) ───────────────

    async def process_stock_document(
        self, file_bytes: bytes, filename: str, content_type: str, doc_type: str = ""
    ) -> dict[str, Any]:
        try:
            return await asyncio.wait_for(
                self._process_stock_internal(file_bytes, filename, content_type, doc_type),
                timeout=OCR_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            return self._stock_timeout_result()
        except RuntimeError as e:
            return self._stock_error_result(str(e))
        except Exception as e:
            logger.error("OCR stock error: %s", e)
            return self._stock_error_result("Erreur inattendue lors de l'analyse.")

    async def _process_stock_internal(
        self, file_bytes: bytes, filename: str, content_type: str, doc_type: str = ""
    ) -> dict[str, Any]:
        self._check_api_key()
        if content_type == "application/pdf":
            return await self._process_pdf_stock(file_bytes, doc_type)
        return await self._process_image_stock(file_bytes, filename, doc_type)

    async def _process_image_stock(
        self, image_bytes: bytes, filename: str, doc_type: str = ""
    ) -> dict[str, Any]:
        media_type = _get_media_type(filename, image_bytes)
        if media_type == "image/tiff":
            image_bytes = _tiff_to_png(image_bytes)
            media_type = "image/png"

        b64 = base64.standard_b64encode(image_bytes).decode()
        data_url = f"data:{media_type};base64,{b64}"

        client = _make_client()
        raw_text = await _stream_response(
            client,
            _VISION_MODEL,
            [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": _build_stock_prompt(doc_type)},
                ],
            }],
        )
        return self._normalize_stock_result(_parse_json(raw_text), raw_text, doc_type)

    async def _do_stock_structure(self, extracted: str, doc_type: str = "") -> dict:
        """Call GLM text model to structure already-extracted PDF text."""
        client = _make_client()
        response = await client.chat.completions.create(
            model=_TEXT_MODEL,
            messages=[{
                "role": "user",
                "content": _build_stock_structure_prompt(doc_type) + extracted[:4000],
            }],
            max_tokens=2048,
        )
        raw = response.choices[0].message.content or ""
        return _parse_json(raw)

    async def _process_pdf_stock(
        self, pdf_bytes: bytes, doc_type: str = ""
    ) -> dict[str, Any]:
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        full_text = ""
        for i, page in enumerate(reader.pages):
            full_text += (
                f"\n--- Page {i + 1} ---\n{page.extract_text() or ''}"
            )

        extracted = full_text.strip()

        # Scanned/image PDF: no extractable text → vision model directly
        if len(extracted) < 50:
            logger.info(
                "PDF has no extractable text (%d chars) — vision pipeline",
                len(extracted),
            )
            return await self._process_pdf_scanned_stock(pdf_bytes, doc_type)

        # Digital PDF: try text structuring first
        parsed: dict = {}
        if self._api_key:
            try:
                parsed = await asyncio.wait_for(
                    self._do_stock_structure(extracted, doc_type),
                    timeout=_STRUCTURE_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "GLM stock structuring timed out after %ss",
                    _STRUCTURE_TIMEOUT,
                )
            except Exception as e:
                logger.warning("GLM stock structuring failed: %s", e)

        # Text path returned no lines (bad PDF layout) → vision fallback
        if not parsed.get("lignes"):
            logger.info(
                "Text extraction yielded 0 lines — vision fallback for PDF"
            )
            return await self._process_pdf_scanned_stock(pdf_bytes, doc_type)

        # For purchase invoices: if lines found but no prices at all → vision fallback
        if doc_type == "facture_achat":
            has_any_price = any(
                ligne.get("prix_unitaire_ht") for ligne in parsed.get("lignes", [])
            )
            if not has_any_price:
                logger.info(
                    "Purchase invoice: lines found but no prices via text path"
                    " — vision fallback"
                )
                return await self._process_pdf_scanned_stock(pdf_bytes, doc_type)

        return self._normalize_stock_result(parsed, extracted, doc_type)

    async def _process_pdf_scanned_stock(
        self, pdf_bytes: bytes, doc_type: str = ""
    ) -> dict[str, Any]:
        """Render each page as PNG via PyMuPDF and send to vision model."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            return self._stock_error_result(
                "PDF scanné détecté mais pymupdf n'est pas installé."
            )

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        # 1.5x = ~108 DPI — lisible pour OCR, image plus légère qu'à 2x
        mat = fitz.Matrix(1.5, 1.5)
        max_pages = min(len(doc), 3)

        all_lignes: list = []
        best_meta: dict = {}
        best_confiance = 0.0

        for page_num in range(max_pages):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=mat)
            raw_png = pix.tobytes("png")
            # Compresser en JPEG ~300 Ko max avant envoi à l'API vision
            img_bytes, _ = _compress_for_vision(raw_png, max_side=1280)

            try:
                result = await asyncio.wait_for(
                    self._process_image_stock(
                        img_bytes, f"page_{page_num + 1}.jpg", doc_type
                    ),
                    timeout=85,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Vision timeout on scanned PDF page %d", page_num + 1
                )
                continue

            all_lignes.extend(result.get("lignes", []))

            conf = float(result.get("confiance", 0.0))
            if conf > best_confiance:
                best_confiance = conf
                best_meta = result

        if not best_meta:
            return self._stock_error_result(
                "Impossible d'extraire les données du PDF scanné."
            )

        return {
            "type_document": best_meta.get("type_document", "autre"),
            "mouvement_suggere": best_meta.get("mouvement_suggere", "entree"),
            "fournisseur": best_meta.get("fournisseur"),
            "reference_document": best_meta.get("reference_document"),
            "date": best_meta.get("date"),
            "confiance": best_confiance,
            "lignes": all_lignes,
            "texte_brut": best_meta.get("texte_brut", ""),
        }

    @staticmethod
    def _normalize_stock_result(
        parsed: dict, raw_text: str = "", doc_type: str = ""
    ) -> dict[str, Any]:
        def _round_price(val):
            if val is None:
                return None
            try:
                if isinstance(val, str):
                    # Handle French decimal format: "909,09091" → 909.09
                    val = val.strip().replace('\xa0', '').replace(' ', '').replace(',', '.')
                return round(float(val), 2)
            except (TypeError, ValueError):
                return None

        def _split_ref_nom(row: dict) -> tuple[str | None, str]:
            """Extract internal reference from nom when reference is absent.

            Handles the pattern: "CODE_INTERNE - Designation lisible"
            where CODE_INTERNE is alphanumeric with underscores (no spaces).
            Pure-digit customs codes are never treated as references.
            """
            import re
            ref = row.get("reference")
            nom = (row.get("nom") or "").strip()
            if ref:
                return ref, nom
            # Match: starts with word_characters (must contain letter + underscore)
            # followed by separator " - " or " – "
            m = re.match(
                r'^([A-Za-z][A-Za-z0-9_\-]{3,})\s*[-–]\s*(.+)$', nom
            )
            if m and '_' in m.group(1):
                return m.group(1), m.group(2).strip()
            return None, nom

        lignes = []
        for row in parsed.get("lignes", []):
            if not row.get("nom"):
                continue
            ref, nom_clean = _split_ref_nom(row)
            lignes.append({
                "reference": ref,
                "nom": nom_clean,
                "quantite": max(1, int(row.get("quantite") or 1)),
                "prix_unitaire_ht": _round_price(
                    row.get("prix_unitaire_ht") or row.get("prix_unitaire")
                ),
                "tva": row.get("tva"),
                "categorie_suggeree": row.get("categorie_suggeree") or None,
            })
        mouvement = (
            "sortie" if doc_type == "bon_sortie"
            else parsed.get("mouvement_suggere", "entree")
        )
        return {
            "type_document": parsed.get("type_document", "autre"),
            "mouvement_suggere": mouvement,
            "fournisseur": parsed.get("fournisseur"),
            "reference_document": parsed.get("reference_document"),
            "date": parsed.get("date"),
            "confiance": float(parsed.get("confiance", 0.5 if raw_text else 0.0)),
            "lignes": lignes,
            "texte_brut": raw_text,
        }

    @staticmethod
    def _stock_timeout_result() -> dict[str, Any]:
        return {
            "type_document": "autre", "mouvement_suggere": "entree",
            "fournisseur": None, "reference_document": None, "date": None,
            "confiance": 0.0, "lignes": [],
            "texte_brut": "Délai dépassé (60s). Fichier trop complexe ou service indisponible.",
        }

    @staticmethod
    def _stock_error_result(message: str) -> dict[str, Any]:
        return {
            "type_document": "autre", "mouvement_suggere": "entree",
            "fournisseur": None, "reference_document": None, "date": None,
            "confiance": 0.0, "lignes": [],
            "texte_brut": f"Erreur : {message}",
        }

    # ── Résultats d'erreur ────────────────────────────────────────────────────

    @staticmethod
    def _timeout_result() -> dict[str, Any]:
        return {
            "texte_brut": (
                "Delai depasse (60s). Fichier trop complexe ou service indisponible."
            ),
            "confiance": 0.0,
            "blocs": [],
            "type_document": "autre",
            "donnees_structurees": {},
        }

    @staticmethod
    def _error_result(message: str) -> dict[str, Any]:
        return {
            "texte_brut": f"Erreur : {message}",
            "confiance": 0.0,
            "blocs": [],
            "type_document": "autre",
            "donnees_structurees": {},
        }


ocr_service = OCRService()
