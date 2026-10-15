"""ENF1 — prépare la base JETABLE du job `api-fuzz`.

À lancer depuis ``backend/django_core``, après seed_demo + seed_catalogue :
    FUZZ_PASSWORD=... python ../../scripts/fuzz/prepare_fuzz_env.py ETAT.json

1. Crée/actualise le compte dédié ``fuzz_admin`` (admin, protégé) dans la
   société démo ``taqinor-demo`` — jamais ``demo_admin`` : le fuzzeur écrit
   partout, y compris sur les utilisateurs et la société ; un compte à lui
   seul garde ``demo_admin`` (e2e, QA nocturne) hors de portée et donne au
   crochet ``before_call`` un id précis à protéger. Le mot de passe est
   ALÉATOIRE, tiré par le workflow (``FUZZ_PASSWORD``, masqué) — jamais en
   dur.
2. Inventorie, pour chaque NOM de champ clé étrangère des modèles Django,
   les ids qui EXISTENT dans la société de fuzz (cluster C12 « Clé primaire
   0 non valide ») ; lus par ``scripts/fuzz/schemathesis_hooks.py``.
3. ENF11 — sème UNE ligne par modèle référencé que la base démo n'a pas
   (``SEMEURS``) et inventorie des ids PAR CHEMIN (``REGLES_PAR_CHEMIN``)
   quand un même nom de champ vise des modèles différents selon l'app.
4. Écrit l'état (ids du compte, de la société, tables des ids FK) en JSON.

Refuse de tourner hors DEBUG (même garde qu'ERR88 sur seed_demo).
"""
from __future__ import annotations

import json
import os
import sys

USERNAME = 'fuzz_admin'
SLUG_DEMO = 'taqinor-demo'
MAX_IDS_PAR_CHAMP = 25


def demarrer_django():
    sys.path.insert(0, os.getcwd())
    os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                          'erp_agentique.settings.dev')
    import django
    django.setup()


def preparer_compte(company, password):
    from django.apps import apps
    from django.core.management import call_command

    user_model = apps.get_model('authentication', 'CustomUser')
    user, _ = user_model.objects.get_or_create(
        username=USERNAME,
        defaults={'email': 'fuzz_admin@taqinor.local', 'company': company},
    )
    user.company = company
    user.role_legacy = user_model.ROLE_ADMIN
    user.is_staff = True
    user.is_active = True
    user.is_protected = True
    user.set_password(password)
    user.save()
    user.societes_autorisees.add(company)
    # Rattache le rôle système « admin » (comptes sans rôle fin, init_roles).
    call_command('init_roles')
    user.refresh_from_db()
    return user


def _a_un_champ_company(modele):
    return any(getattr(f, 'name', None) == 'company'
               for f in modele._meta.get_fields())


def _ids_existants(modele, company, cache):
    from django.apps import apps

    if modele in cache:
        return cache[modele]
    company_model = apps.get_model('authentication', 'Company')
    ids = set()
    try:
        qs = modele._default_manager.all()
        if modele is company_model:
            qs = qs.filter(pk=company.pk)
        elif _a_un_champ_company(modele):
            qs = qs.filter(company=company)
        valeurs = qs.order_by('pk').values_list('pk', flat=True)
        ids = {v for v in valeurs[:MAX_IDS_PAR_CHAMP]
               if isinstance(v, int) and not isinstance(v, bool)}
    except Exception as exc:  # table absente / manager exotique : ignoré
        print(f'  (ignoré) {modele._meta.label}: {exc}', file=sys.stderr)
    cache[modele] = ids
    return ids


def _cibles_par_nom():
    from django.apps import apps

    cibles = {}
    for modele in apps.get_models():
        for champ in modele._meta.get_fields():
            # ENF11 — les M2M DIRECTS (``entites_visibles``…) sont des FK du
            # corps comme les autres : leurs ids doivent être connus aussi
            # (``concrete`` est faux pour un M2M, qui n'a pas de colonne).
            directe_m2m = (getattr(champ, 'many_to_many', False)
                           and not getattr(champ, 'auto_created', False))
            if not (getattr(champ, 'is_relation', False)
                    and (getattr(champ, 'concrete', False) or directe_m2m)):
                continue
            cible = champ.related_model
            if cible is None or isinstance(cible, str):
                continue
            noms = {champ.name}
            if champ.many_to_one or champ.one_to_one:
                noms.add(champ.attname)
            for nom in noms - {'id', 'pk'}:
                cibles.setdefault(nom, set()).add(cible)
    return cibles


