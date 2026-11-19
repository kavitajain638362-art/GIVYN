import { useState } from 'react'
import { Download, Trash2 } from 'lucide-react'
import { Link } from 'react-router'
import { formatDate, useWorkspaceData, workspaceRequest } from './workspaceApi.js'

const modes = { compatibility: 'Compatibility check', comparison: 'Color comparison', metals: 'Metal comparison', draping: 'Drape comparison' }

export default function HistoryPage({ onPortrait }) {
  const { data, error, refresh } = useWorkspaceData('/api/history')
  const [confirmation, setConfirmation] = useState(null)
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState('')

  async function remove(path) {
    setPending(true)
    try {
      await workspaceRequest(path, { method: 'DELETE' })
      if (path === '/api/history' || path.startsWith('/api/analyses/')) onPortrait(null)
      setMessage('Removed from your history.')
      refresh()
    } catch (error) {
      setMessage(error.message)
    } finally {
      setPending(false)
      setConfirmation(null)
    }
  }

  return (
    <main className="frame studio workspace-page" id="main-content" tabIndex={-1}>
      <div className="editorial-heading">
        <div><h1>My analyses</h1><p className="studio-intro">Your saved palettes, colors, and comparisons for this browser.</p></div>
        <Link className="button button-primary" to="/photo">Analyze a portrait</Link>
      </div>
      {message ? <p className="palette-notice" role="status">{message}</p> : null}
      {data ? (
        <>
          <section className="workspace-card history-card">
            <h2>Analysis history</h2>
            {data.analyses.length ? (
              <ul className="history-list">
                {data.analyses.map(({ id, season, created_at }, index) => (
                  <li key={id}>
                    <div><Link to={`/analysis/${id}`} className="text-link">{season} palette</Link>
                      <small>{index === 0 ? 'Latest · ' : ''}{formatDate(created_at)}</small></div>
                    <div className="tool-actions">
                      <a className="text-link" href={`/api/analyses/${id}/report.pdf`} download><Download size={16} /> PDF</a>
                      <button className="text-link" type="button" onClick={() => setConfirmation(`/api/analyses/${id}`)}>
                        <Trash2 size={16} /> Delete
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            ) : <p className="muted">Your first analysis will appear here when your portrait passes the quality check.</p>}
          </section>
          <section className="workspace-card history-card">
            <h2>Favorite colors</h2>
            {data.favorites.length ? (
              <ul className="history-list">
                {data.favorites.map((color) => (
                  <li key={color.hex}><span className="chip-swatch"><i style={{ backgroundColor: color.hex }} />{color.name} <code>{color.hex}</code></span>
                    <button type="button" className="text-link" disabled={pending} onClick={() => remove(`/api/favorites/${color.hex.slice(1)}`)}>Remove</button></li>
                ))}
              </ul>
            ) : <p className="muted">Save a swatch from your personal palette to find it here.</p>}
          </section>
          <section className="workspace-card history-card">
            <h2>Comparison history</h2>
            {data.comparisons.length ? (
              <ul className="history-list">
                {data.comparisons.map((comparison) => (
                  <li key={comparison.id}>
                    <div><span>{modes[comparison.mode]}</span><small>{formatDate(comparison.created_at)}</small></div>
                    <div className="tool-actions">
                      {comparison.result.colors.map((color, index) => (
                        <span className="chip-swatch" key={`${color.hex}-${index}`}><i style={{ backgroundColor: color.hex }} />{color.name || color.hex} · {color.score}</span>
                      ))}
                    </div>
                  </li>
                ))}
              </ul>
            ) : <p className="muted">Results from the color studio will appear here.</p>}
          </section>
          {data.analyses.length || data.favorites.length ? (
            <button type="button" className="text-link" onClick={() => setConfirmation('/api/history')}>Delete all saved data</button>
          ) : null}
          {confirmation ? (
            <section className="workspace-card history-card delete-confirm" aria-label="Confirm deletion">
              <h2>{confirmation === '/api/history' ? 'Delete all saved data?' : 'Delete this analysis?'}</h2>
              <p>Deleting an analysis also removes its saved palette and related comparisons.</p>
              <div className="tool-actions">
                <button type="button" className="button button-primary" disabled={pending} onClick={() => remove(confirmation)}>Confirm deletion</button>
                <button type="button" className="button button-outline" disabled={pending} onClick={() => setConfirmation(null)}>Cancel</button>
              </div>
            </section>
          ) : null}
        </>
      ) : <p className="studio-intro" role={error ? 'alert' : 'status'}>{error || 'Loading your history…'}</p>}
    </main>
  )
}
