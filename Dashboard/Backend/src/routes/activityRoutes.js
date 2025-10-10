const express = require('express');
const router = express.Router();
const activityController = require('../controllers/activityController');

router.get('/', activityController.viewActivities);
router.post('/', activityController.addActivity);

module.exports = router;
