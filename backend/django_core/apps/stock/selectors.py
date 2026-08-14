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


def produits_avertissements(company, produit_ids):
    """ZSAL9 — avertissements de vente (« sale warnings ») des produits dont
    l'id est dans ``produit_ids``, scopés société. Lecture seule : renvoie une
    liste de dicts plats ``{id, nom, avertissement_vente, avertissement_bloquant}``
    pour les seuls produits PORTEURS d'un message — jamais d'instance ni de
    prix. Les appelants (ventes) l'utilisent pour afficher la bannière et
    décider du blocage sans importer ``stock.models``."""
    from .models import Produit
    ids = [pid for pid in (produit_ids or []) if pid]
    if not ids:
        return []
    return list(
        Produit.objects
        .filter(id__in=ids, company=company)
        .exclude(avertissement_vente='')
        .values('id', 'nom', 'avertissement_vente', 'avertissement_bloquant')
    )


def factures_fournisseur_ouvertes(company, *, date_limite=None):
    """YLEDG8 — Factures fournisseur à solde dû > 0, pour proposer les
    échéances d'un ``compta.PaymentRun``. Triées par ``date_echeance``
    (échéances les plus proches / sans date d'abord — comme la balance
    âgée). ``date_limite`` (optionnel) ne retient que les échéances à cette
    date ou avant. Lecture seule ; renvoie une liste de dicts."""
    from .models import FactureFournisseur

    qs = (FactureFournisseur.objects
          .filter(company=company)
          .select_related('fournisseur')
          .order_by('date_echeance', 'id'))
    if date_limite:
        qs = qs.filter(date_echeance__lte=date_limite)
    out = []
    for facture in qs:
        solde = facture.solde_du
        if not solde:
            continue
        out.append({
            'facture_id': facture.id,
            'reference': facture.reference,
            'fournisseur_id': facture.fournisseur_id,
            'fournisseur_nom': (
                facture.fournisseur.nom if facture.fournisseur else ''),
            'date_echeance': facture.date_echeance,
            'montant': solde,
            'rib': getattr(facture.fournisseur, 'rib', '') or '',
        })
    return out


def get_fournisseur_by_id(company, fournisseur_id):
    """FG83 — Renvoie un Fournisseur scopé société par son id, ou None.
    Point d'accès cross-app : SAV utilise ce sélecteur pour ne pas importer
    directement apps.stock.models.Fournisseur."""
    from .models import Fournisseur
    return Fournisseur.objects.filter(
        id=fournisseur_id, company=company).first()


def fournisseurs_pour_controle_ice(company):
    """ZACC14 — Fournisseurs de la société, pour le contrôle d'identifiants
    légaux (ICE/IF) côté compta. Point d'entrée cross-app (jamais un import
    de ``apps.stock.models`` en dehors de ce module). Lecture seule ;
    renvoie une liste de dicts ``{'id', 'nom', 'ice', 'if_fiscal'}``."""
    from .models import Fournisseur

    qs = Fournisseur.objects.filter(company=company).order_by('id')
    return [
        {
            'id': fournisseur.id,
            'nom': fournisseur.nom,
            'ice': fournisseur.ice or '',
            'if_fiscal': fournisseur.identifiant_fiscal or '',
        }
        for fournisseur in qs
    ]


