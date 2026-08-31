"""QJR42 — LES ENTRÉES DU MOTEUR : un dataclass, deux adaptateurs.

CE QUE CE MODULE FERME. Le même client était lu de DEUX façons selon le chemin
emprunté : ``services.entrees_dimensionnement_du_devis`` pour un devis déjà
créé, et le corps de ``services._panneaux_dimensionnement_horaire`` pour le
devis automatique / tunnel (qui part d'un LEAD, avant qu'un devis n'existe).
Deux lectures ⇒ deux dimensionnements possibles pour la même fiche. Ici les
deux chemins rendent la MÊME forme — :class:`EntreesMoteur` — construite par
deux adaptateurs qui sont les SEULS endroits où une fiche (lead ou devis) est
traduite en entrées du moteur.

CE MODULE NE CALCULE RIEN ET N'ÉCRIT RIEN. Il LIT une fiche et rend ses
entrées ; le dimensionnement lui-même reste dans ``apps.ventes.dimensionnement``
(règle #4 : aucun statut, aucune ligne, aucun total n'est touché ici).

POURQUOI UNE FORME « LISIBLE COMME UN DICT ». ``entrees_depuis_devis`` est le
déplacement TEL QUEL de ``services.entrees_dimensionnement_du_devis``, dont les
appelants existants (``dimensionnement._echelle_paliers_batterie``,
``offres_tailles._contexte``, ``services.rafraichir_dimensionnement_devis``)
lisent le résultat par indice (``entrees['ville']``, ``entrees.get(...)``).
:class:`EntreesMoteur` offre donc un accès mapping en LECTURE SEULE : le
déplacement ne change alors AUCUN appelant, ce qui est exactement ce qu'exige
la règle « une tâche déplace OU corrige, jamais les deux ».
"""
from dataclasses import dataclass, fields as _champs_dataclass
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

#: QJR43 — VERSION DU MOTEUR D'ENTRÉES. Entre dans l'empreinte : la bouger
#: périme TOUS les blocs rangés (un recalcul, une fois, par devis). C'est le
#: seul levier pour invalider un cache après un changement de RÈGLE (une
#: silhouette d'occupation retouchée, une couche d'équipement corrigée) que
#: les entrées elles-mêmes ne reflètent pas.
VERSION_MOTEUR_ENTREES = 'qjr43-1'

#: Précision retenue pour la localisation : 4 décimales ≈ 11 m. Au-delà, deux
#: relevés GPS du MÊME toit produiraient deux empreintes et feraient recalculer
#: le tableau le plus lourd du parcours pour rien.
_DECIMALES_GPS = 4


@dataclass(frozen=True)
class EntreesMoteur:
    """Les entrées du moteur calibré pour UNE fiche (un lead ou un devis).

    GELÉ (``frozen=True``) : une entrée lue ne se réécrit pas en route — c'est
    ce qui rend l'empreinte de QJR43 fiable (une valeur qui bouge après coup
    invaliderait silencieusement la clé de cache).

    LES CHAMPS CANONIQUES (ceux que le moteur consomme) :
    ``company``, ``conso_kwh_mensuelles``, ``source_conso``, ``ville``,
    ``lat``, ``lon``, ``occupation``, ``equipements``, ``tranches``,
    ``charges_fixes_mad``, ``jour_reference``.

    ``tranches`` / ``charges_fixes_mad`` — L'IDENTITÉ TARIFAIRE (QJR46) : la
    surcharge de barème de la SOCIÉTÉ, lue par le MÊME
    ``etude_horaire._reglages_tarifaires`` que le moteur de devis. Elles ne
    sont lues qu'avec ``contexte=True`` (comme la localisation) : le chemin de
    garde ne paie aucune requête de plus. ``jour_reference`` est posé par
    QJR45 (voir :func:`jour_reference_par_defaut`).

    DEUX CHAMPS DE CONTEXTE, non canoniques : ``mode`` (le
    ``mode_installation`` déjà vérifié par l'adaptateur) et ``etude_params``
    (le JSON du devis). Ils existent parce que les appelants du chemin DEVIS
    les lisaient déjà sur le dict rendu par
    ``services.entrees_dimensionnement_du_devis`` ; ils n'entrent PAS dans
    l'empreinte des entrées.
    """

    company: object = None
    mode: str = ''
    etude_params: dict = None
    conso_kwh_mensuelles: object = None
    source_conso: object = None
    ville: object = None
    lat: object = None
    lon: object = None
    occupation: object = None
    equipements: object = None
    tranches: object = None
    charges_fixes_mad: object = None
    jour_reference: object = None

    # ── accès mapping en LECTURE SEULE (pont de déplacement, voir docstring) ─

    def keys(self):
        return tuple(champ.name for champ in _champs_dataclass(self))

    def __getitem__(self, cle):
        try:
            return getattr(self, cle)
        except AttributeError:
            raise KeyError(cle) from None

    def __contains__(self, cle):
        return cle in self.keys()

    def get(self, cle, defaut=None):
        return getattr(self, cle, defaut)


def _reglages_tarifaires_de(company):
    """QJR46 — ``(tranches, charges_fixes_mad)`` de la SOCIÉTÉ.

    UNE SEULE lecture pour tout le monde : c'est exactement
    ``etude_horaire._reglages_tarifaires``, celle que le moteur de DEVIS
    applique déjà. Avant QJR46, le dimensionnement omettait simplement les deux
    kwargs — ils retombaient sur ``None`` (grille nationale) — pendant que le
    devis appliquait la surcharge de la société : le MÊME kWh était valorisé
    sur deux barèmes, et le site d'appel ne voyait rien puisque les kwargs
    étaient OMIS plutôt que refusés.
    """
    from apps.ventes.etude_horaire import _reglages_tarifaires
    return _reglages_tarifaires(company)


def jour_reference_par_defaut():
    """QJR45 — LA FRONTIÈRE DU PIPELINE : « aujourd'hui », lu UNE seule fois.

    La sortie du moteur dépend de la date (fenêtre Ramadan de
    ``apps.ventes.ramadan``) : sans paramètre, le même devis rendait des
    économies différentes selon le MOMENT du recalcul, et rien ne disait quelle
    date avait servi. La date est donc résolue ICI, à l'entrée du pipeline, et
    voyage ensuite dans :class:`EntreesMoteur` — jusqu'au moteur (qui calcule
    contre elle) ET jusqu'à l'empreinte (qui la trace).
    """
    from django.utils import timezone
    return timezone.localdate()


def _date_lisible(valeur):
    """``valeur`` en ``date``, ou ``None`` si elle n'en est pas une.

    Tolérant par conception : une surcharge illisible (texte libre, nombre,
    objet) ne DÉCIDE rien — elle vaut une absence, jamais une date inventée.
    """
    from datetime import date, datetime

    if isinstance(valeur, datetime):
        # Un horodatage EN BASE est UTC-aware : on le ramène au fuseau local,
        # la même convention que ``jour_reference_par_defaut``
        # (``timezone.localdate()``) — sinon un devis créé après 23 h locales
        # serait daté de la veille (ou du lendemain) selon le fuseau.
        from django.utils import timezone
        if timezone.is_aware(valeur):
            return timezone.localdate(valeur)
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    if isinstance(valeur, str) and valeur.strip():
        try:
            return date.fromisoformat(valeur.strip()[:10])
        except ValueError:
            return None
    return None


def jour_reference_du_devis(devis):
    """QJR232 — LA DATE DE RÉFÉRENCE DE CE DEVIS. Une, stable, et lisible.

    LE TROU QUE CECI BOUCHE, en trois symptômes du MÊME défaut :

    * ``empreinte_entrees`` fait entrer ``jour_reference`` (à raison — QJR45 :
      sans lui, le même devis rendait des économies différentes selon le
      MOMENT du recalcul, sans que rien ne dise quelle date avait servi). Mais
      la date valait « aujourd'hui » : le bloc le plus coûteux du devis était
      donc invalidé UNE FOIS PAR JOUR CIVIL ET PAR DEVIS, alors que le module
      promet « recalcule SI ET SEULEMENT SI une entrée a bougé ».
    * ``etude.jour_reference`` est accepté et PERSISTÉ par le registre D12
      (``domain/overrides``) et AUCUN chemin moteur ne le lisait : un vendeur
      posait une date de référence et le dimensionnement continuait de
      calculer sur l'horloge du jour, pendant que le code affirmait le
      contraire.
    * ``profils_comparatifs`` relisait la fiche à la main et OMETTAIT
      ``jour_reference`` : le bloc persisté sous une empreinte qui épingle la
      date du devis était en fait calculé sur une SECONDE lecture d'horloge.

    L'ORDRE DE RÉSOLUTION, et il n'y en a qu'un :

    1. la surcharge **déclarée** ``etude.jour_reference`` du registre D12 — le
       vendeur DÉCLARE la date contre laquelle il veut voir calculer ;
    2. sinon la **date du devis** (``date_creation``) : elle est PERSISTÉE dès
       le premier calcul (c'est la création elle-même), elle ne bouge jamais,
       et elle décrit la date à laquelle l'offre a été construite ;
    3. sinon seulement — aucun devis, aucune date — « aujourd'hui »
       (:func:`jour_reference_par_defaut`), le chemin LEAD, inchangé.

    INTERDIT, ET C'EST LA RAISON DE CE DÉTOUR : retirer ``jour_reference`` de
    l'empreinte. Ce serait recréer l'irreproductibilité Ramadan que QJR45 a
    fermée. On stabilise la DATE, on ne dé-trace pas le calcul.

    LECTURE PURE : rien n'est écrit (règle #4).
    """
    from apps.ventes.domain.overrides import effectif

    try:
        valeur, source = effectif(devis, 'etude.jour_reference', None)
    except Exception:  # noqa: BLE001 — un registre illisible ne décide rien
        valeur, source = None, 'auto'
    if source != 'auto':
        declaree = _date_lisible(valeur)
        if declaree is not None:
            return declaree
    du_devis = _date_lisible(getattr(devis, 'date_creation', None))
    if du_devis is not None:
        return du_devis
    return jour_reference_par_defaut()


def entrees_depuis_devis(devis, *, contexte=True, jour_reference=None):
    """P2-A (25/08/2026), déplacé ici par QJR42 — LES ENTRÉES du moteur calibré
    pour CE devis, lues UNE SEULE FOIS et par UNE SEULE fonction.

    RAISON D'ÊTRE : deux lectures ⇒ deux dimensionnements. Le tableau rangé par
    ``services.rafraichir_dimensionnement_devis`` et l'échelle de paliers
    batterie (``dimensionnement.echelle_paliers_batterie``) doivent partir des
    MÊMES factures, de la MÊME localisation, de la MÊME occupation et des MÊMES
    équipements — sinon l'écran montrerait une échelle qui ne se raccorde pas au
    palier « retenu » qu'il désigne. Cette fonction est cette lecture unique.

    Renvoie ``None`` quand le devis n'est pas dimensionnable DU TOUT (mode non
    résidentiel, ou aucune société), sinon un :class:`EntreesMoteur` dont
    ``conso_kwh_mensuelles`` peut valoir ``None`` — c'est-à-dire « société et
    mode d'accord, mais aucun profil de consommation exploitable » : l'appelant
    distingue ainsi les deux situations, qui n'appellent pas la même réaction
    (l'une ne calcule rien, l'autre RETIRE une clé devenue périmée).

    L'ORDRE DES LECTURES EST DÉLIBÉRÉ : la localisation, l'occupation et les
    équipements ne sont lus qu'APRÈS que la consommation s'est avérée
    exploitable — c'est une requête de moins sur le chemin qui ne calculera
    rien de toute façon. ``contexte=False`` les saute complètement (ils restent
    à ``None``) : c'est ce que veut un appelant qui n'a besoin que de la GARDE
    (mode, société, profil exploitable) avant de décider s'il recalcule —
    typiquement ``rafraichir_dimensionnement_devis`` sur son chemin de cache,
    appelé à chaque enregistrement de ligne et qui ne doit y payer AUCUNE
    requête de plus qu'avant. **CE PARAMÈTRE RESTE** : le supprimer ferait
    payer deux requêtes de plus à chaque sauvegarde de ligne.

    ``jour_reference`` — QJR45 : la date contre laquelle le moteur calcule
    (fenêtre Ramadan). ``None`` ⇒ :func:`jour_reference_du_devis` (QJR232 : la
    surcharge D12 ``etude.jour_reference``, sinon la DATE DU DEVIS — plus
    l'horloge du jour, qui périmait l'empreinte une fois par jour civil), lu
    ICI et une seule fois.

    Fonction de LECTURE PURE : elle n'écrit rien, ne touche ni statut, ni
    ligne, ni total (règle #4).
    """
    mode = (getattr(devis, 'mode_installation', None) or '').strip().lower()
    if mode != 'residentiel':
        return None
    company = getattr(devis, 'company', None)
    if company is None:
        return None
    jour = jour_reference or jour_reference_du_devis(devis)

    from apps.crm.selectors import lead_bills_for_devis, site_location_for_devis
    from apps.ventes.courbes_journalieres import (
        equipements_du_devis, occupation_du_devis)
    from apps.ventes.etude_horaire import profil_depuis_factures

    bills = lead_bills_for_devis(devis) or {}
    etude_params = getattr(devis, 'etude_params', None) or {}
    conso, source_conso, _detail = profil_depuis_factures(
        facture_hiver_mad=bills.get('facture_hiver'),
        facture_ete_mad=bills.get('facture_ete'),
        ete_differente=bills.get('ete_differente'),
        factures_mensuelles_mad=etude_params.get('factures_mensuelles_reelles'),
        conso_kwh_mensuelles=etude_params.get('conso_kwh_mensuelles'))

    if not conso or not contexte:
        return EntreesMoteur(
            company=company, mode=mode, etude_params=etude_params,
            conso_kwh_mensuelles=conso, source_conso=source_conso,
            jour_reference=jour)

    localisation = site_location_for_devis(devis) or {}
    # Même relai que ``etude_horaire._etude_horaire_pour_devis`` : sans
    # ``mode_installation`` explicite, ``_occupation`` retombe sur le défaut
    # NON résidentiel — on lui donne donc le mode du devis (déjà vérifié
    # 'residentiel' ci-dessus) pour que le défaut fondateur résidentiel
    # s'applique.
    occupation, _source_occ = occupation_du_devis(
        devis, {'mode_installation': mode})
    tranches, charges_fixes = _reglages_tarifaires_de(company)
    return EntreesMoteur(
        company=company, mode=mode, etude_params=etude_params,
        conso_kwh_mensuelles=conso, source_conso=source_conso,
        ville=localisation.get('site_ville'),
        lat=localisation.get('gps_lat'),
        lon=localisation.get('gps_lng'),
        occupation=occupation,
        equipements=equipements_du_devis(devis),
        tranches=tranches, charges_fixes_mad=charges_fixes,
        jour_reference=jour)


def entrees_depuis_lead(lead, company, *, contexte=True, jour_reference=None):
    """QJR42 — LES MÊMES entrées, lues sur un LEAD (le chemin auto-devis /
    tunnel, où aucun devis n'existe encore).

    C'est la traduction du corps de ``services._panneaux_dimensionnement_horaire``
    en une lecture NOMMÉE et partagée : la facture d'hiver (et la facture d'été
    quand ``ete_differente``), la localisation de la fiche, l'occupation lue par
    ``courbes_journalieres.occupation_du_lead`` (QJR10 / décision fondateur D4 :
    défaut PRÉSENCE, jamais la silhouette de repli PARTIELLE) et les QUINZE
    champs d'équipement de ``crm.selectors.equipements_pour_lead`` (QJR9).

    Rend la MÊME forme que :func:`entrees_depuis_devis`, clé pour clé :
    ``etude_params`` vaut ``{}`` (un lead n'en porte pas) et ``mode`` vaut
    ``'residentiel'`` — c'est le SEUL marché que ce chemin dimensionne.

    ``None`` quand la fiche n'est pas dimensionnable du tout (aucune société).
    ``conso_kwh_mensuelles`` à ``None`` quand aucune facture n'est exploitable :
    l'appelant refuse alors le devis en NOMMANT la donnée manquante, jamais un
    repli forfaitaire (règle fondateur « zéro chiffre inventé »).

    ``jour_reference`` — QJR45 : même sens et même défaut que sur
    :func:`entrees_depuis_devis` (aujourd'hui, lu une seule fois ici).

    Fonction de LECTURE PURE : elle n'écrit rien (règle #4).
    """
    if lead is None or company is None:
        return None
    jour = jour_reference or jour_reference_par_defaut()

    from apps.crm.selectors import equipements_pour_lead
    from apps.ventes.courbes_journalieres import (
        composer_equipements, occupation_du_lead)
    from apps.ventes.etude_horaire import profil_depuis_factures

    conso, source_conso, _detail = profil_depuis_factures(
        facture_hiver_mad=getattr(lead, 'facture_hiver', None),
        facture_ete_mad=getattr(lead, 'facture_ete', None),
        ete_differente=getattr(lead, 'ete_differente', False))

    if not conso or not contexte:
        return EntreesMoteur(
            company=company, mode='residentiel', etude_params={},
            conso_kwh_mensuelles=conso, source_conso=source_conso,
            jour_reference=jour)

    occupation, _source_occ = occupation_du_lead(lead)
    tranches, charges_fixes = _reglages_tarifaires_de(company)
    return EntreesMoteur(
        company=company, mode='residentiel', etude_params={},
        conso_kwh_mensuelles=conso, source_conso=source_conso,
        jour_reference=jour,
        ville=getattr(lead, 'ville', None),
        lat=getattr(lead, 'gps_lat', None),
        lon=getattr(lead, 'gps_lng', None),
        occupation=occupation,
        equipements=composer_equipements(equipements_pour_lead(lead)),
        tranches=tranches, charges_fixes_mad=charges_fixes)


# ════════════════════════════════════════════════════════════════════════════
# QJR43 — L'EMPREINTE DES ENTRÉES
# ════════════════════════════════════════════════════════════════════════════
# CE QU'ELLE REMPLACE. Le bloc le plus lourd du parcours
# (``etude_params['dimensionnement']`` : un balayage de toutes les tailles
# candidates, chacune composant le catalogue et simulant douze jours types)
# était mis en cache sur la simple PRÉSENCE de sa clé. RIEN ne l'invalidait :
# le commercial pouvait corriger la facture d'hiver, l'occupation ou les
# équipements du lead, le tableau servi restait celui de la première lecture.
# L'empreinte fait exactement l'inverse : elle recalcule SI ET SEULEMENT SI une
# entrée a bougé.


def _arrondi(valeur, decimales):
    """Un nombre arrondi, ou ``None`` — jamais une exception sur une saisie."""
    if valeur is None or valeur == '':
        return None
    try:
        return round(float(valeur), decimales)
    except (TypeError, ValueError):
        return None


def _serie_arrondie(serie, decimales=3):
    """Une série de nombres arrondis (le bruit flottant ne périme rien)."""
    if serie is None:
        return None
    if isinstance(serie, (list, tuple)):
        return [_arrondi(v, decimales) for v in serie]
    return _arrondi(serie, decimales)


def _texte(valeur):
    """Un texte normalisé (casse/espaces), ou ``None``."""
    if valeur is None:
        return None
    texte = str(valeur).strip().lower()
    return texte or None


