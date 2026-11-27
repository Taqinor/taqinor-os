"""D-HYB-4 — RECOMPOSER LES BATTERIES d'un devis C&I brouillon (fondateur,
17/11/2026, après-midi).

« I expect the number of panels to be reduced if we use only one battery…
this number should be choosable… with the maximum calculated by the quote
calculator. » Le vendeur choisit N batteries, 1 ≤ N ≤ R (R = la banque que le
calculateur trouve) : l'étude est recalculée avec ``options.nb_batteries = N``
(panneaux redimensionnés pour N, onduleur hybride GARDÉ pour R — « Inverter
for the maximum »), puis les lignes de l'option « avec » sont RECOMPOSÉES par
le même code que la création (``lignes_du_scenario`` : la fusion
``fusionner_kits`` ; l'option « sans » ressort inchangée) et par le même
écrivain que la révision après visite (``revision_visite_ci`` : pipeline
``MODE_ECRIRE``, échéancier re-basé, une transaction).

* brouillon SEULEMENT (un devis envoyé se révise : « Réviser ») ;
* devis commercial / industriel portant une option « avec » (scénario « Les
  deux » ou « Avec batterie ») ;
* ``etude_params.options.nb_batteries = N`` et ``banque_recommandee`` = R
  (posée quand le devis la précède) ;
* aucun statut écrit (règle #4).

Contrat : ``contract_samples/devis_recomposer_batteries.json``.
"""
import logging

logger = logging.getLogger(__name__)

MESSAGE_NON_BROUILLON = ('Devis « %s » : ses batteries ne peuvent plus être recomposées. '
                         'Utilisez « Réviser » pour en créer une nouvelle version.')
MESSAGE_PAS_CI = 'Seul un devis commercial ou industriel recompose ses batteries.'
MESSAGE_SANS_OPTION = ("Ce devis n'a pas d'option « avec batterie » : rien à recomposer.")
MESSAGE_NON_COMPOSEE = 'Option « avec batterie » non composée : %s'
MESSAGE_NB = ('Nombre de batteries attendu : un nombre entier, au moins 1 (au plus la '
              'banque calculée pour ce client).')
MESSAGE_MAXI = ('Au plus %d batterie(s) : c’est la banque calculée pour ce client '
                '(panneaux et onduleur dimensionnés pour elle).')


class RecompositionBatteriesError(Exception):
    """Refus nommé : ``message`` (français, au vendeur), ``champ`` et
    ``statut_http`` (400 : saisie ; 409 : état du devis)."""

    def __init__(self, message, champ, statut_http=409):
        super().__init__(message)
        self.message = message
        self.champ = champ
        self.statut_http = statut_http


def _gardes(devis):
    """Les refus d'état du devis (409), avant tout calcul."""
    from .revision_visite_ci import MESSAGE_INACTIF, MODES_CI
    from .scenario import SCENARIO_AVEC_BATTERIE, SCENARIO_LES_DEUX
    if (getattr(devis, 'mode_installation', '') or '').lower() not in MODES_CI:
        raise RecompositionBatteriesError(MESSAGE_PAS_CI, 'mode_installation')
    if not getattr(devis, 'is_active', True):
        raise RecompositionBatteriesError(MESSAGE_INACTIF, 'devis')
    if devis.statut != 'brouillon':
        raise RecompositionBatteriesError(
            MESSAGE_NON_BROUILLON % devis.get_statut_display(), 'statut')
    scenario = (getattr(devis, 'etude_params', None) or {}).get('scenario')
    if scenario not in (SCENARIO_LES_DEUX, SCENARIO_AVEC_BATTERIE):
        raise RecompositionBatteriesError(MESSAGE_SANS_OPTION, 'scenario')
    if getattr(devis, 'lead', None) is None:
        from .revision_visite_ci import MESSAGE_SANS_LEAD
        raise RecompositionBatteriesError(MESSAGE_SANS_LEAD, 'lead')
    return scenario


def lire_nb_batteries(valeur):
    """N du corps : un nombre entier ≥ 1 (jamais un booléen, un texte ni
    « 1,5 »), sinon 400 nommant ``nb_batteries``."""
    from .etude_ci_batterie import nb_batteries_choisi
    nombre = nb_batteries_choisi(valeur) if isinstance(valeur, (int, float)) else None
    if nombre is None:
        raise RecompositionBatteriesError(MESSAGE_NB, 'nb_batteries', 400)
    return nombre


def _taille_sans(devis, scenario):
    """La taille de l'offre réseau, GARDÉE : kWc « sans » des lignes (deux
    options), sinon le verdict de création (« avec » seule) ; ``None`` ⇒
    l'étude la recalcule comme à la création."""
    from .etude_ci import CLE_TAILLE_CREATION
    from .etudes import puissances_etude_horaire
    from .scenario import SCENARIO_LES_DEUX
    kwc_avec, kwc_sans = puissances_etude_horaire(devis)
    if scenario == SCENARIO_LES_DEUX and (kwc_sans or kwc_avec):
        return kwc_sans or kwc_avec      # panneaux communs : une seule puissance
    verdict = (devis.etude_params or {}).get(CLE_TAILLE_CREATION) or {}
    return verdict.get('retenue_kwc') or None


