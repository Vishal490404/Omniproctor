const prisma = require('../config/prisma');

// Get total number of users
exports.getUserCount = async (req, res) => {
  try {
    const count = await prisma.user.count();
    res.json({ count });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};

// Get user info by ID
exports.getUserById = async (req, res) => {
  try {
    const user = await prisma.user.findUnique({
      where: { id: parseInt(req.params.id) },
      include: { userTests: true }
    });
    if (!user) return res.status(404).json({ message: "User not found" });
    res.json(user);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};

// Add user
exports.addUser = async (req, res) => {
  try {
    const { id, name, branch, image } = req.body;
    const newUser = await prisma.user.create({
      data: { id, name, branch, image }
    });
    res.json(newUser);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};
