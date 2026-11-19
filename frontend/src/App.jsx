import { useEffect, useState } from 'react'
import { Link, Navigate, Route, Routes, useLocation } from 'react-router'
import LandingPage from './LandingPage.jsx'
import PhotoStudio from './PhotoStudio.jsx'
import AnalysisPage from './AnalysisPage.jsx'
import ColorStudio from './ColorStudio.jsx'
import HistoryPage from './HistoryPage.jsx'
import brandMark from './assets/givyn-mark.svg'

function Header() {
  const { pathname } = useLocation()
  return (
    <header className={`site-header ${pathname === '/' ? 'landing-header' : 'workspace-header'}`}>
      <nav className="site-nav nav-first" aria-label="Explore">
        <Link to="/">Home</Link>
        <Link to="/photo#photo-guide">Photo guide</Link>
      </nav>
      <Link to="/" className="brand inline-flex items-center" aria-label="GIVYN home">
        <img src={brandMark} alt="" width="34" height="34" />
        <span>GIVYN</span>
      </Link>
      <nav className="site-nav nav-last" aria-label="Your colors">
        <Link to="/studio">Color studio</Link>
        <Link to="/history">My analyses</Link>
      </nav>
    </header>
  )
}

function PageFocus() {
  const { pathname, hash, key } = useLocation()

  useEffect(() => {
    const title = { '/photo': 'Check your photo', '/studio': 'Color studio', '/history': 'My analyses' }[pathname]
    document.title = pathname === '/' ? 'GIVYN — Personal Color Analysis' : `${title || 'Your colors'} — GIVYN`
    const section = hash && document.getElementById(hash.slice(1))
    if (section) {
      section.scrollIntoView()
      section.focus({ preventScroll: true })
    } else {
      window.scrollTo(0, 0)
      if (key !== 'default') {
        document.getElementById('main-content')?.focus({ preventScroll: true })
      }
    }
  }, [pathname, hash, key])

  return null
}

export default function App() {
  const [portrait, setPortrait] = useState(null)
  const { pathname } = useLocation()
  return (
    <div className={pathname === '/' ? 'app-shell' : 'app-shell inner-pages'}>
      <a className="skip-link" href="#main-content">Skip to content</a>
      <Header />
      <PageFocus />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/photo" element={<PhotoStudio onPortrait={setPortrait} />} />
        <Route path="/analysis/:id" element={<AnalysisPage portrait={portrait} onPortrait={setPortrait} />} />
        <Route path="/studio" element={<ColorStudio portrait={portrait} onPortrait={setPortrait} />} />
        <Route path="/history" element={<HistoryPage onPortrait={setPortrait} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  )
}
