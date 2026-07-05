"""XRH34 — attestation PDF de réussite à un quiz de formation (eLearning
léger), renderer RH DÉDIÉ.

JAMAIS ``/proposal`` (rule #4, CLAUDE.md — réservé au moteur devis ventes).
Suit le même pattern self-contained que ``apps.paie.builders`` (PAIE34) :
rendu HTML → PDF via WeasyPrint, aucune dépendance à une autre app business,
lecture seule de champs publics (jamais de donnée d'achat/marge/salaire).

WeasyPrint est optionnel à l'import : si la lib n'est pas installée (build
allégé), ``render_attestation_reussite_pdf`` lève une ``RuntimeError``
explicite plutôt que de planter à l'import du module.
"""
from datetime import date
from html import escape
from io import BytesIO

MOIS_FR = [
    '', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet',
    'août', 'septembre', 'octobre', 'novembre', 'décembre',
]


def _html_to_pdf(html_string):
    """HTML → octets PDF (WeasyPrint). Import paresseux de weasyprint."""
    try:
        import weasyprint
    except ImportError as exc:  # pragma: no cover - dépend de l'environnement
        raise RuntimeError(
            "WeasyPrint n'est pas installé : génération PDF indisponible."
        ) from exc
    buf = BytesIO()
    weasyprint.HTML(string=html_string).write_pdf(buf)
    buf.seek(0)
    return buf.read()


def render_attestation_reussite_html(tentative, *, today=None):
    """Construit le HTML de l'attestation de réussite (XRH34).

    Lève ``ValueError`` si la tentative n'est pas réussie (une attestation
    n'a de sens QUE pour une réussite — l'appelant est censé filtrer avant,
    ce garde est défensif)."""
    if not tentative.reussi:
        raise ValueError(
            'Aucune attestation pour une tentative non réussie.')
    if today is None:
        today = date.today()

    quiz = tentative.quiz
    employe = tentative.employe
    date_txt = f'{today.day} {MOIS_FR[today.month]} {today.year}'
    date_tentative = tentative.date_creation.date() if hasattr(
        tentative.date_creation, 'date') else tentative.date_creation
    date_tentative_txt = (
        f'{date_tentative.day} {MOIS_FR[date_tentative.month]} '
        f'{date_tentative.year}')

    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<style>
  body {{ font-family: sans-serif; font-size: 12px; color: #222; margin: 40px; }}
  h1 {{ font-size: 20px; text-align: center; }}
  .cadre {{ border: 2px solid #444; padding: 24px; margin-top: 20px; }}
  .score {{ font-weight: bold; font-size: 16px; }}
  .date {{ text-align: right; margin-top: 40px; }}
</style></head><body>
  <h1>Attestation de réussite</h1>
  <div class="cadre">
    <p>Nous attestons que <strong>{escape(employe.nom)} {escape(employe.prenom)}</strong>
    (matricule {escape(employe.matricule)}) a passé le quiz de formation
    « {escape(quiz.intitule)} » le {escape(date_tentative_txt)}.</p>
    <p class="score">Score obtenu : {tentative.score}% (seuil de réussite :
    {quiz.score_reussite}%) — RÉUSSI.</p>
  </div>
  <p class="date">Fait le {escape(date_txt)}.</p>
</body></html>"""


def render_attestation_reussite_pdf(tentative, *, today=None):
    """Attestation de réussite → octets PDF (XRH34)."""
    return _html_to_pdf(
        render_attestation_reussite_html(tentative, today=today))
