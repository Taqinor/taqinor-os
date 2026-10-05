"""Blocs horaires publics de la proposition (SPL247, déplacé de ``public_views.py``).

Tranche tarifaire, profils comparatifs, profil horaire du devis, estimation
de consommation, jours types (``jour_reference``), localisation du moteur
horaire, options de dimensionnement et production par option — assemblés par
``public_views.proposal_data``. Aucune vue ici. Déplacement pur : corps
octet-identiques (seule la profondeur des imports relatifs locaux change),
prouvé par ``tests/golden/split_pv_horaire.json``.
"""
import logging

from ..models import ShareLink

# Même émetteur de journal qu'avant le déplacement (filtres et tests inchangés).
logger = logging.getLogger("apps.ventes.public_views")


def _tranche_tarifaire_publique(dimensionnement):
    """L-BACK T4 (24/08/2026) — sous-ensemble PUBLIC, client-safe, du bloc
    « falaise » de ``apps.ventes.dimensionnement.recommander_taille`` (déjà
    persisté sur le devis résidentiel par
    ``services.rafraichir_dimensionnement_devis``) : contrat
    ``apps/web/src/lib/proposition.ts ProposalResponse.tranche_tarifaire``.

    ``tranche_actuelle``/``tranche_visee``/``cible_kwh_mois`` viennent de
    ``dimensionnement['falaise']`` ; ``residuel_kwh_mois`` de
    ``dimensionnement['meilleure_falaise']`` (LA combinaison qui franchit
    réellement la marche — un résiduel différent de la falaise visée serait un
    second chiffre inventé). ``None`` (⇒ clé absente) quand ``falaise`` est
    absent : le client est déjà dans la tranche la plus basse, rien à
    annoncer. Ne lève jamais."""
    falaise = (dimensionnement or {}).get('falaise')
    if not isinstance(falaise, dict):
        return None
    meilleure = (dimensionnement or {}).get('meilleure_falaise')
    residuel = (meilleure or {}).get('residuel_kwh_mois')
    return {
        'tranche_actuelle': {
            'libelle': (falaise.get('tranche_actuelle') or {}).get('libelle'),
        },
        'tranche_visee': {
            'libelle': (falaise.get('tranche_visee') or {}).get('libelle'),
        },
        'cible_kwh_mois': falaise.get('cible_kwh_mois'),
        'residuel_kwh_mois': residuel,
    }


#: L-PCMP — la note de méthode des variantes d'occupation, par niveau. Les
#: CHIFFRES sont EXACTEMENT les mêmes aux deux niveaux (règle fondateur : seul
#: le texte de méthode se neutralise, jamais un nombre).
_NOTE_PROFILS_CONFIANCE = (
    'Simulation sur VOS factures réelles : seule la répartition de votre '
    'consommation dans la journée change d\'un profil à l\'autre. Calcul '
    'heure par heure, même moteur que votre devis.')


_NOTE_PROFILS_STANDARD = (
    'Simulation sur vos factures : seule la répartition de votre '
    'consommation dans la journée change d\'un profil à l\'autre.')


