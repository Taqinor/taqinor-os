"""Sélecteurs LECTURE SEULE du domaine Stock exposés aux AUTRES apps.

Point d'entrée cross-app : les autres apps lisent les produits à travers ces
fonctions plutôt qu'en important `apps.stock.models` directement (voir CLAUDE.md,
règle de modularité). Comportement strictement identique aux requêtes inline
d'origine.
"""


def get_produit_scoped(company, pk):
    """Produit scopé société par id, ou None. Lecture seule."""
    from .models import Produit
    return Produit.objects.filter(id=pk, company=company).first()


def get_produit_or_raise(company, pk):
    """Produit scopé société par id. Lève Produit.DoesNotExist (ou ValueError/
    TypeError sur pk invalide) — pour les appelants qui gèrent ces exceptions."""
    from .models import Produit
    return Produit.objects.get(pk=pk, company=company)


def produit_does_not_exist():
    """Classe d'exception Produit.DoesNotExist (pour un `except` côté appelant
    sans importer le modèle)."""
    from .models import Produit
    return Produit.DoesNotExist


def lock_produit(pk):
    """Produit verrouillé pour mise à jour (select_for_update). À utiliser dans
    une transaction. Lève Produit.DoesNotExist si absent."""
    from .models import Produit
    return Produit.objects.select_for_update().get(pk=pk)


def mouvements_par_reference(company, reference):
    """XMFG15 — mouvements de stock (SORTIE/ENTREE/REBUT…) rattachés à un
    document source par ``reference`` (ex. la référence d'un ordre
    d'assemblage), scopés société. Lecture seule, jamais d'instance exposée
    hors de cette app : les appelants lisent les champs plats via
    ``.values()`` ou itèrent l'objet localement dans ce module."""
    from .models import MouvementStock
    if not reference:
        return MouvementStock.objects.none()
    return (MouvementStock.objects
            .filter(company=company, reference=reference)
            .select_related('produit'))


def get_emplacement_scoped(company, pk):
    """EmplacementStock scopé société par id, ou None. Lecture seule."""
    from .models import EmplacementStock
    return EmplacementStock.objects.filter(id=pk, company=company).first()


def valid_produit_ids(company, ids):
    """Sous-ensemble des `ids` qui existent comme Produit de la société (set).
    Lecture seule."""
    from .models import Produit
    if not ids:
        return set()
    return set(
        Produit.objects.filter(id__in=list(ids), company=company)
        .values_list('id', flat=True)
    )


def get_fournisseur_by_id(company, fournisseur_id):
    """FG83 — Renvoie un Fournisseur scopé société par son id, ou None.
    Point d'accès cross-app : SAV utilise ce sélecteur pour ne pas importer
    directement apps.stock.models.Fournisseur."""
    from .models import Fournisseur
    return Fournisseur.objects.filter(
        id=fournisseur_id, company=company).first()


def search_fournisseurs(company, q, *, limit=12):
    """QC1 — Recherche floue de fournisseurs (nom) scopée société. Point d'accès
    cross-app : l'autocomplete entreprise de CRM lit le référentiel fournisseur
    à travers ce sélecteur, sans importer apps.stock.models. LECTURE SEULE ;
    renvoie une liste de Fournisseur (au plus ``limit``)."""
    from .models import Fournisseur
    q = (q or '').strip()
    if not q or company is None:
        return []
    return list(
        Fournisseur.objects.filter(company=company, nom__icontains=q)
        .order_by('nom')[:limit])


# ── DC34 — Référentiel sous-traitant UNIFIÉ (Fournisseur type=service) ────────
# Il n'existe plus de référentiel sous-traitant parallèle : un sous-traitant est
# un Fournisseur(type='service') porteur d'un SousTraitantProfile. Les autres
# apps (installations : ordres/attestations/évaluations, AP sous-traitant) lisent
# le référentiel et les comptes à payer à travers ces sélecteurs, jamais en
# important apps.stock.models directement. LECTURE SEULE.

