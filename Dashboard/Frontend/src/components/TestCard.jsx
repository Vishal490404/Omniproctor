import { Link } from "react-router-dom";

const TestCard = ({ name, id }) => (
  <div className="flex justify-between items-center border p-4 rounded-lg shadow-sm hover:shadow-md">
    <h3 className="font-medium text-gray-800">{name}</h3>
    <Link to={`/view/${id}`} className="bg-purple-600 text-white px-4 py-1 rounded hover:bg-purple-700">
      View Test
    </Link>
  </div>
);

export default TestCard;
