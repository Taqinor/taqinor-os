"""Consommation, économies mensuelles et KPI de la proposition publique (SPL250, déplacé de ``public_views.py``).

Séries mensuelles de production et de consommation (sources mesurées /
estimées), économies mensuelles et leurs notes, KPI par mode de marché, en-tête
bancable — assemblés par ``public_views.proposal_data``. Aucune vue ici.
Déplacement pur : corps octet-identiques (seule la profondeur des imports
relatifs locaux change), prouvé par ``tests/golden/split_pv_economie.json``.
"""
import logging

from ..models import ShareLink
# ── Profil saisonnier de production solaire au Maroc (T4) ────────────────────
# M1 — poids mensuels IMPORTÉS de la source unique (quote_engine/constants.py,
# table GHI verrouillée par le drift-lock DC9). Ce module en portait une copie
# manuelle de la table : une seconde vérité qu'aucun test ne surveillait.
from ..quote_engine.constants import MOROCCO_SOLAR_MONTHLY_WEIGHTS

# Même émetteur de journal qu'avant le déplacement (filtres et tests inchangés).
logger = logging.getLogger("apps.ventes.public_views")


def _monthly_production(data) -> list:
    """T4 — production solaire mensuelle (kWh/mois), 12 valeurs.

    Source : production annuelle RÉELLE du devis (``build_quote_data`` →
    ``prod_kwh``, qui reprend déjà l'étude/PVGIS stockée quand elle existe). On
    distribue ce total RÉEL via ``MOROCCO_SOLAR_MONTHLY_WEIGHTS`` (profil GHI
    Maroc normalisé). On ne fabrique jamais le total ; sans annuel → []."""
    annual = data.get('prod_kwh')
    try:
        annual = float(annual)
    except (TypeError, ValueError):
        return []
    if annual <= 0:
        return []
    return [round(annual * w) for w in MOROCCO_SOLAR_MONTHLY_WEIGHTS]


#: Sources de consommation du bloc horaire canonique qui reposent sur une
#: donnée RÉELLE du client. Chacune est soit une saisie en kWh, soit une (ou
#: douze) facture(s) RÉELLE(S) back-calculée(s) par le barème (tranches
#: progressives puis sélectives — ``bareme.kwh_depuis_facture_mad`` inverse la
#: VRAIE fonction de facturation par dichotomie, JAMAIS une division par un
#: prix moyen). Tout le reste — ``absente``, ``inconnue``, toute valeur future
#: non listée ici — est refusé : la série publiée est une lecture, jamais une
#: supposition.
#:
#: À NE PAS CONFONDRE avec ``_SOURCES_CONSO_MESUREES`` (plus bas), qui répond à
#: une AUTRE question : la VARIATION mensuelle est-elle mesurée ? Une facture
#: d'hiver seule est une donnée réelle (elle a droit de cité ici) mais elle est
#: répétée sur douze mois, donc sa variation reste estimée (elle est absente
#: de l'autre liste, et la note du bloc « économies » le dit).
_SOURCES_CONSO_REELLES = (
    'kwh_mensuels_saisis',
    'factures_mensuelles_reelles',
    'facture_hiver',
    'facture_hiver_ete',
)


