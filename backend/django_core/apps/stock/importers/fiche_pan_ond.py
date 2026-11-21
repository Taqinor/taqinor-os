"""CAL117 — import OPTIONNEL d'une fiche constructeur .PAN / .OND.

PARSEUR PUR — stdlib seule, AUCUN import Django : ``grep -rniI
"\\.pan|\\.ond|import_fiche" apps/stock`` ne rendait avant cette tâche que
des faux positifs (``self.panneau``) — aucun dossier ``importers/`` ni
parseur de datasheet n'existait, toute fiche se saisissait à la main.
.PAN/.OND est le format d'échange de fait de la base composants PVsyst.

CE QUE CE MODULE FAIT :
  1. ``parse_pan_ond_bytes``/``parse_pan_ond_text`` — lit le texte brut
     ``clé=valeur`` d'un fichier .PAN/.OND (ignore les en-têtes de section
     et les lignes sans ``=``), détecte le type (module/onduleur) depuis la
     ligne ``PVObject_=...``.
  2. ``propose_mapping`` — traduit les clés PVsyst RECONNUES (table
     ``MODULE_FIELD_MAP``/``ONDULEUR_FIELD_MAP`` ci-dessous, volontairement
     un sous-ensemble EXPLICITE et documenté — étendre la couverture à
     d'autres clés constructeur est un travail futur, jamais une extension
     silencieuse ni une conversion d'unité devinée) vers les noms de champs
     ``FicheTechnique``. Toute clé absente de la table est LISTÉE dans
     ``non_reconnus``, jamais ignorée en silence.
  3. ``champs_a_ecrire`` — sépare, PAR RAPPORT à une fiche existante donnée,
     ce qui peut s'écrire (champ encore vide) de ce qui est DÉJÀ SAISI (donc
     jamais écrasé) : c'est la fonction qui matérialise « aucun écrasement
     silencieux ». L'écriture elle-même (côté vue) n'a lieu qu'après
     confirmation explicite de l'utilisateur.

ZÉRO CHIFFRE INVENTÉ : seules les clés dont l'unité PVsyst correspond
DIRECTEMENT (ou par un facteur d'unité universellement connu — mètres→mm,
watts→kW, fraction→%) à celle du champ ``FicheTechnique`` sont mappées.
CALX356 (lu sur les deux vrais fichiers pvlib de
``contract_samples/pvsyst/``) : ``muVocSpec`` (mV/°C) devient le coefficient
RELATIF %/°C par sa définition, rapporté à la ``Voc`` du même fichier ;
``muISC`` (mA/°C) n'a aucun champ de destination et reste en
``non_reconnus``. ``champs_attendus_absents`` liste les champs que la table
sait remplir mais que le fichier n'apporte pas — jamais remplis d'un repli.
"""
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation


class FichierIllisible(ValueError):
    """Levée quand le fichier ne peut pas être décodé, ou que son type
    (module/onduleur) ne peut pas être déterminé. ``champ`` nomme le champ
    fautif pour l'API — toujours ``'file'`` ici (c'est le fichier entier qui
    est en cause, jamais un champ précis du formulaire)."""

    def __init__(self, message, ligne=None):
        super().__init__(message)
        self.champ = 'file'
        #: CALX356 — numéro (1-based) de la ligne fautive, quand il y en a une.
        self.ligne = ligne


def _premiere_ligne(text):
    """(numéro 1-based, contenu) de la première ligne non vide — c'est elle
    qui doit porter ``PVObject_=…`` ; (1, '') pour un fichier vide."""
    for numero, ligne in enumerate(text.splitlines(), start=1):
        if ligne.strip():
            return numero, ligne.strip()
    return 1, ''


