"""AOF113 — source UNIQUE du productible : la note de calcul ET la simulation.

**Le problème.** La note de calcul et la simulation 25 ans consomment toutes
deux un « productible » (kWh/kWc/an). Si chacune le saisit, le dossier repart
avec exactement la classe de défaut que tout le groupe combat : deux sources de
vérité qui divergent silencieusement. Le dépôt possède déjà UNE table
canonique committée — celle de `apps/ventes/quote_engine/productible.py`,
miroir de `solar.js` et de `apps/web/src/lib/yieldTable.ts`, dérivée de PVGIS.

**Pourquoi la table est LUE et non IMPORTÉE.** `apps/ao` n'a pas le droit
d'importer `apps.ventes.quote_engine` (règle #4, contrôlée par `lint-imports`
et par le test d'AOF117) : un import créerait un chemin par lequel une
évolution de l'AO pourrait casser le moteur de devis, ou l'inverse. Recopier
les valeurs ici recréerait la double source de vérité. La troisième voie est
celle du plan — « lire la table de VALEURS, pas le moteur » : le fichier
canonique est analysé en AST et ses seuls littéraux sont extraits. Aucun code
de `quote_engine` n'est exécuté, aucune dépendance d'import n'est créée, et la
valeur reste unique dans le dépôt. Le test d'AOF113 compare les deux tables :
elles ne peuvent pas diverger sans faire rougir la CI.

**Aucun appel réseau au rendu.** `apps/parametres/pvgis.py` existe et interroge
PVGIS en ligne ; il n'a rien à faire dans un rendu de pièce (un dépôt d'offre
ne dépend pas de la disponibilité d'un service tiers, et deux rendus doivent
donner le même chiffre). Ce module ne fait AUCUNE E/S réseau — un test
statique interdit `requests`/`urllib` dans tout `apps/ao/fabrique/`.
"""
from __future__ import annotations

import ast
import hashlib
import pathlib

#: Chemin de la table CANONIQUE, relatif à `backend/django_core/`.
CHEMIN_TABLE = 'apps/ventes/quote_engine/productible.py'

#: Ce que la table décrit — cité TEL QUEL dans la note de calcul.
MODELE = 'PVGIS (TMY), pertes système ~14 %, inclinaison optimale, plein sud'

#: Valeur historique de `CompanyProfile.productible_kwh_kwc`. Tant que la
#: société garde CETTE valeur, elle n'a rien forcé : on lit la table.
DEFAUT_HISTORIQUE = 1600.0

_CACHE = {}


class ProductibleIndisponible(RuntimeError):
    """La table canonique est illisible — on ne devine JAMAIS une valeur."""


def _racine():
    # …/backend/django_core/apps/ao/fabrique/productible.py → …/django_core
    return pathlib.Path(__file__).resolve().parents[3]


def _charger():
    """Extrait les littéraux de la table canonique — sans exécuter son code."""
    if _CACHE:
        return _CACHE
    chemin = _racine() / CHEMIN_TABLE
    try:
        source = chemin.read_text(encoding='utf-8')
    except OSError as exc:
        raise ProductibleIndisponible(
            'table de productible canonique illisible (%s) : aucune valeur de '
            'repli n\'est inventée' % chemin) from exc

    voulus = {'PRODUCTIBLE_PAR_VILLE', 'DEFAULT_PRODUCTIBLE', '_CITY_ALIASES'}
    trouves = {}
    for noeud in ast.parse(source, filename=str(chemin)).body:
        if not isinstance(noeud, ast.Assign):
            continue
        for cible in noeud.targets:
            if isinstance(cible, ast.Name) and cible.id in voulus:
                try:
                    trouves[cible.id] = ast.literal_eval(noeud.value)
                except ValueError as exc:
                    raise ProductibleIndisponible(
                        '%s n\'est plus un littéral dans %s'
                        % (cible.id, CHEMIN_TABLE)) from exc
    manquants = sorted(voulus - set(trouves))
    if manquants:
        raise ProductibleIndisponible(
            'table canonique incomplète, absent(s) : %s' % ', '.join(manquants))

    table = {str(k).strip().lower(): float(v)
             for k, v in trouves['PRODUCTIBLE_PAR_VILLE'].items()}
    _CACHE.update({
        'table': table,
        'defaut': float(trouves['DEFAULT_PRODUCTIBLE']),
        'alias': {str(k).strip().lower(): str(v).strip().lower()
                  for k, v in trouves['_CITY_ALIASES'].items()},
        'revision': hashlib.sha256(
            repr(sorted(table.items())).encode('utf-8')).hexdigest()[:12],
    })
    return _CACHE


