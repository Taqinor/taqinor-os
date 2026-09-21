"""CALX166 — ÉTAPE « LID » : selon la TECHNOLOGIE de cellule, et seulement
si la société la chiffre.

LE CONSTAT
----------
``lid`` est au catalogue des postes (``services/pertes.py``) sans aucun
calcul. La fiche porte pourtant sa technologie de cellule
(``FicheTechnique.techno_cellule``, texte libre « N-type TOPCon », « PERC »…)
et ``apps/stock/selectors.py`` la publie déjà dans le bloc module — mais
RIEN ne reliait cette technologie à une perte.

CE QUE CETTE ÉTAPE FAIT
------------------------
La société déclare, PAR TECHNOLOGIE, une perte LID sourcée — le réglage
``simulation.lid_par_techno``, une entrée par ligne, chacune avec sa propre
``source``. La technologie lue sur la fiche du module choisit la ligne ; la
perte de cette ligne s'applique uniformément à la série.

POURQUOI IL N'Y A AUCUNE VALEUR PAR DÉFAUT
--------------------------------------------
PVsyst écrit que le LID ne concerne que le cristallin dopé BORE de type p,
les technologies de type n n'étant pas affectées, et que PVsyst ne propose
AUCUNE valeur de LID par défaut
(https://www.pvsyst.com/help/project-design/array-and-system-losses/
lid-loss.html). Une table société sans ligne pour la technologie lue est
donc une réponse parfaitement possible — « cette technologie n'est pas
chiffrée ici » — et l'étape s'omet en CITANT la chaîne lue, sans rien
supposer ni dans un sens ni dans l'autre.

CE QUI LA FAIT SE TAIRE
------------------------
* Aucune table société saisie ⇒ omise en nommant la clé de réglage.
* ``techno_cellule`` absente ou vide sur la fiche ⇒ omise en nommant le champ.
* Technologie lue absente de la table ⇒ omise en CITANT la chaîne lue.
* Ligne de la table sans ``source`` ⇒ REFUSÉE en nommant la technologie : un
  chiffre qu'on ne peut pas sourcer ne se défend pas (D-CALX 7).
* Ligne dont le pourcentage est illisible ⇒ refusée en nommant la
  technologie.

Module PUR : aucune base, aucun réseau.
"""
from __future__ import annotations

from apps.calepinage.services import etapes as _etapes

#: La clé de réglage société lue ici (registre CALX145).
CLE_REGLAGE = 'lid_par_techno'

#: Le champ de fiche produit qui porte la technologie de cellule — publié
#: par ``apps.stock.selectors.specs_for_produit``.
CHAMP_TECHNO = 'techno_cellule'

REFERENCE = (
    'PVsyst — LID loss : le LID ne concerne que le cristallin dopé bore de '
    "type p, les technologies de type n n'étant pas affectées, et PVsyst ne "
    'propose aucune valeur de LID par défaut '
    '(https://www.pvsyst.com/help/project-design/array-and-system-losses/'
    'lid-loss.html).')

LIBELLE = 'LID (première exposition)'

__all__ = ['CLE_REGLAGE', 'CHAMP_TECHNO', 'REFERENCE', 'LIBELLE', 'appliquer']


