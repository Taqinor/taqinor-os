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

from http import HTTPStatus

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
    # CAL192 / CAL193 — les packs pays (Maroc, France).
    'DossierRefuse', 'construire_pack_dossier', 'GENRES_FRANCE',
    'avancement_du_dossier', 'packs_france',
    # CALX41 — enregistrer les champs à compléter d'un dossier.
    'ChampsDossierInvalides', 'enregistrer_champs',
    # ACAL240 — la mention imprimée d'un champ sans valeur.
    'MENTION_A_COMPLETER',
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


def _champ_publie(champ, code, valeur, message, *, valeur_calepinage=None,
                  ecart_saisie=False):
    """La forme PUBLIÉE d'un champ de gabarit — la même dans les deux listes.

    ACAL240 — chaque champ porte aussi ``valeur_calepinage`` (ce que le
    calepinage dit, ou ``None``) et ``ecart_saisie`` (vrai quand une SAISIE
    existe et diffère de la valeur du calepinage) : l'écran peut alors
    proposer « Utiliser la valeur du calepinage » sans rien écrire de lui-même.
    """
    return {
        'code': code,
        'libelle': str(champ.get('libelle') or code),
        'type': str(champ.get('type') or 'texte'),
        'valeur': valeur,
        'obligatoire': bool(champ.get('obligatoire')),
        'message': message,
        'valeur_calepinage': valeur_calepinage,
        'ecart_saisie': bool(ecart_saisie),
    }


def _meme_valeur(saisie, reference):
    """Une saisie ÉGALE à la valeur du calepinage (nombres comparés en
    nombres : « 12,5 » saisi vaut 12.5 calculé)."""
    if saisie is None or reference is None:
        return saisie is reference
    nombre_saisi = _nombre_saisi(saisie)
    nombre_ref = _nombre_saisi(reference)
    if nombre_saisi is not None and nombre_ref is not None:
        return float(nombre_saisi) == float(nombre_ref)
    return str(saisie).strip() == str(reference).strip()


def _champs_du_gabarit(champs, saisis, infos):
    """``(à_compléter, déjà_saisis)`` — un champ SAISI quitte « à compléter ».

    « À compléter » ne liste QUE ce qui reste à faire : c'est cette liste que
    ``avancement_du_dossier`` compte, et c'est elle qui décide de
    ``peut_generer``. Un champ dont la source manque sort avec ``valeur =
    null`` et son message — l'écran n'affiche alors AUCUNE valeur.

    CALX41 — la SAISIE, elle, reste publiée dans sa propre liste : un champ
    qui disparaîtrait dès qu'il est rempli serait un champ que personne ne
    peut plus relire ni corriger. Rien n'y est deviné non plus : la valeur
    publiée est celle que l'utilisateur a enregistrée, telle quelle.
    """
    a_completer, deja_saisis = [], []
    for champ in champs or []:
        if not isinstance(champ, dict):
            continue
        code = str(champ.get('code') or '').strip()
        if not code:
            continue
        cle = champ.get('cle_calepinage')
        valeur = _valeur_reelle((infos or {}).get(cle)) if cle else None
        saisie = _valeur_reelle((saisis or {}).get(code))
        if saisie is not None:
            deja_saisis.append(_champ_publie(
                champ, code, saisie, '', valeur_calepinage=valeur,
                ecart_saisie=(valeur is not None
                              and not _meme_valeur(saisie, valeur))))
            continue
        a_completer.append(_champ_publie(
            champ, code, valeur,
            '' if valeur is not None else MESSAGE_CHAMP_SANS_SOURCE,
            valeur_calepinage=valeur))
    return (a_completer, deja_saisis)


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
    champs, champs_saisis = (
        _champs_du_gabarit(entree.get('champs'), saisis, infos)
        if present else ([], []))

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
        # CALX41 — ce que l'utilisateur a DÉJÀ enregistré, relisible et
        # corrigeable ; « à compléter » ne garde que ce qui reste à faire.
        'champs_saisis': champs_saisis,
        'peut_generer': peut_generer,
        'motif_non_generable': motif,
        'genere_le': entree.get('genere_le'),
        # ACAL240 — le document GED produit (id OPAQUE) et la péremption :
        # ``None`` tant que le dossier n'a pas été généré avec son empreinte.
        'document': entree.get('document'),
        'genere_sur_conception_perimee': entree.get(
            'genere_sur_conception_perimee'),
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

def infos_du_calepinage(calepinage, *, resultat=None):
    """Les données RÉELLES qu'un gabarit peut demander à préremplir.

    Aucune n'est calculée « au mieux » : une donnée absente vaut ``None`` et
    le champ qui la demandait sortira « à compléter ».

    ACAL259 — modules et kWc sont ceux de ``mesures.mesures_du_document`` (LA
    lecture du module), sur le résultat SERVI (``selectors.resultat_servi``,
    bloc ``pose`` : la fiche du stock) quand ``resultat`` n'est pas fourni.

    ACAL241 — client et adresse sont résolus par les fonctions EXISTANTES du
    module (``client_du_calepinage`` : client, sinon lead ; adresse du SITE
    par ``selectors.contexte_geographique`` : lead d'abord) — un calepinage
    né d'un lead n'a plus client et adresse vides.
    """
    from .documents.gabarit_document import client_du_calepinage
    from .mesures import mesures_du_document

    company = getattr(calepinage, 'company', None)
    layout = getattr(calepinage, 'roof_layout', None)
    if resultat is None and isinstance(layout, dict) and layout:
        from .. import selectors

        resultat = selectors.resultat_servi(calepinage)
    mesures = mesures_du_document(layout, resultat)
    pans = mesures['pans']
    domine = max(pans, key=lambda pan: int(pan.get('modules') or 0),
                 default=None)
    return {
        'societe_nom': _valeur_reelle(getattr(company, 'nom', None)),
        'client_nom': _valeur_reelle(client_du_calepinage(calepinage)),
        'adresse': _adresse_du_site(calepinage),
        'puissance_kwc': mesures['kwc'],
        'nombre_modules': (mesures['modules'] or None),
        'orientation_deg': (domine or {}).get('azimut_deg'),
        'inclinaison_deg': (domine or {}).get('inclinaison_deg'),
    }


