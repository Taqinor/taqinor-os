"""OPTIONS CHARGEABLES — le DÉTAIL d'une taille explorable (Éco / Max).

ORDRE FONDATEUR (29/08/2026) : « i want the 3 options to be LOADABLE in the
webpage if client clicks on one of them ». Jusqu'ici, cliquer une carte de
taille ne synchronisait que les CHIFFRES DE TÊTE de la page, en RECOPIANT le
texte déjà rendu par la carte. Les chapitres PROFONDS — les économies mois par
mois, la couverture, la banque batterie, le cumul 25 ans — continuaient
d'afficher les nombres du DEVIS OFFICIEL sous une carte qui n'est pas lui :
des nombres RÉELS, mais ATTRIBUÉS À LA MAUVAISE OFFRE. Ce module sert ce qui
manque pour charger la page ENTIÈRE d'une option.

CE QU'IL NE FAIT PAS, ET C'EST LE POINT.

* Il ne CALCULE aucune carte. Le bloc ``carte`` servi ici est, à l'octet près,
  celui que ``offres_tailles.offres_tailles_publique`` a déjà dérivé pour la
  page — même dérivation, mêmes filtres de section, mêmes arrondis. Deux
  chemins de calcul pour la même carte, c'est exactement l'incident « 21 contre
  22 » que ce parcours a déjà payé une fois.
* Il ne sert PAS « Recommandé ». Cette carte EST le devis : son détail est déjà
  la page servie au chargement, que le navigateur restaure depuis ses originaux
  mis en cache. Lui donner un endpoint aurait rouvert le même risque.
* Il n'ÉCRIT rien (règle #4) : ni ligne, ni total, ni statut, ni
  ``offres_tailles_config``, ni trace d'ouverture — un clic de carte n'est pas
  une seconde consultation.

Contrat : ``apps/ventes/contract_samples/taille_detail.json``.
"""

import hashlib
import json
import logging

logger = logging.getLogger(__name__)

#: Les SEULES tailles qui ont un détail à charger. « Recommandé » n'y est pas
#: (voir l'en-tête) et n'y sera pas : la page le restaure, elle ne le refetch
#: jamais.
CLES_CHARGEABLES = ('eco', 'max')

VARIANTES = ('sans', 'avec')

#: Durée de mémoïsation du détail dérivé. Court DÉLIBÉRÉMENT : la clé porte
#: déjà l'empreinte de la configuration stockée (donc un ajustement vendeur
#: invalide immédiatement), et un quart d'heure suffit à couvrir la session de
#: lecture d'un client — au-delà, mieux vaut re-dériver que servir vieux.
CACHE_SECONDES = 900


def _empreinte_config(devis):
    """Ce qui, sur ce devis, peut changer un détail sans changer son URL.

    La configuration des tailles (``offres_tailles_config``) est la SEULE
    entrée que le vendeur peut modifier entre deux lectures sans que le jeton,
    la taille ou la variante ne bougent. La faire entrer dans la clé de cache,
    c'est garantir qu'un « Régénérer » côté vendeur se voit tout de suite chez
    le client — sans aucune invalidation à écrire à la main (donc sans le
    risque d'oublier de l'écrire).

    ``updated_at`` du devis y entre aussi : re-dimensionner le devis change les
    trois cartes, pas seulement celle qu'on a ajustée.
    """
    brut = getattr(devis, 'offres_tailles_config', None)
    maj = getattr(devis, 'updated_at', None)
    graine = json.dumps(
        {'config': brut, 'maj': maj.isoformat() if maj else None},
        sort_keys=True, default=str)
    return hashlib.sha256(graine.encode('utf-8')).hexdigest()[:16]


def cle_cache(link, cle, variante):
    """La clé de mémoïsation d'UN détail. Bornée au LIEN, jamais au devis seul.

    Le lien porte le niveau de partage ET les cases de section : deux liens du
    même devis peuvent servir des tailles différentes. Une clé au devis les
    aurait mélangés — un client verrait le détail d'une taille que son propre
    lien ne sert pas.
    """
    return 'taille-detail:%s:%s:%s:%s' % (
        getattr(link, 'pk', 'x'), cle, variante,
        _empreinte_config(getattr(link, 'devis', None)))


