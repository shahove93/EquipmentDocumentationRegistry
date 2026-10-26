import { Navigate, Route, Routes } from 'react-router-dom'

import Nav from './components/Nav'
import DocumentCardPage from './pages/DocumentCardPage'
import DocumentCreatePage from './pages/DocumentCreatePage'
import MaterialsPage from './pages/MaterialsPage'
import BatchesPage from './pages/BatchesPage'
import RegistryPage from './pages/RegistryPage'

export default function App() {
  return (
    <>
      <Nav />
      <Routes>
        <Route path="/" element={<RegistryPage />} />
        {/*
          Declared before the id route for the reader's sake. Ranking is by
          specificity, not by order, so `/documents/new` would win over
          `/documents/:id` either way — and it has to, because `new` is not a
          document id and the card would reject it.
        */}
        <Route path="/documents/new" element={<DocumentCreatePage />} />
        <Route path="/documents/:id" element={<DocumentCardPage />} />
        <Route path="/materials" element={<MaterialsPage />} />
        <Route path="/batches" element={<BatchesPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}
