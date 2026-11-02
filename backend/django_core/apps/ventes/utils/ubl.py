"""N38 — Export structuré local d'une facture au format UBL 2.1 (APERÇU
BROUILLON, travail préparatoire).

AARG20 — un seul constructeur : ``apps.ventes.dgi.dgi_export.build_ubl_xml``.
L'aperçu en est la copie octet pour octet, seul le commentaire de tête le marque
« APERCU BROUILLON — non transmis ».

PÉRIMÈTRE STRICT — groundwork uniquement :
  * AUCUN appel externe, AUCun endpoint DGI, AUCUN identifiant/clé.
  * Le XML est aussi déposé localement (MinIO) en best-effort ; l'échec de
    stockage n'empêche jamais la génération/le téléchargement.
"""
import logging

logger = logging.getLogger(__name__)


def build_ubl_xml(facture, profile, currency=None):
    """Aperçu UBL 2.1 d'une facture (str) : le XML DGI, commentaire de tête
    remplacé. ``currency`` : voir ``dgi_export.build_ubl_xml`` (FG52 / DC25)."""
    from apps.ventes.dgi.dgi_export import build_ubl_xml as construire
    declaration, _commentaire, corps = construire(
        facture, profile, currency).split('\n', 2)
    return '\n'.join((
        declaration,
        '<!-- APERCU BROUILLON UBL 2.1 — non transmis a la DGI, '
        'travail preparatoire (N38). -->',
        corps))


def store_ubl_xml(facture, xml_str):
    """Dépose le XML dans MinIO (best-effort) et renvoie la clé, ou None."""
    try:
        from django.conf import settings
        from .minio_client import get_minio_client
        key = f'ubl/{facture.company_id or 0}/{facture.reference}.xml'
        client = get_minio_client()
        client.put_object(
            Bucket=settings.MINIO_BUCKET_PDF,
            Key=key,
            Body=xml_str.encode('utf-8'),
            ContentType='application/xml',
        )
        return key
    except Exception as exc:  # pragma: no cover - stockage best-effort
        logger.warning('Stockage UBL échoué pour %s: %s',
                       facture.reference, exc)
        return None
