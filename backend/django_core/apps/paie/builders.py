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
import hashlib
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

# AUD701 — le corps du bulletin porte désormais le TYPE et le SIGNE de chaque
# ligne : sans eux, une retenue (stockée en positif) s'imprimait exactement
# comme un gain. (L'ancien ``_LIGNE_TPL`` à trois colonnes, sans type ni
# signe, n'a plus d'appelant depuis que le reçu STC passe lui aussi par les
# trois blocs — AUD702.)
_LIGNE_TPL_DETAIL = (
    '<tr><td>{code}</td><td>{libelle}</td><td>{type_libelle}</td>'
    '<td style="text-align:right">{montant_signe}</td></tr>'
)

# AUD701 — les lignes 100 % PATRONALES. Elles ne diminuent JAMAIS le net du
# salarié : elles sortent du corps du bulletin et vont dans un encadré
# « information — non déduit ». La distinction salarial/patronal ne se lit PAS
# sur ``type`` (ces lignes sont `cotisation`, comme les cotisations salariales
# CNSS/AMO/CIMR) : elle se lit sur le CODE — c'est le contrat partagé
# ``apps/paie/contract_samples/bulletin_lignes.json`` qui le dit, et
# ``services._CODES_PATRONALES_ITEMISEES`` porte la même liste côté moteur.
CODES_PATRONAUX_INFORMATIFS = ('MUTUELLE_PAT', 'ALLOC_FAM', 'FORMATION_PRO')

_TYPE_LIBELLES = {
    'gain': 'Gain',
    'retenue': 'Retenue',
    'cotisation': 'Cotisation',
}


def _ligne_context(ligne):
    """Une ``LigneBulletin`` → dict d'affichage (échappé, signé, typé)."""
    type_ligne = ligne.type or 'gain'
    montant = Decimal(ligne.montant or 0)
    # Un gain s'imprime tel quel ; une retenue/cotisation s'imprime avec
    # l'effet de son sens (négatif). Un bulletin d'ANNULATION porte des
    # montants déjà négatifs : la même règle rend alors la retenue en positif,
    # ce qui EST l'extourne correcte.
    signe = montant if type_ligne == 'gain' else -montant
    return {
        'code': escape(ligne.code or ''),
        'libelle': escape(ligne.libelle or ''),
        'type': type_ligne,
        'type_libelle': escape(_TYPE_LIBELLES.get(type_ligne, type_ligne)),
        'montant': _fmt(montant),
        'montant_signe': _fmt(signe),
        'montant_brut': montant,
    }


def _date_fr(valeur):
    """Une date → « 5 juillet 2026 », ou '' si elle n'est pas renseignée."""
    if not valeur:
        return ''
    return f'{valeur.day} {MOIS_FR[valeur.month]} {valeur.year}'


def employeur_context(company):
    """AUD704 — identité de l'employeur, mentions obligatoires du bulletin.

    Ne renvoie QUE les mentions réellement renseignées : une société qui n'a
    pas encore saisi son ICE n'imprime pas « ICE : » suivi du vide, et rien
    n'est jamais inventé. ``mentions`` est une liste de couples (libellé,
    valeur) déjà échappés.
    """
    if company is None:
        return {'nom': '', 'adresse': '', 'mentions': []}
    champs = (
        ('RC', 'registre_commerce'),
        ('IF', 'identifiant_fiscal'),
        ('ICE', 'ice'),
        ("N° CNSS employeur", 'numero_cnss_employeur'),
    )
    mentions = [
        (libelle, escape(str(getattr(company, attribut, '') or '')))
        for libelle, attribut in champs
        if getattr(company, attribut, '')
    ]
    return {
        'nom': escape(getattr(company, 'nom', '') or ''),
        'adresse': escape(getattr(company, 'adresse', '') or ''),
        'mentions': mentions,
    }


