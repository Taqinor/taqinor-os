"""F19 — Compte-rendu d'intervention PDF (client-facing).

Rendu à la volée via le MÊME pipeline que les factures/SAV
(apps.ventes.utils.pdf : identité société + template Jinja2 + WeasyPrint).
Non stocké : généré et streamé à la demande.

CÔTÉ CLIENT : AUCUN prix d'achat, AUCUNE marge — jamais. Le matériel
réellement consommé n'affiche que désignation + quantités (prévu/utilisé) et la
justification d'écart ; jamais un prix interne. Complète le PV de réception.
"""
from apps.ventes.utils.pdf import _company_context, _html_to_pdf, _render_html


def _nom_client_facing(user, company):
    """APDF41 — nom affichable d'un intervenant sur un document client : nom
    complet, sinon raison sociale du profil société, JAMAIS l'identifiant de
    connexion ni une adresse e-mail (``parametres.selectors.nom_intervenant``)."""
    from apps.parametres.selectors import nom_intervenant
    return nom_intervenant(user, company)


def _equipe_payload(intervention):
    noms = [_nom_client_facing(u, intervention.company)
            for u in intervention.equipe.all()]
    return [n for n in noms if n]


def _photos_payload(intervention, *, public_token=None):
    """Photos groupées avant/pendant/après (URL de proxy Django, jamais l'objet
    MinIO directement).

    APDF38 — avec ``public_token`` (page publique du rapport), chaque photo est
    servie par la route À JETON de CETTE intervention (``…/photo/<id>/``, sans
    session) et la forme reste ``{libelle, url}`` ; sans jeton, URL du
    téléchargement authentifié + ``id`` (lu par le rendu PDF interne)."""
    from . import field_services
    groups = {'avant': [], 'pendant': [], 'apres': []}
    by_slot = field_services.photos_by_slot(intervention)
    for slot in field_services.active_shotlist(intervention.company):
        for att in by_slot.get(slot.cle, []):
            if public_token:
                groups.setdefault(slot.phase, []).append({
                    'libelle': slot.libelle,
                    'url': (f'/api/django/public/installations/'
                            f'intervention-rapport/{public_token}/'
                            f'photo/{att.id}/'),
                })
                continue
            groups.setdefault(slot.phase, []).append({
                'id': att.id,
                'libelle': slot.libelle,
                'url': f'/api/django/records/attachments/{att.id}/download/',
            })
    return groups


#: APDF37 — plafonds d'embarquement des photos dans le PDF (nombre, poids
#: cumulé des data URI, côté long en pixels, qualité JPEG).
PDF_PHOTOS_MAX = 12
PDF_PHOTOS_POIDS_MAX = 6 * 1024 * 1024
PDF_PHOTO_COTE_MAX = 900
PDF_PHOTO_QUALITE = 72


def _photo_data_uri(attachment):
    """Data URI JPEG réduite (Pillow) d'une pièce jointe photo, ou None si les
    octets sont illisibles/absents. Les octets sont lus CÔTÉ SERVEUR : le
    rendu PDF n'a pas d'URL de base pour une URI relative."""
    import base64
    import io

    from apps.records.storage import fetch_attachment
    data, _err = fetch_attachment(attachment.file_key)
    if not data:
        return None
    try:
        from PIL import Image, ImageOps
        with Image.open(io.BytesIO(data)) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail((PDF_PHOTO_COTE_MAX, PDF_PHOTO_COTE_MAX))
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            sortie = io.BytesIO()
            img.save(sortie, format='JPEG', quality=PDF_PHOTO_QUALITE,
                     optimize=True)
    except Exception:  # noqa: BLE001 — une photo illisible ne casse pas le PDF
        return None
    return 'data:image/jpeg;base64,' + base64.b64encode(
        sortie.getvalue()).decode()


def _photos_payload_embarquees(intervention):
    """APDF37 — variante PDF de ``_photos_payload`` : chaque photo porte une
    data URI (octets lus côté serveur, réduits). Nombre et poids plafonnés ;
    renvoie ``(groupes, nb_non_reproduites)`` — les photos au-delà du plafond
    (ou illisibles) sont comptées, jamais silencieusement perdues."""
    from apps.records.models import Attachment

    groupes = _photos_payload(intervention)
    embarquees = 0
    poids = 0
    non_reproduites = 0
    for phase in list(groupes):
        retenues = []
        for photo in groupes[phase]:
            if embarquees >= PDF_PHOTOS_MAX:
                non_reproduites += 1
                continue
            att = Attachment.objects.filter(pk=photo['id']).first()
            uri = _photo_data_uri(att) if att is not None else None
            if uri is None or poids + len(uri) > PDF_PHOTOS_POIDS_MAX:
                non_reproduites += 1
                continue
            poids += len(uri)
            embarquees += 1
            retenues.append({**photo, 'url': uri})
        groupes[phase] = retenues
    return groupes, non_reproduites


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
            # APDF41 — jamais l'identifiant de connexion sur un document
            # client (nom complet, sinon raison sociale).
            'assignee': (_nom_client_facing(r.assignee, intervention.company)
                         or None) if r.assignee_id else None,
            'resolution': r.resolution,
        }
        for r in intervention.reserves.all()
    ]


def _signature_payload(intervention):
    """ACHT29 (C-ACHT-027) — signature client recueillie sur l'intervention
    (image data-URL validée ADOC78, signataire, date/heure locale), ou None.
    Même source que la fiche SAV (`apps/sav/pdf.py`)."""
    from django.utils import timezone

    from .signature_validation import erreur_signature_client

    image = getattr(intervention, 'signature_client', None)
    if not image or erreur_signature_client(image):
        return None
    signe_le = getattr(intervention, 'signe_le', None)
    return {
        'image': image,
        'nom': (intervention.signataire_nom or '').strip(),
        'date': (timezone.localtime(signe_le).strftime('%d/%m/%Y %H:%M')
                 if signe_le else ''),
    }


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
        'signature': _signature_payload(intervention),
    })
    # APDF37 — photos EMBARQUÉES (data URI) : le rendu PDF n'a pas de base
    # d'URL pour les chemins relatifs du proxy de téléchargement.
    photos, non_reproduites = _photos_payload_embarquees(intervention)
    context['photos'] = photos
    context['photos_non_reproduites'] = non_reproduites
    html = _render_html('compte_rendu_intervention.html', context)
    return _html_to_pdf(html)
