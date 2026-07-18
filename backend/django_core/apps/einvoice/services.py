"""Services de facturation électronique DGI (NTMAR5-7, NTMAR9).

Gaté par ``EINVOICE_ENABLED`` (settings, défaut OFF) : app entièrement
inerte tant que le flag n'est pas posé — ``generer`` renvoie ``None`` sans
rien écrire. RÉUTILISE l'export UBL existant de ``apps.ventes.dgi.dgi_export``
(N105) — n'introduit AUCUN nouveau moteur de rendu (rule #4 : le moteur de
devis PDF n'est jamais concerné, ceci ne rend QUE du XML de facture).
"""
import hashlib
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import FactureElectronique, TransmissionDGI


def is_einvoice_enabled(company=None):
    """NTMAR5 — flag maître (défaut OFF, no-op invisible si désactivé)."""
    return bool(getattr(settings, 'EINVOICE_ENABLED', False))


def is_dgi_transmission_enabled():
    """NTMAR7 — flag de transmission Simpl (défaut OFF, distinct de
    ``EINVOICE_ENABLED`` : on peut générer localement sans jamais transmettre)."""
    return bool(getattr(settings, 'DGI_TRANSMISSION_ENABLED', False))


# ── MinIO (client local, même patron que ``core.pdf._minio_client`` — recopié
# pour que cette app n'importe pas ``core.pdf`` qui est spécialisé PDF) ───────

def _minio_client():
    import boto3
    return boto3.client(
        's3',
        endpoint_url='http://' + settings.MINIO_ENDPOINT,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        region_name='us-east-1',
    )


def _upload_xml(xml_str, key, bucket=None):
    """Upload best-effort du XML dans MinIO. Toute erreur remonte à
    l'appelant (upload explicitement demandé, jamais avalé silencieusement)."""
    bucket = bucket or getattr(settings, 'MINIO_BUCKET_UPLOADS', 'erp-uploads')
    client = _minio_client()
    try:
        client.head_bucket(Bucket=bucket)
    except Exception:
        try:
            client.create_bucket(Bucket=bucket)
        except Exception:
            pass
    client.put_object(
        Bucket=bucket, Key=key, Body=xml_str.encode('utf-8'),
        ContentType='application/xml')
    return key


def _download_xml(key, bucket=None):
    bucket = bucket or getattr(settings, 'MINIO_BUCKET_UPLOADS', 'erp-uploads')
    client = _minio_client()
    obj = client.get_object(Bucket=bucket, Key=key)
    body = obj['Body'].read()
    if isinstance(body, bytes):
        return body.decode('utf-8')
    return body


def generer(facture_id, company, *, mode=FactureElectronique.Mode.DRY_RUN,
            user=None):
    """NTMAR5 — génère le XML DGI d'une facture ``ventes``.

    Flag OFF (``EINVOICE_ENABLED``) → renvoie ``None``, aucune écriture
    (app inerte). Flag ON → résout la facture via le sélecteur cross-app
    ``apps.ventes.selectors.get_facture_scoped`` (jamais un import de modèle),
    construit le XML via ``apps.ventes.dgi.dgi_export.build_ubl_xml``
    (réutilisation stricte, aucun nouveau moteur), le téléverse dans MinIO et
    crée UNE NOUVELLE version (NTMAR9, jamais d'écrasement). ``statut`` posé
    à ``genere`` — jamais ``signe``/``transmis`` ici.
    """
    if not is_einvoice_enabled(company):
        return None

    from apps.ventes.dgi import build_ubl_xml
    from apps.ventes.selectors import get_facture_scoped

    facture = get_facture_scoped(company, facture_id)
    if facture is None:
        raise ValidationError(
            "Facture introuvable pour cette société — aucune e-facture générée.")

    xml_str = build_ubl_xml(facture)
    hash_contenu = hashlib.sha256(xml_str.encode('utf-8')).hexdigest()

    dernier = (
        FactureElectronique.objects
        .filter(company=company, facture_id=facture_id)
        .order_by('-version').first())
    version = (dernier.version + 1) if dernier else 1

    key = f'einvoice/{company.id}/{uuid.uuid4()}.xml'
    _upload_xml(xml_str, key)

    return FactureElectronique.objects.create(
        company=company,
        facture_id=facture_id,
        facture_ref=getattr(facture, 'reference', '') or '',
        format=FactureElectronique.Format.UBL,
        mode=mode,
        statut=FactureElectronique.Statut.GENERE,
        version=version,
        xml_key=key,
        hash_contenu=hash_contenu,
        genere_le=timezone.now(),
        created_by=user if getattr(user, 'is_authenticated', True) else None,
    )


def regenerer(fe, *, user=None):
    """NTMAR9 — régénère (nouvelle version immuable) depuis la MÊME facture
    d'origine que ``fe``, avec le même ``mode``. Ne modifie jamais ``fe``."""
    return generer(fe.facture_id, fe.company, mode=fe.mode, user=user)


def telecharger_xml(fe):
    """NTMAR9 — récupère le contenu XML original depuis MinIO (str)."""
    if not fe.xml_key:
        raise ValidationError("Aucun XML stocké pour cette e-facture.")
    return _download_xml(fe.xml_key)


def preparer_signature(fe):
    """NTMAR6 — calcule l'empreinte à signer et laisse le terrain prêt
    (``signature_xml``/``certificat_ref``/``signe_le``) SANS signer : la
    signature certifiée dépend de la plateforme DGI live (gaté G14).

    ``EINVOICE_SIGNATURE_PROVIDER`` (défaut ``noop``) retombe proprement —
    aucun provider réel n'est câblé ici. ``fe.statut`` reste ``genere``,
    JAMAIS ``signe``, tant qu'aucun vrai provider n'existe.
    """
    provider = getattr(settings, 'EINVOICE_SIGNATURE_PROVIDER', 'noop')
    empreinte = fe.hash_contenu
    if provider == 'noop':
        return {
            'empreinte': empreinte,
            'provider': provider,
            'signe': False,
            'statut': fe.statut,
        }
    # Emplacement réservé pour un futur provider réel (jamais atteint tant
    # qu'aucune clé/URL de signature certifiée n'est configurée).
    return {
        'empreinte': empreinte,
        'provider': provider,
        'signe': False,
        'statut': fe.statut,
    }


def transmettre(fe):
    """NTMAR7 — étend G14 : file d'attente de transmission Simpl, INERTE tant
    que ``DGI_TRANSMISSION_ENABLED`` est OFF (défaut) ou que l'URL/clé DGI
    n'est pas configurée. N'émet AUCUNE requête réseau dans ce cas — enregistre
    seulement l'intention (``statut=en_attente``)."""
    transmission, _created = TransmissionDGI.objects.get_or_create(
        company=fe.company, einvoice=fe,
        defaults={'statut': TransmissionDGI.Statut.EN_ATTENTE})

    dgi_url = getattr(settings, 'DGI_TRANSMISSION_URL', '') or ''
    if not is_dgi_transmission_enabled() or not dgi_url:
        # Structure prête pour le jour où la DGI publie son API — aucune
        # requête sortante tant que le flag/l'URL ne sont pas configurés.
        return transmission

    # Emplacement réservé pour la transmission réelle (GATED-founder) —
    # jamais atteint sans configuration explicite du founder.
    return transmission
