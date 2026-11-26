"""ADEV160 — les DÉCISIONS du devis automatique, en fonctions pures (D-ACAL-97).

Déplacées TELLES QUELLES des trois fonctions de création (aucun chiffre ne
change : ``tests/test_conception_lead.py::FigeageDevisAutoTests``) pour qu'UNE
définition serve à la fois ``build_devis_auto`` et le moteur unique
(``calculer_conception``, ADEV133). Aucune écriture : ni ORM, ni signal, ni
journal de l'appelant — ce qui doit être dit au vendeur est RENDU (``journal``)
et versé par l'appelant. Les refus restent des ``AutoDevisError`` nommées.

Les collaborateurs sont lus dans le module PORTEUR de chaque marché
(``creation_auto_residentiel`` / ``creation_auto_agricole``) ou importés au
moment de l'appel : un ``patch`` posé sur ces noms (patron des tests du devis
automatique) intercepte toujours le calcul.
"""
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import logging

# Même émetteur qu'avant le déplacement (des tests capturent ce nom).
logger = logging.getLogger("apps.ventes.services")


def _res():
    from apps.ventes.domain import creation_auto_residentiel
    return creation_auto_residentiel


@dataclass
class DecisionResidentielle:
    """Taille, options et layout arrêtés pour un devis résidentiel."""
    panneaux: int
    watt: float
    kwc: float
    source: str
    optimum_avec: object
    choix_batterie: str
    avec_batterie: bool
    deux_options: bool
    phase: object
    hors_reseau: bool
    layout: dict
    #: ``alertes`` (forme ``{code, message}``), ``panneaux_avant_plafond`` /
    #: ``plafond_applique`` et ``contour_client`` — dans l'ordre où ils ont été
    #: notés ; jamais écrit ailleurs.
    journal: dict = field(default_factory=dict)
    #: D-ACAL-169 — le panneau par défaut (id) quand ``watt`` est SA puissance
    #: (taille décidée ici, jamais imposée) ; ``None`` ⇒ choix au wattage.
    panneau_prefere_id: object = None

    def scenario_composition(self):
        R = _res()
        if self.deux_options:
            return R.COMPOSITION_LES_DEUX
        return R.COMPOSITION_AVEC if self.avec_batterie else R.COMPOSITION_SANS


def _taille_residentielle(lead, company, target_kwc, imposition, journal, dimensionner, watt_auto=None):
    """Fondateur 29/08/2026 — deux chemins seulement : une puissance DEMANDÉE
    (souveraine : ``target_kwc``, sinon la fiche) ou le MOTEUR HORAIRE ; le
    compte d'une composition IMPOSÉE (COP2-V3) passe devant les deux.
    ``(panneaux, watt, source, optimum_avec)``. ``watt_auto`` (D-ACAL-169) : la
    puissance du panneau automatique (``panneau_defaut``), sinon 710 Wc."""
    from apps.ventes.domain.taille import (
        _AUTO_PANEL_WATT, AutoDevisError, _refus_dimensionnement, _residential_panel_count,
        phase_client_pour_dimensionnement)
    R = _res()
    taille_kwc = getattr(lead, 'taille_souhaitee_kwc', None)
    cible = None
    if target_kwc not in (None, ''):  # U3/EZ5 — pour CE devis, sans réécrire le lead
        try:
            cible = Decimal(str(target_kwc))
        except (InvalidOperation, TypeError, ValueError):
            raise AutoDevisError('Puissance cible invalide.', field='target_kwc')
        if cible <= 0:
            raise AutoDevisError('La puissance cible doit être supérieure à zéro.', field='target_kwc')
    panneaux, watt, optimum_avec, source = 0, watt_auto or _AUTO_PANEL_WATT, None, None
    taille_demandee = cible if cible is not None else taille_kwc
    if imposition is not None:
        panneaux, watt, source = R._taille_imposee(imposition)
    elif taille_demandee not in (None, ''):
        panneaux = _residential_panel_count(taille_kwc=taille_demandee, panel_watt=watt)
    if imposition is None and panneaux > 0:
        source = 'taille_demandee'
        R._alerter_taille_demandee(journal, cible, taille_demandee)
    elif imposition is None:
        if dimensionner is None:
            from apps.ventes.domain.taille import _panneaux_dimensionnement_horaire as dimensionner
        panneaux, watt_retenu, source, optimum_avec = dimensionner(
            lead=lead, company=company, phase=phase_client_pour_dimensionnement(lead))
        if panneaux <= 0:
            raise _refus_dimensionnement(source)
        if watt_retenu:
            watt = watt_retenu
    return panneaux, watt, source, optimum_avec


