import { useState } from 'react'
import { ArrowRight, Gem, Palette, ScanFace, SplitSquareHorizontal } from 'lucide-react'
import { Link, useSearchParams } from 'react-router'
import { photoAccept, photoSelectionError } from './photoApi.js'
import { formatDate, usePhotoUrl, useWorkspaceData, workspaceRequest } from './workspaceApi.js'
import GarmentPreview from './GarmentPreview.jsx'

const modes = [
  { id: 'compatibility', name: 'Compatibility', icon: Palette },
  { id: 'comparison', name: 'Color comparison', icon: SplitSquareHorizontal },
  { id: 'metals', name: 'Gold & silver', icon: Gem },
  { id: 'draping', name: 'Virtual draping', icon: ScanFace },
]
const initialColors = ['#D94B35', '#BC174C']
const hexPattern = /^#[0-9a-f]{6}$/i

function ColorInput({ index, value, update, swatches }) {
  const usable = hexPattern.test(value)
  return (
    <div className="workspace-card color-input">
      <div className="color-picker-row">
        <label className="picker-label">
          <span className="sr-only">Pick color {index + 1}</span>
          <input type="color" value={usable ? value : '#A84E68'} onChange={(event) => update(event.target.value.toUpperCase())} />
        </label>
        <label className="hex-label">Color {String.fromCharCode(65 + index)}
          <input type="text" value={value} onChange={(event) => update(event.target.value.toUpperCase())}
            maxLength={7} placeholder="#A84E68" spellCheck={false} />
        </label>
      </div>
      <label>Choose a palette swatch
        <select value={swatches.some((swatch) => swatch.hex === value) ? value : ''}
          onChange={(event) => { if (event.target.value) update(event.target.value) }}>
          <option value="">Select a swatch</option>
          {swatches.map((swatch) => <option value={swatch.hex} key={swatch.hex}>{swatch.name} · {swatch.hex}</option>)}
        </select>
      </label>
    </div>
  )
}

function DrapingPreview({ portrait, onRemove, colors }) {
  const [local, setLocal] = useState(null)
  const [error, setError] = useState('')
  const source = local || portrait?.file
  const url = usePhotoUrl(source)
  const rawAnchor = !local && portrait?.anchor ? portrait.anchor.chin[1] * 100 : 65
  const collarStart = Math.min(78, Math.max(46, rawAnchor))
  const mask = !local && portrait?.anchor?.garment_mask

  function choose(event) {
    const files = Array.from(event.target.files)
    event.target.value = ''
    if (!files.length) return
    const problem = photoSelectionError(files)
    setError(problem)
    if (!problem) setLocal(files[0])
  }

  return (
    <section className="drape-section" aria-labelledby="drape-heading">
      <h2 id="drape-heading">Virtual draping preview</h2>
      <p className="muted">
        {mask
          ? 'This approximate garment preview changes the detected fabric region. Face, hair, and skin are preserved outside that region.'
          : 'This approximate simulation places a colored collar behind your original portrait. Photo pixels are preserved.'}
      </p>
      {url ? (
        <>
          <div className="drape-grid">
            {colors.map((color, index) => (
              <figure key={index}>
                {mask ? (
                  <GarmentPreview photoUrl={url} mask={mask} color={hexPattern.test(color) ? color : '#B9A8A7'} index={index} />
                ) : (
                  <div className="drape-image" style={{ '--drape': hexPattern.test(color) ? color : '#B9A8A7', '--collar': `${collarStart}%` }}>
                    <img src={url} alt={`Your original portrait beside drape ${index + 1}`}
                      onError={() => setError('The portrait could not be previewed. Remove it and choose another JPG or PNG.')} />
                  </div>
                )}
                <figcaption>Drape {String.fromCharCode(65 + index)} · {color}</figcaption>
              </figure>
            ))}
          </div>
          <button className="text-link" type="button" onClick={() => { setLocal(null); setError(''); onRemove() }}>Remove portrait</button>
        </>
      ) : (
        <label className="local-drape-select">Choose a portrait for this preview
          <input type="file" accept={photoAccept} onChange={choose} />
          <small>The preview stays in this browser.</small>
        </label>
      )}
      {error ? <p className="inline-error" role="alert">{error}</p> : null}
    </section>
  )
}

