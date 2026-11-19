import { ArrowDown, ArrowRight, CircleCheck, Image as ImageIcon, Library, Palette, SlidersHorizontal } from 'lucide-react'
import { Link } from 'react-router'
import garden from './assets/givyn-garden.webp'
import floralArt from './assets/cosmos-and-glass.webp'

const steps = [
  { icon: ImageIcon, title: 'Choose a portrait', text: 'Use a clear, front-facing photo of yourself.' },
  { icon: CircleCheck, title: 'Check and analyze', text: 'GIVYN checks photo quality, then measures skin color and available contrast.' },
  { icon: SlidersHorizontal, title: 'Explore your palette', text: 'Review your season, compare colors, and see what shaped your result.' },
]

const destinations = [
  { icon: ImageIcon, text: 'Photo guide', path: '/photo#photo-guide', art: garden, alignment: '15% 70%' },
  { icon: Palette, text: 'Color studio', path: '/studio', art: floralArt, alignment: '78% 50%' },
  { icon: Library, text: 'My analyses', path: '/history', art: garden, alignment: '70% 70%' },
]

export default function LandingPage() {
  return (
    <main id="main-content" className="landing" tabIndex={-1}>
      <section className="garden-hero" aria-labelledby="landing-title">
        <img src={garden} className="garden-art" alt="" fetchPriority="high" />
        <div className="garden-copy">
          <h1 id="landing-title"><span>Find your</span><span>true colors.</span></h1>
          <p className="garden-subtitle">Personal Color Analysis Expert System</p>
          <p className="garden-description">Discover the colors that complement your natural features, starting with one clear portrait.</p>
          <Link className="button garden-action" to="/photo">
            Begin my analysis <ArrowRight size={20} aria-hidden="true" />
          </Link>
        </div>
        <nav className="garden-destinations" aria-label="Explore GIVYN">
          {destinations.map(({ icon: Icon, text, path, art, alignment }) => (
            <Link className="garden-card" to={path} key={path}>
              <img src={art} style={{ objectPosition: alignment }} alt="" />
              <span><Icon size={17} aria-hidden="true" /> {text}</span>
            </Link>
          ))}
        </nav>
        <Link className="garden-scroll" to="/#how-it-works" aria-label="How it works"><ArrowDown size={18} /></Link>
      </section>
      <section className="frame how-it-works" id="how-it-works" aria-labelledby="how-title" tabIndex={-1}>
        <h2 id="how-title">How it works</h2>
        <ol className="steps grid md:grid-cols-3">
          {steps.map(({ icon: Icon, title, text }) => (
            <li key={title} className="step flex items-start">
              <Icon className="step-icon" size={47} strokeWidth={1.25} aria-hidden="true" />
              <div>
                <h3>{title}</h3>
                <p>{text}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </main>
  )
}
