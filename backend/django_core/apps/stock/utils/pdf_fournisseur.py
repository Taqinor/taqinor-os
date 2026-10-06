"""PDF du bon de commande FOURNISSEUR (N12) — INTERNE.

Réutilise l'approche WeasyPrint des factures (Jinja2 → HTML → PDF). Ce
document est destiné au fournisseur : il affiche légitimement les PRIX
D'ACHAT, car c'est le prix qu'on paie au fournisseur. Il ne doit JAMAIS être
exposé comme document client.
"""
from decimal import Decimal

from apps.ventes.utils.pdf import _company_context, _render_html, _html_to_pdf

# NTP2P25 — taux TVA STATUTAIRE marocain par défaut (biens courants, hors
# liste des taux réduits 7/10/14 %). `LigneBonCommandeFournisseur` ne porte
# PAS ENCORE de `taux_tva` par ligne (contrairement à XPUR17 côté
# `LigneFactureFournisseur`) : ce document interne affiche donc le total TVA
# calculé à ce taux STANDARD, toujours clairement labellisé « (taux
# standard) » — jamais présenté comme un montant fiscal définitif, et sans
# effet sur aucun autre total de l'OS (rapprochement 3 voies FG131 reste sur
# le HT).
TAUX_TVA_STANDARD_BCF = Decimal('20')


def _format_milliers(montant):
    """ASTK64 — « 1 080.00 » : séparateur de milliers espace, 2 décimales."""
    return f'{Decimal(montant):,.2f}'.replace(',', ' ')


def _format_taux(taux):
    """ASTK64 — « 10,8 » : taux de change sans zéros superflus, virgule."""
    texte = format(Decimal(taux).normalize(), 'f')
    return texte.replace('.', ',')


def _montants_document(bon_commande, lignes):
    """ASTK64 — montants de chaque ligne dans la DEVISE DU DOCUMENT.

    Un BCF en devise (EUR, USD…) imprime ce qui a été convenu avec le
    fournisseur : ``prix_achat_unitaire_devise`` (à défaut, la contre-valeur
    MAD ramenée au taux). Un BCF en MAD garde EXACTEMENT les valeurs
    historiques (``prix_achat_unitaire`` / ``total_achat``) : rendu
    inchangé. Renvoie ``(devise, en_devise, {ligne.id: {pu, total}},
    total_document)``."""
    from ..models import DeviseAchat

    devise = bon_commande.devise or DeviseAchat.MAD
    taux = bon_commande.taux_change
    en_devise = bool(devise != DeviseAchat.MAD and taux)
    montants = {}
    total = Decimal('0')
    for ligne in lignes:
        if en_devise:
            pu = ligne.prix_achat_unitaire_devise
            if pu is None:
                pu = (Decimal(ligne.prix_achat_unitaire or 0)
                      / Decimal(taux)).quantize(Decimal('0.01'))
            ligne_total = (Decimal(ligne.quantite or 0) * pu).quantize(
                Decimal('0.01'))
        else:
            pu = ligne.prix_achat_unitaire
            ligne_total = ligne.total_achat
        montants[ligne.id] = {'pu': pu, 'total': ligne_total}
        total += ligne_total
    if not en_devise:
        devise = DeviseAchat.MAD
    return devise, en_devise, montants, total


def build_bcf_context(bon_commande):
    """Contexte de rendu pour le PDF fournisseur."""
    from ..models import PrixFournisseur

    context = _company_context(company=bon_commande.company)
    context['bc'] = bon_commande
    lignes = list(bon_commande.lignes.select_related('produit').all())
    context['lignes'] = lignes
    context['total_achat'] = bon_commande.total_achat
    # ASTK64 — le document fournisseur est imprimé dans SA devise ; la
    # contre-valeur MAD (au taux du document) n'est qu'une mention.
    devise, en_devise, montants, total_document = _montants_document(
        bon_commande, lignes)
    context['devise_doc'] = devise
    context['en_devise'] = en_devise
    context['montants_ligne'] = montants
    context['total_document'] = (
        total_document if en_devise else context['total_achat'])
    if en_devise:
        context['contre_valeur_mad'] = _format_milliers(
            context['total_achat'] or 0)
        context['taux_change_affiche'] = _format_taux(
            bon_commande.taux_change)
    else:
        context['contre_valeur_mad'] = None
        context['taux_change_affiche'] = None

    # XPUR14 — code article fournisseur (imprimé sur le PDF pour éviter les
    # erreurs de préparation côté fournisseur). Best-effort : absent =
    # colonne vide (comportement historique inchangé).
    produit_ids = [ligne.produit_id for ligne in lignes if ligne.produit_id]
    refs = {}
    if produit_ids and bon_commande.fournisseur_id:
        refs = dict(
            PrixFournisseur.objects.filter(
                produit_id__in=produit_ids,
                fournisseur_id=bon_commande.fournisseur_id,
            ).exclude(ref_produit_fournisseur='')
            .values_list('produit_id', 'ref_produit_fournisseur'))
    context['ref_produit_fournisseur'] = {
        ligne.id: refs.get(ligne.produit_id, '') for ligne in lignes
    }
    # ZPUR8 — champs « Other Information » imprimés sur le PDF BCF (acheteur,
    # réf. fournisseur, incoterm/conditions de paiement, note de bas de
    # page). Vide = comportement historique inchangé (rien à afficher).
    acheteur_nom = ''
    if bon_commande.acheteur_id:
        acheteur = bon_commande.acheteur
        acheteur_nom = acheteur.get_full_name() or acheteur.username
    context['acheteur_nom'] = acheteur_nom
    context['ref_fournisseur'] = bon_commande.ref_fournisseur or ''
    context['incoterm'] = bon_commande.incoterm or ''
    context['conditions_paiement'] = bon_commande.conditions_paiement or ''
    context['note_bas_page'] = bon_commande.note_bas_page or ''
    # NTP2P25 — chaîne Total HT → TVA (taux standard) → Total TTC, réservée à
    # l'affichage (jamais utilisée par le rapprochement 3 voies FG131, qui
    # reste sur le HT). Omise si le total HT est nul (rien à ventiler).
    total_ht = context['total_document'] or Decimal('0')
    if total_ht:
        context['taux_tva_standard'] = TAUX_TVA_STANDARD_BCF
        context['total_tva_standard'] = (
            total_ht * TAUX_TVA_STANDARD_BCF / Decimal('100')
        ).quantize(Decimal('0.01'))
        context['total_ttc_standard'] = (
            total_ht + context['total_tva_standard'])
    else:
        context['taux_tva_standard'] = None
        context['total_tva_standard'] = None
        context['total_ttc_standard'] = None
    return context


def generate_bcf_pdf(bon_commande):
    """Rend le PDF fournisseur et renvoie les octets (non stocké)."""
    context = build_bcf_context(bon_commande)
    html = _render_html('bon_commande_fournisseur.html', context)
    return _html_to_pdf(html)
