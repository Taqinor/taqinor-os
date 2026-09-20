"""NTI18N4 — résolution de la langue de SORTIE d'un document (devis PDF,
facture, BL, PV…), INDÉPENDANTE de la langue d'INTERFACE de l'utilisateur qui
le génère (NTI18N3, ``CustomUser.langue_interface``) : un commercial
francophone génère très bien un devis arabe pour un client arabophone.

Ordre de priorité (le premier trouvé gagne) :
    1. langue EXPLICITE du document (ex. ``?langue=`` de ``/proposal`` — un
       choix ponctuel, écrase tout) ;
    2. ``Client.langue_document`` (préférence du CLIENT, apps.crm) — seulement
       quand elle DIFFÈRE du défaut déclaré par le modèle : ce champ est NON
       NULL et pré-rempli à la création, donc une valeur égale au défaut ne
       prouve aucun choix et ne doit pas masquer le repli société (3) ;
    3. langue par défaut de la SOCIÉTÉ (``CompanyProfile.langue_repli``,
       NTI18N34 — lu défensivement via ``getattr``/import tardif, y compris
       pour une société créée avant l'arrivée de ce champ : le défaut FR du
       modèle préserve alors le comportement historique) ;
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


def _defaut_du_champ(client, nom_champ='langue_document'):
    """Valeur par DÉFAUT déclarée par le modèle pour ``nom_champ``, ou ``None``.

    Lue par introspection du modèle (jamais un ``'fr'`` recodé ici) : le jour
    où ``crm.Client`` change ce défaut, cette fonction suit. Défensive comme le
    reste du module : un objet sans ``_meta`` ni ce champ (duck-typing des
    appelants historiques, objets de test) rend ``None``, et AUCUNE valeur
    n'est alors considérée comme « le défaut ».
    """
    try:
        champ = client._meta.get_field(nom_champ)
    except Exception:  # noqa: BLE001 — jamais bloquant pour un rendu PDF
        return None
    defaut = getattr(champ, 'default', None)
    # ``TextChoices`` : le défaut est un membre d'énum (sous-classe de ``str``)
    # — on compare sur sa VALEUR, comme celle lue en base.
    return _valide(getattr(defaut, 'value', defaut))


def _preference_client(client):
    """Langue VOULUE par le client, ou ``None`` s'il n'en exprime aucune.

    ``crm.Client.langue_document`` est NON NULL et vaut son défaut modèle
    (``'fr'``) dès la création : la valeur stockée ne distingue donc pas « ce
    client a demandé le français » de « personne n'a jamais touché ce
    réglage ». La lire telle quelle faisait court-circuiter l'étape SUIVANTE de
    la chaîne — le repli de la SOCIÉTÉ (NTI18N34) — pour tout client créé sans
    préférence : une société qui avait choisi l'arabe regénérait quand même des
    documents français.

    Une valeur ÉGALE au défaut du modèle est donc traitée comme ABSENTE et la
    chaîne continue. Sans société, ou avec une société restée au défaut, elle
    aboutit de toute façon à ``LANGUE_PAR_DEFAUT`` : le résultat d'hier, à
    l'identique. Une préférence RÉELLEMENT différente (``'ar'``) reste, elle,
    prioritaire sur le repli société.
    """
    langue = _valide(getattr(client, 'langue_document', None))
    if not langue:
        return None
    defaut = _defaut_du_champ(client)
    if defaut is not None and langue == defaut:
        return None
    return langue


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

    client_langue = _preference_client(client)
    if client_langue:
        return client_langue

    if company is not None:
        # NTI18N34 : ``CompanyProfile.langue_repli``. Import tardif +
        # best-effort : aucune exception ne doit jamais atteindre un
        # appelant de génération de PDF (même une société d'avant NTI18N34,
        # sans le champ en base, ne peut jamais faire lever cette fonction).
        try:
            from apps.parametres.models_company import CompanyProfile
            profile = CompanyProfile.get(company)
            company_langue = _valide(getattr(profile, 'langue_repli', None))
            if company_langue:
                return company_langue
        except Exception:  # noqa: BLE001 — jamais bloquant pour un rendu PDF
            pass

    return LANGUE_PAR_DEFAUT
