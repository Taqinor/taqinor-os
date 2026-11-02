# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: acceptation\vnt.spec.js >> P2.12 — VNT60, VNT61, VNT72
- Location: e2e\acceptation\_oracles.js:116:5

# Error details

```
Error: formulaire de signature de l'avenant visible sur la page du lien

expect(locator).toBeVisible() failed

Locator:  locator('#sign-form')
Expected: visible
Received: hidden
Timeout:  30000ms

Call log:
  - formulaire de signature de l'avenant visible sur la page du lien with timeout 30000ms
  - waiting for locator('#sign-form')
    61 × locator resolved to <form hidden="" novalidate="" id="sign-form" data-astro-cid-fof65kao="">…</form>
       - unexpected value "hidden"

```

```yaml
- link "Aller au contenu":
  - /url: "#main"
- banner:
  - link "TAQINOR — accueil":
    - /url: /
  - button "Ouvrir le menu"
- main:
  - group "Langue / Language / اللغة":
    - button "FR" [pressed]
    - button "EN"
    - button "عربي"
  - paragraph: Proposition · Installation solaire
  - heading "Bonjour VNT Kharbachi mvykz6ee1," [level=1]
  - paragraph: Voici votre proposition solaire personnalisée. Tout est détaillé ci-dessous — vous pouvez la signer en ligne en bas de page.
  - paragraph: Total TTC
  - paragraph: 49 000 MAD
  - paragraph: clé en main
  - list:
    - listitem: 5,68 kWc · 8panneaux
    - listitem: 8 723 kWh / an
  - paragraph: Devis valable jusqu’au 2 décembre 2026
  - link "Signer en ligne":
    - /url: "#signer"
  - link "Discuter sur WhatsApp":
    - /url: https://wa.me/212661850410?text=Bonjour%2C%20je%20voudrais%20discuter%20de%20ma%20proposition%20Taqinor%20(r%C3%A9f.%20DEV-202611-0056)%20avant%20de%20signer.
  - paragraph:
    - link "Télécharger le devis (PDF)":
      - /url: /api/proposition-pdf/FgjTC_jEJSMJUi6nNDGvARPNFijvTbGJst8KKI_-3i8
  - navigation "Sommaire de la proposition":
    - link "Matériel":
      - /url: "#installation"
    - link "Économies":
      - /url: "#economies"
    - link "Options":
      - /url: "#options"
    - link "Taqinor":
      - /url: "#confiance"
    - link "Signer":
      - /url: "#signer"
  - term: Référence
  - definition: DEV-202611-0056
  - term: Date
  - definition: 02/11/2026
  - link "Partager sur WhatsApp":
    - /url: https://wa.me/?text=Voici%20ma%20proposition%20solaire%20Taqinor%20(r%C3%A9f.%20DEV-202611-0056)%20%3A%20http%3A%2F%2F127.0.0.1%3A4321%2Fproposition%2FFgjTC_jEJSMJUi6nNDGvARPNFijvTbGJst8KKI_-3i8
  - region "Avenant":
    - paragraph: Avenant à DEV-202611-0055 — nouveau prix
    - paragraph: "Le prix a été renégocié : signez cet avenant pour valider la nouvelle version."
  - paragraph: Devis accepté ✓
  - paragraph:
    - text: Cette proposition a été acceptée par
    - strong: Tijani Kharbachi — avenant négocié
    - text: . Merci de votre confiance — votre conseiller Taqinor revient vers vous.
  - paragraph:
    - link "Suivre l’avancement de mon chantier":
      - /url: /suivi/FgjTC_jEJSMJUi6nNDGvARPNFijvTbGJst8KKI_-3i8
  - heading "Ce que vous recevez" [level=2]
  - paragraph: 5,68 kWc 8 × 710 W panneaux Installation solaire
  - paragraph:
    - text: Dimensionnement de l’option Avec batterie.
    - link "L’autre option a son propre dimensionnement.":
      - /url: "#options"
  - list:
    - listitem: 1 × Onduleur hybride Deye 5kW Monophasé · Deye
    - listitem: 8 × Panneau Canadian Solar 710W · Canadian Solar
    - listitem: 1 × Batterie Dyness 5 kWh · Dyness
    - listitem: 1 × Kit de fixation, câblage et protection complet
    - listitem: 8 × Structures acier
  - paragraph: 12 ans de garantie produit panneaux 30 ans de garantie rendement panneaux 5 ans onduleur 10 ans batterie 2 ans de pose Taqinor
  - paragraph: "Deux garanties : le panneau, et la puissance qu’il délivre. Elles portent sur le matériel — transférables avec le bien, valables quel que soit l’installateur."
  - paragraph: Pose de votre installation par notre équipe, généralement sous 7–14 jours (délai indicatif) selon la disponibilité matériel.
  - paragraph:
    - text: Votre conseiller Taqinor suit ce dossier.
    - link "Le contacter":
      - /url: "#confiance"
  - group: Le détail complet du matériel et les fiches techniques +
  - heading "Vos économies" [level=2]
  - img "Production vs consommation — journée type": lever midi coucher
  - paragraph: Production solaire Votre consommation
  - group: Comment ces économies sont-elles calculées ? +
  - heading "Votre prix" [level=2]
  - article:
    - heading "Avec batterie" [level=3]
    - paragraph: "8 panneaux 5,68 kWc Batteries : 5 kWh"
    - paragraph: 49 000 MAD
    - paragraph: TTC, clé en main · TVA incluse
    - paragraph:
      - link "Voir le détail du matériel (9 postes)":
        - /url: "#equipement"
    - group: Voir le détail du prix
  - heading "Qui est TAQINOR Démo ?" [level=2]
  - paragraph: TAQINOR Démo
  - paragraph:
    - link "Mentions légales complètes":
      - /url: /mentions-legales
  - paragraph:
    - link "Les durées de garantie sont indiquées avec le matériel, plus haut.":
      - /url: "#installation"
  - paragraph: MWh produits et mesurés
  - paragraph: 44,19 MWh produits et mesurés — cumul du suivi de production en temps réel.
  - paragraph: relevé au 05/07/2026
  - paragraph: L'installation la plus proche de chez vous
  - paragraph: Casablanca — 11,36 kWc — installation réelle Taqinor
  - paragraph: "Production mesurée : 1,13 MWh depuis la mise en service (relevé au 04/07/2026)"
  - link "Voir cette réalisation":
    - /url: /realisations/casablanca-11-kwc
  - list "Certifications et garanties":
    - listitem:
      - link "IEC 61215 / 61730 Modules certifiés":
        - /url: /produits/canadian-solar-710
        - paragraph: IEC 61215 / 61730
        - paragraph: Modules certifiés
    - listitem:
      - link "Loi 82-21 Autoconsommation BT":
        - /url: /loi-82-21
        - paragraph: Loi 82-21
        - paragraph: Autoconsommation BT
    - listitem:
      - link "30 ans Garantie performance panneaux":
        - /url: /garanties
        - paragraph: 30 ans
        - paragraph: Garantie performance panneaux
    - listitem:
      - link "5 / 10 ans Garantie onduleur (Deye / Huawei)":
        - /url: /garanties
        - paragraph: 5 / 10 ans
        - paragraph: Garantie onduleur (Deye / Huawei)
  - paragraph: Une question avant de signer ? Parlons-en — sans engagement, et sans appel commercial non sollicité.
  - paragraph: Réponse WhatsApp sous 1 h, 7j/7
  - link "Discuter sur WhatsApp":
    - /url: https://wa.me/212661850410?text=Bonjour%2C%20je%20voudrais%20discuter%20de%20ma%20proposition%20Taqinor%20(r%C3%A9f.%20DEV-202611-0056)%20avant%20de%20signer.
  - link "Demander un rappel":
    - /url: tel:+212661850410
  - link "Poser une question":
    - /url: https://wa.me/212661850410?text=Bonjour%2C%20j'ai%20une%20question%20pr%C3%A9cise%20sur%20ma%20proposition%20Taqinor%20(r%C3%A9f.%20DEV-202611-0056).
  - paragraph:
    - link "Plus simple à l’oral ? Envoyez-nous une note vocale sur WhatsApp.":
      - /url: https://wa.me/212661850410?text=Bonjour%2C%20je%20vous%20envoie%20une%20note%20vocale%20au%20sujet%20de%20ma%20proposition%20Taqinor%20(r%C3%A9f.%20DEV-202611-0056).
  - group: Cette version ne correspond pas tout à fait ? Demander une modification
  - paragraph: Devis accepté ✓
  - paragraph: Merci Tijani Kharbachi — avenant négocié — votre acceptation est bien enregistrée. Votre conseiller Taqinor revient vers vous très vite.
  - paragraph: Réf. DEV-202611-0056.
  - paragraph: Votre signature
  - paragraph: Signature enregistrée ✓
  - link "Télécharger votre exemplaire signé":
    - /url: /api/proposition-pdf/FgjTC_jEJSMJUi6nNDGvARPNFijvTbGJst8KKI_-3i8
  - link "Voir « Et après ? »":
    - /url: "#etapes-suivantes"
  - link "Suivre mon chantier":
    - /url: /suivi/FgjTC_jEJSMJUi6nNDGvARPNFijvTbGJst8KKI_-3i8
  - heading "Et après ?" [level=2]
  - list:
    - listitem:
      - paragraph: "1."
      - paragraph: Signature
      - paragraph: Vous signez en ligne ci-dessus. Votre conseiller Taqinor confirme la réception dans la journée.
    - listitem:
      - paragraph: "2."
      - paragraph: Visite technique
      - paragraph: Un technicien confirme les mesures sur site sous 48–72 h (délai indicatif).
    - listitem:
      - paragraph: "3."
      - paragraph: Installation
      - paragraph: Pose de votre installation par notre équipe, généralement sous 7–14 jours (délai indicatif) selon la disponibilité matériel.
    - listitem:
      - paragraph: "4."
      - paragraph: Mise en service
      - paragraph: Vérification finale, mise en service et remise des documents (garanties, attestations).
  - heading "Partager avec un proche" [level=2]
  - paragraph: Un proche envisage aussi le solaire ? Partagez votre lien de parrainage — Taqinor vous en dit merci quand son projet se concrétise.
  - link "Partager avec un proche":
    - /url: https://wa.me/?text=J'ai%20fait%20installer%20mes%20panneaux%20solaires%20avec%20Taqinor%20%E2%80%94%20si%20%C3%A7a%20vous%20int%C3%A9resse%2C%20voici%20le%20lien%20%3A%20http%3A%2F%2F127.0.0.1%3A4321%2Fparrainage%3Futm_source%3Dparrainage%26utm_campaign%3DDEV-202611-0056
  - link "Télécharger le devis (PDF)":
    - /url: /api/proposition-pdf/FgjTC_jEJSMJUi6nNDGvARPNFijvTbGJst8KKI_-3i8
  - paragraph: Proposition Taqinor · réf. DEV-202611-0056. Document non contractuel sans signature du devis officiel.
  - heading "Et après ?" [level=2]
  - list:
    - listitem:
      - paragraph: "1."
      - paragraph: Signature
      - paragraph: Vous signez en ligne ci-dessus. Votre conseiller Taqinor confirme la réception dans la journée.
  - group: "Et ensuite : visite technique, pose, mise en service +"
  - heading "Vos questions, nos réponses" [level=2]
  - group: Que se passe-t-il en cas de coupure du réseau électrique ?
  - group: Quel entretien est nécessaire ?
  - group: Puis-je emporter mon installation si je déménage ?
  - group: Nos hypothèses
  - paragraph: Chaque chiffre est étudié sur votre facture, pas promis.
  - paragraph: L’étude d’abord. Le chantier ensuite.
- contentinfo:
  - paragraph: Taqinor
  - paragraph:
    - link "+212 6 61 85 04 10":
      - /url: tel:+212661850410
    - link "contact@taqinor.ma":
      - /url: mailto:contact@taqinor.ma
  - paragraph:
    - text: © 2026 Taqinor ·
    - link "Mentions légales":
      - /url: /mentions-legales
    - text: ·
    - link "Confidentialité":
      - /url: /politique-de-confidentialite
- region "Accepter":
  - paragraph: Nous utilisons des mesures anonymes (audience, campagnes) pour améliorer le site. Vous pouvez les refuser sans impact sur votre demande de devis.
  - button "Refuser"
  - button "Accepter"
```

