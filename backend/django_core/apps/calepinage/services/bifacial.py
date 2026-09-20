"""CAL141 — le gain bifacial : calculé et PUBLIÉ À PART, ou pas du tout.

LE CONSTAT
----------
Le moteur de calepinage ne connaît RIEN du bifacial
(``docs/moteur-calepinage.md``, non-objectif n°11 : « aucune mention de gain
bifacial, d'albédo, ni de calcul face arrière ») et la fiche produit n'avait
qu'un booléen avant CAL112 (``bifacialite_pct``,
``apps.stock.selectors.specs_for_produit``). PVsyst, lui, calcule l'irradiance
arrière par FACTEURS DE VUE, avec albédo, hauteur de pose, taux d'occupation
et un mismatch arrière
(https://www.pvsyst.com/help/project-design/bifacial-systems/index.html).

LA RÈGLE DE CE MODULE
---------------------
1. **Le gain n'est calculé QUE s'il est sourçable.** Bifacialité de la fiche,
   albédo SAISI (avec sa source), hauteur de pose, taux d'occupation et pas de
   rangée : il en manque UN, le gain n'est pas calculé et la raison NOMME le
   paramètre absent. Un albédo « 0,2 par défaut » serait exactement le chiffre
   inventé que la règle fondateur interdit — le sol d'une terrasse en
   gravillon blanc et celui d'une toiture bitume ne renvoient pas la même
   lumière, et personne ne peut le deviner à distance.
2. **Le gain est un POSTE SÉPARÉ**, jamais fondu dans une production annoncée.
   Il est publié avec ses quatre facteurs, chacun nommé : on doit pouvoir le
   retirer d'un chiffre en une soustraction visible.
3. **Rien n'est extrapolé.** Le mismatch arrière n'est appliqué que s'il est
   saisi ; sinon le gain est publié BRUT et le dit.

LE MODÈLE, ET POURQUOI CHAQUE FACTEUR EST DÉRIVABLE
---------------------------------------------------
``gain = bifacialité × albédo × FV_arrière→sol × fraction_de_sol_vue``, puis
``× (1 − mismatch_arrière)`` s'il est saisi.

* ``FV_arrière→sol = (1 + cos β) / 2`` — le facteur de vue ISOTROPE d'un plan
  incliné de β vers le sol, vu par sa face ARRIÈRE (le complément du facteur
  de vue au ciel de la face avant, ``(1 + cos β)/2`` et ``(1 − cos β)/2``).
  C'est de la géométrie, pas un réglage.
* ``fraction_de_sol_vue = 2·arctan(largeur_libre / (2·hauteur)) / π`` — la
  fraction de demi-plan angulaire qu'occupe, depuis la face arrière, la bande
  de sol LIBRE entre deux rangées (``largeur_libre = pas × (1 − occupation)``).
  Là encore de la géométrie exacte (angle sous-tendu par une bande à une
  hauteur donnée), et c'est par là que la hauteur de pose et le taux
  d'occupation entrent réellement : un module posé à plat sur le toit ne voit
  presque aucun sol, un module surélevé au-dessus d'une bande libre en voit
  beaucoup.

Module PUR : aucune base, aucun réseau, aucun prix.
"""
from __future__ import annotations

import math

__all__ = ['PARAMETRES_REQUIS', 'gain_bifacial', 'poste_bifacial']

#: Les paramètres SANS LESQUELS aucun gain n'est calculé, et le libellé
#: français que le motif emploie pour nommer celui qui manque.
PARAMETRES_REQUIS = (
    ('bifacialite_pct', 'la bifacialité du module (fiche produit)'),
    ('albedo', "l'albédo du sol (saisi)"),
    ('hauteur_pose_m', 'la hauteur de pose (m)'),
    ('taux_occupation', "le taux d'occupation du sol (GCR)"),
    ('pas_rangee_m', 'le pas entre rangées (m)'),
)


def _nombre(valeur):
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    if nombre != nombre or nombre in (float('inf'), float('-inf')):
        return None
    return nombre