def _perime(dossier, empreinte_courante):
    """``True``/``False`` : les entrées ont-elles changé depuis la
    génération ? ``None`` quand on ne le SAIT pas (jamais généré, ou généré
    avant que l'empreinte ne soit stockée) — jamais un « à jour » deviné."""
    if dossier is None or not dossier.genere_empreinte:
        return None
    if empreinte_courante is None:
        return None
    return dossier.genere_empreinte != empreinte_courante


def _adresse_du_site(calepinage):
    """L'adresse du SITE (« 12 rue X, Rabat »), ou ``None`` — lue par
    ``selectors.contexte_geographique`` (lead d'abord, sinon client)."""
    from ..selectors import contexte_geographique

    if getattr(calepinage, 'company', None) is None:
        return None
    contexte = contexte_geographique(calepinage)
    adresse = _valeur_reelle(contexte.get('adresse'))
    ville = _valeur_reelle(contexte.get('ville'))
    if adresse and ville and ville.lower() not in adresse.lower():
        return '%s, %s' % (adresse, ville)
    return adresse or ville


def _entree_depuis_orm(gabarit, dossier, empreinte_courante=None):
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
        'document': (dossier.document_id if dossier is not None else None),
        'genere_sur_conception_perimee': _perime(dossier, empreinte_courante),
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
    # ACAL240 — l'empreinte COURANTE des entrées, calculée UNE fois et
    # seulement si un dossier a été généré avec la sienne.
    empreinte_courante = None
    if any(d.genere_empreinte for d in dossiers.values()):
        from .empreinte_livrable import empreinte_des_entrees

        empreinte_courante = empreinte_des_entrees(calepinage, 'fr')
    entrees = [_entree_depuis_orm(gabarit, dossiers.get(gabarit.pk),
                                  empreinte_courante)
               for gabarit in gabarits]
    return composer_dossiers(calepinage_id=calepinage.pk, pays=pays,
                             entrees=entrees, infos=infos)


# ── CALX41 — ENREGISTRER LES CHAMPS À COMPLÉTER D'UN DOSSIER ───────────────
#
# L'écran rendait les champs en saisie NON CONTRÔLÉE, sans envoi : ce que
# l'utilisateur tapait était perdu à la fermeture, alors que
# ``DossierReglementaire`` est un modèle PERSISTANT. La saisie s'enregistre
# désormais — et la règle du module ne bouge pas d'un pouce : le gabarit de la
# société FAIT FOI, un code hors du gabarit est REFUSÉ en le nommant (l'ERP
# n'ajoute aucun champ à un formulaire officiel qu'il n'a pas reçu), et une
# valeur vide EFFACE la saisie au lieu d'inventer un défaut.


class ChampsDossierInvalides(ValueError):
    """Saisie refusée — message FRANÇAIS, et le CHAMP fautif est nommé."""

    def __init__(self, message, *, champ='champs'):
        super().__init__(message)
        self.champ = champ


def _nombre_saisi(valeur):
    """Le nombre qu'une saisie VEUT dire, ou ``None`` si ce n'en est pas un.

    Normaliser plutôt que refuser quand l'intention est claire (règle
    fondateur du 08/09/2026) : « 1 234,5 » est un nombre, pas une faute.
    """
    if isinstance(valeur, bool):
        return None
    if isinstance(valeur, (int, float)):
        return valeur
    texte = str(valeur)
    for espace in (' ', ' ', ' '):
        texte = texte.replace(espace, '')
    texte = texte.replace(',', '.')
    try:
        return int(texte)
    except ValueError:
        pass
    try:
        return float(texte)
    except ValueError:
        return None


def _valeur_de_champ(champ, code, valeur):
    """La valeur ENREGISTRABLE d'un champ, ou ``None`` pour l'effacer."""
    libelle = str(champ.get('libelle') or code)
    if isinstance(valeur, (dict, list, tuple)):
        raise ChampsDossierInvalides(
            f"Le champ « {libelle} » attend une valeur simple "
            f"(reçu : {type(valeur).__name__}).", champ=code)
    propre = _valeur_reelle(valeur)
    if propre is None:
        return None
    from .valeurs import nombre_fini

    if str(champ.get('type') or 'texte') == 'nombre':
        nombre = _nombre_saisi(propre)
        if nombre is None:
            raise ChampsDossierInvalides(
                f"Le champ « {libelle} » attend un nombre "
                f"(reçu : « {propre} »).", champ=code)
        # ACAL277 — « nan », « inf », « 1e400 » se lisent comme des
        # nombres mais n'en sont pas : refus nommé, jamais un JSON NaN.
        nombre_fini(nombre, code, libelle=libelle,
                    erreur=ChampsDossierInvalides)
        return nombre
    if isinstance(propre, (int, float)) and not isinstance(propre, bool):
        nombre_fini(propre, code, libelle=libelle,
                    erreur=ChampsDossierInvalides)
        return propre
    return propre if isinstance(propre, bool) else str(propre)


