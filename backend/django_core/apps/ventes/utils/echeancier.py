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


def schedule_for_devis(devis):
    """Liste ordonnée [(clé, pourcentage)] selon le mode du devis.

    Si le devis porte un ``echeancier`` JSON personnalisé (FG46), il prend le
    dessus et est converti en liste de (libelle, pct_or_montant) avec les clés
    canoniques. La dernière tranche est toujours recalculée comme « reste »
    dans ``next_tranche`` — le pourcentage ici est indicatif.

    Sinon, lit l'échéancier éditable de la société (Paramètres → Devis) ;
    repli sur PAYMENT_TERMS_BY_MODE si non configuré (comportement historique).
    """
    custom = getattr(devis, 'echeancier', None)
    if custom:
        try:
            entries = list(custom)
            if entries:
                return [
                    (e.get('type', f'tranche_{i}'), float(e.get('pct_or_montant', 0)))
                    for i, e in enumerate(entries)
                ]
        except (TypeError, AttributeError):
            pass  # écheancier malformé → repli sur le défaut

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
    """Taux de TVA mélangé du devis (TVA/HT×100), pour l'étiquette du PDF.

    A3 — sur un devis à deux options accepté, le taux est celui de l'option
    retenue (mêmes lignes que la facture)."""
    from apps.ventes.utils.options import option_totaux
    opt = option_totaux(devis)
    ht = Decimal(str(opt['ht']))
    if ht <= 0:
        return Decimal(str(devis.taux_tva))
    return _q(Decimal(str(opt['tva'])) / ht * 100)


def _tranche_label(key, devis, index):
    """Libellé d'une tranche : extrait du custom écheancier ou depuis TRANCHE_LABELS."""
    custom = getattr(devis, 'echeancier', None)
    if custom:
        try:
            return list(custom)[index].get('libelle') or TRANCHE_LABELS.get(key, key)
        except (IndexError, TypeError):
            pass
    return TRANCHE_LABELS.get(key, key.capitalize())


def _tranche_type(key):
    """Type Facture d'une tranche : depuis TRANCHE_TYPE ou INTERMEDIAIRE par défaut."""
    return TRANCHE_TYPE.get(key, Facture.TypeFacture.INTERMEDIAIRE)


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

    # A3 — l'option acceptée est autoritative : on facture UNIQUEMENT les lignes
    # de l'option retenue (batterie exclue/incluse selon le choix), au centime.
    # Sans vraie deuxième option, ce sont les totaux complets — inchangé.
    from apps.ventes.utils.options import option_totaux
    opt = option_totaux(devis)
    total_ht = Decimal(str(opt['ht']))
    total_tva = Decimal(str(opt['tva']))
    total_ttc = Decimal(str(opt['ttc']))

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
        'label': _tranche_label(key, devis, index),
        'type': _tranche_type(key),
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
            created_by=user,
            company=company,
        )

    from apps.ventes.utils.company_settings import numbering_config
    cfg = numbering_config(company, 'facture')
    return create_with_reference(
        Facture, cfg['prefix'], company, _create,
        padding=cfg['padding'], period=cfg['period'])


def solde_devis(devis):
    """Solde du devis : total, facturé, payé, restant (Decimals).

    A3 — le total de référence est celui de l'option acceptée (mêmes lignes que
    les factures de l'échéancier) ; sans vraie deuxième option, total complet."""
    from apps.ventes.utils.options import option_totaux
    actives = factures_actives(devis)
    total = Decimal(str(option_totaux(devis)['ttc']))
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
