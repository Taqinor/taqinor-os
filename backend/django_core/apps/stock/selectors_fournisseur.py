"""Groupe NTSCM — Sélecteurs de PERFORMANCE fournisseur (lecture seule).

  * NTSCM8  — OTIF réel (On-Time-In-Full) promis-vs-livré ;
  * NTSCM11 — délai MESURÉ vs délai ANNONCÉ, et le point de commande qui en
    découle ;
  * NTSCM26 — coût total d'acquisition (TCO) au-delà du prix catalogue.

Toutes ces valeurs sont INTERNES (elles reposent sur des prix d'achat) : elles
ne doivent jamais atterrir dans une sortie client-facing.

Aucune fonction ne lit l'horloge quand l'appelant fournit ``aujourdhui`` — les
fenêtres glissantes sont donc reproductibles en test.
"""
from decimal import Decimal

from django.utils import timezone

# Fenêtre glissante par défaut des indicateurs fournisseur.
FENETRE_MOIS_DEFAUT = 12
# Au-delà de cet écart relatif entre délai annoncé et délai mesuré, c'est le
# délai MESURÉ qui pilote le point de commande (NTSCM11).
SEUIL_ECART_DELAI_PCT = Decimal('20')


def _dec(value):
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001 — valeur non numérique -> 0, jamais de crash.
        return Decimal('0')


def _fmt_dec(value):
    """Décimal normalisé (``'8.00'`` -> ``'8'``). Même helper que
    ``apps.mrp.selectors._fmt_dec`` : sans lui, la même grandeur se sérialise
    différemment selon le chemin de calcul et les tests d'API deviennent
    instables."""
    value = value if isinstance(value, Decimal) else _dec(value)
    if value == 0:
        return '0'
    s = format(value, 'f')
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s or '0'


def _debut_fenetre(fenetre_mois, aujourdhui=None):
    """Date de début d'une fenêtre glissante en MOIS (30 jours par mois —
    approximation assumée, identique pour tous les fournisseurs comparés)."""
    import datetime

    aujourdhui = aujourdhui or timezone.localdate()
    try:
        mois = int(fenetre_mois or FENETRE_MOIS_DEFAUT)
    except (TypeError, ValueError):
        mois = FENETRE_MOIS_DEFAUT
    mois = max(1, mois)
    return aujourdhui - datetime.timedelta(days=30 * mois)


def _bcf_de_la_fenetre(company, fournisseur, debut):
    from .models import BonCommandeFournisseur
    return (BonCommandeFournisseur.objects
            .filter(company=company, fournisseur=fournisseur,
                    date_commande__isnull=False,
                    date_commande__gte=debut)
            .exclude(statut=BonCommandeFournisseur.Statut.ANNULE)
            .prefetch_related('lignes', 'receptions'))


def _derniere_reception_confirmee(bc):
    """Date de la DERNIÈRE réception confirmée d'un BCF (la livraison est
    « faite » quand la dernière ligne est arrivée), ou ``None``."""
    dates = [rec.date_reception
             for rec in bc.receptions.all()
             if rec.statut == 'confirme' and rec.date_reception]
    return max(dates) if dates else None


# ═══════════════════════════════════════════════════════════════════════════
# NTSCM8 — OTIF réel (On-Time-In-Full)
# ═══════════════════════════════════════════════════════════════════════════