def decider_taille_residentielle(*, lead, company, target_kwc=None, scenario=None,
                                 plafond_toit=None, imposition=None, dimensionner=None):
    """Contrôle kWh déclaré / factures, taille (:func:`_taille_residentielle`),
    options et batterie souhaitée, site isolé, optimum « avec » (L-2OPT),
    plafond physique du toit et zone du tracé client. Lève ``AutoDevisError``.
    ``dimensionner`` : le moteur horaire (défaut
    ``taille._panneaux_dimensionnement_horaire``) — le devis automatique passe
    le nom de SON module, cible des ``patch`` de ses tests."""
    from apps.ventes.domain.creation_auto import SCENARIOS_DEMANDABLES
    from apps.ventes.domain.geometrie import zone_toit_depuis_contour
    from apps.ventes.domain.taille import AutoDevisError, phase_et_isolement_du_lead
    from apps.ventes.etude_horaire import controle_kwh_declare_du_lead
    from apps.ventes.horaire.conso import MESSAGE_KWH_INCOHERENT
    from apps.ventes.utils.options import deux_options_composables
    R = _res()
    # ERR-QAC-KWH-SAISI-INCOHERENT-FACTURES (fondateur 30/09/2026).
    controle_kwh = controle_kwh_declare_du_lead(lead, company)
    if controle_kwh is not None and not controle_kwh['coherent']:
        raise AutoDevisError(MESSAGE_KWH_INCOHERENT, field='conso_mensuelle_kwh')
    journal = {}
    # D-ACAL-169 — le panneau par défaut que la composition accepte (une lecture) ;
    # désigné mais inutilisable : la règle d'aujourd'hui, DITE au vendeur.
    from apps.ventes.domain.panneau_defaut import aucun_panneau_auto, panneau_auto_composition
    auto = panneau_auto_composition(company) if imposition is None else aucun_panneau_auto()
    R._ajouter_alerte(journal, 'panneau_par_defaut', auto.motif)
    panneaux, watt, source, optimum_avec = _taille_residentielle(
        lead, company, target_kwc, imposition, journal, dimensionner, watt_auto=auto.watt)
    kwc = round(panneaux * watt / 1000, 2)
    # U2/U3 — sans consigne : les deux options ; un choix explicite est souverain.
    demande = (scenario or '').strip().lower()
    if demande and demande not in SCENARIOS_DEMANDABLES:
        raise AutoDevisError('Scénario inconnu « %s » — attendu : %s.'
                             % (scenario, ', '.join(SCENARIOS_DEMANDABLES)), field='scenario')
    choix_batterie = demande if demande else (getattr(lead, 'batterie_souhaitee', '') or '').strip()
    deux_options = choix_batterie not in ('avec', 'sans')
    # QJR-OFFGRID / ACAL32 / QJR400 — phase et site isolé lus une fois.
    phase, hors_reseau = phase_et_isolement_du_lead(lead)
    deux_options = deux_options_composables(deux_options, hors_reseau)
    avec_batterie = R._batterie_hors_reseau(journal, hors_reseau, choix_batterie, choix_batterie == 'avec')
    # L-2OPT — l'axe « avec batterie » a son propre optimum.
    if avec_batterie and optimum_avec:
        panneaux = int(optimum_avec['nb_panneaux'])
        if optimum_avec.get('panel_watt'):
            watt = float(optimum_avec.get('panel_watt'))
        kwc = round(panneaux * watt / 1000, 2)
        source = 'moteur_horaire_avec'
    elif not deux_options:
        optimum_avec = None
    panneaux, kwc, optimum_avec = _plafond_du_toit(lead, plafond_toit, panneaux, kwc, watt, optimum_avec,
                                                   journal)
    layout = {'result': {'panels': panneaux, 'kwc': kwc}, 'panelWatt': watt,
              'scenario': 'avec_batterie' if avec_batterie else 'reseau'}
    # AUTO-PIPELINE — le tracé du client devient la zone du calepinage.
    zone_client = zone_toit_depuis_contour(lead, panneaux=panneaux, kwc=kwc)
    if zone_client:
        layout.update(zone_client)
        journal['contour_client'] = len(zone_client['outline'])
    return DecisionResidentielle(
        panneaux=panneaux, watt=watt, kwc=kwc, source=source, optimum_avec=optimum_avec,
        choix_batterie=choix_batterie, avec_batterie=avec_batterie, deux_options=deux_options,
        phase=phase, hors_reseau=hors_reseau, layout=layout, journal=journal,
        panneau_prefere_id=auto.prefere(watt))


