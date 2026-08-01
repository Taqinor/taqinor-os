"""NTMIG19 — PV de migration (synthèse exportable) en PDF.

Pièce remise au grand compte migré : par lot, comptages source vs cible,
totaux financiers, écarts, dérogations (qui/quand/pourquoi), statut de
conformité, avec une page de couverture au nom du client migré.

Rendu par le service WeasyPrint PARTAGÉ ``core.pdf.render_pdf`` — surtout PAS
le moteur de devis premium (la règle #4 ne concerne que les PDF de devis
clients, et ce PV n'en est pas un). Ne lit que les modèles de cette app :
aucune donnée d'achat, de marge ou de prix de revient n'entre ici.
"""
from html import escape

from django.utils import timezone

from core.pdf import render_pdf

MOIS_FR = [
    '', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet',
    'août', 'septembre', 'octobre', 'novembre', 'décembre',
]

_STYLE = """
  body { font-family: sans-serif; font-size: 12px; color: #222; margin: 40px; }
  h1 { font-size: 20px; text-align: center; margin-top: 8px; }
  h2 { font-size: 14px; margin-top: 24px; border-bottom: 1px solid #bbb;
       padding-bottom: 4px; }
  .couverture { text-align: center; border-bottom: 2px solid #444;
                padding-bottom: 16px; margin-bottom: 20px; }
  .client { font-size: 16px; font-weight: bold; margin-top: 6px; }
  .meta { font-size: 11px; color: #555; margin-top: 4px; }
  table { width: 100%; border-collapse: collapse; margin-top: 10px; }
  th, td { border: 1px solid #ccc; padding: 5px 8px; text-align: left;
           vertical-align: top; }
  th { background: #f2f2f2; }
  .conforme { color: #157347; font-weight: bold; }
  .derog { color: #664d03; font-weight: bold; }
  .ecart { color: #b02a37; font-weight: bold; }
  .ecarts-list { font-size: 11px; margin: 4px 0 0 0; padding-left: 16px; }
  .derog-note { font-size: 11px; color: #664d03; margin-top: 4px; }
  .pied { margin-top: 26px; font-size: 11px; color: #555; }
"""


def _montant(valeur):
    return '—' if valeur is None else f'{valeur} MAD'


def _ligne_lot_html(lot):
    """Une ligne de synthèse pour un lot : comptages, écarts, dérogation."""
    rapport = lot.rapports.order_by('-created_at').first()
    conforme = rapport is not None and rapport.conforme
    if conforme:
        badge = '<span class="conforme">Conforme</span>'
    elif lot.derogation_reconcile:
        badge = '<span class="derog">Dérogé</span>'
    elif rapport is None:
        badge = '<span class="ecart">Non réconcilié</span>'
    else:
        badge = '<span class="ecart">Écarts détectés</span>'

    total_cible = lot.crees + lot.maj
    ecarts_html = ''
    if rapport is not None and rapport.ecarts:
        items = ''.join(
            f'<li>{escape(str(e.get("detail", e)))}</li>'
            for e in rapport.ecarts)
        ecarts_html = f'<ul class="ecarts-list">{items}</ul>'

    derog_html = ''
    if lot.derogation_reconcile:
        qui = getattr(lot.derogation_par, 'username', '') or '—'
        quand = (timezone.localtime(lot.derogation_at).strftime('%d/%m/%Y')
                 if lot.derogation_at else '—')
        derog_html = (
            f'<div class="derog-note">Dérogation accordée par '
            f'{escape(str(qui))} le {quand} — '
            f'{escape(lot.derogation_motif or "")}</div>')

    financier = '—'
    if rapport is not None and (rapport.total_financier_source is not None
                                or rapport.total_financier_cible is not None):
        financier = (
            f'source {_montant(rapport.total_financier_source)}<br>'
            f'cible {_montant(rapport.total_financier_cible)}<br>'
            f'écart {_montant(rapport.ecart_financier)}')

    return (
        f'<tr><td>{escape(lot.entite)}</td>'
        f'<td>{lot.source_lignes}</td>'
        f'<td>{total_cible}<br>({lot.crees} créés / {lot.maj} maj)</td>'
        f'<td>{lot.erreurs}</td>'
        f'<td>{financier}</td>'
        f'<td>{badge}{ecarts_html}{derog_html}</td></tr>')


def render_rapport_migration_html(projet, *, today=None):
    """HTML du PV de migration d'un ``ProjetMigration``."""
    if today is None:
        today = timezone.localdate()
    date_txt = f'{today.day} {MOIS_FR[today.month]} {today.year}'
    # Branding white-label : le nom vient de la société du tenant, jamais
    # d'une marque en dur (une seule instance sert plusieurs sociétés).
    company_nom = escape(getattr(projet.company, 'nom', '') or '')
    editeur = f' par {company_nom}' if company_nom else ''
    # Lots RE-FILTRÉS sur la société du projet : un PV remis à un client ne
    # doit pas pouvoir lister la ligne d'une autre société.
    from .services import lots_du_projet
    lots = list(lots_du_projet(projet))
    lignes = ''.join(_ligne_lot_html(lot) for lot in lots)
    nb_derog = sum(1 for lot in lots if lot.derogation_reconcile)
    pied = (
        f'{len(lots)} lot(s) — {nb_derog} dérogation(s) enregistrée(s). '
        'Un lot marqué « Dérogé » a été clôturé malgré des écarts, sur '
        'décision motivée et tracée.')
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<style>{_STYLE}</style></head><body>
  <div class="couverture">
    <h1>Procès-verbal de migration</h1>
    <div class="client">{escape(projet.nom)}</div>
    <div class="meta">Source : {escape(projet.get_source_display())}
      &nbsp;|&nbsp; Statut : {escape(projet.get_statut_display())}
      &nbsp;|&nbsp; Édité{editeur} le {date_txt}</div>
  </div>
  <h2>Synthèse par lot</h2>
  <table>
    <thead><tr><th>Entité</th><th>Lignes source</th><th>Cible</th>
      <th>Erreurs</th><th>Totaux financiers</th>
      <th>Conformité</th></tr></thead>
    <tbody>{lignes or '<tr><td colspan="6">Aucun lot.</td></tr>'}</tbody>
  </table>
  <div class="pied">{pied}</div>
</body></html>"""


def render_rapport_migration_pdf(projet, *, today=None):
    """PV de migration → octets PDF."""
    return render_pdf(html=render_rapport_migration_html(projet, today=today))
