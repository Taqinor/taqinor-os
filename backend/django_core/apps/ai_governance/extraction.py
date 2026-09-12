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