def _plafond_du_toit(lead, plafond_toit, panneaux, kwc, watt, optimum_avec, journal):
    """AUTO-PIPELINE — le plafond PHYSIQUE du toit ne peut que RÉDUIRE (l'axe
    « avec » subit le même toit). ``(panneaux, kwc, optimum_avec)``."""
    if not plafond_toit:
        return panneaux, kwc, optimum_avec
    try:
        plafond = int(plafond_toit)
    except (TypeError, ValueError):
        plafond = 0
    if plafond > 0 and panneaux > plafond:
        logger.warning('Auto-devis (lead %s): cible de %d panneaux ramenée à %d — '
                       'le tracé du client ne peut pas en porter davantage.',
                       getattr(lead, 'pk', '?'), panneaux, plafond)
        journal['panneaux_avant_plafond'] = panneaux
        journal['plafond_applique'] = plafond
        panneaux = plafond
        kwc = round(panneaux * watt / 1000, 2)
        if optimum_avec and int(optimum_avec.get('nb_panneaux') or 0) > plafond:
            optimum_avec = dict(optimum_avec)
            optimum_avec['nb_panneaux'] = plafond
            watt_avec = optimum_avec.get('panel_watt') or watt
            optimum_avec['kwc'] = round(plafond * float(watt_avec) / 1000, 2)
    return panneaux, kwc, optimum_avec


def verifier_composition_residentielle(decision, *, lead, company, taux_tva=None,
                                       structure_produit_id=None, structure_type=None,
                                       imposition=None):
    """QJR82 / STKCAT8-9 / U3 — l'étape ``verifier`` (mêmes phrases que le
    chemin 3D), la structure (l'appelant, sinon le lead) et le contrôle des
    marques épinglées par la composition À BLANC, AVANT toute écriture.
    Rend ``(structure_produit_id, structure_type)`` ; lève ``AutoDevisError``."""
    from apps.ventes.domain.creation import _structure_demandee
    from apps.ventes.domain.taille import AutoDevisError
    R = _res()
    refus_composition = R.verifier(R.IntentionComposition(
        company=company, nb_panneaux=decision.panneaux, kwc=decision.kwc,
        scenario=decision.scenario_composition(), hors_reseau=decision.hors_reseau,
        **R._champs_imposes(imposition)))
    if refus_composition:
        raise AutoDevisError(refus_composition[0], field='composition')
    structure_produit_id, structure_type = _structure_demandee(
        lead, structure_produit_id, structure_type)
    # COP2-V3 — une composition imposée a déjà été contrôlée à blanc en amont.
    apercu = {'marques_manquantes': []} if imposition is not None else R.composer_devis_residentiel(
        company=company, nb_panneaux=decision.panneaux, panel_watt=decision.watt,
        scenario=decision.choix_batterie or 'les_deux', taux_tva=taux_tva,
        phase=decision.phase, hors_reseau=decision.hors_reseau,
        structure_produit_id=structure_produit_id, structure_type=structure_type,
        dimensionnement_avec=decision.optimum_avec,
        panneau_prefere_id=getattr(decision, 'panneau_prefere_id', None))  # D-ACAL-169
    if apercu['marques_manquantes']:
        detail = ', '.join('%s (%s)' % (m.get('marque'), m.get('libelle_role'))
                           for m in apercu['marques_manquantes'])
        raise AutoDevisError(
            'Marque épinglée introuvable au stock : %s. Ajoutez le produit ou '
            'changez la marque dans Paramètres → Gammes.' % detail, field='marques')
    return structure_produit_id, structure_type


