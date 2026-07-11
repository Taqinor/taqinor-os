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


# ── Q4 — Rendu 3D de toiture (image) dans le bucket PDF ──────────────────────
# Le snapshot 3D est stocké dans le MÊME bucket que les PDF (réutilise toute
# l'infra existante : client MinIO + bucket erp-pdf), sous une clé scopée
# société pour éviter toute collision/fuite inter-tenant. La récupération se
# fait par URL pré-signée (lecture seule, expiration courte) — jamais d'accès
# public direct au bucket.

def upload_roof_image(image_bytes, key, content_type='image/png'):
    """Upload a roof-render image to the (existing) PDF bucket under `key`."""
    client = get_minio_client()
    client.put_object(
        Bucket=settings.MINIO_BUCKET_PDF,
        Key=key,
        Body=image_bytes,
        ContentType=content_type,
    )


def download_roof_image(key):
    """Stream a roof-render image from the PDF bucket. Returns bytes or raises."""
    client = get_minio_client()
    resp = client.get_object(Bucket=settings.MINIO_BUCKET_PDF, Key=key)
    return resp['Body'].read()


def roof_image_signed_url(key, expires=3600):
    """Pre-signed, read-only GET URL for a stored roof-render image (1 h)."""
    client = get_minio_client()
    return client.generate_presigned_url(
        'get_object',
        Params={'Bucket': settings.MINIO_BUCKET_PDF, 'Key': key},
        ExpiresIn=expires,
    )


# ── Image embedding ──────────────────────────────────────────────────────────

def _trim_image_whitespace(raw_bytes):
    """QD1 — Rogne les marges transparentes/blanches autour d'un logo.

    Beaucoup de logos sont livrés dans un canevas quasi carré avec de larges
    marges : la règle CSS ``max-height`` s'applique alors au canevas entier et
    rapetisse le logo VISIBLE. On recadre donc au contenu réel (transparence
    d'abord, sinon marges blanches) avant l'embarquement, pour que la hauteur
    max s'applique au logo lui-même.

    Renvoie ``(bytes, ext)`` — l'image rognée en PNG (ext='png') si un rognage a
    eu lieu, sinon ``(raw_bytes, None)`` (image inchangée). Best-effort et
    GARDÉ : sans Pillow, ou en cas d'erreur, on renvoie l'image inchangée
    (dégradation propre, aucun crash, aucune distorsion du ratio)."""
    try:
        from io import BytesIO as _BytesIO
        from PIL import Image, ImageChops
        img = Image.open(_BytesIO(raw_bytes))
        img.load()
        has_alpha = img.mode in ('RGBA', 'LA') or (
            img.mode == 'P' and 'transparency' in img.info)
        if has_alpha:
            work = img.convert('RGBA')
            # Boîte englobante des pixels non totalement transparents.
            bbox = work.getchannel('A').getbbox()
        else:
            work = img.convert('RGB')
            # Différence avec un fond blanc → boîte du contenu non-blanc.
            bg = Image.new('RGB', work.size, (255, 255, 255))
            bbox = ImageChops.difference(work, bg).getbbox()
        if not bbox:
            return raw_bytes, None  # image vide / uniforme → ne touche à rien
        # Rognage nul (le logo occupe déjà tout le canevas) → inchangé.
        if bbox == (0, 0, work.width, work.height):
            return raw_bytes, None
        cropped = work.crop(bbox)
        out = _BytesIO()
        cropped.save(out, format='PNG')
        return out.getvalue(), 'png'
    except Exception as exc:  # noqa: BLE001 — best-effort, jamais de crash
        logger.warning('Rognage du logo échoué (image inchangée) : %s', exc)
        return raw_bytes, None


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
            # QD1 — rogne d'abord les marges pour que la hauteur max CSS
            # s'applique au logo lui-même, pas à un canevas à larges marges.
            trimmed, ext = _trim_image_whitespace(raw)
            ctx['logo_uri'] = _to_data_uri(
                trimmed, ext or profile.logo_key)

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
    # XFAC19 — QR paiement/vérification (PDF facture LEGACY uniquement, jamais
    # le moteur devis premium). Ajout silencieux : None → footer inchangé.
    try:
        from apps.ventes.services import qr_svg_for_facture_pdf
        context['facture_qr_svg'] = qr_svg_for_facture_pdf(facture)
    except Exception as exc:  # noqa: BLE001 — best-effort, jamais de crash PDF
        logger.warning('QR facture %s indisponible : %s', facture_id, exc)
        context['facture_qr_svg'] = None

    # XSAL13 — rendu arabe RTL quand Client.langue_document == 'ar'. Défaut
    # FR octet-identique : langue absente/non-AR → 'fr', gabarit inchangé.
    from .libelles_ar import document_langue, libelle, arabic_font_face_css
    langue = document_langue(facture.client)
    context['langue_document'] = langue
    context['L'] = lambda cle: libelle(cle, langue)
    context['arabic_font_face_css'] = arabic_font_face_css() if langue == 'ar' else ''

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


