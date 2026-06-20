"""
PDF generation pipeline:
  1. Load CompanyProfile (logo, signature, branding)
  2. Embed images as base64 data-URIs (WeasyPrint needs inline images)
  3. Render Jinja2 template → HTML string
  4. WeasyPrint HTML → PDF bytes
  5. Upload to MinIO erp-pdf bucket
  6. Update model.fichier_pdf with the stored key
"""
import base64
import logging
from io import BytesIO

from django.conf import settings
from django.template.loader import get_template
import weasyprint

from .minio_client import get_minio_client

logger = logging.getLogger(__name__)


# ── MinIO helpers ────────────────────────────────────────────────────────────

def _download(bucket, key):
    """Download bytes from MinIO. Returns None on error."""
    try:
        client = get_minio_client()
        resp = client.get_object(Bucket=bucket, Key=key)
        return resp['Body'].read()
    except Exception as exc:
        logger.warning('MinIO download failed %s/%s: %s', bucket, key, exc)
        return None


def _upload_pdf(pdf_bytes, key):
    client = get_minio_client()
    client.put_object(
        Bucket=settings.MINIO_BUCKET_PDF,
        Key=key,
        Body=pdf_bytes,
        ContentType='application/pdf',
    )


def download_pdf(key):
    """Stream a PDF from MinIO. Returns bytes or raises."""
    client = get_minio_client()
    resp = client.get_object(Bucket=settings.MINIO_BUCKET_PDF, Key=key)
    return resp['Body'].read()


# ── Image embedding ──────────────────────────────────────────────────────────

def _to_data_uri(raw_bytes, key):
    """Convert raw image bytes to a base64 data-URI."""
    ext = key.rsplit('.', 1)[-1].lower() if '.' in key else 'png'
    mime = {
        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
        'png': 'image/png', 'webp': 'image/webp',
    }.get(ext, 'image/png')
    b64 = base64.b64encode(raw_bytes).decode()
    return f'data:{mime};base64,{b64}'


# ── Company context ──────────────────────────────────────────────────────────

def _company_context(company=None):
    """Return branding variables for PDF templates."""
    from apps.parametres.models import CompanyProfile
    profile = CompanyProfile.get(company=company)

    ctx = {
        'entreprise_nom': (
            profile.nom or settings.ENTREPRISE_NOM
        ),
        'entreprise_adresse': (
            profile.adresse or settings.ENTREPRISE_ADRESSE
        ),
        'entreprise_email': (
            profile.email or settings.ENTREPRISE_EMAIL
        ),
        'entreprise_telephone': (
            profile.telephone or settings.ENTREPRISE_TELEPHONE
        ),
        'entreprise_siret':     profile.siret,
        'entreprise_tva_intra': profile.tva_intra,
        # Identifiants légaux marocains (l'ICE est obligatoire sur facture).
        'entreprise_ice':       getattr(profile, 'ice', ''),
        'entreprise_if':        getattr(profile, 'identifiant_fiscal', ''),
        'entreprise_rc':        getattr(profile, 'rc', ''),
        'entreprise_patente':   getattr(profile, 'patente', ''),
        'entreprise_cnss':      getattr(profile, 'cnss', ''),
        'couleur_principale': (
            profile.couleur_principale or settings.ENTREPRISE_COULEUR
        ),
        'rib':    profile.rib,
        'banque': profile.banque,
        # Feature B — blocs paiement & conditions (rendus seulement si non-vides).
        'instructions_paiement': getattr(profile, 'instructions_paiement', ''),
        'conditions_generales': getattr(profile, 'conditions_generales', ''),
        'logo_uri':      None,
        'signature_uri': None,
    }

    if profile.logo_key:
        raw = _download(settings.MINIO_BUCKET_UPLOADS, profile.logo_key)
        if raw:
            ctx['logo_uri'] = _to_data_uri(raw, profile.logo_key)

    if profile.signature_key:
        raw = _download(
            settings.MINIO_BUCKET_UPLOADS, profile.signature_key
        )
        if raw:
            ctx['signature_uri'] = _to_data_uri(
                raw, profile.signature_key
            )

    return ctx


