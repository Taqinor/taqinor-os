"""FG95 — Export PDF branded pour les rapports (ventes / stock / service).

Rendu WeasyPrint + Jinja2 en mémoire (jamais stocké MinIO) ; les prix d'achat
n'apparaissent JAMAIS dans la sortie cliente.  Le logo vient du CompanyProfile
(logo_key → MinIO erp-media) et s'encode en data-URI base64.

Usage interne :
    from apps.reporting.report_pdf import pdf_response
    return pdf_response(request, title='Rapport Ventes', sections=...)

ARC12 — la plomberie WeasyPrint (``HTML(string=...).write_pdf()``) est
déléguée au service partagé ``core.pdf.render_pdf`` ; le GABARIT Jinja2
ci-dessus reste STRICTEMENT identique, donc le rendu est inchangé à l'octet
près.
"""
import base64
import logging
from datetime import date

from django.http import HttpResponse
from jinja2 import Environment

from core.pdf import render_pdf

logger = logging.getLogger(__name__)

# ── Jinja2 template (inline, pas de fichiers extra) ───────────────────────────
_TEMPLATE_SRC = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<style>
  @page { size: A4; margin: 20mm 18mm; }
  body { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
         font-size: 10pt; color: #1a1a2e; }
  .header { display: flex; align-items: center; margin-bottom: 10mm;
             border-bottom: 2px solid {{ color }}; padding-bottom: 4mm; }
  .header img { height: 30mm; margin-right: 8mm; }
  .header-text h1 { margin: 0; font-size: 16pt; color: {{ color }}; }
  .header-text p  { margin: 2px 0; font-size: 8pt; color: #555; }
  .meta { margin-bottom: 6mm; font-size: 8pt; color: #666; }
  h2 { font-size: 11pt; color: {{ color }}; border-bottom: 1px solid #dde;
       padding-bottom: 2px; margin-top: 6mm; }
  table { border-collapse: collapse; width: 100%; margin-bottom: 4mm; }
  th { background: {{ color }}; color: #fff; text-align: left;
       padding: 3px 6px; font-size: 9pt; }
  td { border-bottom: 1px solid #e8e8ee; padding: 3px 6px; font-size: 9pt; }
  tr:nth-child(even) td { background: #f5f5fb; }
  .kv { display: flex; flex-wrap: wrap; gap: 4mm; margin-bottom: 4mm; }
  .kv-item { background: #f0f4ff; border-left: 3px solid {{ color }};
              padding: 2mm 4mm; min-width: 40mm; }
  .kv-item .label { font-size: 7pt; color: #777; margin-bottom: 1mm; }
  .kv-item .value { font-size: 11pt; font-weight: bold; color: {{ color }}; }
  .footer { position: fixed; bottom: 8mm; right: 0; left: 0; text-align: center;
             font-size: 7pt; color: #aaa; border-top: 1px solid #dde;
             padding-top: 2mm; }
</style>
</head>
<body>
<div class="header">
  {% if logo_uri %}<img src="{{ logo_uri }}" alt="logo">{% endif %}
  <div class="header-text">
    <h1>{{ title }}</h1>
    <p>{{ company.nom }}</p>
    {% if company.adresse %}<p>{{ company.adresse }}</p>{% endif %}
    {% if company.email %}<p>{{ company.email }}</p>{% endif %}
  </div>
</div>
<div class="meta">
  Généré le {{ today }}
  {% if period_label %} · Période : {{ period_label }}{% endif %}
</div>
{% for section in sections %}
  <h2>{{ section.title }}</h2>
  {% if section.kv %}
  <div class="kv">
    {% for item in section.kv %}
    <div class="kv-item">
      <div class="label">{{ item.label }}</div>
      <div class="value">{{ item.value }}</div>
    </div>
    {% endfor %}
  </div>
  {% endif %}
  {% if section.table %}
  <table>
    <thead><tr>{% for h in section.table.headers %}<th>{{ h }}</th>{% endfor %}</tr></thead>
    <tbody>
      {% for row in section.table.rows %}
      <tr>{% for cell in row %}<td>{{ cell }}</td>{% endfor %}</tr>
      {% endfor %}
      {% if not section.table.rows %}
      <tr><td colspan="{{ section.table.headers|length }}" style="color:#aaa;font-style:italic;">
        Aucune donnée sur la période.
      </td></tr>
      {% endif %}
    </tbody>
  </table>
  {% endif %}
{% endfor %}
<div class="footer">{{ company.nom }} — Rapport généré par Taqinor OS</div>
</body>
</html>
"""

_jinja_env = Environment(autoescape=True)
_template = _jinja_env.from_string(_TEMPLATE_SRC)


def _logo_data_uri(logo_key: str) -> str | None:
    """Télécharge le logo depuis MinIO (bucket erp-media) et le rend data-URI."""
    if not logo_key:
        return None
    try:
        from django.conf import settings
        from apps.ventes.utils.minio_client import get_minio_client
        client = get_minio_client()
        bucket = getattr(settings, 'MINIO_BUCKET_MEDIA', 'erp-media')
        resp = client.get_object(Bucket=bucket, Key=logo_key)
        raw = resp['Body'].read()
        ext = logo_key.rsplit('.', 1)[-1].lower() if '.' in logo_key else 'png'
        mime = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                'png': 'image/png', 'webp': 'image/webp',
                'svg': 'image/svg+xml'}.get(ext, 'image/png')
        b64 = base64.b64encode(raw).decode()
        return f'data:{mime};base64,{b64}'
    except Exception as exc:
        logger.warning('Logo fetch failed (%s): %s', logo_key, exc)
        return None


def render_report_pdf(
    *,
    title: str,
    sections: list,
    company_profile,
    period_label: str = '',
) -> bytes:
    """Rend le rapport en PDF (bytes).

    ``sections`` est une liste de dicts :
      { title: str,
        kv: [{label, value}, ...] | None,
        table: {headers: [...], rows: [[...], ...]} | None }

    ``company_profile`` est une instance CompanyProfile (peut être None).
    """
    if company_profile:
        logo_uri = _logo_data_uri(company_profile.logo_key)
        color = company_profile.couleur_principale or '#2563EB'
        co_ctx = {
            'nom': company_profile.nom,
            'adresse': company_profile.adresse,
            'email': company_profile.email,
        }
    else:
        logo_uri = None
        color = '#2563EB'
        co_ctx = {'nom': '', 'adresse': '', 'email': ''}

    html_str = _template.render(
        title=title,
        logo_uri=logo_uri,
        color=color,
        company=co_ctx,
        today=date.today().strftime('%d/%m/%Y'),
        period_label=period_label,
        sections=sections,
    )

    return render_pdf(html=html_str)


def pdf_response(pdf_bytes: bytes, filename: str = 'rapport.pdf') -> HttpResponse:
    """Retourne un HttpResponse PDF prêt à streamer."""
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp
