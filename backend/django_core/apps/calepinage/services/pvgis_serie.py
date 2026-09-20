"""CAL135 — le client PVGIS du module : série HORAIRE ``seriescalc``, côté ERP.

LE CONSTAT
----------
Le backend ne connaissait que le MENSUEL (``apps/parametres/pvgis_profils.py``
via ``PVcalc``, et ``DRcalc`` pour la forme d'un jour moyen). La seule série
HORAIRE du dépôt vit dans le Worker du site public
(``apps/web/src/pages/api/roof-production.ts``) : inaccessible à l'ERP. Or une
étude de calepinage (autoconsommation, batterie, courbe de charge, export CSV)
se joue à l'heure, pas au mois.

CE QUE CE CLIENT GARANTIT
-------------------------
1. **Les pertes sont une ENTRÉE (CAL238).** L'appel reçoit une
   ``PolitiquePertes`` et met dans la requête la somme explicite de ses
   postes ; la valeur envoyée est republiée avec le résultat. Ce module
   n'a AUCUNE perte par défaut — sans politique, il n'appelle pas.
2. **Aucun repli silencieux.** PVGIS injoignable, surchargé ou incohérent ⇒
   ``PvgisIndisponible`` et AUCUNE production publiée. Une production de repli
   serait un chiffre inventé présenté comme mesuré.
3. **Le réseau est INJECTABLE.** ``ClientPvgis(transport=…)`` : les tests
   rejouent une réponse ENREGISTRÉE (``tests/fixtures_pvgis/``) et ne touchent
   jamais le réseau.
4. **La cadence est respectée.** PVGIS publie une limite de 30 appels par
   seconde et répond ``529`` quand il est surchargé
   (https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/getting-started-pvgis/api-non-interactive-service_en).
   Le client s'auto-limite et retente un nombre BORNÉ de fois sur 529.
5. **La base de rayonnement est un CHOIX EXPLICITE** (CAL136) : le Maroc est
   couvert par SARAH3 ; la base réellement utilisée est republiée telle que
   PVGIS la nomme dans sa réponse, jamais telle qu'on l'a demandée.
6. **Le cache est borné** par plan arrondi (même discipline que le Worker) :
   deux pans identiques au mètre près ne paient pas deux appels.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

__all__ = [
    'BASES_RAYONNEMENT', 'BASE_PAR_DEFAUT', 'ClientPvgis', 'EntreeInvalide',
    'PvgisIndisponible', 'RACINE_API', 'azimut_pvgis', 'cle_de_cache',
    'vider_le_cache',
]

#: v5_3 — la version courante de l'API PVGIS. ``apps/ventes/weather_feed.py``
#: appelle encore ``tmy`` en v5_2 : le module, lui, ne parle qu'en v5_3 (CAL136).
RACINE_API = 'https://re.jrc.ec.europa.eu/api/v5_3'

#: Les bases de rayonnement ADMISES. SARAH3 (~0,05°) couvre le Maroc ; ERA5
#: (~0,25°) est le bouche-trou mondial. Le choix est EXPLICITE à chaque appel :
#: sur un site de montagne, les deux ne disent pas la même chose.
BASES_RAYONNEMENT = ('PVGIS-SARAH3', 'PVGIS-ERA5')

#: Le défaut du module — un CHOIX documenté (couverture Maroc), pas un hasard.
BASE_PAR_DEFAUT = 'PVGIS-SARAH3'

#: Cadence publiée par PVGIS (appels/seconde) — on reste dessous.
APPELS_PAR_SECONDE = 30

#: Une série horaire est une grosse réponse : délai plus large que le mensuel.
TIMEOUT_S = 30

#: Retentatives sur un 529 (« service surchargé »), bornées : au-delà, on
#: refuse plutôt que de marteler PVGIS.
RETENTATIVES_529 = 3
ATTENTE_529_S = 1.0

#: Durée de vie du cache. Les moyennes long terme de PVGIS ne bougent pas d'un
#: rendu à l'autre (même TTL que le Worker du site public).
CACHE_TTL_S = 6 * 60 * 60
CACHE_MAX = 200


class PvgisIndisponible(RuntimeError):
    """PVGIS injoignable, surchargé ou incohérent — AUCUNE production publiée.

    ``champ`` nomme le champ à pointer côté écran ; ``motif`` est le message
    français à afficher tel quel.
    """

    def __init__(self, message, *, champ='production'):
        super().__init__(message)
        self.champ = champ
        self.motif = message


class EntreeInvalide(ValueError):
    """Une entrée d'appel refusée, en français et en NOMMANT le champ."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def azimut_pvgis(azimut_de_face_deg):
    """Convertit un azimut de FACE du document de toiture en ``aspect`` PVGIS.

    Le document ``roof_layout`` v2 donne ``facingAzimuthDeg`` en azimut de
    face (0 = Nord, 90 = Est, 180 = Sud, 270 = Ouest) ; PVGIS attend
    ``aspect`` en degrés DEPUIS LE SUD, positif vers l'Ouest
    (0 = Sud, −90 = Est, +90 = Ouest, ±180 = Nord).
    """
    if azimut_de_face_deg is None:
        raise EntreeInvalide(
            "L'azimut du pan est inconnu : sans orientation, la production "
            'ne peut pas être demandée à PVGIS.', champ='facingAzimuthDeg')
    try:
        face = float(azimut_de_face_deg)
    except (TypeError, ValueError):
        raise EntreeInvalide(
            f"L'azimut du pan est illisible (reçu : {azimut_de_face_deg!r}).",
            champ='facingAzimuthDeg')
    aspect = (face - 180.0) % 360.0
    if aspect > 180.0:
        aspect -= 360.0
    return aspect


