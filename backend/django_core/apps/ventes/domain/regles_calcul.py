"""Règles de calcul d'un rendu de devis — « nouveaux rendus seulement ».

Décision fondateur (08/10/2026) : les corrections du moteur qui changent des
chiffres imprimés (AMOT8…AMOT60, ADEV28) ne s'appliquent qu'aux NOUVEAUX
rendus. Un devis déjà envoyé à la date de la migration 0136 porte
``regles_calcul = 1`` et continue d'être rendu (PDF, ``/proposal``, page
publique, cartes de tailles) avec les règles d'origine : le client relit
exactement ce qu'il a reçu. Tout autre devis (brouillons, devis créés ensuite,
révisions V2) porte 2.

Pourquoi un drapeau et pas un PDF figé : rien n'est figé aujourd'hui —
``/proposal`` re-rend à chaque appel (``persist=False``) et
``cle_pdf_a_jour`` re-rend dès que l'empreinte du dict de rendu change, ce que
fait mécaniquement toute correction de code. Le drapeau est lu au seul endroit
où le calcul diverge ; c'est le même moteur, jamais un second.
"""

REGLES_ORIGINE = 1
REGLES_CORRIGEES = 2


def calcul_corrige(devis) -> bool:
    """Vrai si ce devis est rendu avec les règles corrigées.

    ``None`` (pas de devis) ou un objet sans le champ (doublure de test,
    ``SimpleNamespace``) suit les règles corrigées : seules les lignes
    explicitement marquées 1 en base gardent l'ancien calcul.
    """
    valeur = getattr(devis, 'regles_calcul', REGLES_CORRIGEES)
    try:
        return int(valeur) >= REGLES_CORRIGEES
    except (TypeError, ValueError):
        return True