def bulletin_context(bulletin):
    """Contexte de rendu d'un bulletin (dict de chaînes prêtes à afficher).

    Lecture seule : ne lit que des champs publics du bulletin et de son profil.

    AUD701 — les lignes sont désormais RÉPARTIES en trois blocs (contrat
    ``apps/paie/contract_samples/bulletin_lignes.json``) : ``gains``,
    ``retenues`` (salariales — cotisations CNSS/AMO/CIMR, IR, avances,
    saisies, mutuelle) et ``patronal`` (informatif, jamais déduit du net).
    ``lignes`` reste la liste complète, inchangée pour ses autres appelants.
    """
    profil = bulletin.profil
    periode = bulletin.periode
    lignes = [_ligne_context(ligne) for ligne in bulletin.lignes.all()]
    gains, retenues, patronal = [], [], []
    for ligne in lignes:
        if ligne['code'] in CODES_PATRONAUX_INFORMATIFS:
            patronal.append(ligne)
        elif ligne['type'] == 'gain':
            gains.append(ligne)
        else:
            retenues.append(ligne)
    # Sous-total DÉRIVÉ des lignes réellement imprimées — jamais un montant
    # reconstruit à côté (règle « zéro chiffre inventé »).
    total_retenues = sum(
        (ligne['montant_brut'] for ligne in retenues), Decimal('0'))
    total_patronal = sum(
        (ligne['montant_brut'] for ligne in patronal), Decimal('0'))
    return {
        'employe': escape(_nom_employe(profil)),
        'matricule': escape(
            getattr(getattr(profil, 'employe', None), 'matricule', '') or ''),
        'numero_cnss': escape(profil.numero_cnss or ''),
        'periode': escape(_libelle_periode(periode)),
        # AUD704 — mentions obligatoires absentes jusqu'ici : identité de
        # l'employeur, date de paiement et jours/heures payés. Les deux
        # dernières EXISTAIENT déjà en base et n'étaient simplement jamais
        # imprimées.
        'employeur': employeur_context(getattr(bulletin, 'company', None)),
        'date_paiement': escape(
            _date_fr(getattr(periode, 'date_paiement', None))),
        'jours_travail': getattr(profil, 'jours_travail_mensuel', '') or '',
        'heures_travail': getattr(profil, 'heures_travail_mensuel', '') or '',
        'lignes': lignes,
        'gains': gains,
        'retenues': retenues,
        'patronal': patronal,
        'total_retenues': _fmt(total_retenues),
        'total_patronal': _fmt(total_patronal),
        'brut': _fmt(bulletin.brut),
        'brut_imposable': _fmt(bulletin.brut_imposable),
        'frais_professionnels': _fmt(bulletin.frais_professionnels),
        'net_imposable': _fmt(bulletin.net_imposable),
        'cnss': _fmt(bulletin.cnss_salariale),
        'amo': _fmt(bulletin.amo_salariale),
        'cimr': _fmt(bulletin.cimr_salariale),
        'ir': _fmt(bulletin.ir),
        'net_a_payer': _fmt(bulletin.net_a_payer),
    }


_BULLETIN_STYLE = """
  body { font-family: sans-serif; font-size: 11px; color: #222; }
  h1 { font-size: 18px; }
  h2 { font-size: 13px; margin: 14px 0 2px; }
  table { width: 100%; border-collapse: collapse; margin-top: 4px; }
  th, td { border: 1px solid #ccc; padding: 4px 6px; }
  .total { font-weight: bold; font-size: 13px; }
  .sous-total td { font-weight: bold; background: #f4f4f4; }
  .chaine td { padding: 3px 6px; }
  .chaine .net { font-weight: bold; font-size: 13px; }
  .patronal { margin-top: 14px; border: 1px dashed #999; padding: 6px 8px; }
  .patronal p { margin: 0 0 4px; font-style: italic; }
  .employeur { border: 1px solid #ccc; padding: 6px 8px; margin-bottom: 8px; }
"""


def _mention_html(libelle, valeur):
    """« &nbsp; <strong>Libellé :</strong> valeur » — vide si non renseigné."""
    if valeur in (None, ''):
        return ''
    return (f'&nbsp; <strong>{escape(libelle)} :</strong> '
            f'{escape(str(valeur))}')


