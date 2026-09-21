"""NTMIG32 — qualité de la SOURCE avant chargement (règles de format).

Ce module ne connaît QUE le fichier source : il ne touche aucune table cible,
n'écrit rien, et ne remplace pas le contrôle métier du moteur ``dataimport``
(qui, lui, refuse une ligne au moment du commit). Son rôle est d'apporter la
réponse que l'intégrateur veut AVANT d'importer : *combien de lignes de mon
export sont exploitables, et pourquoi les autres ne le sont pas ?*

Trois sources de règles, dans cet ordre de priorité :

1. le KIT de la source (``KIT_REGISTRY[(source, entite)]``, NTMIG8/12/13) —
   il déclare ses propres règles par champ ; **absent aujourd'hui du dépôt**,
   il est donc résolu en import PARESSEUX (comme le connecteur Odoo NTMIG9) :
   tant qu'aucun kit n'existe, on ne fabrique PAS un registre de substitution,
   on retombe simplement sur (2) ;
2. l'app ``dataquality`` (NTDATA14), consultée via ses ``selectors`` s'ils
   existent — jamais un import de ses modèles ;
3. à défaut, les règles minimales LOCALES ci-dessous (ICE / e-mail /
   téléphone / montant), déduites du nom du champ CIBLE (pas de l'en-tête
   source, qui varie d'un export à l'autre).

Une ligne invalide n'est jamais supprimée ni corrigée en silence : elle est
COMPTÉE et NOMMÉE (numéro de ligne + champ + motif), à charge de l'appelant de
proposer de continuer sans elle.
"""
import importlib
import re
from decimal import Decimal, InvalidOperation

#: Kits de mapping par source (NTMIG8/12/13) — SEUL point de couplage.
KITS_MODULE = 'apps.migration.kits'
#: Selectors de l'app qualité de données (NTDATA14) — SEUL point de couplage.
DATAQUALITY_SELECTORS_MODULE = 'apps.dataquality.selectors'

#: Nombre maximum de lignes détaillées renvoyées (le compte, lui, est exact).
MAX_DETAILS = 200

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s.]+\.[^@\s]+$')


def _texte(valeur):
    return '' if valeur is None else str(valeur).strip()


def valider_ice(valeur):
    """ICE marocain : 15 chiffres exactement (séparateurs tolérés)."""
    brut = re.sub(r'[\s.\-]', '', _texte(valeur))
    if not brut:
        return None  # champ vide : ce n'est pas une erreur de FORMAT
    if not brut.isdigit():
        return "ICE non numérique"
    if len(brut) != 15:
        return f"ICE de {len(brut)} chiffres (15 attendus)"
    return None


def valider_email(valeur):
    txt = _texte(valeur)
    if not txt:
        return None
    if not _EMAIL_RE.match(txt):
        return "e-mail mal formé"
    return None


def valider_telephone(valeur):
    """Téléphone exploitable : 9 à 15 chiffres une fois la mise en forme ôtée.

    Volontairement PERMISSIF : la normalisation marocaine réelle appartient à
    ``crm.services.normalize_phone`` (NTMIG14) ; ici on ne rejette que ce qui
    ne peut être un numéro (lettres, trop court, trop long).
    """
    txt = _texte(valeur)
    if not txt:
        return None
    chiffres = re.sub(r'\D', '', txt)
    if not chiffres:
        return "téléphone sans chiffre"
    if len(chiffres) < 9:
        return f"téléphone trop court ({len(chiffres)} chiffres)"
    if len(chiffres) > 15:
        return f"téléphone trop long ({len(chiffres)} chiffres)"
    return None


def valider_montant(valeur):
    """Montant parsable, décimale ``,`` ou ``.``, espaces de milliers tolérés."""
    txt = _texte(valeur)
    if not txt:
        return None
    # Espaces de milliers, y compris l'insécable des exports Excel FR.
    brut = re.sub(r'\s', '', txt).replace(',', '.')
    brut = brut.replace('MAD', '').replace('DH', '')
    try:
        Decimal(brut)
    except (InvalidOperation, ValueError):
        return "montant non numérique"
    return None


#: Règles disponibles par clé (une clé de kit se réfère à ces mêmes noms).
REGLES = {
    'ice': valider_ice,
    'email': valider_email,
    'telephone': valider_telephone,
    'montant': valider_montant,
}

#: Déduction locale règle ← nom du champ CIBLE (repli sans kit).
_MOTS_CLES = (
    ('ice', 'ice'),
    ('email', 'email'),
    ('mail', 'email'),
    ('telephone', 'telephone'),
    ('tel', 'telephone'),
    ('mobile', 'telephone'),
    ('whatsapp', 'telephone'),
    ('montant', 'montant'),
    ('prix', 'montant'),
    ('total', 'montant'),
    ('solde', 'montant'),
)