def _monthly_consumption_etude(devis) -> list:
    """Les 12 kWh/mois DÉJÀ résolus par le bloc horaire canonique, ou ``[]``.

    LA SEULE VÉRITÉ. ``services.rafraichir_etude_horaire_devis`` persiste sur
    le devis (``etude_params['etude_horaire']``) la série de consommation que
    LE MOTEUR utilise pour tout le reste : les économies mensuelles, la
    synthèse de la page 1 du PDF, le dimensionnement. Elle est résolue par
    ``etude_horaire.profil_depuis_factures``, dont l'échelle de priorité est
    plus riche que celle du repli ci-dessous : 12 kWh saisis, sinon 12 factures
    RÉELLES, sinon la facture d'hiver (+ celle d'été si distincte) —
    back-calculées au barème de la SOCIÉTÉ, ou à la grille nationale du
    millésime à défaut.

    Sans cette lecture, la page publiait une consommation issue d'un SECOND
    chemin, plus étroit (``kwh_from_bill`` exige le ``distributeur`` du lead) :
    un lead venu du tunnel dont le distributeur n'est pas renseigné — ou vaut
    « autre », ce que le webhook pose explicitement quand le visiteur répond
    « inconnu » — servait ``monthly_consumption: []`` et le graphe perdait la
    ligne « votre consommation », alors que le devis affichait juste à côté des
    économies calculées sur cette même consommation. Deux chemins, deux
    vérités : celui-ci est la seule.

    Renvoie ``[]`` (jamais une série partielle) au moindre doute : bloc absent,
    source non réelle, mois manquants, valeur non numérique ou négative.
    """
    bloc = (getattr(devis, 'etude_params', None) or {}).get('etude_horaire')
    if not isinstance(bloc, dict):
        return []
    if bloc.get('source_consommation') not in _SOURCES_CONSO_REELLES:
        return []
    mois = bloc.get('mois')
    if not isinstance(mois, list) or len(mois) != 12:
        return []
    par_numero = {}
    for entree in mois:
        if not isinstance(entree, dict):
            return []
        numero, valeur = entree.get('mois'), entree.get('consommation_kwh')
        if (isinstance(numero, bool) or not isinstance(numero, int)
                or not 1 <= numero <= 12):
            return []
        if (isinstance(valeur, bool)
                or not isinstance(valeur, (int, float)) or valeur < 0):
            return []
        par_numero[numero] = valeur
    if len(par_numero) != 12:
        return []
    serie = [round(par_numero[numero]) for numero in range(1, 13)]
    # Une année entièrement nulle n'est pas une consommation : on omet.
    return serie if any(v > 0 for v in serie) else []


def _monthly_consumption(devis) -> list:
    """T4 — consommation mensuelle (kWh/mois) depuis les données RÉELLES.

    SOURCE PRIORITAIRE (24/08/2026) : la série déjà résolue par le bloc horaire
    canonique du devis (:func:`_monthly_consumption_etude`) — le MÊME chiffre
    que celui sur lequel le moteur a calculé les économies affichées sur la
    même page. Aucun second calcul, aucune seconde règle.

    REPLI, inchangé, quand aucun bloc horaire n'est persisté sur le devis :
    lit les factures du lead du devis via le sélecteur CRM (cross-app lecture
    seule, jamais d'import direct de ``apps.crm.models``). QX7d — convertit
    MAD→kWh par le MÊME barème réel (progressif puis sélectif) que le chemin ROI
    (``quote_engine.pricing.kwh_from_bill`` : tranches ONEE/Lydec/Redal du
    distributeur, repli plat étiqueté sinon), au lieu de l'ancien prix plat
    figé 1,75 MAD/kWh qui contredisait le tarif ROI (~1,20) sur la même
    proposition. QJR405 — l'inversion se fait en mode ``facture_totale``
    (le lead saisit le TOTAL de sa facture : lignes fixes et TPPAN
    comprises). Facture d'hiver toute l'année, ou hiver+été quand
    ``ete_differente`` (été = mois ~Mai→Oct). Sans facture → [] (la page masque
    alors le graphe)."""
    depuis_etude = _monthly_consumption_etude(devis)
    if depuis_etude:
        return depuis_etude
    from apps.crm.selectors import lead_bills_for_devis
    bills = lead_bills_for_devis(devis)
    if not bills:
        return []
    from ..quote_engine.pricing import kwh_from_bill
    utility = bills.get('distributeur')
    hiver_mad = bills['facture_hiver']
    ete_mad = bills['facture_ete']
    # Mois « été » (index 0=Jan) : Mai→Octobre. Le reste = hiver.
    ete_months = {4, 5, 6, 7, 8, 9}
    # Barème stable par facture → on mémoïse la conversion (2 valeurs max).
    _cache = {}

    # ── M10 (audit adversarial du 19/08/2026) — PAS DE DISTRIBUTEUR RÉEL, PAS
    # DE COURBE. Sans distributeur, ``kwh_from_bill`` dégrade sur un prix PLAT
    # (1,20 MAD/kWh) et le signale (``estimation``) — ce drapeau était JETÉ, et
    # la page publiait une courbe de consommation en kWh qui n'était qu'une
    # division de la facture par un forfait, présentée comme une mesure. Le
    # drapeau décide maintenant : estimation ⇒ série vide ⇒ la page masque le
    # graphe (elle le fait déjà pour un devis sans facture).
    #
    # ── QJR405 (DR7, moitié ERP) — ON INVERSE UNE FACTURE **TOTALE**. Les
    # champs ``facture_hiver`` / ``facture_ete`` du lead viennent de l'écran
    # « Votre facture d'électricité mensuelle (MAD) » : c'est le TOTAL que le
    # client lit sur son papier — lignes fixes (location compteur + entretien)
    # et TPPAN comprises. Les inverser avec le modèle ÉNERGIE SEULE attribuait
    # ces ~40 MAD fixes + la TPPAN à de la consommation et SURESTIMAIT la
    # courbe « votre consommation » publiée (facture de référence : 592,77 MAD
    # ⇒ 429 kWh/mois au lieu de 359, soit +19,5 %). ``facture_totale=True``
    # route l'inversion sur ``bareme.kwh_depuis_facture_mad``, l'inverse EXACT
    # de ``bareme.facture_mad`` (chaîne principale) : lignes fixes retranchées
    # d'abord, TPPAN résolue par la dichotomie sur la facture COMPLÈTE.
    _sonde = kwh_from_bill(hiver_mad, utility=utility, facture_totale=True)
    if _sonde.get('estimation'):
        return []

    def _kwh(mad):
        if mad not in _cache:
            _cache[mad] = round(
                kwh_from_bill(mad, utility=utility, facture_totale=True)
                .get('kwh_mensuel') or 0)
        return _cache[mad]

    out = []
    for m in range(12):
        if (bills['ete_differente'] and ete_mad is not None
                and m in ete_months):
            mad = ete_mad
        else:
            mad = hiver_mad
        out.append(_kwh(mad))
    return out