def otif_fournisseur(company, fournisseur, *, fenetre_mois=None,
                     aujourdhui=None):
    """Taux OTIF = livraisons À L'HEURE **ET** COMPLÈTES / total livraisons.

    Différence assumée avec le « taux de service » générique de FG59 : une
    commande livrée COMPLÈTE mais EN RETARD compte comme NON-OTIF, et
    réciproquement. Les deux conditions doivent tenir ensemble — c'est tout
    l'intérêt de l'indicateur.

    Référence de ponctualité : ``date_livraison_prevue`` du BCF (XPUR7). Un
    BCF sans date prévue n'entre pas dans le calcul (on ne juge pas une
    promesse qui n'a jamais été faite).

    Renvoie ``{fenetre_mois, debut, total_livraisons, nb_otif, nb_retard,
    nb_incomplet, taux_otif_pct}``. ``taux_otif_pct`` vaut ``None`` quand
    aucune livraison n'est mesurable — jamais 0 % (qui se lirait comme un
    fournisseur catastrophique).
    """
    debut = _debut_fenetre(fenetre_mois, aujourdhui)
    total = a_lheure_et_complet = en_retard = incomplet = 0

    for bc in _bcf_de_la_fenetre(company, fournisseur, debut):
        if not bc.date_livraison_prevue:
            continue
        recue_le = _derniere_reception_confirmee(bc)
        if recue_le is None:
            continue
        total += 1
        ponctuel = recue_le <= bc.date_livraison_prevue
        lignes = list(bc.lignes.all())
        commande = sum(int(li.quantite or 0) for li in lignes)
        recu = sum(int(li.quantite_recue or 0) for li in lignes)
        complet = commande > 0 and recu >= commande
        if not ponctuel:
            en_retard += 1
        if not complet:
            incomplet += 1
        if ponctuel and complet:
            a_lheure_et_complet += 1

    taux = None
    if total:
        taux = (_dec(a_lheure_et_complet) / _dec(total)
                * Decimal('100')).quantize(Decimal('0.01'))
    return {
        'fournisseur_id': fournisseur.id,
        'fenetre_mois': int(fenetre_mois or FENETRE_MOIS_DEFAUT),
        'debut': debut.isoformat(),
        'total_livraisons': total,
        'nb_otif': a_lheure_et_complet,
        'nb_retard': en_retard,
        'nb_incomplet': incomplet,
        'taux_otif_pct': _fmt_dec(taux) if taux is not None else None,
    }


# ═══════════════════════════════════════════════════════════════════════════
# NTSCM11 — Délai MESURÉ vs délai ANNONCÉ (par produit, pas juste par commande)
# ═══════════════════════════════════════════════════════════════════════════

