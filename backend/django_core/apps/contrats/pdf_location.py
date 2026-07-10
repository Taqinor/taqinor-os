"""Bons d'enlèvement et de restitution de location (PDF) — ZCTR5.

Odoo imprime un « Pickup & Return receipt » détaillant les articles loués et
leur statut. XCTR17-20 gèrent le cycle complet (réservation → enlèvement →
retour → clôture) mais ne produisaient AUCUN document signable de
sortie/retour — utile en cas de litige (preuve de remise).

Rendu par le WeasyPrint GÉNÉRIQUE existant (Jinja2 + ``weasyprint``, même
patron que ``contrats.services.rendre_contrat_pdf``) — JAMAIS le moteur devis
premium ``/proposal`` (réservé aux devis, rule #4). Rendu à la volée, non
stocké, aucun changement de statut. ``stock.Produit.prix_achat`` n'est
JAMAIS lu ni rendu ici (uniquement le nom du produit).

Cross-app : le nom du client est lu via ``apps.crm.selectors.client_label``
(lecture seule, jamais un import de ``crm.models``) ; la fiche société via
``apps.parametres.models_company.CompanyProfile`` (app foundation, exempte de
la frontière cross-app — CLAUDE.md).

ARC12 — la plomberie WeasyPrint (import paresseux + ``write_pdf()``) est
déléguée au service partagé ``core.pdf.render_pdf`` ; les gabarits Django
restent STRICTEMENT identiques, donc le rendu est inchangé à l'octet près.
"""
from django.template.loader import get_template

from core.pdf import render_pdf


def _company_context(company):
    """Coordonnées société pour l'en-tête du PDF — patron minimal (pas de
    logo/signature embarqués, contrairement à ``ventes.utils.pdf`` : un bon
    de location n'a pas besoin de branding riche)."""
    from apps.parametres.models_company import CompanyProfile

    profile = CompanyProfile.get(company=company)
    return {
        'entreprise_nom': profile.nom or company.nom,
        'entreprise_adresse': getattr(profile, 'adresse', '') or '',
        'entreprise_telephone': getattr(profile, 'telephone', '') or '',
        'entreprise_email': getattr(profile, 'email', '') or '',
    }


def _client_nom(ordre):
    """Nom du client locataire, lu via le sélecteur cross-app CRM (lien
    LÂCHE ``client_id`` — jamais un import de ``crm.models``)."""
    from apps.crm.selectors import client_label

    return client_label(ordre.company, ordre.client_id) or (
        f'Client #{ordre.client_id}')


def _html_to_pdf(html_string):
    return render_pdf(html=html_string)


def _base_context(ordre):
    context = _company_context(ordre.company)
    context['ordre'] = ordre
    context['client_nom'] = _client_nom(ordre)
    context['produit_nom'] = ordre.produit.nom
    context['numero_serie'] = ordre.numero_serie or '—'
    return context


def generate_bon_enlevement_pdf(ordre):
    """PDF « bon d'enlèvement » d'un ``OrdreLocation`` — ZCTR5.

    Client, produit + n° de série, dates de réservation/enlèvement/retour
    prévu, caution (XCTR18), zone de signature (loi 53-05, nom saisi — pas
    de signature électronique). Aucun statut modifié par le rendu."""
    context = _base_context(ordre)
    html = get_template('bon_enlevement_location.html').render(context)
    return _html_to_pdf(html)


def generate_bon_restitution_pdf(ordre):
    """PDF « bon de restitution » d'un ``OrdreLocation`` — ZCTR5.

    Reprend, en plus des informations du bon d'enlèvement : la date de
    retour réelle, la checklist d'inspection (XCTR19, JSON libre) + relevé
    compteur, et les dommages chiffrés le cas échéant. ``prix_achat`` n'est
    jamais rendu (seul le nom du produit l'est). Aucun statut modifié."""
    context = _base_context(ordre)
    checklist = ordre.inspection_checklist or {}
    context['inspection_items'] = sorted(checklist.items()) \
        if isinstance(checklist, dict) else []
    html = get_template('bon_restitution_location.html').render(context)
    return _html_to_pdf(html)
