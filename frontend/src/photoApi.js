export const photoAccept = '.jpg,.jpeg,.png,image/jpeg,image/png'
export const photoMaxMiB = import.meta.env.MODE === 'vercel' ? 4 : 10

export function photoSelectionError(files) {
  if (files.length !== 1) return 'Choose one photo at a time.'
  const [file] = files
  if (!/\.(jpe?g|png)$/i.test(file.name)) return 'Choose a JPG, JPEG, or PNG photo.'
  if (file.size === 0) return 'This file is empty. Choose another photo.'
  if (file.size > photoMaxMiB * 1024 * 1024) return `Choose a photo that is ${photoMaxMiB} MiB or smaller.`
  return ''
}

export async function validatePhoto(photo, signal, options) {
  const body = new FormData()
  body.set('image', photo)
  body.set('consent', 'true')
  Object.entries(options).forEach(([key, value]) => { if (value) body.set(key, value) })
  const response = await fetch('/api/analyses', { method: 'POST', body, signal })
  if (response.headers.get('content-type')?.includes('application/json')) {
    const result = await response.json()
    if (response.ok && result.status === 'valid') return result
    if (response.status === 422 && result.status === 'retake') return result
    if (result.error?.message) return { status: 'error', message: result.error.message }
  }
  if (response.status === 413) return { status: 'error', message: 'This upload is too large. Choose a smaller photo.' }
  return { status: 'error', message: 'The photo checker is unavailable. Try again in a moment.' }
}
