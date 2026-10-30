"""CIQ118 — orchestrateur de l'étude COMMERCIAL / INDUSTRIEL (D-CIQ-0).

``etudier_ci(company, entrees, *, devis=None, lead=None)`` est LA seule
fonction appelée par l'aperçu ``POST /ventes/etude-ci/preview/``, le
rafraîchisseur (CIQ119) et le devis automatique (CIQ120). Elle rend la forme
``exemple`` du contrat ``contract_samples/etude_ci_preview.json``.

Elle LIT seulement (aucun INSERT ni UPDATE) et assemble le noyau pur
``apps.ventes.moteur_ci`` :

1. entrées résolues avec leur provenance — corps > devis > lead (lu par
   ``crm.selectors.entrees_ci_du_lead``, CIQ405) > réglage société ;
2. consommation résolue UNE fois : kWh mensuels saisis > 12 kWh de factures
   > factures MAD converties au tarif C&I (CIQ203, jamais sans tarif) >
   ``bill_kwh`` en lecture seule ;
3. production PVGIS (CIQ109), profil déclaré (CIQ108, profil société puis
   archétype sourcé CIQ107), autoconsommation horaire (CIQ110), onduleurs
   (CIQ111), composition (CIQ115), taille par la règle des 10 ans (CIQ116)
   avec la valorisation ``economie_ci.valoriser`` (CIQ204) injectée ;
4. toit : contenance mesurée du devis, sinon contenance de la surface
   déclarée (CIQ113, façade ``apps.calepinage.services``) ; charge de toiture
   (CIQ114) en alerte interne ;
5. ``regime_8221_suggere`` par ``core.reglementaire.regime_8221`` (CIQ612) ;
   ``sous_reserve_visite`` = drapeau ``visite_avant_devis`` du lead (CIQ404).

Le profil ``activity_profile`` du site ne pilote AUCUN chiffre (C4-VA-01).
Jamais ``prix_achat`` ni marge (parcours récursif à la sortie).
"""
from __future__ import annotations

import calendar
import logging
import math
from decimal import Decimal

from .etude_ci_batterie import CLE as CLE_OPTION_AVEC, option_avec_de_l_etude
from .regles_calcul import REGLES_CORRIGEES_2710, regles_au_moins
from .etude_ci_visite import _couche_visite

logger = logging.getLogger(__name__)

VERSION_MOTEUR = 'ci-1'
METHODE = (
    "autoconsommation horaire : production PVGIS du site × profil déclaré, "
    "12 mois × types de jour ; taille par tranches de 5 kWc jusqu'à "
    "l'horizon marginal de 10 ans (D-CIQ-1, D-CIQ-2)")
#: AMOT99 (D-ACI-18=a) — avec la série horaire ; ``METHODE`` = le repli (dit).
METHODE_8760 = (
    "autoconsommation horaire : production PVGIS de l'année type du site (8 760 h, "
    "pente/azimut/pose déclarés) × profil déclaré, heure par heure ; taille par "
    "tranches de 5 kWc jusqu'à l'horizon marginal de 10 ans (D-CIQ-1, D-CIQ-2, D-ACI-18)")
CLES_INTERDITES = frozenset({'prix_achat', 'marge'})
MODES = ('commercial', 'industriel')

#: Lead.type_toiture → type de pose CIQ7 DÉCLARÉ. Fondateur 26/10/2026 : la
#: terrasse béton se pose LESTÉE ; tôle et fibrociment (couvertures en plaques
#: sur pannes, comme le bac acier) prennent la pose bac acier, la plus proche
#: du catalogue — le fibrociment garde son alerte amiante (couverture). Une
#: couverture « autre » reste NON déclarée (pose estimée).
POSE_DU_TOIT_LEAD = {'bac_acier': 'bac_acier', 'tole_metal': 'bac_acier',
                     'fibrociment': 'bac_acier', 'tuiles': 'toiture_inclinee',
                     'terrasse_beton': 'toit_plat_leste'}
#: Lead.type_surface → pose CIQ7 (fondateur 26/10/2026) : une ombrière ou un
#: terrain n'est pas un toit — sa pose prime sur la couverture déclarée.
POSE_DE_LA_SURFACE_LEAD = {'ombriere': 'ombriere', 'terrain': 'sol'}
#: Poses où les panneaux SUIVENT le toit (affleurantes, CIQ112) : la pente et
#: l'orientation du toit y sont celles des panneaux. Ailleurs (toit plat lesté,
#: ombrière, sol) les tables ont leur propre inclinaison : jamais celle du toit.
POSES_SUIVANT_LE_TOIT = ('bac_acier', 'toiture_inclinee')
#: ADEV90 (D-ACI-13=a) — mode de pose ESTIMÉ quand aucun n'est déclaré :
#: terrasse → lestée, toute autre couverture (ou couverture inconnue) →
#: surimposition. La borne s'applique, dite « pose estimée, à confirmer au
#: calepinage ».
POSE_PAR_DEFAUT_COUVERTURE = {'terrasse_beton': 'toit_plat_leste'}
#: CORC5 (27/10/2026, décision prise pour le fondateur, à revoir) — sans
#: couverture connue : une PENTE de toit déclarée ⇒ les panneaux suivent le
#: toit (surimposition) ; sinon la pose que la composition CHIFFRE
#: (``moteur_ci.composition.TYPE_POSE_DEFAUT``, toit plat lesté, fondateur
#: 26/10) — production, borne de toit et prix décrivent la même installation.
POSE_TOIT_INCLINE = 'toiture_inclinee'


def _pose_estimee(res):
    """CORC5 — le mode de pose ESTIMÉ quand aucun n'est déclaré."""
    from apps.ventes.moteur_ci.composition import TYPE_POSE_DEFAUT
    par_couverture = POSE_PAR_DEFAUT_COUVERTURE.get(res.valeur('couverture'))
    if par_couverture:
        return par_couverture
    # Critique Fable (vague 2) : la pente du LEAD vit dans la feuille privée
    # ``_pente_toit`` (recopiée dans ``pente_deg`` seulement quand les
    # panneaux suivent le toit) — elle compte aussi.
    pente = _num(res.valeur('pente_deg'))
    if pente is None:
        pente = _num(res.valeur('_pente_toit'))
    return POSE_TOIT_INCLINE if pente and pente > 0 else TYPE_POSE_DEFAUT


#: (feuille, chemin dans le corps / dans ``Devis.etude_params``).
FEUILLES = (
    ('mode', 'mode'), ('site', 'site'), ('tension', 'tension'),
    ('phases', 'phases'), ('puissance_souscrite_kva', 'puissance_souscrite_kva'),
    ('kwh_mensuels', 'consommation.kwh_mensuels'),
    ('kwh_annuel', 'consommation.kwh_annuel'),
    ('factures_mad', 'consommation.factures_mad'),
    ('registres_mt', 'consommation.registres_mt'),
    ('jours_ouverts', 'rythme.jours_ouverts'), ('plages', 'rythme.plages'),
    ('equipes', 'rythme.equipes'), ('debut_equipe_h', 'rythme.debut_equipe_h'),
    ('fermetures', 'rythme.fermetures'), ('ramadan', 'rythme.ramadan'),
    ('talon', 'rythme.talon'),
    ('categorie_commerciale', 'rythme.categorie_commerciale'),
    ('reponses_categorie', 'rythme.reponses_categorie'),
    ('courbe_mesuree', 'courbe_mesuree'),
    ('type_pose', 'toit.type_pose'), ('surface_utile_m2', 'toit.surface_utile_m2'),
    ('surface_type', 'toit.surface_type'), ('pente_deg', 'toit.pente_deg'),
    ('azimut_deg', 'toit.azimut_deg'), ('couverture', 'toit.couverture'),
    ('charge_admissible_kg_m2', 'toit.charge_admissible_kg_m2'),
    ('charge_admissible_source', 'toit.charge_admissible_source'),
    ('revente_choisie', 'contraintes.revente_choisie'),
    ('nb_points_raccordement', 'contraintes.nb_points_raccordement'),
    ('longueur_dc_m', 'contraintes.longueur_dc_m'),
    ('longueur_ac_m', 'contraintes.longueur_ac_m'),
    ('besoin_cellule_mt', 'contraintes.besoin_cellule_mt'),
    # R3.7 (fondateur, 28/10/2026) — la mise à la terre n'est composée que si
    # elle est dite nécessaire (visite « à créer », ou saisie) : jamais d'office.
    ('mise_a_la_terre_necessaire', 'contraintes.mise_a_la_terre_necessaire'),
    ('tva_recuperable', 'tva_recuperable'),
    ('batterie_souhaitee', 'options.batterie_souhaitee'), ('om', 'options.om'),
    ('taille_explicite_kwc', 'taille_explicite_kwc'),
    # CIQ134 — cos φ déclaré (feuille PRIVÉE : alerte interne seulement).
    ('_cos_phi', 'cos_phi'),
)

#: Chemin du lecteur lead (contrat CIQ1) → feuille de l'étude.
CHEMINS_LEAD = {
    'consommation.kwh_mensuels': 'kwh_mensuel_declare',
    'consommation.factures_mad': 'releve_kwh',
    'consommation.facture_mad': 'facture_hiver_mad',
    'tension': 'tension', 'phases': 'phases',
    'puissance_souscrite_kva': 'puissance_souscrite_kva',
    'rythme.jours_ouverts': 'jours_ouverts', 'rythme.plages': 'plages',
    'rythme.equipes': 'equipes', 'rythme.fermetures': 'fermetures',
    # ADEV76 — heure de début d'un régime 1x8 / 2x8 sans heure de fin, et le
    # secteur industriel (clé du profil société retenu, D-ACI-7=a).
    'rythme.debut_equipe_h': 'debut_equipe_h',
    'rythme.secteur_industriel': 'secteur_industriel',
    'rythme.categorie_commerciale': 'categorie_commerciale',
    'rythme.reponses_categorie': 'reponses_categorie',
    # Décision fondateur 26/10/2026 — talon déclaré par le client (part du mois).
    'rythme.talon': 'talon',
    'toit.surface_utile_m2': 'surface_utile_m2',
    'toit.type_toiture': 'couverture',
    # Feuille PRIVÉE : elle ne sert qu'à choisir la pose (ombrière / sol).
    'toit.type_surface': '_type_surface',
    # Fondateur 26/10/2026 — pente / orientation DU TOIT déclarées au lead :
    # feuilles privées, retenues seulement quand les panneaux suivent le toit.
    'toit.pente_deg': '_pente_toit', 'toit.azimut_deg': '_azimut_toit',
    'tva_recuperable': 'tva_recuperable',
    # CIQ666 — le contrat d'électricité déclaré au lead (vocabulaire CIQ222).
    'tarif_declare': 'tarif_declare',
}

REGIMES_CONTRAT = {
    'declaration_bt': ('declaration', '< 11 kW'),
    'accord_raccordement': ('accord_raccordement', '11 kW – 5 MW'),
    'autorisation_anre': ('autorisation', '≥ 5 MW'),
}
SOURCE_REGIME = ('loi 82-21 + décret 2.25.100 (BO 7489) — déclaration < 11 kW, '
                 'accord de raccordement 11 kW–5 MW, autorisation ≥ 5 MW (D-CIQ-4)')


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
    if isinstance(valeur, Decimal):
        return int(valeur) if valeur == valeur.to_integral_value() else float(valeur)
    if isinstance(valeur, dict):
        return {k: _json(v) for k, v in valeur.items()}
    if isinstance(valeur, (list, tuple)):
        return [_json(v) for v in valeur]
    return valeur


def _sans_cles_interdites(obj):
    if isinstance(obj, dict):
        return {k: _sans_cles_interdites(v) for k, v in obj.items()
                if k not in CLES_INTERDITES}
    if isinstance(obj, list):
        return [_sans_cles_interdites(v) for v in obj]
    return obj


def _lire(arbre, chemin):
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
    return timezone.localdate()


def _date_iso(moment):
    if moment is None:
        return None
    if hasattr(moment, 'date') and callable(moment.date):
        moment = moment.date()
    return moment.isoformat()


def _alerte(code, champ, message, niveau='alerte', interne=True):
    return {'code': code, 'champ': champ, 'message': message,
            'niveau': niveau, 'interne': interne}


def _uniques(*listes, cle=('code', 'champ')):
    vus, sortie = set(), []
    for liste in listes:
        for element in liste or ():
            if not isinstance(element, dict):
                continue
            k = tuple(str(element.get(c)) for c in cle)
            if k in vus:
                continue
            vus.add(k)
            sortie.append(element)
    return sortie


