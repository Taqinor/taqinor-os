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

    Les placeholders connus : {civilite} {nom} {reference} {lien} {n}. Un
    placeholder vide (ex. civilité inconnue) ne doit pas laisser de double
    espace ni d'espace avant une ponctuation.
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


def build_devis_whatsapp(request, lead, devis_list, langue='fr'):
    """Construit le message WhatsApp pour un ou plusieurs devis d'un lead.

    Renvoie (message, links). Crée/réutilise un lien public par devis.
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
        message = render_message_template(tpl, {
            'civilite': '', 'nom': nom,
            'reference': links[0]['reference'], 'lien': links[0]['url']})
    else:
        entete = MessageTemplate.get_corps(
            company, 'devis_multi_entete', langue)
        ligne = MessageTemplate.get_corps(
            company, 'devis_multi_ligne', langue)
        head = render_message_template(entete, {
            'civilite': '', 'nom': nom, 'n': len(devis_list)})
        body = '\n'.join(
            render_message_template(ligne, {
                'reference': ln['reference'], 'lien': ln['url']})
            for ln in links)
        message = f'{head}\n{body}'
    return message, links


def build_facture_whatsapp(request, facture, modele='facture', langue='fr'):
    """Construit le message WhatsApp pour une facture (ou un rappel).

    Renvoie (message, link_info). `modele` ∈ {'facture', 'relance'}.
    """
    from apps.ventes.models import ShareLink
    from apps.parametres.models import MessageTemplate

    company = facture.company
    link = ShareLink.for_facture(facture)
    url = public_document_url(request, link.token)
    cle = 'relance' if modele == 'relance' else 'facture'
    tpl = MessageTemplate.get_corps(company, cle, langue)
    nom = facture.client.nom if facture.client_id else ''
    message = render_message_template(tpl, {
        'civilite': '', 'nom': nom,
        'reference': facture.reference, 'lien': url})
    return message, {'token': link.token, 'url': url}