def get_sous_traitant(company, fournisseur_id):
    """DC34 — Fournisseur de type « service » (sous-traitant) scopé société, ou
    None. Filtre sur le type pour ne jamais confondre avec un fournisseur
    matériel. Lecture seule."""
    from .models import Fournisseur
    return Fournisseur.objects.filter(
        id=fournisseur_id, company=company,
        type=Fournisseur.Type.SERVICE).first()


def sous_traitants_qs(company, *, metier=None, actif=None):
    """DC34 — queryset des sous-traitants (Fournisseur type=service) de la
    société, filtrable par ``metier`` et ``actif`` (lus sur le profil satellite).
    Trié par nom. Lecture seule."""
    from .models import Fournisseur
    qs = (Fournisseur.objects
          .filter(company=company, type=Fournisseur.Type.SERVICE)
          .select_related('profil_sous_traitant')
          .order_by('nom'))
    if metier:
        qs = qs.filter(profil_sous_traitant__metier=metier)
    if actif is not None:
        qs = qs.filter(profil_sous_traitant__actif=actif)
    return qs


def sous_traitant_est_actif(fournisseur):
    """DC34 — vrai si le sous-traitant est actif (drapeau du profil satellite,
    True par défaut si le profil manque). Lecture seule."""
    profil = getattr(fournisseur, 'profil_sous_traitant', None)
    return getattr(profil, 'actif', True)


def facture_fournisseur_scoped(company, facture_id):
    """DC34/G5 — FactureFournisseur scopée société par id, ou None. Point
    d'entrée cross-app pour l'AP sous-traitant (installations) : lire/agir sur
    une facture fournisseur sans importer apps.stock.models. Lecture seule."""
    from .models import FactureFournisseur
    return (FactureFournisseur.objects
            .select_related('fournisseur', 'created_by')
            .filter(id=facture_id, company=company).first())


def paiement_fournisseur_scoped(company, paiement_id):
    """DC34/G5 — PaiementFournisseur scopé société par id, ou None. Lecture
    seule (point d'entrée cross-app AP sous-traitant)."""
    from .models import PaiementFournisseur
    return (PaiementFournisseur.objects
            .select_related('facture', 'created_by')
            .filter(id=paiement_id, company=company).first())


def factures_sous_traitant_qs(company, *, fournisseur_id=None, statut=None):
    """DC34 — comptes à payer des sous-traitants : les FactureFournisseur dont le
    fournisseur est de type « service », scopées société. Filtrable par
    ``fournisseur_id`` et ``statut``. Montants INTERNES. Lecture seule."""
    from .models import Fournisseur, FactureFournisseur
    qs = (FactureFournisseur.objects
          .filter(company=company,
                  fournisseur__type=Fournisseur.Type.SERVICE)
          .select_related('fournisseur', 'created_by')
          .prefetch_related('paiements')
          .order_by('-date_creation'))
    if fournisseur_id:
        qs = qs.filter(fournisseur_id=fournisseur_id)
    if statut:
        qs = qs.filter(statut=statut)
    return qs


def paiements_sous_traitant_qs(company, *, facture_id=None):
    """DC34 — règlements imputés sur les factures sous-traitant (fournisseur
    type=service), scopés société. Filtrable par ``facture_id``. Lecture
    seule."""
    from .models import Fournisseur, PaiementFournisseur
    qs = (PaiementFournisseur.objects
          .filter(company=company,
                  facture__fournisseur__type=Fournisseur.Type.SERVICE)
          .select_related('facture', 'created_by')
          .order_by('-date_paiement', '-date_creation'))
    if facture_id:
        qs = qs.filter(facture_id=facture_id)
    return qs


# ── DC30 / DC31 — Identité tiers fournisseur DÉRIVÉE (jamais re-stockée) ──────
# La Comptabilité (comptes auxiliaires tiers, DC30) et les Contrats (parties,
# DC31) ne RECOPIENT JAMAIS nom/ICE/IF/RC/RIB d'un fournisseur sur leur propre
# modèle : ils gardent une référence (FK chaîne ``stock.Fournisseur`` ou couple
# typé tiers_type='fournisseur'/tiers_id) et LISENT l'identité au vol via ce
# sélecteur. Identité = source unique sur Fournisseur (DC15). LECTURE SEULE.

