"""Création d'un devis — les chemins par lesquels un devis naît.

Le devis composé depuis un layout 3D (`build_devis_from_layout`), le dry-run
qui l'approuve (`composer_devis_residentiel`), le devis AUTOMATIQUE depuis un
lead (dimensionnement, refus motivé, marque anti-doublon, planification), le
brouillon issu d'un document OCR, la duplication, le devis SAV et l'upsell
d'intervention, et les préréglages (enregistrer / appliquer).

LES CHEMINS RESTENT CINQ, ET DIFFÉRENTS. Ce module les RASSEMBLE, il ne les
unifie pas : leur convergence sur un pipeline unique est M4/M5 (QJR80-QJR85,
puis les bascules). Ici, rien n'a changé de comportement.

IMPORT AMONT DE `domain/taille` : `composer_devis_residentiel` porte
`panel_watt=_AUTO_PANEL_WATT` comme VALEUR PAR DÉFAUT, évaluée à la
définition de la fonction — donc au chargement du module, avant tout pont de
bas de fichier. `domain/taille` est une FEUILLE (il n'importe que
`domain/catalogue`), l'import ne peut donc pas boucler.

QJR76 (M3) — DÉPLACEMENT PUR depuis ``apps/ventes/services.py``, dernier de la
vague : après lui, ``services.py`` n'est plus qu'une façade de ré-exports. Les
corps sont recopiés à l'identique ; la seule retouche possible est mécanique
(`from .x` → `from ..x`, MÊME cible).

ORDRE DE CHARGEMENT : ``services.py`` importe ``domain/`` à la toute fin ; un
module de ``domain/`` importe en BAS de fichier les noms qu'il lit ailleurs, et
il vise TOUJOURS le module qui porte le corps — jamais la façade.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` : des tests capturent ce nom.
"""
from decimal import Decimal, ROUND_HALF_UP
import logging

from apps.ventes.domain.taille import _AUTO_PANEL_WATT

logger = logging.getLogger("apps.ventes.services")


def create_draft_devis_from_ocr(*, company, user, lead, fields):
    """FG106 — crée un DEVIS brouillon (sans lignes) à partir d'un document OCR.

    Point d'entrée cross-app sanctionné (services.py) pour la passerelle
    OCR → ventes (apps.publicapi). Le devis part TOUJOURS d'un lead (le client
    est résolu côté serveur via crm.services, sans doublon — réutilise la même
    règle que le générateur). Les lignes ne sont PAS créées : une LigneDevis
    exige un Produit du catalogue, qu'un document OCR brut ne fournit pas — le
    devis brouillon est laissé à compléter dans l'éditeur. Les montants/numéro
    extraits sont consignés dans la note du devis pour aider la saisie.

    Le devis reste ``brouillon`` : ce service CRÉE, il ne change aucun statut
    aval (règle #4).
    """
    from apps.ventes.models import Devis
    from apps.ventes.utils.references import create_with_reference
    from apps.crm.services import resolve_client_for_lead

    if lead is None:
        raise ValueError("create_draft_devis_from_ocr requires a lead")
    client = resolve_client_for_lead(lead)

    fields = fields or {}
    notes = ["Devis brouillon créé depuis un document OCR."]
    for key, label in (('numero', 'N° document'), ('montant_ht', 'Montant HT'),
                       ('montant_tva', 'Montant TVA'),
                       ('montant_ttc', 'Montant TTC'), ('date', 'Date')):
        val = fields.get(key)
        if val not in (None, ''):
            notes.append(f"{label} : {val}")
    note = "\n".join(notes)

    def _create(ref):
        return Devis.objects.create(
            company=company,
            reference=ref,
            client=client,
            lead=lead,
            statut=Devis.Statut.BROUILLON,
            created_by=user,
            note=note,
        )

    devis = create_with_reference(Devis, 'DEV', company, _create)
    logger.info('FG106: devis brouillon %s créé depuis OCR (company %s)',
                devis.reference, getattr(company, 'id', '?'))
    return devis


def dupliquer_devis(devis, *, user):
    """NTUX13 — Duplique ``devis`` en un devis BROUILLON totalement
    INDÉPENDANT (nouveau numéro, jamais le statut de la source — même un
    devis ``accepte``/``envoye`` redémarre en ``brouillon``).

    À la différence de ``dupliquer-variante`` (QJ15, ``views/devis.py``) qui
    groupe ses copies avec l'original via ``version_parent``/``version`` pour
    une comparaison côte-à-côte, CE duplicata est délibérément SANS lien de
    version : ``version=1``, ``version_parent=None``. Aucun chantier/
    BonCommande/Facture n'est jamais copié — ces objets naissent en aval d'un
    devis ACCEPTÉ (rule #4) et ne sont référencés nulle part sur ``Devis``
    lui-même, donc un brouillon frais n'en hérite jamais.

    Les lignes sont clonées à l'identique (mêmes quantités/prix/sections)."""
    from apps.ventes.models import Devis
    from apps.ventes.utils.company_settings import create_numbered

    company = devis.company
    holder = {}

    def _save(ref):
        obj = Devis.objects.create(
            company=company, reference=ref,
            client=devis.client, lead=devis.lead,
            statut=Devis.Statut.BROUILLON,
            taux_tva=devis.taux_tva,
            remise_globale=devis.remise_globale,
            note=(f'[Copie de {devis.reference}] ' + (devis.note or '')).strip(),
            mode_installation=devis.mode_installation,
            etude_params=devis.etude_params,
            prix_cible_kwc=devis.prix_cible_kwc,
            devise=devis.devise,
            taux_change=devis.taux_change,
            created_by=user,
            # Duplicata indépendant : jamais de groupe de version (à la
            # différence de dupliquer-variante, QJ15).
            version=1, version_parent=None, is_active=True,
        )
        holder['obj'] = obj
        return obj

    create_numbered(Devis, company, 'devis', _save)
    copie = holder['obj']

    # QJR116 — UN SEUL cloneur pour les trois chemins de copie
    # (``domain/lignes.cloner_lignes``) : la liste de champs n'est plus
    # maintenue à la main ici, donc elle ne peut plus diverger de celle du
    # renouvellement ou de la gamme sœur. Elle reprend le jeu COMPLET —
    # y compris le rattachement au LOT, qui manquait aux trois.
    cloner_lignes(devis, copie)
    logger.info('NTUX13: devis %s dupliqué en %s (company %s)',
                devis.reference, copie.reference, getattr(company, 'id', '?'))
    return copie


def _arbitrage_du_calepinage(layout, nb_panneaux, kwc, *, company):
    """AOF164 / PVG2 — le compte RETENU pour ce layout, et le kWc qui le SUIT.

    UNE SEULE écriture de cette règle, pour les DEUX chemins de création qui la
    subissent (le calepinage 3D et le devis automatique, QJR96) : la recopier
    aurait suffi à ce que la bascule A/B du moteur de calepinage s'applique d'un
    côté et pas de l'autre — c'est-à-dire à ce que le même toit sorte avec deux
    comptes de modules selon le bouton par lequel le devis est né.

    Drapeau ``USE_MOTEUR_CALEPINAGE`` baissé (le défaut) ⇒ ``arbitrer_compte_
    calepinage`` rend ``None`` AVANT tout calcul et ce couple ressort tel quel :
    comportement bit-identique à l'historique. Au-delà de la tolérance PVG2,
    ``retenu`` REDEVIENT le compte historique et rien ne bouge non plus.

    Le kWc SUIT le compte : laisser l'ancien kWc face au nouveau compte
    produirait un devis dont la puissance ne correspond plus aux panneaux.
    """
    arbitrage = arbitrer_compte_calepinage(layout, nb_panneaux,
                                           company=company)
    if arbitrage is None or arbitrage['retenu'] == nb_panneaux:
        return nb_panneaux, kwc
    watt_reference = layout.get('panelWatt') or layout.get('watt')
    if not watt_reference and nb_panneaux and kwc:
        watt_reference = kwc * 1000.0 / nb_panneaux
    nb_panneaux = arbitrage['retenu']
    if watt_reference:
        kwc = round(nb_panneaux * float(watt_reference) / 1000.0, 3)
    return nb_panneaux, kwc


def _calepinage_range(layout, toiture, kwc):
    """QJ21 / FG248 — ce qu'un calepinage APPORTE au devis, lu UNE fois.

    Rend ``(layout_stocke, etude_initiale)`` :

    * ``layout_stocke`` est une COPIE du layout de l'appelant (on ne mute jamais
      son dict) enrichie de ``_pans_geometry``, la géométrie par pan DÉJÀ
      PROCESSÉE, pour qu'aucun consommateur n'ait à rejouer
      ``extract_roof_config`` ;
    * ``etude_initiale`` est l'étude que ce chemin APPORTE, et lui seul : le kWc
      que le TOIT modélise et la configuration de toiture importée du builder
      3D. Le pipeline la transporte jusqu'à la création ; il n'en dérive rien.
      Le kWc, lui, est RE-POSÉ ensuite par son propriétaire sur les lignes
      réellement écrites (QJR63, étape 8) — le calepinage modélise à 720 W
      constants quand le devis vend le panneau RÉEL (710 W sur
      DEV-202608-0007), et stocker les deux mettrait deux bases de puissance
      dans le même document.

    QJR96 — LES DEUX ADAPTATEURS DE CRÉATION LISENT ICI. Le devis automatique
    synthétise lui aussi un layout (le tracé du client devient une vraie zone
    roofPro11, ``zone_toit_depuis_contour``) : sans ce lecteur commun, un devis
    né du tunnel repartait sans ``_pans_geometry`` ni ``etude_params['toiture']``
    dès qu'il cessait de passer par ``build_devis_from_layout``.
    """
    layout_stocke = dict(layout or {})
    if toiture and toiture.get('pans'):
        layout_stocke['_pans_geometry'] = toiture['pans']
    etude_initiale = {}
    if kwc:
        etude_initiale['puissance_kwc'] = kwc
    if toiture:
        etude_initiale['toiture'] = toiture
    return layout_stocke, etude_initiale


