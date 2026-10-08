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
from decimal import Decimal

logger = logging.getLogger(__name__)

VERSION_MOTEUR = 'ci-1'
METHODE = (
    "autoconsommation horaire : production PVGIS du site × profil déclaré, "
    "12 mois × types de jour ; taille par tranches de 5 kWc jusqu'à "
    "l'horizon marginal de 10 ans (D-CIQ-1, D-CIQ-2)")
CLES_INTERDITES = frozenset({'prix_achat', 'marge'})
MODES = ('commercial', 'industriel')

#: Lead.type_toiture → type de pose CIQ7 : seulement les correspondances
#: CERTAINES ; une terrasse béton (lestée ou fixée ?) reste à déclarer.
POSE_DU_TOIT_LEAD = {'bac_acier': 'bac_acier', 'tuiles': 'toiture_inclinee'}

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
    'rythme.categorie_commerciale': 'categorie_commerciale',
    'rythme.reponses_categorie': 'reponses_categorie',
    'toit.surface_utile_m2': 'surface_utile_m2',
    'toit.type_toiture': 'couverture',
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
        if feuille == 'couverture':
            res.poser('type_pose', POSE_DU_TOIT_LEAD.get(valeur), prov)
        if feuille == 'surface_utile_m2':
            res.poser('surface_type', 'declaree', prov)
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


#: CIQ141 — couverture constatée à la visite → type de pose CIQ7 : seulement
#: les correspondances CERTAINES (une dalle béton lestée ou fixée reste à dire).
POSE_DE_LA_COUVERTURE_VISITE = {'bac_acier': 'bac_acier', 'tuile': 'toiture_inclinee'}


def _poser_mesure(res, feuille, valeur, provenance):
    """Une mesure de visite passe devant le lead, jamais devant une saisie
    (corps) ni le devis."""
    if _vide(valeur):
        return
    actuelle = res.provenance(feuille) or {}
    if actuelle.get('origine') in ('saisie', 'devis'):
        return
    res.poser(feuille, valeur, provenance)


def _couche_visite(res, lead, alertes):
    """CIQ141 — le relevé de la dernière visite ``ci`` VALIDÉE du lead (façade
    ``apps.visites.selectors.releve_ci_pour_lead``, jamais ses modèles) :
    vérifié par la visite > déclaré > absent. Une mesure « non relevée » ne
    remplace rien et lève une alerte nommée."""
    if lead is None:
        return
    from apps.visites.selectors import releve_ci_pour_lead
    releve = releve_ci_pour_lead(lead)
    if not releve:
        return
    prov = _provenance('mesure_visite', 'visite %s' % releve.get('visite_id'),
                       releve.get('validee_le'))
    # Longueurs de cheminement : par trajet, sommées.
    trajets = releve.get('trajets') or []
    for cle in ('longueur_dc_m', 'longueur_ac_m'):
        valeurs = [_num(t.get(cle)) for t in trajets if _num(t.get(cle)) is not None]
        if valeurs:
            _poser_mesure(res, cle, round(sum(valeurs), 2), prov)
    # Zones de toiture : la plus grande surface utile devient le toit de l'étude.
    zones = []
    for zone in releve.get('zones_toiture') or []:
        surface = _num(zone.get('surface_utile_m2'))
        if surface is None and _num(zone.get('longueur_m')) and _num(zone.get('largeur_m')):
            surface = _num(zone['longueur_m']) * _num(zone['largeur_m'])
        zones.append((surface or 0.0, zone))
    if len(zones) > 1:
        alertes.append(_alerte('plusieurs_zones_toiture', 'toit',
                               'Plusieurs zones de toiture relevées : calepinage requis.'))
    if zones:
        surface, zone = max(zones, key=lambda z: z[0])
        if surface:
            _poser_mesure(res, 'surface_utile_m2', round(surface, 2), prov)
            _poser_mesure(res, 'surface_type', 'mesuree', prov)
        couverture = zone.get('couverture')
        _poser_mesure(res, 'couverture', couverture, prov)
        _poser_mesure(res, 'type_pose', POSE_DE_LA_COUVERTURE_VISITE.get(couverture), prov)
        _poser_mesure(res, 'pente_deg', _num(zone.get('pente_deg')), prov)
        charge = _num(zone.get('charge_admissible_declaree_kg_m2'))
        if charge is not None:
            piece = zone.get('charge_admissible_piece')
            source = 'pièce %s, zone « %s » (visite %s du %s)' % (
                piece if not _vide(piece) else 'non jointe', zone.get('libelle') or '?',
                releve.get('visite_id'), releve.get('validee_le'))
            _poser_mesure(res, 'charge_admissible_kg_m2', charge, prov)
            _poser_mesure(res, 'charge_admissible_source', source, prov)
    # Comptage : seulement si le lead ne le porte pas encore.
    tension = (releve.get('niveau_tension') or {}).get('constate')
    if tension and res.valeur('tension') in (None, 'inconnue'):
        res.poser('tension', tension, prov)
    puissance = (releve.get('puissance_souscrite_kva') or {}).get('constate')
    if puissance is not None and res.valeur('puissance_souscrite_kva') is None:
        res.poser('puissance_souscrite_kva', puissance, prov)
    for mesure, motif in sorted((releve.get('non_releves') or {}).items()):
        alertes.append(_alerte('mesure_non_verifiee', mesure,
                               '%s non vérifiée à la visite (%s).' % (mesure, motif)))


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
                par_mois[numero] = _num(ligne['kwh'])
            if len(par_mois) == 12:
                return [par_mois[m] for m in range(1, 13)], feuille
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
    bill = _num(res.valeur('bill_kwh'))
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
    source = courbe.get('source')
    debut = courbe.get('debut') or courbe.get('date_debut')
    if isinstance(courbe.get('contenu'), str) and courbe['contenu'].strip():
        from rest_framework.exceptions import ValidationError

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
    valeurs = [_num(p) or 0.0 for p in points]
    if int(courbe.get('pas_minutes') or 60) == 15:
        groupes = [valeurs[i:i + 4] for i in range(0, len(valeurs) - len(valeurs) % 4, 4)]
        moyenne = (courbe.get('unite') or 'kwh') == 'kw'
        valeurs = [sum(g) / 4.0 if moyenne else sum(g) for g in groupes]
    return valeurs, debut, source