def get_fournisseur_tiers_identity(company, fournisseur_id):
    """Identité légale d'un fournisseur (tiers) pour un compte auxiliaire compta
    (DC30) ou une partie au contrat (DC31), scopée société.

    Renvoie ``{type_tiers, id, nom, ice, identifiant_fiscal, rc, rib, email,
    telephone, adresse}`` ou ``None`` si le fournisseur n'appartient pas à la
    société. Aucune de ces valeurs ne doit être recopiée sur le compte/la
    partie : c'est l'accesseur unique d'identité tiers fournisseur. LECTURE
    SEULE."""
    f = get_fournisseur_by_id(company, fournisseur_id)
    if f is None:
        return None
    return {
        'type_tiers': 'fournisseur',
        'id': f.id,
        'nom': f.nom,
        'ice': f.ice,
        'identifiant_fiscal': f.identifiant_fiscal,
        'rc': f.rc,
        'rib': f.rib,
        'email': f.email,
        'telephone': f.telephone,
        'adresse': f.adresse,
    }


# ── FG131 — Achats / AP : données pour le rapprochement 3 voies ──────────────
# Point d'entrée cross-app LECTURE SEULE pour la Comptabilité (apps.compta) : le
# rapprochement 3 voies (BC ↔ réception ↔ facture fournisseur) lit les trois
# montants à travers ces sélecteurs plutôt qu'en important apps.stock.models.
# AUCUNE de ces fonctions n'écrit ; les montants d'achat restent INTERNES.


def get_bon_commande_fournisseur(company, bc_id):
    """BonCommandeFournisseur scopé société par id, ou None. Lecture seule."""
    from .models import BonCommandeFournisseur
    return BonCommandeFournisseur.objects.filter(
        id=bc_id, company=company).first()


def get_bcf_by_id(bc_id):
    """QS3 — BCF par id, NON scopé (l'appelant a déjà authentifié via un jeton
    ShareLink borné à ce BCF). Renvoie l'objet ou None. Lecture seule."""
    from .models import BonCommandeFournisseur
    return BonCommandeFournisseur.objects.filter(id=bc_id).first()


def render_bcf_pdf_by_id(bc_id):
    """QS3 — Rend à la volée le PDF FOURNISSEUR d'un BCF (bytes) + son nom de
    fichier cohérent. Renvoie ``(pdf_bytes, filename)`` ou ``(None, None)``.

    Point d'entrée cross-app : ``ventes`` (endpoint public tokenisé) appelle CE
    sélecteur au lieu d'importer les modèles/utils de ``stock`` directement. Le
    PDF montre légitimement les PRIX D'ACHAT au FOURNISSEUR (le jeton l'y
    autorise) — il n'est jamais servi à un client final."""
    bcf = get_bcf_by_id(bc_id)
    if bcf is None:
        return None, None
    from .utils.pdf_fournisseur import generate_bcf_pdf
    pdf_bytes = generate_bcf_pdf(bcf)
    from apps.ventes.utils.filenames import document_filename
    filename = document_filename(
        'Bon-de-commande', bcf.reference,
        client=bcf.fournisseur if bcf.fournisseur_id else None,
        company=bcf.company)
    return pdf_bytes, filename


def montant_commande_bcf(bon_commande):
    """Montant HT COMMANDÉ d'un bon de commande fournisseur (Σ lignes :
    quantité × prix d'achat unitaire). INTERNE. Renvoie un Decimal."""
    from decimal import Decimal
    total = Decimal('0')
    for ligne in bon_commande.lignes.all():
        total += Decimal(str(ligne.quantite or 0)) * (
            ligne.prix_achat_unitaire or Decimal('0'))
    return total