def _profils_comparatifs_publique(etude_params,
                                  niveau=ShareLink.NIVEAU_CONFIANCE):
    """L-PCMP (fondateur, 24/08/2026) — sous-ensemble PUBLIC, client-safe, du
    bloc ``etude_params['profils_comparatifs']`` posé par
    ``apps.ventes.profils_comparatifs``.

    Le client change de silhouette d'occupation sur la page et voit les
    économies de CHAQUE comportement plus l'installation optimale pour
    celui-là. Les trois blocs sont donc SERVIS CALCULÉS : la page n'a plus
    qu'à basculer d'affichage, elle ne calcule AUCUNE économie (règle
    « zéro chiffre inventé » — un chiffre qui apparaît côté client sort du
    moteur, ou n'apparaît pas).

    Whitelist STRICTE de scalaires (économies MAD, taux, kWc, kWh) : ni
    ``prix_achat``, ni marge, ni ligne de composition ne peut fuiter par
    construction. ``None`` quand rien n'est lisible (devis non résidentiel,
    bloc pas encore posé) — clé alors ABSENTE du payload, la page masque la
    section entière."""
    bloc = (etude_params or {}).get('profils_comparatifs')
    if not isinstance(bloc, dict):
        return None

    def _num(valeur):
        if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
            return None
        return float(valeur)

    def _pct(valeur):
        """Un taux du moteur (0..1) rendu en POURCENTAGE, comme partout
        ailleurs sur cette page — jamais un ratio brut que la page devrait
        re-multiplier de son côté."""
        nombre = _num(valeur)
        return None if nombre is None else round(nombre * 100, 1)

    def _mad(valeur):
        nombre = _num(valeur)
        return None if nombre is None else round(nombre)

    def _optimal(brut):
        if not isinstance(brut, dict):
            return None
        kwc = _num(brut.get('kwc'))
        if kwc is None or kwc <= 0:
            return None
        identique = brut.get('identique_au_devis')
        return {
            'kwc': round(kwc, 2),
            'panneaux': (int(brut['panneaux'])
                         if isinstance(brut.get('panneaux'), int) else None),
            'batterie_kwh': _num(brut.get('batterie_kwh')) or 0.0,
            'avec_batterie': bool(brut.get('avec_batterie')),
            'economie_mad': _mad(brut.get('economie_mad')),
            # Tri-état VOULU : True/False quand la comparaison a pu être faite,
            # None quand le kWc du devis n'était pas lisible — la page se tait
            # alors plutôt que d'affirmer « déjà optimal ».
            'identique_au_devis': (identique if isinstance(identique, bool)
                                   else None),
        }

    profils = []
    for entree in bloc.get('profils') or []:
        if not isinstance(entree, dict):
            continue
        occupation = entree.get('occupation')
        economie_sans = _mad(entree.get('economie_sans_mad'))
        if not occupation or economie_sans is None:
            continue
        profils.append({
            'occupation': occupation,
            'est_profil_reel': bool(entree.get('est_profil_reel')),
            'economie_sans_mad': economie_sans,
            'economie_avec_mad': _mad(entree.get('economie_avec_mad')),
            'taux_autoconso_sans_pct': _pct(entree.get('taux_autoconso_sans')),
            'taux_autoconso_avec_pct': _pct(entree.get('taux_autoconso_avec')),
            'couverture_sans_pct': _pct(entree.get('couverture_sans')),
            'couverture_avec_pct': _pct(entree.get('couverture_avec')),
            'optimal': _optimal(entree.get('optimal')),
        })
    if not profils:
        return None
    return {
        'profil_reel': bloc.get('profil_reel'),
        'kwc_devis': _num(bloc.get('kwc_devis')),
        'batterie_kwh_devis': _num(bloc.get('batterie_kwh_devis')) or 0.0,
        'avec_batterie': bool(bloc.get('avec_batterie')),
        'devise': 'MAD',
        'profils': profils,
        'note': (_NOTE_PROFILS_STANDARD
                 if niveau == ShareLink.NIVEAU_STANDARD
                 else _NOTE_PROFILS_CONFIANCE),
    }


