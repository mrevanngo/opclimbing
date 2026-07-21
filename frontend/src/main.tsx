import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import './styles.css';
import ProtectedLayout from './components/ProtectedLayout';
import Login from './routes/login';
import Signup from './routes/signup';
import Home from './routes/home';
import Upload from './routes/upload';
import Annotate from './routes/annotate';
import Analysis from './routes/analysis';
import Profile from './routes/profile';

const root = document.getElementById('root');
if (!root) throw new Error('root element missing');

createRoot(root).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route element={<ProtectedLayout />}>
          <Route path="/" element={<Home />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/climb/:id/holds" element={<Annotate />} />
          <Route path="/climb/:id" element={<Analysis />} />
          <Route path="/profile" element={<Profile />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
