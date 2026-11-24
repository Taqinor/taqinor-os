"""Option « AVEC BATTERIE » C&I en HAUTE TENSION — côté orchestrateur (HT24,
décision fondateur du 24/11/2026 : « With battery now also picks from HV
inverters »).

Les règles pures (grappe en série, tailles admissibles, appairage par la
tension) vivent dans ``moteur_ci.batterie_ht`` ; ce module lit la famille
haute tension du catalogue (par les sélecteurs ``stock``, comme
``etude_ci_batterie``), l'apparie, et rejoue LE MÊME dimensionnement que la
basse tension (``etude_ci_batterie._dimensionner`` : règle marginale sur la
banque, « batteries toujours pleines », combinaison homogène d'hybrides, AC ≤
puissance souscrite).

ORDRE DES FAMILLES — choix de l'orchestrateur, que le fondateur n'a pas vu,
gardé en UN seul endroit (:func:`haute_tension_a_essayer`) : la basse tension
d'abord, à l'identique d'avant ; la haute tension n'est essayée que quand la
basse tension ne compose AUCUNE option. Rien n'est jamais mêlé : un hybride
haute tension ne reçoit qu'une batterie en série, et inversement.

Rien n'est tu : tout article haute tension que l'option n'a pas pu prendre est
NOMMÉ avec son motif (alertes internes ``HYBRIDE_HAUTE_TENSION_ECARTE``,
``BATTERIE_HAUTE_TENSION_ECARTEE``, ``HYBRIDE_PARALLELE_NON_PUBLIE``).
"""
from __future__ import annotations

from apps.ventes.moteur_ci import batterie_ht as regles

CLE = 'ht'


def famille_vide():
    return {'hybrides': [], 'batteries': [], 'elements': [], 'ecartes': []}


def _num(valeur):
    try:
        return float(valeur) if valeur is not None else None
    except (TypeError, ValueError):
        return None


def ajouter_hybride(famille, produit, plage, triphase):
    """Un hybride HAUTE tension du catalogue (fenêtre batterie au-delà de
    60 V) : la forme des hybrides de l'option, plus ses entrées batterie et
    sa limite de parallèle PUBLIÉES (une seule unité quand elle ne l'est pas,
    jamais la limite d'un autre modèle)."""
    from apps.stock.selectors import specs_for_produit

    from .etude_ci_batterie import _element, _hybride
    specs = specs_for_produit(produit) or {}
    publie = regles._entier(specs.get('max_parallele'))
    famille['hybrides'].append(dict(
        _hybride(produit, specs, plage, triphase), bat_nb_entrees=specs.get('bat_nb_entrees'),
        max_parallele_publie=publie, max_parallele=publie or 1))
    famille['elements'].append(_element(produit, 'onduleur_hybride', {
        'ond_phases': specs.get('phases'), 'ond_n_mppt': specs.get('n_mppt'),
        'ond_ac_kw': specs.get('ac_kw')}))


def _haute_tension_par_nom_ou_tension(produit, specs):
    """Repli pour une fiche NON complétée : tension nominale au-delà du port
    basse tension, ou « haute tension » dans le nom (``BAT-DYN-HV-16``)."""
    from apps.ventes.moteur_ci.batterie import TENSION_PORT_BT_MAX_V
    v = _num(specs.get('v_nominal'))
    if v is not None:
        return v > TENSION_PORT_BT_MAX_V
    return 'haute tension' in (getattr(produit, 'nom', '') or '').lower()


def ajouter_batterie(famille, produit, specs):
    """Range une batterie dans la famille haute tension. Vrai quand sa fiche
    déclare une grappe en série (elle n'est alors PAS une batterie basse
    tension) ; faux sinon (le chemin basse tension la lit comme avant) — un
    pack haute tension sans grappe publiée est NOMMÉ."""
    from .etude_ci_batterie import _batterie
    serie = {'serie_min': specs.get('serie_min_modules'), 'serie_max': specs.get('serie_max_modules'),
             'v_module': specs.get('v_module'), 'grappes_max': specs.get('grappes_max_parallele')}
    if not regles.declare_serie(serie):
        if _haute_tension_par_nom_ou_tension(produit, specs):
            famille['ecartes'].append(('batterie', produit.nom, 'grappe en série non publiée sur la fiche ('
                                       + ', '.join(lib for _c, lib in regles.CHAMPS_SERIE) + ')'))
        return False
    batterie = dict(_batterie(produit, specs), **serie)
    manque = regles.manque_serie(serie) + ([] if batterie['kwh_utile'] else ['capacité utile'])
    if manque:
        famille['ecartes'].append(('batterie', produit.nom, 'fiche incomplète : ' + ', '.join(manque)))
    else:
        famille['batteries'].append(batterie)
    return True


