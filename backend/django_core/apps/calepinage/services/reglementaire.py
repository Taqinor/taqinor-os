"""CAL191 — les DOSSIERS RÉGLEMENTAIRES : préremplis, jamais inventés.

LE CONSTAT ET LA DOCTRINE REPRISE
----------------------------------
La fabrique AO ÉCHOUE plutôt que d'inventer
(``apps/ao/fabrique/rendus/note_calcul.py``) : c'est la bonne doctrine pour
une note de calcul. Ici la pièce est ADMINISTRATIVE, donc elle doit rester
REMPLISSABLE — mais sans jamais qu'une valeur par défaut ne se déguise en
donnée. D'où la règle unique de ce module :

    une donnée RÉELLE est servie ; toute autre est marquée « à compléter ».

Ce que le serveur peut préremplir, et RIEN d'autre : identité de la société,
client, adresse, puissance en kWc, nombre de modules, orientation et
inclinaison — toutes lues sur le calepinage lui-même. Un champ dont la source
est absente sort avec ``valeur = null`` et son message : l'écran n'affiche
alors AUCUNE valeur, il n'en devine pas (contrat ``dossiers_reglementaires``
de CAL247).

CE MODULE NE FABRIQUE AUCUN FORMULAIRE OFFICIEL
-----------------------------------------------
L'intitulé du dossier, la liste de ses pièces et la référence de chacune
viennent du GABARIT DÉPOSÉ par la société (CAL190). Une société sans gabarit
ne voit AUCUN dossier — et un gabarit déclaré dont le fichier n'a pas été
déposé reste VISIBLE, avec ``gabarit.present = false`` et le motif en clair :
le masquer ferait croire que le dossier n'existe pas, alors que c'est le
FICHIER qui manque.

LA FORME EST PURE, LA BASE EST UN DÉTAIL
-----------------------------------------
``composer_dossiers`` ne connaît que des dictionnaires : c'est elle qui porte
la règle, et elle se teste sans base. ``dossiers_du_calepinage`` n'est que la
couche qui lit l'ORM et l'appelle.
"""
from __future__ import annotations

#: Les états d'une pièce, tels que le contrat CAL247 les nomme.
ETAT_FOURNIE = 'fournie'
ETAT_A_COMPLETER = 'a_completer'
ETAT_MANQUANTE = 'manquante'

#: Les statuts d'un dossier.
STATUT_GABARIT_MANQUANT = 'gabarit_manquant'
STATUT_INCOMPLET = 'incomplet'
STATUT_COMPLET = 'complet'

#: Le message servi quand la société n'a DÉPOSÉ aucun gabarit — il dit quoi
#: faire, et il ne propose aucun dossier fictif en attendant.
MESSAGE_AUCUN_GABARIT = (
    "Aucun gabarit de dossier réglementaire n'a été déposé pour cette "
    "société : aucun dossier n'est proposé. Déposez un gabarit dans les "
    "réglages du module pour en voir apparaître un."
)

MOTIF_GABARIT_ABSENT = (
    "Le fichier de gabarit de la société n'a pas été déposé : l'ERP ne "
    "fabrique aucun formulaire officiel qu'il n'a pas reçu."
)

MESSAGE_CHAMP_SANS_SOURCE = (
    "Aucune valeur n'est préremplie : le serveur n'a rien à proposer pour ce "
    "champ."
)

__all__ = [
    'ETAT_FOURNIE', 'ETAT_A_COMPLETER', 'ETAT_MANQUANTE',
    'MESSAGE_AUCUN_GABARIT', 'composer_dossiers', 'infos_du_calepinage',
    'dossiers_du_calepinage',
]


# ── la règle, PURE ─────────────────────────────────────────────────────────

def _valeur_reelle(valeur):
    """Une valeur SERVIE, ou ``None`` — une chaîne blanche vaut inconnu."""
    if valeur is None:
        return None
    if isinstance(valeur, str):
        valeur = valeur.strip()
        return valeur or None
    return valeur


def _champ_a_completer(champ, saisis, infos):
    """Un champ du gabarit, avec la seule valeur RÉELLE que le serveur a.

    Renvoie ``None`` quand l'utilisateur l'a déjà saisi : « à compléter » ne
    liste que ce qui reste à faire.
    """
    code = str(champ.get('code') or '').strip()
    if not code:
        return None
    saisie = _valeur_reelle((saisis or {}).get(code))
    if saisie is not None:
        return None
    cle = champ.get('cle_calepinage')
    valeur = _valeur_reelle((infos or {}).get(cle)) if cle else None
    return {
        'code': code,
        'libelle': str(champ.get('libelle') or code),
        'type': str(champ.get('type') or 'texte'),
        'valeur': valeur,
        'obligatoire': bool(champ.get('obligatoire')),
        'message': ('' if valeur is not None else MESSAGE_CHAMP_SANS_SOURCE),
    }


