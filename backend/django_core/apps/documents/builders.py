"""
Générateurs de PDF après-vente (documents clients post-installation).

Ces documents sont de NOUVEAUX types (PV de réception, bon de livraison,
dossier de remise, attestations) — indépendants des devis/factures et de la
règle « moteur premium ». Ils réutilisent NÉANMOINS le même moteur que la
FACTURE : Jinja2 → WeasyPrint, avec l'identité société de
``parametres.CompanyProfile`` (via ``apps.ventes.utils.pdf``).

Garde-fou prix d'achat : le contexte chantier construit ici n'expose JAMAIS
``prix_achat`` / marge. On ne lit que des champs publics (désignation,
quantité, garantie texte). Aucun prix d'achat ne traverse cette couche.

ARC12 — la plomberie WeasyPrint (``HTML(string=...).write_pdf()``) est
déléguée au service partagé ``core.pdf.render_pdf`` ; les gabarits Django
(``get_template(...).render(ctx)``) restent STRICTEMENT identiques, donc le
rendu est inchangé à l'octet près.
"""
import hashlib
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.template.loader import get_template
from django.utils import timezone
from django.utils.html import escape

from apps.ventes.utils.pdf import _company_context
# XSTK18 — réutilise (lecture seule, aucune écriture) les utilitaires AR déjà
# vendored pour la facture legacy (XSAL13, `apps/ventes/utils/libelles_ar.py`) :
# même police Noto Sans Arabic embarquée, même résolution de langue depuis
# `Client.langue_document`. Import identique dans l'esprit à `_company_context`
# ci-dessus (déjà cross-app) — jamais un import de `apps.ventes.models`/`views`.
from apps.ventes.utils.libelles_ar import arabic_font_face_css, document_langue
from core.pdf import render_pdf

logger = logging.getLogger(__name__)

# Garantie par défaut (raisonnable) quand un produit n'a pas de texte garantie.
DEFAULT_GARANTIE = "Garantie selon conditions constructeur."

# XSTK18 — libellés FR/AR du bon de livraison (N22). Propres à ce module (le
# BL n'est pas couvert par `libelles_ar.LIBELLES`, qui ne porte que la
# facture legacy) : gabarit AR avec libellés fixes traduits, valeurs telles
# quelles — pas de traduction automatique.
_BON_LIVRAISON_LIBELLES = {
    'fr': {
        'titre': 'BON DE LIVRAISON',
        'chantier': 'Chantier',
        'expediteur': 'Expéditeur',
        'livre_a': 'Livré à',
        'date_livraison': 'Date de livraison',
        'puissance': 'Puissance',
        'designation': 'Désignation',
        'quantite': 'Quantité',
        'aucun_article': 'Aucun article rattaché à ce chantier.',
        'reception_client': 'Réception client',
        'reception_mention': 'Reçu en bon état — signature',
        'genere_le': 'Document généré le',
    },
    'ar': {
        'titre': 'إذن التسليم',
        'chantier': 'الورش',
        'expediteur': 'المرسل',
        'livre_a': 'التسليم إلى',
        'date_livraison': 'تاريخ التسليم',
        'puissance': 'القدرة',
        'designation': 'البيان',
        'quantite': 'الكمية',
        'aucun_article': 'لا يوجد أي عنصر مرتبط بهذا الورش.',
        'reception_client': 'استلام الزبون',
        'reception_mention': 'تم الاستلام في حالة جيدة — التوقيع',
        'genere_le': 'تم إنشاء الوثيقة بتاريخ',
    },
}


def _bl_libelle(cle, langue='fr'):
    """XSTK18 — Traduction d'un libellé du bon de livraison. FR par défaut
    (comportement inchangé quand `langue` n'est pas 'ar' ou que la clé est
    absente du dictionnaire AR — retombe alors sur le FR, jamais une clé
    brute affichée au client)."""
    table = _BON_LIVRAISON_LIBELLES.get(langue) or _BON_LIVRAISON_LIBELLES['fr']
    return table.get(cle) or _BON_LIVRAISON_LIBELLES['fr'].get(cle, cle)


# Guide d'exploitation & maintenance par défaut (français). Texte générique
# raisonnable, surchargeable plus tard si besoin.
DEFAULT_OPERATING_GUIDANCE = [
    "Vérifiez périodiquement (tous les mois) que les panneaux ne sont pas "
    "ombragés ni encrassés (poussière, feuilles, fientes).",
    "Nettoyez les modules à l'eau claire et avec une raclette douce, tôt le "
    "matin ou en fin de journée — jamais en plein soleil sur verre chaud.",
    "Surveillez la production via l'onduleur / l'application : une baisse "
    "anormale doit être signalée.",
    "Ne couvrez jamais les grilles de ventilation de l'onduleur et gardez le "
    "local technique propre et sec.",
    "Faites contrôler l'installation par un technicien qualifié au moins une "
    "fois par an (serrages, protections, mises à la terre).",
    "En cas d'anomalie (coupure, fumée, odeur, bruit), coupez l'installation "
    "au sectionneur et contactez le service après-vente.",
]


def _as_date(value):
    """Normalise une valeur date (date, datetime ou ISO 'YYYY-MM-DD') → date.

    Le ORM renvoie un ``date`` ; mais une instance fraîchement créée non
    rechargée peut porter la chaîne fournie. On rend les templates robustes
    en garantissant toujours un ``date`` (ou None) avec un ``.strftime``.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _html_to_pdf(html_string):
    """HTML → octets PDF via ``core.pdf.render_pdf`` (ARC12)."""
    return render_pdf(html=html_string)


def _systeme_summary(chantier):
    """Résumé système (sans aucun prix) pour l'en-tête des documents."""
    type_label = (
        chantier.get_type_installation_display()
        if chantier.type_installation else None
    )
    return {
        'puissance_kwc': chantier.puissance_installee_kwc,
        'type_installation': type_label,
        'raccordement': (
            chantier.get_raccordement_display()
            if chantier.raccordement else None
        ),
        'site_adresse': chantier.site_adresse,
        'site_ville': chantier.site_ville,
        'date_mise_en_service': _as_date(chantier.date_mise_en_service),
        'date_pose_reelle': _as_date(chantier.date_pose_reelle),
    }


