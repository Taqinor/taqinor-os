"""L-ECO — LES ÉCONOMIES PAR PÉRIODE, CALCULÉES SERVEUR.

ORDRE FONDATEUR (24/08/2026) : sous le graphe « Sur une journée », le client
doit lire ce qu'il économise **le jour type affiché**, **le mois**, **l'année**
et **en combien d'années l'installation est remboursée** — et ces valeurs
doivent suivre la puce de saison ET la puce de profil d'occupation.

CE MODULE NE CALCULE AUCUNE ÉCONOMIE. Il ne fait que DÉCLINER par période les
douze valeurs que le moteur a déjà produites :

* les 12 MAD/mois sont ceux du bloc ``economies_mensuelles`` (lui-même une
  passe directe de ``eco_s_monthly``/``eco_a_monthly`` du moteur) — jamais une
  seconde série, sinon deux blocs de la même page finiraient par se contredire ;
* l'ANNÉE est la SOMME de ces douze mois, à l'unité près : c'est ce qui rend
  vraie la phrase « sur l'année : X DH », invariante quand le visiteur change
  de saison ;
* le JOUR TYPE d'un mois est ce mois DIVISÉ par ses jours réels
  (``JOURS_PAR_MOIS``) — la même définition de « journée type » que le moteur
  horaire, qui construit justement une journée moyenne par mois ;
* la SAISON est la somme de ses mois, et son jour type la moyenne pondérée par
  les jours — jamais la moyenne des moyennes.

LE RETOUR SUR INVESTISSEMENT N'EST PAS RECALCULÉ ICI NON PLUS. Deux définitions
coexistent dans le dépôt : le cash-flow 25 ans de
``quote_engine.pricing.compute_cashflow_payback`` (qui alimente ``roi_s``/
``roi_a``) et le simple ``coût ÷ économie annuelle`` que
``quote_engine.builder`` réapplique par-dessus UNIQUEMENT quand une étude
industrielle/commerciale a saisi ses propres économies. On reprend **la valeur
déjà servie au client dans CE payload** (``quote.roi_s``/``roi_a``, celle que la
page affiche déjà en « Rentabilisé en X ans »), quelle que soit celle des deux
qui l'a produite : introduire une troisième définition ferait dire deux durées
différentes à la même page. Le départage des deux définitions reste un
arbitrage fondateur ouvert — ce module ne le tranche pas, il s'aligne.

OMISSION PROPRE. Toute période qui n'est pas dérivable de ces sources est
ABSENTE (pas de zéro, pas de « — »), et le bloc entier vaut ``None`` quand les
douze mois ne sont pas servables : la page masque alors le bandeau.
"""
from __future__ import annotations

import logging

from apps.parametres.pvgis_profils import JOURS_PAR_MOIS

logger = logging.getLogger(__name__)

#: Étiquette de provenance servie telle quelle : le client (et le vendeur) doit
#: pouvoir dire d'où sort chaque chiffre sans lire le code.
SOURCE_MOIS = 'economies_mensuelles'
SOURCE_PAYBACK = 'quote.roi'


def _mad(valeur):
    """Montant MAD entier, ou ``None`` — jamais une chaîne, jamais un ``NaN``."""
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None
    if valeur != valeur or valeur in (float('inf'), float('-inf')):
        return None
    return round(valeur)


def _ans(valeur):
    """Durée en années (1 décimale), ou ``None``. Zéro/négatif ⇒ ``None`` : le
    moteur rend ``0.0`` quand il n'a PAS pu calculer un retour (économie nulle),
    et « remboursé en 0 an » serait un mensonge."""
    if isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    if nombre != nombre or nombre <= 0 or nombre in (
            float('inf'), float('-inf')):
        return None
    return round(nombre, 1)


def _serie_12(valeurs):
    """12 montants MAD entiers, ou ``None`` si la série n'est pas exploitable."""
    if not isinstance(valeurs, (list, tuple)) or len(valeurs) != 12:
        return None
    sortie = [_mad(v) for v in valeurs]
    if any(v is None for v in sortie):
        return None
    return sortie


def _par_mois(serie, saison_du_mois):
    """12 entrées ``{mois, jours, saison, mad, jour_mad}``.

    ``jour_mad`` = ``mad ÷ jours``, arrondi au centime : c'est la DÉFINITION du
    jour type, pas une estimation. L'aller-retour ``jour_mad × jours`` retombe
    donc sur ``mad`` à un demi-centime par jour près — l'écart d'arrondi, jamais
    un écart de méthode.
    """
    sortie = []
    for index, montant in enumerate(serie):
        jours = JOURS_PAR_MOIS[index]
        sortie.append({
            'mois': index + 1,
            'jours': jours,
            'saison': saison_du_mois(index + 1),
            'mad': montant,
            'jour_mad': round(montant / jours, 2) if jours else None,
        })
    return sortie


