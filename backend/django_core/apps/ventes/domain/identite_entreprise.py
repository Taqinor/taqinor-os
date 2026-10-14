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


def divergence_ice(devis, ice_declare):
    """CIQ319 — vrai quand le Client porte DÉJÀ un ICE différent de celui
    déclaré à l'acceptation (jamais écrasé : drapeau pour le vendeur)."""
    client = getattr(devis, 'client', None)
    ice_client = ''.join(str(getattr(client, 'ice', '') or '').split())
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
    intacte, version = signature.verifier_contenu(lignes=lignes)
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
    return {
        'signee': True, 'intacte': True, 'version': version,
        'message': "Empreinte conforme : le contenu signé n'a pas changé.",
    }
