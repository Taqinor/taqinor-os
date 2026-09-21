"""FG194 — Ordre de mission PDF (déplacement chantier).

Rendu à la volée via le MÊME moteur que les autres PDF (WeasyPrint), en
réutilisant le contexte de marque société (``apps.ventes.utils.pdf``). Le
gabarit est un template Django INLINE (pas de fichier de template dans une
autre app) : tout reste dans ``apps.rh``. Non stocké : généré et streamé à la
demande. Document INTERNE RH (accès Administrateur/Responsable).
"""
from django.template import Context, Template

_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<style>
  @page { size: A4; margin: 18mm 16mm; }
  body { font-family: Arial, sans-serif; color: #1a1a1a; font-size: 12px; }
  .entete { border-bottom: 3px solid {{ couleur_principale }}; padding-bottom: 8px;
            margin-bottom: 16px; }
  .entreprise { font-size: 18px; font-weight: bold; color: {{ couleur_principale }}; }
  .coord { font-size: 10px; color: #555; }
  h1 { font-size: 20px; text-align: center; margin: 18px 0 4px; }
  .reference { text-align: center; color: #555; margin-bottom: 18px; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 14px; }
  td { padding: 6px 8px; border: 1px solid #ddd; vertical-align: top; }
  td.lib { width: 38%; background: #f5f5f5; font-weight: bold; }
  .motif { white-space: pre-wrap; }
  .signatures { margin-top: 40px; display: flex; justify-content: space-between; }
  .sign { width: 45%; border-top: 1px solid #888; padding-top: 4px; text-align: center;
          font-size: 11px; color: #555; }
</style>
</head>
<body>
  <div class="entete">
    <div class="entreprise">{{ entreprise_nom }}</div>
    <div class="coord">{{ entreprise_adresse }} — {{ entreprise_telephone }}
      {% if entreprise_ice %} — ICE {{ entreprise_ice }}{% endif %}</div>
  </div>

  <h1>Ordre de mission</h1>
  <div class="reference">Référence : {{ reference }}</div>

  <table>
    <tr><td class="lib">Collaborateur</td><td>{{ employe_nom }}
      {% if matricule %}(mat. {{ matricule }}){% endif %}</td></tr>
    <tr><td class="lib">Destination</td><td>{{ destination }}</td></tr>
    <tr><td class="lib">Date de départ</td><td>{{ date_depart|default:"—" }}</td></tr>
    <tr><td class="lib">Date de retour</td><td>{{ date_retour|default:"—" }}</td></tr>
    <tr><td class="lib">Moyen de transport</td>
      <td>{{ moyen_transport|default:"—" }}</td></tr>
    <tr><td class="lib">Per-diem (par jour)</td><td>{{ per_diem }} MAD</td></tr>
    <tr><td class="lib">Motif</td><td class="motif">{{ motif|default:"—" }}</td></tr>
  </table>

  <div class="signatures">
    <div class="sign">Le collaborateur</div>
    <div class="sign">La direction</div>
  </div>
</body>
</html>
"""


def _payload(ordre):
    emp = ordre.employe
    return {
        'reference': ordre.reference,
        'employe_nom': f'{emp.nom} {emp.prenom}' if emp else '',
        'matricule': emp.matricule if emp else '',
        'destination': ordre.destination,
        'motif': ordre.motif,
        'date_depart': ordre.date_depart.isoformat()
        if ordre.date_depart else '',
        'date_retour': ordre.date_retour.isoformat()
        if ordre.date_retour else '',
        'moyen_transport': ordre.moyen_transport,
        'per_diem': ordre.per_diem,
    }


def render_ordre_mission_pdf(ordre):
    """Construit le PDF d'un ``OrdreMission`` (bytes). Scopé par l'appelant."""
    from apps.ventes.utils.pdf import _company_context, _html_to_pdf

    ctx = _company_context(company=ordre.company)
    ctx.update(_payload(ordre))
    html = Template(_TEMPLATE).render(Context(ctx))
    return _html_to_pdf(html)
