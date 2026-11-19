import { Camera, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

function cameraError(error) {
  switch (error.name) {
    case 'NotAllowedError':
      return 'Camera access was denied. Allow access in your browser or choose a photo instead.'
    case 'NotFoundError':
      return 'No camera was found. You can still choose a photo.'
    case 'NotReadableError':
      return 'The camera is busy. Close any app using it and try again.'
    default:
      return 'The camera could not start. Try again or choose a photo.'
  }
}

export default function CameraCapture({ onCapture, onClose }) {
  const videoRef = useRef(null)
  const headingRef = useRef(null)
  const active = useRef(false)
  const [ready, setReady] = useState(false)
  const [takingPhoto, setTakingPhoto] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const video = videoRef.current
    let stream
    active.current = true
    headingRef.current?.focus()

    async function openCamera() {
      if (!navigator.mediaDevices?.getUserMedia) {
        setError('Camera capture requires localhost or HTTPS and a browser with camera access.')
        return
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 960 } },
          audio: false,
        })
        if (active.current) {
          video.srcObject = stream
        } else {
          stream.getTracks().forEach((track) => track.stop())
        }
      } catch (error) {
        if (active.current) setError(cameraError(error))
      }
    }

    openCamera()
    return () => {
      active.current = false
      stream?.getTracks().forEach((track) => track.stop())
      video.srcObject = null
    }
  }, [])

  function capture() {
    const video = videoRef.current
    if (!video.videoWidth || !video.videoHeight || takingPhoto) return
    const scale = Math.min(1, 2048 / Math.max(video.videoWidth, video.videoHeight))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(video.videoWidth * scale)
    canvas.height = Math.round(video.videoHeight * scale)
    const context = canvas.getContext('2d')
    if (!context) {
      setError('This browser could not capture a photo. Choose a file instead.')
      return
    }
    context.drawImage(video, 0, 0, canvas.width, canvas.height)
    setTakingPhoto(true)
    canvas.toBlob((blob) => {
      if (!active.current) return
      setTakingPhoto(false)
      if (!blob) {
        setError('The photo could not be captured. Try again or choose a file.')
        return
      }
      onCapture(new File([blob], 'camera-portrait.jpg', { type: 'image/jpeg' }))
    }, 'image/jpeg', 0.92)
  }

  return (
    <section className="camera-panel" aria-labelledby="camera-title">
      <div className="flex items-center justify-between gap-3">
        <h2 id="camera-title" ref={headingRef} tabIndex={-1}>Take a portrait</h2>
        <button type="button" className="button button-outline icon-button" aria-label="Close camera" onClick={onClose}>
          <X size={20} aria-hidden="true" />
        </button>
      </div>
      <video
        ref={videoRef}
        className="camera-video"
        aria-label="Live camera preview"
        hidden={Boolean(error)}
        autoPlay
        playsInline
        muted
        onCanPlay={() => setReady(true)}
      />
      {error ? <p className="inline-error" role="alert">{error}</p> : (
        <p className="camera-hint" role="status">{ready ? 'Look straight at the camera.' : 'Waiting for camera access…'}</p>
      )}
      <button
        type="button"
        className="button button-primary"
        disabled={!ready || takingPhoto || Boolean(error)}
        onClick={capture}
      >
        <Camera size={19} aria-hidden="true" /> Take photo
      </button>
    </section>
  )
}
