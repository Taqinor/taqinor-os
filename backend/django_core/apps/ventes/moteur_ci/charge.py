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
from apps.ventes.moteur_ci.profils import (
    MOTIF_PROFIL_DECLARE, SAISONS, TYPES_JOUR, forme_archetype,
)
from apps.ventes.moteur_ci.talons import talon_par_defaut
from apps.ventes.ramadan import plage_ramadan_pour

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


def _ramadan_table(ramadan, annee):
    """CLD15 — ``(du, au)`` de la table sourcée ``apps/ventes/ramadan.py`` pour
    l'année de RÉFÉRENCE quand le Ramadan déclaré a des plages mais aucune
    date ; ``None`` sinon (dates saisies, ou table muette pour cette année)."""
    if not (isinstance(ramadan, dict) and ramadan.get('plages')
            and not ramadan.get('du') and not ramadan.get('au')):
        return None
    trouve = plage_ramadan_pour(datetime.date(annee, 1, 1))
    if trouve is None or trouve[0]['debut'].year != annee:
        return None
    return trouve[0]['debut'], trouve[0]['fin']


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
        table = _ramadan_table(ramadan, annee)
        try:
            ramadan_bornes = (_date(ramadan['du'], annee), _date(ramadan['au'], annee))
        except (KeyError, TypeError, ValueError, IndexError):
            if table is not None:
                ramadan_bornes = (_date(table[0], annee), _date(table[1], annee))
            else:
                alertes.append(_alerte('ramadan_sans_dates', 'rythme.ramadan',
                                       'Plages Ramadan déclarées sans dates : ignorées.'))
        if ramadan and not plages_par_type:
            alertes.append(_alerte(
                'ramadan_sans_plages', 'rythme.ramadan',
                "Ramadan déclaré mais aucune plage d'ouverture : le rythme du Ramadan "
                'est ignoré (profil archétype).', niveau='info', interne=True))

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
            # CAD177 — mois SANS heure ouverte (fermeture du mois entier) : le
            # rapport nuit/jour ne situe aucun talon, la facture du mois entier
            # deviendrait le « talon » en silence. Contradiction dite, jamais tue.
            if somme_occ <= 0 and energie > 1e-9:
                incoherent = True
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


def _courbes_archetype(calendrier, niveaux, categorie, profil_societe, talon_kw,
                       talon_part_pct=None, niveau_jour_pct=None):
    """Méthode ``archetype`` : forme sourcée (CIQ107) par jour ouvert.

    Talon DÉCLARÉ (CLD1), par priorité ``kw`` > ``part_pct`` > ``niveau_jour_pct`` :
    ``kw`` = niveau des jours fermés ; ``part_pct`` = part de l'énergie du mois
    étalée à plat sur 24 h × jours (même logique que le chemin déclaré) ;
    ``niveau_jour_pct`` = PLANCHER : chaque heure vaut au moins ce rapport × le
    pic de la forme « ouvre » de la même saison (jours fermés compris), puis la
    courbe est renormalisée à l'énergie du mois.
    """
    par_mois = {}
    for entree in calendrier:
        par_mois.setdefault(entree[0].month, []).append(entree)
    rapport = None
    if talon_kw is None and talon_part_pct is None and niveau_jour_pct is not None:
        rapport = float(niveau_jour_pct) / 100.0
    courbes = {}
    source = None
    pics = {}
    for mois, jours in par_mois.items():
        formes = {}
        plancher = {}
        for jour, ouvert, type_cal, _p in jours:
            saison = saison_bdew(jour)
            forme, src = forme_archetype(categorie, type_cal, saison,
                                         profil_societe=profil_societe)
            if forme is None:
                return None, src
            source = src
            if rapport is not None:
                if saison not in pics:
                    ouvre, _s = forme_archetype(categorie, 'ouvre', saison,
                                                profil_societe=profil_societe)
                    pics[saison] = max(ouvre if ouvre is not None else forme)
                plancher[jour] = rapport * pics[saison]
                forme = [max(f, plancher[jour]) for f in forme] if ouvert else forme
            formes[jour] = forme
        energie = niveaux[mois - 1]
        part_plat = 0.0
        if talon_kw is None and talon_part_pct is not None:
            part_plat = (energie * min(max(float(talon_part_pct), 0.0), 100.0) / 100.0
                         / (HEURES * len(jours)))
            energie -= part_plat * HEURES * len(jours)
        n_ouverts = sum(1 for _j, o, _t, _p in jours if o)
        n_fermes = len(jours) - n_ouverts
        poids_ouvert = sum(sum(formes[j]) if rapport is not None else 1.0
                           for j, o, _t, _p in jours if o)
        poids_ferme = [max(min(formes[j]), plancher.get(j, 0.0))
                       for j, o, _t, _p in jours if not o]
        if talon_kw is not None:
            reste = max(0.0, energie - float(talon_kw) * HEURES * n_fermes)
            energie_jour = reste / n_ouverts if n_ouverts else 0.0
            talon_ferme = float(talon_kw) if n_ouverts else energie / (HEURES * len(jours))
        else:
            # talon d'un jour fermé = creux de l'archétype ramené au niveau du jour ouvert
            denominateur = poids_ouvert + HEURES * sum(poids_ferme)
            energie_jour = energie / denominateur if denominateur > 0 else 0.0
            talon_ferme = None
        for jour, ouvert, _t, _p in jours:
            if ouvert:
                courbes[jour] = [part_plat + energie_jour * w for w in formes[jour]]
            else:
                niveau = (talon_ferme if talon_ferme is not None else
                          energie_jour * max(min(formes[jour]), plancher.get(jour, 0.0)))
                courbes[jour] = [part_plat + niveau] * HEURES
    return courbes, source


