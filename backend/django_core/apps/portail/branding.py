"""NTPRT19 — Branding des PORTAILS EXTERNES (login + emails).

Source de vérité UNIQUE de la marque vue par un client/fournisseur/partenaire :
``core.TenantTheme`` (FG392, logo/couleurs/nom affiché/domaine white-label),
avec un REPLI explicite sur ``parametres.CompanyProfile`` champ par champ.

Deux règles qui tiennent tout :

* **Jamais d'erreur.** Aucun thème, aucun profil, table absente : on renvoie
  une marque VIDE et l'interface retombe sur ses couleurs par défaut
  (``tokens.css``). Une page de login ne casse pas pour un logo.
* **Repli champ par champ, pas objet par objet.** Un ``TenantTheme`` existant
  mais au ``nom_affichage`` vide doit quand même afficher la raison sociale du
  ``CompanyProfile`` — sinon activer le thème pour changer UNE couleur ferait
  disparaître le nom de la société.

SÉCURITÉ — la résolution PUBLIQUE se fait STRICTEMENT par l'en-tête ``Host``
(domaine white-label), jamais par un paramètre d'URL : sans cela, l'endpoint
deviendrait un énumérateur de tenants (``?company=1,2,3…``). Et la charge utile
ne porte QUE de la marque — jamais l'id société, jamais le domaine, jamais
l'identité légale.
"""

#: Marque vide — repli neutre, toujours sérialisable.
MARQUE_VIDE = {
    'nom_affichage': '',
    'logo_url': '',
    'couleur_primaire': '',
    'couleur_secondaire': '',
}


def _tenant_theme(company):
    try:
        from core.models import TenantTheme
        return TenantTheme.objects.filter(company=company).first()
    except Exception:  # noqa: BLE001 - le branding ne casse jamais un écran
        return None


def _profil(company):
    try:
        from apps.parametres.selectors import company_identity
        return company_identity(company)
    except Exception:  # noqa: BLE001
        return {}


def marque_portail(company):
    """Marque à afficher pour ``company``. Ne lève jamais.

    Renvoie un dict aux clés de ``MARQUE_VIDE``. ``TenantTheme`` prime champ
    par champ ; chaque champ vide retombe sur ``CompanyProfile``.
    """
    if company is None:
        return dict(MARQUE_VIDE)
    theme = _tenant_theme(company)
    profil = _profil(company)
    return {
        'nom_affichage': (
            (getattr(theme, 'nom_affichage', '') or '')
            or (profil.get('nom') or '')
            or (getattr(company, 'nom', '') or '')
        ),
        'logo_url': (getattr(theme, 'logo_url', '') or ''),
        'couleur_primaire': (
            (getattr(theme, 'couleur_primaire', '') or '')
            or (profil.get('couleur_principale') or '')
        ),
        'couleur_secondaire': (
            getattr(theme, 'couleur_secondaire', '') or ''),
    }


def company_pour_hote(host):
    """Société dont le ``TenantTheme.domaine`` correspond à ``host``, ou None.

    ``host`` vient de ``request.get_host()`` : on retire un éventuel port et on
    compare sans casse. Un domaine vide ne matche jamais (sinon TOUTES les
    sociétés sans domaine seraient candidates). Aucune autre entrée n'est
    acceptée — pas de paramètre d'URL, donc pas d'énumération de tenants.
    """
    hote = (host or '').split(':', 1)[0].strip().lower()
    if not hote:
        return None
    try:
        from core.models import TenantTheme
        theme = (TenantTheme.objects
                 .filter(domaine__iexact=hote)
                 .exclude(domaine='')
                 .select_related('company')
                 .first())
    except Exception:  # noqa: BLE001
        return None
    return getattr(theme, 'company', None) if theme is not None else None
