// ENF19 — la mécanique d'envoi partagée des formulaires.
import { test, expect, vi } from 'vitest'
import { creerSoumission, creerSoumissionNomRequis } from './soumission.js'

const geste = () => ({ preventDefault: vi.fn() })

test('valide : occupé pendant l’envoi, relâché après', async () => {
  const setOccupe = vi.fn()
  const envoyer = vi.fn(async () => {
    expect(setOccupe).toHaveBeenLastCalledWith(true)
  })
  const e = geste()
  await creerSoumission(() => true, setOccupe, envoyer, vi.fn())(e)
  expect(e.preventDefault).toHaveBeenCalledOnce()
  expect(envoyer).toHaveBeenCalledOnce()
  expect(setOccupe).toHaveBeenLastCalledWith(false)
})

test('un true synchrone pose « occupé » dans le même tour que le geste', () => {
  const setOccupe = vi.fn()
  creerSoumission(() => true, setOccupe, async () => {}, vi.fn())(geste())
  expect(setOccupe).toHaveBeenCalledWith(true)
})

test('invalide (synchrone ou promesse) : rien n’est envoyé, jamais occupé', async () => {
  for (const verdict of [false, Promise.resolve(false)]) {
    const setOccupe = vi.fn()
    const envoyer = vi.fn()
    await creerSoumission(() => verdict, setOccupe, envoyer, vi.fn())(geste())
    expect(envoyer).not.toHaveBeenCalled()
    expect(setOccupe).not.toHaveBeenCalled()
  }
})

test('verdict en promesse positive : envoie', async () => {
  const envoyer = vi.fn()
  await creerSoumission(() => Promise.resolve(true), vi.fn(), envoyer, vi.fn())(geste())
  expect(envoyer).toHaveBeenCalledOnce()
})

test('échec d’envoi : surErreur reçoit l’erreur, occupé relâché', async () => {
  const setOccupe = vi.fn()
  const surErreur = vi.fn()
  const boum = new Error('boum')
  await creerSoumission(() => true, setOccupe, async () => { throw boum }, surErreur)(geste())
  expect(surErreur).toHaveBeenCalledWith(boum)
  expect(setOccupe).toHaveBeenLastCalledWith(false)
})

test('nom requis : nom vide = bandeau, nom saisi = envoi ; échec dans le bandeau', async () => {
  const setError = vi.fn()
  const envoyer = vi.fn()
  const options = { setError, setBusy: vi.fn(), envoyer, messageErreur: () => 'raté' }
  await creerSoumissionNomRequis({ ...options, nom: '  ' })(geste())
  expect(setError).toHaveBeenLastCalledWith('Le nom est requis.')
  expect(envoyer).not.toHaveBeenCalled()

  await creerSoumissionNomRequis({ ...options, nom: 'Amal' })(geste())
  expect(setError).toHaveBeenLastCalledWith(null)
  expect(envoyer).toHaveBeenCalledOnce()

  envoyer.mockRejectedValueOnce(new Error('x'))
  await creerSoumissionNomRequis({ ...options, nom: 'Amal' })(geste())
  expect(setError).toHaveBeenLastCalledWith('raté')
})
