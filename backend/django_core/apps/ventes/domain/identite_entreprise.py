"""Identité d'entreprise à l'acceptation et vérificateur du sceau (VNT50, déplacé tel quel de ``domain/cycle_vie.py``).

CIQ319 / CIQ323 — le bloc ``entreprise`` d'un corps d'acceptation (commercial /
industriel) : lecture, validation (ICE par la règle EXISTANTE de
``parametres``), drapeau de divergence d'ICE. QJR144 — le vérificateur de
l'empreinte d'un devis signé. Lecture pure : aucun statut écrit (règle #4).

``cycle_vie.py`` ré-importe ces noms en bas de fichier : ``_create_esign_record``
et ``signature_entreprise`` les appellent par ce nom, et les appelants qui les
importent depuis ``apps.ventes.domain.cycle_vie`` (vues, portail, tests)
restent valides. Ce module n'importe jamais ``cycle_vie``.
"""


def _champs_signature_entreprise(entreprise):
    """CIQ319 — ``{raison_sociale, signataire_qualite, ice_declare}`` du
    bloc ``entreprise`` (contrat ``acceptation_entreprise.json``), bornés aux
    longueurs du modèle ; ``{}`` sans bloc."""
    if not isinstance(entreprise, dict):
        return {}
    return {
        'raison_sociale': str(entreprise.get('raison_sociale') or '')
        .strip()[:200],
        'signataire_qualite': str(entreprise.get('signataire_qualite') or '')
        .strip()[:150],
        'ice_declare': str(entreprise.get('ice') or '').strip()[:30],
        # ADEV95 — e-mail et attestation de pouvoir du signataire (lien
        # public ; vides / faux sur le portail et l'ERP).
        'signataire_email': str(entreprise.get('signataire_email') or '')
        .strip()[:254],
        'pouvoir_engager': entreprise.get('pouvoir_engager') is True,
    }


#: CIQ319 — modes dont l'acceptation EN LIGNE exige l'identité d'entreprise.
MODES_ACCEPTATION_ENTREPRISE = ('commercial', 'industriel')


#: Champs du bloc ``entreprise`` (contrat ``acceptation_entreprise.json``) et
#: le message 400 qui NOMME chacun.
CHAMPS_ENTREPRISE = (
    ('raison_sociale',
     "La raison sociale de l'entreprise est requise pour accepter ce devis."),
    ('signataire_qualite',
     'La qualité du signataire est requise pour accepter ce devis.'),
    ('ice', "L'ICE de l'entreprise est requis pour accepter ce devis."),
)


class EntrepriseInvalide(Exception):
    """CIQ319 — bloc ``entreprise`` refusé : ``detail`` + ``champ`` nommé
    (``entreprise.<cle>``), rendus en 400 par les vues."""

    def __init__(self, detail, champ):
        super().__init__(detail)
        self.detail = detail
        self.champ = champ


def exige_identite_entreprise(devis):
    """Vrai pour un devis commercial / industriel (règle sur le MODE)."""
    mode = str(getattr(devis, 'mode_installation', '') or '').strip().lower()
    return mode in MODES_ACCEPTATION_ENTREPRISE


def lire_entreprise_acceptation(devis, brut, *, obligatoire):
    """CIQ319/CIQ323 — le bloc ``entreprise`` d'un corps d'acceptation,
    validé, ou ``None``.

    * hors commercial / industriel : IGNORÉ (``None``, ni erreur ni écriture) ;
    * ``obligatoire`` (lien public, portail) : les trois champs requis ;
    * ICE validé par ``parametres.tax_id_validators.validate_ice_ma`` (la
      règle EXISTANTE, jamais une seconde).

    Lève :class:`EntrepriseInvalide` (détail + champ nommé)."""
    if not exige_identite_entreprise(devis):
        return None
    if brut in (None, ''):
        brut = {}
    if not isinstance(brut, dict):
        raise EntrepriseInvalide(
            'Le bloc entreprise doit être un objet.', 'entreprise')
    valeurs = {}
    for cle, message in CHAMPS_ENTREPRISE:
        valeur = brut.get(cle)
        if valeur is not None and not isinstance(valeur, (str, int)):
            raise EntrepriseInvalide(
                f'entreprise.{cle} : texte attendu.', f'entreprise.{cle}')
        valeur = str(valeur or '').strip()
        if obligatoire and not valeur:
            raise EntrepriseInvalide(message, f'entreprise.{cle}')
        valeurs[cle] = valeur
    if valeurs['ice']:
        from apps.parametres.tax_id_validators import validate_ice_ma
        verdict = validate_ice_ma(valeurs['ice'])
        if not verdict.get('valide'):
            raise EntrepriseInvalide(verdict.get('message') or 'ICE invalide.',
                                     'entreprise.ice')
    if not any(valeurs.values()):
        return None
    return valeurs


#: ADEV95 — les champs du SIGNATAIRE exigés en plus sur le LIEN PUBLIC
#: (commercial / industriel), et le message 400 qui nomme chacun.
CHAMPS_SIGNATAIRE = (
    ('signataire_nom', 'Le nom du signataire est requis pour accepter ce devis.'),
    ('signataire_email',
     "L'e-mail du signataire est requis pour accepter ce devis."),
)

#: ADEV95 — l'attestation de pouvoir, cochée explicitement (jamais par défaut).
MESSAGE_POUVOIR = ("Cochez l'attestation : vous agissez en la qualité indiquée "
                   "et avez le pouvoir d'engager la société.")


