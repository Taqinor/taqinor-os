"""CALX167 — ÉTAPE « mismatch fabricant » : la SEULE dispersion de fabrication.

CE QUI EXISTAIT, ET POURQUOI IL NE SUFFISAIT PAS
-------------------------------------------------
``services/pertes.py`` porte le poste ``mismatch`` au catalogue, mais rien ne
le CALCULE : c'est une saisie libre. Ailleurs dans le dépôt,
``apps/ventes/solar_design.py`` pose ``DEFAULT_LOSS_FACTORS['mismatch'] =
0.02`` — un littéral que son propre commentaire déclare non sourcé, et qui ne
concerne pas ``apps.calepinage``. Aucun 2 % n'entre donc ici : sans saisie
sourcée, l'étape est OMISE en nommant la clé qui manque (D-CALX 7).

CE QUE CETTE ÉTAPE APPLIQUE, ET RIEN D'AUTRE
----------------------------------------------
La dispersion de FABRICATION seule — l'écart de puissance entre modules d'un
même lot. PV*SOL sépare explicitement « mismatch (information fabricant) » de
« mismatch (configuration/ombrage) » dans son bilan d'énergie
(https://help.valentin-software.com/pvsol/en/pages/results/energy-balance/) :
la seconde est l'affaire de l'étape ``mismatch_ombrage`` (CALX168), qui se
calcule par chaîne à partir des I-V. Les deux ne doivent jamais se recouvrir,
d'où le refus déclaré plus bas.

LE POSTE À 0 % SOUS SUIVI DE POINT DE PUISSANCE PAR MODULE
------------------------------------------------------------
Quand chaque module porte son propre suivi de point de puissance
(micro-onduleur, optimiseur, optimiseur de brin), la dispersion de fabrication
ne se propage plus dans aucune chaîne : le poste vaut 0 %, et il est PUBLIÉ
à 0 % avec sa raison plutôt que masqué. Aurora documente le même refus :
« Aurora does not apply the mismatch system loss in the case of microinverter,
DC optimizer, or cell string optimizer designs »
(https://help.aurorasolar.com/hc/en-us/articles/220450107-System-Losses).
Ce cas prime sur la saisie : une dispersion saisie et sourcée ne se soustrait
pas davantage sous micro-onduleur.

CE QU'ELLE LIT DANS ``contexte``
----------------------------------
* ``reglages_simulation['mismatch_fabricant_pct']`` — la saisie société avec
  sa provenance (registre CALX145). Non saisie ⇒ étape OMISE en nommant la
  clé, jamais un forfait.
* ``suivi_mpp_par_module`` — la déclaration du suivi de point de puissance
  module par module, l'une des clés de :data:`SUIVIS_MPP` ; à défaut, la
  présence d'un optimiseur dans ``materiel['optimiseur']`` vaut la même
  déclaration (c'est ce que le document porte aujourd'hui).
* ``mismatch_ombrage['origine']`` — l'entrée dont l'étape CALX168 tire SA
  dispersion. Si c'est la MÊME que celle lue ici, l'étape refuse de
  s'exécuter : deux lignes tirées d'un seul chiffre le compteraient deux fois.

Aucune fiche produit ne publie aujourd'hui de dispersion de fabrication : le
sélecteur ``apps/stock/selectors.py`` n'expose pour le module ni ce champ ni
son équivalent, et l'étape ne va donc pas l'y chercher — elle le dira le jour
où la fiche le portera.
"""
from __future__ import annotations

from apps.calepinage.services import etapes

#: La clé de réglage société (registre CALX145, section « simulation »).
CLE_REGLAGE = 'mismatch_fabricant_pct'

#: Le nom de l'entrée, tel qu'il est publié dans la cascade et tel que
#: l'étape CALX168 le déclarerait si elle tirait du même chiffre.
ENTREE_REGLAGE = 'reglages_simulation.%s' % CLE_REGLAGE

#: La clé de ``contexte`` qui DÉCLARE le suivi de point de puissance module
#: par module.
CLE_SUIVI_MPP = 'suivi_mpp_par_module'

#: La clé de ``contexte`` sous laquelle l'étape « mismatch d'ombrage »
#: (CALX168) déclare l'origine de sa propre dispersion.
CLE_MISMATCH_OMBRAGE = 'mismatch_ombrage'

LIBELLE = 'Dispersion de fabrication (mismatch)'

#: Les suivis de point de puissance MODULE PAR MODULE, et leur nom français.
SUIVIS_MPP = {
    'micro_onduleur': 'micro-onduleur',
    'optimiseur': 'optimiseur',
    'optimiseur_de_brin': 'optimiseur de brin',
}

REFERENCE_PVSOL = (
    'PV*SOL — Energy balance : « mismatch (information fabricant) » est un '
    'poste distinct de « mismatch (configuration/ombrage) » '
    '(https://help.valentin-software.com/pvsol/en/pages/results/'
    'energy-balance/)')