def _valider_champs_saisis(champs_gabarit, saisie):
    """``{code: valeur}`` VALIDÉ contre les champs DU GABARIT — PUR.

    Refuse EN NOMMANT le champ fautif : un code absent du gabarit, une valeur
    qui n'est pas une donnée simple, un « nombre » qui n'en est pas un. Une
    valeur vide sort à ``None`` : elle EFFACE la saisie (la seule façon de
    revenir en arrière sans inventer une valeur).
    """
    if saisie is None:
        return {}
    if not isinstance(saisie, dict):
        raise ChampsDossierInvalides(
            "Les champs du dossier se donnent en objet « code : valeur » "
            f"(reçu : {type(saisie).__name__}).")
    connus = {}
    for champ in champs_gabarit or []:
        if not isinstance(champ, dict):
            continue
        code = str(champ.get('code') or '').strip()
        if code:
            connus[code] = champ
    valide = {}
    for brut, valeur in saisie.items():
        code = str(brut or '').strip()
        champ = connus.get(code)
        if champ is None:
            raise ChampsDossierInvalides(
                f"Le champ « {code or brut} » n'existe pas dans le gabarit de "
                f"ce dossier : le gabarit déclare "
                f"{', '.join('« %s »' % c for c in sorted(connus)) or 'aucun champ'}"
                ". L'ERP n'ajoute aucun champ à un formulaire officiel qu'il "
                "n'a pas reçu.", champ=code or 'champs')
        valide[code] = _valeur_de_champ(champ, code, valeur)
    return valide


def enregistrer_champs(dossier, saisie):
    """CALX41 — écrit les champs saisis sur le ``DossierReglementaire``.

    La saisie est FUSIONNÉE : le panneau n'envoie que les champs qu'il
    affiche, et un champ absent de l'envoi garde sa valeur (l'écraser
    effacerait une saisie que personne n'a touchée). Une valeur vide efface
    explicitement le champ concerné.

    Raises:
        ChampsDossierInvalides: code hors gabarit, valeur non simple, nombre
            attendu — le champ fautif est NOMMÉ.
    """
    from django.db import transaction

    from ..models import DossierReglementaire

    valide = _valider_champs_saisis(
        getattr(dossier.gabarit, 'champs', None), saisie)
    # ACAL240 — la fusion se fait SOUS VERROU, sur la ligne RELUE : deux
    # utilisateurs qui saisissent des champs différents ne perdent rien (la
    # copie en mémoire de l'appelant peut être périmée).
    with transaction.atomic():
        verrouille = (DossierReglementaire.objects.select_for_update()
                      .get(pk=dossier.pk, company_id=dossier.company_id))
        courant = dict(verrouille.champs_saisis or {})
        for code, valeur in valide.items():
            if valeur is None:
                courant.pop(code, None)
            else:
                courant[code] = valeur
        verrouille.champs_saisis = courant
        verrouille.save(update_fields=['champs_saisis'])
    dossier.champs_saisis = courant
    return dossier


# ── CAL192 — LE PACK DE RACCORDEMENT AUTOPRODUCTION (MAROC) ────────────────
#
# Aucun rail marocain n'existe dans ce dépôt et le tarif BT de l'ANRE reste
# non publié : la règle « checked facts » impose donc que toute pièce ou
# valeur réglementaire soit SOURCÉE ou OMISE. Ce pack n'invente donc AUCUN
# formulaire : il assemble ce que le module PRODUIT vraiment (planche, note de
# calcul, schéma unifilaire) et ce que la SOCIÉTÉ a DÉPOSÉ (son gabarit, sa
# fiche société). En l'absence de gabarit société, il REFUSE en expliquant en
# français quoi déposer — jamais un gabarit inventé.
#
# ACAL236 — la fusion et le dépôt passent par LA fonction du dossier technique
# (``services/pack_technique.deposer_et_fusionner``) : aucune seconde
# plomberie PDF n'est créée ici.

#: Où le pack se range dans la GED.
CABINET_GED = 'Calepinage'
DOSSIER_GED = 'Dossiers réglementaires'

#: Les pièces que le MODULE produit lui-même, dans l'ordre d'impression :
#: ``(code, libellé, obligatoire)``. Ce ne sont PAS des formulaires officiels
#: — ce sont les sorties du calepinage, produites depuis ses données réelles.
PIECES_PRODUITES = (
    ('planche', 'Planche de calepinage', True),
    ('note_calcul', 'Note de calcul', True),
    ('schema_unifilaire', 'Schéma unifilaire', False),
)


class DossierRefuse(ValueError):
    """Le dossier refuse de sortir, en NOMMANT ce qui manque."""

    def __init__(self, message, *, piece=''):
        super().__init__(message)
        self.piece = piece


def _rendus_du_module(calepinage, company):
    """``code -> fonction de rendu`` (octets PDF). Imports FONCTION-LOCAUX."""
    from .note_calcul import rendre_note_calcul
    from .planche import rendre_planche_pdf

    def _schema():
        # ACAL163 — le schéma NATIF du calepinage (édition appliquée), avec
        # ou sans devis lié, par l'UNIQUE fonction qui l'encapsule.
        from .rapport.electrique import bloc_schema_unifilaire

        octets, motif = bloc_schema_unifilaire(calepinage, company=company)
        if not octets:
            raise DossierRefuse(motif, piece='schema_unifilaire')
        return octets

    return {
        'planche': lambda: rendre_planche_pdf(calepinage, company=company),
        'note_calcul': lambda: rendre_note_calcul(calepinage,
                                                  company=company),
        'schema_unifilaire': _schema,
    }


