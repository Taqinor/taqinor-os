"""Copilote vague 2 (CALA1) — libellés des objets Calepinage (calepinage,
variante) nommés dans l'aperçu d'une proposition de l'assistant, pour
``GET /api/django/agent/libelles/`` et ``erp.ouvrir`` (résolveur
``libelles_calepinage`` de la table ``apps/agent/libelles.py``).

Lecture seule, bornée par LE prédicat d'accès du module
(``selectors.calepinages_visibles`` : société, portée du rôle, vue restreinte
au responsable) et par le droit de LIRE un calepinage (``calepinage_voir``,
la garde des routes). Un objet inconnu, d'une autre société ou hors de la vue
de l'utilisateur est ABSENT du résultat, jamais une erreur ni un indice de son
existence. Jamais un prix, une mesure ni un téléphone : une référence, le nom
du lead (ou le titre du calepinage) et le nom d'une variante.
"""


def _joindre(*morceaux):
    return ' — '.join(m for m in ((x or '').strip() for x in morceaux) if m)


def _nom_du_lead(calepinage):
    """« Prénom Nom » du lead du calepinage (lu par ``crm.selectors``), sinon
    le titre du calepinage ; chaîne vide quand rien n'est connu."""
    from apps.crm.selectors import get_company_lead

    lead = (get_company_lead(calepinage.company, calepinage.lead_id)
            if calepinage.lead_id else None)
    if lead is not None:
        nom = ' '.join(p for p in ((lead.prenom or '').strip(),
                                   (lead.nom or '').strip()) if p)
        if nom:
            return nom
    return (calepinage.titre or '').strip()


def libelle_calepinage(calepinage):
    """« CAL-2611-0012 — Karim Alami » : la référence dérivée, puis le nom."""
    from .services.presentation import reference_calepinage

    return _joindre(reference_calepinage(calepinage), _nom_du_lead(calepinage))


def libelles_calepinage(user, *, calepinage=None, variante=None):
    """``{'calepinage': …, 'variante': …}`` pour les identifiants donnés qui
    existent dans la vue de ``user`` (les autres clés manquent)."""
    from core.permissions import _user_has_or_legacy

    from .models import CalepinageVariante
    from .permissions import CAL_VOIR
    from .selectors import calepinages_visibles

    if getattr(user, 'company_id', None) is None \
            or not _user_has_or_legacy(user, CAL_VOIR):
        return {}
    visibles = calepinages_visibles(user, inclure_archives=True)
    out = {}
    if calepinage:
        trouve = visibles.filter(pk=calepinage).first()
        if trouve is not None:
            out['calepinage'] = libelle_calepinage(trouve)
    if variante:
        trouvee = (CalepinageVariante.objects
                   .filter(pk=variante, calepinage__in=visibles)
                   .select_related('calepinage').first())
        if trouvee is not None:
            from .services.presentation import reference_calepinage

            nom = (trouvee.nom or '').strip()
            out['variante'] = (f'« {nom} » ({reference_calepinage(trouvee.calepinage)})'
                               if nom else reference_calepinage(trouvee.calepinage))
    return out