#: Écart 5 de l'acceptation du 25/11 — l'heure d'ouverture est saisie, seule la fin manque.
MESSAGE_HEURE_FIN = ("Demandez au client son heure de fermeture (fin de journée) : l'heure d'ouverture "
                     "est déjà saisie sur la fiche ; ou choisissez son régime d'équipes.")


def _heure_qui_manque(refus, lead):
    """``(message, field)`` du refus C&I ; un refus qui nomme les heures d'ouverture
    (``heure_debut``) alors que le début EST saisi nomme le champ qui manque vraiment :
    ``heure_fin`` (écart 5 de l'acceptation du 25/11)."""
    message, champ = refus
    if champ == 'heure_debut' and getattr(lead, 'heure_debut', None) is not None \
            and getattr(lead, 'heure_fin', None) is None:
        return MESSAGE_HEURE_FIN, 'heure_fin'
    return message, champ


def decider_ci(*, lead, company, target_kwc=None):
    """CIQ120 — taille (``target_kwc`` / taille souhaitée SOUVERAINES, sinon
    l'étude), ``etude_ci.etudier_ci``, refus moteur, options batterie
    (fondateur 26/10/2026). Rend ``(etude, lignes, scenario)``."""
    from apps.ventes.domain.etude_ci import etudier_ci, refus_devis_auto_ci
    from apps.ventes.domain.etude_ci_batterie import lignes_des_options
    from apps.ventes.domain.taille import AutoDevisError
    taille = target_kwc if target_kwc not in (None, '') else getattr(lead, 'taille_souhaitee_kwc', None)
    corps = {'mode': lead.type_installation}
    if taille not in (None, ''):
        try:
            taille = float(taille)
        except (TypeError, ValueError):
            raise AutoDevisError('Puissance cible invalide.', field='target_kwc')
        if taille <= 0:
            raise AutoDevisError('La puissance cible doit être supérieure à zéro.', field='target_kwc')
        corps['taille_explicite_kwc'] = taille
    etude = etudier_ci(company, corps, lead=lead)
    refus = refus_devis_auto_ci(etude)
    if refus:
        message, champ = _heure_qui_manque(refus, lead)
        raise AutoDevisError(message, field=champ)
    lignes, scenario = lignes_des_options(etude, lead)
    if not any(ligne['produit_id'] for ligne in lignes):
        raise AutoDevisError('Aucun article C&I chiffré à composer.', field='composition')
    return etude, lignes, scenario


