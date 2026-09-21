"""CALX169 — ÉTAPE « ohmique DC » : la chute RÉELLE, heure par heure.

CE QUI EXISTAIT, ET POURQUOI IL NE SUFFISAIT PAS
-------------------------------------------------
Le dépôt porte DEUX représentations de la même perte, jamais réconciliées :

* ``services/cables.py`` mesure la liaison sur les longueurs du PLAN et
  publie une ``chute_tension_pct`` par câble, au courant de dimensionnement
  (donc au STC) ;
* le poste ``ohmique_dc`` de ``services/pertes.py`` reste, lui, un
  pourcentage SAISI, indépendant de ce métré.

Cette étape ferme l'écart : elle reprend la section et la longueur RETENUES
par ``cables_du_calepinage`` et calcule la perte en ``R·I²`` HEURE PAR HEURE.
Le poste saisi du même nom est écarté par l'arbitrage de CALX149 et publié
dans ``entree.saisie_ecartee`` — jamais soustrait une seconde fois.

POURQUOI L'HEURE PAR HEURE CHANGE LE RÉSULTAT
-----------------------------------------------
La perte est quadratique en courant tandis que l'énergie est linéaire : une
installation qui passe l'essentiel de l'année en dessous de sa puissance STC
perd, en énergie, nettement moins que la fraction calculée au STC. PVsyst
chiffre l'ordre de grandeur : la perte pondérée en énergie vaut « de l'ordre
de 60 % » de la fraction déclarée au STC
(https://www.pvsyst.com/help/project-design/array-and-system-losses/
ohmic-losses/array-ohmic-wiring-loss.html). Le rapport exact dépend du profil
de production du site : il est CALCULÉ ici, jamais supposé.

CE QU'ELLE LIT DANS ``contexte``
----------------------------------
* ``norme`` — le verdict de ``services/norme.py::norme_applicable``. Non
  applicable (règle D5, le cas d'une société ``pays=ma`` sans norme choisie)
  ⇒ aucune section n'est publiable, donc étape OMISE avec le motif de la
  norme repris TEL QUEL.
* ``cables`` — le bloc de ``services/cables.py::cables_du_calepinage``
  (``{cables, longueurs, omissions}``), dont le câble de repère ``W1`` porte
  ``section_mm2``, ``longueur_m``, ``nb_conducteurs`` et l'origine de sa
  longueur. Absent ⇒ étape OMISE en nommant ce qui manque.
* ``electrique['chainage']`` — ``modules``, ``modules_par_chaine`` et
  ``puissance_module_wc`` (bloc de ``services/chaines.py``).
* ``fiche_module['vmp_v']`` — la tension au point de puissance d'un module.
* ``suivi_mpp_par_module`` / ``cheminement`` — le cas micro-onduleur, où il
  n'existe AUCUNE liaison DC de chaîne (voir plus bas).

LE CAS MICRO-ONDULEUR
-----------------------
Un groupe déclaré sous micro-onduleur n'a pas de liaison DC de chaîne : la
seule perte continue porte sur le câble module → micro-onduleur, dont la
longueur et la section sont SAISIES. Non saisies ⇒ étape OMISE en les
nommant. La valeur publiée par OpenSolar pour cette configuration
(« Micro-inverter system | DC Wiring 0,1 % »,
https://support.opensolar.com/hc/en-us/articles/4406931180313-Stringing-
Micro-Inverters-and-Power-Optimizers) est un REPÈRE de test cité, jamais un
défaut de ce module.
"""
from __future__ import annotations

from apps.calepinage.services import etapes
from core.electrique.cables import RHO_CUIVRE_20C

LIBELLE = 'Pertes ohmiques DC'

#: Le repère du câble DC de chaîne dans le bloc ``cables`` (CAL131).
REPERE_DC = 'W1'

#: Le coefficient de la formule de chute continue : 2 pour l'aller-retour.
#: C'est celui qu'emploie ``core/electrique/cables.py::chute_tension_v`` pour
#: le continu, et la longueur reste la longueur SIMPLE de la liaison.
COEFFICIENT_ALLER_RETOUR = 2.0

