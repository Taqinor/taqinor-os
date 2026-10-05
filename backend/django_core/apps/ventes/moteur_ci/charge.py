"""CIQ108 — courbe de charge DÉCLARÉE en jours types (12 mois × types de jour × 24 h).

Module PUR (aucun import Django, aucune base lue). La FORME vient du
calendrier déclaré (jours ouverts, plages ou équipes, fermetures, fériés
saisis, Ramadan déclaré, talon) ; le NIVEAU vient des 12 kWh mensuels
déclarés (patron L-ECO du résidentiel). Aucun scalaire « part diurne ».

Conventions :

* les plages sont déclarées en heure CIVILE marocaine ; la sortie est en
  heures GMT (le repère de la production PVGIS, contrat
  ``etude_ci_preview.json``), via ``decalage_maroc_h`` jour par jour —
  aucun « UTC+1 » codé ;
* ``jours_types`` = ``[{mois, type_jour, nb_jours, charge_kwh[24]}]`` ; un
  jour type est la MOYENNE des jours du mois de ce type, donc
  Σ charge × nb_jours = consommation du mois ;
* ``type_jour`` : ``ouvre`` / ``samedi`` / ``dimanche`` (jour ouvert, selon
  le calendrier) ou ``ferme`` (jour fermé, férié saisi, fermeture datée) ;
* talon ``part_pct`` = part de l'énergie du mois consommée par le talon.
"""

import calendar
import datetime

from apps.parametres.pvgis_profils import decalage_maroc_h
from apps.ventes.moteur_ci.categories import elements_horaire
from apps.ventes.moteur_ci.profils import forme_archetype

HEURES = 24
DUREE_EQUIPES_H = {'1x8': 8, '2x8': 16, '3x8': 24, 'continu': 24}
NOMS_JOURS = ('lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche')


def saison_bdew(jour):
    """Saison aux bornes BDEW (celles des archétypes CIQ107)."""
    md = (jour.month, jour.day)
    if (5, 15) <= md <= (9, 14):
        return 'ete'
    if (3, 21) <= md <= (5, 14) or (9, 15) <= md <= (10, 31):
        return 'transition'
    return 'hiver'


def _type_calendaire(jour):
    return {5: 'samedi', 6: 'dimanche'}.get(jour.weekday(), 'ouvre')


def _alerte(code, champ, message, niveau='alerte', interne=False):
    return {'code': code, 'champ': champ, 'message': message,
            'niveau': niveau, 'interne': interne}


def _date(valeur, annee):
    """Date ISO (``AAAA-MM-JJ`` ou ``MM-JJ``) projetée sur ``annee``."""
    if isinstance(valeur, datetime.date):
        mois, jour = valeur.month, valeur.day
    else:
        morceaux = str(valeur).strip().split('-')
        mois, jour = int(morceaux[-2]), int(morceaux[-1])
    if mois == 2 and jour == 29 and not calendar.isleap(annee):
        jour = 28
    return datetime.date(annee, mois, jour)


def _dans_intervalle(jour, du, au):
    if du <= au:
        return du <= jour <= au
    return jour >= du or jour <= au      # intervalle qui enjambe le 31/12


def _occupation(plages):
    """Fraction de chaque heure civile couverte par les plages [[debut, fin]]."""
    occ = [0.0] * HEURES
    for debut, fin in plages or ():
        debut, fin = float(debut), float(fin)
        morceaux = [(debut, fin)] if debut < fin else [(debut, 24.0), (0.0, fin)]
        for a, b in morceaux:
            for h in range(HEURES):
                recouvrement = min(b, h + 1) - max(a, h)
                if recouvrement > 0:
                    occ[h] = min(1.0, occ[h] + recouvrement)
    return occ


def _plages_equipes(equipes, debut_h):
    duree = DUREE_EQUIPES_H.get(equipes)
    if duree is None:
        return None
    if duree >= HEURES:
        return [[0, 24]]
    if debut_h is None:
        return None
    debut = float(debut_h) % 24
    return [[debut, (debut + duree) % 24 or 24.0]]


def _vers_gmt(courbe_civile, decalage):
    """Heure civile → GMT : gmt[g] = civile[g + décalage] (énergie conservée)."""
    return [courbe_civile[(g + decalage) % HEURES] for g in range(HEURES)]


def _jours_annee(annee):
    jour = datetime.date(annee, 1, 1)
    while jour.year == annee:
        yield jour
        jour += datetime.timedelta(days=1)


