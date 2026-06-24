import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Generate from './pages/Generate';
import ContentList from './pages/ContentList';
import ContentDetail from './pages/ContentDetail';
import BulkJobs from './pages/BulkJobs';
import Experiments from './pages/Experiments';
import Settings from './pages/Settings';

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="/generate" element={<Generate />} />
        <Route path="/content" element={<ContentList />} />
        <Route path="/content/:id" element={<ContentDetail />} />
        <Route path="/bulk-jobs" element={<BulkJobs />} />
        <Route path="/experiments" element={<Experiments />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}

export default App;
