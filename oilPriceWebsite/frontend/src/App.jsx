import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Login from './components/auth/Login';
import Panel from './components/pages/Panel';

function App() {
  return (
    <div>
      <BrowserRouter>
      <Routes>
        <Route path='/Login' element={<Login />}></Route>
        <Route path='/Panel' element={<Panel />}></Route>
      </Routes>
      </BrowserRouter>
    </div>
  )
}

export default App