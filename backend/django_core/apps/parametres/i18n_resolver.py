"""NTI18N4 — résolution de la langue de SORTIE d'un document (devis PDF,
facture, BL, PV…), INDÉPENDANTE de la langue d'INTERFACE de l'utilisateur qui
le génère (NTI18N3, ``CustomUser.langue_interface``) : un commercial
francophone génère très bien un devis arabe pour un client arabophone.

Ordre de priorité (le premier trouvé gagne) :
    1. langue EXPLICITE du document (ex. ``?langue=`` de ``/proposal`` — un
       choix ponctuel, écrase tout) ;
    2. ``Client.langue_document`` (préférence du CLIENT, apps.crm) ;
    3. langue par défaut de la SOCIÉTÉ (``CompanyProfile.langue_repli``,
       NTI18N34 — lu défensivement via ``getattr``/import tardif : ce champ
       N'EXISTE PAS ENCORE, cette fonction reste correcte avant ET après son
       arrivée, sans modification) ;
    4. FR (repli de dernier recours, comportement historique inchangé).

Ne renvoie JAMAIS autre chose qu'une des langues supportées par le cadre i18n
léger (fr/en/ar, cf. ``frontend/src/i18n/resolve.py`` ``LOCALES``) — une
valeur inconnue à n'importe quel niveau de la chaîne est traitée comme absente
(défense en profondeur, jamais une langue arbitraire qui atteindrait un
gabarit).

Consommée par l'endpoint ``/proposal`` (query param optionnel ``?langue=``
qui écrase la résolution auto — voir ``apps.ventes.views.devis.DevisViewSet.
proposal``) et par les PDF factures/BL/PV existants (``apps.ventes.utils.
libelles_ar.document_langue``, généralisée ici avec un repli société et un
override explicite qu'elle n'avait pas). JAMAIS un second moteur de rendu
(règle #4 fondateur) : cette fonction ne fait QUE calculer une valeur — le
moteur ``/proposal`` et les gabarits WeasyPrint existants restent seuls
maîtres du choix de leur propre dictionnaire de libellés (NTI18N5 pour le
moteur premium).
"""
from __future__ import annotations

#: Langues supportées par le cadre i18n léger (fr/en/ar). Toute valeur hors
#: de cette liste, à n'importe quel niveau de la chaîne de priorité, est
#: ignorée comme si elle était absente.
LANGUES_SUPPORTEES = ('fr', 'en', 'ar')

#: Repli de tout dernier recours — comportement historique de tous les
#: appelants existants avant cette tâche.
LANGUE_PAR_DEFAUT = 'fr'


def _valide(langue):
    """Renvoie ``langue`` si elle fait partie du vocabulaire supporté,
    ``None`` sinon (traite une valeur vide/inconnue comme absente)."""
    return langue if langue in LANGUES_SUPPORTEES else None


def resolve_langue_sortie(*, langue_explicite=None, client=None, company=None) -> str:
    """Résout la langue de sortie d'un document.

    Tous les arguments sont optionnels et nommés — un appel sans rien renvoie
    toujours ``'fr'`` (comportement historique). ``client`` est typiquement
    une instance ``apps.crm.models.Client`` (lit ``langue_document``), mais
    accepte tout objet compatible (``getattr`` défensif — jamais d'exception
    si le champ est absent). ``company`` est une ``authentication.Company``.
    """
    explicite = _valide(langue_explicite)
    if explicite:
        return explicite

    client_langue = _valide(getattr(client, 'langue_document', None))
    if client_langue:
        return client_langue

    if company is not None:
        # NTI18N34 (pas encore construit) : ``CompanyProfile.langue_repli``.
        # Import tardif + best-effort : aucune dépendance dure sur un champ
        # qui n'existe pas encore, aucune exception ne doit jamais atteindre
        # un appelant de génération de PDF.
        try:
            from apps.parametres.models_company import CompanyProfile
            profile = CompanyProfile.get(company)
            company_langue = _valide(getattr(profile, 'langue_repli', None))
            if company_langue:
                return company_langue
        except Exception:  # noqa: BLE001 — jamais bloquant pour un rendu PDF
            pass

    return LANGUE_PAR_DEFAUT
