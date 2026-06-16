"""Échéancier devis → factures.

Une seule source pour les pourcentages : ``PAYMENT_TERMS_BY_MODE`` du moteur de
devis (déjà utilisé par tous les PDF). À partir d'un devis ACCEPTÉ on génère, à
la demande, des factures de tranche séparément numérotées et postées :

    Résidentiel / Agricole : 30 % acompte · 60 % matériel · 10 % solde
    Industriel / Commercial : 50 % acompte · 40 % matériel · 10 % solde

Règles :
  * chaque tranche non finale vaut EXACTEMENT son pourcentage du TTC du devis ;
  * la DERNIÈRE tranche (solde) vaut le RESTE (total devis − déjà facturé) afin
    que la somme des factures égale toujours le total du devis, au centime près ;
  * le TVA/HT de chaque tranche est le total devis × pourcentage, ce qui
    conserve le poids du split 10/20 ; le taux affiché est le taux mélangé.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from apps.ventes.models import Facture

# Ordre canonique des tranches.
TRANCHE_ORDER = ['acompte', 'materiel', 'solde']
TRANCHE_LABELS = {
    'acompte': 'Acompte',
    'materiel': 'Livraison du matériel',
    'solde': 'Solde',
}
TRANCHE_TYPE = {
    'acompte': Facture.TypeFacture.ACOMPTE,
    'materiel': Facture.TypeFacture.INTERMEDIAIRE,
    'solde': Facture.TypeFacture.SOLDE,
}


def _q(amount) -> Decimal:
    return Decimal(amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def mes_for_devis(devis):
    """Date de mise en service du chantier lié au devis (N30), ou None.

    Sert de défaut à la date de livraison/prestation d'une facture. Import local
    pour éviter tout cycle ventes ↔ installations."""
    if devis is None:
        return None
    try:
        from apps.installations.models import Installation
    except Exception:
        return None
    inst = Installation.objects.filter(devis=devis).exclude(
        date_mise_en_service__isnull=True).order_by('-id').first()
    return inst.date_mise_en_service if inst else None


def schedule_for_devis(devis):
    """Liste ordonnée [(clé, pourcentage)] selon le mode du devis.

    Lit l'échéancier éditable de la société (Paramètres → Devis) ; repli sur
    PAYMENT_TERMS_BY_MODE si non configuré (comportement historique)."""
    from apps.ventes.utils.company_settings import payment_terms_for
    mode = devis.mode_installation or 'residentiel'
    terms = payment_terms_for(getattr(devis, 'company', None), mode)
    return [(key, terms[key]) for key in TRANCHE_ORDER]


def factures_actives(devis):
    """Factures de tranche non annulées du devis, dans l'ordre de création."""
    return devis.factures.exclude(
        statut=Facture.Statut.ANNULEE
    ).order_by('id')


def blended_tva_pct(devis) -> Decimal:
    """Taux de TVA mélangé du devis (TVA/HT×100), pour l'étiquette du PDF."""
    ht = Decimal(str(devis.total_ht))
    if ht <= 0:
        return Decimal(str(devis.taux_tva))
    return _q(Decimal(str(devis.total_tva)) / ht * 100)


def next_tranche(devis):
    """Décrit la prochaine tranche à facturer, ou None si l'échéancier est complet.

    Retourne un dict : key, label, type, pourcentage, ht, tva, ttc, is_last.
    """
    schedule = schedule_for_devis(devis)
    existantes = list(factures_actives(devis))
    index = len(existantes)
    if index >= len(schedule):
        return None

    key, pct = schedule[index]
    is_last = index == len(schedule) - 1

    total_ht = Decimal(str(devis.total_ht))
    total_tva = Decimal(str(devis.total_tva))
    total_ttc = Decimal(str(devis.total_ttc))

    if is_last:
        # Le solde = reste exact pour que la somme égale le total du devis.
        deja_ht = sum((Decimal(str(f.total_ht)) for f in existantes), Decimal('0'))
        deja_tva = sum((Decimal(str(f.total_tva)) for f in existantes), Decimal('0'))
        deja_ttc = sum((Decimal(str(f.total_ttc)) for f in existantes), Decimal('0'))
        ht = _q(total_ht - deja_ht)
        tva = _q(total_tva - deja_tva)
        ttc = _q(total_ttc - deja_ttc)
    else:
        frac = Decimal(str(pct)) / Decimal('100')
        ht = _q(total_ht * frac)
        tva = _q(total_tva * frac)
        ttc = _q(total_ttc * frac)

    return {
        'key': key,
        'label': TRANCHE_LABELS[key],
        'type': TRANCHE_TYPE[key],
        'pourcentage': Decimal(str(pct)),
        'ht': ht,
        'tva': tva,
        'ttc': ttc,
        'is_last': is_last,
    }


def creer_facture_tranche(devis, user, company, create_with_reference):
    """Crée et retourne la prochaine facture de tranche (postée/Émise).

    Lève ValueError si le devis n'est pas accepté ou si l'échéancier est complet.
    ``create_with_reference`` est injecté (utils.references) pour la numérotation
    sans collision, identique au reste du module ventes.
    """
    if devis.statut != devis.Statut.ACCEPTE:
        raise ValueError("Le devis doit être au statut « Accepté ».")

    tr = next_tranche(devis)
    if tr is None:
        raise ValueError("Toutes les tranches de l'échéancier sont déjà facturées.")

    pct_label = int(tr['pourcentage']) if tr['pourcentage'] == int(tr['pourcentage']) \
        else tr['pourcentage']
    libelle = f"{tr['label']} {pct_label} % — devis {devis.reference}"

    def _create(ref):
        return Facture.objects.create(
            reference=ref,
            devis=devis,
            client=devis.client,
            statut=Facture.Statut.EMISE,
            type_facture=tr['type'],
            pourcentage=tr['pourcentage'],
            libelle=libelle,
            montant_ht=tr['ht'],
            montant_tva=tr['tva'],
            montant_ttc=tr['ttc'],
            taux_tva=blended_tva_pct(devis),
            # N30 : date de livraison/prestation par défaut = MES du chantier.
            date_livraison=mes_for_devis(devis),
            created_by=user,
            company=company,
        )

    from apps.ventes.utils.company_settings import doc_prefix
    return create_with_reference(
        Facture, doc_prefix(company, 'facture'), company, _create)


def solde_devis(devis):
    """Solde du devis : total, facturé, payé, restant (Decimals)."""
    actives = factures_actives(devis)
    total = Decimal(str(devis.total_ttc))
    facture = sum((Decimal(str(f.total_ttc)) for f in actives), Decimal('0'))
    paye = sum(
        (Decimal(str(p.montant)) for f in actives for p in f.paiements.all()),
        Decimal('0'),
    )
    # Avoirs (notes de crédit) actifs : réduisent le restant dû. Aucun avoir
    # → 0 → solde historique strictement inchangé.
    avoirs = sum(
        (Decimal(str(a.total_ttc))
         for f in actives for a in f.avoirs.all() if a.statut != 'annulee'),
        Decimal('0'),
    )
    restant = total - paye - avoirs
    return {
        'total_ttc': _q(total),
        'facture': _q(facture),
        'paye': _q(paye),
        'avoirs': _q(avoirs),
        'restant': _q(restant),
        'tranches_total': len(schedule_for_devis(devis)),
        'tranches_facturees': actives.count(),
    }