# ── ENF11 — un objet RÉEL par modèle référencé (seed du fuzz) ────────────
# Les lanes ont mesuré des « API rejected schema-compliant request » dus à
# une base de fuzz SANS ligne du modèle visé : le fuzzeur envoyait ``lot: 0``,
# ``dashboard: 0``… et l'API répondait 400, à raison. Chaque semeur crée UNE
# ligne minimale de la société de fuzz si elle n'en a aucune (idempotent),
# dans un point de sauvegarde : un échec est journalisé, jamais bloquant.

def _modele(label):
    from django.apps import apps

    return apps.get_model(label)


def _premier(label, company, **filtres):
    return (_modele(label).objects.filter(company=company, **filtres)
            .order_by('pk').first())


def _semer(nom, fabrique):
    from django.db import transaction

    try:
        with transaction.atomic():
            objet = fabrique()
        print(f'  seed {nom} : id {getattr(objet, "pk", None)}')
        return objet
    except Exception as exc:  # donnée de seed impossible : on continue
        print(f'  (seed ignoré) {nom} : {exc}', file=sys.stderr)
        return None


def _semer_lot(company, user):
    existant = _premier('stock.LotEntrepot', company)
    if existant is not None:
        return existant
    produit = _premier('stock.Produit', company)
    if produit is None:
        raise ValueError('aucun produit dans la société de fuzz')
    return _modele('stock.LotEntrepot').objects.create(
        company=company, produit=produit, numero_lot='FUZZ-LOT-0001',
        created_by=user)


def _semer_tag(company, user):
    tag, _ = _modele('records.Tag').objects.get_or_create(
        company=company, nom='fuzz-etiquette')
    return tag


def _semer_tagged_item(company, user):
    from django.contrib.contenttypes.models import ContentType

    lead = _premier('crm.Lead', company)
    if lead is None:
        raise ValueError('aucun lead dans la société de fuzz')
    item, _ = _modele('records.TaggedItem').objects.get_or_create(
        tag=_semer_tag(company, user),
        content_type=ContentType.objects.get_for_model(lead),
        object_id=lead.pk)
    return item


def _semer_type_activite(company, user):
    existant = _premier('records.ActivityType', company)
    if existant is not None:
        return existant
    return _modele('records.ActivityType').objects.create(
        company=company, nom='Fuzz')


def inventorier_cibles(company):
    """ENF11 (records) — {« app.modele »: ids} des cibles ``{model, id}``
    (activités, pièces jointes, étiquettes, abonnés, liens GED)."""
    from django.apps import apps

    try:
        from apps.records.models import ALLOWED_TARGETS
        couples = sorted(ALLOWED_TARGETS)
    except Exception as exc:  # registre indisponible : pas de cibles
        print(f'  (cibles ignorées) {exc}', file=sys.stderr)
        return {}
    cibles = {}
    cache = {}
    for app_label, nom in couples:
        try:
            modele = apps.get_model(app_label, nom)
        except LookupError:
            continue
        ids = _ids_existants(modele, company, cache)
        if ids:
            cibles[f'{app_label}.{nom}'] = sorted(ids)[:MAX_IDS_PAR_CHAMP]
    return cibles


def _semer_installation(company, user):
    """Une installation AVEC client (portail client, attestation carbone)."""
    existante = _premier('installations.Installation', company,
                         client__isnull=False)
    if existante is not None:
        return existante
    client = _premier('crm.Client', company)
    if client is None:
        raise ValueError('aucun client dans la société de fuzz')
    return _modele('installations.Installation').objects.create(
        company=company, reference='FUZZ-INST-0001', client=client)


