const prisma = require('../config/prisma');

// Add UserTest
exports.addUserTest = async (req, res) => {
  try {
    const { userId, testId, userLocation, image, recording } = req.body;
    const newUserTest = await prisma.userTest.create({
      data: { userId, testId, userLocation, image, recording }
    });
    res.json(newUserTest);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};
