"""Générateurs de PDF de la Paie (PAIE34) — bulletin + attestations.

Documents internes/employé conformes au cadre marocain :

* le BULLETIN DE PAIE (récapitulatif des gains, cotisations et net à payer
  figés au snapshot du ``BulletinPaie``) ;
* les ATTESTATIONS de salaire, de travail et de domiciliation irrévocable.

Rendu HTML → PDF via WeasyPrint, comme le reste de l'ERP. Tout est
self-contained dans ``apps.paie`` : aucune dépendance à une autre app business
(les templates sont des chaînes HTML construites ici). Le moteur ne lit que des
champs PUBLICS du bulletin/profil — jamais de donnée d'achat/marge. Donnée
SENSIBLE (salaires) — usage paie/employé uniquement.

WeasyPrint est optionnel à l'import : si la lib n'est pas installée (build
allégé), ``render_bulletin_pdf`` lève une ``RuntimeError`` explicite plutôt que
de planter à l'import du module.
"""
from datetime import date
from decimal import Decimal
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


def _fmt(montant):
    """Formate un Decimal en montant lisible « 1 234,56 » (espace milliers)."""
    montant = Decimal(montant or 0).quantize(Decimal('0.01'))
    entier, _, dec = f'{montant:.2f}'.partition('.')
    signe = ''
    if entier.startswith('-'):
        signe = '-'
        entier = entier[1:]
    groupes = []
    while len(entier) > 3:
        groupes.insert(0, entier[-3:])
        entier = entier[:-3]
    groupes.insert(0, entier)
    return f'{signe}{" ".join(groupes)},{dec}'


def _nom_employe(profil):
    employe = getattr(profil, 'employe', None)
    if employe is None:
        return f'Profil #{getattr(profil, "id", "")}'
    return f'{employe.nom} {employe.prenom}'.strip()


def _libelle_periode(periode):
    mois = MOIS_FR[periode.mois] if 1 <= periode.mois <= 12 else str(periode.mois)
    return f'{mois} {periode.annee}'


# ── PAIE34 — Bulletin de paie PDF ──────────────────────────────────────────

_LIGNE_TPL = (
    '<tr><td>{code}</td><td>{libelle}</td>'
    '<td style="text-align:right">{montant}</td></tr>'
)


def bulletin_context(bulletin):
    """Contexte de rendu d'un bulletin (dict de chaînes prêtes à afficher).

    Lecture seule : ne lit que des champs publics du bulletin et de son profil.
    """
    profil = bulletin.profil
    periode = bulletin.periode
    lignes = [
        {
            'code': escape(ligne.code or ''),
            'libelle': escape(ligne.libelle or ''),
            'montant': _fmt(ligne.montant),
        }
        for ligne in bulletin.lignes.all()
    ]
    return {
        'employe': escape(_nom_employe(profil)),
        'matricule': escape(
            getattr(getattr(profil, 'employe', None), 'matricule', '') or ''),
        'numero_cnss': escape(profil.numero_cnss or ''),
        'periode': escape(_libelle_periode(periode)),
        'lignes': lignes,
        'brut': _fmt(bulletin.brut),
        'cnss': _fmt(bulletin.cnss_salariale),
        'amo': _fmt(bulletin.amo_salariale),
        'cimr': _fmt(bulletin.cimr_salariale),
        'ir': _fmt(bulletin.ir),
        'net_a_payer': _fmt(bulletin.net_a_payer),
    }