def etude_params_creation_ci(etude, *, mode, scenario):
    """Les entrées d'``etude_params`` posées à la création C&I : entrées
    résolues, verdict de taille (R1/B1), scénario, banque recommandée (D4) et
    offre mise en avant (CORC9)."""
    from apps.ventes.domain.etude_ci import (
        CLE_TAILLE_CREATION, entrees_pour_etude_params, verdict_taille_creation)
    from apps.ventes.domain.etude_ci_batterie import CLE_BANQUE_RECOMMANDEE, banque_recommandee
    from apps.ventes.domain.scenario import SCENARIO_LES_DEUX, SCENARIO_SANS_BATTERIE
    entrees = entrees_pour_etude_params(etude.get('entrees_resolues'))
    entrees['mode'] = mode
    verdict = verdict_taille_creation(etude)
    if verdict:
        entrees[CLE_TAILLE_CREATION] = verdict
    if scenario:
        entrees['scenario'] = scenario
        recommandee = banque_recommandee(etude)
        if recommandee:
            entrees[CLE_BANQUE_RECOMMANDEE] = recommandee
        if scenario == SCENARIO_LES_DEUX:
            entrees['recommended_option'] = SCENARIO_SANS_BATTERIE
    return entrees


@dataclass(frozen=True)
class DecisionAgricole:
    """Ce que le devis automatique agricole écrit : corps d'étude, sortie du
    moteur, lignes CHIFFRÉES, articles omis (prix à renseigner), pompe."""
    corps: dict
    sortie: dict
    lignes: list
    omises: list
    pompe: dict


def decider_agricole(*, lead, company):
    """AGR124 — champs manquants (AGR403), relevé du point d'eau (D-AGR-4),
    alimentation (AGQ7), ``etudier_pompage`` (AGQ24), refus HMT / débit /
    forage (AGQ1, AGQ9, AGQ40), kit minimum chiffré (AGQ4-6)."""
    from apps.crm.selectors import champs_devis_auto_manquants, visite_point_eau_du_lead
    from apps.ventes.domain import creation_auto_agricole as A
    from apps.ventes.domain.pompage import etudier_pompage, lignes_kit_auto
    from apps.ventes.domain.taille import AutoDevisError, phase_et_isolement_du_lead
    manquants = champs_devis_auto_manquants(lead)
    if manquants:
        raise AutoDevisError('Manque : ' + ', '.join(m['label'] for m in manquants),
                             field=manquants[0]['champ'])
    visite = visite_point_eau_du_lead(lead)
    if visite and visite.get('requise'):
        detail = visite.get('motifs_detail') or [{}]
        raise AutoDevisError(A.MESSAGE_RELEVE_POINT_EAU,
                             field=detail[0].get('champ') or 'niveau_statique_m')
    corps = {'taille': 'recommandee'}
    alim = {'monophase': 'mono', 'triphase': 'tri'}.get(phase_et_isolement_du_lead(lead)[0])
    if not alim:
        raise AutoDevisError('Alimentation de la pompe inconnue : renseignez mono ou tri '
                             '(raccordement du lead)', field='raccordement')
    corps['alim'] = alim
    sortie = etudier_pompage(company, corps, lead=lead, sans_tmy=True)
    hmt_m = (sortie.get('hmt') or {}).get('valeur_m')
    debit = (sortie.get('conception') or {}).get('debit_conception_m3h')
    pompe = sortie.get('pompe') or {}
    resolues = sortie.get('entrees_resolues') or {}
    mode_pompe = (resolues.get('mode_pompe') or {}).get('valeur') or 'neuve'
    if hmt_m is None:
        raise AutoDevisError('HMT introuvable : saisissez la HMT (m).', field='pompe_hmt_m')
    if mode_pompe != 'existante' and debit is None:
        if (resolues.get('debit_souhaite_m3h') or {}).get('valeur') not in (None, ''):
            raise AutoDevisError(
                'Débit de conception introuvable : profil PVGIS du site indisponible et heures de '
                'pompage du réglage société (agricole_pump_hours) non renseignées.',
                field='agricole_pump_hours')
        raise AutoDevisError('Débit de conception introuvable : saisissez le débit souhaité ou '
                             "le besoin en eau (m³/jour).", field='pompe_debit_m3h')
    codes = {a.get('code') for a in sortie.get('alertes') or ()}
    plafonds = (sortie.get('conception') or {}).get('plafonds') or {}
    controle = sortie.get('controle_conception') or {}
    if (controle.get('statut') == 'couverture_insuffisante'
            and ('debit_limite_forage' in codes or plafonds.get('atteint'))):
        raise AutoDevisError(
            "Besoin déclaré incouvrable : débit limité par votre forage (%s m³/h exploitables) — "
            "mois sous la tolérance : %s. Réduisez le besoin ou relevez le débit du forage." % (
                A._fr_nombre(plafonds.get('plafond_retenu_m3h')),
                ', '.join(str(m) for m in controle.get('mois_sous_tolerance') or ()) or '?'),
            field='debit_forage_m3h')
    lignes, omises, manquants = lignes_kit_auto(sortie)
    lignes = _lignes_chiffrees(lignes, company)
    if mode_pompe != 'existante' and (
            pompe.get('placeholder') or not any(ligne['role_pompage'] == 'pompe' for ligne in lignes)):
        raise AutoDevisError(_message_pompes_sans_prix(
            A._fr_nombre(hmt_m), A._fr_nombre(debit), sortie.get('prix_a_renseigner') or []),
            field='pompe')
    if manquants:
        premier = manquants[0]
        message = '%s : %s' % (premier['libelle'], premier['motif'])
        # T4-U3-021 — l'article en cause NOMMÉ (catalogue de la société, jamais
        # un prix) ; sans article servi, la phrase reste celle d'avant.
        noms = [a['nom'] for a in premier.get('articles') or [] if a.get('nom')]
        if noms:
            message += ' — article%s %s' % ('s' if len(noms) > 1 else '', ', '.join('« %s »' % n for n in noms))
        if premier['cle'] == 'variateur' and premier['motif'] == 'aucun article au catalogue':
            message = 'Variateur : aucun modèle compatible au catalogue (%s kW %s)' % (
                A._fr_nombre((sortie.get('puissance_retenue') or {}).get('kw')), alim)
        raise AutoDevisError(message, field='kit.%s' % premier['cle'])
    return DecisionAgricole(corps=corps, sortie=sortie, lignes=lignes, omises=omises, pompe=pompe)


