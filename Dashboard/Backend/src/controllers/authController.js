const bcrypt = require("bcryptjs");
const jwt = require("jsonwebtoken");
const prisma = require("../config/prisma");
require("dotenv").config();

const SECRET_KEY = process.env.JWT_SECRET;

exports.signup = async (req, res) => {
  let { name, email, password } = req.body;
  console.log(name, email, password);

  try {
    console.log(name, email, password);
    const existingUser = await prisma.admin.findFirst({ where: { email } });
    console.log(existingUser);
    if (existingUser)
      return res.status(400).json({ message: "User already exists" });
    const hashedPassword = await bcrypt.hash(password, 10);
    console.log(hashedPassword);
    await prisma.admin.create({
      data: { name, email, password: hashedPassword },
    });

    const token = jwt.sign({ email: email }, SECRET_KEY);

    res.json({ message: "registered successful", token });
  } catch (error) {
    console.log(error);
    res.status(500).json({ error: "Invalid input please try again" });
  }
};

exports.login = async (req, res) => {
  let { email, password } = req.body;
  try {
    const user = await prisma.admin.findUnique({ where: { email } });
    if (!user)
      return res
        .status(401)
        .json({ message: "fail", error: "Account does not exist" });

    const isMatch = await bcrypt.compare(password, user.password);
    if (!isMatch)
      return res
        .status(401)
        .json({ message: "fail", error: "Invalid email or password" });

    const token = jwt.sign({ email: user.email, id: user.id }, SECRET_KEY);

    res.status(200).json({
      message: "success",
      token,
      admin: { id: user.id, name: user.name, email: user.email },
    });
  } catch (error) {
    console.log(error);
    res.status(500).json({ message: "fail", error: error.message });
  }
};
