"""AGR121 — l'orchestrateur ventes du pompage solaire : UNE fonction serveur.

:func:`etudier_pompage` est LA seule fonction appelée par l'aperçu
(``POST /ventes/etude-pompage/preview/``), par le rafraîchisseur (AGR123) et
par le devis automatique (AGR124) — D-AGR-1 : un seul calcul serveur sert
l'écran, le PDF, /proposition et le devis automatique.

CE QUE CE MODULE FAIT — ET NE FAIT PAS
--------------------------------------
* Il RÉSOUT chaque entrée avec sa provenance (forme UNIQUE ``{origine,
  detail, date}`` du contrat ``etude_pompage_preview.json``, AGR2), par
  priorité : corps > devis > lead > réglage société. Le lead est lu par
  ``crm.selectors.entrees_pompage_du_lead`` (AGR404) ; les mesures de visite
  sans colonne Lead (niveau dynamique, refoulement, conduite…) par
  ``visites.selectors.mesures_point_eau_pour_lead`` (AGR413).
* Il LIT le catalogue (``stock.selectors.produits_pompage``, AGR103), les
  profils PVGIS (``apps.parametres.pvgis_profils``) et les températures TMY
  (façade ``apps.calepinage.services``, jamais ses modèles).
* Il APPELLE le noyau pur ``core.pompage`` (HMT, besoin, conception, pompe,
  variateur, champ, kit, tailles) — aucun calcul de pompage n'est recodé ici.
* Il rend EXACTEMENT la forme du contrat. Il n'ÉCRIT RIEN : aucun statut,
  aucune ligne, aucune version, aucune colonne de lead (D-AGR-1).

ZÉRO CHIFFRE INVENTÉ : une donnée absente fait tomber le bloc concerné à
``None`` et le NOMME (alerte ou motif). JAMAIS ``prix_achat`` ni marge, à
aucun niveau (garde récursive :func:`_sans_cles_interdites`).

Appelants de :func:`etudier_pompage` (``git grep -n etudier_pompage``) :
``apps/ventes/etude_pompage_view.py`` (aperçu, AGR121) et
:func:`rafraichir_etude_pompage_devis` (AGR123, cinquième étude de
``etudes.rafraichir_etudes_du_devis``). AGR124 s'y branchera.
"""
from __future__ import annotations

import re
import contextlib
import contextvars
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

#: Clés JAMAIS rendues, à aucun niveau (règle CLAUDE.md, contrat ``interdit``).
CLES_INTERDITES = ('prix_achat', 'marge')

#: Chemins d'entrée résolus (chemin du corps → clé de ``entrees_resolues``).
#: Les objets ``plaque`` et ``localisation`` sont résolus comme UN bloc.
CHEMINS = (
    ('mode_pompe', 'mode_pompe'),
    ('besoin.mode', 'besoin_mode'),
    ('besoin.volume_m3_jour', 'volume_m3_jour'),
    ('besoin.debit_souhaite_m3h', 'debit_souhaite_m3h'),
    ('besoin.mois_pointe', 'mois_pointe'),
    ('besoin.debit_actuel_m3h', 'debit_actuel_m3h'),
    ('besoin.heures_actuelles_jour', 'heures_actuelles_jour'),
    ('besoin.cultures', 'cultures'),
    ('besoin.region', 'region'),
    ('besoin.mois_irrigation', 'mois_irrigation'),
    ('source.debit_exploitation_m3h', 'debit_exploitation_m3h'),
    ('source.debit_autorise_m3h', 'debit_autorise_m3h'),
    ('source.volume_annuel_autorise_m3', 'volume_annuel_autorise_m3'),
    ('source.compteur', 'compteur'),
    ('source.niveau_statique_m', 'niveau_statique_m'),
    ('source.niveau_dynamique_m', 'niveau_dynamique_m'),
    ('source.rabattement_m', 'rabattement_m'),
    ('source.profondeur_forage_m', 'profondeur_forage_m'),
    ('source.diametre_tubage_mm', 'diametre_tubage_mm'),
    ('source.profondeur_calage_m', 'profondeur_calage_m'),
    ('source.volume_reservoir_m3', 'volume_reservoir_m3'),
    ('hmt.saisie_m', 'hmt_saisie_m'),
    ('hmt.denivele_m', 'denivele_m'),
    ('hmt.conduite.materiau', 'conduite_materiau'),
    ('hmt.conduite.diametre_interieur_mm', 'conduite_diametre_interieur_mm'),
    ('hmt.conduite.longueur_m', 'conduite_longueur_m'),
    ('hmt.conduite.c_hazen_williams', 'conduite_c_hazen_williams'),
    ('hmt.pertes_singulieres_m', 'pertes_singulieres_m'),
    ('hmt.pression_service_bar', 'pression_service_bar'),
    ('alim', 'alim'),
    ('type_pompe', 'type_pompe'),
    ('distance_champ_m', 'distance_champ_m'),
    ('options_cochees', 'options_cochees'),
    ('taille', 'taille'),
)

#: Blocs résolus d'un seul tenant (objet du corps → clé de sortie).
BLOCS = (('plaque', ('kw', 'tension_v', 'phases', 'cv', 'courant_a')),
         ('localisation', ('ville', 'lat', 'lon')))

#: Mesures du relevé du point d'eau SANS colonne Lead (AGR413) → chemin.
MESURES_VISITE = (
    ('point_eau', 'niveau_dynamique_m', 'source.niveau_dynamique_m'),
    ('point_eau', 'diametre_tubage_mm', 'source.diametre_tubage_mm'),
    ('point_eau', 'hauteur_refoulement_m', 'hmt.denivele_m'),
    ('point_eau', 'longueur_conduite_m', 'hmt.conduite.longueur_m'),
    ('point_eau', 'diametre_conduite_mm',
     'hmt.conduite.diametre_interieur_mm'),
    ('point_eau', 'bassin_volume_m3', 'source.volume_reservoir_m3'),
    ('pompe_existante', 'tension_v', 'plaque.tension_v'),
)

#: Clé d'étude v2 (``Devis.etude_params``) → préfixe de chemin du corps
#: (contrat ``cles_etude_params_v2.correspondance_corps``).
CLES_DEVIS = (('mode_pompe', 'mode_pompe'), ('plaque', 'plaque'),
              ('besoin', 'besoin'), ('source', 'source'),
              ('hmt_entrees', 'hmt'), ('alim', 'alim'),
              ('type_pompe', 'type_pompe'), ('localisation', 'localisation'),
              ('distance_champ_m', 'distance_champ_m'),
              ('options_cochees', 'options_cochees'), ('taille', 'taille'))

TAILLES_VALIDES = ('recommandee', 'inferieure', 'superieure')


# ── petits outils ────────────────────────────────────────────────────────────

def _vide(valeur):
    return valeur is None or valeur == '' or valeur == [] or valeur == {}


def _num(valeur):
    """Flottant ou ``None`` (jamais un 0 fabriqué)."""
    if valeur is None or valeur == '' or isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _json(valeur):
    """Decimal → nombre JSON, récursivement."""
    if isinstance(valeur, Decimal):
        return int(valeur) if valeur == valeur.to_integral_value() \
            else float(valeur)
    if isinstance(valeur, dict):
        return {k: _json(v) for k, v in valeur.items()}
    if isinstance(valeur, (list, tuple)):
        return [_json(v) for v in valeur]
    return valeur


def _sans_cles_interdites(obj):
    """Copie de ``obj`` sans aucune clé ``prix_achat``/``marge`` (récursif)."""
    if isinstance(obj, dict):
        return {k: _sans_cles_interdites(v) for k, v in obj.items()
                if k not in CLES_INTERDITES}
    if isinstance(obj, list):
        return [_sans_cles_interdites(v) for v in obj]
    return obj


def _lire_chemin(arbre, chemin):
    noeud = arbre
    for morceau in chemin.split('.'):
        if not isinstance(noeud, dict) or morceau not in noeud:
            return None
        noeud = noeud[morceau]
    return noeud


def _provenance(origine, detail=None, date=None):
    return {'origine': origine, 'detail': detail, 'date': date}


def _aujourdhui():
    from django.utils import timezone
    return timezone.localdate().isoformat()


def _date_iso(moment):
    if moment is None:
        return None
    if hasattr(moment, 'date') and callable(moment.date):
        moment = moment.date()
    return moment.isoformat()


# ── 1. RÉSOLUTION DES ENTRÉES (corps > devis > lead > réglage société) ───────

class _Resolution:
    """Accumule ``chemin → (valeur, provenance)`` ; une couche posée PLUS
    TARD (priorité plus haute) remplace la précédente."""

    def __init__(self):
        self.valeurs = {}

    def poser(self, chemin, valeur, provenance):
        if _vide(valeur):
            return
        self.valeurs[chemin] = (valeur, provenance)

    def poser_arbre(self, arbre, provenance):
        """Pose toutes les feuilles CONNUES d'un objet de corps/devis."""
        if not isinstance(arbre, dict):
            return
        for chemin, _cle in CHEMINS:
            self.poser(chemin, _lire_chemin(arbre, chemin), provenance)
        for bloc, champs in BLOCS:
            objet = arbre.get(bloc)
            if isinstance(objet, dict):
                for champ in champs:
                    self.poser('%s.%s' % (bloc, champ), objet.get(champ),
                               provenance)

    def valeur(self, chemin):
        entree = self.valeurs.get(chemin)
        return entree[0] if entree else None

    def provenance(self, chemin):
        entree = self.valeurs.get(chemin)
        return entree[1] if entree else None

    def bloc(self, nom):
        """``(objet, provenance)`` d'un bloc ; provenance = celle de la
        couche la plus prioritaire qui y a contribué."""
        champs = dict(BLOCS)[nom]
        objet, provenance = {}, None
        for champ in champs:
            entree = self.valeurs.get('%s.%s' % (nom, champ))
            objet[champ] = entree[0] if entree else None
            if entree:
                provenance = entree[1]
        if all(v is None for v in objet.values()):
            return None, None
        return objet, provenance

    def entrees_resolues(self):
        sortie = {}
        for chemin, cle in CHEMINS:
            if chemin in self.valeurs:
                valeur, provenance = self.valeurs[chemin]
                sortie[cle] = {'valeur': _json(valeur),
                               'provenance': provenance}
        for nom, _champs in BLOCS:
            objet, provenance = self.bloc(nom)
            if objet is not None:
                sortie[nom] = {'valeur': _json(objet),
                               'provenance': provenance}
        return sortie