def _client_block(client):
    """Bloc client — uniquement des champs publics."""
    if client is None:
        return {}
    return {
        'nom': client.nom,
        'prenom': getattr(client, 'prenom', '') or '',
        'email': getattr(client, 'email', '') or '',
        'telephone': getattr(client, 'telephone', '') or '',
        'adresse': getattr(client, 'adresse', '') or '',
    }


def _quantite_affichee(valeur):
    """ADOC60 — quantité imprimable d'une ligne de nomenclature, ou ``None``
    quand la ligne n'a pas de quantité (intertitre, ligne vide) : jamais une
    cellule « None ». Entier quand la quantité l'est (8.0 → 8), sinon la
    décimale normalisée (2.50 → 2.5)."""
    if valeur is None or valeur == '':
        return None
    try:
        d = Decimal(str(valeur))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not d.is_finite() or d <= 0:
        return None
    if d == d.to_integral_value():
        return int(d)
    return d.normalize()


def _ligne_composant(designation, quantite, produit, marque=''):
    """ADOC60 — whitelist d'une ligne de matériel : désignation, quantité,
    marque, garantie texte. Le prix d'achat n'est jamais lu."""
    garantie = (
        (getattr(produit, 'garantie', None) or '').strip() if produit else '')
    marque = (marque or '').strip() or (
        (getattr(produit, 'marque', None) or '').strip() if produit else '')
    return {
        'designation': designation or (
            getattr(produit, 'nom', '') if produit else ''),
        'quantite': quantite,
        'marque': marque,
        'garantie': garantie or DEFAULT_GARANTIE,
    }


def _composants(chantier):
    """Matériel vendu du chantier (PV, BL FR/AR, garanties du dossier).

    ADOC60 — source = la nomenclature GELÉE du chantier (``Installation.bom``,
    figée à la création par ``installations.services._freeze_bom`` : option
    retenue d'un devis à deux options, ×N villas, sans optionnelles ni
    intertitres) — plus jamais l'itération brute des lignes du devis qui
    listait le kit non acheté et des quantités « None ». Garantie lue sur
    ``Produit.garantie`` via le ``produit_id`` de la ligne (sélecteur stock,
    scopé société), repli ``DEFAULT_GARANTIE``.

    Chantier sans ``bom`` (créé avant N1) : repli sur la MÊME règle que la
    facturation, ``apps.ventes.utils.options.option_lines(devis)`` × nombre
    de propriétés ; lignes sans quantité exclues.

    On ne renvoie QUE désignation + quantité + marque + garantie texte. Le prix
    d'achat n'est jamais lu : impossible de le faire fuiter dans un document
    client.
    """
    bom = getattr(chantier, 'bom', None)
    if isinstance(bom, list) and bom:
        from apps.stock.selectors import get_produit_scoped
        cache = {}
        items = []
        for row in bom:
            if not isinstance(row, dict):
                continue
            quantite = _quantite_affichee(row.get('quantite'))
            if quantite is None:
                continue
            produit_id = row.get('produit_id')
            produit = None
            if produit_id:
                if produit_id not in cache:
                    try:
                        cache[produit_id] = get_produit_scoped(
                            chantier.company, produit_id)
                    except (TypeError, ValueError):
                        cache[produit_id] = None
                produit = cache[produit_id]
            items.append(_ligne_composant(
                row.get('designation'), quantite, produit,
                row.get('marque') or ''))
        return items

    devis = getattr(chantier, 'devis', None)
    if devis is None:
        return []
    from apps.ventes.selectors import nombre_proprietes
    from apps.ventes.utils.options import option_lines
    try:
        n_prop = int(nombre_proprietes(devis) or 1)
    except (TypeError, ValueError):
        n_prop = 1
    items = []
    for ligne in option_lines(devis):
        brute = getattr(ligne, 'quantite', None)
        if brute is None:
            continue
        try:
            brute = Decimal(str(brute)) * n_prop
        except (InvalidOperation, TypeError, ValueError):
            continue
        quantite = _quantite_affichee(brute)
        if quantite is None:
            continue
        items.append(_ligne_composant(
            ligne.designation, quantite, getattr(ligne, 'produit', None)))
    return items


EQUIPEMENT_EN_SERVICE = 'en_service'


def _equipements_poses(chantier):
    """CHT24 — Matériel RÉELLEMENT posé sur le chantier (parc ``sav.Equipement``),
    PAS les lignes du devis (l'intention commerciale, cf. `_composants` juste
    au-dessus). ``ComponentSerial`` (F9, ``installations.models_field``)
    alimente ce parc à la validation (``pousse_parc=True``) : ``sav.Equipement``
    EST déjà la vue consolidée du matériel posé — related_name ``equipements``
    vérifié sur ``Equipement.installation`` (sav/models.py) — donc aucune
    requête distincte sur ``ComponentSerial`` n'est nécessaire ici.

    GARDE-FOU ABSOLU : whitelist champ par champ. On ne lit QUE
    ``numero_serie`` / ``produit.marque`` / ``produit.nom`` / les deux horloges
    de garantie CALCULÉES (``date_fin_garantie``, ``date_fin_garantie_production``
    — sav/models.py:321-322, jamais le texte libre ``Produit.garantie``).
    Aucun ``model_to_dict``/serializer de ``Produit`` : ``prix_achat`` (et tout
    montant d'achat) est structurellement inaccessible depuis cette fonction.
    """
    items = []
    # ADOC77 — seul le matériel EN SERVICE et non mis au rebut figure sous
    # « Équipements posés » : après un remplacement sous garantie, l'ancien
    # numéro de série (statut « remplacé ») et son ancienne garantie ne sont
    # plus remis au client. Valeur littérale de ``sav.Equipement.Statut
    # .EN_SERVICE`` (lecture par la relation inverse, aucun import de modèle).
    poses = chantier.equipements.filter(
        statut=EQUIPEMENT_EN_SERVICE, mis_au_rebut=False)
    for eq in poses.select_related('produit').order_by('id'):
        produit = eq.produit
        items.append({
            'numero_serie': (eq.numero_serie or '').strip(),
            'marque': (
                (getattr(produit, 'marque', None) or '').strip()
                if produit else ''),
            'modele': (
                (getattr(produit, 'nom', None) or '').strip()
                if produit else ''),
            'date_fin_garantie': _as_date(eq.date_fin_garantie),
            'date_fin_garantie_production': _as_date(
                eq.date_fin_garantie_production),
            # AGR622 — garantie légale de conformité (loi 31-08, pose + 12
            # mois), CALCULÉE par sav.Equipement ; None sans date de pose.
            'date_fin_garantie_legale': _as_date(
                getattr(eq, 'date_fin_garantie_legale', None)),
        })
    return items


