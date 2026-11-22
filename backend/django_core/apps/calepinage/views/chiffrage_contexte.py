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


def avec_chiffrage(contexte, calepinage):
    """Le contexte de conception + ``chiffrage`` ; les clés existantes intactes."""
    from apps.ventes.services import chiffrer_conception

    return dict(contexte, chiffrage=chiffrer_conception(
        calepinage=_conception_servie(contexte, calepinage),
        company=getattr(calepinage, 'company', None)))


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