def famille_des_lignes(bat_bt, lignes, devis=None):
    """``(bat, haute tension?)`` de l'option « avec » des LIGNES d'un devis :
    la famille haute tension quand une ligne porte un hybride haute tension
    ET que le devis l'ouvre (``regles_calcul.hybrides_ht_ouverts`` — un devis
    créé avant garde ce qu'il a reçu) ; sinon la basse tension, inchangée."""
    from .regles_calcul import hybrides_ht_ouverts
    famille = (bat_bt or {}).get(CLE) or famille_vide()
    ids = {h['produit'] for h in famille['hybrides']}
    if not ids or not any(getattr(li, 'produit_id', None) in ids for li in lignes or []):
        return bat_bt, False
    devis = devis or next((d for d in (getattr(li, 'devis', None) for li in lignes or [])
                           if d is not None), None)
    if not hybrides_ht_ouverts(devis):
        return bat_bt, False
    return {'hybrides': famille['hybrides'], 'batteries': famille['batteries'],
            'elements': famille['elements']}, True


def haute_tension_a_essayer(resultat_bt):
    """LE choix de l'ordre des familles : la haute tension n'est essayée que
    quand la basse tension ne compose aucune option."""
    return (resultat_bt or {}).get('evaluation') is None


def _alerte(code, message, niveau='alerte'):
    from .etude_ci_batterie import _alerte as alerte
    return alerte(code, message, niveau)


def _alertes_ecartes(ecartes):
    """Les articles haute tension écartés, NOMMÉS avec leur motif, groupés par
    famille d'article."""
    alertes = []
    for genre, code, libelle in (('hybride', 'HYBRIDE_HAUTE_TENSION_ECARTE', 'Onduleurs hybrides'),
                                 ('batterie', 'BATTERIE_HAUTE_TENSION_ECARTEE', 'Batteries')):
        motifs = ['%s (%s)' % (nom, motif) for g, nom, motif in ecartes if g == genre]
        if motifs:
            alertes.append(_alerte(code, "%s haute tension écartés de l'option « avec » : %s." % (
                libelle, ' ; '.join(motifs))))
    return alertes


def _apparier(famille):
    """``(hybrides, batteries, écartés)`` : chaque hybride avec au moins une
    batterie qui forme une grappe valide sur sa fenêtre, et inversement."""
    hybrides, batteries, ecartes = [], [], []
    for h in famille['hybrides']:
        if any(regles.compatible(h, b) for b in famille['batteries']):
            hybrides.append(h)
        else:
            bas, haut = h.get('plage_batterie_v') or (0, 0)
            ecartes.append(('hybride', h['nom'], 'aucune batterie haute tension du catalogue ne forme '
                            'une grappe dans sa fenêtre %g–%g V' % (bas, haut)))
    for b in famille['batteries']:
        if any(regles.compatible(h, b) for h in famille['hybrides']):
            batteries.append(b)
        else:
            ecartes.append(('batterie', b['nom'], 'aucun onduleur hybride haute tension du catalogue '
                            "n'accepte ses grappes"))
    return hybrides, batteries, ecartes


def _sans_ht(resultat_bt, motif, alertes):
    """La basse tension reste le résultat ; le motif dit aussi la haute tension."""
    sortie = dict(resultat_bt)
    if motif:
        sortie['motif'] = '%s ; haute tension : %s' % (resultat_bt.get('motif') or '', motif)
    return sortie, None, alertes