def build_devis_from_layout(*, layout, user, company, lead=None, client=None,
                            taux_tva=Decimal('20'), remise_globale=Decimal('0'),
                            deux_options=False, journal=None, phase=None,
                            dimensionnement_avec=None,
                            mppt_paires=1, structure_type='acier'):
    """Q3 — turn a FINALISED roof layout into a coherent, company-scoped Devis.

    ``mppt_paires`` / ``structure_type`` (QJR80) — les DEUX paramètres de
    composition que cette fonction n'acceptait pas et ne transmettait donc
    jamais, pendant que le dry-run qui l'approuve
    (``composer_devis_residentiel``) les transmettait : l'aperçu et le devis
    pouvaient diverger sur les mètres de câble DC et sur le matériau de
    structure. Les défauts sont ceux de ``composition_residentielle``
    (1 paire, acier), donc un appelant qui ne les renseigne pas compose
    EXACTEMENT ce que ce dépôt composait déjà.

    ``deux_options`` (U2, fondateur 20/08/2026) — compose la forme DEUX
    OPTIONS (« sans batterie » ET « avec batterie » dans un seul devis, cf.
    ``composition_residentielle``) et stocke le scénario correspondant. Défaut
    False : le calepinage 3D a DÉJÀ arrêté son scénario à l'écran, il garde
    donc sa composition mono-option, byte-identique à l'historique.

    ``dimensionnement_avec`` (L-2OPT, optionnel) — ce que le moteur calibré
    recommande POUR L'OPTION AVEC BATTERIE, quand ce n'est pas le même champ PV
    que l'option sans : ``{'nb_panneaux': int, 'kwc': float,
    'batterie_kwh': float | None}``. Combiné à ``deux_options``, il fait
    composer DEUX kits complets, fusionnés en lignes VARIANTÉES (cf.
    :func:`composition_deux_optimiseurs`). ``None`` (LE DÉFAUT) ⇒ un seul champ
    PV, exactement comme aujourd'hui — et un ``nb_panneaux`` identique à celui
    de l'option sans y retombe aussi, par le repli de sécurité de la fusion.

    ``journal`` (U3, optionnel) — dict que l'appelant fournit et que la
    construction remplit sur place avec ce que la composition a REFUSÉ de
    faire : ``marques_manquantes`` (rôles épinglés sans AUCUN candidat en
    stock) et ``avertissements`` (vivier batterie vide…). Sans ce canal, un
    devis pouvait partir SANS panneaux — la marque épinglée ayant vidé leur
    vivier — à un prix effondré, sans que personne ne l'apprenne. Absent
    (``None``) ⇒ comportement inchangé.

    ``phase`` (PVCOMPAT, optionnel) — le RACCORDEMENT déclaré par le client
    (``'monophase'``/``'triphase'``), transmis tel quel à
    ``composition_residentielle`` : un abonnement monophasé n'accepte pas un
    onduleur triphasé. ``None`` ⇒ aucun filtre, comportement inchangé.

    ``layout`` is the serialized roofPro11 output (see Devis.roof_layout):
    a ``result`` block ``{panels, kwc, annualKwh, savings}`` plus an optional
    ``scenario``/equipment hint. From it we compose Devis lines off the seeded
    catalogue via ``composition_residentielle`` — le KIT COMPLET du simulateur
    (panneau, onduleur du bon palier, batteries, structures, socles,
    accessoires, tableau de protection AC/DC, installation, transport, et le
    duo Smart Meter + clé Wifi derrière un onduleur Huawei), et non plus le seul
    squelette panneau + onduleur. La classification par mots-clés reste celle du
    moteur PDF (panneau / onduleur réseau|injection|hybride / batterie) et la
    référence passe toujours par l'util anti-collision (jamais count()+1). The
    client is resolved server-side from the lead via crm.services (no
    duplicates). The layout's production/savings are stored into
    ``etude_params``. A price-less catalogue product is NEVER quoted, and a
    component missing from the catalogue is skipped rather than fatal.

    QJ21 — the stored ``roof_layout`` is enriched with a ``_pans_geometry`` key
    holding the processed per-pan list (azimut_deg, inclinaison_deg, kwc,
    nb_panneaux, orientation, label, roof_type) so consumers never have to
    re-run ``extract_roof_config`` to access the full multi-plane design.

    Returns the created Devis. The Devis is left ``brouillon`` — this service
    only BUILDS; it never changes downstream statuses (rule #4).

    QJR95 (M5, bascule 3/5) — CETTE FONCTION EST DEVENUE UN ADAPTATEUR. Ce
    qu'elle garde est la LECTURE DU CALEPINAGE : d'un layout 3D tirer un compte
    de panneaux, un wattage, un kWc, un scénario et une toiture. C'est la seule
    chose que ce chemin sait faire et que les quatre autres ne savent pas, donc
    la seule qui reste ici. Tout ce qui suivait — composer, vérifier, créer,
    écrire les lignes, écrire l'étude, finaliser — était une recopie des mêmes
    étapes dans un ordre qui n'était celui d'aucun autre chemin ; elle est
    SUPPRIMÉE et remplacée par un appel à ``pipeline.appliquer``.

    DEUX GAINS ASSUMÉS (R4-C.5, portés au DONE LOG) :

    * les QUATRE ÉTUDES sont désormais rafraîchies. Ce chemin n'appelait
      ``rafraichir_etudes_du_devis`` **pas du tout** : un devis né du calepinage
      partait sans bloc horaire, sans tableau de dimensionnement et sans profils
      comparatifs, et n'en recevait qu'au premier enregistrement ultérieur ;
    * la PRÉ-VÉRIFICATION passe aux trois scénarios (QJR82). Elle n'existait ici
      que dans la vue appelante, en version mono-scénario : un devis à deux
      options pouvait naître avec un seul onduleur composable, et ne servir
      qu'une des deux options qu'il promet au client.
    """
    from apps.ventes.models import Devis

    if client is None:
        if lead is None:
            raise ValueError("build_devis_from_layout requires a lead or client")
        from apps.crm.services import resolve_client_for_lead
        client = resolve_client_for_lead(lead)

    result = dict((layout or {}).get('result') or {})
    nb_panneaux = int(result.get('panels') or 0)
    kwc = float(result.get('kwc') or 0)
    # QJR95 — ``annualKwh`` / ``savings`` ne sont plus relus ICI : la
    # production et les économies que le calepinage porte sont écrites par
    # l'étape 6 (``pipeline.ecrire_etude_params``), qui les lit dans le MÊME
    # bloc ``result`` du layout transmis. Les relire des deux côtés, c'était
    # deux lecteurs pour une donnée.

    # FG248 — pont 3D toiture → ERP : extrait la config toiture (surface/pans/
    # orientation/inclinaison/kWc) du builder 3D. Quand le bloc ``result`` ne
    # porte pas le nombre de panneaux / la puissance, on retombe sur la somme des
    # pans (cohérence kWc/panneaux écran ↔ pont 3D). Layout sans géométrie →
    # dict vide → comportement historique strictement inchangé.
    toiture = extract_roof_config(layout)
    if toiture:
        if nb_panneaux <= 0 and toiture.get('nb_panneaux'):
            nb_panneaux = int(toiture['nb_panneaux'])
        if not kwc and toiture.get('kwc'):
            kwc = float(toiture['kwc'])

    # AOF164 / PVG2 — la bascule A/B du moteur de calepinage, écrite une seule
    # fois pour les deux chemins de création (cf. ``_arbitrage_du_calepinage``).
    nb_panneaux, kwc = _arbitrage_du_calepinage(
        layout, nb_panneaux, kwc, company=company)

    # Panel wattage: prefer an explicit hint, else derive from kWc / panels.
    watt = layout.get('panelWatt') or layout.get('watt')
    if not watt and nb_panneaux and kwc:
        watt = int(round(kwc * 1000 / nb_panneaux / 10) * 10)
    if not watt and kwc:
        watt = 550

    # Scenario: 'avec_batterie' / 'hybride' → hybrid inverter + battery;
    # anything else → réseau (grid-tie). Default réseau (residential injection).
    scenario = (layout.get('scenario') or '').lower()
    wants_battery = ('batterie' in scenario or 'hybride' in scenario
                     or bool(layout.get('battery')))

    # PVKIT — le KIT COMPLET du simulateur (structures, socles, accessoires,
    # tableau de protection, installation, transport…), plus le squelette
    # panneau + onduleur ± batterie d'hier : voir ``composition_residentielle``.
    # Un composant absent (ou non tarifé) du catalogue est simplement sauté.
    kwc_composition = kwc or (nb_panneaux * float(watt or 550) / 1000.0)

    # QJ21 / FG248 — le layout RANGÉ (avec sa géométrie par pan déjà processée)
    # et l'étude que ce chemin APPORTE, par LE MÊME lecteur que le devis
    # automatique (cf. ``_calepinage_range``).
    stored_layout, etude_initiale = _calepinage_range(layout, toiture, kwc)

    # ── QJR95 — LE PIPELINE, DANS SON ORDRE UNIQUE ─────────────────────────
    # La cible est SOUVERAINE : elle vient du toit que le commercial a dessiné,
    # et l'étape 2 ne redimensionne donc rien. Le scénario du layout est dit
    # dans le SEUL vocabulaire du pipeline — ``deux_options`` l'emporte, comme
    # le faisait déjà la composition (où ``avec_batterie`` n'a aucun effet dès
    # que la forme est à deux options). PVCOMPAT (``phase``), QJR80
    # (``mppt_paires`` / ``structure_type``) et L-2OPT (``dimensionnement_avec``)
    # sont transmis par les mêmes champs que les quatre autres origines.
    resultat = appliquer(None, IntentionDevis(
        origine=ORIGINE_CALEPINAGE,
        company=company,
        user=user,
        lead=lead,
        client=client,
        mode_installation=Devis.ModeInstallation.RESIDENTIEL,
        cible=CibleDevis(
            nb_panneaux=nb_panneaux,
            panel_watt=watt,
            kwc=kwc_composition,
            source='calepinage',
            dimensionnement_avec=dimensionnement_avec),
        scenario=(COMPOSITION_LES_DEUX if deux_options
                  else (COMPOSITION_AVEC if wants_battery
                        else COMPOSITION_SANS)),
        layout=stored_layout,
        etude_initiale=etude_initiale or None,
        taux_tva=taux_tva,
        remise_globale=remise_globale,
        structure_type=structure_type,
        mppt_paires=mppt_paires,
        phase=phase,
    ))
    devis = resultat['devis']
    line_specs = resultat['composition']
    avertissements = resultat['avertissements']

    # U3 — le canal de l'appelant, rempli sur place comme avant. Il porte en
    # plus, désormais, ce que l'ÉCRIVAIN de lignes a refusé de faire (QJR83,
    # forfaits au panneau) : la composition n'était que la moitié des choses
    # qu'un commercial doit apprendre.
    if journal is not None:
        journal['marques_manquantes'] = list(
            getattr(line_specs, 'marques_manquantes', ()) or ())
        journal['avertissements'] = list(avertissements or ())
        journal['nb_panneaux'] = getattr(line_specs, 'nb_panneaux', 0)
        journal['kwc_reel'] = getattr(line_specs, 'kwc_reel', 0.0)
    elif avertissements:
        # Sans canal fourni, la composition journalisait elle-même ses refus.
        # Le pipeline, lui, les COLLECTE toujours : on les journalise ici
        # plutôt que de les laisser dans une liste que personne ne lit.
        for message in avertissements:
            logger.warning('Q3: devis depuis layout — %s', message)

    logger.info(
        'Q3/QJ21: devis %s built from layout (%d lignes, %.2f kWc, %d pans, company %s)',
        devis.reference, len(line_specs or ()), kwc,
        len(toiture.get('pans', [])) if toiture else 0,
        getattr(company, 'id', '?'))
    return devis