def _profil_societe(company):
    from apps.parametres.models import CompanyProfile
    if company is None:
        return None
    return CompanyProfile.objects.filter(company=company).first()


def _couche_reglage(profil):
    """Réglages société AGR107 : jamais des saisies, toujours nommés."""
    reglages = {}
    if profil is None:
        return reglages
    date = _date_iso(getattr(profil, 'updated_at', None))
    for champ in ('agricole_pump_hours', 'agricole_part_debit_forage_pct',
                  'agricole_marge_cable_descente_m',
                  'agricole_salissure_supp_pct'):
        valeur = _num(getattr(profil, champ, None))
        if valeur is not None:
            reglages[champ] = (valeur, _provenance('reglage_societe', champ,
                                                   date))
    return reglages


def _couche_lead(res, lead):
    """AGR404 — UNE lecture lead (valeur + provenance, aucun défaut)."""
    if lead is None:
        return
    from apps.crm.selectors import entrees_pompage_du_lead, ville_effective

    lecture = entrees_pompage_du_lead(lead) or {}
    cultures = {}
    prov_cultures = None
    for entree in lecture.get('entrees') or ():
        chemin = entree.get('chemin') or ''
        prov = _provenance('lead', entree.get('provenance'),
                           entree.get('date'))
        valeur = entree.get('valeur')
        if chemin.startswith('saisies_economie_pompage.mois_irrigation'):
            res.poser('besoin.mois_irrigation', valeur, prov)
            continue
        if chemin.startswith('saisies_economie_pompage'):
            continue  # économie : contrat AGR3, hors dimensionnement
        if chemin.startswith('besoin.cultures[0].'):
            cle = chemin.rsplit('.', 1)[-1]
            cultures[cle] = valeur
            prov_cultures = prov
            continue
        if chemin == 'hmt_entrees.saisie_m':
            chemin = 'hmt.saisie_m'
        if entree.get('information') and chemin == 'type_pompe':
            # Type de la pompe ACTUELLE : seulement pour une pompe conservée.
            res.poser('_type_pompe_actuelle', valeur, prov)
            continue
        res.poser(chemin, valeur, prov)
    if cultures:
        res.poser('besoin.cultures', [cultures], prov_cultures)

    lat = getattr(lead, 'gps_lat', None)
    lon = getattr(lead, 'gps_lng', None)
    ville = ville_effective(lead) or None
    date = _date_iso(getattr(lead, 'date_creation', None))
    prov = _provenance('lead', 'client', date)
    res.poser('localisation.ville', ville, prov)
    if lat is not None and lon is not None:
        res.poser('localisation.lat', _num(lat), prov)
        res.poser('localisation.lon', _num(lon), prov)


def _visite_point_eau(lead):
    """La dernière visite « relevé du point d'eau » VALIDÉE du lead, par la
    façade de lecture de ``visites`` (jamais ses modèles)."""
    if lead is None:
        return None
    from apps.visites.selectors import visite_point_eau_validee_du_lead
    return visite_point_eau_validee_du_lead(lead)


def _couche_visite(res, lead):
    """AGR413 — mesures du point d'eau sans colonne Lead (la mesure
    remplace la déclaration)."""
    visite = _visite_point_eau(lead)
    if visite is None:
        return
    from apps.visites.selectors import mesures_point_eau_pour_lead

    mesures = mesures_point_eau_pour_lead(visite) or {}
    date = _date_iso(getattr(visite, 'date_realisee', None)
                     or getattr(visite, 'date_prevue', None))
    prov = _provenance('lead', 'mesure_visite', date)
    for categorie, code, chemin in MESURES_VISITE:
        bloc = mesures.get(categorie)
        if isinstance(bloc, dict):
            res.poser(chemin, _json(bloc.get(code)), prov)


def _couche_devis(res, devis):
    if devis is None:
        return
    etude = getattr(devis, 'etude_params', None)
    if not isinstance(etude, dict):
        return
    date = _date_iso(getattr(devis, 'updated_at', None))
    prov = _provenance('saisie', 'devis', date)
    arbre = {}
    for cle_etude, cle_corps in CLES_DEVIS:
        if cle_etude in etude:
            arbre[cle_corps] = etude[cle_etude]
    res.poser_arbre(arbre, prov)
    mois = _lire_chemin(etude, 'saisies_economie_pompage.mois_irrigation.mois')
    res.poser('besoin.mois_irrigation', mois, prov)


def _couche_corps(res, corps):
    if not isinstance(corps, dict):
        return
    res.poser_arbre(corps, _provenance('saisie', None, _aujourdhui()))


def resoudre_entrees(company, entrees, *, devis=None, lead=None):
    """``(_Resolution, reglages)`` — priorité corps > devis > lead (+ mesures
    de visite) > réglage société. Lecture seule."""
    res = _Resolution()
    reglages = _couche_reglage(_profil_societe(company))
    _couche_lead(res, lead)
    _couche_visite(res, lead)
    _couche_devis(res, devis)
    _couche_corps(res, entrees)
    return res, reglages


# ── 2. LECTURES : catalogue, PVGIS, températures ─────────────────────────────

def _specs_module(produit):
    from apps.stock.selectors import specs_for_produit
    try:
        specs = specs_for_produit(produit) or {}
    except Exception:  # fiche illisible : le panneau reste sans spécifs
        logger.warning("pompage._specs_module : erreur ignorée (mode dégradé)", exc_info=True)
        specs = {}
    return {c: _num(specs.get(c)) for c in (
        'vmp_v', 'voc_v', 'isc_a', 'imp_a', 'pmax_wc',
        'temp_coeff_voc_pct_c', 'temp_coeff_pmax_pct_c')}


def _dict_catalogue(produit, **extra):
    """Dict SIMPLE d'un produit catalogue (aucune clé d'achat ni de marge)."""
    d = {'id': produit.id, 'nom': produit.nom, 'sku': produit.sku or '',
         'prix_connu': bool(produit.prix_vente and produit.prix_vente > 0)}
    d.update(extra)
    return d


def _bareme_produit(produit):
    """Barème ``prix_fixe_ht`` / ``prix_par_panneau_ht`` lu sur le produit
    (jamais supposé)."""
    return {'prix_fixe_ht': _num(getattr(produit, 'prix_fixe_ht', None)),
            'prix_par_panneau_ht': _num(getattr(produit, 'prix_par_panneau_ht',
                                                None))}


def _premier_chiffrable(produits):
    """AGQ5 — le premier produit PRICÉ ou à BARÈME saisi (plus petit id)."""
    from core.pompage.kit import bareme_saisi

    for produit in sorted(produits, key=lambda p: p.id):
        if (produit.prix_vente and produit.prix_vente > 0) or bareme_saisi(
                _bareme_produit(produit)):
            return produit
    return None


def lire_catalogue(company):
    """Le catalogue pompage (AGR103) + panneau, structure, installations,
    socle et transport du catalogue de la société. Lecture seule, bornée
    société. AGQ5 — l'installation de repli et le socle sont trouvés par RÔLE
    (``role_devis`` sinon ``classer_produit``), jamais par un SKU codé."""
    from apps.stock.selectors import produits_pompage

    from .catalogue import catalogue_de_la_societe, classer_produit

    pompage = [_json(p) for p in produits_pompage(company)]
    ids_pompage = {e.get('id') for e in pompage if e.get('role_pompage')}
    par_id = {}
    panneaux, transports, installations, socles = [], [], [], []
    for produit in catalogue_de_la_societe(company):
        par_id[produit.id] = produit
        role = getattr(produit, 'role_devis', None) or classer_produit(
            produit.nom)
        if role == 'panneau':
            panneaux.append(produit)
        elif role == 'transport':
            transports.append(produit)
        elif role == 'installation' and produit.id not in ids_pompage:
            installations.append(produit)
        elif role == 'socle':
            socles.append(produit)

    # Barème des prestations (INST-PMP) : lu sur le produit, jamais supposé.
    for element in pompage:
        produit = par_id.get(element.get('id'))
        if produit is not None and element.get('role_pompage') in (
                'installation_pompage',):
            element['prix_fixe_ht'] = _num(getattr(produit, 'prix_fixe_ht',
                                                   None))
            element['prix_par_panneau_ht'] = _num(
                getattr(produit, 'prix_par_panneau_ht', None))

    panneau = None
    candidats = []
    for produit in panneaux:
        specs = _specs_module(produit)
        complet = all(specs[c] and specs[c] > 0 for c in (
            'vmp_v', 'voc_v', 'isc_a', 'imp_a', 'pmax_wc'))
        prix = bool(produit.prix_vente and produit.prix_vente > 0)
        candidats.append(((prix, complet, specs['pmax_wc'] or 0,
                           -produit.id), produit, specs))
    if candidats:
        _cle, produit, specs = max(candidats, key=lambda c: c[0])
        panneau = _dict_catalogue(produit, **specs)

    transport = None
    pricees = [p for p in transports if p.prix_vente and p.prix_vente > 0]
    if pricees:
        transport = _dict_catalogue(pricees[0])
    inst = _premier_chiffrable(installations)
    installation_toiture = (_dict_catalogue(inst, **_bareme_produit(inst))
                            if inst is not None else None)
    socle = _premier_chiffrable(socles)
    return {'pompage': pompage, 'panneau': panneau, 'transport': transport,
            'installation_toiture': installation_toiture,
            'socle': (_dict_catalogue(socle) if socle is not None else None)}