def montant_recu_bcf(bon_commande):
    """Montant HT REÇU pour un BCF : Σ sur les réceptions CONFIRMÉES de
    (quantité reçue × prix d'achat unitaire de la ligne de commande). Reflète
    la marchandise effectivement entrée en stock. INTERNE. Renvoie un Decimal.
    """
    from decimal import Decimal
    from .models import LigneReceptionFournisseur
    total = Decimal('0')
    lignes = (LigneReceptionFournisseur.objects
              .filter(reception__bon_commande=bon_commande,
                      reception__statut='confirme')
              .select_related('ligne_commande'))
    for ligne in lignes:
        pu = (ligne.ligne_commande.prix_achat_unitaire
              if ligne.ligne_commande else Decimal('0'))
        total += Decimal(str(ligne.quantite or 0)) * (pu or Decimal('0'))
    return total


def montant_facture_bcf(bon_commande):
    """Montant HT FACTURÉ rattaché à un BCF : Σ des ``montant_ht`` des
    FactureFournisseur liées (statuts de règlement confondus ; une facture
    reste due tant qu'elle existe). INTERNE. Renvoie un Decimal."""
    from decimal import Decimal
    from django.db.models import Sum
    from .models import FactureFournisseur
    agg = (FactureFournisseur.objects
           .filter(bon_commande=bon_commande)
           .aggregate(total=Sum('montant_ht')))
    return agg['total'] or Decimal('0')


def three_way_amounts(company, bc_id):
    """FG131 — Les trois montants HT du rapprochement 3 voies pour un BCF :
    commandé (BC) ↔ reçu (réception) ↔ facturé (facture fournisseur).

    Renvoie un dict ``{exists, bon_commande_id, reference, fournisseur_id,
    fournisseur_nom, statut, montant_commande, montant_recu, montant_facture}``
    ou ``{'exists': False}`` si le BCF n'appartient pas à la société. LECTURE
    SEULE ; montants INTERNES (jamais client-facing)."""
    bon = get_bon_commande_fournisseur(company, bc_id)
    if bon is None:
        return {'exists': False}
    return {
        'exists': True,
        'bon_commande_id': bon.id,
        'reference': bon.reference,
        'fournisseur_id': bon.fournisseur_id,
        'fournisseur_nom': bon.fournisseur.nom if bon.fournisseur_id else None,
        'statut': bon.statut,
        'montant_commande': montant_commande_bcf(bon),
        'montant_recu': montant_recu_bcf(bon),
        'montant_facture': montant_facture_bcf(bon),
    }


def echeances_facture_fournisseur(company, facture_id):
    """XPUR6 — tranches d'échéancier d'une facture fournisseur (utilisées
    par la balance âgée FG132 et le payment run FG133 pour proposer un
    paiement PAR ÉCHÉANCE plutôt que par facture entière). Renvoie une liste
    de dicts triés par date ; vide si la facture n'a pas d'échéancier
    explicite (repli sur ``FactureFournisseur.date_echeance`` — comportement
    historique inchangé) ou n'appartient pas à la société."""
    from .models import FactureFournisseur
    facture = FactureFournisseur.objects.filter(
        company=company, pk=facture_id).first()
    if facture is None:
        return []
    return [
        {
            'id': e.id,
            'pourcentage': e.pourcentage,
            'montant': e.montant,
            'date_echeance': e.date_echeance,
        }
        for e in facture.echeances.all()
    ]


def acomptes_fournisseur_ouverts(company):
    """XPUR8 — acomptes fournisseur PARTIELLEMENT/NON consommés de la
    société (montant_non_consomme > 0), pour la vue trésorerie/cash-flow
    existante (compta). Renvoie une liste de dicts triés par date de
    versement. LECTURE SEULE, INTERNE."""
    from decimal import Decimal
    from .models import AcompteFournisseur
    qs = (AcompteFournisseur.objects.filter(company=company)
          .select_related('bon_commande', 'bon_commande__fournisseur')
          .order_by('-date_versement'))
    out = []
    for a in qs:
        non_consomme = (a.montant or Decimal('0')) - (
            a.montant_consomme or Decimal('0'))
        if non_consomme > 0:
            out.append({
                'id': a.id,
                'bon_commande_id': a.bon_commande_id,
                'bon_commande_reference': a.bon_commande.reference,
                'fournisseur_nom': (a.bon_commande.fournisseur.nom
                                    if a.bon_commande.fournisseur_id else None),
                'montant': a.montant,
                'montant_non_consomme': non_consomme,
                'date_versement': a.date_versement,
            })
    return out


