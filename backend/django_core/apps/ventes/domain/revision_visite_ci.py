"""CORC2 — le devis C&I RÉVISÉ APRÈS LA VISITE TECHNIQUE (27/10/2026).

Le devis automatique C&I est un devis PRÉLIMINAIRE (fondateur 26/10/2026 :
câble DC = 2 × chaînes × 30 m, câble AC = 30 m par onduleur, toit inconnu =
toit plat lesté ; « les prix pourront être ajustés après la visite
technique »). Une fois la visite C&I VALIDÉE, ses mesures (longueurs de
cheminement, couverture, surface, pente, charge admissible, tension,
puissance souscrite) entrent dans l'étude (``etude_ci._couche_visite``) —
mais le rafraîchisseur n'écrit jamais de LIGNES (règle CIQ119). Ce service
est le geste qui manquait : il RECOMPOSE les lignes C&I avec les mesures.

* brouillon → recomposé SUR PLACE (même référence) ;
* envoyé / accepté / refusé / expiré → ``revision.reviser_devis`` crée la
  V+1 (brouillon), puis elle est recomposée : la V1 garde ce que le client a
  reçu ;
* la TAILLE vendue (kWc de l'offre réseau) est gardée — la visite ajuste
  quantités, longueurs, pose et prix, jamais la puissance proposée ;
* aucun statut n'est écrit (règle #4) ; la remise globale et l'en-tête sont
  intouchés.

Contrat : ``contract_samples/devis_revise_visite.json`` (CSV consomme).
"""
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

MODES_CI = ('commercial', 'industriel')
MESSAGE_PAS_CI = ("Seul un devis commercial ou industriel se révise après la "
                  "visite technique C&I.")
MESSAGE_SANS_VISITE = ("Aucune visite technique C&I validée sur ce lead : "
                       "validez la visite (bureau d'études) avant de préparer "
                       "le devis révisé.")
MESSAGE_SANS_LEAD = ("Ce devis n'est rattaché à aucun lead : la visite "
                     "technique ne peut pas être lue.")


class RevisionVisiteError(Exception):
    """Refus nommé : ``message`` (français, au vendeur) + ``champ``."""

    def __init__(self, message, champ):
        super().__init__(message)
        self.message = message
        self.champ = champ


def _cle_ligne(designation, variante):
    return ((designation or '').strip(), variante or '')


def _photo_lignes(devis):
    """``{(désignation, variante): (quantité, prix unitaire)}`` des lignes
    produit du devis (sections et notes exclues)."""
    photo = {}
    for ligne in devis.lignes.all():
        if getattr(ligne, 'type_ligne', 'produit') != 'produit':
            continue
        cle = _cle_ligne(ligne.designation, getattr(ligne, 'variante', ''))
        quantite, prix = photo.get(cle, (Decimal('0'), ligne.prix_unitaire))
        photo[cle] = (quantite + Decimal(str(ligne.quantite or 0)), ligne.prix_unitaire)
    return photo


def _diff(avant, apres):
    """Lignes changées, en clair pour le vendeur : ``{designation, variante,
    avant, apres}`` où avant/apres = ``{quantite, prix_unitaire_ht}`` ou
    ``None`` (ligne ajoutée / retirée)."""
    def forme(valeur):
        if valeur is None:
            return None
        return {'quantite': str(valeur[0]), 'prix_unitaire_ht': str(valeur[1])}
    changees = []
    for cle in sorted(set(avant) | set(apres)):
        if avant.get(cle) != apres.get(cle):
            changees.append({'designation': cle[0], 'variante': cle[1],
                             'avant': forme(avant.get(cle)),
                             'apres': forme(apres.get(cle))})
    return changees


def _mesures_utilisees(etude):
    """Les entrées que la visite a fournies : ``{cle, valeur, provenance}``."""
    return [{'cle': cle, 'valeur': entree.get('valeur'), 'provenance': entree.get('provenance')}
            for cle, entree in sorted((etude.get('entrees_resolues') or {}).items())
            if ((entree or {}).get('provenance') or {}).get('origine') == 'mesure_visite']


