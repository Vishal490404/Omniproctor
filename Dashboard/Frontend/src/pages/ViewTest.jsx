import { useEffect, useState } from "react";
import Navbar from "../components/Navbar";
import UserCard from "../components/UserCard";
import { useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { FiAlertTriangle, FiCheckCircle, FiXCircle } from "react-icons/fi";
import axios from "axios"; // Uncomment for backend

const ViewTest = () => {
  const { id } = useParams();

  const [testInfo, setTestInfo] = useState({});
  const [users, setUsers] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    // =============================
    // Backend Integration (Axios)
    // =============================
    /*
    const fetchTestData = async () => {
      try {
        const [testRes, userRes, alertRes] = await Promise.all([
          axios.get(`/api/tests/${id}`),
          axios.get(`/api/tests/${id}/users`),
          axios.get(`/api/tests/${id}/alerts`)
        ]);
        setTestInfo(testRes.data);
        setUsers(userRes.data);
        setAlerts(alertRes.data);
      } catch (err) {
        console.error("Error fetching test data:", err);
        setError("Failed to load test details. Please try again later.");
      } finally {
        setLoading(false);
      }
    };
    fetchTestData();
    */

    // =============================
    // Dummy Data for UI Showcase
    // =============================
    setTimeout(() => {
      setTestInfo({ id, name: "Frontend Assessment", date: "2025-10-08", duration: "60 mins" });
      setUsers([
        { name: "John Doe", score: 85 },
        { name: "Jane Smith", score: 78 },
        { name: "Alice Johnson", score: 92 },
      ]);
      setAlerts([
        { id: 1, user: "John Doe", type: "Multiple Face Detected", time: "12:23 PM", severity: "High" },
        { id: 2, user: "John Doe", type: "Tab Switch Detected", time: "12:30 PM", severity: "Medium" },
        { id: 3, user: "Jane Smith", type: "Tab Switch Detected", time: "12:40 PM", severity: "Medium" },
        { id: 4, user: "Alice Johnson", type: "No Malpractice", time: "12:50 PM", severity: "Low" },
      ]);
      setLoading(false);
    }, 1000);
  }, [id]);

  const handleShortlist = (userName) => alert(`${userName} has been shortlisted!`);
  const handleReject = (userName) => alert(`${userName} has been rejected!`);

  if (loading)
    return (
      <div className="flex justify-center items-center h-screen bg-gray-50">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600"></div>
      </div>
    );

  if (error)
    return (
      <div className="flex justify-center items-center h-screen text-red-500 font-medium">{error}</div>
    );

  // Color mapping for severity (modern soft colors)
  const severityColors = {
    High: "bg-red-100 text-red-800",
    Medium: "bg-yellow-100 text-yellow-800",
    Low: "bg-blue-100 text-blue-800",
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-6xl mx-auto px-6 py-10">
        {/* Test Header */}
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="mb-10 text-center">
          <h2 className="text-3xl font-bold text-gray-800 mb-2">{testInfo.name}</h2>
          <p className="text-gray-600">
            Test ID: <span className="font-medium text-gray-700">{testInfo.id}</span> • Date: {testInfo.date} • Duration: {testInfo.duration}
          </p>
        </motion.div>

        {/* Participants with Alerts */}
        {users.map((user) => {
          const userAlerts = alerts.filter((a) => a.user === user.name);
          return (
            <div key={user.name} className="mb-8">
              {/* Participant Card */}
              <UserCard user={user} />

              {/* Participant Alerts */}
              {userAlerts.length > 0 ? (
                <div className="mt-3 space-y-3">
                  {userAlerts.map((alert, index) => (
                    <motion.div
                      key={alert.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.05 }}
                      className={`flex flex-col sm:flex-row justify-between items-start sm:items-center p-4 rounded-lg shadow-md bg-white border-l-4 `}
                    >
                      <div className="flex-1 flex items-center gap-2 mb-2 sm:mb-0">
                        <FiAlertTriangle className="text-gray-400 w-5 h-5" />
                        <div>
                          <p className="text-sm text-gray-500 mb-0.5">{alert.time}</p>
                          <p className="font-medium text-gray-800">{alert.type}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`inline-block px-3 py-1 text-xs font-semibold rounded-full ${severityColors[alert.severity]}`}>
                          {alert.severity} Severity
                        </span>
                        <button onClick={() => handleShortlist(alert.user)} className="bg-green-500 text-white px-3 py-1 rounded-lg hover:bg-green-600 transition flex items-center gap-1">
                          <FiCheckCircle /> Shortlist
                        </button>
                        <button onClick={() => handleReject(alert.user)} className="bg-red-500 text-white px-3 py-1 rounded-lg hover:bg-red-600 transition flex items-center gap-1">
                          <FiXCircle /> Reject
                        </button>
                      </div>
                    </motion.div>
                  ))}
                </div>
              ) : (
                <div className="mt-2 text-gray-500 italic">No alerts for this participant.</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ViewTest;