def _entete_employeur_html(employeur):
    """En-tête employeur du bulletin (AUD704) — n'imprime que le renseigné."""
    if not employeur or not (employeur['nom'] or employeur['adresse']
                             or employeur['mentions']):
        return ''
    lignes = []
    if employeur['nom']:
        lignes.append(f"<strong>{employeur['nom']}</strong>")
    if employeur['adresse']:
        lignes.append(employeur['adresse'].replace('\n', '<br>'))
    if employeur['mentions']:
        lignes.append(' &nbsp; '.join(
            f'<strong>{libelle} :</strong> {valeur}'
            for libelle, valeur in employeur['mentions']))
    return f"<div class=\"employeur\">{'<br>'.join(lignes)}</div>"


def _bloc_lignes_html(titre, lignes, *, sous_total=None,
                      libelle_sous_total=None):
    """Un bloc « titre + tableau typé/signé (+ sous-total) » du bulletin."""
    if not lignes:
        return ''
    corps = ''.join(_LIGNE_TPL_DETAIL.format(**ligne) for ligne in lignes)
    if sous_total is not None:
        corps += (
            f'<tr class="sous-total"><td></td>'
            f'<td>{escape(libelle_sous_total or "Sous-total")}</td><td></td>'
            f'<td style="text-align:right">{sous_total}</td></tr>')
    return (
        f'<h2>{escape(titre)}</h2>'
        '<table><thead><tr><th>Code</th><th>Libellé</th><th>Type</th>'
        '<th>Montant (MAD)</th></tr></thead>'
        f'<tbody>{corps}</tbody></table>')


def render_bulletin_html(bulletin):
    """Construit le HTML du bulletin de paie (PAIE34, refondu AUD701).

    Trois blocs — Gains / Retenues salariales (détail + sous-total) /
    information patronale non déduite — puis la chaîne explicite
    Brut → Total des retenues → Net imposable → IR → Net à payer.
    """
    ctx = bulletin_context(bulletin)
    gains_html = _bloc_lignes_html('Gains', ctx['gains'])
    retenues_html = _bloc_lignes_html(
        'Retenues salariales', ctx['retenues'],
        sous_total=f"-{ctx['total_retenues']}",
        libelle_sous_total='Total des retenues salariales')
    patronal_html = ''
    if ctx['patronal']:
        corps = ''.join(
            f"<tr><td>{ligne['code']}</td><td>{ligne['libelle']}</td>"
            f"<td style=\"text-align:right\">{ligne['montant']}</td></tr>"
            for ligne in ctx['patronal'])
        patronal_html = (
            '<div class="patronal">'
            '<p>Charges patronales — information, NON déduites de votre net '
            'à payer.</p>'
            '<table><thead><tr><th>Code</th><th>Libellé</th>'
            '<th>Montant (MAD)</th></tr></thead>'
            f'<tbody>{corps}</tbody></table>'
            f"<p>Total charges patronales : {ctx['total_patronal']} MAD</p>"
            '</div>')
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<style>{_BULLETIN_STYLE}</style></head><body>
  <h1>Bulletin de paie</h1>
  {_entete_employeur_html(ctx['employeur'])}
  <p><strong>Salarié :</strong> {ctx['employe']}
     &nbsp; <strong>Matricule :</strong> {ctx['matricule']}
     &nbsp; <strong>N° CNSS :</strong> {ctx['numero_cnss']}</p>
  <p><strong>Période :</strong> {ctx['periode']}
     {_mention_html('Date de paiement', ctx['date_paiement'])}
     {_mention_html('Jours payés', ctx['jours_travail'])}
     {_mention_html('Heures payées', ctx['heures_travail'])}</p>
  {gains_html}
  {retenues_html}
  <h2>Récapitulatif</h2>
  <table class="chaine">
    <tr><td>Brut</td>
        <td style="text-align:right">{ctx['brut']}</td></tr>
    <tr><td>Brut imposable</td>
        <td style="text-align:right">{ctx['brut_imposable']}</td></tr>
    <tr><td>Total des retenues salariales</td>
        <td style="text-align:right">-{ctx['total_retenues']}</td></tr>
    <tr><td>Frais professionnels</td>
        <td style="text-align:right">{ctx['frais_professionnels']}</td></tr>
    <tr><td>Net imposable</td>
        <td style="text-align:right">{ctx['net_imposable']}</td></tr>
    <tr><td>Impôt sur le revenu (IR)</td>
        <td style="text-align:right">-{ctx['ir']}</td></tr>
    <tr class="net"><td>Net à payer</td>
        <td style="text-align:right">{ctx['net_a_payer']} MAD</td></tr>
  </table>
  <p class="total">Net à payer : {ctx['net_a_payer']} MAD</p>
  {patronal_html}
