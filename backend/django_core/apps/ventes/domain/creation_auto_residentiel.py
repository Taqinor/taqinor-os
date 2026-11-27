"""Le devis automatique RÉSIDENTIEL (déplacé tel quel de ``creation_auto.py``).

``composer_devis_residentiel`` (le dry-run que le vendeur approuve) et le
corps résidentiel de ``build_devis_auto`` (``_build_devis_auto_residentiel``).
Le dispatcher ``build_devis_auto`` reste dans ``creation_auto.py``, qui
ré-exporte ces noms. NOM DU LOGGER FIGÉ sur ``apps.ventes.services``.
"""
from decimal import Decimal, ROUND_HALF_UP
import logging

from apps.ventes.domain.taille import _AUTO_PANEL_WATT

logger = logging.getLogger("apps.ventes.services")


def composer_devis_residentiel(*, company, kwc=None, nb_panneaux=0,
                               panel_watt=_AUTO_PANEL_WATT, scenario=None,
                               structure_type='acier',
                               structure_produit_id=None,
                               taux_tva=None, mppt_paires=1,
                               gamme_nom_devis=None, phase=None,
                               dimensionnement_avec=None,
                               hors_reseau=False, ville='', modeles=None,
                               onduleur_impose=None, batterie_imposee=None,
                               panneau_prefere_id=None):
    """U3 — LE DRY-RUN : compose sans RIEN créer, et rend le résultat en clair.

    ``panneau_prefere_id`` (D-ACAL-169) — le panneau par défaut de la société
    quand ``panel_watt`` est SA puissance (posé par l'appelant, jamais lu ici) ;
    ``None`` (LE DÉFAUT) ⇒ dry-run strictement inchangé.

    ``modeles`` / ``onduleur_impose`` / ``batterie_imposee`` (COP2-V3) — la
    composition IMPOSÉE, déjà résolue par
    ``composition_imposee.preparer_imposition`` : le dry-run compose EXACTEMENT
    le kit que ``POST devis/auto/`` créera (règle U3). ``None`` (LE DÉFAUT)
    ⇒ dry-run strictement inchangé.

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
    # APAR49 — taux absent ⇒ taux STANDARD de la société (jamais 20 codé).
    if taux_tva is None:
        from apps.ventes.utils.company_settings import tva_standard
        taux_tva = tva_standard(company)
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
        gamme_nom_devis=gamme_nom_devis, modeles=modeles,
        onduleur_impose=onduleur_impose,
        batterie_imposee=batterie_imposee)) or ())
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
        # COP2-V3 — la composition imposée (``None`` ⇒ inchangé).
        modeles=modeles,
        onduleur_impose=onduleur_impose,
        batterie_imposee=batterie_imposee,
        panneau_prefere_id=panneau_prefere_id,  # D-ACAL-169
    ))

    roles = list(getattr(lignes, 'roles', ()) or ())
    # AMOT69 — un 0 % EXPLICITE reste 0 % ; un taux absent a été résolu plus
    # haut par `tva_standard(company)` (RGEN2 : plus de 20 codé en dur).
    taux_demande = Decimal(str(taux_tva))
    # APAR49 — « 14.00 » (colonne société à 2 décimales) rendu « 14 », comme
    # le taux d'une fiche produit : la forme de la valeur ne change pas.
    if taux_demande == taux_demande.to_integral_value():
        taux_demande = Decimal(int(taux_demande))
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


def _modeles_imposes(imposition):
    """COP2-V3 — le panneau IMPOSÉ, au format ACAL63 ``modeles`` (une fiche
    désignée n'est jamais remplacée par la composition)."""
    return [{'produit_id': imposition.panneau_id,
             'watt': imposition.panel_watt,
             'count': int(imposition.nb_panneaux)}]


def _champs_imposes(imposition):
    """COP2-V3 — les champs IMPOSÉS d'une ``IntentionComposition`` / d'une
    ``CibleDevis`` ; ``{}`` hors imposition (appels strictement inchangés)."""
    if imposition is None:
        return {}
    return {'modeles': _modeles_imposes(imposition),
            'onduleur_impose': imposition.onduleur_impose,
            'batterie_imposee': imposition.batterie_imposee}


def _taille_imposee(imposition):
    """COP2-V3 — ``(panneaux, watt, source)`` d'une composition imposée."""
    return (int(imposition.nb_panneaux), float(imposition.panel_watt),
            'composition_imposee')


def _poser_marqueur_impose(devis, imposition):
    """COP2-V3 — pose le marqueur d'imposition ; sans effet hors imposition."""
    if imposition is None:
        return
    from apps.ventes.domain.composition_imposee import poser_marqueur
    poser_marqueur(devis, dict(imposition.marqueur))


def _completeur_etude(etude_extra, refus_extra):
    """La fusion des clés d'étude de l'appelant (``completer_etude`` du
    pipeline) — extraite TELLE QUELLE de :func:`_build_devis_auto_residentiel`
    (COP2-V3, aucun changement) ; un refus du schéma est consigné dans
    ``refus_extra`` (422 nommé après le pipeline)."""
    def _completer_etude(devis):
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
                refus_extra.append(str(exc))
    return _completer_etude


def _fmt_kwc_fr(valeur):
    """Un kWc à la française : virgule décimale, sans zéros inutiles."""
    texte = ('%.2f' % float(valeur)).rstrip('0').rstrip('.')
    return texte.replace('.', ',')


def _ajouter_alerte(journal_auto, code, texte, champ_lead=None):
    """Ajoute une phrase au vendeur dans ``journal_auto['alertes']``, à la
    MÊME forme que le C&I et l'agricole (``{code, message}`` — rendue par
    ``AlertesDevisAuto.jsx``), sans doublon. Sans effet hors dict.
    ``champ_lead`` (ADEV123) : le champ de la fiche qui lève la supposition,
    même clé que le C&I (``suppositions_ci``)."""
    if not isinstance(journal_auto, dict) or not texte:
        return
    alertes = journal_auto.setdefault('alertes', [])
    if all(a.get('message') != texte for a in alertes):
        alertes.append(dict({'code': code, 'message': texte},
                            **({'champ_lead': champ_lead} if champ_lead else {})))


#: ADEV123 — les quatre suppositions du calcul résidentiel, dites avec le
#: champ de la fiche qui les lève (règle du 17/11/2026).
SUPPOSITIONS_RESIDENTIEL = {
    'occupation_jour': ('suppose_presence', "Présence en journée supposée (profil « présent ») : "
                        "renseignez « Présence en journée » sur la fiche."),
    'facture_ete': ('suppose_ete_egal_hiver', "Facture d'été supposée égale à celle d'hiver : renseignez "
                    "« Facture été » (et « Été différent ») sur la fiche."),
    'conso_mensuelle_kwh': ('suppose_kwh_depuis_facture', "Consommation estimée à partir de la facture en "
                            "dirhams (barème ONEE) : renseignez « Consommation mensuelle (kWh) » sur la fiche."),
    'inclinaison_deg': ('suppose_30_plein_sud', "Production calculée à 30° plein sud (supposé) : "
                        "l'inclinaison et l'orientation de la fiche ne sont pas prises en compte par ce calcul."),
}


def _alerter_suppositions(journal_auto, lead, company, devis):
    """ADEV123 — ce que le calcul a SUPPOSÉ, lu aux MÊMES sources que lui
    (``entrees_depuis_lead``, ``occupation_du_lead``, base de production) ;
    aucun chiffre ne change. Sans journal (dict), rien n'est lu."""
    if not isinstance(journal_auto, dict) or lead is None:
        return
    from apps.ventes.courbes_journalieres import DEFAUT_RESIDENTIEL, occupation_du_lead
    from apps.ventes.domain.entrees import entrees_depuis_lead
    from apps.ventes.horaire.productible_pose import base_de_production
    entrees = entrees_depuis_lead(lead, company, contexte=False)
    source_conso = getattr(entrees, 'source_conso', None)
    champs = [
        'occupation_jour' if occupation_du_lead(lead)[1] == DEFAUT_RESIDENTIEL[1] else None,
        'facture_ete' if source_conso == 'facture_hiver' else None,
        'conso_mensuelle_kwh' if source_conso in ('facture_hiver', 'facture_hiver_ete') else None,
        'inclinaison_deg' if not base_de_production(devis) else None,
    ]
    for champ in filter(None, champs):
        code, texte = SUPPOSITIONS_RESIDENTIEL[champ]
        _ajouter_alerte(journal_auto, code, texte, champ_lead=champ)
    _alerter_ville_de_reference(journal_auto, lead)


def _alerter_ville_de_reference(journal_auto, lead):
    """T4-U1-002 — sans GPS, une ville qui n'est pas elle-même dans la table
    d'ensoleillement (« casa », ville voisine) est calculée sur la ville de
    référence de ``pvgis_profils.ancre_de_reference`` (celle que suit le
    productible) : c'est DIT, avec le champ qui le lève."""
    from apps.crm.selectors import repere_toit
    from apps.parametres.pvgis_profils import ancre_de_reference
    from apps.parametres.villes_resolution import nom_canonique

    ville = (getattr(lead, 'ville', None) or '').strip()
    reference = ancre_de_reference(ville) if ville else None
    if reference is None or reference['exacte'] or repere_toit(lead)[0] is not None:
        return
    nom = nom_canonique(reference['cle'])
    _ajouter_alerte(journal_auto, 'ville_reference', (
        'Ville du lead « %s » non reconnue telle quelle : calcul fait sur %s '
        '(ville de référence%s) — corrigez « Ville » ou posez le GPS sur la fiche.'
        % (ville, nom, '' if reference['proche_km'] is None else ' la plus proche')),
        champ_lead='ville')


def _alerter_taille_demandee(journal_auto, cible, taille_demandee):
    """RGEN1 — la taille vient d'une DEMANDE (ce devis, sinon la fiche) :
    la facture n'a pas dimensionné, le vendeur doit le savoir."""
    if cible is not None:
        _ajouter_alerte(journal_auto, 'taille_demandee', (
            'Taille imposée pour ce devis : %s kWc — la facture du lead '
            "n'a pas servi au dimensionnement." % _fmt_kwc_fr(cible)))
        return
    _ajouter_alerte(journal_auto, 'taille_demandee', (
        'Taille demandée sur la fiche du lead : %s kWc — la facture '
        "n'a pas servi au dimensionnement. Videz « taille souhaitée » "
        'sur la fiche pour revenir à la recommandation.'
        % _fmt_kwc_fr(taille_demandee)))


def _batterie_hors_reseau(journal_auto, hors_reseau, choix_batterie,
                          wants_battery):
    """QJR-OFFGRID — un site isolé prend toujours la batterie ; RGEN1 : un
    « sans » explicite écarté ainsi est DIT au vendeur."""
    if not hors_reseau:
        return wants_battery
    if choix_batterie == 'sans':
        _ajouter_alerte(journal_auto, 'batterie_hors_reseau', (
            'Site sans réseau (raccordement « aucun ») : la batterie est '
            "ajoutée d'office, le choix « sans batterie » ne s'applique "
            'pas.'))
    return True


def _journaliser_avertissements(devis, resultat, journal_auto):
    """U3 — ce que la composition et l'écrivain de lignes ont refusé de
    faire : au journal serveur ET (RGEN1) au vendeur, dans les alertes."""
    for avertissement in resultat['avertissements'] or []:
        logger.warning('Auto-devis %s: %s', devis.reference, avertissement)
        _ajouter_alerte(journal_auto, 'composition', str(avertissement))
    # ADEV123 — puis ce que le calcul a SUPPOSÉ (hors de la fonction-mur).
    _alerter_suppositions(journal_auto, devis.lead, devis.company, devis)


def _verser_au_journal(journal_auto, journal):
    """ADEV160 — ce que la décision pure a noté (``DecisionResidentielle.
    journal``), versé DANS SON ORDRE au journal de l'appelant : les alertes par
    :func:`_ajouter_alerte` (même forme, même dédoublonnage), le reste tel
    quel. Sans journal (dict), rien n'est versé."""
    if not isinstance(journal_auto, dict):
        return
    for cle, valeur in journal.items():
        if cle != 'alertes':
            journal_auto[cle] = valeur
            continue
        for alerte in valeur:
            _ajouter_alerte(journal_auto, alerte['code'], alerte['message'],
                            champ_lead=alerte.get('champ_lead'))


def _build_devis_auto_residentiel(*, lead, user, company, taux_tva=None,
                                  remise_globale=Decimal('0'), target_kwc=None,
                                  scenario=None, etude_extra=None, plafond_toit=None,
                                  journal_auto=None, origine=None,
                                  structure_produit_id=None, structure_type=None,
                                  imposition=None, conception=None, resultat_moteur=None):
    """Le corps RÉSIDENTIEL de :func:`creation_auto.build_devis_auto`
    (déplacé tel quel ; voir la docstring du dispatcher).

    ``conception`` (ADEV142, D-ACAL-97) — la version COURANTE et à jour de la
    conception du lead (``ConceptionLead``) : le moteur horaire n'est PAS
    appelé, sa recommandation est LUE dans le bloc ``dimensionnement`` rangé
    (:func:`dimensionneur_de_la_conception`) et les blocs rangés sont apportés
    à la création (``etude_initiale``) : les rafraîchisseurs les trouvent à
    jour par leurs empreintes. ``resultat_moteur`` : le résultat du moteur quand
    il vient de tourner DANS CETTE requête (conception absente ou périmée) — sa
    sortie du moteur horaire est relue telle quelle. ``None`` (LE DÉFAUT) ⇒
    corps inchangé.

    ``imposition`` (COP2-V3, ``composition_imposee.Imposition``) — le kit
    IMPOSÉ, déjà résolu et contrôlé par
    :func:`composition_imposee.build_devis_auto_impose` : le compte de
    panneaux est SOUVERAIN (ni moteur, ni taille demandée, ni arbitrage de
    calepinage, ni plafond de toit), l'onduleur et la batterie imposés
    voyagent dans la ``CibleDevis``, et le marqueur est posé. ``None`` (LE
    DÉFAUT) ⇒ corps strictement inchangé."""
    # ADEV160 (D-ACAL-97) — les DÉCISIONS (contrôle kWh, taille, options,
    # site isolé, optimum « avec », plafond du toit, zone du tracé client,
    # puis ``verifier``, structure et marques à blanc) sont des fonctions PURES
    # de ``conception/decisions.py`` : une définition, appelée ici et par le
    # moteur unique. Ce qu'elles notent pour le vendeur est versé au journal.
    from apps.ventes.conception.decisions import (
        decider_taille_residentielle, verifier_composition_residentielle)
    decision = decider_taille_residentielle(
        lead=lead, company=company, target_kwc=target_kwc, scenario=scenario,
        plafond_toit=plafond_toit, imposition=imposition,
        # Le moteur horaire lu dans CE module (cible des ``patch`` des tests) ;
        # ADEV142 — sa recommandation RANGÉE quand la conception est à jour.
        dimensionner=(_panneaux_dimensionnement_horaire if conception is None
                      else dimensionneur_de_la_conception(conception, resultat_moteur)))
    _verser_au_journal(journal_auto, decision.journal)
    structure_produit_id, structure_type = verifier_composition_residentielle(
        decision, lead=lead, company=company, taux_tva=taux_tva,
        structure_produit_id=structure_produit_id, structure_type=structure_type,
        imposition=imposition)
    source_dimensionnement = decision.source
    deux_options, wants_battery = decision.deux_options, decision.avec_batterie

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
    # U3/PACT10 — les clés d'étude apportées par l'appelant (factures
    # mensuelles réelles, consommation annuelle, distributeur) COMPLÈTENT
    # l'étude déjà écrite par la construction.
    # ERR-E2E-AUTODEVIS-LENT (07/10/2026) — la fusion est confiée au pipeline
    # (``completer_etude``), qui l'exécute APRÈS l'écriture des lignes et de
    # l'étude (le scénario est donc déjà arrêté, comme avant) et AVANT ses
    # quatre études. Elle tournait après le pipeline : les études étaient
    # calculées une première fois SANS ces clés, jetées, puis recalculées —
    # ~35 % de la requête (mesure sur l'image prod : 4,4 s → 2,8 s), assez pour
    # faire dépasser 15 s au POST /devis/auto/ en CI (figures-parite.spec).
    # Le refus du schéma reste rendu APRÈS le pipeline (même 422, même
    # brouillon laissé qu'avant).
    refus_extra = []
    # COP2-V3 — le corps de la fusion est extrait tel quel
    # (:func:`_completeur_etude`) ; même fermeture, mêmes refus.
    _completer_etude = _completeur_etude(etude_extra, refus_extra)

    # ADEV133 — l'intention (layout, arbitrage, cible souveraine) est arrêtée
    # par :func:`intention_auto_residentielle`, partagée avec le moteur unique.
    intention = intention_auto_residentielle(
        decision, lead=lead, company=company, user=user, taux_tva=taux_tva,
        remise_globale=remise_globale, origine=origine,
        structure_produit_id=structure_produit_id, structure_type=structure_type,
        imposition=imposition,
        completer_etude=(_completer_etude
                         if isinstance(etude_extra, dict) and etude_extra
                         else None),
        blocs_conception=blocs_a_apporter(conception),
        conception_source=pointeur_de_conception(conception))
    panneaux, kwc = intention.cible.nb_panneaux, intention.cible.kwc
    resultat = appliquer(None, intention)
    devis = resultat['devis']
    # U3 — ce que la composition ET l'écrivain de lignes ont REFUSÉ de faire
    # (vivier batterie vide, forfait au panneau non re-tarifé…). Sur un chemin
    # sans commercial dans la boucle, le journal serveur est le seul lecteur.
    _journaliser_avertissements(devis, resultat, journal_auto)

    # QJR63 — LE kWc a été posé par son propriétaire à l'étape 8 (``finaliser``),
    # sur les lignes RÉELLEMENT composées : ni ``target_kwc``, ni
    # ``lead.taille_souhaitee_kwc``, qui sont des DEMANDES et non ce que le
    # catalogue a su servir (l'arrondi au palier et le plafond de toit peuvent
    # faire atterrir ailleurs). Le second appel que ce corps faisait ici est
    # SUPPRIMÉ : il reposait la même valeur sur la même instance.

    # U3/PACT10 — les clés d'étude de l'appelant sont déjà fusionnées (par
    # ``_completer_etude``, dans le pipeline, avant ses études) ; un refus du
    # schéma sort ici, après le pipeline, en 422 NOMMÉ comme avant.
    if refus_extra:
        raise AutoDevisError(refus_extra[0], field='etude_params')
    # COP2-V3 — le MARQUEUR : les chemins qui recomposent ne défont pas ce que
    # le commercial a imposé (sans effet hors imposition).
    _poser_marqueur_impose(devis, imposition)

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


def dimensionneur_de_la_conception(conception, resultat_moteur=None):
    """ADEV142 — le ``dimensionner`` de ``decider_taille_residentielle`` qui
    LIT la sortie du moteur horaire au lieu de la recalculer : celle que le
    moteur vient de rendre dans cette requête (``resultat_moteur.taille_moteur``),
    sinon la recommandation du bloc ``dimensionnement`` rangé
    (``recommandation`` / ``recommandation_avec``, sortie de
    ``recommander_taille``). Même forme que :func:`_panneaux_dimensionnement_horaire`."""
    from apps.ventes.domain.taille import MOTIF_MOTEUR_INDISPONIBLE, ResultatTaille, _recommandation_avec_rendue

    def dimensionner(*, lead, company, phase):
        if getattr(resultat_moteur, 'taille_moteur', None) is not None:
            return resultat_moteur.taille_moteur
        bloc = (getattr(conception, 'blocs', None) or {}).get('dimensionnement') or {}
        recommandation, avec = bloc.get('recommandation'), bloc.get('recommandation_avec')
        if not recommandation:  # jamais servi : l'appelant ne lit que des conceptions complètes
            return ResultatTaille((0, None, MOTIF_MOTEUR_INDISPONIBLE, None))
        return ResultatTaille(
            (int(recommandation['panneaux']), recommandation.get('panel_watt'), 'moteur_horaire',
             _recommandation_avec_rendue(avec)),
            hors_residentiel=any((ligne or {}).get('hors_residentiel') for ligne in (recommandation, avec)))
    return dimensionner


def intention_auto_residentielle(decision, *, lead, company, taux_tva, user=None,
                                 remise_globale=Decimal('0'), origine=None,
                                 structure_produit_id=None, structure_type=None,
                                 imposition=None, completer_etude=None, entrees=None,
                                 blocs_conception=None, conception_source=None):
    """ADEV133 (D-ACAL-97) — l'``IntentionDevis`` du devis automatique
    résidentiel, arrêtée depuis la décision pure : le LAYOUT lu par le lecteur
    du calepinage 3D (``_calepinage_range`` : le tracé du client est une donnée
    réelle), l'arbitrage du compte, et la cible SOUVERAINE (une puissance
    demandée gagne sur le moteur sans jamais réécrire le lead ni passer par
    ``Devis.overrides``). Partagée avec le moteur unique ; aucune écriture.
    ``entrees`` : l'``EntreesMoteur`` déjà lu (QJR42), sinon lu ici.
    ``blocs_conception`` (ADEV142) : les blocs de la conception rangée,
    apportés à la création sous ce que le calepinage apporte lui-même ;
    ``conception_source`` (ADEV143) : le pointeur posé sur le devis créé."""
    from apps.ventes.models import Devis

    layout = decision.layout
    toiture = extract_roof_config(layout)
    # COP2-V3 — le compte IMPOSÉ ne passe pas par l'arbitrage : jamais un
    # nombre de panneaux changé en silence.
    panneaux, kwc = (_arbitrage_du_calepinage(
        layout, decision.panneaux, decision.kwc, company=company) if imposition is None
        else (decision.panneaux, decision.kwc))
    layout_range, etude_initiale = _calepinage_range(layout, toiture, kwc)
    if blocs_conception:
        etude_initiale = dict(blocs_conception, **(etude_initiale or {}))
    return IntentionDevis(
        origine=origine or ORIGINE_AUTO, company=company, user=user, lead=lead,
        mode_installation=Devis.ModeInstallation.RESIDENTIEL,
        # QJR42 — LES ENTRÉES DU MOTEUR, LUES UNE FOIS.
        entrees=entrees if entrees is not None else entrees_depuis_lead(lead, company),
        cible=CibleDevis(
            nb_panneaux=panneaux, panel_watt=decision.watt, kwc=kwc, source=decision.source,
            dimensionnement_avec=decision.optimum_avec,
            panneau_prefere_id=getattr(decision, 'panneau_prefere_id', None),  # D-ACAL-169
            # COP2-V3 — le kit IMPOSÉ ({} hors imposition : cible inchangée).
            **_champs_imposes(imposition)),
        scenario=decision.scenario_composition(),
        layout=layout_range, etude_initiale=etude_initiale or None,
        taux_tva=taux_tva, remise_globale=remise_globale,
        phase=decision.phase, hors_reseau=decision.hors_reseau,
        # STKCAT8 — la MÊME structure que le contrôle à blanc.
        structure_produit_id=structure_produit_id, structure_type=structure_type,
        completer_etude=completer_etude, conception_source=conception_source)


# ── PONTS M3 : noms hébergés ailleurs ────────────────────────────────────────
# Imports EN BAS DE FICHIER, visant le module qui PORTE chaque corps.
from apps.ventes.domain.catalogue import _libelle_role  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
from apps.ventes.domain.etudes import rafraichir_etudes_du_devis  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
from apps.ventes.domain.geometrie import extract_roof_config  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
from apps.ventes.domain.entrees import entrees_depuis_lead  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
from apps.ventes.domain.pipeline import (  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    ORIGINE_AUTO,
    CibleDevis,
    IntentionDevis,
    appliquer,
    pointeur_de_conception,
)
from apps.ventes.domain.etape_composer import (  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    COMPOSITION_AVEC,
    COMPOSITION_LES_DEUX,
    COMPOSITION_SANS,
    IntentionComposition,
    composer,
    verifier,
)
from apps.ventes.domain.scenario import (  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    SCENARIO_AVEC_BATTERIE,
    SCENARIO_LES_DEUX,
    SCENARIO_SANS_BATTERIE,
    scenario_effectif,
)
from apps.ventes.domain.taille import (  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    AutoDevisError,
    _panneaux_dimensionnement_horaire,
)
from apps.ventes.domain.creation_calepinage import (  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    _arbitrage_du_calepinage,
    _calepinage_range,
)
from apps.ventes.domain.creation_auto import (  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    SCENARIOS_DEMANDABLES,
    blocs_a_apporter,
)