def _rendre_pieces_produites(rendus):
    """``([(code, libelle, octets)], [signalements])`` — rien n'est sauté."""
    pieces, signalements = [], []
    for code, libelle, obligatoire in PIECES_PRODUITES:
        rendu = rendus.get(code)
        try:
            octets = rendu() if rendu is not None else None
        except Exception as erreur:            # noqa: BLE001 - motif reporté
            if obligatoire:
                raise DossierRefuse(
                    "Dossier réglementaire : la pièce « %s » ne se rend pas "
                    "— %s. Un dossier amputé ne se dépose pas."
                    % (libelle, erreur), piece=code)
            signalements.append('« %s » : %s' % (libelle, erreur))
            continue
        if not octets:
            if obligatoire:
                raise DossierRefuse(
                    "Dossier réglementaire : la pièce « %s » est vide."
                    % libelle, piece=code)
            signalements.append('« %s » : rendu vide.' % libelle)
            continue
        pieces.append((code, libelle, octets))
    return pieces, signalements


# ── ACAL240 — LES PIÈCES DU DOSSIER LUI-MÊME ───────────────────────────────
#
# Le PDF déposé contenait la planche, la note et le schéma — mais NI le
# gabarit déposé par la société, NI les champs saisis, NI les pièces jointes :
# le « dossier » remis n'était pas le dossier. Il est désormais, DANS L'ORDRE :
# pages du gabarit → page des champs → pièces jointes PDF → pièces produites.

#: Ce qu'affiche la page des champs quand ni la saisie ni le calepinage ne
#: donnent de valeur — jamais un défaut inventé.
MENTION_A_COMPLETER = 'à compléter'


def _octets_attachment(company, attachment_id):
    """Les octets d'une ``records.Attachment`` DE LA SOCIÉTÉ, ou ``None``."""
    from apps.records.models import Attachment
    from apps.records.storage import fetch_attachment

    if not attachment_id or company is None:
        return None
    piece = Attachment.objects.filter(pk=attachment_id,
                                      company=company).first()
    if piece is None:
        return None
    octets, erreur = fetch_attachment(piece.file_key)
    return None if erreur else octets


def _est_octets_pdf(octets):
    return bool(octets) and bytes(octets).startswith(b'%PDF-')


def _texte_valeur(valeur):
    """Une valeur IMPRIMÉE à la française (« 12,5 »), jamais réinventée."""
    if isinstance(valeur, bool):
        return 'oui' if valeur else 'non'
    if isinstance(valeur, float):
        texte = ('%.6f' % valeur).rstrip('0').rstrip('.')
        return texte.replace('.', ',')
    return str(valeur)


def _lignes_des_champs(gabarit, champs_saisis, infos):
    """``[(libellé, valeur imprimée, source)]`` — la saisie EN PRIORITÉ,
    sinon la valeur du calepinage, sinon « à compléter ». PUR."""
    lignes = []
    for champ in getattr(gabarit, 'champs', None) or []:
        if not isinstance(champ, dict):
            continue
        code = str(champ.get('code') or '').strip()
        if not code:
            continue
        libelle = str(champ.get('libelle') or code)
        saisie = _valeur_reelle((champs_saisis or {}).get(code))
        cle = champ.get('cle_calepinage')
        calcul = _valeur_reelle((infos or {}).get(cle)) if cle else None
        if saisie is not None:
            lignes.append((libelle, _texte_valeur(saisie), 'saisie'))
        elif calcul is not None:
            lignes.append((libelle, _texte_valeur(calcul), 'calepinage'))
        else:
            lignes.append((libelle, MENTION_A_COMPLETER, 'a_completer'))
    return lignes


def _page_des_champs(gabarit, calepinage, lignes):
    """La page des champs, rendue par ``core.pdf.render_pdf``."""
    from django.utils.html import escape

    from core.pdf import render_pdf

    rangs = ''.join(
        '<tr><th>%s</th><td>%s</td></tr>' % (escape(libelle), escape(valeur))
        for libelle, valeur, _source in lignes)
    html = (
        '<!doctype html><html><head><meta charset="utf-8"><style>'
        'body{font-family:sans-serif;font-size:11pt;margin:2cm}'
        'table{border-collapse:collapse;width:100%%}'
        'th,td{border:1px solid #999;padding:4pt 6pt;text-align:left}'
        'th{width:45%%;background:#f2f2f2}</style></head><body>'
        '<h1>%s</h1><p>%s</p><table>%s</table></body></html>'
        % (escape(getattr(gabarit, 'intitule', '') or ''),
           escape(str(calepinage)), rangs))
    return render_pdf(html=html)


