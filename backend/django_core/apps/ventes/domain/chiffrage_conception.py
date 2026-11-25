"""ACAL992 / ADEV153 — LA porte unique de chiffrage d'une conception (calepinage).

Forme : ``contract_samples/chiffrage_conception.json`` (ACAL991). AUCUN calcul :
le chiffrage est une LECTURE de la conception rangée du lead
(``ConceptionLead``, ``services.conception_ou_calcul`` : la version courante, ou
UNE relance mise en file quand il n'y en a pas) — ni ``calculer_etude_horaire``,
ni ``etudier_ci``, ni rendu du devis (D-ACAL-97 : un seul moteur, ses valeurs
gardées et lues partout). Agricole : non servi (le chiffrage se lit au devis).
Lecture seule ; ne lève jamais (``etat: 'indisponible'`` et son motif).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

UNITES = {'kwc': 'kWc', 'production_annuelle_kwh': 'kWh/an',
          'economie_annee1_mad': 'MAD', 'autoconsommation_pct': '%', 'couverture_pct': '%'}
MOTIF_FACTURE = 'renseignez la facture'  # D-ACAL-40
MOTIF_AGRICOLE = 'le chiffrage agricole se lit au devis'
MOTIF_SANS_LEAD = 'aucun lead lié : le chiffrage du devis ne peut pas être calculé'
MOTIF_ECHEC = 'chiffrage indisponible : calcul du devis en échec'
MOTIF_EN_COURS = 'premier calcul de la conception en cours'
SOURCE_POSE, SOURCE_VILLE, SOURCE_CONCEPTION = 'calepinage_enregistre', 'standard_ville', 'conception'
#: Les entrées de la conception qui disent qu'une consommation est CONNUE (D-ACAL-40).
ENTREES_FACTURE = ('facture_hiver', 'facture_ete', 'conso_mensuelle_kwh', 'bill_kwh', 'releve_conso')


def _bloc(marche, regles, valeurs, *, motif=MOTIF_FACTURE, etat='omis', option=None, motifs_propres=None):
    """Le contrat : ``valeurs`` = ``{grandeur: (valeur, source)}`` ; une
    grandeur absente prend ``etat`` et son motif (``motifs_propres[grandeur]`` d'abord)
    dans ``omissions``."""
    sortie, omissions = {'marche': marche, 'regles_calcul': regles}, []
    for cle, unite in UNITES.items():
        valeur, source = valeurs.get(cle, (None, None))
        servi = valeur is not None
        sortie[cle] = {'valeur': valeur, 'unite': unite,
                       'source': source if servi else None, 'etat': 'servi' if servi else etat}
        if not servi:
            omissions.append({'grandeur': cle, 'motif': (motifs_propres or {}).get(cle, motif)})
    economie = sortie['economie_annee1_mad']
    economie['option'] = option if economie['valeur'] is not None else None
    sortie['omissions'] = omissions
    return sortie


def _pct(fraction):
    return round(float(fraction) * 100, 1) if fraction is not None else None


def _valeur(table, cle):
    return (table.get(cle) or {}).get('valeur')


def _depuis_conception(conception, marche_du_lead):
    """Le bloc d'une conception rangée : ``valeurs[option retenue]`` lues telles quelles."""
    marche, regles = conception.get('marche') or marche_du_lead, conception.get('niveau_regles')
    if marche == 'agricole':
        return _bloc(marche, regles, {}, motif=MOTIF_AGRICOLE, etat='non_servi')
    if conception.get('etat') != 'complet':
        motif = (conception.get('refus') or {}).get('message') or MOTIF_ECHEC
        return _bloc(marche, regles, {}, motif=motif, etat='indisponible')
    option = conception.get('option_retenue') or 'sans'
    table = (conception.get('valeurs') or {}).get(option) or {}
    sur_la_pose = (table.get('production_annuelle') or {}).get('source') == 'pose'
    valeurs = {'kwc': (_valeur(table, 'puissance_kwc'), SOURCE_CONCEPTION),
               'production_annuelle_kwh': (_valeur(table, 'production_annuelle'),
                                           SOURCE_POSE if sur_la_pose else SOURCE_VILLE)}
    if any(cle in (conception.get('entrees_utilisees') or {}) for cle in ENTREES_FACTURE):  # D-ACAL-40
        valeurs['economie_annee1_mad'] = (_valeur(table, 'economies_annuelles'), SOURCE_CONCEPTION)
        valeurs['autoconsommation_pct'] = (_pct(_valeur(table, 'autoconsommation')), SOURCE_CONCEPTION)
        # ACAL2022/2023 — LA part production ÷ consommation de la conception (atelier et vue client la lisent).
        valeurs['couverture_pct'] = (_pct(_valeur(table, 'couverture')), SOURCE_CONCEPTION)
    return _bloc(marche, regles, valeurs, option='avec_batterie' if option == 'avec' else 'sans_batterie')


def chiffrer_conception(*, calepinage, company):
    """Le bloc ``chiffrage`` d'un calepinage (forme ``chiffrage_conception.json``)."""
    from apps.ventes.domain.creation import mode_installation_declare
    from apps.ventes.domain.regles_calcul import REGLES_COURANTES

    marche, regles = None, REGLES_COURANTES
    try:
        from apps.crm.selectors import get_company_lead
        lead = get_company_lead(company, calepinage.lead_id) if calepinage.lead_id else None
        marche = mode_installation_declare(lead, defaut='residentiel')
        if lead is None:
            return _bloc(marche, regles, {}, motif=MOTIF_SANS_LEAD, etat='non_servi')
        from apps.ventes.conception.service import conception_ou_calcul
        conception, _en_cours = conception_ou_calcul(company, calepinage.lead_id)
        if conception is None:  # première conception en file (ou impossible) : jamais un zéro
            return _bloc(marche, regles, {}, motif=MOTIF_EN_COURS)
        return _depuis_conception(conception, marche)
    except Exception:  # noqa: BLE001 — lecture servie à l'atelier, jamais bloquante (D-ENF22-BLE001)
        logger.warning('chiffrage de la conception indisponible (calepinage %s)',
                       getattr(calepinage, 'pk', None), exc_info=True)
        return _bloc(marche or 'residentiel', regles, {}, motif=MOTIF_ECHEC, etat='indisponible')