def regles_locales(champ):
    """Règles minimales déduites du nom du champ cible (jamais devinées sur
    la valeur : un champ ``reference`` ne devient pas un montant parce qu'il
    contient des chiffres)."""
    nom = (champ or '').lower()
    trouvees = []
    for mot, regle in _MOTS_CLES:
        if mot in nom and regle not in trouvees:
            trouvees.append(regle)
            break  # une règle par champ : la plus spécifique gagne
    return trouvees


def _regles_du_kit(kit_cle):
    """Règles déclarées par le kit — ``{}`` tant que les kits n'existent pas.

    Import PARESSEUX : l'absence du module n'est pas une erreur, c'est l'état
    nominal actuel du dépôt (NTMIG8/12/13 non construits).
    """
    if not kit_cle:
        return {}
    try:
        module = importlib.import_module(KITS_MODULE)
    except ImportError:
        return {}
    registre = getattr(module, 'KIT_REGISTRY', None)
    if not registre:
        return {}
    kit = registre.get(kit_cle)
    if kit is None:
        return {}
    return dict(getattr(kit, 'regles_format', None)
                or (kit.get('regles_format') if isinstance(kit, dict) else {})
                or {})


def _regles_dataquality(company, entite):
    """Règles publiées par ``dataquality`` (NTDATA14) via ses SELECTORS.

    L'app n'existe pas encore : import paresseux, ``{}`` sinon. Jamais un
    import de ses modèles, jamais une réimplémentation locale de ses règles.
    """
    try:
        module = importlib.import_module(DATAQUALITY_SELECTORS_MODULE)
    except ImportError:
        return {}
    fabrique = getattr(module, 'regles_format_pour', None)
    if fabrique is None:
        return {}
    try:
        return dict(fabrique(company, entite) or {})
    except Exception:
        # Une app de qualité de données indisponible ne doit jamais empêcher
        # de valider un fichier : on retombe sur les règles locales.
        return {}


def regles_effectives(mapped, *, kit_cle=None, company=None, entite=None):
    """Règles à appliquer, par CHAMP CIBLE : kit > dataquality > local.

    ``mapped`` est le mapping ``colonne source → champ cible`` renvoyé par le
    dry-run : on ne valide que des colonnes réellement importées (valider une
    colonne ignorée signalerait des « erreurs » sans effet sur l'import).
    """
    kit = _regles_du_kit(kit_cle)
    dq = _regles_dataquality(company, entite) if company is not None else {}
    effectives = {}
    for champ in set(mapped.values()):
        noms = kit.get(champ) or dq.get(champ) or regles_locales(champ)
        if isinstance(noms, str):
            noms = [noms]
        retenues = [n for n in (noms or []) if n in REGLES]
        if retenues:
            effectives[champ] = retenues
    return effectives


def valider_lignes(rows, mapped, regles):
    """Rapport de qualité de la source — comptes EXACTS, détails plafonnés.

    Une ligne est invalide dès qu'un de ses champs viole une règle ; elle peut
    porter plusieurs motifs (tous sont listés, jusqu'à :data:`MAX_DETAILS`).
    Les numéros de ligne suivent la convention du moteur d'import (1 = première
    ligne de DONNÉES, en-tête exclu) pour que « ligne 42 » désigne la même
    ligne ici et dans le journal d'import.
    """
    details = []
    motifs = {}
    lignes_invalides = []
    for numero, row in enumerate(rows, 1):
        invalide = False
        for colonne, champ in mapped.items():
            for nom_regle in regles.get(champ, ()):
                motif = REGLES[nom_regle](row.get(colonne))
                if motif is None:
                    continue
                invalide = True
                motifs[motif] = motifs.get(motif, 0) + 1
                if len(details) < MAX_DETAILS:
                    details.append({
                        'ligne': numero, 'colonne': colonne, 'champ': champ,
                        'regle': nom_regle, 'motif': motif,
                        'valeur': _texte(row.get(colonne))[:80]})
        if invalide:
            lignes_invalides.append(numero)
    total = len(rows)
    return {
        'total_lignes': total,
        'lignes_valides': total - len(lignes_invalides),
        'lignes_invalides': len(lignes_invalides),
        'lignes_invalides_numeros': lignes_invalides,
        'motifs': motifs,
        'details': details,
        'details_tronques': len(details) >= MAX_DETAILS,
        'regles_appliquees': regles,
        # L'appelant PROPOSE de continuer sans les lignes invalides : la
        # décision reste humaine, rien n'est retiré du fichier ici.
        'peut_continuer_sans_invalides': bool(lignes_invalides)
        and len(lignes_invalides) < total,
    }
