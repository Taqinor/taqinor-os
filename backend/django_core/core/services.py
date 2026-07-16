"""SCA28 — Services d'amorçage « à la création d'une société » (couche core).

Constat : même une fois CÂBLÉS (SCA24 côté SPA, SCA25 côté emails), les tables
``TenantTheme`` (FG392) et ``BrandedTemplate`` (FG393) restent VIDES pour un
tenant fraîchement inscrit — le branding white-label n'a aucune ligne de départ.
Ce module pose le SEED idempotent de ces deux tables au signup :

  * un ``TenantTheme`` NEUTRE (aucune couleur, aucun logo, aucun domaine) : SCA24
    lit le thème et retombe sur les valeurs par défaut du produit pour tout champ
    vide — la seule présence de la ligne suffit à ce que la SPA la consomme SANS
    étape manuelle, sans imposer une charte au nouveau tenant ;
  * les ``BrandedTemplate`` PAR DÉFAUT (placeholders société, JAMAIS de nom en
    dur) — notamment la signature d'email (kind ``email``, code ``signature``)
    dont le corps ``L'équipe {{ nom_societe }}`` est rendu par
    ``core.selectors.resolve_email_signature`` STRICTEMENT à l'identique du repli
    neutre historique : un tenant nommé « ACME » signe « L'équipe ACME », jamais
    « TAQINOR ».

``core`` reste une couche de FONDATION : ce module n'importe AUCUNE app métier
(seulement ses propres modèles ``core.models`` + la constante de code d'usage de
``core.selectors``). Tout est idempotent et ADDITIF : rejouable sans doublon et
sans jamais écraser une valeur qu'une société aurait déjà personnalisée.
"""
from __future__ import annotations


def seed_tenant_theme(company) -> object:
    """Crée (idempotent) un ``TenantTheme`` NEUTRE pour ``company``.

    Neutre = tous les champs de branding vides (couleurs, logo, domaine, nom
    d'affichage) : SCA24 lit la ligne et applique les défauts du produit. Ne
    touche JAMAIS une ligne existante (``get_or_create``) — une société qui a
    déjà personnalisé son thème garde ses valeurs.
    """
    from core.models import TenantTheme
    theme, _created = TenantTheme.objects.get_or_create(company=company)
    return theme


# Modèles brandés par défaut posés à l'inscription. ``code`` + ``kind`` sont la
# clé d'unicité (avec la société) ; ``corps`` n'utilise que des placeholders
# ``{{ … }}`` — aucun nom de société en dur. La signature reproduit le repli
# neutre historique (« L'équipe {nom} ») rendu par ``resolve_email_signature``.
def _default_branded_templates():
    """Retourne la liste ``(kind, code, nom, sujet, corps)`` des modèles seedés.

    Fonction (et non constante de module) pour importer ``BrandedTemplate`` de
    façon paresseuse et garder ``core`` sans effet de bord à l'import.
    """
    from core.models import BrandedTemplate
    from core.selectors import EMAIL_SIGNATURE_CODE
    return [
        (
            BrandedTemplate.KIND_EMAIL,
            EMAIL_SIGNATURE_CODE,
            'Signature e-mail',
            '',
            "L'équipe {{ nom_societe }}",
        ),
    ]


def seed_branded_templates(company) -> int:
    """Crée (idempotent) les ``BrandedTemplate`` par défaut de ``company``.

    Additif : ``get_or_create`` par ``(company, kind, code)`` — ne remplace
    jamais un modèle qu'une société a déjà rédigé. Renvoie le nombre de modèles
    NOUVELLEMENT créés (0 au deuxième passage).
    """
    from core.models import BrandedTemplate
    crees = 0
    for kind, code, nom, sujet, corps in _default_branded_templates():
        _obj, created = BrandedTemplate.objects.get_or_create(
            company=company, kind=kind, code=code,
            defaults={'nom': nom, 'sujet': sujet, 'corps': corps,
                      'actif': True},
        )
        if created:
            crees += 1
    return crees


def seed_tenant_branding(company, *, user=None) -> dict:
    """Seed complet du branding d'une nouvelle société (thème + modèles).

    Point d'entrée unique appelé par le hook signup (``core.signup_hooks``) ET
    réutilisable par une commande de rattrapage. Idempotent et additif. Renvoie
    un petit résumé sérialisable ``{'theme': bool, 'templates_crees': int}``.
    """
    theme = seed_tenant_theme(company)
    templates_crees = seed_branded_templates(company)
    return {'theme': theme is not None, 'templates_crees': templates_crees}