# ── 1. RÉSOLUTION DES ENTRÉES (corps > devis > lead > réglage société) ───────

def _avec_contrat_du_lead(tarif, precedent):
    """CIQ666 — un tarif saisi SANS contrat (prix de facture seuls) garde le
    contrat déclaré par une couche plus basse (le lead) : jamais un contrat
    supposé, seulement celui que le client a déjà déclaré."""
    if (tarif.get('contrat') or not isinstance(precedent, dict)
            or not precedent.get('contrat')):
        return tarif
    fusion = dict(tarif)
    fusion['contrat'] = precedent['contrat']
    if 'option_bi_horaire' in precedent:
        fusion['option_bi_horaire'] = precedent['option_bi_horaire']
    return fusion


class _Resolution:
    """``feuille → (valeur, provenance)`` ; une couche posée PLUS TARD
    (priorité plus haute) remplace la précédente."""

    def __init__(self):
        self.valeurs = {}

    def poser(self, feuille, valeur, provenance):
        if _vide(valeur):
            return
        self.valeurs[feuille] = (valeur, provenance)

    def poser_arbre(self, arbre, provenance):
        if not isinstance(arbre, dict):
            return
        for feuille, chemin in FEUILLES:
            self.poser(feuille, _lire(arbre, chemin), provenance)
        tarif = arbre.get('tarif') if 'tarif' in arbre else arbre.get('tarif_declare')
        if isinstance(tarif, dict) and '$contrat' not in tarif:
            self.poser('tarif_declare', _avec_contrat_du_lead(
                tarif, self.valeur('tarif_declare')), provenance)

    def valeur(self, feuille):
        entree = self.valeurs.get(feuille)
        return entree[0] if entree else None

    def provenance(self, feuille):
        entree = self.valeurs.get(feuille)
        return entree[1] if entree else None

    def entrees_resolues(self):
        return {feuille: {'valeur': _json(v), 'provenance': p}
                for feuille, (v, p) in sorted(self.valeurs.items())
                if not feuille.startswith('_')}


def _fermetures_des_mois(mois_fermes):
    """Mois de fermeture déclarés au lead → ``[{du, au, motif}]`` (CIQ108)."""
    sortie = []
    for m in mois_fermes or ():
        try:
            m = int(m)
        except (TypeError, ValueError):
            continue
        if 1 <= m <= 12:
            dernier = calendar.monthrange(2023, m)[1]
            sortie.append({'du': '%02d-01' % m, 'au': '%02d-%02d' % (m, dernier),
                           'motif': 'mois de fermeture déclaré'})
    return sortie


def _couche_lead(res, lead):
    if lead is None:
        return
    from apps.crm.selectors import entrees_ci_du_lead, ville_effective

    lecture = entrees_ci_du_lead(lead) or {}
    for entree in lecture.get('entrees') or ():
        chemin = entree.get('chemin') or ''
        feuille = CHEMINS_LEAD.get(chemin)
        if feuille is None:
            continue
        prov = entree.get('provenance') or _provenance('lead', 'client')
        valeur = entree.get('valeur')
        if entree.get('colonne') == 'bill_kwh':
            feuille = 'bill_kwh'
        if feuille == 'fermetures':
            valeur = _fermetures_des_mois(valeur)
        res.poser(feuille, valeur, prov)
        sans_toit = res.valeur('_type_surface') in POSE_DE_LA_SURFACE_LEAD
        if feuille == 'couverture' and not sans_toit:
            res.poser('type_pose', POSE_DU_TOIT_LEAD.get(valeur), prov)
        if feuille == '_type_surface':
            res.poser('type_pose', POSE_DE_LA_SURFACE_LEAD.get(valeur), prov)
        if feuille == 'surface_utile_m2':
            res.poser('surface_type', 'declaree', prov)
    if (res.valeur('type_pose') or _pose_estimee(res)) in POSES_SUIVANT_LE_TOIT:
        for prive, feuille in (('_pente_toit', 'pente_deg'), ('_azimut_toit', 'azimut_deg')):
            res.poser(feuille, res.valeur(prive), res.provenance(prive))
    # CIQ134 — cos φ DÉCLARÉ (information du lead, avec sa provenance) :
    # feuille PRIVÉE (``_``) — il ne sert qu'à l'alerte interne de
    # ``moteur_ci.reactif``, jamais aux entrées résolues ni au client.
    for info in lecture.get('informations') or ():
        if isinstance(info, dict) and info.get('colonne') == 'cos_phi':
            res.poser('_cos_phi', _num(info.get('valeur')),
                      info.get('provenance') or _provenance('lead', 'client'))
    mode = getattr(lead, 'type_installation', None)
    date = _date_iso(getattr(lead, 'date_creation', None))
    prov = _provenance('lead', 'client', date)
    if mode in MODES:
        res.poser('mode', mode, prov)
    site = {'ville': ville_effective(lead) or None,
            'lat': _num(getattr(lead, 'gps_lat', None)),
            'lon': _num(getattr(lead, 'gps_lng', None))}
    if any(v is not None for v in site.values()):
        res.poser('site', site, prov)
    # Garde « kWh déclaré contre factures » (décision du 30/09) : la facture
    # d'hiver est lue même quand le kWh déclaré prime.
    res.poser('_facture_hiver_lead', _num(getattr(lead, 'facture_hiver', None)), prov)


def _couche_devis(res, devis):
    if devis is None:
        return
    etude = getattr(devis, 'etude_params', None)
    if not isinstance(etude, dict):
        return
    res.poser_arbre(etude, _provenance('devis', None, _date_iso(
        getattr(devis, 'updated_at', None))))


def _couche_corps(res, corps):
    if isinstance(corps, dict):
        res.poser_arbre(corps, _provenance('saisie', None, _aujourdhui().isoformat()))


def resoudre_entrees(entrees, *, devis=None, lead=None):
    res = _Resolution()
    _couche_lead(res, lead)
    _couche_devis(res, devis)
    _couche_corps(res, entrees)
    return res


# ── 2. CONSOMMATION, résolue UNE fois ────────────────────────────────────────

def _facture_bt_ttc(kwh, tarif, tarif_declare):
    """Énergie TTC d'un mois de ``kwh`` au tarif BT à tranches (lecture
    progressive, mêmes seuils que la valorisation CIQ204)."""
    from apps.ventes import tarif_ci
    postes = tarif.get('tarifs_par_poste') or []
    seuils = tarif_ci._seuils_bt(tarif, tarif_declare)
    if not postes or seuils is None or len(seuils) != len(postes):
        return None
    total, reste, bas = 0.0, kwh, 0.0
    for (_lo, hi), poste in zip(seuils, postes):
        largeur = reste if hi is None else max(0.0, min(reste, float(hi) - bas))
        total += largeur * float(poste['tarif_kwh_ttc'])
        reste -= largeur
        bas = float(hi) if hi is not None else bas
        if reste <= 0:
            break
    return total if reste <= 1e-9 else None


def _kwh_depuis_mad(montant_ttc, tarif, tarif_declare):
    """Inverse (dichotomie) de :func:`_facture_bt_ttc` ; ``None`` sans tarif BT."""
    if tarif.get('contrat') == 'mt_general' or tarif.get('origine') == 'omis':
        return None
    if _facture_bt_ttc(1.0, tarif, tarif_declare) is None:
        return None
    bas, haut = 0.0, 1000.0
    while (_facture_bt_ttc(haut, tarif, tarif_declare) or 0) < montant_ttc and haut < 1e8:
        haut *= 2
    for _ in range(60):
        milieu = (bas + haut) / 2
        if (_facture_bt_ttc(milieu, tarif, tarif_declare) or 0) < montant_ttc:
            bas = milieu
        else:
            haut = milieu
    return round(bas, 1)


def _consommation(res, tarif, alertes, hypotheses):
    """``(kwh_mensuels [12] | kwh annuel | None, feuille_retenue)``."""
    kwh = res.valeur('kwh_mensuels')
    if isinstance(kwh, (list, tuple)) and len(kwh) == 12 and all(
            _num(v) is not None for v in kwh):
        return [_num(v) for v in kwh], 'kwh_mensuels'
    unique = _num(res.valeur('kwh_mensuel_declare'))
    if unique and unique > 0:
        return [unique] * 12, 'kwh_mensuel_declare'
    annuel = _num(res.valeur('kwh_annuel'))
    if annuel and annuel > 0:
        return annuel, 'kwh_annuel'
    partiel = None
    for feuille in ('factures_mad', 'releve_kwh'):
        lignes = res.valeur(feuille)
        if isinstance(lignes, list):
            par_mois = {}
            for ligne in lignes:
                if not isinstance(ligne, dict) or _num(ligne.get('kwh')) is None:
                    continue
                mois = str(ligne.get('mois') or '')
                try:
                    numero = int(mois.split('-')[-1])
                except ValueError:
                    continue
                if 1 <= numero <= 12:
                    par_mois[numero] = _num(ligne['kwh'])
            if len(par_mois) == 12:
                return [par_mois[m] for m in range(1, 13)], feuille
            if par_mois and partiel is None:
                partiel = (par_mois, feuille)
    bill = _num(res.valeur('bill_kwh'))
    if partiel is not None and not (bill and bill > 0):
        # ADEV77 (D-ACI-1=b) — relevé de n < 12 mois DISTINCTS et aucun autre
        # kWh : moyenne des mois relevés × 12, étiquetée estimation.
        par_mois, feuille = partiel
        moyenne = sum(par_mois.values()) / len(par_mois)
        hypotheses.append({
            'cle': 'consommation', 'valeur': round(moyenne * 12, 1),
            'statut': 'estimation',
            'source': 'relevé partiel (%d mois)' % len(par_mois)})
        return [moyenne] * 12, feuille
    td = res.valeur('tarif_declare')
    lignes = res.valeur('factures_mad')
    montants = {}
    if isinstance(lignes, list):
        for ligne in lignes:
            if isinstance(ligne, dict) and _num(ligne.get('montant_ttc')):
                try:
                    montants[int(str(ligne.get('mois')).split('-')[-1])] = _num(
                        ligne['montant_ttc'])
                except ValueError:
                    continue
    hiver = _num(res.valeur('facture_hiver_mad'))
    if len(montants) == 12 or hiver:
        convertis = []
        for m in range(1, 13):
            mad = montants.get(m, hiver) if len(montants) == 12 else hiver
            convertis.append(_kwh_depuis_mad(mad, tarif, td))
        if all(v is not None for v in convertis):
            hypotheses.append({
                'cle': 'consommation', 'valeur': None, 'statut': 'estimation',
                'source': 'factures MAD converties au tarif C&I (%s)' % (
                    tarif.get('mention') or tarif.get('origine'))})
            return convertis, 'factures_mad' if montants else 'facture_hiver_mad'
        alertes.append(_alerte(
            'conversion_mad_impossible', 'consommation.factures_mad',
            'Facture en MAD sans tarif BT sourcé applicable : aucune conversion en '
            'kWh (jamais un prix moyen supposé).'))
    if bill and bill > 0:
        hypotheses.append({'cle': 'consommation', 'valeur': bill, 'statut': 'estimation',
                           'source': 'bill_kwh (lecture seule, QJR662)'})
        return [bill] * 12, 'bill_kwh'
    return None, None


def _registres_resolus(res):
    """CIQ132 — les 12 registres MT (corps / devis, sinon relevé du lead), ou
    ``None``. Jamais exigés (D-QJR5-14)."""
    from apps.ventes.moteur_ci.charge import registres_lisibles
    registres = res.valeur('registres_mt')
    if registres_lisibles(registres):
        return list(registres)
    releve = res.valeur('releve_kwh')
    if isinstance(releve, list):
        par_mois = {}
        for ligne in releve:
            if not isinstance(ligne, dict):
                continue
            try:
                par_mois[int(str(ligne.get('mois')).split('-')[-1])] = ligne
            except ValueError:
                continue
        candidats = [par_mois.get(m) for m in range(1, 13)]
        if registres_lisibles(candidats):
            return candidats
    return None


