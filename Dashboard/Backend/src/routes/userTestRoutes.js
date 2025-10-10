const express = require('express');
const router = express.Router();
const userTestController = require('../controllers/userTestController');

router.post('/', userTestController.addUserTest);

module.exports = router;
