"""COP2-V1 — LE résolveur catalogue : un matériel nommé → UN produit, ou un refus.

Une seule implémentation, lue par DEUX appelants :

* la recherche catalogue de l'assistant (``GET ventes/assistant/catalogue/``) ;
* la composition IMPOSÉE du devis automatique (``POST ventes/devis/auto/``
  avec ``nb_panneaux`` / ``onduleur_*`` / ``batterie_*``).

Ce que la recherche rend est donc ce que la composition accepte. Le vivier est
CELUI du compositeur : ``catalogue.catalogue_de_la_societe`` (produits de la
société + globaux, non archivés), réduit aux produits TARIFÉS (``_has_price``),
classés par ``catalogue.classer_produit`` — les mêmes catégories que
``composition_residentielle``. Les fiches techniques et le stock sont lus par
``apps.stock.selectors`` (jamais un modèle de stock).

Règles de rapprochement (lecture du COMPOSITEUR, pas une seconde règle) :

* panneau — wattage lu au NOM (``_parse_watt``), la fiche (``pmax_wc``) à
  défaut ; sans wattage demandé : la puissance du panneau PAR DÉFAUT de la
  société s'il est au vivier (D-ACAL-169, ``domain/panneau_defaut``), sinon
  710 Wc (``taille._AUTO_PANEL_WATT``) ; à la puissance du panneau par défaut,
  CE produit passe devant ; à wattage égal un Canadien Solar passe devant
  (``_choisir_panneau``) ;
* onduleur — puissance lue au NOM (``_parse_kw``, ±0,05 kW), la fiche
  (``ac_kw``) seulement quand le nom n'en porte pas ; phase par
  ``compatibilites.est_triphase_produit`` (fiche d'abord, nom ensuite) ;
  famille : ``hybride`` / ``reseau`` / ``offgrid`` (``classer_produit``) ; un
  site isolé n'accepte QUE l'autonome, un site raccordé jamais l'autonome ;
  micro-onduleurs exclus ;
* batterie — calibre lu au NOM (``_parse_kwh``) ; la banque est N modules
  IDENTIQUES, N = plafond(kWh demandés ÷ calibre) comme ``_candidat``, retenue
  quand le total tombe à ±1 kWh de la demande (tolérance BATHOMO) ; « haute
  tension » exclue sauf demande ; un onduleur connu ne garde que les modules
  de sa fenêtre de tension (``_batterie_compatible``) ; stock 0 exclu de la
  recherche par taille, admis quand l'appelant DÉSIGNE le produit (alerte).

Départage avant ``ambigu`` : la marque épinglée (Paramètres → Gammes, jamais
une autre marque — ``_pick_product``), puis la préférence Dyness du
compositeur pour les batteries. Un ``produit_id`` ou une ``marque`` donnés par
l'appelant passent devant l'épingle, avec une alerte (précédent ACAL63).

Résultat : :class:`Resolution` — ``statut`` ``unique`` / ``ambigu`` /
``aucun``, ``produit``, ``candidats`` (``Entree``), ``raison`` (une phrase
française ; pour ``aucun``, les tailles les plus proches), ``alertes``. Aucun
prix d'achat, aucune marge, aucune quantité en stock n'en sort jamais.
"""
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
import math

GENRE_PANNEAU = 'panneau'
GENRE_ONDULEUR = 'onduleur'
GENRE_BATTERIE = 'batterie'
GENRES = (GENRE_PANNEAU, GENRE_ONDULEUR, GENRE_BATTERIE)

FAMILLE_HYBRIDE = 'hybride'
FAMILLE_RESEAU = 'reseau'
FAMILLE_OFFGRID = 'offgrid'
#: Les familles qu'un appelant peut DEMANDER (le site isolé se lit sur le lead).
FAMILLES_DEMANDABLES = (FAMILLE_HYBRIDE, FAMILLE_RESEAU)

PHASE_MONO = 'monophase'
PHASE_TRI = 'triphase'
PHASES = (PHASE_MONO, PHASE_TRI)

STATUT_UNIQUE = 'unique'
STATUT_AMBIGU = 'ambigu'
STATUT_AUCUN = 'aucun'