def _garde_kwh_factures(res, tarif, alertes):
    """Décision du 30/09 : un kWh déclaré qui contredit la facture (> 2×) bloque."""
    from apps.ventes.horaire.conso import RATIO_KWH_FACTURE_MAX, RATIO_KWH_FACTURE_MIN
    kwh = _num(res.valeur('kwh_mensuel_declare'))
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

def lire_production(site):
    """``(productible_mensuel, formes_saison, source)`` ou ``None`` (PVGIS)."""
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
    return productibles, formes, source


def _profil_societe(company, mode, categorie):
    """Profil SAISI par la société (famille du mode), par la façade calepinage."""
    if company is None:
        return None
    from apps.calepinage import services as calepinage_services
    try:
        profils = calepinage_services.profils_de_societe(company, inclure_replis=False)
    except Exception:  # lecture best-effort : l'archétype sourcé prend le relais
        logger.warning('CIQ118 — profils société illisibles', exc_info=True)
        return None
    candidats = [p for p in profils if p.get('famille') == mode]
    if not candidats:
        return None
    choisi = next((p for p in candidats if p.get('cle') == categorie), candidats[0])
    return {'cle': choisi.get('cle'), 'libelle': choisi.get('libelle'),
            'courbe': choisi.get('courbes'), 'provenance': choisi.get('provenance')}