def search_fournisseurs(company, q, *, limit=12):
    """QC1 — Recherche floue de fournisseurs (nom) scopée société. Point d'accès
    cross-app : l'autocomplete entreprise de CRM lit le référentiel fournisseur
    à travers ce sélecteur, sans importer apps.stock.models. LECTURE SEULE ;
    renvoie une liste de Fournisseur (au plus ``limit``)."""
    from .models import Fournisseur
    q = (q or '').strip()
    if not q or company is None:
        return []
    # NTPRT25 — une candidature d'auto-inscription NON VALIDÉE n'apparaît
    # dans AUCUNE liste de sourcing automatique (autocomplete, sélection
    # fournisseur) tant qu'un admin interne n'a pas tranché. Les fournisseurs
    # historiques sont ``valide`` par défaut : comportement inchangé.
    return list(
        Fournisseur.objects
        .filter(company=company, nom__icontains=q,
                statut_validation=Fournisseur.StatutValidation.VALIDE)
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
    # NTPRT25 — jamais un candidat non validé dans la sélection automatique
    # d'un sous-traitant (défaut ``valide`` ⇒ historique inchangé).
    qs = (Fournisseur.objects
          .filter(company=company, type=Fournisseur.Type.SERVICE,
                  statut_validation=Fournisseur.StatutValidation.VALIDE)
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


def ligne_facture_fournisseur_scoped(company, facture_id, ligne_id):
    """XACC33 — Ligne d'une facture fournisseur, scopée société, ou None.

    Point d'entrée cross-app pour ``apps.compta`` (capitalisation d'une ligne
    en immobilisation, XACC33) : jamais un import de ``apps.stock.models`` en
    dehors de ce module. Vérifie que la ligne appartient bien à la facture
    ``facture_id`` ET que cette facture appartient à ``company`` — renvoie
    ``None`` (jamais une autre société) si l'un des deux ne correspond pas.
    Lecture seule."""
    from .models import LigneFactureFournisseur

    return (
        LigneFactureFournisseur.objects
        .select_related('facture', 'produit')
        .filter(
            id=ligne_id, facture_id=facture_id,
            facture__company=company)
        .first()
    )


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
    """Montant HT REÇU pour un BCF : Σ sur ses LIGNES de commande de
    (``quantite_recue`` × prix d'achat unitaire). Reflète la marchandise
    effectivement entrée en stock. INTERNE. Renvoie un Decimal.

    YPROC8 — lit ``quantite_recue`` (dénormalisée sur la ligne BCF, tenue à
    jour à la fois par la confirmation de réception ET par le retour
    fournisseur — ``_reouvrir_quantite_recue_bcf`` la DÉCRÉMENTE), plutôt que
    de reconstruire depuis les lignes de réception confirmées : celles-ci ne
    sont jamais modifiées par un retour, ce qui laissait le 3-voies
    surestimer le reçu après un retour (le rapprochement OUVERT ne se
    rafraîchissait jamais à la baisse)."""
    from decimal import Decimal
    total = Decimal('0')
    for ligne in bon_commande.lignes.all():
        total += Decimal(str(ligne.quantite_recue or 0)) * (
            ligne.prix_achat_unitaire or Decimal('0'))
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


def quantite_en_commande_produit(company, produit_id):
    """YPROC9 — quantité TOTALE de ``produit_id`` déjà « en commande » chez un
    fournisseur (Σ ``quantite_restante`` des lignes de BCF BROUILLON ou
    ENVOYE, jamais ANNULE/RECU — un BCF RECU n'a par construction plus de
    restant). Ce pipeline arrive tôt ou tard en stock : le net de réappro doit
    le déduire pour ne pas re-suggérer ce qui est déjà en route. INTERNE,
    lecture seule."""
    from .models import BonCommandeFournisseur, LigneBonCommandeFournisseur

    lignes = (LigneBonCommandeFournisseur.objects
              .filter(
                  produit_id=produit_id,
                  bon_commande__company=company,
                  bon_commande__statut__in=[
                      BonCommandeFournisseur.Statut.BROUILLON,
                      BonCommandeFournisseur.Statut.ENVOYE,
                  ])
              .select_related('bon_commande'))
    total = 0
    for ligne in lignes:
        total += max(ligne.quantite - ligne.quantite_recue, 0)
    return total


def bcf_sources_en_commande_produit(company, produit_id):
    """YPROC9/ZPUR10 — détail des BCF sources contribuant à
    ``quantite_en_commande_produit`` : liste de dicts {bon_commande_id,
    reference, fournisseur_nom, quantite_restante, date_livraison_prevue}.
    INTERNE, lecture seule."""
    from .models import BonCommandeFournisseur, LigneBonCommandeFournisseur

    lignes = (LigneBonCommandeFournisseur.objects
              .filter(
                  produit_id=produit_id,
                  bon_commande__company=company,
                  bon_commande__statut__in=[
                      BonCommandeFournisseur.Statut.BROUILLON,
                      BonCommandeFournisseur.Statut.ENVOYE,
                  ])
              .select_related('bon_commande', 'bon_commande__fournisseur'))
    out = []
    for ligne in lignes:
        restant = max(ligne.quantite - ligne.quantite_recue, 0)
        if restant <= 0:
            continue
        bc = ligne.bon_commande
        out.append({
            'bon_commande_id': bc.id,
            'reference': bc.reference,
            'fournisseur_nom': (
                bc.fournisseur.nom if bc.fournisseur_id else None),
            'quantite_restante': restant,
            'date_livraison_prevue': bc.date_livraison_prevue,
        })
    return out


def bcf_sources_en_commande_map(company):
    """YOPSB13 — variante « toute la société en une requête » de
    :func:`bcf_sources_en_commande_produit`, pour éviter le N+1 sur la LISTE
    produits (``ProduitSerializer.get_bcf_sources_en_commande``/
    ``get_quantite_en_commande`` appelés une fois par ligne). Renvoie
    ``{produit_id: [sources...]}`` — même forme de dict par source que la
    version unitaire, résultat identique (mêmes filtres BROUILLON/ENVOYE,
    mêmes exclusions ANNULE/RECU/restant<=0). INTERNE, lecture seule."""
    from .models import BonCommandeFournisseur, LigneBonCommandeFournisseur

    lignes = (LigneBonCommandeFournisseur.objects
              .filter(
                  bon_commande__company=company,
                  bon_commande__statut__in=[
                      BonCommandeFournisseur.Statut.BROUILLON,
                      BonCommandeFournisseur.Statut.ENVOYE,
                  ])
              .select_related('bon_commande', 'bon_commande__fournisseur'))
    out = {}
    for ligne in lignes:
        restant = max(ligne.quantite - ligne.quantite_recue, 0)
        if restant <= 0:
            continue
        bc = ligne.bon_commande
        out.setdefault(ligne.produit_id, []).append({
            'bon_commande_id': bc.id,
            'reference': bc.reference,
            'fournisseur_nom': (
                bc.fournisseur.nom if bc.fournisseur_id else None),
            'quantite_restante': restant,
            'date_livraison_prevue': bc.date_livraison_prevue,
        })
    return out


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


def encours_fournisseurs_par_tiers(company):
    """YLEDG13 — encours documentaire (reste dû) par fournisseur, factures
    fournisseur non soldées d'une société. Point d'entrée cross-app
    sanctionné pour ``apps.compta`` (rapprochement auxiliaire/GL, jamais un
    import direct de ``stock.models``). Renvoie une liste de dicts
    ``{'tiers_id', 'nom', 'encours', 'references'}`` (encours > 0
    seulement). Lecture seule."""
    from decimal import Decimal
    from .models import FactureFournisseur

    par_fournisseur = {}
    qs = (FactureFournisseur.objects
          .filter(company=company)
          .select_related('fournisseur'))
    for facture in qs:
        du = facture.solde_du
        if not du:
            continue
        fournisseur = facture.fournisseur
        entry = par_fournisseur.setdefault(fournisseur.id, {
            'tiers_id': fournisseur.id,
            'nom': fournisseur.nom,
            'encours': Decimal('0'),
            'references': [],
        })
        entry['encours'] += Decimal(du)
        entry['references'].append(facture.reference)
    return [v for v in par_fournisseur.values() if v['encours'] > 0]


def exposition_69_21(
        company, periode=None, *, delai_defaut=60, delai_max=120):
    """XFAC2 — Conformité loi 69-21 (délais de paiement légaux) : liste les
    factures fournisseur IMPAYÉES (``solde_du`` > 0) dépassant leur délai
    légal de paiement, avec l'amende estimée.

    Délai applicable par facture = ``Fournisseur.delai_paiement_jours`` s'il
    est renseigné (> 0 — XPUR6, sinon 0 = « comptant, échéance manuelle »),
    sinon ``delai_defaut`` (60 j, le défaut légal 69-21) borné à
    ``delai_max`` (120 j max même si un délai convenu plus long est saisi).
    L'amende est estimée avec un taux annuel simplifié (majoration légale par
    mois de dépassement) appliqué au montant TTC dû, prorata du nombre de
    mois entiers de dépassement — lecture seule, aucune écriture, aucun
    modèle exposé hors de ce module.

    ``periode`` (optionnel, ``'YYYY-MM'``) filtre les factures dont
    ``date_facture`` tombe dans le trimestre civil contenant ce mois (pour
    la déclaration trimestrielle DGI) ; sans periode, toutes les factures
    impayées sont considérées.

    Renvoie une liste de dicts : ``{facture_id, reference, fournisseur_id,
    fournisseur_nom, date_emission, delai_legal_jours, date_echeance_legale,
    jours_depassement, montant_du, amende_estimee}`` — uniquement les
    factures réellement en dépassement (jours_depassement > 0). Une facture
    payée (solde_du == 0) est exclue."""
    from datetime import timedelta
    from decimal import Decimal

    from django.utils import timezone

    from .models import FactureFournisseur

    today = timezone.localdate()

    qs = (FactureFournisseur.objects
          .filter(company=company, date_facture__isnull=False)
          .select_related('fournisseur'))

    if periode:
        annee, mois = (int(part) for part in periode.split('-'))
        trimestre_debut_mois = ((mois - 1) // 3) * 3 + 1
        mois_fin = trimestre_debut_mois + 2
        annee_fin = annee
        if mois_fin > 12:
            mois_fin -= 12
            annee_fin += 1
        from datetime import date as _date
        borne_debut = _date(annee, trimestre_debut_mois, 1)
        if mois_fin == 12:
            borne_fin = _date(annee_fin, 12, 31)
        else:
            borne_fin = _date(annee_fin, mois_fin + 1, 1) - timedelta(days=1)
        qs = qs.filter(date_facture__gte=borne_debut,
                       date_facture__lte=borne_fin)

    lignes = []
    # Taux directeur BAM simplifié + majoration légale : 1 %/mois de
    # dépassement (estimation, configurable côté founder si besoin plus fin).
    taux_mensuel = Decimal('0.01')
    for facture in qs:
        solde = facture.solde_du
        if not solde:
            continue
        fournisseur = facture.fournisseur
        delai = fournisseur.delai_paiement_jours if fournisseur else 0
        delai_legal = min(delai, delai_max) if delai else delai_defaut
        date_echeance_legale = facture.date_facture + timedelta(days=delai_legal)
        jours_depassement = (today - date_echeance_legale).days
        if jours_depassement <= 0:
            continue
        mois_depassement = (jours_depassement // 30) + 1
        amende_estimee = (
            Decimal(solde) * taux_mensuel * mois_depassement
        ).quantize(Decimal('0.01'))
        lignes.append({
            'facture_id': facture.id,
            'reference': facture.reference,
            'fournisseur_id': fournisseur.id if fournisseur else None,
            'fournisseur_nom': fournisseur.nom if fournisseur else '',
            'date_emission': facture.date_facture,
            'delai_legal_jours': delai_legal,
            'date_echeance_legale': date_echeance_legale,
            'jours_depassement': jours_depassement,
            'montant_du': Decimal(solde),
            'amende_estimee': amende_estimee,
        })
    lignes.sort(key=lambda e: e['jours_depassement'], reverse=True)
    return lignes


def lignes_import_depuis_bcf(company, bon_commande_id):
    """XSTK19 — lignes candidates pour un dossier d'import ADII, pré-remplies
    depuis les SKUs d'un bon de commande fournisseur (code SH + pays
    d'origine du produit quand renseignés). Point d'entrée cross-app pour
    ``installations.DossierImport`` — LECTURE SEULE, jamais d'instance
    ``LigneBonCommandeFournisseur`` exposée en dehors de ce module.

    Renvoie [{produit_id, sku, designation, quantite, code_sh, pays_origine}]
    scopé société ; liste vide si le BCF n'existe pas / n'appartient pas à la
    société. Les champs code_sh/pays_origine peuvent être vides (jamais
    inventés)."""
    from .models import LigneBonCommandeFournisseur
    lignes = (LigneBonCommandeFournisseur.objects
              .filter(bon_commande_id=bon_commande_id,
                      bon_commande__company=company,
                      produit__isnull=False)
              .select_related('produit'))
    out = []
    for ligne in lignes:
        p = ligne.produit
        out.append({
            'produit_id': p.id,
            'sku': p.sku or '',
            'designation': p.nom,
            'quantite': ligne.quantite,
            'code_sh': p.code_sh or '',
            'pays_origine': p.pays_origine or '',
        })
    return out


MOUVEMENTS_AGREGES_GROUP_BY = ('produit', 'type', 'mois', 'emplacement')


def mouvements_agreges(company, *, group_by, date_min=None, date_max=None):
    """ZSTK7 — « Reporting ▸ Moves History » : agrège `MouvementStock` par
    ``group_by`` (produit/type/mois/emplacement) sur la période optionnelle,
    en quantités ENTRÉES/SORTIES/NETTES. LECTURE SEULE, INTERNE.

    ``group_by='emplacement'`` réutilise `stock_breakdown_map` (ventilation
    ACTUELLE par emplacement — le modèle `MouvementStock` ne trace pas
    l'emplacement par mouvement) : chaque quantité agrégée est éclatée selon
    la répartition courante du produit entre emplacements. Lève
    ``ValueError`` si ``group_by`` n'est pas reconnu (400 côté vue)."""
    from .models import MouvementStock

    if group_by not in MOUVEMENTS_AGREGES_GROUP_BY:
        raise ValueError(
            f'group_by inconnu : {group_by!r} '
            f'(attendu parmi {MOUVEMENTS_AGREGES_GROUP_BY}).')

    qs = MouvementStock.objects.filter(
        company=company).select_related('produit')
    if date_min:
        qs = qs.filter(date__date__gte=date_min)
    if date_max:
        qs = qs.filter(date__date__lte=date_max)

    ENTREE = MouvementStock.TypeMouvement.ENTREE
    SORTIE = MouvementStock.TypeMouvement.SORTIE

    def _cle(m):
        if group_by == 'produit':
            return (m.produit_id, m.produit.nom if m.produit_id else '—')
        if group_by == 'type':
            return (m.type_mouvement, m.get_type_mouvement_display())
        if group_by == 'mois':
            from .services import _mois_key
            key = _mois_key(m.date)
            return (key, key)
        return None  # 'emplacement' traité séparément ci-dessous.

    buckets = {}
    for m in qs:
        if group_by == 'emplacement':
            continue
        cle, libelle = _cle(m)
        entry = buckets.setdefault(
            cle, {'cle': cle, 'libelle': libelle,
                  'entrees': 0, 'sorties': 0})
        if m.type_mouvement == ENTREE:
            entry['entrees'] += m.quantite
        elif m.type_mouvement == SORTIE:
            entry['sorties'] += m.quantite

    if group_by == 'emplacement':
        from .services import stock_breakdown_map
        breakdown = stock_breakdown_map(company)
        for m in qs:
            rows = breakdown.get(m.produit_id, [])
            total = sum(r['quantite'] for r in rows) or 1
            for r in rows:
                part = r['quantite'] / total
                cle = (r['emplacement_id'], r['emplacement_nom'])
                entry = buckets.setdefault(
                    cle, {'cle': cle, 'libelle': r['emplacement_nom'],
                          'entrees': 0, 'sorties': 0})
                if m.type_mouvement == ENTREE:
                    entry['entrees'] += m.quantite * part
                elif m.type_mouvement == SORTIE:
                    entry['sorties'] += m.quantite * part

    out = []
    for entry in buckets.values():
        out.append({
            'libelle': entry['libelle'],
            'entrees': entry['entrees'],
            'sorties': entry['sorties'],
            'net': entry['entrees'] - entry['sorties'],
        })
    out.sort(key=lambda e: e['libelle'] or '')
    return out


def resolve_via_nomenclature(company, code):
    """ZSTK12 — consulte la nomenclature de code-barres ACTIVE de la société
    (s'il y en a une) et renvoie ``(encode, regle)`` pour la PREMIÈRE règle
    (triée par priorité) dont le motif matche ``code``, ou ``None`` si
    aucune nomenclature active / aucune règle ne matche — repli : le
    résolveur de scan continue alors son comportement HISTORIQUE (jetons
    internes → GS1 → EAN), byte-identique à avant ZSTK12."""
    from .models import NomenclatureCodeBarres

    nomenclature = (NomenclatureCodeBarres.objects
                    .filter(company=company, actif=True)
                    .prefetch_related('regles')
                    .first())
    if nomenclature is None:
        return None
    for regle in nomenclature.regles.all():
        if regle.matches(code):
            return regle.encode, regle
    return None


def trace_serie(company, *, numero_serie=None, numero_lot=None):
    """XSTK7 — rapport de traçabilité bout-en-bout (rappel fabricant) : pour
    un numéro de série (ou de lot XSTK6), remonte EN UN APPEL la chaîne
    réception fournisseur (BCF/réception/fournisseur/date) → emplacements
    (LotEntrepot/SerieEntrepot) → livraison/chantier → équipement installé/
    client. Lit `installations`/`sav` via LEURS selectors (jamais leurs
    models). LECTURE SEULE, INTERNE.

    Exactement un de ``numero_serie``/``numero_lot`` doit être fourni.
    Renvoie ``None`` si rien n'est trouvé (numéro inconnu / hors société —
    l'appelant renvoie 404)."""
    from .models import LigneReceptionFournisseur, LotEntrepot

    if not numero_serie and not numero_lot:
        return None

    chaine = {
        'numero_serie': numero_serie,
        'numero_lot': numero_lot,
        'reception': None,
        'emplacement': None,
        'equipement': None,
    }
    found = False

    if numero_serie:
        # ── Maillon 1 : réception fournisseur (série capturée FG61) ───────
        lignes = (LigneReceptionFournisseur.objects
                  .filter(reception__company=company,
                          numeros_serie__isnull=False)
                  .select_related(
                      'reception', 'reception__bon_commande',
                      'reception__bon_commande__fournisseur', 'produit'))
        for ligne in lignes:
            valeurs = [str(v).strip() for v in (ligne.numeros_serie or [])]
            if numero_serie.strip() in valeurs:
                bc = (ligne.reception.bon_commande
                      if ligne.reception.bon_commande_id else None)
                chaine['reception'] = {
                    'reception_reference': ligne.reception.reference,
                    'bcf_reference': bc.reference if bc else None,
                    'fournisseur_nom': (
                        bc.fournisseur.nom
                        if bc and bc.fournisseur_id else None),
                    'date': (
                        ligne.reception.date_creation.isoformat()
                        if ligne.reception.date_creation else None),
                    'produit_id': ligne.produit_id,
                    'produit_nom': (
                        ligne.produit.nom if ligne.produit_id else None),
                }
                found = True
                break

        # ── Maillon 2 : emplacement entrepôt (SerieEntrepot, installations)
        from apps.installations.selectors import serie_entrepot_scoped_by_serial
        produit_id = (chaine['reception']['produit_id']
                      if chaine['reception'] else None)
        serie_ent = None
        if produit_id is not None:
            serie_ent = serie_entrepot_scoped_by_serial(
                company, produit_id, numero_serie)
        if serie_ent is not None:
            chaine['emplacement'] = {
                'statut': serie_ent.statut,
                'emplacement_id': serie_ent.emplacement_id,
            }
            found = True

        # ── Maillon 3+4 : équipement installé (sav.Equipement) → chantier/
        # client (via Equipement.installation, déjà porté par le selector).
        from apps.sav.selectors import equipement_scoped_by_serial
        equipement = equipement_scoped_by_serial(company, numero_serie)
        if equipement is not None:
            found = True
            installation = equipement.installation
            client_nom = ''
            if installation is not None and installation.client_id:
                c = installation.client
                client_nom = f'{c.nom} {c.prenom or ""}'.strip()
            chaine['equipement'] = {
                'equipement_id': equipement.id,
                'statut': equipement.statut,
                'chantier_reference': (
                    installation.reference if installation else None),
                'client_nom': client_nom or None,
            }

    if numero_lot:
        lot = (LotEntrepot.objects
               .filter(company=company, numero_lot=numero_lot)
               .select_related('produit', 'emplacement')
               .order_by('-date_creation')
               .first())
        if lot is not None:
            found = True
            chaine['reception'] = {
                'reception_reference': lot.reference_reception,
                'bcf_reference': None,
                'fournisseur_nom': None,
                'date': None,
                'produit_id': lot.produit_id,
                'produit_nom': lot.produit.nom if lot.produit_id else None,
            }
            chaine['emplacement'] = {
                'statut': (
                    'epuise' if lot.quantite_restante <= 0 else 'en_stock'),
                'emplacement_id': lot.emplacement_id,
            }

    if not found:
        return None
    return chaine


# ── XMKT29 — Exposition de l'encodeur QR maison (N20) aux autres apps ──────

def qr_svg(text, *, box=4, quiet=4):
    """XMKT29 — encodeur QR SANS dépendance (``apps.stock.labels.qr_svg``),
    exposé ici pour que d'autres apps (compta : SupportOffline XMKT29,
    badges ZMKT19, enquêtes ZMKT12) génèrent un QR SVG sans jamais importer
    ``apps.stock.labels``/``apps.stock.views`` directement — AUCUNE nouvelle
    dépendance (pattern N20)."""
    from .labels import qr_svg as _qr_svg
    return _qr_svg(text, box=box, quiet=quiet)


# ── XSTK20 — Réappro kanban : sélecteurs exposés à installations ───────────

def emplacement_principal_scoped(company):
    """Emplacement de stock PRINCIPAL de cette société, ou None. Amorce les
    emplacements par défaut (dépôt principal + camionnette) si aucun
    n'existe encore, réutilisant `ensure_emplacements` (comportement
    identique à l'écran Emplacements N15). Lecture seule côté appelant."""
    from .models import EmplacementStock
    from .services import ensure_emplacements
    if company is not None:
        ensure_emplacements(company)
    return (EmplacementStock.objects
            .filter(company=company, is_principal=True)
            .first())


def seuil_max_emplacement(company, produit_id, emplacement_id):
    """FG62 — `StockEmplacement.seuil_max` pour (produit, emplacement) de
    cette société, ou None si non défini/inexistant. Lecture seule."""
    from .models import StockEmplacement
    se = (StockEmplacement.objects
          .filter(company=company, produit_id=produit_id,
                  emplacement_id=emplacement_id)
          .first())
    return se.seuil_max if se is not None else None


# ── ZMFG9 — Disponibilité multi-niveaux d'un kit (stock partagé + goulots) ──

def disponibilite_potentielle_recursive(kit, company):
    """ZMFG9 — combien de kits COMPLETS sont assemblables avec le stock
    disponible actuel, en explosant récursivement la nomenclature
    multi-niveaux (XMFG17, garde anti-cycle incluse).

    Le besoin par kit est AGRÉGÉ PAR PRODUIT à travers tous les niveaux
    (``exploser_kit`` cumule les occurrences) : un composant utilisé dans
    deux sous-kits n'est donc JAMAIS compté deux fois côté stock — le nombre
    assemblable = min(disponible ÷ besoin agrégé). Le disponible déduit les
    réservations actives (stock − réservé, comme `structure_kit`).

    Renvoie ``{kit_id, kit_nom, kits_assemblables, composants: [{produit_id,
    sku, designation, besoin_par_kit, disponible, kits_possibles}],
    goulots: [...]}`` où ``goulots`` = les composants LIMITANTS (ceux au
    minimum de ``kits_possibles``, triés par désignation). Un kit sans
    composant renvoie 0 kit assemblable et aucun goulot.

    Lève ``services.KitCycleError`` (cycle) / ``ValueError`` (profondeur
    excessive) — mêmes gardes claires que l'explosion XMFG17. Lecture seule.
    """
    from decimal import Decimal
    from .services import exploser_kit, reserved_quantities

    besoins = exploser_kit(kit, 1)  # lignes produit agrégées tous niveaux.
    reserves = reserved_quantities(company)
    composants = []
    minimum = None
    for ligne in besoins:
        besoin = ligne['quantite'] or Decimal('0')
        if besoin <= 0:
            continue
        dispo = (Decimal(str(ligne['disponible'] or 0))
                 - Decimal(str(reserves.get(ligne['produit_id'], 0))))
        kits_possibles = (
            int((dispo / besoin).to_integral_value(rounding='ROUND_FLOOR'))
            if dispo > 0 else 0)
        minimum = kits_possibles if minimum is None else min(
            minimum, kits_possibles)
        composants.append({
            'produit_id': ligne['produit_id'],
            'sku': ligne['sku'],
            'designation': ligne['designation'],
            'besoin_par_kit': str(besoin),
            'disponible': str(dispo),
            'kits_possibles': kits_possibles,
        })
    kits_assemblables = minimum or 0
    goulots = sorted(
        (c for c in composants if c['kits_possibles'] == kits_assemblables),
        key=lambda c: c['designation']) if composants else []
    return {
        'kit_id': kit.id,
        'kit_nom': kit.nom,
        'kits_assemblables': kits_assemblables,
        'composants': composants,
        'goulots': goulots,
    }


# ── NTPRT20 — Résumé self-service du PORTAIL FOURNISSEUR ────────────────────

def resume_portail_fournisseur(company, fournisseur_id):
    """NTPRT20 — Cartes résumé du tableau de bord fournisseur.

    Point d'entrée cross-app UNIQUE de ``apps.portail`` (jamais un import de
    ``apps.stock.models`` / ``apps.achats.models`` depuis portail). Lecture
    SEULE, bornée au triplet (société, fournisseur) : un ``fournisseur_id``
    absent renvoie des compteurs à zéro, JAMAIS les chiffres de la société
    entière — c'est la différence entre un tableau de bord vide et une fuite.

    Ne contient QUE ce qui existe réellement aujourd'hui : les livraisons
    annoncées (ASN, NTPRT22) et les documents légaux à expiration (NTPRT24)
    ne sont pas encore modélisés — on ne fabrique pas un chiffre pour remplir
    une carte.
    """
    from decimal import Decimal

    vide = {
        'fournisseur_nom': '',
        'bcf_a_confirmer': 0,
        'bcf_en_cours': 0,
        'receptions_recentes': 0,
        'factures_a_payer': 0,
        'montant_a_payer': '0',
    }
    if company is None or not fournisseur_id:
        return vide

    from .models import (
        BonCommandeFournisseur, FactureFournisseur, Fournisseur,
        ReceptionFournisseur,
    )

    fournisseur = (Fournisseur.objects
                   .filter(company=company, pk=fournisseur_id).first())
    if fournisseur is None:
        return vide

    bcf = (BonCommandeFournisseur.objects
           .filter(company=company, fournisseur=fournisseur)
           .exclude(statut=BonCommandeFournisseur.Statut.ANNULE))
    factures = FactureFournisseur.objects.filter(
        company=company, fournisseur=fournisseur).exclude(
        statut=FactureFournisseur.Statut.PAYEE)
    montant = sum((f.montant_ttc or Decimal('0') for f in factures),
                  Decimal('0'))

    return {
        'fournisseur_nom': fournisseur.nom,
        'bcf_a_confirmer': bcf.filter(
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            date_confirmee_fournisseur__isnull=True).count(),
        'bcf_en_cours': bcf.exclude(
            statut=BonCommandeFournisseur.Statut.RECU).count(),
        'receptions_recentes': (ReceptionFournisseur.objects
                                .filter(company=company,
                                        bon_commande__fournisseur=fournisseur)
                                .count()),
        'factures_a_payer': factures.count(),
        'montant_a_payer': str(montant),
    }


# ── PV6 — Specs & Kit de calepinage DÉRIVÉS de FicheTechnique (PV5) ─────────
# Point d'entrée cross-app LECTURE SEULE : le moteur de calepinage
# (core.calepinage) et les autres apps lisent les caractéristiques d'un
# produit à travers ces deux fonctions plutôt qu'en touchant
# `apps.stock.models.FicheTechnique` directement.

def specs_for_produit(produit):
    """PV6 — sous-ensemble de spécifications électriques/dimensions d'un
    produit, lues sur sa FicheTechnique (PV5) et scopées par son
    ``type_fiche`` :

      * ``module`` → ``{vmp_v, voc_v, isc_a, imp_a, pmax_wc,
        temp_coeff_voc_pct_c, temp_coeff_pmax_pct_c, longueur_mm,
        largeur_mm}`` ;
      * ``onduleur`` → ``{n_mppt, mppt_v_min, mppt_v_max, v_max_abs,
        i_max_mppt_a, ac_kw, phases}`` ;
      * ``batterie`` → ``{kwh_nominal, kwh_usable, dod_pct, v_nominal,
        max_charge_kw}``.

    Une clé dont la valeur est NULL sur la fiche est OMISE (jamais rendue à
    ``None``) : un appelant qui fait ``{**DEFAUT, **specs_for_produit(p)}``
    obtient un résultat byte-identique à l'absence de fiche pour tout champ
    non saisi. Produit sans fiche, ou ``type_fiche`` sans bloc connu (vide
    ou ``autre``) → dict VIDE. Lecture seule."""
    fiche = getattr(produit, 'fiche_technique', None)
    if fiche is None:
        return {}

    def _put(d, key, value):
        if value is not None:
            d[key] = value

    out = {}
    if fiche.type_fiche == 'module':
        for key, value in (
            ('vmp_v', fiche.vmp_v), ('voc_v', fiche.voc_v),
            ('isc_a', fiche.isc_a), ('imp_a', fiche.imp_a),
            ('pmax_wc', fiche.pmax_wc),
            ('temp_coeff_voc_pct_c', fiche.temp_coeff_voc_pct_c),
            ('temp_coeff_pmax_pct_c', fiche.temp_coeff_pmax_pct_c),
            ('longueur_mm', fiche.longueur_mm),
            ('largeur_mm', fiche.largeur_mm),
        ):
            _put(out, key, value)
    elif fiche.type_fiche == 'onduleur':
        for key, value in (
            ('n_mppt', fiche.ond_n_mppt),
            ('mppt_v_min', fiche.ond_mppt_v_min),
            ('mppt_v_max', fiche.ond_mppt_v_max),
            ('v_max_abs', fiche.ond_v_max_abs),
            ('i_max_mppt_a', fiche.ond_i_max_mppt_a),
            ('ac_kw', fiche.ond_ac_kw),
            ('phases', fiche.ond_phases),
        ):
            _put(out, key, value)
    elif fiche.type_fiche == 'batterie':
        for key, value in (
            ('kwh_nominal', fiche.bat_kwh_nominal),
            ('kwh_usable', fiche.bat_kwh_usable),
            ('dod_pct', fiche.bat_dod_pct),
            ('v_nominal', fiche.bat_v_nominal),
            ('max_charge_kw', fiche.bat_max_charge_kw),
        ):
            _put(out, key, value)
    return out


def kit_from_produit(produit):
    """PV6 — construit un ``core.calepinage.types.Kit`` à partir des
    dimensions/puissance de la fiche technique MODULE (PV5) d'un produit.

    Mirrors la construction de ``KIT_VILLA_720`` : 1 module par table,
    orientation PORTRAIT, inclinaison 13°, sans faîtage — les seules valeurs
    fixes que la fiche technique ne porte pas encore ; seules les dimensions
    (``longueur_mm``/``largeur_mm``, converties en mètres) et la puissance
    (``pmax_wc``) viennent du produit. Toute valeur requise absente (produit
    sans fiche, ou l'un des trois champs non renseigné) → ``None`` : le
    moteur de calepinage ne devine jamais une géométrie. Lecture seule."""
    fiche = getattr(produit, 'fiche_technique', None)
    if fiche is None:
        return None
    if (fiche.longueur_mm is None or fiche.largeur_mm is None
            or fiche.pmax_wc is None):
        return None

    from core.calepinage.types import Kit, OrientationModule
    try:
        return Kit(
            code=produit.sku or ('PRODUIT_%s' % produit.pk),
            libelle=produit.nom,
            module_long_m=float(fiche.longueur_mm) / 1000.0,
            module_court_m=float(fiche.largeur_mm) / 1000.0,
            puissance_module_wc=float(fiche.pmax_wc),
            inclinaison_deg=13.0,
            orientation=OrientationModule.PORTRAIT,
            modules_par_table=1,
            faitage_m=0.0,
        )
    except ValueError:
        # dimensions incohérentes (ex. largeur > longueur) — jamais deviner.
        return None


def nb_produits_par_entite(company, entite_ids):
    """NTADM25 — nombre de produits ACTIFS par entité (NTADM2).

    Point d'entrée cross-app sanctionné pour ``apps.entites`` (vue consolidée
    « Groupe »), jamais un import direct de ``stock.models``. Les produits
    archivés sont exclus (même règle que la liste catalogue). Renvoie
    ``{entite_id: int}`` — une entité sans produit n'apparaît pas.
    """
    from django.db.models import Count

    from .models import Produit

    ids = [i for i in (entite_ids or []) if i is not None]
    if not ids:
        return {}
    lignes = (Produit.objects
              .filter(company=company, entite_id__in=ids, is_archived=False)
              .values('entite_id')
              .annotate(nb=Count('id')))
    return {ligne['entite_id']: ligne['nb'] for ligne in lignes}


# ══════════════════════════════════════════════════════════════════════════
# NTP2P4 — Budget d'engagement par département (lecture cross-app)
# ══════════════════════════════════════════════════════════════════════════
# ``installations`` (soumission d'une demande d'achat) lit le budget PAR ICI —
# jamais en important ``stock.models``. Tout est lecture seule ; l'écriture de
# l'engagement passe par ``stock.services``.

def budget_departement_actif(company):
    """True si le contrôle budgétaire dur est activé pour cette société.

    OFF par défaut (NTP2P4) : sans activation explicite, la soumission d'une
    demande d'achat n'est soumise à AUCUN contrôle budgétaire — comportement
    historique strictement inchangé."""
    if company is None:
        return False
    from .models import AchatsParametres
    params = AchatsParametres.objects.filter(company=company).first()
    return bool(params and params.budget_departement_actif)


def resoudre_budget_departement(company, departement_id, periode=None):
    """Budget applicable à ce département pour cette période, ou None.

    Le budget MENSUEL de la période visée l'emporte sur le budget ANNUEL de
    l'année (le mensuel est plus spécifique). ``periode`` est une ``date``
    (défaut : aujourd'hui, en heure locale)."""
    if company is None or not departement_id:
        return None
    from django.utils import timezone
    from .models import BudgetDepartement

    jour = periode or timezone.localdate()
    base = BudgetDepartement.objects.filter(
        company=company, departement_id=departement_id, actif=True,
        annee=jour.year)
    mensuel = base.filter(
        periodicite=BudgetDepartement.Periodicite.MENSUELLE,
        mois=jour.month).first()
    if mensuel is not None:
        return mensuel
    return base.filter(
        periodicite=BudgetDepartement.Periodicite.ANNUELLE, mois=0).first()


def consommation_budget(budget):
    """Détail ``engagé`` / ``réalisé`` / ``restant`` d'un budget.

    ``engage``   — engagements encore ACTIFS (demande soumise, pas de BCF) ;
    ``realise``  — engagements CONSOMMÉS (le bon de commande est passé) ;
    ``restant``  — alloué − (engagé + réalisé). Les engagements LIBÉRÉS
    (demande refusée/annulée) ne pèsent plus."""
    from decimal import Decimal
    from django.db.models import Sum
    from .models import EngagementBudget

    if budget is None:
        return None
    agreges = budget.engagements.values('statut').annotate(
        total=Sum('montant'))
    par_statut = {row['statut']: row['total'] or Decimal('0')
                  for row in agreges}
    engage = par_statut.get(EngagementBudget.Statut.ACTIF, Decimal('0'))
    realise = par_statut.get(EngagementBudget.Statut.CONSOMME, Decimal('0'))
    alloue = Decimal(budget.montant_alloue or 0)
    return {
        'budget_id': budget.pk,
        'departement_id': budget.departement_id,
        'periodicite': budget.periodicite,
        'annee': budget.annee,
        'mois': budget.mois,
        'montant_alloue': alloue,
        'engage': engage,
        'realise': realise,
        'consomme_total': engage + realise,
        'restant': alloue - (engage + realise),
        'taux_consommation_pct': (
            round(float((engage + realise) / alloue * 100), 2)
            if alloue else 0.0),
    }


def verifier_budget_disponible(company, departement_id, periode, montant):
    """NTP2P4 — le département a-t-il encore ``montant`` de disponible ?

    Renvoie un dict ``{'controle_actif', 'budget', 'restant', 'depassement',
    'suffisant', 'montant_manquant'}``. ``controle_actif=False`` (réglage OFF
    ou aucun budget configuré) ⇒ ``suffisant=True`` : jamais de blocage
    implicite. LECTURE SEULE — aucun engagement n'est posé ici."""
    from decimal import Decimal

    montant = Decimal(montant or 0)
    vide = {
        'controle_actif': False, 'budget': None, 'restant': None,
        'depassement': Decimal('0'), 'suffisant': True,
        'montant_manquant': Decimal('0'),
    }
    if not budget_departement_actif(company):
        return vide
    budget = resoudre_budget_departement(company, departement_id, periode)
    if budget is None:
        return vide
    detail = consommation_budget(budget)
    restant = detail['restant']
    manquant = montant - restant
    return {
        'controle_actif': True,
        'budget': budget,
        'restant': restant,
        'depassement': max(manquant, Decimal('0')),
        'suffisant': manquant <= 0,
        'montant_manquant': max(manquant, Decimal('0')),
    }


# ══════════════════════════════════════════════════════════════════════════
# NTP2P7 — Onboarding fournisseur (lecture)
# ══════════════════════════════════════════════════════════════════════════

def sod_stricte_active(company):
    """NTP2P37 — la séparation des tâches stricte est-elle activée ?

    OFF par défaut : sans activation, le créateur d'une demande d'achat peut
    encore l'approuver (comportement historique des structures à un seul
    décideur)."""
    if company is None:
        return False
    from .models import AchatsParametres
    params = AchatsParametres.objects.filter(company=company).first()
    return bool(params and params.sod_stricte)


def onboarding_fournisseur_obligatoire(company):
    """True si un dossier d'onboarding VALIDÉ est exigé avant tout BCF.

    OFF par défaut : comportement historique inchangé (seul le ``statut`` du
    fournisseur compte)."""
    if company is None:
        return False
    from .models import AchatsParametres
    params = AchatsParametres.objects.filter(company=company).first()
    return bool(params and params.onboarding_fournisseur_obligatoire)


def progression_onboarding(dossier):
    """Avancement d'un dossier : pièces requises reçues / total requis.

    Renvoie ``{'requis', 'recus', 'manquants', 'expires', 'progression_pct',
    'complet'}``. Une pièce EXPIRÉE ne compte pas comme reçue."""
    from .models import DocumentFournisseur

    requis = list(DocumentFournisseur.TYPES_REQUIS)
    if dossier is None:
        return {
            'requis': requis, 'recus': [], 'manquants': requis,
            'expires': [], 'progression_pct': 0, 'complet': False,
        }
    recus, expires = [], []
    for doc in dossier.documents.all():
        if doc.type_document not in requis:
            continue
        if not doc.file_key:
            continue
        if doc.est_valide():
            if doc.type_document not in recus:
                recus.append(doc.type_document)
        elif doc.type_document not in expires:
            expires.append(doc.type_document)
    manquants = [t for t in requis if t not in recus]
    return {
        'requis': requis,
        'recus': recus,
        'manquants': manquants,
        'expires': expires,
        'progression_pct': (
            round(len(recus) / len(requis) * 100) if requis else 100),
        'complet': not manquants,
    }


def dossier_onboarding_fournisseur(company, fournisseur_id):
    """Dossier d'onboarding scopé société, ou None."""
    if company is None or not fournisseur_id:
        return None
    from .models import DossierOnboardingFournisseur
    return DossierOnboardingFournisseur.objects.filter(
        company=company, fournisseur_id=fournisseur_id
    ).prefetch_related('documents').first()


def fournisseur_peut_recevoir_bcf(company, fournisseur_id):
    """NTP2P7 — le fournisseur peut-il recevoir un NOUVEAU bon de commande ?

    Renvoie ``(autorise: bool, motif: str)``. Quand le flag société est OFF
    (défaut), renvoie toujours ``(True, '')`` — comportement historique."""
    if not onboarding_fournisseur_obligatoire(company):
        return True, ''
    dossier = dossier_onboarding_fournisseur(company, fournisseur_id)
    if dossier is None:
        return False, (
            "Onboarding obligatoire : ce fournisseur n'a aucun dossier "
            "d'entrée en relation.")
    if not dossier.est_valide:
        detail = progression_onboarding(dossier)
        manquants = ', '.join(detail['manquants']) or 'aucune'
        return False, (
            f'Onboarding obligatoire : dossier « '
            f'{dossier.get_statut_display()} » '
            f'({detail["progression_pct"]}% complet, pièces manquantes : '
            f'{manquants}).')
    return True, ''


# ══════════════════════════════════════════════════════════════════════════
# NTP2P8 — Score de risque fournisseur (calcul PUR, aucun service externe)
# ══════════════════════════════════════════════════════════════════════════
# Score 0-100 où 100 = risque nul. On part de 100 et on retranche des
# PÉNALITÉS plafonnées, facteur par facteur, pour que le détail renvoyé soit
# lisible (« pourquoi ce fournisseur est-il à 45 ? ») et non une boîte noire.
#
# Barème (plafonds) :
#   ponctualité (OTD)    -45   taux de retard sur les BCF datés
#   documents légaux     -30   10 par pièce EXPIRÉE, 5 par pièce MANQUANTE
#   retours              -15   taux de retours fournisseur / BCF
#   litiges              -15   5 par réclamation ouverte
#   blocage              -25   statut de blocage du fournisseur
#
# Le barème est volontairement additif et borné : un fournisseur avec 3
# retards consécutifs (100 % de retard → -45) et un document expiré (-10)
# tombe à 45, donc sous la barre des 50 (critère d'acceptation NTP2P8).

PLAFOND_OTD = 45
PLAFOND_DOCUMENTS = 30
PLAFOND_RETOURS = 15
PLAFOND_LITIGES = 15
PLAFOND_BLOCAGE = 25

SEUIL_RISQUE_ELEVE = 50
SEUIL_RISQUE_MODERE = 75


def _facteur(code, libelle, penalite, plafond, detail):
    return {
        'code': code, 'libelle': libelle,
        'penalite': int(penalite), 'plafond': plafond, 'detail': detail,
    }


def _ponctualite_fournisseur(company, fournisseur_id):
    """Taux de retard : BCF dont la date confirmée dépasse la date prévue."""
    from django.db.models import F

    from .models import BonCommandeFournisseur

    qs = BonCommandeFournisseur.objects.filter(
        company=company, fournisseur_id=fournisseur_id,
        date_livraison_prevue__isnull=False,
        date_confirmee_fournisseur__isnull=False)
    total = qs.count()
    if not total:
        return 0, {'bcf_dates': 0, 'retards': 0, 'taux_retard_pct': 0}
    retards = qs.filter(
        date_confirmee_fournisseur__gt=F('date_livraison_prevue')
    ).count()
    taux = retards / total
    return round(taux * PLAFOND_OTD), {
        'bcf_dates': total, 'retards': retards,
        'taux_retard_pct': round(taux * 100),
    }


def _documents_fournisseur(company, fournisseur_id):
    """Pénalité documentaire : pièces légales expirées / manquantes."""
    dossier = dossier_onboarding_fournisseur(company, fournisseur_id)
    if dossier is None:
        # Aucun dossier ouvert : on ne pénalise QUE si la société exige
        # l'onboarding (sinon on punirait tout le référentiel historique).
        if onboarding_fournisseur_obligatoire(company):
            return PLAFOND_DOCUMENTS, {
                'dossier': None, 'expires': [], 'manquants': [],
                'motif': 'aucun dossier alors que l’onboarding est exigé',
            }
        return 0, {'dossier': None, 'expires': [], 'manquants': []}
    detail = progression_onboarding(dossier)
    # Une pièce EXPIRÉE figure aussi dans `manquants` (elle n'est plus « reçue »
    # — c'est voulu : elle doit bloquer comme une pièce absente). Mais pour le
    # SCORE elle ne se paie pas deux fois : on ne compte en « manquant » que ce
    # qui n'a jamais été fourni.
    jamais_fournis = [t for t in detail['manquants']
                      if t not in detail['expires']]
    penalite = min(
        PLAFOND_DOCUMENTS,
        10 * len(detail['expires']) + 5 * len(jamais_fournis))
    return penalite, {
        'dossier': dossier.pk, 'statut_dossier': dossier.statut,
        'expires': detail['expires'], 'manquants': detail['manquants'],
    }


def _retours_fournisseur(company, fournisseur_id):
    """Taux de retours : retours fournisseur rapportés au nombre de BCF."""
    from .models import BonCommandeFournisseur, RetourFournisseur

    bcf = BonCommandeFournisseur.objects.filter(
        company=company, fournisseur_id=fournisseur_id).count()
    retours = RetourFournisseur.objects.filter(
        company=company, fournisseur_id=fournisseur_id).exclude(
        statut=RetourFournisseur.Statut.ANNULE).count()
    if not bcf:
        return 0, {'bcf': 0, 'retours': retours, 'taux_retour_pct': 0}
    taux = min(retours / bcf, 1)
    return round(taux * PLAFOND_RETOURS), {
        'bcf': bcf, 'retours': retours, 'taux_retour_pct': round(taux * 100),
    }


def _litiges_fournisseur(company, fournisseur_id):
    """Réclamations ouvertes — lecture via ``litiges.selectors`` uniquement."""
    from apps.litiges.selectors import compte_reclamations_fournisseur

    compte = compte_reclamations_fournisseur(company, fournisseur_id)
    penalite = min(PLAFOND_LITIGES, 5 * compte['ouvertes'])
    return penalite, compte


def _blocage_fournisseur(fournisseur):
    from .models import Fournisseur

    statut = fournisseur.statut
    if statut == Fournisseur.Statut.BLOQUE_TOTAL:
        return PLAFOND_BLOCAGE, {'statut': statut}
    if statut in (Fournisseur.Statut.BLOQUE_COMMANDES,
                  Fournisseur.Statut.BLOQUE_PAIEMENTS):
        return 15, {'statut': statut}
    return 0, {'statut': statut}


def score_risque_fournisseur(company, fournisseur_id):
    """NTP2P8 — score de risque 0-100 d'un fournisseur (100 = risque nul).

    Calcul PUR (aucun service externe, aucun appel réseau). Renvoie
    ``{'fournisseur_id', 'score', 'niveau', 'facteurs': [...]}`` où chaque
    facteur porte sa pénalité, son plafond et son détail chiffré — le badge
    doit pouvoir expliquer le score, jamais l'asséner.

    Renvoie ``None`` si le fournisseur n'appartient pas à la société.
    """
    fournisseur = get_fournisseur_by_id(company, fournisseur_id)
    if fournisseur is None:
        return None

    p_otd, d_otd = _ponctualite_fournisseur(company, fournisseur.pk)
    p_doc, d_doc = _documents_fournisseur(company, fournisseur.pk)
    p_ret, d_ret = _retours_fournisseur(company, fournisseur.pk)
    p_lit, d_lit = _litiges_fournisseur(company, fournisseur.pk)
    p_blo, d_blo = _blocage_fournisseur(fournisseur)

    facteurs = [
        _facteur('ponctualite', 'Ponctualité de livraison (OTD)',
                 p_otd, PLAFOND_OTD, d_otd),
        _facteur('documents', 'Documents légaux',
                 p_doc, PLAFOND_DOCUMENTS, d_doc),
        _facteur('retours', 'Retours fournisseur',
                 p_ret, PLAFOND_RETOURS, d_ret),
        _facteur('litiges', 'Litiges ouverts',
                 p_lit, PLAFOND_LITIGES, d_lit),
        _facteur('blocage', 'Statut de blocage',
                 p_blo, PLAFOND_BLOCAGE, d_blo),
    ]
    penalite_totale = sum(f['penalite'] for f in facteurs)
    score = max(0, min(100, 100 - penalite_totale))
    if score < SEUIL_RISQUE_ELEVE:
        niveau = 'eleve'
    elif score < SEUIL_RISQUE_MODERE:
        niveau = 'modere'
    else:
        niveau = 'faible'
    return {
        'fournisseur_id': fournisseur.pk,
        'fournisseur_nom': fournisseur.nom,
        'score': score,
        'niveau': niveau,
        'penalite_totale': penalite_totale,
        'facteurs': facteurs,
    }


# ══════════════════════════════════════════════════════════════════════════
# NTP2P19 — Conformité fournisseur exportable (audit achats)
# ══════════════════════════════════════════════════════════════════════════

def _dernier_retard_otd(company, fournisseur_id, *, debut=None, fin=None):
    """Dernier retard constaté : ``(date_prevue, jours_de_retard)`` ou None."""
    from django.db.models import F

    from .models import BonCommandeFournisseur

    qs = BonCommandeFournisseur.objects.filter(
        company=company, fournisseur_id=fournisseur_id,
        date_livraison_prevue__isnull=False,
        date_confirmee_fournisseur__isnull=False,
        date_confirmee_fournisseur__gt=F('date_livraison_prevue'))
    if debut:
        qs = qs.filter(date_livraison_prevue__gte=debut)
    if fin:
        qs = qs.filter(date_livraison_prevue__lte=fin)
    dernier = qs.order_by('-date_livraison_prevue', '-id').first()
    if dernier is None:
        return None
    jours = (dernier.date_confirmee_fournisseur
             - dernier.date_livraison_prevue).days
    return dernier.date_livraison_prevue, jours


def _montant_achete(company, fournisseur_id, *, debut=None, fin=None):
    """Σ des lignes de BCF (HT interne) du fournisseur sur la période."""
    from decimal import Decimal
    from django.db.models import DecimalField, F, Sum
    from django.db.models.functions import Coalesce

    from .models import LigneBonCommandeFournisseur

    qs = LigneBonCommandeFournisseur.objects.filter(
        bon_commande__company=company,
        bon_commande__fournisseur_id=fournisseur_id)
    if debut:
        qs = qs.filter(bon_commande__date_commande__gte=debut)
    if fin:
        qs = qs.filter(bon_commande__date_commande__lte=fin)
    total = qs.aggregate(total=Coalesce(
        Sum(F('quantite') * F('prix_achat_unitaire'),
            output_field=DecimalField(max_digits=18, decimal_places=2)),
        Decimal('0'),
        output_field=DecimalField(max_digits=18, decimal_places=2)))['total']
    return total or Decimal('0')


def conformite_fournisseurs(company, *, debut=None, fin=None):
    """NTP2P19 — une ligne d'audit de conformité par fournisseur ACTIF.

    Cinq colonnes de conformité par fournisseur : statut d'onboarding
    (NTP2P7), score de risque (NTP2P8), documents expirés, dernier retard OTD,
    et montant total acheté sur la période. Lecture seule ; ``debut``/``fin``
    (dates) bornent le retard et le montant, jamais le référentiel lui-même.
    """
    from .models import Fournisseur

    lignes = []
    fournisseurs = Fournisseur.objects.filter(
        company=company, is_archived=False).order_by('nom', 'id')
    for fournisseur in fournisseurs:
        dossier = dossier_onboarding_fournisseur(company, fournisseur.pk)
        progression = progression_onboarding(dossier)
        score = score_risque_fournisseur(company, fournisseur.pk) or {}
        retard = _dernier_retard_otd(
            company, fournisseur.pk, debut=debut, fin=fin)
        lignes.append({
            'fournisseur_id': fournisseur.pk,
            'fournisseur': fournisseur.nom,
            'statut_onboarding': (
                dossier.get_statut_display() if dossier is not None
                else 'Aucun dossier'),
            'score_risque': score.get('score'),
            'niveau_risque': score.get('niveau', ''),
            'documents_expires': ', '.join(progression['expires']),
            'documents_manquants': ', '.join(progression['manquants']),
            'dernier_retard_le': retard[0] if retard else None,
            'dernier_retard_jours': retard[1] if retard else None,
            'montant_achete': _montant_achete(
                company, fournisseur.pk, debut=debut, fin=fin),
        })
    return lignes


# -- Groupe NTWMS -- couche ENTREPOT (casiers, strategies de picking, tarifs) --
# Definis dans `selectors_wms.py` ; re-exportes ici pour que les appelants
# continuent d'ecrire `from apps.stock.selectors import ...`.
from .selectors_wms import (  # noqa: E402,F401
    classe_abc_produit,
    classes_abc_produits,
    comparer_tarifs_transporteurs,
    localisation_casiers,
    planning_quais,
    resoudre_allocation_picking,
    resoudre_code_scanne,
    strategie_picking_produit,
)
