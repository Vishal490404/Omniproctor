import Navbar from "../components/Navbar";
import { useState } from "react";
import axios from "axios";

const CreateTest = () => {
  const [name, setName] = useState("");
  const [link, setLink] = useState("");
  const token = localStorage.getItem("token");

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await axios.post(
        "http://localhost:3000/api/tests/addTest",
        {
          url: link,
          name,
        },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      console.log("Test created:", response.data);
      alert("Test created successfully!");
      setLink("");
      setName("");
    } catch (error) {
      console.error("Failed to create test:", error);
      alert("Failed to create test. Please try again.");
    }
  };

  return (
    <div className="min-h-screen bg-gray-100">
      <Navbar />
      <div className="p-8 max-w-xl mx-auto">
        <h2 className="text-xl font-semibold mb-6">Create New Test</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block mb-2 text-gray-700">Test Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter test name"
              className="w-full border p-2 rounded-md focus:ring-2 focus:ring-purple-500"
              required
            />
          </div>
          <div>
            <label className="block mb-2 text-gray-700">Test Link</label>
            <input
              type="text"
              value={link}
              onChange={(e) => setLink(e.target.value)}
              placeholder="Enter test link"
              className="w-full border p-2 rounded-md focus:ring-2 focus:ring-purple-500"
              required
            />
          </div>
          <button className="bg-purple-600 text-white px-5 py-2 rounded-md hover:bg-purple-700">
            Create Test
          </button>
        </form>
      </div>
    </div>
  );
};

export default CreateTest;
