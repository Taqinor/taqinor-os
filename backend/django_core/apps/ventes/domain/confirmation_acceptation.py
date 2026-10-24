"""ADEV99 (L3 lien public, 24/10/2026) — la confirmation d'acceptation aux DEUX parties.

À l'acceptation, l'e-mail de confirmation (exemplaire signé joint) part :

* au SIGNATAIRE (``DevisSignature.signataire_email``, ADEV95 — l'entreprise C&I) ET au
  CONTACT du lead (son e-mail), sinon au client comme avant — chaque adresse une fois ;
* en COPIE au vendeur (responsable du lead, sinon créateur du devis), PDF joint, en plus
  de la notification in-app (``_notify_seller_accepted``, inchangée).

Le corps dit ce que le client a engagé : raison sociale / ICE quand le devis C&I les
porte, l'horodatage de la signature (Africa/Casablanca) et l'empreinte du contenu
signé (+ celle du PDF quand elle est connue). Français, anglais quand la page était
lue en anglais (``DevisSignature.langue_page``). QJR134 tient : sans enregistrement de
signature, l'e-mail n'affirme ni signature ni exemplaire signé. Best-effort : rien
ici ne peut défaire l'acceptation. Aucun prix d'achat / marge (règle #4).
"""
import logging

logger = logging.getLogger(__name__)

TEXTES = {
    'fr': {
        'sujet': 'Proposition acceptée — {ref}',
        'salut': 'Bonjour {nom},',
        'salut_vide': 'Bonjour,',
        'recu': "Nous avons bien reçu votre acceptation du devis {ref}.",
        'signature': ("Votre signature électronique a été enregistrée conformément "
                      "à la loi 43-20 relative à l'échange électronique de données "
                      "juridiques."),
        'entreprise': 'Société : {rs} — ICE : {ice}',
        'signataire': 'Signataire : {nom}{qualite}',
        'horodatage': 'Signé le {quand} (heure de Casablanca)',
        'empreinte': 'Empreinte du contenu signé (SHA-256) : {h}',
        'empreinte_pdf': 'Empreinte du PDF signé (SHA-256) : {h}',
        'exemplaire': "Vous trouverez ci-joint votre exemplaire signé pour vos archives.",
        'merci': 'Merci pour votre confiance.',
        'cordialement': 'Cordialement,',
        'copie': ("Copie pour information — la confirmation ci-dessous a été "
                  "envoyée au client ({dest})."),
        'copie_sujet': 'Copie — proposition acceptée — {ref}',
    },
    'en': {
        'sujet': 'Proposal accepted — {ref}',
        'salut': 'Hello {nom},',
        'salut_vide': 'Hello,',
        'recu': 'We have received your acceptance of quote {ref}.',
        'signature': ('Your electronic signature has been recorded in accordance '
                      'with Moroccan law 43-20 on the electronic exchange of legal '
                      'data.'),
        'entreprise': 'Company: {rs} — ICE: {ice}',
        'signataire': 'Signatory: {nom}{qualite}',
        'horodatage': 'Signed on {quand} (Casablanca time)',
        'empreinte': 'Fingerprint of the signed content (SHA-256): {h}',
        'empreinte_pdf': 'Fingerprint of the signed PDF (SHA-256): {h}',
        'exemplaire': 'Please find attached your signed copy for your records.',
        'merci': 'Thank you for your trust.',
        'cordialement': 'Kind regards,',
        'copie': ('Copy for your information — the confirmation below was sent '
                  'to the client ({dest}).'),
        'copie_sujet': 'Copy — proposal accepted — {ref}',
    },
}


def _signature_de(devis):
    from apps.ventes.models import DevisSignature
    return DevisSignature.objects.filter(devis=devis).first()


def destinataires_client(devis, sig):
    """Le signataire ET le contact (l'e-mail du lead, à défaut celui du
    client), chaque adresse une seule fois (casse ignorée), jamais vide."""
    lead = getattr(devis, 'lead', None)
    client = getattr(devis, 'client', None)
    contact = (getattr(lead, 'email', '') or '').strip() \
        or (getattr(client, 'email', '') or '')
    candidats = [getattr(sig, 'signataire_email', '') or '', contact]
    vus, sortie = set(), []
    for adresse in (c.strip() for c in candidats):
        if adresse and adresse.lower() not in vus:
            vus.add(adresse.lower())
            sortie.append(adresse)
    return sortie