def _par_role(produits, role):
    from core.pompage.kit import _par_role as par_role
    return par_role(produits, role)


def profils_horaires_site(*, ville=None, lat=None, lon=None):
    """12 journées types (24 valeurs d'irradiance W/m², heure locale) du site,
    depuis PVGIS (forme de la saison × productible du mois), ou ``None``.

    PVGIS est déjà net de 14 % de pertes : AUCUN derate ici (table AGR110
    ``pertes_pvgis_comprises_pct``). Toute indisponibilité ⇒ ``None`` (repli
    étiqueté par le noyau), jamais une erreur."""
    from apps.parametres.pvgis_profils import productible_mensuel
    from core.pompage.volumes import JOURS_PAR_MOIS

    from ..etude_horaire import _formes_production_par_saison, saison_du_mois

    try:
        formes, _source = _formes_production_par_saison(
            ville=ville, lat=lat, lon=lon)
        mensuel = productible_mensuel(ville=ville, lat=lat, lon=lon)
    except Exception:  # réseau PVGIS : on retombe sur le repli étiqueté
        logger.warning('AGR121 — PVGIS indisponible', exc_info=True)
        return None
    if not formes or not mensuel:
        return None
    productibles, _src = mensuel
    profils = []
    for index in range(12):
        forme = formes.get(saison_du_mois(index + 1))
        e_m = _num(productibles[index]) if index < len(productibles) else None
        if not forme or e_m is None or e_m <= 0:
            return None
        jour_kwh_kwc = e_m / JOURS_PAR_MOIS[index]
        profils.append([round(part * jour_kwh_kwc * 1000.0, 2)
                        for part in forme])
    return profils


def temperatures_du_site(lat, lon, *, sans_tmy=False):
    """Températures TMY du site par la façade ``calepinage.services``
    (``{froid_c, chaud_c, source}``), ou ``None`` (replis MENTIONNÉS du
    noyau électrique).

    AGQ24 (C-AGQ-023) — ``sans_tmy`` : le chemin du devis automatique ne
    paie jamais l'appel TMY (replis MENTIONNÉS du noyau électrique)."""
    if sans_tmy or lat is None or lon is None:
        return None
    from apps.calepinage import services as calepinage_services
    try:
        temperatures = calepinage_services.temperatures_site(
            pin={'lat': lat, 'lng': lon})
    except Exception:
        logger.warning('AGR121 — températures TMY indisponibles',
                       exc_info=True)
        return None
    if temperatures is None or not getattr(temperatures, 'source', None):
        return None
    return {'froid_c': temperatures.froid_c, 'chaud_c': temperatures.chaud_c,
            'source': temperatures.source}


# ── 3. FORMES DE SORTIE (contrat) ────────────────────────────────────────────

def _alerte(code, champ, message):
    return {'code': code, 'champ': champ, 'message': message}


def _alertes_uniques(*listes):
    vues, sortie = set(), []
    for liste in listes:
        for a in liste or ():
            cle = (a.get('code'), a.get('champ'), a.get('message'))
            if cle in vues:
                continue
            vues.add(cle)
            sortie.append({'code': a.get('code'), 'champ': a.get('champ'),
                           'message': a.get('message')})
    return sortie


def _hypotheses_uniques(*listes):
    vues, sortie = set(), []
    for liste in listes:
        for h in liste or ():
            if h.get('cle') in vues:
                continue
            vues.add(h.get('cle'))
            sortie.append(h)
    return sortie


def _forme_production(production):
    if not production or production.get('m3_jour_mois') is None:
        return None
    return {
        'm3_jour_mois': production.get('m3_jour_mois'),
        'heures_equivalentes_mois': production.get('heures_equivalentes_mois'),
        'source_irradiation': production.get('source_irradiation'),
        'mode': production.get('mode'),
        'coordonnees_figees': (production.get('coordonnees_figees')
                               if production.get('source_irradiation')
                               == 'pvgis' else None),
        # AGQ40 (D-AGQ-9) — plafond horaire appliqué (forage × part du
        # réglage), ``None`` sans débit de forage.
        'plafond_forage_m3h': production.get('plafond_forage_m3h'),
        # AGM8 (AMOT65, moitié domaine) — les étiquettes d'honnêteté du noyau
        # (« estimation », « rendement non publié »…) : INTERNES, le rendu ne
        # lit que leur présence.
        'etiquettes': list(production.get('etiquettes') or []),
    }


def _fr_m3h(valeur):
    texte = ('%.1f' % float(valeur)).rstrip('0').rstrip('.')
    return texte.replace('.', ',')


def _cv_plaque_ou_derive(produit, kw):
    """AGQ29 (C-AGQ-027) — le CV de PLAQUE du produit (``pompe_cv``, « 10 »
    pour l'OSP 30/8) ; dérivé kW ÷ ``cv_vers_kw`` SEULEMENT sans plaque."""
    from core.pompage.hypotheses import valeur

    plaque = _num((produit or {}).get('pompe_cv'))
    if plaque is not None and plaque > 0:
        return plaque
    return kw / valeur('cv_vers_kw') if kw else None


def _forme_champ(champ, motif_vide):
    vide_chaines = {'serie': None, 'paralleles': None, 'voc_froid_v': None,
                    'vmp_chaud_v': None, 'verifiable': False,
                    'motif': motif_vide}
    if not champ:
        return {'kwc': None, 'nb_panneaux': None, 'ratio': None,
                'chaines': vide_chaines}
    chaines = champ.get('chaines') or {}
    forme = {c: chaines.get(c)
             for c in ('serie', 'paralleles', 'voc_froid_v', 'vmp_chaud_v')}
    forme['verifiable'] = bool(chaines.get('verifiable'))
    forme['motif'] = chaines.get('motif')
    if not forme['verifiable'] and not forme['motif']:
        forme['motif'] = motif_vide or 'chaîne PV non vérifiable'
    return {'kwc': champ.get('kwc'), 'nb_panneaux': champ.get('nb_panneaux'),
            'ratio': champ.get('ratio'), 'chaines': forme}


def _forme_variateur(produit, motif_absent):
    from core.pompage.champ import (
        fiche_saisie, phases_sortie_variateur, tension_sortie_variateur,
    )
    from core.pompage.selection import prix_connu

    if not produit:
        return {'produit': None, 'nom': None, 'kw': None, 'tension_v': None,
                'phases_sortie': None, 'fiche_saisie': False,
                'prix_connu': False, 'motif': motif_absent}
    saisie = fiche_saisie(produit)
    return {
        'produit': produit.get('id'), 'nom': produit.get('nom'),
        'kw': _num(produit.get('pompe_kw')),
        'tension_v': tension_sortie_variateur(produit),
        'phases_sortie': phases_sortie_variateur(produit),
        'fiche_saisie': saisie, 'prix_connu': prix_connu(produit),
        'motif': (None if saisie else
                  'fiche variateur à saisir : tension et phases de sortie '
                  'non vérifiées sur la fiche'),
    }


def _forme_taille(taille, retenue):
    return {
        'cle': taille.get('cle'), 'pompe_produit': taille.get('pompe_produit'),
        'pompe_nom': taille.get('pompe_nom'),
        'puissance_kw': taille.get('puissance_kw'),
        'champ_kwc': taille.get('champ_kwc'),
        'nb_panneaux': taille.get('nb_panneaux'),
        'couverture_mois_critique_pct': taille.get(
            'couverture_mois_critique_pct'),
        'total_ttc': taille.get('total_ttc'),
        'prix_connu': taille.get('prix_connu'),
        'retenue': retenue, 'motif': taille.get('motif'),
    }


def _forme_kit(kit):
    if not kit:
        from core.pompage.kit import NON_INCLUS
        return {'inclus': [], 'options': [], 'non_inclus': list(NON_INCLUS)}
    return {'inclus': kit.get('inclus') or [],
            'options': kit.get('options') or [],
            'non_inclus': kit.get('non_inclus') or []}


# ── 4. L'ORCHESTRATEUR ───────────────────────────────────────────────────────

def _heures_pic_mois(profils, heures_repli):
    """AGQ1 — ``(heures-pic des 12 mois, source)`` : profil PVGIS (passe 1),
    sinon heures du réglage société (``repli``), sinon ``(None, None)``."""
    from core.pompage.conception import heures_pic

    if profils and len(profils) == 12:
        heures = [heures_pic(p) for p in profils]
        if all(heures):
            return heures, 'pvgis'
    repli = _num(heures_repli)
    if repli is not None and repli > 0:
        return [repli] * 12, 'repli'
    return None, None