def _calendrier(rythme, annee, feries, alertes):
    """Pour chaque jour : (ouvert ?, type calendaire, plages civiles ou None)."""
    jours_ouverts = rythme.get('jours_ouverts')
    if jours_ouverts is not None and len(jours_ouverts) != 7:
        alertes.append(_alerte('jours_ouverts_invalides', 'rythme.jours_ouverts',
                               '7 drapeaux lundi→dimanche attendus : calendrier ignoré.'))
        jours_ouverts = None

    plages_par_type = rythme.get('plages') or None
    if not plages_par_type:
        plages_eq = _plages_equipes(rythme.get('equipes'), rythme.get('debut_equipe_h'))
        if plages_eq is not None:
            plages_par_type = {'ouvre': plages_eq}
        elif rythme.get('equipes'):
            alertes.append(_alerte(
                'equipes_sans_heure_debut', 'rythme.debut_equipe_h',
                'Équipes déclarées sans heure de début : plages non placées.'))

    fermetures = []
    for fermeture in rythme.get('fermetures') or ():
        try:
            fermetures.append((_date(fermeture['du'], annee), _date(fermeture['au'], annee)))
        except (KeyError, TypeError, ValueError, IndexError):
            alertes.append(_alerte('fermeture_illisible', 'rythme.fermetures',
                                   'Une fermeture sans dates lisibles est ignorée.'))

    jours_feries = set()
    if feries is None:
        alertes.append(_alerte(
            'feries_non_saisis', 'feries',
            'Aucun jour férié saisi par la société : les fériés sont ignorés.',
            niveau='info', interne=True))
    else:
        for ferie in feries:
            try:
                jours_feries.add(_date(ferie, annee))
            except (TypeError, ValueError, IndexError):
                continue

    ramadan = rythme.get('ramadan')
    ramadan_bornes = None
    if ramadan:
        try:
            ramadan_bornes = (_date(ramadan['du'], annee), _date(ramadan['au'], annee))
        except (KeyError, TypeError, ValueError, IndexError):
            alertes.append(_alerte('ramadan_sans_dates', 'rythme.ramadan',
                                   'Plages Ramadan déclarées sans dates : ignorées.'))

    calendrier = []
    for jour in _jours_annee(annee):
        type_cal = _type_calendaire(jour)
        ouvert = True if jours_ouverts is None else bool(jours_ouverts[jour.weekday()])
        if jour in jours_feries or any(_dans_intervalle(jour, du, au) for du, au in fermetures):
            ouvert = False
        plages = None
        if plages_par_type:
            plages = plages_par_type.get(type_cal, plages_par_type.get('ouvre'))
            if ramadan_bornes and _dans_intervalle(jour, *ramadan_bornes):
                plages_ram = ramadan.get('plages') or {}
                plages = plages_ram.get(type_cal, plages_ram.get('ouvre', plages))
        calendrier.append((jour, ouvert, type_cal, plages))
    return calendrier, jours_ouverts is not None, bool(plages_par_type)


def _niveaux_mensuels(kwh_mensuels, calendrier, alertes):
    if isinstance(kwh_mensuels, (int, float)):
        ouverts = [0] * 12
        for jour, ouvert, _t, _p in calendrier:
            ouverts[jour.month - 1] += 1 if ouvert else 0
        total = sum(ouverts)
        if total == 0:
            return None, None
        alertes.append(_alerte(
            'repartition_annuelle_prorata', 'consommation.kwh_annuel',
            'Total annuel seul : réparti au prorata des jours ouverts de chaque mois.',
            niveau='info'))
        return [float(kwh_mensuels) * n / total for n in ouverts], 'annuel_prorata'
    if not kwh_mensuels or len(kwh_mensuels) != 12 or any(v is None for v in kwh_mensuels):
        return None, None
    return [float(v) for v in kwh_mensuels], 'mensuel_declare'