def _pieces_du_dossier(dossier, *, company, infos=None):
    """``[(code, libellé, octets)]`` : gabarit, page des champs, pièces
    jointes PDF — dans cet ordre.

    Raises:
        DossierRefuse: fichier du gabarit illisible ou NON PDF (``gabarit``).
    """
    gabarit = dossier.gabarit
    octets_gabarit = _octets_attachment(
        company, getattr(gabarit, 'fichier_id', None))
    if octets_gabarit is None:
        raise DossierRefuse(
            "Le fichier du gabarit « %s » est illisible dans le stockage : "
            "redéposez-le dans les réglages du module." % gabarit.intitule,
            piece='gabarit')
    if not _est_octets_pdf(octets_gabarit):
        raise DossierRefuse(
            "Le gabarit « %s » n'est pas un PDF : seul un PDF se fusionne "
            "dans le dossier. Redéposez-le en PDF." % gabarit.intitule,
            piece='gabarit')
    if infos is None:
        infos = infos_du_calepinage(dossier.calepinage)
    pieces = [('gabarit', 'Gabarit — %s' % gabarit.intitule, octets_gabarit)]
    lignes = _lignes_des_champs(gabarit, dossier.champs_saisis, infos)
    if lignes:
        pieces.append(('champs', 'Champs du dossier', _page_des_champs(
            gabarit, dossier.calepinage, lignes)))
    jointes = dossier.pieces_jointes or {}
    for attendue in gabarit.pieces_attendues or []:
        if not isinstance(attendue, dict):
            continue
        code = str(attendue.get('code') or '').strip()
        jointe = jointes.get(code)
        if not isinstance(jointe, dict):
            continue
        octets = _octets_attachment(company, jointe.get('attachment_id'))
        if _est_octets_pdf(octets):
            pieces.append(('jointe:%s' % code,
                           str(attendue.get('intitule') or code), octets))
    return pieces


def construire_pack_dossier(dossier, *, created_by=None, rendus=None,
                            empreinte=None, pieces_dossier=None):
    """Produit et FUSIONNE le dossier réglementaire d'un calepinage.

    Le gabarit de la société FAIT FOI : sans son fichier, rien n'est produit
    et le message dit quoi déposer. ACAL240 — le PDF déposé en GED contient,
    DANS L'ORDRE : les pages du gabarit déposé, une page des champs (saisie,
    sinon valeur du calepinage, sinon « à compléter »), les pièces jointes
    PDF, puis les pièces PRODUITES par le module (planche, note de calcul,
    schéma unifilaire) — jamais un formulaire fabriqué. ``pieces_dossier``
    (``[(code, libellé, octets)]``) remplace les trois premières familles
    (seam de test) ; ``None`` les lit sur le dossier (``_pieces_du_dossier``).

    Returns:
        ``{'document', 'pieces', 'signalements', 'dossier', 'empreinte'}`` —
        ``empreinte`` = l'empreinte COMPLÈTE des entrées à la génération
        (stockée dans ``DossierReglementaire.genere_empreinte``).

    Raises:
        DossierRefuse: gabarit non déposé ou non PDF, société absente, pièce
            obligatoire non rendue.
    """
    calepinage = dossier.calepinage
    company = getattr(dossier, 'company', None) or getattr(
        calepinage, 'company', None)
    if company is None:
        raise DossierRefuse(
            "Un dossier réglementaire se produit toujours dans une société.",
            piece='company')
    gabarit = dossier.gabarit
    if not gabarit.fichier_present:
        raise DossierRefuse(
            "Le gabarit « %s » n'a pas de fichier déposé : déposez le "
            "document fourni par l'administration dans les réglages du "
            "module, l'ERP ne fabrique aucun formulaire officiel qu'il n'a "
            "pas reçu." % gabarit.intitule, piece='gabarit')

    # ACAL236 — le dépôt passe par LA fonction partagée avec le dossier
    # technique et le dossier de fin de chantier : fusion locale contrôlée
    # (pages), ancre stable ``<dossier>:dossier_reglementaire``, version neuve
    # seulement quand l'EMPREINTE DES ENTRÉES change (gabarit compris).
    from .pack_technique import deposer_et_fusionner

    if pieces_dossier is None:
        pieces_dossier = _pieces_du_dossier(dossier, company=company)
    rendus = rendus if rendus is not None else _rendus_du_module(calepinage,
                                                                 company)
    pieces, signalements = _rendre_pieces_produites(rendus)
    pieces = list(pieces_dossier) + list(pieces)
    if not pieces:
        raise DossierRefuse(
            "Dossier réglementaire refusé : aucune pièce à fusionner.",
            piece='pieces')
    if empreinte is None:
        from .empreinte_livrable import empreinte_des_entrees

        empreinte = empreinte_des_entrees(calepinage, 'fr')

    depot = deposer_et_fusionner(
        calepinage, pieces=[(code, libelle, octets, None)
                            for code, libelle, octets in pieces],
        famille='dossier_reglementaire',
        nom='%s — %s' % (gabarit.intitule, calepinage),
        cabinet_nom=CABINET_GED, folder_nom=DOSSIER_GED, company=company,
        created_by=created_by, ancre=getattr(dossier, 'pk', ''),
        refus=DossierRefuse, empreinte=empreinte)
    return {
        'document': depot['document'],
        'pieces': [(code, libelle) for code, libelle, _o in pieces],
        'signalements': signalements,
        'dossier': dossier.pk,
        'empreinte': empreinte,
    }


# ── CAL193 — LES TROIS DOSSIERS FRANÇAIS (DP mairie, Enedis, Consuel) ──────
#
# La mémoire fondateur du 20/08 désigne les rails DP/Enedis/Consuel comme un
# gap produit ; aucun code correspondant n'existait (grep
# ``consuel|cerfa|enedis`` sans résultat côté backend). Ce qui est écrit ici
# se limite aux trois CLÉS de genre et à leurs libellés d'écran : la LISTE des
# pièces de chaque dossier, leurs intitulés et leurs RÉFÉRENCES (numéro de
# CERFA, notice Consuel, documentation Enedis) viennent du gabarit DÉPOSÉ par
# la société (CAL190, qui refuse une pièce sans source). Aucune donnée
# réglementaire chiffrée n'est écrite en dur — un test de surface le vérifie.

