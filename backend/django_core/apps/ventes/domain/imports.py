"""NTMIG10/11 — création de Devis/Facture DEPUIS UNE MIGRATION.

Point d'entrée cross-app pour ``apps.migration`` (kits NTMIG8/12/13, moteur
``dataimport``) : deux créateurs d'en-tête (``creer_devis_import``,
``creer_facture_import``) et deux ajouteurs de lignes maître-détail
(``ajouter_lignes_devis_import``, ``ajouter_lignes_facture_import``) qui
délèguent TOUTE l'écriture ici — jamais ``apps.migration`` n'importe
``Devis``/``Facture``/``LigneDevis``/``LigneFacture`` en direct.

``Facture``/``LigneFacture`` sont physiquement dans ``apps.facturation``
(ODX17) ; ce module les importe via le SHIM ``apps.ventes.models`` (comme le
reste de ``domain/``, ex. ``domain/facturation_ops.py``), jamais
``apps.facturation.models`` directement — même convention que le reste du
paquet.

Numérotation via ``core.numbering.create_with_reference`` (jamais
``count()+1`` — une migration de 100 devis crée 100 références GAP-FREE), le
statut d'origine étant PRÉSERVÉ via une table de correspondance statut
source→statut côté ERP plutôt que forcé à ``brouillon``.

Retournent des TRIPLETS ``(statut, message, instance_ou_none)`` — et non les
doublets ``(statut, message)`` des autres importateurs XFLT22 (véhicules,
contrats…) — parce que l'appelant (``dataimport._commit_raw``) a besoin de
l'instance créée pour poser son ``ExternalRef`` (rapprochement des LIGNES
maître-détail à l'en-tête, NTMIG11 ; rollback futur, NTMIG6).
"""
from decimal import Decimal, InvalidOperation


def _decimal_ou_none(valeur):
    """Valeur → ``Decimal`` tolérant virgule/espaces, ``None`` si vide/illisible
    (jamais une exception — une cellule mal formée devient un champ NON
    renseigné, pas un crash de tout le lot)."""
    if valeur in (None, ''):
        return None
    brut = str(valeur).strip().replace('\xa0', '').replace(' ', '')
    brut = brut.replace(',', '.')
    try:
        return Decimal(brut)
    except (InvalidOperation, ValueError):
        return None


def _resoudre_client(company, ligne, external_system):
    """Client déjà migré (lot ``clients`` antérieur, dépendance NTMIG3) —
    external_id d'abord (le plus fiable, posé par le même projet de
    migration), sinon e-mail, sinon nom exact. ``None`` si rien ne matche."""
    from apps.crm.models import Client

    ext_id = ligne.get('client_external_id')
    if ext_id and external_system:
        from django.contrib.contenttypes.models import ContentType

        from apps.dataimport.models import ExternalRef

        ct = ContentType.objects.get_for_model(Client)
        ref = ExternalRef.objects.filter(
            company=company, external_system=external_system,
            external_id=str(ext_id), content_type=ct).first()
        if ref is not None:
            client = Client.objects.filter(
                company=company, pk=ref.object_id).first()
            if client is not None:
                return client

    email = ligne.get('client_email')
    if email:
        client = Client.objects.filter(
            company=company, email__iexact=str(email).strip()).first()
        if client is not None:
            return client

    nom = ligne.get('client_nom')
    if nom:
        client = Client.objects.filter(
            company=company, nom__iexact=str(nom).strip()).first()
        if client is not None:
            return client

    return None


# ─────────────────────────────────────────────────────────────────────────
# NTMIG10 — Devis (en-têtes)
# ─────────────────────────────────────────────────────────────────────────
def _statut_devis(valeur):
    from apps.ventes.models import Devis

    table = {
        'brouillon': Devis.Statut.BROUILLON, 'draft': Devis.Statut.BROUILLON,
        'envoye': Devis.Statut.ENVOYE, 'envoyé': Devis.Statut.ENVOYE,
        'sent': Devis.Statut.ENVOYE,
        'accepte': Devis.Statut.ACCEPTE, 'accepté': Devis.Statut.ACCEPTE,
        'accepted': Devis.Statut.ACCEPTE, 'won': Devis.Statut.ACCEPTE,
        'refuse': Devis.Statut.REFUSE, 'refusé': Devis.Statut.REFUSE,
        'lost': Devis.Statut.REFUSE, 'cancel': Devis.Statut.REFUSE,
        'expire': Devis.Statut.EXPIRE, 'expiré': Devis.Statut.EXPIRE,
        'expired': Devis.Statut.EXPIRE,
    }
    return table.get(str(valeur or '').strip().lower(), Devis.Statut.BROUILLON)