def reviser_devis_apres_visite(devis, *, user=None):
    """CORC2 — recompose le devis C&I avec les mesures de la visite validée.

    Rend ``{devis, cree, lignes_changees, mesures_utilisees, alertes}`` ;
    lève :class:`RevisionVisiteError` (refus nommé) ou laisse passer
    ``revision.RevisionError`` (version déjà remplacée)."""
    from django.db import transaction

    from apps.visites.selectors import releve_ci_pour_lead

    from .etude_ci import (entrees_pour_etude_params, etudier_ci,
                           refus_devis_auto_ci)
    from .etude_ci_batterie import lignes_des_options
    from .etude_schema import ECRAN, ecrire
    from .etudes import puissances_etude_horaire
    from .pipeline import (MODE_ECRIRE, MODE_RAFRAICHIR, ORIGINE_AUTO,
                           IntentionDevis, appliquer)
    from .revision import reviser_devis
    from .scenario import SCENARIO_LES_DEUX, SCENARIO_SANS_BATTERIE

    mode = (getattr(devis, 'mode_installation', '') or '').lower()
    if mode not in MODES_CI:
        raise RevisionVisiteError(MESSAGE_PAS_CI, 'mode_installation')
    lead = getattr(devis, 'lead', None)
    if lead is None:
        raise RevisionVisiteError(MESSAGE_SANS_LEAD, 'lead')
    if not releve_ci_pour_lead(lead):
        raise RevisionVisiteError(MESSAGE_SANS_VISITE, 'visite')

    cree = devis.statut != 'brouillon'
    cible = reviser_devis(devis, user=user) if cree else devis
    kwc_avec, kwc_sans = puissances_etude_horaire(cible)
    taille = kwc_sans or kwc_avec
    company = cible.company
    etude = etudier_ci(company, {'mode': mode, 'taille_explicite_kwc': taille},
                       devis=cible, lead=lead)
    refus = refus_devis_auto_ci(etude)
    if refus:
        raise RevisionVisiteError(*refus)
    lignes, scenario = lignes_des_options(etude, lead)
    if not any(ligne['produit_id'] for ligne in lignes):
        raise RevisionVisiteError('Aucun article C&I chiffré à composer.', 'composition')

    avant = _photo_lignes(cible)
    composition = [
        {'produit': ligne['produit_id'], 'designation': ligne['designation'],
         'quantite': str(ligne['quantite']), 'prix_unitaire': str(ligne['prix_unitaire']),
         'ordre': ordre,
         **({'variante': ligne['variante']} if ligne.get('variante') else {})}
        for ordre, ligne in enumerate(lignes)]
    entrees = entrees_pour_etude_params(etude.get('entrees_resolues'))
    if scenario:
        entrees['scenario'] = scenario
        if scenario == SCENARIO_LES_DEUX:
            entrees['recommended_option'] = SCENARIO_SANS_BATTERIE
    with transaction.atomic():
        ecrire(cible, proprietaire=ECRAN, **entrees)
        appliquer(cible, IntentionDevis(
            origine=ORIGINE_AUTO, mode=MODE_ECRIRE, company=company, user=user,
            lead=lead, mode_installation=mode, composition=composition))
    appliquer(cible, IntentionDevis(
        origine=ORIGINE_AUTO, mode=MODE_RAFRAICHIR, company=company, user=user,
        lead=lead, mode_installation=mode, force_etudes=True))
    cible.refresh_from_db()
    alertes = [dict(a) for a in etude.get('alertes') or []
               if a.get('niveau') in ('alerte', 'bloquant')]
    logger.info('Devis C&I %s révisé après visite (%s)', cible.reference,
                'V+1' if cree else 'sur place')
    return {'devis': cible, 'cree': cree,
            'lignes_changees': _diff(avant, _photo_lignes(cible)),
            'mesures_utilisees': _mesures_utilisees(etude), 'alertes': alertes}
