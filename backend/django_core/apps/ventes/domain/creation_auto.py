"""Le devis AUTOMATIQUE (SPL267, déplacé de ``domain/creation.py``).

Le dry-run que le vendeur approuve (``composer_devis_residentiel``), le devis
automatique depuis un lead (``build_devis_auto`` — dimensionnement, refus
motivé ; adaptateur de ``pipeline.appliquer``, origines ``auto`` / ``tunnel``),
le tunnel du site (``auto_devis_tunnel_actif``), la marque anti-doublon, la
note d'abstention et la planification Celery.

IMPORT AMONT DE ``domain/taille`` : ``composer_devis_residentiel`` porte
``panel_watt=_AUTO_PANEL_WATT`` comme VALEUR PAR DÉFAUT, évaluée à la
définition de la fonction — donc au chargement du module, avant tout pont de
bas de fichier. ``domain/taille`` est une FEUILLE : l'import ne peut pas
boucler. Les autres noms lus ailleurs dans ``domain/`` sont importés EN BAS
de ce fichier, en visant le module qui porte le corps (``creation`` pour
``_structure_demandee``, ``creation_calepinage`` pour l'arbitrage) — jamais la
façade. Déplacement pur : corps octet-identiques, prouvé par
``tests/golden/split_dm_auto.json``.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` : des tests capturent ce nom.
"""
from decimal import Decimal, ROUND_HALF_UP
import logging

from apps.ventes.domain.taille import _AUTO_PANEL_WATT

logger = logging.getLogger("apps.ventes.services")


#: U3 — les trois scénarios batterie qu'un appelant peut demander POUR CE
#: DEVIS-LÀ, sans jamais réécrire la fiche du lead.
SCENARIOS_DEMANDABLES = ('sans', 'avec', 'les_deux')


def composer_devis_residentiel(*, company, kwc=None, nb_panneaux=0,
                               panel_watt=_AUTO_PANEL_WATT, scenario=None,
                               structure_type='acier',
                               structure_produit_id=None,
                               taux_tva=Decimal('20'), mppt_paires=1,
                               gamme_nom_devis=None, phase=None,
                               dimensionnement_avec=None,
                               hors_reseau=False, ville=''):
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

    ``ville`` (QJR604) — la ville de calcul du barème transport, résolue par
    l'APPELANT depuis un lead de sa société (``transport.ville_du_lead``) —
    jamais un texte libre du corps de requête. ``''`` ⇒ prix catalogue.

    ``hors_reseau`` (QJR-OFFGRID, fondateur 01/09/2026) — le site est ISOLÉ :
    la composition part sur l'onduleur AUTONOME + une batterie OBLIGATOIRE, en
    mono-option. La FORME de la réponse ne change pas d'un champ. Deux
    différences assumées avec le chemin raccordé : le scénario demandé est
    ignoré (un site isolé n'a pas d'alternative à proposer), et un catalogue
    incapable de servir l'autonome ou sa batterie fait REFUSER le dry-run par
    une ``AutoDevisError`` française nommant la référence manquante — là où le
    chemin raccordé se contente d'avertir. La raison : ici, « avertir » aurait
    rendu une composition SANS onduleur, ou (pire) invité à lui substituer un
    hybride que ce client ne peut pas raccorder.
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
    # QJR-OFFGRID — un site ISOLÉ n'a qu'une composition : autonome + batterie.
    # QJR400 — la règle « hors réseau ⇒ jamais deux options » vient du NOYAU
    # (``utils.options.deux_options_composables``), elle n'est plus recopiée.
    from apps.ventes.utils.options import deux_options_composables
    hors_reseau = bool(hors_reseau)
    deux_options = deux_options_composables(deux_options, hors_reseau)
    if hors_reseau:
        avec_batterie = True

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
        hors_reseau=hors_reseau,
        gamme_nom_devis=gamme_nom_devis)) or ())
    # QJR-OFFGRID — SEUL le hors réseau transforme cet avertissement en REFUS
    # (voir la docstring) : sans onduleur autonome tarifé, il n'y a rien à
    # composer et surtout rien à substituer.
    if hors_reseau and avertissements:
        raise AutoDevisError(avertissements[0], field='hors_reseau')
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
        # STKCAT7 — cf. ``build_devis_from_layout`` : MÊME intention des deux
        # côtés, donc MÊME structure à l'aperçu et au devis.
        structure_produit_id=structure_produit_id,
        taux_tva=taux_tva,
        mppt_paires=mppt_paires,
        # PVCOMPAT — le DRY-RUN doit voir la MÊME contrainte de raccordement
        # que la construction, sinon l'aperçu montrerait un onduleur que le
        # devis ne composerait pas.
        phase=phase,
        gamme_nom_devis=gamme_nom_devis,
        dimensionnement_avec=dimensionnement_avec,
        avertissements=avertissements,
        hors_reseau=hors_reseau,
        ville=ville or '',
    ))

    roles = list(getattr(lignes, 'roles', ()) or ())
    taux_demande = Decimal(str(taux_tva or 20))
    rendu = []
    for index, ligne in enumerate(lignes):
        # TVA-LIGNE (06/10/2026) — le taux PAR LIGNE : celui du produit quand
        # sa fiche en porte un (DC7 — 10 % panneaux PV), sinon le taux
        # demandé. Un taux unique (20) pour toute la composition faisait
        # enregistrer les panneaux à 20 % par l'écran.
        tva_produit = getattr(getattr(ligne, 'produit', None), 'tva', None)
        taux_ligne = taux_demande
        if tva_produit is not None:
            taux_ligne = Decimal(str(tva_produit))
            # « 10.00 » (colonne à 2 décimales) rendu « 10 », comme le taux
            # demandé : la forme de la valeur ne change pas d'une ligne à
            # l'autre ; un taux non entier (5.5) reste tel quel.
            if taux_ligne == taux_ligne.to_integral_value():
                taux_ligne = Decimal(int(taux_ligne))
        facteur = Decimal('1') + taux_ligne / Decimal('100')
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
            'taux_tva': str(taux_ligne),
            # L-2OPT — '' sur toute composition mono-optimum (le cas de tous
            # les aperçus d'hier) : la clé est ADDITIVE, jamais absente.
            'variante': getattr(ligne, 'variante', '') or '',
            # ERR-QJR570 (D-QJR5-4) — provenance : posée par le moteur.
            'ligne_composee': True,
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