def _kpi_num(v):
    """Coercion numérique défensive pour le bloc KPI (None si non numérique)."""
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def _mode_kpis(data):
    """QX49 — bloc KPI par mode d'installation, whitelist STRICTE côté serveur.

    Ne renvoie QUE des grandeurs client-facing (jamais prix_achat/marge — RULE
    #4). La page web peut rendre les 4 variantes (résidentiel/agricole/
    industriel/commercial) sans re-calcul côté client. None hors des modes gérés.
    """
    mode = (data.get('mode_installation') or '').strip().lower()
    etude = data.get('etude') or {}
    if mode == 'agricole':
        # AGR301 — liste blanche agricole = les sept dérivées v1 que le moteur
        # pompage écrit pour son rendu (contrat partagé ``proposal_data.json``
        # › ``exemple_agricole.mode_kpis``). RETIRÉS : ``bassin_m3`` (un « ×2 »
        # du besoin de pointe sans aucune source, bâti sur des ET0 ESTIMÉES) et
        # ``fda_eligible`` (un verdict d'éligibilité propre au client, contraire
        # à Q22 / D-AGR-6 — l'aide revient comme RÈGLE sans montant via
        # ``synthese_agricole``, AGR306/AGR308). AJOUTÉ : ``heures_pompage``,
        # dont dépend le m³/jour (le PDF dit « sur N h », la page le dit aussi).
        # Aucun bassin n'est servi tant qu'aucun nombre de jours d'autonomie
        # n'est décidé ou sourcé ; le module agronomique n'est plus importé
        # ici (gardé par test_qx49_proposal_payload).
        return {
            'pompe_cv': _kpi_num(etude.get('pompe_cv')),
            'pompe_kw': _kpi_num(etude.get('pompe_kw')),
            'hmt_m': _kpi_num(etude.get('hmt_m')),
            'debit_hmt_m3h': _kpi_num(etude.get('debit_hmt_m3h')),
            'm3_jour': _kpi_num(etude.get('m3_jour')),
            'heures_pompage': _kpi_num(etude.get('heures_pompage')),
            'champ_kwc': _kpi_num(etude.get('champ_kwc')) or _kpi_num(data.get('puissance_kwc')),
        }
    if mode in ('industriel', 'commercial'):
        # CIQ129 — plus AUCUNE clé d'étude écran v1 lue (retirées du schéma) :
        # la MÊME projection de ``synthese_ci`` que sert /proposition.
        from ..quote_engine.ci.synthese import synthese_ci
        return _mode_kpis_ci(synthese_ci(data) or {})
    return None