def gain_bifacial(*, bifacialite_pct=None, albedo=None, hauteur_pose_m=None,
                  taux_occupation=None, pas_rangee_m=None,
                  inclinaison_deg=None, mismatch_arriere_pct=None,
                  source_albedo=None):
    """Le gain de face arrière, en % de la production de face avant.

    Args:
        bifacialite_pct: le coefficient de bifacialité de la FICHE (% — la
            part de rendement de la face arrière par rapport à l'avant).
        albedo: l'albédo du sol, SAISI (0 à 1). ``source_albedo`` dit d'où il
            vient (``saisie``/``mesure``/``societe``) — un albédo sans source
            est accepté mais publié comme non sourcé.
        hauteur_pose_m: hauteur de la face arrière au-dessus du sol (m).
        taux_occupation: GCR (0 à 1) — la part du sol couverte par les
            modules.
        pas_rangee_m: le pas entre rangées (m).
        inclinaison_deg: l'inclinaison du plan (°). Absente ⇒ le facteur de
            vue n'est pas calculable, donc aucun gain.
        mismatch_arriere_pct: le mismatch de face arrière, SAISI. Absent ⇒ le
            gain est publié BRUT et l'hypothèse est annoncée.

    Returns:
        dict — ``calculable``, ``gain_pct`` (``None`` si incalculable),
        ``facteurs`` (chacun nommé), ``manquants``, ``motif``, ``source``,
        ``hypotheses``.

    Ne lève jamais : un paramètre absent est une RÉPONSE (« non calculable »),
    pas une erreur.
    """
    valeurs = {
        'bifacialite_pct': _nombre(bifacialite_pct),
        'albedo': _nombre(albedo),
        'hauteur_pose_m': _nombre(hauteur_pose_m),
        'taux_occupation': _nombre(taux_occupation),
        'pas_rangee_m': _nombre(pas_rangee_m),
    }
    inclinaison = _nombre(inclinaison_deg)

    manquants = [libelle for cle, libelle in PARAMETRES_REQUIS
                 if valeurs[cle] is None]
    if inclinaison is None:
        manquants.append("l'inclinaison du plan (°)")

    if manquants:
        return {
            'calculable': False, 'gain_pct': None, 'facteurs': {},
            'manquants': manquants, 'source': None, 'hypotheses': [],
            'motif': (
                'Le gain bifacial n’est PAS calculé : il manque '
                + ', '.join(manquants)
                + '. Aucun gain n’est supposé — une face arrière dont on ne '
                  'connaît ni le sol ni la hauteur de pose ne produit pas un '
                  'chiffre, elle produit un silence.'),
        }

    hors_bornes = []
    if not 0.0 <= valeurs['albedo'] <= 1.0:
        hors_bornes.append("l'albédo se compte de 0 à 1 "
                           f"(reçu : {valeurs['albedo']})")
    if not 0.0 < valeurs['taux_occupation'] < 1.0:
        hors_bornes.append("le taux d'occupation se compte strictement entre "
                           f"0 et 1 (reçu : {valeurs['taux_occupation']})")
    if valeurs['hauteur_pose_m'] <= 0 or valeurs['pas_rangee_m'] <= 0:
        hors_bornes.append('la hauteur de pose et le pas entre rangées '
                           'doivent être strictement positifs')
    if valeurs['bifacialite_pct'] < 0:
        hors_bornes.append('la bifacialité ne peut pas être négative')
    if hors_bornes:
        return {
            'calculable': False, 'gain_pct': None, 'facteurs': {},
            'manquants': [], 'source': None, 'hypotheses': [],
            'motif': ('Le gain bifacial n’est PAS calculé : '
                      + ' ; '.join(hors_bornes) + '.'),
        }

    # FV de la face ARRIÈRE vers le sol — géométrie isotrope d'un plan incliné.
    facteur_de_vue = (1.0 + math.cos(math.radians(inclinaison))) / 2.0
    # Fraction angulaire du sol LIBRE réellement vue depuis la face arrière.
    largeur_libre = valeurs['pas_rangee_m'] * (1.0 - valeurs['taux_occupation'])
    fraction_sol = (2.0 * math.atan(
        largeur_libre / (2.0 * valeurs['hauteur_pose_m']))) / math.pi

    gain = (valeurs['bifacialite_pct'] / 100.0) * valeurs['albedo'] \
        * facteur_de_vue * fraction_sol

    hypotheses = []
    mismatch = _nombre(mismatch_arriere_pct)
    if mismatch is None:
        hypotheses.append(
            "aucun mismatch de face arrière n'est saisi : le gain est publié "
            'BRUT (PVsyst en applique un, il n’est pas supposé ici)')
    else:
        gain *= max(0.0, 1.0 - mismatch / 100.0)

    source_albedo = (str(source_albedo).strip().lower()
                     if source_albedo else None)
    if source_albedo is None:
        hypotheses.append(
            "l'albédo est publié SANS source : il est affiché comme non "
            'sourcé, jamais présenté comme une mesure')

    return {
        'calculable': True,
        'gain_pct': round(gain * 100.0, 3),
        'facteurs': {
            'bifacialite_pct': valeurs['bifacialite_pct'],
            'albedo': valeurs['albedo'],
            'albedo_source': source_albedo,
            'hauteur_pose_m': valeurs['hauteur_pose_m'],
            'taux_occupation': valeurs['taux_occupation'],
            'pas_rangee_m': valeurs['pas_rangee_m'],
            'inclinaison_deg': inclinaison,
            'largeur_sol_libre_m': round(largeur_libre, 3),
            'facteur_de_vue_arriere_sol': round(facteur_de_vue, 4),
            'fraction_de_sol_vue': round(fraction_sol, 4),
            'mismatch_arriere_pct': mismatch,
        },
        'manquants': [],
        'source': 'fiche+saisie',
        'hypotheses': hypotheses,
        'motif': (
            'Gain de face arrière calculé par facteurs de vue : bifacialité '
            '(fiche) × albédo (saisi) × facteur de vue arrière→sol × fraction '
            'de sol libre vue depuis la rangée'
            + (' — ' + ' ; '.join(hypotheses) if hypotheses else '') + '.'),
    }


def poste_bifacial(**parametres):
    """Le gain publié comme POSTE SÉPARÉ, jamais fondu dans une production.

    Returns:
        ``(poste | None, diagnostic)``. ``poste`` porte un ``gain_pct``
        POSITIF et la mention explicite qu'il s'agit d'un GAIN — il n'entre
        jamais dans la somme des pertes envoyée à PVGIS (CAL238 additionne des
        PERTES ; y glisser un gain ferait une soustraction invisible).
    """
    diagnostic = gain_bifacial(**parametres)
    if not diagnostic['calculable']:
        return None, diagnostic
    return {
        'poste': 'gain_bifacial',
        'libelle': 'Gain de face arrière (bifacial)',
        'gain_pct': diagnostic['gain_pct'],
        'source': diagnostic['source'],
        'reference': diagnostic['motif'],
        'facteurs': diagnostic['facteurs'],
    }, diagnostic
