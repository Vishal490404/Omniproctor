const prisma = require('../config/prisma');

exports.getAdminInfo = async (req, res) => {
  try {
    const admin = await prisma.admin.findUnique({
      where: { id: parseInt(req.params.id) },
      include: { tests: true }
    });
    if (!admin) return res.status(404).json({ message: "Admin not found" });
    res.json(admin);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};

exports.addAdmin = async (req, res) => {
  try {
    const { email, name, password } = req.body;
    const newAdmin = await prisma.admin.create({
      data: { email, name, password }
    });
    res.json(newAdmin);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};
