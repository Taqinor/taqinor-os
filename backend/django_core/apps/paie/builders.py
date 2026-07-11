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

ARC12 — la plomberie WeasyPrint (``HTML(string=...).write_pdf()`` + import
paresseux) est déléguée au service partagé ``core.pdf.render_pdf`` ; les
GABARITS HTML ci-dessous restent STRICTEMENT identiques, donc le rendu est
inchangé à l'octet près. ``render_bulletins_periode_pdf`` (ZPAI5, fusion
PyMuPDF) est HORS PÉRIMÈTRE : elle n'importe pas WeasyPrint directement, elle
réutilise ``render_bulletin_pdf`` (déjà migré) puis fusionne les pages via
``fitz``.
"""
from datetime import date
from decimal import Decimal
from html import escape

from core.pdf import render_pdf


def _html_to_pdf(html_string):
    """HTML → octets PDF via ``core.pdf.render_pdf`` (ARC12)."""
    return render_pdf(html=html_string)


MOIS_FR = [
    '', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet',
    'août', 'septembre', 'octobre', 'novembre', 'décembre',
]


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
# XPAI14 — Attestation de salaire pour le dossier IJ (indemnités
# journalières CNSS maladie/maternité) : nouveau type dans
# ``render_attestation_pdf``, distinct de l'attestation de salaire
# générique (celle-ci porte les jours d'arrêt + le brut de référence).
TYPE_ATTESTATION_IJ_CNSS = 'attestation_ij_cnss'
ATTESTATION_TYPES = [
    TYPE_SALAIRE, TYPE_TRAVAIL, TYPE_DOMICILIATION, TYPE_ATTESTATION_IJ_CNSS,
]


def _corps_attestation(attestation_type, profil, bulletin, today, *,
                       arret_cnss=None):
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
    if attestation_type == TYPE_ATTESTATION_IJ_CNSS:
        # XPAI14 — Attestation de salaire pour le dossier d'indemnités
        # journalières CNSS (arrêt maladie/maternité).
        arret_cnss = arret_cnss or {}
        numero_cnss = escape(profil.numero_cnss or '')
        brut_ref = _fmt(arret_cnss.get('brut_reference', 0))
        jours_arret = arret_cnss.get('jours_arret', 0)
        type_arret = escape(arret_cnss.get('type_arret_libelle', 'maladie'))
        return (
            f"<p>Nous soussignés, attestons que <strong>{nom}</strong> "
            f"(n° CNSS : <strong>{numero_cnss}</strong>) est employé(e) au "
            f"sein de notre société avec un salaire brut mensuel de "
            f"référence de <strong>{brut_ref} MAD</strong>.</p>"
            f"<p>L'intéressé(e) a été en arrêt de travail "
            f"(<strong>{type_arret}</strong>) pour "
            f"<strong>{jours_arret} jour(s)</strong> sur la période "
            "concernée.</p>"
            "<p>La présente attestation de salaire est délivrée pour "
            "constituer le dossier d'indemnités journalières auprès de la "
            "CNSS.</p>")
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
                            today=None, arret_cnss=None):
    """Construit le HTML d'une attestation (PAIE34).

    ``attestation_type`` ∈ {salaire, travail, domiciliation,
    attestation_ij_cnss}. ``bulletin`` (le dernier bulletin validé) alimente
    l'attestation de salaire. ``arret_cnss`` (dict {'brut_reference',
    'jours_arret', 'type_arret_libelle'}) alimente l'attestation IJ CNSS
    (XPAI14). Lève ``ValueError`` pour un type inconnu.
    """
    if attestation_type not in ATTESTATION_TYPES:
        raise ValueError(f'Type d\'attestation inconnu : {attestation_type!r}.')
    if today is None:
        today = date.today()
    titres = {
        TYPE_SALAIRE: 'Attestation de salaire',
        TYPE_TRAVAIL: 'Attestation de travail',
        TYPE_DOMICILIATION: 'Attestation de domiciliation irrévocable',
        TYPE_ATTESTATION_IJ_CNSS:
            'Attestation de salaire — dossier IJ CNSS',
    }
    titre = titres[attestation_type]
    corps = _corps_attestation(
        attestation_type, profil, bulletin, today, arret_cnss=arret_cnss)
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
                           today=None, arret_cnss=None):
    """Attestation → octets PDF (PAIE34)."""
    return _html_to_pdf(
        render_attestation_html(
            attestation_type, profil, bulletin=bulletin, today=today,
            arret_cnss=arret_cnss))


# ── XPAI1 — Reçu pour solde de tout compte (STC) ────────────────────────────

def render_stc_html(bulletin, *, today=None):
    """Construit le HTML du reçu pour solde de tout compte (XPAI1).

    Reprend le contexte du bulletin (``bulletin_context``) et affiche en plus
    les lignes d'indemnités de fin de contrat déjà matérialisées sur le
    bulletin STC (préfixe ``STC_`` des codes de ligne).
    """
    if today is None:
        today = date.today()
    ctx = bulletin_context(bulletin)
    lignes_html = ''.join(
        _LIGNE_TPL.format(**ligne) for ligne in ctx['lignes'])
    date_txt = f'{today.day} {MOIS_FR[today.month]} {today.year}'
    motif = escape(getattr(bulletin, 'motif', '') or '')
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<style>
  body {{ font-family: sans-serif; font-size: 11px; color: #222; margin: 30px; }}
  h1 {{ font-size: 18px; text-align: center; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  th, td {{ border: 1px solid #ccc; padding: 4px 6px; }}
  .total {{ font-weight: bold; font-size: 13px; margin-top: 10px; }}
  .date {{ text-align: right; margin-top: 40px; }}
  .signature {{ margin-top: 60px; display: flex; justify-content: space-between; }}
</style></head><body>
  <h1>Reçu pour solde de tout compte</h1>
  <p><strong>Salarié :</strong> {ctx['employe']}
     &nbsp; <strong>Matricule :</strong> {ctx['matricule']}
     &nbsp; <strong>N° CNSS :</strong> {ctx['numero_cnss']}</p>
  <p><strong>Période de sortie :</strong> {ctx['periode']}</p>
  {f'<p><strong>Motif :</strong> {motif}</p>' if motif else ''}
  <table>
    <thead><tr><th>Code</th><th>Libellé</th><th>Montant (MAD)</th></tr></thead>
    <tbody>{lignes_html}</tbody>
  </table>
  <p class="total">Net à payer (solde de tout compte) : {ctx['net_a_payer']} MAD</p>
  <p>Je soussigné(e) {ctx['employe']}, reconnais avoir reçu de mon employeur la
  somme ci-dessus au titre du solde de tout compte, et lui donne quittance,
  sans réserve ni restriction, pour raison de salaire, indemnités et
  accessoires de toute nature.</p>
  <div class="signature">
    <span>Signature de l'employeur</span>
    <span>Signature du salarié (précédée de la mention « pour solde de tout
    compte »)</span>
  </div>
  <p class="date">Fait le {escape(date_txt)}.</p>
</body></html>"""


