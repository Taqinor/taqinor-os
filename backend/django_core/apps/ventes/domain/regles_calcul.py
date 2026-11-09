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
#: Niveau 5 (D-CI-SENSIB-ENVOYES, « nouveaux rendus seulement », 30/10/2026) :
#: retour de l'option « avec batterie » d'un devis C&I non accepté
#: (ERR-CEC6-RETOUR-AVEC-BATTERIE-PERDU) et curseur de stockage ancré sur le TTC
#: du devis (ERR-AMOT59-CURSEUR-STOCKAGE-PRIX). Le niveau 4 est en production
#: depuis le matin : un devis envoyé au niveau 4 garde ses chiffres. La
#: migration 0144 laisse à 4 tout devis non brouillon. Porte aussi
#: D-CI-BATTERIE-NON-RENTABLE (fondateur 30/10/2026) : une option C&I « avec
#: batterie » hors de la règle marginale des 10 ans est MONTRÉE (meilleur
#: groupe de modules, ``batterie_rentable: false``, l'offre réseau reste
#: recommandée) au lieu d'être cachée — un devis de niveau ≤ 4 la cache encore.
REGLES_RETOURS_3010B = 5
#: Niveau 6 (D-ENF-ARRONDI-PDF, fondateur 30/10/2026, « nouveaux rendus
#: seulement ») : l'argent AFFICHÉ par le moteur de devis (cartes d'option,
#: totaux multi-villa, prix au kWc, économies, cumul 25 ans des tailles…) est
#: arrondi MOITIÉ VERS LE HAUT (``core.money.quantize_mad``) au lieu de
#: l'arrondi bancaire de ``round()`` — un écart d'une unité, sur les seules
#: valeurs exactement à moitié. La migration 0145 laisse à 5 tout devis non
#: brouillon : il garde l'arrondi qu'il a reçu (``montants.arrondi_affichage``).
REGLES_ARRONDI_3010 = 6
#: Niveau 7 (écarts de la contre-visite AMOT du 31/10/2026, C-AMOT-VER-003/006,
#: « nouveaux rendus seulement ») : le payback du curseur de stockage
#: (AMOT103), de l'échelle batterie (AMOT102) et de la carte « avec » de repli
#: (AMOT107) suit la définition de ``roi_a`` (part stockée 0, rendement du
#: devis, provision d'onduleur réelle). La migration 0146 laisse à 6 tout devis
#: non brouillon : il garde les paybacks qu'il a reçus.
REGLES_ECARTS_3110 = 7
#: Niveau 8 (contre-visite AGNR du 01/11/2026, C-AGNR-VER-007, AGNR54,
#: « nouveaux rendus seulement ») : la consommation de TOUS les lecteurs
#: publics (estimation mois par mois, journée type, couverture batterie,
#: simulateur, repli de ``monthly_consumption``) est résolue par
#: ``etude_horaire.profil_conso_du_devis`` (factures écran, kWh déclaré
#: CAD166, barème société) — la même série que l'étude. La migration 0147
#: laisse à 7 tout devis non brouillon : il garde la page qu'il a reçue.
#: Porte aussi AGNR52 : les % d'échéancier imprimés (puce CGV, marqueur C&I,
#: cases agricoles) sont dérivés des montants servis, branches MAD dès 2 tranches.
REGLES_CONSO_PUBLIQUE_0111 = 8
#: Niveau 9 (contre-visite AMOT du 01/11/2026, C-AMOT-VER-040/030, AMOT116 et
#: AMOT115, « nouveaux rendus seulement ») : un devis C&I dont la consommation
#: est connue ne demande plus « vos 12 dernières factures » mais nomme le
#: manque réel (contrat d'électricité, horaires d'activité) ; en base « deux »,
#: chaque carte d'option imprime l'économie TTC à côté de la HT. La migration
#: 0148 laisse à 8 tout devis non brouillon (drapeau de rendu
#: ``regles_ecarts_0111_historique``) : il garde la phrase et les cartes reçues.
REGLES_ECARTS_0111 = 9
#: Niveau 10 (ADVS5/ADVS6, D-ADVS-3, 02/11/2026, « nouveaux rendus seulement ») :
#: UNE règle range chaque ligne dans ses options (``utils.options.panier_de_ligne`` :
#: variante, rôle stocké, tout accessoire de batterie dans « avec » seulement,
#: mots-clés en repli), pour le PDF, la page et l'argent du noyau. La migration
#: 0149 laisse à 9 tout devis non brouillon : il garde ses deux répartitions
#: d'hier (moteur : rôle seul ; noyau : variante puis mots-clés), écart compris.
REGLES_PANIER_UNIQUE_0211 = 10
#: Niveau 11 (ADVS3, D-ADVS-4, 03/11/2026, « nouveaux rendus seulement ») : un TTC à
#: moins d'1 MAD sous une centaine y remonte au lieu de perdre 100 MAD. La migration
#: 0151 laisse tout devis non brouillon à son niveau : il garde le total reçu.
#: Porte aussi AGNR42-D6 : facture annuelle de la source « étude horaire » = somme exacte
#: arrondie une fois (factures hiver/été décimales : 17 010 et non 17 016).
#: Porte aussi ERR-CADV83-COUVERTURES : la réserve « prix révisable au-delà » sur les
#: couvertures (dessous : ``regles_validite_historique``, la pastille reçue).
REGLES_CENTAINE_0311 = 11
#: AMOT118 (C-AMOT-VER4-010, 04/11/2026) — niveau 12, contrat UNIQUE des correctifs
#: de chiffres de la contre-visite AMOT du 04/11 (AMOT120 provision d'onduleur
#: hors réseau, AMOT121 port batterie off-grid, AMOT122 branche d'échéancier,
#: AMOT123 économie TTC C&I, AMOT126 une-page C&I en ``fmt_dirhams``). La migration
#: 0153 ne passe que les brouillons jamais envoyés de 11 à 12 : un envoyé garde son rendu.
REGLES_ECARTS_0411 = 12
#: Niveau posé sur un devis neuf (défaut du modèle ``Devis.regles_calcul``).
REGLES_COURANTES = REGLES_ECARTS_0411


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