def _mode_kpis_ci(synthese):
    """CIQ306 — ``mode_kpis`` C&I v2 : PROJECTION de ``synthese_ci``
    (contrat ``proposal_data.json`` › ``notes_ciq4.mode_kpis_ci_v2``) —
    énergie + ``argent.indicateurs.retour_ans`` + ``argent.revente``. Aucune
    clé d'étude JS lue, aucun calcul ; l'argent omis (ou sa case décochée)
    ⇒ économies, payback et revente à ``None``. CIQ307 : par
    ``chiffres_cles`` — la MÊME projection que lisent les gabarits PDF.
    Les NOMS de sortie sont ceux du contrat (forme ``mode_kpis``), pas des
    clés d'``etude_params``."""
    from ..quote_engine.ci.synthese import chiffres_cles
    c = chiffres_cles(synthese)
    return {
        'taux_autoconso': c['taux_autoconso_pct'],
        'taux_couverture': c['taux_couverture_pct'],
        'economies_annuelles': c['economie_annuelle_mad'],
        'payback': c['payback_ans'],
        'injection_kwh_an': c['revente_kwh_an'],
        'injection_dh_an': c['revente_mad_an'],
    }


#: PV77 — clés de l'étude bancable qui ne sortent JAMAIS côté client. Le bloc
#: brut ``etude_params['simulation']`` (P75/P90, arbre de pertes, VAN/TRI,
#: puissance souscrite…) est un outil d'INGÉNIERIE : il vit sur le PDF signé par
#: le vendeur et dans l'écran interne, jamais dans une charge utile publique.
_BANKABLE_CLES_INTERNES = ('simulation', 'bankable')


def _sans_internes_bancables(data):
    """Retire l'étude bancable BRUTE de la charge utile publique.

    Ne touche RIEN quand le devis n'en porte pas : le dict est renvoyé tel quel
    (aucune copie, aucune clé ajoutée ou retirée), donc la proposition publique
    d'un devis sans simulation est byte-identique à celle d'aujourd'hui.
    """
    etude = data.get('etude')
    if not isinstance(etude, dict):
        return data
    if not any(cle in etude for cle in _BANKABLE_CLES_INTERNES):
        return data
    propre = dict(data)
    propre['etude'] = {
        cle: valeur for cle, valeur in etude.items()
        if cle not in _BANKABLE_CLES_INTERNES
    }
    return propre


def _bankable_headline(devis, data):
    """PV77 — les DEUX chiffres client de l'étude bancable, ou ``None``.

    Whitelist STRICTE, dans l'esprit de ``_mode_kpis`` : la production P50
    (médiane — le chiffre honnête à annoncer) et l'économie cumulée sur 25 ans
    DÉJÀ affichée par le document (cashflow QX39 du scénario retenu — jamais un
    second chiffre concurrent). Tout le reste de la simulation reste interne :
    P90/P75, décomposition des pertes, VAN/TRI, puissance souscrite.

    ``None`` quand le devis ne porte pas de simulation → la clé n'est pas
    envoyée du tout et la page publique se comporte comme aujourd'hui.
    """
    simulation = (getattr(devis, 'etude_params', None) or {}).get('simulation')
    if not isinstance(simulation, dict) or not simulation:
        return None
    pr = simulation.get('pr')
    p50 = _kpi_num(pr.get('p50_kwh')) if isinstance(pr, dict) else None
    scenario = data.get('scenario') or ''
    gain = (data.get('net_gain_avec') if scenario == 'Avec batterie'
            else data.get('net_gain_sans'))
    if gain is None:
        gain = data.get('net_gain_sans')
        if gain is None:
            gain = data.get('net_gain_avec')
    return {
        'p50_kwh': p50,
        'economies_25_ans': _kpi_num(gain),
        # 'pvgis' (données satellitaires) ou 'manual' (repli hors ligne) —
        # dit au client d'où vient le chiffre, sans rien révéler du modèle.
        'source': simulation.get('source') or None,
    }


#: CJ2b — sources RÉELLES de consommation qui portent une VRAIE variation
#: mensuelle (``etude_horaire.profil_depuis_factures``) : 12 kWh mesurés ou 12
#: factures réelles saisies. Les deux autres sources valides
#: (``facture_hiver``/``facture_hiver_ete``) répètent HONNÊTEMENT un ou deux
#: points réels sur l'année — la variation mois par mois y est donc estimée.
_SOURCES_CONSO_MESUREES = ('kwh_mensuels_saisis', 'factures_mensuelles_reelles')

