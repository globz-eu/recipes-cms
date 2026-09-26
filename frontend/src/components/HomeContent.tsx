import { apiUrl, resetCsrfToken } from '../api/client'
import type { HomePage } from '../api/home'

interface HomeContentProps {
  pages: HomePage[]
}

export function HomeContent({ pages }: HomeContentProps) {
  return (
    <div className="home-content">
      {pages.map((page, index) => (
        <article key={index}>
          <h1>{page.title}</h1>
          {page.description && <p>{page.description}</p>}
        </article>
      ))}
      <footer>
        <a
          href={apiUrl(`/admin/logout/?next=${encodeURIComponent(window.location.href)}`)}
          onClick={resetCsrfToken}
        >
          Log out
        </a>
      </footer>
    </div>
  )
}