def _build_devis_auto_ci(*, lead, user, company, taux_tva=Decimal('20'),
                         target_kwc=None):
    """CIQ120 — devis automatique COMMERCIAL / INDUSTRIEL par le serveur.

    Chaîne : ``etude_ci.etudier_ci`` (entrées du lead, CIQ405 ; garde
    kWh-vs-factures) → taille retenue (ou ``target_kwc`` / la taille
    souhaitée du lead, SOUVERAINES) → composition du moteur → devis BROUILLON
    (référence ``utils/references.py``, lignes par l'écrivain unique) → étude
    v2 écrite UNE fois par le rafraîchisseur (taille donnée = les lignes).
    Tension, phases et puissance souscrite partent dans les ENTRÉES. Le type
    du lead n'est JAMAIS changé (convention 20). Aucun statut touché (#4).
    Refus ``AutoDevisError`` nommant la donnée manquante ou la cause moteur.
    """
    from apps.crm.services import resolve_client_for_lead
    from apps.ventes.domain.etude_ci import (
        entrees_pour_etude_params, etudier_ci, lignes_du_devis_ci,
        refus_devis_auto_ci)
    from apps.ventes.domain.lignes import creer_ligne
    from apps.ventes.models import Devis
    from apps.ventes.utils.references import create_with_reference

    taille = target_kwc if target_kwc not in (None, '') else getattr(
        lead, 'taille_souhaitee_kwc', None)
    corps = {'mode': lead.type_installation}
    if taille not in (None, ''):
        try:
            taille = float(taille)
        except (TypeError, ValueError):
            raise AutoDevisError('Puissance cible invalide.', field='target_kwc')
        if taille <= 0:
            raise AutoDevisError('La puissance cible doit être supérieure à zéro.',
                                 field='target_kwc')
        corps['taille_explicite_kwc'] = taille
    etude = etudier_ci(company, corps, lead=lead)
    refus = refus_devis_auto_ci(etude)
    if refus:
        raise AutoDevisError(refus[0], field=refus[1])
    lignes = lignes_du_devis_ci(etude.get('composition'))
    if not any(ligne['produit_id'] for ligne in lignes):
        raise AutoDevisError('Aucun article C&I chiffré à composer.',
                             field='composition')

    client = resolve_client_for_lead(lead)
    entrees = entrees_pour_etude_params(etude.get('entrees_resolues'))
    entrees['mode'] = lead.type_installation

    def _create(ref):
        return Devis.objects.create(
            company=company, reference=ref, client=client, lead=lead,
            statut=Devis.Statut.BROUILLON, created_by=user,
            taux_tva=taux_tva, mode_installation=lead.type_installation,
            etude_params=entrees)

    devis = create_with_reference(Devis, 'DEV', company, _create)
    for ordre, ligne in enumerate(lignes):
        creer_ligne(devis, produit_id=ligne['produit_id'],
                    designation=ligne['designation'], quantite=ligne['quantite'],
                    prix_unitaire=ligne['prix_unitaire'], ordre=ordre)
    rafraichir_etudes_du_devis(devis)
    logger.info('Auto-devis C&I %s: %s kWc (lead %s, company %s)', devis.reference,
                (etude.get('taille') or {}).get('retenue_kwc'), getattr(lead, 'pk', '?'),
                getattr(company, 'id', '?'))
    return devis


