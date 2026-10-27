"""Selectors du module Achats (``apps.achats``).

Point d'entrée des LECTURES cross-app du domaine Achats (CLAUDE.md : les autres
apps lisent ``achats`` via ``apps.achats.selectors`` ou par string-FK, jamais via
``apps.achats.models``).

Volontairement vide pour l'instant : aucune autre app ne lit finement les
modèles achats fournisseurs (les lectures existantes passent par
``apps.stock.selectors``/``services``, shims transitoires ODX19). Ajouter ici une
fonction de lecture fine dès qu'une autre app en aura besoin — jamais un import
direct de ``apps.achats.models`` depuis l'extérieur.
"""


def bcf_du_chantier(installation):
    """Revue chantier 26/10/2026 — les BCF dont ``chantier_origine`` est ce
    chantier (tous statuts, annulés exclus), bornés à SA société, avec
    l'avancement de réception par ligne. AUCUN prix (D-ASTK-2 : le prix
    d'achat ne sort jamais d'ici). Lecture seule.

    Rend une liste de dicts (forme ``bons_commande`` du contrat
    ``installations/contract_samples/chantier_approvisionnement.json``) :
    ``{id, reference, statut, statut_display, fournisseur_id,
    fournisseur_nom, date_commande, date_livraison_prevue, nb_lignes,
    quantite_commandee, quantite_recue, lignes: [{produit_id, designation,
    quantite, quantite_recue}]}``."""
    from .models import BonCommandeFournisseur
    if installation is None or getattr(installation, 'pk', None) is None:
        return []
    bons = (BonCommandeFournisseur.objects
            .filter(company_id=installation.company_id,
                    chantier_origine_id=installation.pk)
            .exclude(statut=BonCommandeFournisseur.Statut.ANNULE)
            .select_related('fournisseur')
            .prefetch_related('lignes__produit')
            .order_by('date_creation', 'pk'))
    out = []
    for bon in bons:
        lignes = []
        for ligne in bon.lignes.all():
            lignes.append({
                'produit_id': ligne.produit_id,
                'designation': (ligne.designation
                                or (ligne.produit.nom if ligne.produit_id
                                    else '')),
                'quantite': ligne.quantite,
                'quantite_recue': ligne.quantite_recue,
            })
        out.append({
            'id': bon.pk,
            'reference': bon.reference,
            'statut': bon.statut,
            'statut_display': bon.get_statut_display(),
            'fournisseur_id': bon.fournisseur_id,
            'fournisseur_nom': (bon.fournisseur.nom if bon.fournisseur_id
                                else None),
            'date_commande': (bon.date_commande.isoformat()
                              if bon.date_commande else None),
            'date_livraison_prevue': (
                bon.date_livraison_prevue.isoformat()
                if bon.date_livraison_prevue else None),
            'nb_lignes': len(lignes),
            'quantite_commandee': sum(li['quantite'] for li in lignes),
            'quantite_recue': sum(li['quantite_recue'] for li in lignes),
            'lignes': lignes,
        })
    return out