def _recette_summary(chantier):
    """CHT24 — Résumé de recette (``installations.CommissioningRecord``) :
    résultat de conformité + relevés I-V par string, SI la fiche existe.
    Aucun montant : uniquement des mesures électriques et un libellé de
    résultat. Lecture DÉFENSIVE : ``commissioning_record`` est un accesseur
    inverse OneToOne qui lève une exception héritant d'``AttributeError``
    quand la fiche n'existe pas encore — ``getattr(..., None)`` suffit (même
    patron que ``_handover_pack_summary``)."""
    record = getattr(chantier, 'commissioning_record', None)
    if record is None:
        return None
    readings = [{
        'string_label': r.string_label,
        'voc_mesure_v': r.voc_mesure_v,
        'isc_mesure_a': r.isc_mesure_a,
        'pmax_mesure_w': r.pmax_mesure_w,
        'defaut_detecte': bool(r.defaut_detecte),
    } for r in record.iv_readings.all().order_by('id')]
    return {'resultat': record.get_resultat_display(), 'readings': readings}


def _photos_count(chantier):
    """CHT24 — Nombre de photos du chantier, via le sélecteur cross-app déjà
    existant (``installations.selectors.chantier_photos``, déjà utilisé par
    PUB63/PUB73 — import fonction-local). Best-effort : une erreur de comptage
    ne doit jamais bloquer la génération du dossier de remise."""
    try:
        from apps.installations.selectors import chantier_photos
        return chantier_photos(chantier.company, chantier.id).count()
    except Exception:
        return 0


def _checklist_summary(chantier):
    """Résumé de la checklist chantier SI elle existe — sinon None.

    Lecture DÉFENSIVE : un autre module ajoutera peut-être une checklist au
    chantier. On la lit via getattr/try sans rien casser si elle est absente.
    Convention attendue (best-effort) : un related manager (``checklist_items``
    ou ``checklist``) d'objets avec un booléen ``fait``/``done``/``coche`` et un
    libellé ``label``/``libelle``.
    """
    for attr in ('checklist_items', 'checklist', 'items_checklist'):
        manager = getattr(chantier, attr, None)
        if manager is None:
            continue
        try:
            rows = list(manager.all())
        except Exception:
            continue
        if not rows:
            continue
        items = []
        done = 0
        for row in rows:
            label = (
                getattr(row, 'label', None)
                or getattr(row, 'libelle', None)
                or str(row)
            )
            fait = bool(
                getattr(row, 'fait', None)
                if getattr(row, 'fait', None) is not None
                else getattr(row, 'done', None)
                if getattr(row, 'done', None) is not None
                else getattr(row, 'coche', False)
            )
            if fait:
                done += 1
            items.append({'label': label, 'fait': fait})
        return {'items': items, 'done': done, 'total': len(items)}
    return None


def _base_context(chantier):
    """Contexte commun : identité société + blocs chantier (sans prix)."""
    ctx = _company_context(company=chantier.company)
    ctx['chantier'] = {
        'reference': chantier.reference,
        'statut': (
            chantier.get_statut_display() if chantier.statut else None
        ),
    }
    ctx['systeme'] = _systeme_summary(chantier)
    ctx['client'] = _client_block(chantier.client)
    technicien = chantier.technicien_responsable
    ctx['technicien'] = (
        (getattr(technicien, 'get_full_name', lambda: '')() or
         getattr(technicien, 'username', ''))
        if technicien else ''
    )
    return ctx


# ── Générateurs publics ──────────────────────────────────────────────────────

def empreinte_signature(chantier):
    """AUD306 — empreinte SHA-256 (16 hex) de l'ÉTAT SIGNÉ d'un chantier.

    Elle ne dépend que des données PERSISTÉES au moment de la remise réelle
    (référence du chantier, nom du signataire, horodatage `signe_le`, trait de
    signature) — jamais de l'instant du rendu. Deux téléchargements du même PV
    signé portent donc la MÊME empreinte, et toute modification de l'état
    signé en produit une autre : c'est ce qui distingue « la version signée »
    d'une simple régénération à la volée depuis l'état LIVE du chantier.
    """
    signe_le = getattr(chantier, 'signe_le', None)
    parts = [
        str(getattr(chantier, 'reference', '') or ''),
        str(getattr(chantier, 'signataire_nom', '') or ''),
        signe_le.isoformat() if signe_le is not None else '',
        str(getattr(chantier, 'signature_client', '') or ''),
    ]
    # CIQ631 — signataire nommé, co-signature, recette et réserves C&I :
    # ajoutés SEULEMENT quand ils existent (résidentiel : empreinte
    # octet-identique quand ces champs sont vides).
    extras = [str(getattr(chantier, champ, '') or '')
              for champ in _CHAMPS_SIGNATAIRE_CI]
    if any(extras):
        parts.extend(extras)
    contenu_ci = _contenu_ci_empreinte(chantier)
    if contenu_ci:
        parts.append(contenu_ci)
    graine = '|'.join(parts)
    return hashlib.sha256(graine.encode('utf-8')).hexdigest()[:16]


#: CIQ631 — champs du signataire nommé et de la co-signature.
_CHAMPS_SIGNATAIRE_CI = (
    'signataire_fonction', 'signataire_societe', 'cosignataire_nom',
    'cosignataire_fonction', 'cosignataire_organisme',
)


def _pv_ci(chantier):
    """CIQ631 — résumé liste blanche (recette + réserves ouvertes) d'un
    chantier industriel, via le sélecteur installations ; None ailleurs."""
    from apps.installations.selectors import pv_recette_ci
    try:
        return pv_recette_ci(chantier)
    except Exception:  # pragma: no cover - défensif (PV jamais bloqué)
        logger.exception('CIQ631 — résumé recette C&I indisponible')
        return None


