"""ACAL992 — LA porte unique de chiffrage d'une conception (calepinage).

Forme : ``contract_samples/chiffrage_conception.json`` (ACAL991). AUCUN calcul
neuf : un calepinage lié à un devis LIT le rendu de ce devis
(``build_quote_data(devis, {'pdf_mode': 'full'})``, même appel que
``regles_calcul_ecarts_dryrun.ecarts_du_devis``) ; sans devis, le moteur du
devis sur les entrées du lead (résidentiel : ``calculer_etude_horaire`` ;
C&I : ``etudier_ci``). Agricole : non servi (le chiffrage se lit au devis).
Lecture seule ; ne lève jamais (``etat: 'indisponible'`` et son motif).
"""
from __future__ import annotations

import dataclasses
import logging

logger = logging.getLogger(__name__)

UNITES = {'kwc': 'kWc', 'production_annuelle_kwh': 'kWh/an',
          'economie_annee1_mad': 'MAD', 'autoconsommation_pct': '%'}
MOTIF_FACTURE = 'renseignez la facture'  # D-ACAL-40
MOTIF_AGRICOLE = 'le chiffrage agricole se lit au devis'
MOTIF_SANS_LEAD = 'aucun lead lié : le chiffrage du devis ne peut pas être calculé'
MOTIF_ECHEC = 'chiffrage indisponible : calcul du devis en échec'
MOTIF_KWC = 'aucun module posé : puissance du calepinage inconnue'
SOURCE_POSE, SOURCE_VILLE = 'calepinage_enregistre', 'standard_ville'


def _bloc(marche, regles, valeurs, *, motif=MOTIF_FACTURE, etat='omis', option=None):
    """Le contrat : ``valeurs`` = ``{grandeur: (valeur, source)}`` ; une
    grandeur absente prend ``etat`` et son motif dans ``omissions``."""
    sortie, omissions = {'marche': marche, 'regles_calcul': regles}, []
    for cle, unite in UNITES.items():
        valeur, source = valeurs.get(cle, (None, None))
        servi = valeur is not None
        sortie[cle] = {'valeur': valeur, 'unite': unite,
                       'source': source if servi else None, 'etat': 'servi' if servi else etat}
        if not servi:
            omissions.append({'grandeur': cle, 'motif': motif})
    economie = sortie['economie_annee1_mad']
    economie['option'] = option if economie['valeur'] is not None else None
    sortie['omissions'] = omissions
    return sortie


def _pct(fraction):
    return round(float(fraction) * 100, 1) if fraction is not None else None


def _depuis_devis(devis, marche):
    """Le rendu du devis lié, lu tel quel (production saisie, économie
    imposée et options divergentes comprises)."""
    from apps.ventes.horaire.productible_pose import base_de_production
    from apps.ventes.quote_engine.builder import build_quote_data
    from apps.ventes.quote_engine.figures import production_imprimee

    data = build_quote_data(devis, {'pdf_mode': 'full'})
    imprimee = production_imprimee(data)  # R3-D : LA production que le PDF imprime (C&I : celle de l'étude)
    avec = data.get('recommended') == 'Avec batterie'
    saisie = (devis.etude_params or {}).get('production_source') == 'saisie'
    source_prod = 'devis' if saisie else (SOURCE_POSE if base_de_production(devis) else SOURCE_VILLE)
    valeurs = {'kwc': (data.get('puissance_kwc') or None, 'devis'),
               'production_annuelle_kwh': (float(imprimee) if imprimee is not None else None, source_prod)}
    if not data.get('savings_estimated'):  # D-ACAL-40 : rien sans facture
        valeurs['economie_annee1_mad'] = (data.get('eco_a_ann' if avec else 'eco_s_ann'), 'devis')
        valeurs['autoconsommation_pct'] = (_pct(data.get('autoconso_avec' if avec else 'autoconso_sans')), 'devis')
    return _bloc(marche, devis.regles_calcul, valeurs,
                 option='avec_batterie' if avec else 'sans_batterie')


def _base_de_la_pose(calepinage, kwc):
    """Niveau ≥ 15 : la base de la pose réelle de CE calepinage, sinon ``None``."""
    from apps.ventes.coherence.registre import TOLERANCES
    from apps.ventes.domain.regles_calcul import REGLES_POSE_REELLE_2111, regles_au_moins
    if not regles_au_moins(None, REGLES_POSE_REELLE_2111):
        return None
    from apps.calepinage.selectors_devis import productible_pose_du_calepinage
    from apps.ventes.horaire.productible_pose import base_depuis_servi
    servi = productible_pose_du_calepinage(
        calepinage, tolerance_kwc_ratio=TOLERANCES['kwc_calepinage_ratio'])
    return base_depuis_servi(servi, kwc=kwc)[0]


