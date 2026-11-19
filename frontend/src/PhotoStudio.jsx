import {
  ArrowLeft, Camera, Check, CircleAlert, CircleCheck,
  ImagePlus, LoaderCircle, RotateCcw, Trash2, UserRound,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import CameraCapture from './CameraCapture.jsx'
import { photoAccept, photoMaxMiB, photoSelectionError, validatePhoto } from './photoApi.js'
import floralArt from './assets/givyn-garden.webp'

const hairOptions = [['Black','#241D20'], ['Dark brown','#3A2621'], ['Brown','#634438'], ['Light brown','#956C4D'],
  ['Auburn','#8A4834'], ['Red','#B96538'], ['Blonde','#C9A568'], ['Gray','#9D9B9B'], ['White','#E7E1D9']]
const eyeOptions = [['Dark brown','#382822'], ['Brown','#644838'], ['Hazel','#887749'], ['Amber','#A27432'],
  ['Green','#688473'], ['Blue','#6689A3'], ['Gray','#839297']]
const initialFeatures = { hair: '', eyes: '', observation: '' }

function NaturalFeatures({ features, onChange, disabled }) {
  return (
    <fieldset className="feature-fields" disabled={disabled}>
      <legend>Natural colors <span>optional</span></legend>
      <p>These help when the photo leaves your hair, eye color, or undertone uncertain.</p>
      <div className="input-grid">
        {[['hair', 'Natural hair color', hairOptions, 'Estimate from photo'], ['eyes', 'Natural eye color', eyeOptions, 'Estimate from photo']].map(([key, label, choices, empty]) => (
          <label key={key}>{label}
            <select value={features[key]} onChange={(event) => onChange(key, event.target.value)}>
              <option value="">{empty}</option>
              {choices.map(([name, hex]) => <option value={hex} key={hex}>{name}</option>)}
            </select>
          </label>
        ))}
        <label>Which drapes feel more harmonious?
          <select value={features.observation} onChange={(event) => onChange('observation', event.target.value)}>
            <option value="">Unsure</option>
            <option value="warm">Warmer colors, such as peach</option>
            <option value="cool">Cooler colors, such as berry</option>
            <option value="mixed">Both about the same</option>
          </select>
        </label>
      </div>
    </fieldset>
  )
}

const tips = [
  'Use soft, even light.',
  'Face the camera with your forehead and cheeks visible.',
  'Use an original photo without filters or heavy makeup.',
]

function PhotoGuide() {
  return (
    <aside id="photo-guide" className="photo-guide" aria-labelledby="guide-title" tabIndex={-1}>
      <div className="guide-art" aria-hidden="true">
        <img src={floralArt} alt="" />
      </div>
      <div className="guide-copy">
        <h2 id="guide-title">Photo guide</h2>
        <ul>
          {tips.map((tip) => (
            <li key={tip} className="flex items-start gap-4">
              <Check size={23} strokeWidth={1.8} aria-hidden="true" />
              <span>{tip}</span>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  )
}

function DropZone({ onChoose, onCamera, onDrop, chooseRef, cameraRef }) {
  const [dragging, setDragging] = useState(false)

  return (
    <section
      className={`drop-zone ${dragging ? 'is-dragging' : ''}`}
      aria-labelledby="drop-title"
      onDragOver={(event) => {
        if (!event.dataTransfer.types.includes('Files')) return
        event.preventDefault()
        event.dataTransfer.dropEffect = 'copy'
        setDragging(true)
      }}
      onDragLeave={(event) => {
        if (!(event.relatedTarget instanceof Node) || !event.currentTarget.contains(event.relatedTarget)) setDragging(false)
      }}
      onDrop={(event) => {
        event.preventDefault()
        setDragging(false)
        onDrop(Array.from(event.dataTransfer.files))
      }}
    >
      <UserRound size={67} strokeWidth={1.15} className="drop-icon" aria-hidden="true" />
      <h2 id="drop-title">Drop your portrait here</h2>
      <p>JPG, JPEG, or PNG · up to {photoMaxMiB} MiB</p>
      <div className="photo-actions flex flex-wrap items-center justify-center">
        <button className="button button-primary" ref={chooseRef} type="button" onClick={onChoose}>Choose a photo</button>
        <button className="button button-outline" ref={cameraRef} type="button" onClick={onCamera}>
          <Camera size={20} aria-hidden="true" /> Use camera
        </button>
      </div>
    </section>
  )
}

function PortraitPreview({ file, onChoose, onCamera, onRemove, cameraRef, busy }) {
  const [preview, setPreview] = useState(null)
  const [broken, setBroken] = useState(false)

  useEffect(() => {
    const url = URL.createObjectURL(file)
    setPreview({ file, url })
    setBroken(false)
    return () => URL.revokeObjectURL(url)
  }, [file])

  return (
    <section className="portrait-preview" aria-label="Selected photo">
      <div className="preview-image">
        {preview?.file === file && (
          broken
            ? <p className="preview-unavailable"><ImagePlus size={25} aria-hidden="true" /> Preview unavailable</p>
            : <img src={preview.url} alt="Your selected portrait" onError={() => setBroken(true)} />
        )}
      </div>
      <div className="preview-tools flex flex-wrap items-center">
        <span className="photo-name" title={file.name}>{file.name}</span>
        <button type="button" className="text-link" onClick={onChoose} disabled={busy}>
          <RotateCcw size={15} aria-hidden="true" /> Replace photo
        </button>
        <button type="button" className="text-link" ref={cameraRef} onClick={onCamera} disabled={busy}>
          <Camera size={16} aria-hidden="true" /> Use camera
        </button>
        <button type="button" className="text-link" onClick={onRemove}>
          <Trash2 size={16} aria-hidden="true" /> Remove photo
        </button>
      </div>
    </section>
  )
}

function ValidationFeedback({ result }) {
  const headingRef = useRef(null)
  useEffect(() => {
    headingRef.current?.focus()
  }, [result])

  if (!result) return null
  const passed = result.status === 'valid'
  const retake = result.status === 'retake'
  const Icon = passed ? CircleCheck : CircleAlert

  return (
    <section className={`feedback ${passed ? 'feedback-pass' : 'feedback-issue'}`} role={passed ? 'status' : 'alert'}>
      <Icon size={23} aria-hidden="true" />
      <div>
        <h2 ref={headingRef} tabIndex={-1}>
          {passed ? 'Your photo has been analyzed' : retake ? 'Try another photo' : 'Couldn’t check your photo'}
        </h2>
        {passed ? <p>GIVYN used the available facial details to estimate your colors.</p> : null}
        {passed && result.warnings?.length ? (
          <ul>{result.warnings.map((warning) => <li key={warning.code}>{warning.message}</li>)}</ul>
        ) : null}
        {passed ? <Link className="button button-primary result-link" to={`/analysis/${result.analysis.id}`}>Open my results</Link> : null}
        {retake ? (
          <ul>
            {result.issues.map((issue) => <li key={issue.code}>{issue.message}</li>)}
          </ul>
        ) : null}
        {result.status === 'error' ? <p>{result.message}</p> : null}
      </div>
    </section>
  )
}

export default function PhotoStudio({ onPortrait }) {
  const [file, setFile] = useState(null)
  const [consent, setConsent] = useState(false)
  const [cameraOpen, setCameraOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const [selectionError, setSelectionError] = useState('')
  const [features, setFeatures] = useState(initialFeatures)
  const inputRef = useRef(null)
  const requestRef = useRef(null)
  const chooseRef = useRef(null)
  const cameraRef = useRef(null)
  const consentRef = useRef(null)
  const nextFocus = useRef(null)

  useEffect(() => () => {
    requestRef.current?.abort()
    requestRef.current = null
  }, [])
  useEffect(() => {
    nextFocus.current?.current?.focus()
    nextFocus.current = null
  }, [file, cameraOpen])

  const completed = result?.status === 'valid' || result?.status === 'retake'
  const canCheck = file && consent && !busy && !completed

  function cancelCheck() {
    requestRef.current?.abort()
    requestRef.current = null
    setBusy(false)
  }

  function stagePhoto(files) {
    const error = photoSelectionError(files)
    setSelectionError(error)
    if (error) return
    cancelCheck()
    onPortrait(null)
    nextFocus.current = consentRef
    setFile(files[0])
    setResult(null)
    setConsent(false)
    setCameraOpen(false)
  }

  function removePhoto() {
    cancelCheck()
    onPortrait(null)
    nextFocus.current = chooseRef
    setFile(null)
    setFeatures(initialFeatures)
    setConsent(false)
    setResult(null)
    setSelectionError('')
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (!canCheck || requestRef.current) return
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort('timeout'), 30000)
    requestRef.current = controller
    setSelectionError('')
    setResult(null)
    setBusy(true)
    try {
      const outcome = await validatePhoto(file, controller.signal, features)
      if (requestRef.current === controller) {
        if (outcome.analysis) onPortrait({ file, id: outcome.analysis.id, anchor: outcome.analysis.drape_anchor })
        setResult(outcome)
      }
    } catch {
      if (requestRef.current === controller) {
        setResult({
          status: 'error',
          message: controller.signal.aborted
            ? 'The photo check took too long. Try again.'
            : 'Could not reach the photo checker. Make sure GIVYN’s server is running and try again.',
        })
      }
    } finally {
      window.clearTimeout(timeout)
      if (requestRef.current === controller) {
        requestRef.current = null
        setBusy(false)
      }
    }
  }

  const choosePhoto = () => inputRef.current?.click()
  const openCamera = () => {
    setSelectionError('')
    setCameraOpen(true)
  }
  const closeCamera = () => {
    nextFocus.current = cameraRef
    setCameraOpen(false)
  }

  return (
    <main id="main-content" className="frame studio" tabIndex={-1}>
      <Link to="/" className="back-link text-link"><ArrowLeft size={21} aria-hidden="true" /> Back to home</Link>
      <h1>Check your photo</h1>
      <p className="studio-intro">Start with a portrait in soft, even light.</p>
      <div className="studio-layout grid items-stretch">
        <form className="photo-form" onSubmit={handleSubmit} aria-label="Check a portrait">
          <input
            ref={inputRef}
            type="file"
            accept={photoAccept}
            aria-label="Portrait photo file"
            hidden
            onChange={(event) => {
              const files = Array.from(event.target.files)
              event.target.value = ''
              if (files.length) stagePhoto(files)
            }}
          />
          {cameraOpen ? (
            <CameraCapture onCapture={(capture) => stagePhoto([capture])} onClose={closeCamera} />
          ) : (
            <>
              {file ? (
                <PortraitPreview
                  file={file}
                  onChoose={choosePhoto}
                  onCamera={openCamera}
                  onRemove={removePhoto}
                  cameraRef={cameraRef}
                  busy={busy}
                />
              ) : (
                <DropZone
                  onChoose={choosePhoto}
                  onCamera={openCamera}
                  onDrop={stagePhoto}
                  chooseRef={chooseRef}
                  cameraRef={cameraRef}
                />
              )}
              {selectionError ? <p className="inline-error" role="alert">{selectionError}</p> : null}
              {file && !completed ? (
                <NaturalFeatures
                  features={features}
                  onChange={(key, value) => setFeatures((current) => ({ ...current, [key]: value }))}
                  disabled={busy}
                />
              ) : null}
              <label className="consent flex items-start gap-3">
                <input
                  type="checkbox"
                  ref={consentRef}
                  checked={consent}
                  disabled={!file || busy || completed}
                  onChange={(event) => setConsent(event.target.checked)}
                />
                <span>
                  I consent to GIVYN checking and analyzing this photo.
                  <small>The server discards the photo. Your measurements and palette are saved to this browser’s history.</small>
                </span>
              </label>
              <ValidationFeedback result={result} />
              {completed ? null : (
                <button type="submit" className="button button-primary check-button" disabled={!canCheck}>
                  {busy ? <><LoaderCircle className="spinner" size={21} aria-hidden="true" /> Checking and analyzing…</> : 'Check and analyze'}
                </button>
              )}
              {busy ? (
                <div className="check-progress flex items-center justify-between gap-3">
                  <p role="status">Checking photo quality and measuring the available colors.</p>
                  <button type="button" className="text-link" onClick={cancelCheck}>Cancel check</button>
                </div>
              ) : null}
            </>
          )}
        </form>
        <PhotoGuide />
      </div>
    </main>
  )
}
