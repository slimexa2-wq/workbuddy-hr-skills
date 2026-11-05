import unittest
import time
import sys
import os

# Add project root to sys.path so we can import ultra_modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from ultra_modules.zhaopin_greeting_personalizer_self_healing_guard import ZhaopinGreetingPersonalizer

class TestZhaopinGreetingPersonalizer(unittest.TestCase):
    def setUp(self):
        self.personalizer = ZhaopinGreetingPersonalizer()

    def test_normal_generation(self):
        result = self.personalizer.generate(
            candidate_name="张三",
            past_companies=["腾讯", "阿里"],
            expected_location="北京"
        )
        self.assertIn("您好 张三，看到您曾在腾讯、阿里工作过，请问您对北京的工作机会感兴趣吗？期待您的回复！", result["greeting"])
        self.assertIn("snapshot_id", result)

    def test_missing_parameters_fallback(self):
        result = self.personalizer.generate()
        self.assertIn("您好 候选人，请问您对我们公司的工作机会感兴趣吗？期待您的回复！", result["greeting"])

    def test_dirty_data_self_healing(self):
        result = self.personalizer.generate(
            candidate_name="  ",
            past_companies=[None, "", "百度", 123], # Invalid items should be ignored
            expected_location=None
        )
        self.assertIn("您好 候选人，看到您曾在百度工作过，请问您对我们公司的工作机会感兴趣吗？期待您的回复！", result["greeting"])

    def test_successful_undo(self):
        result = self.personalizer.generate("李四")
        snapshot_id = result["snapshot_id"]
        success, msg = self.personalizer.undo(snapshot_id)
        self.assertTrue(success)
        self.assertEqual(msg, "Undo successful")
        self.assertEqual(self.personalizer.snapshots[snapshot_id]["status"], "undone")

    def test_undo_failure_after_time_limit(self):
        # Override the time limit for the test to make it run fast
        self.personalizer.UNDO_TIME_LIMIT = 0.1
        result = self.personalizer.generate("王五")
        snapshot_id = result["snapshot_id"]

        # Wait for longer than the limit
        time.sleep(0.2)

        success, msg = self.personalizer.undo(snapshot_id)
        self.assertFalse(success)
        self.assertIn("Undo time limit exceeded", msg)
        self.assertEqual(self.personalizer.snapshots[snapshot_id]["status"], "active")

if __name__ == '__main__':
    unittest.main()
