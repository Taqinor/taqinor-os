"""XQHS27 — Documents terrain QHSE imprimables bilingues FR/AR.

Rendu PDF INTERNE (WeasyPrint) pour trois documents terrain déjà saisis dans
l'app QHSE/RH, JAMAIS ``/proposal`` (règle CLAUDE.md #4 — ce chemin ne rend
QUE des devis client) et sans aucun prix :

* ``PermisTravail`` (checklist type + signatures) ;
* ``InductionSecurite`` (fiche d'accueil + émargement) ;
* ``CauserieSecurite`` (thème + liste d'émargement — modèle ``rh``, lu
  EXCLUSIVEMENT via ``apps.rh.selectors.causerie_securite_for_id``, jamais un
  import de ``rh.models``/``rh.views``).

Chaque document se rend en FR ou en AR (``lang='fr'`` / ``lang='ar'``) : le
gabarit AR bascule en RTL (``dir="rtl"``) et utilise une police arabe
embarquée dans l'image Docker (``fonts-noto-naskh-arabic``, paquet Debian
libre — voir ``Dockerfile``) afin d'éviter le rendu "tofu" (glyphes carrés).

Le texte des deux langues est un dictionnaire de libellés fixe (pas de
traduction dynamique) : on ne traduit QUE la coquille du document (titres de
colonnes, en-têtes) — les données saisies (thème, noms, mesures de
prévention…) restent telles que saisies par l'utilisateur.

ARC11 — la plomberie WeasyPrint (``HTML(string=...).write_pdf()`` + import
paresseux) est déléguée au service partagé ``core.pdf.render_pdf`` ; les
GABARITS HTML/CSS bilingues ci-dessous restent STRICTEMENT identiques (aucune
option de branding activée), donc le rendu est inchangé à l'octet près.
"""
import html as _html

from core.pdf import render_pdf


def _esc(value):
    """Échappe le texte utilisateur injecté dans le HTML (jamais de jeton
    brut, jamais d'injection HTML depuis un champ libre)."""
    if value is None:
        return ''
    return _html.escape(str(value))


_LABELS = {
    'fr': {
        'permis_titre': 'Permis de travail',
        'reference': 'Référence',
        'type': 'Type',
        'statut': 'Statut',
        'chantier': 'Chantier',
        'validite': 'Fenêtre de validité',
        'delivre_par': 'Délivré par',
        'valide_par': 'Validé par',
        'mesures': 'Mesures de prévention',
        'notes': 'Notes',
        'signature_delivreur': 'Signature du délivreur',
        'signature_beneficiaire': 'Signature du bénéficiaire',
        'induction_titre': 'Accueil / induction sécurité',
        'personne': 'Personne accueillie',
        'entreprise_externe': 'Entreprise externe',
        'date_induction': "Date de l'accueil",
        'anime_par': 'Animé par',
        'themes': 'Thèmes couverts',
        'acquittement': "J'ai reçu ce briefing sécurité et je m'engage à respecter les consignes.",
        'signature_participant': 'Signature',
        'causerie_titre': 'Causerie sécurité (toolbox talk)',
        'theme': 'Thème',
        'date': 'Date',
        'lieu': 'Lieu',
        'animateur': 'Animateur',
        'emargement_titre': "Liste d'émargement",
        'nom_participant': 'Nom',
        'present': 'Présent',
        'signature': 'Signature',
        'oui': 'Oui',
        'non': 'Non',
    },
    'ar': {
        'permis_titre': 'تصريح عمل',
        'reference': 'المرجع',
        'type': 'النوع',
        'statut': 'الحالة',
        'chantier': 'الورش',
        'validite': 'فترة الصلاحية',
        'delivre_par': 'سلمه',
        'valide_par': 'صادق عليه',
        'mesures': 'إجراءات الوقاية',
        'notes': 'ملاحظات',
        'signature_delivreur': 'توقيع المسلِّم',
        'signature_beneficiaire': 'توقيع المستفيد',
        'induction_titre': 'استقبال / توجيه السلامة',
        'personne': 'الشخص المستقبَل',
        'entreprise_externe': 'المقاولة الخارجية',
        'date_induction': 'تاريخ الاستقبال',
        'anime_par': 'أشرف عليه',
        'themes': 'المواضيع المتناولة',
        'acquittement': 'تسلمت هذا التوجيه الأمني وألتزم باحترام التعليمات.',
        'signature_participant': 'التوقيع',
        'causerie_titre': 'جلسة توعية بالسلامة',
        'theme': 'الموضوع',
        'date': 'التاريخ',
        'lieu': 'المكان',
        'animateur': 'المشرف',
        'emargement_titre': 'قائمة التوقيعات',
        'nom_participant': 'الاسم',
        'present': 'حاضر',
        'signature': 'التوقيع',
        'oui': 'نعم',
        'non': 'لا',
    },
}