def _courbes_declarees(calendrier, niveaux, talon_mode, talon_valeur, rapport_talon):
    """Courbe civile de chaque jour, calée sur l'énergie de son mois.

    ``talon_mode`` : ``kw`` (talon en kW), ``part`` (part du mois),
    ``rapport`` (talon = rapport × puissance en plage, archétype),
    ``nul`` (borne talon 0), ``etale`` (borne : énergie étalée sur 24 h des
    jours ouverts). Rend ``(courbes, talon_incoherent)``.
    """
    par_mois = {}
    for entree in calendrier:
        par_mois.setdefault(entree[0].month, []).append(entree)
    courbes = {}
    incoherent = False
    for mois, jours in par_mois.items():
        energie = niveaux[mois - 1]
        n_jours = len(jours)
        occs = {}
        for jour, ouvert, _t, plages in jours:
            if not ouvert:
                occs[jour] = [0.0] * HEURES
            elif talon_mode == 'etale':
                occs[jour] = [1.0] * HEURES
            else:
                occs[jour] = _occupation(plages)
        somme_occ = sum(sum(o) for o in occs.values())
        if talon_mode in ('nul', 'etale'):
            talon = 0.0
        elif talon_mode == 'kw':
            talon = float(talon_valeur)
        elif talon_mode == 'part':
            talon = energie * float(talon_valeur) / 100.0 / (HEURES * n_jours)
        else:   # rapport : talon = r × (talon + L)  ⇒  L = talon × (1/r − 1)
            r = rapport_talon
            denominateur = HEURES * n_jours + (1.0 / r - 1.0) * somme_occ if r > 0 else 0
            talon = energie / denominateur if r > 0 and denominateur > 0 else 0.0
        reste = energie - talon * HEURES * n_jours
        if reste < 0 or somme_occ <= 0:
            if reste < -1e-9 or (somme_occ <= 0 and reste > 1e-9):
                incoherent = True
            talon = energie / (HEURES * n_jours)
            niveau_plage = 0.0
        else:
            niveau_plage = reste / somme_occ
        for jour, _o, _t, _p in jours:
            courbes[jour] = [talon + niveau_plage * occs[jour][h] for h in range(HEURES)]
    return courbes, incoherent


def _courbes_archetype(calendrier, niveaux, categorie, profil_societe, talon_kw):
    """Méthode ``archetype`` : forme sourcée (CIQ107) par jour ouvert."""
    par_mois = {}
    for entree in calendrier:
        par_mois.setdefault(entree[0].month, []).append(entree)
    courbes = {}
    source = None
    for mois, jours in par_mois.items():
        formes = {}
        poids_ferme = []
        for jour, ouvert, type_cal, _p in jours:
            forme, src = forme_archetype(categorie, type_cal, saison_bdew(jour),
                                         profil_societe=profil_societe)
            if forme is None:
                return None, src
            source = src
            formes[jour] = forme
            if not ouvert:
                poids_ferme.append(min(forme))
        energie = niveaux[mois - 1]
        n_ouverts = sum(1 for _j, o, _t, _p in jours if o)
        n_fermes = len(jours) - n_ouverts
        if talon_kw is not None:
            reste = max(0.0, energie - float(talon_kw) * HEURES * n_fermes)
            energie_jour = reste / n_ouverts if n_ouverts else 0.0
            talon_ferme = float(talon_kw) if n_ouverts else energie / (HEURES * len(jours))
        else:
            # talon d'un jour fermé = creux de l'archétype ramené au niveau du jour ouvert
            denominateur = n_ouverts + HEURES * sum(poids_ferme)
            energie_jour = energie / denominateur if denominateur > 0 else 0.0
            talon_ferme = None
        for jour, ouvert, _t, _p in jours:
            if ouvert:
                courbes[jour] = [energie_jour * w for w in formes[jour]]
            else:
                niveau = talon_ferme if talon_ferme is not None else energie_jour * min(formes[jour])
                courbes[jour] = [niveau] * HEURES
    return courbes, source


def _jours_types(calendrier, courbes, annee):
    groupes = {}
    for jour, ouvert, type_cal, _p in calendrier:
        type_jour = type_cal if ouvert else 'ferme'
        cle = (jour.month, type_jour)
        gmt = _vers_gmt(courbes[jour], decalage_maroc_h(jour))
        cumul, n = groupes.get(cle, ([0.0] * HEURES, 0))
        groupes[cle] = ([c + g for c, g in zip(cumul, gmt)], n + 1)
    ordre = {'ouvre': 0, 'samedi': 1, 'dimanche': 2, 'ferme': 3}
    sortie = []
    for (mois, type_jour) in sorted(groupes, key=lambda k: (k[0], ordre[k[1]])):
        cumul, n = groupes[(mois, type_jour)]
        sortie.append({'mois': mois, 'type_jour': type_jour, 'nb_jours': n,
                       'charge_kwh': [c / n for c in cumul]})
    return sortie


