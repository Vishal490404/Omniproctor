import Navbar from "../components/Navbar";
import { useState } from "react";

const CreateTest = () => {
  const [link, setLink] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    alert(`Test Created with Link: ${link}`);
  };

  return (
    <div className="min-h-screen bg-gray-100">
      <Navbar />
      <div className="p-8 max-w-xl mx-auto">
        <h2 className="text-xl font-semibold mb-6">Create New Test</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
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