def render_stc_pdf(bulletin, *, today=None):
    """Reçu pour solde de tout compte → octets PDF (XPAI1)."""
    return _html_to_pdf(render_stc_html(bulletin, today=today))


# ── XPAI26 — Registres d'inspection du travail ─────────────────────────────

def render_registre_conges_html(registre, *, today=None):
    """Construit le HTML du registre des congés annuel (XPAI26).

    ``registre`` = le dict renvoyé par ``services.registre_conges`` (année +
    lignes ``{'matricule', 'nom', 'droits', 'pris', 'solde'}``). Format
    conforme à l'inspection du travail (registre récapitulatif annuel).
    """
    if today is None:
        today = date.today()
    date_txt = f'{today.day} {MOIS_FR[today.month]} {today.year}'
    lignes_html = ''.join(
        f"<tr><td>{escape(str(lig['matricule']))}</td>"
        f"<td>{escape(str(lig['nom']))}</td>"
        f"<td>{_fmt(lig['droits'])}</td>"
        f"<td>{_fmt(lig['pris'])}</td>"
        f"<td>{_fmt(lig['solde'])}</td></tr>"
        for lig in registre['lignes'])
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<style>
  body {{ font-family: sans-serif; font-size: 11px; color: #222; margin: 30px; }}
  h1 {{ font-size: 16px; text-align: center; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
  th, td {{ border: 1px solid #999; padding: 4px 6px; text-align: right; }}
  th:nth-child(1), th:nth-child(2), td:nth-child(1), td:nth-child(2)
    {{ text-align: left; }}
  .date {{ text-align: right; margin-top: 20px; }}
</style></head><body>
  <h1>Registre des congés — année {registre['annee']}</h1>
  <table>
    <thead><tr><th>Matricule</th><th>Nom</th>
      <th>Droits (j)</th><th>Pris (j)</th><th>Solde (j)</th></tr></thead>
    <tbody>{lignes_html}</tbody>
  </table>
  <p class="date">Édité le {escape(date_txt)}.</p>
</body></html>"""


def render_registre_conges_pdf(registre, *, today=None):
    """Registre des congés → octets PDF (XPAI26)."""
    return _html_to_pdf(render_registre_conges_html(registre, today=today))


def render_historique_carriere_html(historique, *, today=None):
    """Construit le HTML de la fiche historique carrière/salaire (XPAI26).

    ``historique`` = le dict renvoyé par ``services.historique_carriere``
    (identité + poste + liste ``annees`` ``{'annee', 'brut'}``).
    """
    if today is None:
        today = date.today()
    date_txt = f'{today.day} {MOIS_FR[today.month]} {today.year}'
    lignes_html = ''.join(
        f"<tr><td>{a['annee']}</td><td>{_fmt(a['brut'])}</td></tr>"
        for a in historique['annees'])
    embauche = historique.get('date_embauche')
    embauche_txt = embauche.isoformat() if embauche else '—'
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<style>
  body {{ font-family: sans-serif; font-size: 12px; color: #222; margin: 40px; }}
  h1 {{ font-size: 18px; text-align: center; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
  th, td {{ border: 1px solid #999; padding: 4px 8px; text-align: right; }}
  th:first-child, td:first-child {{ text-align: left; }}
  .date {{ text-align: right; margin-top: 20px; }}
</style></head><body>
  <h1>Fiche historique de carrière</h1>
  <p><strong>Matricule :</strong> {escape(str(historique['matricule']))}
     &nbsp; <strong>Nom :</strong> {escape(historique['nom'])}
     {escape(historique['prenom'])}</p>
  <p><strong>Poste :</strong> {escape(historique['poste'] or '—')}
     &nbsp; <strong>Type de contrat :</strong>
     {escape(historique['type_contrat'])}</p>
  <p><strong>Date d'embauche :</strong> {escape(embauche_txt)}</p>
  <table>
    <thead><tr><th>Année</th><th>Rémunération brute (MAD)</th></tr></thead>
    <tbody>{lignes_html}</tbody>
  </table>
  <p class="date">Édité le {escape(date_txt)}.</p>
</body></html>"""


def render_historique_carriere_pdf(historique, *, today=None):
    """Fiche historique de carrière → octets PDF (XPAI26)."""
    return _html_to_pdf(
        render_historique_carriere_html(historique, today=today))


# ── ZPAI5 — Impression en lot des bulletins d'une période (PDF fusionné) ────

def render_bulletins_periode_pdf(periode):
    """Fusionne les PDF des bulletins VALIDÉS d'une période en un seul flux (ZPAI5).

    Réutilise ``render_bulletin_pdf``/WeasyPrint pour chaque bulletin (les
    brouillons sont exclus), puis concatène les pages via PyMuPDF (``fitz``,
    déjà une dépendance de l'ERP) — une page-break naturelle entre chaque
    bulletin, dans l'ordre matricule/nom. Self-contained : aucune dépendance à
    une autre app. Lève ``ValueError`` si la période n'a AUCUN bulletin
    validé. Renvoie les octets du PDF fusionné.
    """
    from .models import BulletinPaie

    bulletins = list(
        BulletinPaie.objects
        .filter(company=periode.company, periode=periode,
                statut=BulletinPaie.STATUT_VALIDE)
        .select_related('profil', 'profil__employe')
    )
    if not bulletins:
        raise ValueError("Aucun bulletin validé pour cette période.")

    def _tri_matricule_nom(bulletin):
        employe = getattr(bulletin.profil, 'employe', None)
        matricule = getattr(employe, 'matricule', '') or ''
        nom = _nom_employe(bulletin.profil)
        return (matricule, nom)

    bulletins.sort(key=_tri_matricule_nom)

    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover - dépend de l'environnement
        raise RuntimeError(
            "WeasyPrint/PyMuPDF ne sont pas installés : génération PDF "
            "indisponible."
        ) from exc

    out = fitz.open()
    try:
        for bulletin in bulletins:
            pdf_bytes = render_bulletin_pdf(bulletin)
            seg = fitz.open(stream=pdf_bytes, filetype='pdf')
            out.insert_pdf(seg)
            seg.close()
        return out.tobytes()
    finally:
        out.close()