def _autoconso(jours_types, production_jours_types, kwc):
    prod = {p['mois']: p['production_kwh_kwc'] for p in production_jours_types}
    total = 0.0
    for jt in jours_types:
        p = prod.get(jt['mois'])
        if p is None:
            continue
        total += jt['nb_jours'] * sum(min(c, kwc * x) for c, x in zip(jt['charge_kwh'], p))
    return total


def _choisir_borne(bornes, production_jours_types):
    """La borne qui donne la MOINDRE autoconsommation, à la taille de référence.

    Taille de référence : production annuelle = consommation annuelle.
    """
    conso = sum(jt['nb_jours'] * sum(jt['charge_kwh']) for jt in bornes['talon_nul'])
    prod_kwc = 0.0
    nb_par_mois = {}
    for jt in bornes['talon_nul']:
        nb_par_mois[jt['mois']] = nb_par_mois.get(jt['mois'], 0) + jt['nb_jours']
    for p in production_jours_types:
        prod_kwc += nb_par_mois.get(p['mois'], 0) * sum(p['production_kwh_kwc'])
    if prod_kwc <= 0:
        return None
    kwc_ref = conso / prod_kwc
    return min(bornes, key=lambda cle: (_autoconso(bornes[cle], production_jours_types, kwc_ref), cle))


#: CIQ132 — postes MT et leurs clés de registre acceptées (contrat CIQ2
#: ``registres_mt`` : ``pointe_kwh`` …, relevé du lead : ``kwh_pointe`` …).
POSTES_MT = ('pointe', 'pleines', 'creuses')
_CLES_REGISTRE = {p: ('%s_kwh' % p, 'kwh_%s' % p) for p in POSTES_MT}
EQUIPES_NUIT = frozenset({'3x8', 'continu'})


def _registre(mois_bloc, poste):
    for cle in _CLES_REGISTRE[poste]:
        valeur = (mois_bloc or {}).get(cle)
        if valeur not in (None, ''):
            try:
                return max(0.0, float(valeur))
            except (TypeError, ValueError):
                return None
    return None


def registres_lisibles(registres):
    """Les 12 mois portent-ils chacun leurs trois postes ?"""
    if not isinstance(registres, (list, tuple)) or len(registres) != 12:
        return False
    return all(_registre(m, p) is not None for m in registres for p in POSTES_MT)


