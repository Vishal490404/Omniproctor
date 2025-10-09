import { useEffect, useState } from "react";
import Navbar from "../components/Navbar";
import TestCard from "../components/TestCard";
import { motion } from "framer-motion";
// import axios from "axios"; // Uncomment when backend is ready

const ActiveTests = () => {
  const [tests, setTests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    // 🧩 Backend call placeholder
    // Uncomment and configure when API is ready
    /*
    const fetchTests = async () => {
      try {
        const response = await axios.get("/api/tests/active"); 
        // Replace with your real backend endpoint
        setTests(response.data || []);
      } catch (err) {
        console.error("Error fetching tests:", err);
        setError("Failed to fetch tests. Please try again later.");
      } finally {
        setLoading(false);
      }
    };

    fetchTests();
    */

    // 🧪 Dummy data for UI showcase
    setTimeout(() => {
      setTests([
        { id: 1, name: "Frontend Assessment" },
        { id: 2, name: "Backend Challenge" },
        { id: 3, name: "System Design Quiz" },
      ]);
      setLoading(false);
    }, 1000);
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-indigo-50 to-slate-100">
      <Navbar />

      <div className="max-w-6xl mx-auto px-6 py-10">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="flex justify-between items-center mb-10"
        >
          <h2 className="text-3xl font-semibold text-slate-800 tracking-tight">
            Active Tests
          </h2>
          <button className="bg-indigo-600 hover:bg-indigo-700 text-white font-medium px-5 py-2 rounded-lg shadow-md transition-all duration-300">
            + New Test
          </button>
        </motion.div>

        {/* Loading State */}
        {loading && (
          <div className="flex justify-center items-center h-48">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600"></div>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="text-center text-red-500 font-medium">{error}</div>
        )}

        {/* Test Cards */}
        {!loading && !error && tests.length > 0 && (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {tests.map((test, index) => (
              <motion.div
                key={test.id}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
              >
                <TestCard name={test.name} id={test.id} />
              </motion.div>
            ))}
          </div>
        )}

        {/* Empty State */}
        {!loading && !error && tests.length === 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center mt-20"
          >
            <h3 className="text-xl font-semibold text-slate-600 mb-2">
              No Active Tests Found
            </h3>
            <p className="text-slate-500 mb-4">
              Looks like you haven’t created any tests yet.
            </p>
            <button className="bg-indigo-600 hover:bg-indigo-700 text-white font-medium px-6 py-2 rounded-lg shadow-md transition-all duration-300">
              Create a Test
            </button>
          </motion.div>
        )}
      </div>
    </div>
  );
};

export default ActiveTests;
