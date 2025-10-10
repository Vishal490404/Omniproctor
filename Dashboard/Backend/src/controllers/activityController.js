const prisma = require('../config/prisma');

// View all activities
exports.viewActivities = async (req, res) => {
  try {
    const activities = await prisma.activity.findMany({
      include: { userTest: true }
    });
    res.json(activities);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};

// Add activity
exports.addActivity = async (req, res) => {
  try {
    const { userTestId, timeIssue, type, screenshot, metadata } = req.body;
    const newActivity = await prisma.activity.create({
      data: {
        userTestId,
        timeIssue: new Date(timeIssue),
        type,
        screenshot,
        metadata
      }
    });
    res.json(newActivity);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};