def _profil_horaire_pour_devis(devis):
    """L-BACK T4 — ``(kwc, conso, ville, lat, lon, occupation, equipements)``
    d'un devis, MÊME LECTURE que ``services.rafraichir_dimensionnement_devis``/
    ``etude_horaire._etude_horaire_pour_devis`` (kWc du bloc horaire déjà
    persisté — jamais une seconde dérivation depuis les lignes ici, cet
    endpoint est en lecture seule). ``kwc`` vaut ``None`` quand aucun bloc
    horaire n'est encore posé (devis non résidentiel, ou pas encore
    rafraîchi) — l'appelant omet alors les clés qui en dépendent."""
    from apps.crm.selectors import lead_bills_for_devis, site_location_for_devis

    from ..courbes_journalieres import equipements_du_devis, occupation_du_devis
    from ..etude_horaire import profil_depuis_factures

    etude_params = getattr(devis, 'etude_params', None) or {}
    bloc_horaire = etude_params.get('etude_horaire') or {}
    kwc = bloc_horaire.get('kwc')

    bills = lead_bills_for_devis(devis) or {}
    conso, _source, _detail = profil_depuis_factures(
        facture_hiver_mad=bills.get('facture_hiver'),
        facture_ete_mad=bills.get('facture_ete'),
        ete_differente=bills.get('ete_differente'),
        factures_mensuelles_mad=etude_params.get(
            'factures_mensuelles_reelles'),
        conso_kwh_mensuelles=etude_params.get('conso_kwh_mensuelles'))

    localisation = site_location_for_devis(devis) or {}
    ville = localisation.get('site_ville')
    lat, lon = localisation.get('gps_lat'), localisation.get('gps_lng')

    mode = (getattr(devis, 'mode_installation', None) or '').strip().lower()
    occupation, _source_occ = occupation_du_devis(
        devis, {'mode_installation': mode})
    equipements = equipements_du_devis(devis)
    return kwc, conso, ville, lat, lon, occupation, equipements


def _estimation_conso_publique(devis):
    """L-BACK T4 — bloc ``estimation_conso`` (contrat public, voir
    ``etude_horaire.estimation_conso_mensuelle``). ``None`` best-effort — un
    bloc d'affichage additif ne fait jamais tomber la page client."""
    try:
        from ..etude_horaire import estimation_conso_mensuelle
        _kwc, conso, _v, _lat, _lon, _occ, equipements = (
            _profil_horaire_pour_devis(devis))
        return estimation_conso_mensuelle(conso, equipements)
    except Exception:  # noqa: BLE001 — voir _economies_mensuelles_publiques
        logger.warning('estimation_conso indisponible', exc_info=True)
        return None


def _jour_reference_publique(devis):
    """QJR406 — LA date de référence du devis, pour les surfaces PUBLIQUES.

    Les blocs ``jours_types`` et ``couverture_batterie`` rejouent les douze
    jours types (``etude_horaire.jours_types_annee``), dont la forme dépend de
    la fenêtre RAMADAN, donc d'une DATE. QJR164 a câblé le paramètre
    ``jour_reference`` dans les deux fonctions publiques, mais AUCUN des deux
    appelants de production ne le passait : les deux surfaces retombaient sur
    l'horloge du serveur (``timezone.localdate()``, au fond de
    ``jours_types_annee``) pendant que le devis persisté, lui, porte SON jour
    de référence — le client qui rouvrait son lien voyait une journée type qui
    n'était pas celle de son devis (écart visible autour du Ramadan).

    Source UNIQUE : ``domain.entrees.jour_reference_du_devis`` (QJR232) —
    surcharge D12 ``etude.jour_reference``, sinon la date du devis, sinon
    « aujourd'hui ». Aucune seconde règle de résolution.

    ``None`` best-effort : une résolution impossible rend l'ancien
    comportement (repli d'horloge posé au fond de ``jours_types_annee``,
    inchangé) plutôt que de faire tomber un bloc d'affichage additif.
    """
    try:
        from ..domain.entrees import jour_reference_du_devis
        return jour_reference_du_devis(devis)
    except Exception:  # noqa: BLE001 — voir _economies_mensuelles_publiques
        logger.warning('jour_reference indisponible', exc_info=True)
        return None


def _jours_types_publique(devis):
    """L-BACK T4 — bloc ``jours_types`` (contrat public, voir
    ``etude_horaire.jours_types_publics``). ``None`` best-effort.

    QJR406 — la date de référence du DEVIS est transmise (voir
    :func:`_jour_reference_publique`), jamais l'horloge du rendu."""
    try:
        from ..etude_horaire import jours_types_publics
        kwc, conso, ville, lat, lon, occupation, equipements = (
            _profil_horaire_pour_devis(devis))
        if not kwc:
            return None
        return jours_types_publics(
            kwc=kwc, conso_kwh_mensuelles=conso, ville=ville, lat=lat,
            lon=lon, occupation=occupation, equipements=equipements,
            jour_reference=_jour_reference_publique(devis))
    except Exception:  # noqa: BLE001 — voir _economies_mensuelles_publiques
        logger.warning('jours_types indisponible', exc_info=True)
        return None