def creer_devis_import(company, ligne, *, external_system=None, user=None):
    """NTMIG10 — crée UN ``Devis`` (en-tête, sans lignes) depuis une ligne de
    migration déjà mappée par le kit source (``migration.kits``).

    Renvoie ``('cree', '', devis)``, ``('doublon', motif, None)`` (référence
    source déjà rattachée à un devis de cette société, rejeu idempotent) ou
    ``('erreur', motif, None)`` — jamais d'exception : une ligne fautive est
    SKIPPÉE par l'appelant, elle n'arrête jamais tout le lot.
    """
    from core.numbering import create_with_reference

    from apps.ventes.models import Devis

    client = _resoudre_client(company, ligne, external_system)
    if client is None:
        return ('erreur', (
            "client introuvable (client_external_id/client_email/"
            "client_nom absents ou non migrés)"), None)

    def _create(ref):
        return Devis.objects.create(
            company=company, reference=ref, client=client,
            statut=_statut_devis(ligne.get('statut')),
            created_by=user if getattr(user, 'pk', None) else None,
            note=(f"Migré (réf. source {ligne.get('reference_source')})"
                  if ligne.get('reference_source') else ''),
        )

    devis = create_with_reference(Devis, 'DEV', company, _create)
    return ('cree', '', devis)


# ─────────────────────────────────────────────────────────────────────────
# NTMIG10 — Factures (en-têtes)
# ─────────────────────────────────────────────────────────────────────────
def _statut_facture(valeur):
    from apps.ventes.models import Facture

    table = {
        'brouillon': Facture.Statut.BROUILLON, 'draft': Facture.Statut.BROUILLON,
        'emise': Facture.Statut.EMISE, 'émise': Facture.Statut.EMISE,
        'posted': Facture.Statut.EMISE, 'open': Facture.Statut.EMISE,
        'payee': Facture.Statut.PAYEE, 'payée': Facture.Statut.PAYEE,
        'paid': Facture.Statut.PAYEE, 'in_payment': Facture.Statut.PAYEE,
        'en_retard': Facture.Statut.EN_RETARD, 'overdue': Facture.Statut.EN_RETARD,
        'annulee': Facture.Statut.ANNULEE, 'annulée': Facture.Statut.ANNULEE,
        'cancel': Facture.Statut.ANNULEE, 'cancelled': Facture.Statut.ANNULEE,
    }
    return table.get(
        str(valeur or '').strip().lower(), Facture.Statut.BROUILLON)


def creer_facture_import(company, ligne, *, external_system=None, user=None):
    """NTMIG10 — crée UNE ``Facture`` (en-tête, type ``COMPLETE``, sans
    lignes) depuis une ligne de migration déjà mappée par le kit source.

    Même contrat de retour que :func:`creer_devis_import`. La facture migrée
    n'est jamais rattachée à un ``BonCommande``/``Devis`` de la chaîne
    historique (rule #4 : le moteur devis n'est pas concerné, seule
    l'EN-TÊTE facture est reconstituée) — ``devis``/``bon_commande`` restent
    ``None``, un lien optionnel additif que rien n'exige ici.
    """
    from core.numbering import create_with_reference

    from apps.ventes.models import Facture

    client = _resoudre_client(company, ligne, external_system)
    if client is None:
        return ('erreur', (
            "client introuvable (client_external_id/client_email/"
            "client_nom absents ou non migrés)"), None)

    def _create(ref):
        return Facture.objects.create(
            company=company, reference=ref, client=client,
            type_facture=Facture.TypeFacture.COMPLETE,
            statut=_statut_facture(ligne.get('statut')),
            libelle=(f"Migrée (réf. source {ligne.get('reference_source')})"
                     if ligne.get('reference_source') else ''),
        )

    facture = create_with_reference(Facture, 'FAC', company, _create)
    return ('cree', '', facture)


# ─────────────────────────────────────────────────────────────────────────
# NTMIG11 — lignes maître-détail (rattachées à un en-tête déjà importé)
# ─────────────────────────────────────────────────────────────────────────
#: Alias d'en-tête TOLÉRÉS pour le fichier « lignes » (normalisation
#: minuscule/espaces) — ce fichier n'a pas de kit dédié (NTMIG8/12/13 portent
#: sur les EN-TÊTES de document, pas sur leurs lignes).
_ALIAS_LIGNE = {
    'document_external_id': (
        'document_external_id', 'devis_external_id', 'facture_external_id',
        'document_id', 'ref_document', 'reference_document'),
    'designation': ('designation', 'désignation', 'libelle', 'libellé'),
    'quantite': ('quantite', 'quantité', 'qte', 'qty'),
    'prix_unitaire_ht': (
        'prix_unitaire_ht', 'prix_unitaire', 'pu_ht', 'prix', 'pu'),
    'taux_tva': ('taux_tva', 'tva', 'tva_pct'),
}


def _normaliser_ligne_document(row):
    """Ligne SOURCE (dict en-tête brut→valeur) → dict aux clés canoniques
    ci-dessus, insensible à la casse/aux espaces des en-têtes."""
    norm = {str(k).strip().lower(): v for k, v in (row or {}).items()}
    resultat = {}
    for champ, alias in _ALIAS_LIGNE.items():
        for nom in alias:
            if nom in norm and norm[nom] not in (None, ''):
                resultat[champ] = norm[nom]
                break
    return resultat