#: Les trois genres de dossier français, et ce qu'ils nomment à l'écran.
GENRES_FRANCE = (
    ('dp_mairie', "Déclaration préalable en mairie"),
    ('enedis', "Raccordement Enedis"),
    ('consuel', "Attestation de conformité (Consuel)"),
)

MESSAGE_GENRE_SANS_GABARIT = (
    "Aucun gabarit « %s » n'a été déposé pour la France : déposez le "
    "formulaire officiel et la liste de ses pièces (avec leur référence) "
    "dans les réglages du module. L'ERP ne reproduit aucun formulaire de "
    "mémoire."
)


def avancement_du_dossier(dossier):
    """L'état d'avancement PIÈCE PAR PIÈCE d'un dossier composé.

    Compte ce qui est réellement fourni ; ``pourcentage`` vaut ``None`` quand
    le dossier n'attend AUCUNE pièce (un pourcentage sur zéro pièce serait un
    chiffre inventé).
    """
    pieces = dossier.get('pieces') or []
    fournies = [p for p in pieces if p['etat'] == ETAT_FOURNIE]
    a_completer = [p for p in pieces if p['etat'] == ETAT_A_COMPLETER]
    manquantes = [p for p in pieces if p['etat'] == ETAT_MANQUANTE]
    total = len(pieces)
    return {
        'pieces_total': total,
        'pieces_fournies': len(fournies),
        'pieces_a_completer': len(a_completer),
        'pieces_manquantes': len(manquantes),
        'champs_a_completer': len(dossier.get('champs_a_completer') or []),
        # CALX41 — un champ enregistré quitte « à compléter » et se compte
        # ici : l'avancement tient donc compte de ce qui a été saisi.
        'champs_saisis': len(dossier.get('champs_saisis') or []),
        'pourcentage': (round(len(fournies) * 100 / total)
                        if total else None),
    }


def packs_france(calepinage, agregat=None):
    """CAL193 — les trois dossiers FR, chacun avec son avancement.

    ACAL309 — ``agregat`` (``dossiers_du_calepinage(calepinage, pays='fr')``)
    peut etre fourni par l'appelant pour ne le calculer qu'une fois.

    Un genre dont la société n'a déposé AUCUN gabarit sort avec
    ``gabarit_depose = False`` et le message qui dit quoi déposer : il n'est
    ni masqué (on saurait alors rien) ni inventé (on mentirait).
    """
    from ..models import GabaritDossierReglementaire

    if agregat is None:
        agregat = dossiers_du_calepinage(calepinage, pays='fr')
    # Le GENRE vit sur le gabarit, pas dans le dossier composé : y ajouter une
    # clé ferait diverger la forme du contrat CAL247, que l'écran consomme.
    genre_par_gabarit = dict(
        GabaritDossierReglementaire.objects
        .filter(company=getattr(calepinage, 'company', None), pays='fr')
        .values_list('id', 'genre'))
    par_genre = {}
    for dossier in agregat['dossiers']:
        genre = genre_par_gabarit.get(dossier.get('gabarit_id')) or ''
        par_genre.setdefault(genre, []).append(dossier)
    packs = []
    for genre, libelle in GENRES_FRANCE:
        dossiers = par_genre.get(genre) or []
        packs.append({
            'genre': genre,
            'libelle': libelle,
            'gabarit_depose': bool(dossiers),
            'message': ('' if dossiers
                        else MESSAGE_GENRE_SANS_GABARIT % libelle),
            'dossiers': [dict(dossier,
                              avancement=avancement_du_dossier(dossier))
                         for dossier in dossiers],
        })
    return {
        'calepinage': agregat['calepinage'],
        'pays': agregat['pays'],
        'packs': packs,
    }


# ── ACAL238 — LA PORTE DE DÉPÔT DES GABARITS ET DES PIÈCES ─────────────────
#
# ``GabaritDossierReglementaire`` n'avait ni sérialiseur, ni route : aucune
# société ne pouvait déposer le document fourni par l'administration, donc
# aucun dossier n'apparaissait jamais. Ces services sont l'UNIQUE écrivain
# d'un gabarit (genres dp_mairie, enedis, consuel, manuel… — une seule porte)
# et des pièces jointes d'un dossier. La société et l'auteur viennent TOUJOURS
# de l'appelant serveur, jamais du corps de la requête ; le fichier est une
# ``records.Attachment`` (ARC26), rattachée à l'objet qu'elle documente.
#
# Défaut gravé : un gabarit se dépose en PDF SEULEMENT (un Word est refusé
# sous « fichier ») ; chaque création / modification / suppression est
# journalisée (auteur, avant, après) dans le fil générique ``records``.

#: Le refus d'un fichier qui n'est pas un PDF (contrat ``refus_400``).
MESSAGE_GABARIT_NON_PDF = (
    "Un gabarit se dépose en PDF : le fichier reçu n'en est pas un.")

#: Les champs qu'un dépôt / une modification de gabarit peut écrire.
CHAMPS_GABARIT = ('pays', 'code', 'genre', 'intitule', 'version', 'actif',
                  'pieces_attendues', 'champs')

#: Les clés vérifiées, dans l'ordre du modèle, pour NOMMER l'élément fautif
#: d'une liste (``pieces_attendues[1].source_reference``).
_CLES_PIECE = ('code', 'intitule', 'source_reference')
_CLES_CHAMP = ('code', 'libelle', 'type', 'cle_calepinage')

__all__ += [
    'GabaritRefuse', 'MESSAGE_GABARIT_NON_PDF', 'gabarit_publie',
    'deposer_gabarit', 'modifier_gabarit', 'supprimer_gabarit',
    'PieceRefusee', 'joindre_piece',
]


