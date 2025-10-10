require('dotenv').config();
const authRoutes = require("./routes/authRoutes");
const express = require('express');
const cors = require('cors');

const app = express();
const port = 3000;

app.use(express.json());
app.use(cors());

//Routes

app.use("/auth", authRoutes);
app.use("/api/admins", require("./routes/adminRoutes"));
app.use("/api/users", require("./routes/userRoutes"));
app.use("/api/tests", require("./routes/testRoutes"));
app.use("/api/userTests", require("./routes/userTestRoutes"));
app.use("/api/activities", require("./routes/activityRoutes"));

app.get("/", (req, res)=>{
    res.send("Server is running");
});

app.listen(port, ()=>{
    console.log(`Server is running on http://localhost:${port}`);
});