#: U3 — les trois scénarios batterie qu'un appelant peut demander POUR CE
#: DEVIS-LÀ, sans jamais réécrire la fiche du lead.
SCENARIOS_DEMANDABLES = ('sans', 'avec', 'les_deux')


def composer_devis_residentiel(*, company, kwc=None, nb_panneaux=0,
                               panel_watt=_AUTO_PANEL_WATT, scenario=None,
                               structure_type='acier',
                               taux_tva=Decimal('20'), mppt_paires=1,
                               gamme_nom_devis=None, phase=None,
                               dimensionnement_avec=None):
    """U3 — LE DRY-RUN : compose sans RIEN créer, et rend le résultat en clair.

    C'est la moitié « à blanc » de la source de vérité : le même catalogue, la
    même fonction pure, les mêmes règles de gamme que ``build_devis_auto`` —
    mais aucune écriture, aucun devis, aucun statut. L'écran générateur s'en
    sert pour PRÉREMPLIR ses lignes éditables au lieu de recomposer de son
    côté ; c'est ce qui fait qu'il n'existe plus « deux sortes de devis ».

    ``kwc`` OU ``nb_panneaux`` suffit : l'un se déduit de l'autre à
    ``panel_watt``. Company-scopé (le catalogue d'une autre société ne fuite
    jamais). Rend un dict SÉRIALISABLE — la forme figée dans
    ``contract_samples/composition_residentielle.json``.

    ``dimensionnement_avec`` (L-2OPT, optionnel) — l'optimum de l'axe AVEC
    BATTERIE (``{'nb_panneaux', 'kwc', 'batterie_kwh'}``), quand le moteur
    calibré en désigne un DIFFÉRENT de l'optimum sans stockage : le dry-run
    compose alors la même FUSION que la création (lignes variantées), sans quoi
    l'aperçu et le devis ne parleraient pas du même kit. ``None`` (LE DÉFAUT)
    ⇒ dry-run strictement inchangé, et chaque ligne rendue porte
    ``variante: ''``.
    """
    kwp = float(kwc or 0)
    nb_force = int(nb_panneaux or 0)
    watt = float(panel_watt or 0) or float(_AUTO_PANEL_WATT)
    if kwp <= 0 and nb_force > 0:
        kwp = nb_force * watt / 1000.0

    demande = (scenario or '').strip().lower()
    if demande and demande not in SCENARIOS_DEMANDABLES:
        raise AutoDevisError(
            'Scénario inconnu « %s » — attendu : %s.'
            % (scenario, ', '.join(SCENARIOS_DEMANDABLES)),
            field='scenario')
    # Même défaut que le devis auto (U2) : sans consigne, on propose LES DEUX.
    avec_batterie = demande == 'avec'
    deux_options = demande not in ('avec', 'sans')

    # ── QJR82 — L'ÉTAPE `verifier` VUE PAR L'ÉCRAN GÉNÉRATEUR ──────────────
    # L'écran PRÉREMPLIT ses lignes avec ce dry-run : il doit lire les MÊMES
    # phrases françaises que le calepinage 3D oppose, sinon le commercial
    # découvre le trou de catalogue à la génération du PDF. Ici c'est un
    # AVERTISSEMENT et non un refus — le dry-run n'écrit rien, et le commercial
    # reste libre de composer à la main ce que le catalogue ne sert pas.
    avertissements = list(verifier(IntentionComposition(
        company=company, nb_panneaux=nb_force, kwc=kwp,
        scenario=(COMPOSITION_LES_DEUX if deux_options
                  else (COMPOSITION_AVEC if avec_batterie
                        else COMPOSITION_SANS)),
        gamme_nom_devis=gamme_nom_devis)) or ())
    # ── QJR80 — LA MÊME ÉTAPE `composer` QUE LA CRÉATION ────────────────────
    # « Miroir EXACT de ``build_devis_from_layout`` » n'est plus une intention
    # écrite en commentaire : les deux chemins remplissent LE MÊME
    # ``IntentionComposition`` et appellent LA MÊME fonction. Un paramètre ne
    # peut plus être transmis d'un côté et oublié de l'autre.
    lignes = composer(IntentionComposition(
        company=company,
        kwc=kwp,
        nb_panneaux=nb_force,
        panel_watt=watt,
        scenario=(COMPOSITION_LES_DEUX if deux_options
                  else (COMPOSITION_AVEC if avec_batterie
                        else COMPOSITION_SANS)),
        structure_type=structure_type,
        taux_tva=taux_tva,
        mppt_paires=mppt_paires,
        # PVCOMPAT — le DRY-RUN doit voir la MÊME contrainte de raccordement
        # que la construction, sinon l'aperçu montrerait un onduleur que le
        # devis ne composerait pas.
        phase=phase,
        gamme_nom_devis=gamme_nom_devis,
        dimensionnement_avec=dimensionnement_avec,
        avertissements=avertissements,
    ))

    roles = list(getattr(lignes, 'roles', ()) or ())
    facteur = Decimal('1') + (Decimal(str(taux_tva or 20)) / Decimal('100'))
    rendu = []
    for index, ligne in enumerate(lignes):
        # Le TTC est DÉRIVÉ du HT stocké, jamais l'inverse : l'écran saisit en
        # TTC mais la base fait foi en HT (même aller-retour qu'`htFromTtc`).
        ttc = (Decimal(ligne.prix_unitaire) * facteur).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP)
        rendu.append({
            'ordre': index,
            'role': roles[index] if index < len(roles) else None,
            'produit': getattr(ligne.produit, 'id', None),
            'designation': ligne.designation,
            'quantite': int(ligne.quantite),
            'prix_unitaire_ht': str(Decimal(ligne.prix_unitaire)),
            'prix_unitaire_ttc': str(ttc),
            'taux_tva': str(Decimal(str(taux_tva or 20))),
            # L-2OPT — '' sur toute composition mono-optimum (le cas de tous
            # les aperçus d'hier) : la clé est ADDITIVE, jamais absente.
            'variante': getattr(ligne, 'variante', '') or '',
        })

    return {
        'lignes': rendu,
        'scenario': (SCENARIO_LES_DEUX if deux_options
                     else (SCENARIO_AVEC_BATTERIE if avec_batterie
                           else SCENARIO_SANS_BATTERIE)),
        'nb_panneaux': getattr(lignes, 'nb_panneaux', 0),
        'panel_watt': getattr(lignes, 'panel_watt_reel', watt),
        'kwc_reel': getattr(lignes, 'kwc_reel', 0.0),
        'blocs': getattr(lignes, 'blocs', 1),
        # L-2OPT — l'option « avec » quand elle a son PROPRE champ PV. Sur une
        # composition mono-optimum : ``variantes`` False et les deux valeurs
        # recopient l'option unique — aucun appelant ne peut lire un trou.
        'variantes': bool(getattr(lignes, 'variantes', False)),
        'nb_panneaux_avec': (getattr(lignes, 'nb_panneaux_avec', 0)
                             or getattr(lignes, 'nb_panneaux', 0)),
        'kwc_reel_avec': (getattr(lignes, 'kwc_reel_avec', 0.0)
                          or getattr(lignes, 'kwc_reel', 0.0)),
        'avertissements': list(avertissements),
        'marques_manquantes': [
            {**m, 'libelle_role': _libelle_role(m.get('role'))}
            for m in (getattr(lignes, 'marques_manquantes', ()) or ())
        ],
    }