def _localisation_pour_moteur_horaire(devis, data):
    """PACT10 (« deux optimiseurs ») — ``(ville, lat, lon)`` best-effort pour
    le moteur horaire, MÊME LECTURE que ``courbes_journalieres._production``
    (``data['client_city']`` en priorité, sinon la ville du chantier via le
    sélecteur CRM, jamais ses modèles). Ne lève jamais : ``(None, None,
    None)`` quand la localisation est indisponible — l'appelant omet alors
    ce que ça dérive (Q6), il n'approxime pas."""
    try:
        _kwc, _conso, ville_lead, lat, lon, _occ, _equip = (
            _profil_horaire_pour_devis(devis))
    except Exception:  # noqa: BLE001 — un lead absent/illisible n'arrête rien
        ville_lead, lat, lon = None, None, None
    ville = data.get('client_city') or ville_lead
    return ville, lat, lon


def _dimensionnement_option_depuis_items(items):
    """PACT10 (« deux optimiseurs ») — nb panneaux / kWc / batteries D'UNE
    option, dérivés des lignes RÉELLES de cette option (``sans_items``/
    ``avec_items`` du builder — déjà splittés par option). MÊME discipline
    que ``quote_engine.builder.panneaux_et_watt_lu`` : un watt illisible
    laisse ``puissance_kwc`` à ``None`` (jamais le repli 710 W, réservé au
    KPI interne — CE REPLI NE SORT JAMAIS SUR UN DOCUMENT CLIENT).

    QJR92b (29/08/2026) — MÊME discipline pour la CAPACITÉ BATTERIE : une
    ligne batterie dont la désignation ne porte aucun kWh lisible contribuait
    un défaut fabriqué de 5,0 kWh, publié sur la page proposition PUBLIQUE.
    Elle contribue désormais 0, et ``capacite_batterie_kwh`` vaut ``None``
    quand AUCUNE ligne batterie n'a de capacité lisible : le client OMET la
    valeur (contrat ``dimensionnement_options.json``, note ``derivation``)
    au lieu de lire un nombre inventé. ``nb_batteries`` reste le compte RÉEL —
    c'est ainsi que l'inconnu remonte plutôt que d'être tu."""
    from ..domain.catalogue import _parse_kwh
    from ..quote_engine.builder import _is_battery, _is_panel, _parse_watt
    nb_panneaux = 0
    watt = None
    nb_batteries = 0.0
    capacite_batterie_kwh = 0.0
    for it in items or []:
        designation = it.get('designation') or ''
        produit_nom = it.get('_produit_nom') or ''
        try:
            qty = float(it.get('quantite') or 0)
        except (TypeError, ValueError):
            qty = 0.0
        if qty <= 0:
            continue
        if _is_panel(designation, produit_nom):
            nb_panneaux += int(round(qty))
            watt = watt or _parse_watt(designation, produit_nom)
        elif _is_battery(designation):
            nb_batteries += qty
            capacite_batterie_kwh += qty * (_parse_kwh(designation) or 0.0)
    puissance_kwc = (
        round(nb_panneaux * watt / 1000, 2)
        if (nb_panneaux and watt) else None)
    nb_batteries_int = int(round(nb_batteries))
    return {
        'nb_panneaux': nb_panneaux,
        'puissance_kwc': puissance_kwc,
        'nb_batteries': nb_batteries_int,
        # QJR92b — ``0.0`` signifie ici « aucune capacité LISIBLE », jamais
        # « zéro kWh vendu » : on l'omet (``None``) au lieu de publier un
        # chiffre faux, exactement comme un watt illisible laisse ``puissance_kwc``
        # absent juste au-dessus.
        'capacite_batterie_kwh': (
            round(capacite_batterie_kwh, 2)
            if (nb_batteries_int and capacite_batterie_kwh > 0) else None),
    }