def _base_css(lang):
    """CSS commun ; ``dir: rtl`` + police arabe pour ``lang == 'ar'``."""
    direction = 'rtl' if lang == 'ar' else 'ltr'
    font_family = (
        "'Noto Naskh Arabic', 'DejaVu Sans', sans-serif" if lang == 'ar'
        else "'Liberation Sans', sans-serif"
    )
    align = 'right' if lang == 'ar' else 'left'
    return (
        "body{font-family:%s;font-size:11pt;color:#1a1a1a;margin:1.5cm;"
        "direction:%s;text-align:%s;line-height:1.5;}"
        "h1{font-size:16pt;border-bottom:2px solid #2b5cab;padding-bottom:6px;}"
        "table{width:100%%;border-collapse:collapse;margin-top:10px;}"
        "td,th{border:1px solid #999;padding:5px 8px;text-align:%s;}"
        ".sign-box{border:1px solid #999;height:60px;margin-top:4px;}"
        ".row{margin-top:8px;}"
        ".label{font-weight:bold;}"
    ) % (font_family, direction, align, align)


def _html_shell(lang, title, body):
    dir_attr = 'rtl' if lang == 'ar' else 'ltr'
    return (
        f"<html dir='{dir_attr}' lang='{lang}'><head><meta charset='utf-8'>"
        f"<title>{_esc(title)}</title>"
        f"<style>{_base_css(lang)}</style></head><body>{body}</body></html>"
    )


def _render_pdf(html_str):
    """Rend le PDF (bytes) via le service partagé ``core.pdf.render_pdf``
    (ARC11) — la plomberie WeasyPrint (import paresseux + write_pdf) y est
    centralisée ; le gabarit reste inchangé."""
    return render_pdf(html=html_str)


# ── Permis de travail ───────────────────────────────────────────────────────

def _permis_travail_html(permis, lang):
    lb = _LABELS[lang]
    body = (
        f"<h1>{_esc(lb['permis_titre'])} — {_esc(permis.titre)}</h1>"
        "<table>"
        f"<tr><td class='label'>{_esc(lb['reference'])}</td>"
        f"<td>{_esc(permis.reference or '—')}</td></tr>"
        f"<tr><td class='label'>{_esc(lb['type'])}</td>"
        f"<td>{_esc(permis.get_type_permis_display())}</td></tr>"
        f"<tr><td class='label'>{_esc(lb['statut'])}</td>"
        f"<td>{_esc(permis.get_statut_display())}</td></tr>"
        f"<tr><td class='label'>{_esc(lb['chantier'])}</td>"
        f"<td>{_esc(permis.chantier_id or '—')}</td></tr>"
        f"<tr><td class='label'>{_esc(lb['validite'])}</td>"
        f"<td>{_esc(permis.date_debut or '—')} → "
        f"{_esc(permis.date_fin or '—')}</td></tr>"
        f"<tr><td class='label'>{_esc(lb['delivre_par'])}</td>"
        f"<td>{_esc(permis.delivre_par or '—')}</td></tr>"
        f"<tr><td class='label'>{_esc(lb['valide_par'])}</td>"
        f"<td>{_esc(permis.valide_par or '—')}</td></tr>"
        "</table>"
        f"<div class='row'><div class='label'>{_esc(lb['mesures'])}</div>"
        f"<div>{_esc(permis.mesures_prevention or '—')}</div></div>"
        f"<div class='row'><div class='label'>{_esc(lb['notes'])}</div>"
        f"<div>{_esc(permis.notes or '—')}</div></div>"
        "<table><tr>"
        f"<th>{_esc(lb['signature_delivreur'])}</th>"
        f"<th>{_esc(lb['signature_beneficiaire'])}</th>"
        "</tr><tr>"
        "<td class='sign-box'></td><td class='sign-box'></td>"
        "</tr></table>"
    )
    return _html_shell(lang, lb['permis_titre'], body)


def render_permis_travail_pdf(permis, lang='fr'):
    """XQHS27 — PDF INTERNE du permis de travail (FR/AR). Jamais ``/proposal``,
    aucun prix. ``lang`` non reconnue retombe sur ``'fr'``."""
    if lang not in _LABELS:
        lang = 'fr'
    return _render_pdf(_permis_travail_html(permis, lang))


