// src/pages/Signup.jsx
import { useState } from "react";
import axios from "axios";
import Input from "../components/Input";
import Button from "../components/Button";

const Signup = () => {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const handleSignup = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage("");

    try {
      // Replace with your signup API endpoint
      const res = await axios.post("http://localhost:3000/auth/signup", {
        name,
        email,
        password,
      });

      if (res.data.message === "registered successful") {
        setMessage("Account created successfully! You can now log in.");
        setName("");
        setEmail("");
        setPassword("");
      } else {
        setMessage(res.data.message || "Signup failed. Try again.");
      }
    } catch (error) {
      setMessage("Signup failed. Please check your details.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Left Image Section */}
      <div className="w-1/2 bg-blue-100 flex flex-col justify-center items-center p-8">
        <img
          src="https://cdn.pixabay.com/photo/2020/06/10/14/20/online-exam-5282975_1280.jpg"
          alt="Proctored Exam"
          className="rounded-2xl shadow-lg mb-6 max-h-[400px]"
        />
        <h2 className="text-3xl font-semibold text-gray-800 text-center">
          Join Our Secure Exam Platform
        </h2>
        <p className="text-gray-600 text-center mt-3 px-8">
          Create your account and get started with AI-powered proctoring.
        </p>
      </div>

      {/* Right Signup Form Section */}
      <div className="w-1/2 bg-white flex items-center justify-center">
        <form
          onSubmit={handleSignup}
          className="bg-white shadow-xl rounded-2xl p-10 w-3/4 max-w-md"
        >
          <h2 className="text-3xl font-bold text-center mb-8 text-blue-700">
            Sign Up
          </h2>
          <Input
            label="Name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Enter your full name"
          />
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
            placeholder="Create a password"
          />
          <Button text="Sign Up" loading={loading} />
          {message && (
            <p className="text-center mt-4 text-sm text-red-500">{message}</p>
          )}
        </form>
      </div>
    </div>
  );
};

export default Signup;