def delai_mesure_vs_annonce(company, fournisseur, produit=None, *,
                            fenetre_mois=None, aujourdhui=None,
                            seuil_ecart_pct=None):
    """Compare le délai ANNONCÉ (catalogue) au délai RÉEL mesuré.

    Annoncé : ``PrixFournisseur.delai_livraison_jours`` (XPUR7) du couple
    produit×fournisseur — ou sa moyenne sur tous les produits du fournisseur
    quand ``produit`` n'est pas précisé.
    Mesuré : ``date_commande`` → dernière réception confirmée, sur la fenêtre.

    Renvoie ``{delai_annonce_jours, delai_mesure_jours, ecart_jours,
    ecart_type_jours, ecart_pct, utiliser_delai_reel, delai_retenu_jours,
    nb_mesures}``. ``utiliser_delai_reel`` est vrai quand l'écart relatif
    dépasse le seuil (défaut 20 %) : c'est CE délai qu'il faut passer au
    calcul de point de commande.
    """
    from .models import PrixFournisseur

    debut = _debut_fenetre(fenetre_mois, aujourdhui)
    seuil = (_dec(seuil_ecart_pct) if seuil_ecart_pct is not None
             else SEUIL_ECART_DELAI_PCT)

    # ── Délai ANNONCÉ ──────────────────────────────────────────────────────
    tarifs = PrixFournisseur.objects.filter(
        company=company, fournisseur=fournisseur,
        delai_livraison_jours__isnull=False)
    if produit is not None:
        tarifs = tarifs.filter(produit=produit)
    annonces = [int(t.delai_livraison_jours) for t in tarifs]
    delai_annonce = (sum(annonces) / len(annonces)) if annonces else None

    # ── Délai MESURÉ ───────────────────────────────────────────────────────
    mesures = []
    produit_id = getattr(produit, 'id', produit)
    for bc in _bcf_de_la_fenetre(company, fournisseur, debut):
        if produit_id is not None and not any(
                li.produit_id == produit_id for li in bc.lignes.all()):
            continue
        recue_le = _derniere_reception_confirmee(bc)
        if recue_le is None:
            continue
        jours = (recue_le - bc.date_commande).days
        if jours >= 0:
            mesures.append(jours)

    delai_mesure = (sum(mesures) / len(mesures)) if mesures else None
    ecart_type = None
    if len(mesures) >= 2:
        moyenne = delai_mesure
        variance = sum((m - moyenne) ** 2 for m in mesures) / len(mesures)
        ecart_type = variance ** 0.5

    ecart_jours = ecart_pct = None
    utiliser_reel = False
    if delai_annonce is not None and delai_mesure is not None:
        ecart_jours = delai_mesure - delai_annonce
        if delai_annonce > 0:
            ecart_pct = (_dec(ecart_jours) / _dec(delai_annonce)
                         * Decimal('100')).quantize(Decimal('0.01'))
            utiliser_reel = ecart_pct > seuil
        elif delai_mesure > 0:
            # Annoncé à 0 jour mais réellement livré en N jours : l'écart est
            # infini en relatif — le délai réel s'impose.
            utiliser_reel = True

    if utiliser_reel:
        delai_retenu = delai_mesure
    elif delai_annonce is not None:
        delai_retenu = delai_annonce
    else:
        delai_retenu = delai_mesure

    return {
        'fournisseur_id': fournisseur.id,
        'produit_id': produit_id,
        'fenetre_mois': int(fenetre_mois or FENETRE_MOIS_DEFAUT),
        'nb_mesures': len(mesures),
        'delai_annonce_jours': (round(delai_annonce, 1)
                                if delai_annonce is not None else None),
        'delai_mesure_jours': (round(delai_mesure, 1)
                               if delai_mesure is not None else None),
        'ecart_jours': (round(ecart_jours, 1)
                        if ecart_jours is not None else None),
        'ecart_type_jours': (round(ecart_type, 1)
                             if ecart_type is not None else None),
        'ecart_pct': _fmt_dec(ecart_pct) if ecart_pct is not None else None,
        'seuil_ecart_pct': _fmt_dec(seuil),
        'utiliser_delai_reel': utiliser_reel,
        'delai_retenu_jours': (round(delai_retenu, 1)
                               if delai_retenu is not None else None),
    }


def point_de_commande_avec_delai_reel(company, produit, *,
                                      avg_daily_consumption,
                                      current_stock=None, aujourdhui=None,
                                      safety_stock=0, fenetre_mois=None,
                                      seuil_ecart_pct=None):
    """Point de commande calculé avec le délai qui FAIT FOI (NTSCM11).

    Enveloppe ``core.stock_reorder.predict_reorder`` (fondation pure, jamais
    modifiée) en lui passant ``lead_time_days`` = délai RÉEL quand l'écart
    mesuré dépasse le seuil, délai annoncé sinon. Sans fournisseur ni délai
    connu, on retombe sur 0 — comportement historique.
    """
    from core.stock_reorder import predict_reorder

    fournisseur = getattr(produit, 'fournisseur', None)
    detail = None
    lead_time = 0
    if fournisseur is not None:
        detail = delai_mesure_vs_annonce(
            company, fournisseur, produit, fenetre_mois=fenetre_mois,
            aujourdhui=aujourdhui, seuil_ecart_pct=seuil_ecart_pct)
        lead_time = detail['delai_retenu_jours'] or 0

    resultat = predict_reorder(
        current_stock=(produit.quantite_stock if current_stock is None
                       else current_stock),
        today=(aujourdhui or timezone.localdate()),
        avg_daily_consumption=avg_daily_consumption,
        lead_time_days=lead_time,
        safety_stock=safety_stock)
    return {'delai': detail, 'lead_time_days': lead_time,
            'reorder_point': resultat.reorder_point,
            'suggested_qty': resultat.suggested_qty,
            'stockout_date': (resultat.stockout_date.isoformat()
                              if resultat.stockout_date else None)}