def _courbe_mesuree_resolue(courbe, annee_reference):
    """CIQ133 — ``(valeurs horaires, début, source)`` d'une courbe MESURÉE, ou
    ``None``. Un fichier passe par LE parseur du calepinage (façade
    ``apps.calepinage.services.apercu_courbe_csv``) : aucun second lecteur.
    Fichier illisible ⇒ 400 FR nommant la colonne (message du parseur)."""
    if not isinstance(courbe, dict):
        return None
    from rest_framework.exceptions import ValidationError
    source = courbe.get('source')
    debut = courbe.get('debut') or courbe.get('date_debut')
    if isinstance(courbe.get('contenu'), str) and courbe['contenu'].strip():
        from apps.calepinage import services as calepinage_services
        try:
            apercu = calepinage_services.apercu_courbe_csv(
                courbe['contenu'], colonne=courbe.get('colonne'),
                unite=courbe.get('unite') or 'kwh', origine=source or '')
        except calepinage_services.ImportCourbeInvalide as erreur:
            raise ValidationError({'courbe_mesuree': [erreur.motif],
                                   'champ': erreur.champ or 'fichier'})
        return apercu['valeurs'], debut or '%d-01-01' % annee_reference, source
    points = courbe.get('points')
    if not isinstance(points, list) or not points:
        return None
    from apps.ventes.moteur_ci.charge import valeurs_horaires_depuis_points
    try:  # CLD6 — tout pas diviseur de 60 min agrégé à l'heure, refus nommé sinon
        valeurs = valeurs_horaires_depuis_points(
            [_num(p) or 0.0 for p in points], pas_min=courbe.get('pas_minutes') or 60,
            unite=courbe.get('unite') or 'kwh')
    except ValueError as erreur:
        raise ValidationError({'courbe_mesuree': [str(erreur)]})
    return valeurs, debut, source


def _garde_kwh_factures(res, tarif, alertes):
    """Décision du 30/09 : un kWh déclaré qui contredit la facture (> 2×) bloque."""
    from apps.ventes.horaire.conso import RATIO_KWH_FACTURE_MAX, RATIO_KWH_FACTURE_MIN
    kwh = _num(res.valeur('kwh_mensuel_declare'))
    # ADEV100 (L3, 24/10/2026) — le générateur pré-rempli envoie le kWh du lead
    # en ANNUEL (12 × mensuel) ou en 12 mois : la décision du 30/09 vaut pour
    # tout kWh déclaré, pas seulement pour la feuille mensuelle du lead.
    if not kwh:
        annuel = _num(res.valeur('kwh_annuel'))
        mensuels = [_num(v) for v in (res.valeur('kwh_mensuels') or [])]
        mensuels = [v for v in mensuels if v]
        if annuel:
            kwh = annuel / 12.0
        elif len(mensuels) == 12:
            kwh = sum(mensuels) / 12.0
    facture = _num(res.valeur('_facture_hiver_lead'))
    if not kwh or not facture:
        return
    tarife = _facture_bt_ttc(kwh, tarif, res.valeur('tarif_declare'))
    if tarife is None:
        return
    ratio = tarife / facture
    if not (RATIO_KWH_FACTURE_MIN <= ratio <= RATIO_KWH_FACTURE_MAX):
        alertes.append(_alerte(
            'kwh_incoherent_factures', 'consommation.kwh_mensuels',
            'Le kWh déclaré (%.0f kWh/mois) contredit la facture déclarée (%.0f MAD) : '
            'à corriger sur le lead avant le devis.' % (kwh, facture), niveau='bloquant'))


# ── 3. LECTURES : production, profil société, catalogue ──────────────────────

def lire_production(site, toit=None):
    """``(productible_mensuel, formes_saison, source, serie)`` ou ``None`` (PVGIS).

    AMOT99 — ``serie`` : l'année type HORAIRE au plan de ``toit``, au point
    GPS du site, sinon (CORC12) au point de sa ville au gazetier ; sinon
    ``None`` (repli dit, hypothèse ``methode_autoconsommation``)."""
    from apps.parametres.pvgis_profils import productible_mensuel

    from ..etude_horaire import _formes_production_par_saison

    site = site or {}
    ville, lat, lon = site.get('ville'), _num(site.get('lat')), _num(site.get('lon'))
    try:
        formes, _source = _formes_production_par_saison(ville=ville, lat=lat, lon=lon)
        mensuel = productible_mensuel(ville=ville, lat=lat, lon=lon)
    except Exception:  # réseau PVGIS : étude omise, avertissement nommé
        logger.warning('CIQ118 — PVGIS indisponible', exc_info=True)
        return None
    if not formes or not mensuel:
        return None
    productibles, source = mensuel
    # CORC12 (27/10/2026, constat CMP) — sans GPS déclaré, la série horaire
    # se calcule au point de la VILLE au gazetier (ville inconnue ⇒ repli dit
    # sur les journées moyennes).
    return productibles, formes, source, _serie_horaire(*_point_du_site(site), toit)


def _serie_horaire(lat, lon, toit):
    if lat is None or lon is None:
        return None
    from apps.parametres.pvgis_profils import serie_horaire_annee_type
    from apps.ventes.moteur_ci.production import plan_de_production
    plan = plan_de_production(toit)
    try:
        serie = serie_horaire_annee_type(lat, lon, angle_deg=plan['angle_deg'],
                                         aspect_deg=plan['aspect_deg'], montage=plan['montage'])
    except Exception:  # noqa: BLE001 — série absente : repli dit, jamais l'étude omise
        logger.warning('AMOT99 — série horaire PVGIS indisponible', exc_info=True)
        return None
    return dict(serie, plan=plan) if serie else None


def _toit_declare(res):
    """``(toit déclaré, toit de la série horaire)`` — AMOT99 : le plan de la série
    prend la pose déclarée, sinon la pose estimée D-ACI-13."""
    toit = {'type_pose': res.valeur('type_pose'), 'pente_deg': res.valeur('pente_deg'),
            'azimut_deg': res.valeur('azimut_deg')}
    pose = toit['type_pose'] or _pose_estimee(res)
    return toit, dict(toit, type_pose=pose)


def _profil_societe(company, mode, cle):
    """Profil SAISI par la société (famille du mode), par la façade calepinage.

    ADEV76 (D-ACI-7=a) — retenu SEULEMENT si sa clé = ``cle`` (catégorie
    commerciale, ou secteur industriel déclaré du lead) : jamais le premier
    profil venu à la place de l'archétype ou d'un profil déclaré exigé."""
    if company is None or _vide(cle):
        return None
    from apps.calepinage import services as calepinage_services
    try:
        profils = calepinage_services.profils_de_societe(company, inclure_replis=False)
    except Exception:  # lecture best-effort : l'archétype sourcé prend le relais
        logger.warning('CIQ118 — profils société illisibles', exc_info=True)
        return None
    choisi = next((p for p in profils
                   if p.get('famille') == mode and p.get('cle') == cle), None)
    if choisi is None:
        return None
    return {'cle': choisi.get('cle'), 'libelle': choisi.get('libelle'),
            'courbe': choisi.get('courbes'), 'provenance': choisi.get('provenance')}


def lire_catalogue_ci(company):
    """Catalogue C&I (``stock.selectors.produits_ci``) + prix de VENTE HT du
    catalogue de la société + module retenu. Jamais ``prix_achat``."""
    from apps.calepinage.services.chaines import specs_module, specs_onduleur
    from apps.stock.selectors import produits_ci, specs_for_produit
    from core.product_roles import ROLES_CI_BAREME_COFFRET, ROLES_ONDULEUR_CI

    from ..compatibilites import est_triphase_produit
    from .catalogue import catalogue_de_la_societe, classer_produit

    objets = {p.id: p for p in catalogue_de_la_societe(company)}
    elements = []
    for element in produits_ci(company):
        produit = objets.get(element['id'])
        if produit is not None and produit.prix_vente and produit.prix_vente > 0:
            element = dict(element, prix_vente_ht=produit.prix_vente,
                           paliers_prix_vente=list(
                               getattr(produit, 'paliers_prix_vente', None) or []),
                           # ADEV79 — la TVA de l'article (TTC des paliers → HT).
                           tva_pct=getattr(produit, 'tva', None))
        if produit is not None and element.get('role_ci') in ROLES_CI_BAREME_COFFRET and (
                produit.prix_fixe_ht is not None or produit.prix_par_panneau_ht is not None):
            # Coffret au barème (26/10/2026) : par onduleur + par panneau.
            element = dict(element, bareme_coffret={
                'par_onduleur_ht': produit.prix_fixe_ht,
                'par_panneau_ht': produit.prix_par_panneau_ht})
        elements.append(element)

    onduleurs = []
    for element in elements:
        # ADEV86 (D-ACI-3=b) — triphasés ET monophasés : la combinaison ne
        # garde que ceux de la phase du site.
        if element.get('role_ci') not in ROLES_ONDULEUR_CI:
            continue
        produit = objets.get(element['id'])
        specs = {}
        if produit is not None:
            try:
                specs = specs_for_produit(produit) or {}
            except Exception:  # fiche illisible : candidat sans spécifs
                logger.warning("etude_ci.lire_catalogue_ci : erreur ignorée (mode dégradé)", exc_info=True)
                specs = {}
        onduleurs.append({
            'produit': element['id'], 'nom': element.get('nom'),
            'kw_ac': (element.get('fiche') or {}).get('ond_ac_kw') or specs.get('ac_kw'),
            'prix': element.get('prix_vente_ht'),
            'triphase': est_triphase_produit(produit) if produit is not None else None,
            'role_ci': element.get('role_ci'),
            'phases': (element.get('fiche') or {}).get('ond_phases'),
            'eligible_ci': element.get('eligible_ci'),
            'motif_exclusion': element.get('motif_exclusion'),
            'dc_max_kwc': specs.get('dc_max_kwc'),
            's_max_kva': specs.get('s_max_kva'),
            # Demande CMP (27/10/2026) : chaînes par entrée MPPT publiées par la
            # fiche, lues d'abord par le concepteur de chaînes (facultatif).
            'chaines_max_par_mppt': specs.get('chaines_max_par_mppt'),
            # ADEV87 — la fiche électrique (chaînes), ``None`` si incomplète.
            'spec': specs_onduleur(specs, element.get('nom') or '')[0] if specs else None,
        })

    module = module_spec = None
    candidats = []
    for produit in objets.values():
        role = getattr(produit, 'role_devis', None) or classer_produit(produit.nom)
        if role != 'panneau':
            continue
        try:
            specs = specs_for_produit(produit) or {}
        except Exception:  # fiche illisible
            logger.warning("etude_ci.lire_catalogue_ci : erreur ignorée (mode dégradé)", exc_info=True)
            specs = {}
        pmax = _num(specs.get('pmax_wc'))
        prix = bool(produit.prix_vente and produit.prix_vente > 0)
        # ADEV78 — un module à puissance PUBLIÉE passe devant un module tarifé
        # sans Pmax (sans Pmax, aucun panneau ne se compte).
        candidats.append(((bool(pmax), prix, pmax or 0, -produit.id), produit, specs))
    if candidats:
        _cle, produit, specs = max(candidats, key=lambda c: c[0])
        module = {
            'produit': produit.id, 'designation': produit.nom,
            'pmax_wc': _num(specs.get('pmax_wc')),
            'prix_connu': bool(produit.prix_vente and produit.prix_vente > 0),
            'prix_vente_ht': produit.prix_vente,
            'tva_pct': getattr(produit, 'tva', None),
            # ADEV82 — le module porte aussi ses paliers (prix de la taille).
            'paliers_prix_vente': list(getattr(produit, 'paliers_prix_vente', None) or []),
            'longueur_mm': _num(specs.get('longueur_mm')),
            'largeur_mm': _num(specs.get('largeur_mm')),
            'poids_kg': _num(specs.get('poids_kg')),
        }
        # ADEV87 — la fiche électrique du module retenu (chaînes).
        module_spec = specs_module(specs, produit.nom)[0] if specs else None
    prix_par_id = {e['id']: e['prix_vente_ht'] for e in elements if e.get('prix_vente_ht')}
    if module and module.get('prix_vente_ht'):
        prix_par_id[module['produit']] = module['prix_vente_ht']
    # Fondateur 26/10/2026 — hybrides BT et batteries de l'option « avec ».
    from .etude_ci_batterie import catalogue_batterie_ci
    return {'elements': elements, 'onduleurs': onduleurs, 'module': module,
            'module_spec': module_spec, 'prix_par_id': prix_par_id,
            'batterie': catalogue_batterie_ci(objets.values())}


def _reglages_societe(company):
    if company is None:
        return None
    from apps.parametres.models import CompanyProfile
    return CompanyProfile.objects.filter(company=company).first()


# ── 4. TOIT ──────────────────────────────────────────────────────────────────