def _besoin(res, *, profils=None, heures_repli=None):
    """``(besoin_retenu, besoin_agronomique, alertes)`` — D-AGR-3 ; AGQ1
    (D-AGQ-1) : sans volume ni pompe actuelle, le débit souhaité × heures-pic
    du mois fait le besoin."""
    from core.pompage.agronomie import besoin_agronomique
    from core.pompage.conception import (
        alerte_heures_superieures_24, besoin_retenu,
    )

    mode = res.valeur('besoin.mode')
    cultures = res.valeur('besoin.cultures') or []
    region = res.valeur('besoin.region')
    agro = None
    alertes = []
    if cultures and mode in (None, 'agronomique'):
        parcelles = [{'culture': c.get('crop'), 'surface_ha': c.get(
            'surface_ha'), 'methode': c.get('irrigation')}
            for c in cultures if isinstance(c, dict)]
        agro = besoin_agronomique(parcelles, region=region)
        alertes.extend(agro.get('alertes') or [])
    volume = res.valeur('besoin.volume_m3_jour') \
        if mode in (None, 'volume_declare') else None
    debit_actuel = res.valeur('besoin.debit_actuel_m3h') \
        if mode in (None, 'pompe_actuelle') else None
    heures = res.valeur('besoin.heures_actuelles_jour') \
        if mode in (None, 'pompe_actuelle') else None
    souhaite = (_num(res.valeur('besoin.debit_souhaite_m3h'))
                if mode in (None, 'debit_souhaite') else None)
    # AGM5 — plus de 24 h/jour : alerte qui nomme le champ, besoin inchangé.
    alerte_24 = alerte_heures_superieures_24(heures)
    if alerte_24:
        alertes.append(alerte_24)
    heures_pic, source_heures = _heures_pic_mois(profils, heures_repli)
    if volume is not None:
        prov = res.provenance('besoin.volume_m3_jour')
    elif debit_actuel is not None and heures is not None:
        prov = res.provenance('besoin.debit_actuel_m3h')
    elif souhaite is not None:
        prov = res.provenance('besoin.debit_souhaite_m3h')
    else:
        prov = res.provenance('besoin.debit_actuel_m3h')
    besoin = besoin_retenu(
        volume_declare_m3_jour=volume,
        mois_irrigation=res.valeur('besoin.mois_irrigation'),
        debit_actuel_m3h=debit_actuel, heures_actuelles=heures,
        besoin_agronomique=agro if mode in (None, 'agronomique') else None,
        provenance_declaree=prov, debit_souhaite_m3h=souhaite,
        heures_pic_mois=heures_pic, source_heures_pic=source_heures)
    return besoin, agro, alertes


def _hmt(res, debit_m3h):
    from core.pompage.hydraulique import hmt_composantes

    statique = _num(res.valeur('source.niveau_statique_m'))
    dynamique = _num(res.valeur('source.niveau_dynamique_m'))
    rabattement = _num(res.valeur('source.rabattement_m'))
    provenances = {}
    if dynamique is None and statique is not None and rabattement is not None:
        dynamique = statique + rabattement
        provenances['niveau_dynamique_m'] = _provenance(
            'calculee', 'niveau statique + rabattement', None)
    for chemin, cle in (('source.niveau_dynamique_m', 'niveau_dynamique_m'),
                        ('hmt.denivele_m', 'denivele_m'),
                        ('hmt.pertes_singulieres_m', 'pertes_singulieres_m')):
        if res.provenance(chemin) and cle not in provenances:
            provenances[cle] = res.provenance(chemin)
    return hmt_composantes(
        hmt_saisie=_num(res.valeur('hmt.saisie_m')), debit_m3h=debit_m3h,
        niveau_dynamique_m=dynamique, niveau_statique_m=statique,
        denivele_m=_num(res.valeur('hmt.denivele_m')),
        longueur_conduite_m=_num(res.valeur('hmt.conduite.longueur_m')),
        diametre_interieur_mm=_num(res.valeur(
            'hmt.conduite.diametre_interieur_mm')),
        materiau_conduite=res.valeur('hmt.conduite.materiau'),
        c_hazen_williams=_num(res.valeur('hmt.conduite.c_hazen_williams')),
        pertes_singulieres_m=_num(res.valeur('hmt.pertes_singulieres_m')),
        pression_service_bar=_num(res.valeur('hmt.pression_service_bar')),
        provenances=provenances)


def _conception(res, besoin, reglages, *, profils, hmt_m, production=None,
                plaque_kw=None):
    from core.pompage.conception import conception

    niveau = res.valeur('source.niveau_dynamique_m') \
        or res.valeur('source.niveau_statique_m')
    exploitation = 'source.debit_exploitation_m3h'
    return conception(
        besoin=besoin, profils_horaires=profils,
        agricole_pump_hours=_reglage(reglages, 'agricole_pump_hours'),
        debit_exploitation_m3h=_num(res.valeur(exploitation)),
        provenance_exploitation=res.provenance(exploitation),
        part_reglage_pct=_reglage(reglages,
                                  'agricole_part_debit_forage_pct'),
        debit_autorise_m3h=_num(res.valeur('source.debit_autorise_m3h')),
        volume_autorise_m3_an=_num(res.valeur(
            'source.volume_annuel_autorise_m3')),
        production_m3_jour_mois=production, niveau_eau_m=_num(niveau),
        hmt_m=hmt_m, debit_actuel_m3h=_num(res.valeur(
            'besoin.debit_actuel_m3h')),
        pompe_actuelle_kw=plaque_kw,
        volume_reservoir_m3=_num(res.valeur('source.volume_reservoir_m3')))


def _reglage(reglages, cle):
    entree = reglages.get(cle)
    return entree[0] if entree else None


def _parametres_kit(res, reglages, catalogue, produits):
    """Paramètres de ``core.pompage.kit.composer_kit`` lus une fois (AGQ5 :
    socle et installation de repli viennent du catalogue par rôle)."""
    return dict(
        structure=_par_role(produits, 'structure_sol'),
        installation_pompage=_par_role(produits, 'installation_pompage'),
        installation_toiture=catalogue['installation_toiture'],
        socle=catalogue.get('socle'),
        transport=catalogue['transport'], produits_options=produits,
        distance_champ_m=_num(res.valeur('distance_champ_m')),
        profondeur_calage_m=_num(res.valeur('source.profondeur_calage_m')),
        marge_cable_m=_reglage(reglages, 'agricole_marge_cable_descente_m'),
        longueur_conduite_m=_num(res.valeur('hmt.conduite.longueur_m')),
        volume_bassin_m3=_num(res.valeur('source.volume_reservoir_m3')),
        options_cochees=res.valeur('options_cochees'))


def _site_du_calcul(res, reglages, sans_tmy):
    """Site de l'étude : profils PVGIS, alertes, coordonnées figées,
    températures TMY et heures de repli (lectures, repli étiqueté)."""
    # Site : PVGIS + températures TMY (lectures, repli étiqueté).
    localisation, _prov_loc = res.bloc('localisation')
    localisation = localisation or {}
    lat, lon = _num(localisation.get('lat')), _num(localisation.get('lon'))
    ville = localisation.get('ville')
    profils = profils_horaires_site(ville=ville, lat=lat, lon=lon)
    alertes_pvgis = []
    coordonnees = None
    if profils is None and not ville and (lat is None or lon is None):
        # AGQ26 (C-AGQ-025) — aucun site transmis : ce n'est PAS une panne
        # PVGIS, c'est la localisation qui manque — l'alerte le dit.
        alertes_pvgis.append(_alerte(
            'site_inconnu', 'localisation',
            "Site non renseigné (ville ou GPS) : production en repli plat "
            "(débit × heures du réglage société), sans variation mensuelle."))
    elif profils is None:
        alertes_pvgis.append(_alerte(
            'pvgis_indisponible', 'production',
            "Irradiation du site indisponible : production en REPLI PLAT "
            "(débit × heures du réglage société), sans variation mensuelle."))
    elif lat is not None and lon is not None:
        coordonnees = {'lat': lat, 'lon': lon, 'fige_le': _aujourdhui()}
    temperatures = temperatures_du_site(lat, lon, sans_tmy=sans_tmy)
    heures_repli = _reglage(reglages, 'agricole_pump_hours')
    return profils, alertes_pvgis, coordonnees, temperatures, heures_repli


def _lire_mode_pompe(brut):
    """AGM6 — ``(mode, alertes)`` : un mode vide vaut ``neuve`` (défaut
    AGQ39, aucune alerte) ; un mode inconnu bascule sur ``neuve`` en le DISANT
    (``mode_pompe_invalide``), jamais en silence."""
    mode = brut or 'neuve'
    if mode in ('neuve', 'existante'):
        return mode, []
    return 'neuve', [_alerte(
        'mode_pompe_invalide', 'mode_pompe',
        "Mode de pompe « %s » inconnu (attendu : neuve ou existante) : "
        "pompe neuve étudiée." % mode)]


def _alerte_type_suppose(mode_pompe, type_pompe):
    """AGM6 — ``[alerte]`` d'une pompe neuve sans type déclaré (immergée
    supposée), sinon ``[]``."""
    if mode_pompe != 'neuve' or type_pompe:
        return []
    return [_alerte(
        'type_pompe_supposee', 'type_pompe',
        "Type de pompe non renseigné (immergée ou de surface) : pompe "
        "immergée supposée.")]


