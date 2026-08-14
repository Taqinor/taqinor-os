"""NTWMS9 — interface commune des connecteurs transporteur + connecteur NoOp.

``TransportProvider`` hérite de ``core.integrations.BaseProvider`` (la
fondation) : le registre, la résolution du secret et le drapeau
``is_configured`` sont ceux de la plateforme, jamais réécrits ici.
"""
from core.integrations import BaseProvider, register_provider

# Type d'intégration de cette famille de connecteurs.
TYPE_TRANSPORT = 'transport'


class TransportProvider(BaseProvider):
    """Contrat d'un connecteur transporteur.

    ``creer_expedition(unite)`` → ``(numero_suivi, etiquette_pdf_bytes)``.
    ``estimer_tarif(poids_kg, dimensions, destination)`` → ``{cout, delai_jours,
    devise}`` ou ``None`` quand le connecteur ne sait pas répondre.

    RÈGLE ABSOLUE : un connecteur NON configuré ne fait AUCUN appel réseau.
    """

    integration_type = TYPE_TRANSPORT
    # Délai indicatif affiché quand le connecteur n'a pas d'estimation réelle.
    delai_indicatif_jours = None

    def creer_expedition(self, unite):
        raise NotImplementedError

    def estimer_tarif(self, poids_kg=None, dimensions='', destination=''):
        """Estimation de coût/délai. ``None`` = ce connecteur ne sait pas."""
        return None


@register_provider
class NoOpProvider(TransportProvider):
    """Connecteur par DÉFAUT : aucune intégration externe.

    Il produit un numéro de suivi INTERNE dérivé du SSCC (donc unique et
    traçable) et une étiquette PDF générique rendue par le moteur d'étiquettes
    du module. Il est TOUJOURS « configuré » (il n'a besoin d'aucun secret) :
    c'est le repli qui garantit qu'une expédition reste possible sans compte
    transporteur.
    """

    code = 'aucun'
    label = 'Aucun (étiquette interne)'

    def is_configured(self) -> bool:
        return True

    def creer_expedition(self, unite):
        from .. import labels
        from apps.ventes.utils.pdf import _html_to_pdf

        numero_suivi = f'INT-{unite.sscc}'
        html = labels.render_etiquettes_sscc_html([{
            'sscc': unite.sscc,
            'titre': f'{unite.get_type_unite_display()} {unite.sscc}',
            'sous_titre': f'Suivi interne {numero_suivi}',
        }])
        return numero_suivi, _html_to_pdf(html)

    def estimer_tarif(self, poids_kg=None, dimensions='', destination=''):
        # Aucun tarif propre : le comparateur (NTWMS10) retombera sur le
        # `Transporteur.tarif_base` existant. Retourner None est le
        # comportement CORRECT, jamais un coût inventé.
        return None


def providers_configures(company):
    """Connecteurs transporteur disponibles pour cette société.

    Toujours au moins le NoOp. Chaque ``IntegrationConfig`` ACTIF de type
    ``transport`` dont le connecteur est enregistré ET configuré (secret
    présent) s'ajoute à la liste. Sans configuration : uniquement le NoOp —
    dégradation gracieuse, zéro appel externe.

    Renvoie une liste de ``(code, provider)``.
    """
    from core.integrations import provider_from_config
    from core.models import IntegrationConfig

    out = [(NoOpProvider.code, NoOpProvider())]
    if company is None:
        return out
    configs = IntegrationConfig.objects.filter(
        company=company, integration_type=TYPE_TRANSPORT, actif=True)
    for config in configs:
        provider = provider_from_config(config)
        if provider is None or not provider.is_configured():
            # Clé absente ou connecteur inconnu → on l'ignore SILENCIEUSEMENT
            # (gating : jamais d'erreur, jamais d'appel réseau à vide).
            continue
        if provider.code == NoOpProvider.code:
            continue
        out.append((provider.code, provider))
    return out


def provider_pour_societe(company, code):
    """Connecteur ``code`` pour cette société, ou le NoOp en repli.

    Un code inconnu ou non configuré retombe TOUJOURS sur le NoOp : une
    expédition ne peut pas être bloquée par une intégration absente.
    """
    for provider_code, provider in providers_configures(company):
        if provider_code == code:
            return provider
    return NoOpProvider()