function ComparisonResults({ result, nameForHex }) {
  if (!result) return null
  const multi = result.colors.length > 1
  return (
    <section className="comparison-results" aria-live="polite">
      <h2>{multi ? 'Comparison results' : 'Compatibility result'}</h2>
      {multi && result.winner ? <p className="muted">{nameForHex(result.winner)} scored highest for this analysis.</p> : null}
      {result.tie ? <p className="muted">The top colors scored equally in this comparison.</p> : null}
      <div className="comparison-grid">
        {result.colors.map((color, index) => (
          <article className="swatch-card" key={`${color.hex}-${index}`}>
            <div className="swatch-color" style={{ backgroundColor: color.hex }} />
            <div className="swatch-copy">
              <h3>{color.name || nameForHex(color.hex)}</h3>
              <code>{color.hex}</code>
              <p className="comparison-score"><strong>{color.score}/100</strong> {color.level || 'Metal color fit'}</p>
              {color.hsv ? <p>{color.temperature} · brightness {color.hsv.v}% · saturation {color.hsv.s}%</p> : null}
              <p>{color.explanation}</p>
              {color.nearest ? (
                <p className="chip-swatch"><i style={{ backgroundColor: color.nearest.hex }} />
                  {color.level === 'Less harmonious' ? 'Try' : 'Closest palette color'} {color.nearest.name} {color.nearest.hex}</p>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}

function StudioTools({ analysis, options, portrait, onRemove }) {
  const [mode, setMode] = useState('compatibility')
  const [colors, setColors] = useState(initialColors)
  const [preset, setPreset] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const palette = [...new Map(Object.values(analysis.palette).flat().map((color) => [color.hex, color])).values()]
  const chosen = mode === 'compatibility' ? colors.slice(0, 1) : colors
  const available = mode === 'metals' || chosen.every((hex) => hexPattern.test(hex))

  function selectMode(next) {
    setMode(next)
    setResult(null)
    setError('')
  }

  function pickPreset(label) {
    setPreset(label)
    setResult(null)
    const match = options.comparisons.find((entry) => entry.label === label)
    if (match) setColors(match.colors.map((color) => color.hex))
  }

  const nameForHex = (hex) => {
    const names = [...options.comparisons.flatMap((entry) => entry.colors), ...options.metals, ...palette]
    return names.find((swatch) => swatch.hex === hex)?.name || hex
  }

  async function submit(event) {
    event.preventDefault()
    if (!available || busy) return
    setBusy(true)
    setResult(null)
    setError('')
    try {
      const response = await workspaceRequest(`/api/analyses/${analysis.id}/comparisons`, {
        method: 'POST', body: JSON.stringify({ mode, colors: chosen }),
      })
      setResult(response)
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="studio-modes" aria-label="Color studio tools">
        {modes.map(({ id, name, icon: Icon }) => (
          <button type="button" key={id} className="button button-outline" aria-pressed={mode === id}
            disabled={busy} onClick={() => selectMode(id)}><Icon size={18} /> {name}</button>
        ))}
      </div>
      <form onSubmit={submit}>
        <fieldset disabled={busy}>
          {mode === 'metals' ? (
            <div className="metal-preview">
              {options.metals.map((color) => (
                <div key={color.hex}><i style={{ '--metal': color.hex }} /><span>{color.name}</span><code>{color.hex}</code></div>
              ))}
            </div>
          ) : (
            <>
              <label className="preset-picker">{mode === 'compatibility' ? 'Start with a preset pair’s first color' : 'Comparison preset'}
                <select value={preset} onChange={(event) => pickPreset(event.target.value)}>
                  <option value="">Custom colors</option>
                  {options.comparisons.map((entry) => <option key={entry.label}>{entry.label}</option>)}
                </select>
              </label>
              <div className="color-input-grid">
                {chosen.map((value, index) => (
                  <ColorInput key={index} index={index} value={value} swatches={palette} update={(next) => {
                    setPreset('')
                    setResult(null)
                    setColors((old) => old.map((color, position) => position === index ? next : color))
                  }} />
                ))}
              </div>
              {!available ? <p className="inline-error">Enter a six-digit HEX color such as #A84E68.</p> : null}
              {mode === 'draping' ? <DrapingPreview portrait={portrait} onRemove={onRemove} colors={chosen} /> : null}
            </>
          )}
          <button className="button button-primary studio-submit" disabled={!available || busy}>
            {busy ? 'Comparing…' : mode === 'compatibility' ? 'Check compatibility' : mode === 'metals' ? 'Compare metals' : 'Compare colors'}
            <ArrowRight size={18} />
          </button>
        </fieldset>
      </form>
      {error ? <p className="inline-error" role="alert">{error}</p> : null}
      <ComparisonResults result={result} nameForHex={nameForHex} />
    </>
  )
}

export default function ColorStudio({ portrait, onPortrait }) {
  const [params, setParams] = useSearchParams()
  const { data: history, error: historyError } = useWorkspaceData('/api/history')
  const { data: options, error: optionsError } = useWorkspaceData('/api/colors/options')
  const historyList = history?.analyses || []
  const selected = historyList.find((entry) => String(entry.id) === params.get('analysis')) || historyList[0]
  const { data: analysis, error: analysisError } = useWorkspaceData(selected ? `/api/analyses/${selected.id}` : null)
  const error = historyError || optionsError || analysisError

  return (
    <main className="frame studio workspace-page" id="main-content" tabIndex={-1}>
      <div className="editorial-heading">
        <div><h1>Color studio</h1><p className="studio-intro">Explore how colors work with your personal palette.</p></div>
        {selected ? (
          <label className="analysis-picker">Analysis
            <select value={selected.id} onChange={(event) => setParams({ analysis: event.target.value })}>
              {historyList.map((entry) => <option value={entry.id} key={entry.id}>{entry.season} · {formatDate(entry.created_at)}</option>)}
            </select>
          </label>
        ) : null}
      </div>
      {error ? <p className="inline-error" role="alert">{error}</p> : null}
      {history && !selected ? (
        <div className="workspace-card studio-empty">
          <h2>Start with a portrait</h2>
          <p>Analyze a photo to unlock personalized color checks, comparisons, and draping.</p>
          <Link className="button button-primary" to="/photo">Begin my analysis</Link>
        </div>
      ) : analysis && options ? (
        <StudioTools key={analysis.id} analysis={analysis} options={options}
          portrait={portrait?.id === analysis.id ? portrait : null} onRemove={() => onPortrait(null)} />
      ) : error ? null : <p role="status" className="muted">Preparing your studio…</p>}
    </main>
  )
}
