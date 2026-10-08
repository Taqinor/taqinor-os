import { render } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import SocieteSection from '../pages/parametres/SocieteSection'

/* Harnais de rendu PARTAGÉ des tests de Paramètres › Société & identité
   (ERR-QAH-PARAMETRES-CHAMP-ERREUR-GENERIQUE, APAR31) : un seul endroit
   plutôt qu'une copie dans chaque fichier de test (check_duplicats_litteraux).
   `saveError` = tranche `parametres.error` (erreurs 400 par champ). */

function noop() {}

export const FORM_VIDE = {
  nom: '', adresse: '', email: '', telephone: '',
  rib: '', banque: '', siret: '', tva_intra: '',
  instructions_paiement: '', conditions_generales: '',
  ice: '', identifiant_fiscal: '', rc: '', patente: '', cnss: '',
  couleur_principale: '#1d4ed8',
}

export function renderSocieteSection({ saveError = null } = {}) {
  const store = configureStore({
    reducer: {
      parametres: (s = { error: saveError }) => s,
      auth: (s = { user: { company_est_demo: false } }) => s,
    },
  })
  return render(
    <Provider store={store}>
      <SocieteSection
        accent="#1d4ed8" profile={null} form={FORM_VIDE}
        set={noop} uploading={false} dispatch={noop}
      />
    </Provider>,
  )
}