#: Les champs SAISIS du cheminement pour la liaison module → micro-onduleur.
CHAMP_MICRO_LONGUEUR = 'cheminement.module_vers_micro_onduleur_m'
CHAMP_MICRO_SECTION = 'cheminement.module_vers_micro_onduleur_mm2'

#: La clé de ``contexte`` qui déclare un suivi de point de puissance module
#: par module (même déclaration que pour CALX167).
CLE_SUIVI_MPP = 'suivi_mpp_par_module'
SUIVI_MICRO_ONDULEUR = 'micro_onduleur'

REFERENCE_PVSYST = (
    'PVsyst — Array ohmic wiring loss : Ploss = Rw·I², la perte pondérée en '
    'énergie valant « de l\'ordre de 60 % » de la fraction déclarée au STC '
    '(https://www.pvsyst.com/help/project-design/array-and-system-losses/'
    'ohmic-losses/array-ohmic-wiring-loss.html)')

MOTIF_SANS_CABLE = (
    "Aucun câble DC de repère « {repere} » n'est publié par le métré du "
    "plan : sans section ni longueur retenues, la perte ohmique n'est pas "
    "calculable et l'étape est OMISE. {detail}")

MOTIF_SANS_TENSION = (
    "La tension continue de la liaison n'est pas connue : il y faut le "
    "nombre de modules par chaîne (bloc « electrique.chainage ») et le Vmp "
    "de la fiche module. L'étape est OMISE plutôt que de supposer une "
    "tension.")

MOTIF_SANS_PUISSANCE_STC = (
    "La puissance STC du champ n'est pas connue (bloc « electrique.chainage "
    "» : modules et puissance_module_wc) : la fraction au STC, qui sert de "
    "repère au calcul horaire, n'est pas publiable. Étape OMISE.")

MOTIF_MICRO_SANS_SAISIE = (
    "Groupe déclaré sous micro-onduleur : il n'existe aucune liaison DC de "
    "chaîne, et la seule perte continue porte sur le câble module → "
    "micro-onduleur, dont la longueur et la section sont SAISIES. Elles ne "
    "le sont pas : l'étape est OMISE, et aucun forfait n'est appliqué à "
    "leur place.")

MOTIF_SERIE_ILLISIBLE = (
    "Aucune colonne d'énergie lisible sur la série : la perte ohmique se "
    "calcule sur le courant de chaque heure, elle n'a rien à quoi "
    "s'appliquer. Étape OMISE.")

__all__ = ['appliquer', 'LIBELLE', 'REPERE_DC', 'CHAMP_MICRO_LONGUEUR',
           'CHAMP_MICRO_SECTION', 'CLE_SUIVI_MPP', 'SUIVI_MICRO_ONDULEUR']


def appliquer(serie, contexte):
    """``(serie, etape)`` — la perte ``R·I²`` de la liaison continue."""
    contexte = contexte if isinstance(contexte, dict) else {}

    motif_norme = _motif_norme(contexte)
    if motif_norme:
        return serie, etapes.etape_omise(LIBELLE, motif_norme)

    colonne = etapes.colonne_energie(serie)
    if colonne is None:
        return serie, etapes.etape_omise(LIBELLE, MOTIF_SERIE_ILLISIBLE)

    if _sous_micro_onduleur(contexte):
        liaison = _liaison_micro_onduleur(contexte)
    else:
        liaison = _liaison_de_chaine(contexte)
    if isinstance(liaison, dict) and liaison.get('motif_omission'):
        return serie, liaison

    return _appliquer_liaison(serie, colonne, liaison)


# ── la liaison, et d'où viennent ses trois grandeurs ────────────────────

def _sous_micro_onduleur(contexte):
    """Le groupe est-il DÉCLARÉ sous micro-onduleur ?"""
    declare = str(contexte.get(CLE_SUIVI_MPP) or '').strip().lower()
    return declare == SUIVI_MICRO_ONDULEUR