class GabaritRefuse(ValueError):
    """Un dépôt refusé : ``erreurs`` = ``{champ nommé: message}``."""

    def __init__(self, erreurs, *, statut=HTTPStatus.BAD_REQUEST):
        super().__init__('; '.join(str(m) for m in erreurs.values()))
        self.erreurs = dict(erreurs)
        self.statut = statut


class PieceRefusee(ValueError):
    """Une pièce refusée, champ nommé."""

    def __init__(self, message, *, champ='piece'):
        super().__init__(message)
        self.champ = champ


def _est_pdf(fichier):
    signature = b'%PDF-'
    entete = fichier.read(len(signature))
    fichier.seek(0)
    return entete == signature


def gabarit_publie(gabarit):
    """La forme publiée d'UN gabarit (contrat
    ``gabarits_dossier_reglementaire.json``, ``detail.exemple``)."""
    fichier = gabarit.fichier if gabarit.fichier_id else None
    auteur = gabarit.depose_par if gabarit.depose_par_id else None
    return {
        'id': gabarit.pk,
        'pays': gabarit.pays,
        'code': gabarit.code,
        'genre': gabarit.genre,
        'intitule': gabarit.intitule,
        'version': gabarit.version,
        'actif': gabarit.actif,
        'pieces_attendues': list(gabarit.pieces_attendues or []),
        'champs': list(gabarit.champs or []),
        'fichiers': ({'attachment': fichier.pk, 'nom': fichier.filename}
                     if fichier is not None else None),
        'depose_par': ({'id': auteur.pk, 'nom_complet': str(auteur)}
                       if auteur is not None else None),
        'depose_le': gabarit.depose_le,
    }


def _liste_saisie(valeur, champ):
    """Une liste reçue en JSON (multipart) ou déjà décodée."""
    if isinstance(valeur, str):
        import json

        try:
            return json.loads(valeur) if valeur.strip() else []
        except ValueError:
            raise GabaritRefuse({champ: (
                f"« {champ} » se donne en liste JSON : le texte reçu "
                "n'est pas lisible.")})
    return valeur


def _booleen(valeur):
    if isinstance(valeur, str):
        return valeur.strip().lower() in ('1', 'true', 'vrai', 'oui', 'on')
    return bool(valeur)


def _premier_element_fautif(liste, cles, prefixe):
    """Le chemin NOMMÉ de l'élément fautif d'une liste, ou le préfixe."""
    if not isinstance(liste, list):
        return prefixe
    vus = set()
    for rang, element in enumerate(liste):
        if not isinstance(element, dict):
            return f'{prefixe}[{rang}]'
        code = str(element.get('code') or '').strip()
        if not code or code in vus:
            return f'{prefixe}[{rang}].code'
        vus.add(code)
        for cle in cles[1:]:
            if prefixe == 'champs' and cle in ('type', 'cle_calepinage'):
                continue
            if not str(element.get(cle) or '').strip():
                return f'{prefixe}[{rang}].{cle}'
    if prefixe == 'champs':
        from ..models import GabaritDossierReglementaire as Gabarit

        for rang, element in enumerate(liste):
            if str(element.get('type') or 'texte') not in Gabarit.TYPES_CHAMP:
                return f'champs[{rang}].type'
            cle = element.get('cle_calepinage')
            if cle and cle not in Gabarit.CLES_PREREMPLISSAGE:
                return f'champs[{rang}].cle_calepinage'
    return prefixe


def _valider(gabarit):
    """``clean()`` du modèle, ses refus RE-NOMMÉS au chemin fautif."""
    from django.core.exceptions import ValidationError

    try:
        gabarit.clean()
    except ValidationError as refus:
        erreurs = {}
        for champ, messages in refus.message_dict.items():
            nom = champ
            if champ == 'pieces_attendues':
                nom = _premier_element_fautif(gabarit.pieces_attendues,
                                              _CLES_PIECE, champ)
            elif champ == 'champs':
                nom = _premier_element_fautif(gabarit.champs, _CLES_CHAMP,
                                              champ)
            erreurs[nom] = ' '.join(messages)
        raise GabaritRefuse(erreurs)
    from ..models import GabaritDossierReglementaire

    doublon = (GabaritDossierReglementaire.objects
               .filter(company=gabarit.company, pays=gabarit.pays,
                       code=gabarit.code)
               .exclude(pk=gabarit.pk).exists())
    if doublon:
        raise GabaritRefuse({'code': (
            f"Un gabarit « {gabarit.code} » existe déjà pour ce pays dans la "
            "société : modifiez-le plutôt que d'en déposer un second.")})


def _appliquer(gabarit, donnees):
    for champ in CHAMPS_GABARIT:
        if champ not in donnees:
            continue
        valeur = donnees[champ]
        if champ in ('pieces_attendues', 'champs'):
            valeur = _liste_saisie(valeur, champ)
        elif champ == 'actif':
            valeur = _booleen(valeur)
        elif valeur is None:
            valeur = ''
        setattr(gabarit, champ, valeur)


def _stocker_pdf(fichier, *, company, cible, user):
    """Le PDF déposé, en ``records.Attachment`` rattachée à ``cible``."""
    from django.contrib.contenttypes.models import ContentType

    from apps.records.models import Attachment
    from apps.records.storage import store_attachment

    donnees, erreur = store_attachment(fichier, company=company)
    if erreur:
        raise GabaritRefuse({'fichier': erreur})
    return Attachment.objects.create(
        company=company,
        content_type=ContentType.objects.get_for_model(cible.__class__),
        object_id=cible.pk,
        uploaded_by=user if getattr(user, 'pk', None) else None,
        **donnees)


