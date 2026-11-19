"""Copilote vague 2 (lane VAD) — lectures COMPACTES de la vente pour l'assistant.

Lectures pures (aucune écriture) servies par les vues minces de
``views/assistant.py`` et, pour le point du matin, par :func:`brief_ventes`
(sélecteur PUBLIC lu par ``apps/crm``). Chaque lecture compose les calculs
EXISTANTS (``vente_facturation.etat_vente``, le recouvrement de
``apps.facturation.recouvrement``) : aucun montant n'est recalculé ici.

Délibérément ABSENTS de toute sortie : prix d'achat, marge, coût, téléphone et
e-mail du client (décision D-W2-Q6 ; contrats ``assistant_*.json``).
"""
from decimal import Decimal, ROUND_HALF_UP

#: Au plus cinq factures dans l'état compact d'une vente (les plus récentes).
FACTURES_MAX = 5
#: Statuts d'une facture émise (reste dû réclamable).
STATUTS_EMIS = ('emise', 'en_retard')


def texte_montant(valeur):
    """Un montant en texte décimal à deux décimales (``"15000.00"``)."""
    return str(Decimal(str(valeur or 0)).quantize(Decimal('0.01'),
                                                  rounding=ROUND_HALF_UP))


def nom_du_client(client):
    """« Nom Prénom » du client (même forme que la liste des relances)."""
    if client is None:
        return ''
    return f"{client.nom or ''} {client.prenom or ''}".strip()


def lien_devis(devis_id):
    """L'écran du devis (table ``agent/contract_samples/assistant_ecrans.json``)."""
    return f'/ventes/devis?devis={devis_id}'


def lien_facture(facture_id):
    """L'écran de la facture (même table)."""
    return f'/ventes/factures?facture={facture_id}'


# ── VAD1 — l'état compact d'une vente ───────────────────────────────────────

def _factures_compactes(etat, devis):
    """Les ``FACTURES_MAX`` dernières factures de l'état, avec leur reste dû
    (``Facture.montant_du`` d'une facture émise ; 0 sinon)."""
    from apps.facturation.selectors import factures_avec_montant_du
    from .models import Facture

    dernieres = list(etat.get('factures') or [])[-FACTURES_MAX:]
    objets = {f.pk: f for f in factures_avec_montant_du(Facture.objects.filter(
        pk__in=[f['id'] for f in dernieres], company_id=devis.company_id))}
    compactes = []
    for f in dernieres:
        objet = objets.get(f['id'])
        du = (objet.montant_du if objet is not None
              and f['statut'] in STATUTS_EMIS else 0)
        compactes.append({
            'facture_id': f['id'], 'reference': f['reference'],
            'nature': f['nature'], 'statut': f['statut'],
            'total_ttc': f['total_ttc'], 'montant_paye': f['montant_paye'],
            'montant_du': texte_montant(du),
            'date_emission': f['date_emission'],
        })
    return compactes


def _a_faire_vente(etat, factures):
    """Le geste suivant, ensemble FERMÉ : facturer | emettre_brouillon |
    encaisser | reviser | rien (``reviser`` : pas la tête de chaîne)."""
    if not etat['est_tete']:
        return 'reviser'
    if any(f['statut'] == 'brouillon' for f in etat.get('factures') or []):
        return 'emettre_brouillon'
    if etat['prochaine_action'] != 'aucune' and not etat['raison_bloquee']:
        return 'facturer'
    if any(f['statut'] in STATUTS_EMIS and Decimal(f['montant_du']) > 0
           for f in factures):
        return 'encaisser'
    return 'rien'


def vente_etat_compacte(devis, user):
    """L'état COMPACT de la vente de ``devis`` (contrat
    ``assistant_vente_etat.json``) : ``etat_vente`` réduit, montants en texte,
    cinq factures au plus, ``a_faire`` et ``lien``."""
    from .vente_facturation import etat_vente

    etat = etat_vente(devis, user)
    factures = _factures_compactes(etat, devis)
    validite = getattr(devis, 'date_validite', None)
    return {
        'etat': etat,
        'client': nom_du_client(getattr(devis, 'client', None)),
        'date_validite': validite.isoformat() if validite else None,
        'factures': factures,
        'a_faire': _a_faire_vente(etat, factures),
        'lien': lien_devis(devis.pk),
    }