def build_devis_auto(*, lead, user, company, taux_tva=Decimal('20'),
                     remise_globale=Decimal('0'), target_kwc=None,
                     scenario=None, etude_extra=None, plafond_toit=None,
                     journal_auto=None, origine=None):
    """Crée un devis RÉSIDENTIEL automatiquement dimensionné depuis la fiche lead.

    Dimensionne le champ PV par le MOTEUR HORAIRE (ordre fondateur du
    29/08/2026 : « ALL sizing should go through the new sizing tool ») — sauf
    si une PUISSANCE est demandée (``target_kwc``, sinon la taille souhaitée du
    lead), auquel cas cette puissance est souveraine. Puis compose PAR DÉFAUT
    la forme DEUX OPTIONS
    (« sans batterie » ET « avec batterie » — U2 ; un ``batterie_souhaitee``
    explicite du lead, « avec » ou « sans », reste souverain et compose cette
    option-là seule) et confie la création à ``pipeline.appliquer``
    (sélection catalogue, numérotation anti-collision, devis ``brouillon``). Lève
    ``AutoDevisError`` (→ 422) si le marché n'est pas résidentiel ou si aucune
    donnée de dimensionnement n'est exploitable — l'agent demande alors la donnée
    plutôt que de produire un devis vide. Ne change aucun statut (règle #4).

    ``origine`` (QJR96) — laquelle des deux origines SANS COMMERCIAL DANS LA
    BOUCLE demande ce devis : ``'auto'`` (LE DÉFAUT — le bouton « devis
    automatique » de la fiche lead) ou ``'tunnel'`` (le webhook du site, cf.
    :func:`creer_devis_automatique_depuis_lead`). Elle NE DÉCIDE AUCUNE LIGNE :
    les deux traversent le même pipeline, avec les mêmes entrées et le même
    composeur — elle NOMME seulement d'où vient la demande.

    Trois réglages POUR CE DEVIS-LÀ (U3), qui ne réécrivent JAMAIS la fiche du
    lead — c'est un choix ponctuel du commercial, pas une correction du lead :

    * ``target_kwc`` — puissance cible demandée (EZ5) ; passe devant la taille
      souhaitée du lead ET devant le dimensionnement du moteur.
    * ``scenario`` — ``'sans'`` / ``'avec'`` / ``'les_deux'`` ; passe devant le
      ``batterie_souhaitee`` du lead. Absent : c'est le lead qui décide, et son
      silence vaut « les deux » (U2).
    * ``etude_extra`` — clés d'étude à FUSIONNER dans ``etude_params`` (les
      factures mensuelles réelles du contrat PACT10, par exemple). Elles
      complètent ce que la construction a déjà écrit, sans jamais écraser le
      scénario arrêté ci-dessus.

    AUTO-PIPELINE (26/08/2026) — deux paramètres de plus, tous deux OPTIONNELS
    et sans effet quand ils sont absents (l'endpoint ``/devis/auto/`` est donc
    inchangé) :

    * ``plafond_toit`` — borne PHYSIQUE dure en panneaux (cf.
      ``plafond_physique_du_contour``). Elle ne peut que RÉDUIRE : jamais une
      cible relevée, jamais un chiffre ajouté au devis.
    * ``journal_auto`` — dict que l'appelant fournit pour recevoir ce qui s'est
      décidé sans lui (``plafond_applique``, ``panneaux_avant_plafond``,
      ``contour_client``), afin de pouvoir l'écrire NOIR SUR BLANC dans
      l'historique du lead. Rien n'y est écrit s'il n'est pas fourni.

    Et, quand le lead porte un tracé de toit, le layout du devis embarque
    désormais ce tracé comme VRAIE zone de calepinage
    (``zone_toit_depuis_contour``) : l'écran 3D ouvre sur le toit du client,
    déjà pavé, au lieu d'une carte vierge.
    """
    marche = (getattr(lead, 'type_installation', '') or '').lower()
    if marche and marche != 'residentiel':
        raise AutoDevisError(
            "L'auto-devis ne gère que le résidentiel pour l'instant. Pour "
            "l'industriel/commercial ou l'agricole, utilisez l'écran générateur "
            "de devis.",
            field='type_installation')

    taille_kwc = getattr(lead, 'taille_souhaitee_kwc', None)
    # U3/EZ5 — une cible demandée pour CE devis passe devant les deux données
    # du lead, sans les réécrire.
    cible = None
    if target_kwc not in (None, ''):
        from decimal import InvalidOperation
        try:
            cible = Decimal(str(target_kwc))
        except (InvalidOperation, TypeError, ValueError):
            raise AutoDevisError(
                'Puissance cible invalide.', field='target_kwc')
        if cible <= 0:
            raise AutoDevisError(
                'La puissance cible doit être supérieure à zéro.',
                field='target_kwc')
    # ── ORDRE FONDATEUR (29/08/2026) — TOUT PASSE PAR LE MOTEUR ─────────────
    # « why do i bloody have the 900dh path — all sizing should go through the
    # new sizing tool, and i said ALL sizing ».
    #
    # DEUX chemins, et deux seulement :
    #
    #   1. UNE PUISSANCE EST DEMANDÉE — ``target_kwc`` pour ce devis, sinon la
    #      ``taille_souhaitee_kwc`` de la fiche : elle est SOUVERAINE (le
    #      commercial sait ce qu'il vend). Simple conversion kWc → panneaux.
    #   2. SINON — le MOTEUR HORAIRE dimensionne, dès qu'une donnée de
    #      consommation existe (la facture d'hiver suffit : elle est inversée
    #      au barème ONEE réel, la forme 24 h vient de la silhouette de repli
    #      documentée). Il n'y a PLUS de troisième chemin : la règle des
    #      900 DH/mois ne décide plus aucun devis. Si le moteur ne peut pas
    #      dimensionner, on REFUSE en nommant la donnée manquante — jamais un
    #      repli silencieux qui donnerait au client une taille issue d'une
    #      autre règle que celle affichée sur sa proposition.
    panneaux = 0
    # Le wattage du panneau doit être CELUI SUR LEQUEL LE BALAYAGE A DÉCIDÉ :
    # dimensionner sur un panneau de 550 Wc puis composer à 710 Wc livrerait
    # une autre puissance que celle qui a été évaluée.
    watt_dimensionnement = _AUTO_PANEL_WATT
    # L-2OPT — ce que le moteur recommande POUR L'AXE AVEC BATTERIE. ``None``
    # sur le chemin souverain : une puissance demandée par le commercial vaut
    # pour les deux options.
    optimum_avec = None
    taille_demandee = cible if cible is not None else taille_kwc
    # Une taille NULLE ou illisible sur la fiche ne « demande » rien : elle
    # laisse la main au moteur plutôt que de refuser un lead parfaitement
    # dimensionnable (``target_kwc``, lui, a déjà été validé plus haut).
    if taille_demandee not in (None, ''):
        panneaux = _residential_panel_count(taille_kwc=taille_demandee)
    if panneaux > 0:
        source_dimensionnement = 'taille_demandee'
    else:
        panneaux, watt_retenu, source_dimensionnement, optimum_avec = (
            _panneaux_dimensionnement_horaire(
                lead=lead, company=company,
                phase=phase_client_pour_dimensionnement(lead)))
        if panneaux <= 0:
            raise _refus_dimensionnement(source_dimensionnement)
        if watt_retenu:
            watt_dimensionnement = watt_retenu

    kwc = round(panneaux * watt_dimensionnement / 1000, 2)
    # ── U2 (fondateur 20/08/2026) — LE DÉFAUT EST « LES DEUX OPTIONS » ──────
    # « le devis auto sort SANS batterie alors que le calepinage 3D sort AVEC ;
    # le DÉFAUT doit être le devis avec LES DEUX options ». Le devis auto ne
    # choisissait à la place du client que parce que le lead ne disait rien :
    # un lead SANS préférence de batterie repartait en « réseau », donc sans
    # stockage ni onduleur hybride, et le client ne voyait jamais l'option.
    # Désormais le silence du lead veut dire « propose les deux » — c'est la
    # forme que la proposition résidentielle sait déjà rendre.
    #
    # Un choix EXPLICITE du lead reste souverain : « avec » compose l'hybride
    # + batterie seuls, « sans » compose le réseau seul. On ne repropose pas
    # une option que le client a déjà écartée.
    # U3 — un scénario demandé POUR CE DEVIS passe devant la fiche du lead.
    demande = (scenario or '').strip().lower()
    if demande and demande not in SCENARIOS_DEMANDABLES:
        raise AutoDevisError(
            'Scénario inconnu « %s » — attendu : %s.'
            % (scenario, ', '.join(SCENARIOS_DEMANDABLES)),
            field='scenario')
    choix_batterie = (
        demande if demande
        else (getattr(lead, 'batterie_souhaitee', '') or '').strip())
    wants_battery = choix_batterie == 'avec'
    deux_options = choix_batterie not in ('avec', 'sans')

    # ── L-2OPT — L'AXE « AVEC BATTERIE » A SON PROPRE OPTIMUM ───────────────
    # Le moteur calibré désigne DEUX gagnants (DIM2) : ``recommandation`` au
    # meilleur payback SANS stockage, et ``recommandation_avec`` au meilleur
    # payback AVEC — issus d'un balayage CONJOINT champ × stockage. Le second
    # n'alimentait aucune ligne de devis.
    #
    #   · scénario MONO « avec » — le devis ne propose QUE le stockage : il
    #     doit donc être dimensionné sur l'optimum AVEC, pas sur celui d'un
    #     champ sans batterie que personne n'achètera. C'est tout l'objet de ce
    #     chantier ;
    #   · scénario « les deux » — les deux champs partent au devis, fusionnés
    #     en lignes variantées (cf. ``composition_deux_optimiseurs``) ;
    #   · scénario MONO « sans » — RIEN ne change : l'optimum « avec » ne le
    #     concerne pas.
    if wants_battery and optimum_avec:
        panneaux = int(optimum_avec['nb_panneaux'])
        watt_avec = optimum_avec.get('panel_watt')
        if watt_avec:
            watt_dimensionnement = float(watt_avec)
        kwc = round(panneaux * watt_dimensionnement / 1000, 2)
        source_dimensionnement = 'moteur_horaire_avec'
    elif not deux_options:
        # Mono « sans » : l'optimum « avec » n'a rien à faire dans ce devis.
        optimum_avec = None

    # ── AUTO-PIPELINE — LE PLAFOND PHYSIQUE DU TOIT, S'IL EST CONNU ────────
    # Il ne peut que RÉDUIRE, et il ne mord que sur une cible physiquement
    # impossible (surface du contour ÷ surface d'un panneau — voir
    # ``plafond_physique_du_contour`` pour pourquoi c'est le seul plafond
    # honnête à prononcer ici). Le plafond de CALEPINAGE, lui, reste celui du
    # moteur qui dessine, à l'écran.
    if plafond_toit:
        try:
            plafond = int(plafond_toit)
        except (TypeError, ValueError):
            plafond = 0
        if plafond > 0 and panneaux > plafond:
            logger.warning(
                'Auto-devis (lead %s): cible de %d panneaux ramenée à %d — '
                'le tracé du client ne peut pas en porter davantage.',
                getattr(lead, 'pk', '?'), panneaux, plafond)
            if isinstance(journal_auto, dict):
                journal_auto['panneaux_avant_plafond'] = panneaux
                journal_auto['plafond_applique'] = plafond
            panneaux = plafond
            kwc = round(panneaux * watt_dimensionnement / 1000, 2)
            if optimum_avec and int(optimum_avec.get('nb_panneaux') or 0) > plafond:
                # L'axe « avec batterie » subit le MÊME toit : sans cela le
                # devis proposerait une option qui ne rentre pas.
                optimum_avec = dict(optimum_avec)
                optimum_avec['nb_panneaux'] = plafond
                watt_avec = optimum_avec.get('panel_watt') or watt_dimensionnement
                optimum_avec['kwc'] = round(plafond * float(watt_avec) / 1000, 2)

    layout = {
        'result': {'panels': panneaux, 'kwc': kwc},
        'panelWatt': watt_dimensionnement,
        'scenario': 'avec_batterie' if wants_battery else 'reseau',
    }
    # ── AUTO-PIPELINE — LE TRACÉ DU CLIENT DEVIENT LA ZONE DU CALEPINAGE ───
    # Sans ces clés, le layout d'un devis automatique ne décrit AUCUNE
    # géométrie : l'écran 3D s'ouvrait sur une carte vierge et le commercial
    # devait re-tracer le toit pour voir un seul panneau, alors que le client
    # l'avait déjà dessiné. Avec elles, l'écran ouvre sur le contour du client
    # et le pave immédiatement. Absent de tracé → dict vide → comportement
    # STRICTEMENT inchangé.
    zone_client = zone_toit_depuis_contour(lead, panneaux=panneaux, kwc=kwc)
    if zone_client:
        layout.update(zone_client)
        if isinstance(journal_auto, dict):
            journal_auto['contour_client'] = len(zone_client['outline'])
    # ── U3 — GARDE MARQUE ÉPINGLÉE, portée côté SERVEUR ────────────────────
    # Cette garde ne vivait que dans `createAutoQuote` : le chemin backend en
    # était dépourvu. Une marque réglée dans Paramètres → Gammes mais absente
    # du stock VIDE le vivier de son rôle — le devis serait parti sans
    # panneaux, à un prix effondré.
    #
    # On le découvre par un DRY-RUN : exactement la composition qui sera
    # créée, sans aucune écriture. Refuser AVANT de créer vaut mieux que créer
    # puis effacer — un devis effacé rendrait sa référence au compteur, et le
    # numéro suivant la reprendrait.
    # ── PVCOMPAT — LE RACCORDEMENT DU CLIENT DESCEND JUSQU'À LA COMPOSITION ──
    # ``crm.Lead.raccordement`` ('monophase'/'triphase'/'inconnu') existe depuis
    # l'assistant du site et n'était lu NULLE PART côté composition : un client
    # monophasé pouvait se voir composer un onduleur triphasé, impossible à
    # raccorder chez lui. « inconnu » (ou vide) laisse la composition décider
    # exactement comme avant. Le DRY-RUN le reçoit aussi, sinon l'aperçu et le
    # devis ne parleraient pas du même onduleur.
    from apps.ventes.compatibilites import normaliser_phase
    phase_client = normaliser_phase(getattr(lead, 'raccordement', None))

    # ── QJR82 — L'ÉTAPE `verifier`, LA MÊME QUE LE CHEMIN 3D ────────────────
    # La pré-vérification n'était câblée que sur le calepinage 3D : le devis
    # AUTOMATIQUE et le TUNNEL créaient des devis sans elle, et découvraient à
    # la génération du PDF qu'une moitié de la composition n'existait pas au
    # catalogue. C'est la MÊME étape et les MÊMES phrases françaises : un lead
    # refusé et un devis refusé le sont désormais pour la même raison, dite de
    # la même façon (c'est aussi ce que la note d'abstention du tunnel recopie,
    # cf. ``corps_note_refus_auto_devis``).
    #
    # ELLE EST PRONONCÉE AVANT TOUTE ÉCRITURE : refuser vaut mieux que créer
    # puis effacer — un devis effacé rendrait sa référence au compteur.
    refus_composition = verifier(IntentionComposition(
        company=company, nb_panneaux=panneaux, kwc=kwc,
        scenario=(COMPOSITION_LES_DEUX if deux_options
                  else (COMPOSITION_AVEC if wants_battery
                        else COMPOSITION_SANS))))
    if refus_composition:
        raise AutoDevisError(refus_composition[0], field='composition')

    apercu = composer_devis_residentiel(
        company=company, nb_panneaux=panneaux,
        panel_watt=watt_dimensionnement,
        scenario=choix_batterie or 'les_deux', taux_tva=taux_tva,
        phase=phase_client,
        # L-2OPT — le DRY-RUN voit EXACTEMENT la composition qui sera créée,
        # fusion comprise : sans cela il contrôlerait les marques d'un kit qui
        # n'est pas celui du devis.
        dimensionnement_avec=optimum_avec)
    if apercu['marques_manquantes']:
        detail = ', '.join(
            '%s (%s)' % (m.get('marque'), m.get('libelle_role'))
            for m in apercu['marques_manquantes'])
        raise AutoDevisError(
            'Marque épinglée introuvable au stock : %s. Ajoutez le produit ou '
            'changez la marque dans Paramètres → Gammes.' % detail,
            field='marques')

    # ── QJR96 (M5, bascule 4/5) — LE PIPELINE, DANS SON ORDRE UNIQUE ────────
    # Ce chemin RECONSTRUISAIT un layout pour le repasser à
    # ``build_devis_from_layout``, qui le relisait aussitôt pour en ressortir le
    # compte, le wattage et le scénario que cette fonction venait d'arrêter :
    # un aller-retour par une sérialisation intermédiaire, sur le seul chemin où
    # AUCUN commercial n'est dans la boucle pour rattraper un écart. Ce corps est
    # SUPPRIMÉ. La cible est passée TELLE QUELLE au pipeline, qui compose par LE
    # MÊME composeur que l'écran, écrit ses lignes par L'ÉCRIVAIN UNIQUE et
    # rafraîchit les quatre études sur l'instance relue.
    #
    # LE LAYOUT RESTE, et il est lu par LE MÊME lecteur (``_calepinage_range``)
    # que le calepinage 3D : c'est une donnée RÉELLE — le tracé du client — que
    # l'écran 3D rouvre, pas un intermédiaire de calcul.
    #
    # LA RÈGLE SOUVERAINE EST CONSERVÉE TELLE QUELLE : une puissance DEMANDÉE
    # (``target_kwc``, sinon ``lead.taille_souhaitee_kwc``) gagne sur le moteur,
    # et elle ne réécrit JAMAIS la fiche du lead. Elle est désormais portée par
    # la CIBLE de l'étape 2 — ``decider_taille`` rend une cible fournie telle
    # quelle et n'interroge alors aucun moteur — et par rien d'autre. Elle n'est
    # PAS posée dans ``Devis.overrides`` : les chemins ``taille.*`` du registre
    # (D12) portent des déclarations HUMAINES que ``puissance_kwc_du_devis``
    # fait gagner sur les lignes ; un chemin automatique qui en poserait une
    # signerait d'une main humaine un chiffre que personne n'a tapé, et ferait
    # publier la puissance DEMANDÉE là où QJR63 a établi que seules les LIGNES
    # font foi.
    from apps.ventes.models import Devis

    toiture = extract_roof_config(layout)
    panneaux, kwc = _arbitrage_du_calepinage(
        layout, panneaux, kwc, company=company)
    layout_range, etude_initiale = _calepinage_range(layout, toiture, kwc)

    resultat = appliquer(None, IntentionDevis(
        origine=origine or ORIGINE_AUTO,
        company=company,
        user=user,
        lead=lead,
        mode_installation=Devis.ModeInstallation.RESIDENTIEL,
        # QJR42 — LES ENTRÉES DU MOTEUR, LUES UNE FOIS. Sans elles l'étape 1 les
        # relirait pour son compte : deux lectures de la même fiche, donc deux
        # occasions de dimensionner un même lead différemment.
        entrees=entrees_depuis_lead(lead, company),
        cible=CibleDevis(
            nb_panneaux=panneaux,
            panel_watt=watt_dimensionnement,
            kwc=kwc,
            source=source_dimensionnement,
            dimensionnement_avec=optimum_avec),
        scenario=(COMPOSITION_LES_DEUX if deux_options
                  else (COMPOSITION_AVEC if wants_battery
                        else COMPOSITION_SANS)),
        layout=layout_range,
        etude_initiale=etude_initiale or None,
        taux_tva=taux_tva,
        remise_globale=remise_globale,
        phase=phase_client,
    ))
    devis = resultat['devis']
    # U3 — ce que la composition ET l'écrivain de lignes ont REFUSÉ de faire
    # (vivier batterie vide, forfait au panneau non re-tarifé…). Sur un chemin
    # sans commercial dans la boucle, le journal serveur est le seul lecteur.
    for avertissement in resultat['avertissements'] or []:
        logger.warning('Auto-devis %s: %s', devis.reference, avertissement)

    # QJR63 — LE kWc a été posé par son propriétaire à l'étape 8 (``finaliser``),
    # sur les lignes RÉELLEMENT composées : ni ``target_kwc``, ni
    # ``lead.taille_souhaitee_kwc``, qui sont des DEMANDES et non ce que le
    # catalogue a su servir (l'arrondi au palier et le plafond de toit peuvent
    # faire atterrir ailleurs). Le second appel que ce corps faisait ici est
    # SUPPRIMÉ : il reposait la même valeur sur la même instance.

    # U3/PACT10 — les clés d'étude apportées par l'appelant (factures
    # mensuelles réelles, consommation annuelle, distributeur) COMPLÈTENT
    # l'étude déjà écrite par la construction.
    if isinstance(etude_extra, dict) and etude_extra:
        # QJR62 — ÉCRIVAIN UNIQUE : la fusion vit dans ``domain.etude_schema``.
        # QJR64 / D12 — LE SCÉNARIO PASSE PAR LE REGISTRE, plus par un cas
        # particulier codé en dur. Le scénario qui fait foi est
        # ``scenario_effectif`` (surcharge déclarée, sinon celui que la
        # construction vient d'arrêter) : un corps de requête ne peut plus
        # l'écraser, et une déclaration humaine survit à tout recalcul aval.
        from apps.ventes.domain.etude_schema import AUTO_DEVIS, ecrire
        _scenario_arrete = scenario_effectif(
            devis, (devis.etude_params or {}).get('scenario'))
        _extra = {cle: valeur for cle, valeur in etude_extra.items()
                  if not (_scenario_arrete and cle == 'scenario')}
        if _scenario_arrete and _scenario_arrete != (
                devis.etude_params or {}).get('scenario'):
            _extra['scenario'] = _scenario_arrete
        if _extra:
            try:
                ecrire(devis, proprietaire=AUTO_DEVIS, **_extra)
            except ValueError as exc:
                # ``etude_extra`` vient du CORPS DE REQUÊTE : un refus du
                # schéma doit sortir en 422 NOMMÉ, jamais en 500.
                raise AutoDevisError(str(exc), field='etude_params')

    # L-1V (incident test16, 27/08/2026) — LES QUATRE ÉTUDES EN UN SEUL GESTE,
    # comme sur les chemins d'écriture du générateur (``atomic``,
    # ``replace-lines``, ``sync-layout``). Ce chemin gardait l'appel CJ2a
    # d'origine (bloc horaire SEUL) : un devis automatique naissait sans
    # ``dimensionnement``, et la page client perdait d'un coup les trois
    # tailles Éco/Recommandé/Max, la tranche tarifaire, le régime batterie,
    # le balayage de stockage et les profils comparatifs — jusqu'à la première
    # édition manuelle (DEV-202608-0033/0034). Posé APRÈS la fusion
    # ``etude_extra`` ci-dessus (les factures réelles nourrissent le
    # dimensionnement), toujours APRÈS la construction (la puissance et le
    # stockage réellement composés), best-effort et non bloquant : un devis
    # reste parfaitement valide sans ses études.
    # QJR47 — ``force=True`` RETIRÉ : le devis vient de NAÎTRE, il ne porte
    # aucun bloc estampillé, donc les quatre études se calculent de toute
    # façon (et la fusion ``etude_extra`` ci-dessus est déjà entrée dans
    # l'empreinte des entrées).
    rafraichir_etudes_du_devis(devis)

    logger.info(
        'Auto-devis %s: %d panneaux, %.2f kWc, batterie=%s, deux_options=%s, '
        'dimensionnement=%s (company %s)',
        devis.reference, panneaux, kwc, wants_battery, deux_options,
        source_dimensionnement, getattr(company, 'id', '?'))
    return devis