def lire_catalogue_ci(company):
    """Catalogue C&I (``stock.selectors.produits_ci``) + prix de VENTE HT du
    catalogue de la société + module retenu. Jamais ``prix_achat``."""
    from apps.stock.selectors import produits_ci, specs_for_produit

    from ..compatibilites import est_triphase_produit
    from .catalogue import catalogue_de_la_societe, classer_produit

    objets = {p.id: p for p in catalogue_de_la_societe(company)}
    elements = []
    for element in produits_ci(company):
        produit = objets.get(element['id'])
        if produit is not None and produit.prix_vente and produit.prix_vente > 0:
            element = dict(element, prix_vente_ht=produit.prix_vente,
                           paliers_prix_vente=list(
                               getattr(produit, 'paliers_prix_vente', None) or []))
        elements.append(element)

    onduleurs = []
    for element in elements:
        if element.get('role_ci') != 'onduleur_string_tri':
            continue
        produit = objets.get(element['id'])
        specs = {}
        if produit is not None:
            try:
                specs = specs_for_produit(produit) or {}
            except Exception:  # fiche illisible : candidat sans spécifs
                specs = {}
        onduleurs.append({
            'produit': element['id'], 'nom': element.get('nom'),
            'kw_ac': (element.get('fiche') or {}).get('ond_ac_kw') or specs.get('ac_kw'),
            'prix': element.get('prix_vente_ht'),
            'triphase': est_triphase_produit(produit) if produit is not None else None,
            'eligible_ci': element.get('eligible_ci'),
            'motif_exclusion': element.get('motif_exclusion'),
            'dc_max_kwc': specs.get('dc_max_kwc'),
            's_max_kva': specs.get('s_max_kva'),
        })

    module = None
    candidats = []
    for produit in objets.values():
        role = getattr(produit, 'role_devis', None) or classer_produit(produit.nom)
        if role != 'panneau':
            continue
        try:
            specs = specs_for_produit(produit) or {}
        except Exception:  # fiche illisible
            specs = {}
        pmax = _num(specs.get('pmax_wc'))
        prix = bool(produit.prix_vente and produit.prix_vente > 0)
        candidats.append(((prix, bool(pmax), pmax or 0, -produit.id), produit, specs))
    if candidats:
        _cle, produit, specs = max(candidats, key=lambda c: c[0])
        module = {
            'produit': produit.id, 'designation': produit.nom,
            'pmax_wc': _num(specs.get('pmax_wc')),
            'prix_connu': bool(produit.prix_vente and produit.prix_vente > 0),
            'prix_vente_ht': produit.prix_vente,
            'longueur_mm': _num(specs.get('longueur_mm')),
            'largeur_mm': _num(specs.get('largeur_mm')),
            'poids_kg': _num(specs.get('poids_kg')),
        }
    prix_par_id = {e['id']: e['prix_vente_ht'] for e in elements if e.get('prix_vente_ht')}
    if module and module.get('prix_vente_ht'):
        prix_par_id[module['produit']] = module['prix_vente_ht']
    return {'elements': elements, 'onduleurs': onduleurs, 'module': module,
            'prix_par_id': prix_par_id}


def _reglages_societe(company):
    if company is None:
        return None
    from apps.parametres.models import CompanyProfile
    return CompanyProfile.objects.filter(company=company).first()


# ── 4. TOIT ──────────────────────────────────────────────────────────────────

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
    module = module or {}
    cotes = None
    if module.get('longueur_mm') and module.get('largeur_mm'):
        cotes = (module['longueur_mm'] / 1000.0, module['largeur_mm'] / 1000.0)
    pente = _num(res.valeur('pente_deg'))
    site = res.valeur('site') or {}
    resultat = calepinage_services.contenance_surface_declaree(
        surface, mode_pose=res.valeur('type_pose'), cotes_module_m=cotes,
        inclinaison_deg=pente if pente is not None else PVGIS_ANGLE_DEG,
        latitude_deg=_num(site.get('lat')), puissance_module_wc=pmax)
    if resultat.get('kwc') is None:
        alertes.append(_alerte('contenance_toit_inconnue', 'toit',
                               'Contenance du toit non bornée : %s.' % resultat.get('motif')))
        return None
    return {'kwc': round(float(resultat['kwc']), 2),
            'source': 'surface utile déclarée (%g m²) — estimation, à confirmer au '
                      'calepinage/visite' % surface}


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


def _completer_prix(composition, prix_par_id):
    """Les lignes dont l'article a un prix de vente connu mais que la
    composition n'a pas chiffré (panneau) reçoivent ce prix unitaire HT."""
    for ligne in composition.get('lignes') or []:
        prix = prix_par_id.get(ligne.get('produit'))
        if prix is not None and not ligne.get('prix_unitaire_ht') \
                and ligne.get('role') != 'onduleur_string_tri':
            ligne['prix_unitaire_ht'] = str(prix)
            ligne['prix_connu'] = True
            if ligne.get('motif') and 'prix' in ligne['motif']:
                ligne['motif'] = None
    composition['prix_a_renseigner'] = [ligne['designation']
                                        for ligne in composition.get('lignes') or []
                                        if not ligne['prix_connu']]
    composition['incomplet'] = bool(composition['prix_a_renseigner'])
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


def _apercu_valorisation(bilan, jours_types, tension):
    return {'bilan': bilan, 'profil_charge': {'jours_types': jours_types},
            'entrees_resolues': {'tension': {'valeur': tension}}}