def _preparer(famille, nb_batteries):
    """``(bat haute tension, modèle de banque, nb choisi, alertes, motif)`` —
    appairage, modèle (le moins cher par kWh utile), tailles admissibles."""
    from apps.ventes.moteur_ci.batterie import _noms_sans_prix, choisir_modele_banque

    from .etude_ci_batterie import nb_batteries_choisi
    hybrides, batteries, ecartes = _apparier(famille)
    alertes = [_alerte('HYBRIDE_PARALLELE_NON_PUBLIE', (
        '« %s » : limite d’appareils en parallèle non publiée sur sa fiche (champ « Appareils en '
        'parallèle (maxi) ») — un seul appareil retenu.' % h['nom']))
        for h in hybrides if not h.get('max_parallele_publie')]
    if not hybrides or not batteries:
        return None, None, None, _alertes_ecartes(famille['ecartes'] + ecartes) + alertes, (
            'aucun couple onduleur hybride / batterie haute tension appariable par la tension')
    modele = choisir_modele_banque(batteries)
    if modele is None:
        return None, None, None, _alertes_ecartes(famille['ecartes'] + ecartes) + alertes, (
            'aucune batterie haute tension tarifée (%s)' % ', '.join(_noms_sans_prix(batteries)))
    retenus = [h for h in hybrides if regles.compatible(h, modele)]
    grappes = max(regles.grappes_par_appareil(h) * int(h['max_parallele']) for h in retenus)
    grappes = min(grappes, regles.grappes_max_batterie(modele) or grappes)
    tailles = regles.tailles_admissibles(modele, retenus, grappes)
    alertes = _alertes_ecartes(famille['ecartes'] + ecartes) + alertes
    nb = nb_batteries_choisi(nb_batteries)
    if nb is not None and nb not in tailles:
        alertes.append(_alerte('NB_BATTERIES_HORS_GRAPPE', regles.message_nb_impose(nb, modele, tailles),
                               niveau='bloquant'))
        nb = None
    modele = dict(modele, tailles_admissibles=list(tailles), grappes_par_taille=tailles,
                  max_modules=max(tailles) if tailles else None)
    bat = {'hybrides': retenus, 'batteries': [modele], 'elements': famille['elements']}
    return bat, modele, nb, alertes, None if tailles else 'aucune grappe valide commune aux hybrides'


def essayer_haute_tension(resultat_bt, bat_bt, *, regles_ht, nb_batteries, dimensionner):
    """``(résultat, bat de la famille retenue ou None, alertes)``.

    Basse tension composée, ou aucun hybride haute tension au catalogue
    (aucune option haute tension possible) : le résultat basse tension
    inchangé, aucune alerte. Devis antérieur à la
    règle (``regles_ht`` faux) : inchangé, les hybrides haute tension NOMMÉS.
    Sinon la famille haute tension est appariée et dimensionnée par
    ``dimensionner(bat, batteries, nb_batteries=, max_appareils=, parallele=)``."""
    famille = (bat_bt or {}).get(CLE) or famille_vide()
    if not famille['hybrides'] or not haute_tension_a_essayer(resultat_bt):
        return resultat_bt, None, []
    if not regles_ht:
        return resultat_bt, None, _alertes_ecartes([
            ('hybride', h['nom'], 'devis créé avant la règle haute tension du 24/11/2026 : il garde '
             "l'option qu'il a reçue") for h in famille['hybrides']])
    bat, modele, nb, alertes, motif = _preparer(famille, nb_batteries)
    if motif:
        return _sans_ht(resultat_bt, motif, alertes)
    limite = max(h['max_parallele'] for h in bat['hybrides'])
    publiee = [h for h in bat['hybrides'] if h.get('max_parallele_publie')]
    resultat = dimensionner(bat, bat['batteries'], nb_batteries=nb, max_appareils=limite, parallele=(
        limite, 'fiche de « %s »' % publiee[0]['nom'] if publiee else 'limite non publiée : un appareil'))
    if resultat.get('evaluation') is None:
        motif = (resultat.get('motif') or '').replace('basse tension', 'haute tension')
        return _sans_ht(dict(resultat_bt, alertes=list(resultat_bt.get('alertes') or [])
                             + list(resultat.get('alertes') or [])), motif, alertes)
    evalue = resultat['evaluation']
    resultat = dict(resultat, hypotheses=list(resultat.get('hypotheses') or []) + regles.hypotheses_banque(
        dict(modele, quantite=(evalue.get('batterie') or {}).get('quantite')),
        evalue.get('onduleurs'), bat['hybrides']))
    if evalue.get('batterie') and int(evalue['batterie'].get('quantite') or 0) > 0:
        alertes.append(_alerte('BOITIER_HAUTE_TENSION_A_VERIFIER', (
            'Option « avec batterie » haute tension : %d boîtier(s) de contrôle haute tension (un par '
            'grappe, fiche Deye BOS-B Pro-A3 p. 2 « BOS-B-PDU-2-A ») non composé(s) en ligne — vérifier '
            'que le prix de « %s » le comprend.' % (
                modele['grappes_par_taille'].get(int(evalue['batterie']['quantite']), 0), modele['nom'])),
            niveau='info'))
    return resultat, bat, alertes
