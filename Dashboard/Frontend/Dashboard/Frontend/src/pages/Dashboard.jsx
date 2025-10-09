import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";

const Dashboard = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  return (
    <div className="min-h-screen bg-blue-50 p-10">
      <div className="bg-white shadow-lg rounded-xl p-6 max-w-3xl mx-auto">
        <h1 className="text-3xl font-bold text-blue-600 mb-4">
          Welcome, {user?.email || "User"}!
        </h1>
        <p className="text-gray-700 mb-6">
          This is your dashboard. You can add analytics, charts, or project cards here.
        </p>
        <button
          onClick={handleLogout}
          className="bg-red-500 text-white px-6 py-2 rounded-lg hover:bg-red-600 transition"
        >
          Logout
        </button>
      </div>
    </div>
  );
};

export default Dashboard;