#: AGNR6 (D-AGNR-1 option (a)) — la source « deux factures » NOMME son origine
#: par le libellé client du contrat ``factures_client.json``, lu dans le
#: catalogue du moteur (une seule chaîne pour la page et le PDF).
_SOURCE_DEUX_FACTURES = 'facture_hiver_ete'


def _libelle_deux_factures():
    """« Estimation — deux factures (hiver/été) » (``i18n_labels``, FR)."""
    from ..quote_engine import i18n_labels
    return i18n_labels.libelle('res_estimation_deux_factures', 'fr')


def _note_economies_mensuelles(modele, source_consommation, estimation):
    """CJ2b — phrase FR qui dit d'où viennent les 12 valeurs, jamais un chiffre
    dans le texte (RULE #4 : aucun montant/prix d'achat). Dit « estimation »
    quand ``estimation`` est vrai (contrat public)."""
    if modele == 'horaire' and not estimation:
        return ('Calculé heure par heure : production PVGIS contre votre '
                'courbe de consommation issue de vos factures mensuelles '
                'réelles.')
    if modele == 'horaire' and source_consommation == _SOURCE_DEUX_FACTURES:
        return (f'{_libelle_deux_factures()} : calcul heure par heure, '
                "production PVGIS contre votre consommation d'hiver et "
                "d'été, répétée sur les douze mois faute de facture mois "
                'par mois.')
    if modele == 'horaire':
        return ('Estimation heure par heure : production PVGIS contre une '
                "consommation dérivée de votre facture d'hiver (et d'été), "
                'répétée sur les douze mois faute de facture mois par mois.')
    if modele == 'factures':
        return ('Estimation : économie annuelle calculée sur vos factures '
                'réelles par tranche tarifaire, répartie sur les douze mois '
                'selon un profil saisonnier type (pas encore un calcul '
                'mois par mois).')
    return ('Estimation : production annuelle × taux d\'autoconsommation de '
            'référence, répartie sur les douze mois selon un profil '
            'saisonnier type — transmettez vos factures pour un calcul '
            'plus précis.')


def _note_economies_mensuelles_standard(source_consommation=None):
    """L-NIV (24/08/2026) — méthodologie NEUTRE (niveau standard) : ni
    « PVGIS », ni « heure par heure », ni « tranches » — la mécanique interne
    du moteur n'est pas montrable à un prospect pas encore qualifié. Les 12
    valeurs MAD/mois, elles, restent EXACTEMENT les mêmes (règle fondateur :
    les chiffres ne changent jamais, seul le texte de méthode se neutralise).

    AGNR6 — la source « deux factures » garde son libellé client (une
    provenance, pas une mécanique du moteur) ; les autres, la phrase neutre."""
    if source_consommation == _SOURCE_DEUX_FACTURES:
        return (f"{_libelle_deux_factures()} : votre consommation d'hiver et "
                "d'été, répétée sur les douze mois, face à la production "
                'estimée de votre installation.')
    return ('Estimation basée sur votre profil de consommation et la '
            'production estimée de votre installation, répartie sur les '
            'douze mois selon un profil saisonnier type.')


