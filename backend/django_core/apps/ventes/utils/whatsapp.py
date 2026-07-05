"""Construction du message WhatsApp prêt à envoyer (lien wa.me).

Le client reçoit un lien PUBLIC, en lecture seule, expirant (30 j) vers le PDF
CLIENT du devis/facture — jamais de prix d'achat ni de marge (le PDF client ne
les contient pas). On NE fait QU'ouvrir WhatsApp avec le message pré-rempli ; le
commercial appuie lui-même sur Envoyer. Aucun envoi automatique, aucune pièce
jointe (cela exigerait l'API payante WhatsApp Business — hors périmètre).
"""
import re
from urllib.parse import quote

from .phone import normalize_ma_phone


def render_message_template(text, ctx):
    """Remplace {placeholders} et nettoie les espaces parasites.

    Les placeholders connus : {civilite} {nom} {reference} {lien} {n}
    {lien_rdv} (XSAL17 — lien de réservation de visite, résolu par
    l'appelant via ``apps.crm.services.resoudre_lien_rdv``). Un placeholder
    vide (ex. civilité inconnue) ne doit pas laisser de double espace ni
    d'espace avant une ponctuation.
    """
    out = text
    for key, val in ctx.items():
        out = out.replace('{' + key + '}', str(val if val is not None else ''))
    out = re.sub(r'[ \t]+', ' ', out)        # espaces multiples → un seul
    out = re.sub(r' +([,.;])', r'\1', out)   # espace avant , . ; (pas « : »)
    out = re.sub(r'[ \t]+\n', '\n', out)     # espace en fin de ligne
    return out.strip()


def public_document_url(request, token):
    """URL absolue publique vers le PDF (déduite de la requête, ou réglage)."""
    from django.conf import settings
    base = getattr(settings, 'PUBLIC_BASE_URL', '') or ''
    path = f'/api/django/public/document/{token}/'
    if base:
        return base.rstrip('/') + path
    return request.build_absolute_uri(path)


def build_wa_url(phone_raw, message):
    """Construit l'URL wa.me, ou None si le numéro est inexploitable."""
    number = normalize_ma_phone(phone_raw)
    if not number:
        return None
    return f'https://wa.me/{number}?text={quote(message)}'


def _nom_complet(prenom, nom):
    prenom = (prenom or '').strip()
    nom = (nom or '').strip()
    return f'{prenom} {nom}'.strip() if prenom else nom


def _lien_rdv_for(lead, request):
    """XSAL17 — Résout le lien de réservation de visite d'un lead, best-effort
    (jamais bloquant pour l'envoi d'un devis). Lazy import : ventes lit crm
    via son services.py, jamais crm.models directement."""
    try:
        from apps.crm.services import public_booking_url
        return public_booking_url(lead, request=request)
    except Exception:  # noqa: BLE001 — jamais bloquer l'envoi du devis
        return ''


def build_devis_whatsapp(request, lead, devis_list, langue='fr'):
    """Construit le message WhatsApp pour un ou plusieurs devis d'un lead.

    Renvoie (message, links). Crée/réutilise un lien public par devis.
    XSAL17 — {lien_rdv} est résolu paresseusement (une seule fois) SEULEMENT
    si le gabarit configuré le contient, pour ne jamais créer de
    ``BookingLink`` inutile sur un template qui ne l'utilise pas.
    """
    from apps.ventes.models import ShareLink
    from apps.parametres.models import MessageTemplate

    company = lead.company
    nom = _nom_complet(lead.prenom, lead.nom)
    links = []
    for d in devis_list:
        link = ShareLink.for_devis(d)
        links.append({
            'devis_id': d.id, 'reference': d.reference,
            'token': link.token, 'url': public_document_url(request, link.token),
        })

    if len(devis_list) == 1:
        tpl = MessageTemplate.get_corps(company, 'devis_unique', langue)
        lien_rdv = _lien_rdv_for(lead, request) if '{lien_rdv}' in tpl else ''
        message = render_message_template(tpl, {
            'civilite': '', 'nom': nom,
            'reference': links[0]['reference'], 'lien': links[0]['url'],
            'lien_rdv': lien_rdv})
    else:
        entete = MessageTemplate.get_corps(
            company, 'devis_multi_entete', langue)
        ligne = MessageTemplate.get_corps(
            company, 'devis_multi_ligne', langue)
        lien_rdv = (_lien_rdv_for(lead, request)
                    if ('{lien_rdv}' in entete or '{lien_rdv}' in ligne) else '')
        head = render_message_template(entete, {
            'civilite': '', 'nom': nom, 'n': len(devis_list),
            'lien_rdv': lien_rdv})
        body = '\n'.join(
            render_message_template(ligne, {
                'reference': ln['reference'], 'lien': ln['url'],
                'lien_rdv': lien_rdv})
            for ln in links)
        message = f'{head}\n{body}'
    return message, links


