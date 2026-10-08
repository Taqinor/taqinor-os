"""Signature HMAC des webhooks Meta (``X-Hub-Signature-256``).

ASEC36-revue — primitive de FONDATION partagée : le webhook Lead Ads du CRM
(``apps.crm.webhooks``) et le webhook WhatsApp SAV entrant
(``apps.sav.public_views``) vérifient la même signature Meta. Le SAV importait
la fonction PRIVÉE du CRM (frontière cross-app) ; elle vit désormais ici, et
les deux apps l'importent. Comportement identique à l'ancienne
``crm.webhooks._check_meta_lead_ads_signature`` (PUB26, QJR413).
"""
import hashlib
import hmac


def signature_hub_sha256_valide(request, secret):
    """Vrai si ``X-Hub-Signature-256`` est présente ET valide (HMAC-SHA256 du
    corps brut avec ``secret``). Absente ou mal formée → False (rejet).

    QJR413 (a) — comparaison en BYTES : un en-tête non-ASCII rendait un 500
    public avec ``compare_digest`` sur des ``str``."""
    sig_header = request.META.get('HTTP_X_HUB_SIGNATURE_256', '')
    if not sig_header or not sig_header.startswith('sha256='):
        return False
    expected = 'sha256=' + hmac.new(
        secret.encode(), request.body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(str(sig_header).encode('utf-8'),
                               expected.encode('utf-8'))
