"""QX13 — builder UNIQUE des URLs client-facing (proposition, suivi…).

Deux 404 ont été trouvés en prod à des moments d'intention maximale parce que
les URLs client étaient forgées à la main, ici ``/proposal/<token>`` alors que
la page du site est ``/proposition/<token>``. Ce module centralise la
construction pour que TOUS les producteurs (relances, emails, notifications)
émettent le MÊME chemin, garanti présent dans la table de routes du site.

Un test (``test_qx13_client_links``) vérifie que chaque chemin produit ici
existe bien dans ``apps/web/src/pages`` — un renommage de route côté site qui
casserait ces liens fait échouer la CI.

PV84 — le lien client porte désormais le NOM du client dans l'URL
(``chemin_proposition``) : ``/proposition/<slug-client>/<token>``. Le TOKEN
reste le SEUL secret/auth (ShareLink imprévisible, expirant) ; le slug est
PUREMENT COSMÉTIQUE et n'est JAMAIS vérifié côté serveur — un slug absent,
périmé ou différent du nom actuel du client fonctionne à l'identique. Les
anciens liens sans slug (``proposition_path``/``proposition_url``, forme
``/proposition/<token>``) restent valides à vie (route site optionnelle sur
le slug — gérée côté ``apps/web``).
"""
from __future__ import annotations

# Chemins RELATIFS (sans hôte) — la source de vérité des routes client.
# Doivent correspondre à un fichier réel dans ``apps/web/src/pages``.
PROPOSITION_PATH = '/proposition/{token}'
PROPOSITION_PATH_SLUG = '/proposition/{slug}/{token}'
SUIVI_PATH = '/suivi/{token}'

# PV84 — borne de lisibilité du slug nom-client dans l'URL (jamais une
# contrainte de sécurité — cosmétique seulement).
SLUG_MAX_LEN = 40
SLUG_FALLBACK = 'proposition'


def _site_url() -> str:
    """Base URL du site public (settings.SITE_URL), sans slash final."""
    from django.conf import settings
    # SCA29 — pas de marque en dur ici ; le défaut vit dans settings.base.
    return (getattr(settings, 'SITE_URL', '') or '').rstrip('/')


def slugifier_nom(nom_complet: str) -> str:
    """PV84 — translittère un nom en slug ASCII minuscule borné à
    ``SLUG_MAX_LEN``, jamais vide (repli ``SLUG_FALLBACK``). ``django.utils.
    text.slugify`` gère déjà la translittération accents→ASCII (NFKD) : «
    Aït Benhaddou Éléonore » → ``ait-benhaddou-eleonore``."""
    from django.utils.text import slugify
    slug = slugify(nom_complet or '')
    if not slug:
        return SLUG_FALLBACK
    slug = slug[:SLUG_MAX_LEN].rstrip('-')
    return slug or SLUG_FALLBACK


def _nom_complet_devis(devis) -> str:
    """Nom complet du CLIENT d'un devis (ou, à défaut, de son LEAD d'origine)
    — pour le slug cosmétique de l'URL seulement. Jamais de téléphone/email,
    jamais d'autre donnée sensible : uniquement nom + prénom."""
    for porteur in (getattr(devis, 'client', None), getattr(devis, 'lead', None)):
        if porteur is None:
            continue
        nom = (getattr(porteur, 'nom', '') or '').strip()
        prenom = (getattr(porteur, 'prenom', '') or '').strip()
        full = f'{nom} {prenom}'.strip()
        if full:
            return full
    return ''


def proposition_path(token: str) -> str:
    """Chemin relatif de la proposition tokenisée SANS slug (« /proposition/
    <token> »). Forme historique — conservée pour les appelants qui n'ont
    qu'un token (pas de devis) ; toujours servie par le site (lien à vie)."""
    return PROPOSITION_PATH.format(token=token)


def proposition_url(token: str) -> str:
    """URL absolue de la proposition tokenisée SANS slug."""
    return f'{_site_url()}{proposition_path(token)}'


def chemin_proposition(devis, token: str = None) -> str:
    """PV84 — fonction PARTAGÉE : chemin RELATIF de la proposition tokenisée
    d'un devis, nom du client INCLUS dans l'URL (« /proposition/<slug-client>/
    <token> »). TOUS les producteurs du chemin proposition (endpoints devis,
    moteur PDF, relances, carte de partage…) doivent passer par ICI — jamais
    reconstruire ``/proposition/...`` en dur.

    ``token`` : passer le token d'un ``ShareLink`` déjà résolu pour éviter une
    requête redondante ; omis, il est résolu via ``ShareLink.for_devis``
    (idempotent — réutilise un lien encore valide).

    Le slug est PUREMENT cosmétique et n'est JAMAIS vérifié côté serveur : le
    TOKEN reste le seul secret/auth."""
    if token is None:
        from ..models import ShareLink  # import local — évite un cycle utils→models
        token = ShareLink.for_devis(devis).token
    slug = slugifier_nom(_nom_complet_devis(devis))
    return PROPOSITION_PATH_SLUG.format(slug=slug, token=token)


def url_proposition(devis, token: str = None) -> str:
    """URL absolue équivalente à ``chemin_proposition`` (base ``SITE_URL``)."""
    return f'{_site_url()}{chemin_proposition(devis, token)}'


def suivi_path(token: str) -> str:
    """Chemin relatif du suivi post-signature (« /suivi/<token> », QX34)."""
    return SUIVI_PATH.format(token=token)


def suivi_url(token: str) -> str:
    """URL absolue du suivi post-signature."""
    return f'{_site_url()}{suivi_path(token)}'