# ── XCTR17 — Location de matériel SORTANTE : produits louables ─────────────

def get_produit_louable(company, pk):
    """Produit LOUABLE scopé société par id, ou ``None`` (XCTR17).

    Renvoie ``None`` si le produit n'existe pas dans la société OU si
    ``louable`` est faux — jamais un produit non louable (garde métier avant
    la création d'un ``contrats.OrdreLocation``)."""
    from .models import Produit
    return Produit.objects.filter(
        id=pk, company=company, louable=True).first()


def produits_louables_qs(company):
    """QuerySet des produits louables de la société (XCTR17). Lecture seule."""
    from .models import Produit
    return Produit.objects.filter(company=company, louable=True)


# ── XPUR17 — TVA par ligne sur la facture fournisseur ────────────────────────
# Ventilation HT/TVA PAR TAUX (20/14/10/7 %/exonéré). Point d'entrée cross-app
# LECTURE SEULE pour la comptabilité (apps.compta) : le relevé de déductions
# TVA lit la ventilation à travers ce sélecteur plutôt qu'en important
# apps.stock.models directement.

def sous_totaux_tva_facture_fournisseur(facture):
    """XPUR17 — sous-totaux HT/TVA groupés par taux pour UNE facture
    fournisseur, dérivés de ses lignes. Une ligne sans taux (`taux_tva` NULL
    — facture historique) n'est PAS incluse ici : la facture garde alors son
    `montant_tva` global agrégé comme unique source de vérité (compat totale).
    Renvoie une liste triée par taux décroissant : ``[{taux_tva, total_ht,
    total_tva}, ...]`` (vide si aucune ligne ventilée). LECTURE SEULE."""
    from decimal import Decimal
    par_taux = {}
    for ligne in facture.lignes.all():
        if ligne.taux_tva is None:
            continue
        taux = ligne.taux_tva
        entry = par_taux.setdefault(
            taux, {'taux_tva': taux, 'total_ht': Decimal('0'),
                   'total_tva': Decimal('0')})
        entry['total_ht'] += ligne.total_ht
        entry['total_tva'] += ligne.total_tva
    return sorted(par_taux.values(), key=lambda e: e['taux_tva'], reverse=True)


def releve_deductions_tva_par_taux(company, *, date_debut=None, date_fin=None):
    """XPUR17 — relevé de déductions TVA (achats) groupé PAR TAUX sur la
    période, toutes factures fournisseur confondues (statut de règlement
    indifférent — la déduction s'apprécie à la facture, pas au paiement).
    Point d'entrée cross-app pour la comptabilité. LECTURE SEULE."""
    from decimal import Decimal
    from .models import FactureFournisseur
    qs = FactureFournisseur.objects.filter(company=company).prefetch_related(
        'lignes')
    if date_debut:
        qs = qs.filter(date_facture__gte=date_debut)
    if date_fin:
        qs = qs.filter(date_facture__lte=date_fin)

    par_taux = {}
    for facture in qs:
        for entry in sous_totaux_tva_facture_fournisseur(facture):
            taux = entry['taux_tva']
            agg = par_taux.setdefault(
                taux, {'taux_tva': taux, 'total_ht': Decimal('0'),
                       'total_tva': Decimal('0'), 'nombre_factures': 0})
            agg['total_ht'] += entry['total_ht']
            agg['total_tva'] += entry['total_tva']
            agg['nombre_factures'] += 1
    return sorted(par_taux.values(), key=lambda e: e['taux_tva'], reverse=True)