def _economies_mensuelles_publiques(devis, data, synthese,
                                    niveau=ShareLink.NIVEAU_CONFIANCE):
    """CJ2b (fondateur, 21/08/2026) — bloc ``economies_mensuelles`` : les 12
    valeurs MAD/mois sans/avec batterie « qu'on ne voit ni ... calculée ni la
    donnée pvgis ». JAMAIS un second calcul : ``sans``/``avec`` viennent tels
    quels du moteur (``eco_s_monthly``/``eco_a_monthly``, la même série que la
    courbe mensuelle du PDF).

    ``None`` quand la couche économique n'est pas servable — MÊME garde que
    ``synthese_economies`` (``synthese`` est déjà ``None`` si Z2 s'applique) :
    aucune ré-implémentation de l'ancrage.

    ``avec``/``total_avec`` ne sont servis QUE quand le document REND l'option
    batterie (``avec_ok``, le drapeau post-repli/post-QF6 du moteur — le même
    repère que ``courbes_journalieres._options_reelles``) — jamais un chiffre
    « avec batterie » sur une option que ce devis ne peut pas livrer (CJ2a a
    trouvé un vrai trou catalogue : la batterie non livrable en résidentiel
    monophasé). Un devis MONO-option « Avec batterie » sert donc bien sa série,
    puisque c'est la seule option qu'il présente.
    RULE #4 — aucun prix d'achat/marge, uniquement les montants client TTC déjà
    calculés par le moteur.
    """
    if synthese is None:
        return None
    try:
        return _economies_mensuelles_calcul(devis, data, niveau)
    except Exception:  # noqa: BLE001 — voir ci-dessous
        # UN BLOC D'AFFICHAGE ADDITIF NE FAIT JAMAIS TOMBER LA PAGE CLIENT.
        # Cet appel vit dans le grand ``try`` de ``proposal_data``, dont le
        # ``except`` répond 404 « Proposition indisponible » : sans cette garde,
        # un défaut dans DOUZE CHIFFRES D'AFFICHAGE priverait le client de sa
        # proposition ENTIÈRE (prix, composition, signature). Même discipline
        # que ``construire_courbes_journalieres``, qui porte déjà la sienne.
        logger.warning('economies_mensuelles indisponibles', exc_info=True)
        return None


def _economies_mensuelles_calcul(devis, data, niveau=ShareLink.NIVEAU_CONFIANCE):
    """Cœur de :func:`_economies_mensuelles_publiques` (exceptions gérées
    au-dessus)."""
    sans = data.get('eco_s_monthly')
    if not (isinstance(sans, (list, tuple)) and len(sans) == 12
            and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                    for v in sans)):
        return None

    avec = data.get('eco_a_monthly')
    # CJ2b/L-VAR (24/08/2026) — LA SERVABILITÉ SE LIT SUR ``avec_ok`` SEUL.
    # L'ancienne condition exigeait EN PLUS ``deux_options`` : sur un devis
    # MONO-option « Avec batterie » (avec_ok vrai, deux_options faux — le cas
    # exact de DEV-202608-0023, rétréci par la resynchronisation 3D), elle
    # annulait la série « avec » du SEUL document que le client possède. La
    # page lisait alors ``avec === null`` comme « la batterie n'est pas
    # vendable » et masquait le calque batterie du graphe de production —
    # alors que l'unique option de ce devis EST celle avec batterie.
    # ``avec_ok`` est le drapeau POST-repli/POST-QF6 du moteur (builder.py) :
    # il vaut déjà faux quand le document ne rend pas l'option batterie (devis
    # sans batterie, hybride sans batterie Z1, scénario stocké « Sans
    # batterie »), donc la garde CJ2a — jamais un chiffre « avec batterie » sur
    # une option que ce devis ne livre pas — reste entièrement portée. C'est
    # aussi EXACTEMENT le repère que lit ``courbes_journalieres.
    # _options_reelles`` : les deux blocs ne peuvent plus se contredire.
    avec_reellement_vendable = bool(data.get('avec_ok'))
    if not (avec_reellement_vendable
            and isinstance(avec, (list, tuple)) and len(avec) == 12
            and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                    for v in avec)):
        avec = None

    modele = data.get('savings_model')
    if modele not in ('horaire', 'factures'):
        # 'etude' (override industriel/commercial saisi) ou toute autre valeur
        # inattendue : jamais montré comme 'horaire'/'factures' sans l'être.
        modele = 'estimation'
    bloc_horaire = ((getattr(devis, 'etude_params', None) or {})
                    .get('etude_horaire') or {})
    source_consommation = bloc_horaire.get('source_consommation')
    estimation = (
        bool(data.get('savings_estimated'))
        or modele != 'horaire'
        or source_consommation not in _SOURCES_CONSO_MESUREES)

    return {
        'sans': [round(v) for v in sans],
        'avec': [round(v) for v in avec] if avec is not None else None,
        'total_sans': round(sum(sans)),
        'total_avec': round(sum(avec)) if avec is not None else None,
        'devise': 'MAD',
        'modele': modele,
        'estimation': estimation,
        'note': (
            _note_economies_mensuelles_standard(source_consommation)
            if niveau == ShareLink.NIVEAU_STANDARD
            else _note_economies_mensuelles(
                modele, source_consommation, estimation)
        ),
    }