def courbe_registres_mt(rythme, registres, *, annee_reference, feries=None):
    """CIQ132 — jours types (GMT) depuis les registres pointe / pleines /
    creuses de la facture MT, provenance et alertes.

    Pour chaque mois, l'énergie de chaque poste est répartie UNIFORMÉMENT sur
    les heures de ce poste des jours OUVERTS, selon les plages horaires
    OFFICIELLES (``tarifs_officiels.poste_horaire``, heures GMT — le Maroc est
    à GMT, aucun décalage codé). Les jours FERMÉS déclarés reçoivent le talon =
    puissance moyenne des heures creuses du mois (dérivée, publiée). Contrôle
    sans seuil inventé : 1x8 / plages de jour seules avec creuses > pleines, ou
    3x8 / continu avec creuses nulles ⇒ ``incoherence_equipes_registres``
    (jamais bloquant). Puissance atteinte et kvarh passent aux alertes sans
    toucher la courbe.
    """
    from apps.parametres.tarifs_officiels import poste_horaire

    rythme = rythme or {}
    alertes = []
    provenance = {
        'methode': 'registres_mt', 'archetype': None, 'niveau_donnees': 'declare',
        'heures': 'GMT', 'annee_reference': annee_reference, 'repartition': 'registres_mt',
        'talon': None, 'bornes': None, 'reponses_non_consommees': [],
    }
    if not registres_lisibles(registres):
        alertes.append(_alerte('registres_incomplets', 'consommation.registres_mt',
                               '12 mois × pointe / pleines / creuses requis.', niveau='bloquant'))
        return None, provenance, alertes
    calendrier, _jours, _plages = _calendrier(rythme, annee_reference, feries, alertes)
    postes_h = {m: [poste_horaire(m, h) for h in range(HEURES)] for m in range(1, 13)}
    courbes = {}
    talons = []
    for mois in range(1, 13):
        jours = [e for e in calendrier if e[0].month == mois]
        ouverts = [e for e in jours if e[1]]
        fermes = [e for e in jours if not e[1]]
        heures_poste = {p: postes_h[mois].count(p) for p in POSTES_MT}
        energie = {p: _registre(registres[mois - 1], p) for p in POSTES_MT}
        h_creuses_mois = heures_poste['creuses'] * len(jours)
        talon = energie['creuses'] / h_creuses_mois if fermes and h_creuses_mois else 0.0
        talons.append(round(talon, 6))
        niveau = {}
        for p in POSTES_MT:
            reste = energie[p] - talon * heures_poste[p] * len(fermes)
            if reste < -1e-9:
                alertes.append(_alerte(
                    'talon_au_dela_du_registre', 'consommation.registres_mt',
                    'Mois %d : le talon des jours fermés dépasse le registre « %s ».' % (mois, p)))
                reste = 0.0
            heures = heures_poste[p] * len(ouverts)
            niveau[p] = reste / heures if heures else 0.0
        for jour, ouvert, _t, _p in jours:
            courbes[jour] = ([niveau[postes_h[mois][h]] for h in range(HEURES)]
                             if ouvert else [talon] * HEURES)
    provenance['talon'] = {'valeur': {'kw_par_mois': talons}, 'statut': 'derive',
                           'source': 'puissance moyenne des heures creuses du mois (registres)'}

    creuses = sum(_registre(m, 'creuses') for m in registres)
    pleines = sum(_registre(m, 'pleines') for m in registres)
    equipes = rythme.get('equipes')
    jour_seul = equipes == '1x8' or (not equipes and bool(rythme.get('plages')) and all(
        float(d) >= 5 and float(f) <= 22 and float(d) < float(f)
        for plages in (rythme.get('plages') or {}).values() for d, f in plages))
    if (jour_seul and creuses > pleines) or (equipes in EQUIPES_NUIT and creuses == 0):
        alertes.append(_alerte(
            'incoherence_equipes_registres', 'rythme.equipes',
            'Équipes déclarées et registres de la facture incohérents (creuses %.0f kWh, '
            'pleines %.0f kWh) : à vérifier avec le client.' % (creuses, pleines),
            interne=True))
    for mois, bloc in enumerate(registres, start=1):
        for cle, libelle in (('puissance_atteinte_kw', 'puissance atteinte'),
                             ('puissance_atteinte_kva', 'puissance atteinte'),
                             ('kvarh', 'énergie réactive')):
            if (bloc or {}).get(cle) not in (None, ''):
                alertes.append(_alerte(
                    'registre_information', 'consommation.registres_mt',
                    'Mois %d : %s déclarée (%s) — information, sans effet sur la courbe.'
                    % (mois, libelle, bloc[cle]), niveau='info', interne=True))
    return _jours_types_gmt(calendrier, courbes), provenance, alertes


def _jours_types_gmt(calendrier, courbes):
    """Comme :func:`_jours_types`, pour des courbes DÉJÀ en heures GMT."""
    groupes = {}
    for jour, ouvert, type_cal, _p in calendrier:
        type_jour = type_cal if ouvert else 'ferme'
        cle = (jour.month, type_jour)
        cumul, n = groupes.get(cle, ([0.0] * HEURES, 0))
        groupes[cle] = ([c + g for c, g in zip(cumul, courbes[jour])], n + 1)
    ordre = {'ouvre': 0, 'samedi': 1, 'dimanche': 2, 'ferme': 3}
    return [{'mois': mois, 'type_jour': type_jour, 'nb_jours': groupes[(mois, type_jour)][1],
             'charge_kwh': [c / groupes[(mois, type_jour)][1]
                            for c in groupes[(mois, type_jour)][0]]}
            for (mois, type_jour) in sorted(groupes, key=lambda k: (k[0], ordre[k[1]]))]


def _mois_le_plus_proche(mois, mesures):
    return min(mesures, key=lambda m: (min(abs(m - mois), 12 - abs(m - mois)), m))