# ── Induction sécurité ──────────────────────────────────────────────────────

def _induction_securite_html(induction, lang):
    lb = _LABELS[lang]
    personne = induction.personne_nom
    if induction.est_sous_traitant and induction.entreprise_externe:
        personne = f'{personne} ({induction.entreprise_externe})'
    body = (
        f"<h1>{_esc(lb['induction_titre'])}</h1>"
        "<table>"
        f"<tr><td class='label'>{_esc(lb['personne'])}</td>"
        f"<td>{_esc(personne)}</td></tr>"
        f"<tr><td class='label'>{_esc(lb['chantier'])}</td>"
        f"<td>{_esc(induction.chantier_id or '—')}</td></tr>"
        f"<tr><td class='label'>{_esc(lb['date_induction'])}</td>"
        f"<td>{_esc(induction.date_induction or '—')}</td></tr>"
        f"<tr><td class='label'>{_esc(lb['anime_par'])}</td>"
        f"<td>{_esc(induction.anime_par or '—')}</td></tr>"
        "</table>"
        f"<div class='row'><div class='label'>{_esc(lb['themes'])}</div>"
        f"<div>{_esc(induction.themes or '—')}</div></div>"
        f"<div class='row'>{_esc(lb['acquittement'])}</div>"
        "<table><tr><th>{}</th></tr>"
        "<tr><td class='sign-box'></td></tr></table>"
        .format(_esc(lb['signature_participant']))
    )
    return _html_shell(lang, lb['induction_titre'], body)


def render_induction_securite_pdf(induction, lang='fr'):
    """XQHS27 — PDF INTERNE de la fiche d'accueil sécurité (FR/AR)."""
    if lang not in _LABELS:
        lang = 'fr'
    return _render_pdf(_induction_securite_html(induction, lang))


# ── Causerie sécurité (rh) ──────────────────────────────────────────────────

def _causerie_securite_html(causerie, lang):
    """``causerie`` = instance ``rh.CauserieSecurite`` obtenue via
    ``apps.rh.selectors.causerie_securite_for_id`` (jamais un import de
    ``rh.models`` ici)."""
    lb = _LABELS[lang]
    animateur = causerie.animateur
    animateur_nom = (
        f'{animateur.prenom} {animateur.nom}' if animateur else '—')
    rows = ''.join(
        "<tr><td>{}</td><td>{}</td><td class='sign-box'></td></tr>".format(
            _esc(f'{p.participant.prenom} {p.participant.nom}'),
            _esc(lb['oui']) if p.present else _esc(lb['non']),
        )
        for p in causerie.participants.all()
    )
    body = (
        f"<h1>{_esc(lb['causerie_titre'])}</h1>"
        "<table>"
        f"<tr><td class='label'>{_esc(lb['theme'])}</td>"
        f"<td>{_esc(causerie.theme)}</td></tr>"
        f"<tr><td class='label'>{_esc(lb['date'])}</td>"
        f"<td>{_esc(causerie.date_causerie)}</td></tr>"
        f"<tr><td class='label'>{_esc(lb['chantier'])}</td>"
        f"<td>{_esc(causerie.chantier_id or '—')}</td></tr>"
        f"<tr><td class='label'>{_esc(lb['lieu'])}</td>"
        f"<td>{_esc(causerie.lieu or '—')}</td></tr>"
        f"<tr><td class='label'>{_esc(lb['animateur'])}</td>"
        f"<td>{_esc(animateur_nom)}</td></tr>"
        "</table>"
        f"<h1 style='font-size:13pt;'>{_esc(lb['emargement_titre'])}</h1>"
        "<table><tr>"
        f"<th>{_esc(lb['nom_participant'])}</th>"
        f"<th>{_esc(lb['present'])}</th>"
        f"<th>{_esc(lb['signature'])}</th>"
        f"</tr>{rows}</table>"
    )
    return _html_shell(lang, lb['causerie_titre'], body)


def render_causerie_securite_pdf(causerie, lang='fr'):
    """XQHS27 — PDF INTERNE de la fiche causerie + émargement (FR/AR).
    ``causerie`` doit provenir de ``apps.rh.selectors.causerie_securite_for_id``
    (déjà scopé société) — cette fonction ne fait aucune vérification de
    société elle-même."""
    if lang not in _LABELS:
        lang = 'fr'
    return _render_pdf(_causerie_securite_html(causerie, lang))