def _forme_composition(composition):
    if composition is None:
        return None
    return {k: composition.get(k) for k in
            ('lignes', 'onduleurs', 'prix_a_renseigner', 'incomplet', 'options')}


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


def etudier_ci(company, entrees, *, devis=None, lead=None, production_figee=None,
               onduleurs_imposes=None):
    """L'étude C&I complète (forme ``exemple`` du contrat), sans écriture.

    ``production_figee`` (CIQ119) : le bloc ``production`` déjà figé sur le
    devis — il remplace l'appel PVGIS. ``onduleurs_imposes`` (CIQ119) :
    ``[{produit, nom, kw_ac, quantite}]`` lus sur les LIGNES du devis — la
    combinaison n'est alors pas recherchée.
    """
    from apps.ventes import economie_ci, tarif_ci
    from apps.ventes.moteur_ci.charge import courbe_declaree
    from apps.ventes.moteur_ci.composition import composer_ci
    from apps.ventes.moteur_ci.onduleurs import combiner_onduleurs
    from apps.ventes.moteur_ci.production import bloc_production_ci
    from apps.ventes.moteur_ci.taille import dimensionner_ci
    from apps.ventes.quote_engine.pricing import PRODUCTION_DERATE

    alertes, hypotheses = [], []
    res = resoudre_entrees(entrees, devis=devis, lead=lead)
    mode = res.valeur('mode')
    if mode not in MODES:
        alertes.append(_alerte('mode_inconnu', 'mode',
                               'Mode commercial ou industriel requis.', niveau='bloquant'))
        return _sans_cles_interdites(_vide_etude(res, alertes, hypotheses))
    _couche_visite(res, lead, alertes)
    if _num(res.valeur('longueur_dc_m')) is None and _num(res.valeur('longueur_ac_m')) is None:
        alertes.append(_alerte(
            'longueurs_non_relevees', 'contraintes',
            'Longueurs de câble non relevées — à confirmer à la visite.'))
    tension = res.valeur('tension')
    tarif = tarif_ci.tarif_applicable(res.valeur('tarif_declare'), tension=tension)
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
    lecture = None if production_figee else lire_production(site)
    if lecture is None and not production_figee:
        alertes.append(_alerte('production_indisponible', 'production',
                               'Profil PVGIS indisponible : production non calculée, étude omise.',
                               niveau='bloquant'))
        return _sans_cles_interdites(_vide_etude(res, alertes, hypotheses))
    if production_figee:
        production = production_figee
    else:
        productibles, formes, source = lecture
        production, hyp_prod, al_prod = bloc_production_ci(
            productible_mensuel=productibles, formes_saison=formes,
            derate=PRODUCTION_DERATE,
            coordonnees_figees={'lat': _num(site.get('lat')), 'lon': _num(site.get('lon')),
                                'date_appel': _aujourdhui().isoformat()},
            source=source, toit={'type_pose': res.valeur('type_pose'),
                                 'pente_deg': res.valeur('pente_deg'),
                                 'azimut_deg': res.valeur('azimut_deg')})
        alertes.extend(al_prod)
        hypotheses.extend(hyp_prod)
    if production is None:
        return _sans_cles_interdites(_vide_etude(res, alertes, hypotheses))

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
            profil_societe=_profil_societe(company, mode, categorie),
            production_jours_types=production['jours_types'])
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
    entrees_compo = {
        'module': catalogue['module'], 'phase': phase,
        'tension': (tension or '').upper(), 'type_pose': res.valeur('type_pose'),
        'longueur_dc_m': res.valeur('longueur_dc_m'),
        'longueur_ac_m': res.valeur('longueur_ac_m'),
        'nb_points_raccordement': res.valeur('nb_points_raccordement'),
        'revente_choisie': revente,
        'besoin_cellule_mt': res.valeur('besoin_cellule_mt'),
        'batterie_souhaitee': bool(res.valeur('batterie_souhaitee')),
    }

    def combiner(kwc):
        if onduleurs_imposes:
            return _combinaison_imposee(onduleurs_imposes, catalogue['onduleurs'])
        return combiner_onduleurs(kwc, catalogue['onduleurs'], phase=phase)

    def composer(kwc, onduleurs):
        return _completer_prix(composer_ci(kwc, catalogue['elements'], onduleurs=onduleurs,
                                           entrees=entrees_compo, forfaits=forfaits),
                               catalogue['prix_par_id'])

    td = res.valeur('tarif_declare')

    def valoriser(bilan):
        resultat = economie_ci.valoriser(
            _apercu_valorisation(bilan, jours_types, tension), tarif, tarif_declare=td)
        return (resultat.get('economie_annee1') or {}).get('total_mad')

    if tarif.get('origine') == tarif_ci.ORIGINE_OMIS:
        alertes.append(_alerte('tarif_omis', 'tarif', tarif_ci.MENTION_OMIS,
                               niveau='bloquant'))
    hypotheses.append({'cle': 'base_taille', 'valeur': 'HT', 'statut': 'estimation',
                       'source': 'coût de vente HT ÷ économie HT (la base HT/TTC du '
                                 'document suit D-CIQ-3, economie_ci)'})
    borne_toit = _borne_toit(res, devis, catalogue['module'], alertes)
    _charge_toiture(res, catalogue, alertes)
    resultat = dimensionner_ci(
        charge_jours_types=jours_types, production_jours_types=production['jours_types'],
        tension=tension, combiner=combiner, composer=composer, valoriser=valoriser,
        bornes={'toit': borne_toit,
                'phase': {'kwc': None, 'motif': 'triphasé : aucune borne de phase'
                          if phase == 'tri' else 'phase : voir la combinaison d’onduleurs'}},
        puissance_souscrite_kva=res.valeur('puissance_souscrite_kva'),
        revente_choisie=revente, taille_explicite_kwc=res.valeur('taille_explicite_kwc'),
        taux_tva_pct=20)
    alertes.extend(resultat['alertes'])
    hypotheses.extend(resultat['hypotheses'])
    evaluation = resultat['evaluation']

    bilan = composition = economie = regime = None
    if evaluation is not None:
        bilan = evaluation['bilan']
        alertes.extend(evaluation['alertes_bilan'])
        composition = evaluation['composition']
        alertes.extend(composition.get('alertes') or [])
        alertes.extend((evaluation['onduleurs'] or {}).get('alertes') or [])
        hypotheses.extend(composition.get('hypotheses') or [])
        economie = economie_ci.valoriser(
            _apercu_valorisation(bilan, jours_types, tension), tarif, tarif_declare=td)
        regime = _regime(evaluation['kwc'], evaluation['puissance_ac'], tension)
        alertes.extend(_alertes_reactif(res, tension, bilan, registres))
    elif resultat.get('prix_manquants'):
        composition = {'lignes': [], 'onduleurs': {'combinaison': [], 'ratio_dc_ac': {
            'valeur': None, 'bornes': None, 'source': None}, 'chaines': None},
            'prix_a_renseigner': resultat['prix_manquants'], 'incomplet': True,
            'options': []}
    if composition is not None and composition.get('prix_a_renseigner'):
        alertes.append(_alerte(
            'prix_a_renseigner', 'composition.lignes',
            '%d articles C&I sans prix de vente : devis incomplet.'
            % len(composition['prix_a_renseigner'])))

    etude = {
        'entrees_resolues': res.entrees_resolues(),
        'niveau_donnees': niveau,
        'sous_reserve_visite': sous_reserve,
        'profil_charge': profil_charge,
        'production': production,
        'taille': resultat['taille'],
        'bilan': bilan,
        'economie_ci': economie,
        'composition': _forme_composition(composition),
        'regime_8221_suggere': regime,
        'alertes': _uniques(alertes),
        'hypotheses': _uniques(hypotheses, cle=('cle',)),
        'methode': METHODE,
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


def refus_devis_auto_ci(etude):
    """``(message, champ)`` qui interdit un devis automatique C&I, ou ``None``.

    Les refus nomment la donnée manquante de la règle « devis auto prêt » pro
    (contrat CIQ1 : le groupe consommation) ou la cause du moteur."""
    codes = {a.get('code'): a for a in etude.get('alertes') or []}
    if 'mode_inconnu' in codes:
        return codes['mode_inconnu']['message'], 'type_installation'
    if 'kwh_incoherent_factures' in codes:
        return codes['kwh_incoherent_factures']['message'], 'conso_mensuelle_kwh'
    if 'consommation_absente' in codes or 'conversion_mad_impossible' in codes:
        return ('Consommation (kWh) ou facture mensuelle (MAD) manquante : '
                'aucun devis automatique sans consommation.', 'conso_mensuelle_kwh')
    if 'production_indisponible' in codes:
        return codes['production_indisponible']['message'], 'ville'
    taille = etude.get('taille') or {}
    if taille.get('raison_arret') == 'prix_manquants':
        manquants = (etude.get('composition') or {}).get('prix_a_renseigner') or []
        return ('Prix à renseigner : %s.' % ', '.join(str(m) for m in manquants),
                'composition')
    if 'tarif_omis' in codes:
        return codes['tarif_omis']['message'], 'tarif_declare'
    if not taille.get('retenue_kwc'):
        alerte = next((a for a in etude.get('alertes') or []
                       if a.get('niveau') == 'bloquant'), None)
        return ((alerte or {}).get('message')
                or 'Aucune taille C&I rentable dans l’horizon de 10 ans.', 'taille')
    return None


def lignes_du_devis_ci(composition):
    """Les lignes du devis : les articles du catalogue que le moteur a
    composés, au prix de VENTE HT. Une ligne sans article (« prix à
    renseigner », « à confirmer à la visite ») reste dans l'étude, jamais une
    ligne à 0."""
    lignes = []
    for ligne in (composition or {}).get('lignes') or []:
        produit = ligne.get('produit')
        quantite = _num(ligne.get('quantite'))
        prix = _num(ligne.get('prix_unitaire_ht'))
        if not produit or not quantite or quantite <= 0 or prix is None \
                or not ligne.get('prix_connu'):
            continue
        lignes.append({'produit_id': produit,
                       'designation': ligne.get('designation') or '',
                       'quantite': Decimal(str(quantite)),
                       'prix_unitaire': Decimal(str(prix))})
    return lignes


# ── 6. RAFRAÎCHISSEUR (CIQ119) : l'étude suit les LIGNES facturées ───────────

CLE_ETUDE_CI = 'etude_ci'
CLE_PRODUCTION_FIGEE = 'production_figee'


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


def _empreinte(entrees_stockees, kwc, onduleurs):
    import hashlib
    import json
    charge = {'entrees': entrees_stockees, 'kwc': kwc,
              'onduleurs': [(o['produit'], o['quantite']) for o in onduleurs],
              'version': VERSION_MOTEUR}
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
                       **{CLE_ETUDE_CI: None, CLE_PRODUCTION_FIGEE: None})
            return None
        company = getattr(devis, 'company', None)
        catalogue = lire_catalogue_ci(company)
        onduleurs = _onduleurs_des_lignes(devis, catalogue)
        # CIQ129 — une clé v1 retirée (jamais une entrée du moteur) n'entre
        # pas dans l'empreinte.
        stockees = {k: v for k, v in params.items()
                    if k not in CLES_DERIVEES_NON_COPIEES
                    and k not in CLES_RETIREES_CI_V1}
        empreinte = _empreinte(stockees, kwc, onduleurs)
        existant = params.get(CLE_ETUDE_CI) or {}
        if not force and existant.get('empreinte') == empreinte:
            return existant
        etude = etudier_ci(
            company, {'mode': mode, 'taille_explicite_kwc': kwc}, devis=devis,
            lead=getattr(devis, 'lead', None),
            production_figee=params.get(CLE_PRODUCTION_FIGEE),
            onduleurs_imposes=onduleurs or None)
        if etude.get('bilan') is None:
            if CLE_ETUDE_CI in params or CLE_PRODUCTION_FIGEE in params:
                ecrire(devis, proprietaire=MOTEUR_CI,
                       **{CLE_ETUDE_CI: None, CLE_PRODUCTION_FIGEE: None})
            return None
        bloc = {cle: etude.get(cle) for cle in (
            'entrees_resolues', 'profil_charge', 'production', 'taille', 'bilan',
            'composition', 'economie_ci', 'alertes', 'hypotheses')}
        bloc['version'] = VERSION_MOTEUR
        bloc['empreinte'] = empreinte
        ecrire(devis, proprietaire=MOTEUR_CI,
               **{CLE_ETUDE_CI: bloc, CLE_PRODUCTION_FIGEE: etude.get('production')})
        return bloc
    except Exception:  # noqa: BLE001 — jamais bloquant pour un devis
        logger.warning('etude_ci non rafraîchie sur %s',
                       getattr(devis, 'reference', '?'), exc_info=True)
        return None
