"""ADOC78 — validation partagée d'une signature client tracée à l'écran.

La signature est injectée telle quelle dans ``<img src="…">`` des PDF (PV de
réception, bon de livraison FR/AR, fiche de synthèse SAV pour la signature
d'intervention) : seule une data-URL image PNG ou JPEG en base64, bornée en
taille, est acceptée — jamais une URL http/file (récupérée par le moteur PDF)
ni une chaîne parasite (« null ») qui verrouillerait le document signé.
"""
import re

# ~512 Kio d'image une fois décodée : une signature SignaturePad (PNG) pèse
# quelques dizaines de Kio.
SIGNATURE_MAX_CARACTERES = 700_000

_DATA_URL = re.compile(
    r'^data:image/(?:png|jpeg|jpg);base64,[A-Za-z0-9+/]+={0,2}$')


def erreur_signature_client(valeur):
    """Message FR d'erreur pour ``valeur`` (str), ou ``None`` si valide."""
    sig = (valeur or '').strip() if isinstance(valeur, str) else ''
    if not sig:
        return 'Signature vide.'
    if len(sig) > SIGNATURE_MAX_CARACTERES:
        return (f'Signature trop volumineuse (maximum '
                f'{SIGNATURE_MAX_CARACTERES} caractères).')
    if not _DATA_URL.match(sig):
        return ('Signature invalide : seule une image PNG ou JPEG tracée '
                '(data-URL base64) est acceptée.')
    return None


class SignatureRefusee(Exception):
    """ACHT28 — signature d'intervention refusée. ``code`` : ``'invalide'``
    (400 / op en erreur) ou ``'deja_signee'`` (409 / op en erreur)."""

    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


def enregistrer_signature_intervention(interv, user, signature, nom='',
                                       motif=''):
    """ACHT28 (C-ACHT-026) — LE service unique d'écriture de la signature
    client d'une intervention, appelé par l'action `signer-client` ET l'op de
    synchro `intervention.signer_client` :

      * ``erreur_signature_client`` (data-URL PNG/JPEG bornée, jamais une
        URL injectée dans ``<img src>`` de la fiche SAV / du compte-rendu) ;
      * une RE-signature (``signe_le`` déjà posé) est refusée
        (``deja_signee``) sans ``motif`` explicite ; avec motif, une note
        « Signature remplacée (motif : …) » trace l'ancien et le nouveau
        signataire ;
      * ``signature_client`` / ``signataire_nom`` / ``signe_le`` suivis au
        chatter de l'intervention.
    Lève ``SignatureRefusee`` sans rien écrire. Renvoie l'intervention."""
    from django.utils import timezone

    from . import intervention_activity
    from .models import Intervention

    sig = signature.strip() if isinstance(signature, str) else ''
    nom = (nom or '').strip()
    motif = (motif or '').strip()
    erreur = erreur_signature_client(sig)
    if erreur:
        raise SignatureRefusee('invalide', erreur)
    if interv.signe_le and not motif:
        quand = timezone.localtime(interv.signe_le)
        raise SignatureRefusee('deja_signee', (
            "Cette intervention est déjà signée"
            + (f" par {interv.signataire_nom}" if interv.signataire_nom
               else "")
            + f" le {quand:%d/%m/%Y à %H:%M}. Une re-signature exige un "
            "motif explicite (`motif_override_signature`) — il sera "
            "journalisé."))
    old = Intervention.objects.get(pk=interv.pk)
    interv.signature_client = sig
    if nom:
        interv.signataire_nom = nom
    interv.signe_le = timezone.now()
    interv.save(update_fields=['signature_client', 'signataire_nom',
                               'signe_le'])
    intervention_activity.log_changes(old, interv, user)
    if old.signe_le:
        intervention_activity.log_note(
            interv, user,
            f"Signature remplacée (motif : {motif}) — ancien signataire : "
            f"{old.signataire_nom or 'anonyme'}, nouveau signataire : "
            f"{interv.signataire_nom or 'anonyme'}.")
    return interv