class IceDivergent(Exception):
    """ADEV95 — l'ICE déclaré diffère de celui que le Client porte déjà :
    409 ``ice_divergent`` qui nomme les deux, rien n'est écrit."""

    def __init__(self, ice_client, ice_declare):
        self.ice_client, self.ice_declare = ice_client, ice_declare
        self.detail = (
            f"L'ICE saisi ({ice_declare}) ne correspond pas à l'ICE enregistré "
            f"pour votre société ({ice_client}). Vérifiez-le ou contactez "
            "votre conseiller avant de signer.")
        super().__init__(self.detail)


def lire_signataire_lien(devis, brut, *, nom):
    """ADEV95 (D-CIQ-11) — en plus de :func:`lire_entreprise_acceptation`,
    le LIEN PUBLIC d'un devis commercial / industriel exige le nom (celui tapé
    pour signer), l'e-mail VALIDE du signataire et l'attestation de pouvoir
    (``pouvoir_engager`` booléen vrai) ; un ICE différent de celui du Client
    lève :class:`IceDivergent`. Hors C&I : ``None``. Lève
    :class:`EntrepriseInvalide` (400 qui nomme le champ)."""
    entreprise = lire_entreprise_acceptation(devis, brut, obligatoire=True)
    if entreprise is None:
        return None
    for cle, message in CHAMPS_SIGNATAIRE:
        valeur = brut.get(cle)
        if not isinstance(valeur, str) or not valeur.strip():
            raise EntrepriseInvalide(message, f'entreprise.{cle}')
        entreprise[cle] = valeur.strip()
    if _nom_normalise(entreprise['signataire_nom']) != _nom_normalise(nom):
        raise EntrepriseInvalide(
            'Le nom du signataire doit être celui que vous tapez pour signer.',
            'entreprise.signataire_nom')
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email
    try:
        validate_email(entreprise['signataire_email'])
    except ValidationError:
        raise EntrepriseInvalide("L'e-mail du signataire est invalide.",
                                 'entreprise.signataire_email') from None
    if brut.get('pouvoir_engager') is not True:
        raise EntrepriseInvalide(MESSAGE_POUVOIR, 'entreprise.pouvoir_engager')
    entreprise['pouvoir_engager'] = True
    if divergence_ice(devis, entreprise['ice']):
        raise IceDivergent(_ice_du_client(devis), entreprise['ice'])
    return entreprise


def _nom_normalise(nom):
    return ' '.join(str(nom or '').split()).casefold()


def _ice_du_client(devis):
    return ''.join(str(getattr(getattr(devis, 'client', None), 'ice', '')
                       or '').split())


def divergence_ice(devis, ice_declare):
    """CIQ319 — vrai quand le Client porte DÉJÀ un ICE différent de celui
    déclaré à l'acceptation (jamais écrasé : drapeau pour le vendeur)."""
    ice_client = _ice_du_client(devis)
    declare = ''.join(str(ice_declare or '').split())
    return bool(ice_client and declare and ice_client != declare)


def verifier_empreinte_signature(devis, *, lignes=None):
    """QJR144 — LE VÉRIFICATEUR du sceau d'un devis signé.

    ``DevisSignature.content_hash`` existait depuis QJ10 mais AUCUN code du
    dépôt ne savait le recomparer : il était écrit une fois et relu seulement
    par des tests — un sceau que personne ne pouvait vérifier. Ce service est
    la porte de lecture, exposée en cross-app par ``apps.ventes.services``.

    Rend un dict FRANÇAIS, affichable tel quel :

    * ``signee`` — ce devis porte-t-il une signature électronique ;
    * ``intacte`` — ``True`` (le contenu reproduit l'empreinte), ``False`` (il
      a changé depuis la signature), ``None`` (aucune empreinte scellée : « on
      ne sait pas » n'est pas « falsifié ») ;
    * ``version`` — la version du payload qui concorde (2 = sceau étendu de
      QJR144 ; 1 = sceau d'origine, qui ne couvrait NI le taux de TVA par
      ligne, NI les lignes optionnelles, NI l'option retenue) ;
    * ``message`` — la phrase à montrer.

    LECTURE PURE : ne touche ni statut, ni ligne, ni total (règle #4).
    """
    from apps.ventes.models import DevisSignature

    signature = DevisSignature.objects.filter(devis=devis).first()
    if signature is None:
        return {
            'signee': False, 'intacte': None, 'version': None,
            'message': "Ce devis ne porte aucune signature électronique.",
        }
    from apps.ventes.domain.modifiabilite import figures_sceau
    intacte, version = signature.verifier_contenu(
        lignes=lignes, figures=figures_sceau(devis))
    if intacte is None:
        return {
            'signee': True, 'intacte': None, 'version': None,
            'message': ("Cette signature ne porte aucune empreinte de "
                        "contenu : elle est antérieure au scellement, son "
                        "contenu ne peut donc pas être vérifié."),
        }
    if not intacte:
        return {
            'signee': True, 'intacte': False, 'version': None,
            'message': ("Le contenu de ce devis NE correspond PLUS à ce qui a "
                        "été signé : l'empreinte scellée ne se reproduit pas."),
        }
    if version == DevisSignature.CONTENT_HASH_V1:
        return {
            'signee': True, 'intacte': True, 'version': version,
            'message': ("Empreinte conforme (sceau d'origine). Portée : ce "
                        "sceau ne couvre ni le taux de TVA par ligne, ni les "
                        "lignes optionnelles, ni l'option retenue."),
        }
    if version == DevisSignature.CONTENT_HASH_V2 and exige_identite_entreprise(devis):
        # ADEV96 — un sceau v2 d'un devis C&I ne couvrait pas l'étude.
        return {
            'signee': True, 'intacte': True, 'version': version,
            'message': ("Empreinte conforme (sceau v2). Portée : ce sceau ne "
                        "couvre pas les chiffres de l'étude C&I."),
        }
    return {
        'signee': True, 'intacte': True, 'version': version,
        'message': "Empreinte conforme : le contenu signé n'a pas changé.",
    }