def _dimensionnement_options_publique(devis, data):
    """PACT10 (« deux optimiseurs ») — clé ``dimensionnement_options`` :
    nb panneaux/kWc/batteries PAR OPTION (contrat
    ``apps/ventes/contract_samples/dimensionnement_options.json``), dérivés
    des lignes RÉELLES (``sans_items``/``avec_items``, déjà splittés par
    option par le builder) — jamais un chiffre inventé.

    L-VAR — la branche ``'avec'`` n'est servie QUE si ``avec_ok`` (même
    discipline que ``_economies_mensuelles_calcul``/CJ2b) : jamais un
    dimensionnement « avec batterie » sur une option que ce devis ne livre
    pas. ``divergent`` compare les deux nb_panneaux — ``False`` sans branche
    ``'avec'`` (rien à comparer). ``production_annuelle_kwh`` vient du
    moteur horaire (lecture pure) quand la localisation est résolue, sinon
    ``None``. ``None`` best-effort — un bloc d'affichage additif ne fait
    jamais tomber la page client."""
    try:
        from ..etude_horaire import production_annuelle_pour_kwc
        sans = _dimensionnement_option_depuis_items(data.get('sans_items'))
        out = {'sans': sans, 'divergent': False}
        avec = None
        if bool(data.get('avec_ok')):
            avec = _dimensionnement_option_depuis_items(data.get('avec_items'))
            out['avec'] = avec
            out['divergent'] = sans['nb_panneaux'] != avec['nb_panneaux']
        ville, lat, lon = _localisation_pour_moteur_horaire(devis, data)
        sans['production_annuelle_kwh'] = production_annuelle_pour_kwc(
            sans['puissance_kwc'], ville=ville, lat=lat, lon=lon)
        if avec is not None:
            avec['production_annuelle_kwh'] = production_annuelle_pour_kwc(
                avec['puissance_kwc'], ville=ville, lat=lat, lon=lon)
        return out
    except Exception:  # noqa: BLE001
        logger.warning('dimensionnement_options indisponible', exc_info=True)
        return None


def _production_par_option_publique(devis, data, dimensionnement_options):
    """PACT10 (« deux optimiseurs ») — clé ``production_par_option`` :
    séries de production journalière PAR OPTION (même forme que
    ``courbes_journalieres.production``, contrat
    ``apps/ventes/contract_samples/dimensionnement_options.json``),
    calculées à la volée avec le kWc DE CHAQUE OPTION — UNIQUEMENT quand
    ``dimensionnement_options.divergent`` est vrai : deux options au MÊME
    kWc partagent déjà la même courbe (``courbes_journalieres``), la
    recalculer deux fois ferait diverger deux séries censées être
    identiques. Sinon (ou sur toute erreur) : ``{'sans': None, 'avec':
    None}`` — la page retombe sur la courbe unique déjà servie. Lecture
    pure, rien n'est persisté."""
    resultat = {'sans': None, 'avec': None}
    if not dimensionnement_options or not dimensionnement_options.get('divergent'):
        return resultat
    try:
        from ..etude_horaire import production_journaliere_par_saison
        ville, lat, lon = _localisation_pour_moteur_horaire(devis, data)
        sans_kwc = (dimensionnement_options.get('sans') or {}).get('puissance_kwc')
        if sans_kwc:
            resultat['sans'] = production_journaliere_par_saison(
                sans_kwc, ville=ville, lat=lat, lon=lon) or None
        avec_bloc = dimensionnement_options.get('avec') or {}
        avec_kwc = avec_bloc.get('puissance_kwc')
        if avec_kwc:
            resultat['avec'] = production_journaliere_par_saison(
                avec_kwc, ville=ville, lat=lat, lon=lon) or None
        return resultat
    except Exception:  # noqa: BLE001
        logger.warning('production_par_option indisponible', exc_info=True)
        return {'sans': None, 'avec': None}