# ── Core render/convert ──────────────────────────────────────────────────────

def _render_html(template_name, context):
    template = get_template(template_name)
    return template.render(context)


def _html_to_pdf(html_string):
    buf = BytesIO()
    weasyprint.HTML(string=html_string).write_pdf(buf)
    buf.seek(0)
    return buf.read()


# ── Public API ───────────────────────────────────────────────────────────────

def generate_devis_pdf(devis_id):
    """Generate, upload and persist PDF for a Devis. Returns MinIO key."""
    from apps.ventes.models import Devis
    devis = (
        Devis.objects
        .select_related('client', 'created_by', 'company')
        .prefetch_related('lignes__produit')
        .get(pk=devis_id)
    )

    context = _company_context(company=devis.company)
    context['devis'] = devis

    html = _render_html('devis.html', context)
    pdf_bytes = _html_to_pdf(html)

    # ERR75 — company-scope the legacy fallback key so two tenants sharing a
    # reference (per-company/month numbering) can never collide on the same
    # MinIO object. Mirrors the premium path (builder._pdf_key).
    key = f'devis/{devis.company_id}/{devis.reference}.pdf'
    _upload_pdf(pdf_bytes, key)

    devis.fichier_pdf = key
    devis.save(update_fields=['fichier_pdf'])

    logger.info('PDF devis généré : %s', key)
    return key


def generate_facture_pdf(facture_id):
    """Generate, upload and persist PDF for a Facture. Returns MinIO key."""
    from apps.ventes.models import Facture
    facture = (
        Facture.objects
        .select_related('client', 'created_by', 'bon_commande', 'company')
        .prefetch_related('lignes__produit')
        .get(pk=facture_id)
    )

    context = _company_context(company=facture.company)
    context['facture'] = facture

    html = _render_html('facture.html', context)
    pdf_bytes = _html_to_pdf(html)

    key = f'factures/{facture.reference}.pdf'
    _upload_pdf(pdf_bytes, key)

    facture.fichier_pdf = key
    facture.save(update_fields=['fichier_pdf'])

    logger.info('PDF facture généré : %s', key)
    return key


def generate_avoir_pdf(avoir_id):
    """Generate, upload and persist PDF for an Avoir. Returns MinIO key.

    Réutilise le STYLE facture (templates/pdf/avoir.html en est une copie
    relabellée « AVOIR »), aucune refonte visuelle."""
    from apps.ventes.models import Avoir
    avoir = (
        Avoir.objects
        .select_related('client', 'created_by', 'company', 'facture')
        .prefetch_related('lignes__produit')
        .get(pk=avoir_id)
    )

    context = _company_context(company=avoir.company)
    context['avoir'] = avoir

    html = _render_html('avoir.html', context)
    pdf_bytes = _html_to_pdf(html)

    key = f'avoirs/{avoir.reference}.pdf'
    _upload_pdf(pdf_bytes, key)

    avoir.fichier_pdf = key
    avoir.save(update_fields=['fichier_pdf'])

    logger.info('PDF avoir généré : %s', key)
    return key


def generate_releve_pdf(client, releve_data):
    """Relevé de compte client (style maison) — rendu à la volée, non stocké."""
    context = _company_context(company=client.company)
    context['releve'] = releve_data
    html = _render_html('releve.html', context)
    return _html_to_pdf(html)


def generate_lettre_relance_pdf(facture, niveau, message):
    """Lettre de relance pour une facture en retard (style maison)."""
    context = _company_context(company=facture.company)
    context['facture'] = facture
    context['niveau'] = niveau
    context['message'] = message
    html = _render_html('lettre_relance.html', context)
    return _html_to_pdf(html)