def auto_devis_tunnel_actif(company):
    """La société veut-elle des devis automatiques depuis le tunnel ?

    Réglage de société (``parametres.CompanyProfile.devis_auto_depuis_tunnel``),
    ACTIF par défaut — c'est le flux que le fondateur a demandé. Une société
    qui n'a pas encore de profil hérite donc du défaut, jamais d'un « non »
    silencieux ; un profil illisible vaut « non » (on ne crée pas de document
    sur une lecture ratée).
    """
    try:
        from apps.parametres.models import CompanyProfile
        profil = CompanyProfile.objects.filter(company=company).first()
    except Exception:  # noqa: BLE001 — table absente / migration en cours
        logger.warning(
            'Auto-devis: profil de société illisible (company %s) — '
            'création automatique désactivée par prudence.',
            getattr(company, 'pk', '?'))
        return False
    if profil is None:
        return True
    return bool(getattr(profil, 'devis_auto_depuis_tunnel', True))


_MARQUE_AUTO_DEVIS = 'ventes.auto_devis'


def _liberer_marque_auto_devis(company, lead_id):
    """F5 — RELÂCHE la marque d'achèvement d'un lead dont la création a échoué.

    ``dedupe_event`` pose sa ligne AVANT le travail — c'est ce qui lui permet
    de départager deux workers simultanés. Mais laissée en place après un
    échec, cette même ligne devient une porte fermée DÉFINITIVEMENT : un lead
    sans facture aujourd'hui, ou un catalogue momentanément incomplet, et plus
    jamais personne — ni un rejeu, ni un appel manuel du service — ne pourrait
    lui créer son devis automatique. La marque doit donc dire « c'est FAIT »,
    pas « ça a été tenté ».

    Best-effort et silencieuse sur erreur : elle est appelée depuis des
    chemins d'exception, et ne doit jamais masquer l'erreur d'origine.
    """
    try:
        from core.idempotency import ProcessedWebhookEvent
        ProcessedWebhookEvent.objects.filter(
            company=company, source=_MARQUE_AUTO_DEVIS,
            event_id=str(lead_id)).delete()
    except Exception:  # noqa: BLE001 — jamais au-dessus de l'erreur d'origine
        logger.warning(
            'Auto-devis: marque de dédup non relâchée pour le lead %s — un '
            'prochain essai sera refusé.', lead_id, exc_info=True)