REFERENCE_AURORA = (
    'Aurora — System Losses : « Aurora does not apply the mismatch system '
    'loss in the case of microinverter, DC optimizer, or cell string '
    'optimizer designs » (https://help.aurorasolar.com/hc/en-us/articles/'
    '220450107-System-Losses)')

MOTIF_SANS_SAISIE = (
    "Aucune dispersion de fabrication saisie pour cette société : l'étape "
    "est OMISE et la série ressort inchangée. Le 2 % employé ailleurs dans "
    "le dépôt est un littéral non sourcé qui ne concerne pas le calepinage.")

MOTIF_VALEUR_ILLISIBLE = (
    "La dispersion de fabrication saisie n'est pas un pourcentage lisible "
    "entre 0 et 100 : l'étape est OMISE plutôt que de retrancher un chiffre "
    "qu'on ne sait pas relire.")

MOTIF_MEME_ORIGINE = (
    "L'étape « mismatch_ombrage » (CALX168) tire sa dispersion de la MÊME "
    "entrée que celle-ci : appliquer les deux compterait une seule "
    "dispersion deux fois. La dispersion de fabrication est donc OMISE, et "
    "c'est la dispersion d'ombrage, calculée par chaîne, qui s'applique.")

MOTIF_SUIVI_MPP = (
    "Chaque module du groupe porte son propre suivi de point de puissance "
    "({suivi}) : la dispersion de fabrication ne se propage plus dans aucune "
    "chaîne, et le poste vaut 0,0 %.")

__all__ = ['appliquer', 'CLE_REGLAGE', 'ENTREE_REGLAGE', 'CLE_SUIVI_MPP',
           'CLE_MISMATCH_OMBRAGE', 'SUIVIS_MPP', 'LIBELLE']


def appliquer(serie, contexte):
    """``(serie, etape)`` — la dispersion de fabrication, et elle seule."""
    contexte = contexte if isinstance(contexte, dict) else {}

    suivi = _suivi_mpp(contexte)
    if suivi:
        # Le poste est PUBLIÉ à 0 % — pas masqué : une ligne absente se
        # lirait « oubliée », alors que c'est un refus documenté.
        return serie, etapes.etape_appliquee(
            LIBELLE,
            source='materiel',
            entree={'champ': CLE_SUIVI_MPP, 'suivi': suivi, 'pct': 0.0,
                    'motif': MOTIF_SUIVI_MPP.format(suivi=suivi)},
            reference=REFERENCE_AURORA)

    if _origine_mismatch_ombrage(contexte) == ENTREE_REGLAGE:
        return serie, etapes.etape_omise(LIBELLE, MOTIF_MEME_ORIGINE)

    saisie = etapes.reglage(contexte, CLE_REGLAGE)
    if saisie is None:
        return serie, etapes.etape_omise(LIBELLE, MOTIF_SANS_SAISIE,
                                         champ=ENTREE_REGLAGE)

    pct = _pourcentage(saisie.get('valeur'))
    if pct is None:
        return serie, etapes.etape_omise(LIBELLE, MOTIF_VALEUR_ILLISIBLE,
                                         champ=ENTREE_REGLAGE)

    suite = etapes.mettre_a_l_echelle(serie, 1.0 - pct / 100.0)
    return suite, etapes.etape_appliquee(
        LIBELLE,
        source=saisie.get('source'),
        entree={'champ': ENTREE_REGLAGE, 'pct': pct},
        reference=saisie.get('reference') or REFERENCE_PVSOL)


def _suivi_mpp(contexte):
    """Le suivi de point de puissance module par module, ou ``''``.

    Deux lectures, dans cet ordre : la DÉCLARATION explicite du document, puis
    l'optimiseur retenu au matériel — un optimiseur choisi EST un suivi par
    module, et c'est la seule forme que le dépôt sache aujourd'hui porter.
    """
    declare = (contexte.get(CLE_SUIVI_MPP) or '')
    declare = str(declare).strip().lower()
    if declare in SUIVIS_MPP:
        return SUIVIS_MPP[declare]
    materiel = contexte.get('materiel')
    if isinstance(materiel, dict) and materiel.get('optimiseur'):
        return SUIVIS_MPP['optimiseur']
    return ''


def _origine_mismatch_ombrage(contexte):
    """L'entrée dont CALX168 tire sa dispersion, ou ``''``."""
    bloc = contexte.get(CLE_MISMATCH_OMBRAGE)
    if not isinstance(bloc, dict):
        return ''
    return str(bloc.get('origine') or '').strip()


def _pourcentage(valeur):
    """Un pourcentage de perte lisible dans ``[0, 100[``, ou ``None``."""
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    if nombre != nombre or nombre < 0.0 or nombre >= 100.0:
        return None
    return nombre
