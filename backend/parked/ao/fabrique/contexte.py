"""AOF111 — le contexte de dossier UNIQUE : zéro re-saisie, zéro littéral.

**Le constat qui a produit ce module.** Les quatre défauts réels de la session
FRDISI du 27/07 sont TOUS des bugs de recopie, aucun n'est un bug de calcul :

* un montant tapé « 5 143 680 » pour 5 413 680 (deux chiffres permutés) ;
* une parenthèse annonçant « batteries 2 800 » quand le bordereau disait 2 600 ;
* un bordereau frère resté à 5 219 280 après la mise à jour du principal ;
* un LISEZ-MOI figé sur des chiffres d'une version antérieure.

Une relecture humaine ne les attrape pas de façon fiable — la preuve est qu'elle
ne les a pas attrapés. Les générer TOUS depuis une valeur unique les élimine par
construction : `construire_contexte()` calcule une fois, les 9+ pièces lisent.

**Ce que le module garantit.**

1. *Gelé.* Le contexte rendu est immuable en profondeur (`MappingProxyType` +
   tuples). Une pièce ne peut pas « corriger localement » un chiffre : la seule
   façon de changer une valeur est de reconstruire le contexte, ce qui périme
   les artefacts déjà rendus (`empreinte.Artefact`).
2. *Versionné.* `VERSION_CONTEXTE` bouge dès que la forme change, de sorte
   qu'un artefact ancien ne soit jamais relu contre une forme neuve.
3. *Reproductible.* Deux constructions sur la même entrée donnent le même
   contexte ET la même empreinte (les seules clés qui bougent — horodatage,
   opérateur — sont hors empreinte par construction, cf. `empreinte.py`).
4. *Sans littéral dans les gabarits.* `cles_disponibles()` publie les chemins
   pointés lisibles par un gabarit ; `litteraux_chiffres()` refuse un gabarit
   qui écrirait un montant en dur au lieu de le référencer.

Le module est PUR : `construire_contexte` reçoit un mapping (ou tout objet
exposant les mêmes clés) préparé par la couche Django. Aucun import d'ORM, de
réseau ou de `quote_engine` (règle #4).
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from types import MappingProxyType

from .empreinte import (CLES_SIGNIFIANTES, empreinte_contexte,
                        cles_hors_perimetre)
from .resultat_calepinage import valider_lot

VERSION_CONTEXTE = 1

#: Sections construites, dans l'ordre où elles sont écrites. L'ordre n'a aucun
#: effet sur l'empreinte (clés triées) ; il rend la lecture d'un contexte
#: sérialisé prévisible.
SECTIONS = CLES_SIGNIFIANTES


class ContexteIncomplet(ValueError):
    """Une donnée SANS laquelle une pièce mentirait est absente."""


class CleInconnue(KeyError):
    """Un gabarit référence un chemin qui n'existe pas dans le contexte."""


_ABSENT = object()


# --------------------------------------------------------------------- gel
def geler(valeur, _profondeur=0):
    """Immuabilité PROFONDE : mapping → `MappingProxyType`, séquence → tuple."""
    if _profondeur > 32:
        raise ValueError('contexte trop profond (cycle ?)')
    if isinstance(valeur, (MappingProxyType, dict)):
        return MappingProxyType({
            cle: geler(val, _profondeur + 1) for cle, val in valeur.items()})
    if isinstance(valeur, (list, tuple)):
        return tuple(geler(v, _profondeur + 1) for v in valeur)
    if isinstance(valeur, (set, frozenset)):
        return tuple(geler(v, _profondeur + 1) for v in sorted(valeur, key=repr))
    return valeur


def est_gele(valeur, _profondeur=0):
    """`True` si aucune partie de `valeur` n'est modifiable en place."""
    if _profondeur > 32:
        return False
    if isinstance(valeur, dict):
        return False
    if isinstance(valeur, MappingProxyType):
        return all(est_gele(v, _profondeur + 1) for v in valeur.values())
    if isinstance(valeur, (list, set)):
        return False
    if isinstance(valeur, tuple):
        return all(est_gele(v, _profondeur + 1) for v in valeur)
    return True