def _semer_supervision(company, user):
    """Un système supervisé (MonitoringConfig) + un relevé daté d'HIER."""
    from datetime import timedelta
    from decimal import Decimal

    from django.utils import timezone

    installation = _semer_installation(company, user)
    config, _ = _modele('monitoring.MonitoringConfig').objects.get_or_create(
        installation=installation,
        defaults={'company': company,
                  'expected_annual_kwh': Decimal('5000')})
    hier = timezone.localdate() - timedelta(days=1)
    _modele('monitoring.ProductionReading').objects.get_or_create(
        company=company, installation=installation, date=hier,
        defaults={'energy_kwh': Decimal('12.50'), 'created_by': user})
    return config


def _semer_visite(company, user):
    existante = _premier('visites.VisiteTerrain', company)
    if existante is not None:
        return existante
    lead = _premier('crm.Lead', company)
    if lead is None:
        raise ValueError('aucun lead dans la société de fuzz')
    return _modele('visites.VisiteTerrain').objects.create(
        company=company, lead=lead)


def _installations_supervisees(qs, company):
    return qs.filter(pk__in=_modele('monitoring.MonitoringConfig').objects
                     .filter(company=company).values('installation'))


def _clients_avec_installation(qs, company):
    return qs.filter(pk__in=_modele('installations.Installation').objects
                     .filter(company=company, client__isnull=False)
                     .values('client'))


def _semer_dashboard(company, user):
    existant = _premier('core.Dashboard', company)
    if existant is not None:
        return existant
    return _modele('core.Dashboard').objects.create(
        company=company, titre='Tableau de bord fuzz')


def _semer_modele_marque(company, user):
    existant = _premier('core.BrandedTemplate', company)
    if existant is not None:
        return existant
    return _modele('core.BrandedTemplate').objects.create(
        company=company, kind='email', code='fuzz-modele', nom='Modèle fuzz')


def _semer_equipement(company, user):
    existant = _premier('sav.Equipement', company)
    if existant is not None:
        return existant
    produit = _premier('stock.Produit', company)
    if produit is None:
        raise ValueError('aucun produit dans la société de fuzz')
    return _modele('sav.Equipement').objects.create(
        company=company, produit=produit, numero_serie='FUZZ-SN-0001',
        client_vente=_premier('crm.Client', company))


def _semer_equipe_maintenance(company, user):
    equipe, _ = _modele('sav.EquipeMaintenance').objects.get_or_create(
        company=company, nom='Équipe fuzz')
    return equipe


def _semer_contrat_maintenance(company, user):
    from django.utils import timezone

    existant = _premier('sav.ContratMaintenance', company)
    if existant is not None:
        return existant
    client = _premier('crm.Client', company)
    if client is None:
        raise ValueError('aucun client dans la société de fuzz')
    return _modele('sav.ContratMaintenance').objects.create(
        company=company, client=client, date_debut=timezone.localdate())


def _utilisateurs_internes(qs, company):
    """Comptes actifs de la société, hors comptes portail client."""
    portail = getattr(qs.model, 'PORTEE_PORTAIL_CLIENT', None)
    qs = qs.filter(is_active=True)
    return qs.exclude(portee=portail) if portail else qs


def _semer_calepinage(company, user):
    """Un calepinage ordinaire, sur le DERNIER lead (les autres restent
    libres pour ``POST calepinages/`` — un seul ouvert par lead)."""
    existant = _premier('calepinage.Calepinage', company)
    if existant is not None:
        return existant
    from apps.calepinage.services.creation import creer_pour_lead

    lead = (_modele('crm.Lead').objects.filter(company=company)
            .order_by('-pk').first())
    if lead is None:
        raise ValueError('aucun lead dans la société de fuzz')
    return creer_pour_lead(lead.pk, company, user=user,
                           titre='Calepinage fuzz')


