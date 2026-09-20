"""CAL140 — la perte thermique vient de la FICHE, heure par heure, ou se tait.

LE CONSTAT
----------
La perte thermique valait 8 % forfaitaires pour tout le monde
(``apps/ventes/solar_design.py``, poste ``temperature``), et le seul calcul
thermique fin du dépôt vit côté site public en constantes de code
(``apps/web/src/lib/estimatorBrainV2.ts`` : coefficient −0,34 %/°C, ΔT 30 °C
pour toute la planète). Or un module posé à Ouarzazate et un module posé à
Essaouira ne chauffent pas pareil, et la fiche technique porte EXACTEMENT ce
qu'il faut pour le dire : NOCT, ou le couple Uc/Uv, et le coefficient de
puissance γ (``apps.stock.selectors.specs_for_produit`` — champs ``noct_c``,
``uc_w_m2k``, ``uv_w_m3sk``, ``temp_coeff_pmax_pct_c``, posés par CAL111).

LES DEUX MODÈLES, ET L'ORDRE DE PRÉSÉANCE
-----------------------------------------
pvlib expose ``sapm`` / ``pvsyst`` / ``faiman`` / ``noct_sam``
(https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.modelchain.ModelChain.html).
Deux suffisent ici, et on prend TOUJOURS le plus informé :

* **Faiman / PVsyst** (préféré) — ``T_cellule = T_air + G / (Uc + Uv × vent)``.
  C'est le modèle que PVsyst emploie, et il tient compte du VENT : un toit
  ventilé chauffe moins. Il exige ``uc_w_m2k`` ; sans ``uv_w_m3sk`` la fiche
  ne dit rien du vent, et l'hypothèse ``Uv = 0`` est prise ET NOMMÉE (elle est
  CONSERVATRICE : moins de refroidissement, donc plus de perte).
* **NOCT** (repli) — ``T_cellule = T_air + (NOCT − 20) / 800 × G``, la
  définition même de la NOCT. Employé quand la fiche donne ``noct_c`` sans
  ``uc_w_m2k``.

La perte horaire vaut ``γ × (T_cellule − 25)`` (γ est négatif sur une fiche :
on publie une PERTE positive). Les heures sans soleil ne pèsent rien : la
moyenne est PONDÉRÉE PAR L'IRRADIANCE, parce qu'une perte thermique à 3 h du
matin ne coûte aucun kWh.

CE QUI SE PASSE QUAND LA FICHE NE DIT RIEN
------------------------------------------
Aucun modèle n'est appliqué, AUCUNE valeur n'est fabriquée : le service rend
``calculable = False`` avec son motif, et l'appelant CONSERVE le poste
forfaitaire qu'il avait — en l'ÉTIQUETANT ``hypothese`` (c'est ce que fait
``poste_thermique``). Un forfait annoncé est honnête ; un forfait présenté
comme un calcul ne l'est pas.

Module PUR : aucune base, aucun réseau, aucun prix.
"""
from __future__ import annotations

__all__ = ['MODELE_FAIMAN', 'MODELE_NOCT', 'TEMPERATURE_STC_C',
           'perte_thermique', 'poste_thermique', 'temperature_cellule']

#: Température de référence STC — la définition de la puissance crête.
TEMPERATURE_STC_C = 25.0

MODELE_FAIMAN = 'faiman'
MODELE_NOCT = 'noct'

#: Irradiance de définition de la NOCT (W/m²) et température d'air associée —
#: ce sont les conditions NOCT elles-mêmes, pas des réglages.
NOCT_IRRADIANCE_W_M2 = 800.0
NOCT_TEMPERATURE_AIR_C = 20.0


def _nombre(valeur):
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    if nombre != nombre:
        return None
    return nombre