def generate_note_debit_pdf(note_debit_id):
    """ZFAC4 — generate, upload and persist PDF for a NoteDebit. Returns MinIO
    key. Layout legacy facture (templates/pdf/note_debit.html, copie
    relabellée de avoir.html), aucune refonte visuelle."""
    from apps.ventes.models import NoteDebit
    note_debit = (
        NoteDebit.objects
        .select_related('client', 'created_by', 'company', 'facture')
        .prefetch_related('lignes__produit')
        .get(pk=note_debit_id)
    )

    context = _company_context(company=note_debit.company)
    context['note_debit'] = note_debit

    html = _render_html('note_debit.html', context)
    pdf_bytes = _html_to_pdf(html)

    key = f'notes-debit/{note_debit.reference}.pdf'
    _upload_pdf(pdf_bytes, key)

    note_debit.fichier_pdf = key
    note_debit.save(update_fields=['fichier_pdf'])

    logger.info('PDF note de débit généré : %s', key)
    return key


def generate_bon_commande_pdf(bc_id):
    """ZSAL8 — PDF imprimable du bon de commande CLIENT (rendu à la volée,
    non stocké — layout maison LEGACY, PAS le moteur devis premium, réservé
    au devis client par la règle #4). Identité société (ICE/IF/RC),
    lignes de l'option retenue du devis d'origine (jamais ``prix_achat``),
    chaîne Sous-total → Remise → HT → TVA → TTC, statut de livraison."""
    from decimal import Decimal

    from apps.ventes.models import BonCommande
    from apps.ventes.utils.options import option_lines, option_totaux

    bc = (
        BonCommande.objects
        .select_related('client', 'devis', 'company')
        .get(pk=bc_id)
    )

    context = _company_context(company=bc.company)
    context['bc'] = bc
    if bc.devis:
        context['lignes'] = option_lines(bc.devis)
        totaux = option_totaux(bc.devis)
        # QX1 — ``option_totaux`` renvoie désormais les totaux NETS (remise
        # globale déjà appliquée), plus le brut/remise pour l'affichage. Le
        # template reçoit le brut (Sous-total HT) + la remise (delta) + les
        # valeurs nettes (HT net, TVA sur net, TTC) : plus de double
        # soustraction, plus de sur-facturation.
        context['total_ht_brut'] = totaux.get('ht_brut', totaux['ht'])
        context['total_ht'] = totaux['ht']          # HT NET (après remise)
        context['total_tva'] = totaux['tva']         # TVA sur le HT net
        context['total_ttc'] = totaux['ttc']         # TTC net
        context['remise_montant'] = totaux.get('remise', Decimal('0'))
        context['remise_globale'] = bc.devis.remise_globale or Decimal('0')
    else:
        context['lignes'] = []
        context['total_ht_brut'] = Decimal('0')
        context['total_ht'] = Decimal('0')
        context['total_tva'] = Decimal('0')
        context['total_ttc'] = Decimal('0')
        context['remise_montant'] = Decimal('0')
        context['remise_globale'] = Decimal('0')

    html = _render_html('bon_commande.html', context)
    return _html_to_pdf(html)


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