def _resoudre_decalage(decalage_h):
    """CLD3 — décalage civil→GMT : ``None`` ⇒ constant du régime en vigueur
    (``decalage_maroc_h(None)``, un site garde ses horaires d'horloge) ; un
    entier ⇒ ce décalage ; ``'historique'`` ⇒ ``None`` (date par date)."""
    if decalage_h == 'historique':
        return None
    if decalage_h is None:
        return decalage_maroc_h(None)
    return int(decalage_h)


def _jours_types(calendrier, courbes, annee, decalage_h=None):
    fixe = _resoudre_decalage(decalage_h)
    groupes = {}
    for jour, ouvert, type_cal, _p in calendrier:
        type_jour = type_cal if ouvert else 'ferme'
        cle = (jour.month, type_jour)
        gmt = _vers_gmt(courbes[jour], decalage_maroc_h(jour) if fixe is None else fixe)
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


def courbe_registres_mt(rythme, registres, *, annee_reference, feries=None,
                        decalage_h=None):
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
    toucher la courbe. ``decalage_h`` (CLD3) est accepté pour l'uniformité des
    trois chemins mais SANS effet ici : les postes sont déjà en heures GMT.
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
        if fermes and ouverts:
            # CLD14 — le talon plat des jours fermés ne dépasse jamais le plus
            # petit registre rapporté à ses heures : sinon ``reste < 0 → 0``
            # AJOUTE de l'énergie (Σ courbe > Σ registres).
            plafonds = {p: energie[p] / (heures_poste[p] * len(fermes))
                        for p in POSTES_MT if heures_poste[p]}
            limite = min(plafonds, key=plafonds.get) if plafonds else None
            if limite is not None and talon > plafonds[limite] + 1e-12:
                talon = plafonds[limite]
                alertes.append(_alerte(
                    'talon_plafonne_au_registre', 'consommation.registres_mt',
                    'Mois %d : talon des jours fermés plafonné par le registre « %s » '
                    '(%.3f kW)%s.' % (mois, limite, talon,
                                      ' : jours fermés à zéro' if talon <= 0 else ''),
                    niveau='info', interne=True))
        talons.append(round(talon, 6))
        if not ouverts and jours:
            # CLD5 — aucun jour ouvert ce mois : pas de talon « 24 h plat » (il
            # perdrait pointe / pleines) ; chaque registre est réparti sur les
            # heures de SON poste, tous les jours du mois.
            niveau = {p: energie[p] / (heures_poste[p] * len(jours)) if heures_poste[p] else 0.0
                      for p in POSTES_MT}
            talons[-1] = round(niveau['creuses'], 6)
            alertes.append(_alerte(
                'registre_hors_ouverture', 'consommation.registres_mt',
                'Mois %d : aucun jour ouvert, mais des registres relevés : chaque poste '
                'est réparti sur ses heures de tous les jours du mois.' % mois,
                niveau='info', interne=True))
            for jour, _o, _t, _p in jours:
                courbes[jour] = [niveau[postes_h[mois][h]] for h in range(HEURES)]
            continue
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