def temperature_cellule(*, t_air_c, irradiance_w_m2, modele, noct_c=None,
                        uc_w_m2k=None, uv_w_m3sk=None, vent_m_s=None):
    """La température de cellule d'UNE heure, par le modèle demandé.

    Aucune valeur n'est supposée : les paramètres manquants font rendre
    ``None`` (l'appelant a déjà décidé du modèle et de ce qu'il sait).
    """
    t_air = _nombre(t_air_c)
    irradiance = _nombre(irradiance_w_m2)
    if t_air is None or irradiance is None or irradiance < 0:
        return None
    if modele == MODELE_FAIMAN:
        uc = _nombre(uc_w_m2k)
        if uc is None or uc <= 0:
            return None
        uv = _nombre(uv_w_m3sk) or 0.0
        vent = _nombre(vent_m_s) or 0.0
        echange = uc + uv * max(0.0, vent)
        if echange <= 0:
            return None
        return t_air + irradiance / echange
    if modele == MODELE_NOCT:
        noct = _nombre(noct_c)
        if noct is None:
            return None
        return t_air + ((noct - NOCT_TEMPERATURE_AIR_C)
                        / NOCT_IRRADIANCE_W_M2) * irradiance
    return None


def _modele_de_la_fiche(specs):
    """Le modèle applicable et ses paramètres, LUS sur la fiche seule."""
    uc = _nombre(specs.get('uc_w_m2k'))
    noct = _nombre(specs.get('noct_c'))
    if uc is not None and uc > 0:
        return MODELE_FAIMAN, {
            'uc_w_m2k': uc,
            'uv_w_m3sk': _nombre(specs.get('uv_w_m3sk')),
        }
    if noct is not None:
        return MODELE_NOCT, {'noct_c': noct}
    return None, {}