def _ids_calepinages_modeles(company):
    from django.contrib.contenttypes.models import ContentType

    from apps.calepinage.services.modeles import NOM_TAG_MODELE

    return (_modele('records.TaggedItem').objects
            .filter(tag__company=company, tag__nom=NOM_TAG_MODELE,
                    content_type=ContentType.objects.get_for_model(
                        _modele('calepinage.Calepinage')))
            .values('object_id'))


def _semer_calepinage_modele(company, user):
    """Un calepinage MARQUÉ modèle (``depuis-modele``), sur un client."""
    modeles = _modele('calepinage.Calepinage').objects.filter(
        company=company, pk__in=_ids_calepinages_modeles(company))
    if modeles.exists():
        return modeles.first()
    from apps.calepinage.services.creation import creer_pour_client
    from apps.calepinage.services.modeles import marquer_modele

    client = _premier('crm.Client', company)
    if client is None:
        raise ValueError('aucun client dans la société de fuzz')
    calepinage = creer_pour_client(client.pk, company, user=user,
                                   titre='Modèle fuzz')
    marquer_modele(calepinage, user=user)
    return calepinage


def _semer_systeme_fixation(company, user):
    existant = _premier('calepinage.SystemeFixation', company)
    if existant is not None:
        return existant
    return _modele('calepinage.SystemeFixation').objects.create(
        company=company, code='fuzz-systeme', libelle='Système fuzz',
        provenance='Seed du harnais de fuzz (ENF11), jamais une donnée réelle.')


def _semer_entite(company, user):
    existant = _premier('entites.Entite', company)
    if existant is not None:
        return existant
    return _modele('entites.Entite').objects.create(
        company=company, nom='Entité fuzz', code='FUZZ')


def _semer_categorie_fournisseur(company, user):
    existant = _premier('stock.CategorieFournisseur', company)
    if existant is not None:
        return existant
    return _modele('stock.CategorieFournisseur').objects.create(
        company=company, nom='Catégorie fuzz')


def _semer_condition_paiement(company, user):
    existant = _premier('parametres.ConditionPaiement', company)
    if existant is not None:
        return existant
    return _modele('parametres.ConditionPaiement').objects.create(
        company=company, libelle='Comptant (fuzz)')


def _semer_emplacement_stock(company, user):
    existant = _premier('stock.EmplacementStock', company)
    if existant is not None:
        return existant
    return _modele('stock.EmplacementStock').objects.create(
        company=company, nom='Dépôt fuzz', is_principal=True)


def _semer_kit(company, user):
    # CI #997 fuzz (2) — ``composant_kit`` (sous-kit d'un composant) vise un
    # KitProduit : sans kit dans la société, le corps conforme ``{composant_kit:
    # 1}`` répondait 400 « objet inexistant ».
    existant = _premier('stock.KitProduit', company)
    if existant is not None:
        return existant
    return _modele('stock.KitProduit').objects.create(
        company=company, nom='Kit fuzz')


def _semer_gabarit_dossier(company, user):
    existant = _premier('calepinage.GabaritDossierReglementaire', company)
    if existant is not None:
        return existant
    return _modele('calepinage.GabaritDossierReglementaire').objects.create(
        company=company, pays='ma', code='fuzz-gabarit',
        intitule='Gabarit fuzz')


def _semer_ged(company, user):
    """Coffre, armoire + dossier, étiquette GED."""
    coffre = _premier('ged.Coffre', company) or _modele(
        'ged.Coffre').objects.create(company=company, nom='Coffre fuzz')
    cabinet, _ = _modele('ged.Cabinet').objects.get_or_create(
        company=company, nom='Armoire fuzz')
    if _premier('ged.Folder', company) is None:
        _modele('ged.Folder').objects.create(
            company=company, cabinet=cabinet, nom='Dossier fuzz')
    _modele('ged.DocumentTag').objects.get_or_create(
        company=company, slug='fuzz-etiquette',
        defaults={'nom': 'Étiquette fuzz'})
    return coffre


def _calepinages_modeles(qs, company):
    return qs.filter(pk__in=_ids_calepinages_modeles(company))


def _calepinages_ordinaires(qs, company):
    return qs.exclude(pk__in=_ids_calepinages_modeles(company))


