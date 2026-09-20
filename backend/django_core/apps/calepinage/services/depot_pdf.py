"""SOLMVP15 — déposer et FUSIONNER les PDF du module, par ``records``.

D'OÙ ÇA VIENT
=============
Les deux packs du module (CAL181 dossier technique, CAL190 dossier
réglementaire) déposaient chaque pièce comme document de la GED puis
appelaient sa primitive de fusion. La GED sort du produit (PHASE 2 : elle
reviendra) : les packs, eux, restent — ce sont deux capacités de l'atelier.

CE QUI REMPLACE LA GED, ET POURQUOI C'EST LE MÊME CHEMIN
========================================================
Les pièces jointes du module vivent DÉJÀ dans ``records`` : les photos de site
(CAL52) et le FICHIER de gabarit de dossier réglementaire
(``GabaritDossierReglementaire.fichier``, une FK vers ``records.Attachment``)
y sont depuis le premier jour. Un pack déposé dans ``records`` n'est donc pas
un second référentiel : c'est celui que le module utilise déjà, atteint par son
service de stockage (``records.storage.store_attachment`` — validation du type
réel, MinIO, clé préfixée par la société).

Ce module reste le SEUL foyer de dépôt PDF du calepinage : ni
``pack_technique`` ni ``reglementaire`` ne parle au stockage directement.

LA FUSION
=========
Elle se fait sur les OCTETS, avec PyMuPDF — la même bibliothèque, déjà en
production, déjà utilisée par ce module (``analyse_plan.py``). C'est même un
aller-retour de MOINS qu'avant : les pièces sont fusionnées telles qu'elles
viennent d'être rendues, au lieu d'être redescendues du stockage après dépôt.
Aucune source n'est jamais mutée.

LES REFUS
=========
Tout refus est un ``ValueError`` au motif FRANÇAIS — c'est ce que les deux
packs attrapent déjà. Une liste vide, un PDF illisible, un fichier trop lourd
pour le stockage : la cause est NOMMÉE, jamais un 500.
"""
from __future__ import annotations

__all__ = ['DepotRefuse', 'fusionner_pdf', 'deposer_pdf']


class DepotRefuse(ValueError):
    """Refus de dépôt ou de fusion, message FRANÇAIS nommant la cause."""


def fusionner_pdf(parties):
    """Fusionne N PDF (octets, DANS L'ORDRE) en un seul flux paginé.

    Args:
        parties: itérable de ``(libelle, octets)`` — le libellé ne sert qu'aux
            messages de refus (nommer la pièce fautive, jamais « un PDF »).

    Returns:
        Les octets du PDF fusionné.

    Raises:
        DepotRefuse: liste vide, pièce vide, pièce illisible, ou PyMuPDF
            absent du serveur.
    """
    parties = [(libelle, octets) for libelle, octets in (parties or [])]
    if not parties:
        raise DepotRefuse('Aucun document à fusionner.')

    try:
        import fitz  # PyMuPDF — déjà en production, jamais une seconde plomberie
    except ImportError as erreur:  # pragma: no cover — dépendance présente
        raise DepotRefuse(
            "La bibliothèque PDF (PyMuPDF) n'est pas installée sur ce "
            'serveur : la fusion est impossible.') from erreur

    sortie = fitz.open()
    try:
        for libelle, octets in parties:
            if not octets:
                raise DepotRefuse(
                    'La pièce « %s » est vide : rien à fusionner.' % libelle)
            try:
                segment = fitz.open(stream=octets, filetype='pdf')
            except Exception as erreur:  # noqa: BLE001 — jamais un 500
                raise DepotRefuse(
                    "La pièce « %s » n'a pas pu être lue comme un PDF."
                    % libelle) from erreur
            try:
                sortie.insert_pdf(segment)
            finally:
                segment.close()
        return sortie.tobytes()
    finally:
        sortie.close()


def deposer_pdf(cible, octets, *, filename, company=None, user=None):
    """Dépose un PDF comme pièce jointe ``records`` de ``cible``.

    IDEMPOTENT PAR LE NOM DE FICHIER — et c'est la MÊME idempotence qu'avant.
    Le service de la GED ancrait le dépôt sur ``(source_type, source_id)``, où
    l'ancre des packs portait l'empreinte du layout ; ici l'ancre voyage dans
    ``filename``, que les deux packs composent avec cette même empreinte. Une
    pièce jointe de même cible ET même nom de fichier est donc RÉUTILISÉE
    (aucun second téléversement), et une conception MODIFIÉE — donc une autre
    empreinte, donc un autre nom — en produit une nouvelle. Relancer un pack
    sur la même conception ne duplique rien, exactement comme avant.

    Le nom MÉTIER du document n'est PAS rangé ici : la pièce jointe générique
    n'a pas de champ « nom », et inventer une table pour le porter serait
    rouvrir un référentiel documentaire que ce module n'a pas à tenir. Ce sont
    les deux packs qui publient leur nom, comme avant.

    Args:
        cible: l'objet métier auquel la pièce se rattache (le calepinage) —
            la pièce jointe est générique (``content_type``/``object_id``).
        octets: le contenu du PDF.
        filename: le nom de fichier (``…​.pdf``) — ce que l'utilisateur voit,
            et l'ancre d'idempotence.
        company: la société — POSÉE côté serveur ; à défaut celle de ``cible``.
        user: l'auteur du dépôt, s'il est connu.

    Returns:
        ``(attachment, cree)`` — l'``records.Attachment`` et un booléen VRAI
        seulement si le dépôt a réellement eu lieu. Le ``pk`` de la pièce est
        l'identifiant que les modèles du module rangent dans leur colonne
        ``document_id`` OPAQUE.

    Raises:
        DepotRefuse: contenu vide, société absente, ou refus du service de
            stockage (type réel non PDF, fichier trop volumineux) — le motif
            du service est rendu TEL QUEL.
    """
    from django.contrib.contenttypes.models import ContentType
    from django.core.files.base import ContentFile

    from apps.records.models import Attachment
    from apps.records.storage import store_attachment

    if not octets:
        raise DepotRefuse('Document vide : rien à déposer.')
    company = company or getattr(cible, 'company', None)
    if company is None:
        raise DepotRefuse(
            'Un document se dépose toujours dans une société.')

    nom_fichier = (filename or 'document.pdf')[:255]
    type_cible = ContentType.objects.get_for_model(type(cible))
    deja = (Attachment.objects
            .filter(company=company, content_type=type_cible,
                    object_id=getattr(cible, 'pk', None),
                    filename=nom_fichier)
            .order_by('id').first())
    if deja is not None:
        return deja, False

    fichier = ContentFile(octets, name=nom_fichier)
    depose, refus = store_attachment(fichier, company=company)
    if refus:
        raise DepotRefuse(refus)

    piece = Attachment.objects.create(
        company=company,
        content_type=type_cible,
        object_id=getattr(cible, 'pk', None),
        file_key=depose['file_key'],
        filename=nom_fichier,
        size=depose['size'],
        mime=depose['mime'] or 'application/pdf',
        uploaded_by=user if getattr(user, 'pk', None) else None,
    )
    return piece, True