</body></html>"""


def render_bulletin_pdf(bulletin):
    """Bulletin de paie → octets PDF (PAIE34)."""
    return _html_to_pdf(render_bulletin_html(bulletin))


# ── AUD703 — Archive immuable du bulletin validé (doctrine D9) ─────────────

class ArchiveBulletinIndisponible(RuntimeError):
    """L'archive d'un bulletin VALIDÉ existe mais ne peut pas être servie.

    On préfère un échec explicite à un re-rendu : re-rendre servirait un
    document POTENTIELLEMENT DIFFÉRENT de celui qui a été remis au salarié —
    exactement le défaut que l'archive ferme.
    """


def cle_archive_bulletin(bulletin):
    """Clé de l'objet archivé, préfixée par la SOCIÉTÉ (multi-tenant)."""
    periode = bulletin.periode
    return (f'paie/{bulletin.company_id}/bulletins/'
            f'{periode.annee}/{periode.mois:02d}/{bulletin.id}.pdf')


def _archive_put(cle, pdf_bytes):
    """Téléverse l'archive dans MinIO. Isolé pour être remplaçable en test."""
    from django.conf import settings

    from core.pdf import _upload_pdf

    return _upload_pdf(pdf_bytes, cle,
                       getattr(settings, 'MINIO_BUCKET_PDF', 'erp-pdf'))


def _archive_get(cle):
    """Relit l'archive depuis MinIO. Isolé pour être remplaçable en test."""
    from django.conf import settings

    from core.pdf import _minio_client

    bucket = getattr(settings, 'MINIO_BUCKET_PDF', 'erp-pdf')
    return _minio_client().get_object(Bucket=bucket, Key=cle)['Body'].read()


def archiver_bulletin_pdf(bulletin, *, pdf_bytes=None):
    """Rend (si besoin), archive et EMPREINTE le PDF d'un bulletin (AUD703).

    Écrit ``pdf_archive_cle`` / ``pdf_sha256`` / ``pdf_archive_le`` sur le
    bulletin — champs autorisés après validation (cf.
    ``BulletinPaie._CHAMPS_AUTORISES_APRES_VALIDATION``). L'empreinte est
    posée MÊME si le téléversement échoue (l'entrepôt peut être indisponible) :
    on garde alors la preuve de ce qui a été rendu, sans prétendre à une
    archive. Renvoie les octets du PDF. N'archive jamais deux fois : un
    bulletin qui porte déjà une clé est rendu tel quel depuis son archive.
    """
    from django.utils import timezone

    if pdf_bytes is None:
        pdf_bytes = render_bulletin_pdf(bulletin)
    empreinte = hashlib.sha256(pdf_bytes).hexdigest()
    cle = cle_archive_bulletin(bulletin)
    champs = ['pdf_sha256', 'pdf_archive_le']
    try:
        _archive_put(cle, pdf_bytes)
    except Exception:
        # Entrepôt indisponible : on n'invente pas une archive qui n'existe
        # pas. La clé reste vide → le prochain appel réessaiera d'archiver.
        cle = ''
    else:
        bulletin.pdf_archive_cle = cle
        champs.append('pdf_archive_cle')
    bulletin.pdf_sha256 = empreinte
    bulletin.pdf_archive_le = timezone.now()
    if bulletin.pk:
        bulletin.save(update_fields=champs)
    return pdf_bytes


