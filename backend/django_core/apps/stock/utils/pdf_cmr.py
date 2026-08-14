"""NTWMS43 — CMR simplifiée / lettre de voiture d'une expédition.

Document de transport routier standard pour les envois inter-villes au Maroc :
expéditeur, destinataire, nature des marchandises, poids total, nombre de
colis et références SSCC (NTWMS6).

DEUX RÈGLES DURES.
1. Ce PDF n'a AUCUN rapport avec le moteur de devis vendorisé (règle #4) :
   c'est un document INTERNE/transporteur, rendu par le WeasyPrint déjà en
   place pour les autres documents internes (``apps.ventes.utils.pdf``).
2. WHITE-LABEL : l'expéditeur vient TOUJOURS du profil de la société
   (``_company_context``). Aucune marque n'est écrite en dur — ce document
   part chez un transporteur tiers.

Le gabarit est construit ICI, en Python (même pratique que
``apps/stock/labels.py``) : cette lane ne possède pas le dossier de gabarits
partagé ``templates/pdf/``.
"""
from decimal import Decimal

from django.utils import timezone


def _esc(value):
    """Échappement HTML minimal — les valeurs viennent de la base."""
    return (str(value if value is not None else '')
            .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


def _dec(value):
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001 — valeur non numérique -> 0, jamais de crash.
        return Decimal('0')


def _fmt_dec(value):
    """Décimal normalisé (``'3.000'`` -> ``'3'``, ``'12.50'`` -> ``'12.5'``)."""
    value = value if isinstance(value, Decimal) else _dec(value)
    if value == 0:
        return '0'
    s = format(value, 'f')
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s or '0'


def _unites_de_lexpedition(expedition):
    """L'unité expédiée ET ses enfants (une palette porte des colis)."""
    unite = expedition.unite_logistique
    if unite is None:
        return []
    unites = [unite]
    unites.extend(list(unite.enfants.all()))
    return unites


def build_cmr_context(expedition):
    """Contexte de la lettre de voiture — LECTURE SEULE, rien n'est écrit.

    ``nb_colis`` compte les unités réellement transportées (la palette et ses
    colis) ; ``poids_total_kg`` somme leurs poids renseignés (une unité sans
    poids compte 0, jamais un poids inventé).
    """
    from apps.ventes.utils.pdf import _company_context

    context = _company_context(company=expedition.company)
    unites = _unites_de_lexpedition(expedition)

    marchandises = []
    poids_total = Decimal('0')
    for unite in unites:
        poids_total += _dec(unite.poids_kg)
        for ligne in unite.lignes.select_related('produit').all():
            marchandises.append({
                'designation': getattr(ligne.produit, 'nom', '') or '',
                'quantite': ligne.quantite,
                'sscc': unite.sscc,
            })

    transporteur = (expedition.get_transporteur_provider_display()
                    if expedition.transporteur_provider else '')
    if expedition.transporteur_id:
        transporteur = (getattr(expedition.transporteur, 'nom', '')
                        or transporteur)

    context.update({
        'expedition': expedition,
        'numero_suivi': expedition.numero_suivi or '',
        'destination': expedition.destination or '',
        'transporteur': transporteur,
        'date_expedition': (expedition.date_expedition
                            or timezone.now()),
        'unites': unites,
        'nb_colis': len(unites),
        'poids_total_kg': poids_total,
        'marchandises': marchandises,
        'sscc_liste': [u.sscc for u in unites],
    })
    return context


def render_cmr_html(expedition):
    """HTML de la lettre de voiture (testable SANS WeasyPrint)."""
    ctx = build_cmr_context(expedition)

    lignes_html = ''.join(
        f'<tr><td>{_esc(m["designation"])}</td>'
        f'<td class="num">{_esc(m["quantite"])}</td>'
        f'<td class="mono">{_esc(m["sscc"])}</td></tr>'
        for m in ctx['marchandises']
    ) or ('<tr><td colspan="3" class="vide">Aucune ligne de contenu '
          'déclarée.</td></tr>')

    sscc_html = ''.join(
        f'<li class="mono">{_esc(s)}</li>' for s in ctx['sscc_liste'])

    date_str = ctx['date_expedition'].strftime('%d/%m/%Y')
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<title>Lettre de voiture</title>
<style>
  @page {{ size: A4; margin: 14mm; }}
  body {{ font-family: Helvetica, Arial, sans-serif; font-size: 10pt;
          color: #111; }}
  h1 {{ font-size: 15pt; margin: 0 0 2mm; }}
  .sous-titre {{ font-size: 9pt; color: #555; margin: 0 0 6mm; }}
  .cases {{ display: flex; gap: 6mm; margin-bottom: 6mm; }}
  .case {{ flex: 1; border: 0.4mm solid #333; padding: 3mm; }}
  .case h2 {{ font-size: 8pt; text-transform: uppercase; letter-spacing: .4pt;
              margin: 0 0 2mm; color: #444; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 5mm; }}
  th, td {{ border: 0.3mm solid #666; padding: 1.6mm 2mm; text-align: left; }}
  th {{ background: #eee; font-size: 8.5pt; text-transform: uppercase; }}
  .num {{ text-align: right; }}
  .mono {{ font-family: "Courier New", monospace; font-size: 9pt; }}
  .vide {{ color: #777; font-style: italic; }}
  .totaux td {{ font-weight: bold; }}
  ul {{ margin: 0; padding-left: 5mm; }}
  .signatures {{ display: flex; gap: 6mm; margin-top: 8mm; }}
  .signature {{ flex: 1; border-top: 0.3mm solid #333; padding-top: 2mm;
                font-size: 8.5pt; color: #444; }}
</style></head>
<body>
  <h1>Lettre de voiture (CMR simplifiée)</h1>
  <p class="sous-titre">Transport routier de marchandises &mdash;
     document non contractuel, établi le {date_str}.</p>

  <div class="cases">
    <div class="case">
      <h2>Expéditeur</h2>
      <div>{_esc(ctx.get('entreprise_nom'))}</div>
      <div>{_esc(ctx.get('entreprise_adresse'))}</div>
      <div>{_esc(ctx.get('entreprise_telephone'))}</div>
    </div>
    <div class="case">
      <h2>Destinataire</h2>
      <div>{_esc(ctx['destination']) or '&mdash;'}</div>
    </div>
    <div class="case">
      <h2>Transporteur</h2>
      <div>{_esc(ctx['transporteur']) or '&mdash;'}</div>
      <div class="mono">{_esc(ctx['numero_suivi'])}</div>
    </div>
  </div>

  <table>
    <thead><tr>
      <th>Nature de la marchandise</th><th class="num">Quantité</th>
      <th>SSCC</th>
    </tr></thead>
    <tbody>{lignes_html}</tbody>
    <tfoot><tr class="totaux">
      <td>Nombre de colis : {ctx['nb_colis']}</td>
      <td class="num">Poids total</td>
      <td>{_fmt_dec(ctx['poids_total_kg'])} kg</td>
    </tr></tfoot>
  </table>

  <div class="case">
    <h2>Références SSCC transportées</h2>
    <ul>{sscc_html or '<li class="vide">Aucune</li>'}</ul>
  </div>

  <div class="signatures">
    <div class="signature">Signature de l'expéditeur</div>
    <div class="signature">Signature du transporteur</div>
    <div class="signature">Signature du destinataire</div>
  </div>
</body></html>"""


def generate_cmr_pdf(expedition):
    """Rend la lettre de voiture et renvoie les octets (jamais stockée)."""
    from apps.ventes.utils.pdf import _html_to_pdf
    return _html_to_pdf(render_cmr_html(expedition))
