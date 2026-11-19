import { useEffect, useRef, useState } from 'react'

function loadImage(source) {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error('Preview unavailable'))
    image.src = source
  })
}

export default function GarmentPreview({ photoUrl, mask, color, index }) {
  const canvasRef = useRef(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    async function render() {
      try {
        const [photo, garmentMask] = await Promise.all([loadImage(photoUrl), loadImage(mask)])
        if (!active) return
        const canvas = canvasRef.current
        const scale = Math.min(1, 1024 / Math.max(photo.naturalWidth, photo.naturalHeight))
        canvas.width = Math.round(photo.naturalWidth * scale)
        canvas.height = Math.round(photo.naturalHeight * scale)
        const context = canvas.getContext('2d', { willReadFrequently: true })
        if (!context) throw new Error('Canvas unavailable')
        context.drawImage(garmentMask, 0, 0, canvas.width, canvas.height)
        const alpha = context.getImageData(0, 0, canvas.width, canvas.height).data
        context.drawImage(photo, 0, 0, canvas.width, canvas.height)
        const image = context.getImageData(0, 0, canvas.width, canvas.height)
        const target = color.slice(1).match(/../g).map((channel) => parseInt(channel, 16))
        for (let pixel = 0; pixel < image.data.length; pixel += 4) {
          if (alpha[pixel] < 245) continue
          const luma = (.2126 * image.data[pixel] + .7152 * image.data[pixel + 1] + .0722 * image.data[pixel + 2]) / 255
          const shading = .55 + .65 * luma
          for (let channel = 0; channel < 3; channel += 1) {
            image.data[pixel + channel] = Math.min(255, Math.round(target[channel] * shading))
          }
        }
        context.putImageData(image, 0, 0)
        setError('')
      } catch {
        if (active) setError('The garment preview could not be drawn. Try choosing a portrait again.')
      }
    }
    render()
    return () => { active = false }
  }, [photoUrl, mask, color])

  return (
    <>
      <canvas ref={canvasRef} role="img" aria-label={`Your original portrait beside drape ${index + 1}`} className="garment-canvas" />
      {error ? <p role="alert" className="inline-error">{error}</p> : null}
    </>
  )
}
