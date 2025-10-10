const prisma = require('../config/prisma');

// Get test details
exports.getTestById = async (req, res) => {
  try {
    const test = await prisma.test.findUnique({
      where: { id: parseInt(req.params.id) },
      include: { admin: true, userTests: true }
    });
    if (!test) return res.status(404).json({ message: "Test not found" });
    res.json(test);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};

// Add test
exports.addTest = async (req, res) => {
  try {
    const { url, name } = req.body;

    // Ensure the logged-in user is an admin
    const adminId = req.user?.id;
    if (!adminId) {
      return res.status(401).json({ message: "Unauthorized: admin not logged in" });
    }

    // Get current date and time
    const now = new Date();
    const date = now; // DateTime field in Prisma expects Date object
    const time = now.toLocaleTimeString("en-IN", { hour12: false }); // e.g., "15:42:10"

    // Create the test
    const newTest = await prisma.test.create({
      data: {
        adminId,
        url,
        name,
        date,
        time,
      },
    });

    res.status(201).json({
      message: "Test created successfully",
      test: newTest,
    });
  } catch (err) {
    console.error("Error creating test:", err);
    res.status(500).json({ error: err.message });
  }
};


// Get all active tests
exports.getActiveTests = async (req, res) => {
  try {
    const activeTests = await prisma.test.findMany({
      where: { isActive: true },
      include: {
        admin: true,         // Optional — include admin info
        userTests: true      // Optional — include related user tests
      }
    });
    res.json(activeTests);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};

exports.getActiveTestCount = async (req, res) => {
  try {
    const count = await prisma.test.count({
      where: { isActive: true }
    });
    res.json({ count });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};
