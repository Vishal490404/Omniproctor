const UserCard = ({ user }) => (
  <div className="flex justify-between items-center p-4 rounded-lg shadow-sm bg-white hover:shadow-md transition">
    <div>
      <p className="text-gray-800 font-semibold text-lg">{user.name}</p>
      {user.score !== undefined && (
        <p className="text-gray-500 text-sm">Score: {user.score}</p>
      )}
    </div>
    {/* Optional placeholder for future actions */}
    <div className="flex items-center gap-2">
      {/* You can add icons or status indicators here if needed */}
    </div>
  </div>
);

export default UserCard;