def _bloc_preuve(sig, t):
    """Raison sociale / ICE, signataire, horodatage Casablanca, empreintes."""
    from core.dates import TZ_METIER
    lignes = []
    if sig.raison_sociale or sig.ice_declare:
        lignes.append(t['entreprise'].format(rs=sig.raison_sociale or '—',
                                             ice=sig.ice_declare or '—'))
    qualite = f' ({sig.signataire_qualite})' if sig.signataire_qualite else ''
    lignes.append(t['signataire'].format(nom=sig.signataire_nom, qualite=qualite))
    if sig.signed_at:
        quand = sig.signed_at.astimezone(TZ_METIER).strftime('%d/%m/%Y %H:%M')
        lignes.append(t['horodatage'].format(quand=quand))
    if sig.content_hash:
        lignes.append(t['empreinte'].format(h=sig.content_hash))
    if sig.signed_pdf_sha256:
        lignes.append(t['empreinte_pdf'].format(h=sig.signed_pdf_sha256))
    return '\n'.join(lignes) + '\n\n'


def corps_confirmation(devis, sig, *, acompte_bloc='', langue='fr'):
    """Le corps de la confirmation (FR, EN si ``langue == 'en'``)."""
    from apps.ventes.email_service import _signature as _signature_societe
    t = TEXTES['en' if langue == 'en' else 'fr']
    client = getattr(devis, 'client', None)
    nom = ''
    if client is not None:
        nom = f"{client.nom} {getattr(client, 'prenom', '') or ''}".strip()
    salut = t['salut'].format(nom=nom) if nom else t['salut_vide']
    preuve = sig is not None
    return (
        f"{salut}\n\n{t['recu'].format(ref=devis.reference)}\n\n"
        + (f"{t['signature']}\n\n{_bloc_preuve(sig, t)}" if preuve else '')
        + (acompte_bloc or '')
        + (f"{t['exemplaire']}\n\n" if preuve else '')
        + f"{t['merci']}\n\n{t['cordialement']}\n{_signature_societe(devis.company)}"
    )


def _vendeur(devis):
    lead = getattr(devis, 'lead', None)
    return getattr(lead, 'owner', None) or getattr(devis, 'created_by', None)


def envoyer_confirmations(*, devis, user, acompte_bloc=''):
    """Copie au vendeur (PDF joint) PUIS confirmation à chaque destinataire
    client (PDF joint). Rend la liste des adresses client servies.

    G (revue du 24/10/2026) — chaque envoi client est gardé SÉPARÉMENT : un
    échec sur le premier destinataire (journalisé) n'empêche jamais le
    second ; seules les adresses réellement servies sont rendues."""
    from apps.ventes.email_service import send_document_email
    sig = _signature_de(devis)
    langue = 'en' if getattr(sig, 'langue_page', '') == 'en' else 'fr'
    t = TEXTES[langue]
    corps = corps_confirmation(devis, sig, acompte_bloc=acompte_bloc, langue=langue)
    dests = destinataires_client(devis, sig)
    vendeur = _vendeur(devis)
    email_vendeur = (getattr(vendeur, 'email', '') or '').strip()
    if email_vendeur and email_vendeur.lower() not in {d.lower() for d in dests} \
            and getattr(user, 'pk', None) != getattr(vendeur, 'pk', None):
        try:
            send_document_email(
                devis, to_email=email_vendeur,
                sujet=t['copie_sujet'].format(ref=devis.reference),
                corps=f"{t['copie'].format(dest=', '.join(dests) or '—')}\n\n{corps}",
                user=user, attach_pdf=True, log_activity=False)
        except Exception:  # noqa: BLE001 — best-effort, journalisé (D-ENF22-BLE001)
            logger.warning('ADEV99 : copie vendeur non partie (%s)', devis.reference, exc_info=True)
    servies = []
    for dest in dests:
        try:
            send_document_email(
                devis, to_email=dest, sujet=t['sujet'].format(ref=devis.reference),
                corps=corps, user=user, attach_pdf=True, log_activity=False)
        except Exception:  # noqa: BLE001 — un destinataire n'arrête pas l'autre (D-ENF22-BLE001)
            logger.warning('ADEV99 : confirmation non partie à %s (%s)', dest,
                           devis.reference, exc_info=True)
            continue
        servies.append(dest)
    return servies