def _message_pompes_sans_prix(hmt, debit, noms):
    """Refus « aucune pompe chiffrable » : les pompes à courbe sans prix NOMMÉES
    et (T4-U3-021) OÙ les chiffrer — le prix de vente de leur fiche, dans Stock
    → Catalogue (même renvoi que les autres manques du catalogue)."""
    message = 'Aucune pompe chiffrable pour HMT %s m / débit %s m³/h' % (hmt, debit)
    if noms:
        message += (' — pompes à courbe sans prix : %s. Prix de vente à saisir dans '
                    'Stock → Catalogue, fiche de chaque pompe' % ', '.join(noms))
    return message + '.'


def _lignes_chiffrees(lignes, company):
    """AGQ4/AGQ5 — le prix de chaque ligne du kit : le BARÈME de l'installation
    (ligne FORFAIT seule, jamais une ligne vendue à la quantité), sinon le prix
    de vente ; une ligne sans prix positif est écartée (jamais gratuite)."""
    from apps.ventes.domain.catalogue import (
        catalogue_de_la_societe, porte_bareme_par_panneau, prix_forfait_ht)
    produits = {p.id: p for p in catalogue_de_la_societe(company)}
    nb_panneaux = sum(int(ligne['quantite']) for ligne in lignes if ligne.get('cle') == 'panneaux')
    chiffrees = []
    for ligne in lignes:
        produit = produits.get(ligne['produit_id'])
        if produit is None:
            continue
        forfait = ligne.get('cle') == 'installation' and porte_bareme_par_panneau(produit)
        montant = prix_forfait_ht(produit, nb_panneaux) if forfait else produit.prix_vente
        if montant and montant > 0:
            chiffrees.append(dict(ligne, prix_unitaire=Decimal(str(montant))))
    return chiffrees
