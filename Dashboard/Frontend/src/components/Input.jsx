// src/components/Input.jsx
const Input = ({ label, type, value, onChange, placeholder }) => (
  <div className="flex flex-col mb-4">
    <label className="text-gray-700 mb-2 font-medium">{label}</label>
    <input
      type={type}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      className="p-3 border rounded-lg focus:ring-2 focus:ring-blue-400 focus:outline-none"
    />
  </div>
);

export default Input;