# ------------------------------------------------------------- conversions
def _lire(source, cle, defaut=None):
    """Lit une clé sur un mapping OU un attribut sur un objet."""
    if source is None:
        return defaut
    if hasattr(source, 'get') and hasattr(source, '__getitem__'):
        return source.get(cle, defaut)
    return getattr(source, cle, defaut)


def montant(valeur, defaut=None):
    """Tout montant est un `Decimal` — jamais un `float` (règle du centime)."""
    if valeur is None or valeur == '':
        return defaut
    if isinstance(valeur, Decimal):
        return valeur
    try:
        return Decimal(str(valeur))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ContexteIncomplet('montant illisible : %r' % (valeur,)) from exc


def _texte(valeur, defaut=''):
    return defaut if valeur is None else str(valeur)


def _jour(valeur):
    if valeur in (None, ''):
        return None
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    return date.fromisoformat(str(valeur)[:10])


# ---------------------------------------------------------------- sections
def _identite(dossier):
    """Identité du SOUMISSIONNAIRE (nous) — reprise telle quelle, jamais tapée."""
    src = _lire(dossier, 'identite') or {}
    return {
        'raison_sociale': _texte(_lire(src, 'raison_sociale')),
        'forme_juridique': _texte(_lire(src, 'forme_juridique')),
        'adresse': _texte(_lire(src, 'adresse')),
        'ville': _texte(_lire(src, 'ville')),
        'ice': _texte(_lire(src, 'ice')),
        'rc': _texte(_lire(src, 'rc')),
        'if_fiscal': _texte(_lire(src, 'if_fiscal')),
        'cnss': _texte(_lire(src, 'cnss')),
        'patente': _texte(_lire(src, 'patente')),
        'rib': _texte(_lire(src, 'rib')),
        'banque': _texte(_lire(src, 'banque')),
        'signataire': _texte(_lire(src, 'signataire')),
        'qualite_signataire': _texte(_lire(src, 'qualite_signataire')),
        'telephone': _texte(_lire(src, 'telephone')),
        'email': _texte(_lire(src, 'email')),
    }


def _acheteur(dossier):
    """Le maître d'ouvrage — c'est LUI qui reçoit le pli."""
    src = _lire(dossier, 'acheteur') or {}
    return {
        'nom': _texte(_lire(src, 'nom')),
        'adresse': _texte(_lire(src, 'adresse')),
        'ville': _texte(_lire(src, 'ville')),
        'representant': _texte(_lire(src, 'representant')),
    }


def _marche(dossier):
    src = _lire(dossier, 'marche') or {}
    return {
        'objet': _texte(_lire(src, 'objet')),
        'reference_acheteur': _texte(_lire(src, 'reference_acheteur')),
        'reference': _texte(_lire(src, 'reference')),
        'type_prix': _texte(_lire(src, 'type_prix'), 'unitaires'),
        'lot': _texte(_lire(src, 'lot')),
        'mode_passation': _texte(_lire(src, 'mode_passation')),
        'lieu_execution': _texte(_lire(src, 'lieu_execution')),
        'delai_execution_jours': _lire(src, 'delai_execution_jours'),
        'validite_offre_jours': _lire(src, 'validite_offre_jours'),
    }


def _batiment(src):
    return {
        'code': _texte(_lire(src, 'code')),
        'libelle': _texte(_lire(src, 'libelle')),
        'ville': _texte(_lire(src, 'ville')),
        'surface_toiture_m2': _lire(src, 'surface_toiture_m2'),
        'type_toiture': _texte(_lire(src, 'type_toiture')),
        'engagement_modules': _lire(src, 'engagement_modules'),
    }


