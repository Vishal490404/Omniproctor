import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import Navbar from "../components/Navbar";
import { FiClipboard, FiPlusCircle } from "react-icons/fi";

const Dashboard = () => {
  const stats = {
    activeTests: 12,
    totalUsers: 146,
    pendingReviews: 4,
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-indigo-50 to-slate-100">
      <Navbar />

      {/* Main Section */}
      <div className="max-w-6xl mx-auto px-6 py-10">
        {/* Greeting */}
        <motion.h2
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-3xl font-bold text-slate-800 mb-10 text-center"
        >
          👋 Welcome back,{" "}
          <span className="bg-gradient-to-r from-indigo-500 to-purple-500 bg-clip-text text-transparent">
            Admin
          </span>
        </motion.h2>

        {/* Stats Overview */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-10">
          {[
            { label: "Active Tests", value: stats.activeTests },
            { label: "Total Users", value: stats.totalUsers },
            { label: "Pending Reviews", value: stats.pendingReviews },
          ].map((item, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 * idx }}
              className="bg-white border border-indigo-100 rounded-2xl shadow-md hover:shadow-xl p-6 flex flex-col items-center transition-all duration-300"
            >
              <h3 className="text-4xl font-semibold text-indigo-600">
                {item.value}
              </h3>
              <p className="text-slate-500 mt-1 text-sm font-medium tracking-wide">
                {item.label}
              </p>
            </motion.div>
          ))}
        </div>

        {/* Action Cards */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="grid sm:grid-cols-2 gap-8 justify-center items-center"
        >
          {/* List Active Tests */}
          <Link
            to="/active"
            className="group relative bg-white border border-indigo-100 p-8 rounded-2xl shadow-md hover:shadow-2xl transition-all duration-300 flex flex-col items-center justify-center overflow-hidden"
          >
            <div className="bg-gradient-to-tr from-indigo-500 to-purple-500 text-white p-4 rounded-full mb-4 group-hover:scale-110 transition-transform shadow-md">
              <FiClipboard size={32} />
            </div>
            <h3 className="text-xl font-semibold text-slate-800 mb-2">
              List Active Tests
            </h3>
            <p className="text-slate-500 text-sm text-center">
              View and manage all ongoing assessments in real time.
            </p>
            <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-purple-500/5 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity"></div>
          </Link>

          {/* Create New Test */}
          <Link
            to="/create"
            className="group relative bg-white border border-indigo-100 p-8 rounded-2xl shadow-md hover:shadow-2xl transition-all duration-300 flex flex-col items-center justify-center overflow-hidden"
          >
            <div className="bg-gradient-to-tr from-indigo-500 to-purple-500 text-white p-4 rounded-full mb-4 group-hover:scale-110 transition-transform shadow-md">
              <FiPlusCircle size={32} />
            </div>
            <h3 className="text-xl font-semibold text-slate-800 mb-2">
              Create New Test
            </h3>
            <p className="text-slate-500 text-sm text-center">
              Add a new test and assign it to your team or candidates.
            </p>
            <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-purple-500/5 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity"></div>
          </Link>
        </motion.div>
      </div>
    </div>
  );
};

export default Dashboard;
