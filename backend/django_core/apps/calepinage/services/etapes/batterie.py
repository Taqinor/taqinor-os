"""CALX188 — LE BLOC « batterie » : le dispatch horaire sur la série AC réelle.

CE QUE CE MODULE EST, ET CE QU'IL N'EST PAS
---------------------------------------------
Ce n'est PAS une étape de la chaîne de pertes. ``batterie`` ne figure pas dans
``chaine_pertes.ORDRE_ETAPES`` et n'y figurera pas : une batterie ne RETRANCHE
pas de l'énergie à la production, elle la DÉPLACE dans le temps. Seul son
rendement aller-retour est une perte, et il est publié SÉPARÉMENT
(``energie.pertes_batterie_kwh``) plutôt que fondu dans la cascade, où il se
lirait comme une perte de production.

C'est donc un PRODUCTEUR DE BLOC POST-CHAÎNE : ``services/simulation.py``
(CALX5) l'appelle APRÈS ``appliquer_chaine``, sur la série sortie de chaîne
(``colonne_energie='p_ac_kw'``, CALX170) et sur la courbe de charge de
CALX189, et publie ce qu'il rend sous ``resultat['batterie']``.

UN SEUL MOTEUR DE DISPATCH
----------------------------
``services/batterie.py::simuler_batterie`` (CAL152/CAL153) fait tourner les
stratégies heure par heure ; il est appelé TEL QUEL. Ce module ne réécrit
aucune règle de dispatch : il lui donne les deux courbes, puis RELIT les flux
qu'il a produits pas par pas (sa trace interne : entrées solaire, écrêtage et
réseau, sortie, import, surplus restant, état de charge) — CALX63 : depuis
que la batterie peut se charger sur l'écrêtage de l'onduleur (couplage DC)
ou sur le réseau (heures creuses), la seule variation d'état de charge ne
désigne plus sans ambiguïté d'où vient l'énergie. Une seconde arithmétique
de priorité finirait par diverger de la première : il n'y en a qu'une.

CALX63 — CE QUE LA DÉCLARATION PEUT EN PLUS
--------------------------------------------
* ``couplage: 'dc'`` : l'écrêtage que l'étape « écrêtage » (CALX172) a posé
  sur chaque point (``ecretage_kw``) est offert à la charge ;
* ``strategie: 'plafond_injection'`` : le plafond et sa justification se
  lisent sur le RACCORDEMENT du site (``raccordement.plafond_injection_kw``
  / ``…_justification``, CALX190) — un refus les nomme là. La batterie ne
  stocke que le surplus au-dessus du plafond ; l'export posé est le surplus
  qui reste APRÈS elle, et c'est le bloc « autoconsommation » (CALX190) qui
  l'écrête au point de livraison et publie ce qu'il écrête ;
* ``strategie: 'heures_tarif'`` : la grille horaire de la SOCIÉTÉ se lit
  dans le contexte (:data:`CLE_TOU_HEURES`, libellés seulement), posée par
  l'orchestrateur depuis ``services/batterie.py::heures_tarif_societe`` ;
  absente ⇒ bloc OMIS en nommant ``parametres.tou_heures`` ;
* le VIEILLISSEMENT par cycles (``total.vieillissement``) quand la série
  couvre une année entière et que la fiche publie ses cycles et sa rétention
  de fin de vie.

Parité citée :
* PV*SOL — la priorité de dispatch explicite (consommation directe → décharge
  → import réseau → charge du surplus → export) :
  https://help.valentin-software.com/pvsol/en/calculation/battery-systems/
* OpenSolar — « l'activité de la batterie heure par heure sur toute l'année » :
  https://support.opensolar.com/hc/en-us/articles/12382460685455-How-OpenSolar-Models-Battery-Energy-Storage

CE QUI N'EST JAMAIS SUPPOSÉ (D-CALX 7)
----------------------------------------
* La STRATÉGIE est SAISIE. Décision fondateur : « aucune stratégie de batterie
  par défaut tant qu'aucune n'est choisie ». Sans elle, le bloc est OMIS en
  nommant le champ — jamais un ``autoconso`` implicite.
* Les paramètres d'une stratégie (seuil d'effacement, heures de décalage,
  réserve de secours) sont SAISIS : ``simuler_batterie`` les refuse en nommant
  le champ, et ce refus devient tel quel le motif d'omission du bloc.
* La capacité et les puissances viennent de la FICHE, par
  ``services/batterie.py::specs_batterie`` — que ``services/simulation.py``
  résout (il a seul accès au stock) et pose dans le contexte. Ce module est
  PUR : il ne lit ni base ni réseau.
* Le SURPLUS n'est pas affiché à zéro quand il n'est pas calculable : il est
  OMIS avec son motif (décision fondateur).

CE QUE CE MODULE POSE SUR LA SÉRIE (colonnes du contrat CALX142)
------------------------------------------------------------------
``charge_kwh``, ``batterie_soc_pct``, ``reseau_import_kwh`` et
``reseau_export_kwh``, point par point, PAR COPIE (la série reçue n'est jamais
modifiée). Quand le bloc est omis, aucune colonne n'est écrite : une colonne à
zéro se lirait « mesuré à zéro ».
"""
from __future__ import annotations