def _leads_sans_calepinage(qs, company):
    return qs.exclude(pk__in=_modele('calepinage.Calepinage').objects
                      .filter(company=company, lead_id__isnull=False)
                      .values('lead_id'))


def _tags_hors_modele(qs, company):
    from apps.calepinage.services.modeles import NOM_TAG_MODELE

    return qs.exclude(nom=NOM_TAG_MODELE)


def _semer_retour_fournisseur(company, user):
    """Un retour fournisseur (brouillon) + UNE ligne, numéroté par le MÊME
    chemin que la vue (``create_with_reference`` « RF », jamais count()+1)."""
    existant = _premier('achats.RetourFournisseur', company)
    if existant is not None:
        return existant
    from apps.ventes.utils.references import create_with_reference

    fournisseur = _premier('stock.Fournisseur', company)
    produit = _premier('stock.Produit', company)
    if fournisseur is None or produit is None:
        raise ValueError('aucun fournisseur ou produit dans la société de fuzz')
    modele = _modele('achats.RetourFournisseur')

    def _save(ref):
        retour = modele.objects.create(
            company=company, reference=ref, fournisseur=fournisseur,
            motif='Retour fuzz (ENF11)', created_by=user)
        _modele('achats.LigneRetourFournisseur').objects.create(
            retour=retour, produit=produit, quantite=1)
        return retour
    return create_with_reference(modele, 'RF', company, _save)


# ── CI #997 (stock/achats) — FK sans ligne en base de fuzz : un casier, un BCF
# ENVOYÉ (réceptionnable) à une ligne, une réception brouillon, une facture
# fournisseur à payer, une livraison, une vague, une palette ouverte et une
# expédition (« Clé primaire 1 non valide », à raison, sinon).

def _semer_casier(company, user):
    existant = _premier('installations.BinLocation', company)
    if existant is not None:
        return existant
    return _modele('installations.BinLocation').objects.create(
        company=company, emplacement=_semer_emplacement_stock(company, user),
        code='FUZZ-A-01')


def _semer_bcf_envoye(company, user):
    """BCF ENVOYÉ + une ligne, numéroté par le chemin de la vue (« BCF »)."""
    modele = _modele('achats.BonCommandeFournisseur')
    existant = modele.objects.filter(company=company, statut='envoye').order_by('pk').first()
    if existant is not None:
        return existant
    from apps.ventes.utils.references import create_with_reference

    fournisseur = _premier('stock.Fournisseur', company)
    produit = _premier('stock.Produit', company)
    if fournisseur is None or produit is None:
        raise ValueError('aucun fournisseur ou produit dans la société de fuzz')

    def _save(ref):
        bcf = modele.objects.create(
            company=company, reference=ref, fournisseur=fournisseur,
            statut='envoye', created_by=user)
        _modele('achats.LigneBonCommandeFournisseur').objects.create(
            bon_commande=bcf, produit=produit, quantite=10,
            prix_achat_unitaire=100)
        return bcf
    return create_with_reference(modele, 'BCF', company, _save)


def _semer_reception(company, user):
    modele = _modele('achats.ReceptionFournisseur')
    existant = _premier('achats.ReceptionFournisseur', company)
    if existant is not None:
        return existant
    from apps.ventes.utils.references import create_with_reference

    bcf = _semer_bcf_envoye(company, user)
    return create_with_reference(modele, 'REC', company, lambda ref: modele.objects.create(
        company=company, reference=ref, bon_commande=bcf, created_by=user))


def _semer_facture_fournisseur(company, user):
    modele = _modele('achats.FactureFournisseur')
    existant = _premier('achats.FactureFournisseur', company)
    if existant is not None:
        return existant
    from apps.ventes.utils.references import create_with_reference

    fournisseur = _premier('stock.Fournisseur', company)
    if fournisseur is None:
        raise ValueError('aucun fournisseur dans la société de fuzz')
    return create_with_reference(modele, 'FF', company, lambda ref: modele.objects.create(
        company=company, reference=ref, fournisseur=fournisseur,
        montant_ht=1000, montant_tva=200, montant_ttc=1200, created_by=user))