def _valeur_mesuree(v):
    """kWh d'une heure mesurée, ou ``None`` (absent, illisible, NaN)."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if x != x else max(0.0, x)


def valeurs_horaires_depuis_points(points, *, pas_min, unite='kwh'):
    """CLD6 — points JSON d'une courbe mesurée → kWh de chaque heure CIVILE.

    ``pas_min`` : pas des points en minutes, tout diviseur de 60 (5, 10, 15,
    20, 30, 60…). ``unite`` : ``kwh`` (énergie du pas, sommée) ou ``kw``
    (puissance moyenne du pas : × pas/60 avant la somme). Une heure dont un
    point est absent (``None``) vaut ``None`` (jour écarté, CLD4). Pas qui ne
    divise pas 60, ou nombre de points non multiple de 60/pas ⇒
    ``ValueError`` en français (le branchement la convertit en 400).
    """
    try:
        pas = int(pas_min)
    except (TypeError, ValueError):
        pas = 0
    if pas <= 0 or 60 % pas:
        raise ValueError(
            'Pas de la courbe mesurée de %s min non pris en charge : un pas qui '
            'divise 60 min (5, 10, 15, 20, 30 ou 60) est attendu.' % pas_min)
    par_heure = 60 // pas
    points = list(points or [])
    if len(points) % par_heure:
        raise ValueError(
            'La courbe mesurée au pas de %d min compte %d points : un multiple de %d '
            '(une heure entière) est attendu.' % (pas, len(points), par_heure))
    facteur = pas / 60.0 if unite == 'kw' else 1.0
    sortie = []
    for i in range(0, len(points), par_heure):
        groupe = [_valeur_mesuree(v) for v in points[i:i + par_heure]]
        sortie.append(None if any(v is None for v in groupe) else sum(groupe) * facteur)
    return sortie


def _mois_le_plus_proche(mois, mesures):
    return min(mesures, key=lambda m: (min(abs(m - mois), 12 - abs(m - mois)), m))


def courbe_mesuree_jours_types(valeurs_horaires, debut, *, annee_reference,
                               kwh_mensuels=None, source=None, decalage_h=None):
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
    valeurs = [_valeur_mesuree(v) for v in valeurs_horaires or []]
    nb_jours = len(valeurs) // HEURES
    if nb_jours == 0:
        alertes.append(_alerte('courbe_mesuree_vide', 'courbe_mesuree',
                               'Courbe mesurée vide : ignorée.', niveau='bloquant'))
        return None, provenance, alertes
    fixe = _resoudre_decalage(decalage_h)
    compte = {}
    for date in _jours_annee(annee_reference):
        cle = (date.month, _type_calendaire(date))
        compte[cle] = compte.get(cle, 0) + 1
    # CLD4 — un jour manquant ou à valeur absente n'est PAS un zéro : écarté.
    groupes = {}
    mesures_mois = {}
    ecartes = {}
    for i in range(nb_jours):
        date = jour + datetime.timedelta(days=i)
        civile = valeurs[i * HEURES:(i + 1) * HEURES]
        if any(v is None for v in civile):
            ecartes[date.month] = ecartes.get(date.month, 0) + 1
            continue
        gmt = _vers_gmt(civile, decalage_maroc_h(date) if fixe is None else fixe)
        cle = (date.month, _type_calendaire(date))
        cumul, n = groupes.get(cle, ([0.0] * HEURES, 0))
        groupes[cle] = ([c + g for c, g in zip(cumul, gmt)], n + 1)
        mesures_mois[date.month] = mesures_mois.get(date.month, 0) + 1
    fin = jour + datetime.timedelta(days=nb_jours - 1)
    provenance['couverture'] = {'debut': jour.isoformat(), 'fin': fin.isoformat(),
                                'jours': nb_jours}
    if not groupes:
        alertes.append(_alerte('courbe_mesuree_vide', 'courbe_mesuree',
                               'Courbe mesurée sans aucun jour complet : ignorée.',
                               niveau='bloquant'))
        return None, provenance, alertes
    mesures = sorted({m for m, _t in groupes})
    sortie = []
    for (m, t), (cumul, n) in groupes.items():
        moyenne = [c / n for c in cumul]
        sortie.append({'mois': m, 'type_jour': t,
                       'nb_jours': compte.get((m, t), n), 'charge_kwh': moyenne})
    # Mois partiel : un type de jour jamais mesuré ce mois-là emprunte la
    # moyenne de TOUS les jours mesurés du mois (dit dans l'alerte).
    partiels = []
    for m in mesures:
        du_mois = [jt for jt in sortie if jt['mois'] == m]
        total_calendaire = sum(v for (mm, _t), v in compte.items() if mm == m)
        if mesures_mois[m] >= total_calendaire and not ecartes.get(m):
            continue
        partiels.append('mois %d : %d jour(s) mesuré(s) sur %d%s' % (
            m, mesures_mois[m], total_calendaire,
            ', %d écarté(s) (valeur absente)' % ecartes[m] if ecartes.get(m) else ''))
        n_mesures = sum(groupes[(m, jt['type_jour'])][1] for jt in du_mois)
        moyenne_mois = [sum(groupes[(m, jt['type_jour'])][0][h] for jt in du_mois) / n_mesures
                        for h in range(HEURES)]
        for t in ('ouvre', 'samedi', 'dimanche'):
            if (m, t) not in groupes and compte.get((m, t)):
                sortie.append({'mois': m, 'type_jour': t, 'nb_jours': compte[(m, t)],
                               'charge_kwh': list(moyenne_mois)})
    if partiels:
        alertes.append(_alerte(
            'mesure_incomplete', 'courbe_mesuree',
            'Courbe mesurée incomplète — niveau = moyenne des jours mesurés × jours du '
            'mois : %s.' % ' ; '.join(partiels), niveau='info', interne=True))

    manquants = [m for m in range(1, 13) if m not in mesures]
    niveaux = None
    if isinstance(kwh_mensuels, (list, tuple)) and len(kwh_mensuels) == 12:
        niveaux = [None if v is None else float(v) for v in kwh_mensuels]
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


#: ADEV76 — feuilles du rythme qu'un profil déclaré peut exiger, dans
#: l'ordre où la fiche lead les pose (les jours, puis les heures).
FEUILLE_JOURS = 'rythme.jours_ouverts'
FEUILLE_PLAGES = 'rythme.plages'


def _repli_source(categorie, profil_societe):
    """``(True, None)`` si le profil SAISI par la société ou l'archétype
    vendorisé couvre TOUS les (type de jour, saison) que lit
    :func:`_courbes_archetype` ; sinon ``(False, motif)``."""
    for type_jour in TYPES_JOUR:
        for saison in SAISONS:
            forme, motif = forme_archetype(categorie, type_jour, saison,
                                           profil_societe=profil_societe)
            if forme is None:
                return False, str(motif)
    return True, None


def profil_charge_prerequis(rythme, categorie=None, profil_societe=None):
    """ADEV76 (D-ACI-5=a) — LA règle des prérequis du profil de charge.

    Rend la liste ORDONNÉE des feuilles du rythme qui manquent pour que
    :func:`courbe_declaree` trace un profil (``[]`` = prêt) :

    * plages déclarées = heures (``plages``) OU régime d'équipes placé (3x8 /
      continu, ou 1x8 / 2x8 avec ``debut_equipe_h``) OU réponses de catégorie
      qui posent un horaire (CIQ130) ;
    * dès que des plages existent, les jours ouverts sont exigés ;
    * sans plage : le profil SAISI par la société ou l'archétype vendorisé de
      ``categorie`` suffit ; sinon les jours (s'ils manquent) puis les plages.

    ``categorie`` : catégorie commerciale (``industriel`` ⇒ aucun archétype).
    Pure, sans alerte : :func:`courbe_declaree` l'appelle pour décider, et
    ``apps.ventes.selectors.profil_charge_prerequis_ci`` l'expose aux autres
    apps (la fiche lead la lit, jamais une copie).
    """
    rythme = rythme or {}
    fusionne, _non_consommees = _fusionner_categorie(
        rythme, rythme.get('categorie_commerciale') or categorie, [])
    jours = fusionne.get('jours_ouverts')
    jours_declares = jours is not None and len(jours) == 7
    plages = bool(fusionne.get('plages')) or _plages_equipes(
        fusionne.get('equipes'), fusionne.get('debut_equipe_h')) is not None
    if plages:
        return [] if jours_declares else [FEUILLE_JOURS]
    if _repli_source(categorie, profil_societe)[0]:
        return []
    return ([] if jours_declares else [FEUILLE_JOURS]) + [FEUILLE_PLAGES]


def _signaler_cellules_completees(cellules, archetype, profil_societe, provenance, alertes):
    """CLD16 — un profil société PARTIEL (CAL149 : saisons ou types de jour
    absents) retombe sur l'archétype pour les cellules manquantes : les liste
    en provenance et en alerte interne (``cellules`` : paires lues)."""
    if not profil_societe:
        return
    completees = []
    for type_jour, saison in sorted(cellules, key=lambda c: (TYPES_JOUR.index(c[0]),
                                                             SAISONS.index(c[1]))):
        forme, src = forme_archetype(archetype, type_jour, saison, profil_societe=profil_societe)
        if forme is not None and src.get('type') != 'profil_societe':
            completees.append('%s/%s' % (type_jour, saison))
    if not completees:
        return
    provenance['profil_societe_completee'] = {'cellules': completees, 'complete_par': archetype}
    alertes.append(_alerte(
        'profil_societe_complete', 'consommation.profil_societe',
        "Profil société partiel : cellules (type de jour/saison) complétées par l'archétype "
        '« %s » : %s.' % (archetype, ', '.join(completees)), niveau='info', interne=True))


def courbe_declaree(rythme, kwh_mensuels, *, annee_reference, archetype=None, feries=None,
                    profil_societe=None, production_jours_types=None, segment=None,
                    decalage_h=None):
    """Jours types de charge (heures GMT), provenance et alertes.

    ``rythme`` : bloc ``rythme`` du contrat (jours_ouverts, plages, equipes,
    debut_equipe_h, fermetures, ramadan, talon). ``kwh_mensuels`` : 12 kWh
    déclarés, ou un total annuel (nombre). ``archetype`` : catégorie
    commerciale dont l'archétype CIQ107 sert de repli (ou ``None``).
    ``feries`` : dates SAISIES par la société (``None`` ⇒ ignorés, et dit).
    ``production_jours_types`` : ``[{mois, production_kwh_kwc[24]}]`` (CIQ109),
    requis seulement pour départager les deux bornes d'un talon inconnu.
    ``segment`` : ``commercial`` ⇒ un commerce SANS catégorie reçoit aussi le
    talon défaut fondateur (fondateur 27/10/2026) ; sinon la borne décide.
    ``decalage_h`` (CLD3, décision prise pour le fondateur, à revoir) : ``None``
    ⇒ décalage CONSTANT du régime en vigueur (le Maroc est à UTC+0 depuis le
    20/09/2026), un entier ⇒ ce décalage, ``'historique'`` ⇒ date par date.
    """
    rythme = rythme or {}
    rythme_saisi = rythme
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

    if _ramadan_table(rythme.get('ramadan'), annee_reference) is not None:
        provenance['ramadan'] = {
            'source': 'dates Ramadan %d : apps/ventes/ramadan.py' % annee_reference,
            'statut': 'table'}
    talon = _talon_valide(rythme.get('talon'), alertes)
    talon_kw = talon.get('kw')
    talon_pct = talon.get('part_pct')

    # ADEV76 — LA règle des prérequis (partagée avec la fiche lead).
    manquants = profil_charge_prerequis(rythme_saisi, archetype, profil_societe)
    if FEUILLE_PLAGES in manquants:
        if FEUILLE_JOURS in manquants:
            alertes.append(_alerte(
                'jours_ouverts_non_declares', FEUILLE_JOURS,
                'Jours ouverts non déclarés : aucun week-end supposé, profil déclaré incomplet.',
                niveau='bloquant'))
        motif = ('Aucune plage ni équipe déclarée et aucun archétype sourcé : profil déclaré exigé.'
                 if not archetype and not profil_societe
                 else _repli_source(archetype, profil_societe)[1])
        alertes.append(_alerte('profil_declare_exige', FEUILLE_PLAGES,
                               motif or MOTIF_PROFIL_DECLARE, niveau='bloquant'))
        return None, provenance, alertes

    if not plages_declarees:
        niveau_pct = talon.get('niveau_jour_pct')
        courbes, source = _courbes_archetype(calendrier, niveaux, archetype, profil_societe, talon_kw,
                                             talon_pct, niveau_pct)
        _signaler_cellules_completees(
            {(t, saison_bdew(j)) for j, _o, t, _p in calendrier}, archetype, profil_societe,
            provenance, alertes)
        declare = ({'kw': talon_kw} if talon_kw is not None
                   else {'part_pct': float(talon_pct)} if talon_pct is not None
                   else {'niveau_jour_pct': float(niveau_pct)} if niveau_pct is not None
                   else None)
        provenance.update({
            'methode': 'archetype',
            'archetype': {'cle': source.get('cle'), 'source': source.get('jeu_de_donnees')
                          or source.get('provenance'), 'licence': source.get('licence')},
            'niveau_donnees': 'estimation',
            'talon': {'valeur': declare, 'statut': 'declare' if declare else 'estimation'},
        })
        if not jours_declares:
            alertes.append(_alerte(
                'jours_ouverts_non_declares', 'rythme.jours_ouverts',
                "Jours ouverts non déclarés : chaque jour reçoit la même énergie (seules les formes "
                "de l'archétype servent) — déclarer les jours ouverts.",
                niveau='info', interne=True))
        alertes.append(_alerte(
            'profil_estime', 'rythme',
            "Profil horaire estimé (archétype) : déclarer jours et heures d'ouverture "
            'pour un chiffre déclaré.', niveau='info'))
        return _jours_types(calendrier, courbes, annee_reference, decalage_h), provenance, alertes

    if FEUILLE_JOURS in manquants:
        alertes.append(_alerte(
            'jours_ouverts_non_declares', FEUILLE_JOURS,
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
        if talon.get('niveau_jour_pct') is None:
            _signaler_cellules_completees(
                {('ouvre', saison_bdew(j)) for j, o, _t, _p in calendrier if o}, archetype,
                profil_societe, provenance, alertes)
        par_defaut = _courbes_talon_par_defaut(calendrier, niveaux, archetype, profil_societe,
                                               provenance, alertes, talon, segment)
        if par_defaut is not None:
            courbes, incoherent = par_defaut
        else:
            courbes_nul, incoherent_nul = _courbes_declarees(calendrier, niveaux, 'nul', None, None)
            courbes_etale, incoherent_etale = _courbes_declarees(
                calendrier, niveaux, 'etale', None, None)
            incoherent = incoherent_nul or incoherent_etale
            bornes = {
                'talon_nul': _jours_types(calendrier, courbes_nul, annee_reference, decalage_h),
                'etale_24h': _jours_types(calendrier, courbes_etale, annee_reference, decalage_h),
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
            _alerte_talon_incoherent(incoherent, alertes)
            return bornes[retenue], provenance, alertes
    _alerte_talon_incoherent(incoherent, alertes)
    return _jours_types(calendrier, courbes, annee_reference, decalage_h), provenance, alertes


def _rapport_hors_plages(calendrier, archetype, profil_societe):
    """CLD2 — ``(rapport, source, sans_objet)`` : moyenne de la forme (« ouvre »
    de la saison, archétype ou profil société) HORS des plages déclarées ÷
    moyenne DANS les plages, sur les jours ouverts du calendrier (heures
    civiles) — les saisons pèsent leur nombre de jours ouverts. ``sans_objet`` :
    les plages couvrent les 24 h (aucune heure hors plage). ``rapport`` ``None``
    quand aucune forme ne se lit ou qu'aucune heure n'est déclarée."""
    formes = {}
    dedans = [0.0, 0.0]
    dehors = [0.0, 0.0]
    src = None
    for jour, ouvert, _t, plages in calendrier:
        if not ouvert:
            continue
        saison = saison_bdew(jour)
        if saison not in formes:
            formes[saison] = forme_archetype(archetype, 'ouvre', saison,
                                             profil_societe=profil_societe)
        forme, src = formes[saison]
        if forme is None:
            return None, None, False
        for h, occ in enumerate(_occupation(plages)):
            dedans[0] += occ * forme[h]
            dedans[1] += occ
            dehors[0] += (1.0 - occ) * forme[h]
            dehors[1] += 1.0 - occ
    if dedans[1] <= 1e-9 or dedans[0] <= 0:
        return None, None, False
    if dehors[1] <= 1e-9:
        return None, src, True
    return (dehors[0] / dehors[1]) / (dedans[0] / dedans[1]), src, False


def _courbes_talon_par_defaut(calendrier, niveaux, archetype, profil_societe, provenance,
                              alertes, talon_saisi=None, segment=None):
    """Talon NON déclaré, horaires déclarés : ``(courbes, incoherent)`` qui
    SUIVENT les horaires, ou ``None`` (aucune catégorie commerciale ni
    archétype : la borne conservatrice décide).

    Décision fondateur 26/10/2026 : talon = niveau hors horaires de
    l'archétype (le sien, le plus proche, ou le profil saisi par la société),
    sinon le défaut fondateur de 20 % (``talons.talon_par_defaut``).
    Décision prise pour le fondateur (à revoir) 27/10/2026 : % du niveau de
    jour = moyenne hors plages ÷ moyenne dans les plages (CLD2 — et non plus le
    rapport creux / pic de la forme). Plages sur 24 h ⇒ talon sans objet.
    Fondateur 27/10/2026 — UNE définition : ``talon.niveau_jour_pct`` DÉCLARÉ
    (réponse « équipements hors horaires ») est un % du niveau des heures
    ouvertes, appliqué par la MÊME règle que les défauts.
    """
    declare = (talon_saisi or {}).get('niveau_jour_pct')
    if declare is not None:
        rapport = float(declare) / 100.0
        provenance['talon'] = {'valeur': {'niveau_jour_pct': float(declare)}, 'statut': 'declare'}
        return _courbes_declarees(calendrier, niveaux, 'rapport', None, rapport)
    rapport, src = None, None
    if archetype or profil_societe:
        rapport, src, sans_objet = _rapport_hors_plages(calendrier, archetype, profil_societe)
        if sans_objet:
            provenance['talon'] = {'valeur': None, 'statut': 'sans_objet',
                                   'source': 'plages sur 24 h : aucune heure hors horaires'}
            return _courbes_declarees(calendrier, niveaux, 'nul', None, None)
    source = (src.get('jeu_de_donnees') or src.get('provenance')) if rapport is not None else None
    rapport, talon = talon_par_defaut(archetype, rapport, source,
                                      commercial=segment == 'commercial')
    if rapport is None:
        return None
    provenance['talon'] = {'valeur': {'rapport_nuit_jour': rapport},
                           'statut': talon['statut'], 'source': talon['source']}
    alertes.append(_alerte(
        'talon_estime', 'rythme.talon',
        'Talon non déclaré : niveau hors horaires de l’archétype sourcé (estimation).'
        if talon['statut'] == 'estimation' else
        'Talon non déclaré : 20 % de la puissance des heures ouvertes (défaut fondateur), '
        'à confirmer avec le client.', niveau='info'))
    return _courbes_declarees(calendrier, niveaux, 'rapport', None, rapport)


def _talon_valide(talon, alertes):
    """CLD7 — le talon déclaré sans valeur négative : une valeur < 0 est
    ignorée (alerte interne), le talon retombe sur l'estimé."""
    propre = {}
    for cle, valeur in (talon or {}).items():
        try:
            negatif = valeur is not None and float(valeur) < 0
        except (TypeError, ValueError):
            negatif = False
        if negatif:
            alertes.append(_alerte(
                'talon_negatif', 'rythme.talon.%s' % cle,
                'Talon négatif (%s = %s) ignoré : le talon estimé sert.' % (cle, valeur),
                interne=True))
        else:
            propre[cle] = valeur
    return propre


def _alerte_talon_incoherent(incoherent, alertes):
    if incoherent:
        alertes.append(_alerte(
            'talon_incoherent', 'rythme.talon',
            'Talon déclaré incompatible avec les kWh du mois (ou aucune heure de plage) : '
            'consommation du mois répartie à plat.'))
