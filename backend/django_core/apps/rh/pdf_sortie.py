"""ZRH12 — certificat de travail légal (art. 72 du Code du travail) — PDF.

Le certificat de travail est OBLIGATOIRE à la sortie de tout salarié : il
liste les dates d'entrée/sortie et le ou les emplois occupés, avec mention
FACULTATIVE de la qualité du travail (jamais imposée). DISTINCT de :

* l'attestation de travail (« fait partie de notre personnel »), déjà rendue
  par ``apps.paie.builders.render_attestation_html(type='travail')``
  (PAIE34) — ce renderer-ci ne la duplique PAS ;
* le reçu pour solde de tout compte (STC), déjà couvert par
  ``apps.paie.builders.render_stc_html`` (XPAI1) — ce renderer-ci ne le
  duplique PAS non plus.

Renderer WeasyPrint DÉDIÉ, JAMAIS ``/proposal`` (rule #4, CLAUDE.md — réservé
au moteur devis ventes). Suit le même pattern self-contained que
``apps.rh.pdf_attestation`` (XRH34) / ``apps.paie.builders`` (PAIE34) : rendu
HTML -> PDF via WeasyPrint, aucune dépendance à une autre app business,
lecture seule de champs publics.

WeasyPrint est optionnel à l'import : si la lib n'est pas installée (build
allégé), ``render_certificat_travail_pdf`` lève une ``RuntimeError``
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


def _postes_occupes(employe):
    """XRH6 — postes occupés successifs, du plus ancien au plus récent,
    reconstitués depuis le chatter ``DossierActivity`` (champ ``poste_ref``,
    transitions loguées automatiquement). Sans historique disponible,
    retombe sur le poste courant uniquement (poste_ref ou poste libre)."""
    postes = []
    activites = (
        employe.activites
        .filter(type='log', field='poste_ref')
        .order_by('date_creation'))
    for act in activites:
        if act.old_value and act.old_value not in postes and act.old_value != '—':
            postes.append(act.old_value)
        if act.new_value and act.new_value not in postes and act.new_value != '—':
            postes.append(act.new_value)

    poste_actuel = (
        employe.poste_ref.intitule if employe.poste_ref_id
        else employe.poste)
    if poste_actuel and poste_actuel not in postes:
        postes.append(poste_actuel)
    return postes or ['—']


def render_certificat_travail_html(employe, *, today=None):
    """Construit le HTML du certificat de travail (ZRH12, art. 72).

    Lève ``ValueError`` si l'employé n'a pas de ``date_sortie`` — le
    certificat de travail n'a de sens QUE pour un employé sorti (l'appelant
    est censé filtrer avant ; ce garde est défensif)."""
    if not employe.date_sortie:
        raise ValueError(
            'Aucun certificat de travail pour un employé non sorti.')
    if today is None:
        today = date.today()

    nom = escape(f'{employe.nom} {employe.prenom}')
    cin = escape(employe.cin or '—')
    date_entree = employe.date_embauche
    date_entree_txt = (
        f'{date_entree.day} {MOIS_FR[date_entree.month]} {date_entree.year}'
        if date_entree else '—')
    date_sortie_txt = (
        f'{employe.date_sortie.day} {MOIS_FR[employe.date_sortie.month]} '
        f'{employe.date_sortie.year}')
    date_txt = f'{today.day} {MOIS_FR[today.month]} {today.year}'
    postes = _postes_occupes(employe)
    postes_txt = escape(', '.join(postes))

    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<style>
  body {{ font-family: sans-serif; font-size: 12px; color: #222; margin: 40px; }}
  h1 {{ font-size: 18px; text-align: center; }}
  .date {{ text-align: right; margin-top: 40px; }}
</style></head><body>
  <h1>Certificat de travail</h1>
  <p>Nous soussignés, certifions que <strong>{nom}</strong>
  (CIN : <strong>{cin}</strong>) a été employé(e) au sein de notre société
  du <strong>{escape(date_entree_txt)}</strong> au
  <strong>{escape(date_sortie_txt)}</strong>, en qualité de
  <strong>{postes_txt}</strong>.</p>
  <p>Le/la salarié(e) est libre de tout engagement à l'égard de notre
  société à compter de cette date.</p>
  <p>Le présent certificat de travail est délivré conformément à l'article
  72 du Code du travail, pour servir et valoir ce que de droit.</p>
  <p class="date">Fait le {escape(date_txt)}.</p>
</body></html>"""


def render_certificat_travail_pdf(employe, *, today=None):
    """Certificat de travail → octets PDF (ZRH12)."""
    return _html_to_pdf(
        render_certificat_travail_html(employe, today=today))