#: Tolérance de puissance d'un onduleur (« 10 kW » = 9,95-10,05 kW).
TOLERANCE_KW = 0.05
#: BATHOMO — tolérance de capacité d'une banque (la même que le compositeur).
TOLERANCE_KWH = 1.0

_CATEGORIES_ONDULEUR = {
    'onduleur_hybride': FAMILLE_HYBRIDE,
    'onduleur_reseau': FAMILLE_RESEAU,
    'onduleur_offgrid': FAMILLE_OFFGRID,
}
#: Le rôle Gammes (épingle de marque) de chaque famille d'onduleur.
ROLE_DE_FAMILLE = {
    FAMILLE_HYBRIDE: 'onduleur_hybride',
    FAMILLE_RESEAU: 'onduleur_reseau',
    FAMILLE_OFFGRID: 'onduleur_offgrid',
}
_LIBELLE_FAMILLE = {
    FAMILLE_HYBRIDE: 'hybride',
    FAMILLE_RESEAU: 'réseau',
    FAMILLE_OFFGRID: 'hors réseau',
}


@dataclass
class Entree:
    """Un produit du vivier, lu UNE fois (jamais de prix d'achat)."""

    produit: object
    genre: str
    famille: str = ''
    kw: object = None
    kwh: object = None
    wc: object = None
    phase: str = ''


@dataclass
class Resolution:
    statut: str
    produit: object = None
    candidats: list = field(default_factory=list)
    raison: str = ''
    alertes: list = field(default_factory=list)
    #: Batteries : le nombre de modules de la banque retenue (1 ailleurs).
    nombre: int = 1


# ── Lecture du vivier ────────────────────────────────────────────────────────
def _specs(produit):
    # Même lecture que ``catalogue._tension_nominale_batterie`` : le
    # sélecteur rend ``{}`` / ``None`` sans fiche, il ne lève pas.
    from apps.stock.selectors import specs_for_produit
    return specs_for_produit(produit) or {}


def _nombre(valeur):
    try:
        n = float(valeur)
    except (TypeError, ValueError):
        return None
    if n != n or n <= 0:
        return None
    return n


def _entree(produit, categorie):
    """L'``Entree`` d'un produit tarifé déjà classé, ou ``None``."""
    from apps.ventes.domain.catalogue import (
        _parse_kw, _parse_kwh, _parse_watt, _pas_micro_onduleur)
    nom = getattr(produit, 'nom', '') or ''
    if categorie == 'panneau':
        wc = _parse_watt(nom) or _nombre(_specs(produit).get('pmax_wc'))
        return Entree(produit, GENRE_PANNEAU, wc=wc)
    if categorie in _CATEGORIES_ONDULEUR:
        if not _pas_micro_onduleur(produit):
            return None
        from apps.ventes.compatibilites import est_triphase_produit
        kw = _parse_kw(nom) or _nombre(_specs(produit).get('ac_kw'))
        return Entree(produit, GENRE_ONDULEUR,
                      famille=_CATEGORIES_ONDULEUR[categorie], kw=kw,
                      phase=PHASE_TRI if est_triphase_produit(produit)
                      else PHASE_MONO)
    if categorie == 'batterie':
        return Entree(produit, GENRE_BATTERIE, kwh=_parse_kwh(nom))
    return None


def vivier(company):
    """Toutes les ``Entree`` vendables de la société, dans l'ordre du
    compositeur (id croissant). Lecture seule."""
    from apps.ventes.domain.catalogue import (
        _has_price, catalogue_de_la_societe, classer_produit)
    entrees = []
    for produit in catalogue_de_la_societe(company):
        if not _has_price(produit):
            continue
        entree = _entree(produit, classer_produit(getattr(produit, 'nom', '')))
        if entree is not None:
            entrees.append(entree)
    return entrees


def entree_du_produit(company, produit_id):
    """L'``Entree`` du produit ``produit_id`` dans le vivier, ou ``None``
    (inconnu, d'une autre société, archivé, sans prix ou non classé : le
    refus ne dit jamais lequel)."""
    try:
        cle = int(produit_id)
    except (TypeError, ValueError):
        return None
    return next((e for e in vivier(company)
                 if getattr(e.produit, 'pk', None) == cle), None)