def _semer_logistique(company, user):
    """Livraison (chantier), vague de picking, palette OUVERTE, expédition."""
    from apps.stock.services import creer_unite_logistique

    if _premier('installations.Livraison', company) is None:
        _modele('installations.Livraison').objects.create(
            company=company, reference='FUZZ-LIV-0001',
            installation=_semer_installation(company, user))
    if _premier('stock.VaguePicking', company) is None:
        _modele('stock.VaguePicking').objects.create(
            company=company, reference='FUZZ-VAG-0001')
    if _premier('stock.UniteLogistique', company, type_unite='palette') is None:
        creer_unite_logistique(company=company, type_unite='palette')
    if _premier('stock.ExpeditionTransporteur', company) is None:
        _modele('stock.ExpeditionTransporteur').objects.create(
            company=company,
            unite_logistique=creer_unite_logistique(company=company, type_unite='colis'))
    return _premier('stock.UniteLogistique', company, type_unite='palette')


def _palettes_ouvertes(qs, company):
    return qs.filter(type_unite='palette', statut='en_preparation')


# ── CI #997 (ventes) — FK sans ligne en base de fuzz : une fiche de recette
# (``recette`` des courbes I-V, packs as-built, attestations) et un dossier
# réglementaire (``dossier`` de la checklist et de la navette opérateur) —
# « Clé primaire 1 non valide », à raison, sinon.

def _semer_recette(company, user):
    existant = _premier('ventes.CommissioningTest', company)
    if existant is not None:
        return existant
    return _modele('ventes.CommissioningTest').objects.create(
        company=company, technicien='Fuzz', created_by=user)


def _semer_dossier_reglementaire(company, user):
    existant = _premier('ventes.RegulatoryDossier', company)
    if existant is not None:
        return existant
    devis = _premier('ventes.Devis', company)
    if devis is None:
        raise ValueError('aucun devis dans la société de fuzz')
    return _modele('ventes.RegulatoryDossier').objects.create(
        company=company, devis=devis, created_by=user)


SEMEURS = (
    ('stock.LotEntrepot', _semer_lot),
    ('records.ActivityType', _semer_type_activite),
    ('records.Tag', _semer_tag),
    ('records.TaggedItem', _semer_tagged_item),
    ('installations.Installation', _semer_installation),
    ('monitoring.MonitoringConfig', _semer_supervision),
    ('visites.VisiteTerrain', _semer_visite),
    ('core.Dashboard', _semer_dashboard),
    ('core.BrandedTemplate', _semer_modele_marque),
    ('sav.Equipement', _semer_equipement),
    ('sav.EquipeMaintenance', _semer_equipe_maintenance),
    ('sav.ContratMaintenance', _semer_contrat_maintenance),
    ('calepinage.Calepinage', _semer_calepinage),
    ('calepinage.Calepinage (modèle)', _semer_calepinage_modele),
    ('calepinage.SystemeFixation', _semer_systeme_fixation),
    ('calepinage.GabaritDossierReglementaire', _semer_gabarit_dossier),
    ('entites.Entite', _semer_entite),
    ('stock.CategorieFournisseur', _semer_categorie_fournisseur),
    ('parametres.ConditionPaiement', _semer_condition_paiement),
    ('stock.EmplacementStock', _semer_emplacement_stock),
    ('stock.KitProduit', _semer_kit),
    ('ged (coffre, dossier, étiquette)', _semer_ged),
    ('achats.RetourFournisseur', _semer_retour_fournisseur),
    ('installations.BinLocation', _semer_casier),
    ('achats.BonCommandeFournisseur (envoyé)', _semer_bcf_envoye),
    ('achats.ReceptionFournisseur', _semer_reception),
    ('achats.FactureFournisseur', _semer_facture_fournisseur),
    ('stock logistique (livraison, vague, palette, expédition)', _semer_logistique),
    ('ventes.CommissioningTest', _semer_recette),
    ('ventes.RegulatoryDossier', _semer_dossier_reglementaire),
)


