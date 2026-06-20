"""ERR46 — Validation anti-SSRF des URL de webhook (N89).

Un webhook est un POST sortant émis CÔTÉ SERVEUR vers une cible fournie par un
admin/responsable. Sans garde-fou, cette cible peut pointer vers des adresses
internes (métadonnées cloud 169.254.169.254, base de données, MinIO, services
loopback…) : c'est une SSRF. On impose donc, à l'écriture (serializer) ET au
moment de la livraison :

  - le schéma DOIT être https (jamais http/file/gopher…) ;
  - l'hôte ne doit PAS résoudre vers une adresse privée / loopback /
    link-local / réservée / multicast / non spécifiée.

La résolution DNS est effectuée à la validation pour bloquer aussi les noms
d'hôte qui résolvent vers une IP interne (et pas seulement les IP littérales).
"""
import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeWebhookURL(ValueError):
    """L'URL de webhook est rejetée (schéma non https ou hôte interne)."""


def _ip_is_blocked(ip_str):
    """True si l'IP appartient à une plage non routable/dangereuse."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        # Adresse non parsable → on bloque par prudence.
        return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local        # 169.254.0.0/16 (incl. métadonnées cloud)
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_webhook_target_url(url):
    """Valide une URL de webhook. Lève `UnsafeWebhookURL` si elle est dangereuse.

    Renvoie l'URL inchangée si elle est sûre (https + hôte public résolvable)."""
    if not url:
        raise UnsafeWebhookURL("L'URL du webhook est obligatoire.")
    parsed = urlparse(url)
    if parsed.scheme.lower() != 'https':
        raise UnsafeWebhookURL("L'URL du webhook doit utiliser https.")
    host = parsed.hostname
    if not host:
        raise UnsafeWebhookURL("L'URL du webhook est invalide (hôte absent).")

    # Si l'hôte est déjà une IP littérale, on la teste directement…
    try:
        ipaddress.ip_address(host)
        candidates = [host]
    except ValueError:
        # …sinon on résout le nom et on teste TOUTES les adresses obtenues.
        try:
            infos = socket.getaddrinfo(host, parsed.port or 443,
                                       proto=socket.IPPROTO_TCP)
        except socket.gaierror as exc:
            raise UnsafeWebhookURL(
                "L'hôte du webhook est introuvable (DNS).") from exc
        candidates = [info[4][0] for info in infos]

    if not candidates:
        raise UnsafeWebhookURL("L'hôte du webhook n'a pas pu être résolu.")
    for ip_str in candidates:
        if _ip_is_blocked(ip_str):
            raise UnsafeWebhookURL(
                "L'URL du webhook pointe vers une adresse interne interdite.")
    return url