def _point_du_site(site):
    """``(lat, lon)`` : le GPS déclaré du site, sinon (CORC12) le point de sa
    VILLE au gazetier (``parametres.villes_maroc.coordonnees_ville`` — la
    ville que PVGIS lit aussi). Jamais une position devinée : ville inconnue
    ⇒ ``(None, None)``. Sert la série horaire, la borne lestée (espacement
    anti-ombrage) et les coordonnées FIGÉES de l'étude."""
    site = site or {}
    lat, lon = _num(site.get('lat')), _num(site.get('lon'))
    if lat is not None and lon is not None:
        return lat, lon
    from apps.parametres.villes_maroc import coordonnees_ville
    coords = coordonnees_ville(site.get('ville') or '')
    return (coords[0], coords[1]) if coords else (None, None)


def _borne_toit(res, devis, module, alertes):
    pmax = (module or {}).get('pmax_wc')
    if devis is not None and pmax:
        from .dimensionnement_devis import contenance_toit_du_devis
        try:
            nb = contenance_toit_du_devis(devis)
        except Exception:  # géométrie illisible : on retombe sur la surface
            logger.warning('CIQ118 — contenance du devis illisible', exc_info=True)
            nb = None
        if nb:
            return {'kwc': round(nb * pmax / 1000.0, 2),
                    'source': 'contenance mesurée du calepinage du devis (%d panneaux)' % nb}
    surface = _num(res.valeur('surface_utile_m2'))
    if surface is None:
        return None
    from apps.calepinage import services as calepinage_services
    from apps.parametres.pvgis_profils import PVGIS_ANGLE_DEG
    from apps.ventes.moteur_ci.production import ANGLE_POSE_RASANTE_DEG, bascule_rasante_admissible
    module = module or {}
    cotes = None
    if module.get('longueur_mm') and module.get('largeur_mm'):
        cotes = (module['longueur_mm'] / 1000.0, module['largeur_mm'] / 1000.0)
    pente = _num(res.valeur('pente_deg'))
    site = res.valeur('site') or {}
    mode_pose = res.valeur('type_pose')
    pose_estimee = not mode_pose
    if pose_estimee:
        mode_pose = _pose_estimee(res)
    resultat = calepinage_services.contenance_surface_declaree(
        surface, mode_pose=mode_pose, cotes_module_m=cotes,
        inclinaison_deg=pente if pente is not None else PVGIS_ANGLE_DEG,
        latitude_deg=_point_du_site(site)[0], puissance_module_wc=pmax)
    if resultat.get('kwc') is None:
        alertes.append(_alerte('contenance_toit_inconnue', 'toit',
                               'Contenance du toit non bornée : %s.' % resultat.get('motif')))
        return None
    source = 'surface utile déclarée (%g m²) — estimation, à confirmer au calepinage/visite' % surface
    if pose_estimee:
        source = ('surface utile déclarée (%g m²), pose estimée « %s » — estimation, à '
                  'confirmer au calepinage/visite' % (surface, mode_pose))
    borne = {'kwc': round(float(resultat['kwc']), 2), 'source': source}
    if not bascule_rasante_admissible({'type_pose': mode_pose, 'pente_deg': pente}):
        return borne
    if devis is not None and not regles_au_moins(devis, REGLES_CORRIGEES_2710):
        # R1 (P5) — devis aux règles ≤ 2 : ni bascule rasante, ni borne
        # maximale, ni disparition de « taille au-delà du toit » (devis envoyés
        # intouchés) ; sans devis (aperçu) la règle s'applique.
        return borne
    # R1 (fondateur 28/10/2026) — toit plat SANS pente déclarée : la borne est
    # la configuration qui pose le PLUS de panneaux ; les deux contenances
    # (30° par défaut, pose rasante 10° jointive) viennent du MÊME service.
    rasante = calepinage_services.contenance_surface_declaree(
        surface, mode_pose=mode_pose, cotes_module_m=cotes,
        inclinaison_deg=ANGLE_POSE_RASANTE_DEG, latitude_deg=_point_du_site(site)[0],
        puissance_module_wc=pmax, pose_rasante=True)
    if rasante.get('kwc') is None:
        return borne
    kwc_30, kwc_10 = borne['kwc'], round(float(rasante['kwc']), 2)
    borne.update({
        'kwc': max(kwc_30, kwc_10), 'kwc_30': kwc_30, 'kwc_10': kwc_10, 'surface_m2': surface,
        'source_30': ('tables à %g° sur la surface déclarée (défaut toit plat, décision '
                      'fondateur du 27/10/2026)' % PVGIS_ANGLE_DEG),
        'source_10': ('tables jointives en pose rasante %g° sur la surface déclarée (décision '
                      'fondateur du 28/10/2026)' % ANGLE_POSE_RASANTE_DEG),
    })
    return borne


def _serie_rasante(site, toit_serie, toit_declare, production, *, figee, bloc_figee=None,
                   source_figee=None):
    """R1 — la production en pose rasante 10° (même chaîne PVGIS, série au
    plan rasant), lue PARESSEUSEMENT au premier palier qui ne tient pas à
    30° : ``{'lire': appelable | None}`` puis, une fois lue, ``bloc``,
    ``hypotheses``, ``alertes``. Production figée (CIQ119) : PVGIS n'est
    jamais rappelé — seule la série rasante FIGÉE du devis
    (``production_figee_rasante``, B2) sert, avec ses traces ; ni une pente
    déclarée, ni une autre pose (``toit_rasant``) n'ouvrent de seconde série."""
    from apps.ventes.moteur_ci.production import (
        bloc_production_ci, plan_de_production, production_pour_bilan, toit_rasant,
        traces_production,
    )
    from apps.ventes.quote_engine.pricing import PRODUCTION_DERATE
    etat = {'lire': None}
    if figee:
        if bloc_figee and toit_rasant(toit_serie) is not None:
            hyp, al = traces_production(bloc_figee, source=source_figee, toit=toit_declare)
            etat.update(bloc=bloc_figee, hypotheses=hyp, alertes=al,
                        lire=lambda: production_pour_bilan(bloc_figee))
        return etat
    rasant = toit_rasant(toit_serie)
    if rasant is None:
        return etat

    def lire():
        if 'bloc' not in etat:
            etat['bloc'] = None
            lecture = lire_production(site, toit=rasant)
            if lecture:
                prod_r, formes_r, source_r, serie_r = (tuple(lecture) + (None,))[:4]
                bloc, hyp, al = bloc_production_ci(
                    productible_mensuel=prod_r, formes_saison=formes_r, derate=PRODUCTION_DERATE,
                    coordonnees_figees=dict(production.get('coordonnees_figees') or {}),
                    source=source_r, toit=toit_declare, serie=serie_r,
                    plan=(serie_r or {}).get('plan') or plan_de_production(rasant))
                if bloc is not None:
                    etat.update(bloc=bloc, hypotheses=hyp, alertes=al)
        return production_pour_bilan(etat['bloc']) if etat.get('bloc') else None
    etat['lire'] = lire
    return etat


def _servir_pose_rasante(resultat, rasante, production, alertes, hypotheses, traces_30):
    """R1 — la taille retenue est logée en pose rasante : le bloc production
    servi (et ses traces) est celui de cette inclinaison ; sinon la
    production telle quelle."""
    from apps.ventes.moteur_ci.production import ANGLE_POSE_RASANTE_DEG
    if resultat.get('inclinaison_retenue_deg') != ANGLE_POSE_RASANTE_DEG or not rasante.get('bloc'):
        return production
    al_prod, hyp_prod = traces_30
    _remplacer(alertes, al_prod, rasante['alertes'])
    _remplacer(hypotheses, hyp_prod, rasante['hypotheses'])
    return rasante['bloc']


def verdict_taille_creation(etude):
    """R1 (B1, arbitrage coordinatrice 28/10/2026) — le verdict de taille
    CALCULÉ par le balayage à la création d'un devis (``taille_creation_ci``
    de ``etude_params``) : raison d'arrêt, inclinaison retenue, contenances
    du toit, phrase « limitée par le toit ». ``None`` pour une taille saisie
    (jamais « limitée par le toit ») ou sans taille."""
    taille = (etude or {}).get('taille') or {}
    if taille.get('retenue_kwc') is None or taille.get('raison_arret') == 'taille_explicite':
        return None
    toit = (taille.get('bornes') or {}).get('toit') or {}
    return {'retenue_kwc': taille['retenue_kwc'], 'nb_panneaux': taille.get('nb_panneaux'),
            'raison_arret': taille.get('raison_arret'),
            'inclinaison_retenue_deg': taille.get('inclinaison_retenue_deg'),
            'taille_limitee_toit': taille.get('taille_limitee_toit'),
            'toit': {k: toit.get(k) for k in ('kwc', 'kwc_30', 'kwc_10', 'surface_m2')}}


def _relire_verdict_toit(taille, verdict, hypotheses):
    """R1 (B1) — l'étude STOCKÉE est rafraîchie depuis les LIGNES (taille
    explicite) : le verdict « limitée par le toit » calculé à la création est
    relu tant que les lignes (kWc retenu) et le toit (contenances, surface,
    pose retenue) n'ont pas changé ; sinon rien — une taille saisie à la main
    n'imprime jamais la phrase."""
    if not isinstance(verdict, dict) or not taille or not verdict.get('taille_limitee_toit') \
            or taille.get('raison_arret') != 'taille_explicite':
        return
    toit = (taille.get('bornes') or {}).get('toit') or {}
    toit_creation = verdict.get('toit') or {}
    meme_toit = all(_num(toit.get(k)) == _num(toit_creation.get(k))
                    for k in ('kwc_30', 'kwc_10', 'surface_m2'))
    if not meme_toit or _num(verdict.get('retenue_kwc')) != _num(taille.get('retenue_kwc')) \
            or _num(verdict.get('inclinaison_retenue_deg')) != _num(taille.get('inclinaison_retenue_deg')):
        return
    taille['taille_limitee_toit'] = verdict['taille_limitee_toit']
    hypotheses.append({'cle': 'taille_limitee_toit', 'valeur': taille['retenue_kwc'],
                       'statut': 'estimation', 'source': verdict['taille_limitee_toit']})


def _traces_evaluation(evaluation, alertes, hypotheses):
    """Les alertes et hypothèses portées par l'évaluation retenue (bilan,
    composition, combinaison d'onduleurs)."""
    composition = evaluation['composition']
    alertes.extend(evaluation['alertes_bilan'])
    alertes.extend(composition.get('alertes') or [])
    alertes.extend((evaluation['onduleurs'] or {}).get('alertes') or [])
    hypotheses.extend(composition.get('hypotheses') or [])


def _remplacer(liste, anciens, nouveaux):
    """Retire de ``liste`` (en place) les éléments ``anciens`` (identité) et
    ajoute ``nouveaux`` — ``_uniques`` garde le PREMIER d'une clé."""
    liste[:] = [x for x in liste if not any(x is a for a in anciens)] + list(nouveaux or ())


def _charge_toiture(res, catalogue, alertes):
    from apps.ventes.roof_load import ChargeNonSourcee, verifier_charge_toiture
    module = catalogue.get('module') or {}
    aire = None
    if module.get('longueur_mm') and module.get('largeur_mm'):
        aire = module['longueur_mm'] * module['largeur_mm'] / 1e6
    type_pose = res.valeur('type_pose')
    structure = next((e for e in catalogue['elements']
                      if e.get('role_ci') == 'structure_ci'
                      and (e.get('type_pose') or (e.get('fiche') or {}).get(
                          'struct_type_pose')) == type_pose), None)
    try:
        resultat = verifier_charge_toiture(
            charge_admissible_kg_m2=res.valeur('charge_admissible_kg_m2'),
            charge_admissible_source=res.valeur('charge_admissible_source'),
            struct_masse_kg_m2=((structure or {}).get('fiche') or {}).get('struct_masse_kg_m2'),
            poids_module_kg=module.get('poids_kg'), aire_module_m2=aire,
            couverture=res.valeur('couverture'))
    except ChargeNonSourcee as erreur:
        alertes.append(_alerte('charge_toiture_non_sourcee', 'toit.charge_admissible_source',
                               str(erreur), niveau='bloquant'))
        return
    alertes.extend(resultat.get('alertes') or [])
    if resultat.get('message'):
        alertes.append(_alerte('charge_toiture', 'toit.charge_admissible_kg_m2',
                               resultat['message'], niveau='info'))


# ── 5. ASSEMBLAGE ────────────────────────────────────────────────────────────