def _par_saison(mois):
    """``{saison: {mad, jours, jour_mad}}`` — somme des mois de la saison.

    Le jour type de la saison est la somme des MAD divisée par la somme des
    JOURS (moyenne pondérée), jamais la moyenne des jours types mensuels : un
    février de 28 jours ne pèse pas autant qu'un juillet de 31.
    """
    cumuls = {}
    for entree in mois:
        saison = entree.get('saison')
        if not saison:
            continue
        cumul = cumuls.setdefault(saison, {'mad': 0, 'jours': 0})
        cumul['mad'] += entree['mad']
        cumul['jours'] += entree['jours']
    return {
        saison: {
            'mad': cumul['mad'],
            'jours': cumul['jours'],
            'jour_mad': (round(cumul['mad'] / cumul['jours'], 2)
                         if cumul['jours'] else None),
        }
        for saison, cumul in cumuls.items()
    }


def _bloc_variante(serie, saison_du_mois, payback):
    """Le triplet complet d'UNE variante (sans batterie, avec, ou un profil)."""
    mois = _par_mois(serie, saison_du_mois)
    bloc = {
        'annuel_mad': sum(entree['mad'] for entree in mois),
        'mois': mois,
        'saisons': _par_saison(mois),
    }
    if payback is not None:
        bloc['retour_investissement_ans'] = payback
    return bloc


def _profils_par_periode(profils_bloc, saison_du_mois, avec_servi):
    """Les mêmes déclinaisons, par profil d'occupation.

    RÉUTILISE la machinerie ``profils_comparatifs`` : ce sont les séries que le
    moteur horaire a calculées pour CHAQUE silhouette (présent / absent /
    présence partielle) sur les MÊMES factures. Quand le visiteur change de
    profil sur la page, il lit donc des économies calculées SERVEUR pour ce
    comportement-là — la page ne multiplie rien.

    Un profil dont la série mensuelle n'a pas été persistée (bloc antérieur à
    cette couche) est simplement ABSENT : jamais un profil affiché avec les
    chiffres d'un autre.
    """
    if not isinstance(profils_bloc, dict):
        return None
    sortie = []
    for entree in profils_bloc.get('profils') or []:
        if not isinstance(entree, dict):
            continue
        occupation = entree.get('occupation')
        serie_sans = _serie_12(entree.get('economies_mois_sans'))
        if not occupation or serie_sans is None:
            continue
        variante = {
            'occupation': occupation,
            'est_profil_reel': bool(entree.get('est_profil_reel')),
            'sans': _bloc_variante(serie_sans, saison_du_mois, None),
        }
        serie_avec = (_serie_12(entree.get('economies_mois_avec'))
                      if avec_servi else None)
        if serie_avec is not None:
            variante['avec'] = _bloc_variante(
                serie_avec, saison_du_mois, None)
        sortie.append(variante)
    return sortie or None


def construire_economies_periodes(data, economies_mensuelles, etude_params):
    """Bloc public ``economies_periodes``, ou ``None``. Ne lève jamais.

    ``economies_mensuelles`` est le bloc DÉJÀ construit pour ce payload : c'est
    lui la source unique des douze valeurs, pour que les deux blocs de la page
    ne puissent pas diverger.
    """
    try:
        return _construire(data, economies_mensuelles, etude_params)
    except Exception:  # noqa: BLE001 — un bandeau d'affichage additif ne fait
        # JAMAIS tomber la proposition entière (prix, composition, signature).
        # Même discipline que ``_economies_mensuelles_publiques``.
        logger.warning('economies_periodes indisponibles', exc_info=True)
        return None


def _construire(data, economies_mensuelles, etude_params):
    """Cœur de :func:`construire_economies_periodes` (exceptions gérées
    au-dessus)."""
    if not isinstance(economies_mensuelles, dict):
        return None
    serie_sans = _serie_12(economies_mensuelles.get('sans'))
    if serie_sans is None:
        return None

    from apps.ventes.etude_horaire import saison_du_mois

    # « avec batterie » suit EXACTEMENT la garde d'``economies_mensuelles`` :
    # jamais un chiffre « avec » sur un devis qui ne peut pas livrer l'option.
    serie_avec = _serie_12(economies_mensuelles.get('avec'))

    bloc = {
        'devise': 'MAD',
        'source_mois': SOURCE_MOIS,
        'source_retour_investissement': SOURCE_PAYBACK,
        'modele': economies_mensuelles.get('modele'),
        'estimation': bool(economies_mensuelles.get('estimation')),
        'sans': _bloc_variante(serie_sans, saison_du_mois,
                               _ans((data or {}).get('roi_s'))),
    }
    if serie_avec is not None:
        bloc['avec'] = _bloc_variante(serie_avec, saison_du_mois,
                                      _ans((data or {}).get('roi_a')))

    profils = _profils_par_periode(
        (etude_params or {}).get('profils_comparatifs'), saison_du_mois,
        serie_avec is not None)
    if profils:
        bloc['profils'] = profils
    return bloc