from apps.calepinage.services import chaine_pertes, courbe_charge, etapes
from apps.calepinage.services.batterie import (CHAMP_JUSTIFICATION_PLAFOND,
                                               CHAMP_PLAFOND,
                                               CHAMP_TOU_HEURES, MOTIVATIONS,
                                               StrategieInvalide,
                                               candidates_omises,
                                               capacites_candidates,
                                               reserve_depuis_appareils,
                                               simuler_batterie,
                                               simuler_groupes,
                                               vieillissement_batterie)

LIBELLE = 'Batterie'

#: La clé du contexte qui porte la DÉCLARATION de batterie du calepinage,
#: posée par ``services/simulation.py`` (CALX5) :
#: ``{strategie, seuil_effacement_kw, heures_charge, heures_decharge,
#: reserve_backup_kwh, etat_initial_kwh, groupes: [{groupe, packs, specs}]}``.
#: ``specs`` est EXACTEMENT ce que ``services/batterie.py::specs_batterie``
#: rend : la résolution de la fiche produit touche le stock, elle appartient
#: donc à l'orchestrateur, jamais à ce module pur.
CLE_CONTEXTE = 'batterie'

#: Les colonnes de points que ce bloc écrit (contrat CALX142).
COLONNES_POSEES = ('charge_kwh', 'batterie_soc_pct', 'reseau_import_kwh',
                   'reseau_export_kwh')

MOTIF_SANS_DECLARATION = (
    "Aucune batterie n'est déclarée sur ce calepinage : le bloc « batterie » "
    'est OMIS. Une batterie supposée changerait le taux d’autonomie, donc la '
    'proposition faite au client.')

MOTIF_SANS_STRATEGIE = (
    "Aucune stratégie de batterie n'a été choisie : le bloc « batterie » est "
    'OMIS. Une batterie ne se pilote pas toute seule — tant que personne n’a '
    'choisi entre autoconsommation, effacement de pointe, secours et '
    'décalage, aucun kWh stocké ne peut être publié.')

MOTIF_SANS_CAPACITE = (
    "La capacité UTILE de la batterie déclarée est inconnue : elle se lit sur "
    'la fiche du pack (CAL153), elle ne se suppose pas. Le bloc « batterie » '
    'est OMIS.')

MOTIF_SANS_PRODUCTION = (
    "Aucune colonne d'énergie n'est lisible sur la série sortie de chaîne : "
    'le dispatch se joue heure par heure CONTRE une production, et celle-ci '
    "n'est pas calculée. Le bloc « batterie » est OMIS.")

MOTIF_DECALAGE_PAS_NON_HORAIRE = (
    'La stratégie de décalage se règle sur des HEURES saisies (0 à 23), et la '
    'série n’avance pas par pas d’une heure : rattacher chaque pas à une '
    'heure reviendrait à deviner le calendrier. Le bloc « batterie » est OMIS.')

#: CALX63 — la clé du contexte qui porte les LIBELLÉS d'heures de la grille
#: horaire SAISIE par la société (``services/batterie.py::
#: heures_tarif_societe``, posée par l'orchestrateur, seul à lire la base).
CLE_TOU_HEURES = 'tou_heures'

#: CALX63 — la clé du contexte qui porte le raccordement du site (la même
#: que lit CALX190).
CLE_RACCORDEMENT = 'raccordement'

MOTIF_TARIF_PAS_NON_HORAIRE = (
    'La stratégie « heures du tarif » se règle sur les HEURES de la grille '
    'horaire de la société, et la série n’avance pas par pas d’une heure : '
    'rattacher chaque pas à une heure reviendrait à deviner le calendrier. Le '
    'bloc « batterie » est OMIS.')

MENTION_PLAFOND_AU_COMPTEUR = (
    'Stratégie « plafond d’injection » : la batterie ne stocke que le surplus '
    'AU-DESSUS du plafond saisi au raccordement ; ce qui reste au-dessus est '
    'écrêté et publié par le bloc « autoconsommation » (CALX190), sur la '
    'série après batterie — une seule fonction d’écrêtage, un seul endroit.')

MENTION_CHARGE_RESEAU = (
    'Stratégie « heures du tarif » : {reseau} kWh ont été chargés sur le '
    'réseau aux heures creuses — ils sont comptés dans l’import, et la '
    'décharge des heures de pointe les restitue avec l’énergie solaire '
    'stockée : « autoconsommé » compte donc toute l’énergie servie par la '
    'batterie, sans répartir sa provenance (une répartition serait un chiffre '
    'inventé).')

MOTIF_VIEILLISSEMENT_PAS_ANNUEL = (
    'La série ne couvre pas une année entière : les cycles ANNUELS de la '
    'batterie ne se lisent pas sur elle, et le vieillissement par cycles est '
    'OMIS.')

MOTIF_VIEILLISSEMENT_PLUSIEURS = (
    'Plusieurs groupes de batteries sont déclarés : leurs fiches ne publient '
    'pas forcément les mêmes cycles ni la même rétention de fin de vie, et le '
    'nombre de cycles n’est pas publié groupe par groupe. Le vieillissement '
    'par cycles est OMIS.')