def _sous_reserve_visite(res, lead, niveau_donnees):
    motifs = []
    if lead is not None:
        from apps.crm.services import visite_pro_avant_devis
        bloc = visite_pro_avant_devis(lead)
        if bloc:
            motifs.extend(bloc.get('motifs') or [])
    else:
        tension = res.valeur('tension')
        if tension == 'mt':
            motifs.append('site MT : visite avant le devis final (D-CIQ-5)')
        elif tension in (None, 'inconnue'):
            motifs.append('tension de raccordement inconnue')
        if _num(res.valeur('puissance_souscrite_kva')) is None:
            motifs.append('puissance souscrite inconnue')
        if _num(res.valeur('surface_utile_m2')) is None:
            motifs.append('surface disponible inconnue')
    if niveau_donnees == 'estimation':
        motifs.append('profil horaire non déclaré : estimation sous réserve de visite')
    return {'valeur': bool(motifs), 'motif': '; '.join(motifs) if motifs else None}


def _regime(kwc, puissance_ac, tension):
    from core.reglementaire.regime_8221 import regime_8221
    forme = regime_8221(puissance_dc_kwc=kwc, puissance_ac_kw=puissance_ac or None,
                        niveau=(tension or '').upper() if tension in ('bt', 'mt') else None)
    regime, seuil = REGIMES_CONTRAT.get(forme.get('code'), (None, None))
    return {'regime': regime, 'seuil': seuil, 'source': SOURCE_REGIME}


def _completer_prix(composition, prix_par_id, tva_defaut=None):
    """Les lignes dont l'article a un prix de vente connu mais que la
    composition n'a pas chiffré (panneau) reçoivent ce prix unitaire HT.
    ADEV82 — une ligne au prix de PALIER porte le HT de ce palier (même règle
    que la taille, ``moteur_ci.taille.prix_palier_ht``) : taille et devis au
    même prix."""
    from apps.ventes.moteur_ci.composition import prix_palier_ht
    for ligne in composition.get('lignes') or []:
        prix = prix_par_id.get(ligne.get('produit'))
        if prix is not None and not ligne.get('prix_unitaire_ht') \
                and ligne.get('role') != 'onduleur_string_tri':
            ligne['prix_unitaire_ht'] = str(prix)
            ligne['prix_connu'] = True
            if ligne.get('motif') and 'prix' in ligne['motif']:
                ligne['motif'] = None
        palier_ht = prix_palier_ht(ligne, tva_defaut)
        if palier_ht is not None and ligne.get('role') != 'onduleur_string_tri':
            ligne['prix_unitaire_ht'] = str(palier_ht)
    from apps.ventes.moteur_ci.composition import postes_non_chiffres
    a_renseigner, visite = postes_non_chiffres(composition.get('lignes'))
    composition['prix_a_renseigner'] = a_renseigner
    composition['a_chiffrer_visite'] = visite
    composition['incomplet'] = bool(a_renseigner or visite)
    return composition


def _alertes_reactif(res, tension, bilan, registres):
    """CIQ134 — alerte INTERNE de facteur de puissance après PV (MT), par
    ``moteur_ci.reactif`` (la seule formule) : kWh et autoconsommé du bilan
    mensuel, kvarh / cos φ des registres MT déclarés, sinon cos φ déclaré
    avec sa provenance. Rien de déclaré ⇒ la note seule ; BT ⇒ rien."""
    from apps.ventes.moteur_ci.reactif import evaluer_reactif
    par_mois = sorted((m for m in (bilan or {}).get('par_mois') or ()
                       if isinstance(m, dict)), key=lambda m: m.get('mois') or 0)
    regs = list(registres or ())
    regs += [None] * (len(par_mois) - len(regs))
    return evaluer_reactif(
        tension=tension,
        kwh_mensuels=[m.get('consommation_kwh') for m in par_mois],
        autoconso_mensuels=[m.get('autoconso_kwh') for m in par_mois],
        kvarh_mensuels=[(r or {}).get('kvarh') if isinstance(r, dict) else None
                        for r in regs],
        cos_phi_mensuels=[(r or {}).get('cos_phi') if isinstance(r, dict) else None
                          for r in regs],
        cos_phi_declare=res.valeur('_cos_phi'),
        provenance_cos_phi=res.provenance('_cos_phi'))['alertes']


def _alerte_bande_prix_kwc(reglages, evaluation):
    """ADEV82 — total HT/kWc hors de la bande INTERNE saisie par la société
    (``CompanyProfile.bande_prix_kwc_ci``) ⇒ alerte interne (jamais au
    document) ; bande vide ⇒ rien."""
    bande = getattr(reglages, 'bande_prix_kwc_ci', None)
    kwc = _num((evaluation or {}).get('kwc'))
    if not isinstance(bande, dict) or not kwc:
        return []
    bas, haut = _num(bande.get('min_ht')), _num(bande.get('max_ht'))
    if bas is None and haut is None:
        return []
    prix = float(evaluation.get('cout') or 0) / kwc
    if (bas is not None and prix < bas) or (haut is not None and prix > haut):
        return [_alerte(
            'PRIX_KWC_HORS_BANDE', 'composition',
            'Total HT %.0f DH/kWc hors de la bande interne %s–%s DH/kWc%s.' % (
                prix, '%.0f' % bas if bas is not None else '…',
                '%.0f' % haut if haut is not None else '…',
                ' (%s)' % bande['source'] if bande.get('source') else ''),
            interne=True)]
    return []


def _apercu_valorisation(bilan, jours_types, tension):
    return {'bilan': bilan, 'profil_charge': {'jours_types': jours_types},
            'entrees_resolues': {'tension': {'valeur': tension}}}


def _valoriseur(tarif, tarif_declare, jours_types, tension):
    """``valoriser(bilan)`` → l'économie annuelle (MAD, ``economie_annee1``)
    de la valorisation horaire C&I (``economie_ci``) ; ``valoriser.complet``
    → le bloc ``economie_ci`` entier (la même valorisation)."""
    from apps.ventes import economie_ci

    def complet(bilan):
        return economie_ci.valoriser(_apercu_valorisation(bilan, jours_types, tension),
                                     tarif, tarif_declare=tarif_declare)

    def valoriser(bilan):
        return (complet(bilan).get('economie_annee1') or {}).get('total_mad')

    valoriser.complet = complet
    return valoriser


def _forme_composition(composition):
    if composition is None:
        return None
    return {k: composition.get(k) for k in
            ('lignes', 'onduleurs', 'prix_a_renseigner', 'a_chiffrer_visite', 'incomplet',
             'options')}


def _vide_etude(res, alertes, hypotheses, sous_reserve=None):
    return {
        'entrees_resolues': res.entrees_resolues(),
        'niveau_donnees': None,
        'sous_reserve_visite': sous_reserve or {'valeur': True, 'motif': 'étude non calculée'},
        'profil_charge': None, 'production': None, 'taille': None, 'bilan': None,
        'economie_ci': None, 'composition': None, 'regime_8221_suggere': None,
        'alertes': _uniques(alertes), 'hypotheses': _uniques(hypotheses, cle=('cle',)),
        'methode': METHODE, 'version_moteur': VERSION_MOTEUR,
    }


def _taille_en_panneaux_entiers(taille, module, hypotheses):
    """CAD177 — une taille saisie se pose en panneaux ENTIERS.

    La composition pose ``ceil(kWc / Pmax)`` panneaux : un bilan calculé à la
    taille saisie (20 kWc) décrivait une autre installation que celle vendue
    (29 × 710 Wc = 20,59 kWc), et l'étude rafraîchie depuis les lignes
    (CIQ119, kWc réel des panneaux) — celle du PDF — imprimait d'autres taux
    que l'aperçu de l'écran. Sans Pmax publiée : la taille saisie, telle quelle.
    """
    kwc = _num(taille)
    pmax = _num((module or {}).get('pmax_wc'))
    if not kwc or kwc <= 0 or not pmax or pmax <= 0:
        return taille
    nb = int(math.ceil(kwc * 1000.0 / pmax - 1e-9))
    pose = round(nb * pmax / 1000.0, 6)
    if abs(pose - kwc) > 1e-9:
        hypotheses.append({
            'cle': 'taille_panneaux_entiers', 'valeur': pose, 'statut': 'declare',
            'source': '%d panneaux de %g Wc pour la taille saisie de %g kWc' % (nb, pmax, kwc)})
    return pose


def _combinaison_imposee(onduleurs_imposes, catalogue_onduleurs):
    """CIQ119 — les onduleurs RÉELLEMENT au devis, au format CIQ111."""
    prix = {o['produit']: o.get('prix') for o in catalogue_onduleurs}
    combinaison, total = [], Decimal('0')
    for item in onduleurs_imposes:
        combinaison.append({'produit': item['produit'], 'nom': item.get('nom') or '',
                            'kw_ac': item.get('kw_ac'), 'quantite': item['quantite'],
                            's_max_kva': item.get('s_max_kva')})
        if prix.get(item['produit']) is not None:
            total += Decimal(str(prix[item['produit']])) * int(item['quantite'])
    return {'combinaison': combinaison,
            'ratio_dc_ac': {'valeur': None, 'bornes': None,
                            'source': 'onduleurs du devis (lignes facturées)'},
            'chaines': None, 'exclus': [], 'prix_vente_total_ht': str(total),
            'motif': None, 'alertes': [], 'hypotheses': []}


def _jours_types_de_charge(company, res, mode, categorie, rythme, mesuree, registres,
                           conso, production):
    """Extraction C20 d'``etudier_ci`` : ``(jours_types, provenance, alertes)`` de la
    courbe de charge — mesurée > registres MT > déclarée (archétype / profil société)."""
    from apps.ventes.moteur_ci.charge import courbe_declaree
    if mesuree:
        # CIQ133 — priorité : courbe mesurée > registres MT > déclaré > archétype.
        from apps.ventes.moteur_ci.charge import courbe_mesuree_jours_types
        valeurs, debut, source_mesure = mesuree
        jours_types, prov_charge, al_charge = courbe_mesuree_jours_types(
            valeurs, debut, annee_reference=_aujourdhui().year - 1,
            kwh_mensuels=conso if isinstance(conso, list) else None, source=source_mesure)
    elif registres:
        # CIQ132 — priorité : registres MT > profil déclaré > archétype.
        from apps.ventes.moteur_ci.charge import courbe_registres_mt
        jours_types, prov_charge, al_charge = courbe_registres_mt(
            {k: v for k, v in rythme.items() if v is not None}, registres,
            annee_reference=_aujourdhui().year - 1)
    else:
        jours_types, prov_charge, al_charge = courbe_declaree(
            {k: v for k, v in rythme.items() if v is not None}, conso,
            annee_reference=_aujourdhui().year - 1, archetype=categorie,
            profil_societe=_profil_societe(
                company, mode, categorie if mode == 'commercial'
                else res.valeur('secteur_industriel')),
            production_jours_types=production['jours_types'], segment=mode)
    return jours_types, prov_charge, al_charge


#: ADEV86 (D-ACI-3=b) — site monophasé sans onduleur C&I monophasé éligible :
#: l'alerte bloquante (et donc le refus, ADEV78) le DIT avant de nommer les
#: candidats exclus.
MESSAGE_MONO_SANS_ONDULEUR = (
    "Raccordement monophasé déclaré : aucun onduleur C&I monophasé éligible et "
    "pricé au catalogue (aucun triphasé n'est proposé à sa place).")


def _alertes_phase_du_site(alertes, phase):
    if phase != 'mono':
        return alertes
    return [dict(a, message='%s %s' % (MESSAGE_MONO_SANS_ONDULEUR, a.get('message') or ''))
            if a.get('code') == 'OND_AUCUN_CANDIDAT' and a.get('niveau') == 'bloquant'
            else a for a in alertes]


def _entrees_composition(res, catalogue, phase, tension, revente):
    """Les entrées de ``moteur_ci.composition.composer_ci`` (extraction C20)."""
    return {
        'module': catalogue['module'], 'phase': phase,
        'tension': (tension or '').upper(), 'type_pose': res.valeur('type_pose'),
        'longueur_dc_m': res.valeur('longueur_dc_m'),
        'longueur_ac_m': res.valeur('longueur_ac_m'),
        'nb_points_raccordement': res.valeur('nb_points_raccordement'),
        'revente_choisie': revente,
        'besoin_cellule_mt': res.valeur('besoin_cellule_mt'),
        # R3.7 — None (inconnue) ⇒ aucune ligne, alerte interne de visite.
        'mise_a_la_terre_necessaire': res.valeur('mise_a_la_terre_necessaire'),
        'batterie_souhaitee': bool(res.valeur('batterie_souhaitee')),
    }