def _liaison_de_chaine(contexte):
    """La liaison DC de chaîne : section et longueur du métré du plan."""
    cable = _cable(contexte, REPERE_DC)
    if cable is None:
        return etapes.etape_omise(
            LIBELLE,
            MOTIF_SANS_CABLE.format(repere=REPERE_DC,
                                    detail=_detail_omissions(contexte)),
            champ='cables[%s]' % REPERE_DC)

    section = _nombre(cable.get('section_mm2'))
    longueur = _nombre(cable.get('longueur_m'))
    if not section or longueur is None:
        return etapes.etape_omise(
            LIBELLE,
            MOTIF_SANS_CABLE.format(repere=REPERE_DC,
                                    detail=_detail_omissions(contexte)),
            champ='cables[%s].section_mm2' % REPERE_DC)

    conducteurs = _nombre(cable.get('nb_conducteurs')) or 2.0
    paires = max(1.0, conducteurs / 2.0)

    chainage = _chainage(contexte)
    modules_par_chaine = _nombre(chainage.get('modules_par_chaine'))
    fiche_module = contexte.get('fiche_module') or {}
    vmp = _nombre(fiche_module.get('vmp_v'))
    if not modules_par_chaine or not vmp:
        return etapes.etape_omise(LIBELLE, MOTIF_SANS_TENSION,
                                  champ='fiche_module.vmp_v')

    puissance_stc = _puissance_stc(chainage)
    if puissance_stc is None:
        return etapes.etape_omise(
            LIBELLE, MOTIF_SANS_PUISSANCE_STC,
            champ='electrique.chainage.puissance_module_wc')

    return {
        'champ': 'cables[%s]' % REPERE_DC,
        'liaison': 'chaîne continue module → onduleur',
        'section_mm2': section,
        'longueur_m': longueur,
        'branches_paralleles': paires,
        'tension_v': modules_par_chaine * vmp,
        'puissance_stc_w': puissance_stc,
        'origine_longueur': cable.get('longueur_origine') or 'plan',
    }


def _liaison_micro_onduleur(contexte):
    """La liaison module → micro-onduleur : longueur ET section SAISIES."""
    cheminement = contexte.get('cheminement') or {}
    longueur = _nombre(cheminement.get('module_vers_micro_onduleur_m'))
    section = _nombre(cheminement.get('module_vers_micro_onduleur_mm2'))
    if longueur is None or not section:
        champ = (CHAMP_MICRO_LONGUEUR if longueur is None
                 else CHAMP_MICRO_SECTION)
        return etapes.etape_omise(LIBELLE, MOTIF_MICRO_SANS_SAISIE,
                                  champ=champ)

    chainage = _chainage(contexte)
    modules = _nombre(chainage.get('modules'))
    fiche_module = contexte.get('fiche_module') or {}
    vmp = _nombre(fiche_module.get('vmp_v'))
    if not modules or not vmp:
        return etapes.etape_omise(LIBELLE, MOTIF_SANS_TENSION,
                                  champ='fiche_module.vmp_v')

    puissance_stc = _puissance_stc(chainage)
    if puissance_stc is None:
        return etapes.etape_omise(
            LIBELLE, MOTIF_SANS_PUISSANCE_STC,
            champ='electrique.chainage.puissance_module_wc')

    return {
        'champ': CHAMP_MICRO_LONGUEUR,
        'liaison': 'module → micro-onduleur',
        'section_mm2': section,
        'longueur_m': longueur,
        'branches_paralleles': modules,
        'tension_v': vmp,
        'puissance_stc_w': puissance_stc,
        'origine_longueur': 'saisie',
    }


# ── le calcul horaire ────────────────────────────────────────────────────