MENTION_PLUSIEURS_GROUPES = (
    'Plusieurs groupes de batteries sont déclarés : ils sont dispatchés comme '
    'UNE banque (c’est le même point de livraison). L’énergie restituée et le '
    'nombre de cycles ne sont donc PAS publiés groupe par groupe — les '
    'répartir au prorata serait un chiffre inventé.')

MOTIF_RESERVE_EN_DOUBLE = (
    'Une réserve de secours nue ET des appareils secourus sont déclarés : la '
    'réserve se saisit d’une seule façon, jamais les deux. Le bloc '
    '« batterie » est OMIS.')

#: CALX270 — la réserve DÉDUITE des appareils, dite en clair dans le bloc.
MENTION_RESERVE_APPAREILS = (
    'Réserve de secours déduite de {nombre} appareil(s) secouru(s) : '
    '{energie} kWh pour {duree} h de coupure (puissance continue '
    '{continue_kw} kW, pointe au démarrage {pointe_kw} kW).')

DEFINITION_AUTONOMIE = (
    "Taux d'autonomie = 1 − énergie importée du réseau ÷ consommation. "
    'Heures sans import = les pas où le réseau n’a rien fourni. Les deux se '
    'comptent APRÈS le dispatch de la batterie.')

#: Tolérance d'arithmétique flottante — jamais un seuil métier.
_EPSILON = 1e-9


# ── lectures partagées (CALX190 et CALX191 les relisent ici) ────────────

def verdict_horaire(contexte):
    """Le verdict d'alignement horaire de CALX59 — ``(possible, motif)``.

    ``possible=False`` ⇒ les trois blocs horaires (``autoconsommation``,
    ``batterie``, ``hors_reseau``) sont OMIS avec le MÊME motif, celui que
    ``chaine_pertes`` formule : une seule phrase dans tout le dépôt.
    """
    verdict = (contexte or {}).get(chaine_pertes.CLE_CROISEMENT_HORAIRE)
    if not isinstance(verdict, dict):
        return True, ''
    if verdict.get('possible'):
        return True, ''
    return False, (verdict.get('motif')
                   or chaine_pertes.MOTIF_FUSEAU_ABSENT)


def courbe_de_charge(serie, contexte=None, *, charge=None):
    """La courbe de charge de CALX189, calculée UNE fois si on ne l'a pas.

    ``services/simulation.py`` (CALX5) l'assemble une seule fois et la passe
    aux trois blocs ; un appel direct (tests, script) peut la laisser vide et
    elle est assemblée ici, par le MÊME service.
    """
    if isinstance(charge, dict):
        return charge
    return courbe_charge.construire_courbe_charge(serie, contexte)


def production_horaire(serie):
    """L'énergie de la série, pas par pas, en kWh — ou ``None``.

    Lit la colonne que la série DÉCLARE (``colonne_energie``), avec son
    facteur vers le kilowatt et le pas de la série : aucune colonne lisible ⇒
    ``None``, jamais une liste de zéros.
    """
    nom = etapes.colonne_energie(serie)
    if nom is None:
        return None
    facteur = etapes.FACTEURS_KW[nom]
    heures = float(pas_minutes(serie)) / 60.0
    valeurs = []
    for point in (serie or {}).get('points') or []:
        brut = point.get(nom)
        try:
            valeurs.append(max(0.0, float(brut) * facteur * heures))
        except (TypeError, ValueError):
            valeurs.append(0.0)
    return valeurs


def pas_minutes(serie, charge=None):
    """Le pas de temps retenu : celui de la série, sinon celui de la charge."""
    for source in ((serie or {}), (charge or {})):
        valeur = source.get('pas_minutes')
        try:
            nombre = int(valeur)
        except (TypeError, ValueError):
            continue
        if nombre > 0:
            return nombre
    return etapes.PAS_MINUTES_PVGIS


def poser_colonnes(serie, colonnes):
    """Une COPIE de la série dont chaque point porte les colonnes données.

    ``colonnes`` est ``{nom: [valeur par point]}``. Pure : ni la série reçue
    ni ses points ne sont modifiés.
    """
    points = []
    for rang, point in enumerate((serie or {}).get('points') or []):
        copie = dict(point)
        for nom, valeurs in colonnes.items():
            if rang < len(valeurs):
                copie[nom] = valeurs[rang]
        points.append(copie)
    suite = dict(serie or {})
    suite['points'] = points
    return suite


def autonomie(import_horaire, charge_horaire):
    """``{taux_autonomie, heures_sans_import}`` — la part NON importée.

    Relu par ``etapes/autoconsommation.py`` (CALX190) : les deux blocs
    publient le même chiffre parce qu'ils appellent la même fonction.
    """
    total_conso = sum(charge_horaire or [])
    total_import = sum(import_horaire or [])
    heures = sum(1 for valeur in (import_horaire or []) if valeur <= _EPSILON)
    taux = (round(1.0 - total_import / total_conso, 4)
            if total_conso > _EPSILON else None)
    return {'taux_autonomie': taux, 'heures_sans_import': heures}


# ── la déclaration de batterie, lue sans rien supposer ───────────────────