def _composition_prix_manquants(resultat):
    """ADEV79 (D-ACI-6=a) — les postes de taille ET les postes fixes sans
    prix : le refus les nomme tous, une seule fois (extraction C20)."""
    a_renseigner = list(resultat['prix_manquants'])
    a_renseigner += [p for p in resultat.get('postes_fixes_sans_prix') or []
                     if p not in a_renseigner]
    return {'lignes': [], 'onduleurs': {'combinaison': [], 'ratio_dc_ac': {
        'valeur': None, 'bornes': None, 'source': None}, 'chaines': None},
        'prix_a_renseigner': a_renseigner, 'a_chiffrer_visite': [],
        'incomplet': True, 'options': []}


def _alertes_postes(composition, avec):
    """Les alertes des postes non chiffrés de la composition — option « avec
    batterie » comprise (fondateur 26/10/2026 : un article de l'option sans
    prix fait refuser, nommé) — et celles de l'option « avec ». L'option
    « avec » composée remplace l'ancienne mention « batterie : valeur non
    chiffrée » des options de la composition."""
    alertes = list(avec['alertes'])
    if composition is None:
        return alertes
    manquants = list(composition.get('prix_a_renseigner') or [])
    manquants += [p for p in avec['prix_a_renseigner'] if p not in manquants]
    if manquants:
        composition.update(prix_a_renseigner=manquants, incomplet=True)
        alertes.append(_alerte('prix_a_renseigner', 'composition.lignes',
                               '%d articles C&I sans prix de vente : devis incomplet.'
                               % len(manquants)))
    if composition.get('a_chiffrer_visite'):
        alertes.append(_alerte(
            'a_chiffrer_visite', 'composition.lignes',
            'À chiffrer après la visite technique, hors total (estimation sous réserve '
            'de visite) : %s.' % ', '.join(composition['a_chiffrer_visite'])))
    if avec['bloc'] is not None:
        composition['options'] = [o for o in composition.get('options') or []
                                  if o.get('cle') != 'batterie']
    return alertes


def etudier_ci(company, entrees, *, devis=None, lead=None, production_figee=None,
               onduleurs_imposes=None, source_production_figee=None, option_avec_imposee=None,
               production_figee_rasante=None, verdict_creation=None):
    """L'étude C&I complète (forme ``exemple`` du contrat), sans écriture.

    ``production_figee`` (CIQ119) : le bloc ``production`` déjà figé sur le
    devis — il remplace l'appel PVGIS. ``onduleurs_imposes`` (CIQ119) :
    ``[{produit, nom, kw_ac, quantite}]`` lus sur les LIGNES du devis — la
    combinaison n'est alors pas recherchée. ``source_production_figee``
    (CAD177) : le libellé PVGIS qui accompagnait ``production_figee`` — la
    production reprise rend les MÊMES hypothèses/alertes que son calcul.
    ``option_avec_imposee`` (CIQ119) : l'option « avec batterie » lue sur les
    LIGNES (``etude_ci_batterie.option_imposee_des_lignes``), évaluée telle
    quelle. ``production_figee_rasante`` (R1, B2) : la série rasante figée du
    devis (option « avec » logée au-delà de 30°). ``verdict_creation`` (R1,
    B1) : ``etude_params.taille_creation_ci``, relu en taille explicite.
    """
    from apps.ventes import tarif_ci
    from apps.ventes.moteur_ci.composition import composer_ci
    from apps.ventes.moteur_ci.onduleurs import combiner_onduleurs
    from apps.ventes.moteur_ci.production import (
        bloc_production_ci, plan_de_production, production_pour_bilan, traces_production,
    )
    from apps.ventes.moteur_ci.taille import dimensionner_ci
    from apps.ventes.quote_engine.pricing import PRODUCTION_DERATE

    alertes, hypotheses = [], []
    res = resoudre_entrees(entrees, devis=devis, lead=lead)
    mode = res.valeur('mode')
    if mode not in MODES:
        alertes.append(_alerte('mode_inconnu', 'mode',
                               'Mode commercial ou industriel requis.', niveau='bloquant'))
        return _sans_cles_interdites(_vide_etude(res, alertes, hypotheses))
    _couche_visite(res, lead, alertes, devis=devis)
    if _num(res.valeur('longueur_dc_m')) is None and _num(res.valeur('longueur_ac_m')) is None:
        alertes.append(_alerte(
            'longueurs_non_relevees', 'contraintes',
            'Longueurs de câble non relevées — à confirmer à la visite.'))
    tension = res.valeur('tension')
    tarif = tarif_ci.tarif_applicable(res.valeur('tarif_declare'), tension=tension, **tarif_ci.regles_du(devis))
    # ADEV76 — dit dès la résolution : un refus nomme le contrat du lead même
    # quand le profil de charge arrête l'étude plus loin.
    if tarif.get('origine') == tarif_ci.ORIGINE_OMIS:
        alertes.append(_alerte('tarif_omis', 'tarif', tarif_ci.MENTION_OMIS,
                               niveau='bloquant'))
    conso, _feuille = _consommation(res, tarif, alertes, hypotheses)
    registres = _registres_resolus(res)
    mesuree = _courbe_mesuree_resolue(res.valeur('courbe_mesuree'), _aujourdhui().year - 1)
    if conso is None and mesuree:
        conso = round(sum(mesuree[0]), 3)
    if conso is None and registres:
        from apps.ventes.moteur_ci.charge import POSTES_MT, _registre
        conso = [sum(_registre(m, p) for p in POSTES_MT) for m in registres]
    _garde_kwh_factures(res, tarif, alertes)

    site = res.valeur('site') or {}
    toit_declare, toit_serie = _toit_declare(res)
    lecture = None if production_figee else lire_production(site, toit=toit_serie)
    if lecture is None and not production_figee:
        alertes.append(_alerte('production_indisponible', 'production',
                               'Profil PVGIS indisponible : production non calculée, étude omise.',
                               niveau='bloquant'))
        return _sans_cles_interdites(_vide_etude(res, alertes, hypotheses))
    if production_figee:
        production = production_figee
        # CAD177 — mêmes traces que le calcul qui l'a figée (idempotence d'un
        # ré-enregistrement sans changement, CIQ334/CIQ346).
        hyp_prod, al_prod = traces_production(
            production, source=source_production_figee, toit=toit_declare)
        alertes.extend(al_prod)
        hypotheses.extend(hyp_prod)
    else:
        productibles, formes, source, serie = (tuple(lecture) + (None,))[:4]  # 3 = avant AMOT99
        production, hyp_prod, al_prod = bloc_production_ci(
            productible_mensuel=productibles, formes_saison=formes,
            derate=PRODUCTION_DERATE,
            # Critique Fable (vague 2) : le point RÉELLEMENT appelé (GPS ou
            # ville au gazetier), pour une étude reproductible.
            coordonnees_figees={'lat': _point_du_site(site)[0], 'lon': _point_du_site(site)[1],
                                'date_appel': _aujourdhui().isoformat()},
            # R1 (P4) — le plan du toit, série OU repli (pose estimée comprise).
            source=source, toit=toit_declare, serie=serie,
            plan=(serie or {}).get('plan') or plan_de_production(toit_serie))
        alertes.extend(al_prod)
        hypotheses.extend(hyp_prod)
    if production is None:
        return _sans_cles_interdites(_vide_etude(res, alertes, hypotheses))
    rasante = _serie_rasante(site, toit_serie, toit_declare, production, figee=bool(production_figee),
                             bloc_figee=production_figee_rasante, source_figee=source_production_figee)

    if conso is None:
        alertes.append(_alerte('consommation_absente', 'consommation',
                               'Consommation non déclarée : aucune taille calculée.',
                               niveau='bloquant'))
        etude = _vide_etude(res, alertes, hypotheses)
        etude['production'] = production
        return _sans_cles_interdites(_json(etude))

    categorie = res.valeur('categorie_commerciale') if mode == 'commercial' else 'industriel'
    # CIQ130 — la catégorie et ses réponses partent au noyau, qui en tire des
    # éléments d'horaire déclarés (jamais des coefficients).
    rythme = {k: res.valeur(k) for k in (
        'jours_ouverts', 'plages', 'equipes', 'debut_equipe_h', 'fermetures',
        'ramadan', 'talon', 'categorie_commerciale', 'reponses_categorie')}
    jours_types, prov_charge, al_charge = _jours_types_de_charge(
        company, res, mode, categorie, rythme, mesuree, registres, conso, production)
    alertes.extend(al_charge)
    niveau = (prov_charge or {}).get('niveau_donnees')
    sous_reserve = _sous_reserve_visite(res, lead, niveau)
    if not jours_types:
        etude = _vide_etude(res, alertes, hypotheses, sous_reserve)
        etude['production'] = production
        etude['niveau_donnees'] = niveau
        return _sans_cles_interdites(_json(etude))
    profil_charge = {'methode': prov_charge.get('methode'),
                     'archetype': prov_charge.get('archetype'),
                     'jours_types': jours_types, 'talon': prov_charge.get('talon')}

    catalogue = lire_catalogue_ci(company)
    reglages = _reglages_societe(company)
    forfaits = getattr(reglages, 'forfaits_ci', None) or {}
    phase = res.valeur('phases')
    revente = bool(res.valeur('revente_choisie'))
    entrees_compo = _entrees_composition(res, catalogue, phase, tension, revente)

    def combiner(kwc):
        if onduleurs_imposes:
            return _combinaison_imposee(onduleurs_imposes, catalogue['onduleurs'])
        # ADEV87 — module et fiches onduleur passés : les chaînes se calculent.
        return combiner_onduleurs(kwc, catalogue['onduleurs'], phase=phase,
                                  module=catalogue.get('module_spec'),
                                  ac_max_kw=_num(res.valeur('puissance_souscrite_kva')))

    def composer(kwc, onduleurs, extra=()):
        return _completer_prix(composer_ci(kwc, catalogue['elements'] + list(extra), onduleurs=onduleurs,
                                           entrees=entrees_compo, forfaits=forfaits),
                               catalogue['prix_par_id'],
                               getattr(reglages, 'tva_standard', None))

    valoriser = _valoriseur(tarif, res.valeur('tarif_declare'), jours_types, tension)
    hypotheses.append({'cle': 'base_taille', 'valeur': 'HT', 'statut': 'estimation',
                       'source': 'coût de vente HT ÷ économie HT (la base HT/TTC du '
                                 'document suit D-CIQ-3, economie_ci)'})
    borne_toit = _borne_toit(res, devis, catalogue['module'], alertes)
    _charge_toiture(res, catalogue, alertes)
    resultat = dimensionner_ci(
        charge_jours_types=jours_types, production_jours_types=production_pour_bilan(production),
        tension=tension, combiner=combiner, composer=composer, valoriser=valoriser,
        bornes={'toit': borne_toit,
                'phase': {'kwc': None, 'motif': 'triphasé : aucune borne de phase'
                          if phase == 'tri' else 'phase : voir la combinaison d’onduleurs'}},
        puissance_souscrite_kva=res.valeur('puissance_souscrite_kva'),
        revente_choisie=revente,
        taille_explicite_kwc=_taille_en_panneaux_entiers(
            res.valeur('taille_explicite_kwc'), catalogue['module'], hypotheses),
        # ADEV79 — TTC des paliers → HT : TVA de l'article, à défaut le taux
        # standard SAISI de la société (lecture seule), jamais un 20 codé.
        taux_tva_pct=getattr(reglages, 'tva_standard', None), pmax_wc=(catalogue['module'] or {}).get('pmax_wc'),
        production_rasante=rasante['lire'])
    production = _servir_pose_rasante(resultat, rasante, production, alertes, hypotheses, (al_prod, hyp_prod))
    _relire_verdict_toit(resultat['taille'], verdict_creation, resultat['hypotheses'])
    alertes.extend(_alertes_phase_du_site(resultat['alertes'], phase))
    hypotheses.extend(resultat['hypotheses'])
    evaluation = resultat['evaluation']

    bilan = composition = economie = regime = None
    if evaluation is not None:
        bilan, composition = evaluation['bilan'], evaluation['composition']
        _traces_evaluation(evaluation, alertes, hypotheses)
        economie = valoriser.complet(bilan)
        regime = _regime(evaluation['kwc'], evaluation['puissance_ac'], tension)
        alertes.extend(_alertes_reactif(res, tension, bilan, registres))
        alertes.extend(_alerte_bande_prix_kwc(reglages, evaluation))
    elif resultat.get('prix_manquants'):
        composition = _composition_prix_manquants(resultat)
    # Fondateur 26/10/2026 — l'option « avec batterie » (hybrides BT + banque).
    # CEC1 (O&M hors an 0) est une règle du 27/10 : un devis envoyé ≤ 2 recalculé la garde.
    avec = option_avec_de_l_etude(
        catalogue, None if onduleurs_imposes else evaluation, choix=res.valeur('batterie_souhaitee'),
        lead=lead, charge=jours_types, production=production_pour_bilan(production), tension=tension,
        revente_choisie=revente, valoriser=valoriser, taux_tva_pct=getattr(reglages, 'tva_standard', None),
        phase=phase, ps_kva=_num(res.valeur('puissance_souscrite_kva')), composer=composer,
        borne_toit=borne_toit, production_rasante=rasante['lire'], imposee=option_avec_imposee,
        regles_2710=regles_au_moins(devis, REGLES_CORRIGEES_2710))
    alertes.extend(_alertes_postes(composition, avec))
    hypotheses.extend(avec['hypotheses'])

    etude = {
        'entrees_resolues': res.entrees_resolues(),
        'niveau_donnees': niveau,
        'sous_reserve_visite': sous_reserve,
        'profil_charge': profil_charge,
        'production': production,
        # R1 (B2) — la série rasante lue mais NON retenue (taille à 30°) : figée
        # par le rafraîchisseur pour loger l'option « avec » au-delà.
        'production_rasante': rasante.get('bloc') if rasante.get('bloc') is not production else None,
        'taille': resultat['taille'],
        'bilan': bilan,
        'economie_ci': economie,
        'composition': _forme_composition(composition),
        'regime_8221_suggere': regime,
        **({CLE_OPTION_AVEC: avec['bloc']} if avec['bloc'] else {}),
        'alertes': _uniques(alertes),
        'hypotheses': _uniques(hypotheses, cle=('cle',)),
        'methode': METHODE_8760 if production.get('serie_horaire') else METHODE,
        'version_moteur': VERSION_MOTEUR,
    }
    return _sans_cles_interdites(_json(etude))