def _economies_mensuelles(etude, variante):
    """Les douze économies MAD de CETTE taille, dans CETTE variante.

    LU sur le bloc ``mois`` de l'étude horaire déjà calculée pour la carte
    (``economie_sans_mad`` / ``economie_avec_mad``) — la même grandeur, la même
    échelle de temps et le même arrondi que le bloc ``economies_mensuelles``
    du payload de la page. Aucune seconde intégration.

    ``None`` dès que l'étude ne rend pas douze mois : c'est déjà la règle
    « année complète ou rien » du moteur, et une série de onze mois se lirait
    comme une année en dessous de la vérité.
    """
    mois = (etude or {}).get('mois')
    if not isinstance(mois, list) or len(mois) != 12:
        return None
    champ = 'economie_%s_mad' % variante
    valeurs = []
    for bloc in mois:
        valeur = (bloc or {}).get(champ)
        if not isinstance(valeur, (int, float)) or isinstance(valeur, bool):
            return None
        valeurs.append(round(valeur))
    return {
        'valeurs': valeurs,
        'total': round(sum(valeurs)),
        'devise': 'MAD',
    }


def _cashflow(profond, variante, horizon, escalade):
    """La courbe cumulée de cette taille, telle que la page la trace déjà.

    Elle vient du MÊME appel ``compute_cashflow_payback`` que le
    ``economies_cumulees_25_ans_mad`` de la carte (passe-plat ``sortie`` de
    ``offres_tailles._cumul_moteur``) : le dernier point de cette série EST le
    chiffre affiché sur la carte, par construction. La recalculer ici aurait
    été la deuxième occasion d'oublier l'un de ses deux arguments de
    discipline (``inverter_replace_cost``, ``battery_share``).
    """
    serie = ((profond or {}).get('cashflow') or {}).get(variante)
    if not serie:
        return None
    bloc = {'cumulative': list(serie)}
    if horizon is not None:
        bloc['horizon_annees'] = horizon
    if escalade is not None:
        bloc['escalade_tarifaire_pct'] = escalade
    return bloc


def deriver_detail(devis, data, bloc_tailles, cle, variante):
    """Le détail d'UNE taille, ou ``None``. PEUT lever (voir le filet public).

    ``bloc_tailles`` est le bloc ``offres_tailles`` DÉJÀ dérivé et DÉJÀ filtré
    pour ce lien : c'est lui, et lui seul, qui décide si cette taille est
    servable à ce client. Ce module n'ajoute AUCUNE règle d'accès de son cru —
    une règle recopiée finit toujours par diverger de son original.
    """
    if cle not in CLES_CHARGEABLES or variante not in VARIANTES:
        return None
    offres = (bloc_tailles or {}).get('offres') or []
    offre = next((o for o in offres if o.get('cle') == cle), None)
    if offre is None:
        return None
    carte = offre.get(variante)
    if not carte:
        return None

    from . import offres_tailles as moteur

    contexte = moteur._contexte(devis)
    if contexte is None:
        return None
    nb_panneaux = carte.get('nb_panneaux')
    if not nb_panneaux:
        return None
    config = (moteur.lire_config_stockee(devis).get(cle) or {}).get('config') \
        or {}
    # LE MÊME DRAPEAU QUE LA DÉRIVATION, PAS CELUI DE LA VARIANTE DEMANDÉE.
    # ``avec_servable`` court-circuite le chemin batterie AVANT le calcul :
    # le passer à faux pour un détail « sans » ferait tourner l'étude horaire
    # sans capacité là où la dérivation l'a fait avec — deux passages voisins,
    # donc deux séries potentiellement différentes sous la même carte.
    avec_servable = 'avec' in list((data or {}).get('variantes_servables')
                                   or [])
    profond = {}
    moteur._carte_moteur(contexte, int(nb_panneaux), config,
                         avec_servable=avec_servable,
                         sortie_profonde=profond)

    detail = {
        'cle': cle,
        'titre': offre.get('titre'),
        'variante': variante,
        'est_le_devis': bool(offre.get('est_le_devis')),
        'carte': carte,
    }
    mensuelles = _economies_mensuelles(profond.get('etude'), variante)
    if mensuelles is not None:
        detail['economies_mensuelles'] = mensuelles
    cashflow = _cashflow(profond, variante,
                         (bloc_tailles or {}).get('horizon_annees'),
                         (bloc_tailles or {}).get('escalade_tarifaire_pct'))
    if cashflow is not None:
        detail['cashflow'] = cashflow
    return detail


def detail_publique(devis, data, bloc_tailles, cle, variante):
    """Le détail pour la page publique — best-effort, ne lève JAMAIS.

    MÊME patron que ``offres_tailles.offres_tailles_publique`` : toute
    exception est journalisée et la réponse devient ``None`` — que la vue
    traduit en 404 générique. La page retombe alors sur ce qu'elle sait déjà
    faire (la synchronisation des seuls chiffres de tête) et propose de
    réessayer : un chapitre profond indisponible ne casse jamais la lecture.
    """
    try:
        return deriver_detail(devis, data, bloc_tailles, cle, variante)
    except Exception:  # noqa: BLE001
        logger.warning('taille_detail indisponible', exc_info=True)
        return None