def devis_recipient_phone(devis):
    """QG8 — Numéro du destinataire d'un devis : client, sinon lead
    (WhatsApp puis téléphone). Renvoie la chaîne brute ou '' si aucune."""
    client = getattr(devis, 'client', None)
    if client is not None:
        phone = getattr(client, 'telephone', None)
        if phone:
            return phone
    lead = getattr(devis, 'lead', None)
    if lead is not None:
        return (getattr(lead, 'whatsapp', None)
                or getattr(lead, 'telephone', None) or '')
    return ''


def build_single_devis_whatsapp(request, devis, langue='fr'):
    """QG8 — Message WhatsApp pour UN devis (miroir de la voie lead CRM).

    Réutilise le modèle « devis_unique » de la société, crée/réutilise un lien
    public tokenisé (30 j) vers le PDF CLIENT du devis (jamais de prix d'achat
    ni de marge). Renvoie (message, link_info). Le nom du destinataire vient du
    client, sinon du lead."""
    from apps.ventes.models import ShareLink
    from apps.parametres.models import MessageTemplate

    company = devis.company
    client = getattr(devis, 'client', None)
    lead = getattr(devis, 'lead', None)
    if client is not None:
        nom = _nom_complet(getattr(client, 'prenom', ''), client.nom)
    elif lead is not None:
        nom = _nom_complet(getattr(lead, 'prenom', ''), getattr(lead, 'nom', ''))
    else:
        nom = ''
    link = ShareLink.for_devis(devis)
    url = public_document_url(request, link.token)
    tpl = MessageTemplate.get_corps(company, 'devis_unique', langue)
    message = render_message_template(tpl, {
        'civilite': '', 'nom': nom,
        'reference': devis.reference, 'lien': url})
    return message, {'token': link.token, 'url': url}


def build_facture_whatsapp(request, facture, modele='facture', langue='fr'):
    """Construit le message WhatsApp pour une facture (ou un rappel).

    Renvoie (message, link_info). `modele` ∈ {'facture', 'relance'}.
    """
    url_builder = (lambda token: public_document_url(request, token))
    return _build_facture_whatsapp_message(facture, modele, langue, url_builder)


def build_facture_whatsapp_draft(facture, modele='relance', langue='fr'):
    """XFAC8 — variante SANS ``request`` (job planifié, pas de vue HTTP).

    L'URL publique s'appuie sur ``settings.PUBLIC_BASE_URL`` (déjà utilisé en
    priorité par ``public_document_url``) ; sans ce réglage, le lien reste un
    chemin relatif (le message garde son sens, seul le lien est incomplet).
    Ne fait QU'ouvrir un brouillon wa.me — aucun envoi automatique."""
    def _url(token):
        from django.conf import settings
        base = getattr(settings, 'PUBLIC_BASE_URL', '') or ''
        path = f'/api/django/public/document/{token}/'
        return (base.rstrip('/') + path) if base else path
    return _build_facture_whatsapp_message(facture, modele, langue, _url)


def _build_facture_whatsapp_message(facture, modele, langue, url_builder):
    from apps.ventes.models import ShareLink
    from apps.parametres.models import MessageTemplate

    company = facture.company
    link = ShareLink.for_facture(facture)
    url = url_builder(link.token)
    cle = 'relance' if modele == 'relance' else 'facture'
    tpl = MessageTemplate.get_corps(company, cle, langue)
    nom = facture.client.nom if facture.client_id else ''
    message = render_message_template(tpl, {
        'civilite': '', 'nom': nom,
        'reference': facture.reference, 'lien': url})
    return message, {'token': link.token, 'url': url}