# ═══════════════════════════════════════════════════════════════════════════
# NTSCM26 — Coût total d'acquisition (TCO) par fournisseur
# ═══════════════════════════════════════════════════════════════════════════

def cout_total_acquisition(company, fournisseur, produit, *,
                           cout_rupture_jour=None, fenetre_mois=None,
                           aujourdhui=None):
    """TCO d'un produit chez un fournisseur : prix nu + retard + qualité.

    * prix nu — ``PrixFournisseur.prix_achat`` (le seul chiffre que FG58
      comparait jusqu'ici) ;
    * coût du retard — jours de retard moyens × ``cout_rupture_jour``
      (paramétrable ; à défaut le coût de retard vaut 0, jamais un chiffre
      inventé) ;
    * coût qualité — ``cout_impact_mad`` moyen des incidents (NTSCM9) du
      couple fournisseur×produit sur la fenêtre.

    Le prix nu est TOUJOURS renvoyé à part : le TCO le complète, il ne le
    remplace jamais. INTERNE — jamais client-facing.
    """
    from .models import IncidentQualiteFournisseur, PrixFournisseur

    tarif = PrixFournisseur.objects.filter(
        company=company, fournisseur=fournisseur, produit=produit).first()
    prix_nu = _dec(tarif.prix_achat) if tarif else Decimal('0')

    delai = delai_mesure_vs_annonce(
        company, fournisseur, produit, fenetre_mois=fenetre_mois,
        aujourdhui=aujourdhui)
    retard_jours = max(_dec(delai['ecart_jours'] or 0), Decimal('0'))
    cout_jour = _dec(cout_rupture_jour or 0)
    cout_retard = (retard_jours * cout_jour).quantize(Decimal('0.01'))

    debut = _debut_fenetre(fenetre_mois, aujourdhui)
    incidents = list(IncidentQualiteFournisseur.objects.filter(
        company=company, fournisseur=fournisseur, produit=produit,
        date_incident__gte=debut, cout_impact_mad__isnull=False))
    cout_qualite = Decimal('0')
    if incidents:
        total = sum((_dec(i.cout_impact_mad) for i in incidents),
                    Decimal('0'))
        cout_qualite = (total / len(incidents)).quantize(Decimal('0.01'))

    tco = (prix_nu + cout_retard + cout_qualite).quantize(Decimal('0.01'))
    return {
        'fournisseur_id': fournisseur.id,
        'fournisseur_nom': fournisseur.nom,
        'produit_id': produit.id,
        'prix_nu': _fmt_dec(prix_nu),
        'retard_moyen_jours': _fmt_dec(retard_jours),
        'cout_rupture_jour': _fmt_dec(cout_jour),
        'cout_retard': _fmt_dec(cout_retard),
        'nb_incidents': len(incidents),
        'cout_qualite': _fmt_dec(cout_qualite),
        'tco': _fmt_dec(tco),
    }


def comparer_tco_fournisseurs(company, produit, *, cout_rupture_jour=None,
                              fenetre_mois=None, aujourdhui=None):
    """TCO de TOUS les fournisseurs tarifant ce produit, du moins cher au
    plus cher EN TCO (le prix nu reste affiché à côté)."""
    from .models import PrixFournisseur

    lignes = []
    tarifs = (PrixFournisseur.objects
              .filter(company=company, produit=produit)
              .select_related('fournisseur'))
    for tarif in tarifs:
        lignes.append(cout_total_acquisition(
            company, tarif.fournisseur, produit,
            cout_rupture_jour=cout_rupture_jour, fenetre_mois=fenetre_mois,
            aujourdhui=aujourdhui))
    lignes.sort(key=lambda ligne: _dec(ligne['tco']))
    return lignes