def courbe_mesuree_jours_types(valeurs_horaires, debut, *, annee_reference,
                               kwh_mensuels=None, source=None):
    """CIQ133 — jours types (GMT) depuis une courbe de charge MESURÉE.

    ``valeurs_horaires`` : kWh de chaque heure CIVILE consécutive depuis le
    jour ``debut`` (date ISO), déjà ramenés au pas horaire (parseur unique
    ``apps.calepinage.services.apercu_courbe_csv`` pour un fichier). Pour
    chaque mois MESURÉ : moyenne par type de jour × heure, ``nb_jours`` = jours
    réellement mesurés (énergie du mois = mesure). Mois NON mesurés : niveau =
    kWh mensuel déclaré, FORME empruntée au mois mesuré le plus proche
    (étiquetée) ; sans kWh déclaré, le mois est omis et dit.
    """
    alertes = []
    provenance = {
        'methode': 'courbe_mesuree', 'archetype': None, 'niveau_donnees': 'mesure',
        'heures': 'GMT', 'annee_reference': annee_reference, 'repartition': 'mesure',
        'talon': None, 'bornes': None, 'reponses_non_consommees': [],
        'couverture': None, 'mois_forme_empruntee': [], 'source': source,
    }
    try:
        jour = datetime.date.fromisoformat(str(debut)[:10])
    except (TypeError, ValueError):
        alertes.append(_alerte('courbe_mesuree_sans_debut', 'courbe_mesuree.debut',
                               'Courbe mesurée sans date de début lisible : ignorée.',
                               niveau='bloquant'))
        return None, provenance, alertes
    valeurs = [max(0.0, float(v or 0)) for v in valeurs_horaires or []]
    nb_jours = len(valeurs) // HEURES
    if nb_jours == 0:
        alertes.append(_alerte('courbe_mesuree_vide', 'courbe_mesuree',
                               'Courbe mesurée vide : ignorée.', niveau='bloquant'))
        return None, provenance, alertes
    groupes = {}
    for i in range(nb_jours):
        date = jour + datetime.timedelta(days=i)
        civile = valeurs[i * HEURES:(i + 1) * HEURES]
        gmt = _vers_gmt(civile, decalage_maroc_h(date))
        cle = (date.month, _type_calendaire(date))
        cumul, n = groupes.get(cle, ([0.0] * HEURES, 0))
        groupes[cle] = ([c + g for c, g in zip(cumul, gmt)], n + 1)
    fin = jour + datetime.timedelta(days=nb_jours - 1)
    provenance['couverture'] = {'debut': jour.isoformat(), 'fin': fin.isoformat(),
                                'jours': nb_jours}
    mesures = sorted({m for m, _t in groupes})
    sortie = [{'mois': m, 'type_jour': t, 'nb_jours': n, 'charge_kwh': [c / n for c in cumul]}
              for (m, t), (cumul, n) in groupes.items()]

    manquants = [m for m in range(1, 13) if m not in mesures]
    niveaux = None
    if isinstance(kwh_mensuels, (list, tuple)) and len(kwh_mensuels) == 12:
        niveaux = [None if v is None else float(v) for v in kwh_mensuels]
    compte = {}
    for date in _jours_annee(annee_reference):
        cle = (date.month, _type_calendaire(date))
        compte[cle] = compte.get(cle, 0) + 1
    for mois in manquants:
        if niveaux is None or niveaux[mois - 1] is None:
            alertes.append(_alerte('mois_non_mesure', 'courbe_mesuree',
                                   'Mois %d non mesuré et sans kWh déclaré : omis.' % mois))
            continue
        modele = _mois_le_plus_proche(mois, mesures)
        formes = [jt for jt in sortie if jt['mois'] == modele]
        energie_modele = sum(sum(jt['charge_kwh']) * compte.get((mois, jt['type_jour']), 0)
                             for jt in formes)
        if energie_modele <= 0:
            continue
        facteur = niveaux[mois - 1] / energie_modele
        for jt in formes:
            n = compte.get((mois, jt['type_jour']), 0)
            if n:
                sortie.append({'mois': mois, 'type_jour': jt['type_jour'], 'nb_jours': n,
                               'charge_kwh': [c * facteur for c in jt['charge_kwh']]})
        provenance['mois_forme_empruntee'].append(mois)
        alertes.append(_alerte(
            'forme_empruntee', 'courbe_mesuree',
            'Mois %d non mesuré : niveau déclaré, forme empruntée au mois mesuré %d.'
            % (mois, modele), niveau='info'))
    ordre = {'ouvre': 0, 'samedi': 1, 'dimanche': 2, 'ferme': 3}
    sortie.sort(key=lambda jt: (jt['mois'], ordre[jt['type_jour']]))
    return sortie, provenance, alertes