def bulletin_pdf_a_servir(bulletin):
    """Les octets à SERVIR pour ce bulletin (AUD703) — jamais un re-rendu.

    * bulletin en BROUILLON → rendu à la volée (rien n'a encore été remis) ;
    * bulletin VALIDÉ déjà archivé → l'objet archivé, à l'octet près ;
    * bulletin VALIDÉ pas encore archivé (validé avant AUD703, ou entrepôt
      indisponible ce jour-là) → rendu MAINTENANT puis archivé, et ce sont ces
      octets-là qui font foi ensuite.

    Lève ``ArchiveBulletinIndisponible`` si une archive EXISTE mais est
    illisible : mieux vaut un échec explicite qu'un document divergent.
    """
    from .models import BulletinPaie

    if getattr(bulletin, 'statut', None) != BulletinPaie.STATUT_VALIDE:
        return render_bulletin_pdf(bulletin)
    if bulletin.pdf_archive_cle:
        try:
            return _archive_get(bulletin.pdf_archive_cle)
        except Exception as exc:
            raise ArchiveBulletinIndisponible(
                "Archive du bulletin indisponible : le document remis au "
                "salarié ne peut pas être resservi pour l'instant."
            ) from exc
    return archiver_bulletin_pdf(bulletin)


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

def stc_est_definitif(bulletin):
    """AUD702 — un reçu STC n'est DÉFINITIF que sur un bulletin VALIDÉ.

    Tant que le bulletin est en brouillon, ``generer_bulletin_stc`` supprime et
    recrée toutes ses lignes à chaque appel : le montant d'un reçu signé
    aujourd'hui peut ne plus correspondre à rien en base demain. Un reçu servi
    depuis un brouillon est donc un PROJET — sans clause de quittance ni bloc
    de signature.
    """
    from .models import BulletinPaie

    return getattr(bulletin, 'statut', None) == BulletinPaie.STATUT_VALIDE


# AUD702 — mentions protectrices du reçu pour solde de tout compte. Le délai
# de forclusion de SOIXANTE JOURS, la remise en DEUX EXEMPLAIRES et le
# récapitulatif détaillé des sommes sont les trois mentions dont l'ABSENCE
# était prouvée par lecture du gabarit. La FORMULATION exacte reste à
# contre-valider par le conseil juridique — aucun article de loi n'est cité
# ici, et aucun délai autre que celui posé par la tâche n'est inventé.
_STC_MENTIONS_LEGALES = (
    '<div class="mentions">'
    '<p><strong>Mentions</strong></p>'
    '<ul>'
    '<li>Le présent reçu peut être dénoncé par le salarié dans un délai de '
    '<strong>soixante (60) jours</strong> à compter de sa signature.</li>'
    '<li>Il est établi en <strong>deux exemplaires</strong>, dont un remis au '
    'salarié.</li>'
    '<li>Le détail des sommes composant le total ci-dessus figure dans les '
    'tableaux Gains et Retenues salariales de ce document.</li>'
    '</ul></div>'
)


