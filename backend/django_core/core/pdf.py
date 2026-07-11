"""ARC11 — Service de rendu PDF PARTAGÉ (hors devis).

Avant ARC11, ~45 fichiers appelaient WeasyPrint indépendamment (rh, compta,
qhse, pos, paie, reporting…), chacun re-codant la même plomberie :
``HTML(string=...).write_pdf()``, la gestion de l'import paresseux de la lib,
un en-tête/pied brandé et l'upload MinIO optionnel. Ce module CENTRALISE cette
plomberie une seule fois — les appelants gardent leur GABARIT (HTML/CSS) à
l'octet près et ne délèguent QUE les mécanismes dupliqués.

EXCLUSIONS ABSOLUES (règle #4, CLAUDE.md) — ne passent JAMAIS par ce service :
``apps/ventes/quote_engine/**`` (le moteur premium de devis client) et le PDF
FACTURE legacy. L'allowlist du garde-fou WeasyPrint (ARC52) les liste
nommément ; ce service est le chemin recommandé pour tout NOUVEAU PDF interne.

Découplage ``core`` (contrat import-linter ``core-foundation-is-a-base-layer``)
--------------------------------------------------------------------------------

``core`` reste une couche de fondation : AUCUN import d'app domaine.
* le branding est lu depuis ``parametres.CompanyProfile`` via
  ``django.apps.apps.get_model`` (résolution paresseuse par chaîne — jamais un
  ``from apps.parametres...`` qui créerait une arête d'import interdite) ;
* le client MinIO est reconstruit localement depuis ``settings`` (même patron
  que ``core.backup._minio_client`` — recopié depuis
  ``apps.ventes.utils.minio_client`` SANS l'importer).

API publique
------------

``render_pdf(html=None, *, template=None, context=None, company=None,
header=False, footer=False, upload_to=None, upload_bucket=None)`` :

* fournir SOIT ``html`` (chaîne HTML finale, cas des 3 pilotes qui gardent leur
  markup tel quel), SOIT ``template`` + ``context`` (rendu Django) ;
* ``header``/``footer`` sont OPT-IN (défaut ``False``) : quand ils sont activés,
  un bandeau brandé (raison sociale + identifiants légaux de ``CompanyProfile``)
  est injecté — les pilotes existants les laissent à ``False`` pour un rendu
  strictement identique ;
* ``upload_to`` (clé objet) déclenche un upload MinIO best-effort et
  ``render_pdf`` retourne alors le tuple ``(pdf_bytes, key)`` ; sans
  ``upload_to``, elle retourne simplement les ``bytes`` du PDF.
"""
from html import escape

from django.conf import settings

__all__ = ['render_pdf', 'branded_header_html', 'branded_footer_html']


# ── Plomberie WeasyPrint (import paresseux — lib lourde) ─────────────────────

def _html_to_pdf_bytes(html_string):
    """HTML → octets PDF via WeasyPrint (import FONCTION-LOCAL).

    Lève une ``RuntimeError`` explicite si WeasyPrint n'est pas installé (build
    allégé) — même contrat que les renderers RH/compta d'origine, plutôt qu'un
    ``ImportError`` opaque au chargement du module."""
    try:
        import weasyprint
    except ImportError as exc:  # pragma: no cover - dépend de l'environnement
        raise RuntimeError(
            "WeasyPrint n'est pas installé : génération PDF indisponible."
        ) from exc
    # ``write_pdf()`` SANS cible renvoie directement les octets PDF (API
    # WeasyPrint documentée) — même convention d'appel que les renderers
    # RH/compta/qhse d'origine, donc les tests existants qui mockent
    # ``HTML(...).write_pdf()`` (lambda sans argument) restent compatibles.
    return weasyprint.HTML(string=html_string).write_pdf()


# ── Branding OPT-IN depuis CompanyProfile (résolution paresseuse) ────────────

def _company_profile(company):
    """Retourne le ``CompanyProfile`` de la société (ou ``None``).

    Résolution PARESSEUSE par chaîne (``apps.get_model``) : ``core`` ne crée
    aucune arête d'import statique vers ``apps.parametres``."""
    if company is None:
        return None
    from django.apps import apps as django_apps
    try:
        Profile = django_apps.get_model('parametres', 'CompanyProfile')
    except LookupError:  # pragma: no cover - modèle toujours présent en prod
        return None
    return Profile.objects.filter(company=company).first()


def _identifiants_ligne(profile):
    """Ligne « ICE : … | IF : … | RC : … » (segments non vides seulement)."""
    segments = []
    ice = getattr(profile, 'ice', '') or ''
    if_fiscal = getattr(profile, 'identifiant_fiscal', '') or ''
    rc = getattr(profile, 'rc', '') or ''
    if ice:
        segments.append('ICE : ' + escape(ice))
    if if_fiscal:
        segments.append('IF : ' + escape(if_fiscal))
    if rc:
        segments.append('RC : ' + escape(rc))
    return ' &nbsp;|&nbsp; '.join(segments)