def _batiments(dossier):
    return [_batiment(b) for b in (_lire(dossier, 'batiments') or ())]


def _calepinage(dossier):
    """Résultats de calepinage FIGÉS — consommés, JAMAIS recalculés.

    C'est ICI que le contrat AOF112 est opposé : le lot passe par
    `valider_lot`, donc un compte retenu inférieur à l'optimum prouvé, une
    sensibilité au delta recopié ou un résultat sans `hash_entree` n'entrent
    pas dans un dossier. La validation est faite UNE fois, à l'entrée ; aucune
    pièce ne la refait et aucune ne la contourne.
    """
    brut = _lire(dossier, 'calepinage') or ()
    if not brut:
        return []
    return [r.vers_dict() for r in valider_lot(brut).resultats]


def _equipement(src):
    return {
        'role': _texte(_lire(src, 'role')),
        'designation': _texte(_lire(src, 'designation')),
        'marque': _texte(_lire(src, 'marque')),
        'reference': _texte(_lire(src, 'reference')),
        'quantite': _lire(src, 'quantite'),
        'unite': _texte(_lire(src, 'unite'), 'U'),
        'batiment': _texte(_lire(src, 'batiment')),
        'caracteristiques': dict(_lire(src, 'caracteristiques') or {}),
    }


def _equipements(dossier):
    return [_equipement(e) for e in (_lire(dossier, 'equipements') or ())]


def _montants(dossier):
    """Les montants du dossier — en `Decimal`, au centime, JAMAIS en `float`.

    Aucune valeur de coût, de marge ou de bénéfice n'entre ici : ce contexte
    alimente des pièces remises au maître d'ouvrage (ratchet AOF129).
    """
    src = _lire(dossier, 'montants') or {}
    interdits = tuple(cle for cle in src
                      if _CLE_SENSIBLE.search(str(cle)))
    if interdits:
        raise ContexteIncomplet(
            'clés de coût interdites dans les montants du contexte client : %s'
            % ', '.join(sorted(interdits)))
    return {
        'sous_total_ht': montant(_lire(src, 'sous_total_ht')),
        'remise': montant(_lire(src, 'remise'), Decimal('0')),
        'total_ht': montant(_lire(src, 'total_ht')),
        'taux_tva': montant(_lire(src, 'taux_tva'), Decimal('20')),
        'tva': montant(_lire(src, 'tva')),
        'total_ttc': montant(_lire(src, 'total_ttc')),
        'devise': _texte(_lire(src, 'devise'), 'DH'),
    }


def _clauses(dossier):
    src = _lire(dossier, 'clauses') or {}
    return {str(cle): _texte(val) for cle, val in
            (src.items() if hasattr(src, 'items') else ())}


def _dates(dossier):
    src = _lire(dossier, 'dates') or {}
    return {str(cle): _jour(val) for cle, val in
            (src.items() if hasattr(src, 'items') else ())}


def _engagements(dossier):
    """Ce qu'on s'engage à installer, par bâtiment — la promesse du bordereau."""
    src = _lire(dossier, 'engagements') or ()
    if hasattr(src, 'items'):
        src = [{'batiment': cle, 'modules': val} for cle, val in src.items()]
    return [{'batiment': _texte(_lire(e, 'batiment')),
             'modules': _lire(e, 'modules'),
             'kwc': _lire(e, 'kwc')} for e in src]


#: Toute clé dont le nom trahit une donnée d'économie interne.
_CLE_SENSIBLE = re.compile(
    r'prix_achat|cout_revient|cout_de_revient|\bcout\b|couts|marge|benefice|'
    r'bénéfice|coefficient', re.IGNORECASE)