def ajouter_lignes_devis_import(company, external_system, rows, *, user=None):
    """NTMIG11 — crée des ``LigneDevis`` rattachées à des devis DÉJÀ importés
    (résolus par l'``external_id`` du DOCUMENT, posé à l'import de l'en-tête
    NTMIG10 via ``ExternalRef``).

    ``rows`` : lignes SOURCE brutes (dict en-tête→valeur, telles que rendues
    par ``dataimport.parse_rows``) — normalisées ici (alias tolérés).

    Renvoie ``(crees, erreurs)`` — ``erreurs`` = ``[{'ligne', 'raison'}]`` ;
    une ligne dont le document parent est introuvable (« orpheline ») part en
    erreur ligne, JAMAIS un crash de tout le fichier.
    """
    from django.contrib.contenttypes.models import ContentType

    from apps.dataimport.models import ExternalRef
    from apps.ventes.models import Devis, LigneDevis

    ct = ContentType.objects.get_for_model(Devis)
    crees, erreurs = 0, []
    for i, row in enumerate(rows, 1):
        ligne = _normaliser_ligne_document(row)
        doc_ext_id = str(ligne.get('document_external_id') or '').strip()
        if not doc_ext_id:
            erreurs.append({'ligne': i, 'raison':
                            'document_external_id manquant'})
            continue
        ref = ExternalRef.objects.filter(
            company=company, external_system=external_system,
            external_id=doc_ext_id, content_type=ct).first()
        devis = (Devis.objects.filter(company=company, pk=ref.object_id)
                 .first() if ref is not None else None)
        if devis is None:
            erreurs.append({'ligne': i, 'raison': (
                f'devis introuvable pour « {doc_ext_id} » (ligne orpheline '
                '— import de l\'en-tête manquant ou différent)')})
            continue
        designation = str(ligne.get('designation') or '').strip()
        if not designation:
            erreurs.append({'ligne': i, 'raison': 'désignation manquante'})
            continue
        LigneDevis.objects.create(
            devis=devis, designation=designation[:255],
            quantite=_decimal_ou_none(ligne.get('quantite')),
            prix_unitaire=_decimal_ou_none(ligne.get('prix_unitaire_ht')),
            taux_tva=_decimal_ou_none(ligne.get('taux_tva')))
        crees += 1
    return crees, erreurs


def ajouter_lignes_facture_import(company, external_system, rows, *,
                                  user=None):
    """NTMIG11 — crée des ``LigneFacture`` rattachées à des factures DÉJÀ
    importées. Même contrat que :func:`ajouter_lignes_devis_import`.

    ``LigneFacture.produit`` est un FK NON NULLABLE (contrairement à
    ``LigneDevis.produit``) : une ligne dont la désignation ne correspond à
    AUCUN produit du catalogue est une erreur ligne nommée (« produit
    introuvable pour… »), jamais une ligne créée sans produit ni un produit
    fabriqué à la volée.
    """
    from django.contrib.contenttypes.models import ContentType

    from apps.dataimport.models import ExternalRef
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture

    ct = ContentType.objects.get_for_model(Facture)
    crees, erreurs = 0, []
    for i, row in enumerate(rows, 1):
        ligne = _normaliser_ligne_document(row)
        doc_ext_id = str(ligne.get('document_external_id') or '').strip()
        if not doc_ext_id:
            erreurs.append({'ligne': i, 'raison':
                            'document_external_id manquant'})
            continue
        ref = ExternalRef.objects.filter(
            company=company, external_system=external_system,
            external_id=doc_ext_id, content_type=ct).first()
        facture = (
            Facture.objects.filter(company=company, pk=ref.object_id).first()
            if ref is not None else None)
        if facture is None:
            erreurs.append({'ligne': i, 'raison': (
                f'facture introuvable pour « {doc_ext_id} » (ligne orpheline '
                '— import de l\'en-tête manquant ou différent)')})
            continue
        designation = str(ligne.get('designation') or '').strip()
        if not designation:
            erreurs.append({'ligne': i, 'raison': 'désignation manquante'})
            continue
        produit = Produit.objects.filter(
            company=company, nom__iexact=designation).first()
        if produit is None:
            erreurs.append({'ligne': i, 'raison': (
                f'produit introuvable pour « {designation} » (LigneFacture '
                'exige un produit du catalogue)')})
            continue
        LigneFacture.objects.create(
            facture=facture, produit=produit, designation=designation[:255],
            quantite=_decimal_ou_none(ligne.get('quantite')) or Decimal('1'),
            prix_unitaire=(
                _decimal_ou_none(ligne.get('prix_unitaire_ht'))
                or Decimal('0')),
            taux_tva=_decimal_ou_none(ligne.get('taux_tva')))
        crees += 1
    return crees, erreurs