def _nombre(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    return None if nombre != nombre else nombre


def _grandeur(specs, nom):
    """Une grandeur de ``specs_batterie`` — ``(valeur, source)``."""
    grandeurs = (specs or {}).get('grandeurs')
    if not isinstance(grandeurs, dict):
        return None, None
    ligne = grandeurs.get(nom)
    if not isinstance(ligne, dict):
        return None, None
    return _nombre(ligne.get('valeur')), ligne.get('source')


def _groupes_declares(declaration):
    """Les groupes de batteries déclarés, chacun avec ses specs de fiche."""
    lus = []
    for rang, groupe in enumerate(declaration.get('groupes') or []):
        if not isinstance(groupe, dict):
            continue
        specs = groupe.get('specs')
        specs = specs if isinstance(specs, dict) else {}
        capacite = _nombre(specs.get('capacite_utile_kwh'))
        dod, source_dod = _grandeur(specs, 'dod_pct')
        lus.append({
            'groupe': groupe.get('groupe') or f'Groupe {rang + 1}',
            'packs': specs.get('nb_packs') or groupe.get('packs'),
            'capacite_utile_kwh': capacite,
            'profondeur_decharge_pct': dod,
            'source': specs.get('capacite_utile_source') or source_dod,
            'puissance_charge_kw': _nombre(specs.get('puissance_charge_kw')),
            'puissance_decharge_kw': _nombre(
                specs.get('puissance_decharge_kw')),
            'rendement_ar_pct': _grandeur(specs, 'rendement_ar_pct')[0],
            # CALX63 — les cycles et la rétention de fin de vie PUBLIÉS.
            'cycles_publies': _grandeur(specs, 'cycles_publies')[0],
            'eol_pct': _grandeur(specs, 'eol_pct')[0],
            'avertissements': list(specs.get('avertissements') or []),
        })
    return lus


def _banque(groupes):
    """La banque RÉELLE : un seul point de livraison, donc un seul dispatch.

    Les capacités et les puissances s'additionnent ; le rendement retenu est
    le PLUS BAS publié par les fiches (le maillon faible), jamais une moyenne
    qui flatterait le parc.
    """
    capacite = 0.0
    charge_kw = 0.0
    decharge_kw = 0.0
    rendements = []
    for groupe in groupes:
        if groupe['capacite_utile_kwh'] is None:
            return None
        capacite += groupe['capacite_utile_kwh']
        if groupe['puissance_charge_kw'] is not None:
            charge_kw += groupe['puissance_charge_kw']
        if groupe['puissance_decharge_kw'] is not None:
            decharge_kw += groupe['puissance_decharge_kw']
        if groupe['rendement_ar_pct'] is not None:
            rendements.append(groupe['rendement_ar_pct'])
    if capacite <= 0:
        return None
    return {
        'capacite_utile_kwh': capacite,
        'puissance_charge_kw': charge_kw if charge_kw > 0 else None,
        'puissance_decharge_kw': decharge_kw if decharge_kw > 0 else None,
        'rendement_ar_pct': min(rendements) if rendements else None,
    }


def _flux_horaires(trace, charge, production):
    """Les flux de chaque pas, RELUS sur la trace du dispatch.

    La POLITIQUE de dispatch est celle de ``simuler_batterie`` et d'elle
    seule : on ne relit ici que les flux qu'il a produits (CALX63 — l'entrée
    se ventile entre surplus solaire, écrêtage de l'onduleur récupéré en
    couplage DC et réseau des heures creuses). Aucun flux n'est reconstruit.

    L'export posé est le surplus qui reste APRÈS la batterie, AVANT le
    plafond d'injection : le plafond au point de livraison est appliqué et
    publié par UN seul bloc, « autoconsommation » (CALX190), avec sa
    fonction — le poser aussi ici lui ferait lire « 0 kWh écrêté » et sortir
    l'énergie écrêtée de sa cascade.
    """
    def serie(cle):
        return list(trace.get(cle) or [])

    solaire = serie('entree')
    ecretage = serie('entree_ecretage')
    reseau = serie('entree_reseau')
    sorties = serie('sortie')
    imports = serie('import')
    surplus = serie('surplus')
    etats = serie('etat')
    flux = []
    for rang, (conso, prod) in enumerate(zip(charge, production)):
        flux.append({
            'conso': conso, 'prod': prod, 'direct': min(conso, prod),
            'entree': solaire[rang] + ecretage[rang] + reseau[rang],
            'entree_ecretage': ecretage[rang],
            'entree_reseau': reseau[rang],
            'sortie': sorties[rang],
            'export': surplus[rang],
            'import': imports[rang],
            'etat': etats[rang],
        })
    return flux


def _omission(motif, *, champ=''):
    texte = motif.strip()
    if champ:
        texte = f'{texte} Champ manquant : « {champ} ».'
    return {
        'groupes': [], 'total': None, 'avertissements': [],
        'motif_absence': texte,
    }


def _ecretage_horaire(points, pas):
    """CALX63 — l'énergie écrêtée par l'onduleur à chaque pas (kWh), ou ``None``.

    Relue sur la colonne que l'étape « écrêtage » (CALX172) pose sur chaque
    point (``ecretage_kw``, une puissance) × la durée du pas. L'étape omise
    (aucun point ne porte la colonne) ⇒ ``None`` : rien n'est offert, et rien
    n'est publié comme récupéré. Un point dont la puissance était illisible
    (colonne ``None``) n'offre rien.
    """
    from apps.calepinage.services.etapes.ecretage import COLONNE_ECRETAGE

    if not any(isinstance(point, dict) and COLONNE_ECRETAGE in point
               for point in points):
        return None
    heures = float(pas) / 60.0
    return [max(0.0, _nombre(point.get(COLONNE_ECRETAGE)) or 0.0) * heures
            if isinstance(point, dict) else 0.0 for point in points]


def _champ_du_refus(refus):
    """Le champ d'un refus, NOMMÉ là où il se saisit (CALX63).

    Le plafond d'injection se saisit au RACCORDEMENT (CALX190) ; la grille
    horaire est un réglage SOCIÉTÉ (``parametres.tou_heures``) — ni l'un ni
    l'autre n'est un champ de la déclaration de batterie. Tout le reste l'est.
    """
    champ = refus.champ or ''
    if not champ:
        return ''
    if champ.startswith(CHAMP_TOU_HEURES):
        return champ
    nom = champ.rsplit('.', 1)[-1]
    if nom in (CHAMP_PLAFOND, CHAMP_JUSTIFICATION_PLAFOND):
        return f'{CLE_RACCORDEMENT}.{nom}'
    return f'{CLE_CONTEXTE}.{champ}'


# ── l'entrée unique, appelée par services/simulation.py (CALX5) ──────────

def bloc_batterie(serie, contexte=None, *, charge=None):
    """Le bloc ``resultat['batterie']``, capacités candidates comprises.

    CALX271 — le bloc porte TOUJOURS ``capacites_candidates`` (voir
    :func:`_capacites_du_site`), qu'il soit calculé ou OMIS : c'est
    précisément quand aucune batterie n'est encore choisie que la
    comparaison des capacités du stock sert.
    """
    suite, bloc = _bloc_batterie_dispatch(serie, contexte, charge=charge)
    bloc['capacites_candidates'] = _capacites_du_site(serie, contexte,
                                                      charge=charge)
    return suite, bloc


def _bloc_batterie_dispatch(serie, contexte=None, *, charge=None):
    """Le bloc ``resultat['batterie']`` et la série enrichie de ses colonnes.

    Args:
        serie: la série SORTIE DE CHAÎNE (CALX147), en alternatif
            (``colonne_energie='p_ac_kw'``, CALX170).
        contexte: le contexte de simulation (CALX5). Sa clé ``batterie``
            porte la déclaration décrite dans :data:`CLE_CONTEXTE`.
        charge: la courbe de charge de CALX189, déjà assemblée. Absente, elle
            est assemblée ici par ``services/courbe_charge.py``.

    Returns:
        ``(serie, bloc)``. ``bloc`` suit le contrat CALX4 —
        ``{groupes, total, avertissements, motif_absence}``. Le bloc OMIS
        porte ``total: None`` et son motif ; la série ressort alors INCHANGÉE
        (aucune colonne à zéro).
    """
    contexte = contexte or {}

    possible, motif_fuseau = verdict_horaire(contexte)
    if not possible:
        return serie, _omission(motif_fuseau)

    declaration = contexte.get(CLE_CONTEXTE)
    if not isinstance(declaration, dict) or not declaration.get('groupes'):
        return serie, _omission(MOTIF_SANS_DECLARATION,
                                champ=f'{CLE_CONTEXTE}.groupes')

    bloc_charge = courbe_de_charge(serie, contexte, charge=charge)
    courbe = bloc_charge.get('courbe')
    if not courbe:
        motif = (bloc_charge.get('omissions') or {}).get('batterie')
        return serie, _omission(motif or courbe_charge.MOTIF_BATTERIE)

    production = production_horaire(serie)
    if production is None:
        return serie, _omission(MOTIF_SANS_PRODUCTION,
                                champ='serie.colonne_energie')

    strategie = (declaration.get('strategie') or '').strip()
    if not strategie:
        return serie, _omission(MOTIF_SANS_STRATEGIE,
                                champ=f'{CLE_CONTEXTE}.strategie')

    groupes = _groupes_declares(declaration)
    banque = _banque(groupes)
    if banque is None:
        return serie, _omission(
            MOTIF_SANS_CAPACITE,
            champ=f'{CLE_CONTEXTE}.groupes[].specs.capacite_utile_kwh')

    pas = pas_minutes(serie, bloc_charge)
    if strategie == 'decalage' and pas != 60:
        return serie, _omission(MOTIF_DECALAGE_PAS_NON_HORAIRE,
                                champ='simulation.resolution_minutes')
    if strategie == 'heures_tarif' and pas != 60:
        return serie, _omission(MOTIF_TARIF_PAS_NON_HORAIRE,
                                champ='simulation.resolution_minutes')

    points = (serie or {}).get('points') or []
    longueur = min(len(courbe), len(production), len(points))
    courbe = list(courbe[:longueur])
    production = list(production[:longueur])
    heure_de_depart = 0
    if points and isinstance(points[0], dict):
        heure_de_depart = int(_nombre(points[0].get('heure')) or 0)

    etat_initial = min(max(0.0, _nombre(declaration.get('etat_initial_kwh'))
                           or 0.0), banque['capacite_utile_kwh'])

    # CALX270 — la réserve de secours DÉDUITE des appareils que le document
    # déclare secourus (``battery.appareils`` + ``battery.duree_secours_h``),
    # à la place de la réserve nue ; jamais les deux à la fois.
    reserve = declaration.get('reserve_backup_kwh')
    if declaration.get('appareils') is not None:
        if reserve not in (None, ''):
            return serie, _omission(
                MOTIF_RESERVE_EN_DOUBLE,
                champ=f'{CLE_CONTEXTE}.reserve_backup_kwh')
        try:
            reserve = reserve_depuis_appareils(
                declaration.get('appareils'),
                duree_h=declaration.get('duree_secours_h'))
        except StrategieInvalide as refus:
            champ = ('duree_secours_h' if refus.champ == 'duree_h'
                     else refus.champ)
            return serie, _omission(refus.motif,
                                    champ=f'{CLE_CONTEXTE}.{champ}')

    parametres = {
        'strategie': strategie,
        'capacite_utile_kwh': banque['capacite_utile_kwh'],
        'puissance_charge_kw': banque['puissance_charge_kw'],
        'puissance_decharge_kw': banque['puissance_decharge_kw'],
        'rendement_ar_pct': banque['rendement_ar_pct'],
        'seuil_effacement_kw': declaration.get('seuil_effacement_kw'),
        'heures_charge': declaration.get('heures_charge'),
        'heures_decharge': declaration.get('heures_decharge'),
        # CALX268 — la commande horaire à SOC cible, quand le document la
        # déclare ; CALX270 — la part effaçable d'un tableau partiel.
        'fenetres': declaration.get('fenetres'),
        'reserve_backup_kwh': reserve,
        'part_effacable_pct': declaration.get('part_effacable_pct'),
        'plafond_effacable_kw': declaration.get('plafond_effacable_kw'),
        'etat_initial_kwh': etat_initial,
    }
    # CALX63 — le plafond d'injection du RACCORDEMENT, pour sa stratégie.
    if strategie == 'plafond_injection':
        raccordement = contexte.get(CLE_RACCORDEMENT)
        raccordement = raccordement if isinstance(raccordement, dict) else {}
        parametres['plafond_injection_kw'] = raccordement.get(CHAMP_PLAFOND)
        parametres['plafond_injection_justification'] = str(
            raccordement.get(CHAMP_JUSTIFICATION_PLAFOND) or '')
    # CALX63 — ce que le SITE porte : l'écrêtage de l'onduleur (offert à un
    # couplage DC), la grille horaire de la société et le mois de chaque pas.
    communs = {
        'ecretage_horaire': (
            _ecretage_horaire(points[:longueur], pas)
            if str(declaration.get('couplage') or '').strip().lower() == 'dc'
            else None),
        'tou_heures': (contexte.get(CLE_TOU_HEURES)
                       if strategie == 'heures_tarif' else None),
        'mois_des_heures': (
            [_nombre(point.get('mois')) if isinstance(point, dict) else None
             for point in points[:longueur]]
            if strategie == 'heures_tarif' else None),
    }
    trace = {}
    try:
        if declaration.get('couplage') not in (None, ''):
            # CALX267 — la banque DÉCLARE son couplage (``ac`` | ``dc``) :
            # elle passe par ``simuler_groupes`` (un groupe DC sans onduleur
            # est refusé en le nommant) ; un seul groupe rend exactement le
            # dispatch de ``simuler_batterie``.
            dispatch = simuler_groupes(
                courbe, production, [dict(
                    parametres,
                    groupe=' + '.join(groupe['groupe'] for groupe in groupes),
                    couplage=declaration.get('couplage'),
                    onduleur_ref=declaration.get('onduleur_ref'),
                    modele=declaration.get('model'))],
                pas_heures=float(pas) / 60.0,
                heure_de_depart=heure_de_depart, _trace=trace,
                **communs)['agregat']
        else:
            dispatch = simuler_batterie(
                courbe, production, pas_heures=float(pas) / 60.0,
                heure_de_depart=heure_de_depart, _trace=trace,
                **communs, **parametres)
    except StrategieInvalide as refus:
        return serie, _omission(refus.motif, champ=_champ_du_refus(refus))

    # CALX63 — l'horizon du vieillissement est CELUI de la projection de
    # production (CALX178 : saisi, ou dérivé de la garantie des modules) —
    # une seule lecture, celle de ``etapes/vieillissement.py``.
    from apps.calepinage.services.etapes.vieillissement import _horizon

    flux = _flux_horaires(trace, courbe, production)
    suite, bloc = _publier(serie, flux, dispatch, groupes, banque, strategie,
                           etat_initial=etat_initial,
                           pas_heures=float(pas) / 60.0,
                           horizon=_horizon(contexte)[0])
    if isinstance(reserve, dict):
        bloc['avertissements'].append(MENTION_RESERVE_APPAREILS.format(
            nombre=len(reserve['detail']), energie=reserve['energie_kwh'],
            duree=reserve['duree_h'],
            continue_kw=reserve['puissance_continue_kw'],
            pointe_kw=reserve['puissance_pointe_kw']))
    return suite, bloc


#: Les durées (heures) d'une série qui couvre UNE année civile entière.
_HEURES_D_UNE_ANNEE = (8760.0, 8784.0)


def _vieillissement(groupes, *, total_sortie, capacite, heures_couvertes,
                    horizon):
    """CALX63 — le vieillissement PAR CYCLES de la banque, ou son omission.

    Les cycles ANNUELS se lisent sur le dispatch d'une année entière
    (énergie restituée ÷ capacité utile) ; les cycles et la rétention de fin
    de vie se lisent sur la fiche (``services/batterie.py::
    vieillissement_batterie`` omet en nommant le champ absent).
    """
    if len(groupes) != 1:
        omis = vieillissement_batterie(None, None, None)
        omis.update({'champ': f'{CLE_CONTEXTE}.groupes',
                     'motif_absence': MOTIF_VIEILLISSEMENT_PLUSIEURS})
        return omis
    groupe = groupes[0]
    annuelle = any(abs(heures_couvertes - duree) < 1e-6
                   for duree in _HEURES_D_UNE_ANNEE)
    cycles = (total_sortie / capacite
              if annuelle and capacite > _EPSILON else None)
    resultat = vieillissement_batterie(
        cycles, groupe.get('cycles_publies'), groupe.get('eol_pct'),
        horizon_annees=horizon)
    if not annuelle and resultat['champ'] == 'cycles_annuels':
        resultat['motif_absence'] = MOTIF_VIEILLISSEMENT_PAS_ANNUEL
    return resultat


def _publier(serie, flux, dispatch, groupes, banque, strategie, *,
             etat_initial, pas_heures=1.0, horizon=None):
    """La série enrichie et le bloc, tirés des MÊMES flux pas par pas."""
    capacite = banque['capacite_utile_kwh']
    total_conso = sum(pas['conso'] for pas in flux)
    total_prod = sum(pas['prod'] for pas in flux)
    total_entree = sum(pas['entree'] for pas in flux)
    total_sortie = sum(pas['sortie'] for pas in flux)
    total_import = sum(pas['import'] for pas in flux)
    total_export = sum(pas['export'] for pas in flux)
    total_direct = sum(pas['direct'] for pas in flux)
    # CALX63 — les deux entrées qui ne viennent pas de la production de la
    # série (écrêtage récupéré, réseau des heures creuses) : le bilan ferme
    # avec elles.
    total_ecretage = sum(pas['entree_ecretage'] for pas in flux)
    total_reseau = sum(pas['entree_reseau'] for pas in flux)
    variation = (flux[-1]['etat'] - etat_initial) if flux else 0.0
    pertes = total_entree - total_sortie - variation

    suite = poser_colonnes(serie, {
        'charge_kwh': [round(pas['conso'], 4) for pas in flux],
        'batterie_soc_pct': [round(pas['etat'] / capacite * 100.0, 2)
                             for pas in flux],
        'reseau_import_kwh': [round(pas['import'], 4) for pas in flux],
        'reseau_export_kwh': [round(pas['export'], 4) for pas in flux],
    })

    part = autonomie([pas['import'] for pas in flux],
                     [pas['conso'] for pas in flux])
    plusieurs = len(groupes) > 1
    avertissements = []
    for groupe in groupes:
        avertissements.extend(groupe['avertissements'])
    if plusieurs:
        avertissements.append(MENTION_PLUSIEURS_GROUPES)
    if strategie == 'plafond_injection':
        avertissements.append(MENTION_PLAFOND_AU_COMPTEUR)
    if total_reseau > _EPSILON:
        avertissements.append(MENTION_CHARGE_RESEAU.format(
            reseau=round(total_reseau, 3)))

    lignes = []
    for groupe in groupes:
        lignes.append({
            'groupe': groupe['groupe'],
            'packs': groupe['packs'],
            'capacite_utile_kwh': groupe['capacite_utile_kwh'],
            'strategie': strategie,
            'cycles_an': (None if plusieurs
                          else round(total_sortie / capacite, 2)),
            'energie_restituee_kwh': (None if plusieurs
                                      else round(total_sortie, 3)),
            'profondeur_decharge_pct': groupe['profondeur_decharge_pct'],
            'source': groupe['source'],
        })

    bloc = {
        'groupes': lignes,
        'total': {
            'capacite_utile_kwh': round(capacite, 3),
            'energie_restituee_kwh': round(total_sortie, 3),
            'energie_stockee_kwh': round(total_entree, 3),
            'taux_autonomie': part['taux_autonomie'],
            'heures_sans_import': part['heures_sans_import'],
            'strategie': strategie,
            'objectif_dimensionnant': dispatch['objectif_dimensionnant'],
            'energie': {
                'production_kwh': round(total_prod, 3),
                'consommation_kwh': round(total_conso, 3),
                'autoconsomme_kwh': round(total_direct + total_sortie, 3),
                'export_kwh': round(total_export, 3),
                'import_reseau_kwh': round(total_import, 3),
                'pertes_batterie_kwh': round(pertes, 3),
                'variation_stock_kwh': round(variation, 3),
                # CALX63 — production + écrêtage récupéré + charge réseau =
                # autoconsommé + export + pertes + variation de stock.
                'ecretage_recupere_kwh': round(total_ecretage, 3),
                'charge_reseau_kwh': round(total_reseau, 3),
            },
            'definition': DEFINITION_AUTONOMIE,
            # CALX63 — la capacité année par année, par les cycles.
            'vieillissement': _vieillissement(
                groupes, total_sortie=total_sortie, capacite=capacite,
                heures_couvertes=len(flux) * pas_heures, horizon=horizon),
        },
        'avertissements': avertissements,
        'motif_absence': '',
    }
    return suite, bloc


# ── CALX271 — les capacités du STOCK, comparées sur la série réelle ──────

#: La clé du contexte qui porte les batteries du stock de la société, lues
#: par ``services/simulation.py`` (seul à toucher le stock) :
#: ``[{produit, libelle, capacite_utile_kwh, puissance_charge_kw,
#: puissance_decharge_kw, rendement_ar_pct: {valeur, source}, source}]``.
CLE_CAPACITES_STOCK = 'capacites_batterie_stock'

MOTIF_SANS_CAPACITES_STOCK = (
    "Aucune batterie du stock de la société ne publie de capacité utile "
    'lisible sur sa fiche : il n’y a rien à comparer. Complétez la fiche '
    'd’une batterie du stock (capacité utile, ou capacité nominale et '
    'profondeur de décharge) — aucune capacité n’est inventée.')


def _capacites_du_stock(contexte):
    """Les fiches du stock UTILISABLES (capacité utile lisible), et elles seules."""
    lues = []
    for capacite in (contexte or {}).get(CLE_CAPACITES_STOCK) or []:
        if not isinstance(capacite, dict):
            continue
        utile = _nombre(capacite.get('capacite_utile_kwh'))
        if utile is None or utile <= 0:
            continue
        lues.append(capacite)
    return lues


def _declaration_du_document(contexte):
    """La section ``battery`` du document (seuil, motivation), ou ``{}``."""
    declaration = (contexte or {}).get(CLE_CONTEXTE)
    if isinstance(declaration, dict) and declaration:
        return declaration
    layout = (contexte or {}).get('layout')
    brute = layout.get('battery') if isinstance(layout, dict) else None
    return brute if isinstance(brute, dict) else {}


def _capacites_du_site(serie, contexte=None, *, charge=None):
    """CALX271 — les capacités candidates du stock, classées par motivation.

    Le dispatch EXISTANT tourne, pour chaque batterie du stock dont la fiche
    publie une capacité utile, sur la courbe de charge (CALX189) et la série
    AC sortie de chaîne — puis les candidates sont classées, pour CHACUNE des
    trois motivations (``services/batterie.py::MOTIVATIONS``), par
    ``capacites_candidates``. La motivation déclarée par le client
    (``roof_layout.battery.motivation``) est republiée pour que l'écran la
    présélectionne ; aucune n'est supposée. Aucun prix n'entre.

    Returns:
        dict — ``capacites_stock`` (les fiches comparées : ``produit``,
        ``libelle``, ``capacite_utile_kwh``, ``source``),
        ``motivation_declaree``, ``par_motivation`` (``{motivation:
        <capacites_candidates>}``, ou ``None`` quand rien n'est comparable)
        et ``motif_absence``.
    """
    contexte = contexte or {}
    utilisables = _capacites_du_stock(contexte)
    declaration = _declaration_du_document(contexte)
    motivation = declaration.get('motivation')
    bloc = {
        'capacites_stock': [{
            'produit': capacite.get('produit'),
            'libelle': capacite.get('libelle'),
            'capacite_utile_kwh': _nombre(capacite.get('capacite_utile_kwh')),
            'source': capacite.get('source'),
        } for capacite in utilisables],
        'motivation_declaree': motivation if motivation in MOTIVATIONS
        else None,
        'par_motivation': None,
        'motif_absence': '',
    }
    if not utilisables:
        bloc['motif_absence'] = MOTIF_SANS_CAPACITES_STOCK
        return bloc

    possible, motif_fuseau = verdict_horaire(contexte)
    if not possible:
        bloc['motif_absence'] = motif_fuseau
        return bloc
    bloc_charge = courbe_de_charge(serie, contexte, charge=charge)
    courbe = bloc_charge.get('courbe')
    if not courbe:
        motif = (bloc_charge.get('omissions') or {}).get('batterie')
        bloc['motif_absence'] = motif or courbe_charge.MOTIF_BATTERIE
        return bloc
    production = production_horaire(serie)
    if production is None:
        bloc['motif_absence'] = MOTIF_SANS_PRODUCTION
        return bloc

    points = (serie or {}).get('points') or []
    longueur = min(len(courbe), len(production), len(points))
    heure_de_depart = 0
    if points and isinstance(points[0], dict):
        heure_de_depart = int(_nombre(points[0].get('heure')) or 0)
    pas = pas_minutes(serie, bloc_charge)

    par_motivation = {}
    for nom in MOTIVATIONS:
        try:
            par_motivation[nom] = capacites_candidates(
                list(courbe[:longueur]), list(production[:longueur]),
                motivation=nom, capacites_kwh=utilisables,
                seuil_effacement_kw=declaration.get('seuil_effacement_kw'),
                pas_heures=float(pas) / 60.0,
                heure_de_depart=heure_de_depart)
        except StrategieInvalide as refus:
            texte = refus.motif.strip()
            if refus.champ:
                texte = (f'{texte} Champ manquant : '
                         f'« {CLE_CONTEXTE}.{refus.champ} ».')
            par_motivation[nom] = candidates_omises(nom, texte)
    bloc['par_motivation'] = par_motivation
    return bloc
