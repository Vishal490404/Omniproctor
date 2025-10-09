// src/App.jsx
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Dashboard from "./pages/Dashboard";
import ActiveTests from "./pages/ActiveTest";
import ViewTest from "./pages/ViewTest";
import CreateTest from "./pages/CreateTest";


function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/" element={<Dashboard />} />
        <Route path="/active" element={<ActiveTests />} />
        <Route path="/view/:id" element={<ViewTest />} />
        <Route path="/create" element={<CreateTest />} />
      </Routes>
    </Router>
  );
}

export default App;