def perte_thermique(specs_module, points):
    """La perte thermique MOYENNE (%) d'une série horaire, ou son silence.

    Args:
        specs_module: le bloc plat de ``apps.stock.selectors.specs_for_produit``
            pour le PANNEAU retenu (``noct_c``, ``uc_w_m2k``, ``uv_w_m3sk``,
            ``temp_coeff_pmax_pct_c``). Un dict vide = fiche absente.
        points: la série horaire — dicts portant ``t2m_c`` (température d'air),
            ``gi_w_m2`` (irradiance sur le plan ; ``gh_w_m2`` accepté pour un
            TMY) et, facultativement, ``ws10m`` (vent). C'est exactement la
            forme rendue par ``services/pvgis_serie`` (``serie_horaire`` et
            ``tmy``).

    Returns:
        dict — ``calculable``, ``pct`` (perte moyenne pondérée par
        l'irradiance, ``None`` si incalculable), ``source`` (``'fiche'`` ou
        ``None``), ``modele``, ``parametres``, ``motif`` (le français à
        afficher), ``heures_retenues``, ``temperature_cellule_moyenne_c``,
        ``temperature_cellule_max_c``.

    Ne lève jamais : une fiche muette est une RÉPONSE (« non calculable »),
    pas une erreur.
    """
    specs = specs_module if isinstance(specs_module, dict) else {}
    gamma = _nombre(specs.get('temp_coeff_pmax_pct_c'))
    modele, parametres = _modele_de_la_fiche(specs)

    vide = {
        'calculable': False, 'pct': None, 'source': None, 'modele': None,
        'parametres': {}, 'heures_retenues': 0,
        'temperature_cellule_moyenne_c': None,
        'temperature_cellule_max_c': None,
    }
    if gamma is None:
        return dict(vide, motif=(
            "La fiche du panneau ne porte pas son coefficient de puissance "
            "(« temp_coeff_pmax_pct_c ») : la perte thermique ne peut pas "
            "être calculée. Le poste forfaitaire est conservé et annoncé "
            "comme hypothèse."))
    if modele is None:
        return dict(vide, motif=(
            "La fiche du panneau ne porte ni NOCT ni coefficient d'échange "
            "Uc : la perte thermique ne peut pas être calculée. Le poste "
            "forfaitaire est conservé et annoncé comme hypothèse."))

    somme_ponderee = 0.0
    somme_irradiance = 0.0
    somme_temperature = 0.0
    heures = 0
    t_max = None
    for point in (points or []):
        if not isinstance(point, dict):
            continue
        irradiance = _nombre(point.get('gi_w_m2'))
        if irradiance is None:
            irradiance = _nombre(point.get('gh_w_m2'))
        if irradiance is None or irradiance <= 0:
            # Une perte thermique la nuit ne coûte aucun kWh : l'heure ne
            # pèse rien dans la moyenne (pondération par l'irradiance).
            continue
        t_cellule = temperature_cellule(
            t_air_c=point.get('t2m_c'), irradiance_w_m2=irradiance,
            modele=modele, vent_m_s=point.get('ws10m'), **parametres)
        if t_cellule is None:
            continue
        # γ est NÉGATIF sur une fiche (−0,35 %/°C) : au-dessus de 25 °C la
        # perte est positive, en dessous elle est négative (un GAIN par temps
        # froid, réel et conservé tel quel — l'effacer gonflerait la perte).
        perte_pct = -gamma * (t_cellule - TEMPERATURE_STC_C)
        somme_ponderee += perte_pct * irradiance
        somme_irradiance += irradiance
        somme_temperature += t_cellule
        heures += 1
        t_max = t_cellule if t_max is None else max(t_max, t_cellule)

    if heures == 0 or somme_irradiance <= 0:
        return dict(vide, motif=(
            "La série horaire fournie ne porte aucune heure ensoleillée "
            "exploitable (irradiance et température) : la perte thermique "
            "n'est pas calculée."))

    hypotheses = []
    if modele == MODELE_FAIMAN and parametres.get('uv_w_m3sk') is None:
        hypotheses.append(
            "la fiche ne donne pas Uv : l'effet du vent est ignoré "
            '(hypothèse conservatrice, Uv = 0)')

    return {
        'calculable': True,
        'pct': round(somme_ponderee / somme_irradiance, 3),
        'source': 'fiche',
        'modele': modele,
        'parametres': dict(parametres, temp_coeff_pmax_pct_c=gamma),
        'heures_retenues': heures,
        'temperature_cellule_moyenne_c': round(somme_temperature / heures, 2),
        'temperature_cellule_max_c': round(t_max, 2),
        'motif': (
            'Perte thermique calculée heure par heure sur la série '
            f'({modele}), depuis la fiche produit'
            + (' — ' + ' ; '.join(hypotheses) if hypotheses else '') + '.'),
    }


def poste_thermique(specs_module, points, *, forfait_pct=None,
                    source_forfait='hypothese'):
    """Le POSTE de perte thermique prêt pour CAL139 — calculé, ou annoncé.

    Args:
        forfait_pct: le poste forfaitaire à CONSERVER quand la fiche ne permet
            aucun calcul. ``None`` ⇒ aucun poste n'est rendu du tout (rien
            n'est inventé, pas même un forfait).

    Returns:
        ``(poste | None, diagnostic)`` — ``poste`` est un dict de la forme
        attendue par ``services/pertes.py`` ; ``diagnostic`` est le retour
        complet de :func:`perte_thermique`, à afficher tel quel.
    """
    diagnostic = perte_thermique(specs_module, points)
    if diagnostic['calculable']:
        return {
            'poste': 'thermique',
            'libelle': 'Échauffement des modules',
            'pct': diagnostic['pct'],
            'source': 'fiche',
            'reference': diagnostic['motif'],
        }, diagnostic

    if forfait_pct is None:
        return None, diagnostic
    return {
        'poste': 'thermique',
        'libelle': 'Échauffement des modules (forfait)',
        'pct': float(forfait_pct),
        'source': source_forfait,
        'reference': diagnostic['motif'],
    }, diagnostic