def etudier_pompage(company, entrees, *, devis=None, lead=None,
                    facture=None, sans_tmy=False):
    """AGR121 — l'étude de pompage complète, forme EXACTE du contrat
    ``etude_pompage_preview.json`` (``exemple``). Aucune écriture.

    ``company`` : TOUJOURS celle de l'appelant (``request.user``) ;
    ``entrees`` : le corps (forme ``corps`` du contrat) ; ``devis`` / ``lead``
    déjà scopés société par l'appelant (``lead`` retombe sur ``devis.lead``).

    AGR123 — ``facture`` (:func:`facture_du_devis`) : le système RÉELLEMENT
    facturé (pompe, variateur, panneaux des LIGNES). Fourni, la pompe, la
    puissance, le variateur, le champ et la production décrivent CE système
    (évalué, jamais redimensionné) au lieu de la proposition du catalogue ;
    les tailles et le kit restent la proposition du moteur.
    """
    from core.pompage.hydraulique import debit_a_hmt
    from core.pompage.selection import _sortie_pompe, choisir_pompe, kw_pompe
    from core.pompage.tailles import proposer_tailles

    if lead is None and devis is not None:
        lead = getattr(devis, 'lead', None)
    res, reglages = resoudre_entrees(company, entrees or {}, devis=devis,
                                     lead=lead)
    mode_pompe, alertes_entree = _lire_mode_pompe(res.valeur('mode_pompe'))
    alim = res.valeur('alim')
    type_pompe = res.valeur('type_pompe')
    if mode_pompe == 'existante' and not type_pompe:
        type_pompe = res.valeur('_type_pompe_actuelle')
    alertes_entree.extend(_alerte_type_suppose(mode_pompe, type_pompe))
    taille_voulue = res.valeur('taille')
    if taille_voulue not in TAILLES_VALIDES:
        taille_voulue = 'recommandee'

    (profils, alertes_pvgis, coordonnees, temperatures,
     heures_repli) = _site_du_calcul(res, reglages, sans_tmy)

    # Besoin (D-AGR-3) puis débit de conception (passe 1, sans production).
    besoin, agro, alertes_besoin = _besoin(res, profils=profils,
                                           heures_repli=heures_repli)
    serie = besoin.get('m3_jour_mois')
    plaque, _prov_plaque = res.bloc('plaque')
    plaque_kw = _num((plaque or {}).get('kw'))
    passe1 = _conception(res, besoin, reglages, profils=profils, hmt_m=None)
    debit_conception = passe1['conception']['debit_conception_m3h']
    # AGQ2 (D-AGQ-2) — le mois critique de la passe 1 (heures-pic) n'est qu'une
    # indication : les tailles ET le champ lisent le mois RECALCULÉ sur la
    # production (pire mois production ÷ besoin), la passe 2 aussi.

    # HMT au débit de conception (pertes Hazen-Williams à ce débit).
    debit_hmt = debit_conception or _num(res.valeur(
        'besoin.debit_actuel_m3h'))
    hmt = _hmt(res, debit_hmt)
    hmt_m = hmt.get('valeur_m')

    catalogue = lire_catalogue(company)
    produits = catalogue['pompage']
    pompes = [p for p in produits if p.get('role_pompage') == 'pompe']
    variateurs = [p for p in produits
                  if p.get('role_pompage') == 'variateur_pompage']
    panneau = catalogue['panneau']
    kit_params = _parametres_kit(res, reglages, catalogue, produits)
    # AGQ40 (D-AGQ-9) — la production de chaque heure est plafonnée au
    # plafond RETENU de la passe 1 (forage × part du réglage, ou ABH).
    plafond_m3h = passe1['conception']['plafonds']['plafond_retenu_m3h']
    commun = dict(profils_horaires=profils, temperatures=temperatures,
                  salissure_pct=_reglage(reglages,
                                         'agricole_salissure_supp_pct'),
                  agricole_pump_hours=heures_repli, coordonnees=coordonnees,
                  plafond_m3h=plafond_m3h)
    alertes_moteur, hypotheses_moteur = [], []
    if panneau is None:
        alertes_moteur.append(_alerte(
            'aucun_panneau', 'panneau',
            "Aucun panneau au catalogue : champ non dimensionné."))

    if mode_pompe == 'existante':
        from core.pompage.conception import pompe_existante

        existante = pompe_existante(
            plaque=plaque, variateurs=variateurs, panneau=panneau,
            besoin_m3_jour_mois=serie, hmt_m=hmt_m,
            debit_declare_m3h=_num(res.valeur('besoin.debit_actuel_m3h')),
            type_pompe=type_pompe, **commun)
        tailles = proposer_tailles(
            mode_pompe='existante', plaque=plaque,
            debit_declare_m3h=_num(res.valeur('besoin.debit_actuel_m3h')),
            besoin_m3_jour_mois=serie, hmt_m=hmt_m, alimentation=alim,
            type_pompe=type_pompe, variateurs=variateurs, panneau=panneau,
            besoin_agronomique=agro, kit=kit_params, **commun)
        pompe = existante['pompe']
        variateur = existante['variateur']
        puissance = existante['puissance_retenue']
        prix_a_renseigner = []
        alertes_moteur.extend(existante['alertes'])
        hypotheses_moteur.extend(existante['hypotheses'])
        choisie = tailles['tailles'][0] if tailles['tailles'] else None
        # Rejeu live AGQ41 (24/10) — la ligne « Champ » du résumé ET la carte
        # « Recommandée » lisent le MÊME champ : celui de la taille retenue
        # (comme pour une pompe neuve). Avant, ``pompe_existante`` recevait le
        # mois critique de la passe 1 et ``proposer_tailles`` non : sans kW de
        # plaque, 4,95 kWc (9 panneaux) d'un côté, 5,5 kWc (10) de l'autre.
        champ_complet = ((choisie or {}).get('champ')
                         or existante['champ'])
        if champ_complet:
            hypotheses_moteur.extend(champ_complet.get('hypotheses') or [])
        taille_retenue = 'recommandee'
        methode = ("Pompe existante conservée (D-AGR-7) : variateur et champ "
                   "dimensionnés sur la PLAQUE ; production estimée sur le "
                   "débit DÉCLARÉ de la pompe actuelle × Σ min(1, P/P_plaque),"
                   " étiquetée « estimation sur débit déclaré ».")
    else:
        choix = choisir_pompe(
            pompes, hmt_m=hmt_m, debit_conception_m3h=debit_conception,
            alimentation=alim, type_pompe=type_pompe or 'immergee',
            diametre_tubage_mm=_num(res.valeur('source.diametre_tubage_mm')),
            profondeur_calage_m=_num(res.valeur('source.profondeur_calage_m')),
            niveau_dynamique_m=_num(res.valeur('source.niveau_dynamique_m')))
        alertes_moteur.extend(choix['alertes'])
        hypotheses_moteur.extend(choix['hypotheses'])
        prix_a_renseigner = choix['prix_a_renseigner']
        tailles = proposer_tailles(
            mode_pompe='neuve', choix_pompe=choix, besoin_m3_jour_mois=serie,
            hmt_m=hmt_m, alimentation=alim, type_pompe=type_pompe,
            variateurs=variateurs, panneau=panneau,
            besoin_agronomique=agro, kit=kit_params, **commun)
        par_cle = {t['cle']: t for t in tailles['tailles']}
        taille_retenue = (taille_voulue if taille_voulue in par_cle
                          else 'recommandee')
        if taille_voulue not in par_cle and taille_voulue != 'recommandee':
            alertes_entree.append(_alerte(
                'taille_indisponible', 'taille',
                "Taille « %s » indisponible pour ce besoin : taille "
                "recommandée retenue." % taille_voulue))
        choisie = par_cle.get(taille_retenue)
        if choisie is not None:
            produit = next((p for p in choix['paliers']
                            if p.get('id') == choisie['pompe_produit']), None)
            kw, _src = kw_pompe(produit) if produit else (None, None)
            debit = (debit_a_hmt(produit['courbe_pompe'], hmt_m)
                     if produit and choix['etape'] == 'courbe' else None)
            pompe = (_sortie_pompe(produit, kw=kw, debit_hmt=debit, hmt=hmt_m)
                     if produit else choix['pompe'])
            if choix['etape'] == 'pre_dimensionnement':
                pompe['etiquette'] = choix['pompe'].get('etiquette')
            champ_complet = choisie.get('champ')
            variateur = _forme_variateur(
                (champ_complet or {}).get('variateur'),
                'aucun variateur compatible au catalogue')
            cv = _cv_plaque_ou_derive(produit, kw)
            puissance = {'kw': round(kw, 2) if kw else None,
                         'cv': round(cv, 1) if cv else None}
            if champ_complet:
                alertes_moteur.extend(champ_complet.get('alertes') or [])
                hypotheses_moteur.extend(champ_complet.get('hypotheses') or [])
        else:
            pompe = choix['pompe']
            champ_complet = None
            variateur = _forme_variateur(
                None, 'aucune pompe retenue : variateur non choisi')
            puissance = choix['puissance_retenue']
        methode = ("HMT = niveau dynamique + dénivelé + pertes Hazen-Williams "
                   "+ pertes singulières + pression de service × 10,197 m/bar"
                   " ; besoin %s (D-AGR-3) ; débit de conception = besoin du "
                   "mois critique ÷ heures-pic PVGIS de ce mois ; production "
                   "heure par heure sur le profil PVGIS du site avec lois de "
                   "similitude de la courbe ; champ dimensionné sur le mois "
                   "critique." % (
                       {'agronomique_plein': 'agronomique plein (FAO-56)',
                        'debit_souhaite': 'dérivé du débit souhaité × '
                                          'heures-pic du mois'}.get(
                           besoin.get('nature'), 'déclaré')))
        if pompe.get('placeholder'):
            methode = ("Aucune pompe pricée ne couvre le débit de conception :"
                       " ligne « Pompe — prix à renseigner : <noms> » (jamais "
                       "enregistrée comme article gratuit), production et "
                       "couverture omises.")
    if profils is None:
        methode = ("PVGIS indisponible : production = débit à la HMT × heures "
                   "du réglage société (`agricole_pump_hours`), étiquetée "
                   "« repli » ; coordonnées non figées.")

    if facture is not None:
        pompe, puissance, variateur, champ_complet, alertes_facture = (
            _systeme_facture(
                facture, mode_pompe=mode_pompe, hmt_m=hmt_m, serie=serie,
                plaque_kw=plaque_kw,
                debit_declare=_num(res.valeur('besoin.debit_actuel_m3h')),
                commun=commun, pompe_actuelle=pompe,
                puissance_actuelle=puissance, variateur_actuel=variateur))
        alertes_moteur.extend(alertes_facture)

    production_brute = (champ_complet or {}).get('production') or {}
    production = _forme_production(production_brute or None)
    if production and production_brute.get('plafond_atteint'):
        alertes_moteur.append(_alerte(
            'debit_limite_forage', 'source.debit_exploitation_m3h',
            "Débit limité par votre forage : la pompe livrerait davantage, "
            "la production de chaque heure est plafonnée à %s m³/h (débit "
            "d'exploitation × part du réglage société)."
            % _fr_m3h(production.get('plafond_forage_m3h'))))
    passe2 = _conception(
        res, besoin, reglages, profils=profils, hmt_m=hmt_m,
        production=production['m3_jour_mois'] if production else None,
        plaque_kw=plaque_kw if mode_pompe == 'existante' else None)
    hypotheses_moteur.extend(passe2['hypotheses'])

    if choisie is not None and choisie.get('ha_irrigables'):
        ha = choisie['ha_irrigables']
    else:
        ha = {'valeur': None, 'base': None, 'motif': 'aucune pompe retenue'}

    kit = _forme_kit(choisie.get('composition') if choisie else None)
    if choisie is None and pompe.get('placeholder'):
        kit['inclus'] = [{'cle': 'pompe', 'role_pompage': 'pompe',
                          'produit': None, 'designation': pompe.get('nom'),
                          'quantite': 1, 'prix_connu': False}]
    alertes_kit = (choisie.get('composition') or {}).get('alertes') \
        if choisie else []

    entrees_resolues = res.entrees_resolues()
    if profils is None and heures_repli is not None:
        entrees_resolues['heures_repli'] = {
            'valeur': heures_repli,
            'provenance': reglages['agricole_pump_hours'][1]}

    motif_champ = None
    if pompe.get('placeholder'):
        motif_champ = 'aucune pompe retenue'
    sortie = {
        'entrees_resolues': entrees_resolues,
        'hmt': {'valeur_m': hmt_m,
                'composantes': (hmt.get('composantes')
                                if hmt.get('source') == 'calculee' else None),
                'source': hmt.get('source')},
        'besoin': {'m3_jour_mois': serie, 'nature': besoin.get('nature'),
                   'source_et0': besoin.get('source_et0'),
                   'autre_besoin': besoin.get('autre_besoin')},
        'conception': {
            'mois_critique': passe2['conception']['mois_critique'],
            'debit_conception_m3h': (passe2['conception']
                                     ['debit_conception_m3h']
                                     if mode_pompe == 'neuve' else None),
            'plafonds': {k: passe2['conception']['plafonds'].get(k)
                         for k in ('debit_exploitation_m3h',
                                   'part_reglage_pct', 'debit_autorise_m3h',
                                   'plafond_retenu_m3h', 'atteint')},
        },
        'pompe': pompe,
        'variateur': variateur,
        'prix_a_renseigner': list(prix_a_renseigner),
        'puissance_retenue': puissance,
        'champ': _forme_champ(champ_complet, motif_champ),
        'production': production,
        'couverture_pct_mois': (passe2['couverture_pct_mois']
                                if production else None),
        'controle_conception': passe2['controle_conception'],
        'ha_irrigables': {'valeur': ha.get('valeur'), 'base': ha.get('base'),
                          'motif': ha.get('motif')},
        'autonomie_reservoir_jours': passe2['autonomie_reservoir_jours'],
        'tailles': [_forme_taille(t, t['cle'] == taille_retenue)
                    for t in tailles['tailles']],
        'tailles_omises': tailles['tailles_omises'],
        'kit': kit,
        'alertes': _alertes_uniques(
            alertes_entree, alertes_pvgis, alertes_besoin, hmt.get('alertes'),
            alertes_moteur, tailles.get('alertes'), alertes_kit,
            passe2['alertes']),
        'hypotheses': _hypotheses_uniques(hypotheses_moteur),
        'methode': methode,
    }
    # Rejeu live AGQ41 (24/10) — le kit minimum manquant est SERVI : l'écran
    # refuse « Auto-remplir » (comme le devis automatique) en nommant la cause
    # au lieu de poser un kit sans variateur.
    sortie['roles_minimum_manquants'] = roles_minimum_manquants(sortie)
    return _sans_cles_interdites(_json(sortie))


