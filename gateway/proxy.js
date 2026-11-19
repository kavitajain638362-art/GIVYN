import { Readable } from 'node:stream'
import { pipeline } from 'node:stream/promises'

const maxBodyBytes = 4 * 1024 * 1024 + 64 * 1024

function fail(res, status, code, message) {
  res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' })
  res.end(JSON.stringify({ status: 'error', error: { code, message } }))
}

export default async function gateway(req, res) {
  const requestUrl = new URL(req.url, 'http://gateway.invalid')
  if (!requestUrl.pathname.startsWith('/api/')) {
    return fail(res, 404, 'not_found', 'This API route does not exist.')
  }

  const binding = process.env.GIVYN_API_URL
  if (!binding) return fail(res, 503, 'binding_missing', 'The analysis service is unavailable.')

  // Retain the binding origin and any base path. Request paths cannot change the host.
  const target = new URL(binding)
  target.pathname = target.pathname.replace(/\/$/, '') + requestUrl.pathname
  target.search = requestUrl.search

  const headers = new Headers()
  for (const name of ['accept', 'content-type']) {
    if (req.headers[name]) headers.set(name, req.headers[name])
  }
  const profile = req.headers.cookie?.split(';').map(cookie => cookie.trim())
    .find(cookie => cookie.startsWith('givyn_profile='))
  if (profile) headers.set('cookie', profile)

  try {
    let body
    if (req.method !== 'GET' && req.method !== 'HEAD') {
      const chunks = []
      let size = 0
      for await (const chunk of req.iterator({ destroyOnReturn: false })) {
        size += chunk.length
        if (size > maxBodyBytes) {
          req.resume()
          return fail(res, 413, 'upload_limit', 'Choose a photo that is 4 MiB or smaller.')
        }
        chunks.push(chunk)
      }
      body = Buffer.concat(chunks, size)
    }
    const upstream = await fetch(target, {
      method: req.method, headers, body, redirect: 'manual', signal: AbortSignal.timeout(55_000),
    })
    res.statusCode = upstream.status
    for (const name of ['content-type', 'content-disposition', 'allow']) {
      const value = upstream.headers.get(name)
      if (value) res.setHeader(name, value)
    }
    res.setHeader('Cache-Control', 'no-store')
    const cookies = upstream.headers.getSetCookie()
    if (cookies.length) res.setHeader('Set-Cookie', cookies)
    if (upstream.body) await pipeline(Readable.fromWeb(upstream.body), res)
    else res.end()
  } catch {
    if (res.headersSent) res.destroy()
    else if (!res.destroyed) fail(res, 502, 'service_unavailable', 'The analysis service is unavailable. Try again shortly.')
  }
}
