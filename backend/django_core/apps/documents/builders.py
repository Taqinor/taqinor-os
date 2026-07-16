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
from datetime import date, datetime

from django.template.loader import get_template

from apps.ventes.utils.pdf import _company_context
# XSTK18 — réutilise (lecture seule, aucune écriture) les utilitaires AR déjà
# vendored pour la facture legacy (XSAL13, `apps/ventes/utils/libelles_ar.py`) :
# même police Noto Sans Arabic embarquée, même résolution de langue depuis
# `Client.langue_document`. Import identique dans l'esprit à `_company_context`
# ci-dessus (déjà cross-app) — jamais un import de `apps.ventes.models`/`views`.
from apps.ventes.utils.libelles_ar import arabic_font_face_css, document_langue
from core.pdf import render_pdf

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


def _composants(chantier):
    """Composants installés depuis les lignes du devis d'origine.

    On ne renvoie QUE désignation + quantité + garantie texte. Le prix d'achat
    n'est jamais lu : impossible de le faire fuiter dans un document client.
    """
    devis = getattr(chantier, 'devis', None)
    if devis is None:
        return []
    items = []
    for ligne in devis.lignes.select_related('produit').all():
        produit = ligne.produit
        garantie = (getattr(produit, 'garantie', None) or '').strip() \
            if produit else ''
        marque = (getattr(produit, 'marque', None) or '').strip() \
            if produit else ''
        items.append({
            'designation': ligne.designation,
            'quantite': ligne.quantite,
            'marque': marque,
            'garantie': garantie or DEFAULT_GARANTIE,
        })
    return items


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

def generate_pv_reception(chantier):
    """N21 — Procès-verbal de réception des travaux."""
    ctx = _base_context(chantier)
    ctx['composants'] = _composants(chantier)
    ctx['checklist'] = _checklist_summary(chantier)
    html = get_template('document_pv_reception.html').render(ctx)
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
    langue = document_langue(chantier.client)
    if langue == 'ar':
        ctx['L'] = lambda cle: _bl_libelle(cle, langue)
        ctx['arabic_font_face_css'] = arabic_font_face_css()
        template_name = 'document_bon_livraison_ar.html'
    else:
        template_name = 'document_bon_livraison.html'
    html = get_template(template_name).render(ctx)
    return _html_to_pdf(html)


def generate_dossier_remise(chantier):
    """N23 — Dossier de remise (handover pack)."""
    ctx = _base_context(chantier)
    ctx['composants'] = _composants(chantier)
    ctx['guidance'] = DEFAULT_OPERATING_GUIDANCE
    html = get_template('document_dossier_remise.html').render(ctx)
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


def generate_attestation(chantier, attestation_type):
    """N24 — Attestation (type configurable)."""
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
    html = get_template('document_attestation.html').render(ctx)
    return _html_to_pdf(html)
