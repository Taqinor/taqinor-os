"""F19 — Compte-rendu d'intervention PDF (client-facing).

Rendu à la volée via le MÊME pipeline que les factures/SAV
(apps.ventes.utils.pdf : identité société + template Jinja2 + WeasyPrint).
Non stocké : généré et streamé à la demande.

CÔTÉ CLIENT : AUCUN prix d'achat, AUCUNE marge — jamais. Le matériel
réellement consommé n'affiche que désignation + quantités (prévu/utilisé) et la
justification d'écart ; jamais un prix interne. Complète le PV de réception.
"""
from apps.ventes.utils.pdf import _company_context, _html_to_pdf, _render_html


def _equipe_payload(intervention):
    return [u.username for u in intervention.equipe.all()]


def _photos_payload(intervention):
    """Photos groupées avant/pendant/après (URL de proxy Django, jamais l'objet
    MinIO directement)."""
    from . import field_services
    groups = {'avant': [], 'pendant': [], 'apres': []}
    by_slot = field_services.photos_by_slot(intervention)
    for slot in field_services.active_shotlist(intervention.company):
        for att in by_slot.get(slot.cle, []):
            groups.setdefault(slot.phase, []).append({
                'libelle': slot.libelle,
                'url': f'/api/django/records/attachments/{att.id}/download/',
            })
    return groups


def _serials_payload(intervention):
    return [
        {
            'designation': (s.designation
                            or (s.produit.nom if s.produit_id else '—')),
            'numero_serie': s.numero_serie or '—',
        }
        for s in intervention.serials.all()
    ]


def _consommation_payload(intervention):
    """Matériel réellement consommé — désignation + quantités + justification.
    JAMAIS de prix d'achat ni de marge."""
    cons = getattr(intervention, 'consommation', None)
    if cons is None:
        return []
    return [
        {
            'designation': li.designation,
            'quantite_prevue': li.quantite_prevue,
            'quantite_utilisee': li.quantite_utilisee,
            'variance': li.variance,
            'justification': li.justification,
            'hors_nomenclature': li.hors_nomenclature,
        }
        for li in cons.lignes.all()
    ]


def _reserves_payload(intervention):
    return [
        {
            'description': r.description,
            'statut': r.get_statut_display(),
            'assignee': getattr(r.assignee, 'username', None),
            'resolution': r.resolution,
        }
        for r in intervention.reserves.all()
    ]


def compte_rendu_pdf(intervention):
    """Génère le compte-rendu d'intervention (PDF, octets). Client-facing."""
    inst = intervention.installation
    client = getattr(inst, 'client', None)
    context = _company_context(company=intervention.company)
    context.update({
        'intervention': intervention,
        'type_intervention': intervention.get_type_intervention_display(),
        'statut': intervention.get_statut_display(),
        'chantier_reference': inst.reference if inst else '',
        'client': client,
        'client_nom': (f"{client.nom} {client.prenom or ''}".strip()
                       if client else ''),
        'site_ville': getattr(inst, 'site_ville', '') or '',
        'site_adresse': getattr(inst, 'site_adresse', '') or '',
        # XFSM8 — notes d'accès du chantier, reprises telles quelles (jamais
        # ressaisies) sur le compte-rendu.
        'contact_site_nom': getattr(inst, 'contact_site_nom', '') or '',
        'contact_site_telephone': getattr(inst, 'contact_site_telephone', '') or '',
        'acces_instructions': getattr(inst, 'acces_instructions', '') or '',
        'horaires_acces': getattr(inst, 'horaires_acces', '') or '',
        'date_prevue': intervention.date_prevue,
        'date_realisee': intervention.date_realisee,
        'arrivee_site_le': intervention.arrivee_site_le,
        'depart_depot_le': intervention.depart_depot_le,
        'retour_depot_le': intervention.retour_depot_le,
        'equipe': _equipe_payload(intervention),
        'photos': _photos_payload(intervention),
        'serials': _serials_payload(intervention),
        'consommation': _consommation_payload(intervention),
        'reserves': _reserves_payload(intervention),
    })
    html = _render_html('compte_rendu_intervention.html', context)
    return _html_to_pdf(html)
