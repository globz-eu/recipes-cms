import { useQuery } from '@tanstack/react-query'
import { ApiError } from './api/client'
import { homeQueryKey, fetchHome } from './api/home'
import { HomeContent } from './components/HomeContent'
import { LoginPrompt } from './components/LoginPrompt'
import './App.css'

function App() {
  const { data, isPending, error } = useQuery({
    queryKey: homeQueryKey,
    queryFn: fetchHome,
    retry: (failureCount, err) => {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        return false
      }
      return failureCount < 2
    },
  })

  if (isPending) {
    return <main><p>Loading...</p></main>
  }

  if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
    return <main><LoginPrompt /></main>
  }

  if (error) {
    return <main><p>Error loading content: {error.message}</p></main>
  }

  return <main><HomeContent pages={data} /></main>
}

export default App