# ── 5. AGR123 — LE RAFRAÎCHISSEUR : l'étude suit la pompe FACTURÉE ───────────

def _systeme_facture(facture, *, mode_pompe, hmt_m, serie, plaque_kw,
                     debit_declare, commun, pompe_actuelle,
                     puissance_actuelle, variateur_actuel):
    """``(pompe, puissance, variateur, champ, alertes)`` du système FACTURÉ.

    ÉVALUE le système des lignes (pompe → kW plaque et courbe ; variateur ;
    nombre de panneaux × Pmax) — il ne le redimensionne JAMAIS. Pompe neuve
    absente des lignes ⇒ pompe, puissance et production OMISES (jamais
    périmées). Pompe existante (D-AGR-7) : la plaque reste la pompe, seuls le
    variateur et le champ viennent des lignes.
    """
    from core.pompage.champ import (
        _chaines_pour, _chaines_vides, _fiche, spec_module,
    )
    from core.pompage.hydraulique import debit_a_hmt
    from core.pompage.selection import _sortie_pompe, kw_pompe
    from core.pompage.volumes import production_mensuelle

    alertes = []
    produit_pompe = facture.get('pompe')
    courbe, declare = None, None
    if mode_pompe == 'existante':
        pompe, puissance, p_kw = pompe_actuelle, puissance_actuelle, plaque_kw
        declare = debit_declare
    elif facture.get('nb_pompes', 0) > 1:
        # AGM7 — plusieurs pompes facturées : aucune ne représente le système
        # (jamais la première × la quantité totale) ⇒ pompe et production
        # OMISES, dites.
        alertes.append(_alerte(
            'pompes_multiples', 'pompe',
            "%d pompes au devis (lignes ou quantité) : puissance, débit et "
            "production de la pompe omis (l'étude décrit UNE pompe)."
            % facture['nb_pompes']))
        return (_sortie_pompe(None, kw=None, debit_hmt=None, hmt=hmt_m),
                {'kw': None, 'cv': None},
                _forme_variateur(None, 'plusieurs pompes facturées'), None,
                alertes)
    elif produit_pompe:
        p_kw, _src = kw_pompe(produit_pompe)
        brute = produit_pompe.get('courbe_pompe') or {}
        if brute.get('debits_m3h') and brute.get('hmt_m'):
            courbe = brute
        debit = (debit_a_hmt(courbe, hmt_m)
                 if courbe is not None and hmt_m is not None else None)
        pompe = _sortie_pompe(produit_pompe, kw=p_kw, debit_hmt=debit,
                              hmt=hmt_m)
        cv = _cv_plaque_ou_derive(produit_pompe, p_kw)
        puissance = {'kw': round(p_kw, 2) if p_kw else None,
                     'cv': round(cv, 1) if cv else None}
    else:
        alertes.append(_alerte(
            'pompe_non_facturee', 'pompe',
            "Aucune ligne pompe au devis : puissance, débit et production "
            "de la pompe omis."))
        return (_sortie_pompe(None, kw=None, debit_hmt=None, hmt=hmt_m),
                {'kw': None, 'cv': None},
                _forme_variateur(None, 'aucune pompe facturée'), None,
                alertes)

    produit_variateur = facture.get('variateur')
    motif_variateur = 'aucun variateur facturé'
    if facture.get('nb_variateurs', 0) > 1:
        # AGM7 — plusieurs variateurs : aucun ne décrit le champ.
        alertes.append(_alerte(
            'variateurs_multiples', 'variateur',
            "%d variateurs au devis (lignes ou quantité) : variateur et "
            "chaînes non évalués." % facture['nb_variateurs']))
        produit_variateur = None
        motif_variateur = 'plusieurs variateurs facturés'
    if produit_variateur:
        variateur = _forme_variateur(produit_variateur, None)
    elif mode_pompe == 'existante':
        variateur = variateur_actuel
    else:
        variateur = _forme_variateur(None, motif_variateur)

    if facture.get('modeles_panneaux', 0) > 1:
        # AGM7 — plusieurs modèles de panneaux : « premier modèle × quantité
        # totale » serait faux (kWc, m³/jour) ⇒ champ non évalué, dit.
        alertes.append(_alerte(
            'panneaux_modeles_multiples', 'champ',
            "%d modèles de panneaux au devis : champ et production omis "
            "(l'étude décrit UN modèle de panneau)."
            % facture['modeles_panneaux']))
        return pompe, puissance, variateur, None, alertes

    module = spec_module(facture.get('panneau'))
    nb = facture.get('nb_panneaux') or 0
    if module is None or nb <= 0:
        alertes.append(_alerte(
            'champ_non_facture', 'champ',
            "Aucun panneau à fiche électrique complète au devis : champ et "
            "production omis."))
        return pompe, puissance, variateur, None, alertes

    kwc = nb * module.pmax_wc / 1000.0
    mppt = _num(_fiche(produit_variateur or {}).get('var_rendement_mppt_pct'))
    production = production_mensuelle(
        kwc=kwc, profils_horaires=commun.get('profils_horaires'),
        courbe_pompe=courbe, hmt_m=hmt_m, p_plaque_kw=p_kw,
        rendement_mppt=mppt / 100.0 if mppt else None,
        salissure_pct=commun.get('salissure_pct'),
        debit_declare_m3h=declare,
        agricole_pump_hours=commun.get('agricole_pump_hours'),
        besoin_m3_jour_mois=serie, coordonnees=commun.get('coordonnees'),
        plafond_m3h=commun.get('plafond_m3h'))
    chaines = _chaines_vides(motif_variateur)
    if produit_variateur:
        nb_cable, chaines, alertes_chaines, _suivant = _chaines_pour(
            produit_variateur, module, nb, commun.get('temperatures'))
        alertes.extend(alertes_chaines)
        if nb_cable != nb:
            chaines = _chaines_vides(
                'le nombre de panneaux facturé ne forme pas de chaîne '
                'admissible sur ce variateur')
    champ = {'kwc': round(kwc, 2), 'nb_panneaux': nb,
             'ratio': round(kwc / p_kw, 2) if p_kw else None,
             'chaines': chaines,
             'production': (production if production.get('m3_jour_mois')
                            is not None else None)}
    return pompe, puissance, variateur, champ, alertes