# ------------------------------------------------------------- construction
def construire_contexte(dossier, *, genere_le=None, genere_par='',
                        productible=None, derivations=None, strict=False):
    """Construit le contexte GELÉ et VERSIONNÉ d'un dossier AO.

    :param dossier: mapping (ou objet à attributs) préparé par la couche
        Django : `identite`, `acheteur`, `marche`, `batiments`, `calepinage`,
        `equipements`, `montants`, `clauses`, `dates`, `engagements`.
    :param productible: résolution de productible (AOF113) — source UNIQUE de
        la note de calcul ET de la simulation.
    :param derivations: grandeurs RECALCULÉES (AOF114) ; jamais saisies.
    :param strict: exige les données sans lesquelles une pièce mentirait.
    :returns: mapping immuable en profondeur, portant son empreinte.
    """
    contenu = {
        'identite': _identite(dossier),
        'acheteur': _acheteur(dossier),
        'marche': _marche(dossier),
        'batiments': _batiments(dossier),
        'calepinage': _calepinage(dossier),
        'equipements': _equipements(dossier),
        'montants': _montants(dossier),
        'clauses': _clauses(dossier),
        'dates': _dates(dossier),
        'engagements': _engagements(dossier),
        'productible': dict(productible) if productible else
        (dict(_lire(dossier, 'productible') or {})),
        'derivations': dict(derivations) if derivations else
        (dict(_lire(dossier, 'derivations') or {})),
    }
    if strict:
        _exiger(contenu)

    contenu['version_contexte'] = VERSION_CONTEXTE
    contenu['genere_le'] = genere_le
    contenu['genere_par'] = _texte(genere_par)
    empreinte = empreinte_contexte(contenu)
    contenu['empreinte'] = empreinte

    contexte = geler(contenu)
    reste = cles_hors_perimetre(contexte)
    if reste:
        raise ContexteIncomplet(
            'sections non classées (ni signifiantes ni volatiles) : %s — les '
            'verser explicitement dans empreinte.CLES_SIGNIFIANTES ou '
            'CLES_VOLATILES' % ', '.join(reste))
    return contexte


def _exiger(contenu):
    manquants = []
    if not contenu['identite']['raison_sociale']:
        manquants.append('identite.raison_sociale')
    if not contenu['marche']['objet']:
        manquants.append('marche.objet')
    if contenu['montants']['total_ht'] is None:
        manquants.append('montants.total_ht')
    if contenu['montants']['total_ttc'] is None:
        manquants.append('montants.total_ttc')
    if manquants:
        raise ContexteIncomplet(
            'contexte incomplet : %s' % ', '.join(manquants))


def reconstruire(contexte, **remplacements):
    """Nouveau contexte = ancien + remplacements — l'ancien reste intact.

    Un contexte ne se modifie JAMAIS en place : c'est ce qui garantit qu'un
    artefact déjà rendu devient PÉRIMÉ (et non silencieusement faux) quand une
    valeur bouge.
    """
    base = {cle: _degeler(contexte[cle]) for cle in contexte
            if cle not in ('empreinte',)}
    base.update(remplacements)
    return construire_contexte(
        base, genere_le=base.get('genere_le'),
        genere_par=base.get('genere_par', ''),
        productible=base.get('productible'),
        derivations=base.get('derivations'))


def _degeler(valeur):
    if isinstance(valeur, MappingProxyType):
        return {cle: _degeler(val) for cle, val in valeur.items()}
    if isinstance(valeur, tuple):
        return [_degeler(v) for v in valeur]
    return valeur


# ------------------------------------------------------------------ lecture
def valeur(contexte, chemin, defaut=_ABSENT):
    """Lecture par chemin pointé — `valeur(ctx, 'montants.total_ttc')`.

    C'est l'UNIQUE accès qu'un gabarit a au dossier : il ne connaît pas de
    chiffres, seulement des chemins.
    """
    courant = contexte
    for segment in str(chemin).split('.'):
        if isinstance(courant, (MappingProxyType, dict)):
            if segment not in courant:
                courant = _ABSENT
                break
            courant = courant[segment]
        elif isinstance(courant, (list, tuple)) and segment.lstrip('-').isdigit():
            index = int(segment)
            if index >= len(courant) or index < -len(courant):
                courant = _ABSENT
                break
            courant = courant[index]
        else:
            courant = _ABSENT
            break
    if courant is _ABSENT:
        if defaut is _ABSENT:
            raise CleInconnue('chemin inconnu dans le contexte : %r' % (chemin,))
        return defaut
    return courant