def render_stc_html(bulletin, *, today=None, definitif=None):
    """Construit le HTML du reçu pour solde de tout compte (XPAI1).

    Reprend le contexte du bulletin (``bulletin_context``) et affiche en plus
    les lignes d'indemnités de fin de contrat déjà matérialisées sur le
    bulletin STC (préfixe ``STC_`` des codes de ligne).

    AUD702 — le détail est rendu en TROIS BLOCS (Gains / Retenues salariales
    avec sous-total / charges patronales informatives), comme le bulletin
    (AUD701) : le reçu n'affichait auparavant aucune cotisation salariale.
    ``definitif`` (déduit du statut du bulletin par défaut) commande la clause
    de quittance et les signatures : un bulletin NON validé produit un PROJET
    filigrané, sans quittance ni bloc de signature.
    """
    if today is None:
        today = date.today()
    if definitif is None:
        definitif = stc_est_definitif(bulletin)
    ctx = bulletin_context(bulletin)
    gains_html = _bloc_lignes_html('Gains', ctx['gains'])
    retenues_html = _bloc_lignes_html(
        'Retenues salariales', ctx['retenues'],
        sous_total=f"-{ctx['total_retenues']}",
        libelle_sous_total='Total des retenues salariales')
    patronal_html = _bloc_lignes_html(
        'Charges patronales — information, NON déduites du net',
        ctx['patronal'])
    date_txt = f'{today.day} {MOIS_FR[today.month]} {today.year}'
    motif = escape(getattr(bulletin, 'motif', '') or '')
    if definitif:
        filigrane = ''
        cloture = f"""
  <p>Je soussigné(e) {ctx['employe']}, reconnais avoir reçu de mon employeur la
  somme ci-dessus au titre du solde de tout compte, et lui donne quittance,
  sans réserve ni restriction, pour raison de salaire, indemnités et
  accessoires de toute nature.</p>
  {_STC_MENTIONS_LEGALES}
  <div class="signature">
    <span>Signature de l'employeur</span>
    <span>Signature du salarié (précédée de la mention « pour solde de tout
    compte »)</span>
  </div>"""
    else:
        filigrane = (
            '<div class="filigrane">PROJET</div>'
            '<p class="bandeau">PROJET — sans valeur juridique. Ce document '
            'est établi depuis un bulletin non validé : ses montants peuvent '
            'encore changer. Il ne donne aucune quittance et ne doit pas être '
            'signé.</p>')
        cloture = (
            '<p class="bandeau">Le reçu DÉFINITIF, portant la clause de '
            'quittance, les mentions protectrices et les signatures, ne sera '
            'délivré qu\'après validation du bulletin de solde de tout '
            'compte.</p>')
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<style>
  body {{ font-family: sans-serif; font-size: 11px; color: #222; margin: 30px; }}
  h1 {{ font-size: 18px; text-align: center; }}
  h2 {{ font-size: 13px; margin: 14px 0 2px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 4px; }}
  th, td {{ border: 1px solid #ccc; padding: 4px 6px; }}
  .sous-total td {{ font-weight: bold; background: #f4f4f4; }}
  .total {{ font-weight: bold; font-size: 13px; margin-top: 10px; }}
  .date {{ text-align: right; margin-top: 40px; }}
  .signature {{ margin-top: 60px; display: flex; justify-content: space-between; }}
  .mentions {{ margin-top: 14px; border: 1px solid #999; padding: 6px 8px; }}
  .mentions ul {{ margin: 4px 0 0 16px; padding: 0; }}
  .bandeau {{ border: 2px solid #b00; color: #b00; font-weight: bold;
             padding: 6px 8px; text-align: center; }}
  .filigrane {{ position: fixed; top: 40%; left: 0; width: 100%;
               text-align: center; font-size: 72px; font-weight: bold;
               color: #b00; opacity: 0.12; transform: rotate(-25deg); }}
</style></head><body>
  {filigrane}
  <h1>Reçu pour solde de tout compte{'' if definitif else ' — PROJET'}</h1>
  <p><strong>Salarié :</strong> {ctx['employe']}
     &nbsp; <strong>Matricule :</strong> {ctx['matricule']}
     &nbsp; <strong>N° CNSS :</strong> {ctx['numero_cnss']}</p>
  <p><strong>Période de sortie :</strong> {ctx['periode']}</p>
  {f'<p><strong>Motif :</strong> {motif}</p>' if motif else ''}
  {gains_html}
  {retenues_html}
  {patronal_html}
  <p class="total">Net à payer (solde de tout compte) : {ctx['net_a_payer']} MAD</p>
  {cloture}
  <p class="date">Fait le {escape(date_txt)}.</p>
</body></html>"""


def render_stc_pdf(bulletin, *, today=None, definitif=None):
    """Reçu pour solde de tout compte → octets PDF (XPAI1)."""
    return _html_to_pdf(
        render_stc_html(bulletin, today=today, definitif=definitif))


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
