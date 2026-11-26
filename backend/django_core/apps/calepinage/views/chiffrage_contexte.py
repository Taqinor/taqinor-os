"""ACAL993 — le bloc ``chiffrage`` du contexte de conception.

Les grandeurs que le client lira sur son devis (kWc, production année 1,
économie année 1 et son option), lues par LA porte de ventes
(``apps.ventes.services.chiffrer_conception``, contrat
``apps/ventes/contract_samples/chiffrage_conception.json``) : aucun calcul de
production ni d'argent ici. Servi à l'OUVERTURE de l'atelier
(``design-context``), jamais à chaque geste. Sans lead : ``non_servi`` et son
motif ; une erreur du moteur : ``indisponible`` (la porte ne lève jamais).
Avec ``?devis=<B>`` (ACON80), le chiffrage lit le devis ET le document de la
VARIANTE servie, jamais ceux du calepinage de base.
"""
import copy


#: D-ACAL-106 — le motif d'un montant retenu pour un lecteur sans devis.
MOTIF_SANS_DEVIS = "montant réservé aux comptes qui lisent les devis"


def avec_chiffrage(contexte, calepinage, user=None):
    """Le contexte de conception + ``chiffrage`` ; les clés existantes intactes.

    D-ACAL-106 — un lecteur SANS ``ventes_voir`` (le Technicien qui fait le
    relevé) ne reçoit aucun montant : l'économie en MAD est ``non_servi``
    (motif dans ``omissions``) et la facture du lead est ``null`` — mêmes
    formes que le contrat sert déjà sans facture.
    """
    from apps.ventes.services import chiffrer_conception

    servi = dict(contexte, chiffrage=chiffrer_conception(
        calepinage=_conception_servie(contexte, calepinage),
        company=getattr(calepinage, 'company', None)))
    servi = servi if _lit_les_devis(user) else _sans_montants(servi)
    return servi if _nomme_les_devis(user) else _sans_devis_nomme(servi)


def _nomme_les_devis(user):
    """Lot 8, relecture finale (D-ACAL-106) — LA garde qui décide si un devis peut être NOMMÉ à ce
    lecteur : ``services.devis.lit_les_devis``, celle que la vue passe à ``devis_apercu._caviarder``."""
    from ..services.devis import lit_les_devis

    return user is None or lit_les_devis(user)


def _sans_devis_nomme(contexte):
    """``cible.devis_agricole`` (``{id, reference}``, ACAL1268) devient ``{id: null, reference: null}`` :
    l'écran dit qu'un devis agricole existe, sans le nommer ni le lier ; le champ de panneaux repris du
    devis reste (la pose en a besoin). Sans devis agricole (``null``) : inchangé."""
    cible = contexte.get('cible')
    if not isinstance(cible, dict) or cible.get('devis_agricole') is None:
        return contexte
    return dict(contexte, cible=dict(cible, devis_agricole={'id': None, 'reference': None}))


def _lit_les_devis(user):
    from core.permissions import _user_has_or_legacy

    return user is None or _user_has_or_legacy(user, 'ventes_voir')


def _sans_montants(contexte):
    chiffrage = dict(contexte.get('chiffrage') or {})
    if 'economie_annee1_mad' in chiffrage:
        chiffrage['economie_annee1_mad'] = {
            'valeur': None, 'unite': 'MAD', 'source': None,
            'etat': 'non_servi', 'option': None}
        omissions = [o for o in chiffrage.get('omissions') or []
                     if o.get('grandeur') != 'economie_annee1_mad']
        chiffrage['omissions'] = omissions + [
            {'grandeur': 'economie_annee1_mad', 'motif': MOTIF_SANS_DEVIS}]
    servi = dict(contexte, chiffrage=chiffrage)
    conso = contexte.get('consommation_lead')
    if isinstance(conso, dict) and 'facture_mensuelle_mad' in conso:
        servi['consommation_lead'] = dict(conso, facture_mensuelle_mad=None)
    return servi


def _conception_servie(contexte, calepinage):
    """Le calepinage tel que le contexte le sert : sa variante (devis et
    document) quand ``contexte['variante']`` est posée, sinon lui-même.
    Copie en mémoire, jamais enregistrée."""
    variante = contexte.get('variante')
    if not variante:
        return calepinage
    servi = copy.copy(calepinage)
    servi.devis_id = variante.get('devis')
    servi.roof_layout = (contexte.get('geometrie') or {}).get(
        'roof_layout', calepinage.roof_layout)
    return servi
