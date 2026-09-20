"""Tarification contractuelle — quel prix s'applique à ce client.

Les listes de prix et leurs règles : le prix contractuel d'un produit pour
un client donné, la règle applicable (remise, majoration) et le prix qui en
sort, avec sa SOURCE (contrat, liste, standard).

QJR76 (M3) — DÉPLACEMENT PUR depuis ``apps/ventes/services.py``, dernier de la
vague : après lui, ``services.py`` n'est plus qu'une façade de ré-exports. Les
corps sont recopiés à l'identique ; la seule retouche possible est mécanique
(`from .x` → `from ..x`, MÊME cible).

ORDRE DE CHARGEMENT : ``services.py`` importe ``domain/`` à la toute fin ; un
module de ``domain/`` importe en BAS de fichier les noms qu'il lit ailleurs, et
il vise TOUJOURS le module qui porte le corps — jamais la façade.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` : des tests capturent ce nom.
"""
from decimal import Decimal, ROUND_HALF_UP


def _round2(x):
    """Arrondi MAD à 2 décimales, HALF_UP (comme le reste du module)."""
    return Decimal(x).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _regle_applicable(regles, produit, quantite):
    """XSAL2 — la règle la plus spécifique dont le palier est atteint.

    Ordre : spécificité de portée (produit > catégorie > marque > catalogue)
    d'abord, puis priorité explicite, puis palier le plus élevé atteint par
    `quantite`. Une règle inactive ou dont le palier n'est pas atteint est
    ignorée."""
    candidates = [
        r for r in regles
        if r.actif and r.matches_produit(produit) and quantite >= r.quantite_min
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda r: (r.specificite, r.priorite, r.quantite_min), reverse=True)
    return candidates[0]


def _appliquer_regle(regle, prix_base):
    """XSAL2 — applique une règle résolue au prix de base (jamais à
    `prix_achat`)."""
    if regle.type_regle == regle.TypeRegle.PRIX_FIXE:
        return _round2(regle.valeur)
    if regle.type_regle == regle.TypeRegle.REMISE_PCT:
        return _round2(prix_base * (1 - regle.valeur / 100))
    if regle.type_regle == regle.TypeRegle.FORMULE_SUR_PRIX_VENTE:
        return _round2(prix_base * regle.valeur)
    return _round2(prix_base)  # pragma: no cover - défensif, type inconnu


def _resolve_liste_prix(client):
    """NTCPQ4 — Sélectionne la liste de prix applicable à un client.

    Priorité : liste explicitement assignée au client (``client.liste_prix``)
    si elle est active > liste de la société correspondant au SEGMENT du client
    (la plus récente active) > aucune. Les listes hors fenêtre de validité ou
    archivées (``est_active`` False) ne sont JAMAIS retenues, même si leur
    segment correspond au client (NTCPQ4). Renvoie une ``ListePrix`` active ou
    ``None``."""
    if client is None:
        return None
    liste = getattr(client, 'liste_prix', None)
    if liste is not None and liste.est_active:
        return liste
    # Segment du client : champ dédié s'il existe, sinon type de client.
    segment = (getattr(client, 'segment_client', '')
               or getattr(client, 'type_client', '') or '')
    company_id = getattr(client, 'company_id', None)
    if segment and company_id is not None:
        from apps.ventes.models import ListePrix
        candidates = ListePrix.objects.filter(
            company_id=company_id, segment_client=segment, archived=False,
        ).order_by('-created_at')
        for candidate in candidates:
            if candidate.est_active:
                return candidate
    return None


def prix_applicable(*, produit, client=None, quantite=1):
    """XSAL1/XSAL2 — Prix unitaire résolu pour un produit/client/quantité.

    Ordre de résolution :
      1. `client.liste_prix` (si assignée et active) → règles de paliers/
         portée (XSAL2, la plus spécifique satisfaite par `quantite`) →
         sinon le prix de ligne fixe (`LignePrixListe`) → sinon
         `produit.prix_vente`.
      2. Sans liste (client=None, `liste_prix` vide, ou liste inactive) →
         `produit.prix_vente` (comportement historique, octet-identique).

    Ne renvoie et ne consulte JAMAIS `produit.prix_achat`. Renvoie un dict
    `{"prix": Decimal, "source": "liste"|"regle"|"standard",
    "liste_nom": str|None}` pour que l'appelant (endpoint XSAL3) puisse
    afficher le badge « Tarif : <nom de la liste> »."""
    quantite = Decimal(str(quantite or 1))
    prix_standard = produit.prix_vente

    liste = _resolve_liste_prix(client)
    if liste is None:
        return {'prix': prix_standard, 'source': 'standard', 'liste_nom': None}

    regles = list(liste.regles.filter(actif=True).select_related('produit'))
    regle = _regle_applicable(regles, produit, quantite)
    if regle is not None:
        prix_ligne = liste.lignes.filter(produit=produit).values_list(
            'prix_unitaire', flat=True).first()
        base = prix_ligne if prix_ligne is not None else prix_standard
        return {
            'prix': _appliquer_regle(regle, base),
            'source': 'regle',
            'liste_nom': liste.nom,
        }

    ligne = liste.lignes.filter(produit=produit).first()
    if ligne is not None:
        return {'prix': ligne.prix_unitaire, 'source': 'liste', 'liste_nom': liste.nom}

    return {'prix': prix_standard, 'source': 'standard', 'liste_nom': None}


def profondeur_remise_effective(devis, *, remise_globale=None):
    """AUD611 — la profondeur de remise RÉELLE du devis, en %.

    Le seuil d'approbation (T17) ne regardait que ``remise_globale``. Or un
    devis peut porter 0 % de remise globale et des remises de LIGNE cumulées
    bien au-delà du seuil : il partait alors au client sans passer par la
    moindre approbation. La remise de ligne et la remise globale sont le MÊME
    geste commercial vu de deux endroits ; le seuil doit voir leur effet
    combiné.

    Formule : ``1 − net / brut`` où ``brut`` est la somme des lignes AVANT
    toute remise et ``net`` la somme APRÈS remise de ligne PUIS remise globale.
    Elle se réduit exactement à ``remise_globale`` quand aucune ligne ne porte
    de remise — le comportement d'hier est donc préservé au centième.

    :param remise_globale: pourcentage global à considérer À LA PLACE de celui
        porté par l'instance (le garde d'envoi juge la valeur ENTRANTE, pas
        celle encore en base).

    Le résultat n'est JAMAIS inférieur à la remise globale : une donnée de
    ligne aberrante (remise négative, ligne à prix nul) ne peut pas AFFAIBLIR
    un seuil qui se déclenchait hier.
    """
    globale = Decimal(str(
        (remise_globale if remise_globale is not None
         else getattr(devis, 'remise_globale', 0)) or 0))
    lignes_liees = getattr(devis, 'lignes', None)
    if lignes_liees is None:
        return globale

    brut = Decimal('0')
    net_lignes = Decimal('0')
    for ligne in lignes_liees.all():
        if not ligne.compte_dans_totaux:
            continue
        if ligne.quantite is None or ligne.prix_unitaire is None:
            continue
        brut += Decimal(str(ligne.quantite)) * Decimal(str(ligne.prix_unitaire))
        # ``LigneDevis.total_ht`` PORTE déjà la remise de ligne : on ne
        # réimplémente pas la formule d'argent de `ventes`, on la consomme.
        net_lignes += Decimal(str(ligne.total_ht))
    if brut <= 0:
        return globale

    net = net_lignes * (Decimal('1') - globale / Decimal('100'))
    effective = ((Decimal('1') - net / brut) * Decimal('100')).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    return max(effective, globale)