def semer_objets_references(company, user):
    for nom, fabrique in SEMEURS:
        _semer(nom, lambda f=fabrique: f(company, user))


# ── ENF11 — ids par CHEMIN : un même nom de champ vise des modèles différents
# selon l'app (``lot`` = stock.LotEntrepot ici, ventes.LotDevis ailleurs ;
# ``tag`` = records.Tag ou ged.DocumentTag…). La table par nom (intersection
# ou union) donnait alors des ids d'un AUTRE modèle. Chaque règle :
# (motif du gabarit de chemin, champs du corps/de la requête, modèle,
#  filtre optionnel ``f(qs, company) -> qs``, longueur max d'une liste).
REGLES_PAR_CHEMIN = (
    (r'^/api/django/(stock|achats)/', ('lot', 'lot_id'), 'stock.LotEntrepot',
     None, None),
    (r'^/api/django/records/', ('activity_type', 'type_suivant'),
     'records.ActivityType', None, None),
    (r'^/api/django/records/', ('tag', 'tag_id'), 'records.Tag', None, None),
    (r'^/api/django/monitoring/', ('installation', 'installation_id'),
     'installations.Installation', _installations_supervisees, None),
    (r'^/api/django/monitoring/', ('client', 'client_id'), 'crm.Client',
     _clients_avec_installation, None),
    (r'^/api/django/sav/', ('equipe', 'equipe_id'), 'sav.EquipeMaintenance',
     None, None),
    (r'^/api/django/sav/', ('contrat', 'contrat_id'), 'sav.ContratMaintenance',
     None, None),
    (r'^/api/django/sav/', ('ticket_ids',), 'sav.Ticket', None, None),
    (r'^/api/django/sav/', ('technicien', 'technicien_id'),
     'authentication.CustomUser', _utilisateurs_internes, None),
    (r'^/api/django/sav/tickets/actions-groupees/', ('ids',), 'sav.Ticket',
     None, None),
    (r'^/api/django/calepinage/calepinages/$', ('lead', 'lead_id'),
     'crm.Lead', _leads_sans_calepinage, None),
    (r'^/api/django/calepinage/', ('modele', 'modele_id'),
     'calepinage.Calepinage', _calepinages_modeles, None),
    (r'^/api/django/calepinage/calepinages/comparer-projets/', ('ids',),
     'calepinage.Calepinage', _calepinages_ordinaires, 5),
    (r'^/api/django/calepinage/calepinages/\{[^}]+\}/comparatif', ('ids',),
     'calepinage.Calepinage', _calepinages_ordinaires, 4),
    (r'^/api/django/calepinage/', ('tag_id',), 'records.Tag',
     _tags_hors_modele, None),
    (r'^/api/django/calepinage/', ('systeme_id', 'systeme'),
     'calepinage.SystemeFixation', None, None),
    (r'^/api/django/calepinage/', ('gabarit', 'gabarit_id'),
     'calepinage.GabaritDossierReglementaire', None, None),
    (r'^/api/django/ged/', ('tag', 'tags', 'tag_id'), 'ged.DocumentTag',
     None, None),
    (r'^/api/django/ged/', ('folder', 'folder_id'), 'ged.Folder', None, None),
    (r'^/api/django/ged/dossiers/', ('parent',), 'ged.Folder', None, None),
    (r'^/api/django/ged/tags/', ('parent',), 'ged.DocumentTag', None, None),
    (r'^/api/django/ged/', ('coffre', 'coffre_id'), 'ged.Coffre', None, None),
    (r'^/api/django/ged/', ('proprietaire',), 'authentication.CustomUser',
     _utilisateurs_internes, None),
    (r'^/api/django/ged/', ('contact', 'contact_id'), 'crm.Client', None, None),
    (r'^/api/django/(stock|achats)/', ('retour', 'retour_id'),
     'achats.RetourFournisseur', None, None),
    # CI #997 — ``bon_commande``/``facture``/``facture_origine`` visent aussi
    # ventes.BonCommande / facturation.Facture : l'union donnait leurs ids.
    (r'^/api/django/(stock|achats)/', ('bon_commande', 'bon_commande_id'),
     'achats.BonCommandeFournisseur', None, None),
    (r'^/api/django/(stock|achats)/', ('facture', 'facture_id', 'facture_origine'),
     'achats.FactureFournisseur', None, None),
    (r'^/api/django/stock/', ('livraison', 'livraison_id'),
     'installations.Livraison', None, None),
    (r'^/api/django/stock/unites-logistiques/', ('parent', 'parent_id'),
     'stock.UniteLogistique', _palettes_ouvertes, None),
    # CI #997 (ventes) — ``dossier`` vise aussi les dossiers d'import
    # (installations) et de stock : l'union donnait leurs ids.
    (r'^/api/django/ventes/dossiers-(checklist|echanges)/', ('dossier',),
     'ventes.RegulatoryDossier', None, None),
)