def _contenu_ci_empreinte(chantier):
    """CIQ631 — hachage du résultat de recette et de la liste des réserves
    d'un chantier industriel ('' ailleurs)."""
    resume = _pv_ci(chantier)
    if resume is None:
        return ''
    recette = resume['recette'] or {}
    morceaux = [str(recette.get('resultat') or ''),
                str(recette.get('date') or ''),
                str(recette.get('pr') or '')]
    morceaux.extend(f"{e['libelle']}={e['ok']}"
                    for e in recette.get('essais') or [])
    morceaux.extend(
        f"{r['description']}/{r['date_echeance']}/{r['responsable']}"
        for r in resume['reserves'])
    return hashlib.sha256(
        '|'.join(morceaux).encode('utf-8')).hexdigest()


def _signataire_ci_fragment(chantier):
    """CIQ631 — fonction et société du signataire, co-signataire
    facultatif ; '' quand tout est vide (PV résidentiel identique)."""
    fonction = (getattr(chantier, 'signataire_fonction', '') or '').strip()
    societe = (getattr(chantier, 'signataire_societe', '') or '').strip()
    co_nom = (getattr(chantier, 'cosignataire_nom', '') or '').strip()
    co_fonction = (
        getattr(chantier, 'cosignataire_fonction', '') or '').strip()
    co_org = (getattr(chantier, 'cosignataire_organisme', '') or '').strip()
    lignes = []
    if fonction or societe:
        lignes.append('Signataire : {}{}{}'.format(
            escape(getattr(chantier, 'signataire_nom', '') or '—'),
            ', ' + escape(fonction) if fonction else '',
            ' — ' + escape(societe) if societe else ''))
    if co_nom:
        lignes.append('Co-signataire : {}{}{}'.format(
            escape(co_nom),
            ', ' + escape(co_fonction) if co_fonction else '',
            ' — ' + escape(co_org) if co_org else ''))
    if not lignes:
        return ''
    return '<p class="signataires">{}</p>'.format('<br />'.join(lignes))


def _pv_ci_fragment(chantier):
    """CIQ631 — PV d'un chantier industriel : résumé de recette (date,
    résultat, PR « à titre d'information », essais) et réserves ouvertes
    avec échéance et responsable. '' hors chantier industriel. Jamais de
    prix ni ``prix_achat`` (liste blanche du sélecteur)."""
    resume = _pv_ci(chantier)
    if resume is None:
        return ''
    html = '<div class="section-title">Recette de mise en service</div>'
    recette = resume['recette']
    if recette is None:
        html += '<p>Aucune fiche de recette.</p>'
    else:
        lignes = [
            ("Date de l'essai", (recette['date'].strftime('%d/%m/%Y')
                                 if recette['date'] else '—')),
            ('Résultat', recette['resultat']),
            ('PR mesuré ({})'.format(recette['pr_libelle']),
             _fr_mesure(recette['pr'])),
        ]
        lignes.extend((e['libelle'], _oui_non(e['ok']))
                      for e in recette['essais'])
        html += '<table><tbody>{}</tbody></table>'.format(''.join(
            '<tr><td>{}</td><td>{}</td></tr>'.format(
                escape(libelle), escape(valeur))
            for libelle, valeur in lignes))
    html += '<div class="section-title">Réserves ouvertes</div>'
    if not resume['reserves']:
        html += '<p>Aucune réserve ouverte.</p>'
    else:
        html += ('<table><thead><tr><th>Réserve</th><th>Échéance</th>'
                 '<th>Responsable</th></tr></thead><tbody>{}</tbody>'
                 '</table>').format(''.join(
                     '<tr><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
                         escape(r['description'] or '—'),
                         (r['date_echeance'].strftime('%d/%m/%Y')
                          if r['date_echeance'] else '—'),
                         escape(r['responsable'] or '—'))
                     for r in resume['reserves']))
    return html


def generate_pv_reception(chantier, fige_le=None, definitive=False):
    """N21 — Procès-verbal de réception des travaux.

    AUD306 — le PV réutilise désormais le patron de `generate_bon_livraison`
    (NTMOB16) : le trait de signature client capturé par l'action
    `signer-client` est injecté QUAND IL EXISTE, accompagné de l'horodatage
    PERSISTÉ `signe_le` et d'une empreinte de l'état signé. Auparavant le
    gabarit n'affichait qu'une mention manuscrite statique : l'ERP ne pouvait
    ni montrer si/quand le PV avait été signé, ni distinguer deux
    téléchargements faits à des moments différents (le document est régénéré
    à la volée depuis l'état LIVE du chantier). Un chantier NON signé garde
    un contexte strictement identique à avant cette tâche.
    """
    ctx = _base_context(chantier)
    ctx['composants'] = _composants(chantier)
    ctx['checklist'] = _checklist_summary(chantier)
    # CIQ631 — PV de réception DÉFINITIVE : même gabarit, son titre.
    if definitive:
        ctx['doc_titre'] = 'PROCÈS-VERBAL DE RÉCEPTION DÉFINITIVE'
    if chantier.signature_client:
        ctx['signature_client'] = chantier.signature_client
        ctx['signataire_nom'] = chantier.signataire_nom or None
        ctx['signe_le'] = chantier.signe_le
        ctx['empreinte_signature'] = empreinte_signature(chantier)
        # ADOC70 — gel tardif (chantier signé avant le gel en GED) : la mention
        # « figé le …, après la signature du … » remplace l'empreinte.
        if fige_le is not None:
            ctx['fige_le'] = fige_le
    html = get_template('document_pv_reception.html').render(ctx)
    # AGR611 — chantier agricole : mesures de la recette pompage + formalité
    # art. 3 (fragment vide ailleurs : PV strictement inchangé).
    html = _inject_before(html, '<div class="signature-section">',
                          _recette_pompage_fragment(chantier))
    # CIQ631 — chantier industriel : recette + réserves ouvertes ; signataire
    # nommé et co-signataire (fragments vides ailleurs : PV identique).
    fragment = _pv_ci_fragment(chantier) + _signataire_ci_fragment(chantier)
    if definitive:
        date_def = getattr(chantier, 'date_reception_definitive', None)
        fragment = '<p>Réception définitive prononcée le {}.</p>'.format(
            date_def.strftime('%d/%m/%Y') if date_def else '—') + fragment
    html = _inject_before(html, '<div class="signature-section">', fragment)
    return _html_to_pdf(html)