# ── Rendu (recherche + 409 choix) ────────────────────────────────────────────
def _nombre_rendu(valeur):
    """``10`` plutôt que ``10.0`` ; ``None`` reste ``None``."""
    if valeur is None:
        return None
    n = float(valeur)
    return int(n) if n == int(n) else round(n, 3)


def prix_ttc(produit, company):
    """Prix de VENTE TTC unitaire (TVA du produit, sinon taux standard)."""
    taux = getattr(produit, 'tva', None)
    if taux is None:
        from apps.ventes.utils.company_settings import tva_standard
        taux = tva_standard(company)
    ttc = Decimal(str(produit.prix_vente)) * (
        Decimal('1') + Decimal(str(taux)) / Decimal('100'))
    return str(ttc.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def ligne_catalogue(entree, company):
    """Une ligne de ``assistant_catalogue.json`` — jamais d'achat ni de stock
    chiffré (``en_stock`` : batteries seulement, booléen)."""
    from apps.ventes.domain.catalogue import _batterie_en_stock
    produit = entree.produit
    return {
        'produit_id': produit.pk,
        'nom': getattr(produit, 'nom', '') or '',
        'marque': getattr(produit, 'marque', '') or '',
        'genre': entree.genre,
        'kw': _nombre_rendu(entree.kw),
        'kwh': _nombre_rendu(entree.kwh),
        'wc': _nombre_rendu(entree.wc),
        'phase': entree.phase,
        'famille': entree.famille,
        'prix_ttc': prix_ttc(produit, company),
        'en_stock': (_batterie_en_stock(produit)
                     if entree.genre == GENRE_BATTERIE else None),
    }


def choix_409(entrees, company):
    """Les candidats d'un 409 ``choix`` (≤ 10), forme de
    ``assistant_devis_cree.json`` › ``exemple_409_choix``."""
    return [{
        'produit_id': e.produit.pk,
        'nom': getattr(e.produit, 'nom', '') or '',
        'marque': getattr(e.produit, 'marque', '') or '',
        'kw': _nombre_rendu(e.kw),
        'kwh': _nombre_rendu(e.kwh),
        'phase': e.phase,
        'prix_ttc': prix_ttc(e.produit, company),
    } for e in list(entrees)[:10]]


# ── Départages ───────────────────────────────────────────────────────────────
def _sans_accents(texte):
    from apps.ventes.domain.catalogue import _sans_accents as _sa
    return _sa(texte)


def _epingle(company, role, gamme=None):
    # ``marque_preferee`` ne lève JAMAIS (sa docstring) : réglage absent,
    # rôle inconnu ou marque vide ⇒ ``None``.
    from apps.ventes.domain.catalogue import marque_preferee
    return marque_preferee(company, gamme, role)


def _filtrer_marque(entrees, marque):
    from apps.ventes.domain.catalogue import _marque_correspond
    return [e for e in entrees if _marque_correspond(e.produit, marque)]


def _appliquer_marque(entrees, *, company, role, marque=None, gamme=None,
                      alertes=None):
    """``marque`` de l'appelant d'abord ; sinon l'épingle Gammes du rôle
    (jamais une autre marque). Rend ``(entrees, raison_si_vide)``."""
    if marque:
        restantes = _filtrer_marque(entrees, marque)
        if not restantes:
            return [], 'Aucun produit de la marque « %s » ne convient.' % marque
        epingle = _epingle(company, role, gamme)
        if epingle and epingle.casefold() != str(marque).strip().casefold() \
                and alertes is not None:
            alertes.append(
                'Marque « %s » demandée : elle passe devant la marque épinglée '
                '« %s » (Paramètres → Gammes).' % (marque, epingle))
        return restantes, ''
    epingle = _epingle(company, role, gamme)
    if not epingle:
        return entrees, ''
    restantes = _filtrer_marque(entrees, epingle)
    if not restantes and entrees:
        return [], ('La marque épinglée « %s » (Paramètres → Gammes) n\'a aucun '
                    'produit qui convient ; le serveur n\'en choisit jamais une '
                    'autre.' % epingle)
    return restantes, ''


def _tailles_proches(valeurs, cible, unite, n=2):
    distinctes = sorted({float(v) for v in valeurs if v})
    proches = sorted(sorted(distinctes, key=lambda v: abs(v - cible))[:n])
    return ', '.join('%s %s' % (_fmt(v), unite) for v in proches)


def _fmt(valeur):
    texte = ('%.2f' % float(valeur)).rstrip('0').rstrip('.')
    return texte.replace('.', ',')


def _conclure(retenues, *, nom_genre, nombre=1, alertes=None):
    if len(retenues) == 1:
        return Resolution(STATUT_UNIQUE, retenues[0].produit, list(retenues),
                          alertes=list(alertes or []), nombre=nombre)
    noms = ' ou '.join('%s (produit %s)' % (e.produit.nom, e.produit.pk)
                       for e in retenues[:10])
    return Resolution(
        STATUT_AMBIGU, None, list(retenues),
        raison='%d %s conviennent : %s. Précisez le produit.' % (
            len(retenues), nom_genre, noms),
        alertes=list(alertes or []), nombre=nombre)


def _panneau_auto_du_vivier(company, vivier_marque, *, marque=None):
    """D-ACAL-169 — le panneau par défaut de ``company`` s'il est dans le vivier
    du résolveur (tarifé, classé panneau, marque retenue) ; sinon la règle
    d'aujourd'hui — DITE quand rien ne l'explique, muette quand l'appelant a
    lui-même demandé une autre ``marque``."""
    from dataclasses import replace

    from apps.ventes.domain.panneau_defaut import aucun_panneau_auto, panneau_auto
    auto = panneau_auto(company)
    if not auto.designe:
        return auto
    entree = next((e for e in vivier_marque if e.produit.pk == auto.produit_id), None)
    if entree is not None:
        # Contrat du stock : le watt de LA lecture du résolveur (nom, puis fiche), jamais un second.
        return replace(auto, watt=entree.wc or auto.watt)
    if marque:
        return aucun_panneau_auto()
    return auto.refus('le catalogue des devis', "il n'est pas parmi ses panneaux tarifés de la marque retenue")


def _alerte_puissance_non_precisee(auto, cible):
    if auto.designe:
        return ('Puissance du panneau non précisée : %s Wc retenus (panneau par '
                'défaut de la société : « %s »).' % (_fmt(cible), auto.nom))
    return ('Puissance du panneau non précisée : %s Wc retenus '
            '(panneau par défaut du devis automatique).' % _fmt(cible))


# ── Les trois genres ─────────────────────────────────────────────────────────
def resoudre_panneau(company, entrees, *, wc=None, marque=None, gamme=None):
    alertes = []
    panneaux = [e for e in entrees if e.genre == GENRE_PANNEAU]
    vivier_marque, raison = _appliquer_marque(
        panneaux, company=company, role='panneau', marque=marque, gamme=gamme,
        alertes=alertes)
    # D-ACAL-169 — le panneau par défaut, s'il est au vivier (marque comprise) :
    # SA puissance quand rien n'est précisé, et CE produit à cette puissance.
    auto = _panneau_auto_du_vivier(company, vivier_marque, marque=marque)
    cible = float(wc) if wc else float(auto.watt)
    if not wc:
        alertes[:0] = [_alerte_puissance_non_precisee(auto, cible)] + ([auto.motif] if auto.motif else [])
    if raison:
        return Resolution(STATUT_AUCUN, raison=raison, alertes=alertes)
    defaut = [e for e in vivier_marque if auto.prefere(cible) is not None and e.produit.pk == auto.produit_id]
    if defaut:
        return _conclure(defaut, nom_genre='panneaux', alertes=alertes)
    exacts = [e for e in vivier_marque if e.wc and abs(float(e.wc) - cible) < 0.5]
    if not exacts:
        proches = _tailles_proches([e.wc for e in vivier_marque], cible, 'Wc')
        return Resolution(STATUT_AUCUN, raison=(
            'Aucun panneau de %s Wc au catalogue.%s' % (
                _fmt(cible), (' Tailles les plus proches : %s.' % proches)
                if proches else '')), alertes=alertes)
    # Même départage que le compositeur : un Canadien Solar passe devant.
    canadiens = [e for e in exacts
                 if 'canadien' in _sans_accents(getattr(e.produit, 'nom', ''))]
    return _conclure(canadiens or exacts, nom_genre='panneaux',
                     alertes=alertes)


def resoudre_onduleur(company, entrees, *, kw, phase=None, famille=None,
                      marque=None, hors_reseau=False, gamme=None):
    from apps.ventes.domain.catalogue import _filtrer_onduleurs_complets
    alertes = []
    onduleurs = [e for e in entrees if e.genre == GENRE_ONDULEUR]
    if hors_reseau:
        onduleurs = [e for e in onduleurs if e.famille == FAMILLE_OFFGRID]
    else:
        onduleurs = [e for e in onduleurs if e.famille != FAMILLE_OFFGRID]
    if famille and not hors_reseau:
        onduleurs = [e for e in onduleurs if e.famille == famille]
    if phase:
        onduleurs = [e for e in onduleurs if e.phase == phase]
    cible = float(kw)
    a_la_taille = [e for e in onduleurs
                   if e.kw and abs(float(e.kw) - cible) <= TOLERANCE_KW]
    libelle = 'onduleur%s%s' % (
        (' ' + _LIBELLE_FAMILLE[FAMILLE_OFFGRID]) if hors_reseau
        else ((' ' + _LIBELLE_FAMILLE[famille]) if famille else ''),
        (' ' + ('triphasé' if phase == PHASE_TRI else 'monophasé')) if phase else '')
    if not a_la_taille:
        proches = _tailles_proches([e.kw for e in onduleurs], cible, 'kW')
        return Resolution(STATUT_AUCUN, raison=(
            'Aucun %s de %s kW au catalogue.%s' % (
                libelle, _fmt(cible), (' Tailles les plus proches : %s.' % proches)
                if proches else '')), alertes=alertes)
    familles = sorted({e.famille for e in a_la_taille})
    if len(familles) > 1:
        return Resolution(STATUT_AMBIGU, None, a_la_taille, raison=(
            'Onduleurs de %s kW en deux familles (%s) : précisez hybride '
            '(avec batterie) ou réseau. Candidats : %s.' % (
                _fmt(cible), ' et '.join(_LIBELLE_FAMILLE[f] for f in familles),
                ' ou '.join('%s (produit %s)' % (e.produit.nom, e.produit.pk)
                            for e in a_la_taille[:10]))), alertes=alertes)
    role = ROLE_DE_FAMILLE[familles[0]]
    retenues, raison = _appliquer_marque(
        a_la_taille, company=company, role=role, marque=marque, gamme=gamme,
        alertes=alertes)
    if raison:
        return Resolution(STATUT_AUCUN, raison=raison, alertes=alertes)
    # PVOND — le verrou de complétude du compositeur (jamais vidant).
    complets = set(id(p) for p in _filtrer_onduleurs_complets(
        [e.produit for e in retenues]))
    retenues = [e for e in retenues if id(e.produit) in complets] or retenues
    return _conclure(retenues, nom_genre='onduleurs', alertes=alertes)


def _banque(entree, kwh):
    """``n`` modules de ``entree`` pour ``kwh`` (plafond, comme ``_candidat``),
    ou ``None`` hors tolérance / au-delà du plafond de la fiche."""
    from apps.ventes.domain.catalogue import _max_modules_par_banc
    calibre = float(entree.kwh or 0)
    if calibre <= 0:
        return None
    n = max(1, int(math.ceil(float(kwh) / calibre - 1e-9)))
    if abs(n * calibre - float(kwh)) >= TOLERANCE_KWH:
        return None
    plafond = _max_modules_par_banc(entree.produit)
    if plafond is not None and n > plafond:
        return None
    return n


def resoudre_batterie(company, entrees, *, kwh, onduleur=None, marque=None,
                      haute_tension=False, gamme=None):
    from apps.ventes.domain.catalogue import (
        _batterie_compatible, _batterie_en_stock, _plage_batterie_de_l_onduleur)
    alertes = []
    batteries = [e for e in entrees if e.genre == GENRE_BATTERIE]
    if not haute_tension:
        batteries = [e for e in batteries
                     if 'haute tension' not in _sans_accents(
                         getattr(e.produit, 'nom', ''))]
    if onduleur is not None:
        plage = _plage_batterie_de_l_onduleur(onduleur)
        batteries = [e for e in batteries
                     if _batterie_compatible(e.produit, plage)]
    batteries = [e for e in batteries if _batterie_en_stock(e.produit)]
    banques = [(e, _banque(e, kwh)) for e in batteries]
    a_la_taille = [(e, n) for e, n in banques if n]
    if not a_la_taille:
        proches = _tailles_proches([e.kwh for e in batteries], float(kwh), 'kWh')
        compat = (' compatible avec l\'onduleur « %s »' % onduleur.nom
                  if onduleur is not None else '')
        return Resolution(STATUT_AUCUN, raison=(
            'Aucune batterie de %s kWh%s au catalogue.%s' % (
                _fmt(kwh), compat, (' Tailles les plus proches : %s.' % proches)
                if proches else '')), alertes=alertes)
    nombres = {id(e): n for e, n in a_la_taille}
    retenues, raison = _appliquer_marque(
        [e for e, _n in a_la_taille], company=company, role='batterie',
        marque=marque, gamme=gamme, alertes=alertes)
    if raison:
        return Resolution(STATUT_AUCUN, raison=raison, alertes=alertes)
    # Préférence du compositeur (composition_residentielle) : Dyness d'abord.
    dyness = [e for e in retenues
              if any(m in _sans_accents(getattr(e.produit, 'nom', ''))
                     for m in ('dyness', 'deyness'))]
    retenues = dyness or retenues
    resolution = _conclure(retenues, nom_genre='batteries', alertes=alertes)
    if resolution.statut == STATUT_UNIQUE:
        resolution.nombre = nombres[id(retenues[0])]
    return resolution


def resoudre_par_id(company, genre, produit_id, *, entrees=None):
    """Un produit DÉSIGNÉ par l'appelant : présent, tarifé, du bon genre —
    ou ``aucun`` (jamais un remplaçant)."""
    entrees = entrees if entrees is not None else vivier(company)
    try:
        cle = int(produit_id)
    except (TypeError, ValueError):
        cle = None
    entree = next((e for e in entrees
                   if getattr(e.produit, 'pk', None) == cle), None)
    noms = {GENRE_PANNEAU: 'panneau', GENRE_ONDULEUR: 'onduleur',
            GENRE_BATTERIE: 'batterie'}
    if entree is None:
        return Resolution(STATUT_AUCUN, raison=(
            'Produit %s introuvable dans le catalogue vendable de la société '
            '(inconnu, archivé ou sans prix de vente).' % produit_id))
    if entree.genre != genre:
        return Resolution(STATUT_AUCUN, raison=(
            '« %s » (produit %s) n\'est pas un %s.'
            % (entree.produit.nom, cle, noms.get(genre, genre))))
    alertes = []
    if genre == GENRE_BATTERIE:
        from apps.ventes.domain.catalogue import _batterie_en_stock
        if not _batterie_en_stock(entree.produit):
            alertes.append('« %s » est désignée alors que son stock est à 0 : '
                           'vérifiez l\'approvisionnement.' % entree.produit.nom)
    role = (ROLE_DE_FAMILLE.get(entree.famille) if genre == GENRE_ONDULEUR
            else genre)
    epingle = _epingle(company, role)
    if epingle:
        from apps.ventes.domain.catalogue import _marque_correspond
        if not _marque_correspond(entree.produit, epingle):
            alertes.append(
                '« %s » est désigné : il passe devant la marque épinglée « %s » '
                '(Paramètres → Gammes).' % (entree.produit.nom, epingle))
    return Resolution(STATUT_UNIQUE, entree.produit, [entree], alertes=alertes)
