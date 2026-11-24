"""Lectures du dossier contractuel servies à l'écran (formes :
contract_samples/dossier_contractuel.json et acte_contractuel.json).

Aucune écriture ici, sauf la préparation idempotente du dossier à la première
lecture (un chantier ancien ou créé à la main obtient ses actes à la première
ouverture de l'onglet — conception § 5), qui passe par ``services``.
"""
from . import contenu as K
from . import types as T


def _iso_dt(valeur):
    if valeur is None:
        return None
    texte = valeur.isoformat()
    return texte[:-6] + 'Z' if texte.endswith('+00:00') else texte


def _drapeaux(acte, lecture, actes_du_chantier):
    annule = acte.chantier.annule or acte.statut == T.ANNULE
    jumelle = any(a.pk != acte.pk and a.type == T.LIVRAISON == acte.type
                  and a.statut in (T.EMIS, T.SIGNE) for a in actes_du_chantier)
    peut_emettre = False
    if not annule and acte.statut == T.BROUILLON and not jumelle:
        vente = lecture.vente()
        peut_emettre = vente is not None and not (
            acte.type == T.CLOTURE and (K.reste_du(vente) or 0) > 0) \
            and not K.montants_figes(acte, lecture)
    return {
        'ecarte': jumelle,
        'peut_modifier': not annule and acte.statut == T.BROUILLON,
        'peut_emettre': peut_emettre,
        'peut_signer': (not annule and acte.statut == T.EMIS
                        and acte.type != T.CLOTURE),
        'peut_rouvrir': not annule and acte.statut == T.EMIS,
    }


def resume_acte(acte, lecture, actes_du_chantier, *, contenu_fr=None):
    """Le résumé d'un acte (une ligne du dossier)."""
    from .services import document_ged
    document = (document_ged(acte) if acte.statut in (T.EMIS, T.SIGNE)
                else None)
    drapeaux = _drapeaux(acte, lecture, actes_du_chantier)
    return {
        'id': acte.pk,
        'type': acte.type,
        'variante': acte.variante or '',
        'rang': T.RANGS[acte.type],
        'titre': K.titre_acte(acte.type, acte.variante, lecture.vente()),
        'reference': acte.reference,
        'statut': acte.statut,
        'version': acte.version,
        'personnalise': bool(acte.surcharges or acte.surcharges_ar),
        'ecarte': drapeaux['ecarte'],
        'emis_le': _iso_dt(acte.emis_le),
        'signe_le': _iso_dt(acte.signe_le),
        'signataire_nom': acte.signataire_nom or '',
        'mode_signature': acte.mode_signature or '',
        'avertissements': K.avertissements(acte, contenu_fr, lecture),
        'peut_modifier': drapeaux['peut_modifier'],
        'peut_emettre': drapeaux['peut_emettre'],
        'peut_signer': drapeaux['peut_signer'],
        'peut_rouvrir': drapeaux['peut_rouvrir'],
        'document_ged_id': document.pk if document is not None else None,
    }


def _actes(chantier):
    from ..models import ActeContractuel
    return list(ActeContractuel.objects.filter(
        company=chantier.company, chantier=chantier).order_by('id'))


def _ordre(acte):
    variantes = {'': 0, T.RESTE_A_REGLER: 0, T.TRANCHE_REGLEE: 1}
    return (T.RANGS[acte.type], variantes.get(acte.variante, 2), acte.pk)


def _prochaine_action(chantier, actes, vente):
    """Le premier acte non terminé dans l'ordre des rangs ; None quand tout
    est fait, sans devis ou chantier annulé."""
    if chantier.annule or vente is None:
        return None
    for rang in (1, 2, 3, 4):
        groupe = [a for a in actes if T.RANGS[a.type] == rang
                  and a.statut != T.ANNULE]
        if not groupe:
            continue
        termines = (T.EMIS, T.SIGNE) if rang == 4 else (T.SIGNE,)
        if any(a.statut in termines for a in groupe):
            continue
        emis = next((a for a in groupe if a.statut == T.EMIS), None)
        acte = emis or groupe[0]
        if rang == 1:
            libelle = ('Faire signer le contrat' if emis
                       else 'Envoyer et faire signer le contrat')
        elif rang == 2:
            libelle = 'Faire signer la livraison du matériel'
        elif rang == 3:
            libelle = 'Faire signer la réception des travaux'
        elif (K.reste_du(vente) or 0) > 0:
            libelle = ('Solde non réglé : enregistrez le paiement avant de '
                       'remettre le quitus')
        else:
            libelle = 'Remettre le quitus et le certificat de garantie'
        return {'acte_id': acte.pk, 'type': acte.type, 'libelle': libelle}
    return None


def dossier_du_chantier(chantier, user=None):
    """Le dossier contractuel d'un chantier (forme de
    ``dossier_contractuel.json``) ; prépare les cinq actes s'ils manquent."""
    from .services import preparer_dossier
    if not chantier.annule:
        preparer_dossier(chantier, user)
    actes = sorted(_actes(chantier), key=_ordre)
    lecture = K.Lecture(chantier)
    vente = lecture.vente()
    client = K._bloc_client(chantier)
    devis = getattr(chantier, 'devis', None)
    return {
        'chantier': {
            'id': chantier.pk,
            'reference': chantier.reference or '',
            'annule': bool(chantier.annule),
            'devis_id': getattr(devis, 'pk', None),
            'devis_reference': getattr(devis, 'reference', '') or '',
        },
        'client': client['nom_complet'],
        'prix_ttc': K._s(vente['prix_ttc']) if vente else None,
        'regle_ttc': K._s(vente['paye']) if vente else None,
        'reste_ttc': K._s(K.reste_du(vente)) if vente else None,
        'prochaine_action': _prochaine_action(chantier, actes, vente),
        'actes': [resume_acte(a, lecture, actes) for a in actes],
    }


def detail_acte(acte, langue='fr'):
    """Le détail d'un acte dans une langue (résumé + contenu)."""
    lecture = K.Lecture(acte.chantier)
    actes = _actes(acte.chantier)
    contenu = K.contenu_de(acte, langue, lecture)
    contenu_fr = contenu if langue == 'fr' else None
    detail = resume_acte(acte, lecture, actes, contenu_fr=contenu_fr)
    detail.update({
        'chantier': {'id': acte.chantier_id,
                     'reference': acte.chantier.reference or ''},
        'langue': langue,
        'langues': list(T.LANGUES),
        'sections_personnalisees': K.sections_personnalisees(acte, langue),
        'sections_modifiables': K.sections_modifiables(acte.type, langue),
        'contenu': contenu,
    })
    return detail


def acte_de_la_societe(company, pk):
    """L'acte ``pk`` de la société ``company`` (ou None) — la portée de rôle
    est appliquée ensuite par la vue, sur le chantier."""
    from ..models import ActeContractuel
    if company is None:
        return None
    return (ActeContractuel.objects
            .select_related('chantier', 'chantier__devis', 'chantier__client',
                            'chantier__company')
            .filter(company=company, pk=pk).first())