def generate_bon_livraison(chantier):
    """N22 — Bon de livraison.

    XSTK18 — rendu bilingue FR/AR (RTL) selon `chantier.client.langue_document`.
    Mêmes données, mêmes identifiants légaux, numérotation inchangée. Le
    rendu FR par défaut passe par le gabarit HISTORIQUE, intégralement
    inchangé (`document_bon_livraison.html`) → byte-identique. Un client
    `langue_document='ar'` passe par le NOUVEAU gabarit dédié
    (`document_bon_livraison_ar.html`, RTL + police Noto Sans Arabic
    embarquée) — jamais de traduction automatique, libellés fixes traduits.
    """
    ctx = _base_context(chantier)
    ctx['composants'] = _composants(chantier)
    ctx['date_livraison'] = (
        _as_date(chantier.date_pose_reelle)
        or _as_date(chantier.date_mise_en_service)
    )
    # NTMOB16 — trait de signature client (data-URL PNG, SignaturePad.jsx),
    # capturé via l'action `signer-client`. N'ajoute les clés QUE si une
    # signature existe réellement : un chantier sans signature garde un
    # contexte STRICTEMENT identique à avant cette tâche (byte-identique,
    # XSTK18 test_fr_client_renders_existing_template_byte_identical).
    if chantier.signature_client:
        ctx['signature_client'] = chantier.signature_client
        ctx['signataire_nom'] = chantier.signataire_nom or None
    # NTI18N4 — `company=` ajoute le repli société (NTI18N34) à la chaîne de
    # résolution ; sans effet tant que ce champ n'existe pas.
    langue = document_langue(chantier.client, company=chantier.company)
    if langue == 'ar':
        ctx['L'] = lambda cle: _bl_libelle(cle, langue)
        ctx['arabic_font_face_css'] = arabic_font_face_css()
        template_name = 'document_bon_livraison_ar.html'
    else:
        template_name = 'document_bon_livraison.html'
    html = get_template(template_name).render(ctx)
    return _html_to_pdf(html)


def _handover_pack_summary(chantier):
    """AUD307 — pièces du pack de remise CH4 (`installations.HandoverPack`).

    Même patron défensif que `_checklist_summary` : ``None`` quand le chantier
    n'a pas encore de pack persisté (l'accesseur inverse OneToOne lève une
    exception qui hérite d'``AttributeError``, donc ``getattr(..., None)``
    suffit), et chaque pièce dégrade proprement — une entrée malformée est
    ignorée plutôt que de casser la génération du document client.
    """
    pack = getattr(chantier, 'handover_pack', None)
    if pack is None:
        return None
    pieces = []
    for piece in (pack.pieces or []):
        if not isinstance(piece, dict):
            continue
        pieces.append({
            'libelle': (
                piece.get('libelle') or piece.get('type') or '—'),
            'reference': piece.get('reference') or '',
            'present': bool(piece.get('present')),
        })
    return {
        'pieces': pieces,
        'complet': bool(pack.complet),
        'presentes': sum(1 for p in pieces if p['present']),
        'total': len(pieces),
        'monitoring_acces': pack.monitoring_acces or '',
    }


def _equipements_poses_fragment(chantier):
    """CHT24 — Fragment HTML « Équipements posés » (échappé champ par champ
    via ``django.utils.html.escape``), injecté dans le PDF « dossier de
    remise » à l'appui du parc RÉELLEMENT posé (au lieu des lignes du devis
    déjà couvertes par `_composants`). Chaîne vide (donc AUCUN changement du
    document) si le chantier n'a aucun équipement posé — même garantie de
    non-régression que `_handover_pack_summary`/`pack_remise` juste au-dessus.

    GARDE-FOU ABSOLU : construit exclusivement depuis les dicts déjà
    whitelistés de `_equipements_poses`/`_recette_summary` — jamais un accès
    direct à `Produit` ici, donc `prix_achat` ne peut structurellement pas
    apparaître dans ce fragment.
    """
    equipements = _equipements_poses(chantier)
    if not equipements:
        return ''
    rows = []
    for eq in equipements:
        garantie_bits = []
        if eq['date_fin_garantie']:
            garantie_bits.append(
                'Matériel : ' + eq['date_fin_garantie'].strftime('%d/%m/%Y'))
        elif eq.get('date_fin_garantie_legale'):
            # AGR622 — sans garantie constructeur, dire que la garantie
            # légale court (au lieu d'un « — » muet). Une seule source :
            # Produit.garantie_mois via les horloges sav.Equipement.
            garantie_bits.append(
                'Garantie constructeur : non renseignée — garantie légale de '
                'conformité 12 mois (loi 31-08) jusqu\'au '
                + eq['date_fin_garantie_legale'].strftime('%d/%m/%Y'))
        if eq['date_fin_garantie_production']:
            garantie_bits.append(
                'Production : ' +
                eq['date_fin_garantie_production'].strftime('%d/%m/%Y'))
        rows.append(
            '<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
                escape(eq['numero_serie'] or '—'),
                escape(eq['marque'] or '—'),
                escape(eq['modele'] or '—'),
                escape(' — '.join(garantie_bits) or '—'),
            ))
    html = (
        '<div class="section-title">Équipements posés</div>'
        '<table><thead><tr>'
        '<th>N° de série</th><th>Marque</th><th>Modèle</th>'
        '<th>Garantie</th>'
        '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table>'
    )
    recette = _recette_summary(chantier)
    if recette is not None:
        html += (
            '<div class="section-title">Recette de mise en service</div>'
            '<p>Résultat : {}</p>'.format(escape(recette['resultat'] or '—'))
        )
        iv_rows = ''.join(
            '<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'
            .format(
                escape(r['string_label'] or '—'),
                r['voc_mesure_v'] if r['voc_mesure_v'] is not None else '—',
                r['isc_mesure_a'] if r['isc_mesure_a'] is not None else '—',
                r['pmax_mesure_w'] if r['pmax_mesure_w'] is not None else '—',
                'Oui' if r['defaut_detecte'] else 'Non',
            ) for r in recette['readings']
        )
        if iv_rows:
            html += (
                '<table><thead><tr>'
                '<th>String</th><th>Voc (V)</th><th>Isc (A)</th>'
                '<th>Pmax (W)</th><th>Défaut détecté</th>'
                '</tr></thead><tbody>' + iv_rows + '</tbody></table>'
            )
    html += '<p>Photos du chantier au dossier : {}.</p>'.format(
        _photos_count(chantier))
    return html


# ── AGR611 — recette POMPAGE dans le PV de réception et le dossier de remise ─