def _journaliser(gabarit, user, *, avant, apres):
    """Auteur, avant, après — dans le fil générique (``records``)."""
    import json

    from apps.records.services import log_activity

    texte = (lambda forme: json.dumps(forme, ensure_ascii=False,
                                      sort_keys=True, default=str)
             if forme is not None else '')
    log_activity(
        gabarit, 'creation' if avant is None else 'modification',
        user=user if getattr(user, 'pk', None) else None,
        field='gabarit', field_label='Gabarit de dossier réglementaire',
        old_value=texte(avant), new_value=texte(apres),
        company=gabarit.company)


def deposer_gabarit(company, user, donnees, fichier=None):
    """Crée un gabarit de la société ``company`` (jamais lue du corps)."""
    from django.db import transaction
    from django.utils import timezone

    from ..models import GabaritDossierReglementaire

    if fichier is not None and not _est_pdf(fichier):
        raise GabaritRefuse({'fichier': MESSAGE_GABARIT_NON_PDF})
    gabarit = GabaritDossierReglementaire(company=company)
    _appliquer(gabarit, donnees or {})
    _valider(gabarit)
    with transaction.atomic():
        gabarit.save()
        if fichier is not None:
            gabarit.fichier = _stocker_pdf(fichier, company=company,
                                           cible=gabarit, user=user)
            gabarit.depose_le = timezone.now()
            gabarit.depose_par = user if getattr(user, 'pk', None) else None
            gabarit.save(update_fields=['fichier', 'depose_le',
                                        'depose_par'])
        _journaliser(gabarit, user, avant=None,
                     apres=gabarit_publie(gabarit))
    return gabarit


def modifier_gabarit(gabarit, user, donnees, fichier=None):
    """Modifie un gabarit (mise à jour PARTIELLE), fichier compris."""
    from django.db import transaction
    from django.utils import timezone

    if fichier is not None and not _est_pdf(fichier):
        raise GabaritRefuse({'fichier': MESSAGE_GABARIT_NON_PDF})
    avant = gabarit_publie(gabarit)
    _appliquer(gabarit, donnees or {})
    _valider(gabarit)
    with transaction.atomic():
        if fichier is not None:
            gabarit.fichier = _stocker_pdf(fichier, company=gabarit.company,
                                           cible=gabarit, user=user)
            gabarit.depose_le = timezone.now()
            gabarit.depose_par = user if getattr(user, 'pk', None) else None
        gabarit.save()
        _journaliser(gabarit, user, avant=avant,
                     apres=gabarit_publie(gabarit))
    return gabarit


def supprimer_gabarit(gabarit, user):
    """Supprime un gabarit INUTILISÉ ; utilisé par des dossiers → 409 nommé
    (``PROTECT`` : un dossier ne perd jamais son gabarit)."""
    from django.db import transaction

    utilisations = gabarit.dossiers.count()
    if utilisations:
        raise GabaritRefuse({'detail': (
            f"Ce gabarit est utilisé par {utilisations} dossier(s) : "
            "archivez-le plutôt que de le supprimer.")}, statut=HTTPStatus.CONFLICT)
    with transaction.atomic():
        _journaliser(gabarit, user, avant=gabarit_publie(gabarit),
                     apres=None)
        gabarit.delete()


def joindre_piece(dossier, code, *, fichier=None, retirer=False, user=None):
    """Joint (ou retire) la pièce ``code`` d'un dossier — sous verrou.

    Écrit ``DossierReglementaire.pieces_jointes[code] = {attachment_id,
    depose_le, fichier}`` ; ``retirer`` efface l'entrée (la pièce redevient
    non fournie). Rend la forme du contrat (``joindre_piece``).
    """
    from django.db import transaction
    from django.utils import timezone

    from ..models import DossierReglementaire

    code = str(code or '').strip()
    attendues = {str(p.get('code') or '').strip()
                 for p in dossier.gabarit.pieces_attendues or ()
                 if isinstance(p, dict)}
    if not code or code not in attendues:
        raise PieceRefusee(
            f"La pièce « {code} » n'existe pas dans ce dossier.")
    if not retirer and fichier is None:
        raise PieceRefusee("Joignez le fichier de la pièce (ou demandez son "
                           "retrait avec « retirer »).", champ='fichier')
    with transaction.atomic():
        verrouille = (DossierReglementaire.objects.select_for_update()
                      .get(pk=dossier.pk, company=dossier.company))
        jointes = dict(verrouille.pieces_jointes or {})
        if retirer:
            jointes.pop(code, None)
            reponse = {'piece': code, 'etat': ETAT_MANQUANTE,
                       'attachment': None, 'depose_le': None}
        else:
            try:
                piece = _stocker_pdf(fichier, company=verrouille.company,
                                     cible=verrouille, user=user)
            except GabaritRefuse as refus:
                raise PieceRefusee(refus.erreurs['fichier'],
                                   champ='fichier')
            depose_le = timezone.now()
            jointes[code] = {'attachment_id': piece.pk,
                             'depose_le': depose_le.isoformat(),
                             'fichier': piece.filename}
            reponse = {'piece': code, 'etat': ETAT_FOURNIE,
                       'attachment': piece.pk, 'depose_le': depose_le}
        verrouille.pieces_jointes = jointes
        verrouille.save(update_fields=['pieces_jointes'])
    dossier.pieces_jointes = jointes
    return reponse
