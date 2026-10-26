import { Link, useLocation } from 'react-router-dom'

/**
 * The two top-level sections.
 *
 * The active item is decided from the path rather than by `NavLink`'s own
 * matching: the registry lives at `/`, and its cards and create screen live
 * under `/documents`, all of which belong to «Документы». A `NavLink to="/"`
 * would either mark itself active everywhere or nowhere, and neither is the
 * truth here.
 */
export default function Nav() {
  const { pathname } = useLocation()

  const documentsActive =
    pathname === '/' || pathname === '/documents' || pathname.startsWith('/documents/')
  const materialsActive = pathname === '/materials' || pathname.startsWith('/materials/')
  const batchesActive = pathname === '/batches' || pathname.startsWith('/batches/')

  const linkClass = (active: boolean) =>
    active ? 'nav__link nav__link--active' : 'nav__link'

  return (
    <nav className="nav" aria-label="Разделы">
      <div className="nav__inner">
        <span className="nav__brand">Equipment Documentation Registry</span>
        <div className="nav__links">
          <Link
            className={linkClass(documentsActive)}
            to="/"
            aria-current={documentsActive ? 'page' : undefined}
          >
            Документы
          </Link>
          <Link className={linkClass(batchesActive)} to="/batches" aria-current={batchesActive ? 'page' : undefined}>Партии</Link>
          <Link
            className={linkClass(materialsActive)}
            to="/materials"
            aria-current={materialsActive ? 'page' : undefined}
          >
            Материалы и оборудование
          </Link>
        </div>
      </div>
    </nav>
  )
}