def corps_note_refus_auto_devis(exc):
    """Le CORPS de la note d'abstention — pur, testable sans base.

    Il NOMME le motif : le champ que le moteur a trouvé manquant, et le
    message français qu'il oppose déjà au commercial sur l'écran de devis.
    C'est délibérément le MÊME texte des deux côtés : un lead refusé et un
    devis refusé le sont pour la même raison, et la lire deux fois formulée
    autrement ferait croire à deux problèmes.

    Le corps est DÉTERMINISTE (aucune date, aucun compteur) — c'est ce qui
    permet à la garde anti-répétition de reconnaître le même motif d'un rejeu
    à l'autre.
    """
    champ = getattr(exc, 'field', None) or 'donnée manquante'
    message = (str(exc) or '').strip()
    corps = ('Devis automatique NON créé depuis le tunnel — le '
             'dimensionnement s\'abstient (%s).' % champ)
    if message:
        corps += ' Motif : %s' % message
    corps += (' Complétez la fiche puis créez le devis à la main : rien n\'a '
              'été écrit sur ce lead.')
    return corps


def _noter_refus_auto_devis(company, lead_id, lead, exc):
    """Pose la note d'abstention. BEST-EFFORT : ne remonte jamais.

    Un chemin d'observabilité n'a pas le droit de transformer une abstention
    (cas normal) en erreur : l'appelant rend ``None`` dans les deux cas.
    """
    try:
        from apps.crm.services import ajouter_note_lead_si_nouvelle
        ajouter_note_lead_si_nouvelle(
            company=company, lead_id=lead_id,
            user=getattr(lead, 'owner', None),
            body=corps_note_refus_auto_devis(exc))
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'Auto-devis: note d\'abstention non posée sur le lead %s.',
            lead_id, exc_info=True)