def generate_proforma_pdf(devis, reference):
    """XFAC10 — facture pro-forma NON comptabilisée (layout facture legacy,
    variante filigranée). Rendu à la volée, non stocké — ne touche jamais le
    moteur devis premium (RULE #4 : /proposal reste le seul chemin PDF
    client-facing pour un DEVIS ; ceci est un rendu FACTURE, pas un devis)."""
    context = _company_context(company=devis.company)
    context['devis'] = devis
    context['reference'] = reference
    html = _render_html('proforma.html', context)
    return _html_to_pdf(html)


def generate_dossier_contentieux_pdf(client, dossier_data):
    """XFAC21 — pack PDF complet du dossier contentieux (recouvrement externe).

    Rendu à la volée, non stocké (comme le relevé) — layout maison, jamais le
    moteur devis premium (RULE #4 : ceci ne concerne AUCUN devis)."""
    context = _company_context(company=client.company)
    context['dossier'] = dossier_data
    html = _render_html('dossier_contentieux.html', context)
    return _html_to_pdf(html)


def generate_recu_pdf(paiement):
    """XFAC9 — quittance (reçu de paiement) PDF. Layout maison (PAS le moteur
    devis) : identité société, montant en chiffres ET en lettres, mode,
    référence(s) facture(s) réglée(s) avec le détail d'affectation (XFAC1 si
    présent), solde restant. Rendu à la volée, non stocké (jamais de prix
    d'achat)."""
    from decimal import Decimal
    from apps.ventes.utils.nombre_lettres import montant_en_lettres

    company = paiement.company
    client = paiement.facture.client if paiement.facture_id else paiement.client
    client_nom = ''
    if client is not None:
        client_nom = f"{client.nom} {client.prenom or ''}".strip()

    affectations = list(paiement.affectations.select_related('facture').all()) \
        if paiement.facture_id is None else []
    facture_reference = paiement.facture.reference if paiement.facture_id else None
    if affectations:
        solde_restant = sum(
            (a.facture.montant_du for a in affectations), Decimal('0'))
    elif paiement.facture_id:
        solde_restant = paiement.facture.montant_du
    else:
        solde_restant = paiement.montant_disponible

    context = _company_context(company=company)
    context['paiement'] = paiement
    context['client_nom'] = client_nom
    context['facture_reference'] = facture_reference
    context['affectations'] = affectations
    context['solde_restant'] = solde_restant
    context['montant_lettres'] = montant_en_lettres(paiement.montant)

    html = _render_html('recu.html', context)
    return _html_to_pdf(html)


def generate_bordereau_remise_pdf(remise_id):
    """XFSM19 — bordereau PDF d'une remise d'encaissement terrain.

    Layout maison (PAS le moteur devis) : identité société, technicien,
    lignes (paiement/mode/date/facture), montant déclaré vs somme des
    lignes, écart. Généré à la clôture ; uploadé + persisté sur
    ``RemiseEncaissement.fichier_pdf`` comme les autres PDF stockés
    (devis/facture/avoir). Renvoie les octets PDF."""
    from apps.ventes.models import RemiseEncaissement

    remise = (
        RemiseEncaissement.objects
        .select_related('technicien', 'company')
        .prefetch_related('lignes__paiement__facture')
        .get(pk=remise_id)
    )

    context = _company_context(company=remise.company)
    context['remise'] = remise
    context['lignes'] = list(remise.lignes.all())
    context['montant_lignes'] = remise.montant_lignes
    context['ecart'] = remise.ecart

    html = _render_html('bordereau_remise.html', context)
    pdf_bytes = _html_to_pdf(html)

    key = f'remises-encaissement/{remise.company_id}/{remise.reference or remise.id}.pdf'
    _upload_pdf(pdf_bytes, key)

    remise.fichier_pdf = key
    remise.save(update_fields=['fichier_pdf'])

    logger.info('PDF bordereau de remise généré : %s', key)
    return pdf_bytes