# ── 5 bis. DEVIS AUTOMATIQUE (CIQ120) : de l'étude aux lignes ────────────────

#: Clés d'ENTRÉE persistées dans ``Devis.etude_params`` (contrat CIQ2,
#: ``cles_etude_params_ci_v2.entrees``) — les feuilles lues sur le lead seul
#: (kWh déclaré, facture d'hiver) n'y sont pas recopiées : le rafraîchisseur
#: relit le lead.
CLES_ENTREES_PERSISTEES = ('mode', 'site', 'tension', 'phases',
                           'puissance_souscrite_kva', 'consommation', 'rythme',
                           'courbe_mesuree', 'toit', 'contraintes', 'options',
                           'taille_explicite_kwc')


def entrees_pour_etude_params(entrees_resolues):
    """Les entrées RÉSOLUES, remises dans la forme ``etude_params`` C&I v2."""
    arbre = {}
    for feuille, chemin in FEUILLES:
        entree = (entrees_resolues or {}).get(feuille)
        if not isinstance(entree, dict) or _vide(entree.get('valeur')):
            continue
        morceaux = chemin.split('.')
        if morceaux[0] not in CLES_ENTREES_PERSISTEES:
            continue
        noeud = arbre
        for morceau in morceaux[:-1]:
            noeud = noeud.setdefault(morceau, {})
        noeud[morceaux[-1]] = entree['valeur']
    tarif = (entrees_resolues or {}).get('tarif_declare')
    if isinstance(tarif, dict) and isinstance(tarif.get('valeur'), dict):
        arbre['tarif_declare'] = tarif['valeur']
    return arbre


#: ADEV76 (D-ACI-5=a) — champ d'une alerte BLOQUANTE du moteur → champ du
#: LEAD qui la lève (un 409 nomme toujours ce que la fiche lead sait poser).
CHAMP_LEAD_DES_ALERTES = {
    'tarif': 'contrat_electricite',
    'rythme.jours_ouverts': 'jours_ouverture',
    'rythme.plages': 'heure_debut',
}
#: L'ordre dans lequel un refus nomme le premier champ manquant du lead.
ORDRE_CHAMPS_LEAD_CI = ('contrat_electricite', 'jours_ouverture', 'heure_debut')
#: ADEV89 — phases du site admises par le devis automatique (jamais « inconnu »).
PHASES_DECLAREES = ('mono', 'tri')
# ALEA54 — ces refus s'adressent à la COMMERCIALE : une consigne à suivre auprès
# du client, jamais le jargon du moteur (« profil de charge », « archétype »).
MESSAGES_CHAMP_LEAD_CI = {
    # CORC3 (27/10/2026) — le refus nommait le moteur (« Tarif non déclaré et
    # contrat d'électricité inconnu : économies non chiffrées … »).
    'contrat_electricite': ("Demandez au client son contrat d'électricité — basse tension "
                            'patenté, force motrice ou moyenne tension : il est écrit sur '
                            'sa facture ; sans lui, les économies ne se chiffrent pas.'),
    'raccordement': ('Demandez au client si son site est en monophasé ou en triphasé — '
                     "c'est écrit sur sa facture ou sur son compteur ; le choix des "
                     'onduleurs en dépend.'),
    'jours_ouverture': ("Demandez au client quels jours le site est ouvert (ou en "
                        "production), ou choisissez son activité : le week-end n'est "
                        'jamais supposé.'),
    'heure_debut': ("Demandez au client ses heures d'ouverture (début et fin de journée, "
                    "ou régime d'équipes), ou choisissez son activité : pour celle-ci, "
                    "aucun horaire type n'est connu."),
}
#: ADEV78 — champs d'alerte (racine) dont le refus porte sur la composition.
CHAMPS_COMPOSITION = frozenset({'composition', 'onduleurs', 'taille_explicite_kwc'})
#: ADEV78 — refus d'une étude SANS taille et sans alerte bloquante, par
#: raison d'arrêt : « aucune taille rentable » est réservé à l'horizon.
MESSAGES_ARRET = {
    'horizon_marginal': ('Aucune taille C&I rentable dans l’horizon de 10 ans.', 'taille'),
    'toit': ('Contenance du toit inférieure à la première tranche de 5 kWc : '
             'aucune taille C&I.', 'surface_toiture_m2'),
    'puissance_souscrite': ('Puissance souscrite déclarée inférieure à la première '
                            'tranche de 5 kWc : aucune taille C&I.', 'compteur_puissance_kva'),
}
MESSAGE_PRIX_A_RENSEIGNER = (
    "Prix à renseigner avant un devis automatique C&I : %s. À régler par "
    "l'administrateur dans Paramètres › Devis › Prestations C&I, ou sur la fiche de l'article.")
#: CORC6 (27/10/2026, constat CCAT) — une prestation chiffrée (forfait réglé)
#: SANS article au catalogue comptait dans l'étude et disparaissait du devis.
MESSAGE_PRESTATION_SANS_ARTICLE = (
    "Article manquant au catalogue pour : %s. Le prix est réglé dans Paramètres "
    "› Devis › Prestations C&I, mais aucun article du Stock ne porte ce rôle : "
    "créez-le (ou désarchivez-le) avant un devis automatique.")
MESSAGE_MAD_SANS_CONTRAT = (
    "Facture en MAD sans contrat d'électricité déclaré : précisez le contrat "
    '(BT patenté / force motrice) ou saisissez la conso en kWh.')


def _champ_lead_manquant(alertes):
    """``(champ du lead, alerte)`` du PREMIER manquant (ordre fixe), ou ``None``."""
    trouves = {}
    for alerte in alertes:
        if alerte.get('niveau') != 'bloquant':
            continue
        champ = CHAMP_LEAD_DES_ALERTES.get(alerte.get('champ'))
        if champ is not None:
            trouves.setdefault(champ, alerte)
    for champ in ORDRE_CHAMPS_LEAD_CI:
        if champ in trouves:
            return champ, trouves[champ]
    return None


def refus_devis_auto_ci(etude):
    """``(message, champ)`` qui interdit un devis automatique C&I, ou ``None``.

    Les refus nomment un CHAMP DU LEAD (ADEV76) : la consommation, puis le
    contrat d'électricité, les jours et les heures d'ouverture (dans cet
    ordre, la règle des prérequis ``moteur_ci.charge.profil_charge_prerequis``)
    — testés AVANT « prix à renseigner » — ou la cause du moteur."""
    alertes = etude.get('alertes') or []
    codes = {a.get('code'): a for a in alertes}
    if 'mode_inconnu' in codes:
        return codes['mode_inconnu']['message'], 'type_installation'
    if 'kwh_incoherent_factures' in codes:
        return codes['kwh_incoherent_factures']['message'], 'conso_mensuelle_kwh'
    if 'conversion_mad_impossible' in codes:
        return MESSAGE_MAD_SANS_CONTRAT, 'contrat_electricite'
    if 'consommation_absente' in codes:
        return ('Consommation (kWh) ou facture mensuelle (MAD) manquante : '
                'aucun devis automatique sans consommation.', 'conso_mensuelle_kwh')
    if 'production_indisponible' in codes:
        return codes['production_indisponible']['message'], 'ville'
    manquant = _champ_lead_manquant(alertes)
    if manquant is not None:
        champ, alerte = manquant
        return MESSAGES_CHAMP_LEAD_CI.get(champ) or alerte.get('message'), champ
    # ADEV89 (rejeu « humain » 23/10/2026) — la PHASE du site est un prérequis
    # du devis automatique : sans elle, un hôtel triphasé à 14 MWh/mois sortait
    # composé d'onduleurs monophasés de 5 kW (puis refusé sur un disjoncteur
    # mono sans prix). Le refus nomme le champ du lead (bouton « Compléter »).
    phase = ((etude.get('entrees_resolues') or {}).get('phases') or {}).get('valeur')
    if phase not in PHASES_DECLAREES:
        return MESSAGES_CHAMP_LEAD_CI['raccordement'], 'raccordement'
    taille = etude.get('taille') or {}
    bloquants = [a for a in alertes if a.get('niveau') == 'bloquant']
    # ADEV78 — la VRAIE cause d'un arrêt « module » ou « onduleurs ».
    for code in ('CI_MODULE_FICHE', 'OND_AUCUN_CANDIDAT'):
        alerte = next((a for a in bloquants if a.get('code') == code), None)
        if alerte is not None:
            return alerte['message'], 'composition'
    # ADEV79 (D-ACI-6=a) — un poste de taille OU un poste fixe sans prix fait
    # refuser en nommant les postes et le chemin où les régler (jamais un 0).
    manquants = (etude.get('composition') or {}).get('prix_a_renseigner') or []
    if taille.get('raison_arret') == 'prix_manquants' or manquants:
        return (MESSAGE_PRIX_A_RENSEIGNER % ', '.join(str(m) for m in manquants),
                'composition')
    # CORC6 — une ligne chiffrée sans article ne s'écrit pas au devis (et le
    # regroupement « Installation clé en main » ne la reconnaîtrait pas) :
    # refus nommé, jamais un total d'étude qui diverge du total du devis.
    orphelines = lignes_chiffrees_sans_article(etude.get('composition'))
    if orphelines:
        return MESSAGE_PRESTATION_SANS_ARTICLE % ', '.join(orphelines), 'composition'
    # ADEV78 — TOUTE alerte bloquante refuse, même quand une taille existe
    # (taille saisie aux onduleurs infaisables comprise).
    if bloquants:
        champ = bloquants[0].get('champ') or ''
        return bloquants[0].get('message'), (
            'composition' if champ.split('.')[0] in CHAMPS_COMPOSITION else 'taille')
    if not taille.get('retenue_kwc'):
        return MESSAGES_ARRET.get(taille.get('raison_arret'), MESSAGES_ARRET['horizon_marginal'])
    return None


def lignes_chiffrees_sans_article(composition):
    """CORC6 — désignations des lignes CHIFFRÉES (prix connu, quantité > 0)
    sans article du catalogue : :func:`lignes_du_devis_ci` les saute, elles
    n'entrent donc jamais au devis. Les postes « à chiffrer après visite »
    (hors total) n'en sont pas."""
    noms = []
    for ligne in (composition or {}).get('lignes') or []:
        if ligne.get('a_chiffrer_visite') or ligne.get('produit'):
            continue
        quantite = _num(ligne.get('quantite'))
        if ligne.get('prix_connu') and quantite and quantite > 0:
            nom = ligne.get('designation') or ligne.get('role') or '?'
            if nom not in noms:
                noms.append(nom)
    return noms


