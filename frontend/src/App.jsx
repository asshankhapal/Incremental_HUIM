import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import IngestPage from './pages/IngestPage';
import PipelinePage from './pages/PipelinePage';
import ResultsPage from './pages/ResultsPage';
import ConfigPage from './pages/ConfigPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/ingest" element={<IngestPage />} />
          <Route path="/pipeline" element={<PipelinePage />} />
          <Route path="/results" element={<ResultsPage />} />
          <Route path="/config" element={<ConfigPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