def _depuis_lead(calepinage, lead, company, marche, regles, kwc):
    from apps.ventes.domain.entrees import entrees_depuis_lead, kwargs_moteur_ombre
    from apps.ventes.etude_horaire import calculer_etude_horaire
    from apps.ventes.horaire.public import production_annuelle_pour_kwc

    base = _base_de_la_pose(calepinage, kwc)
    source_prod = SOURCE_POSE if base else SOURCE_VILLE
    valeurs = {'kwc': (kwc, 'lead')}
    entrees = entrees_depuis_lead(lead, company)
    if entrees is not None and entrees.conso_kwh_mensuelles:
        entrees = dataclasses.replace(entrees, base_production=base)
        etude = calculer_etude_horaire(kwc=kwc, source_conso=entrees.source_conso,
                                       **kwargs_moteur_ombre(entrees))
        annuel = (etude or {}).get('annuel') or {}
        valeurs.update(production_annuelle_kwh=(annuel.get('production_kwh'), source_prod),
                       economie_annee1_mad=(annuel.get('economie_sans_mad'), 'lead'),
                       autoconsommation_pct=(_pct(annuel.get('taux_autoconso_sans')), 'lead'))
    elif base:  # sans facture, la pose réelle seule : production servie, économie omise
        valeurs['production_annuelle_kwh'] = (production_annuelle_pour_kwc(kwc, base_production=base), SOURCE_POSE)
    return _bloc(marche, regles, valeurs, option='sans_batterie')


def _depuis_ci(lead, company, marche, regles, kwc):
    from apps.ventes.domain.etude_ci import etudier_ci
    etude = etudier_ci(company, {'mode': marche, 'taille_explicite_kwc': kwc}, lead=lead)
    bilan = etude.get('bilan') or {}
    economie = etude.get('economie_ci') or {}
    valeurs = {'kwc': ((etude.get('taille') or {}).get('retenue_kwc'), 'lead'),
               'production_annuelle_kwh': (bilan.get('production_kwh'), SOURCE_VILLE)}
    if economie.get('statut') == 'calcule':
        valeurs.update(economie_annee1_mad=((economie.get('economie_annee1') or {}).get('total_mad'), 'lead'),
                       autoconsommation_pct=(_pct(bilan.get('taux_autoconso')), 'lead'))
    return _bloc(marche, regles, valeurs, option='sans_batterie')


def chiffrer_conception(*, calepinage, company):
    """Le bloc ``chiffrage`` d'un calepinage (forme ``chiffrage_conception.json``)."""
    from apps.ventes.domain.creation import mode_installation_declare
    from apps.ventes.domain.etude_schema import MARCHES_CI
    from apps.ventes.domain.regles_calcul import REGLES_COURANTES

    marche, regles = None, REGLES_COURANTES
    try:
        devis = calepinage.devis if getattr(calepinage, 'devis_id', None) else None
        if devis is not None and devis.company_id != getattr(company, 'id', None):
            devis = None
        from apps.crm.selectors import get_company_lead
        lead = get_company_lead(company, calepinage.lead_id) if calepinage.lead_id else None
        marche = mode_installation_declare(devis, lead, defaut='residentiel')
        if marche == 'agricole':
            return _bloc(marche, regles, {}, motif=MOTIF_AGRICOLE, etat='non_servi')
        if devis is not None:
            return _depuis_devis(devis, marche)
        if lead is None:
            return _bloc(marche, regles, {}, motif=MOTIF_SANS_LEAD, etat='non_servi')
        from apps.ventes.domain.geometrie import lire_layout
        kwc = lire_layout(calepinage.roof_layout).kwc or None
        if kwc is None:
            return _bloc(marche, regles, {}, motif=MOTIF_KWC)
        if marche in MARCHES_CI:
            return _depuis_ci(lead, company, marche, regles, kwc)
        return _depuis_lead(calepinage, lead, company, marche, regles, kwc)
    except Exception:  # noqa: BLE001 — lecture servie à l'atelier, jamais bloquante (D-ENF22-BLE001)
        logger.warning('chiffrage de la conception indisponible (calepinage %s)',
                       getattr(calepinage, 'pk', None), exc_info=True)
        return _bloc(marche or 'residentiel', regles, {}, motif=MOTIF_ECHEC, etat='indisponible')