def devis_auto_possible(etude):
    """CORC1 — ``{possible, message, champ}`` : le devis automatique C&I
    passerait-il sur CETTE étude ? Le MÊME refus que le bouton
    (:func:`refus_devis_auto_ci`) — le message s'adresse au vendeur et
    ``champ`` nomme le champ du lead à compléter (``composition`` / ``taille``
    : réglage catalogue ou cause du moteur)."""
    refus = refus_devis_auto_ci(etude)
    if refus:
        return {'possible': False, 'message': refus[0], 'champ': refus[1]}
    return {'possible': True, 'message': None, 'champ': None}


def lignes_du_devis_ci(composition):
    """Les lignes du devis : les articles du catalogue que le moteur a
    composés, au prix de VENTE HT. Une ligne sans article (« prix à
    renseigner », « à confirmer à la visite ») reste dans l'étude, jamais une
    ligne à 0 ; une ligne « à chiffrer après visite » (ADEV79, D-ACI-2=a)
    reste hors du devis, listée dans ``composition.a_chiffrer_visite``."""
    from apps.ventes.moteur_ci.composition import nom_client
    lignes = []
    for ligne in (composition or {}).get('lignes') or []:
        if ligne.get('a_chiffrer_visite'):
            continue
        produit = ligne.get('produit')
        quantite = _num(ligne.get('quantite'))
        prix = _num(ligne.get('prix_unitaire_ht'))
        if not produit or not quantite or quantite <= 0 or prix is None \
                or not ligne.get('prix_connu'):
            continue
        meme = next((x for x in lignes if x['produit_id'] == produit
                     and x['prix_unitaire'] == Decimal(str(prix))), None)
        if meme is not None:  # même article au même prix : une seule ligne
            meme['quantite'] += Decimal(str(quantite))
            continue
        lignes.append({'produit_id': produit,
                       'designation': nom_client(ligne.get('designation') or ''),
                       'quantite': Decimal(str(quantite)),
                       'prix_unitaire': Decimal(str(prix))})
    return lignes


# ── 6. RAFRAÎCHISSEUR (CIQ119) : l'étude suit les LIGNES facturées ───────────

CLE_ETUDE_CI = 'etude_ci'
CLE_PRODUCTION_FIGEE = 'production_figee'
CLE_PRODUCTION_FIGEE_RASANTE = 'production_figee_rasante'
CLE_TAILLE_CREATION = 'taille_creation_ci'


def _onduleurs_des_lignes(devis, catalogue):
    """``[{produit, nom, kw_ac, quantite}]`` des onduleurs C&I au devis."""
    par_id = {o['produit']: o for o in catalogue['onduleurs']}
    quantites = {}
    for ligne in devis.lignes.all():
        if getattr(ligne, 'type_ligne', 'produit') != 'produit' \
                or getattr(ligne, 'optionnelle', False):
            continue
        if ligne.produit_id in par_id:
            quantites[ligne.produit_id] = quantites.get(ligne.produit_id, 0) + int(
                ligne.quantite or 0)
    return [dict(par_id[pid], quantite=q) for pid, q in sorted(quantites.items()) if q > 0]


def _empreinte(entrees_stockees, kwc, onduleurs, option_avec=None):
    import hashlib
    import json
    charge = {'entrees': entrees_stockees, 'kwc': kwc,
              'onduleurs': [(o['produit'], o['quantite']) for o in onduleurs],
              'version': VERSION_MOTEUR}
    if option_avec:
        # Fondateur 26/10/2026 — l'option « avec batterie » des lignes ; clé
        # absente sans elle (les empreintes d'hier restent identiques).
        charge['option_avec'] = option_avec['empreinte']
    return hashlib.sha256(json.dumps(_json(charge), sort_keys=True, default=str)
                          .encode('utf-8')).hexdigest()[:16]


def _kwc_option_servie(devis, kwc_avec, kwc_sans):
    """AMOT62 (C-AMOT-052) — le kWc de l'option que le document C&I SERT.

    ``etudes.puissances_etude_horaire`` rend ``(kWc AVEC, kWc SANS)`` sur un
    devis à panneaux variantés (``kwc_sans`` ``None`` sinon : une seule
    puissance). Un C&I à deux options titre l'offre RÉSEAU seule (CIQ302,
    ``utils.options.option_mise_en_avant`` → SANS), sauf option AVEC acceptée
    (QJR401) — même règle que ``builder`` (``option_servie``). L'étude décrit
    donc CETTE option : kWc, production, taux et économies imprimés parlent
    de la même installation (sonde VC lci8 : étude 49,7 kWc imprimée à côté
    de 35,5 kWc servis)."""
    if not kwc_sans:
        return kwc_avec
    from apps.ventes.utils.options import AVEC_BATTERIE
    if (getattr(devis, 'option_acceptee', '') or '') == AVEC_BATTERIE:
        return kwc_avec or kwc_sans
    return kwc_sans


def _option_avec_du_devis(devis, catalogue, kwc_avec, kwc_sans):
    """L'option « avec batterie » des LIGNES (``None`` sans hybride ET
    batterie) et ``mono`` : vrai quand le devis ne porte QUE cette option
    (aucun champ « sans » distinct, aucun onduleur string C&I en ligne)."""
    from .etude_ci_batterie import option_imposee_des_lignes
    lignes = list(devis.lignes.all())
    imposee = option_imposee_des_lignes(lignes, catalogue, kwc_avec)
    string = {o['produit'] for o in catalogue['onduleurs']}
    mono = imposee is not None and not kwc_sans and not any(
        li.produit_id in string for li in lignes)
    return imposee, mono


def _servir_option_avec_seule(bloc, avec):
    """Devis à option « avec » SEULE : l'étude décrit l'installation vendue —
    bilan, économie et taille de l'option « avec » (jamais un champ « sans »
    que personne n'achète)."""
    if not avec or not avec.get('economie_ci'):
        return bloc
    bilan = dict(bloc.get('bilan') or {}, **avec['bilan'])
    taille = dict(bloc.get('taille') or {}, retenue_kwc=avec['kwc'])
    return dict(bloc, bilan=bilan, economie_ci=avec['economie_ci'], taille=taille)


def bloc_etude_ci_stocke(etude, *, mono=False):
    """La forme STOCKÉE de ``etude_params.etude_ci`` (rafraîchisseur CIQ119).
    Option « avec » : clé ADDITIVE (absente sans elle aux lignes) ; seule
    (``mono``), l'étude décrit l'option « avec ». AMOT99 — les 8 760 h vivent
    dans ``production_figee`` seule (``economie_ci_options.apercu_du_devis``)."""
    bloc = {cle: etude.get(cle) for cle in (
        'entrees_resolues', 'profil_charge', 'production', 'taille', 'bilan',
        'composition', 'economie_ci', 'alertes', 'hypotheses')}
    if etude.get(CLE_OPTION_AVEC):
        bloc[CLE_OPTION_AVEC] = etude[CLE_OPTION_AVEC]
        if mono:
            bloc = _servir_option_avec_seule(bloc, etude[CLE_OPTION_AVEC])
    serie = (bloc.get('production') or {}).get('serie_horaire')
    if serie:
        bloc['production'] = dict(bloc['production'], serie_horaire={
            k: v for k, v in serie.items() if k != 'kwh_kwc'})
    return bloc


def _source_production(etude):
    """CAD177 — le libellé PVGIS (hypothèse ``source_production``) d'une
    étude C&I déjà posée, ou ``None``."""
    for hyp in (etude or {}).get('hypotheses') or []:
        if isinstance(hyp, dict) and hyp.get('cle') == 'source_production':
            return hyp.get('valeur')
    return None


def rafraichir_etude_ci_devis(devis, *, force=False):
    """CIQ119 — (re)pose ``etude_ci`` / ``production_figee`` d'un devis C&I.

    Commercial ou industriel SEULEMENT. Relit les LIGNES (kWc réel par
    ``etudes.puissances_etude_horaire``, onduleurs réellement au devis), les
    entrées stockées et ``production_figee`` ; appelle :func:`etudier_ci` en
    « taille donnée » (aucun redimensionnement) et n'écrit QUE les dérivées
    ``moteur_ci`` par ``etude_schema.ecrire`` (``update_fields`` : aucun
    statut, aucune ligne, aucun total — règle #4). Empreinte identique ⇒
    aucune écriture. Plus aucun panneau ⇒ dérivées RETIRÉES, jamais périmées.
    Ne lève jamais : une étude n'empêche pas d'enregistrer un devis.
    """
    from .etude_schema import CLES_RETIREES_CI_V1, MOTEUR_CI, ecrire
    from .etudes import CLES_DERIVEES_NON_COPIEES, puissances_etude_horaire
    try:
        mode = (getattr(devis, 'mode_installation', None) or '').strip().lower()
        if mode not in MODES:
            return None
        params = dict(getattr(devis, 'etude_params', None) or {})
        kwc = _kwc_option_servie(devis, *puissances_etude_horaire(devis))
        if not kwc:
            if CLE_ETUDE_CI in params or CLE_PRODUCTION_FIGEE in params:
                ecrire(devis, proprietaire=MOTEUR_CI,
                       **{CLE_ETUDE_CI: None, CLE_PRODUCTION_FIGEE: None,
                          CLE_PRODUCTION_FIGEE_RASANTE: None})
            return None
        company = getattr(devis, 'company', None)
        catalogue = lire_catalogue_ci(company)
        onduleurs = _onduleurs_des_lignes(devis, catalogue)
        # Fondateur 26/10/2026 — l'option « avec batterie » des lignes.
        imposee, mono = _option_avec_du_devis(devis, catalogue, *puissances_etude_horaire(devis))
        # CIQ129 — une clé v1 retirée (jamais une entrée du moteur) n'entre
        # pas dans l'empreinte.
        stockees = {k: v for k, v in params.items()
                    if k not in CLES_DERIVEES_NON_COPIEES
                    and k not in CLES_RETIREES_CI_V1}
        empreinte = _empreinte(stockees, kwc, onduleurs, imposee)
        existant = params.get(CLE_ETUDE_CI) or {}
        if not force and existant.get('empreinte') == empreinte:
            return existant
        etude = etudier_ci(
            company, {'mode': mode, 'taille_explicite_kwc': kwc}, devis=devis,
            lead=getattr(devis, 'lead', None),
            production_figee=params.get(CLE_PRODUCTION_FIGEE),
            onduleurs_imposes=onduleurs or None,
            source_production_figee=_source_production(existant),
            option_avec_imposee=imposee,
            production_figee_rasante=params.get(CLE_PRODUCTION_FIGEE_RASANTE),
            verdict_creation=params.get(CLE_TAILLE_CREATION))
        if etude.get('bilan') is None:
            if CLE_ETUDE_CI in params or CLE_PRODUCTION_FIGEE in params:
                ecrire(devis, proprietaire=MOTEUR_CI,
                       **{CLE_ETUDE_CI: None, CLE_PRODUCTION_FIGEE: None,
                          CLE_PRODUCTION_FIGEE_RASANTE: None})
            return None
        bloc = dict(bloc_etude_ci_stocke(etude, mono=mono), version=VERSION_MOTEUR, empreinte=empreinte)
        ecrire(devis, proprietaire=MOTEUR_CI,
               **{CLE_ETUDE_CI: bloc, CLE_PRODUCTION_FIGEE: etude.get('production'),
                  CLE_PRODUCTION_FIGEE_RASANTE: etude.get('production_rasante')})
        return bloc
    except Exception:  # noqa: BLE001 — jamais bloquant pour un devis (D-ENF22-BLE001)
        logger.warning('etude_ci non rafraîchie sur %s',
                       getattr(devis, 'reference', '?'), exc_info=True)
        return None


# ── AMOT99 — la courbe de garantie de la fiche module ───────────────────────

def courbe_degradation_des_produits(produits):
    """AMOT99 (D-ACI-18=a) — la courbe de dégradation retenue
    (``moteur_ci.degradation.courbe_depuis_fiches``) depuis les fiches
    MODULE des produits, lues par la façade ``apps.stock.selectors`` ; aucun
    module à fiche publiée ⇒ le défaut, dit « fiche muette »."""
    from apps.stock.selectors import specs_for_produit, type_fiche_produit
    from apps.ventes.moteur_ci.degradation import courbe_depuis_fiches
    return courbe_depuis_fiches([
        specs_for_produit(p) or {} for p in produits
        if p is not None and type_fiche_produit(p) == 'module'])


def courbe_degradation_du_devis(devis):
    """AMOT99 — la courbe des modules de l'option RETENUE du devis."""
    from apps.ventes.utils.options import option_lines
    return courbe_degradation_des_produits(
        getattr(ligne, 'produit', None) for ligne in option_lines(devis))