#: Le cadre des essais (contrat ``recette_pompage.json``).
CADRE_ESSAIS_POMPAGE = 'Cadre des essais : IEC 62253:2011'

#: La formalité d'une installation NON raccordée (loi 82-21, art. 3). Ni
#: guichet, ni pièces, ni délai (non sourcés) ; aucune promesse de dépôt.
FORMALITE_HORS_RESEAU = (
    "Loi 82-21, art. 3 : une installation non raccordée au réseau est "
    "soumise à déclaration auprès de l'administration ; modalités fixées "
    "par voie réglementaire.")


def _est_chantier_pompage(chantier):
    return (getattr(chantier, 'type_installation', None) or '') == 'agricole'


def _recette_pompage_summary(chantier):
    """AGR611 — résumé de la RECETTE POMPAGE (``installations.RecettePompage``,
    cadre IEC 62253:2011) d'un chantier agricole, en LISTE BLANCHE : des
    mesures, la promesse figée du devis et l'écart — jamais un prix ni
    ``prix_achat``. ``None`` hors agricole ou sans fiche (accesseur inverse
    OneToOne lu défensivement, patron de ``_recette_summary``). La
    comparaison vient du SERVICE ``installations.services.
    comparer_recette_pompage`` (une seule formule). Une recette non conforme
    est résumée TELLE QUELLE."""
    if not _est_chantier_pompage(chantier):
        return None
    recette = getattr(chantier, 'recette_pompage', None)
    if recette is None:
        return None
    from apps.installations.services import comparer_recette_pompage
    comparaison = comparer_recette_pompage(recette)
    return {
        'date_essai': _as_date(recette.date_essai),
        'niveau_statique_m': recette.niveau_statique_m,
        'niveau_dynamique_m': recette.niveau_dynamique_m,
        'hmt_mesuree_m': recette.hmt_mesuree_m,
        'debit_mesure_m3h': recette.debit_mesure_m3h,
        'debit_promis_m3h': comparaison['promesse'].get('debit_hmt_m3h'),
        'ecart_debit_pct': comparaison['ecart_debit_pct'],
        'commentaire_ecart': recette.commentaire_ecart or '',
        'courant_plaque_a': recette.courant_plaque_a,
        'courants_phases_a': [recette.courant_phase_1_a,
                              recette.courant_phase_2_a,
                              recette.courant_phase_3_a],
        'frequence_variateur_hz': recette.frequence_variateur_hz,
        'irradiance_wm2': recette.irradiance_wm2,
        'source_irradiance': (recette.get_source_irradiance_display()
                              if recette.source_irradiance else ''),
        'isolement_moteur_mohm': recette.isolement_moteur_mohm,
        'isolement_ok': recette.isolement_ok,
        'sens_rotation_ok': recette.sens_rotation_ok,
        'test_marche_a_sec_ok': recette.test_marche_a_sec_ok,
        'resultat': recette.get_resultat_display(),
    }


def _client_forme(chantier):
    """AGR611 — l'étape de checklist ``client_forme`` est-elle COCHÉE ?"""
    try:
        return chantier.checklist.filter(cle='client_forme',
                                         fait=True).exists()
    except Exception:
        return False


def _fr_mesure(valeur):
    if valeur is None:
        return '—'
    if isinstance(valeur, float):
        texte = ('%.2f' % valeur).rstrip('0').rstrip('.')
    else:
        texte = str(valeur)
    return texte.replace('.', ',')


def _oui_non(valeur):
    if valeur is None:
        return '—'
    return 'Oui' if valeur else 'Non'


def _recette_pompage_fragment(chantier):
    """AGR611 — fragment HTML (échappé champ par champ) des MESURES de la
    recette pompage + bloc « Formalités » (loi 82-21, art. 3), injecté À
    L'IDENTIQUE dans le PV de réception et le dossier de remise (jumeaux du
    même geste). Chaîne vide hors chantier agricole : PV et dossier
    résidentiels/C&I restent OCTET-IDENTIQUES. Construit exclusivement depuis
    :func:`_recette_pompage_summary` (liste blanche) : ``prix_achat`` ne peut
    structurellement pas y apparaître."""
    if not _est_chantier_pompage(chantier):
        return ''
    html = ''
    recette = _recette_pompage_summary(chantier)
    if recette is not None:
        phases = ' / '.join(_fr_mesure(c) for c in recette['courants_phases_a'])
        irradiance = _fr_mesure(recette['irradiance_wm2'])
        if recette['irradiance_wm2'] is not None and recette['source_irradiance']:
            irradiance += ' ({})'.format(recette['source_irradiance'].lower())
        lignes = [
            ("Date de l'essai", (recette['date_essai'].strftime('%d/%m/%Y')
                                 if recette['date_essai'] else '—')),
            ('Niveau statique (m)', _fr_mesure(recette['niveau_statique_m'])),
            ('Niveau dynamique (m)',
             _fr_mesure(recette['niveau_dynamique_m'])),
            ('HMT mesurée (m)', _fr_mesure(recette['hmt_mesuree_m'])),
            ('Débit mesuré (m³/h)', _fr_mesure(recette['debit_mesure_m3h'])),
            ('Débit promis au devis (m³/h)',
             _fr_mesure(recette['debit_promis_m3h'])),
            ('Écart de débit (%)', _fr_mesure(recette['ecart_debit_pct'])),
            ("Commentaire d'écart", recette['commentaire_ecart'] or '—'),
            ('Courant par phase (A) / plaque (A)',
             '{} / plaque {}'.format(
                 phases, _fr_mesure(recette['courant_plaque_a']))),
            ('Fréquence du variateur (Hz)',
             _fr_mesure(recette['frequence_variateur_hz'])),
            ('Irradiance (W/m²)', irradiance),
            ('Isolement moteur (MΩ)', '{} — conforme : {}'.format(
                _fr_mesure(recette['isolement_moteur_mohm']),
                _oui_non(recette['isolement_ok']))),
            ('Sens de rotation correct', _oui_non(recette['sens_rotation_ok'])),
            ('Test de marche à sec', _oui_non(recette['test_marche_a_sec_ok'])),
            ('Résultat', recette['resultat']),
        ]
        html += (
            '<div class="section-title">Recette pompage — mesures</div>'
            '<p>{}</p><table><tbody>{}</tbody></table>'.format(
                escape(CADRE_ESSAIS_POMPAGE),
                ''.join('<tr><td>{}</td><td>{}</td></tr>'.format(
                    escape(libelle), escape(valeur))
                    for libelle, valeur in lignes)))
    if _client_forme(chantier):
        html += '<p>Formation du client : faite</p>'
    html += ('<div class="section-title">Formalités</div>'
             '<p>{}</p>'.format(escape(FORMALITE_HORS_RESEAU)))
    return html


