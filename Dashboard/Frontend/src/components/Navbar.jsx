import { FiUser, FiSettings } from "react-icons/fi";

const Navbar = () => (
  <nav className="w-full bg-gradient-to-r from-indigo-600 via-indigo-700 to-indigo-800 text-white shadow-lg">
    <div className="max-w-7xl mx-auto flex justify-between items-center px-8 py-4">
      {/* Left Section */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-white/10 backdrop-blur-md flex items-center justify-center shadow-md">
          <span className="text-lg font-bold text-white tracking-wider">AD</span>
        </div>
        <h1 className="text-2xl font-semibold tracking-wide">Admin Dashboard</h1>
      </div>

      {/* Right Section */}
      <div className="flex items-center gap-6 text-lg">
        <FiSettings
          className="cursor-pointer hover:text-indigo-300 transition-transform duration-200 hover:scale-110"
          title="Settings"
        />
        <div className="relative group">
          <FiUser
            className="cursor-pointer hover:text-indigo-300 transition-transform duration-200 hover:scale-110"
            title="Profile"
          />
          {/* Future dropdown placeholder */}
          <div className="absolute right-0 mt-2 w-40 bg-white text-slate-700 rounded-lg shadow-lg opacity-0 group-hover:opacity-100 group-hover:translate-y-1 transform transition-all duration-300 pointer-events-none group-hover:pointer-events-auto">
            <p className="px-4 py-2 hover:bg-indigo-50 cursor-pointer">Profile</p>
            <p className="px-4 py-2 hover:bg-indigo-50 cursor-pointer">Logout</p>
          </div>
        </div>
      </div>
    </div>
  </nav>
);

export default Navbar;
