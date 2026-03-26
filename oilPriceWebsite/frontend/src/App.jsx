import React from 'react'
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import Login from './components/auth/Login';
import Register from './components/auth/Register';
import Panel from './components/pages/Panel';
import Navbar from './components/nav/Navbar';


function AppLayout() {
  const location = useLocation();
  const showNavbar = location.pathname === '/panel';

  return (
    <>
      {showNavbar && <Navbar />}
      <Routes>
        <Route path="/" element={<Login />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/panel" element={<Panel />} />
      </Routes>
    </>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppLayout />
    </BrowserRouter>
  );
}

export default App