def cle_de_cache(service, params):
    """La clé de cache d'un appel : le PLAN ARRONDI, pas la coordonnée exacte.

    Arrondi volontaire (4 décimales ≈ 11 m, angles au dixième de degré) : deux
    pans posés au mètre près sur le même toit sont le même appel PVGIS.
    """
    arrondis = []
    for cle in sorted(params):
        valeur = params[cle]
        if cle in ('lat', 'lon'):
            valeur = round(float(valeur), 4)
        elif cle in ('angle', 'aspect'):
            valeur = round(float(valeur), 1)
        arrondis.append(f'{cle}={valeur}')
    return service + '?' + '&'.join(arrondis)


class _Limiteur:
    """Auto-limitation à ``APPELS_PAR_SECONDE`` — la cadence publiée par PVGIS.

    Fenêtre glissante d'une seconde, partagée par le processus. L'horloge et
    l'attente sont injectables : un test ne dort jamais vraiment.
    """

    def __init__(self, par_seconde=APPELS_PAR_SECONDE, horloge=None,
                 dormir=None):
        self.par_seconde = par_seconde
        self._horloge = horloge or time.monotonic
        self._dormir = dormir or time.sleep
        self._appels = []
        self._verrou = threading.Lock()

    def attendre_son_tour(self):
        with self._verrou:
            maintenant = self._horloge()
            self._appels = [t for t in self._appels if maintenant - t < 1.0]
            if len(self._appels) >= self.par_seconde:
                attente = 1.0 - (maintenant - self._appels[0])
                if attente > 0:
                    self._dormir(attente)
                    maintenant = self._horloge()
                    self._appels = [t for t in self._appels
                                    if maintenant - t < 1.0]
            self._appels.append(maintenant)


class _Cache:
    """Cache borné en taille ET en durée (jamais une fuite de mémoire)."""

    def __init__(self, ttl_s=CACHE_TTL_S, taille_max=CACHE_MAX, horloge=None):
        self.ttl_s = ttl_s
        self.taille_max = taille_max
        self._horloge = horloge or time.monotonic
        self._entrees = {}

    def lire(self, cle):
        entree = self._entrees.get(cle)
        if entree is None:
            return None
        pose_a, valeur = entree
        if self._horloge() - pose_a > self.ttl_s:
            self._entrees.pop(cle, None)
            return None
        return valeur

    def poser(self, cle, valeur):
        if len(self._entrees) >= self.taille_max:
            self._entrees.pop(next(iter(self._entrees)), None)
        self._entrees[cle] = (self._horloge(), valeur)

    def vider(self):
        self._entrees.clear()