def creer_devis_automatique_depuis_lead(*, lead_id, company_id):
    """AUTO-PIPELINE — le devis brouillon d'un lead arrivé du tunnel.

    Rend le ``Devis`` créé, ou ``None`` — et ``None`` n'est JAMAIS une erreur :
    c'est le cas normal quand le lead n'a pas de quoi être chiffré. LES PORTES,
    dans l'ordre, et aucune n'est nouvelle :

    1. **Société / lead lisibles** — lecture cross-app par
       ``crm.selectors.get_company_lead`` (jamais ``crm.models``).
    2. **Réglage de société** — ``auto_devis_tunnel_actif``.
    3. **IDEMPOTENCE — un lead, un devis**, en DEUX gardes distinctes, car
       elles n'attrapent pas la même chose :

       a. une lecture « ce lead porte-t-il déjà un devis ? » — elle couvre le
          cas courant (webhook re-livré plus tard, tâche rejouée après coup,
          devis déjà saisi à la main par un commercial) ;
       b. une MARQUE D'ACHÈVEMENT en base
          (``core.idempotency.dedupe_event``, contrainte d'unicité sur
          ``(company, source, event_id)``) — elle seule départage deux
          exécutions SIMULTANÉES, que la lecture (a) laisserait passer
          ensemble. Il n'y a ici NI transaction englobante, NI
          ``select_for_update`` : c'est la contrainte d'unicité qui arbitre,
          et le perdant de l'insertion abandonne sans rien créer.

       La marque n'est gardée QUE si un devis a réellement été créé : tout
       échec la relâche (voir ``_liberer_marque_auto_devis``), sans quoi un
       lead non chiffrable aujourd'hui — facture manquante, catalogue
       incomplet — resterait définitivement fermé à un appel ultérieur.
    4. **Assez de donnée RÉELLE** — c'est ``build_devis_auto`` qui tranche,
       avec EXACTEMENT les portes qu'il oppose déjà au commercial
       (``AutoDevisError`` : marché non résidentiel, aucune facture d'hiver ni
       taille souhaitée, marque épinglée absente du stock). Un lead incomplet
       ou parasite ne reçoit donc rien du tout, et surtout pas un devis vide.

    Le tracé du client, s'il existe, entre dans le layout du devis
    (``zone_toit_depuis_contour``) et borne physiquement la taille
    (``plafond_physique_du_contour``). Sans tracé : un devis automatique
    ordinaire, sans calepinage — le comportement d'aujourd'hui.
    """
    from django.db import transaction

    from apps.crm.selectors import get_company_lead
    from authentication.models import Company
    from core.idempotency import dedupe_event

    from ..models import Devis

    company = Company.objects.filter(pk=company_id).first()
    if company is None:
        return None
    if not auto_devis_tunnel_actif(company):
        logger.info(
            'Auto-devis: désactivé pour la société %s — lead %s non chiffré.',
            company_id, lead_id)
        return None

    lead = get_company_lead(company, lead_id)
    if lead is None:
        return None

    # PORTE 3a — un lead qui porte déjà un devis (automatique OU saisi à la
    # main) n'en reçoit jamais un second.
    if Devis.objects.filter(company=company, lead=lead).exists():
        logger.info(
            'Auto-devis: le lead %s porte déjà un devis — rien créé.', lead_id)
        return None

    # PORTE 3b — LA COURSE. Deux livraisons simultanées du même webhook, ou un
    # rejeu Celery concurrent (``acks_late``), peuvent franchir la porte 3a
    # ensemble : seule une contrainte d'unicité en base les départage. C'est
    # EXACTEMENT la primitive que le webhook utilise déjà pour ses propres
    # rejeux (``core.idempotency.dedupe_event``) — on ne s'en réinvente pas une
    # seconde. Perdant = on ne crée rien, en silence : l'autre worker s'en
    # charge.
    if not dedupe_event(company=company, source=_MARQUE_AUTO_DEVIS,
                        event_id=str(lead_id)):
        logger.info(
            'Auto-devis: création déjà en cours/faite pour le lead %s '
            '(dédup) — rien créé.', lead_id)
        return None

    journal_auto = {}
    # Le ``try`` couvre TOUT ce qui suit la pose de la marque — y compris les
    # lectures catalogue/géométrie — et il ENVELOPPE la transaction (et non
    # l'inverse) : un refus de dimensionnement doit défaire ce que la
    # construction aurait pu commencer, jamais laisser un devis à moitié écrit.
    # F5 — chaque sortie en échec RELÂCHE la marque : elle atteste d'un devis
    # CRÉÉ, jamais d'une tentative.
    try:
        # Lectures pures (catalogue + géométrie du tracé) — hors transaction.
        produit_panneau, _societe = _panneau_pour_calepinage(
            {'panelWatt': _AUTO_PANEL_WATT}, company=company, devis=None)
        plafond = plafond_physique_du_contour(
            contour_client_lnglat(lead), produit_panneau)
        with transaction.atomic():
            devis = build_devis_auto(
                lead=lead,
                # Le devis est attribué au commercial qui possède le lead
                # quand il y en a un, à personne sinon — jamais à un
                # utilisateur inventé pour la circonstance.
                user=getattr(lead, 'owner', None),
                company=company, plafond_toit=plafond,
                journal_auto=journal_auto,
                # QJR96 — L'ORIGINE DÉCLARÉE AU PIPELINE. Le tunnel n'est pas un
                # autre moteur : c'est le MÊME geste, demandé par le webhook du
                # site au lieu du bouton d'un commercial. Elle ne décide aucune
                # ligne — elle NOMME la demande, pour le journal et pour les
                # propriétaires d'étude.
                origine=ORIGINE_TUNNEL)
    except AutoDevisError as exc:
        _liberer_marque_auto_devis(company, lead_id)
        logger.info(
            'Auto-devis: lead %s non chiffrable (%s) — aucun devis créé.',
            lead_id, exc.field or 'donnée manquante')
        # ── F6 (revue Fable, 29/08/2026) — UN REFUS SE VOIT SUR LE LEAD ──
        #
        # Le refus ne laissait qu'une ligne de journal serveur. Côté
        # commercial, le lead arrivait NU, sans devis et sans un mot — alors
        # que la veille les mêmes leads en recevaient un. Le silence se lisait
        # comme une panne ; c'est une ABSTENTION, et elle a un motif nommable.
        #
        # UNE FOIS PAR MOTIF, JAMAIS PAR REJEU : le refus relâche la marque de
        # dédup (une donnée manquante aujourd'hui ne ferme pas le lead pour
        # toujours), si bien qu'une re-livraison du webhook rejoue le même
        # refus. ``ajouter_note_lead_si_nouvelle`` (apps.crm.services — la
        # frontière cross-app, jamais ``crm.models``) ne repose pas un corps
        # identique ; un motif DIFFÉRENT, lui, mérite bien sa note.
        _noter_refus_auto_devis(company, lead_id, lead, exc)
        return None
    except Exception:  # noqa: BLE001 — relâcher AVANT de laisser remonter
        _liberer_marque_auto_devis(company, lead_id)
        raise

    # ── LA BOUCLE DE VÉRIFICATION DU COMMERCIAL ───────────────────────────
    # Le devis porte le lead : il apparaît donc DÉJÀ dans la liste des devis et
    # sur la fiche du lead. Ce qui manquait, c'est le REÇU daté qui dit d'où il
    # sort et qu'il attend une relecture. Note d'historique (chatter existant,
    # aucun mécanisme neuf), best-effort : un devis créé ne doit jamais être
    # remis en cause par une note qui échoue.
    corps = (
        'Devis automatique créé depuis le tunnel — à vérifier : %s.'
        % devis.reference)
    if journal_auto.get('contour_client'):
        corps += (
            ' Le calepinage part du tracé du client (%d points) : ouvrez '
            '« Concevoir la toiture (3D) » pour le contrôler.'
            % journal_auto['contour_client'])
    if journal_auto.get('plafond_applique'):
        corps += (
            ' Taille ramenée de %d à %d panneaux : la surface du tracé du '
            'client ne peut physiquement pas en porter davantage.'
            % (journal_auto['panneaux_avant_plafond'],
               journal_auto['plafond_applique']))
    try:
        from apps.crm.services import ajouter_note_lead
        ajouter_note_lead(company=company, lead_id=lead_id,
                          user=getattr(lead, 'owner', None), body=corps)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'Auto-devis %s: note d\'historique échouée sur le lead %s.',
            devis.reference, lead_id, exc_info=True)

    logger.info('Auto-devis %s créé automatiquement pour le lead %s '
                '(company %s).', devis.reference, lead_id, company_id)
    return devis


def planifier_devis_automatique_pour_lead(lead_id, company_id):
    """Met la création du devis automatique EN FILE — jamais en ligne.

    Point d'entrée cross-app : ``apps.crm`` appelle CETTE fonction (règle
    services.py), et rien d'autre de ``ventes``.

    Contrairement à ``planifier_resynchronisation_produit`` (PVSYNC), il n'y a
    ici **aucun repli en ligne**, et c'est délibéré : le webhook du site est
    une surface PUBLIQUE dont le temps de réponse est un engagement, alors que
    la composition + l'étude horaire se comptent en secondes. Un courtier
    injoignable fait donc simplement retomber ce lead-là sur le chemin
    d'aujourd'hui — le commercial crée son devis à la main — ce qui est un
    dégradé acceptable ; un webhook qui met cinq secondes à répondre ne l'est
    pas. L'échec est journalisé, jamais avalé en silence.
    """
    from ..tasks import task_devis_automatique_depuis_lead

    try:
        task_devis_automatique_depuis_lead.apply_async(
            args=[lead_id, company_id], retry=False)
    except Exception as exc:  # noqa: BLE001 — courtier indisponible
        logger.warning(
            'Auto-devis: file Celery indisponible (%s) — le lead %s n\'aura '
            'pas de devis automatique (création manuelle inchangée).',
            exc, lead_id)


# ── QJ16 — Reusable quote presets ────────────────────────────────────────────

def save_devis_as_preset(devis, nom: str, description: str = "", *, user=None):
    """QJ16 — snapshot a Devis into a company-scoped DevisPreset.

    The preset captures the line configuration (designation, quantite,
    prix_unitaire, remise, taux_tva per line, plus taux_tva and remise_globale
    at devis level) as a JSON snapshot.  The company is ALWAYS forced from
    ``devis.company`` — never from user input.

    Price-less lines are excluded at save time (same guard as auto-fill): if a
    line's produit has no sell price, it is still captured in the snapshot so the
    preset is complete, but at apply-time such lines are re-checked and skipped
    if the product is no longer priced.

    Returns the created DevisPreset.
    """
    from apps.ventes.models import DevisPreset

    company = devis.company
    if company is None:
        raise ValueError("save_devis_as_preset: devis has no company")

    def _ds(value):
        # Normalise a Decimal to a clean string (strip trailing zeros):
        # 10.00 -> "10", 10.50 -> "10.5". None stays None.
        if value is None:
            return None
        s = str(value)
        return s.rstrip('0').rstrip('.') if '.' in s else s

    lignes_snapshot = []
    for ligne in devis.lignes.select_related('produit').order_by('id'):
        produit = ligne.produit
        lignes_snapshot.append({
            'produit_id': produit.pk if produit else None,
            'designation': ligne.designation,
            'quantite': _ds(ligne.quantite),
            'prix_unitaire': _ds(ligne.prix_unitaire),
            'remise': _ds(ligne.remise),
            'taux_tva': _ds(ligne.taux_tva),
        })

    preset = DevisPreset.objects.create(
        company=company,
        nom=nom.strip(),
        description=description,
        mode_installation=devis.mode_installation or None,
        taux_tva=devis.taux_tva,
        remise_globale=devis.remise_globale,
        lignes_snapshot=lignes_snapshot,
        etude_params_snapshot=dict(devis.etude_params) if devis.etude_params else None,
        created_by=user,
    )
    logger.info(
        'QJ16: preset "%s" saved (id=%s, company=%s, %d lignes)',
        preset.nom, preset.pk, company.pk, len(lignes_snapshot))
    return preset