#: CIQ130 — catégories dont l'élément d'horaire S'AJOUTE à des heures
#: d'ouverture déjà déclarées (cuisson de nuit, garde de nuit) ; seul, il ne
#: décrit pas la journée.
CATEGORIES_PLAGES_ADDITIVES = frozenset({'boulangerie', 'sante'})


def _fusionner_categorie(rythme, categorie, alertes):
    """``(rythme fusionné, réponses non consommées)`` — la saisie gagne."""
    plages_cat, fermetures_cat, non_consommees, alertes_cat = elements_horaire(
        categorie, rythme.get('reponses_categorie'))
    alertes.extend(alertes_cat)
    if non_consommees:
        alertes.append(_alerte(
            'reponses_non_consommees', 'rythme.reponses_categorie',
            'Réponses sans effet sur la courbe (aucun coefficient sourcé) : %s.'
            % ', '.join(non_consommees), niveau='info', interne=True))
    if not plages_cat and not fermetures_cat:
        return rythme, non_consommees
    rythme = dict(rythme)
    if fermetures_cat:
        saisies = list(rythme.get('fermetures') or [])
        rythme['fermetures'] = saisies + [f for f in fermetures_cat if f not in saisies]
    if plages_cat:
        base = rythme.get('plages') or None
        if not base:
            equipes = _plages_equipes(rythme.get('equipes'), rythme.get('debut_equipe_h'))
            base = {'ouvre': equipes} if equipes else None
        if base is None and categorie in CATEGORIES_PLAGES_ADDITIVES:
            alertes.append(_alerte(
                'heures_jour_a_preciser', 'rythme.plages',
                "Plage de nuit déclarée : heures d'ouverture de jour à préciser "
                '(plage non placée).'))
            return rythme, non_consommees
        fusion = {k: [list(p) for p in v] for k, v in (base or {}).items()}
        for type_jour, plages in plages_cat.items():
            existantes = fusion.get(type_jour) or [list(p) for p in (base or {}).get('ouvre') or []]
            fusion[type_jour] = existantes + [p for p in plages if p not in existantes]
        rythme['plages'] = fusion
    return rythme, non_consommees


