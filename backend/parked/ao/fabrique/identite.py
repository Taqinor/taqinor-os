"""AOF144 — marque blanche de premier rang : soumissionnaire ≠ bureau.

Deux rôles, deux identités légales. La règle est binaire :

* **un rendu CLIENT n'utilise QUE le soumissionnaire** ;
* quand la marque blanche est active, la société propriétaire de l'ERP (le
  bureau d'exécution) n'apparaît **nulle part** dans un artefact remis au
  maître d'ouvrage.

Le bureau d'exécution n'est pas re-modélisé : sans enregistrement
``IdentiteAO`` explicite, il est lu par ``parametres.selectors.company_identity``
(lecture cross-app par SELECTOR, jamais un import de modèles). C'est ce qui
garantit qu'aucun champ d'identité n'est dupliqué avec
``authentication.Company`` / ``parametres.CompanyProfile``.

:func:`controler_absence_du_bureau` est le test BINAIRE branché au ratchet
AOF129 : il refuse un artefact client qui nomme le bureau.
"""
from __future__ import annotations

__all__ = [
    'CHAMPS_IDENTITE',
    'controler_absence_du_bureau',
    'identite_bureau',
    'identite_client',
    'identite_soumissionnaire',
    'marque_blanche_active',
    'noms_a_masquer',
]

#: Champs d'identité exposés au rendu (mêmes clés quelle que soit la source).
CHAMPS_IDENTITE = (
    'raison_sociale', 'ice', 'identifiant_fiscal', 'registre_commerce',
    'adresse', 'signataire_nom', 'signataire_qualite', 'rib',
    'mentions_legales', 'logo_id',
)


def _vide():
    return {champ: '' for champ in CHAMPS_IDENTITE}


def _depuis_modele(identite):
    return {
        'raison_sociale': identite.raison_sociale or '',
        'ice': identite.ice or '',
        'identifiant_fiscal': identite.identifiant_fiscal or '',
        'registre_commerce': identite.registre_commerce or '',
        'adresse': identite.adresse or '',
        'signataire_nom': identite.signataire_nom or '',
        'signataire_qualite': identite.signataire_qualite or '',
        'rib': identite.rib or '',
        'mentions_legales': identite.mentions_legales or '',
        'logo_id': identite.logo_id or '',
    }


def _identite_declaree(appel_offre, role):
    from ..models import IdentiteAO

    return IdentiteAO.objects.filter(
        company=appel_offre.company, appel_offre=appel_offre,
        role=role).first()


def marque_blanche_active(appel_offre):
    """Vrai si le dossier est déposé sous une identité TIERCE."""
    return bool(getattr(appel_offre, 'marque_blanche', False))


def identite_soumissionnaire(appel_offre):
    """Identité du DÉPOSANT — celle qui figure sur les pièces remises.

    Repli, dans l'ordre : l'``IdentiteAO`` déclarée, puis le champ texte
    ``AppelOffre.soumissionnaire``, puis l'identité du bureau (dépôt en nom
    propre : les deux rôles se confondent, et c'est légitime).
    """
    declaree = _identite_declaree(
        appel_offre, 'soumissionnaire')
    if declaree is not None:
        return _depuis_modele(declaree)
    if appel_offre.soumissionnaire:
        identite = _vide()
        identite['raison_sociale'] = appel_offre.soumissionnaire
        return identite
    return identite_bureau(appel_offre)


def identite_bureau(appel_offre):
    """Identité du BUREAU D'EXÉCUTION — jamais dans un rendu client.

    Sans ``IdentiteAO`` déclarée, elle est LUE (jamais recopiée) via
    ``parametres.selectors.company_identity``.
    """
    declaree = _identite_declaree(appel_offre, 'bureau_execution')
    if declaree is not None:
        return _depuis_modele(declaree)
    from apps.parametres import selectors as parametres_selectors

    profil = parametres_selectors.company_identity(appel_offre.company)
    identite = _vide()
    identite.update({
        'raison_sociale': profil.get('nom') or appel_offre.company.nom,
        'ice': profil.get('ice', ''),
        'identifiant_fiscal': profil.get('identifiant_fiscal', ''),
        'registre_commerce': profil.get('rc', ''),
        'adresse': profil.get('adresse', ''),
        'rib': profil.get('rib', ''),
    })
    return identite


def identite_client(appel_offre):
    """L'identité à utiliser dans TOUT rendu remis au maître d'ouvrage.

    C'est le soumissionnaire, toujours. Une pièce client ne connaît pas le
    bureau d'exécution : c'est ce qui rend la bascule marque blanche ON/OFF
    sûre par construction plutôt que par vigilance.
    """
    return identite_soumissionnaire(appel_offre)


def noms_a_masquer(appel_offre):
    """Les dénominations du BUREAU qui ne doivent pas fuir en marque blanche.

    Liste vide quand la marque blanche n'est pas active (le bureau EST le
    soumissionnaire, le nommer est normal).
    """
    if not marque_blanche_active(appel_offre):
        return []
    bureau = identite_bureau(appel_offre)
    client = identite_client(appel_offre)
    candidats = {
        (bureau.get('raison_sociale') or '').strip(),
        (appel_offre.company.nom or '').strip(),
    }
    protege = (client.get('raison_sociale') or '').strip().lower()
    return sorted(
        nom for nom in candidats
        if nom and nom.lower() != protege)


def controler_absence_du_bureau(texte, appel_offre):
    """Test BINAIRE : le bureau est-il nommé dans cet artefact client ?

    Renvoie la liste des dénominations trouvées (vide = artefact propre).
    Branché au ratchet AOF129 : un rendu client qui nomme le bureau est
    REFUSÉ, jamais « signalé pour relecture ».
    """
    minuscule = (texte or '').lower()
    return [nom for nom in noms_a_masquer(appel_offre)
            if nom.lower() in minuscule]