def cles_disponibles(contexte, _prefixe='', _profondeur=0):
    """Tous les chemins pointés lisibles — publiés à l'éditeur de gabarits."""
    chemins = []
    if _profondeur > 8:
        return tuple(chemins)
    if isinstance(contexte, (MappingProxyType, dict)):
        for cle in sorted(contexte, key=str):
            chemin = '%s.%s' % (_prefixe, cle) if _prefixe else str(cle)
            chemins.append(chemin)
            chemins.extend(cles_disponibles(contexte[cle], chemin,
                                            _profondeur + 1))
    elif isinstance(contexte, (list, tuple)):
        for index, item in enumerate(contexte):
            chemin = '%s.%d' % (_prefixe, index)
            chemins.append(chemin)
            chemins.extend(cles_disponibles(item, chemin, _profondeur + 1))
    return tuple(chemins)


# ----------------------------------------------------- gabarits sans chiffre
#: Un nombre écrit en dur dans un gabarit. Sont tolérés : les numéros de
#: version CSS/HTML hors zone de texte (le contrôle porte sur le TEXTE rendu au
#: lecteur), et les entités d'échappement.
_LITTERAL = re.compile(r'(?<![\w.#-])\d[\d\s  .,]*\d|(?<![\w.#-])\d(?![\w])')

#: Ce qu'un gabarit a le droit d'écrire en clair malgré un chiffre : une
#: référence de norme, un numéro d'article de loi, un format de papier.
_TOLERES = re.compile(
    r'\b(?:NF|EN|IEC|CEI|ISO|NM|UTE|C\s?15|A4|A3|A0|CO2|m2|m3|H2O)\b',
    re.IGNORECASE)


def litteraux_chiffres(texte, tolerances=()):
    """Les chiffres écrits EN DUR dans un gabarit — un gabarit n'en a aucun.

    Le contrat AOF111 est « aucun gabarit ne peut contenir un chiffre
    littéral ; il ne référence que des clés du contexte ». Ce détecteur est ce
    qui rend le contrat opposable au lieu d'être une intention.

    :param tolerances: fragments littéraux explicitement admis (référence de
        norme, gabarit de page…), retirés avant l'analyse.
    """
    reste = str(texte)
    for tolere in tolerances:
        reste = reste.replace(str(tolere), ' ')
    reste = _TOLERES.sub(' ', reste)
    # Un COMMENTAIRE n'est pas du texte lu par la commission : ni le
    # commentaire Django ({# … #}), ni le commentaire HTML, ni un bloc CSS
    # (les valeurs métriques d'une feuille de style ne sont pas des montants).
    reste = re.sub(r'\{#.*?#\}|<!--.*?-->', ' ', reste, flags=re.DOTALL)
    reste = re.sub(r'<style\b.*?</style>|<script\b.*?</script>', ' ', reste,
                   flags=re.DOTALL | re.IGNORECASE)
    # Les expressions de gabarit ({{ ... }}) NE sont pas du texte littéral :
    # elles référencent le contexte, ce qui est précisément l'objectif.
    reste = re.sub(r'\{\{.*?\}\}|\{%.*?%\}', ' ', reste, flags=re.DOTALL)
    # Enfin les BALISES : le contrôle porte sur le texte LU par la commission,
    # pas sur la structure. `colspan="7"` est de la mise en tableau, pas un
    # montant — et une valeur affichée est forcément dans un nœud de texte.
    reste = re.sub(r'<[^>]*>', ' ', reste)
    return tuple(m.group(0).strip() for m in _LITTERAL.finditer(reste)
                 if m.group(0).strip())
