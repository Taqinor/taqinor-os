"""QX13 — builder UNIQUE des URLs client-facing (proposition, suivi…).

Deux 404 ont été trouvés en prod à des moments d'intention maximale parce que
les URLs client étaient forgées à la main, ici ``/proposal/<token>`` alors que
la page du site est ``/proposition/<token>``. Ce module centralise la
construction pour que TOUS les producteurs (relances, emails, notifications)
émettent le MÊME chemin, garanti présent dans la table de routes du site.

Un test (``test_qx13_client_links``) vérifie que chaque chemin produit ici
existe bien dans ``apps/web/src/pages`` — un renommage de route côté site qui
casserait ces liens fait échouer la CI.
"""
from __future__ import annotations

# Chemins RELATIFS (sans hôte) — la source de vérité des routes client.
# Doivent correspondre à un fichier réel dans ``apps/web/src/pages``.
PROPOSITION_PATH = '/proposition/{token}'
SUIVI_PATH = '/suivi/{token}'


def _site_url() -> str:
    """Base URL du site public (settings.SITE_URL), sans slash final."""
    from django.conf import settings
    # SCA29 — pas de marque en dur ici ; le défaut vit dans settings.base.
    return (getattr(settings, 'SITE_URL', '') or '').rstrip('/')


def proposition_path(token: str) -> str:
    """Chemin relatif de la proposition tokenisée (« /proposition/<token> »)."""
    return PROPOSITION_PATH.format(token=token)


def proposition_url(token: str) -> str:
    """URL absolue de la proposition tokenisée."""
    return f'{_site_url()}{proposition_path(token)}'


def suivi_path(token: str) -> str:
    """Chemin relatif du suivi post-signature (« /suivi/<token> », QX34)."""
    return SUIVI_PATH.format(token=token)


def suivi_url(token: str) -> str:
    """URL absolue du suivi post-signature."""
    return f'{_site_url()}{suivi_path(token)}'
