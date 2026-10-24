"""QX13 — builder UNIQUE des URLs client-facing (proposition, suivi…).

Deux 404 ont été trouvés en prod à des moments d'intention maximale parce que
les URLs client étaient forgées à la main, ici ``/proposal/<token>`` alors que
la page du site est ``/proposition/<token>``. Ce module centralise la
construction pour que TOUS les producteurs (relances, emails, notifications)
émettent le MÊME chemin, garanti présent dans la table de routes du site.

Un test (``test_qx13_client_links``) vérifie que chaque chemin produit ici
existe bien dans ``apps/web/src/pages`` — un renommage de route côté site qui
casserait ces liens fait échouer la CI.

ADEV97 (L3 lien public, 24/10/2026) — le NOM du client ne voyage plus dans
l'URL : ``chemin_proposition`` rend ``/proposition/<token>`` (le lien est une
capacité : aucune donnée personnelle dans un chemin qu'on transfère, qu'un
scanner de messagerie journalise ou qu'un historique garde). Les liens déjà
envoyés sous la forme PV84 ``/proposition/<slug-client>/<token>`` restent
valides à vie : la route du site est un attrape-tout dont le TOKEN est le
dernier segment, le slug n'a jamais été vérifié.
"""
from __future__ import annotations

# Chemins RELATIFS (sans hôte) — la source de vérité des routes client.
# Doivent correspondre à un fichier réel dans ``apps/web/src/pages``.
PROPOSITION_PATH = '/proposition/{token}'
#: PV84 — ancienne forme (encore résolue par le site, plus jamais produite).
PROPOSITION_PATH_SLUG = '/proposition/{slug}/{token}'
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


def chemin_proposition(devis, token: str = None) -> str:
    """Fonction PARTAGÉE : chemin RELATIF de la proposition tokenisée d'un
    devis (« /proposition/<token> », ADEV97 : sans le nom du client). TOUS les
    producteurs du chemin proposition (endpoints devis, moteur PDF, relances,
    carte de partage…) doivent passer par ICI — jamais reconstruire
    ``/proposition/...`` en dur.

    ``token`` : passer le token d'un ``ShareLink`` déjà résolu pour éviter une
    requête redondante ; omis, il est résolu via ``ShareLink.for_devis``
    (idempotent — réutilise un lien encore valide). Le TOKEN reste le seul
    secret/auth."""
    if token is None:
        from ..models import ShareLink  # import local — évite un cycle utils→models
        token = ShareLink.for_devis(devis).token
    return proposition_path(token)


def url_proposition(devis, token: str = None) -> str:
    """URL absolue équivalente à ``chemin_proposition`` (base ``SITE_URL``)."""
    return f'{_site_url()}{chemin_proposition(devis, token)}'


def suivi_path(token: str) -> str:
    """Chemin relatif du suivi post-signature (« /suivi/<token> », QX34)."""
    return SUIVI_PATH.format(token=token)