# ── Table de correspondance — volontairement un sous-ensemble EXPLICITE. ──
#
# ``(champ FicheTechnique, conversion)`` ; conversion ∈ {'float', 'int',
# 'float_m_to_mm' (mètres PVsyst → millimètres), 'float_w_to_kw' (watts
# PVsyst → kilowatts)} — toutes des facteurs d'unité universels, jamais une
# hypothèse propre au calcul solaire.
MODULE_FIELD_MAP = {
    'PNom': ('pmax_wc', 'float'),
    'Voc': ('voc_v', 'float'),
    'Isc': ('isc_a', 'float'),
    # CALX356 — un vrai .PAN (pvlib tests/data/ET-M772BH550GL.PAN, PVsyst
    # 7.2) écrit ``Vmp``/``Imp`` ; ``Vmpp``/``Impp`` restent lus (CAL117).
    'Vmp': ('vmp_v', 'float'),
    'Imp': ('imp_a', 'float'),
    'Vmpp': ('vmp_v', 'float'),
    'Impp': ('imp_a', 'float'),
    'Weight': ('poids_kg', 'float'),
    'Width': ('largeur_mm', 'float_m_to_mm'),
    'Height': ('longueur_mm', 'float_m_to_mm'),
    'Depth': ('epaisseur_mm', 'float_m_to_mm'),
    # CALX356 — déjà en %/°C dans PVsyst (``muPmpReq=-0.340``) : direct.
    'muPmpReq': ('temp_coeff_pmax_pct_c', 'float'),
    # CALX356 — PVsyst publie ``muVocSpec`` en mV/°C ; la fiche attend le
    # coefficient RELATIF (%/°C), rapporté à la Voc STC du MÊME fichier :
    # mV/°C ÷ (Voc × 1000 mV) × 100 = muVocSpec ÷ (Voc × 10). C'est la
    # définition du coefficient relatif, pas une hypothèse ; sans ``Voc``
    # lisible dans le fichier, la clé reste dans ``non_reconnus``.
    'muVocSpec': ('temp_coeff_voc_pct_c', 'mv_par_c_relatif_voc'),
    # Facteur de bifacialité PVsyst en fraction (0.700) → % de la fiche.
    'BifacialityFactor': ('bifacialite_pct', 'fraction_to_pct'),
    # Tolérance haute de Pmax, déjà en % dans PVsyst (``PNomTolUp=0.90``).
    'PNomTolUp': ('tolerance_pmax_max_pct', 'float'),
}
# ``muISC`` (mA/°C) n'a AUCUN champ de destination (la fiche ne porte pas de
# coefficient Isc) : il reste dans ``non_reconnus``, jamais deviné.

ONDULEUR_FIELD_MAP = {
    'Pnom': ('ond_ac_kw', 'float_w_to_kw'),
    # CALX356 — un vrai .OND (bloc ``Converter=TConverter``) publie la
    # puissance AC nominale ``PNomConv`` DÉJÀ en kW (``PNomConv=250.000``).
    'PNomConv': ('ond_ac_kw', 'float'),
    'NbMPPT': ('ond_n_mppt', 'int'),
    'VMppMin': ('ond_mppt_v_min', 'float'),
    'VMPPMax': ('ond_mppt_v_max', 'float'),
    'VAbsMax': ('ond_v_max_abs', 'float'),
    'IMaxMPP': ('ond_i_max_mppt_a', 'float'),
    'EfficMax': ('ond_rendement_max_pct', 'float'),
    'EfficEuro': ('ond_rendement_euro_pct', 'float'),
    # Pertes de nuit PVsyst en watts — la fiche les attend en watts.
    'Night_Loss': ('ond_conso_nuit_w', 'float'),
    'MonoTri': ('ond_phases', 'mono_tri'),
}

# Clés de structure PVsyst — jamais des données de fiche, jamais listées en
# « non reconnu » (ce ne sont pas des champs que l'utilisateur attend de
# voir traduits).
_CLES_STRUCTURE = {'PVObject_'}


def _est_structure(key, value):
    """CALX356 — en-têtes de sous-objets d'un vrai fichier PVsyst :
    ``PVObject_Commercial=pvCommercial``, ``PVObject_IAM=pvIAM``,
    ``Converter=TConverter``, ``ProfilPIO=TCubicProfile`` (nom de classe
    Delphi ``T…``). Ce ne sont pas des valeurs de fiche."""
    if key in _CLES_STRUCTURE or key.startswith('PVObject_'):
        return True
    return (len(value) > 1 and value[0] == 'T' and value[1].isupper()
            and value.isalnum())


def parse_pan_ond_text(text):
    """Parse ``clé=valeur`` à plat depuis le texte d'un .PAN/.OND — ignore
    les lignes sans ``=``, les lignes vides, et les en-têtes de
    sous-section (valeur vide, ex. ``PVObject_Commercial=``). Rend un
    ``dict[str, str]`` (dernière occurrence gagne, comme le format PVsyst le
    veut pour les clés du bloc électrique principal)."""
    raw = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        value = value.strip()
        if not key or not value:
            continue
        raw[key] = value
    return raw


def detect_type(raw):
    """Détecte ``'module'``/``'onduleur'``/``None`` depuis la ligne
    ``PVObject_=...`` — heuristique volontairement large (``pvinverter``,
    ``ondinverter``… contiennent tous ``inv``) car l'orthographe exacte
    varie selon la version de PVsyst source du fichier."""
    marqueur = (raw.get('PVObject_') or '').lower()
    if 'module' in marqueur:
        return 'module'
    if 'inv' in marqueur:
        return 'onduleur'
    return None


_PHASES = {'mono': 1, 'tri': 3}


