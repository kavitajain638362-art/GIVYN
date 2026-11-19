import { useEffect, useState } from 'react'

export async function workspaceRequest(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: options.body ? { 'Content-Type': 'application/json', ...options.headers } : options.headers,
  })
  if (response.status === 204) return null
  const json = await response.json().catch(() => null)
  if (!response.ok || !json) throw new Error(json?.error?.message || 'The studio is unavailable. Try again in a moment.')
  return json
}

export function useWorkspaceData(path) {
  const [state, setState] = useState({ path: null })
  const [revision, setRevision] = useState(0)

  useEffect(() => {
    if (!path) return
    const controller = new AbortController()
    workspaceRequest(path, { signal: controller.signal })
      .then((data) => setState({ path, data }))
      .catch((error) => {
        if (!controller.signal.aborted) setState({ path, error: error.message })
      })
    return () => controller.abort()
  }, [path, revision])

  return {
    ...(state.path === path ? state : {}),
    refresh: () => setRevision((current) => current + 1),
  }
}

export function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

export function usePhotoUrl(file) {
  const [preview, setPreview] = useState(null)
  useEffect(() => {
    if (!file) return
    const url = URL.createObjectURL(file)
    setPreview({ file, url })
    return () => URL.revokeObjectURL(url)
  }, [file])
  return preview?.file === file ? preview?.url : null
}