def _piece(piece, jointes, gabarit):
    """Une pièce du gabarit, avec son ÉTAT et sa SOURCE (jamais inventée)."""
    code = str(piece.get('code') or '').strip()
    jointe = (jointes or {}).get(code)
    jointe = jointe if isinstance(jointe, dict) else None
    obligatoire = bool(piece.get('obligatoire'))
    if jointe:
        etat, message = ETAT_FOURNIE, ''
    elif obligatoire:
        etat = ETAT_A_COMPLETER
        message = "Cette pièce obligatoire n'a pas encore été jointe."
    else:
        etat = ETAT_MANQUANTE
        message = "Aucun fichier n'a été joint à cette pièce."
    source_type = str(piece.get('source_type') or '').strip() or (
        'gabarit_societe' if gabarit.get('present') else 'saisie_societe')
    return {
        'code': code,
        'intitule': str(piece.get('intitule') or code),
        'etat': etat,
        'obligatoire': obligatoire,
        'fichier': (jointe or {}).get('fichier'),
        'fichier_url': (jointe or {}).get('fichier_url'),
        'message': message,
        'source': {
            'type': source_type,
            'gabarit_id': gabarit.get('id'),
            'fichier': gabarit.get('fichier'),
            'depose_le': gabarit.get('depose_le'),
            # La RÉFÉRENCE saisie par la société avec sa pièce — jamais une
            # référence reproduite de mémoire par l'ERP (CAL190).
            'reference': piece.get('source_reference'),
        },
    }


def composer_dossier(entree, infos):
    """UN dossier au format du contrat CAL247, depuis des dictionnaires.

    Args:
        entree: ``{id, gabarit_id, intitule, gabarit:{present, fichier,
            depose_le, depose_par, version}, pieces_attendues, champs,
            champs_saisis, pieces_jointes, genere_le}``.
        infos: les données RÉELLES du calepinage (``infos_du_calepinage``).
    """
    gabarit = dict(entree.get('gabarit') or {})
    gabarit.setdefault('id', entree.get('gabarit_id'))
    present = bool(gabarit.get('present'))
    saisis = entree.get('champs_saisis') or {}
    jointes = entree.get('pieces_jointes') or {}

    pieces = [_piece(piece, jointes, gabarit)
              for piece in (entree.get('pieces_attendues') or [])
              if isinstance(piece, dict)] if present else []
    champs = [champ for champ in (
        _champ_a_completer(champ, saisis, infos)
        for champ in (entree.get('champs') or []) if isinstance(champ, dict)
    ) if champ is not None] if present else []

    champs_bloquants = [c for c in champs
                        if c['obligatoire'] and c['valeur'] is None]
    pieces_bloquantes = [p for p in pieces
                         if p['obligatoire'] and p['etat'] != ETAT_FOURNIE]
    peut_generer = present and not champs_bloquants and not pieces_bloquantes
    if not present:
        statut, motif = STATUT_GABARIT_MANQUANT, MOTIF_GABARIT_ABSENT
    elif peut_generer:
        statut, motif = STATUT_COMPLET, ''
    else:
        statut = STATUT_INCOMPLET
        motif = _motif(champs_bloquants, pieces_bloquantes)
    return {
        'id': entree.get('id'),
        'gabarit_id': gabarit.get('id'),
        'intitule': str(entree.get('intitule') or ''),
        'statut': statut,
        'gabarit': {
            'present': present,
            'fichier': gabarit.get('fichier'),
            'depose_le': gabarit.get('depose_le'),
            'depose_par': gabarit.get('depose_par'),
            'version': gabarit.get('version'),
        },
        'pieces': pieces,
        'champs_a_completer': champs,
        'peut_generer': peut_generer,
        'motif_non_generable': motif,
        'genere_le': entree.get('genere_le'),
    }


def _motif(champs, pieces):
    """Le motif EN FRANÇAIS, qui NOMME ce qui manque (jamais « erreur »)."""
    morceaux = []
    if champs:
        morceaux.append(
            'champs obligatoires à compléter : '
            + ', '.join(champ['libelle'] for champ in champs))
    if pieces:
        morceaux.append(
            'pièces obligatoires non fournies : '
            + ', '.join(piece['intitule'] for piece in pieces))
    if not morceaux:
        return ''
    # Majuscule sur la PREMIÈRE lettre seulement : ``capitalize()`` mettrait
    # tout le reste en minuscules et abîmerait les libellés de la société.
    phrase = ' ; '.join(morceaux)
    return phrase[:1].upper() + phrase[1:] + '.'


