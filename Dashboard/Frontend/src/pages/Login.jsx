// src/pages/Login.jsx
import { useState } from "react";
import axios from "axios";
import Input from "../components/Input";
import Button from "../components/Button";
import { useNavigate } from 'react-router-dom'
import { motion } from "framer-motion";

const Login = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage("");

    try {
      // Replace with your API endpoint
      const res = await axios.post("http://localhost:3000/auth/login", {
        email,
        password,
      });

      if (res.data.message === "success") {
        setMessage("Login successful!");
        console.log(res.data.admin.id);
        localStorage.setItem("token", res.data.token);
        localStorage.setItem("adminId", res.data.admin.id);
        localStorage.setItem("adminName", res.data.admin.name);
        navigate("/dashboard");
      } else {
        setMessage(res.data.error || "Invalid credentials");
      }
    } catch (error) {
      setMessage("Login failed. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Left Image Section */}
<motion.div
        initial={{ opacity: 0, x: -50 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.8 }}
        className="hidden md:flex w-1/2 bg-gradient-to-br from-blue-700 to-indigo-600 flex-col justify-center items-center text-white p-12"
      >
        <img
          src="https://digiproctor.com/assets/images/digiProctor%20aI-assisted-remote-proctoring.svg"
          alt="Online Exam"
        />
        <h2 className="text-4xl font-bold mb-2 tracking-tight">
          Secure Online Proctoring
        </h2>
        <p className="text-gray-200 text-center max-w-md leading-relaxed">
          Ensuring fairness and transparency in every test.
        </p>
      </motion.div>


      {/* Right Login Form Section */}
      <div className="w-1/2 bg-white flex items-center justify-center">
        <form
          onSubmit={handleLogin}
          className="bg-white shadow-xl rounded-2xl p-10 w-3/4 max-w-md"
        >
          <h2 className="text-3xl font-bold text-center mb-8 text-blue-700">
            Login
          </h2>
          <Input
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Enter your email"
          />
          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter your password"
          />
          <Button text="Login" loading={loading} />
          {message && (
            <p className="text-center mt-4 text-sm text-red-500">{message}</p>
          )}
        </form>
      </div>
    </div>
  );
};

export default Login;
