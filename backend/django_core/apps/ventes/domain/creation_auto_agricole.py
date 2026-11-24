"""Le devis automatique AGRICOLE (déplacé tel quel de ``creation_auto.py``).

Le dispatcher ``build_devis_auto`` reste dans ``creation_auto.py``.
NOM DU LOGGER FIGÉ sur ``apps.ventes.services``.
"""
from decimal import Decimal
import logging


logger = logging.getLogger("apps.ventes.services")


#: AGR124 — refus D-AGR-4 : le relevé du point d'eau d'abord.
MESSAGE_RELEVE_POINT_EAU = (
    "Relevé du point d'eau à faire avant le devis : le niveau d'eau et le "
    "débit du forage se mesurent lors d'une visite technique.")


def _fr_nombre(valeur):
    if valeur is None:
        return '?'
    texte = ('%.1f' % float(valeur)).rstrip('0').rstrip('.')
    return texte.replace('.', ',')


def _build_devis_auto_agricole(*, lead, user, company, taux_tva=None,
                               remise_globale=Decimal('0'), journal_auto=None,
                               target_kwc=None, conception=None, resultat_moteur=None):
    """AGR124 — devis automatique AGRICOLE (pompage) par le serveur.

    Entrées : ``crm.selectors.entrees_pompage_du_lead`` (AGR404), lues par
    ``pompage.etudier_pompage`` — jamais une colonne du lead lue ici. Refus
    ``AutoDevisError(field=…)`` : données manquantes (``devis_auto.
    champs_requis``, AGR403), relevé du point d'eau requis (D-AGR-4), HMT ou
    débit introuvables, aucune pompe chiffrable. Chaîne : ``etudier_pompage``
    → taille Recommandée + kit minimum (afficheur par défaut) → devis
    BROUILLON (numérotation ``utils/references.py``, lignes par l'écrivain
    unique) → étude v2 écrite UNE fois par le rafraîchisseur (AGR123). Les
    entrées carburant du lead partent dans ``saisies_economie_pompage``
    (provenance ``lead``). Le type du lead n'est JAMAIS changé (D-AGR-9) ;
    aucun statut touché (règle #4). ``journal_auto['alertes']`` reçoit les
    alertes de l'étude et les articles « prix à renseigner » omis.

    ADEV142 — ``conception`` (version courante, à jour) : ses blocs sont
    apportés à la création ; la décision est celle que le moteur vient de
    prendre dans CETTE requête (``resultat_moteur.decision_devis``), sinon UN
    appel de ``decider_agricole`` compose les lignes."""
    # AGNR39 — une puissance cible n'a aucun sens au pompage (le champ découle
    # de la pompe) : refusée en la NOMMANT (400), jamais ignorée en silence.
    if target_kwc not in (None, ''):
        from rest_framework.exceptions import ValidationError
        raise ValidationError({'target_kwc': (
            "La puissance cible ne s'applique pas au pompage : le champ "
            "solaire découle de la pompe retenue (HMT et débit du lead).")})
    # APAR49 — taux absent ⇒ taux STANDARD de la société (jamais 20 codé).
    if taux_tva is None:
        from apps.ventes.utils.company_settings import tva_standard
        taux_tva = tva_standard(company)
    from apps.crm.services import resolve_client_for_lead
    from apps.ventes.conception.decisions import decider_agricole
    from apps.ventes.domain.pompage import etude_precalculee
    from apps.ventes.models import Devis

    # ADEV160 (D-ACAL-97) — champs manquants, relevé du point d'eau,
    # alimentation, ``etudier_pompage``, refus HMT / débit / forage et kit
    # minimum chiffré : la décision PURE de ``conception/decisions.py`` (une
    # définition, appelée ici et par le moteur unique).
    decision = ((getattr(resultat_moteur, 'decision_devis', None) if conception is not None else None)
                or decider_agricole(lead=lead, company=company))
    sortie, lignes, omises, pompe = (decision.sortie, decision.lignes,
                                     decision.omises, decision.pompe)
    client = resolve_client_for_lead(lead)
    etude = blocs_et_creation(conception, etude_params_creation_agricole(decision, lead))

    def _create(ref):
        return Devis.objects.create(
            company=company, reference=ref, client=client, lead=lead,
            statut=Devis.Statut.BROUILLON, created_by=user,
            taux_tva=taux_tva, devise=devise_par_defaut(company),
            remise_globale=remise_globale, mode_installation='agricole',
            etude_params=etude)

    with etude_precalculee(lead, sortie):
        devis = _ecrire_devis_auto_par_pipeline(
            company=company, user=user, lead=lead, creer=_create,
            lignes=lignes, mode_installation='agricole')
    if journal_auto is not None:
        journal_auto['alertes'] = alertes_journal_agricole(sortie, omises)
    logger.info('Auto-devis agricole %s: pompe %s (lead %s, company %s)',
                devis.reference, pompe.get('nom'), getattr(lead, 'pk', '?'),
                getattr(company, 'id', '?'))
    return devis


def etude_params_creation_agricole(decision, lead):
    """ADEV133 — l'``etude_params`` posé à la création agricole (corps d'étude,
    entrées carburant du lead) : partagé avec le moteur unique."""
    from apps.ventes.domain.pompage import saisies_economie_pompage_du_lead
    etude = dict(decision.corps)
    saisies = saisies_economie_pompage_du_lead(lead)
    if saisies:
        etude['saisies_economie_pompage'] = saisies
    return etude


def alertes_journal_agricole(sortie, omises):
    """ADEV133 — les alertes du journal d'un devis automatique agricole (étude,
    articles « prix à renseigner » omis) : partagées avec le moteur unique."""
    alertes = [dict(a) for a in (sortie.get('alertes') or [])]
    for designation in omises:
        alertes.append({
            'code': 'article_prix_a_renseigner', 'champ': 'kit',
            'message': ('« %s » non ajouté au devis : prix à renseigner '
                        'au catalogue (jamais un article gratuit).'
                        % designation)})
    return alertes


# ── PONTS M3 : noms hébergés ailleurs ────────────────────────────────────────
# Imports EN BAS DE FICHIER, visant le module qui PORTE chaque corps.
from apps.ventes.domain.creation_auto import (  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    _ecrire_devis_auto_par_pipeline,
    blocs_et_creation,
)
from apps.ventes.domain.creation import devise_par_defaut  # noqa: E402 — anti-cycle (D-ENF22)