#: Le cache PARTAGÉ du processus (un client neuf ne repart pas de zéro).
_CACHE_PARTAGE = _Cache()


def vider_le_cache():
    """Vide le cache partagé — pour les tests, et eux seuls."""
    _CACHE_PARTAGE.vider()


def _transport_urllib(url, timeout_s):
    """Transport RÉSEAU par défaut : rend ``(statut, corps)``, jamais d'appel
    caché ailleurs dans le module."""
    requete = urllib.request.Request(url, headers={
        'User-Agent': 'taqinor-os', 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(requete, timeout=timeout_s) as reponse:
            return reponse.status, reponse.read().decode('utf-8')
    except urllib.error.HTTPError as erreur:  # 4xx/5xx — dont 529
        try:
            corps = erreur.read().decode('utf-8', 'replace')
        except Exception:  # pragma: no cover - défensif
            corps = ''
        return erreur.code, corps


class ClientPvgis:
    """Le client PVGIS du module — réseau INJECTABLE, pertes EXPLICITES.

    Args:
        transport: ``callable(url, timeout_s) -> (statut, corps)``. Par défaut
            ``urllib``. Un test passe une fonction qui rend une réponse
            ENREGISTRÉE : aucun appel réseau en test, jamais.
        racine: racine de l'API (v5_3 par défaut).
        limiteur / cache : injectables pour les tests.
    """

    def __init__(self, transport=None, *, racine=RACINE_API,
                 timeout_s=TIMEOUT_S, limiteur=None, cache=None,
                 dormir=None, retentatives_529=RETENTATIVES_529):
        self.transport = transport or _transport_urllib
        self.racine = racine.rstrip('/')
        self.timeout_s = timeout_s
        self.limiteur = limiteur or _Limiteur()
        self.cache = cache if cache is not None else _CACHE_PARTAGE
        self._dormir = dormir or time.sleep
        self.retentatives_529 = retentatives_529
        #: Les URL réellement construites, dans l'ordre — c'est ce que lit le
        #: test de CAL238 pour vérifier que la perte partie est la perte
        #: publiée.
        self.urls_appelees = []

    # ── construction de la requête ──────────────────────────────────────
    def construire_url(self, service, params):
        """L'URL EXACTE d'un appel — la seule façon d'en fabriquer une ici."""
        return (f'{self.racine}/{service}?'
                + urllib.parse.urlencode(params, safe=''))

    # ── l'appel, avec cadence, retentative bornée et refus net ──────────
    def _appeler(self, service, params):
        cle = cle_de_cache(service, params)
        en_cache = self.cache.lire(cle)
        if en_cache is not None:
            self.urls_appelees.append(None)  # repère : servi par le cache
            return en_cache, True

        url = self.construire_url(service, params)
        dernier_motif = ''
        for tentative in range(self.retentatives_529 + 1):
            self.limiteur.attendre_son_tour()
            self.urls_appelees.append(url)
            try:
                statut, corps = self.transport(url, self.timeout_s)
            except (urllib.error.URLError, TimeoutError, OSError) as erreur:
                raise PvgisIndisponible(
                    'PVGIS est injoignable '
                    f'({type(erreur).__name__}) : aucune production n\'est '
                    'publiée — le module ne remplace jamais une mesure '
                    'manquante par une estimation de repli.')
            if statut == 529:
                dernier_motif = 'PVGIS est surchargé (529)'
                if tentative < self.retentatives_529:
                    self._dormir(ATTENTE_529_S * (tentative + 1))
                    continue
                break
            if statut != 200:
                raise PvgisIndisponible(
                    f'PVGIS a refusé la demande (HTTP {statut}) : aucune '
                    'production n\'est publiée.')
            try:
                charge = json.loads(corps)
            except ValueError:
                raise PvgisIndisponible(
                    'La réponse de PVGIS est illisible (JSON invalide) : '
                    'aucune production n\'est publiée.')
            self.cache.poser(cle, charge)
            return charge, False

        raise PvgisIndisponible(
            f'{dernier_motif} après {self.retentatives_529 + 1} tentatives : '
            'aucune production n\'est publiée.')

    # ── la série horaire ────────────────────────────────────────────────
    def serie_horaire(self, *, lat, lon, inclinaison_deg, aspect_deg,
                      politique, puissance_kwc=1.0, annee_debut, annee_fin,
                      base=BASE_PAR_DEFAUT, montage='building'):
        """Série horaire ``seriescalc`` d'un plan, pertes PASSÉES explicitement.

        Args:
            politique: la ``PolitiquePertes`` de CAL238 — OBLIGATOIRE. Sa
                somme est la valeur ``loss`` de la requête, et elle est
                republiée avec le résultat.
            aspect_deg: azimut PVGIS (0 = Sud, −90 = Est, +90 = Ouest). Un
                azimut de FACE se convertit par ``azimut_pvgis()``.

        Returns:
            dict — ``points`` (heure par heure), ``base`` (celle que PVGIS dit
            avoir utilisée), ``fenetre_annees``, ``loss_passee_pct`` et le
            détail des postes, ``url``.

        Raises:
            EntreeInvalide: coordonnées, angles, années ou politique absents.
            PvgisIndisponible: réseau, surcharge, réponse inexploitable.
        """
        params = self._params_communs(
            lat=lat, lon=lon, base=base, politique=politique)
        params.update({
            'startyear': _entier(annee_debut, champ='annee_debut'),
            'endyear': _entier(annee_fin, champ='annee_fin'),
            'pvcalculation': 1,
            'peakpower': _puissance(puissance_kwc),
            'angle': _angle(inclinaison_deg, champ='inclinaison_deg',
                            mini=0.0, maxi=90.0),
            'aspect': _angle(aspect_deg, champ='aspect_deg',
                             mini=-180.0, maxi=180.0),
            'pvtechchoice': 'crystSi',
            'mountingplace': montage,
            'outputformat': 'json',
        })
        if params['endyear'] < params['startyear']:
            raise EntreeInvalide(
                "La fenêtre d'années est à l'envers : « annee_fin » "
                f"({params['endyear']}) précède « annee_debut » "
                f"({params['startyear']}).", champ='annee_fin')

        charge, depuis_cache = self._appeler('seriescalc', params)
        lignes = (((charge or {}).get('outputs') or {}).get('hourly'))
        if not isinstance(lignes, list) or not lignes:
            raise PvgisIndisponible(
                'La réponse de PVGIS ne porte aucune série horaire : aucune '
                'production n\'est publiée.')

        points = []
        for ligne in lignes:
            horodatage = _horodatage(ligne.get('time'))
            if horodatage is None:
                continue
            annee, mois, jour, heure = horodatage
            points.append({
                'annee': annee, 'mois': mois, 'jour': jour, 'heure': heure,
                'p_w': _flottant(ligne.get('P')),
                'gi_w_m2': _flottant(ligne.get('G(i)')),
                't2m_c': _flottant(ligne.get('T2m')),
            })
        if not points:
            raise PvgisIndisponible(
                'La série horaire de PVGIS est inexploitable (aucun '
                'horodatage lisible) : aucune production n\'est publiée.')

        resultat = {
            'service': 'seriescalc',
            'points': points,
            'puissance_kwc': params['peakpower'],
            'url': self.construire_url('seriescalc', params),
            'depuis_cache': depuis_cache,
        }
        resultat.update(_provenance(charge, base, politique))
        return resultat

    # ── l'année météo type (TMY) ────────────────────────────────────────
    def tmy(self, *, lat, lon, base=BASE_PAR_DEFAUT, utiliser_horizon=True):
        """CAL136 — année météo TYPE (``tmy``) en v5_3, base CHOISIE.

        ``apps/ventes/weather_feed.py`` appelle encore ``tmy`` en v5_2 et
        AUCUN appelant du dépôt ne choisit sa base. Ici le choix est explicite
        à chaque appel (vérifié en direct le 20/09/2026 : ``tmy`` honore bien
        ``raddatabase``, la réponse renvoie la base demandée), et la base
        RÉELLEMENT utilisée est republiée avec la fenêtre d'années.

        Pas de ``loss`` ici, et ce n'est pas une entorse à CAL238 : le TMY est
        une série MÉTÉO (irradiance, température), pas un calcul PV — PVGIS
        n'expose aucun paramètre de pertes sur ce service.

        Returns:
            dict — ``base``, ``base_meteo``, ``fenetre_annees``,
            ``mois_retenus`` (l'année retenue pour chaque mois),
            ``temperature_min_c`` / ``temperature_max_c`` (pour le
            dimensionnement des tensions, CAL123) et ``points``.
        """
        if base not in BASES_RAYONNEMENT:
            raise EntreeInvalide(
                f'Base de rayonnement inconnue : « {base} ». Bases admises : '
                f'{", ".join(BASES_RAYONNEMENT)}.', champ='base')
        params = {
            'lat': _coordonnee(lat, champ='lat', maxi=90.0),
            'lon': _coordonnee(lon, champ='lon', maxi=180.0),
            'raddatabase': base,
            'usehorizon': 1 if utiliser_horizon else 0,
            'outputformat': 'json',
        }
        charge, depuis_cache = self._appeler('tmy', params)
        lignes = (((charge or {}).get('outputs') or {}).get('tmy_hourly'))
        if not isinstance(lignes, list) or not lignes:
            raise PvgisIndisponible(
                'La réponse de PVGIS ne porte aucune année météo type : les '
                'températures de dimensionnement ne sont pas publiées.')

        points = []
        temperatures = []
        for ligne in lignes:
            horodatage = _horodatage(ligne.get('time(UTC)')
                                     or ligne.get('time'))
            if horodatage is None:
                continue
            _annee, mois, jour, heure = horodatage
            t2m = _flottant(ligne.get('T2m'))
            if t2m is not None:
                temperatures.append(t2m)
            points.append({
                'mois': mois, 'jour': jour, 'heure': heure, 't2m_c': t2m,
                'gh_w_m2': _flottant(ligne.get('G(h)')),
                'ws10m': _flottant(ligne.get('WS10m')),
            })
        if not points:
            raise PvgisIndisponible(
                "L'année météo type de PVGIS est inexploitable (aucun "
                'horodatage lisible).')

        meteo = (((charge or {}).get('inputs') or {}).get('meteo_data') or {})
        an_min, an_max = meteo.get('year_min'), meteo.get('year_max')
        return {
            'service': 'tmy',
            'points': points,
            'mois_retenus': list(
                ((charge or {}).get('outputs') or {}).get('months_selected')
                or []),
            # Les extrêmes sont ceux de la série REÇUE — sourcés, jamais des
            # températures de catalogue (CAL123 les reprend telles quelles).
            'temperature_min_c': min(temperatures) if temperatures else None,
            'temperature_max_c': max(temperatures) if temperatures else None,
            'base': meteo.get('radiation_db') or base,
            'base_demandee': base,
            'base_meteo': meteo.get('meteo_db'),
            'fenetre_annees': (f'{an_min}-{an_max}'
                               if an_min is not None and an_max is not None
                               else None),
            'url': self.construire_url('tmy', params),
            'depuis_cache': depuis_cache,
        }

    # ── briques communes ────────────────────────────────────────────────
    def _params_communs(self, *, lat, lon, base, politique):
        if base not in BASES_RAYONNEMENT:
            raise EntreeInvalide(
                f'Base de rayonnement inconnue : « {base} ». Bases admises : '
                f'{", ".join(BASES_RAYONNEMENT)} — le choix est explicite, il '
                'n\'y a pas de base « par défaut de PVGIS » dans ce module.',
                champ='base')
        if politique is None or not getattr(politique, 'valeur_loss', ''):
            raise EntreeInvalide(
                'Aucune politique de pertes n\'a été fournie : le module '
                'passe TOUJOURS à PVGIS la somme explicite de ses postes '
                '(CAL238) et n\'appelle pas sans elle.', champ='pertes')
        return {
            'lat': _coordonnee(lat, champ='lat', maxi=90.0),
            'lon': _coordonnee(lon, champ='lon', maxi=180.0),
            'raddatabase': base,
            # CAL238 — la perte part telle qu'elle est publiée, à la virgule
            # près : c'est la MÊME chaîne des deux côtés.
            'loss': politique.valeur_loss,
        }


def _provenance(charge, base_demandee, politique):
    """Ce que PVGIS dit avoir utilisé + la perte réellement passée.

    La base publiée est celle de la RÉPONSE (``meteo_data.radiation_db``),
    pas celle qu'on a demandée : si PVGIS bascule sur ERA5 faute de couverture,
    le chiffre affiché à côté de la production doit le dire.
    """
    meteo = (((charge or {}).get('inputs') or {}).get('meteo_data') or {})
    an_min = meteo.get('year_min')
    an_max = meteo.get('year_max')
    fenetre = (f'{an_min}-{an_max}'
               if an_min is not None and an_max is not None else None)
    publication = politique.publication()
    return {
        'base': meteo.get('radiation_db') or base_demandee,
        'base_demandee': base_demandee,
        'base_meteo': meteo.get('meteo_db'),
        'fenetre_annees': fenetre,
        'loss_passee_pct': publication['loss_passee_pct'],
        'pertes': publication['pertes'],
        'pertes_non_sourcees': publication['postes_non_sources'],
    }


def _horodatage(valeur):
    """``'20200101:0009'`` → ``(2020, 1, 1, 0)``, ou ``None`` si illisible."""
    texte = str(valeur or '')
    if len(texte) < 11 or ':' not in texte:
        return None
    try:
        return (int(texte[0:4]), int(texte[4:6]), int(texte[6:8]),
                int(texte[9:11]))
    except ValueError:
        return None


def _flottant(valeur):
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    if nombre != nombre:
        return None
    return nombre


def _coordonnee(valeur, *, champ, maxi):
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        raise EntreeInvalide(
            f'La coordonnée « {champ} » est illisible (reçu : {valeur!r}) : '
            'sans point GPS, aucune production ne peut être demandée.',
            champ=champ)
    if not -maxi <= nombre <= maxi:
        raise EntreeInvalide(
            f'La coordonnée « {champ} » est hors bornes (reçu : {nombre}).',
            champ=champ)
    return nombre


def _angle(valeur, *, champ, mini, maxi):
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        raise EntreeInvalide(
            f"L'angle « {champ} » est illisible (reçu : {valeur!r}).",
            champ=champ)
    if not mini <= nombre <= maxi:
        raise EntreeInvalide(
            f"L'angle « {champ} » doit être compris entre {mini} et {maxi} "
            f'(reçu : {nombre}).', champ=champ)
    return nombre


def _entier(valeur, *, champ):
    try:
        return int(valeur)
    except (TypeError, ValueError):
        raise EntreeInvalide(
            f'« {champ} » doit être une année (reçu : {valeur!r}).',
            champ=champ)


def _puissance(valeur):
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        raise EntreeInvalide(
            f'La puissance crête est illisible (reçu : {valeur!r}).',
            champ='puissance_kwc')
    if nombre <= 0:
        raise EntreeInvalide(
            'La puissance crête demandée à PVGIS doit être strictement '
            f'positive (reçu : {nombre}).', champ='puissance_kwc')
    return nombre