#: Les ENTRÉES v2 lues par le rafraîchisseur (contrat AGR2, AGR122).
CLES_ENTREES_V2 = tuple(cle for cle, _corps in CLES_DEVIS)

#: Les sept clés v1 que le rendu lit encore (dérivées de la pompe RETENUE).
CLES_V1_RENDU = ('pompe_cv', 'pompe_kw', 'hmt_m', 'debit_hmt_m3h', 'm3_jour',
                 'champ_kwc', 'heures_pompage')

#: Version de la forme des dérivées : la changer périme toutes les empreintes.
VERSION_DERIVEES = 1


def facture_du_devis(devis, catalogue):
    """AGR123 — le système RÉELLEMENT facturé, lu sur les LIGNES du devis.

    ``{pompe, variateur, panneau, nb_panneaux, lignes}`` : la première ligne
    pompe et la première ligne variateur (forme catalogue AGR103, rôle de
    ``stock.selectors.produits_pompage``), le panneau des lignes panneau (et
    leur quantité totale). Les lignes OPTIONNELLES (add-ons non activés) ne
    sont pas facturées : elles sont ignorées. ``lignes`` = l'empreinte
    ``[[produit, quantité], …]`` de ce qui a été lu.
    """
    from .catalogue import classer_produit

    par_id = {p.get('id'): p for p in catalogue.get('pompage') or ()}
    pompe = variateur = panneau = None
    nb, lignes = 0, []
    # AGM7 — combien de pompes / variateurs (quantités additionnées) et de
    # MODÈLES de panneaux (produits distincts) : l'étude n'en mélange aucun.
    nb_pompes = nb_variateurs = 0
    modeles_panneaux = set()
    lignes_devis = devis.lignes.select_related('produit').order_by('ordre',
                                                                   'id')
    for ligne in lignes_devis:
        produit = getattr(ligne, 'produit', None)
        if produit is None or getattr(ligne, 'optionnelle', False):
            continue
        lignes.append([produit.id, str(ligne.quantite)])
        element = par_id.get(produit.id)
        role = (element or {}).get('role_pompage')
        if role == 'pompe':
            pompe = pompe or element
            nb_pompes += int(_num(ligne.quantite) or 0)
        elif role == 'variateur_pompage':
            variateur = variateur or element
            nb_variateurs += int(_num(ligne.quantite) or 0)
        elif (getattr(produit, 'role_devis', None)
              or classer_produit(produit.nom)) == 'panneau':
            nb += int(_num(ligne.quantite) or 0)
            modeles_panneaux.add(produit.id)
            if panneau is None:
                panneau = _dict_catalogue(produit, **_specs_module(produit))
    return {'pompe': pompe, 'variateur': variateur, 'panneau': panneau,
            'nb_panneaux': nb, 'lignes': lignes, 'nb_pompes': nb_pompes,
            'nb_variateurs': nb_variateurs,
            'modeles_panneaux': len(modeles_panneaux)}


def _empreinte(etude, facture, lead_id):
    import hashlib
    import json

    charge = {
        'version': VERSION_DERIVEES,
        'entrees': {cle: etude.get(cle) for cle in CLES_ENTREES_V2},
        'saisies': (etude.get('saisies_economie_pompage') or {}).get(
            'mois_irrigation'),
        'pvgis_fige': etude.get('pvgis_fige'),
        'lignes': facture.get('lignes'),
        'lead': lead_id,
    }
    texte = json.dumps(charge, sort_keys=True, default=str,
                       ensure_ascii=True)
    return hashlib.sha256(texte.encode('utf-8')).hexdigest()


def _au_mois_critique(serie, mois):
    if not serie or not mois or not 1 <= mois <= len(serie):
        return None
    return serie[mois - 1]


#: AMOT63 — entrées RÉSOLUES persistées (``etude_params['entrees_pompage']``,
#: forme figée dans ``contract_samples/etude_pompage_preview.json``) : ce que
#: le schéma et la comparaison besoin/livré impriment.
#: Rejeu live AGQ41 (24/10) — ``debit_exploitation_m3h`` en fait partie : sans
#: lui, un débit du forage venu du LEAD s'imprimait « déclaré par vous le … »
#: SANS sa valeur (« D'où viennent ces chiffres », AGQ28). Même cause, même
#: remède pour ``volume_m3_jour`` (rejeu du 24/10, phase 3).
CLES_ENTREES_POMPAGE = (
    'cultures', 'region', 'niveau_statique_m', 'niveau_dynamique_m',
    'debit_exploitation_m3h', 'profondeur_forage_m', 'volume_reservoir_m3',
    'distance_champ_m', 'plaque', 'volume_m3_jour',
)


def derivees_de_l_etude(sortie, *, pvgis_fige=None):
    """AGR122/AGR123 — l'étude (forme du contrat) → les clés DÉRIVÉES
    ``moteur_pompage`` d'``etude_params``. ``None`` = clé RETIRÉE (Z2)."""
    production = sortie.get('production')
    conception = sortie.get('conception') or {}
    mois = conception.get('mois_critique')
    champ = sortie.get('champ') or {}
    hmt = sortie.get('hmt') or {}
    pompe = sortie.get('pompe') or {}
    puissance = sortie.get('puissance_retenue') or {}
    figees = (production or {}).get('coordonnees_figees')
    if pvgis_fige and figees and (pvgis_fige.get('lat'), pvgis_fige.get(
            'lon')) == (figees.get('lat'), figees.get('lon')):
        figees = pvgis_fige
    provenance = {cle: (v or {}).get('provenance')
                  for cle, v in (sortie.get('entrees_resolues') or {}).items()}
    # AMOT63 — les valeurs RÉSOLUES que le moteur a utilisées (priorité corps >
    # devis > lead déjà appliquée par le résolveur) : le rendu les lit au
    # lieu de ne voir que les entrées saisies au devis.
    resolues = sortie.get('entrees_resolues') or {}
    entrees_pompage = {cle: (resolues[cle] or {}).get('valeur')
                       for cle in CLES_ENTREES_POMPAGE if cle in resolues}
    return {
        'besoin_mensuel': sortie.get('besoin'),
        'production': production,
        'couverture_pct_mois': sortie.get('couverture_pct_mois'),
        'controle_conception': sortie.get('controle_conception'),
        'conception': conception or None,
        'champ': champ if champ.get('kwc') is not None else None,
        'hmt_composantes': hmt.get('composantes'),
        'ha_irrigables': sortie.get('ha_irrigables'),
        'autonomie_reservoir_jours': sortie.get('autonomie_reservoir_jours'),
        'kit': sortie.get('kit'),
        'alertes_pompage': sortie.get('alertes') or None,
        'hypotheses_pompage': sortie.get('hypotheses') or None,
        'pvgis_fige': figees or None,
        'provenance_pompage': {'entrees': provenance},
        'entrees_pompage': entrees_pompage or None,
        'pompe_cv': puissance.get('cv'),
        'pompe_kw': puissance.get('kw'),
        'hmt_m': hmt.get('valeur_m'),
        'debit_hmt_m3h': pompe.get('debit_a_hmt_m3h'),
        'm3_jour': _au_mois_critique(
            (production or {}).get('m3_jour_mois'), mois),
        'champ_kwc': champ.get('kwc'),
        'heures_pompage': _au_mois_critique(
            (production or {}).get('heures_equivalentes_mois'), mois),
    }


#: AGQ24 (C-AGQ-023) — l'étude DÉJÀ calculée par le devis automatique, posée
#: le temps de son écriture : ``(lead_id, sortie)``. Le rafraîchisseur la
#: relit au lieu de relancer le moteur (une seule étude par devis auto).
_ETUDE_PRECALCULEE = contextvars.ContextVar('etude_pompage_precalculee',
                                            default=None)


@contextlib.contextmanager
def etude_precalculee(lead, sortie):
    """AGQ24 — pendant ce bloc, :func:`rafraichir_etude_pompage_devis` d'un
    devis de ce ``lead`` relit ``sortie`` (aucun second calcul)."""
    jeton = _ETUDE_PRECALCULEE.set((getattr(lead, 'pk', None), sortie))
    try:
        yield
    finally:
        _ETUDE_PRECALCULEE.reset(jeton)


def _sortie_precalculee(devis):
    courante = _ETUDE_PRECALCULEE.get()
    if not courante or courante[0] is None:
        return None
    lead_id, sortie = courante
    return sortie if getattr(devis, 'lead_id', None) == lead_id else None


