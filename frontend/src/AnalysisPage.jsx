import { useState } from 'react'
import { Copy, Download, Heart } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { formatDate, useWorkspaceData, workspaceRequest } from './workspaceApi.js'

function PaletteGroups({ analysis }) {
  const { data, refresh } = useWorkspaceData('/api/history')
  const [notice, setNotice] = useState('')
  const [pending, setPending] = useState('')
  const favorites = new Set(data?.favorites.map((color) => color.hex))

  async function toggle(swatch) {
    setPending(swatch.hex)
    setNotice('')
    try {
      const saved = favorites.has(swatch.hex)
      await workspaceRequest(saved ? `/api/favorites/${swatch.hex.slice(1)}` : '/api/favorites',
        saved ? { method: 'DELETE' } : { method: 'POST', body: JSON.stringify({ hex: swatch.hex, name: swatch.name }) })
      setNotice(saved ? `${swatch.name} removed from favorites.` : `${swatch.name} saved to favorites.`)
      refresh()
    } catch (error) {
      setNotice(error.message)
    } finally {
      setPending('')
    }
  }

  async function copy(hex) {
    try {
      await navigator.clipboard.writeText(hex)
      setNotice(`Copied ${hex}.`)
    } catch {
      setNotice(`Copy ${hex} from the swatch label.`)
    }
  }

  return (
    <section className="palette-section" aria-labelledby="palette-heading">
      <h2 id="palette-heading">Your personal palette</h2>
      {notice ? <p className="palette-notice" role="status">{notice}</p> : null}
      {['Complementary', 'Neutrals', 'Accents', 'Use with care'].map((group) => (
        <section className="palette-group" key={group}>
          <h3>{group}</h3>
          <div className="swatch-grid">
            {analysis.palette[group].map((swatch) => (
              <article className="swatch-card" key={swatch.hex}>
                <div className="swatch-color" style={{ backgroundColor: swatch.hex }} />
                <div className="swatch-copy">
                  <h4>{swatch.name}</h4>
                  <code>{swatch.hex}</code>
                  <p>{swatch.explanation}</p>
                  <div className="tool-actions">
                    <button type="button" className="text-link" onClick={() => copy(swatch.hex)}>
                      <Copy size={15} /> Copy HEX
                    </button>
                    <button
                      type="button" className="text-link" aria-pressed={favorites.has(swatch.hex)}
                      disabled={Boolean(pending) || !data} onClick={() => toggle(swatch)}
                    >
                      <Heart size={15} fill={favorites.has(swatch.hex) ? 'currentColor' : 'none'} />
                      {favorites.has(swatch.hex) ? 'Saved' : 'Save'}
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>
      ))}
    </section>
  )
}

export default function AnalysisPage({ portrait, onPortrait }) {
  const { id } = useParams()
  const { data, error } = useWorkspaceData(/^\d+$/.test(id) ? `/api/analyses/${id}` : '/api/analyses/0')
  return (
    <main className="frame studio workspace-page" id="main-content" tabIndex={-1}>
      <Link to="/history" className="back-link text-link">My analyses</Link>
      {data ? (
        <>
          <div className="editorial-heading">
            <div>
              <h1>{data.season.tentative ? 'Explore' : 'Your'} {data.season.name} palette</h1>
              {data.season.tentative ? <p className="muted">Tentative match · {data.season.confidence.toLowerCase()} confidence.
                {data.season.alternative ? ` Compare ${data.season.alternative} before deciding.` : ''}</p> : null}
              <p className="studio-intro">{data.season.description}</p>
            </div>
            <div className="tool-actions">
              <Link className="button button-primary" to={`/studio?analysis=${id}`}>Explore color studio</Link>
              <a className="button button-outline" href={`/api/analyses/${id}/report.pdf`} download><Download size={17} /> Download PDF</a>
              {portrait?.id === data.id ? <button type="button" className="text-link" onClick={() => onPortrait(null)}>Remove portrait</button> : null}
            </div>
          </div>
          {data.capture_warnings?.length ? (
            <section className="workspace-card photo-notes" aria-label="Photo conditions">
              <h2>Photo notes</h2>
              {data.capture_warnings.map((warning) => <p key={warning.code}>{warning.message}</p>)}
            </section>
          ) : null}
          <div className="measurement-grid">
            <article className="workspace-card">
              <h2>Skin depth</h2>
              <div className="sample-pair">
                <div><i style={{ backgroundColor: data.skin.hex }} /><small>Photo sample {data.skin.hex}</small></div>
                <div><i style={{ backgroundColor: data.skin.reference_hex }} /><small>Monk {data.skin.monk_index} reference</small></div>
              </div>
              <p>{data.skin.depth} by measured lightness.</p>
            </article>
            <article className="workspace-card">
              <h2>Undertone</h2>
              <strong>{data.undertone.category} · {data.undertone.confidence.toLowerCase()} confidence</strong>
              <p>{data.undertone.reason}</p>
            </article>
            <article className="workspace-card">
              <h2>Facial contrast</h2>
              <strong>{data.contrast.level}</strong>
              <p>{data.contrast.reason}</p>
            </article>
          </div>
          <details className="workspace-card reasoning" open>
            <summary>Why {data.season.name}?</summary>
            <p>{data.season.reason} Confidence is {data.season.confidence.toLowerCase()}.
              {data.season.alternative ? ` Consider ${data.season.alternative} as an alternative.` : ''}</p>
            <p><strong>{data.season.tentative ? 'Tentative estimate · ' : ''}{data.season.score_label || 'Weighted fit scores'}</strong></p>
            <div className="season-scores" aria-label={data.season.score_label || 'Weighted fit scores'}>
              {data.season.ranked.map(({ name, score }) => (
                <div key={name}><span>{name}</span><meter value={score} max="100">{score}</meter><b>{score}</b></div>
              ))}
            </div>
            {data.season.rules.map((rule) => <p key={rule}>{rule}</p>)}
            {data.season.cautions?.map((note) => <p key={note}>{note}</p>)}
            {data.season.stability ? <p>{data.season.stability.description} Agreement: {data.season.stability.agreement}%.</p> : null}
            {data.season.evaluation ? <p className="muted">
              Model {data.season.version}: trained on {data.season.evaluation.training_rows} feature rows.
              Held-out feature accuracy: {(100 * data.season.evaluation.test.accuracy).toFixed(1)}% across {data.season.evaluation.test.rows} rows
              from {data.season.evaluation.test_identities} supplied identities. {data.season.evaluation.scope}
            </p> : null}
            <p className="muted">{data.season.method === 'trained_model' ? 'Support values are experimental model probabilities, not personal accuracy.' : 'The numbers are heuristic fit scores.'} {data.limitations[0]}</p>
          </details>
          <PaletteGroups analysis={data} />
          <details className="workspace-card reasoning">
            <summary>Photo measurements and limitations</summary>
            <div className="table-scroll">
              <table>
                <thead><tr><th>Region</th><th>HEX</th><th>RGB</th><th>HSV (°, %, %)</th><th>CIE Lab</th></tr></thead>
                <tbody>
                  {data.skin.patches.map((patch) => (
                    <tr key={patch.region}><th>{patch.region.replace('_', ' ')}</th><td>{patch.hex}</td>
                      <td>{patch.rgb.join(', ')}</td><td>{['h','s','v'].map((key) => patch.hsv[key]).join(', ')}</td>
                      <td>{['l','a','b'].map((key) => patch.lab[key]).join(', ')}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="measurement-grid">
              {['hair', 'eyes'].map((region) => {
                const feature = data.features?.[region]
                return <div key={region}><strong>{region === 'hair' ? 'Hair' : 'Eyes'}</strong>
                  <p>{feature ? `${feature.hex} · ${feature.source || 'provided'} · CIE Lab ${['l','a','b'].map((key) => feature.lab[key]).join(', ')}` : 'Not reliably measured; optional manual input is available.'}</p>
                  {feature?.note ? <p>{feature.note}</p> : null}
                </div>
              })}
            </div>
            {data.limitations.map((limit) => <p key={limit}>{limit}</p>)}
            <p className="muted">{formatDate(data.created_at)} · Knowledge base {data.knowledge_version}</p>
          </details>
        </>
      ) : (
        <><h1>Your colors</h1><p className="studio-intro" role={error ? 'alert' : 'status'}>{error || 'Loading your analysis…'}</p></>
      )}
    </main>
  )
}