def build_devis_auto(*, lead, user, company, taux_tva=Decimal('20'),
                     remise_globale=Decimal('0'), target_kwc=None,
                     scenario=None, etude_extra=None, plafond_toit=None,
                     journal_auto=None, origine=None,
                     structure_produit_id=None, structure_type=None):
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
    * ``structure_produit_id`` / ``structure_type`` (STKCAT8/STKCAT9) — la
      STRUCTURE du kit. Absents (LE DÉFAUT), c'est LE LEAD qui décide : son
      ``structure_produit`` épinglé d'abord, sa préférence acier/aluminium
      ensuite, l'acier historique à défaut (cf. :func:`_structure_demandee`).
      Fournis, ils passent devant le lead sans jamais réécrire sa fiche —
      comme les trois réglages ci-dessus.

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
    if marche in ('commercial', 'industriel'):
        # CIQ120 — le C&I passe par LE moteur serveur (D-CIQ-0), origine
        # « auto » seulement : le tunnel du site reste refusé pour le C&I.
        if (origine or ORIGINE_AUTO) != ORIGINE_AUTO:
            raise AutoDevisError(
                "Le devis automatique depuis le site n'est pas ouvert au "
                "commercial et à l'industriel : le commercial le lance depuis "
                "la fiche lead.", field='type_installation')
        return _build_devis_auto_ci(lead=lead, user=user, company=company,
                                    taux_tva=taux_tva, target_kwc=target_kwc)
    if marche and marche != 'residentiel':
        raise AutoDevisError(
            "L'auto-devis ne gère que le résidentiel pour l'instant. Pour "
            "l'industriel/commercial ou l'agricole, utilisez l'écran générateur "
            "de devis.",
            field='type_installation')

    # ERR-QAC-KWH-SAISI-INCOHERENT-FACTURES (décision fondateur 30/09/2026) —
    # un kWh déclaré que les factures de la fiche contredisent n'est jamais
    # chiffré en silence : aucun devis tant que la fiche n'est pas corrigée.
    from apps.ventes.etude_horaire import controle_kwh_declare_du_lead
    from apps.ventes.horaire.conso import MESSAGE_KWH_INCOHERENT
    controle_kwh = controle_kwh_declare_du_lead(lead, company)
    if controle_kwh is not None and not controle_kwh['coherent']:
        raise AutoDevisError(MESSAGE_KWH_INCOHERENT,
                             field='conso_mensuelle_kwh')

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

    # ── QJR-OFFGRID (fondateur 01/09/2026) — LE SITE ISOLÉ ──────────────────
    # Le lead déclare « aucun » raccordement : il n'y a pas de réseau à
    # injecter, donc rien à comparer. Le devis auto part sur l'onduleur
    # AUTONOME + batterie, en option unique — et il REFUSE (étape 4 ci-dessous)
    # plutôt que de coter un hybride que ce client ne pourra pas raccorder.
    # ACAL32 — phase ET site isolé lus UNE fois (``taille``), comme le
    # chemin 3D et le pré-vol.
    # QJR400 — même propriétaire unique que ci-dessus pour « hors réseau ⇒
    # jamais deux options ».
    from apps.ventes.utils.options import deux_options_composables
    phase_client, hors_reseau = phase_et_isolement_du_lead(lead)
    deux_options = deux_options_composables(deux_options, hors_reseau)
    if hors_reseau:
        wants_battery = True

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
    # ACAL32 — ``phase_client`` est lu plus haut, avec ``hors_reseau``, par
    # ``taille.phase_et_isolement_du_lead`` (une seule déduction).

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
                        else COMPOSITION_SANS)),
        hors_reseau=hors_reseau))
    if refus_composition:
        raise AutoDevisError(refus_composition[0], field='composition')

    # STKCAT9 — LA STRUCTURE VIENT DU LEAD quand l'appelant n'en impose
    # aucune : un lead aluminium (ou porteur d'une pergola) ne reçoit plus un
    # devis acier. Résolue UNE fois, servie aux DEUX points de composition.
    structure_produit_id, structure_type = _structure_demandee(
        lead, structure_produit_id, structure_type)

    apercu = composer_devis_residentiel(
        company=company, nb_panneaux=panneaux,
        panel_watt=watt_dimensionnement,
        scenario=choix_batterie or 'les_deux', taux_tva=taux_tva,
        phase=phase_client,
        hors_reseau=hors_reseau,
        # STKCAT8 — LA STRUCTURE DESCEND SUR LES DEUX POINTS DE COMPOSITION.
        # Ce chemin en avait DEUX (ce dry-run, qui contrôle les marques, et
        # l'``IntentionDevis`` finale qui écrit les lignes) et n'en informait
        # AUCUN : le devis automatique composait toujours de l'acier. Les
        # transmettre tous les deux est ce qui interdit à l'aperçu et au devis
        # de diverger.
        structure_produit_id=structure_produit_id,
        structure_type=structure_type,
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
        hors_reseau=hors_reseau,
        # STKCAT8 — le SECOND point de composition de ce chemin (cf. le
        # dry-run ci-dessus) : la MÊME structure, sinon l'aperçu contrôlé et
        # le devis écrit ne seraient plus le même kit.
        structure_produit_id=structure_produit_id,
        structure_type=structure_type,
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
    # BARÈME TRANSPORT — QJR604 : appliqué par l'étape ``composer`` du
    # pipeline (ville du lead), avant le cliché de marge et le gel du prix/kWc.
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


# ── PONTS M3 : noms hébergés ailleurs ────────────────────────────────────────
# Imports EN BAS DE FICHIER, visant le module qui PORTE chaque corps.
from apps.ventes.domain.catalogue import _libelle_role  # noqa: E402
from apps.ventes.domain.etudes import rafraichir_etudes_du_devis  # noqa: E402
from apps.ventes.domain.geometrie import (  # noqa: E402
    _panneau_pour_calepinage,
    contour_client_lnglat,
    extract_roof_config,
    plafond_physique_du_contour,
    zone_toit_depuis_contour,
)
from apps.ventes.domain.entrees import entrees_depuis_lead  # noqa: E402
from apps.ventes.domain.pipeline import (  # noqa: E402
    ORIGINE_AUTO,
    ORIGINE_TUNNEL,
    CibleDevis,
    IntentionDevis,
    appliquer,
)
from apps.ventes.domain.etape_composer import (  # noqa: E402
    COMPOSITION_AVEC,
    COMPOSITION_LES_DEUX,
    COMPOSITION_SANS,
    IntentionComposition,
    composer,
    verifier,
)
from apps.ventes.domain.scenario import (  # noqa: E402
    SCENARIO_AVEC_BATTERIE,
    SCENARIO_LES_DEUX,
    SCENARIO_SANS_BATTERIE,
    scenario_effectif,
)
from apps.ventes.domain.taille import (  # noqa: E402
    AutoDevisError,
    _panneaux_dimensionnement_horaire,
    _refus_dimensionnement,
    _residential_panel_count,
    phase_client_pour_dimensionnement,
    phase_et_isolement_du_lead,
)
from apps.ventes.domain.creation import _structure_demandee  # noqa: E402
from apps.ventes.domain.creation_calepinage import (  # noqa: E402
    _arbitrage_du_calepinage,
    _calepinage_range,
)
