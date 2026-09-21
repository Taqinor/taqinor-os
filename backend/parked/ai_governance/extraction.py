"""NTAI15/NTAI16 — Extraction documentaire à la demande (upload → champs).

Un endpoint, tous les gabarits : ``POST /api/django/ai/extraire/?schema=<nom>``
prend un fichier, le passe à l'OCR EXISTANT (``core.ai.extract_document``) et
rend les champs du gabarit demandé.

CE QUI N'ARRIVE JAMAIS ICI :

  * **aucune écriture** — ni bulletin de paie, ni facture fournisseur, ni ligne
    de stock : le résultat est une PROPOSITION que l'utilisateur applique (ou
    pas) depuis l'écran métier ;
  * **aucune persistance du fichier** — les octets ne vivent qu'en mémoire, le
    temps de l'extraction (même garantie que le scan de carte de visite) ;
  * **aucun appel réseau sans clé** — sans fournisseur OCR configuré, la
    réponse est une 503 douce en français.

NTAI16 ajoute, pour la facture fournisseur, un RAPPROCHEMENT : les lignes
extraites sont appariées au catalogue produit de la société (via les
``selectors`` de ``stock``, jamais ses modèles) pour préparer le contrôle
3 volets. L'appariement est un INDICE (score), jamais une décision.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from core.ai.registry import is_capability_configured
from core.ai.schemas import available_schemas, get_schema

from .services import AiCopiloteUnavailable, exiger_feature

#: Taille max d'une pièce à extraire (scan A4 couleur confortable).
EXTRACTION_MAX_BYTES = 12 * 1024 * 1024  # 12 Mo

#: Octets magiques acceptés — mêmes familles que le reste du dépôt, plus le
#: PDF (un bulletin de paie ou une facture fournisseur arrive le plus souvent
#: en PDF, contrairement à une carte de visite).
EXTRACTION_MAGIC = {
    'application/pdf': lambda h: h[:5] == b'%PDF-',
    'image/png': lambda h: h[:8] == b'\x89PNG\r\n\x1a\n',
    'image/jpeg': lambda h: h[:3] == b'\xff\xd8\xff',
    'image/webp': lambda h: h[:4] == b'RIFF' and h[8:12] == b'WEBP',
}

#: Seuil d'appariement d'une ligne de facture au catalogue (même valeur que
#: l'appariement de bon de livraison — un score plus bas produirait des
#: rapprochements que personne ne pourrait justifier).
RAPPROCHEMENT_SEUIL = 0.6


def _detect_mime(entete: bytes):
    for mime, test in EXTRACTION_MAGIC.items():
        if test(entete):
            return mime
    return None


def _decimal(valeur):
    """Decimal tolérant (« 1 234,56 » → 1234.56), ou ``None`` si illisible."""
    if valeur in (None, ''):
        return None
    texte = str(valeur)
    for espace in (' ', ' ', ' ', ' '):
        texte = texte.replace(espace, '')
    texte = texte.replace(',', '.')
    try:
        return Decimal(texte)
    except (InvalidOperation, ValueError):
        return None


def extraire_document(*, company, file_bytes, schema, mime_hint='') -> dict:
    """Extrait les champs de ``schema`` depuis ``file_bytes``. N'ÉCRIT RIEN.

    Lève :class:`AiCopiloteUnavailable` : gabarit inconnu / fichier absent,
    trop gros ou d'un format non reconnu (400) ; aucun fournisseur OCR
    configuré (503, aucun appel réseau).
    """
    exiger_feature(company, 'ai.extraire')

    from core.ai.services import extract_document

    nom_schema = str(schema or '').strip().lower()
    if nom_schema not in available_schemas():
        raise AiCopiloteUnavailable(
            'Gabarit inconnu — attendu : ' + ', '.join(available_schemas())
            + '.')
    if not file_bytes:
        raise AiCopiloteUnavailable('Aucun fichier fourni.')
    if len(file_bytes) > EXTRACTION_MAX_BYTES:
        raise AiCopiloteUnavailable('Fichier trop volumineux (max 12 Mo).')

    mime = _detect_mime(file_bytes[:12])
    if mime is None:
        raise AiCopiloteUnavailable(
            'Format non reconnu (PDF, JPEG, PNG ou WebP uniquement).')

    if not is_capability_configured('ocr'):
        raise AiCopiloteUnavailable(
            "Aucun fournisseur OCR n'est configuré (clé absente) — "
            'saisie manuelle requise.', configured=False)

    resultat = extract_document(
        content=file_bytes, mime_type=mime, schema=nom_schema)
    if not resultat.configured:
        raise AiCopiloteUnavailable(
            "Aucun fournisseur OCR n'est configuré (clé absente) — "
            'saisie manuelle requise.', configured=False)
    if not resultat.ok:
        raise AiCopiloteUnavailable(
            resultat.error or "L'extraction n'a rien produit d'exploitable.")

    gabarit = get_schema(nom_schema)
    donnees = resultat.data or {}
    # On ne renvoie QUE les champs du gabarit : un fournisseur bavard ne peut
    # pas glisser de clé inattendue dans la réponse.
    champs = {cle: donnees.get(cle) for cle in gabarit.field_keys()}
    manquants = [cle for cle in gabarit.required_keys()
                 if champs.get(cle) in (None, '', [])]

    reponse = {
        'schema': nom_schema,
        'label': gabarit.label,
        'champs': champs,
        'champs_manquants': manquants,
        # Contrat explicite : aucune écriture, aucun fichier conservé.
        'applique': False,
        'fichier_conserve': False,
        'source': resultat.provider,
    }
    if nom_schema == 'facture_fournisseur':
        reponse['rapprochement'] = rapprocher_facture(company, champs)
    return reponse


# ─────────────────────────────────────────────────────────────────────────────
# NTAI20 — Résumé d'un long document (map-reduce), avec repli sur l'aperçu
# ─────────────────────────────────────────────────────────────────────────────
#
# Un contrat de 40 pages ne tient pas dans un prompt. On résume donc FRAGMENT
# par FRAGMENT (map), puis on résume les résumés (reduce) — et chaque point clé
# reste RATTACHÉ à son fragment, pour qu'un lecteur puisse aller vérifier.
#
# Sans clé LLM, l'endpoint ne tombe pas : il rend l'aperçu plein-texte que la
# GED expose déjà (GED14). L'utilisateur obtient toujours quelque chose.

#: Nombre max de fragments résumés (borne le coût d'un document de 300 pages).
RESUME_FRAGMENTS_MAX = 8

#: Taille d'un fragment quand le document n'a pas encore été découpé par la GED.
RESUME_TAILLE_FRAGMENT = 2000

#: Longueur de l'aperçu plein-texte rendu en repli.
RESUME_APERCU_CARACTERES = 1200


def fragments_du_document(document) -> list:
    """Fragments de texte du document, du premier au dernier.

    Réutilise les ``DocumentChunk`` de la GED (FG352/GED12) quand ils existent ;
    sinon découpe le texte OCR EN MÉMOIRE (aucune écriture, aucun index créé
    ici — l'indexation reste le métier de la GED)."""
    try:
        chunks = list(document.chunks.order_by('chunk_index')
                      .values_list('texte', flat=True))
    except Exception:  # noqa: BLE001 — pas de fragments indexés
        chunks = []
    fragments = [t for t in chunks if (t or '').strip()]
    if fragments:
        return fragments

    texte = str(getattr(document, 'texte_ocr', '') or '').strip()
    if not texte:
        return []
    return [texte[i:i + RESUME_TAILLE_FRAGMENT]
            for i in range(0, len(texte), RESUME_TAILLE_FRAGMENT)]


def resumer_document(*, company, document_id, max_tokens=400) -> dict:
    """NTAI20 — Résumé d'un long document + points clés cités. LECTURE SEULE.

    Sans clé LLM : renvoie l'aperçu plein-texte existant (``source:
    'apercu'``) — jamais une erreur, jamais un résumé inventé.
    """
    exiger_feature(company, 'ai.resumer_document')

    from core.ai.registry import is_capability_configured as _configure
    from core.ai.services import summarize_thread

    document = _document_scoped(company, document_id)
    if document is None:
        raise AiCopiloteUnavailable('Document introuvable.')

    fragments = fragments_du_document(document)
    if not fragments:
        raise AiCopiloteUnavailable(
            "Ce document n'a pas de texte exploitable (pas encore océrisé ?).")

    apercu = ' '.join(fragments)[:RESUME_APERCU_CARACTERES]
    if not _configure('llm'):
        return {
            'document_id': getattr(document, 'pk', document_id),
            'resume': '',
            'points_cles': [],
            'apercu': apercu,
            'fragments': len(fragments),
            'source': 'apercu',
        }

    retenus = fragments[:RESUME_FRAGMENTS_MAX]
    points = []
    for index, fragment in enumerate(retenus):
        partiel = summarize_thread(
            [{'texte': fragment}],
            context='Fragment de document long — résume-le en 1 à 2 phrases.',
            max_tokens=180)
        if partiel.available:
            points.append({
                'fragment': index + 1,
                'texte': partiel.summary,
                # Citation VÉRIFIABLE : le numéro renvoie à un fragment réel.
                'citation': f'[fragment {index + 1}]',
            })

    if not points:
        return {
            'document_id': getattr(document, 'pk', document_id),
            'resume': '',
            'points_cles': [],
            'apercu': apercu,
            'fragments': len(fragments),
            'source': 'apercu',
        }

    global_ = summarize_thread(
        [{'texte': p['texte']} for p in points],
        context='Synthèse générale à partir des résumés de fragments.',
        max_tokens=max_tokens)

    return {
        'document_id': getattr(document, 'pk', document_id),
        'resume': global_.summary if global_.available else '',
        'points_cles': points,
        'apercu': apercu,
        'fragments': len(fragments),
        # Vrai quand le document dépasse la borne : le lecteur doit savoir que
        # la fin n'a pas été lue, plutôt que de croire à un résumé complet.
        'tronque': len(fragments) > len(retenus),
        'source': 'llm',
    }


def _document_scoped(company, document_id):
    """Document GED de la société, via le SELECTOR de la GED. ``None`` sinon."""
    if not document_id:
        return None
    try:
        from apps.ged.selectors import documents_for_company
    except Exception:  # noqa: BLE001 — app absente (édition allégée)
        return None
    try:
        return documents_for_company(company).filter(pk=document_id).first()
    except (ValueError, TypeError):
        return None


def _catalogue_appariement(company) -> list:
    """Catalogue produit de la société, LU VIA LE SELECTOR de ``stock``.

    La frontière inter-apps interdit de lire ``stock.models`` d'ici. Tant que
    ``apps.stock.selectors`` n'expose pas de fonction dédiée
    (``catalogue_pour_appariement(company) -> [{id, designation, reference}]``),
    l'appariement PRODUIT reste éteint : les lignes sortent non appariées, avec
    leurs quantités et leurs totaux — le rapprochement reste faisable à la
    main, et personne ne voit un appariement inventé. Le jour où la fonction
    existe, elle est utilisée sans toucher une ligne ici.
    """
    try:
        from apps.stock import selectors as stock_selectors
    except Exception:  # noqa: BLE001 — module stock absent (édition allégée)
        return []
    fournisseur = getattr(stock_selectors, 'catalogue_pour_appariement', None)
    if fournisseur is None:
        return []
    try:
        return list(fournisseur(company))
    except Exception:  # noqa: BLE001 — un catalogue illisible ≠ un échec
        return []


def rapprocher_facture(company, champs: dict) -> dict:
    """NTAI16 — Prépare le rapprochement d'une facture fournisseur.

    Apparie chaque ligne extraite au catalogue produit de la société (lecture
    via les ``selectors`` de ``stock`` — jamais ses modèles) et recalcule le
    total HT des lignes pour le CONFRONTER au total imprimé.

    Aucune décision n'est prise : un écart est SIGNALÉ, pas corrigé, et rien
    n'est écrit. Si le catalogue est illisible, on renvoie les lignes non
    appariées plutôt que d'échouer — le rapprochement reste faisable à la main.
    """
    from core.ai.services import match_ocr_lines

    lignes = champs.get('lignes')
    if not isinstance(lignes, list):
        lignes = []

    catalogue = _catalogue_appariement(company)

    appariees = match_ocr_lines(
        lignes, catalogue, threshold=RAPPROCHEMENT_SEUIL)
    details, total_calcule = [], Decimal('0')
    for brute, ligne in zip(lignes, appariees):
        total_ligne = _decimal(brute.get('total_ht'))
        if total_ligne is None:
            pu = _decimal(brute.get('prix_unitaire_ht'))
            if pu is not None:
                total_ligne = pu * Decimal(str(ligne.quantite or 0))
        if total_ligne is not None:
            total_calcule += total_ligne
        details.append({
            'designation': ligne.designation,
            'reference': ligne.reference,
            'quantite': ligne.quantite,
            'total_ht': str(total_ligne) if total_ligne is not None else None,
            'produit_id': ligne.catalogue_id,
            'produit_label': ligne.catalogue_label,
            'score': ligne.score,
            'apparie': ligne.matched,
        })

    total_imprime = _decimal(champs.get('total_ht'))
    ecart = None
    if total_imprime is not None and details:
        ecart = str(total_imprime - total_calcule)

    return {
        'lignes': details,
        'lignes_appariees': sum(1 for d in details if d['apparie']),
        'total_ht_calcule': str(total_calcule) if details else None,
        'total_ht_imprime': (str(total_imprime)
                             if total_imprime is not None else None),
        # Écart entre ce qui est IMPRIMÉ et la somme des lignes LUES. Non nul
        # = une ligne a été mal lue, ou la facture ne s'additionne pas : un
        # humain tranche. On ne « corrige » jamais un total.
        'ecart_total_ht': ecart,
        'applique': False,
    }