def _convertir(valeur_str, conversion, raw=None):
    if conversion == 'int':
        return int(Decimal(valeur_str))
    if conversion == 'mono_tri':
        phases = _PHASES.get(valeur_str.strip().lower())
        if phases is None:
            raise ValueError(valeur_str)
        return phases
    nombre = Decimal(valeur_str)
    if conversion == 'float_m_to_mm':
        return nombre * Decimal('1000')
    if conversion == 'float_w_to_kw':
        return nombre / Decimal('1000')
    if conversion == 'fraction_to_pct':
        return nombre * Decimal('100')
    if conversion == 'mv_par_c_relatif_voc':
        voc = Decimal((raw or {}).get('Voc', ''))
        if voc <= 0:
            raise ValueError('Voc')
        return nombre / (voc * Decimal('10'))
    return nombre


def champs_attendus(type_fiche):
    """CALX356 — champs de ``FicheTechnique`` que la table sait remplir pour
    ce type : ceux que le fichier n'apporte pas sont LISTÉS
    (``champs_attendus_absents``), jamais remplis d'une valeur de repli."""
    table = MODULE_FIELD_MAP if type_fiche == 'module' else ONDULEUR_FIELD_MAP
    return sorted({champ for champ, _ in table.values()})


@dataclass
class PropositionImport:
    type_fiche: str
    mapping: dict = field(default_factory=dict)
    reconnus: list = field(default_factory=list)
    non_reconnus: list = field(default_factory=list)
    champs_attendus_absents: list = field(default_factory=list)


def propose_mapping(text, type_fiche_force=None):
    """Point d'entrée principal : rend une ``PropositionImport`` — jamais
    d'écriture, jamais d'effet de bord. Lève ``FichierIllisible`` si le
    type ne peut pas être déterminé (fichier vide, format inconnu)."""
    raw = parse_pan_ond_text(text)
    type_fiche = type_fiche_force or detect_type(raw)
    if type_fiche not in ('module', 'onduleur'):
        numero, contenu = _premiere_ligne(text)
        raise FichierIllisible(
            f"Ligne {numero} : « {contenu[:60]} » — un fichier PVsyst "
            "commence par « PVObject_=pvModule » (.PAN) ou "
            "« PVObject_=pvGInverter » (.OND) ; type de fiche non reconnu "
            "(fichier vide, tronqué, ou format non-PVsyst).", ligne=numero)

    champ_map = MODULE_FIELD_MAP if type_fiche == 'module' else ONDULEUR_FIELD_MAP
    proposition = PropositionImport(type_fiche=type_fiche)
    for key, value in raw.items():
        if _est_structure(key, value):
            continue
        entree = champ_map.get(key)
        if entree is None:
            proposition.non_reconnus.append(key)
            continue
        champ_nom, conversion = entree
        try:
            proposition.mapping[champ_nom] = _convertir(value, conversion, raw)
            proposition.reconnus.append(key)
        except (InvalidOperation, ValueError):
            # Valeur présente mais illisible pour CETTE clé précise — la
            # clé part en non-reconnue plutôt que de faire échouer tout
            # l'import sur un seul champ fautif.
            proposition.non_reconnus.append(key)
    proposition.non_reconnus.sort()
    proposition.champs_attendus_absents = [
        champ for champ in champs_attendus(type_fiche)
        if champ not in proposition.mapping]
    return proposition


def parse_pan_ond_bytes(data, filename=''):
    """Décode ``data`` (bytes) en tentant UTF-8 puis Latin-1 (les fichiers
    PVsyst historiques sont souvent en ANSI/Latin-1), puis délègue à
    ``propose_mapping``. Lève ``FichierIllisible`` si aucun encodage ne
    fonctionne."""
    # CALX356 — ``utf-8-sig`` d'abord : le vrai .OND de pvlib (CPS
    # SCH275KTL…) commence par un BOM UTF-8 ; décodé en ``utf-8`` nu, la
    # première clé devenait ``﻿PVObject_`` et le fichier était refusé.
    for encodage in ('utf-8-sig', 'latin-1'):
        try:
            texte = data.decode(encodage)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise FichierIllisible(
            f"Fichier {filename or '(sans nom)'} illisible : encodage non "
            "reconnu (ni UTF-8 ni Latin-1).")
    return propose_mapping(texte)


def champs_a_ecrire(fiche, mapping):
    """Sépare le ``mapping`` proposé en ce qui peut s'écrire (champ encore
    vide sur ``fiche``) et ce qui est DÉJÀ SAISI (jamais écrasé). Rend
    ``(a_ecrire: dict, deja_saisis: list[str])`` — pure, aucune écriture
    n'a lieu ici (c'est l'appelant, après confirmation explicite, qui
    applique ``a_ecrire``)."""
    a_ecrire = {}
    deja_saisis = []
    for champ_nom, valeur in mapping.items():
        actuel = getattr(fiche, champ_nom, None)
        if actuel is None or actuel == '':
            a_ecrire[champ_nom] = valeur
        else:
            deja_saisis.append(champ_nom)
    return a_ecrire, sorted(deja_saisis)