def composer_dossiers(*, calepinage_id, pays, entrees, infos):
    """L'agrégat COMPLET du contrat ``dossiers_reglementaires.json``.

    Une société SANS gabarit reçoit une liste VIDE (pas un dossier fantôme)
    et le message qui dit quoi déposer.
    """
    entrees = list(entrees or [])
    return {
        'calepinage': calepinage_id,
        'pays': (pays or '').upper() or None,
        'gabarits_deposes': len(entrees),
        'message_aucun_gabarit': (None if entrees else MESSAGE_AUCUN_GABARIT),
        'dossiers': [composer_dossier(entree, infos) for entree in entrees],
    }


# ── la couche qui lit la base ──────────────────────────────────────────────

def infos_du_calepinage(calepinage):
    """Les données RÉELLES qu'un gabarit peut demander à préremplir.

    Aucune n'est calculée « au mieux » : une donnée absente vaut ``None`` et
    le champ qui la demandait sortira « à compléter ».
    """
    from .production import pans_du_layout

    company = getattr(calepinage, 'company', None)
    client = getattr(calepinage, 'client', None)
    pans = pans_du_layout(getattr(calepinage, 'roof_layout', None))
    modules = sum(int(pan.get('modules') or 0) for pan in pans)
    kwc = [pan.get('kwc') for pan in pans if pan.get('kwc') is not None]
    domine = max(pans, key=lambda pan: int(pan.get('modules') or 0),
                 default=None)
    return {
        'societe_nom': _valeur_reelle(getattr(company, 'nom', None)),
        'client_nom': _valeur_reelle(getattr(client, 'nom', None)),
        'adresse': _valeur_reelle(getattr(client, 'adresse', None)),
        'puissance_kwc': (sum(kwc) if kwc else None),
        'nombre_modules': (modules or None),
        'orientation_deg': (domine or {}).get('azimut_deg'),
        'inclinaison_deg': (domine or {}).get('inclinaison_deg'),
    }


def _entree_depuis_orm(gabarit, dossier):
    depose_par = gabarit.depose_par
    fichier = gabarit.fichier
    return {
        'id': dossier.pk if dossier is not None else None,
        'gabarit_id': gabarit.pk,
        'intitule': gabarit.intitule,
        'gabarit': {
            'id': gabarit.pk,
            'present': gabarit.fichier_present,
            'fichier': getattr(fichier, 'filename', None) or getattr(
                fichier, 'nom', None),
            'depose_le': gabarit.depose_le,
            'depose_par': ({'id': depose_par.pk,
                            'nom_complet': str(depose_par)}
                           if depose_par is not None else None),
            'version': gabarit.version or None,
        },
        'pieces_attendues': gabarit.pieces_attendues or [],
        'champs': gabarit.champs or [],
        'champs_saisis': (dossier.champs_saisis if dossier is not None
                          else {}),
        'pieces_jointes': (dossier.pieces_jointes if dossier is not None
                           else {}),
        'genere_le': (dossier.genere_le if dossier is not None else None),
    }


def dossiers_du_calepinage(calepinage, *, pays=None):
    """Les dossiers réglementaires d'un calepinage — LECTURE PURE.

    Aucune écriture : un GET qui crée une ligne en base est un GET qui ment.
    Un dossier pas encore ouvert sort avec ``id = null`` — l'écran sait alors
    qu'il n'a jamais été commencé.
    """
    from ..models import DossierReglementaire, GabaritDossierReglementaire
    from ..selectors import imagerie_site

    company = getattr(calepinage, 'company', None)
    if pays is None:
        pays = (imagerie_site(company) or {}).get('pays')
    if company is None or not pays:
        # Sans société ni pays de projet, aucun gabarit ne peut être choisi :
        # on ne DEVINE pas un pays (le fournisseur d'imagerie et le pays sont
        # un réglage société, CAL47).
        return composer_dossiers(
            calepinage_id=getattr(calepinage, 'pk', None), pays=pays,
            entrees=[], infos={})

    gabarits = list(GabaritDossierReglementaire.objects
                    .filter(company=company, pays=pays, actif=True)
                    .select_related('fichier', 'depose_par')
                    .order_by('intitule', 'id'))
    dossiers = {d.gabarit_id: d for d in DossierReglementaire.objects
                .filter(company=company, calepinage=calepinage)}
    infos = infos_du_calepinage(calepinage)
    entrees = [_entree_depuis_orm(gabarit, dossiers.get(gabarit.pk))
               for gabarit in gabarits]
    return composer_dossiers(calepinage_id=calepinage.pk, pays=pays,
                             entrees=entrees, infos=infos)