def _inject_before(html, marker, fragment):
    """CHT24 — Insère `fragment` juste avant la première occurrence de
    `marker` dans le HTML déjà rendu par le gabarit Jinja. `fragment` vide =
    no-op strict (document byte-identique). Si `marker` venait à disparaître
    (gabarit modifié ailleurs), l'ajout se fait avant la fermeture du
    document plutôt que d'être silencieusement perdu."""
    if not fragment:
        return html
    idx = html.find(marker)
    if idx == -1:
        idx = html.rfind('</body>')
        if idx == -1:
            return html + fragment
    return html[:idx] + fragment + html[idx:]


def generate_dossier_remise(chantier):
    """N23 — Dossier de remise (handover pack).

    AUD307 — le PDF LIT désormais le `HandoverPack` (CH4) qui gate la remise.
    Avant, il se construisait uniquement depuis `_composants` + un texte
    statique : une équipe pouvait confirmer `pack_remise.complet=True` puis
    remettre au client un PDF ne contenant AUCUNE des pièces validées par CH4
    (ni certificat de recette IEC 62446-1, ni dossier 82-21, ni accès
    monitoring). Un chantier SANS pack persisté garde un contexte
    strictement identique à avant cette tâche.

    CHT24 — le PDF ajoute désormais le matériel RÉELLEMENT posé (parc
    ``sav.Equipement``, PAS les lignes du devis) : n° de série, marque,
    modèle, garanties calculées, résumé de recette (`CommissioningRecord`) et
    compte de photos — injecté en HTML déjà échappé (`_equipements_poses_fragment`)
    plutôt que via le contexte du gabarit. Un chantier SANS équipement posé
    garde un document strictement identique à avant cette tâche.
    """
    ctx = _base_context(chantier)
    ctx['composants'] = _composants(chantier)
    ctx['guidance'] = DEFAULT_OPERATING_GUIDANCE
    pack = _handover_pack_summary(chantier)
    if pack is not None:
        ctx['pack_remise'] = pack
    html = get_template('document_dossier_remise.html').render(ctx)
    html = _inject_before(
        html, '<div class="footer">', _equipements_poses_fragment(chantier))
    # AGR611 — le MÊME fragment que le PV de réception (jumeaux du geste).
    html = _inject_before(
        html, '<div class="footer">', _recette_pompage_fragment(chantier))
    return _html_to_pdf(html)


# Types d'attestation supportés (clé → libellé + corps français).
ATTESTATION_TYPES = {
    'installation': {
        'titre': "Attestation d'installation",
        'corps': (
            "Nous, soussignés {entreprise_nom}, attestons par la présente "
            "avoir réalisé l'installation d'un système photovoltaïque "
            "{puissance} chez le client {client_nom}, sis {site}."
        ),
    },
    'fin_travaux': {
        'titre': "Attestation de fin de travaux",
        'corps': (
            "Nous, soussignés {entreprise_nom}, attestons par la présente que "
            "les travaux d'installation du système photovoltaïque {puissance} "
            "réalisés chez le client {client_nom}, sis {site}, sont achevés et "
            "conformes."
        ),
    },
}


def generate_attestation(chantier, attestation_type, date_emission=None):
    """N24 — Attestation (type configurable).

    ADOC70 — « Fait … le » = ``date_emission`` (date de la PREMIÈRE émission,
    figée en GED par :func:`attestation_pour_client`), jamais l'instant du
    téléchargement."""
    cfg = ATTESTATION_TYPES.get(attestation_type)
    if cfg is None:
        raise ValueError(f"Type d'attestation inconnu : {attestation_type}")
    ctx = _base_context(chantier)

    puissance = (
        f"de {chantier.puissance_installee_kwc} kWc"
        if chantier.puissance_installee_kwc is not None else ""
    )
    client = chantier.client
    client_nom = (
        f"{client.nom} {getattr(client, 'prenom', '') or ''}".strip()
        if client else ""
    )
    site = ", ".join(
        p for p in (chantier.site_adresse, chantier.site_ville) if p
    ) or (getattr(client, 'adresse', '') or "")

    corps = cfg['corps'].format(
        entreprise_nom=ctx['entreprise_nom'],
        puissance=puissance,
        client_nom=client_nom,
        site=site,
    )
    ctx['attestation'] = {'titre': cfg['titre'], 'corps': corps}
    ctx['date_emission'] = date_emission or _aujourdhui()
    html = get_template('document_attestation.html').render(ctx)
    return _html_to_pdf(html)


# ── ADOC70 — documents signés / émis FIGÉS en GED (D-ADOC-2) ─────────────────
#
# Un PV de réception ou un bon de livraison SIGNÉ est figé en GED : il est
# ensuite servi TEL QUEL (octets de la version en vigueur), même si le chantier
# est modifié après coup — plus jamais « Signé le … — empreinte » imprimé sur un
# contenu changé depuis. Une re-signature motivée (AUD305, nouvelle empreinte)
# crée une NOUVELLE VERSION du même Document GED, l'ancienne reste en
# historique. L'attestation est figée à sa première émission (datée de cette
# émission) ; ``regenerer`` en crée une nouvelle version datée du jour.
#
# Dépôt : ``ged.services.deposit_document(versionner_si_modifie=True)``
# (ADOC61) en import fonction-local — cabinet « Chantiers », dossier = la
# référence du chantier, source_id = chantier.pk.

SOURCE_PV_RECEPTION = 'documents.pv_reception'
SOURCE_BON_LIVRAISON = 'documents.bon_livraison'
SOURCE_ATTESTATION = 'documents.attestation'
GED_CABINET_CHANTIERS = 'Chantiers'
# Au-delà de ce délai entre la signature et le gel, le PV ne peut plus
# affirmer l'empreinte du contenu signé : il dit quand il a été figé.
GEL_TARDIF_SEUIL = timedelta(hours=1)
EMPREINTE_KEY = 'empreinte_signature'


