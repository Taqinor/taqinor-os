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