def appliquer(serie, contexte):
    """``(serie, etape)`` — la perte LID de la technologie lue, ou le silence."""
    contexte = contexte if isinstance(contexte, dict) else {}
    saisie = _etapes.reglage(contexte, CLE_REGLAGE)
    if not saisie:
        return serie, _etapes.etape_omise(
            LIBELLE,
            "Aucune perte LID déclarée par cette société : PVsyst ne propose "
            'aucune valeur par défaut, et il n\'en est donc appliqué aucune. '
            'La table se saisit technologie par technologie, chacune avec sa '
            'source.',
            champ=f'simulation.{CLE_REGLAGE}')

    fiche = contexte.get('fiche_module')
    fiche = fiche if isinstance(fiche, dict) else {}
    brute = fiche.get(CHAMP_TECHNO)
    lue = brute.strip() if isinstance(brute, str) else ''
    if not lue:
        return serie, _etapes.etape_omise(
            LIBELLE,
            "La fiche du module ne dit pas sa technologie de cellule : la "
            f'table « {CLE_REGLAGE} » ne peut pas être consultée, et aucune '
            'ligne n\'est choisie à sa place.',
            champ=f'fiche_module.{CHAMP_TECHNO}')

    table = saisie.get('valeur')
    ligne = _ligne_de_la_techno(table, lue)
    if ligne is None:
        return serie, _etapes.etape_omise(
            LIBELLE,
            f'La technologie lue sur la fiche — « {lue} » — ne figure pas '
            f'dans la table société « {CLE_REGLAGE} » : aucune perte LID n\'a '
            'été saisie pour elle. PVsyst rappelle que les technologies de '
            "type n ne sont pas affectées par le LID ; l'absence de ligne "
            "n'est donc pas forcément un oubli, mais elle n'est jamais "
            'comblée par un chiffre supposé.',
            champ=f'simulation.{CLE_REGLAGE} (ligne « {lue} »)')

    source = (ligne.get('source') or '').strip() \
        if isinstance(ligne, dict) else ''
    if not source:
        return serie, _etapes.etape_omise(
            LIBELLE,
            f'La ligne « {lue} » de la table société « {CLE_REGLAGE} » est '
            'REFUSÉE : elle ne porte pas sa source. Chaque technologie se '
            'saisit avec la provenance de son chiffre.',
            champ=f'simulation.{CLE_REGLAGE} (ligne « {lue} », source)')

    pct = _pourcentage(ligne.get('pct'))
    if pct is None:
        return serie, _etapes.etape_omise(
            LIBELLE,
            f'La ligne « {lue} » de la table société « {CLE_REGLAGE} » ne '
            'porte pas de pourcentage lisible entre 0 et 100.',
            champ=f'simulation.{CLE_REGLAGE} (ligne « {lue} », pct)')

    rendue = _etapes.mettre_a_l_echelle(serie, 1.0 - pct / 100.0)
    entree = {
        'techno_lue': lue,
        'ligne_retenue': _cle_de_la_techno(table, lue),
        'pct': pct,
        'source_de_la_ligne': source,
        'reference_de_la_ligne': ligne.get('reference') or '',
        'source_du_reglage': saisie.get('source'),
    }
    return rendue, _etapes.etape_appliquee(
        LIBELLE, source=source, entree=entree, reference=REFERENCE)


def _cle_de_la_techno(table, lue):
    """La clé de la table qui correspond à la technologie lue, ou ``None``."""
    if not isinstance(table, dict):
        return None
    cible = _normaliser(lue)
    for cle in table:
        if _normaliser(cle) == cible:
            return cle
    return None


def _ligne_de_la_techno(table, lue):
    cle = _cle_de_la_techno(table, lue)
    if cle is None:
        return None
    ligne = table[cle]
    return ligne if isinstance(ligne, dict) else {}


def _normaliser(texte):
    """Une technologie comparable : minuscules, sans accent ni séparateur.

    « N-type TOPCon », « n type topcon » et « N_TYPE_TOPCON » désignent la
    même technologie : la table société n'a pas à deviner la casse ni la
    ponctuation qu'un fournisseur a employées sur sa fiche.
    """
    brut = str(texte).strip().lower()
    accents = {'à': 'a', 'â': 'a', 'ä': 'a', 'é': 'e', 'è': 'e', 'ê': 'e',
               'ë': 'e', 'î': 'i', 'ï': 'i', 'ô': 'o', 'ö': 'o', 'ù': 'u',
               'û': 'u', 'ü': 'u', 'ç': 'c'}
    plat = ''.join(accents.get(lettre, lettre) for lettre in brut)
    for separateur in ('-', '_', '/', '+', '.'):
        plat = plat.replace(separateur, ' ')
    return '_'.join(plat.split())


def _pourcentage(valeur):
    if isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    if nombre != nombre or nombre < 0 or nombre >= 100:
        return None
    return nombre
