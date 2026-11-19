"""Copilote vague 2 — libellés des chantiers et des interventions nommés dans
l'aperçu d'une proposition de l'assistant, pour ``GET
/api/django/agent/libelles/`` et ``erp.ouvrir`` (résolveur
``libelles_installations`` de la table ``apps/agent/libelles.py``).

Lecture seule, bornée à la SOCIÉTÉ, au droit de LIRE le module installations
(``LectureDuModule`` des listes) et à la PORTÉE des listes
(``chantiers_visibles`` / ``interventions_visibles``, les sélecteurs de
``InstallationViewSet`` et ``InterventionViewSet``). Plus strict que l'écran
sur un seul point, sans rien ouvrir : un lecteur entré par l'octroi
``ventes_voir`` (sans code installations) ne reçoit aucun libellé. Un objet
inconnu, d'une autre société ou hors portée est ABSENT ; jamais un montant,
une adresse ni un téléphone : une référence, un nom, une ville, une date.
"""


def _chantier_en_clair(chantier):
    """« CHT-202611-0012 — Benali, Casablanca (Signé) »."""
    client = (chantier.client.nom or '').strip() if chantier.client_id else ''
    lieu = ', '.join(p for p in (client, (chantier.site_ville or '').strip()) if p)
    tete = ' — '.join(p for p in (chantier.reference, lieu) if p)
    return f'{tete} ({chantier.get_statut_display()})'


def _intervention_en_clair(intervention):
    """« Contrôle — chantier CHT-202611-0012, 25/11/2026 »."""
    from core.formats_fr import formater_date

    quand = formater_date(intervention.date_prevue)
    ou = f'chantier {intervention.installation.reference}'
    return f'{intervention.get_type_intervention_display()} — ' + (
        f'{ou}, {quand}' if quand else ou)


def libelles_installations(user, *, chantier=None, intervention=None):
    """``{'chantier': …, 'intervention': …}`` pour les identifiants donnés que
    ``user`` voit (les autres clés manquent)."""
    from authentication.permissions import peut_lire_module

    from .selectors import chantiers_visibles, interventions_visibles

    if (getattr(user, 'company_id', None) is None
            or not peut_lire_module(user, 'installations')):
        return {}
    out = {}
    if chantier:
        trouve = (chantiers_visibles(user).filter(pk=chantier)
                  .select_related('client').first())
        if trouve is not None:
            out['chantier'] = _chantier_en_clair(trouve)
    if intervention:
        trouve = (interventions_visibles(user).filter(pk=intervention)
                  .select_related('installation').first())
        if trouve is not None:
            out['intervention'] = _intervention_en_clair(trouve)
    return out