def _tranches_canoniques(tranches):
    """QJR46 — une table de tranches réduite à ce qui la DÉFINIT.

    ``pricing.TrancheTable`` est une sous-classe de ``list`` : sérialisée
    telle quelle, elle rendrait ses paires mais PERDRAIT
    ``selective_threshold`` et ``boundary_tolerance`` — deux barèmes aux mêmes
    paires mais au seuil sélectif différent auraient la même empreinte. On
    sérialise donc les trois, explicitement. (Et jamais ``str(objet)`` : la
    représentation par défaut porte une adresse mémoire, qui changerait
    l'empreinte à chaque processus.)
    """
    if tranches is None:
        return None
    try:
        paires = [[_arrondi(paire[0], 3), _arrondi(paire[1], 6)]
                  for paire in tranches]
    except (TypeError, IndexError, KeyError):
        return None
    return {
        'paires': paires,
        'seuil_selectif': _arrondi(
            getattr(tranches, 'selective_threshold', None), 3),
        'tolerance_bord': _arrondi(
            getattr(tranches, 'boundary_tolerance', None), 3),
    }


def empreinte_entrees(e):
    """QJR43 — l'empreinte SHA-256 des entrées du moteur pour cette fiche.

    CE QUI Y ENTRE, et rien d'autre : la consommation mensuelle, sa source, la
    localisation (ville normalisée, lat/lon arrondis à ``_DECIMALES_GPS``),
    l'occupation, les couches d'équipement, l'identité tarifaire
    (``tranches`` + ``charges_fixes_mad``), le ``jour_reference`` et
    :data:`VERSION_MOTEUR_ENTREES`.

    POURQUOI LES COUCHES D'ÉQUIPEMENT PLUTÔT QUE LES 15 CHAMPS BRUTS. Les 15
    champs du lead (``crm.selectors.equipements_pour_lead``) ne franchissent le
    moteur que sous la forme composée par ``courbes_journalieres`` — une
    piscine déclarée SANS puissance de pompe ne produit aucune couche et ne
    change donc AUCUN chiffre. Empreindre les couches, c'est empreindre
    exactement ce que le moteur consomme : ni un recalcul de moins (toute
    grandeur réelle qui bouge change sa couche), ni un recalcul de trop.

    NE FAIT PAS ENTRER ``mode`` / ``etude_params`` : ce sont des champs de
    contexte du chemin devis, pas des entrées du moteur (``etude_params``
    contient d'ailleurs le bloc que cette empreinte estampille — l'y inclure
    créerait une dépendance circulaire).

    Rend un texte hexadécimal stable entre deux processus (``json.dumps``
    trié, séparateurs figés) : deux serveurs ne peuvent pas se contredire.
    """
    charge = {
        'version': VERSION_MOTEUR_ENTREES,
        'conso_kwh_mensuelles': _serie_arrondie(
            getattr(e, 'conso_kwh_mensuelles', None)),
        'source_conso': _texte(getattr(e, 'source_conso', None)),
        'ville': _texte(getattr(e, 'ville', None)),
        'lat': _arrondi(getattr(e, 'lat', None), _DECIMALES_GPS),
        'lon': _arrondi(getattr(e, 'lon', None), _DECIMALES_GPS),
        'occupation': _texte(getattr(e, 'occupation', None)),
        'equipements': getattr(e, 'equipements', None) or {},
        'tranches': _tranches_canoniques(getattr(e, 'tranches', None)),
        'charges_fixes_mad': _arrondi(
            getattr(e, 'charges_fixes_mad', None), 2),
        'jour_reference': _texte(getattr(e, 'jour_reference', None)),
    }
    canonique = json.dumps(charge, sort_keys=True, separators=(',', ':'),
                           default=str, ensure_ascii=False)
    return hashlib.sha256(canonique.encode('utf-8')).hexdigest()


def empreinte_entrees_du_devis(devis):
    """QJR44 — l'empreinte des entrées de CE devis, en une lecture.

    ``None`` quand le devis n'est pas dimensionnable (mode, société) ou que
    son profil de consommation n'est pas exploitable : aucun bloc dérivé ne
    peut alors être déclaré frais, et l'appelant recalcule (ou retire sa clé).
    Jamais une empreinte de repli : « pas d'entrées » ne vaut pas « entrées
    inchangées ».
    """
    entrees = entrees_depuis_devis(devis)
    if entrees is None or not entrees.conso_kwh_mensuelles:
        return None
    return empreinte_entrees(entrees)