def table():
    """La table ville → kWh/kWc/an, telle qu'elle est committée."""
    return dict(_charger()['table'])


def revision():
    """Empreinte courte de la table — citée dans la pièce avec sa source."""
    return _charger()['revision']


def villes_connues():
    donnees = _charger()
    return tuple(sorted(set(donnees['table']) | set(donnees['alias'])))


def _normaliser(ville):
    return str(ville or '').strip().lower()


def resoudre(ville, *, override=None, date_verification=None):
    """Résout LE productible d'un site. Une seule valeur, une seule fois.

    :param ville: ville du site (accepte les alias de la table canonique).
    :param override: `CompanyProfile.productible_kwh_kwc` — il ne prime QUE
        s'il diffère réellement du défaut historique 1600 (sinon ce n'est pas
        un choix de l'opérateur, c'est la valeur d'usine).
    :param date_verification: date de la dernière vérification de la table,
        écrite telle quelle dans la pièce quand elle est connue.
    :returns: mapping des données à écrire dans le contexte — valeur, ville
        retenue, méthode de résolution, source et révision.
    """
    donnees = _charger()
    cle = _normaliser(ville)
    resolue = donnees['alias'].get(cle, cle)

    if override is not None:
        try:
            forcee = float(override)
        except (TypeError, ValueError):
            forcee = None
        if forcee and forcee > 0 and abs(forcee - DEFAUT_HISTORIQUE) > 0.5:
            return _resultat(forcee, ville, 'override société', resolue,
                             donnees, date_verification)

    if not cle:
        return _resultat(donnees['defaut'], ville, 'ville inconnue → repli',
                         '', donnees, date_verification)
    if resolue in donnees['table']:
        methode = 'table PVGIS' if resolue == cle else 'alias → %s' % resolue
        return _resultat(donnees['table'][resolue], ville, methode, resolue,
                         donnees, date_verification)
    return _resultat(donnees['defaut'], ville, 'ville inconnue → repli', '',
                     donnees, date_verification)


def _resultat(valeur, ville, methode, ville_retenue, donnees, date_verification):
    return {
        'valeur_kwh_kwc': float(valeur),
        'ville_demandee': str(ville or ''),
        'ville_retenue': ville_retenue,
        'methode': methode,
        'modele': MODELE,
        'source': CHEMIN_TABLE,
        'revision': donnees['revision'],
        'date_verification': date_verification,
        'reseau': False,
    }


def phrase_source(resolution):
    """La phrase CITÉE dans la note de calcul — générée, jamais rédigée.

    « Productible retenu : 1 651 kWh/kWc/an (Casablanca) — PVGIS (TMY), … ;
    source : apps/ventes/quote_engine/productible.py, révision 4f2c… ».
    """
    ville = resolution.get('ville_retenue') or \
        resolution.get('ville_demandee') or 'site'
    phrase = ('Productible retenu : %s kWh/kWc/an (%s) — %s ; source : %s, '
              'révision %s'
              % (_entier_fr(resolution['valeur_kwh_kwc']), ville.title(),
                 resolution['modele'], resolution['source'],
                 resolution['revision']))
    if resolution.get('date_verification'):
        phrase += ' (vérifiée le %s)' % resolution['date_verification']
    return phrase


def _entier_fr(valeur):
    return '{:,.0f}'.format(float(valeur)).replace(',', ' ')


def production_annuelle_kwh(resolution, kwc):
    """kWc → kWh/an avec LA valeur du contexte. Aucun autre productible.

    La fonction est volontairement triviale : son intérêt est qu'il n'existe
    aucune autre façon, dans la fabrique, de passer d'une puissance à une
    production — donc aucune façon d'utiliser un second productible.
    """
    return float(resolution['valeur_kwh_kwc']) * float(kwc)
