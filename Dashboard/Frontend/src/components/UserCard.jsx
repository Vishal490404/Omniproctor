const UserCard = ({ user }) => (
  <div className="flex justify-between items-center p-4 rounded-lg shadow-sm bg-white hover:shadow-md transition">
    <div>
      <p className="text-gray-800 font-semibold text-lg">{user.name}</p>
      <p className="text-gray-500 text-sm">Branch: {user.branch}</p>
      {user.image && (
        <img 
          src={user.image} 
          alt={user.name} 
          className="w-10 h-10 rounded-full mt-1"
        />
      )}
    </div>
    {/* Optional placeholder for future actions */}
    <div className="flex items-center gap-2">
      {/* You can add icons or buttons here if needed */}
    </div>
  </div>
);

export default UserCard;
