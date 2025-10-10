const express = require('express');
const router = express.Router();
const testController = require('../controllers/testController');

router.get('/:id', testController.getTestById);
router.post('/', testController.addTest);
router.get('/activeTests', testController.getActiveTests);
router.get('/activeTestsCnt', testController.getActiveTestCount);

module.exports = router;
