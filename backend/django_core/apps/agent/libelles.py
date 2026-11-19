"""COP-G4 + copilote vague 2 (FND8) — libellés des objets désignés par l'assistant.

Un type d'objet (``registry.OBJETS``) -> le résolveur de l'app qui le possède,
importé PARESSEUSEMENT par son chemin (jamais un import de ses modèles) :
``libelles_<app>(user, **{type: id}) -> {type: libellé}``, la forme de
``libelles_crm`` / ``libelles_ventes``. Tant qu'une app n'a pas encore son
``selectors_libelles.py`` (lanes de la vague 2B), ses types sont simplement
ABSENTS de la réponse — jamais une erreur. ``utilisateur`` est résolu ici
(fondation : un compte de la même société, prénom et nom seulement).
"""
from __future__ import annotations

import importlib

#: type -> (module, fonction) du résolveur. Un objet inconnu, d'une autre
#: société ou hors portée est ABSENT de ce que rend le résolveur.
RESOLVEURS = {
    'lead': ('apps.crm.selectors_libelles', 'libelles_crm'),
    'touche': ('apps.crm.selectors_libelles', 'libelles_crm'),
    'client': ('apps.crm.selectors_libelles', 'libelles_crm'),
    'devis': ('apps.ventes.selectors_libelles', 'libelles_ventes'),
    'facture': ('apps.ventes.selectors_libelles', 'libelles_ventes'),
    'calepinage': ('apps.calepinage.selectors_libelles', 'libelles_calepinage'),
    'variante': ('apps.calepinage.selectors_libelles', 'libelles_calepinage'),
    'visite': ('apps.visites.selectors_libelles', 'libelles_visites'),
    'chantier': ('apps.installations.selectors_libelles', 'libelles_installations'),
    'intervention': ('apps.installations.selectors_libelles', 'libelles_installations'),
    'ticket': ('apps.sav.selectors_libelles', 'libelles_sav'),
    'equipement': ('apps.sav.selectors_libelles', 'libelles_sav'),
    'produit': ('apps.stock.selectors_libelles', 'libelles_stock'),
    'bcf': ('apps.stock.selectors_libelles', 'libelles_stock'),
    'fournisseur': ('apps.stock.selectors_libelles', 'libelles_stock'),
}
UTILISATEUR = 'utilisateur'
#: Tous les types résolus (ordre stable : paramètres de la route).
TYPES = tuple(RESOLVEURS) + (UTILISATEUR,)


def _resolveur(module: str, nom: str):
    """La fonction, ou None si le MODULE lui-même n'existe pas encore (une
    erreur d'import À L'INTÉRIEUR du module reste une erreur)."""
    try:
        return getattr(importlib.import_module(module), nom)
    except ModuleNotFoundError as exc:
        if exc.name and module.startswith(exc.name):
            return None
        raise


def _libelle_utilisateur(user, ident: int) -> dict:
    """« Prénom Nom » d'un compte ACTIF de la même société ; jamais son e-mail,
    son identifiant de connexion ni son rôle."""
    from django.contrib.auth import get_user_model

    company_id = getattr(user, 'company_id', None)
    if not company_id:
        return {}
    compte = get_user_model().objects.filter(
        pk=ident, company_id=company_id, is_active=True).only('first_name', 'last_name').first()
    nom = ' '.join(p for p in ((compte.first_name or '').strip(), (compte.last_name or '').strip())
                   if p) if compte else ''
    return {UTILISATEUR: nom} if nom else {}


def libelles_objets(user, ids: dict) -> dict:
    """``{type: libellé}`` pour ``ids`` (``{type: entier}``) — un appel par
    résolveur, avec seulement SES types."""
    groupes: dict = {}
    for type_objet, ident in ids.items():
        if type_objet in RESOLVEURS:
            groupes.setdefault(RESOLVEURS[type_objet], {})[type_objet] = ident
    sortie: dict = {}
    for (module, nom), demandes in groupes.items():
        fonction = _resolveur(module, nom)
        if fonction is not None:
            sortie.update(fonction(user, **demandes))
    if UTILISATEUR in ids:
        sortie.update(_libelle_utilisateur(user, ids[UTILISATEUR]))
    return sortie