def render_bulletin_html(bulletin):
    """Construit le HTML du bulletin de paie (PAIE34)."""
    ctx = bulletin_context(bulletin)
    lignes_html = ''.join(
        _LIGNE_TPL.format(**ligne) for ligne in ctx['lignes'])
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<style>
  body {{ font-family: sans-serif; font-size: 11px; color: #222; }}
  h1 {{ font-size: 18px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  th, td {{ border: 1px solid #ccc; padding: 4px 6px; }}
  .total {{ font-weight: bold; font-size: 13px; }}
</style></head><body>
  <h1>Bulletin de paie</h1>
  <p><strong>Salarié :</strong> {ctx['employe']}
     &nbsp; <strong>Matricule :</strong> {ctx['matricule']}
     &nbsp; <strong>N° CNSS :</strong> {ctx['numero_cnss']}</p>
  <p><strong>Période :</strong> {ctx['periode']}</p>
  <table>
    <thead><tr><th>Code</th><th>Libellé</th><th>Montant (MAD)</th></tr></thead>
    <tbody>{lignes_html}</tbody>
  </table>
  <p class="total">Net à payer : {ctx['net_a_payer']} MAD</p>
</body></html>"""


def render_bulletin_pdf(bulletin):
    """Bulletin de paie → octets PDF (PAIE34)."""
    return _html_to_pdf(render_bulletin_html(bulletin))


# ── PAIE34 — Attestations (salaire / travail / domiciliation) ──────────────

TYPE_SALAIRE = 'salaire'
TYPE_TRAVAIL = 'travail'
TYPE_DOMICILIATION = 'domiciliation'
ATTESTATION_TYPES = [TYPE_SALAIRE, TYPE_TRAVAIL, TYPE_DOMICILIATION]


def _corps_attestation(attestation_type, profil, bulletin, today):
    """Corps (HTML) de l'attestation selon son type."""
    nom = escape(_nom_employe(profil))
    if attestation_type == TYPE_SALAIRE:
        net = _fmt(bulletin.net_a_payer) if bulletin else '—'
        brut = _fmt(bulletin.brut) if bulletin else '—'
        return (
            f"<p>Nous soussignés, attestons que <strong>{nom}</strong> est "
            f"employé(e) au sein de notre société et perçoit un salaire brut "
            f"mensuel de <strong>{brut} MAD</strong>, soit un net à payer de "
            f"<strong>{net} MAD</strong>.</p>"
            "<p>La présente attestation est délivrée à l'intéressé(e) pour "
            "servir et valoir ce que de droit.</p>")
    if attestation_type == TYPE_TRAVAIL:
        return (
            f"<p>Nous soussignés, attestons que <strong>{nom}</strong> fait "
            "partie de notre personnel.</p>"
            "<p>La présente attestation de travail est délivrée à "
            "l'intéressé(e) pour servir et valoir ce que de droit.</p>")
    # Domiciliation irrévocable de salaire.
    rib = escape(profil.rib or '')
    banque = escape(profil.banque or '')
    return (
        f"<p>Nous soussignés, attestons que le salaire de "
        f"<strong>{nom}</strong> est domicilié de manière IRRÉVOCABLE sur le "
        f"compte bancaire suivant :</p>"
        f"<p><strong>Banque :</strong> {banque} &nbsp; "
        f"<strong>RIB :</strong> {rib}</p>"
        "<p>Cette domiciliation ne peut être modifiée sans l'accord de "
        "l'organisme bénéficiaire.</p>")


def render_attestation_html(attestation_type, profil, *, bulletin=None,
                            today=None):
    """Construit le HTML d'une attestation (PAIE34).

    ``attestation_type`` ∈ {salaire, travail, domiciliation}. ``bulletin`` (le
    dernier bulletin validé) alimente l'attestation de salaire. Lève
    ``ValueError`` pour un type inconnu.
    """
    if attestation_type not in ATTESTATION_TYPES:
        raise ValueError(f'Type d\'attestation inconnu : {attestation_type!r}.')
    if today is None:
        today = date.today()
    titres = {
        TYPE_SALAIRE: 'Attestation de salaire',
        TYPE_TRAVAIL: 'Attestation de travail',
        TYPE_DOMICILIATION: 'Attestation de domiciliation irrévocable',
    }
    titre = titres[attestation_type]
    corps = _corps_attestation(attestation_type, profil, bulletin, today)
    date_txt = f'{today.day} {MOIS_FR[today.month]} {today.year}'
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<style>
  body {{ font-family: sans-serif; font-size: 12px; color: #222; margin: 40px; }}
  h1 {{ font-size: 18px; text-align: center; }}
  .date {{ text-align: right; margin-top: 40px; }}
</style></head><body>
  <h1>{escape(titre)}</h1>
  {corps}
  <p class="date">Fait le {escape(date_txt)}.</p>
</body></html>"""


def render_attestation_pdf(attestation_type, profil, *, bulletin=None,
                           today=None):
    """Attestation → octets PDF (PAIE34)."""
    return _html_to_pdf(
        render_attestation_html(
            attestation_type, profil, bulletin=bulletin, today=today))
