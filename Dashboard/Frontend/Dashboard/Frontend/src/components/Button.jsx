// src/components/Button.jsx
const Button = ({ text, onClick, loading }) => (
  <button
    onClick={onClick}
    disabled={loading}
    className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-lg transition duration-200 w-full disabled:opacity-60"
  >
    {loading ? "Signing in..." : text}
  </button>
);

export default Button;