def _appliquer_liaison(serie, colonne, liaison):
    """La perte ``R·I²`` heure par heure, et la fraction pondérée publiée."""
    resistance = _resistance_ohm(liaison['longueur_m'],
                                 liaison['section_mm2'])
    facteur_kw = etapes.FACTEURS_KW[colonne]
    denominateur = (liaison['tension_v'] ** 2
                    * liaison['branches_paralleles'])

    points = []
    energie_avant = 0.0
    energie_perdue = 0.0
    for point in serie.get('points') or []:
        valeur = point.get(colonne)
        puissance_w = _puissance_w(valeur, facteur_kw)
        if puissance_w is None:
            points.append(point)
            continue
        fraction = _fraction(resistance, puissance_w, denominateur)
        copie = dict(point)
        copie[colonne] = float(valeur) * (1.0 - fraction)
        points.append(copie)
        energie_avant += puissance_w
        energie_perdue += puissance_w * fraction

    suite = dict(serie)
    suite['points'] = points
    suite['colonne_energie'] = colonne

    perte_stc = _fraction(resistance, liaison['puissance_stc_w'],
                          denominateur)
    perte_ponderee = (energie_perdue / energie_avant
                      if energie_avant > 0.0 else 0.0)
    entree = dict(liaison)
    entree.pop('origine_longueur', None)
    entree.update({
        'resistance_ohm': round(resistance, 6),
        'perte_stc_pct': round(100.0 * perte_stc, 4),
        'perte_ponderee_pct': round(100.0 * perte_ponderee, 4),
        'formule': 'Ploss(h) = R · I(h)², I(h) = P(h) / (U · n)',
        'rho_ohm_mm2_par_m': RHO_CUIVRE_20C,
    })
    return suite, etapes.etape_appliquee(
        LIBELLE,
        source=liaison['origine_longueur'],
        entree=entree,
        reference=REFERENCE_PVSYST)


def _resistance_ohm(longueur_m, section_mm2):
    """``R = 2 · ρ · L / S`` (Ω) — le 2 porte l'aller-retour, pas la longueur."""
    return (COEFFICIENT_ALLER_RETOUR * RHO_CUIVRE_20C
            * float(longueur_m) / float(section_mm2))


def _fraction(resistance, puissance_w, denominateur):
    """``R·P / (U²·n)`` — la part perdue, bornée à 1 (jamais une énergie < 0)."""
    if denominateur <= 0.0 or puissance_w <= 0.0:
        return 0.0
    return min(1.0, resistance * puissance_w / denominateur)


def _puissance_w(valeur, facteur_kw):
    """La puissance du point en WATTS, ou ``None`` si elle est illisible."""
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur) * facteur_kw * 1000.0
    except (TypeError, ValueError):
        return None


# ── lectures de contexte ─────────────────────────────────────────────────

def _motif_norme(contexte):
    """Le motif de la norme NON applicable, repris tel quel, ou ``''``."""
    norme = contexte.get('norme')
    if not isinstance(norme, dict) or norme.get('applicable', False):
        return ''
    return (norme.get('motif') or '').strip()


def _cable(contexte, repere):
    """Le câble de ce repère dans le bloc ``cables``, ou ``None``."""
    bloc = contexte.get('cables')
    if not isinstance(bloc, dict):
        return None
    for cable in bloc.get('cables') or ():
        if isinstance(cable, dict) and cable.get('repere') == repere:
            return cable
    return None


def _detail_omissions(contexte):
    """Ce que le métré dit lui-même, pour ne pas le redire autrement."""
    bloc = contexte.get('cables')
    if not isinstance(bloc, dict):
        return "Le bloc « cables » n'est pas fourni au contexte."
    omissions = [str(motif) for motif in (bloc.get('omissions') or ())]
    return ' '.join(omissions) if omissions else ''


def _chainage(contexte):
    electrique = contexte.get('electrique')
    if not isinstance(electrique, dict):
        return {}
    chainage = electrique.get('chainage')
    return chainage if isinstance(chainage, dict) else {}


def _puissance_stc(chainage):
    """La puissance STC du champ en WATTS, ou ``None``."""
    modules = _nombre(chainage.get('modules'))
    unitaire = _nombre(chainage.get('puissance_module_wc'))
    if not modules or not unitaire:
        return None
    return modules * unitaire


def _nombre(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None
