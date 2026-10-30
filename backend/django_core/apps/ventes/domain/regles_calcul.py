"""Règles de calcul d'un rendu de devis — « nouveaux rendus seulement ».

Décision fondateur (08/10/2026) : les corrections du moteur qui changent des
chiffres imprimés (AMOT8…AMOT60, ADEV28) ne s'appliquent qu'aux NOUVEAUX
rendus. Un devis déjà envoyé à la date de la migration 0138 porte
``regles_calcul = 1`` et continue d'être rendu (PDF, ``/proposal``, page
publique, cartes de tailles) avec les règles d'origine : le client relit
exactement ce qu'il a reçu. Tout autre devis (brouillons, devis créés ensuite,
révisions V2) porte 2.

Niveau 3 (corrections résidentielles du 27/10/2026, D-RES-2710-1 ombrage du
calepinage dans le moteur horaire, D-RES-2710-2 voiture électrique déjà
possédée) : la migration 0142 laisse à 2 tout devis non brouillon (envoyé
après le 08/10) et passe les brouillons et tout devis neuf à 3. Ces
corrections se branchent sur ``regles_au_moins(devis, REGLES_CORRIGEES_2710)``
— jamais sur ``calcul_corrige``, qui reste vrai dès le niveau 2 (les gardes
existantes ne bougent pas).

Pourquoi un drapeau et pas un PDF figé : rien n'est figé aujourd'hui —
``/proposal`` re-rend à chaque appel (``persist=False``) et
``cle_pdf_a_jour`` re-rend dès que l'empreinte du dict de rendu change, ce que
fait mécaniquement toute correction de code. Le drapeau est lu au seul endroit
où le calcul diverge ; c'est le même moteur, jamais un second.
"""

REGLES_ORIGINE = 1
REGLES_CORRIGEES = 2
REGLES_CORRIGEES_2710 = 3
#: Niveau 4 (D-CI-SENSIB-ENVOYES, fondateur 30/10/2026) : sensibilités C&I du
#: scénario production par le moteur du central (ERR-CI-SENSIBILITE-P90-INVERSEE).
#: La migration 0143 laisse à 3 tout devis non brouillon : il garde son tableau.
REGLES_SENSIBILITES_3010 = 4
#: Niveau posé sur un devis neuf (défaut du modèle ``Devis.regles_calcul``).
REGLES_COURANTES = REGLES_SENSIBILITES_3010


def regles_au_moins(devis, niveau: int) -> bool:
    """Vrai si ce devis est rendu avec les règles de ``niveau`` ou plus récentes.

    ``None`` (pas de devis) ou un objet sans le champ (doublure de test,
    ``SimpleNamespace``) suit les règles courantes : seules les lignes
    explicitement marquées à un niveau inférieur en base gardent l'ancien
    calcul.
    """
    valeur = getattr(devis, 'regles_calcul', REGLES_COURANTES)
    try:
        return int(valeur) >= niveau
    except (TypeError, ValueError):
        return True


def calcul_corrige(devis) -> bool:
    """Vrai si ce devis est rendu avec les règles corrigées.

    ``None`` (pas de devis) ou un objet sans le champ (doublure de test,
    ``SimpleNamespace``) suit les règles corrigées : seules les lignes
    explicitement marquées 1 en base gardent l'ancien calcul.
    """
    return regles_au_moins(devis, REGLES_CORRIGEES)
