"""D-ACAL-109 / D-ACAL-110 (fondateur, 25/11/2026) — une désignation à la main ne retire
jamais une option.

Un onduleur désigné à l'étape Électrique force le scénario qui lui convient (hybride ⇒
« avec batterie », réseau ⇒ « sans ») : il sert CETTE option. L'AUTRE option reste, telle
que le moteur la compose sans désignation d'onduleur (même lead, même plafond de toit, sa
taille, son onduleur) ; un module désigné vaut pour les deux options (il n'est lié à aucun
scénario). Un lead qui ne demande qu'une option (batterie souhaitée, site isolé) en garde
une. Chaque option dit ce qui est désigné (``source`` ``impose`` des valeurs, posé par
``valeurs.dire_l_impose``) et une supposition dit laquelle est laquelle ; un module d'une
autre puissance garde la puissance de chaque option au panneau le plus proche
(``taille.panneaux_pour_la_meme_puissance``) et une supposition dit le nombre et le kWc
avant et après. Aucune écriture.
"""

CODE_OPTION_DU_MOTEUR = 'option_materiel_du_moteur'
CODE_PANNEAUX_AU_MODULE = 'panneaux_au_module_designe'
LIBELLES = {'sans': 'sans batterie', 'avec': 'avec batterie'}
MESSAGE_OPTION_DU_MOTEUR = ("Onduleur désigné à la main « %s » : il sert l'option %s ; l'option %s garde "
                            "l'onduleur choisi par le moteur.")
MESSAGE_PANNEAUX_AU_MODULE = ('Module désigné « %s » (%s Wc) : option %s à %d panneaux pour %s kWc, au lieu de '
                              '%d panneaux pour %s kWc calculés par le moteur depuis la facture (au panneau le '
                              'plus proche de la même puissance).')


def deux_options_du_lead(lead):
    """Le lead SANS désignation aurait-il les deux options ? La règle de
    ``decisions.decider_taille_residentielle`` (batterie souhaitée, site isolé)."""
    from apps.ventes.domain.taille import phase_et_isolement_du_lead
    from apps.ventes.utils.options import deux_options_composables

    choix = (getattr(lead, 'batterie_souhaitee', '') or '').strip()
    return deux_options_composables(choix not in ('avec', 'sans'), phase_et_isolement_du_lead(lead)[1])


def arrondi(arrondis, scenario, panneau, decision, nombre):
    """Note le passage du compte du moteur (``decision``) au compte ``nombre`` du module
    ``panneau`` (``Entree`` du catalogue) pour l'option ``scenario``."""
    watt = float(panneau.wc)
    arrondis.append({'option': scenario, 'nom': panneau.produit.nom, 'watt': watt,
                     'moteur': {'nb_panneaux': int(decision.panneaux), 'puissance_kwc': decision.kwc},
                     'retenu': {'nb_panneaux': int(nombre), 'puissance_kwc': round(nombre * watt / 1000, 2)}})


def garder_l_autre_option(resultat, calcul, porteur, toit, imposes, designes):
    """Après une conception désignée réussie (résidentiel) : calcule l'option que
    l'onduleur désigné n'a pas prise, sans l'onduleur désigné (le module désigné, lui,
    reste), et la range dans ``resultat.autre_option = (option, résultat)``. Un échec du
    moteur sur cette option la dit absente (``absents``), jamais un refus."""
    from apps.ventes.conception.moteur import ResultatConception
    from apps.ventes.conception.porte_calepinage import SimulationEnCours
    from apps.ventes.conception.valeurs import options
    from apps.ventes.domain.taille import AutoDevisError

    designee = resultat.option_designee
    if designee not in LIBELLES or not deux_options_du_lead(porteur[0]):
        return
    autre_option = 'sans' if designee == 'avec' else 'avec'
    autre = ResultatConception(marche=resultat.marche, entrees_utilisees=dict(resultat.entrees_utilisees),
                               empreinte=resultat.empreinte, niveau_regles=resultat.niveau_regles)
    autre.pose_a_produire, autre.plan_a_produire = resultat.pose_a_produire, resultat.plan_a_produire
    module = {'panneau_produit_id': designes['panneau_produit_id']} if designes.get('panneau_produit_id') else {}
    try:
        if module:
            calcul(autre, *porteur, toit=toit, imposes=dict(imposes or {}, **module), completer=True,
                   scenario=autre_option)
        else:
            calcul(autre, *porteur, toit=toit, imposes=imposes)
    except SimulationEnCours:
        raise
    except AutoDevisError as exc:
        resultat.absents['option_%s' % autre_option] = 'refus : %s' % exc.message
        return
    if autre_option in options(autre)[1]:
        resultat.autre_option = (autre_option, autre)
        resultat.arrondis += autre.arrondis


def ajouter_l_autre_option(resultat, investissement, *, froid, company):
    """Pose les valeurs de l'autre option (lues sur SON résultat, par ``valeurs.valeurs``)
    et les suppositions qui disent laquelle est laquelle et l'arrondi au module désigné."""
    from apps.ventes.conception import valeurs as V

    if resultat.autre_option is not None:
        option, autre = resultat.autre_option
        portees = dict(resultat.valeurs, **{option: V.valeurs(autre, option, investissement, froid=froid,
                                                              company=company)})
        resultat.valeurs = {o: portees[o] for o in ('sans', 'avec') if o in portees}
        onduleurs = (resultat.valeurs.get(resultat.option_designee) or {}).get('onduleurs') or {}
        nom = next((o.get('designation') for o in onduleurs.get('valeur') or []), None)
        if (resultat.imposes_retenus or {}).get('onduleur_produit_id') and nom:
            resultat.suppositions.append({
                'code': CODE_OPTION_DU_MOTEUR, 'champ': 'onduleur_produit', 'valeur': option, 'source': 'defaut',
                'message': MESSAGE_OPTION_DU_MOTEUR % (nom, LIBELLES[resultat.option_designee], LIBELLES[option])})
    from apps.ventes.domain.resolution_catalogue import _fmt
    for note in resultat.arrondis:
        resultat.suppositions.append({
            'code': CODE_PANNEAUX_AU_MODULE, 'champ': 'module_produit', 'source': 'defaut',
            'valeur': {'option': note['option'], 'moteur': note['moteur'], 'retenu': note['retenu']},
            'message': MESSAGE_PANNEAUX_AU_MODULE % (
                note['nom'], _fmt(note['watt']), LIBELLES.get(note['option'], note['option']),
                note['retenu']['nb_panneaux'], _fmt(note['retenu']['puissance_kwc']),
                note['moteur']['nb_panneaux'], _fmt(note['moteur']['puissance_kwc']))})