def branded_header_html(company):
    """En-tête brandé (raison sociale + identifiants) ou '' si pas de profil."""
    profile = _company_profile(company)
    if profile is None:
        return ''
    nom = escape(getattr(profile, 'nom', '') or '')
    identifiants = _identifiants_ligne(profile)
    ligne_id = ''
    if identifiants:
        ligne_id = '<div class="pdf-brand-ids">' + identifiants + '</div>'
    return (
        '<div class="pdf-brand-header" style="text-align:center;'
        'border-bottom:2px solid #444;padding-bottom:10px;margin-bottom:20px;">'
        '<div class="pdf-brand-nom" style="font-size:16px;font-weight:bold;">'
        + nom + '</div>' + ligne_id + '</div>'
    )


def branded_footer_html(company):
    """Pied brandé (adresse/contact) ou '' si pas de profil renseigné."""
    profile = _company_profile(company)
    if profile is None:
        return ''
    parts = []
    adresse = getattr(profile, 'adresse', '') or ''
    telephone = getattr(profile, 'telephone', '') or ''
    email = getattr(profile, 'email', '') or ''
    if adresse:
        parts.append(escape(adresse.replace('\n', ' ')))
    if telephone:
        parts.append('Tél : ' + escape(telephone))
    if email:
        parts.append(escape(email))
    if not parts:
        return ''
    contenu = ' &nbsp;|&nbsp; '.join(parts)
    return (
        '<div class="pdf-brand-footer" style="text-align:center;'
        'border-top:1px solid #ccc;padding-top:8px;margin-top:24px;'
        'font-size:10px;color:#555;">' + contenu + '</div>'
    )


def _inject_branding(html_string, company, header, footer):
    """Insère l'en-tête après ``<body>`` et le pied avant ``</body>``.

    Insertion textuelle simple (pas de parsing DOM) : si ``<body>`` n'est pas
    trouvé, on préfixe/suffixe le bandeau — le rendu reste valide."""
    if header:
        header_html = branded_header_html(company)
        if header_html:
            if '<body>' in html_string:
                html_string = html_string.replace(
                    '<body>', '<body>' + header_html, 1)
            else:
                html_string = header_html + html_string
    if footer:
        footer_html = branded_footer_html(company)
        if footer_html:
            if '</body>' in html_string:
                html_string = html_string.replace(
                    '</body>', footer_html + '</body>', 1)
            else:
                html_string = html_string + footer_html
    return html_string


# ── Upload MinIO OPTIONNEL (best-effort, client local) ───────────────────────

def _minio_client():
    """Client boto3/S3 vers MinIO (recopié de ventes.utils.minio_client pour
    que ``core`` reste dépendance-libre vis-à-vis des apps domaine — même
    patron que ``core.backup._minio_client``)."""
    import boto3
    return boto3.client(
        's3',
        endpoint_url='http://' + settings.MINIO_ENDPOINT,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        region_name='us-east-1',
    )


def _upload_pdf(pdf_bytes, key, bucket):
    """Téléverse ``pdf_bytes`` sous ``key`` dans ``bucket`` (crée le bucket au
    besoin). Retourne la clé. Best-effort : toute erreur remonte à l'appelant
    (l'upload est explicitement demandé, on ne l'avale pas silencieusement)."""
    client = _minio_client()
    try:
        client.head_bucket(Bucket=bucket)
    except Exception:
        try:
            client.create_bucket(Bucket=bucket)
        except Exception:
            pass
    client.put_object(
        Bucket=bucket, Key=key, Body=pdf_bytes,
        ContentType='application/pdf')
    return key


# ── API publique ─────────────────────────────────────────────────────────────

def render_pdf(html=None, *, template=None, context=None, company=None,
               header=False, footer=False, upload_to=None, upload_bucket=None):
    """Rend un PDF (bytes) à partir d'un HTML final OU d'un template Django.

    Paramètres
    ----------
    html : str, optionnel
        HTML final déjà construit par l'appelant (cas des pilotes qui gardent
        leur gabarit à l'octet près). Exclusif avec ``template``.
    template / context : str / dict, optionnel
        Nom de gabarit Django + contexte, rendus via ``render_to_string``.
    company : optionnel
        Société utilisée pour le branding OPT-IN de l'en-tête/pied.
    header / footer : bool
        Injecte un en-tête/pied brandé (défaut ``False`` — les pilotes gardent
        un rendu identique en les laissant désactivés).
    upload_to : str, optionnel
        Clé objet MinIO. Si fournie, le PDF est téléversé et la fonction
        retourne ``(pdf_bytes, key)`` au lieu des seuls ``bytes``.
    upload_bucket : str, optionnel
        Bucket cible (défaut ``settings.MINIO_BUCKET_UPLOADS``).

    Retour
    ------
    ``bytes`` (PDF) — ou ``(bytes, key)`` quand ``upload_to`` est fourni.
    """
    if html is None and template is None:
        raise ValueError("render_pdf exige 'html' ou 'template'.")
    if html is not None and template is not None:
        raise ValueError(
            "render_pdf : fournir 'html' OU 'template', pas les deux.")

    if template is not None:
        from django.template.loader import render_to_string
        html = render_to_string(template, context or {})

    if header or footer:
        html = _inject_branding(html, company, header, footer)

    pdf_bytes = _html_to_pdf_bytes(html)

    if upload_to:
        bucket = upload_bucket or settings.MINIO_BUCKET_UPLOADS
        key = _upload_pdf(pdf_bytes, upload_to, bucket)
        return pdf_bytes, key
    return pdf_bytes