def rafraichir_etude_pompage_devis(devis, *, force=False, sortie=None):
    """AGR123 — l'étude pompage d'un devis AGRICOLE suit ses LIGNES.

    Cinquième étude de ``etudes.rafraichir_etudes_du_devis`` (donc appelée à
    chaque écriture de ligne, par ``atomic``/``replace-lines``/
    ``LigneDevisViewSet``, et — forcée — par les chemins de copie et la V2,
    qui purgent les dérivées via ``CLES_DERIVEES_NON_COPIEES``).

    Relit les LIGNES (:func:`facture_du_devis`), les ENTRÉES v2 stockées et
    ``pvgis_fige``, appelle :func:`etudier_pompage` et ne réécrit QUE les
    dérivées ``moteur_pompage`` (``etude_schema.ecrire`` :
    ``update_fields=['etude_params']``, aucun statut, aucune ligne, aucun
    total — règle #4). Empreinte : mêmes entrées ⇒ AUCUNE écriture (ni même un
    calcul). Ligne pompe supprimée ⇒ dérivées de la pompe OMISES.

    No-op (``None``) sur tout marché non agricole. Ne lève JAMAIS : un
    rafraîchissement raté n'empêche pas l'enregistrement d'une ligne.
    """
    if (getattr(devis, 'mode_installation', None) or '').strip().lower() \
            != 'agricole':
        return None
    try:
        from .etude_schema import MOTEUR_POMPAGE, ecrire

        etude = dict(devis.etude_params or {})
        company = devis.company
        lead = getattr(devis, 'lead', None)
        catalogue = lire_catalogue(company)
        facture = facture_du_devis(devis, catalogue)
        empreinte = _empreinte(etude, facture, getattr(lead, 'id', None))
        stockee = (etude.get('provenance_pompage') or {}).get('_empreinte')
        if not force and stockee == empreinte:
            return None

        corps = {}
        fige = etude.get('pvgis_fige') or {}
        localisation = etude.get('localisation') or {}
        if (fige.get('lat') is not None and fige.get('lon') is not None
                and (localisation.get('lat') is None
                     or localisation.get('lon') is None)):
            corps['localisation'] = dict(localisation, lat=fige['lat'],
                                         lon=fige['lon'])
        # AGQ24 — l'étude écrite par le devis automatique est RELUE (passée
        # ou posée par :func:`etude_precalculee`) : jamais deux calculs.
        sortie = sortie or _sortie_precalculee(devis)
        if sortie is None:
            sortie = etudier_pompage(company, corps, devis=devis, lead=lead,
                                     facture=facture)
        derivees = derivees_de_l_etude(sortie, pvgis_fige=fige or None)
        # ``pvgis_fige`` est À LA FOIS une entrée de l'empreinte et une dérivée
        # que CE rafraîchisseur écrit (premier appel : None → coordonnées
        # figées). L'empreinte STOCKÉE décrit donc l'état APRÈS écriture —
        # sinon le second appel, sans aucun changement, la verrait différente
        # et relancerait le moteur (garde « mêmes entrées ⇒ zéro calcul »).
        empreinte = _empreinte(
            dict(etude, pvgis_fige=derivees.get('pvgis_fige')), facture,
            getattr(lead, 'id', None))
        derivees['provenance_pompage']['_empreinte'] = empreinte
        a_ecrire = {cle: valeur for cle, valeur in derivees.items()
                    if etude.get(cle) != valeur}
        if a_ecrire:
            ecrire(devis, proprietaire=MOTEUR_POMPAGE, **a_ecrire)
        return derivees
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant (D-ENF22-BLE001)
        logger.warning('rafraichir_etude_pompage_devis indisponible sur %s',
                       getattr(devis, 'reference', '?'), exc_info=True)
        return None


# ── 6. AGR124 — LE DEVIS AUTOMATIQUE AGRICOLE (lectures pour creation_auto) ──

#: Sous-blocs de ``saisies_economie_pompage`` (contrat AGR3) qui portent une
#: PROVENANCE ``{origine, detail, date}`` ; les autres portent ``saisi_le``.
_SAISIES_AVEC_PROVENANCE = ('energie_actuelle', 'mois_irrigation')


def saisies_economie_pompage_du_lead(lead):
    """AGR124 (repris de l'ex-AGR215) — les entrées CARBURANT du lead (énergie
    actuelle, bouteilles/jour, litres/mois, prix payé + date, mois
    d'irrigation) dans la forme ``saisies_economie_pompage`` du contrat
    partagé ``economie_pompage.json``, provenance ``lead``. Lecture UNIQUE par
    ``crm.selectors.entrees_pompage_du_lead`` (AGR404), jamais une colonne lue
    directement ; rien d'inventé (une donnée absente reste absente). ``None``
    quand le lead n'a rien déclaré."""
    if lead is None:
        return None
    from apps.crm.selectors import entrees_pompage_du_lead

    lecture = entrees_pompage_du_lead(lead) or {}
    saisies = {}
    for entree in lecture.get('entrees') or ():
        chemin = entree.get('chemin') or ''
        if not chemin.startswith('saisies_economie_pompage.'):
            continue
        if entree.get('ignoree'):
            continue  # AGQ19 — colonne d'une autre énergie, jamais appliquée
        morceaux = chemin.split('.')[1:]
        if len(morceaux) != 2:
            continue
        bloc, champ = morceaux
        valeur = _json(entree.get('valeur'))
        if _vide(valeur):
            continue
        cible = saisies.setdefault(bloc, {})
        cible[champ] = valeur
        date = entree.get('date')
        if bloc in _SAISIES_AVEC_PROVENANCE:
            cible['provenance'] = _provenance(
                'lead', entree.get('provenance'), date)
        elif date:
            cible['saisi_le'] = date
        for cle in ('unite', 'periode'):
            if entree.get(cle):
                cible[cle] = entree[cle]
    return saisies or None


#: AGQ4 (D-AGQ-3) — LE kit minimum du devis automatique agricole (D-AGR-8) :
#: ``(clé de kit.inclus, libellé)``. Un rôle absent ou sans prix REFUSE le
#: devis automatique en le nommant ; les options restent facultatives. La
#: pompe ne compte pas en mode « existante » (aucune ligne pompe, D-AGR-7).
ROLES_KIT_MINIMUM = (
    ('pompe', 'Pompe'),
    ('variateur', 'Variateur'),
    ('panneaux', 'Panneaux'),
    ('structure', 'Structure au sol'),
    ('installation', 'Installation'),
)


#: Rejeu live AGQ41 (24/10) — les alertes du noyau qui laissent le champ
#: solaire non dimensionné : leur message EST la cause dite au vendeur (le 409
#: ne sert aucune alerte, « voir les alertes » ne menait nulle part).
CODES_CHAMP_NON_DIMENSIONNE = ('panneau_sans_fiche', 'besoin_inconnu',
                               'irradiation_inconnue', 'aucun_variateur',
                               'chaine_non_verifiable', 'hmt_inconnue',
                               'besoin_nul')


def _cause_champ_vide(sortie):
    for alerte in (sortie or {}).get('alertes') or ():
        if (alerte.get('code') in CODES_CHAMP_NON_DIMENSIONNE
                and alerte.get('message')):
            # « … : champ non dimensionné. » — la conséquence est déjà dite.
            return re.sub(r'\s*:\s*champ (solaire )?non dimensionné\.?$', '',
                          alerte['message'].strip()).rstrip('. ')
    motif = (((sortie or {}).get('champ') or {}).get('chaines') or {}).get(
        'motif')
    return motif or 'cause non servie par le moteur'


def roles_minimum_manquants(sortie):
    """AGQ4 — ``[{cle, libelle, motif}]`` des rôles du kit minimum absents
    de ``kit.inclus`` ou sans prix connu (barème compris, AGQ5) ; un champ
    non dimensionné dit SA cause (alerte du noyau), jamais « voir les alertes »."""
    kit = (sortie or {}).get('kit') or {}
    existante = ((sortie or {}).get('pompe') or {}).get('mode') == 'existante'
    inclus = {ligne.get('cle'): ligne for ligne in kit.get('inclus') or ()}
    champ_vide = ((sortie or {}).get('champ') or {}).get('nb_panneaux') is None
    manquants = []
    for cle, libelle in ROLES_KIT_MINIMUM:
        if cle == 'pompe' and existante:
            continue
        ligne = inclus.get(cle)
        if ligne is None:
            if cle in ('panneaux', 'structure') and champ_vide:
                motif = 'champ solaire non dimensionné — %s' % (
                    _cause_champ_vide(sortie))
            else:
                motif = 'aucun article au catalogue'
        elif not ligne.get('produit') and cle != 'pompe':
            # AGM13 — la ligne PLACEHOLDER du noyau (produit None) : aucun
            # article de ce rôle n'existe (un article sans prix est une ligne
            # AVEC produit). La pompe placeholder reste « prix à renseigner »
            # (ses candidats existent, sans prix).
            motif = 'aucun article au catalogue (rôle %s)' % (
                ligne.get('role_pompage') or cle)
        elif not ligne.get('prix_connu') or not ligne.get('produit'):
            motif = 'prix à renseigner au catalogue'
        else:
            continue
        manquants.append({'cle': cle, 'libelle': libelle, 'motif': motif})
    return manquants


def lignes_kit_auto(sortie):
    """AGR124 — le KIT MINIMUM de l'étude (``kit.inclus`` + options cochées
    par défaut, dont l'afficheur d'un variateur VEICHI) en lignes de devis
    ``[{produit_id, designation, quantite, role_pompage, cle}]``.

    Seuls les articles PRICÉS (prix ou barème) deviennent des lignes ; une
    ligne « prix à renseigner » ou sans quantité n'est JAMAIS un article
    gratuit : elle est rendue dans ``omises`` (désignations) pour être nommée
    dans les alertes. AGQ4 — rend aussi ``manquants`` =
    :func:`roles_minimum_manquants` (le kit minimum, qui REFUSE le devis).
    Rend ``(lignes, omises, manquants)``."""
    kit = (sortie or {}).get('kit') or {}
    candidates = list(kit.get('inclus') or [])
    for option in kit.get('options') or []:
        if option.get('cochee'):
            candidates.append({
                'cle': option.get('cle'), 'role_pompage': option.get('cle'),
                'produit': option.get('produit'),
                'designation': option.get('libelle'),
                'quantite': option.get('quantite'),
                'prix_connu': option.get('prix_connu')})
    lignes, omises = [], []
    for ligne in candidates:
        quantite = _num(ligne.get('quantite'))
        if (not ligne.get('prix_connu') or not ligne.get('produit')
                or not quantite or quantite <= 0):
            omises.append(ligne.get('designation') or ligne.get('cle') or '')
            continue
        lignes.append({'produit_id': ligne['produit'],
                       'designation': ligne.get('designation') or '',
                       'quantite': Decimal(str(quantite)),
                       'role_pompage': ligne.get('role_pompage') or '',
                       'cle': ligne.get('cle') or ''})
    return lignes, omises, roles_minimum_manquants(sortie)