# Test source

```ts
  847  |     expect(sign.status(), await sign.text()).toBe(200)
  848  |     await page.goto(lien, { waitUntil: 'domcontentloaded', timeout: 120_000 })
  849  |     const confirme = page.locator('[data-avenant="signe"]')
  850  |     await expect(confirme).toBeVisible({ timeout: 60_000 })
  851  |     await expect(confirme).toContainText(/Avenant signé le .+ ✓/)
  852  |     await expect(page.locator('section[data-avenant="a_signer"]')).toHaveCount(0)
  853  |   }, { remise: '0' })
  854  | })
  855  | 
  856  | etape('P2.7', ['VNT53', 'VNT55'], async ({ page, testInfo }) => {
  857  |   // Parcours classique Réviser → Envoyer la V2 d'un accepté : 0 étape de cadence commerciale, UNE tâche
  858  |   // « Faire signer l'avenant » (ADEV57). Puis abandonner la révision rend la V1 active (VNT55) — sur une 2e réplique.
  859  |   await avecReplique(page, testInfo, async (r) => {
  860  |     const etapes = async () => listeDe(await lireJson(await page.request.get(`${API}/crm/relance-etapes/?lead=${r.leadId}`,
  861  |       { timeout: 120_000 }), 'étapes de cadence'))
  862  |     const avant = new Set((await etapes()).map((e) => e.id))
  863  |     const v2 = await lireJson(await page.request.post(`${API}/ventes/devis/${r.devisId}/reviser/`, { timeout: 120_000 }), 'révision')
  864  |     expect(v2.version).toBe(2)
  865  |     await lireJson(await page.request.post(`${API}/ventes/devis/${v2.id}/share-link/`, { timeout: 120_000, data: { envoi: true } }), 'envoi de la V2')
  866  |     expect((await devisDetail(page.request, v2.id)).statut).toBe('envoye')
  867  |     const nouvelles = (await etapes()).filter((e) => !avant.has(e.id))
  868  |     expect(nouvelles.map((e) => e.libelle), 'aucune étape de cadence commerciale, une tâche avenant').toEqual(['Faire signer l’avenant'])
  869  |     // Persistance : relue, toujours UNE tâche avenant ouverte.
  870  |     const relues = (await etapes()).filter((e) => e.libelle === 'Faire signer l’avenant')
  871  |     expect(relues).toHaveLength(1)
  872  |   }, { remise: '10' })
  873  |   await avecReplique(page, testInfo, async (r) => {
  874  |     const v2 = await lireJson(await page.request.post(`${API}/ventes/devis/${r.devisId}/reviser/`, { timeout: 120_000 }), 'révision')
  875  |     expect((await devisDetail(page.request, r.devisId)).is_active, 'V1 désactivée par Réviser').toBe(false)
  876  |     const sup = await page.request.delete(`${API}/ventes/devis/${v2.id}/`, { timeout: 120_000 })
  877  |     expect(sup.status(), await sup.text()).toBeLessThan(300)
  878  |     const v1 = await devisDetail(page.request, r.devisId)
  879  |     expect([v1.statut, v1.is_active], 'révision abandonnée : la V1 acceptée redevient active').toEqual(['accepte', true])
  880  |   })
  881  | })
  882  | 
  883  | etape('P2.10', ['VNT54', 'VNT58', 'VNT80'], async ({ page, suivi, testInfo }) => {
  884  |   // 409 vers la tête : (a) le geste Prix négocié rejoué sur la V1 remplacée ⇒ 409 `version_remplacee` nommant la V2 ;
  885  |   // (b) un 2e devis accepté depuis la LISTE sur le même lead ⇒ 409 `vente_active_existante`, erreur SOUS la ligne
  886  |   // avec « Ouvrir <réf> » qui ouvre la vente en vigueur (`?devis=<id>`).
  887  |   await avecReplique(page, testInfo, async (r) => {
  888  |     const neg = await prixNegocieParApi(page.request, r.devisId, '49000')
  889  |     const v2 = neg.devis_v2
  890  |     suivi.attendre(new RegExp(`/ventes/devis/${r.devisId}/prix-negocie/$`), 409)
  891  |     const rejoue = await page.request.post(`${API}/ventes/devis/${r.devisId}/prix-negocie/`, { timeout: 120_000,
  892  |       data: { prix_ttc: '48000', mode: 'appliquer' } })
  893  |     expect(rejoue.status(), await rejoue.text()).toBe(409)
  894  |     const c1 = await rejoue.json()
  895  |     expect([c1.code, c1.successeur?.id, c1.successeur?.reference]).toEqual(['version_remplacee', v2.id, v2.reference])
  896  |     const produit = await lireJson(await page.request.post(`${API}/stock/produits/`, { timeout: 120_000,
  897  |       data: { nom: `VNT 2e ${Date.now()}`, prix_vente: '1000.00' } }), 'produit 2e devis')
  898  |     const d2 = await lireJson(await page.request.post(`${API}/ventes/devis/atomic/`, { timeout: 120_000,
  899  |       data: { lead: r.leadId, taux_tva: '20.00', lignes: [{ produit: produit.id, designation: 'Deuxième affaire', quantite: '1',
  900  |         prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), '2e devis')
  901  |     await lireJson(await page.request.post(`${API}/ventes/devis/${d2.id}/share-link/`, { timeout: 120_000, data: { envoi: true } }), 'envoi 2e devis')
  902  |     const d2lu = await devisDetail(page.request, d2.id)
  903  |     suivi.attendre(new RegExp(`/ventes/devis/${d2.id}/accepter/$`), 409)
  904  |     await page.goto(`/ventes/devis?devis=${d2.id}`)
  905  |     const ligne = page.locator(`#devis-row-${d2.id}`)
  906  |     await expect(ligne).toBeVisible({ timeout: 60_000 })
  907  |     await ligne.getByRole('button', { name: 'Accepter' }).click()
  908  |     const dlg = page.getByRole('dialog').filter({ hasText: `Accepter le devis — ${d2lu.reference}` })
  909  |     await expect(dlg).toBeVisible({ timeout: 30_000 })
  910  |     await dlg.getByLabel('Nom de la personne qui accepte').fill('Tijani Kharbachi')
  911  |     const cible = new RegExp(`/ventes/devis/${d2.id}/accepter/$`)
  912  |     const [rep] = await Promise.all([
  913  |       page.waitForResponse((x) => x.request().method() === 'POST' && cible.test(new URL(x.url()).pathname)),
  914  |       dlg.getByRole('button', { name: "Confirmer l'acceptation" }).click(),
  915  |     ])
  916  |     expect(rep.status()).toBe(409)
  917  |     expect((await rep.json()).vente_active?.id, 'le 409 nomme la vente en vigueur (la V2)').toBe(v2.id)
  918  |     const alerte = page.getByRole('alert').filter({ hasText: `Ouvrir ${v2.reference}` })
  919  |     await expect(alerte, 'erreur sous la ligne refusée avec « Ouvrir <réf> »').toBeVisible({ timeout: 30_000 })
  920  |     await alerte.getByRole('button', { name: `Ouvrir ${v2.reference}` }).click()
  921  |     await expect(page).toHaveURL(new RegExp(`[?&]devis=${v2.id}`))
  922  |     // Persistance : relu, le 2e devis n'est pas accepté et la V2 reste la seule vente en vigueur.
  923  |     expect((await devisDetail(page.request, d2.id)).statut).toBe('envoye')
  924  |     const v2lu = await devisDetail(page.request, v2.id)
  925  |     expect([v2lu.statut, v2lu.is_active]).toEqual(['accepte', true])
  926  |     await page.request.delete(`${API}/ventes/devis/${d2.id}/`, { timeout: 120_000 }).catch(() => null)
  927  |   }, { remise: '0' })
  928  | })
  929  | 
  930  | /** Signature de l'avenant PAR LE LIEN, sur la page publique servie en local (`E2E_WEB_BASE`, jamais la prod) :
  931  |  *  bandeau « Avenant à <V1> », formulaire de signature (#sign-form : nom, cases, tracé #sign-pad, #sign-submit),
  932  |  *  puis confirmation « Avenant signé le … ✓ » et statut inchangé (accepté). */
  933  | async function signerAvenantParLaPage(page, r, v2Id, jeton) {
  934  |   const web = process.env.E2E_WEB_BASE
  935  |   expect(web, 'E2E_WEB_BASE absent : apps/web non servie (NON JOUABLE sans elle)').toBeTruthy()
  936  |   expect(web, 'jamais la prod').toMatch(/^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?/)
  937  |   const lien = `${web.replace(/\/$/, '')}/proposition/${jeton}`
  938  |   const rep = await page.goto(lien, { waitUntil: 'domcontentloaded', timeout: 120_000 })
  939  |   expect(rep.status(), `page publique ${lien}`).toBe(200)
  940  |   const bandeau = page.locator('section[data-avenant="a_signer"]')
  941  |   await expect(bandeau).toBeVisible({ timeout: 60_000 })
  942  |   await expect(bandeau).toContainText(`Avenant à ${r.reference} — nouveau prix`)
  943  |   // Le geste du client : le bouton « Signer en ligne » du haut de page mène au bloc de signature.
  944  |   const cta = page.getByRole('link', { name: 'Signer en ligne' }).or(page.getByRole('button', { name: 'Signer en ligne' })).first()
  945  |   if (await cta.count()) await cta.click()
  946  |   const formulaire = page.locator('#sign-form')
> 947  |   await expect(formulaire, "formulaire de signature de l'avenant visible sur la page du lien").toBeVisible({ timeout: 30_000 })
       |                                                                                                ^ Error: formulaire de signature de l'avenant visible sur la page du lien
  948  |   await formulaire.locator('#sign-nom').fill('Tijani Kharbachi')
  949  |   for (const c of await formulaire.locator('input[type="checkbox"]:visible').all()) await c.check()
  950  |   const pad = formulaire.locator('#sign-pad')
  951  |   const b = await pad.boundingBox()
  952  |   await page.mouse.move(b.x + 20, b.y + b.height / 2)
  953  |   await page.mouse.down()
  954  |   await page.mouse.move(b.x + b.width / 2, b.y + 10, { steps: 8 })
  955  |   await page.mouse.move(b.x + b.width - 20, b.y + b.height / 2, { steps: 8 })
  956  |   await page.mouse.up()
  957  |   await formulaire.locator('#sign-submit').click()
  958  |   await expect(page.locator('[data-avenant="signe"]').or(page.locator('#sign-success'))).toBeVisible({ timeout: 60_000 })
  959  |   await page.goto(lien, { waitUntil: 'domcontentloaded', timeout: 120_000 })
  960  |   await expect(page.locator('[data-avenant="signe"]')).toContainText(/Avenant signé le .+ ✓/, { timeout: 60_000 })
  961  |   const lue = await lireJson(await page.request.get(`${API}/ventes/proposal/${jeton}/`, { timeout: 120_000 }), 'proposition relue')
  962  |   expect([lue.avenant?.a_signer, Boolean(lue.avenant?.signe_le)]).toEqual([false, true])
  963  |   const v2 = await devisDetail(page.request, v2Id)
  964  |   expect([v2.statut, v2.is_active], 'statut inchangé (règle #4)').toEqual(['accepte', true])
  965  | }
  966  | 
  967  | etape('P2.11', ['VNT60', 'VNT61', 'VNT72', 'VNT73'], async ({ page, testInfo }) => {
  968  |   // BUREAU : « Prix négocié » 49 000 puis « Faire signer l'avenant » dans le dialogue (lien affiché) ; le client
  969  |   // ouvre le lien et signe l'avenant sur la page publique (formulaire), confirmation, statut inchangé.
  970  |   await avecReplique(page, testInfo, async (r) => {
  971  |     await page.goto(`/crm/leads/${r.leadId}`)
  972  |     await ongletDevis(page).click()
  973  |     await panneauVente(page, r).getByRole('button', { name: 'Prix négocié' }).click()
  974  |     const dlg = page.getByRole('dialog').filter({ hasText: 'Prix négocié' })
  975  |     await dlg.getByLabel('Nouveau prix TTC (MAD)').fill('49000')
  976  |     await dlg.getByRole('button', { name: 'Voir les effets' }).click()
  977  |     await expect(dlg.locator('dl[aria-label="Effets du prix négocié"]')).toContainText('10,00', { timeout: 30_000 })
  978  |     const cible = new RegExp(`/ventes/devis/${r.devisId}/prix-negocie/$`)
  979  |     const [rep] = await Promise.all([
  980  |       page.waitForResponse((x) => x.request().method() === 'POST' && cible.test(new URL(x.url()).pathname)),
  981  |       dlg.getByRole('button', { name: 'Appliquer le prix négocié' }).click(),
  982  |     ])
  983  |     const v2Id = (await rep.json()).devis_v2.id
  984  |     await dlg.getByRole('button', { name: "Faire signer l'avenant" }).click()
  985  |     const lien = dlg.getByTestId('lien-avenant')
  986  |     await expect(lien).toContainText('/proposition/', { timeout: 30_000 })
  987  |     const jeton = (await lien.innerText()).trim().split('/').pop()
  988  |     await signerAvenantParLaPage(page, r, v2Id, jeton)
  989  |   }, { remise: '0' })
  990  | })
  991  | 
  992  | etape('P2.12', ['VNT60', 'VNT61', 'VNT72'], async ({ page, testInfo }) => {
  993  |   // TÉLÉPHONE (375 × 812) : même avenant, le client signe sur son téléphone par le lien.
  994  |   await avecReplique(page, testInfo, async (r) => {
  995  |     const neg = await prixNegocieParApi(page.request, r.devisId, '49000')
  996  |     const a = await lireJson(await page.request.post(`${API}/ventes/devis/${neg.devis_v2.id}/avenant/demander-signature/`,
  997  |       { timeout: 120_000 }), 'demande de signature')
  998  |     await page.setViewportSize({ width: 375, height: 812 })
  999  |     await signerAvenantParLaPage(page, r, neg.devis_v2.id, a.share_link.split('/').pop())
  1000 |   }, { remise: '0' })
  1001 | })
  1002 | 
  1003 | // ───────────────────────── Lot M3 (VNT95) : étapes P3.x ─────────────────────────
  1004 | const lireFunnelSigne = async (request) => {
  1005 |   const d = await lireJson(await request.get(`${API}/reporting/commercial/dashboard/`, { timeout: 120_000 }), 'tableau de bord commercial')
  1006 |   const signe = d.funnel.find((e) => e.label === STAGE_LABELS.SIGNED)
  1007 |   return { count: signe.count, valeur: Number(signe.valeur), total_signes: d.total_signes }
  1008 | }
  1009 | 
  1010 | /** Code exécuté dans le conteneur Django (E2E_DJANGO_EXEC) : `manage.py shell` y démarre en ~3 min. */
  1011 | function shellDjango(code) {
  1012 |   const surmesure = process.env.E2E_DJANGO_EXEC
  1013 |   if (!surmesure) throw new Error('E2E_DJANGO_EXEC absent : lecture du carnet impossible')
  1014 |   const [cmd, ...args] = surmesure.split(' ')
  1015 |   return execFileSync(cmd, [...args, 'python', 'manage.py', 'shell', '-c', code], { stdio: 'pipe', timeout: 2_000_000 }).toString()
  1016 | }
  1017 | 
  1018 | etape('P3.1', ['VNT84', 'VNT85', 'VNT86'], async ({ page, testInfo }) => {
  1019 |   // Chaîne révisée (V1 54 500 acceptée → Prix négocié 49 000 = V2) : le KPI « devis signés » ne compte qu'UNE vente
  1020 |   // (49 000) et l'intégrité ne signale pas la V1 remplacée.
  1021 |   const avant = await lireFunnelSigne(page.request)
  1022 |   await avecReplique(page, testInfo, async (r) => {
  1023 |     await prixNegocieParApi(page.request, r.devisId, '49000')
  1024 |     const apres = await lireFunnelSigne(page.request)
  1025 |     expect(apres.count - avant.count, 'une seule vente signée comptée').toBe(1)
  1026 |     expect(apres.total_signes - avant.total_signes).toBe(1)
  1027 |     expect((apres.valeur - avant.valeur).toFixed(2), 'valeur signée = 49 000 (jamais 54 500 + 49 000)').toBe('49000.00')
  1028 |     const integ = await lireJson(await page.request.get(`${API}/reporting/insights/integrite/`, { timeout: 120_000 }), 'intégrité')
  1029 |     expect(JSON.stringify(integ), "la V1 remplacée n'est pas signalée « acceptée sans chantier »").not.toContain(r.reference)
  1030 |   }, { remise: '0' })
  1031 | })
  1032 | 
  1033 | etape('P3.4', ['VNT88'], async ({ page, testInfo }) => {
  1034 |   // Carnet / rappel « à facturer » (sélecteurs sans route HTTP : lus dans le conteneur Django) — la V2 est
  1035 |   // rappelée, la V1 remplacée jamais. `manage.py shell` y démarre en plusieurs minutes sur cette pile chargée.
  1036 |   await avecReplique(page, testInfo, async (r) => {
  1037 |     testInfo.setTimeout(2_400_000)
  1038 |     const neg = await prixNegocieParApi(page.request, r.devisId, '49000')
  1039 |     const code = ['from apps.ventes.models import Devis',
  1040 |       'from apps.ventes.selectors_facturation import devis_a_facturer',
  1041 |       `d = Devis.objects.get(pk=${neg.devis_v2.id})`,
  1042 |       'ids = sorted(x.id for x in devis_a_facturer(d.company, jours=-1))',
  1043 |       "print('IDS=' + ','.join(map(str, ids)))"].join('\n') + '\n'
  1044 |     const sortie = shellDjango(code)
  1045 |     const ids = (/IDS=([\d,]*)/.exec(sortie)?.[1] || '').split(',').filter(Boolean).map(Number)
  1046 |     expect(ids, 'la V2 (vente en vigueur sans facture) est rappelée').toContain(neg.devis_v2.id)
  1047 |     expect(ids, "la V1 remplacée n'est jamais rappelée").not.toContain(r.devisId)
```