def inventorier_ids_par_chemin(company):
    regles = []
    for motif, champs, label, filtre, maxi in REGLES_PAR_CHEMIN:
        try:
            qs = _modele(label)._default_manager.all()
            if _a_un_champ_company(qs.model):
                qs = qs.filter(company=company)
            if filtre is not None:
                qs = filtre(qs, company)
            ids = [v for v in qs.order_by('pk').values_list('pk', flat=True)
                   .distinct()[:MAX_IDS_PAR_CHAMP]
                   if isinstance(v, int) and not isinstance(v, bool)]
        except Exception as exc:  # modèle absent / filtre cassé : ignoré
            print(f'  (règle ignorée) {motif} {champs}: {exc}',
                  file=sys.stderr)
            continue
        if ids:
            regles.append({'motif': motif, 'champs': list(champs),
                           'ids': ids, 'max': maxi})
        else:
            print(f'  (règle sans id) {motif} {champs} -> {label}',
                  file=sys.stderr)
    return regles


def inventorier_ids_fk(company):
    cache = {}
    table = {}
    for nom, modeles in sorted(_cibles_par_nom().items()):
        ensembles = [_ids_existants(m, company, cache) for m in modeles]
        ensembles = [s for s in ensembles if s]
        if not ensembles:
            continue
        # Un même nom peut viser plusieurs modèles : on préfère les ids
        # valides pour TOUS (intersection), à défaut l'union (meilleur
        # effort).
        choisis = set.intersection(*ensembles) or set.union(*ensembles)
        table[nom] = sorted(choisis)[:MAX_IDS_PAR_CHAMP]
    return table


def main():
    if len(sys.argv) != 2:
        sys.exit('usage : prepare_fuzz_env.py <fichier_etat.json>')
    password = os.environ.get('FUZZ_PASSWORD', '')
    if len(password) < 16:
        sys.exit('FUZZ_PASSWORD absent ou trop court')
    demarrer_django()
    from django.apps import apps
    from django.conf import settings

    if not settings.DEBUG:
        sys.exit('refusé hors DEBUG : base de fuzz jetable uniquement')
    company = apps.get_model('authentication', 'Company').objects.get(
        slug=SLUG_DEMO)
    user = preparer_compte(company, password)
    semer_objets_references(company, user)
    table = inventorier_ids_fk(company)
    regles = inventorier_ids_par_chemin(company)
    cibles = inventorier_cibles(company)
    etat = {
        'username': USERNAME,
        'user_id': user.pk,
        'company_id': company.pk,
        # ENF1b — rôle du compte, protégé par le crochet ``before_call``.
        'role_id': user.role_id,
        'fk_ids': table,
        # ENF11 — ids par chemin (prioritaires sur ``fk_ids``).
        'fk_ids_chemin': regles,
        # ENF11 (records) — ids réels des cibles ``{model, id}``.
        'cibles': cibles,
    }
    with open(sys.argv[1], 'w', encoding='utf-8') as fh:
        json.dump(etat, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print(f'{USERNAME} prêt (id {user.pk}, rôle {user.role_id}, '
          f'société {company.pk}) ; {len(table)} noms de champs FK '
          'avec ids connus')


if __name__ == '__main__':
    main()
