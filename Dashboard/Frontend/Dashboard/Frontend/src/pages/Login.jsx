// src/pages/Login.jsx
import { useState } from "react";
import axios from "axios";
import Input from "../components/Input";
import Button from "../components/Button";

const Login = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

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
        // You can navigate or store token here
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
      <div className="w-1/2 bg-blue-100 flex flex-col justify-center items-center p-8">
        <img
          src="https://cdn.pixabay.com/photo/2020/05/01/06/28/exam-5115348_1280.jpg"
          alt="Online Exam"
          className="rounded-2xl shadow-lg mb-6 max-h-[400px]"
        />
        <h2 className="text-3xl font-semibold text-gray-800 text-center">
          Secure Online Proctoring
        </h2>
        <p className="text-gray-600 text-center mt-3 px-8">
          AI-driven monitoring for fair and transparent examinations.
        </p>
      </div>

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