def _etude(devis, scenario, nombre):
    """L'étude recalculée avec N (mêmes entrées que la création : le lead et
    les entrées stockées du devis), sa banque calculée R et ses lignes."""
    from .etude_ci import CLE_TAILLE_CREATION, etudier_ci, provenance_lignes_du_devis, refus_devis_auto_ci
    from .etude_ci_batterie import CLE, lignes_du_scenario
    corps = {'mode': devis.mode_installation.lower(), 'options': {'nb_batteries': nombre}}
    taille = _taille_sans(devis, scenario)
    if taille:
        corps['taille_explicite_kwc'] = taille
    # ACAL1226 — la taille issue du verdict de création est dite « calculée à la création ».
    etude = etudier_ci(devis.company, corps, devis=devis, lead=devis.lead,
                       provenance_corps=provenance_lignes_du_devis(),
                       verdict_creation=(devis.etude_params or {}).get(CLE_TAILLE_CREATION))
    refus = refus_devis_auto_ci(etude)
    if refus:
        raise RecompositionBatteriesError(*refus)
    avec = etude.get(CLE)
    if not avec:
        motif = next((a.get('message') for a in etude.get('alertes') or []
                      if a.get('champ') == 'option_avec'), 'aucune banque calculée.')
        raise RecompositionBatteriesError(MESSAGE_NON_COMPOSEE % motif, 'option_avec')
    maxi = avec['batterie'].get('quantite_recommandee') or avec['batterie'].get('quantite')
    if nombre > int(maxi):
        raise RecompositionBatteriesError(MESSAGE_MAXI % int(maxi), 'nb_batteries', 400)
    return etude, avec, int(maxi), lignes_du_scenario(etude, scenario)


def _ecrire(devis, avec, nombre, maxi, lignes, user):
    """Les entrées (``options.nb_batteries``, ``banque_recommandee``) puis les
    lignes par le pipeline, l'échéancier re-basé — dans UNE transaction."""
    from django.db import transaction

    from apps.ventes.utils.echeancier import EcheancierIncoherent

    from .etude_ci_batterie import CLE_BANQUE_RECOMMANDEE
    from .etude_schema import ECRAN, MOTEUR_CI, ecrire
    from .modifiabilite import rebaser_echeancier, ttc_du_devis
    from .pipeline import MODE_ECRIRE, ORIGINE_AUTO, IntentionDevis, appliquer
    composition = [
        {'produit': ligne['produit_id'], 'designation': ligne['designation'],
         'quantite': str(ligne['quantite']), 'prix_unitaire': str(ligne['prix_unitaire']),
         'ordre': ordre, **({'variante': ligne['variante']} if ligne.get('variante') else {})}
        for ordre, ligne in enumerate(lignes)]
    options = dict((devis.etude_params or {}).get('options') or {}, nb_batteries=nombre)
    banque = {'produit': avec['batterie'].get('produit'),
              'nom': avec['batterie'].get('nom') or '', 'quantite': maxi}
    with transaction.atomic():
        ttc_avant = ttc_du_devis(devis)
        ecrire(devis, proprietaire=ECRAN, options=options)
        ecrire(devis, proprietaire=MOTEUR_CI, **{CLE_BANQUE_RECOMMANDEE: banque})
        appliquer(devis, IntentionDevis(
            origine=ORIGINE_AUTO, mode=MODE_ECRIRE, company=devis.company, user=user,
            lead=devis.lead, mode_installation=devis.mode_installation.lower(),
            composition=composition))
        try:
            rebaser_echeancier(devis, ttc_avant=ttc_avant)
        except EcheancierIncoherent as exc:
            raise RecompositionBatteriesError(str(exc), 'echeancier')


def recomposer_batteries(devis, nb_batteries, *, user=None):
    """D-HYB-4 — recompose l'option « avec » du brouillon pour N batteries.

    Rend ``{devis_id, nb_batteries, quantite_recommandee, nb_panneaux_avec,
    kwc_avec, lignes_changees, onduleur_extension, alertes}`` ; lève
    :class:`RecompositionBatteriesError` (refus nommé, rien d'écrit)."""
    from .pipeline import MODE_RAFRAICHIR, ORIGINE_AUTO, IntentionDevis, appliquer
    from .revision_visite_ci import _photo_lignes
    scenario = _gardes(devis)
    nombre = lire_nb_batteries(nb_batteries)
    etude, avec, maxi, lignes = _etude(devis, scenario, nombre)
    if not any(ligne['produit_id'] for ligne in lignes):
        raise RecompositionBatteriesError('Aucun article C&I chiffré à composer.', 'composition')
    avant = _photo_lignes(devis)
    _ecrire(devis, avec, nombre, maxi, lignes, user)
    appliquer(devis, IntentionDevis(
        origine=ORIGINE_AUTO, mode=MODE_RAFRAICHIR, company=devis.company, user=user,
        lead=devis.lead, mode_installation=devis.mode_installation.lower(), force_etudes=True))
    devis.refresh_from_db()
    logger.info('Devis C&I %s : batteries recomposées (%d sur %d)', devis.reference, nombre, maxi)
    return {'devis_id': devis.id, 'nb_batteries': nombre, 'quantite_recommandee': maxi,
            'nb_panneaux_avec': avec.get('nb_panneaux'), 'kwc_avec': avec.get('kwc'),
            'lignes_changees': avant != _photo_lignes(devis),
            'onduleur_extension': avec.get('onduleur_extension'),
            'alertes': [dict(a) for a in etude.get('alertes') or []
                        if a.get('niveau') in ('alerte', 'bloquant')]}