def courbe_declaree(rythme, kwh_mensuels, *, annee_reference, archetype=None, feries=None,
                    profil_societe=None, production_jours_types=None):
    """Jours types de charge (heures GMT), provenance et alertes.

    ``rythme`` : bloc ``rythme`` du contrat (jours_ouverts, plages, equipes,
    debut_equipe_h, fermetures, ramadan, talon). ``kwh_mensuels`` : 12 kWh
    déclarés, ou un total annuel (nombre). ``archetype`` : catégorie
    commerciale dont l'archétype CIQ107 sert de repli (ou ``None``).
    ``feries`` : dates SAISIES par la société (``None`` ⇒ ignorés, et dit).
    ``production_jours_types`` : ``[{mois, production_kwh_kwc[24]}]`` (CIQ109),
    requis seulement pour départager les deux bornes d'un talon inconnu.
    """
    rythme = rythme or {}
    alertes = []
    # CIQ130 — les réponses de catégorie deviennent des éléments d'HORAIRE
    # déclarés, fusionnés avec la saisie (la saisie gagne).
    rythme, non_consommees = _fusionner_categorie(
        rythme, rythme.get('categorie_commerciale') or archetype, alertes)
    calendrier, jours_declares, plages_declarees = _calendrier(
        rythme, annee_reference, feries, alertes)
    niveaux, repartition = _niveaux_mensuels(kwh_mensuels, calendrier, alertes)
    provenance = {
        'methode': None, 'archetype': None, 'niveau_donnees': None,
        'heures': 'GMT', 'annee_reference': annee_reference,
        'repartition': repartition, 'talon': None, 'bornes': None,
        'reponses_non_consommees': non_consommees,
    }
    if niveaux is None:
        alertes.append(_alerte('consommation_absente', 'consommation',
                               '12 kWh mensuels ou un total annuel requis.', niveau='bloquant'))
        return None, provenance, alertes

    talon = rythme.get('talon') or {}
    talon_kw = talon.get('kw')
    talon_pct = talon.get('part_pct')

    if not plages_declarees:
        if not archetype and not profil_societe:
            alertes.append(_alerte(
                'profil_declare_exige', 'rythme.plages',
                'Aucune plage ni équipe déclarée et aucun archétype sourcé : profil déclaré exigé.',
                niveau='bloquant'))
            return None, provenance, alertes
        courbes, source = _courbes_archetype(calendrier, niveaux, archetype, profil_societe, talon_kw)
        if courbes is None:
            alertes.append(_alerte('profil_declare_exige', 'rythme.plages', str(source),
                                   niveau='bloquant'))
            return None, provenance, alertes
        provenance.update({
            'methode': 'archetype',
            'archetype': {'cle': source.get('cle'), 'source': source.get('jeu_de_donnees')
                          or source.get('provenance'), 'licence': source.get('licence')},
            'niveau_donnees': 'estimation',
            'talon': {'valeur': {'kw': talon_kw} if talon_kw is not None else None,
                      'statut': 'declare' if talon_kw is not None else 'estimation'},
        })
        if not jours_declares:
            alertes.append(_alerte(
                'jours_ouverts_non_declares', 'rythme.jours_ouverts',
                "Jours ouverts non déclarés : la semaine de l'archétype sert (estimation).",
                niveau='info'))
        alertes.append(_alerte(
            'profil_estime', 'rythme',
            "Profil horaire estimé (archétype) : déclarer jours et heures d'ouverture "
            'pour un chiffre déclaré.', niveau='info'))
        return _jours_types(calendrier, courbes, annee_reference), provenance, alertes

    if not jours_declares:
        alertes.append(_alerte(
            'jours_ouverts_non_declares', 'rythme.jours_ouverts',
            'Jours ouverts non déclarés : aucun week-end supposé, profil déclaré incomplet.',
            niveau='bloquant'))
        return None, provenance, alertes

    provenance.update({'methode': 'declare', 'niveau_donnees': 'declare'})
    incoherent = False
    if talon_kw is not None:
        courbes, incoherent = _courbes_declarees(calendrier, niveaux, 'kw', talon_kw, None)
        provenance['talon'] = {'valeur': {'kw': float(talon_kw)}, 'statut': 'declare'}
    elif talon_pct is not None:
        courbes, incoherent = _courbes_declarees(calendrier, niveaux, 'part', talon_pct, None)
        provenance['talon'] = {'valeur': {'part_pct': float(talon_pct)}, 'statut': 'declare'}
    else:
        rapport = None
        if archetype or profil_societe:
            forme, src = forme_archetype(archetype, 'ouvre', 'hiver', profil_societe=profil_societe)
            if forme is not None and max(forme) > 0:
                rapport = min(forme) / max(forme)
        if rapport:
            courbes, incoherent = _courbes_declarees(calendrier, niveaux, 'rapport', None, rapport)
            provenance['talon'] = {
                'valeur': {'rapport_nuit_jour': rapport}, 'statut': 'estimation',
                'source': src.get('jeu_de_donnees') or src.get('provenance')}
            alertes.append(_alerte(
                'talon_estime', 'rythme.talon',
                'Talon non déclaré : rapport nuit/jour de l’archétype sourcé (estimation).',
                niveau='info'))
        else:
            bornes = {
                'talon_nul': _jours_types(
                    calendrier, _courbes_declarees(calendrier, niveaux, 'nul', None, None)[0],
                    annee_reference),
                'etale_24h': _jours_types(
                    calendrier, _courbes_declarees(calendrier, niveaux, 'etale', None, None)[0],
                    annee_reference),
            }
            alertes.append(_alerte(
                'talon_non_declare', 'rythme.talon',
                'Talon non déclaré : la borne donnant la MOINDRE autoconsommation sert à la taille.'))
            if not production_jours_types:
                alertes.append(_alerte(
                    'production_requise_pour_borne', 'production',
                    'Production horaire absente : les deux bornes du talon ne sont pas départagées.',
                    niveau='bloquant', interne=True))
                provenance['bornes'] = {'retenue': None, 'candidates': sorted(bornes)}
                return None, provenance, alertes
            retenue = _choisir_borne(bornes, production_jours_types)
            provenance['bornes'] = {'retenue': retenue, 'candidates': sorted(bornes)}
            provenance['talon'] = {'valeur': None, 'statut': 'borne_conservatrice'}
            return bornes[retenue], provenance, alertes
    if incoherent:
        alertes.append(_alerte(
            'talon_incoherent', 'rythme.talon',
            'Talon déclaré incompatible avec les kWh du mois (ou aucune heure de plage) : '
            'consommation du mois répartie à plat.'))
    return _jours_types(calendrier, courbes, annee_reference), provenance, alertes