def _aujourdhui():
    """ADOC70 — date du jour (fuseau du projet). Point unique, pour que la
    date d'émission d'une attestation soit testable sans figer l'horloge du
    stockage objet (MinIO refuse une requête signée à une date décalée)."""
    return timezone.localdate()


def _source_attestation(attestation_type):
    """Source GED d'une attestation : une par type (installation /
    fin_travaux) — sinon les deux types d'un même chantier (même source_id)
    se versionneraient l'un sur l'autre."""
    return f'{SOURCE_ATTESTATION}.{attestation_type}'


def _document_ged(chantier, source_type):
    """Document GED déjà déposé pour ce document de chantier, hors corbeille
    (un document en corbeille n'est jamais servi), ou None."""
    from apps.ged import services as ged_services
    document = ged_services.find_document_by_source(
        chantier.company, source_type=source_type, source_id=chantier.pk)
    if document is None or getattr(document, 'supprime_le', None):
        return None
    return document


def _octets_en_vigueur(document):
    """Octets de la version en vigueur (la plus haute) d'un Document GED, ou
    None si le contenu n'est pas récupérable (l'appelant re-rend alors le
    document et le re-dépose)."""
    version = document.versions.order_by('-version').first()
    if version is None or not version.file_key:
        return None
    from apps.records.storage import fetch_attachment
    data, err = fetch_attachment(version.file_key)
    if err or not data:
        return None
    return data


def _deposer_fige(chantier, *, source_type, nom, pdf, meta):
    """Dépose ``pdf`` en GED (version 1, ou NOUVELLE VERSION du même Document
    si le contenu diffère — ADOC61) et trace ``meta`` dans ``custom_data``.
    Best-effort : une panne de stockage ne bloque jamais la remise du document
    au client (journalisée)."""
    from apps.ged import services as ged_services
    try:
        document, _created = ged_services.deposit_document(
            company=chantier.company, nom=nom, source_type=source_type,
            source_id=chantier.pk, contenu_bytes=pdf,
            mime='application/pdf', filename=f'{nom}.pdf',
            cabinet_nom=GED_CABINET_CHANTIERS,
            folder_nom=chantier.reference or f'Chantier {chantier.pk}',
            description='Document de chantier figé (ADOC70).',
            versionner_si_modifie=True)
        document.custom_data = {**(document.custom_data or {}), **meta}
        document.save(update_fields=['custom_data'])
        return document
    except Exception:
        logger.exception(
            'ADOC70 — gel GED impossible (%s, chantier %s)',
            source_type, chantier.pk)
        return None


def _servir_signe(chantier, *, source_type, nom, render, maintenant=None):
    """PV / BL d'un chantier SIGNÉ : la version GED figée si elle correspond à
    l'empreinte de signature courante ; sinon (jamais figé, ou re-signé) rendu
    puis gel (nouvelle version du même Document)."""
    empreinte = empreinte_signature(chantier)
    document = _document_ged(chantier, source_type)
    if document is not None and (
            (document.custom_data or {}).get(EMPREINTE_KEY) == empreinte):
        data = _octets_en_vigueur(document)
        if data:
            return data
    maintenant = maintenant or timezone.now()
    signe_le = getattr(chantier, 'signe_le', None)
    tardif = bool(signe_le and maintenant - signe_le > GEL_TARDIF_SEUIL)
    pdf = render(chantier, maintenant if tardif else None)
    _deposer_fige(
        chantier, source_type=source_type, nom=nom, pdf=pdf,
        meta={EMPREINTE_KEY: empreinte, 'fige_le': maintenant.isoformat(),
              'gel_tardif': tardif})
    return pdf


def _servir_pv(chantier, maintenant=None):
    return _servir_signe(
        chantier, source_type=SOURCE_PV_RECEPTION,
        nom=f'PV de réception {chantier.reference}',
        render=lambda c, fige_le: generate_pv_reception(c, fige_le=fige_le),
        maintenant=maintenant)


def _servir_bl(chantier, maintenant=None):
    return _servir_signe(
        chantier, source_type=SOURCE_BON_LIVRAISON,
        nom=f'Bon de livraison {chantier.reference}',
        render=lambda c, _fige_le: generate_bon_livraison(c),
        maintenant=maintenant)


def pv_reception_pour_client(chantier):
    """PV de réception servi : figé en GED dès que le chantier est signé."""
    if not chantier.signature_client:
        return generate_pv_reception(chantier)
    return _servir_pv(chantier)


def bon_livraison_pour_client(chantier):
    """Bon de livraison servi : figé en GED dès que le chantier est signé."""
    if not chantier.signature_client:
        return generate_bon_livraison(chantier)
    return _servir_bl(chantier)


def figer_documents_signes(chantier, maintenant=None):
    """ADOC70 — fige en GED le PV de réception et le bon de livraison d'un
    chantier signé (à appeler au geste de signature — ADOC71 — ; sinon le
    premier téléchargement fige). Idempotent : une empreinte déjà figée
    n'ajoute rien. Renvoie ``{'pv_reception': bytes, 'bon_livraison': bytes}``
    ({} si le chantier n'est pas signé)."""
    if not getattr(chantier, 'signature_client', None):
        return {}
    return {
        'pv_reception': _servir_pv(chantier, maintenant=maintenant),
        'bon_livraison': _servir_bl(chantier, maintenant=maintenant),
    }


def attestation_pour_client(chantier, attestation_type, regenerer=False):
    """ADOC70 — attestation figée à sa PREMIÈRE émission (datée de cette
    émission) puis servie telle quelle ; ``regenerer=True`` (réservé aux
    responsables par la vue) crée une nouvelle version datée du jour."""
    if attestation_type not in ATTESTATION_TYPES:
        raise ValueError(f"Type d'attestation inconnu : {attestation_type}")
    source_type = _source_attestation(attestation_type)
    if not regenerer:
        document = _document_ged(chantier, source_type)
        if document is not None:
            data = _octets_en_vigueur(document)
            if data:
                return data
    date_emission = _aujourdhui()
    pdf = generate_attestation(
        chantier, attestation_type, date_emission=date_emission)
    titre = ATTESTATION_TYPES[attestation_type]['titre']
    _deposer_fige(
        chantier, source_type=source_type,
        nom=f'{titre} {chantier.reference}', pdf=pdf,
        meta={'type': attestation_type,
              'date_emission': date_emission.isoformat()})
    return pdf
