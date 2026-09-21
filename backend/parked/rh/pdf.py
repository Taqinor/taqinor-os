"""XRH20 — Promesse d'embauche / lettre d'offre PDF.

Rendu à la volée via le MÊME moteur que les autres PDF (WeasyPrint), en
réutilisant le contexte de marque société (``apps.ventes.utils.pdf``) — même
pattern que ``apps.rh.mission_pdf`` (FG194). Le gabarit est un template
Django INLINE : tout reste dans ``apps.rh``. Non stocké : généré et streamé
à la demande.
"""
from django.template import Context, Template

_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<style>
  @page { size: A4; margin: 20mm 18mm; }
  body { font-family: Arial, sans-serif; color: #1a1a1a; font-size: 12px; }
  .entete { border-bottom: 3px solid {{ couleur_principale }}; padding-bottom: 8px;
            margin-bottom: 20px; }
  .entreprise { font-size: 18px; font-weight: bold; color: {{ couleur_principale }}; }
  .coord { font-size: 10px; color: #555; }
  h1 { font-size: 20px; text-align: center; margin: 18px 0 24px; }
  p { line-height: 1.6; }
  table { width: 100%; border-collapse: collapse; margin: 16px 0; }
  td { padding: 6px 8px; border: 1px solid #ddd; vertical-align: top; }
  td.lib { width: 40%; background: #f5f5f5; font-weight: bold; }
  .signature-block { margin-top: 40px; }
  .signature-block .signe {
    border: 1px solid #ccc; padding: 10px; background: #fafafa;
    font-size: 11px; color: #333;
  }
</style>
</head>
<body>
  <div class="entete">
    <div class="entreprise">{{ entreprise_nom }}</div>
    <div class="coord">{{ entreprise_adresse }} — {{ entreprise_telephone }}
      {% if entreprise_ice %} — ICE {{ entreprise_ice }}{% endif %}</div>
  </div>

  <h1>Promesse d'embauche</h1>

  <p>Nous avons le plaisir de vous proposer un poste au sein de notre
  société aux conditions suivantes :</p>

  <table>
    <tr><td class="lib">Candidat</td><td>{{ candidat_nom }}</td></tr>
    <tr><td class="lib">Poste proposé</td><td>{{ poste_propose|default:"—" }}</td></tr>
    <tr><td class="lib">Type de contrat</td><td>{{ type_contrat_display }}</td></tr>
    <tr><td class="lib">Date de début proposée</td>
      <td>{{ date_debut_proposee|default:"—" }}</td></tr>
    {% if salaire_propose %}
    <tr><td class="lib">Salaire proposé</td><td>{{ salaire_propose }} MAD</td></tr>
    {% endif %}
  </table>

  <p>Cette promesse est valable jusqu'au {{ expires_at }}. Merci de nous
  faire part de votre acceptation via le lien qui vous a été communiqué.</p>

  {% if signataire_nom %}
  <div class="signature-block">
    <div class="signe">
      Signé électroniquement par <strong>{{ signataire_nom }}</strong>
      le {{ date_signature }} (loi 53-05 — nom dactylographié consenti).
    </div>
  </div>
  {% endif %}
</body>
</html>
"""


def _payload(promesse):
    candidature = promesse.candidature
    return {
        'candidat_nom': candidature.nom,
        'poste_propose': promesse.poste_propose,
        'type_contrat_display': promesse.get_type_contrat_display(),
        'date_debut_proposee': (
            promesse.date_debut_proposee.isoformat()
            if promesse.date_debut_proposee else ''),
        'salaire_propose': (
            promesse.salaire_propose if promesse.salaire_propose else ''),
        'expires_at': promesse.expires_at.strftime('%d/%m/%Y'),
        'signataire_nom': promesse.signataire_nom,
        'date_signature': (
            promesse.date_signature.strftime('%d/%m/%Y %H:%M')
            if promesse.date_signature else ''),
    }


def render_promesse_embauche_pdf(promesse):
    """Construit le PDF d'une ``PromesseEmbauche`` (bytes). Scopé par
    l'appelant."""
    from apps.ventes.utils.pdf import _company_context, _html_to_pdf

    ctx = _company_context(company=promesse.company)
    ctx.update(_payload(promesse))
    html = Template(_TEMPLATE).render(Context(ctx))
    return _html_to_pdf(html)