def apply_preset_to_devis(preset, devis, *, skip_priceless: bool = True) -> list:
    """QJ16 — apply a DevisPreset to an existing (empty) Devis.

    Creates LigneDevis rows on ``devis`` from the preset snapshot.  The caller
    is responsible for ensuring ``devis`` is brouillon and belongs to the same
    company as the preset (enforced below — cross-company apply is refused).

    ``skip_priceless=True`` (default): lines whose snapshot product no longer
    has a sell price are skipped (same guard as auto-fill — never auto-quote a
    price-less product).  Pass ``skip_priceless=False`` only in tests that need
    to exercise the skipping logic.

    Returns the list of created LigneDevis instances (may be empty if all lines
    are priceless).

    RULE #4: this service only builds lines — it never changes Devis.statut.
    """
    from apps.stock.models import Produit

    if preset.company_id != devis.company_id:
        raise ValueError(
            "apply_preset_to_devis: preset and devis belong to different companies"
        )

    created = []
    for snap in preset.lignes_snapshot:
        produit_id = snap.get('produit_id')
        produit = None
        if produit_id:
            try:
                produit = Produit.objects.get(
                    pk=produit_id, company=devis.company)
            except Produit.DoesNotExist:
                # Product deleted or belongs to another company — try global
                try:
                    produit = Produit.objects.get(
                        pk=produit_id, company__isnull=True)
                except Produit.DoesNotExist:
                    produit = None

        if skip_priceless and produit is not None and not _has_price(produit):
            logger.info(
                'QJ16 apply_preset: skipping priceless product %s ("%s")',
                produit_id, snap.get('designation', ''))
            continue

        taux_snap = snap.get('taux_tva')
        ligne = creer_ligne(
            devis,
            produit=produit,
            designation=snap['designation'],
            quantite=Decimal(str(snap['quantite'])),
            prix_unitaire=Decimal(str(snap['prix_unitaire'])),
            remise=Decimal(str(snap.get('remise', '0'))),
            taux_tva=Decimal(str(taux_snap)) if taux_snap is not None else None,
        )
        created.append(ligne)

    # Apply devis-level settings from preset if the devis is fresh (no lignes yet
    # before this call means we can safely update tva and remise).
    if created:
        devis.taux_tva = preset.taux_tva
        devis.remise_globale = preset.remise_globale
        if preset.mode_installation:
            devis.mode_installation = preset.mode_installation
        if preset.etude_params_snapshot and not devis.etude_params:
            devis.etude_params = dict(preset.etude_params_snapshot)
        devis.save(update_fields=[
            'taux_tva', 'remise_globale', 'mode_installation', 'etude_params'])

    logger.info(
        'QJ16 apply_preset: applied preset "%s" to devis %s (%d lines)',
        preset.nom, getattr(devis, 'reference', devis.pk), len(created))
    return created


# ── XSAV3 — Devis de réparation hors garantie depuis un ticket SAV ───────────

def create_devis_pour_ticket(*, company, user, client_id, lignes, note=None):
    """XSAV3 — Crée un Devis BROUILLON pour un travail SAV non couvert.

    Point d'entrée cross-app (sav → ventes) : ``apps.sav`` appelle CETTE
    fonction plutôt que d'importer ``apps.ventes.models`` directement (règle
    de modularité CLAUDE.md). ``lignes`` est une liste de dicts
    ``{'produit_id': int, 'designation': str, 'quantite': Decimal,
    'prix_unitaire': Decimal}`` — le prix unitaire attendu ici est TOUJOURS le
    prix de VENTE catalogue (``Produit.prix_vente``), jamais ``prix_achat``.

    Référence générée via ``apps.ventes.utils.references`` (jamais count()+1).
    Renvoie le ``Devis`` créé (brouillon, sans lien lead — un ticket SAV n'a
    pas de lead d'origine).
    """
    from ..models import Devis
    from ..utils.references import create_with_reference
    from apps.crm.models import Client

    client = Client.objects.get(pk=client_id, company=company)

    def _create(ref):
        return Devis.objects.create(
            company=company, reference=ref, client=client,
            statut=Devis.Statut.BROUILLON, created_by=user,
            note=note or '',
        )
    devis = create_with_reference(Devis, 'DEV', company, _create)

    for ligne in (lignes or []):
        produit_id = ligne.get('produit_id')
        if not produit_id:
            continue
        creer_ligne(
            devis,
            produit_id=produit_id,
            designation=ligne.get('designation') or '',
            quantite=Decimal(str(ligne.get('quantite') or 1)),
            prix_unitaire=Decimal(str(ligne.get('prix_unitaire') or 0)),
        )
    return devis


# ── ZFSM5 — Devis d'upsell créé sur place depuis l'intervention ────────────
# apps.installations ne peut PAS importer apps.ventes.models directement
# (règle de modularité CLAUDE.md) : cette fonction est son unique porte
# d'entrée pour générer un devis brouillon d'upsell depuis une intervention
# (opportunité vue sur place — 2ᵉ site, batterie, extension) — DISTINCT de
# XFSM18 (réserve → devis de RÉPARATION, reprise d'un défaut).

def create_devis_upsell_from_intervention(*, intervention, user):
    """ZFSM5 — crée un DEVIS brouillon d'upsell à partir d'une intervention,
    pour le cas où le technicien voit une opportunité sur place. Le client
    est celui du CHANTIER (`intervention.installation.client`, déjà résolu —
    pattern `create_devis_from_reserve`, aucune re-résolution lead
    nécessaire). La description est pré-remplie depuis le chantier/type
    d'intervention ; aucune ligne n'est créée (une LigneDevis exige un
    Produit du catalogue) — le devis brouillon est laissé à compléter dans
    l'éditeur.

    Le devis reste ``brouillon`` : ce service CRÉE, il ne change aucun statut
    aval (règle #4). Aucun impact sur `/proposal`.

    IDEMPOTENT : si ``intervention.devis_upsell_id`` pointe déjà vers un
    devis existant, le renvoie tel quel plutôt que d'en créer un second.
    Renvoie le ``Devis`` créé (ou réutilisé)."""
    from ..models import Devis
    from ..utils.references import create_with_reference

    if intervention.devis_upsell_id:
        existant = Devis.objects.filter(
            pk=intervention.devis_upsell_id, company=intervention.company
        ).first()
        if existant is not None:
            return existant

    installation = intervention.installation
    if installation is None or installation.client_id is None:
        raise ValueError(
            "create_devis_upsell_from_intervention requires an intervention "
            "attached to a chantier with a resolved client")
    client = installation.client
    company = intervention.company or installation.company

    note = (
        "Devis d'upsell généré depuis une intervention sur place.\n"
        f"Chantier : {installation.reference}\n"
        f"Type d'intervention : {intervention.get_type_intervention_display()}")

    def _create(ref):
        return Devis.objects.create(
            company=company,
            reference=ref,
            client=client,
            statut=Devis.Statut.BROUILLON,
            created_by=user,
            note=note,
        )

    devis = create_with_reference(Devis, 'DEV', company, _create)
    intervention.devis_upsell_id = devis.id
    intervention.save(update_fields=['devis_upsell_id'])
    logger.info(
        'ZFSM5: devis upsell %s créé depuis intervention %s (company %s)',
        devis.reference, intervention.id, getattr(company, 'id', '?'))
    return devis


# ── PONTS M3 : noms hébergés ailleurs ────────────────────────────────────────
# Imports EN BAS DE FICHIER, visant le module qui PORTE chaque corps.
from apps.ventes.domain.bordereau import concevoir_electrique_du_devis  # noqa: E402,F401
from apps.ventes.domain.catalogue import (  # noqa: E402,F401
    _has_price,
    _is_battery,
    _is_hybrid_inverter,
    _is_reseau_inverter,
    _libelle_role,
    carte_marques_composition,
    catalogue_de_la_societe,
    ordre_lignes_societe,
)
from apps.ventes.domain.composition import (  # noqa: E402,F401
    composition_deux_optimiseurs,
    composition_residentielle,
)
from apps.ventes.domain.etudes import (  # noqa: E402,F401
    rafraichir_etudes_du_devis,
    refresh_marge_snapshot,
)
from apps.ventes.domain.lignes import (  # noqa: E402,F401
    cloner_lignes,
    creer_ligne,
)
from apps.ventes.domain.geometrie import (  # noqa: E402,F401
    _panneau_pour_calepinage,
    arbitrer_compte_calepinage,
    contour_client_lnglat,
    extract_roof_config,
    plafond_physique_du_contour,
    zone_toit_depuis_contour,
)
from apps.ventes.domain.entrees import entrees_depuis_lead  # noqa: E402,F401
from apps.ventes.domain.pipeline import (  # noqa: E402,F401
    COMPOSITION_AVEC,
    COMPOSITION_LES_DEUX,
    COMPOSITION_SANS,
    ORIGINE_AUTO,
    ORIGINE_CALEPINAGE,
    ORIGINE_TUNNEL,
    CibleDevis,
    IntentionComposition,
    IntentionDevis,
    appliquer,
    composer,
    verifier,
)
from apps.ventes.domain.scenario import (  # noqa: E402,F401
    SCENARIO_AVEC_BATTERIE,
    SCENARIO_LES_DEUX,
    SCENARIO_SANS_BATTERIE,
    _scenario_stocke,
    poser_puissance_kwc,
    scenario_effectif,
)
from apps.ventes.domain.taille import (  # noqa: E402,F401
    AutoDevisError,
    _panneaux_dimensionnement_horaire,
    _refus_dimensionnement,
    _residential_panel_count,
    phase_client_pour_dimensionnement,
)
